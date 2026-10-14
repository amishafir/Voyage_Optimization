#!/usr/bin/env python3
"""Live weather collector: archive every model run for Route 1 and Route 2.

Stores each ECMWF IFS wind run (00/06/12/18 UTC) and each Meteo-France SMOC
currents run (00 UTC) once, with its full hourly series, for every distinct
weather cell of the route's subsegments (collect/collector.py), in one HDF5
archive per route (shared/run_archive.py).

    python3 run_all.py --route all                # both routes, until stopped
    python3 run_all.py --route all --dry-run      # partition and API budget only, no API calls
    python3 run_all.py --route 1 --once           # do whatever is pending now, then exit
    python3 run_all.py --route all --backfill-wind --dry-run   # missed wind runs and their cost
    python3 run_all.py --route all --backfill-wind             # fetch them from the archive

Routes are read from config/routes/<name>.yaml at start-up. If the waypoints
have changed since an archive was created, the program refuses to add to it;
start a new file instead.

The schedule survives restarts: the /runs table of each archive lists every
expected run, and runs that came due while the program was stopped are
fetched if still possible (wind until the next run is published, currents
until the next day's run is published) and otherwise logged as missed.
Missed wind runs can be fetched later with --backfill-wind; missed currents
are lost.

Stop with Ctrl+C or SIGTERM: the current step is finished first (a second
Ctrl+C stops at once).
"""
import argparse
import logging
import os
import signal
import sys
import time
from pathlib import Path

PIPELINE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(PIPELINE_DIR))

from collect.collector import (  # noqa: E402
    API_LIMITS,
    CHUNK_SIZE,
    CURRENT,
    CURRENT_SPAN_H,
    SECONDS_PER_CHUNK,
    WAVE_HEIGHT_NOTE,
    WIND,
    WIND_LAST_LEAD_H,
    ApiClient,
    Pacer,
    PlanMismatch,
    RouteRuns,
    RunCollector,
    build_sampling_plan,
    daily_calls,
    utc,
)
from collect.waypoints import load_route_config  # noqa: E402

logger = logging.getLogger("run_all")

ROUTES = {
    "1": {"name": "Route 1", "route": "persian_gulf_malacca", "hdf5": "route1_runs.h5"},
    "2": {"name": "Route 2", "route": "st_johns_liverpool", "hdf5": "route2_runs.h5"},
}


def parse_args(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--route", required=True, choices=sorted(ROUTES) + ["all"],
                    help="route to collect: 1, 2 or all")
    ap.add_argument("--data-dir", default=str(PIPELINE_DIR / "data"),
                    help="directory of the archives (default: pipeline/data)")
    ap.add_argument("--log-file", help="log file (default: <data-dir>/collector_route<N>.log)")
    ap.add_argument("--dry-run", action="store_true",
                    help="print the API budget (with --backfill-wind: the backfill's cost); "
                         "no API calls")
    ap.add_argument("--once", action="store_true",
                    help="do whatever is pending now, then exit")
    ap.add_argument("--backfill-wind", action="store_true",
                    help="fetch the missed wind runs from the Single Runs archive, then exit")
    return ap.parse_args(argv)


def setup_logging(log_file=None):
    fmt = logging.Formatter("%(asctime)sZ %(levelname)s %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
    fmt.converter = time.gmtime
    handlers = [logging.StreamHandler()]
    if log_file:
        os.makedirs(os.path.dirname(os.path.abspath(log_file)), exist_ok=True)
        handlers.append(logging.FileHandler(log_file))
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    for h in handlers:
        h.setFormatter(fmt)
        root.addHandler(h)


def build_plans(keys):
    plans = {}
    for k in keys:
        route = ROUTES[k]
        cfg = load_route_config({"collection": {"route": route["route"]}})
        plans[k] = build_sampling_plan(cfg["waypoints"], route_key=route["route"],
                                       route_name=cfg.get("name", route["route"]))
    return plans


def budget_report(plans):
    """Lines describing the daily API budget; returns (lines, worst-case calls per day)."""
    wind_hours = sum(WIND_LAST_LEAD_H.values()) + len(WIND_LAST_LEAD_H)   # values per cell per day
    lines, typical, worst, burst = [], 0.0, 0.0, 0.0
    for k, plan in plans.items():
        c = daily_calls(plan)
        n_wind, n_cur = len(plan.queries[WIND]), len(plan.queries[CURRENT])
        fetch = c["wind"] + c["current"]
        typical += fetch + c["probes_typical"]
        worst += fetch + c["probes_max"]
        burst += n_wind + n_cur
        mb = (n_wind * wind_hours + n_cur * CURRENT_SPAN_H) * 2 * 4 / 2**20
        lines.append(
            f"{ROUTES[k]['name']} ({plan.route_key}): {len(plan.waypoints)} waypoints, "
            f"{sum(s.length_nm for s in plan.subsegments):.1f} NM after the port trim, "
            f"{len(plan.subsegments)} subsegments; per day {n_wind} wind cells x 4 runs = "
            f"{c['wind']:.0f} calls, {n_cur} current cells x 1 run = {c['current']:.0f} calls, "
            f"probes about {c['probes_typical']:.0f} (at most {c['probes_max']:.0f}); "
            f"{fetch + c['probes_typical']:.0f} calls typical, {fetch + c['probes_max']:.0f} "
            f"at most; about {mb:.1f} MB of runs per day before compression")
    lines.append(
        f"Total: {typical:.0f} calls per day typical, {worst:.0f} at most, before chunk retries "
        f"and backfills (limit {API_LIMITS['day']} per day per IP). Largest burst, a wind and a "
        f"currents run fetched in the same hour: {burst:.0f} calls (limit {API_LIMITS['hour']} "
        f"per hour); requests paced at <= {CHUNK_SIZE * 60 / SECONDS_PER_CHUNK:.0f} calls per "
        f"minute (limit {API_LIMITS['minute']})")
    return lines, worst


class Shutdown:
    """First SIGINT/SIGTERM: finish the current step, then stop. Second: stop now."""

    def __init__(self):
        self.requested = False
        signal.signal(signal.SIGINT, self._handler)
        signal.signal(signal.SIGTERM, self._handler)

    def _handler(self, signum, frame):
        if self.requested:
            raise KeyboardInterrupt
        self.requested = True
        logger.info("Shutdown requested (%s); finishing the current step",
                    signal.Signals(signum).name)

    def sleep_until(self, t):
        while not self.requested and time.time() < t:
            time.sleep(min(30.0, max(0.0, t - time.time())))


def main(argv=None):
    args = parse_args(argv)
    keys = sorted(ROUTES) if args.route == "all" else [args.route]
    log_file = None
    if not args.dry_run:
        log_file = args.log_file or os.path.join(
            args.data_dir, "collector_" + "_".join(f"route{k}" for k in keys) + ".log")
    setup_logging(log_file)

    plans = build_plans(keys)
    lines, worst = budget_report(plans)
    for line in lines:
        logger.info(line)
    if worst > API_LIMITS["day"]:
        logger.error("At most %.0f calls per day exceed the free limit of %d per IP: run the "
                     "routes on separate machines", worst, API_LIMITS["day"])
        return 1 if args.dry_run else 2
    if args.dry_run and not args.backfill_wind:
        return 0

    paths = {k: os.path.join(args.data_dir, ROUTES[k]["hdf5"]) for k in keys}
    if args.backfill_wind:
        keys = [k for k in keys if os.path.exists(paths[k])]
        if not keys:
            logger.error("No archive to backfill in %s", args.data_dir)
            return 3
    try:
        routes = [RouteRuns(ROUTES[k]["name"], plans[k], paths[k]) for k in keys]
    except PlanMismatch as e:
        logger.error("%s", e)
        return 3
    collector = RunCollector(routes, ApiClient(pacer=Pacer(SECONDS_PER_CHUNK)))

    if args.backfill_wind:
        collector.backfill_wind(dry_run=args.dry_run)
        return 0

    logger.info("Wave height: %s", WAVE_HEIGHT_NOTE)
    logger.info("Archives: %s", ", ".join(paths[k] for k in keys))
    if args.once:
        collector.step()
        return 0
    shutdown = Shutdown()
    while not shutdown.requested:
        wake = collector.step()
        if wake - time.time() > 1800:
            logger.info("Next action at %s", utc(wake))
        shutdown.sleep_until(wake)
    logger.info("Collector stopped.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        logger.info("Collector stopped at once.")
        sys.exit(130)

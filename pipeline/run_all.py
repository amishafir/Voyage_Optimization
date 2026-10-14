#!/usr/bin/env python3
"""Live weather collector for Route 1 and Route 2, sampled by subsegment.

Every 6 hours, a few hours after each ECMWF IFS run becomes available, asks
Open-Meteo once per distinct wind cell and once per distinct current cell of
each selected route (collect/collector.py) and appends one sample to the
route's HDF5 file, with one node per subsegment.

The free API allows 10,000 calls per day per IP. Route 1 costs about 7,400
calls per day and Route 2 about 5,200, so run one route per machine:

    python3 run_all.py --route 1             # Route 1, Persian Gulf -> Strait of Malacca
    python3 run_all.py --route 2             # Route 2, St. John's -> Liverpool
    python3 run_all.py --route all --dry-run # partition and API budget only, no API calls
    python3 run_all.py --route 2 --once --data-dir /tmp/smoke   # one sample now, then exit

Routes are read from config/routes/<name>.yaml at start-up. If the waypoints
have changed since an output file was created, the program refuses to append
to it; start a new file instead.

Stop with Ctrl+C or SIGTERM: the current sample is finished first (a second
Ctrl+C stops at once). Restarting resumes the same files.
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
    FORECAST_DAYS,
    SECONDS_PER_CHUNK,
    WAVE_HEIGHT_NOTE,
    WIND,
    Pacer,
    PlanMismatch,
    RouteCollector,
    build_sampling_plan,
    calls_per_sample,
    previous_slot,
    utc,
)
from collect.waypoints import load_route_config  # noqa: E402
from shared.hdf5_io import PREDICTED_DTYPE  # noqa: E402

logger = logging.getLogger("run_all")

# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

ROUTES = {
    "1": {"name": "Route 1", "route": "persian_gulf_malacca", "hdf5": "route1_subsegments.h5"},
    "2": {"name": "Route 2", "route": "st_johns_liverpool", "hdf5": "route2_subsegments.h5"},
}

# ---------------------------------------------------------------------------
# Timing
# ---------------------------------------------------------------------------

SAMPLE_INTERVAL_HOURS = 6

# Samples are taken at NWP_OFFSET_HOURS after each 00/06/12/18 UTC cycle,
# i.e. at 02, 08, 14 and 20 UTC.
#
# Wind is ECMWF IFS (models=ecmwf_ifs): runs at 00/06/12/18 UTC, updated every
# 6 h (open-meteo.com/en/docs/ecmwf-api). Open-Meteo's model metadata
# (api.open-meteo.com/data/ecmwf_ifs/static/meta.json, read 2026-10-14) had
# the 06 UTC run available on the API at 12:24 UTC, 6.4 h after the cycle
# start. The 00 and 12 UTC runs reach 15 days, and ECMWF's dissemination
# schedule ends them about 1 h later than the 144 h runs at 06 and 18 UTC
# (07:34 vs 12:27 UTC), so they should arrive about 7.5 h after the cycle
# start. 8 h leaves a margin for all four runs.
#
# Currents are Meteo-France SMOC (models=meteofrance_currents): one run per
# day, updated every 24 h (open-meteo.com/en/docs/marine-weather-api); the
# metadata had the 00 UTC run available at 12:05 UTC, so the 14 UTC sample is
# the first to see each new run.
#
# Each sample logs and stores (/samples) the run it was served from, and
# warns when that run is older than MAX_RUN_AGE_HOURS.
NWP_OFFSET_HOURS = 8
MAX_RUN_AGE_HOURS = {
    WIND: NWP_OFFSET_HOURS + SAMPLE_INTERVAL_HOURS / 2,   # one ECMWF cycle behind
    CURRENT: 36.0,                                         # one SMOC day behind
}

# A cycle missed by a restart is still collected if it is at most this late;
# the current conditions are then those of the query time.
LATE_GRACE_SECONDS = 3600


# ---------------------------------------------------------------------------
# Set-up
# ---------------------------------------------------------------------------

def parse_args(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--route", required=True, choices=sorted(ROUTES) + ["all"],
                    help="route to collect: 1, 2 or all (all exceeds the free daily API limit)")
    ap.add_argument("--data-dir", default=str(PIPELINE_DIR / "data"),
                    help="directory of the HDF5 output (default: pipeline/data)")
    ap.add_argument("--log-file", help="log file (default: <data-dir>/collector_route<N>.log)")
    ap.add_argument("--dry-run", action="store_true",
                    help="partition the routes and print the API budget; no API calls")
    ap.add_argument("--once", action="store_true",
                    help="collect the most recent scheduled cycle now, however late, then exit")
    ap.add_argument("--allow-over-budget", action="store_true",
                    help="run even if the planned calls exceed the free daily limit")
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
    """Lines describing the API budget, and the planned calls per day."""
    per_day = 24 // SAMPLE_INTERVAL_HOURS
    lines, total = [], 0.0
    for k, plan in plans.items():
        calls = calls_per_sample(plan)
        n = sum(calls.values())
        total += n
        chunks = sum(-(-len(plan.queries[g]) // CHUNK_SIZE) for g in plan.queries)
        n_times = 24 * FORECAST_DAYS        # hourly values per subsegment and sample
        mb = len(plan.subsegments) * n_times * PREDICTED_DTYPE.itemsize * per_day / 2**20
        lines.append(
            f"{ROUTES[k]['name']} ({plan.route_key}): {len(plan.waypoints)} waypoints, "
            f"{sum(s.length_nm for s in plan.subsegments):.1f} NM after the port trim, "
            f"{len(plan.subsegments)} subsegments, {len(plan.queries[WIND])} wind cells, "
            f"{len(plan.queries[CURRENT])} current cells -> {n:.0f} calls per sample, "
            f"{n * per_day:.0f} per day; {chunks} requests, about "
            f"{chunks * SECONDS_PER_CHUNK / 60:.1f} min per sample; "
            f"predicted_weather grows about {mb:.0f} MB per day before compression")
    lines.append(f"Total: {total:.0f} calls per sample, {total * per_day:.0f} per day at "
                 f"{per_day} samples per day (limits: {API_LIMITS['day']} per day, "
                 f"{API_LIMITS['hour']} per hour, {API_LIMITS['minute']} per minute; "
                 f"paced at <= {CHUNK_SIZE * 60 / SECONDS_PER_CHUNK:.0f} per minute)")
    return lines, total * per_day


class Shutdown:
    """First SIGINT/SIGTERM: finish the current sample, then stop. Second: stop now."""

    def __init__(self):
        self.requested = False
        signal.signal(signal.SIGINT, self._handler)
        signal.signal(signal.SIGTERM, self._handler)

    def _handler(self, signum, frame):
        if self.requested:
            raise KeyboardInterrupt
        self.requested = True
        logger.info("Shutdown requested (%s); finishing the current sample",
                    signal.Signals(signum).name)

    def sleep_until(self, t):
        while not self.requested and time.time() < t:
            time.sleep(min(30.0, max(0.0, t - time.time())))


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

def main(argv=None):
    args = parse_args(argv)
    keys = sorted(ROUTES) if args.route == "all" else [args.route]
    log_file = None
    if not args.dry_run:
        log_file = args.log_file or os.path.join(
            args.data_dir, "collector_" + "_".join(f"route{k}" for k in keys) + ".log")
    setup_logging(log_file)

    plans = build_plans(keys)
    lines, calls_per_day = budget_report(plans)
    for line in lines:
        logger.info(line)
    over = calls_per_day > API_LIMITS["day"]
    if over:
        logger.error("Planned %.0f calls per day exceed the free limit of %d per IP: run one "
                     "route per machine (--route 1 / --route 2)", calls_per_day, API_LIMITS["day"])
    if args.dry_run:
        return 1 if over else 0
    if over and not args.allow_over_budget:
        return 2

    try:
        collectors = [
            RouteCollector(ROUTES[k]["name"], plans[k], os.path.join(args.data_dir, ROUTES[k]["hdf5"]),
                           SAMPLE_INTERVAL_HOURS, NWP_OFFSET_HOURS, MAX_RUN_AGE_HOURS)
            for k in keys
        ]
    except PlanMismatch as e:
        logger.error("%s", e)
        return 3

    logger.info("Wave height: %s", WAVE_HEIGHT_NOTE)
    logger.info("Sampling every %d h at %s UTC; output: %s", SAMPLE_INTERVAL_HOURS,
                ", ".join(f"{(NWP_OFFSET_HOURS + i * SAMPLE_INTERVAL_HOURS) % 24:02d}:00"
                          for i in range(24 // SAMPLE_INTERVAL_HOURS)),
                ", ".join(c.path for c in collectors))

    shutdown = Shutdown()
    pacer = Pacer(SECONDS_PER_CHUNK)
    attempted = set()
    period = SAMPLE_INTERVAL_HOURS * 3600
    while not shutdown.requested:
        now = time.time()
        slot = previous_slot(now, SAMPLE_INTERVAL_HOURS, NWP_OFFSET_HOURS)
        due = [c for c in collectors
               if (c.path, slot) not in attempted and not c.has_sample(slot)]
        if due and (args.once or now - slot <= LATE_GRACE_SECONDS):
            if now - slot > 600:
                logger.warning("Collecting the %s cycle %.0f min late", utc(slot), (now - slot) / 60)
            for c in due:
                if shutdown.requested:
                    break
                attempted.add((c.path, slot))
                try:
                    c.collect(slot, pacer)
                except Exception:
                    logger.exception("[%s] sample at %s failed", c.label, utc(slot))
            if args.once:
                break
            continue
        if args.once:
            logger.info("The %s cycle is already collected; nothing to do", utc(slot))
            break
        target = slot + period
        logger.info("Next sample at %s (in %.0f min)", utc(target), (target - now) / 60)
        shutdown.sleep_until(target)

    logger.info("Collector stopped.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        logger.info("Collector stopped at once.")
        sys.exit(130)

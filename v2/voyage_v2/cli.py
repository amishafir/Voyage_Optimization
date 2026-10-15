"""
Load a voyage from a route's weather archive and print what was loaded;
optionally evaluate arcs.

    python3 -m voyage_v2 ARCHIVE --start "YYYY-MM-DD HH:MM" --eta HOURS [--arc SUB SOG T [TAU]] ...

ARCHIVE is a route archive written by the live collector (e.g. route1_runs.h5).
--start is UTC and is rounded to the nearest quarter hour; --eta is in hours
after the start, a multiple of 0.25. Steps (T, TAU) count quarter hours from
the start; without TAU an arc uses pseudo real-time weather.
"""

from __future__ import annotations

import argparse
import sys

from .core import Ship, Voyage, DEFAULT_SHIP
from .loader import STEP_SECONDS, ReferenceTimeError, VoyageData, load_voyage_data


def _summary(data: VoyageData) -> str:
    a, sub = data.attrs, data.subsegments
    total_nm = float(sub["length_nm"].sum())
    lines = [
        f"Route    {a.get('route_label', '?')}: {a.get('route_name', '?')}  ({data.archive})",
        f"Start    {data.utc(0):%Y-%m-%d %H:%M} UTC"
        + ("" if data.requested_start_unix == data.start_unix else
           f"  (asked {_utc(data, data.requested_start_unix):%Y-%m-%d %H:%M:%S}, rounded to the nearest 0.25 h)"),
        f"ETA      {data.eta_steps / 4:.2f} h = {data.eta_steps} steps, arrival by {data.utc(data.eta_steps):%Y-%m-%d %H:%M} UTC",
        f"Plan     {len(sub):,} subsegments, {total_nm:,.1f} NM, {data.n_cells['wind']} wind cells, "
        f"{data.n_cells['current']} current cells (mean SOG for the ETA {total_nm / (data.eta_steps / 4):.2f} kn)",
    ]
    for grid, runs in data.runs.items():
        label = f"{grid.capitalize():<9}"
        for i, r in enumerate(runs):
            lines.append(f"{label if i == 0 else ' ' * 9}run {r.name}  steps {r.first_step:+d}..{r.last_step:+d} "
                         f"({r.n_hours} h x {r.speed.shape[0]} cells)")
        last = max(r.last_step for r in runs)
        if last < data.eta_steps:
            lines.append(f"{' ' * 9}data ends at step {last} ({data.utc(last):%Y-%m-%d %H:%M} UTC); "
                         f"steps {last + 1}..{data.eta_steps} hold the last value")
    return "\n".join(lines)


def _utc(data: VoyageData, unix: float):
    return data.utc(0) + (data.utc(1) - data.utc(0)) * ((unix - data.start_unix) / STEP_SECONDS)


def _arc_table(voyage: Voyage, arcs) -> str:
    head = (f"{'sub':>5} {'SOG':>6} {'t':>5} {'tau':>5} | {'bearing':>7} {'NM':>6} | {'wind':>6} {'from':>5} {'BN':>3} | "
            f"{'curr':>5} {'to':>5} | {'SWS':>6} {'fuel mt':>9} | sources")
    rows = [head, "-" * len(head)]
    for sub, sog, t, tau in arcs:
        d = voyage.arc_detail(sub, sog, t, tau)
        src = f"wind {d['wind_run']}{' held' if d['wind_held'] else ''}, current {d['current_run']}" \
              f"{' held' if d['current_held'] else ''}"
        rows.append(f"{sub:>5} {sog:>6.2f} {t:>5} {('-' if tau is None else tau):>5} | {d['bearing_deg']:>7.1f} "
                    f"{d['length_nm']:>6.3f} | {d['wind_speed_kmh']:>6.1f} {d['wind_from_deg']:>5.0f} {d['beaufort']:>3} | "
                    f"{d['current_speed_kmh']:>5.2f} {d['current_to_deg']:>5.0f} | {d['sws_kn']:>6.2f} "
                    f"{d['fuel_mt']:>9.5f} | {src}")
    return "\n".join(rows)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="python3 -m voyage_v2", description=__doc__.split("\n\n")[0].strip())
    p.add_argument("archive", help="route weather archive (HDF5, collector layout model-runs-v1)")
    p.add_argument("--start", required=True, help='voyage start, UTC: "YYYY-MM-DD HH:MM"')
    p.add_argument("--eta", required=True, type=float, help="ETA in hours after the start (multiple of 0.25)")
    p.add_argument("--ship", default=str(DEFAULT_SHIP), help="ship particulars (YAML)")
    p.add_argument("--arc", nargs="+", action="append", metavar="SUB SOG T [TAU]", default=[],
                   help="evaluate an arc: subsegment, SOG [kn], step, information step (optional)")
    args = p.parse_args(argv)

    arcs = []
    for a in args.arc:
        if len(a) not in (3, 4):
            p.error(f"--arc takes SUB SOG T [TAU], got {' '.join(a)}")
        arcs.append((int(a[0]), float(a[1]), int(a[2]), int(a[3]) if len(a) == 4 else None))

    try:
        data = load_voyage_data(args.archive, args.start, args.eta)
    except (ReferenceTimeError, ValueError, OSError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    print(_summary(data))
    voyage = Voyage(data, Ship.from_yaml(args.ship))
    if arcs:
        print()
        print(_arc_table(voyage, arcs))
    return 0

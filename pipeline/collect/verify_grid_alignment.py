"""
Check the subsegment partition against the live Open-Meteo APIs.

For a route, asks each API which grid point serves
  - the midpoint of sampled subsegments, and
  - the points `delta` NM before and after sampled cell boundaries,
and compares it with the grid point predicted by shared/weather_grids.py.
A boundary passes when both sides match, which places it within `delta` NM
of where the API switches cells. It also reports any point whose weather
value comes back missing (NaN), which happens when no sea cell is in reach.

Uses about (midpoints + 2 * boundaries) API calls per grid; Open-Meteo's
free tier allows 600 per minute and 10,000 per day, and the script stays
under 400 per minute.

    python3 -m collect.verify_grid_alignment config/routes/st_johns_liverpool.yaml
"""

from __future__ import annotations

import argparse
import json
import random
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from shared.rhumb import RhumbLeg  # noqa: E402
from shared.subsegments import partition_route, trim_route  # noqa: E402
from shared.weather_grids import DEFAULT_GRIDS  # noqa: E402

# One cheap variable per grid: the response's coordinates, and whether its value is NaN.
PROBE_VARIABLE = {"wind": "wind_speed_10m", "current": "ocean_current_velocity"}
CHUNK = 100
SECONDS_PER_CHUNK = 15.0
MATCH_TOL_DEG = 1e-4  # the API reports float32 coordinates


def served_points(grid, variable, points):
    """(lat, lon, value) for each of `points`: the grid point the API uses and its
    current value of `variable` (None when the API reports NaN)."""
    out = []
    for start in range(0, len(points), CHUNK):
        chunk = points[start:start + CHUNK]
        params = {
            "latitude": ",".join(f"{p[0]:.6f}" for p in chunk),
            "longitude": ",".join(f"{p[1]:.6f}" for p in chunk),
            "current": variable,
            "forecast_days": 1,
            **grid.api_params,
        }
        url = f"{grid.api_url}?{urllib.parse.urlencode(params)}"
        for attempt in range(5):
            try:
                with urllib.request.urlopen(url, timeout=60) as r:
                    body = json.load(r)
                break
            except urllib.error.HTTPError as e:
                if e.code != 429 or attempt == 4:
                    raise
                time.sleep(60)
        body = body if isinstance(body, list) else [body]
        out += [(b["latitude"], b["longitude"], b.get("current", {}).get(variable)) for b in body]
        if start + CHUNK < len(points):
            time.sleep(SECONDS_PER_CHUNK)
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("route_yaml")
    ap.add_argument("--midpoints", type=int, default=300,
                    help="subsegment midpoints to check (0 or more than the count: all)")
    ap.add_argument("--boundaries", type=int, default=100, help="cell boundaries to check")
    ap.add_argument("--delta-nm", type=float, default=0.01)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()

    with open(args.route_yaml) as f:
        waypoints = yaml.safe_load(f)["waypoints"]
    subs = partition_route(waypoints)
    points = trim_route(waypoints)
    legs = [RhumbLeg(*a, *b) for a, b in zip(points, points[1:])]
    leg_start = [sum(leg.length_nm for leg in legs[:i]) for i in range(len(legs))]

    def point(leg_idx, route_nm):
        leg = legs[leg_idx]
        return leg.point_at((route_nm - leg_start[leg_idx]) / leg.length_nm)

    rng = random.Random(args.seed)
    mids = subs if not 0 < args.midpoints < len(subs) else rng.sample(subs, args.midpoints)
    # Boundaries inside a leg, where at least one grid changes cell.
    pairs = [(a, b) for a, b in zip(subs, subs[1:])
             if a.leg == b.leg and min(a.length_nm, b.length_nm) > 2 * args.delta_nm]
    pairs = rng.sample(pairs, min(args.boundaries, len(pairs)))

    checks = [(f"mid #{s.index}", s.leg, s.start_nm + s.length_nm / 2, s) for s in mids]
    for a, b in pairs:
        checks.append((f"before #{b.index}", a.leg, b.start_nm - args.delta_nm, a))
        checks.append((f"after #{b.index}", b.leg, b.start_nm + args.delta_nm, b))
    points = [point(leg, d) for _, leg, d, _ in checks]

    print(f"{args.route_yaml}: {len(subs)} subsegments; checking {len(mids)} midpoints "
          f"and {len(pairs)} boundaries (+-{args.delta_nm} NM), {len(points)} points per grid")
    for name, grid in DEFAULT_GRIDS.items():
        served = served_points(grid, PROBE_VARIABLE[name], points)
        misses, nans = [], []
        for (label, _, d, s), p, got in zip(checks, points, served):
            want = grid.center_of(s.cells[name])
            if abs(want[0] - got[0]) > MATCH_TOL_DEG or abs(want[1] - got[1]) > MATCH_TOL_DEG:
                misses.append((label, d, p, want, got))
            if got[2] is None:
                nans.append((label, d, p, got))
        print(f"  {name} ({grid.name}, {grid.api_params}): "
              f"{len(points) - len(misses)}/{len(points)} served by the predicted grid point, "
              f"{len(nans)} NaN values")
        for label, d, p, want, got in sorted(misses, key=lambda m: m[1]):
            print(f"    {label:>13} at {d:8.2f} NM ({p[0]:.4f}, {p[1]:.4f}): "
                  f"predicted ({want[0]:.5f}, {want[1]:.5f}), served ({got[0]:.5f}, {got[1]:.5f})")
        for label, d, p, got in sorted(nans, key=lambda m: m[1]):
            print(f"    NaN {label:>9} at {d:8.2f} NM ({p[0]:.4f}, {p[1]:.4f}), "
                  f"served by ({got[0]:.5f}, {got[1]:.5f})")


if __name__ == "__main__":
    main()

"""
Partition a route into subsegments.

A subsegment is a maximal stretch of the route on which the vessel holds one
bearing (it lies on one leg between consecutive waypoints) and stays in one
cell of every weather grid. A new subsegment therefore starts at every
waypoint and at every point where the route crosses a cell edge of the wind
grid or of the current grid (see shared/weather_grids.py).

This replaces the old scheme of sampling every 5 or 25 NM, whose sample
spacing had no relation to where the weather can actually change.

Usage:
    from shared.subsegments import partition_route
    subsegments = partition_route([(47.57, -52.71), (48.80, -47.50), ...])

    python3 -m shared.subsegments config/routes/st_johns_liverpool.yaml
"""

from __future__ import annotations

import argparse
import csv
import statistics
from dataclasses import dataclass
from typing import Dict, Hashable, List, Mapping, Optional, Sequence, Tuple

from shared.rhumb import RhumbLeg
from shared.weather_grids import DEFAULT_GRIDS

# Two breakpoints closer than this (about 2 mm) are one breakpoint, e.g. where
# the route passes through a corner of a cell and crosses two edges at once.
MERGE_TOL_NM = 1e-6


@dataclass(frozen=True)
class Subsegment:
    index: int                    # 0-based position along the route
    leg: int                      # runs from waypoint `leg` to waypoint `leg + 1`
    start_lat: float
    start_lon: float
    length_nm: float
    start_nm: float               # distance of the start from the route origin
    bearing_deg: float            # constant along the leg
    cells: Dict[str, Hashable]    # grid name -> cell the whole subsegment lies in

    @property
    def end_nm(self) -> float:
        return self.start_nm + self.length_nm


def _as_lat_lon(waypoint) -> Tuple[float, float]:
    """Accept (lat, lon) pairs or route-YAML style {'lat': ..., 'lon': ...}."""
    if isinstance(waypoint, Mapping):
        return float(waypoint["lat"]), float(waypoint["lon"])
    lat, lon = waypoint
    return float(lat), float(lon)


def partition_route(waypoints: Sequence, grids: Optional[Mapping] = None) -> List[Subsegment]:
    """Split the route through `waypoints` into subsegments.

    Args:
        waypoints: Route waypoints in sailing order, as (lat, lon) pairs or as
            dicts with 'lat' and 'lon' keys (the format of config/routes/*.yaml).
            Consecutive waypoints are joined by rhumb lines.
        grids: Mapping from a name to a weather grid. Defaults to the wind
            and current grids of shared.weather_grids.

    Returns:
        The subsegments in sailing order. Their lengths add up to the route
        length, and each one starts at the previous one's end.
    """
    grids = DEFAULT_GRIDS if grids is None else grids
    points = [_as_lat_lon(w) for w in waypoints]
    if len(points) < 2:
        raise ValueError("a route needs at least two waypoints")

    subsegments: List[Subsegment] = []
    route_nm = 0.0
    for leg_idx, ((lat1, lon1), (lat2, lon2)) in enumerate(zip(points, points[1:])):
        leg = RhumbLeg(lat1, lon1, lat2, lon2)
        if leg.length_nm < MERGE_TOL_NM:
            continue  # repeated waypoint

        fractions = sorted(f for grid in grids.values() for f in grid.boundary_fractions(leg))
        breaks = [0.0]
        tol = MERGE_TOL_NM / leg.length_nm
        for f in fractions:
            if f - breaks[-1] > tol and 1.0 - f > tol:
                breaks.append(f)
        breaks.append(1.0)

        for f0, f1 in zip(breaks, breaks[1:]):
            mid_lat, mid_lon = leg.point_at(0.5 * (f0 + f1))
            start_lat, start_lon = leg.point_at(f0)
            subsegments.append(Subsegment(
                index=len(subsegments),
                leg=leg_idx,
                start_lat=start_lat,
                start_lon=start_lon,
                length_nm=(f1 - f0) * leg.length_nm,
                start_nm=route_nm + f0 * leg.length_nm,
                bearing_deg=leg.bearing_deg,
                cells={name: grid.cell_of(mid_lat, mid_lon) for name, grid in grids.items()},
            ))
        route_nm += leg.length_nm
    return subsegments


def write_csv(subsegments: Sequence[Subsegment], path: str, grids: Optional[Mapping] = None) -> None:
    """One row per subsegment, with the grid point each weather grid serves it from."""
    grids = DEFAULT_GRIDS if grids is None else grids
    names = list(grids)
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["index", "leg", "start_lat", "start_lon", "length_nm", "start_nm",
                    "bearing_deg"] + [f"{n}_{k}" for n in names
                                      for k in ("row", "col", "lat", "lon")])
        for s in subsegments:
            row = [s.index, s.leg, f"{s.start_lat:.6f}", f"{s.start_lon:.6f}",
                   f"{s.length_nm:.6f}", f"{s.start_nm:.6f}", f"{s.bearing_deg:.4f}"]
            for n in names:
                lat, lon = grids[n].center_of(s.cells[n])
                row += [*s.cells[n], f"{lat:.6f}", f"{lon:.6f}"]
            w.writerow(row)


def _main() -> None:
    import yaml

    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("route_yaml", help="route file with a 'waypoints:' list")
    ap.add_argument("--csv", help="write the subsegments to this CSV file")
    args = ap.parse_args()

    with open(args.route_yaml) as f:
        waypoints = yaml.safe_load(f)["waypoints"]
    subs = partition_route(waypoints)
    lengths = [s.length_nm for s in subs]
    total = sum(lengths)
    print(f"{args.route_yaml}: {len(waypoints)} waypoints, {total:.2f} NM, "
          f"{len(subs)} subsegments")
    print(f"  length (NM): min {min(lengths):.4f}, median {statistics.median(lengths):.3f}, "
          f"mean {total / len(subs):.3f}, max {max(lengths):.3f}")
    for cut in (0.01, 0.1, 0.5):
        print(f"  shorter than {cut} NM: {sum(l < cut for l in lengths)}")
    for name in DEFAULT_GRIDS:
        print(f"  distinct {name} cells: {len({s.cells[name] for s in subs})}")
    if args.csv:
        write_csv(subs, args.csv)
        print(f"  written to {args.csv}")


if __name__ == "__main__":
    _main()

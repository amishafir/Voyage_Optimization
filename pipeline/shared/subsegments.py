"""
Partition a route into subsegments.

A subsegment is a maximal stretch of the route on which the vessel holds one
bearing (it lies on one leg between consecutive waypoints) and stays in one
cell of every weather grid. A new subsegment therefore starts at every
waypoint and at every point where the route crosses a cell edge of the wind
grid or of the current grid (see shared/weather_grids.py).

This replaces the old scheme of sampling every 5 or 25 NM, whose sample
spacing had no relation to where the weather can actually change.

The first and last PORT_TRIM_NM of a route are cut off: leaving and entering
port is not part of voyage planning, and next to the coast the weather APIs
substitute nearby sea cells for land-masked ones.

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

# Distance cut off at each end of the route (port departure and arrival).
PORT_TRIM_NM = 2.0


@dataclass(frozen=True)
class Subsegment:
    index: int                    # 0-based position along the route
    leg: int                      # runs from point `leg` to `leg + 1` of trim_route()
    start_lat: float
    start_lon: float
    length_nm: float
    start_nm: float               # distance from the start of the trimmed route
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


def trim_route(waypoints: Sequence, start_nm: float = PORT_TRIM_NM,
               end_nm: float = PORT_TRIM_NM) -> List[Tuple[float, float]]:
    """The route without its first `start_nm` and its last `end_nm`.

    Returns (lat, lon) points: a new first point `start_nm` along the route,
    the waypoints strictly between the two cuts, and a new last point
    `end_nm` before the end. The new end points lie on the original legs, so
    every leg keeps its bearing.
    """
    points = [_as_lat_lon(w) for w in waypoints]
    if len(points) < 2:
        raise ValueError("a route needs at least two waypoints")
    legs = [RhumbLeg(*a, *b) for a, b in zip(points, points[1:])]
    total = sum(leg.length_nm for leg in legs)
    d0, d1 = start_nm, total - end_nm
    if min(start_nm, end_nm) < 0 or d1 - d0 < MERGE_TOL_NM:
        raise ValueError(f"cannot trim {start_nm} + {end_nm} NM from a {total:.2f} NM route")

    out: List[Tuple[float, float]] = []
    a = 0.0
    for i, leg in enumerate(legs):
        b = a + leg.length_nm
        if b > d0 and a < d1 and leg.length_nm >= MERGE_TOL_NM:
            if not out:
                out.append(leg.point_at((d0 - a) / leg.length_nm) if d0 > a else points[i])
            out.append(leg.point_at((d1 - a) / leg.length_nm) if d1 < b else points[i + 1])
        a = b
    return out


def partition_route(waypoints: Sequence, grids: Optional[Mapping] = None,
                    port_trim_nm: float = PORT_TRIM_NM) -> List[Subsegment]:
    """Split the route through `waypoints` into subsegments.

    Args:
        waypoints: Route waypoints in sailing order, as (lat, lon) pairs or as
            dicts with 'lat' and 'lon' keys (the format of config/routes/*.yaml).
            Consecutive waypoints are joined by rhumb lines.
        grids: Mapping from a name to a weather grid. Defaults to the wind
            and current grids of shared.weather_grids.
        port_trim_nm: Distance cut off at each end of the route; see trim_route.

    Returns:
        The subsegments in sailing order. Their lengths add up to the length
        of the trimmed route, and each one starts at the previous one's end.
    """
    grids = DEFAULT_GRIDS if grids is None else grids
    points = trim_route(waypoints, port_trim_nm, port_trim_nm)

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
    ap.add_argument("--port-trim-nm", type=float, default=PORT_TRIM_NM)
    args = ap.parse_args()

    with open(args.route_yaml) as f:
        waypoints = yaml.safe_load(f)["waypoints"]
    subs = partition_route(waypoints, port_trim_nm=args.port_trim_nm)
    lengths = [s.length_nm for s in subs]
    total = sum(lengths)
    print(f"{args.route_yaml}: {len(waypoints)} waypoints, {total:.2f} NM after cutting "
          f"{args.port_trim_nm} NM at each end, {len(subs)} subsegments")
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

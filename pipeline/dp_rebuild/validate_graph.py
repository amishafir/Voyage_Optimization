"""
DP graph rebuild — structural validator.

Run after `build_nodes.py` / `build_edges.py` to confirm the graph satisfies
the spec in §14.14 / §14.15.

Checks performed:

  C1. **Square uniformity** — every (V band × H band) square must carry a
      single (segment, weather_cell, forecast_window) triple. A mismatch
      means an H line (segment or weather-cell boundary) or V line
      (forecast-window boundary) is missing.

  C2. **Edge weather fidelity** — every edge's stored `weather` must equal
      the weather at the *interior* of the square the edge enters (the
      square just above-and-right of the source node). A mismatch means
      the lookup policy is evaluating the wrong side of a boundary.

  C3. **Topology basics** — source uniqueness, sink placement, SOG in
      [v_min, v_max], Δt > 0, Δd > 0, edges don't overshoot adjacent
      boundaries.

Exit code 0 on full pass, 1 if any check fails.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple

import numpy as np

from build_nodes import GraphConfig, Node, build_nodes, h_line_distances_from_geo
from build_edges import Edge, build_edges, index_nodes
from geo_grid import position_at_d, rhumb_total_nm
from h5_weather import VoyageWeather
from load_route import Route, load_yaml_route, synthesize_multi_window
from route_waypoints import WAYPOINTS


# ---------------------------------------------------------------------------
# Labeling — what physical conditions apply at (t, d)?
# ---------------------------------------------------------------------------

GRID_DEG = 0.5  # marine NWP grid — should match what was used to build H lines


@dataclass(frozen=True)
class SquareLabel:
    segment_id: int
    cell_lat_idx: int
    cell_lon_idx: int
    window_start: float
    window_end: float


def label_at(t: float, d: float, route: Route, voyage: VoyageWeather,
             grid_deg: float = GRID_DEG) -> SquareLabel:
    """Square label using the *same paper-waypoint geometry* the analytic
    H-line generator uses. Segment + (lat, lon) at d come from rhumb
    interpolation along the polyline (`position_at_d`); cell is the
    floor of (lat, lon) over `grid_deg`. This guarantees C1 sees a
    constant label inside each (V band × H band) square as long as the
    H-lines are placed at every segment-boundary AND every cell-crossing
    along the rhumb route — which is what `h_line_distances_from_geo`
    produces.
    """
    lat_at, lon_at, seg_idx = position_at_d(d, WAYPOINTS)
    window = route.window_for_time(t)
    return SquareLabel(
        segment_id=seg_idx,
        cell_lat_idx=int(np.floor(lat_at / grid_deg)),
        cell_lon_idx=int(np.floor(lon_at / grid_deg)),
        window_start=window.start,
        window_end=window.end,
    )


# ---------------------------------------------------------------------------
# C1 — Square uniformity
# ---------------------------------------------------------------------------

def check_square_uniformity(
    nodes: List[Node],
    cfg: GraphConfig,
    route: Route,
    voyage: VoyageWeather,
    samples_per_square: int = 5,
) -> Tuple[int, List[str]]:
    """Verify every V×H square has one and only one (seg, cell, window) triple.

    For each square, sample `samples_per_square` interior points on a
    uniform grid and check they all produce the same label.
    """
    v_times = sorted({n.time_h for n in nodes if n.line_type == "V" and not n.is_source})
    h_distances = sorted({n.distance_nm for n in nodes if n.line_type == "H"})

    # Time bands: [0, v_times[0]), [v_times[0], v_times[1]), ..., [v_times[-2], v_times[-1]]
    t_edges = [0.0] + v_times
    # Distance bands: [0, h_distances[0]), ..., [h_distances[-2], h_distances[-1]]
    d_edges = [0.0] + h_distances

    total_squares = 0
    mismatches: List[str] = []

    for i in range(len(t_edges) - 1):
        t_lo, t_hi = t_edges[i], t_edges[i + 1]
        if t_hi - t_lo < 1e-9:
            continue
        for j in range(len(d_edges) - 1):
            d_lo, d_hi = d_edges[j], d_edges[j + 1]
            if d_hi - d_lo < 1e-9:
                continue
            total_squares += 1
            labels = set()
            for a in np.linspace(0.1, 0.9, samples_per_square):
                for b in np.linspace(0.1, 0.9, samples_per_square):
                    t_s = t_lo + a * (t_hi - t_lo)
                    d_s = d_lo + b * (d_hi - d_lo)
                    labels.add(label_at(t_s, d_s, route, voyage))
                    if len(labels) > 1:
                        break
                if len(labels) > 1:
                    break
            if len(labels) > 1:
                mismatches.append(
                    f"  SQUARE t∈[{t_lo:.2f},{t_hi:.2f}] d∈[{d_lo:.2f},{d_hi:.2f}] "
                    f"has {len(labels)} distinct labels: {labels}"
                )
    return total_squares, mismatches


# ---------------------------------------------------------------------------
# C2 — Edge weather fidelity
# ---------------------------------------------------------------------------

def check_edge_weather(
    edges: List[Edge],
    nodes: List[Node],
    voyage: VoyageWeather,
    sample_size: int = 2000,
    grid_deg: float = GRID_DEG,
) -> List[str]:
    """Sample edges; verify stored weather matches the enter-square center.

    Probe at the center of the enter-square using the **cell-canonical**
    lookup (`cell_weather_at_d` over the paper-waypoint polyline) — the
    same policy `lookup_source_state` in build_edges.py applies. So this
    check now verifies the new Qg5(b) per-cell mean aggregation, not the
    old nearest-waypoint lookup.
    """
    from bisect import bisect_right

    mismatches: List[str] = []
    if not edges:
        return mismatches

    v_times_sorted = sorted({n.time_h for n in nodes if n.line_type == "V" and not n.is_source})
    h_dist_sorted = sorted({n.distance_nm for n in nodes if n.line_type == "H"})

    rng = np.random.default_rng(0)
    sample_idx = rng.choice(len(edges), size=min(sample_size, len(edges)), replace=False)

    for k in sample_idx:
        e = edges[int(k)]
        iv = bisect_right(v_times_sorted, e.src_t)
        ih = bisect_right(h_dist_sorted, e.src_d)
        next_v = v_times_sorted[iv] if iv < len(v_times_sorted) else None
        next_h = h_dist_sorted[ih] if ih < len(h_dist_sorted) else None
        t_in = (e.src_t + next_v) / 2.0 if next_v is not None else e.src_t
        d_in = (e.src_d + next_h) / 2.0 if next_h is not None else e.src_d
        wx_interior = voyage.cell_weather_at_d(
            d_in, waypoints=WAYPOINTS, sample_hour=0, grid_deg=grid_deg,
        )
        # Compare field-by-field with nan handling
        for f, stored in (
            ("wind_speed_10m_kmh", e.weather.wind_speed_10m_kmh),
            ("wind_direction_10m_deg", e.weather.wind_direction_10m_deg),
            ("beaufort_number", e.weather.beaufort_number),
            ("wave_height_m", e.weather.wave_height_m),
            ("ocean_current_velocity_kmh", e.weather.ocean_current_velocity_kmh),
            ("ocean_current_direction_deg", e.weather.ocean_current_direction_deg),
        ):
            interior = wx_interior[f]
            stored_val = float(stored)
            interior_val = float(interior)
            if np.isnan(stored_val) and np.isnan(interior_val):
                continue
            if abs(stored_val - interior_val) > 1e-4:
                mismatches.append(
                    f"  Edge ({e.src_t:.2f},{e.src_d:.2f})→({e.dst_t:.2f},{e.dst_d:.2f}) "
                    f"{f}: stored={stored_val} interior@({t_in:.3f},{d_in:.3f})={interior_val}"
                )
                break  # one field mismatch per edge is enough
    return mismatches


# ---------------------------------------------------------------------------
# C3 — Topology basics
# ---------------------------------------------------------------------------

def check_topology(nodes: List[Node], edges: List[Edge], cfg: GraphConfig) -> List[str]:
    problems: List[str] = []

    sources = [n for n in nodes if n.is_source]
    if len(sources) != 1:
        problems.append(f"  Source count = {len(sources)}, expected 1")
    else:
        s = sources[0]
        if abs(s.time_h) > 1e-9 or abs(s.distance_nm) > 1e-9:
            problems.append(f"  Source not at (0,0): {s}")

    non_sink_at_L = sum(1 for n in nodes
                        if abs(n.distance_nm - cfg.length_nm) < 1e-9 and not n.is_sink)
    if non_sink_at_L:
        problems.append(f"  {non_sink_at_L} nodes at d=L but not flagged is_sink")

    bad_sog = bad_dt = bad_dd = 0
    for e in edges:
        if e.sog < cfg.v_min - 1e-6 or e.sog > cfg.v_max + 1e-6:
            bad_sog += 1
        if e.dst_t - e.src_t <= 0:
            bad_dt += 1
        if e.dst_d - e.src_d <= 0:
            bad_dd += 1
    if bad_sog:
        problems.append(f"  {bad_sog} edges with SOG outside [{cfg.v_min}, {cfg.v_max}]")
    if bad_dt:
        problems.append(f"  {bad_dt} edges with Δt ≤ 0")
    if bad_dd:
        problems.append(f"  {bad_dd} edges with Δd ≤ 0")

    # First-line-crossed rule: dst_t ≤ next V time after src_t OR
    #                          dst_d ≤ next H distance after src_d
    # Equivalently: the edge doesn't overshoot BOTH adjacent boundaries.
    # (Cheap to check on a sample.)
    v_times_sorted = sorted({n.time_h for n in nodes if n.line_type == "V" and not n.is_source})
    h_dist_sorted = sorted({n.distance_nm for n in nodes if n.line_type == "H"})
    from bisect import bisect_right

    overshoot = 0
    rng = np.random.default_rng(1)
    sample_idx = rng.choice(len(edges), size=min(2000, len(edges)), replace=False)
    for k in sample_idx:
        e = edges[int(k)]
        i_v = bisect_right(v_times_sorted, e.src_t)
        i_h = bisect_right(h_dist_sorted, e.src_d)
        next_v = v_times_sorted[i_v] if i_v < len(v_times_sorted) else None
        next_h = h_dist_sorted[i_h] if i_h < len(h_dist_sorted) else None
        if next_v is not None and next_h is not None:
            # At least one of the dst coordinates must be at/before the adjacent boundary.
            if e.dst_t > next_v + 1e-6 and e.dst_d > next_h + 1e-6:
                overshoot += 1
    if overshoot:
        problems.append(f"  {overshoot}/{len(sample_idx)} sampled edges overshoot both boundaries")

    return problems


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------

def main() -> int:
    yaml_path = Path(__file__).resolve().parent.parent.parent / \
        "Dynamic speed optimization" / "weather_forecasts.yaml"
    h5_path = Path(__file__).resolve().parent.parent / "data" / "voyage_weather.h5"

    print("Loading route + HDF5 weather …")
    route = load_yaml_route(yaml_path)
    route = synthesize_multi_window(route, window_h=6.0)
    voyage = VoyageWeather(h5_path)

    cfg = GraphConfig(
        length_nm=rhumb_total_nm(WAYPOINTS),
        eta_h=route.eta_h,
        dt_h=6.0,
        zeta_nm=1.0,
        tau_h=0.1,
        weather_cell_nm=30.0,
        v_min=9.0,
        v_max=13.0,
    )
    h_lines = h_line_distances_from_geo(cfg, WAYPOINTS, grid_deg=GRID_DEG)
    nodes = build_nodes(cfg, route, h_line_distances=h_lines)
    edges = build_edges(cfg, nodes, voyage, route, WAYPOINTS,
                        sample_hour=0, grid_deg=GRID_DEG)
    print(f"  {len(nodes):,} nodes, {len(edges):,} edges, "
          f"{len(h_lines)} H lines, "
          f"{sum(1 for n in nodes if n.line_type == 'V' and not n.is_source)//4000 or 1} × V lines")

    exit_code = 0

    # C1
    print("\n[C1] Square uniformity …")
    total, mism = check_square_uniformity(nodes, cfg, route, voyage)
    print(f"     Total squares checked: {total:,}")
    if mism:
        print(f"     MISMATCHES: {len(mism)}")
        for line in mism[:20]:
            print(line)
        if len(mism) > 20:
            print(f"     … and {len(mism) - 20} more")
        exit_code = 1
    else:
        print("     PASS — every square has a single (segment, cell, window) triple.")

    # C2
    print("\n[C2] Edge weather fidelity (sample 2000) …")
    mism2 = check_edge_weather(edges, nodes, voyage, sample_size=2000)
    if mism2:
        print(f"     MISMATCHES: {len(mism2)}")
        for line in mism2[:10]:
            print(line)
        if len(mism2) > 10:
            print(f"     … and {len(mism2) - 10} more")
        exit_code = 1
    else:
        print("     PASS — edge.weather matches enter-square interior for every sampled edge.")

    # C3
    print("\n[C3] Topology basics …")
    topo = check_topology(nodes, edges, cfg)
    if topo:
        print("     ISSUES:")
        for line in topo:
            print(line)
        exit_code = 1
    else:
        print("     PASS — source/sink/SOG/Δt/Δd/first-line-crossed all OK.")

    print(f"\nValidator exit code: {exit_code}")
    return exit_code


if __name__ == "__main__":
    sys.exit(main())

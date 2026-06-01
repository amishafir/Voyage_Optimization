"""
DP graph rebuild — atomic-edge builder.

One graph, one edge type. Each emitted edge is a single sub-arc that
traverses one cell at one *target* SOG (the captain's decision). Speed
change happens only at H-line crossings (in SR DP) or V-lines (Luo).
The atomic-edge graph is shared by both DP modes; Luo is implemented as
a Bellman-side state augmentation, not a separate edge set.

Per-edge construction:
  - Enumerate 41 target SOGs in [9, 13] kn at 0.1 kn step.
  - For each (src, target_SOG) pick the first frame line crossed:
        if next H-line comes first → snap arrival t to 0.1 h on that H-line,
        else (next V-line first)   → snap arrival d to 1 nm on that V-line.
  - Realized SOG = (Δd / Δt) after snap (slightly off target).
  - Inverse-solve SWS at *realized* SOG with cell-canonical weather +
    paper β; FCR · Δt is the edge fuel scalar (one calculation per edge).

Block-start sample_hour: every sub-arc in block k reads sample_hour = k·6
(matches Luo 2024). Sub-arcs never cross V-lines, so a single sample_hour
applies for the whole edge.

Lazy node interning: the builder discovers nodes BFS-style from the
source (0, 0); only (t, d) pairs that some edge actually lands on become
graph nodes. The returned `(nodes, edges)` pair plugs straight into the
existing `BellmanSolver`.

Spec reference: docs/meeting_prep_2026_05_11.md §2.1.4.
"""

from __future__ import annotations

import sys
from bisect import bisect_right
from collections import deque
from dataclasses import dataclass
from math import isnan
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

_PIPELINE_ROOT = Path(__file__).resolve().parent.parent
if str(_PIPELINE_ROOT) not in sys.path:
    sys.path.insert(0, str(_PIPELINE_ROOT))

from shared.physics import (  # noqa: E402
    calculate_fuel_consumption_rate,
    calculate_sws_from_sog,
)

from weather import Weather  # noqa: E402
from nodes import Node  # noqa: E402
from frame import Frame  # noqa: E402


# ----------------------------------------------------------------------
# AtomicEdge — Bellman-compatible (matches Edge field set + adds target_sog)
# ----------------------------------------------------------------------

@dataclass(frozen=True)
class AtomicEdge:
    """One sub-arc through one cell at one target SOG.

    Mirrors the ``AtomicEdge`` struct in ``pipeline/dp_cpp/src/atomic_edges.hpp``.
    Field names match ``build_edges.Edge`` so ``BellmanSolver`` works on
    ``List[AtomicEdge]`` without modification.

    ``crosses_v_line``: True iff this arc reaches a V-line as its terminal
    boundary. Used by Luo DP to release the SOG lock at block boundaries.
    V-line arcs always set this; H-line arcs do NOT (even if they happen to
    snap onto a V-line time) unless they were clipped to a V-line because
    their snapped time overshot one.
    """
    src_t: float
    src_d: float
    dst_t: float
    dst_d: float
    sog: float            # REALIZED SOG = Δd / Δt (post-snap) — physics
    target_sog: float     # DECISION SOG (Luo lock label)
    weather: Weather      # cell-canonical weather at src_d, block sample_hour
    heading_deg: float    # paper-β at src_d
    sws: float            # SWS inverse-solved at realized SOG
    fcr_mt_per_h: float   # 0.000706 · sws³
    fuel_mt: float        # FCR · (dst_t - src_t)
    crosses_v_line: bool = False


# ----------------------------------------------------------------------
# Per-source edge enumeration
# ----------------------------------------------------------------------

_SWS_MAX_FEASIBLE = 25.0


def _emit_from_src(
    src_t: float,
    src_d: float,
    frame: Frame,
    forecast_hour: Optional[int] = None,
    override_sample_hour: Optional[int] = None,
    perturber=None,
) -> List[AtomicEdge]:
    """Enumerate every atomic edge out of (src_t, src_d).

    Returns an empty list if the source coincides with the sink (d = L)
    or if cell-canonical weather at src_d is NaN (Port B coastal gap).

    `override_sample_hour`: if set, used for ALL edges (matches today's
    single-snapshot behavior and the test HDF5 which only has hours 0–11).
    If `None`, uses block-start sample_hour (Luo 2024 spec).

    `perturber`: optional `WeatherPerturber`. If supplied, the cell-canonical
    weather is post-processed by `perturber.perturb(base, src_t, src_d, waypoints)`
    BEFORE the SWS inverse-solve — injects within-block temporal variation
    that SR DP can exploit at H-line crossings (and Luo cannot).
    """
    if abs(src_d - frame.cfg.length_nm) < 1e-9:
        return []

    # Time-varying sample_hour pick (mirror of pipeline/dp_cpp/src/atomic_edges.cpp,
    # commit 752ae0b). override_sample_hour is not None  → legacy static mode.
    # override_sample_hour is None  → active_sample_hour(src_t), with NaN walkback
    # through sh_list to the most recent valid sample at the same cell.
    #
    # frame.base_sample_hour anchors the voyage start (departure-time sweep);
    # 0 (default) means "use sh_list[0]" — legacy behaviour preserved.
    sh_list = frame.voyage.sample_hours
    if override_sample_hour is not None:
        sample_hour = override_sample_hour
    elif not sh_list:
        return []
    else:
        sh_base_arg = frame.base_sample_hour if frame.base_sample_hour else None
        sample_hour = frame.voyage.active_sample_hour(src_t, sh_base=sh_base_arg)

    weather = frame.cell_weather_at(src_d, sample_hour, forecast_hour)
    if weather.has_nan() and override_sample_hour is None:
        # Walk back through sh_list to most recent valid sample at this cell.
        idx = bisect_right(sh_list, sample_hour) - 1
        while idx > 0 and weather.has_nan():
            idx -= 1
            weather = frame.cell_weather_at(src_d, sh_list[idx], forecast_hour)
            if not weather.has_nan():
                sample_hour = sh_list[idx]
                break
    if weather.has_nan():
        return []

    if perturber is not None:
        weather = perturber.perturb(weather, t_h=src_t, d_nm=src_d,
                                    waypoints=frame.waypoints)
        if weather.has_nan():
            return []
    weather_dict = {
        "wind_speed_10m_kmh": weather.wind_speed_10m_kmh,
        "wind_direction_10m_deg": weather.wind_direction_10m_deg,
        "beaufort_number": weather.beaufort_number,
        "wave_height_m": weather.wave_height_m,
        "ocean_current_velocity_kmh": weather.ocean_current_velocity_kmh,
        "ocean_current_direction_deg": weather.ocean_current_direction_deg,
    }
    heading = frame.paper_heading_at(src_d)

    next_v = frame.next_v_time(src_t)
    next_h = frame.next_h_distance(src_d)
    if next_v is None and next_h is None:
        return []

    L = frame.cfg.length_nm
    eps = 1e-9

    edges: List[AtomicEdge] = []

    for target_sog in frame.sog_grid():
        dt_to_h = ((next_h - src_d) / target_sog) if next_h is not None else 1e18
        dt_to_v = (next_v - src_t) if next_v is not None else 1e18

        # Prefer the closer boundary, BUT if H-line snap collapses dst_t back to
        # src_t (H-line is too close given the τ_h grid), fall back to the
        # V-line target. Mirrors C++ atomic_edges.cpp lines 57–62.
        use_h = (dt_to_h <= dt_to_v + eps) and (next_h is not None)
        h_too_close = False
        if use_h and next_v is not None:
            snapped_t = frame.snap_h_dst_t(src_t + dt_to_h)
            if snapped_t <= src_t + eps:
                use_h = False
                h_too_close = True

        # crosses_v_line: V-line arcs always; H-line arcs whose snapped time
        # overshoots the next V-line are clipped to it and also count.
        crosses_v_line = not use_h

        if use_h:
            dst_d = next_h
            dst_t = frame.snap_h_dst_t(src_t + dt_to_h)
            if next_v is not None and dst_t > next_v - eps:
                dst_t = next_v
                crosses_v_line = True
        else:
            if next_v is None:
                continue
            dst_t = next_v
            dst_d_raw = src_d + target_sog * dt_to_v
            dst_d = frame.snap_v_dst_d(dst_d_raw)
            if dst_d > L:
                dst_d = L
            # Clip to next_h only when H-line was legitimately chosen as the
            # first boundary (not when we fell back to V-line because H was
            # too close — that would create a zero-distance edge).
            if (not h_too_close) and next_h is not None and dst_d > next_h - eps:
                dst_d = next_h

        dt = dst_t - src_t
        dd = dst_d - src_d
        if dt <= eps or dd <= eps:
            continue

        # Realized SOG from snap geometry. We deliberately do NOT clamp to
        # [v_min, v_max] — that's a *decision-grid* range, not an engine
        # bound. The engine bound is SWS ≤ SWS_MAX_FEASIBLE below.
        # Mirrors C++ atomic_edges.cpp lines 97–104.
        realized_sog = dd / dt

        sws = calculate_sws_from_sog(
            target_sog=realized_sog,
            weather=weather_dict,
            ship_heading_deg=heading,
            ship_parameters=None,
        )
        if sws != sws or sws > _SWS_MAX_FEASIBLE:  # NaN or engine-bound
            continue
        fcr = calculate_fuel_consumption_rate(sws)
        fuel = fcr * dt
        if isnan(fuel):
            continue

        edges.append(AtomicEdge(
            src_t=src_t, src_d=src_d,
            dst_t=dst_t, dst_d=dst_d,
            sog=realized_sog,
            target_sog=target_sog,
            weather=weather,
            heading_deg=heading,
            sws=sws,
            fcr_mt_per_h=fcr,
            fuel_mt=fuel,
            crosses_v_line=crosses_v_line,
        ))

    return edges


# ----------------------------------------------------------------------
# BFS edge build with lazy node interning
# ----------------------------------------------------------------------

def _line_type_at(t: float, d: float, frame: Frame) -> str:
    """Best-effort label for the Node line_type field. Bellman doesn't use it,
    but validators may; default 'V' for nodes on V-lines, 'H' otherwise."""
    eps = 1e-6
    for vt in frame.v_line_times:
        if abs(t - vt) < eps:
            return "V"
    if abs(t) < eps:  # source at t = 0 sits on the implicit V-line
        return "V"
    return "H"


def build_atomic_edges(
    frame: Frame,
    forecast_hour: Optional[int] = None,
    override_sample_hour: Optional[int] = None,
    perturber=None,
    verbose: bool = False,
) -> Tuple[List[Node], List[AtomicEdge]]:
    """Build the atomic-edge graph by BFS from the source.

    Walks the (t, d) plane, emitting every feasible atomic edge from each
    discovered node and interning dst (t, d) pairs as new nodes. Returns
    `(nodes, edges)` ready for `BellmanSolver`.

    `override_sample_hour`: if set, all edges read weather at this single
    sample_hour (matches today's behavior). If `None`, edges use block-start
    sample_hour per Luo 2024 spec (requires HDF5 to cover all block hours).

    `perturber`: optional `WeatherPerturber` for stress-testing — wraps the
    cell-canonical weather lookup to inject within-block temporal variation.
    """
    L = frame.cfg.length_nm
    eps_key = 9

    # node_index: (rounded t, rounded d) -> Node
    node_index: Dict[Tuple[float, float], Node] = {}

    def _intern(t: float, d: float) -> Node:
        k = (round(t, eps_key), round(d, eps_key))
        if k in node_index:
            return node_index[k]
        is_source = (k == (0.0, 0.0))
        is_sink = abs(d - L) < 1e-9
        node = Node(
            time_h=t,
            distance_nm=d,
            line_type=_line_type_at(t, d, frame),
            is_source=is_source,
            is_sink=is_sink,
        )
        node_index[k] = node
        return node

    src_node = _intern(0.0, 0.0)
    queue: deque = deque([src_node])
    visited: Set[Tuple[float, float]] = set()

    edges: List[AtomicEdge] = []
    while queue:
        n = queue.popleft()
        nk = (round(n.time_h, eps_key), round(n.distance_nm, eps_key))
        if nk in visited:
            continue
        visited.add(nk)

        if n.is_sink:
            continue  # no outgoing edges from sink

        out = _emit_from_src(
            n.time_h, n.distance_nm, frame,
            forecast_hour=forecast_hour,
            override_sample_hour=override_sample_hour,
            perturber=perturber,
        )
        for e in out:
            edges.append(e)
            dst_node = _intern(e.dst_t, e.dst_d)
            dk = (round(dst_node.time_h, eps_key), round(dst_node.distance_nm, eps_key))
            if dk not in visited:
                queue.append(dst_node)

        if verbose and len(visited) % 5000 == 0:
            print(f"  …{len(visited)} nodes visited, {len(edges)} edges so far")

    nodes = list(node_index.values())
    return nodes, edges


# ----------------------------------------------------------------------
# Summary
# ----------------------------------------------------------------------

def summarize(nodes: List[Node], edges: List[AtomicEdge]) -> None:
    print("=" * 72)
    print("DP rebuild — atomic-edge graph summary")
    print("=" * 72)
    n_v = sum(1 for n in nodes if n.line_type == "V")
    n_h = sum(1 for n in nodes if n.line_type == "H")
    n_sink = sum(1 for n in nodes if n.is_sink)
    n_src = sum(1 for n in nodes if n.is_source)
    print(f"Nodes:           {len(nodes):,} "
          f"(V={n_v:,}, H={n_h:,}, source={n_src}, sink={n_sink})")
    print(f"Edges:           {len(edges):,}")
    if not edges:
        print("=" * 72)
        return

    fuels = [e.fuel_mt for e in edges]
    swss = [e.sws for e in edges if not isnan(e.sws)]
    target_sogs = [e.target_sog for e in edges]
    realized_sogs = [e.sog for e in edges]
    fan = len(edges) / max(1, sum(1 for n in nodes if not n.is_sink))
    print(f"Avg fan-out:     {fan:.2f} edges per non-sink node")
    print(f"Target SOG:      {len(set(target_sogs))} distinct values, "
          f"[{min(target_sogs):.1f}, {max(target_sogs):.1f}] kn")
    print(f"Realized SOG:    [{min(realized_sogs):.4f}, {max(realized_sogs):.4f}] kn  "
          f"(post-snap)")
    if swss:
        print(f"SWS range:       [{min(swss):.3f}, {max(swss):.3f}] kn  "
              f"(mean {sum(swss)/len(swss):.3f})")
    print(f"Fuel/edge:       [{min(fuels):.5f}, {max(fuels):.4f}] mt  "
          f"(mean {sum(fuels)/len(fuels):.4f})")
    print("=" * 72)


# ----------------------------------------------------------------------
# Smoke test
# ----------------------------------------------------------------------

if __name__ == "__main__":
    import time
    from frame import from_route as _frame_from_route
    from weather import VoyageWeather
    from route import load_yaml_route, synthesize_multi_window
    from route_waypoints import WAYPOINTS

    yaml_path = Path(__file__).resolve().parent.parent / \
        "config" / "routes" / "persian_gulf_malacca_paper.yaml"
    h5_path = Path(__file__).resolve().parent.parent / "data" / "voyage_weather.h5"

    route = load_yaml_route(yaml_path)
    route = synthesize_multi_window(route, window_h=6.0)
    voyage = VoyageWeather(h5_path)

    frame = _frame_from_route(route, voyage, WAYPOINTS)
    print(f"Frame: V-lines={len(frame.v_line_times)}, "
          f"H-lines={len(frame.h_line_distances)}, "
          f"SOGs={len(frame.sog_grid())}\n")

    t0 = time.time()
    # override_sample_hour=0: matches today's single-snapshot behavior on the
    # test HDF5 (which only has hours 0..11). Drop once hourly data covers
    # the full voyage and per-block sample_hour can be used.
    nodes, edges = build_atomic_edges(frame, override_sample_hour=0, verbose=True)
    print(f"\nBuild time: {time.time() - t0:.2f} s\n")
    summarize(nodes, edges)

    # Optional smoke test: build with a stress-test perturber and confirm
    # the call surface works end-to-end.
    import os
    if os.environ.get("DP_REBUILD_STRESS_SMOKE"):
        from weather_perturb import WeatherPerturber
        print("\n--- stress-perturber smoke test ---")
        perturber = WeatherPerturber(
            mode="random_walk_ou", sigma_wind=15.0, sigma_wave=1.0,
            tau_h=4.0, seed=42,
        )
        t0 = time.time()
        nodes_p, edges_p = build_atomic_edges(
            frame, override_sample_hour=0, perturber=perturber,
        )
        print(f"perturbed build: {len(nodes_p):,} nodes, {len(edges_p):,} edges, "
              f"{time.time() - t0:.1f} s")

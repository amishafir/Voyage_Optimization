"""
End-to-end runner for the rebuilt graph: one atomic-edge graph,
two Bellman modes (Free DP, Luo DP).

Spec reference: docs/meeting_prep_2026_05_11.md §2 — single edge set,
Luo realized as a Bellman-side SOG-lock state augmentation.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from bellman import BellmanSolver
from bellman_locked import BellmanSolverLocked
from build_atomic_edges import build_atomic_edges, summarize as summarize_edges
from build_edges_locked import simulate_steady_voyage
from frame import from_route as frame_from_route, summarize as summarize_frame
from h5_weather import VoyageWeather
from load_route import load_yaml_route, synthesize_multi_window
from route_waypoints import WAYPOINTS


def _print_header(title: str) -> None:
    print()
    print("=" * 78)
    print(title)
    print("=" * 78)


def main() -> None:
    yaml_path = _HERE.parent.parent / "Dynamic speed optimization" / "weather_forecasts.yaml"
    h5_path = _HERE.parent / "data" / "voyage_weather.h5"

    route = load_yaml_route(yaml_path)
    route = synthesize_multi_window(route, window_h=6.0)
    voyage = VoyageWeather(h5_path)

    _print_header("DP REBUILD — frame")
    frame = frame_from_route(route, voyage, WAYPOINTS)
    summarize_frame(frame)

    # ---- Build the atomic-edge graph (single graph, both DP modes) ----
    _print_header("DP REBUILD — build atomic-edge graph")
    t0 = time.time()
    nodes, edges = build_atomic_edges(frame, override_sample_hour=0)
    build_t = time.time() - t0
    print(f"\nBuild time:  {build_t:.2f} s")
    summarize_edges(nodes, edges)

    # ---- Free DP ----
    _print_header("DP REBUILD — Free DP (no SOG lock)")
    t0 = time.time()
    free = BellmanSolver(nodes, edges)
    free.solve()
    free_res = free.result(eta_mode="hard", eta=frame.cfg.eta_h)
    free_solve_t = time.time() - t0
    print(f"  Total fuel:        {free_res.total_fuel_mt:.3f} mt")
    print(f"  Voyage time:       {free_res.voyage_time_h:.3f} h")
    print(f"  Sink:              {free_res.sink_node}")
    print(f"  Schedule length:   {len(free_res.schedule)} edges")
    print(f"  Solve time:        {free_solve_t:.3f} s")
    print(f"  NaN edges skipped: {free_res.nan_edges_skipped}")

    # ---- Luo DP ----
    _print_header("DP REBUILD — Luo DP (SOG-lock per 6 h block)")
    t0 = time.time()
    luo = BellmanSolverLocked(nodes, edges, set(frame.v_line_times))
    luo.solve()
    luo_res = luo.result(eta_h=frame.cfg.eta_h)
    luo_solve_t = time.time() - t0
    print(f"  Total fuel:        {luo_res.total_fuel_mt:.3f} mt")
    print(f"  Voyage time:       {luo_res.voyage_time_h:.3f} h")
    print(f"  Sink:              {luo_res.sink_node}")
    print(f"  Schedule length:   {len(luo_res.schedule)} edges")
    print(f"  Solve time:        {luo_solve_t:.3f} s")
    print(f"  States reached:    {luo_res.states_reached:,}")
    print(f"  Distinct locks:    {luo_res.distinct_locks_used} / {len(frame.sog_grid())}")

    # Block-locked invariant: every 6 h block in the Luo schedule must
    # have exactly one distinct target_sog.
    by_block: dict = {}
    for e in luo_res.schedule:
        block = int(e.src_t // frame.cfg.dt_h)
        by_block.setdefault(block, set()).add(round(e.target_sog, 4))
    one_sog_blocks = sum(1 for s in by_block.values() if len(s) == 1)
    print(f"  Lock invariant:    {one_sog_blocks}/{len(by_block)} blocks have a single target SOG")
    assert one_sog_blocks == len(by_block), "Luo lock invariant violated!"

    # ---- Steady-SOG baseline (continuous resim, for reference) ----
    _print_header("BASELINE — steady SOG = L / ETA")
    target_sog = frame.cfg.length_nm / frame.cfg.eta_h
    res = simulate_steady_voyage(
        L=frame.cfg.length_nm,
        eta_h=frame.cfg.eta_h,
        route=route,
        voyage=voyage,
        h_line_distances=frame.h_line_distances,
        waypoints=WAYPOINTS,
        target_sog=target_sog,
        sample_hour=0,
    )
    if res is not None:
        _final_t, _final_d, base_fuel, _, _, _, _ = res
        print(f"  Target SOG: {target_sog:.3f} kn")
        print(f"  Total fuel: {base_fuel:.3f} mt")
    else:
        base_fuel = float("nan")
        print("  Steady-SOG infeasible (engine bound).")

    # ---- Summary ----
    _print_header("SUMMARY — single graph, two DP modes")
    print(f"  Baseline (steady SOG):  {base_fuel:.3f} mt")
    print(f"  Free DP:                {free_res.total_fuel_mt:.3f} mt  "
          f"(Δ vs baseline {free_res.total_fuel_mt - base_fuel:+.3f} mt)")
    print(f"  Luo DP:                 {luo_res.total_fuel_mt:.3f} mt  "
          f"(Δ vs baseline {luo_res.total_fuel_mt - base_fuel:+.3f} mt)")
    print(f"  Δ Luo - Free:           {luo_res.total_fuel_mt - free_res.total_fuel_mt:+.3f} mt  "
          f"(Luo ≥ Free by construction)")
    print()
    print("  Single graph used by both DPs:")
    print(f"    {len(nodes):,} nodes, {len(edges):,} atomic edges, build {build_t:.1f} s")
    print(f"    Solve: Free {free_solve_t:.2f} s, Luo {luo_solve_t:.2f} s")


if __name__ == "__main__":
    main()

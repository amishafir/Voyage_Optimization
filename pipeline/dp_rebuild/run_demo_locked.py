"""
End-to-end demo for the LOCKED-mode rebuild graph.

Same node set as the free-DP graph, but the edges are 6h block edges
(one constant SWS held over the full block, simulated forward through
every H-line crossing). Compares directly to `run_demo.py`'s 367.561 mt.

Run:
    python3 pipeline/dp_rebuild/run_demo_locked.py
"""

from __future__ import annotations

import time
from math import isnan
from pathlib import Path

from bellman import BellmanSolver
from build_edges_locked import build_locked_edges, summarize_locked, verify_locked_schedule
from build_nodes import GraphConfig, build_nodes, h_line_distances_from_geo
from geo_grid import rhumb_total_nm
from h5_weather import VoyageWeather
from load_route import load_yaml_route, synthesize_multi_window
from route_waypoints import WAYPOINTS


def main() -> None:
    repo_root = Path(__file__).resolve().parent.parent.parent
    h5_path = repo_root / "pipeline" / "data" / "voyage_weather.h5"
    yaml_path = repo_root / "Dynamic speed optimization" / "weather_forecasts.yaml"

    print("[1] Loading route + HDF5 weather …")
    route = synthesize_multi_window(load_yaml_route(yaml_path), window_h=6.0)
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

    print("[2] Building V/H lines + nodes (geo H-lines, same as free-DP) …")
    h_lines = h_line_distances_from_geo(cfg, WAYPOINTS, grid_deg=0.5)
    nodes = build_nodes(cfg, route, h_line_distances=h_lines)
    print(f"     {len(nodes):,} nodes, {len(h_lines)} H lines")

    print("[3] Building LOCKED edges (one SWS per 6h block, cell-canonical weather) …")
    t0 = time.time()
    edges = build_locked_edges(
        cfg, route, voyage,
        h_line_distances=h_lines,
        waypoints=WAYPOINTS,
        sample_hour=0,
        zeta_d_locked=1.0,
        tau_h_locked=0.1,
    )
    print(f"     {len(edges):,} locked edges  (build time {time.time() - t0:.1f}s)")
    summarize_locked(edges)

    print("[4] Solving forward Bellman DP on the locked graph …")
    t0 = time.time()
    solver = BellmanSolver(nodes, edges)
    solver.solve()
    print(f"     solved in {time.time() - t0:.2f}s")

    result = solver.result(eta_mode="hard", eta=cfg.eta_h)

    print()
    print("=" * 72)
    print("BELLMAN RESULT  (LOCKED mode, hard ETA)")
    print("=" * 72)
    print(f"  Route:             Persian Gulf → Strait of Malacca")
    print(f"  L = {cfg.length_nm:.2f} nm   ETA = {cfg.eta_h:.1f} h   "
          f"v ∈ [{cfg.v_min}, {cfg.v_max}] kn")
    print(f"  Decision policy:   one constant SWS per {cfg.dt_h:.0f}h block")
    print("-" * 72)
    print(f"  Total fuel:        {result.total_fuel_mt:>10.3f} mt")
    print(f"  Voyage time:       {result.voyage_time_h:>10.3f} h")
    print(f"  Average SOG:       {cfg.length_nm / result.voyage_time_h:>10.3f} kn")
    print(f"  Schedule length:   {len(result.schedule):>10,} blocks")
    print(f"  Sink:              ({result.sink_node[0]:.3f} h, {result.sink_node[1]:.3f} nm)")
    print(f"  NaN edges skipped: {result.nan_edges_skipped:>10,}")
    print("=" * 72)

    # Block-by-block schedule (a locked schedule is just ~46 blocks)
    print("\nSchedule (block-by-block):")
    print(f"  {'src_t':>6} {'src_d':>9}  {'dst_t':>6} {'dst_d':>9}  "
          f"{'SWS':>6} {'avgSOG':>7} {'#sub':>5} {'fuel':>8}")
    for e in result.schedule:
        sws_s = f"{e.sws:.2f}" if not isnan(e.sws) else "  NaN"
        fuel_s = f"{e.fuel_mt:.4f}" if not isnan(e.fuel_mt) else "    NaN"
        print(f"  {e.src_t:>6.2f} {e.src_d:>9.3f}  "
              f"{e.dst_t:>6.2f} {e.dst_d:>9.3f}  "
              f"{sws_s:>6} {e.sog:>7.3f} {e.sub_legs:>5} {fuel_s:>8}")

    # Sanity check: resimulate the chosen schedule continuously
    print()
    verify = verify_locked_schedule(
        result.schedule, route, voyage,
        h_line_distances=h_lines, L=cfg.length_nm, eta_h=cfg.eta_h,
        waypoints=WAYPOINTS, sample_hour=0,
    )

    # Quick comparison line if free-DP value is known.
    print()
    print("Comparison vs free-DP (per-square decisions):")
    free_dp = 367.561
    diff = result.total_fuel_mt - free_dp
    print(f"  Free DP   (run_demo.py):    {free_dp:>10.3f} mt")
    print(f"  Locked DP (Bellman):        {result.total_fuel_mt:>10.3f} mt")
    if verify:
        print(f"  Locked DP (continuous):     {verify['continuous_fuel']:>10.3f} mt  "
              f"(d_final = {verify['continuous_d']:.3f} nm, Δd = {verify['delta_d']:+.3f} nm)")
    print(f"  Δ (Bellman vs free):        {diff:>+10.3f} mt  "
          f"({diff / free_dp * 100:+.2f}%)")


if __name__ == "__main__":
    main()

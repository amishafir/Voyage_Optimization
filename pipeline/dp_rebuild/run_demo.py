"""
End-to-end demo for the rebuilt DP graph.

Loads the YAML route + voyage_weather.h5, builds nodes + edges (with fuel),
solves forward Bellman, and prints the optimal schedule + total fuel.

Run:
    python3 pipeline/dp_rebuild/run_demo.py
"""

from __future__ import annotations

import time
from math import isnan
from pathlib import Path

from bellman import BellmanSolver
from build_edges import build_edges
from build_nodes import GraphConfig, build_nodes, h_line_distances_from_geo
from geo_grid import rhumb_total_nm
from h5_weather import VoyageWeather
from load_route import load_yaml_route, synthesize_multi_window
from route_waypoints import WAYPOINTS


def main() -> None:
    repo_root = Path(__file__).resolve().parent.parent.parent
    h5_path = repo_root / "pipeline" / "data" / "voyage_weather.h5"
    yaml_path = repo_root / "Dynamic speed optimization" / "weather_forecasts.yaml"

    # 1. Load route + voyage weather
    print("[1] Loading route + HDF5 weather …")
    route = synthesize_multi_window(load_yaml_route(yaml_path), window_h=6.0)
    voyage = VoyageWeather(h5_path)

    # Use the rhumb-sum length from the paper-table waypoints (Qg1..Qg4)
    # instead of YAML's reported sum. Difference is ~0.4 nm out of 3393
    # — paper-rounding — but this keeps the graph self-consistent with the
    # analytic rhumb-vs-grid H-line generator below.
    L_rhumb = rhumb_total_nm(WAYPOINTS)
    print(f"     rhumb-sum L = {L_rhumb:.3f} nm  "
          f"(YAML paper sum: {route.length_nm:.3f} nm, "
          f"Δ = {L_rhumb - route.length_nm:+.3f} nm)")

    cfg = GraphConfig(
        length_nm=L_rhumb,
        eta_h=route.eta_h,
        dt_h=6.0,
        zeta_nm=1.0,
        tau_h=0.1,
        weather_cell_nm=30.0,
        v_min=9.0,
        v_max=13.0,
    )

    # 2. Build nodes — H-lines from analytic rhumb-line ↔ 0.5° grid crossings.
    print("[2] Building V/H lines + nodes (geo H-lines) …")
    h_lines = h_line_distances_from_geo(cfg, WAYPOINTS, grid_deg=0.5)
    nodes = build_nodes(cfg, route, h_line_distances=h_lines)
    print(f"     {len(nodes):,} nodes, {len(h_lines)} H lines")

    # 3. Build edges + per-edge fuel
    print("[3] Building edges + SWS inverse + FCR + fuel …")
    t0 = time.time()
    edges = build_edges(cfg, nodes, voyage, route, WAYPOINTS, sample_hour=0)
    print(f"     {len(edges):,} edges  (build time {time.time() - t0:.1f}s)")

    # 4. Solve Bellman
    print("[4] Solving forward Bellman DP …")
    t0 = time.time()
    solver = BellmanSolver(nodes, edges)
    solver.solve()
    solve_time = time.time() - t0
    print(f"     solved in {solve_time:.2f}s  "
          f"({solver.num_canonical_nodes:,} canonical nodes, "
          f"{solver.num_unknown_edges} unknown-source edges)")

    # 5. Result under hard ETA
    result = solver.result(eta_mode="hard", eta=cfg.eta_h)

    print()
    print("=" * 72)
    print("BELLMAN RESULT  (hard ETA)")
    print("=" * 72)
    print(f"  Route:             Persian Gulf → Strait of Malacca")
    print(f"  L = {cfg.length_nm:.2f} nm   ETA = {cfg.eta_h:.1f} h   "
          f"v ∈ [{cfg.v_min}, {cfg.v_max}] kn")
    print(f"  Speed grid:        ζ = {cfg.zeta_nm} nm,  τ = {cfg.tau_h} h,  "
          f"dt_h = {cfg.dt_h} h")
    print("-" * 72)
    print(f"  Total fuel:        {result.total_fuel_mt:>10.3f} mt")
    print(f"  Voyage time:       {result.voyage_time_h:>10.3f} h")
    print(f"  Average SOG:       {cfg.length_nm / result.voyage_time_h:>10.3f} kn")
    print(f"  Schedule length:   {len(result.schedule):>10,} edges")
    print(f"  Sink:              ({result.sink_node[0]:.3f} h, {result.sink_node[1]:.3f} nm)")
    print(f"  Nodes reached:     {result.nodes_reached:>10,}  "
          f"/ {solver.num_canonical_nodes:,} canonical")
    print(f"  Nodes unreached:   {result.nodes_unreached:>10,}")
    print(f"  NaN edges skipped: {result.nan_edges_skipped:>10,}")
    print("=" * 72)

    # 6. Schedule preview
    print("\nSchedule (first 5 + last 5 of {} edges):".format(len(result.schedule)))
    print(f"  {'src_t':>6} {'src_d':>8}  {'dst_t':>6} {'dst_d':>8}  "
          f"{'SOG':>6} {'SWS':>6} {'head':>6} {'fuel':>8}")
    for e in result.schedule[:5]:
        sws_s = f"{e.sws:.2f}" if not isnan(e.sws) else "  NaN"
        fuel_s = f"{e.fuel_mt:.4f}" if not isnan(e.fuel_mt) else "    NaN"
        print(f"  {e.src_t:>6.2f} {e.src_d:>8.2f}  {e.dst_t:>6.2f} {e.dst_d:>8.2f}  "
              f"{e.sog:>6.2f} {sws_s:>6} {e.heading_deg:>6.1f} {fuel_s:>8}")
    print("  ...")
    for e in result.schedule[-5:]:
        sws_s = f"{e.sws:.2f}" if not isnan(e.sws) else "  NaN"
        fuel_s = f"{e.fuel_mt:.4f}" if not isnan(e.fuel_mt) else "    NaN"
        print(f"  {e.src_t:>6.2f} {e.src_d:>8.2f}  {e.dst_t:>6.2f} {e.dst_d:>8.2f}  "
              f"{e.sog:>6.2f} {sws_s:>6} {e.heading_deg:>6.1f} {fuel_s:>8}")

    # 7. Aggregates over the chosen path
    print("\nPath aggregates:")
    swss = [e.sws for e in result.schedule if not isnan(e.sws)]
    sogs = [e.sog for e in result.schedule]
    fcrs = [e.fcr_mt_per_h for e in result.schedule if not isnan(e.fcr_mt_per_h)]
    if swss:
        print(f"  SOG range:  [{min(sogs):.3f}, {max(sogs):.3f}] kn  (mean {sum(sogs)/len(sogs):.3f})")
        print(f"  SWS range:  [{min(swss):.3f}, {max(swss):.3f}] kn  (mean {sum(swss)/len(swss):.3f})")
        print(f"  FCR range:  [{min(fcrs):.4f}, {max(fcrs):.4f}] mt/h "
              f"(mean {sum(fcrs)/len(fcrs):.4f})")


if __name__ == "__main__":
    main()

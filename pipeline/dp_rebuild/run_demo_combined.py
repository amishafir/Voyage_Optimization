"""
Combined-graph demo: free-DP edges UNION locked-DP edges, single Bellman.

Both edge sets share the same node table (verified by the locked builder's
closing assertion). Bellman's relaxation is edge-type agnostic — it just
picks the lowest-cost outgoing arc at every node — so the optimum on the
combined graph satisfies

    combined_fuel  <=  min(free_only_fuel, locked_only_fuel).

This script runs all three Bellman passes and reports them side by side.

Run:
    python3 pipeline/dp_rebuild/run_demo_combined.py
"""

from __future__ import annotations

import time
from collections import Counter
from math import isnan
from pathlib import Path

from bellman import BellmanSolver
from build_edges import Edge, build_edges
from build_edges_locked import LockedEdge, build_locked_edges, simulate_steady_voyage
from build_nodes import GraphConfig, build_nodes, h_line_distances_from_geo
from geo_grid import rhumb_total_nm
from h5_weather import VoyageWeather
from load_route import load_yaml_route, synthesize_multi_window
from route_waypoints import WAYPOINTS


def _classify(edge) -> str:
    return "locked" if isinstance(edge, LockedEdge) else "free"


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

    print("[2] Building V/H lines + nodes (geo H-lines) …")
    h_lines = h_line_distances_from_geo(cfg, WAYPOINTS, grid_deg=0.5)
    nodes = build_nodes(cfg, route, h_line_distances=h_lines)
    print(f"     {len(nodes):,} nodes, {len(h_lines)} H lines")

    print("[3] Building free-DP edges …")
    t0 = time.time()
    edges_free = build_edges(cfg, nodes, voyage, route, WAYPOINTS, sample_hour=0)
    print(f"     {len(edges_free):,} free edges  (build {time.time()-t0:.1f}s)")

    print("[4] Building locked-DP edges (one SWS per 6h block) …")
    t0 = time.time()
    edges_locked = build_locked_edges(
        cfg, route, voyage,
        h_line_distances=h_lines,
        waypoints=WAYPOINTS,
        nodes=nodes,
        sample_hour=0,
        tau_h_locked=0.1,
    )
    print(f"     {len(edges_locked):,} locked edges  (build {time.time()-t0:.1f}s)")

    print("[5] Steady-SOG baseline (constant SOG = L/ETA over the whole voyage) …")
    baseline_sog = cfg.length_nm / cfg.eta_h
    res_baseline = simulate_steady_voyage(
        L=cfg.length_nm, eta_h=cfg.eta_h,
        route=route, voyage=voyage,
        h_line_distances=h_lines, waypoints=WAYPOINTS,
        sample_hour=0,
    )
    if res_baseline is None:
        baseline_fuel = float("nan")
        print(f"     INFEASIBLE at steady SOG {baseline_sog:.3f} kn "
              f"(some sub-leg requires SWS > engine bound)")
    else:
        _bt, _bd, baseline_fuel, n_sub, sws_mean, sws_max, sws_min = res_baseline
        print(f"     SOG = {baseline_sog:.3f} kn  →  {baseline_fuel:.3f} mt  "
              f"({n_sub} sub-legs, SWS [{sws_min:.2f}, {sws_max:.2f}] kn, "
              f"mean {sws_mean:.2f})")

    print("[6] Solving Bellman on each graph …")

    def solve(label, edges):
        t0 = time.time()
        solver = BellmanSolver(nodes, edges)
        solver.solve()
        result = solver.result(eta_mode="hard", eta=cfg.eta_h)
        dt = time.time() - t0
        return solver, result, dt

    s_free, r_free, dt_free = solve("free", edges_free)
    s_lock, r_lock, dt_lock = solve("locked", edges_locked)
    s_comb, r_comb, dt_comb = solve("combined", edges_free + edges_locked)

    print()
    print("=" * 78)
    print("BELLMAN RESULT — three graphs, same nodes, hard ETA = "
          f"{cfg.eta_h:.0f} h")
    print("=" * 78)
    print(f"  {'graph':<22} {'edges':>12} {'fuel (mt)':>12}  {'Δ vs base':>11}  "
          f"{'sched':>6}  {'solve s':>8}")
    print("  " + "-" * 76)
    base_str = f"{baseline_fuel:.3f}" if baseline_fuel == baseline_fuel else "   NaN"
    print(f"  {'baseline (steady SOG)':<22} {'—':>12} {base_str:>12}  "
          f"{'—':>11}  {'1':>6}  {'—':>8}")
    for label, r, edges, dt in [
        ("free (per-square)", r_free, edges_free, dt_free),
        ("locked (6h block)", r_lock, edges_locked, dt_lock),
        ("combined (union)", r_comb, edges_free + edges_locked, dt_comb),
    ]:
        if baseline_fuel == baseline_fuel:
            delta_base = r.total_fuel_mt - baseline_fuel
            delta_str = f"{delta_base:+8.3f}"
        else:
            delta_str = "    —"
        print(f"  {label:<22} {len(edges):>12,} {r.total_fuel_mt:>12.3f}  "
              f"{delta_str:>11}  {len(r.schedule):>6,}  {dt:>8.2f}")
    print("=" * 78)

    delta_free = r_comb.total_fuel_mt - r_free.total_fuel_mt
    delta_lock = r_comb.total_fuel_mt - r_lock.total_fuel_mt
    print(f"  combined − free   : {delta_free:+8.3f} mt   "
          f"(must be ≤ 0; combined ⊇ free)")
    print(f"  combined − locked : {delta_lock:+8.3f} mt   "
          f"(must be ≤ 0; combined ⊇ locked)")
    if baseline_fuel == baseline_fuel:
        delta_b_comb = r_comb.total_fuel_mt - baseline_fuel
        pct = 100.0 * delta_b_comb / baseline_fuel
        print(f"  combined − baseline: {delta_b_comb:+8.3f} mt   "
              f"({pct:+.2f} % vs steady SOG = {baseline_sog:.3f} kn)")
    print()

    # Schedule mix on the combined graph
    mix = Counter(_classify(e) for e in r_comb.schedule)
    print(f"  Combined schedule has {len(r_comb.schedule)} edges: "
          f"{mix['free']} free + {mix['locked']} locked")
    print(f"  Sink:    ({r_comb.sink_node[0]:.3f} h, "
          f"{r_comb.sink_node[1]:.3f} nm)")
    print()

    # First/last 5 schedule lines, with edge type tag
    print("Combined schedule preview (first 5 + last 5):")
    print(f"  {'kind':<6} {'src_t':>6} {'src_d':>9}  {'dst_t':>6} {'dst_d':>9}"
          f"  {'SOG':>6} {'SWS':>6} {'fuel':>8}")
    sched = r_comb.schedule
    for e in sched[:5] + ([None] if len(sched) > 10 else []) + sched[-5:]:
        if e is None:
            print("  ...")
            continue
        sws_s = f"{e.sws:.2f}" if not isnan(e.sws) else "  NaN"
        fuel_s = f"{e.fuel_mt:.4f}" if not isnan(e.fuel_mt) else "    NaN"
        print(f"  {_classify(e):<6} {e.src_t:>6.2f} {e.src_d:>9.3f}  "
              f"{e.dst_t:>6.2f} {e.dst_d:>9.3f}  "
              f"{e.sog:>6.2f} {sws_s:>6} {fuel_s:>8}")


if __name__ == "__main__":
    main()

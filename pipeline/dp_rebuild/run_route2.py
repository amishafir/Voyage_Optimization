"""
End-to-end runner for Route 2 (St. John's → Liverpool).

Single script that:
  1. Loads Route 2 (yaml + HDF5 + computed-bearing waypoints).
  2. Builds the atomic-edge graph.
  3. Solves SR DP, Luo DP, and Baseline (steady SOG = L/ETA).
  4. Classifies every block A/B/C and reports aligned-vs-unaligned breakdown.
  5. Ranks 3-WP windows by SR–Luo divergence and reports the top.
  6. Renders the 4-panel visualization of the most divergent window.

Default sample_hour = 0. Pass `--sample-hour N` to use a different snapshot.
"""

from __future__ import annotations

import argparse
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Dict, List

import numpy as np

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

import cartopy.crs as ccrs
import matplotlib.pyplot as plt
from matplotlib.cm import ScalarMappable
from matplotlib.colors import Normalize

from bellman import BellmanSolver
from bellman_locked import BellmanSolverLocked
from atomic_edges import build_atomic_edges
from build_edges_locked import simulate_steady_voyage
from frame import from_route as frame_from_route
from geo_grid import rhumb_distance_nm, rhumb_grid_crossings
from weather import VoyageWeather
from route import build_route_from_waypoints_yaml, synthesize_multi_window
from visualize_schedules import (
    _draw_mercator,
    _draw_td_frame,
    _overlay_schedule,
    GRID_DEG,
    SOG_COLORMAP,
    SOG_MIN,
    SOG_MAX,
)


YAML_PATH = _HERE.parent / "config" / "routes" / "st_johns_liverpool.yaml"
H5_PATH = _HERE.parent / "data" / "experiment_d_391wp.h5"
RESULTS_DIR = _HERE / "results"
ETA_H = 168.0


def _schedule_to_polyline(schedule):
    pts = [(schedule[0].src_t, schedule[0].src_d)]
    for e in schedule:
        pts.append((e.dst_t, e.dst_d))
    return pts


def _interp_d_at_t(pts, t):
    for i in range(len(pts) - 1):
        t1, d1 = pts[i]
        t2, d2 = pts[i + 1]
        if t1 - 1e-9 <= t <= t2 + 1e-9:
            if t2 == t1:
                return d1
            f = (t - t1) / (t2 - t1)
            return d1 + f * (d2 - d1)
    return pts[0][1] if t < pts[0][0] else pts[-1][1]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample-hour", type=int, default=0,
                    help="HDF5 sample_hour to use (default 0)")
    ap.add_argument("--no-viz", action="store_true",
                    help="Skip rendering the visualization")
    args = ap.parse_args()
    sample_hour = args.sample_hour

    print("=" * 78)
    print(f"Route 2 — St. John's → Liverpool   (sample_hour = {sample_hour})")
    print("=" * 78)

    # ---- Load route + HDF5 ------------------------------------------------
    route, waypoints = build_route_from_waypoints_yaml(YAML_PATH, eta_h=ETA_H)
    route = synthesize_multi_window(route, window_h=6.0)
    voyage = VoyageWeather(H5_PATH)
    frame = frame_from_route(route, voyage, waypoints)
    print(f"Route: L = {frame.cfg.length_nm:.2f} nm, ETA = {frame.cfg.eta_h:.0f} h, "
          f"{len(frame.v_line_times)} V-lines, {len(frame.h_line_distances)} H-lines, "
          f"{len(frame.sog_grid())} target SOGs")

    # ---- Build atomic graph -----------------------------------------------
    print("\nBuilding atomic-edge graph …")
    t0 = time.time()
    nodes, edges = build_atomic_edges(frame, override_sample_hour=sample_hour)
    build_t = time.time() - t0
    print(f"  {len(nodes):,} nodes, {len(edges):,} edges  (build {build_t:.1f} s)")

    # ---- Solve SR + Luo + Baseline --------------------------------------
    print("\nFree DP …")
    t0 = time.time()
    sr = BellmanSolver(nodes, edges)
    sr.solve()
    sr_res = sr.result(eta_mode="hard", eta=frame.cfg.eta_h)
    print(f"  fuel = {sr_res.total_fuel_mt:.3f} mt, time = {sr_res.voyage_time_h:.3f} h, "
          f"sched = {len(sr_res.schedule)} edges  ({time.time()-t0:.2f} s)")

    print("\nLuo DP (SOG-lock per 6 h) …")
    t0 = time.time()
    luo = BellmanSolverLocked(nodes, edges, set(frame.v_line_times))
    luo.solve()
    luo_res = luo.result(eta_h=frame.cfg.eta_h)
    print(f"  fuel = {luo_res.total_fuel_mt:.3f} mt, time = {luo_res.voyage_time_h:.3f} h, "
          f"sched = {len(luo_res.schedule)} edges  ({time.time()-t0:.2f} s)")

    print("\nBaseline (steady SOG = L/ETA) …")
    target_sog = frame.cfg.length_nm / frame.cfg.eta_h
    res = simulate_steady_voyage(
        L=frame.cfg.length_nm, eta_h=frame.cfg.eta_h,
        route=route, voyage=voyage, h_line_distances=frame.h_line_distances,
        waypoints=waypoints, target_sog=target_sog, sample_hour=sample_hour,
    )
    base_fuel = res[2] if res else float("nan")
    print(f"  target SOG = {target_sog:.3f} kn, fuel = {base_fuel:.3f} mt")

    # ---- Headline ---------------------------------------------------------
    print("\n" + "=" * 78)
    print("Route 2 SUMMARY")
    print("=" * 78)
    print(f"  Baseline:  {base_fuel:.3f} mt")
    print(f"  SR DP:   {sr_res.total_fuel_mt:.3f} mt   "
          f"(Δ {sr_res.total_fuel_mt - base_fuel:+.3f} mt, "
          f"{(sr_res.total_fuel_mt - base_fuel)/base_fuel*100:+.3f}%)")
    print(f"  Luo DP:    {luo_res.total_fuel_mt:.3f} mt   "
          f"(Δ {luo_res.total_fuel_mt - base_fuel:+.3f} mt, "
          f"{(luo_res.total_fuel_mt - base_fuel)/base_fuel*100:+.3f}%)")
    print(f"  Δ Luo-SR: {luo_res.total_fuel_mt - sr_res.total_fuel_mt:+.3f} mt")

    # ---- A/B/C overlap analysis ------------------------------------------
    sr_blk: Dict[int, list] = defaultdict(list)
    for e in sr_res.schedule:
        sr_blk[int(e.src_t // 6.0)].append(e)
    luo_blk: Dict[int, list] = defaultdict(list)
    for e in luo_res.schedule:
        luo_blk[int(e.src_t // 6.0)].append(e)

    counts = {"A": 0, "B": 0, "C": 0}
    aligned = 0
    fuel_by_type = {"A": (0.0, 0.0), "B": (0.0, 0.0), "C": (0.0, 0.0)}
    aligned_sr = aligned_luo = 0.0

    for blk in sorted(set(sr_blk) | set(luo_blk)):
        f_eds = sr_blk.get(blk, [])
        l_eds = luo_blk.get(blk, [])
        if not f_eds or not l_eds:
            continue
        f_sogs = sorted({round(e.target_sog, 4) for e in f_eds})
        l_sog = round(l_eds[0].target_sog, 4)
        if len(f_sogs) == 1 and abs(f_sogs[0] - l_sog) < 1e-6:
            t = "A"
        elif len(f_sogs) == 1:
            t = "B"
        else:
            t = "C"
        counts[t] += 1
        f_acc, l_acc = fuel_by_type[t]
        ff = sum(e.fuel_mt for e in f_eds)
        lf = sum(e.fuel_mt for e in l_eds)
        fuel_by_type[t] = (f_acc + ff, l_acc + lf)
        if (abs(f_eds[0].src_d - l_eds[0].src_d) < 1e-3
                and abs(f_eds[-1].dst_d - l_eds[-1].dst_d) < 1e-3):
            aligned += 1
            aligned_sr += ff
            aligned_luo += lf

    print("\nBlock classification (Route 2):")
    print(f"  Type A (SR 1 SOG = Luo's): {counts['A']}")
    print(f"  Type B (SR 1 SOG ≠ Luo's): {counts['B']}")
    print(f"  Type C (SR ≥ 2 SOGs):      {counts['C']}")
    print(f"  TOTAL blocks:                {sum(counts.values())}")
    print(f"  Aligned (✓): {aligned}/{sum(counts.values())}  "
          f"Δfuel on aligned = {aligned_luo - aligned_sr:+.3f} mt")

    # ---- Divergence ranking ----------------------------------------------
    sr_pts = _schedule_to_polyline(sr_res.schedule)
    luo_pts = _schedule_to_polyline(luo_res.schedule)
    full_cum = [0.0]
    for i in range(len(waypoints) - 1):
        w1, w2 = waypoints[i], waypoints[i + 1]
        full_cum.append(full_cum[-1] +
                        rhumb_distance_nm(w1.lat_deg, w1.lon_deg,
                                          w2.lat_deg, w2.lon_deg))

    print("\nDivergence ranking — 3-waypoint windows:")
    print(f"  {'window':>10} {'d-range (nm)':>22} "
          f"{'sr':>9} {'luo':>9} {'Δfuel':>9} {'area':>9} {'max|Δd|':>9}")
    rows = []
    for s in range(1, len(waypoints) - 1):
        d0, d1 = full_cum[s - 1], full_cum[s + 1]
        f_in = [e for e in sr_res.schedule
                if e.src_d >= d0 - 1e-6 and e.dst_d <= d1 + 1e-6]
        l_in = [e for e in luo_res.schedule
                if e.src_d >= d0 - 1e-6 and e.dst_d <= d1 + 1e-6]
        if not f_in or not l_in:
            continue
        ff = sum(e.fuel_mt for e in f_in)
        lf = sum(e.fuel_mt for e in l_in)
        t_lo = max(f_in[0].src_t, l_in[0].src_t)
        t_hi = min(f_in[-1].dst_t, l_in[-1].dst_t)
        if t_hi <= t_lo:
            continue
        sample_t = np.linspace(t_lo, t_hi, 200)
        diff = [abs(_interp_d_at_t(sr_pts, t) - _interp_d_at_t(luo_pts, t))
                for t in sample_t]
        area = float(np.trapezoid(diff, sample_t))
        max_dd = max(diff)
        rows.append((s, d0, d1, ff, lf, area, max_dd))
    rows.sort(key=lambda r: r[5], reverse=True)
    for r in rows:
        s, d0, d1, ff, lf, ar, mx = r
        print(f"  WP{s}-WP{s+2:<5}  [{d0:>7.1f},{d1:>7.1f}]   "
              f"{ff:>9.3f} {lf:>9.3f} {lf-ff:>+9.3f} {ar:>9.2f} {mx:>9.2f}")

    if not rows:
        print("\nNo divergent window data — skipping viz.")
        return

    top_s, d_start, d_end, *_ = rows[0]
    print(f"\nMost divergent: WP{top_s}–WP{top_s+2}")

    if args.no_viz:
        return

    # ---- Visualization: 4-panel for most divergent window ----------------
    print("\nRendering 4-panel visualization …")
    sub_wp = waypoints[top_s - 1: top_s - 1 + 3]
    cumulative = full_cum[top_s - 1: top_s - 1 + 3]
    L_subset = d_end - d_start
    edges_in = [e for e in (sr_res.schedule + luo_res.schedule)
                if d_start - 1e-6 <= e.src_d and e.dst_d <= d_end + 1e-6]
    t_lo = min(e.src_t for e in edges_in)
    t_hi = max(e.dst_t for e in edges_in)

    cell_d_lat: set = set()
    cell_d_lon: set = set()
    cum = d_start
    for i in range(2):
        w1, w2 = sub_wp[i], sub_wp[i + 1]
        for c in rhumb_grid_crossings(
            w1.lat_deg, w1.lon_deg, w2.lat_deg, w2.lon_deg, grid_deg=GRID_DEG,
        ):
            d_voy = round(cum + c.distance_nm, 9)
            (cell_d_lat if c.axis == "lat" else cell_d_lon).add(d_voy)
        cum += rhumb_distance_nm(w1.lat_deg, w1.lon_deg, w2.lat_deg, w2.lon_deg)

    fig = plt.figure(figsize=(26, 8))
    norm = Normalize(vmin=SOG_MIN, vmax=SOG_MAX)
    cmap = plt.get_cmap(SOG_COLORMAP)

    # Panel 1: Mercator
    extent = (min(w.lon_deg for w in sub_wp) - 0.8,
              max(w.lon_deg for w in sub_wp) + 0.8,
              min(w.lat_deg for w in sub_wp) - 0.8,
              max(w.lat_deg for w in sub_wp) + 0.8)
    ax_map = fig.add_subplot(1, 4, 1, projection=ccrs.Mercator())
    _draw_mercator(ax_map, sub_wp, extent)

    # Panel 2: SR
    ax_free = fig.add_subplot(1, 4, 2)
    _draw_td_frame(ax_free, frame, d_start, d_end, t_lo, t_hi,
                   sub_wp, cumulative, cell_d_lat, cell_d_lon)
    _overlay_schedule(ax_free, sr_res.schedule, d_start, d_end, cmap, norm,
                      "SR DP", sr_res.total_fuel_mt, total_blocks_shown=None)

    # Panel 3: Luo
    ax_luo = fig.add_subplot(1, 4, 3)
    _draw_td_frame(ax_luo, frame, d_start, d_end, t_lo, t_hi,
                   sub_wp, cumulative, cell_d_lat, cell_d_lon)
    _overlay_schedule(ax_luo, luo_res.schedule, d_start, d_end, cmap, norm,
                      "Luo DP (SOG-lock per 6 h)", luo_res.total_fuel_mt,
                      total_blocks_shown=None)

    # Panel 4: Overlay with fill_between
    ax_ovr = fig.add_subplot(1, 4, 4)
    _draw_td_frame(ax_ovr, frame, d_start, d_end, t_lo, t_hi,
                   sub_wp, cumulative, cell_d_lat, cell_d_lon)
    f_in = [e for e in sr_res.schedule
            if e.src_d >= d_start - 1e-6 and e.dst_d <= d_end + 1e-6]
    l_in = [e for e in luo_res.schedule
            if e.src_d >= d_start - 1e-6 and e.dst_d <= d_end + 1e-6]
    f_xy = [(e.src_t, e.src_d) for e in f_in] + [(f_in[-1].dst_t, f_in[-1].dst_d)]
    l_xy = [(e.src_t, e.src_d) for e in l_in] + [(l_in[-1].dst_t, l_in[-1].dst_d)]
    f_xs, f_ys = zip(*f_xy)
    l_xs, l_ys = zip(*l_xy)
    common_t = np.linspace(max(f_xs[0], l_xs[0]), min(f_xs[-1], l_xs[-1]), 400)
    f_d = np.interp(common_t, f_xs, f_ys)
    l_d = np.interp(common_t, l_xs, l_ys)
    ax_ovr.fill_between(common_t, f_d, l_d, color="#ffd166", alpha=0.55, zorder=8,
                        label=f"div area {float(np.trapezoid(np.abs(f_d - l_d), common_t)):.1f} nm·h")
    ax_ovr.plot(f_xs, f_ys, color="#1a73e8", linewidth=2.0, zorder=10,
                label=f"SR ({sum(e.fuel_mt for e in f_in):.3f} mt)")
    ax_ovr.plot(l_xs, l_ys, color="#d62728", linewidth=2.0, linestyle="--", zorder=10,
                label=f"Luo  ({sum(e.fuel_mt for e in l_in):.3f} mt)")
    ax_ovr.legend(loc="upper right", fontsize=7, framealpha=0.92)
    ax_ovr.set_title(f"Overlay — max |Δd| = {float(np.max(np.abs(f_d - l_d))):.2f} nm",
                     fontsize=10, pad=8)

    sm = ScalarMappable(cmap=cmap, norm=norm)
    sm.set_array([])
    cbar = fig.colorbar(sm, ax=[ax_free, ax_luo], orientation="horizontal",
                        fraction=0.04, pad=0.10, aspect=40, label="target SOG (kn)")
    cbar.set_ticks([9, 10, 11, 12, 13])

    out = RESULTS_DIR / f"route2_schedules_wp{top_s}-{top_s+2}_sh{sample_hour}.png"
    plt.tight_layout(rect=(0, 0.05, 1, 1))
    plt.savefig(out, dpi=150)
    print(f"Saved: {out}")


if __name__ == "__main__":
    main()

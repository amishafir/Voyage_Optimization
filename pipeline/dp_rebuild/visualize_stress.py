"""
Visualize stress-test schedules — Mercator + Free DP + Luo DP + overlay,
on Route 2's most divergent 3-WP window under a chosen σ.

Defaults to σ_wind = 20 km/h, σ_wave = 1.33 m, seed = 42 (matches the
stress sweep). Picks the most divergent 3-WP window automatically.

Saves: results/stress_schedules_route{R}_sigmaWIND_wpA-B.png
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
from typing import List

import cartopy.crs as ccrs
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.cm import ScalarMappable
from matplotlib.colors import Normalize

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from bellman import BellmanSolver
from bellman_locked import BellmanSolverLocked
from build_atomic_edges import build_atomic_edges
from frame import from_route as frame_from_route
from geo_grid import rhumb_distance_nm, rhumb_grid_crossings
from h5_weather import VoyageWeather
from load_route import build_route_from_waypoints_yaml, synthesize_multi_window
from visualize_schedules import (
    _draw_mercator, _draw_td_frame, _overlay_schedule,
    GRID_DEG, SOG_COLORMAP, SOG_MIN, SOG_MAX,
)
from weather_perturb import WeatherPerturber


def _polyline(schedule):
    pts = [(schedule[0].src_t, schedule[0].src_d)]
    for e in schedule:
        pts.append((e.dst_t, e.dst_d))
    return pts


def _interp_d_at_t(pts, t):
    for i in range(len(pts) - 1):
        t1, d1 = pts[i]
        t2, d2 = pts[i + 1]
        if t1 - 1e-9 <= t <= t2 + 1e-9:
            if t2 == t1: return d1
            f = (t - t1) / (t2 - t1)
            return d1 + f * (d2 - d1)
    return pts[0][1] if t < pts[0][0] else pts[-1][1]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sigma-wind", type=float, default=20.0)
    ap.add_argument("--sigma-wave", type=float, default=None,
                    help="Default = sigma_wind / 15")
    ap.add_argument("--tau-h", type=float, default=4.0)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--sample-hour", type=int, default=0)
    args = ap.parse_args()
    sigma_wave = args.sigma_wave if args.sigma_wave is not None else args.sigma_wind / 15.0

    yaml_path = _HERE.parent / "config" / "routes" / "st_johns_liverpool.yaml"
    h5_path = _HERE.parent / "data" / "experiment_d_391wp.h5"

    print("=" * 88)
    print(f"Stress-test viz — Route 2, σ_wind={args.sigma_wind} km/h, "
          f"σ_wave={sigma_wave:.2f} m, τ={args.tau_h}h, seed={args.seed}")
    print("=" * 88)

    route, waypoints = build_route_from_waypoints_yaml(yaml_path, eta_h=168.0)
    route = synthesize_multi_window(route, window_h=6.0)
    voyage = VoyageWeather(h5_path)
    frame = frame_from_route(route, voyage, waypoints)

    perturber = WeatherPerturber(
        mode="random_walk_ou",
        sigma_wind=args.sigma_wind, sigma_wave=sigma_wave,
        tau_h=args.tau_h, seed=args.seed,
    )

    print("Building stressed graph …")
    t0 = time.time()
    nodes, edges = build_atomic_edges(
        frame, override_sample_hour=args.sample_hour, perturber=perturber,
    )
    print(f"  {len(nodes):,} nodes, {len(edges):,} edges ({time.time()-t0:.1f} s)")

    print("Solving Free DP …")
    free = BellmanSolver(nodes, edges)
    free.solve()
    free_res = free.result(eta_mode="hard", eta=frame.cfg.eta_h)
    print(f"  fuel = {free_res.total_fuel_mt:.3f} mt, sched = {len(free_res.schedule)}")

    print("Solving Luo DP …")
    luo = BellmanSolverLocked(nodes, edges, set(frame.v_line_times))
    luo.solve()
    luo_res = luo.result(eta_h=frame.cfg.eta_h)
    print(f"  fuel = {luo_res.total_fuel_mt:.3f} mt, sched = {len(luo_res.schedule)}")
    print(f"  Δ(Luo - Free) = {luo_res.total_fuel_mt - free_res.total_fuel_mt:+.3f} mt")

    # ---- Find the most divergent 3-WP window under stress ----
    free_pts = _polyline(free_res.schedule)
    luo_pts = _polyline(luo_res.schedule)
    full_cum = [0.0]
    for i in range(len(waypoints) - 1):
        w1, w2 = waypoints[i], waypoints[i + 1]
        full_cum.append(full_cum[-1] +
                        rhumb_distance_nm(w1.lat_deg, w1.lon_deg,
                                          w2.lat_deg, w2.lon_deg))

    rows = []
    for s in range(1, len(waypoints) - 1):
        d0, d1 = full_cum[s - 1], full_cum[s + 1]
        f_in = [e for e in free_res.schedule
                if e.src_d >= d0 - 1e-6 and e.dst_d <= d1 + 1e-6]
        l_in = [e for e in luo_res.schedule
                if e.src_d >= d0 - 1e-6 and e.dst_d <= d1 + 1e-6]
        if not f_in or not l_in: continue
        t_lo = max(f_in[0].src_t, l_in[0].src_t)
        t_hi = min(f_in[-1].dst_t, l_in[-1].dst_t)
        if t_hi <= t_lo: continue
        sample_t = np.linspace(t_lo, t_hi, 200)
        diff = [abs(_interp_d_at_t(free_pts, t) - _interp_d_at_t(luo_pts, t))
                for t in sample_t]
        area = float(np.trapezoid(diff, sample_t))
        max_dd = max(diff)
        rows.append((s, d0, d1, sum(e.fuel_mt for e in f_in),
                     sum(e.fuel_mt for e in l_in), area, max_dd))
    rows.sort(key=lambda r: r[5], reverse=True)
    top_s, d_start, d_end, *_, max_dd = rows[0]
    print(f"\nMost divergent window: WP{top_s}–WP{top_s+2} "
          f"(area = {rows[0][5]:.1f} nm·h, max |Δd| = {max_dd:.1f} nm)")

    # ---- Render 4-panel ----
    sub_wp = waypoints[top_s - 1: top_s - 1 + 3]
    cumulative = full_cum[top_s - 1: top_s - 1 + 3]
    edges_in = [e for e in (free_res.schedule + luo_res.schedule)
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

    extent = (min(w.lon_deg for w in sub_wp) - 0.8,
              max(w.lon_deg for w in sub_wp) + 0.8,
              min(w.lat_deg for w in sub_wp) - 0.8,
              max(w.lat_deg for w in sub_wp) + 0.8)
    ax_map = fig.add_subplot(1, 4, 1, projection=ccrs.Mercator())
    _draw_mercator(ax_map, sub_wp, extent)

    ax_free = fig.add_subplot(1, 4, 2)
    _draw_td_frame(ax_free, frame, d_start, d_end, t_lo, t_hi,
                   sub_wp, cumulative, cell_d_lat, cell_d_lon)
    _overlay_schedule(ax_free, free_res.schedule, d_start, d_end, cmap, norm,
                      f"Free DP @ σ={args.sigma_wind:.0f}", free_res.total_fuel_mt,
                      total_blocks_shown=None)

    ax_luo = fig.add_subplot(1, 4, 3)
    _draw_td_frame(ax_luo, frame, d_start, d_end, t_lo, t_hi,
                   sub_wp, cumulative, cell_d_lat, cell_d_lon)
    _overlay_schedule(ax_luo, luo_res.schedule, d_start, d_end, cmap, norm,
                      f"Luo DP @ σ={args.sigma_wind:.0f}", luo_res.total_fuel_mt,
                      total_blocks_shown=None)

    ax_ovr = fig.add_subplot(1, 4, 4)
    _draw_td_frame(ax_ovr, frame, d_start, d_end, t_lo, t_hi,
                   sub_wp, cumulative, cell_d_lat, cell_d_lon)
    f_in = [e for e in free_res.schedule
            if e.src_d >= d_start - 1e-6 and e.dst_d <= d_end + 1e-6]
    l_in = [e for e in luo_res.schedule
            if e.src_d >= d_start - 1e-6 and e.dst_d <= d_end + 1e-6]
    f_xs, f_ys = zip(*([(e.src_t, e.src_d) for e in f_in]
                        + [(f_in[-1].dst_t, f_in[-1].dst_d)]))
    l_xs, l_ys = zip(*([(e.src_t, e.src_d) for e in l_in]
                        + [(l_in[-1].dst_t, l_in[-1].dst_d)]))
    common_t = np.linspace(max(f_xs[0], l_xs[0]), min(f_xs[-1], l_xs[-1]), 400)
    f_d = np.interp(common_t, f_xs, f_ys)
    l_d = np.interp(common_t, l_xs, l_ys)
    ax_ovr.fill_between(common_t, f_d, l_d, color="#ffd166", alpha=0.55, zorder=8,
                        label=f"div area {float(np.trapezoid(np.abs(f_d - l_d), common_t)):.1f} nm·h")
    ax_ovr.plot(f_xs, f_ys, color="#1a73e8", linewidth=2.0, zorder=10,
                label=f"Free ({sum(e.fuel_mt for e in f_in):.3f} mt)")
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

    out_dir = _HERE / "results"
    out_dir.mkdir(exist_ok=True)
    out = out_dir / f"stress_schedules_route2_sigma{int(args.sigma_wind)}_wp{top_s}-{top_s+2}.png"
    plt.tight_layout(rect=(0, 0.05, 1, 1))
    plt.savefig(out, dpi=150)
    print(f"Saved: {out}")


if __name__ == "__main__":
    main()

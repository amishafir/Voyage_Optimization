"""
Scan all 3-waypoint windows (WPi, WPi+1, WPi+2) and rank by Free vs Luo
divergence inside that window.

Two divergence metrics per window:
  * area_nm_h : area between the two schedules in (t, d) space, by integrating
                |d_free(t) − d_luo(t)| over the window's time range.
  * fuel_diff : Σ(luo_fuel) − Σ(free_fuel) for edges contained in the d-range.

Prints a ranked table; the top window is the best candidate to visualize.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from bellman import BellmanSolver
from bellman_locked import BellmanSolverLocked
from atomic_edges import build_atomic_edges
from frame import from_route as frame_from_route
from geo_grid import rhumb_distance_nm
from weather import VoyageWeather
from route import load_yaml_route, synthesize_multi_window
from route_waypoints import WAYPOINTS


def _schedule_to_polyline(schedule):
    """Schedule -> list of (t, d) breakpoints in order."""
    pts = [(schedule[0].src_t, schedule[0].src_d)]
    for e in schedule:
        pts.append((e.dst_t, e.dst_d))
    return pts


def _interp_d_at_t(pts, t):
    """Linear interpolate d at time t along the polyline."""
    for i in range(len(pts) - 1):
        t1, d1 = pts[i]
        t2, d2 = pts[i + 1]
        if t1 - 1e-9 <= t <= t2 + 1e-9:
            if t2 == t1:
                return d1
            f = (t - t1) / (t2 - t1)
            return d1 + f * (d2 - d1)
    if t < pts[0][0]:
        return pts[0][1]
    return pts[-1][1]


def main() -> None:
    yaml_path = _HERE.parent / "config" / "routes" / "persian_gulf_malacca_paper.yaml"
    h5_path = _HERE.parent / "data" / "voyage_weather.h5"
    route = load_yaml_route(yaml_path)
    route = synthesize_multi_window(route, window_h=6.0)
    voyage = VoyageWeather(h5_path)
    full_frame = frame_from_route(route, voyage, WAYPOINTS)

    print("Building graph + solving Free + Luo …")
    nodes, edges = build_atomic_edges(full_frame, override_sample_hour=0)
    free = BellmanSolver(nodes, edges)
    free.solve()
    free_res = free.result(eta_mode="hard", eta=full_frame.cfg.eta_h)
    luo = BellmanSolverLocked(nodes, edges, set(full_frame.v_line_times))
    luo.solve()
    luo_res = luo.result(eta_h=full_frame.cfg.eta_h)

    free_pts = _schedule_to_polyline(free_res.schedule)
    luo_pts = _schedule_to_polyline(luo_res.schedule)

    # Cumulative distances
    full_cum = [0.0]
    for i in range(len(WAYPOINTS) - 1):
        w1, w2 = WAYPOINTS[i], WAYPOINTS[i + 1]
        full_cum.append(full_cum[-1] +
                        rhumb_distance_nm(w1.lat_deg, w1.lon_deg,
                                          w2.lat_deg, w2.lon_deg))

    print("\n" + "=" * 100)
    print("3-waypoint window divergence — ranked")
    print("=" * 100)
    print(f"  {'window':>14} {'d-range (nm)':>22} "
          f"{'free_fuel':>10} {'luo_fuel':>10} {'Δfuel':>9} "
          f"{'area_nm·h':>10} {'max|Δd|':>9}")
    print("-" * 100)

    rows = []
    n_full = len(WAYPOINTS)
    for s in range(1, n_full - 1):  # 3-wp windows: s, s+1, s+2
        d_start = full_cum[s - 1]
        d_end = full_cum[s + 1]

        # Edges of each schedule that sit inside [d_start, d_end]
        free_in = [e for e in free_res.schedule
                   if e.src_d >= d_start - 1e-6 and e.dst_d <= d_end + 1e-6]
        luo_in = [e for e in luo_res.schedule
                  if e.src_d >= d_start - 1e-6 and e.dst_d <= d_end + 1e-6]
        if not free_in or not luo_in:
            continue
        free_fuel = sum(e.fuel_mt for e in free_in)
        luo_fuel = sum(e.fuel_mt for e in luo_in)

        # Time range over which both polylines are defined
        t_lo = max(free_in[0].src_t, luo_in[0].src_t)
        t_hi = min(free_in[-1].dst_t, luo_in[-1].dst_t)
        if t_hi <= t_lo:
            continue

        # Sample area = ∫ |d_free(t) − d_luo(t)| dt
        sample_t = np.linspace(t_lo, t_hi, 200)
        diff = [abs(_interp_d_at_t(free_pts, t) - _interp_d_at_t(luo_pts, t))
                for t in sample_t]
        area = float(np.trapezoid(diff, sample_t))
        max_dd = max(diff)

        rows.append((s, d_start, d_end, free_fuel, luo_fuel,
                     luo_fuel - free_fuel, area, max_dd))

    # Sort by area (most divergent first)
    rows.sort(key=lambda r: r[6], reverse=True)

    for r in rows:
        s, d0, d1, ff, lf, df, ar, mx = r
        win = f"WP{s}–WP{s+2}"
        print(f"  {win:>14}  [{d0:>7.1f},{d1:>7.1f}]   "
              f"{ff:>10.3f} {lf:>10.3f} {df:>+9.3f} "
              f"{ar:>10.2f} {mx:>9.2f}")

    print("=" * 100)
    if rows:
        top = rows[0]
        print(f"\nMost divergent 3-waypoint window: WP{top[0]}–WP{top[0]+2} "
              f"(area = {top[6]:.2f} nm·h, max |Δd| = {top[7]:.2f} nm).")
        print(f"Run: python3 visualize_schedules.py 3 {top[0]}")


if __name__ == "__main__":
    main()

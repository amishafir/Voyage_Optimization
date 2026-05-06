"""
Visualize the rebuilt graph + Free DP and Luo DP optimal schedules,
side by side.

Layout (3 panels):
  1. Mercator chart of the chosen waypoint subset (default WP1 → WP2 → WP3),
     with rhumb-line segments + 0.5° NWP grid + lat/lon crossings.
  2. (t, d) view with H-lines + V-lines from the new frame, with the
     Free DP optimal schedule's atomic edges overlaid (polyline).
  3. Same (t, d) frame, with the Luo DP optimal schedule's atomic edges
     overlaid.

Edges are colored by target SOG (viridis colormap, 9 kn → 13 kn).

Both schedules are computed for the FULL voyage; only the portion that
fits inside the chosen subset's distance range is plotted, so the
comparison is honest (the optimum the global solver actually picks for
those first 506 nm under hard-ETA = 280 h).

Usage:
  python3 visualize_schedules.py                 # default WP1 → WP2 → WP3
  python3 visualize_schedules.py 4               # WP1 → … → WP4 (n_wp from start)
  python3 visualize_schedules.py 3 7             # n_wp=3 starting at WP7  (→ WP7,8,9)
  python3 visualize_schedules.py 13              # full voyage

Saves to `pipeline/dp_rebuild/visualize_schedules_wp{N}.png`.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import cartopy.crs as ccrs
import cartopy.feature as cfeature
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.cm import ScalarMappable
from matplotlib.colors import Normalize

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from bellman import BellmanSolver  # noqa: E402
from bellman_locked import BellmanSolverLocked  # noqa: E402
from build_atomic_edges import build_atomic_edges  # noqa: E402
from frame import from_route as frame_from_route  # noqa: E402
from geo_grid import (  # noqa: E402
    rhumb_distance_nm,
    rhumb_grid_crossings,
    _mercator_y,
    _inverse_mercator_lat_deg,
)
from h5_weather import VoyageWeather  # noqa: E402
from load_route import load_yaml_route, synthesize_multi_window  # noqa: E402
from route_waypoints import WAYPOINTS  # noqa: E402


GRID_DEG = 0.5
DEFAULT_N_WP = 3
SOG_COLORMAP = "viridis"
SOG_MIN, SOG_MAX = 9.0, 13.0


def _draw_mercator(ax, waypoints, extent):
    ax.set_extent(extent, crs=ccrs.PlateCarree())
    ax.add_feature(cfeature.LAND, facecolor="#f1efea", edgecolor="#7a7367")
    ax.add_feature(cfeature.OCEAN, facecolor="#cee2ec")
    ax.add_feature(cfeature.COASTLINE, linewidth=0.5, color="#5a544a")
    ax.add_feature(cfeature.BORDERS, linestyle=":", linewidth=0.4, color="#7a7367")

    gl = ax.gridlines(
        crs=ccrs.PlateCarree(), draw_labels=True,
        xlocs=np.arange(np.floor(extent[0] / GRID_DEG) * GRID_DEG,
                        np.ceil(extent[1] / GRID_DEG) * GRID_DEG + GRID_DEG / 2,
                        GRID_DEG),
        ylocs=np.arange(np.floor(extent[2] / GRID_DEG) * GRID_DEG,
                        np.ceil(extent[3] / GRID_DEG) * GRID_DEG + GRID_DEG / 2,
                        GRID_DEG),
        color="#a0a0a0", alpha=0.5, linewidth=0.4, linestyle="--",
    )
    gl.top_labels = False
    gl.right_labels = False
    gl.xlabel_style = {"size": 7}
    gl.ylabel_style = {"size": 7}

    for i in range(len(waypoints) - 1):
        w1, w2 = waypoints[i], waypoints[i + 1]
        my1, my2 = _mercator_y(w1.lat_deg), _mercator_y(w2.lat_deg)
        sample_lons = [w1.lon_deg + f * (w2.lon_deg - w1.lon_deg)
                       for f in np.linspace(0, 1, 100)]
        sample_lats = [_inverse_mercator_lat_deg(my1 + f * (my2 - my1))
                       for f in np.linspace(0, 1, 100)]
        ax.plot(sample_lons, sample_lats, color="#c33d4a", linewidth=2.0,
                transform=ccrs.PlateCarree(), zorder=4)
        for c in rhumb_grid_crossings(
            w1.lat_deg, w1.lon_deg, w2.lat_deg, w2.lon_deg, grid_deg=GRID_DEG,
        ):
            color = "#0f7a8b" if c.axis == "lat" else "#e08a25"
            ax.plot(c.lon_deg, c.lat_deg, marker="o", markersize=5,
                    color=color, markeredgecolor="black", markeredgewidth=0.4,
                    transform=ccrs.PlateCarree(), zorder=6)

    for wp in waypoints:
        ax.plot(wp.lon_deg, wp.lat_deg, marker="*", markersize=14,
                color="#222831", markeredgecolor="white", markeredgewidth=1.0,
                transform=ccrs.PlateCarree(), zorder=7)
        ax.text(wp.lon_deg + 0.15, wp.lat_deg + 0.15,
                f"WP{wp.idx}\n({wp.lat_deg:.2f},{wp.lon_deg:.2f})",
                fontsize=7, fontweight="bold",
                transform=ccrs.PlateCarree(), zorder=8,
                bbox=dict(boxstyle="round,pad=0.2", fc="white",
                          ec="#222831", alpha=0.85, lw=0.5))

    wp_chain = " → ".join(f"WP{w.idx}" for w in waypoints)
    ax.set_title(f"Mercator — {wp_chain}", fontsize=10, pad=8)


def _draw_td_frame(ax, frame, d_start, d_end, t_lo, t_hi,
                   waypoints, cumulative, cell_d_lat, cell_d_lon):
    """Draw V-lines + H-lines on a (t, d) panel — shared between Free and Luo."""
    L_subset = d_end - d_start
    eta_span = t_hi - t_lo
    ax.invert_yaxis()
    ax.set_xlim(t_lo - eta_span * 0.05, t_hi + eta_span * 0.18)
    ax.set_ylim(d_end + L_subset * 0.05, d_start - L_subset * 0.05)
    ax.set_xlabel("time from voyage start  (h)")
    ax.set_ylabel("distance from voyage start  (nm)")

    label_y = d_start - L_subset * 0.04
    v_in_range = [t for t in frame.v_line_times if t_lo - 1e-6 <= t <= t_hi + 1e-6]
    for v in v_in_range:
        ax.axvline(v, color="#5870a8", linestyle="--", linewidth=0.9, alpha=0.5)
        if int(v) % 12 == 0:
            ax.text(v, label_y, f"{int(v)}h", color="#5870a8",
                    fontsize=7, ha="center", va="bottom", fontweight="bold")

    seg_boundary_d = set(round(c, 9) for c in cumulative[1:-1])
    h_in_range = [d for d in frame.h_line_distances
                  if d_start - 1e-6 <= d <= d_end + 1e-6]
    for d in h_in_range:
        d_r = round(d, 9)
        if d_r in seg_boundary_d or abs(d - d_end) < 1e-6:
            continue
        if d_r in cell_d_lat:
            ax.axhline(d, color="#0f7a8b", linestyle=":", linewidth=0.5, alpha=0.5)
        elif d_r in cell_d_lon:
            ax.axhline(d, color="#e08a25", linestyle=":", linewidth=0.5, alpha=0.5)
        else:
            ax.axhline(d, color="#888", linestyle=":", linewidth=0.5, alpha=0.35)

    # Source waypoint label (top-left of the slice)
    ax.text(t_lo + eta_span * 0.02, d_start,
            f"WP{waypoints[0].idx}  d={d_start:.1f}",
            fontsize=7, color="#1f4e79", va="center", ha="left",
            fontweight="bold",
            bbox=dict(boxstyle="round,pad=0.2", fc="white",
                      ec="#1f4e79", lw=0.6, alpha=0.9))

    label_x = t_hi + eta_span * 0.02
    for i in range(1, len(waypoints)):
        d = cumulative[i]
        ax.axhline(d, color="red", linestyle="-", linewidth=1.0, alpha=0.85)
        wp = waypoints[i]
        ax.text(label_x, d, f"WP{wp.idx}\nd={d:.1f}",
                fontsize=7, color="#a52a2a", va="center", ha="left",
                fontweight="bold",
                bbox=dict(boxstyle="round,pad=0.2", fc="white",
                          ec="red", lw=0.6, alpha=0.9))


def _overlay_schedule(ax, schedule, d_start, d_end, cmap, norm,
                      title_prefix, total_fuel, total_blocks_shown,
                      annotate_sog: bool = True):
    """Plot atomic edges of a schedule as colored line segments in (t, d).

    With `annotate_sog=True`, each edge gets a small text label at its
    midpoint showing the target SOG (kn) — useful for reading the speed
    pattern directly off the plot.
    """
    edges_in_range = [
        e for e in schedule
        if e.src_d >= d_start - 1e-6 and e.dst_d <= d_end + 1e-6
    ]
    for e in edges_in_range:
        color = cmap(norm(e.target_sog))
        ax.plot([e.src_t, e.dst_t], [e.src_d, e.dst_d],
                color=color, linewidth=1.6, alpha=0.95, zorder=10,
                solid_capstyle="round")
        ax.plot([e.src_t, e.dst_t], [e.src_d, e.dst_d],
                color="white", linewidth=2.6, alpha=0.4, zorder=9,
                solid_capstyle="round")  # halo for visibility over H-line dots

    if annotate_sog:
        # Place SOG label at edge midpoint with white background for readability.
        # Slight horizontal offset alternates per edge so adjacent labels don't
        # overlap when edges share an endpoint.
        for idx, e in enumerate(edges_in_range):
            mid_t = (e.src_t + e.dst_t) / 2.0
            mid_d = (e.src_d + e.dst_d) / 2.0
            color = cmap(norm(e.target_sog))
            ax.text(mid_t, mid_d, f"{e.target_sog:.1f}",
                    fontsize=6, color="black",
                    ha="center", va="center", zorder=12,
                    bbox=dict(boxstyle="round,pad=0.15", fc="white",
                              ec=color, lw=0.6, alpha=0.9))

    n_e = len(edges_in_range)
    sub_total = sum(e.fuel_mt for e in edges_in_range)
    ax.set_title(
        f"{title_prefix} — first {n_e} atomic edges  ·  "
        f"Σ fuel in subset = {sub_total:.3f} mt  "
        f"(global total {total_fuel:.3f} mt)",
        fontsize=10, pad=8,
    )


def main() -> None:
    n_wp = int(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_N_WP
    start_idx = int(sys.argv[2]) if len(sys.argv) > 2 else 1
    if n_wp < 2 or n_wp > len(WAYPOINTS):
        raise SystemExit(f"n_waypoints must be in [2, {len(WAYPOINTS)}], got {n_wp}")
    if start_idx < 1 or start_idx + n_wp - 1 > len(WAYPOINTS):
        raise SystemExit(
            f"start_idx must be in [1, {len(WAYPOINTS) - n_wp + 1}], "
            f"got {start_idx} (with n_wp={n_wp})"
        )

    waypoints = WAYPOINTS[start_idx - 1 : start_idx - 1 + n_wp]
    suffix = (f"wp{start_idx}-{start_idx + n_wp - 1}"
              if start_idx > 1 else f"wp{n_wp}")
    out_path = _HERE / f"visualize_schedules_{suffix}.png"

    # ---- Load full route + frame, build atomic graph, solve Free + Luo ----
    yaml_path = _HERE.parent.parent / "Dynamic speed optimization" / "weather_forecasts.yaml"
    h5_path = _HERE.parent / "data" / "voyage_weather.h5"
    route = load_yaml_route(yaml_path)
    route = synthesize_multi_window(route, window_h=6.0)
    voyage = VoyageWeather(h5_path)
    full_frame = frame_from_route(route, voyage, WAYPOINTS)

    print("Building atomic-edge graph (full voyage) …")
    t0 = time.time()
    nodes, edges = build_atomic_edges(full_frame, override_sample_hour=0)
    print(f"  {len(nodes):,} nodes, {len(edges):,} edges  (build {time.time()-t0:.1f} s)")

    print("Solving Free DP …")
    t0 = time.time()
    free = BellmanSolver(nodes, edges)
    free.solve()
    free_res = free.result(eta_mode="hard", eta=full_frame.cfg.eta_h)
    print(f"  fuel = {free_res.total_fuel_mt:.3f} mt  (solve {time.time()-t0:.2f} s)")

    print("Solving Luo DP …")
    t0 = time.time()
    luo = BellmanSolverLocked(nodes, edges, set(full_frame.v_line_times))
    luo.solve()
    luo_res = luo.result(eta_h=full_frame.cfg.eta_h)
    print(f"  fuel = {luo_res.total_fuel_mt:.3f} mt  (solve {time.time()-t0:.2f} s)")

    # ---- Geometry of the chosen subset (in absolute voyage coordinates) ----
    full_cum = [0.0]
    for i in range(len(WAYPOINTS) - 1):
        w1, w2 = WAYPOINTS[i], WAYPOINTS[i + 1]
        full_cum.append(full_cum[-1] +
                        rhumb_distance_nm(w1.lat_deg, w1.lon_deg,
                                          w2.lat_deg, w2.lon_deg))
    d_start = full_cum[start_idx - 1]
    d_end = full_cum[start_idx - 1 + n_wp - 1]
    L_subset = d_end - d_start

    # Cumulative within the subset (used for axhline label placement)
    cumulative = [full_cum[start_idx - 1 + i] for i in range(n_wp)]

    seg_distances = []
    for i in range(n_wp - 1):
        seg_distances.append(cumulative[i + 1] - cumulative[i])

    # Time range covered by edges that touch [d_start, d_end] in either schedule
    edges_in_subset = [e for e in (free_res.schedule + luo_res.schedule)
                       if d_start - 1e-6 <= e.src_d <= d_end + 1e-6
                       or d_start - 1e-6 <= e.dst_d <= d_end + 1e-6]
    if edges_in_subset:
        t_subset_min = min(e.src_t for e in edges_in_subset)
        t_subset_max = max(e.dst_t for e in edges_in_subset)
    else:
        t_subset_min = 0.0
        t_subset_max = max(72.0, L_subset / 12.0 * 1.05)
    t_axis_lo = t_subset_min
    t_axis_hi = t_subset_max
    eta_h = t_axis_hi - t_axis_lo
    print(f"\nSubset: WP{start_idx}..WP{start_idx + n_wp - 1}, "
          f"{n_wp - 1} segments")
    print(f"  d range:  [{d_start:.2f}, {d_end:.2f}] nm   (L_subset = {L_subset:.2f} nm)")
    print(f"  t range:  [{t_axis_lo:.2f}, {t_axis_hi:.2f}] h "
          f"(span {eta_h:.2f} h)")

    # Cell crossing classification (for axhline coloring) — absolute coords
    cell_d_lat: set = set()
    cell_d_lon: set = set()
    cum = d_start
    for i in range(n_wp - 1):
        w1, w2 = waypoints[i], waypoints[i + 1]
        for c in rhumb_grid_crossings(
            w1.lat_deg, w1.lon_deg, w2.lat_deg, w2.lon_deg, grid_deg=GRID_DEG,
        ):
            d_voy = round(cum + c.distance_nm, 9)
            if c.axis == "lat":
                cell_d_lat.add(d_voy)
            else:
                cell_d_lon.add(d_voy)
        cum += seg_distances[i]

    # ---- Figure: 4 panels (Mercator | Free | Luo | Overlay) ----
    fig = plt.figure(figsize=(26, 8))

    # Panel 1: Mercator
    all_lons = [w.lon_deg for w in waypoints]
    all_lats = [w.lat_deg for w in waypoints]
    extent = (min(all_lons) - 0.8, max(all_lons) + 0.8,
              min(all_lats) - 0.8, max(all_lats) + 0.8)
    ax_map = fig.add_subplot(1, 4, 1, projection=ccrs.Mercator())
    _draw_mercator(ax_map, waypoints, extent)

    # Colormap for target SOG
    norm = Normalize(vmin=SOG_MIN, vmax=SOG_MAX)
    cmap = plt.get_cmap(SOG_COLORMAP)

    # Panel 2: Free DP
    ax_free = fig.add_subplot(1, 4, 2)
    _draw_td_frame(ax_free, full_frame, d_start, d_end, t_axis_lo, t_axis_hi,
                   waypoints, cumulative, cell_d_lat, cell_d_lon)
    _overlay_schedule(ax_free, free_res.schedule, d_start, d_end, cmap, norm,
                      "Free DP", free_res.total_fuel_mt,
                      total_blocks_shown=None)

    # Panel 3: Luo DP
    ax_luo = fig.add_subplot(1, 4, 3)
    _draw_td_frame(ax_luo, full_frame, d_start, d_end, t_axis_lo, t_axis_hi,
                   waypoints, cumulative, cell_d_lat, cell_d_lon)
    _overlay_schedule(ax_luo, luo_res.schedule, d_start, d_end, cmap, norm,
                      "Luo DP (SOG-lock per 6 h)", luo_res.total_fuel_mt,
                      total_blocks_shown=None)

    # Panel 4: Overlay (both schedules together with fill_between for divergence)
    ax_ovr = fig.add_subplot(1, 4, 4)
    _draw_td_frame(ax_ovr, full_frame, d_start, d_end, t_axis_lo, t_axis_hi,
                   waypoints, cumulative, cell_d_lat, cell_d_lon)
    free_in = [e for e in free_res.schedule
               if e.src_d >= d_start - 1e-6 and e.dst_d <= d_end + 1e-6]
    luo_in = [e for e in luo_res.schedule
              if e.src_d >= d_start - 1e-6 and e.dst_d <= d_end + 1e-6]
    free_xy = [(e.src_t, e.src_d) for e in free_in] + [(free_in[-1].dst_t, free_in[-1].dst_d)]
    luo_xy = [(e.src_t, e.src_d) for e in luo_in] + [(luo_in[-1].dst_t, luo_in[-1].dst_d)]
    free_xs, free_ys = zip(*free_xy)
    luo_xs, luo_ys = zip(*luo_xy)
    # Resample both onto a common time grid for fill_between
    common_t = np.linspace(max(free_xs[0], luo_xs[0]),
                           min(free_xs[-1], luo_xs[-1]), 400)
    free_d = np.interp(common_t, free_xs, free_ys)
    luo_d = np.interp(common_t, luo_xs, luo_ys)
    ax_ovr.fill_between(common_t, free_d, luo_d,
                        color="#ffd166", alpha=0.55, zorder=8,
                        label=f"divergence area = "
                              f"{float(np.trapezoid(np.abs(free_d - luo_d), common_t)):.1f} nm·h")
    ax_ovr.plot(free_xs, free_ys, color="#1a73e8", linewidth=2.0, zorder=10,
                label=f"Free DP ({sum(e.fuel_mt for e in free_in):.3f} mt)")
    ax_ovr.plot(luo_xs, luo_ys, color="#d62728", linewidth=2.0, zorder=10,
                linestyle="--",
                label=f"Luo DP ({sum(e.fuel_mt for e in luo_in):.3f} mt)")
    ax_ovr.legend(loc="upper right", fontsize=7, framealpha=0.92)
    max_dd = float(np.max(np.abs(free_d - luo_d)))
    ax_ovr.set_title(f"Overlay — max |Δd| = {max_dd:.2f} nm",
                     fontsize=10, pad=8)

    # Shared colorbar across the two (t, d) panels (Free + Luo)
    sm = ScalarMappable(cmap=cmap, norm=norm)
    sm.set_array([])
    cbar = fig.colorbar(sm, ax=[ax_free, ax_luo], orientation="horizontal",
                        fraction=0.04, pad=0.10, aspect=40,
                        label="target SOG (kn)")
    cbar.set_ticks([9, 10, 11, 12, 13])

    # Frame-line legend (compact, top-right of Free panel)
    legend_handles = [
        plt.Line2D([], [], color="red", linewidth=1.4,
                   label="segment-boundary H-line"),
        plt.Line2D([], [], color="#e08a25", linestyle=":", linewidth=1.0,
                   label="lon-line H"),
        plt.Line2D([], [], color="#0f7a8b", linestyle=":", linewidth=1.0,
                   label="lat-line H"),
        plt.Line2D([], [], color="#5870a8", linestyle="--", linewidth=0.9,
                   label="V-line (every 6 h)"),
    ]
    ax_free.legend(handles=legend_handles, loc="lower right", fontsize=7,
                   framealpha=0.92)

    plt.tight_layout(rect=(0, 0.05, 1, 1))
    plt.savefig(out_path, dpi=150)
    print(f"\nSaved: {out_path}")


if __name__ == "__main__":
    main()

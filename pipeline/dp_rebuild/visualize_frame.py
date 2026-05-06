"""
Visualize the rebuilt graph frame (V-lines + H-lines from `frame.py`)
on the (t, d) plane, side-by-side with a Mercator chart of the same
rhumb-line segments and 0.5° NWP grid crossings.

Defaults to the first 3 paper waypoints — WP1 → WP2 → WP3 (2 segments).

Differences vs the legacy `visualize_geo_grid.py`:
  * H-line distances and V-line times come from the new `Frame` object
    (`frame.h_line_distances`, `frame.v_line_times`) instead of being
    re-computed inline. Confirms the rebuild's geometry matches what
    the original visualizer drew.
  * Distance and time axes are bounded to the chosen waypoint subset
    so a 3-waypoint subset doesn't display 280 h of empty (t, d) space.

Saves to `pipeline/dp_rebuild/visualize_frame.png`.

Usage:
  python3 visualize_frame.py             # WP1 → WP2 → WP3 (default)
  python3 visualize_frame.py 4           # WP1 → WP2 → WP3 → WP4
  python3 visualize_frame.py 13          # full voyage
"""

from __future__ import annotations

import sys
from pathlib import Path

import cartopy.crs as ccrs
import cartopy.feature as cfeature
import matplotlib.pyplot as plt
import numpy as np

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from frame import from_route as frame_from_route  # noqa: E402
from geo_grid import (  # noqa: E402
    rhumb_bearing_deg,
    rhumb_distance_nm,
    rhumb_grid_crossings,
    _mercator_y,
    _inverse_mercator_lat_deg,
)
from h5_weather import VoyageWeather  # noqa: E402
from load_route import load_yaml_route, synthesize_multi_window  # noqa: E402
from route_waypoints import WAYPOINTS  # noqa: E402


GRID_DEG = 0.5
DEFAULT_N_WAYPOINTS = 3


def main() -> None:
    n_wp = int(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_N_WAYPOINTS
    if n_wp < 2 or n_wp > len(WAYPOINTS):
        raise SystemExit(
            f"n_waypoints must be in [2, {len(WAYPOINTS)}], got {n_wp}"
        )

    waypoints = WAYPOINTS[:n_wp]
    n_segments = n_wp - 1
    out_path = _HERE / f"visualize_frame_wp{n_wp}.png"

    # ---- Build the full-route frame, then filter to the first N waypoints ----
    yaml_path = _HERE.parent.parent / "Dynamic speed optimization" / "weather_forecasts.yaml"
    h5_path = _HERE.parent / "data" / "voyage_weather.h5"
    route = load_yaml_route(yaml_path)
    route = synthesize_multi_window(route, window_h=6.0)
    voyage = VoyageWeather(h5_path)
    full_frame = frame_from_route(route, voyage, WAYPOINTS)

    # ---- Compute cumulative distance for each waypoint along the rhumb path ----
    seg_distances = []
    cumulative = [0.0]
    for i in range(n_segments):
        w1, w2 = waypoints[i], waypoints[i + 1]
        d = rhumb_distance_nm(w1.lat_deg, w1.lon_deg, w2.lat_deg, w2.lon_deg)
        seg_distances.append(d)
        cumulative.append(cumulative[-1] + d)
    L_subset = cumulative[-1]

    # ---- Console summary ----
    print("=" * 88)
    print(f"Frame visualization — first {n_wp} waypoints, "
          f"{n_segments} segments, total {L_subset:.2f} nm")
    print("=" * 88)
    print(f"  {'seg':>3}  {'WP→WP':>7}  {'rhumb_nm':>9}  {'bearing°':>9}  "
          f"{'lon×':>5}  {'lat×':>5}  {'tot':>5}")
    total_lon = total_lat = 0
    for i in range(n_segments):
        w1, w2 = waypoints[i], waypoints[i + 1]
        crossings = rhumb_grid_crossings(
            w1.lat_deg, w1.lon_deg, w2.lat_deg, w2.lon_deg, grid_deg=GRID_DEG,
        )
        n_lat = sum(1 for c in crossings if c.axis == "lat")
        n_lon = sum(1 for c in crossings if c.axis == "lon")
        total_lat += n_lat
        total_lon += n_lon
        b = rhumb_bearing_deg(w1.lat_deg, w1.lon_deg, w2.lat_deg, w2.lon_deg)
        print(f"  {i+1:>3}   {w1.idx:>2}→{w2.idx:<3}  "
              f"{seg_distances[i]:>9.3f}  {b:>9.2f}  "
              f"{n_lon:>5}  {n_lat:>5}  {len(crossings):>5}")

    # H-lines from the new frame, filtered to the subset distance range
    h_in_range = [d for d in full_frame.h_line_distances if d <= L_subset + 1e-6]
    n_seg_boundary = n_segments - 1   # interior segment boundaries
    n_grid_xings = total_lon + total_lat
    print(f"  → {n_grid_xings} grid crossings + {n_seg_boundary} segment-boundary "
          f"+ 1 terminal = {n_grid_xings + n_seg_boundary + 1} expected H-lines")
    print(f"  → frame.h_line_distances ∩ [0, L_subset]: {len(h_in_range)} entries")

    # ETA range for time axis: pick a comfortable upper bound (~72h for 3 wp)
    eta_h = max(72.0, L_subset / 12.0 * 1.05)
    v_in_range = [t for t in full_frame.v_line_times if t <= eta_h + 1e-6]
    print(f"  → frame.v_line_times ∩ [0, {eta_h:.0f}h]: {len(v_in_range)} entries "
          f"({v_in_range[:6]}{'…' if len(v_in_range) > 6 else ''})")
    print("=" * 88)

    # ----------------------------------------------------------------------
    # Figure: Mercator (left) + (t, d) panel (right)
    # ----------------------------------------------------------------------
    fig = plt.figure(figsize=(18, 9))

    # ---- Left panel: Mercator ----
    all_lons = [w.lon_deg for w in waypoints]
    all_lats = [w.lat_deg for w in waypoints]
    lon_pad, lat_pad = 0.8, 0.8
    extent = (min(all_lons) - lon_pad, max(all_lons) + lon_pad,
              min(all_lats) - lat_pad, max(all_lats) + lat_pad)

    ax_map = fig.add_subplot(1, 2, 1, projection=ccrs.Mercator())
    ax_map.set_extent(extent, crs=ccrs.PlateCarree())
    ax_map.add_feature(cfeature.LAND, facecolor="#f1efea", edgecolor="#7a7367")
    ax_map.add_feature(cfeature.OCEAN, facecolor="#cee2ec")
    ax_map.add_feature(cfeature.COASTLINE, linewidth=0.5, color="#5a544a")
    ax_map.add_feature(cfeature.BORDERS, linestyle=":", linewidth=0.4, color="#7a7367")

    # 0.5° grid
    gl = ax_map.gridlines(
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

    # Rhumb-line segments + crossings
    for i in range(n_segments):
        w1, w2 = waypoints[i], waypoints[i + 1]
        my1, my2 = _mercator_y(w1.lat_deg), _mercator_y(w2.lat_deg)
        sample_lons = [w1.lon_deg + f * (w2.lon_deg - w1.lon_deg)
                       for f in np.linspace(0, 1, 100)]
        sample_lats = [_inverse_mercator_lat_deg(my1 + f * (my2 - my1))
                       for f in np.linspace(0, 1, 100)]
        ax_map.plot(sample_lons, sample_lats, color="#c33d4a", linewidth=2.0,
                    transform=ccrs.PlateCarree(), zorder=4)
        for c in rhumb_grid_crossings(
            w1.lat_deg, w1.lon_deg, w2.lat_deg, w2.lon_deg, grid_deg=GRID_DEG,
        ):
            color = "#0f7a8b" if c.axis == "lat" else "#e08a25"
            ax_map.plot(c.lon_deg, c.lat_deg, marker="o", markersize=5,
                        color=color, markeredgecolor="black", markeredgewidth=0.4,
                        transform=ccrs.PlateCarree(), zorder=6)

    # Waypoint stars
    for wp in waypoints:
        ax_map.plot(wp.lon_deg, wp.lat_deg, marker="*", markersize=14,
                    color="#222831", markeredgecolor="white", markeredgewidth=1.0,
                    transform=ccrs.PlateCarree(), zorder=7)
        ax_map.text(wp.lon_deg + 0.15, wp.lat_deg + 0.15,
                    f"WP{wp.idx}\n({wp.lat_deg:.2f},{wp.lon_deg:.2f})",
                    fontsize=8, fontweight="bold",
                    transform=ccrs.PlateCarree(), zorder=8,
                    bbox=dict(boxstyle="round,pad=0.2", fc="white",
                              ec="#222831", alpha=0.85, lw=0.5))

    wp_chain = " → ".join(f"WP{w.idx}" for w in waypoints)
    ax_map.set_title(f"Mercator chart — rhumb-line segments {wp_chain} "
                     "with 0.5° NWP grid", fontsize=11, pad=12)
    ax_map.legend(handles=[
        plt.Line2D([], [], color="#c33d4a", linewidth=2.0, label="rhumb-line segment"),
        plt.Line2D([], [], color="#e08a25", marker="o", linestyle="",
                   markersize=6, markeredgecolor="black", markeredgewidth=0.4,
                   label="lon-line crossing"),
        plt.Line2D([], [], color="#0f7a8b", marker="o", linestyle="",
                   markersize=6, markeredgecolor="black", markeredgewidth=0.4,
                   label="lat-line crossing"),
        plt.Line2D([], [], color="#222831", marker="*", linestyle="",
                   markersize=10, label="waypoint"),
    ], loc="upper left", fontsize=8, framealpha=0.9)

    # ---- Right panel: (t, d) view of frame ----
    ax_td = fig.add_subplot(1, 2, 2)
    ax_td.invert_yaxis()
    ax_td.set_xlabel("time from voyage start  (h)")
    ax_td.set_ylabel("distance from voyage start  (nm) — grows downward")
    ax_td.set_title("Same crossings as H-lines on the DP graph (from new frame)",
                    fontsize=11, pad=12)
    ax_td.set_xlim(-eta_h * 0.05, eta_h * 1.18)
    ax_td.set_ylim(L_subset + L_subset * 0.05, -L_subset * 0.05)

    # V-lines (every 6 h, from frame.v_line_times)
    label_y = -L_subset * 0.04
    for v in v_in_range:
        ax_td.axvline(v, color="#5870a8", linestyle="--", linewidth=0.9, alpha=0.65)
        if int(v) % 12 == 0:
            ax_td.text(v, label_y, f"{int(v)}h", color="#5870a8",
                       fontsize=7, ha="center", va="bottom", fontweight="bold")

    # H-lines from frame.h_line_distances. Distinguish:
    #   - segment-boundary H-lines (heading changes) → red solid
    #   - cell-boundary H-lines (lat/lon crossings) → orange/teal dotted
    # frame doesn't carry the lat/lon-axis tag, so re-derive from per-segment crossings.
    seg_boundary_d = set(round(c, 9) for c in cumulative[1:-1])  # interior boundaries
    cell_d_lat: set = set()
    cell_d_lon: set = set()
    cum = 0.0
    for i in range(n_segments):
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

    for d in h_in_range:
        d_r = round(d, 9)
        if d_r in seg_boundary_d:
            continue  # drawn separately on top
        if abs(d - L_subset) < 1e-6:
            continue  # terminal H-line drawn separately
        if d_r in cell_d_lat:
            ax_td.axhline(d, color="#0f7a8b", linestyle=":",
                          linewidth=0.5, alpha=0.55)
        elif d_r in cell_d_lon:
            ax_td.axhline(d, color="#e08a25", linestyle=":",
                          linewidth=0.5, alpha=0.55)
        else:
            # H-line came from outside our re-derived set (rounding tolerance);
            # paint as a generic dotted line.
            ax_td.axhline(d, color="#888", linestyle=":",
                          linewidth=0.5, alpha=0.4)

    # Source waypoint label (top-left)
    ax_td.text(eta_h * 0.02, 0.0,
               f"WP{waypoints[0].idx}  ({waypoints[0].lat_deg:.2f}°N, "
               f"{waypoints[0].lon_deg:.2f}°E)\nd = 0 nm  (start)",
               fontsize=8, color="#1f4e79", va="center", ha="left",
               fontweight="bold",
               bbox=dict(boxstyle="round,pad=0.25", fc="white",
                         ec="#1f4e79", lw=0.7, alpha=0.92))

    # Segment-boundary H-lines (interior + terminal at L_subset)
    label_x = eta_h * 1.02
    for i in range(1, n_wp):
        d = cumulative[i]
        ax_td.axhline(d, color="red", linestyle="-", linewidth=1.0, alpha=0.85)
        wp = waypoints[i]
        label = (f"WP{wp.idx}  ({wp.lat_deg:.2f}°N, {wp.lon_deg:.2f}°E)\n"
                 f"d = {d:.1f} nm")
        ax_td.text(label_x, d, label,
                   fontsize=8, color="#a52a2a", va="center", ha="left",
                   fontweight="bold",
                   bbox=dict(boxstyle="round,pad=0.25", fc="white",
                             ec="red", lw=0.7, alpha=0.92))

    # Footer
    n_total_h = n_grid_xings + n_seg_boundary + 1
    footer = (f"H-lines: {n_grid_xings} grid crossings "
              f"+ {n_seg_boundary} segment-boundary + 1 terminal "
              f"= {n_total_h} total  ·  V-lines: {len(v_in_range)} every 6 h")
    ax_td.text(0.5, 0.015, footer,
               transform=ax_td.transAxes, ha="center", va="bottom",
               fontsize=9, color="black",
               bbox=dict(boxstyle="round,pad=0.3", fc="white", ec="#666",
                         alpha=0.95, lw=0.7))

    ax_td.legend(handles=[
        plt.Line2D([], [], color="red", linewidth=1.4,
                   label="segment-boundary H-line (heading change)"),
        plt.Line2D([], [], color="#e08a25", linestyle=":", linewidth=1.0,
                   label="lon-line crossing H-line"),
        plt.Line2D([], [], color="#0f7a8b", linestyle=":", linewidth=1.0,
                   label="lat-line crossing H-line"),
        plt.Line2D([], [], color="#5870a8", linestyle="--", linewidth=0.9,
                   label="V-line (every 6 h, time-decision cadence)"),
    ], loc="upper right", fontsize=8, framealpha=0.92,
       bbox_to_anchor=(0.99, 0.94))

    plt.tight_layout()
    plt.savefig(out_path, dpi=150)
    print(f"\nSaved: {out_path}")


if __name__ == "__main__":
    main()

"""
Visualize the first three waypoints (segments 1 and 2) of the voyage on a
Cartopy / Mercator chart, with the 0.5° NWP grid overlaid.

Shows:
  - rhumb-line segments WP1 → WP2 → WP3 (straight lines on Mercator)
  - 0.5° NWP grid lines (lat & lon)
  - one marker per rhumb-vs-grid crossing, coloured by which axis was crossed
  - cumulative-distance label at each crossing
  - each waypoint annotated with its index + (lat, lon)

A second figure shows the same crossings on the (t, d) plane, side-by-side
with the equivalent H-line distances we'd produce in the DP graph.

Saves to `visualize_geo_grid.png`.
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Tuple

import cartopy.crs as ccrs
import cartopy.feature as cfeature
import matplotlib.pyplot as plt
import numpy as np

from geo_grid import (
    Crossing,
    cell_index,
    rhumb_bearing_deg,
    rhumb_distance_nm,
    rhumb_grid_crossings,
)
from route_waypoints import WAYPOINTS

GRID_DEG = 0.5
SEGMENTS_TO_SHOW = list(range(1, 13))   # all 12 segments — full voyage
OUT = Path(__file__).resolve().parent / "visualize_geo_grid.png"


def gather_segment_data() -> List[Tuple[int, "Waypoint", "Waypoint", float, float, List[Crossing]]]:
    """For each segment in SEGMENTS_TO_SHOW, return
        (seg_id, wp_start, wp_end, distance_nm, bearing_deg, crossings)"""
    out = []
    for seg_id in SEGMENTS_TO_SHOW:
        wp1 = WAYPOINTS[seg_id - 1]
        wp2 = WAYPOINTS[seg_id]
        d = rhumb_distance_nm(wp1.lat_deg, wp1.lon_deg, wp2.lat_deg, wp2.lon_deg)
        b = rhumb_bearing_deg(wp1.lat_deg, wp1.lon_deg, wp2.lat_deg, wp2.lon_deg)
        crossings = rhumb_grid_crossings(
            wp1.lat_deg, wp1.lon_deg, wp2.lat_deg, wp2.lon_deg, grid_deg=GRID_DEG,
        )
        out.append((seg_id, wp1, wp2, d, b, crossings))
    return out


def main() -> None:
    seg_data = gather_segment_data()

    # ------------------------------------------------------------------
    # Console summary — one row per segment.
    # ------------------------------------------------------------------
    print("=" * 92)
    print(f"Rhumb-line segments + 0.5° NWP grid crossings  ({len(seg_data)} segments)")
    print("=" * 92)
    print(f"  {'seg':>3} {'WP→WP':>7} {'rhumb_nm':>9} {'paper_nm':>9} "
          f"{'Δd':>7} {'bearing°':>9} {'paper_β°':>9} "
          f"{'lon×':>5} {'lat×':>5} {'total':>6}")
    cumulative = 0.0
    seg_starts_d = [0.0]
    total_lon = total_lat = 0
    for seg_id, w1, w2, d, b, crossings in seg_data:
        n_lat = sum(1 for c in crossings if c.axis == "lat")
        n_lon = sum(1 for c in crossings if c.axis == "lon")
        total_lat += n_lat
        total_lon += n_lon
        print(f"  {seg_id:>3}  {w1.idx:>2}→{w2.idx:<3} "
              f"{d:>9.3f} {w1.distance_nm:>9.2f} {d - w1.distance_nm:>+7.3f} "
              f"{b:>9.2f} {w1.heading_deg:>9.2f} "
              f"{n_lon:>5} {n_lat:>5} {len(crossings):>6}")
        cumulative += d
        seg_starts_d.append(cumulative)
    total = cumulative
    paper_total = sum(WAYPOINTS[s - 1].distance_nm for s in SEGMENTS_TO_SHOW)
    n_h_total = sum(len(c) for _, _, _, _, _, c in seg_data)
    print("  " + "-" * 88)
    print(f"  TOT             {total:>9.3f} {paper_total:>9.2f} "
          f"{total - paper_total:>+7.3f}     —          —      "
          f"{total_lon:>5} {total_lat:>5} {n_h_total:>6}")
    print(f"  + segment-boundary H-lines (interior, =11 for full voyage):     "
          f"{len(SEGMENTS_TO_SHOW) - 1:>6}")
    print(f"  + terminal H-line at d=L:                                         1")
    print(f"  total H-lines = grid crossings + seg boundaries + terminal = "
          f"{n_h_total + (len(SEGMENTS_TO_SHOW) - 1) + 1}")
    print("=" * 92)

    # ------------------------------------------------------------------
    # Figure: Mercator map (left) + (t, d) graph view (right)
    # ------------------------------------------------------------------
    fig = plt.figure(figsize=(18, 9))

    # ---- Left panel: Mercator map ----
    # Compute map extent from waypoints + a buffer.
    all_lons = [WAYPOINTS[s - 1].lon_deg for s in SEGMENTS_TO_SHOW] + \
               [WAYPOINTS[SEGMENTS_TO_SHOW[-1]].lon_deg]
    all_lats = [WAYPOINTS[s - 1].lat_deg for s in SEGMENTS_TO_SHOW] + \
               [WAYPOINTS[SEGMENTS_TO_SHOW[-1]].lat_deg]
    lon_pad = 0.8
    lat_pad = 0.8
    extent = (min(all_lons) - lon_pad, max(all_lons) + lon_pad,
              min(all_lats) - lat_pad, max(all_lats) + lat_pad)

    ax_map = fig.add_subplot(1, 2, 1, projection=ccrs.Mercator())
    ax_map.set_extent(extent, crs=ccrs.PlateCarree())
    ax_map.add_feature(cfeature.LAND, facecolor="#f1efea", edgecolor="#7a7367")
    ax_map.add_feature(cfeature.OCEAN, facecolor="#cee2ec")
    ax_map.add_feature(cfeature.COASTLINE, linewidth=0.5, color="#5a544a")
    ax_map.add_feature(cfeature.BORDERS, linestyle=":", linewidth=0.4, color="#7a7367")

    # Draw the 0.5° grid (gridlines).
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

    # Plot each rhumb segment as a straight line in Mercator coords.
    cum_d = 0.0
    for seg_id, w1, w2, d, b, crossings in seg_data:
        # Sample the rhumb line at many fractions for a smooth display
        n_sample = 100
        from geo_grid import _mercator_y, _inverse_mercator_lat_deg
        my1, my2 = _mercator_y(w1.lat_deg), _mercator_y(w2.lat_deg)
        sample_lons = [w1.lon_deg + f * (w2.lon_deg - w1.lon_deg)
                       for f in np.linspace(0, 1, n_sample)]
        sample_lats = [_inverse_mercator_lat_deg(my1 + f * (my2 - my1))
                       for f in np.linspace(0, 1, n_sample)]
        ax_map.plot(sample_lons, sample_lats, color="#c33d4a", linewidth=2.0,
                    transform=ccrs.PlateCarree(), zorder=4)

        # Crossings: lat-line crossings teal, lon-line crossings orange
        for c in crossings:
            color = "#0f7a8b" if c.axis == "lat" else "#e08a25"
            ax_map.plot(c.lon_deg, c.lat_deg, marker="o", markersize=5,
                        color=color, markeredgecolor="black",
                        markeredgewidth=0.4,
                        transform=ccrs.PlateCarree(), zorder=6)
        cum_d += d

    # Waypoints
    for seg_id in SEGMENTS_TO_SHOW + [SEGMENTS_TO_SHOW[-1] + 1]:
        wp = WAYPOINTS[seg_id - 1] if seg_id <= 13 else None
        if wp is None:
            continue
    for idx in (SEGMENTS_TO_SHOW + [SEGMENTS_TO_SHOW[-1] + 1]):
        wp = WAYPOINTS[idx - 1]
        ax_map.plot(wp.lon_deg, wp.lat_deg, marker="*", markersize=14,
                    color="#222831", markeredgecolor="white",
                    markeredgewidth=1.0,
                    transform=ccrs.PlateCarree(), zorder=7)
        ax_map.text(wp.lon_deg + 0.15, wp.lat_deg + 0.15,
                    f"WP{wp.idx}\n({wp.lat_deg:.2f},{wp.lon_deg:.2f})",
                    fontsize=8, fontweight="bold",
                    transform=ccrs.PlateCarree(), zorder=8,
                    bbox=dict(boxstyle="round,pad=0.2", fc="white",
                              ec="#222831", alpha=0.8, lw=0.5))

    ax_map.set_title("Mercator chart — rhumb-line segments WP1 → WP2 → WP3 "
                     "with 0.5° NWP grid",
                     fontsize=11, pad=12)

    # Legend (manually placed, since cartopy doesn't auto-collect)
    legend_handles = [
        plt.Line2D([], [], color="#c33d4a", linewidth=2.0, label="rhumb-line segment"),
        plt.Line2D([], [], color="#e08a25", marker="o", linestyle="",
                   markersize=6, markeredgecolor="black", markeredgewidth=0.4,
                   label="lon-line crossing"),
        plt.Line2D([], [], color="#0f7a8b", marker="o", linestyle="",
                   markersize=6, markeredgecolor="black", markeredgewidth=0.4,
                   label="lat-line crossing"),
        plt.Line2D([], [], color="#222831", marker="*", linestyle="",
                   markersize=10, label="waypoint"),
    ]
    ax_map.legend(handles=legend_handles, loc="upper left", fontsize=8,
                  framealpha=0.9)

    # ---- Right panel: (t, d) graph view ----
    ax_td = fig.add_subplot(1, 2, 2)
    ax_td.invert_yaxis()
    ax_td.set_xlabel("time from voyage start  (h)")
    ax_td.set_ylabel("distance from voyage start  (nm) — grows downward")
    ax_td.set_title("Same crossings as H-lines on the DP graph", fontsize=11, pad=12)

    eta_h = 280.0   # YAML voyage ETA — full voyage
    ax_td.set_xlim(-5, eta_h + 25)
    ax_td.set_ylim(total + 60, -60)

    # V-lines every 6h for reference (light grey)
    for v in range(6, int(eta_h) + 1, 6):
        ax_td.axvline(v, color="#bbbbbb", linestyle=":", linewidth=0.4, alpha=0.5)

    # Crossing H-lines: dotted, lat=teal, lon=orange. No per-line text labels —
    # at full voyage scale they'd be unreadable. The legend explains them.
    for seg_id, w1, w2, _, _, crossings in seg_data:
        for c in crossings:
            d_voy = seg_starts_d[seg_id - 1] + c.distance_nm
            color = "#0f7a8b" if c.axis == "lat" else "#e08a25"
            ax_td.axhline(d_voy, color=color, linestyle=":",
                          linewidth=0.5, alpha=0.55)

    # Segment-boundary H-lines on top (red, solid, slightly thicker)
    for i, d in enumerate(seg_starts_d[1:], start=1):
        ax_td.axhline(d, color="red", linestyle="-", linewidth=1.0, alpha=0.85)
        if i == 1 or i % 3 == 0:
            ax_td.text(eta_h + 5, d, f"WP{i + 1} d={d:.0f}",
                       fontsize=7, color="red", va="center", ha="left")

    n_seg_interior = len(SEGMENTS_TO_SHOW) - 1  # 11 for the full voyage
    n_total_h = n_h_total + n_seg_interior + 1  # + terminal
    ax_td.text(0.5, 0.015,
               f"H-lines: {n_h_total} grid crossings + {n_seg_interior} "
               f"segment-boundary + 1 terminal  =  {n_total_h} total\n"
               f"(was 146 H-lines under the previous waypoint-midpoint policy)",
               transform=ax_td.transAxes, ha="center", va="bottom",
               fontsize=9, color="black",
               bbox=dict(boxstyle="round,pad=0.3", fc="white", ec="#666",
                         alpha=0.95, lw=0.7))

    legend_handles_td = [
        plt.Line2D([], [], color="red", linewidth=1.4,
                   label="segment-boundary H-line (heading change)"),
        plt.Line2D([], [], color="#e08a25", linestyle=":", linewidth=1.0,
                   label="lon-line crossing H-line"),
        plt.Line2D([], [], color="#0f7a8b", linestyle=":", linewidth=1.0,
                   label="lat-line crossing H-line"),
    ]
    ax_td.legend(handles=legend_handles_td, loc="upper right", fontsize=8,
                 framealpha=0.92)

    plt.tight_layout()
    plt.savefig(OUT, dpi=150)
    print(f"\nSaved: {OUT}")


if __name__ == "__main__":
    main()

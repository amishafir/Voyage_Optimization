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

import sys
from pathlib import Path
from typing import List, Tuple

import cartopy.crs as ccrs
import cartopy.feature as cfeature
import matplotlib.pyplot as plt
import numpy as np

from geo_grid import (
    Crossing,
    rhumb_bearing_deg,
    rhumb_distance_nm,
    rhumb_grid_crossings,
)
from route_waypoints import WAYPOINTS as YAML_WAYPOINTS, Waypoint
from test_routes import TEST_ROUTES

GRID_DEG = 0.5

# Fixture selection: pass a name on argv, else default to the YAML paper route.
#   python3 visualize_geo_grid.py            → YAML paper route, segments 1..3
#   python3 visualize_geo_grid.py iceland_tromso  → Iceland → Tromsø, all segments
FIXTURE = sys.argv[1] if len(sys.argv) > 1 else "yaml_paper"

if FIXTURE == "yaml_paper":
    WAYPOINTS_USED = YAML_WAYPOINTS
    SEGMENTS_TO_SHOW = [1, 2, 3]   # WP1 → WP2 → WP3 → WP4
    OUT_NAME = "visualize_geo_grid.png"
elif FIXTURE in TEST_ROUTES:
    WAYPOINTS_USED = TEST_ROUTES[FIXTURE]
    SEGMENTS_TO_SHOW = list(range(1, len(WAYPOINTS_USED)))
    OUT_NAME = f"visualize_geo_grid_{FIXTURE}.png"
else:
    raise SystemExit(
        f"unknown fixture {FIXTURE!r}. Options: yaml_paper, "
        + ", ".join(TEST_ROUTES.keys())
    )

OUT = Path(__file__).resolve().parent / OUT_NAME


def pick_projection(
    lat_min: float, lat_max: float,
    lon_min: float, lon_max: float, lon_span: float,
) -> Tuple[ccrs.Projection, str]:
    """Auto-select a Cartopy projection from route extent.

    - mostly arctic (min lat > 70°)        → NorthPolarStereo
    - mostly antarctic (max lat < −70°)    → SouthPolarStereo
    - antimeridian-crossing (lon span > 180°) → PlateCarree at mean lon
    - else                                 → Mercator
    """
    if lat_min > 70.0:
        return ccrs.NorthPolarStereo(), "NorthPolarStereo"
    if lat_max < -70.0:
        return ccrs.SouthPolarStereo(), "SouthPolarStereo"
    if lon_span > 180.0:
        central_lon = (lon_min + lon_max) / 2.0 + 180.0
        return ccrs.PlateCarree(central_longitude=central_lon), \
               f"PlateCarree(central_longitude={central_lon:.1f}°)"
    return ccrs.Mercator(), "Mercator"


def gather_segment_data() -> List[Tuple[int, "Waypoint", "Waypoint", float, float, List[Crossing]]]:
    """For each segment in SEGMENTS_TO_SHOW, return
        (seg_id, wp_start, wp_end, distance_nm, bearing_deg, crossings)"""
    out = []
    for seg_id in SEGMENTS_TO_SHOW:
        wp1 = WAYPOINTS_USED[seg_id - 1]
        wp2 = WAYPOINTS_USED[seg_id]
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
        # Paper distance/heading may be None on hypothetical fixtures.
        paper_d_str = f"{w1.distance_nm:>9.2f}" if w1.distance_nm is not None else f"{'—':>9}"
        delta_d_str = (f"{d - w1.distance_nm:>+7.3f}"
                       if w1.distance_nm is not None else f"{'—':>7}")
        paper_b_str = f"{w1.heading_deg:>9.2f}" if w1.heading_deg is not None else f"{'—':>9}"
        print(f"  {seg_id:>3}  {w1.idx:>2}→{w2.idx:<3} "
              f"{d:>9.3f} {paper_d_str} {delta_d_str} "
              f"{b:>9.2f} {paper_b_str} "
              f"{n_lon:>5} {n_lat:>5} {len(crossings):>6}")
        cumulative += d
        seg_starts_d.append(cumulative)
    total = cumulative
    paper_total = sum(
        (WAYPOINTS_USED[s - 1].distance_nm or 0.0) for s in SEGMENTS_TO_SHOW
    )
    has_paper = any(WAYPOINTS_USED[s - 1].distance_nm is not None for s in SEGMENTS_TO_SHOW)
    n_h_total = sum(len(c) for _, _, _, _, _, c in seg_data)
    print("  " + "-" * 88)
    if has_paper:
        print(f"  TOT             {total:>9.3f} {paper_total:>9.2f} "
              f"{total - paper_total:>+7.3f}     —          —      "
              f"{total_lon:>5} {total_lat:>5} {n_h_total:>6}")
    else:
        print(f"  TOT             {total:>9.3f}        —        —     "
              f"—          —      "
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

    # ---- Left panel: auto-selected projection ----
    # Compute map extent from waypoints + a buffer.
    all_lons = [WAYPOINTS_USED[s - 1].lon_deg for s in SEGMENTS_TO_SHOW] + \
               [WAYPOINTS_USED[SEGMENTS_TO_SHOW[-1]].lon_deg]
    all_lats = [WAYPOINTS_USED[s - 1].lat_deg for s in SEGMENTS_TO_SHOW] + \
               [WAYPOINTS_USED[SEGMENTS_TO_SHOW[-1]].lat_deg]
    lon_pad = 0.8
    lat_pad = 0.8

    # Span of unwrapped longitudes (sensitive to antimeridian crossings).
    sorted_lons = sorted(all_lons)
    lon_span = sorted_lons[-1] - sorted_lons[0]
    projection, projection_name = pick_projection(
        min(all_lats), max(all_lats),
        min(all_lons), max(all_lons), lon_span,
    )
    print(f"\nAuto-selected projection: {projection_name}")

    extent = (min(all_lons) - lon_pad, max(all_lons) + lon_pad,
              min(all_lats) - lat_pad, max(all_lats) + lat_pad)

    ax_map = fig.add_subplot(1, 2, 1, projection=projection)
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
        wp = WAYPOINTS_USED[seg_id - 1] if seg_id <= 13 else None
        if wp is None:
            continue
    for idx in (SEGMENTS_TO_SHOW + [SEGMENTS_TO_SHOW[-1] + 1]):
        wp = WAYPOINTS_USED[idx - 1]
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

    wp_first = SEGMENTS_TO_SHOW[0]
    wp_last = SEGMENTS_TO_SHOW[-1] + 1
    wp_chain = " → ".join(f"WP{i}" for i in range(wp_first, wp_last + 1))
    ax_map.set_title(f"{projection_name} chart — rhumb-line segments {wp_chain} "
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

    # ETA scaled to the *shown* portion (avg ~12 kn cruising) so the panel
    # isn't 80% empty when only a few segments are rendered.
    eta_h = max(72.0, total / 12.0 * 1.05)
    ax_td.set_xlim(-eta_h * 0.05, eta_h * 1.18)
    ax_td.set_ylim(total + total * 0.05, -total * 0.05)

    # V-lines every 6h — the time-decision cadence for the DP graph.
    # Visible (not background-grey), labelled at the top so the cadence reads.
    label_y = -total * 0.04   # just above d=0 (top of the inverted axis)
    for v in range(6, int(eta_h) + 1, 6):
        ax_td.axvline(v, color="#5870a8", linestyle="--", linewidth=0.9, alpha=0.65)
        # Label every 12 h to avoid clutter
        if v % 12 == 0:
            ax_td.text(v, label_y, f"{v}h", color="#5870a8",
                       fontsize=7, ha="center", va="bottom", fontweight="bold")
    # Add a "V-lines (every 6h)" entry to the right-panel legend below.

    # Crossing H-lines: dotted, lat=teal, lon=orange. No per-line text labels —
    # at full voyage scale they'd be unreadable. The legend explains them.
    for seg_id, w1, w2, _, _, crossings in seg_data:
        for c in crossings:
            d_voy = seg_starts_d[seg_id - 1] + c.distance_nm
            color = "#0f7a8b" if c.axis == "lat" else "#e08a25"
            ax_td.axhline(d_voy, color=color, linestyle=":",
                          linewidth=0.5, alpha=0.55)

    # Segment-boundary H-lines on top (red, solid, slightly thicker).
    # Each label carries the WP index, its (lat, lon), and the cumulative d so
    # the (t, d) panel is self-explanatory next to the Mercator chart.
    label_x = eta_h * 1.02
    label_every = max(1, len(seg_starts_d[1:]) // 6)  # cap to ~6 labels

    # Source waypoint label at the TOP-LEFT (d=0, just inside the plot area)
    # so the voyage origin is visually anchored where the eye lands first.
    wp_source = WAYPOINTS_USED[wp_first - 1]
    ax_td.text(eta_h * 0.02, 0.0,
               f"WP{wp_first}  ({wp_source.lat_deg:.2f}°N, "
               f"{wp_source.lon_deg:.2f}°E)\nd = 0 nm  (start)",
               fontsize=8, color="#1f4e79", va="center", ha="left",
               fontweight="bold",
               bbox=dict(boxstyle="round,pad=0.25",
                         fc="white", ec="#1f4e79", lw=0.7, alpha=0.92))

    for i, d in enumerate(seg_starts_d[1:], start=1):
        ax_td.axhline(d, color="red", linestyle="-", linewidth=1.0, alpha=0.85)
        if i == 1 or i == len(seg_starts_d) - 1 or i % label_every == 0:
            wp_idx = wp_first + i
            wp = WAYPOINTS_USED[wp_idx - 1]
            label = (f"WP{wp_idx}  ({wp.lat_deg:.2f}°N, {wp.lon_deg:.2f}°E)\n"
                     f"d = {d:.1f} nm")
            ax_td.text(label_x, d, label,
                       fontsize=8, color="#a52a2a", va="center", ha="left",
                       fontweight="bold",
                       bbox=dict(boxstyle="round,pad=0.25",
                                 fc="white", ec="red", lw=0.7, alpha=0.92))

    n_seg_interior = len(SEGMENTS_TO_SHOW) - 1
    n_total_h = n_h_total + n_seg_interior + 1  # + terminal
    is_full_voyage = SEGMENTS_TO_SHOW == list(range(1, 13))
    footer = (f"H-lines: {n_h_total} grid crossings + {n_seg_interior} "
              f"segment-boundary + 1 terminal  =  {n_total_h} total")
    if is_full_voyage:
        footer += "\n(was 146 H-lines under the previous waypoint-midpoint policy)"
    ax_td.text(0.5, 0.015, footer,
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
        plt.Line2D([], [], color="#5870a8", linestyle="--", linewidth=0.9,
                   label="V-line (every 6 h, time-decision cadence)"),
    ]
    # Legend goes top-right (free now that WP1 is on the top-left).
    ax_td.legend(handles=legend_handles_td, loc="upper right", fontsize=8,
                 framealpha=0.92,
                 bbox_to_anchor=(0.99, 0.94))   # nudge slightly inside

    plt.tight_layout()
    plt.savefig(OUT, dpi=150)
    print(f"\nSaved: {OUT}")


if __name__ == "__main__":
    main()

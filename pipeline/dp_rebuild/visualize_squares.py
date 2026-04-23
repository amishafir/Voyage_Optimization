"""
Visualize a small patch of the DP graph so we can eyeball how segments,
time windows, and weather change across adjacent squares.

Picks a 3 (time bands) × 2 (distance bands) grid near the segment 0/1
boundary (d ≈ 213.87 nm). Colors each square by wave height. Uses
*real time-varying weather* by mapping each V-line window index to a
different `sample_hour` in the HDF5 (12 sample hours cycle).

Saves to visualize_squares.png next to this file.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib.patches as patches
import matplotlib.pyplot as plt
import numpy as np

from build_edges import (
    Edge,
    edges_from_source,
    index_nodes,
    lookup_source_state,
    next_coord,
)
from build_nodes import GraphConfig, Node, build_nodes, h_line_distances_from_h5
from h5_weather import VoyageWeather
from load_route import load_yaml_route, synthesize_multi_window


GRID_DEG = 0.5
OUT_PATH = Path(__file__).with_suffix("").with_name("visualize_squares.png")


def main() -> None:
    h5_path = Path(__file__).resolve().parent.parent / "data" / "voyage_weather.h5"
    yaml_path = Path(__file__).resolve().parent.parent.parent / \
        "Dynamic speed optimization" / "weather_forecasts.yaml"

    vw = VoyageWeather(h5_path)
    route = synthesize_multi_window(load_yaml_route(yaml_path), window_h=6.0)

    # Pick three V bands and two H bands around the segment 0/1 boundary.
    # H edges are pulled from the live boundary generators so the picture
    # always matches the current policy (post-2026-04-23 fix uses first-wp
    # of each new cell/segment, putting the seg 0/1 boundary at d=223.74).
    v_edges = [6.0, 12.0, 18.0, 24.0]
    seg_boundaries = vw.segment_boundaries_nm()
    cell_boundaries = vw.weather_cell_boundaries_nm(grid_deg=GRID_DEG)
    seg01 = seg_boundaries[0]  # the 0→1 transition (first interior segment boundary)
    # Nearest cell boundaries below and above the segment boundary.
    below = max((d for d in cell_boundaries if d < seg01 - 1e-6), default=seg01 - 20)
    above = min((d for d in cell_boundaries if d > seg01 + 1e-6), default=seg01 + 20)
    h_edges_true = [below, seg01, above]
    h_edges_disp = [round(below, 2), round(seg01, 2), round(above, 2)]

    fig, ax = plt.subplots(figsize=(13, 8))

    # Collect wave heights so we can scale the color map
    cells_info = []
    waves = []
    for i in range(len(v_edges) - 1):
        t_lo, t_hi = v_edges[i], v_edges[i + 1]
        window_idx = int(t_lo // 6)
        sample_hour = window_idx % len(vw.sample_hours)
        for j in range(len(h_edges_true) - 1):
            d_lo, d_hi = h_edges_true[j], h_edges_true[j + 1]
            d_lo_disp, d_hi_disp = h_edges_disp[j], h_edges_disp[j + 1]
            t_mid = (t_lo + t_hi) / 2
            d_mid = (d_lo + d_hi) / 2
            # Segment via boundary-bisect (H-line-consistent); cell via the
            # nearest waypoint *within that segment* so the label agrees with
            # weather_at's own segment-aware lookup.
            seg = vw.segment_for_distance(d_mid)
            wp = vw.nearest_waypoint_in_segment(d_mid, seg)
            cell = (int(np.floor(wp.lat / GRID_DEG)), int(np.floor(wp.lon / GRID_DEG)))
            wx = vw.weather_at(d_mid, sample_hour=sample_hour)
            cells_info.append(dict(
                t_lo=t_lo, t_hi=t_hi, d_lo=d_lo, d_hi=d_hi,
                t_mid=t_mid, d_mid=d_mid,
                d_lo_disp=d_lo_disp, d_hi_disp=d_hi_disp,
                window_idx=window_idx, sample_hour=sample_hour,
                segment=seg, cell=cell,
                wind=wx["wind_speed_10m_kmh"],
                wind_dir=wx["wind_direction_10m_deg"],
                bn=int(wx["beaufort_number"]),
                wave=wx["wave_height_m"],
                current=wx["ocean_current_velocity_kmh"],
            ))
            waves.append(wx["wave_height_m"])

    vmin, vmax = min(waves), max(waves)
    base_cmap = plt.get_cmap("YlGnBu")
    # Keep only the lighter portion of the colormap so the upper row is
    # readable (not near-black).
    cmap_lo, cmap_hi = 0.10, 0.55

    def shade(wave: float) -> tuple:
        t = (wave - vmin) / (vmax - vmin + 1e-9)
        return base_cmap(cmap_lo + t * (cmap_hi - cmap_lo))

    # Draw squares
    for c in cells_info:
        color = shade(c["wave"])
        rect = patches.Rectangle(
            (c["t_lo"], c["d_lo"]), c["t_hi"] - c["t_lo"], c["d_hi"] - c["d_lo"],
            facecolor=color, edgecolor="black", linewidth=1.0,
        )
        ax.add_patch(rect)
        txt = (
            f"seg {c['segment']}   cell {c['cell']}\n"
            f"win [{c['window_idx']*6},{(c['window_idx']+1)*6})  sh={c['sample_hour']}\n"
            f"BN{c['bn']}  wind {c['wind']:.1f} kmh @ {c['wind_dir']:.0f}°\n"
            f"wave {c['wave']:.2f} m   curr {c['current']:.2f} kmh"
        )
        ax.text(c["t_mid"], c["d_mid"], txt, ha="center", va="center",
                fontsize=8.5, family="monospace")

    # Segment-boundary H line emphasised
    for d, d_disp in zip(h_edges_true, h_edges_disp):
        is_seg_boundary = abs(d - seg01) < 1e-6
        ax.axhline(d, color="red" if is_seg_boundary else "gray",
                   linestyle="-" if is_seg_boundary else "--",
                   linewidth=2.0 if is_seg_boundary else 1.0, alpha=0.7)
        ax.text(v_edges[0] - 0.4, d, f"d = {d_disp:.2f} nm", ha="right", va="center",
                fontsize=9, color="red" if is_seg_boundary else "black")
    for t in v_edges:
        ax.axvline(t, color="gray", linestyle="--", linewidth=1.0, alpha=0.7)
        # va="bottom" anchors the bottom edge of the text at this y-coord;
        # with the axis inverted, the text renders visually above this point.
        ax.text(t, h_edges_true[0] - 1.5, f"t = {t:.0f} h",
                ha="center", va="bottom", fontsize=9)

    # Nodes: every V line has nodes every zeta_nm across distance,
    # every H line has nodes every tau_h across time. Plot dots in-range.
    zeta = 1.0   # nm, matches GraphConfig default
    tau = 0.1    # h,  matches GraphConfig default

    # H-line nodes: for each H line, dots every tau_h along the time axis
    # (τ=0.1 h → 181 nodes per H line across 18 h — deliberately dense).
    for d in h_edges_true:
        ts = np.arange(v_edges[0], v_edges[-1] + 1e-9, tau)
        ax.scatter(ts, [d] * len(ts), s=10, facecolor="white",
                   edgecolor="black", linewidths=0.6, zorder=5)

    # V-line nodes: for each V line, dots every zeta_nm along the distance axis.
    # Restrict to the d-window shown (a V line actually has ~L/ζ ≈ 3400 nodes).
    for t in v_edges:
        ds = np.arange(np.ceil(h_edges_true[0]), np.floor(h_edges_true[-1]) + 1e-9, zeta)
        ax.scatter([t] * len(ds), ds, s=18, facecolor="white",
                   edgecolor="black", linewidths=0.8, zorder=5)

    # --------------------------------------------------------------
    # Sample edges — pick a handful of source nodes inside the view,
    # compute their outgoing edges, and draw them as arrows annotated
    # with SOG / SWS / fuel.
    # --------------------------------------------------------------
    cfg_small = GraphConfig.from_route(route, dt_h=6.0, zeta_nm=zeta, tau_h=tau,
                                        v_min=9.0, v_max=13.0)
    local_h_lines = h_edges_true
    local_v_times = v_edges
    # Minimal node set for edges_from_source: just the ones on local lines.
    local_nodes: List[Node] = []
    for t in local_v_times:
        ds_nodes = np.arange(h_edges_true[0], h_edges_true[-1] + 1e-9, zeta)
        for d in ds_nodes:
            local_nodes.append(Node(time_h=float(t), distance_nm=float(d), line_type="V"))
    for d in local_h_lines:
        ts_nodes = np.arange(local_v_times[0], local_v_times[-1] + 1e-9, tau)
        for t in ts_nodes:
            local_nodes.append(Node(time_h=float(t), distance_nm=float(d), line_type="H"))
    by_v, by_h = index_nodes(local_nodes)
    v_times_local_sorted = sorted(by_v.keys())
    h_dist_local_sorted = sorted(by_h.keys())

    # Three edge-type examples. (V→V isn't realisable in this graph: every
    # 6h edge at v_max=13 kn covers 78 nm, but no H-line gap is > 48 nm.)
    #
    # We pick a specific (source, target-line) combination for each type.
    sample_edges_spec = [
        # V→H: source on V line, destination on next H line
        ("V→H", "V",
         Node(time_h=v_edges[0], distance_nm=218.0, line_type="V"),
         "h"),
        # H→V: source on H line, destination on next V line
        ("H→V", "H",
         Node(time_h=v_edges[1] - 0.5, distance_nm=h_edges_true[1], line_type="H"),
         "v"),
        # H→H: source on H line (intersection), destination on next H line
        ("H→H", "H",
         Node(time_h=v_edges[0], distance_nm=h_edges_true[1], line_type="H"),
         "h"),
    ]

    cmap_edges = plt.get_cmap("plasma")
    norm = plt.Normalize(vmin=cfg_small.v_min, vmax=cfg_small.v_max)

    for label, _src_line, src, target in sample_edges_spec:
        next_v = next_coord(v_times_local_sorted, src.time_h)
        next_h = next_coord(h_dist_local_sorted, src.distance_nm)
        state = lookup_source_state(src, vw, route,
                                     next_v_time=next_v, next_h_distance=next_h,
                                     sample_hour=0)
        es: List[Edge] = edges_from_source(
            src, cfg_small,
            v_times_local_sorted, h_dist_local_sorted,
            by_v, by_h, state,
        )
        # Partition by destination line type
        if target == "v":
            es = [e for e in es if abs(e.dst_t - (next_v if next_v else -1)) < 1e-9]
        else:  # target == "h"
            es = [e for e in es if abs(e.dst_d - (next_h if next_h else -1)) < 1e-9]
        if not es:
            continue
        mid_sog = (cfg_small.v_min + cfg_small.v_max) / 2
        e = min(es, key=lambda ee: abs(ee.sog - mid_sog))

        color = cmap_edges(norm(e.sog))
        ax.annotate(
            "", xy=(e.dst_t, e.dst_d), xytext=(e.src_t, e.src_d),
            arrowprops=dict(arrowstyle="->", color=color, lw=2.2, alpha=0.95,
                            shrinkA=3, shrinkB=3),
            zorder=6,
        )
        sws_txt = f"{e.sws:.2f}" if not np.isnan(e.sws) else "NaN"
        fuel_txt = f"{e.fuel_mt:.3f}" if not np.isnan(e.fuel_mt) else "NaN"
        # Label offset: put V→H label above-right of dst, H→V above-left,
        # H→H right of dst.
        dt_offset, dd_offset, ha = {
            "V→H": (0.25, 0.5, "left"),
            "H→V": (0.25, -0.5, "left"),
            "H→H": (0.25, 0.5, "left"),
        }[label]
        ax.text(e.dst_t + dt_offset, e.dst_d + dd_offset,
                f"{label}  SOG {e.sog:.2f}  SWS {sws_txt}  fuel {fuel_txt} mt",
                fontsize=8.0, color="black", family="monospace",
                ha=ha, va="center",
                bbox=dict(boxstyle="round,pad=0.25", fc="white",
                          ec=color, alpha=0.95, lw=1.2),
                zorder=7)

    # Footer note about the missing V→V
    ax.text(0.99, 0.02,
            "V→V not realised: max H-line gap ≈ 48 nm  <  v_max × Δt_h = 78 nm",
            transform=ax.transAxes,
            ha="right", va="bottom", fontsize=8.5, color="#606060",
            bbox=dict(boxstyle="round,pad=0.3", fc="white", ec="#909090",
                      alpha=0.85, lw=0.6))

    # Annotations
    ax.annotate("segment 0 → 1 boundary", xy=(6.1, seg01), xytext=(6.1, seg01 - 2.5),
                color="red", fontsize=10, fontweight="bold")
    ax.set_xlim(v_edges[0] - 2.5, v_edges[-1] + 0.3)
    # Distance grows downward: d=0 at top, d=L at bottom.
    ax.set_ylim(h_edges_true[-1] + 2, h_edges_true[0] - 4)
    ax.set_xlabel("time from voyage start  (h)")
    ax.set_ylabel("distance from voyage start  (nm) — grows downward")
    ax.set_title("DP graph — 6 adjacent squares around the segment 0/1 boundary\n"
                 "color = wave height (m);  sample_hour maps window index → HDF5 time sample")

    from matplotlib.colors import LinearSegmentedColormap
    # Build a trimmed colormap matching what we render so the colorbar agrees.
    trimmed = LinearSegmentedColormap.from_list(
        "trimmed_ylgnbu",
        [base_cmap(cmap_lo + i / 255 * (cmap_hi - cmap_lo)) for i in range(256)],
    )
    sm = plt.cm.ScalarMappable(cmap=trimmed, norm=plt.Normalize(vmin=vmin, vmax=vmax))
    sm.set_array([])
    fig.colorbar(sm, ax=ax, label="wave height (m)", fraction=0.04, pad=0.01)

    plt.tight_layout()
    plt.savefig(OUT_PATH, dpi=130)
    print(f"saved: {OUT_PATH}")


if __name__ == "__main__":
    main()

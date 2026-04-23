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

    # Three V bands: [6,12), [12,18), [18,24)   — indices 1, 2, 3 (window 0 = [0,6))
    # Two H bands: [198, 213.87), [213.87, 229.74)
    v_edges = [6.0, 12.0, 18.0, 24.0]
    h_edges_true = [198.0, 213.8702481750, 229.7404963499999]  # real values
    h_edges_disp = [198.00, 213.87, 229.74]                    # for labels

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
            wp = vw.nearest_waypoint(d_mid)
            cell = (int(np.floor(wp.lat / GRID_DEG)), int(np.floor(wp.lon / GRID_DEG)))
            wx = vw.weather_at(d_mid, sample_hour=sample_hour)
            cells_info.append(dict(
                t_lo=t_lo, t_hi=t_hi, d_lo=d_lo, d_hi=d_hi,
                t_mid=t_mid, d_mid=d_mid,
                d_lo_disp=d_lo_disp, d_hi_disp=d_hi_disp,
                window_idx=window_idx, sample_hour=sample_hour,
                segment=wp.segment, cell=cell,
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
        is_seg_boundary = abs(d - 213.8702481750) < 1e-6
        ax.axhline(d, color="red" if is_seg_boundary else "gray",
                   linestyle="-" if is_seg_boundary else "--",
                   linewidth=2.0 if is_seg_boundary else 1.0, alpha=0.7)
        ax.text(v_edges[0] - 0.4, d, f"d = {d_disp:.2f} nm", ha="right", va="center",
                fontsize=9, color="red" if is_seg_boundary else "black")
    for t in v_edges:
        ax.axvline(t, color="gray", linestyle="--", linewidth=1.0, alpha=0.7)
        ax.text(t, h_edges_true[0] - 2, f"t = {t:.0f} h", ha="center", va="top", fontsize=9)

    # Annotations
    ax.annotate("segment 0 → 1 boundary", xy=(6.1, 213.87), xytext=(6.1, 217),
                color="red", fontsize=10, fontweight="bold")
    ax.set_xlim(v_edges[0] - 2.5, v_edges[-1] + 0.3)
    ax.set_ylim(h_edges_true[0] - 4, h_edges_true[-1] + 2)
    ax.set_xlabel("time from voyage start  (h)")
    ax.set_ylabel("distance from voyage start  (nm)")
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

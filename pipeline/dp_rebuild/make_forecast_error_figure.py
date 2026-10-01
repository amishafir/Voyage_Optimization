"""Forecast error against lead time, both routes (paper Section 6.4 figure).

Four panels, one per field the speed model consumes, sharing a lead axis.
Shaded bands are the 95% cluster-bootstrap intervals from make_forecast_error.py.

Usage (from pipeline/dp_rebuild/):
    ../../venv/bin/python make_forecast_error_figure.py
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "runs" / "2026_10_01_forecast_error" / "forecast_error.json"
OUT = ROOT / "paper_workspace" / "figures" / "forecast_error"

PANELS = [("wind_speed_10m_kmh", "Wind speed", "MAE (km/h)"),
          ("wind_direction_10m_deg", "Wind direction", "MAE (deg)"),
          ("ocean_current_velocity_kmh", "Current speed", "MAE (km/h)"),
          ("ocean_current_direction_deg", "Current direction", "MAE (deg)")]
STYLE = {"Indian Ocean": ("#1f77b4", "o", "-"), "North Atlantic": ("#d62728", "s", "--")}


def main() -> None:
    d = json.loads(SRC.read_text())
    bands = [b for b in d["Indian Ocean"][PANELS[0][0]]]
    mid = [(int(b.split("-")[0]) + int(b.split("-")[1])) / 2 for b in bands]

    fig, axes = plt.subplots(2, 2, figsize=(7.2, 5.2), sharex=True)
    for ax, (field, title, ylab) in zip(axes.ravel(), PANELS):
        for route, (c, m, ls) in STYLE.items():
            v = [d[route][field][b] for b in bands]
            ax.plot(mid, [x[0] for x in v], ls, color=c, marker=m, ms=4, lw=1.4, label=route)
            ax.fill_between(mid, [x[1] for x in v], [x[2] for x in v], color=c, alpha=0.18, lw=0)
        ax.set_title(title, fontsize=9.5)
        ax.set_ylabel(ylab, fontsize=8.5)
        ax.tick_params(labelsize=8)
        ax.grid(True, lw=0.4, alpha=0.35)
        ax.set_ylim(bottom=0)
    for ax in axes[1]:
        ax.set_xlabel("forecast lead (h)", fontsize=8.5)
    axes[0][0].legend(frameon=False, fontsize=8, loc="upper left")
    fig.tight_layout()
    for ext in ("pdf", "png"):
        fig.savefig(f"{OUT}.{ext}", dpi=200)
    print(f"wrote {OUT}.pdf / .png")


if __name__ == "__main__":
    main()

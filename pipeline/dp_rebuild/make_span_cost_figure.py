"""Span-versus-forecast-cost scatter (paper Fig. in Section 6.3).

One point per voyage, both routes, from the rolling-horizon chain run:

    x = optimisation span   = naive_mt  - oracle_sr    (what a perfect planner could save)
    y = forecast cost       = rh_sr_mt  - oracle_sr    (what imperfect information cost)

The diagonal y = x is the break-even line: above it the forecast cost exceeds
the whole span, so rolling-horizon SR finishes behind the constant-speed Naive
baseline. Those points are exactly the voyages counted in the "cost exceeds
span" column of the span table.

Usage (from pipeline/dp_rebuild/):
    ../../venv/bin/python make_span_cost_figure.py
"""
from __future__ import annotations

import csv
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "runs" / "2026_09_09_rh_chain41_waypoint" / "results.csv"
OUT = ROOT / "paper_workspace" / "figures" / "span_vs_cost"

ROUTE = {
    "route1": ("Indian Ocean", "o", "#1f77b4"),
    "route2": ("North Atlantic", "s", "#d62728"),
}


def load(path: Path):
    per = {}
    with path.open() as fh:
        for r in csv.DictReader(fh):
            span = float(r["naive_mt"]) - float(r["oracle_sr"])
            cost = float(r["rh_sr_mt"]) - float(r["oracle_sr"])
            per.setdefault(r["route"], []).append((span, cost))
    return per


def main() -> None:
    per = load(SRC)
    fig, ax = plt.subplots(figsize=(5.4, 4.2))

    hi = max(v for pts in per.values() for p in pts for v in p) * 1.08
    ax.plot([0, hi], [0, hi], ls="--", lw=1.0, color="0.45", zorder=1)
    ax.annotate(
        "cost = span\n(below: re-planning pays)",
        xy=(hi * 0.70, hi * 0.70), xytext=(hi * 0.72, hi * 0.50),
        fontsize=7.5, color="0.35", ha="left",
        arrowprops=dict(arrowstyle="-", lw=0.7, color="0.6"),
    )

    for key, pts in per.items():
        label, marker, colour = ROUTE[key]
        lost = sum(1 for s, c in pts if c > s)
        ax.scatter(
            [s for s, _ in pts], [c for _, c in pts],
            marker=marker, s=34, facecolors="none", edgecolors=colour,
            linewidths=1.2, label=f"{label} ($n$={len(pts)}, {lost} above)", zorder=3,
        )

    ax.set_xlabel("Optimisation span, Naive $-$ oracle (mt)")
    ax.set_ylabel("Forecast cost, RH $-$ oracle (mt)")
    ax.set_xlim(0, hi)
    ax.set_ylim(0, hi)
    ax.set_aspect("equal")
    ax.grid(True, lw=0.4, alpha=0.35)
    ax.legend(frameon=False, fontsize=8, loc="upper left")
    fig.tight_layout()

    for ext in ("pdf", "png"):
        fig.savefig(f"{OUT}.{ext}", dpi=200)
    print(f"wrote {OUT}.pdf and {OUT}.png")

    for key, pts in per.items():
        lost = [(s, c) for s, c in pts if c > s]
        print(f"  {ROUTE[key][0]:15} n={len(pts):2}  above diagonal: {len(lost):2}")


if __name__ == "__main__":
    main()

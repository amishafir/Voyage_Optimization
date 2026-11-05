"""One explanatory figure: when is the full graph worth its computation, and when does Luo's
time-only graph (piece-by-piece pricing) give the same fuel saving for less?

For each route: Luo's fuel saved over constant SOG as a share of the full graph's saving (y),
against Luo's computation as a share of the full graph's (DP arcs, all re-plans; x, log scale).
The full graph is the point (100%, 100%). A route's break-even (savings.py, 0.05 points) is ringed.
Luo's arcs depend almost only on the epoch, so the top axis names the epoch.

Input savings.csv (savings.py). Output savings_explained.png/.pdf.

    python3 explain_plot.py        (needs matplotlib)
"""
import csv
import statistics as st
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

ROOT = Path(globals().get("__file__", "explain_plot.py")).resolve().parent
EPOCHS = ["6", "3", "2", "1.5", "1", "0.5", "0.25"]
TOL = 0.05
ROUTES = {3: "Route 3 Tacoma–Anchorage", 4: "Route 4 Rotterdam–Algeciras",
          5: "Route 5 Kaohsiung–Yokohama", 6: "Route 6 Durban–Cape Town"}
# Reference palette (dataviz skill), categorical slots 1-4 in order; text and grid tokens.
COLORS = {3: "#2a78d6", 4: "#eb6834", 5: "#1baf7a", 6: "#eda100"}
INK, INK2, MUTED, GRID, SURFACE = "#0b0b0b", "#52514e", "#8a8984", "#e4e3df", "#fcfcfb"


def main():
    rows = list(csv.DictReader(open(ROOT / "savings.csv")))
    by = {(int(r["route"]), r["method"]): r for r in rows}
    plt.rcParams.update({"font.family": "sans-serif", "font.size": 9.5, "axes.edgecolor": GRID,
                         "axes.labelcolor": INK2, "xtick.color": INK2, "ytick.color": INK2,
                         "figure.facecolor": SURFACE, "axes.facecolor": SURFACE})
    fig, ax = plt.subplots(figsize=(10, 6.2))
    box = {"facecolor": SURFACE, "edgecolor": "none", "pad": 1.5, "alpha": 0.9}
    epoch_x = {e: [] for e in EPOCHS}
    evens = []
    for k, name in ROUTES.items():
        full = by[(k, "Full graph")]
        fs, fa = float(full["saving_pct"]), float(full["arcs"])
        pts = [by[(k, f"Luo {e} h, piece by piece")] for e in EPOCHS]
        x = [100 * float(p["arcs"]) / fa for p in pts]
        y = [100 * float(p["saving_pct"]) / fs for p in pts]
        for e, xi in zip(EPOCHS, x):
            epoch_x[e].append(xi)
        c = COLORS[k]
        ax.plot(x + [100], y + [100], color=c, linewidth=2, solid_capstyle="round", zorder=3, label=name)
        ax.scatter(x, y, s=34, color=c, edgecolor=SURFACE, linewidth=2, zorder=4)
        # break-even: coarsest epoch within TOL points of the full graph's saving
        i = next(i for i, p in enumerate(pts) if float(p["saving_pct"]) >= fs - TOL)
        evens.append((x[i], fa / float(pts[i]["arcs"]), EPOCHS[i]))
        ax.scatter([x[i]], [y[i]], s=150, facecolor="none", edgecolor=c, linewidth=2, zorder=5)
        ax.annotate(f"{name.split()[0]} {name.split()[1]}", (x[0], y[0]), xytext=(-8, 0),
                    textcoords="offset points", ha="right", va="center", color=INK, fontsize=9)
    ax.scatter([100], [100], s=90, marker="D", color=INK, edgecolor=SURFACE, linewidth=2, zorder=6)
    ax.annotate("Full graph\n(time + distance)", (100, 100), xytext=(0, -14), textcoords="offset points",
                ha="center", va="top", color=INK, fontsize=9, bbox=box)
    ax.axhline(100, color=INK2, linewidth=1, zorder=2)
    ax.annotate("full graph's saving", (0.0105, 100), xytext=(0, -4), textcoords="offset points",
                ha="left", va="top", color=INK2, fontsize=8.5, bbox=box)

    # The two regimes, split at the break-even span.
    lo, hi = min(e[0] for e in evens), max(e[0] for e in evens)
    ax.axvspan(0.01, lo, color=GRID, alpha=0.45, zorder=0, linewidth=0)
    ax.axvspan(lo, hi, color=GRID, alpha=0.2, zorder=0, linewidth=0)
    ax.text(0.012, 114, "Epochs too coarse:\nLuo saves less, the full\ngraph is worth its\ncomputation",
            color=INK, fontsize=9.5, va="top", ha="left", bbox=box)
    ax.text(2.6, 62, f"Past break-even (1–3 h epochs)\nLuo saves as much as the full graph\nwith "
            f"{min(e[1] for e in evens):,.0f}–{max(e[1] for e in evens):,.0f}x less computation;\n"
            f"finer epochs only add computation", color=INK, fontsize=9.5, va="bottom", ha="left", bbox=box)
    ax.annotate("break-even zone\n(ringed point per route)", (lo, 114), xytext=(4, 0), textcoords="offset points",
                ha="left", va="top", color=INK2, fontsize=8.5)

    ax.set_xscale("log")
    ax.set_xlim(0.01, 300)
    ax.set_ylim(50, 116)
    ax.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:g}%"))
    ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:.0f}%"))
    ax.set_xlabel("Computation, as a share of the full graph's (DP arcs per voyage, all re-plans; log scale)")
    ax.set_ylabel("Fuel saved over constant SOG,\nas a share of the full graph's saving")
    ax.grid(color=GRID, linewidth=1)
    ax.set_axisbelow(True)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    top = ax.secondary_xaxis("top")
    top.set_ticks([st.mean(epoch_x[e]) for e in EPOCHS], labels=[f"{e} h" for e in EPOCHS])
    top.tick_params(colors=INK2)
    top.set_xlabel("Luo decision epoch (piece-by-piece pricing)", color=INK2)
    top.spines["top"].set_visible(False)
    fig.legend(*ax.get_legend_handles_labels(), loc="upper left", ncol=4, frameon=False, fontsize=8.5,
               bbox_to_anchor=(0.005, 0.945))
    fig.suptitle("Below 1–3 h epochs the full graph saves more; from there on, Luo's time-only graph "
                 "matches it far more cheaply", x=0.01, ha="left", fontsize=11.5, color=INK)
    fig.text(0.01, 0.005, "Routes 3–6, 25 voyages (departures every 48 h, 21 Oct – 2 Nov 2026), rolling horizon "
             "re-planned every 6 h with the forecast known 6 h earlier; route means. Not shown: Luo et al. as "
             "published (6 h, start-point pricing) saves -0.7% to -3.1% vs constant SOG, i.e. it burns more.",
             color=INK2, fontsize=7.5, ha="left", va="bottom", wrap=True)
    fig.tight_layout(rect=(0, 0.04, 1, 0.91))
    for ext in ("png", "pdf"):
        fig.savefig(ROOT / f"savings_explained.{ext}", dpi=200)


if __name__ == "__main__":
    main()

"""Fuel efficiency against computation with perfect foresight as 100%, one panel per route.

y: perfect-foresight fuel / realized fuel (the full graph planned in the actual weather;
   per voyage, then the route mean): perfect foresight is the top line (100%), no method can
   exceed it; constant SOG is a parallel line beneath it. Lower = more fuel.
x: computation, DP arcs per voyage summed over all re-plans (log scale; ops/*.csv).
Luo is a curve over its epochs (6 h to 0.25 h), for each pricing; the full graph is one point.

Inputs epochs.csv (plot_epochs.py), ops/*.csv (count_ops.py). Output foresight_tradeoff.png/.pdf.

    python3 foresight_plot.py        (needs matplotlib)
"""
import csv
import statistics as st
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

ROOT = Path(globals().get("__file__", "foresight_plot.py")).resolve().parent
EPOCHS = ["6", "3", "2", "1.5", "1", "0.5", "0.25"]
TOL = 0.05   # break-even: coarsest piece-by-piece epoch within TOL points of the full graph
NAMES = {3: "Route 3 · Tacoma–Anchorage", 4: "Route 4 · Rotterdam–Algeciras",
         5: "Route 5 · Kaohsiung–Yokohama", 6: "Route 6 · Durban–Cape Town"}
BLUE, ORANGE = "#2a78d6", "#eb6834"
INK, INK2, MUTED, GRID, SURFACE = "#0b0b0b", "#52514e", "#8a8984", "#e4e3df", "#fcfcfb"
GOOD_BAND, BAD_BAND = "#eaf2fb", "#f3f2ef"


def main():
    rows = list(csv.DictReader(open(ROOT / "epochs.csv")))
    ops = {}
    for f in (ROOT / "ops").glob("r*_*.csv"):
        route, start = int(f.name[1]), f.stem.split("_", 1)[1]
        for o in csv.DictReader(open(f)):
            ops[(route, start, o["method"])] = int(o["arcs"])

    plt.rcParams.update({"font.family": "sans-serif", "font.size": 9, "axes.edgecolor": GRID,
                         "axes.labelcolor": INK2, "xtick.color": INK2, "ytick.color": INK2,
                         "axes.titlecolor": INK, "figure.facecolor": SURFACE, "axes.facecolor": SURFACE})
    fig, axes = plt.subplots(2, 2, figsize=(10.5, 8))
    box = {"facecolor": SURFACE, "edgecolor": "none", "pad": 1.5, "alpha": 0.85}
    for ax, k in zip(axes.flat, sorted(NAMES)):
        rs = [r for r in rows if int(r["route"]) == k]
        idx = lambda col: st.mean(100 * float(r["perfect_info_mt"]) / float(r[col]) for r in rs)
        arcs = lambda m: st.mean(ops[(k, r["start"], m)] for r in rs)
        const, full = idx("constant_sog_mt"), idx("full_graph_rolling_mt")
        fa = arcs("Full graph")
        series = {}
        for pricing, color, label in (("start point", ORANGE, "Luo, start-point pricing (Luo et al. at 6 h)"),
                                      ("piece by piece", BLUE, "Luo, piece-by-piece pricing")):
            x = [arcs(f"Luo {e} h, {pricing}") for e in EPOCHS]
            y = [idx(f"luo_{e}h_{pricing.replace(' ', '_')}_mt") for e in EPOCHS]
            series[pricing] = (x, y)
            ax.plot(x, y, color=color, linewidth=2, solid_capstyle="round", label=label, zorder=3)
            ax.scatter(x, y, s=34, color=color, edgecolor=SURFACE, linewidth=2, zorder=4)
        ax.scatter([fa], [full], s=70, marker="D", color=INK, edgecolor=SURFACE, linewidth=2, zorder=5,
                   label="Full graph (time + distance)")

        lo_y = min(const, min(series["start point"][1])) - 0.25
        ax.set_xscale("log")
        ax.set_xlim(1.5e5, 2e11)
        ax.set_ylim(lo_y, 100 + 0.09 * (100 - lo_y))
        x0, x1 = ax.get_xlim()
        ax.axhspan(100, const, color=GOOD_BAND, zorder=0, linewidth=0)
        ax.axhspan(const, lo_y, color=BAD_BAND, zorder=0, linewidth=0)
        ax.axhline(100, color=INK, linewidth=1.5, zorder=2)
        ax.axhline(const, color=MUTED, linewidth=1.5, linestyle=(0, (4, 3)), zorder=2)
        ax.annotate("Perfect foresight = 100%", (x0, 100), xytext=(4, 3), textcoords="offset points",
                    ha="left", va="bottom", color=INK, fontsize=8)
        ax.annotate(f"Constant speed {const:.2f}%", (x1, const), xytext=(-4, -3), textcoords="offset points",
                    ha="right", va="top", color=INK2, fontsize=8, bbox=box)
        ax.annotate("worse than constant speed", (x1, lo_y), xytext=(-4, 4), textcoords="offset points",
                    ha="right", va="bottom", color=INK2, fontsize=8, style="italic")

        # labels: epochs on the blue curve, Luo et al. on the orange one
        xb, yb = series["piece by piece"]
        for e, xi, yi in zip(EPOCHS, xb, yb):
            ax.annotate(f"{e} h", (xi, yi), xytext=(0, 7), textcoords="offset points", ha="center",
                        va="bottom", color=INK2, fontsize=7.5)
        xo, yo = series["start point"]
        ax.annotate("Luo et al.", (xo[0], yo[0]), xytext=(8, 0), textcoords="offset points", ha="left",
                    va="center", color=INK2, fontsize=8)
        # forecast gap of the full graph
        ax.annotate("", xy=(fa * 2.2, 100), xytext=(fa * 2.2, full),
                    arrowprops={"arrowstyle": "<->", "color": INK2, "linewidth": 1, "shrinkA": 0, "shrinkB": 0})
        ax.annotate(f"forecast\ngap\n{100 - full:.2f}%", (fa * 2.5, (100 + full) / 2), ha="left", va="center",
                    color=INK2, fontsize=7.5)
        ax.annotate(f"full graph\n{full:.2f}%", (fa, full), xytext=(0, -9), textcoords="offset points",
                    ha="center", va="top", color=INK, fontsize=8, bbox=box)
        # break-even
        i = next(i for i, y in enumerate(yb) if y >= full - TOL)
        ax.axvline(xb[i], color=BLUE, linewidth=1, alpha=0.45, zorder=1)
        ax.set_title(f"{NAMES[k]}\nLuo matches the full graph from {EPOCHS[i]} h epochs, with "
                     f"{fa / xb[i]:,.0f}x fewer arcs", loc="left", fontsize=9.5)

        ax.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(
            lambda v, _: f"{v / 1e9:g} G" if v >= 1e9 else f"{v / 1e6:g} M" if v >= 1e6 else f"{v / 1e3:g} K"))
        ax.yaxis.set_major_locator(matplotlib.ticker.MultipleLocator(1 if 100 - lo_y > 2.5 else 0.5))
        ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:g}%"))
        ax.grid(color=GRID, linewidth=1, alpha=0.8)
        ax.set_axisbelow(True)
        for s in ("top", "right"):
            ax.spines[s].set_visible(False)
    for ax in axes[1]:
        ax.set_xlabel("Computation: DP arcs per voyage, all re-plans (log scale)")
    for ax in axes[:, 0]:
        ax.set_ylabel("Efficiency vs perfect foresight\n(perfect-foresight fuel / fuel burned)")
    handles, labels = axes[0, 0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", ncol=3, frameon=False, bbox_to_anchor=(0.5, 0.995), fontsize=8.5)
    fig.text(0.5, 0.952, "Blue band = what optimization can win over constant speed. Rolling horizon re-planned every 6 h "
             "with 6 h-old forecasts; route means, 6-7 voyages per route", ha="center", color=INK2, fontsize=8)
    fig.tight_layout(rect=(0, 0, 1, 0.94))
    for ext in ("png", "pdf"):
        fig.savefig(ROOT / f"foresight_tradeoff.{ext}", dpi=200)


if __name__ == "__main__":
    main()

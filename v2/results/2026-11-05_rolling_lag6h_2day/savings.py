"""Every method measured against constant SOG: fuel saved over constant SOG, share of the attainable
saving captured, and computation (DP arcs), per route. Draws savings_tradeoff.png/.pdf and finds the
break-even epoch: the coarsest Luo epoch (piece-by-piece pricing) whose saving is within TOL
percentage points of the full graph's.

- saving [%]   = 100 * (constant SOG fuel - method fuel) / constant SOG fuel, per voyage, then the
                 route mean. Perfect information gives the attainable saving (the ceiling).
- captured [%] = route-mean saving / route-mean perfect-information saving (ratio of means; per-voyage
                 ratios blow up on voyages where constant SOG is already near perfect information).
- arcs         = DP arcs summed over all re-plans, route mean (ops/*.csv from count_ops.py).

Inputs epochs.csv (plot_epochs.py) and ops/*.csv. Writes savings.csv and the chart.

    python3 savings.py [--tol 0.05]       (the chart needs matplotlib)
"""
import argparse
import csv
import statistics as st
from pathlib import Path

ROOT = Path(globals().get("__file__", "savings.py")).resolve().parent
EPOCHS = ["6", "3", "2", "1.5", "1", "0.5", "0.25"]
NAMES = {3: "Route 3 · Tacoma–Anchorage", 4: "Route 4 · Rotterdam–Algeciras",
         5: "Route 5 · Kaohsiung–Yokohama", 6: "Route 6 · Durban–Cape Town"}


def load():
    rows = list(csv.DictReader(open(ROOT / "epochs.csv")))
    ops = {}
    for f in (ROOT / "ops").glob("r*_*.csv"):
        route, start = int(f.name[1]), f.stem.split("_", 1)[1]
        for o in csv.DictReader(open(f)):
            ops[(route, start, o["method"])] = int(o["arcs"])
    return rows, ops


def methods():
    yield "Full graph", "full_graph_rolling_mt"
    for pricing in ("piece by piece", "start point"):
        for e in EPOCHS:
            yield f"Luo {e} h, {pricing}", f"luo_{e}h_{pricing.replace(' ', '_')}_mt"


def summarize(tol):
    rows, ops = load()
    out = []
    for k in sorted({int(r["route"]) for r in rows}):
        rs = [r for r in rows if int(r["route"]) == k]
        save = lambda r, col: 100 * (1 - float(r[col]) / float(r["constant_sog_mt"]))
        ceiling = st.mean(save(r, "perfect_info_mt") for r in rs)
        out.append({"route": k, "method": "Perfect information", "saving_pct": ceiling, "captured_pct": 100.0,
                    "beats_const": f"{sum(save(r, 'perfect_info_mt') > 0 for r in rs)}/{len(rs)}", "arcs": None})
        for m, col in methods():
            s = [save(r, col) for r in rs]
            out.append({"route": k, "method": m, "saving_pct": st.mean(s),
                        "captured_pct": 100 * st.mean(s) / ceiling,
                        "beats_const": f"{sum(x > 0 for x in s)}/{len(rs)}",
                        "arcs": st.mean(ops[(k, r["start"], m)] for r in rs)})
    with open(ROOT / "savings.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(out[0]))
        w.writeheader()
        w.writerows(out)
    # Break-even: coarsest piece-by-piece epoch within tol points of the full graph's saving.
    even = {}
    for k in sorted({o["route"] for o in out}):
        by = {o["method"]: o for o in out if o["route"] == k}
        full = by["Full graph"]
        for e in EPOCHS:
            o = by[f"Luo {e} h, piece by piece"]
            if o["saving_pct"] >= full["saving_pct"] - tol:
                even[k] = (e, o, full)
                break
    return out, even


def print_tables(out, even, tol):
    for k in sorted({o["route"] for o in out}):
        print(f"\n### {NAMES[k]}\n")
        print("| Method | Saving vs constant SOG | Share of attainable saving | Beats constant SOG | Arcs |")
        print("|---|---|---|---|---|")
        for o in (o for o in out if o["route"] == k):
            arcs = "-" if o["arcs"] is None else f"{o['arcs'] / 1e6:,.1f} M"
            name = f"**{o['method']}**" if o["method"] in ("Full graph", "Perfect information") else o["method"]
            print(f"| {name} | {o['saving_pct']:+.2f}% | {o['captured_pct']:.0f}% | {o['beats_const']} | {arcs} |")
    print(f"\nBreak-even (coarsest piece-by-piece Luo epoch within {tol} points of the full graph's saving):")
    for k, (e, o, full) in even.items():
        print(f"  Route {k}: {e} h, saving {o['saving_pct']:.2f}% vs full graph {full['saving_pct']:.2f}%, "
              f"arcs {o['arcs'] / 1e6:,.1f} M vs {full['arcs'] / 1e6:,.0f} M ({full['arcs'] / o['arcs']:,.0f}x fewer)")


def chart(out, even, tol):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    BLUE, ORANGE = "#2a78d6", "#eb6834"
    INK, INK2, MUTED, GRID, SURFACE = "#0b0b0b", "#52514e", "#8a8984", "#e4e3df", "#fcfcfb"
    plt.rcParams.update({"font.family": "sans-serif", "font.size": 9, "axes.edgecolor": GRID,
                         "axes.labelcolor": INK2, "xtick.color": INK2, "ytick.color": INK2,
                         "axes.titlecolor": INK, "figure.facecolor": SURFACE, "axes.facecolor": SURFACE})
    fig, axes = plt.subplots(2, 2, figsize=(10, 7.4), sharex=True)
    box = {"facecolor": SURFACE, "edgecolor": "none", "pad": 1.5, "alpha": 0.85}
    for ax, k in zip(axes.flat, sorted(even)):
        by = {o["method"]: o for o in out if o["route"] == k}
        ceiling = by["Perfect information"]["saving_pct"]
        for pricing, color, label in (("start point", ORANGE, "Luo, start-point pricing"),
                                      ("piece by piece", BLUE, "Luo, piece-by-piece pricing")):
            pts = [by[f"Luo {e} h, {pricing}"] for e in EPOCHS]
            x, y = [p["arcs"] for p in pts], [p["saving_pct"] for p in pts]
            ax.plot(x, y, color=color, linewidth=2, solid_capstyle="round", label=label, zorder=3)
            ax.scatter(x, y, s=36, color=color, edgecolor=SURFACE, linewidth=2, zorder=4)
            if pricing == "piece by piece":
                for e, xi, yi in zip(EPOCHS, x, y):
                    ax.annotate(f"{e} h", (xi, yi), xytext=(0, 8), textcoords="offset points",
                                ha="center", color=INK2, fontsize=7.5)
            else:
                ax.annotate("Luo et al. (6 h)", (x[0], y[0]), xytext=(8, 0), textcoords="offset points",
                            va="center", color=INK2, fontsize=8)
        full = by["Full graph"]
        ax.scatter([full["arcs"]], [full["saving_pct"]], s=64, marker="D", color=INK, edgecolor=SURFACE,
                   linewidth=2, zorder=5, label="Full graph (time + distance)")
        ax.annotate(f"full graph\n{full['saving_pct']:.2f}%", (full["arcs"], full["saving_pct"]), xytext=(0, -10),
                    textcoords="offset points", ha="center", va="top", color=INK, fontsize=8, bbox=box)
        ax.axhline(ceiling, color=MUTED, linewidth=1.5, linestyle=(0, (4, 3)), zorder=2,
                   label="Perfect information (attainable saving)")
        ax.annotate(f"perfect information {ceiling:.2f}%", (2.5e5, ceiling), xytext=(0, 4), textcoords="offset points",
                    va="bottom", ha="left", color=INK2, fontsize=8, bbox=box)
        ax.axhline(0, color=INK2, linewidth=1, zorder=2)
        ax.annotate("constant SOG", (2.5e5, 0), xytext=(0, 4), textcoords="offset points", va="bottom",
                    ha="left", color=INK2, fontsize=8, bbox=box)
        ax.axvline(even[k][1]["arcs"], color=BLUE, linewidth=1, alpha=0.5, zorder=1)
        ax.set_xscale("log")
        ax.set_xlim(2e5, 4e10)
        ax.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(
            lambda v, _: f"{v / 1e9:g} G" if v >= 1e9 else f"{v / 1e6:g} M" if v >= 1e6 else f"{v / 1e3:g} K"))
        ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:+.1f}%" if abs(v) > 1e-9 else "0%"))
        e, o, _ = even[k]
        ax.set_title(f"{NAMES[k]}\nbreak-even at {e} h epochs: same saving with {full['arcs'] / o['arcs']:,.0f}x fewer arcs",
                     loc="left", fontsize=9.5)
        lo, hi = ax.get_ylim()
        ax.set_ylim(lo, ceiling + 0.12 * (ceiling - lo))
        ax.grid(color=GRID, linewidth=1)
        ax.set_axisbelow(True)
        for s in ("top", "right"):
            ax.spines[s].set_visible(False)
    for ax in axes[1]:
        ax.set_xlabel("Computation: DP arcs per voyage, all re-plans (log scale)")
    for ax in axes[:, 0]:
        ax.set_ylabel("Fuel saved vs constant SOG")
    handles, labels = axes[0, 0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", ncol=2, frameon=False, bbox_to_anchor=(0.5, 0.995))
    fig.text(0.5, 0.905, f"Route means, rolling horizon with a 6 h information lag. Break-even = coarsest Luo epoch "
             f"(piece by piece) within {tol} points of the full graph's saving (blue line)", ha="center", color=INK2, fontsize=8.5)
    fig.tight_layout(rect=(0, 0, 1, 0.895))
    for ext in ("png", "pdf"):
        fig.savefig(ROOT / f"savings_tradeoff.{ext}", dpi=200)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--tol", type=float, default=0.05)
    a = ap.parse_args()
    out, even = summarize(a.tol)
    print_tables(out, even, a.tol)
    try:
        chart(out, even, a.tol)
    except ImportError:
        print("matplotlib not available: chart skipped")

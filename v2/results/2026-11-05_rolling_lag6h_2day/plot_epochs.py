"""Convergence chart: Luo's epoch length from 6 h down to 0.25 h against the full graph.

Rolling horizon with a 6 h information lag, the 25 voyages of this folder. For every route (its
own panel, its own averages) and every epoch length, the mean realized fuel above the full graph
with perfect information, for Luo with start-point pricing (Luo et al.) and piece-by-piece pricing;
reference lines for the full graph (rolling horizon) and constant SOG. The band is the min-max over
the route's voyages.

Inputs: start_*/r<R>_full_luo6h.txt (6 h), start_*/r<R>_luo30min.txt (0.5 h) and
epochs/start_*/r<R>_luo<steps>.txt (3, 2, 1.5, 1, 0.25 h). Outputs: epochs.csv (fuel in mt and
solve times in s per voyage), epoch_convergence.png/.pdf (fuel against epoch) and
epoch_tradeoff.png/.pdf (fuel against DP arcs, from ops/*.csv written by count_ops.py).

    python3 plot_epochs.py        (needs matplotlib)
"""
import csv
import re
import statistics as st
from pathlib import Path

ROOT = Path(__file__).parent
ROUTE_NAMES = {3: "Route 3 · Tacoma–Anchorage", 4: "Route 4 · Rotterdam–Algeciras",
               5: "Route 5 · Kaohsiung–Yokohama", 6: "Route 6 · Durban–Cape Town"}
EPOCHS = [6, 3, 2, 1.5, 1, 0.5, 0.25]
MT = r":\s+([0-9.]+) mt"


def blocks(text):
    out, cur = {}, None
    for line in text.splitlines():
        if line and not line.startswith(" "):
            cur = line.strip()
            out[cur] = []
        elif cur is not None:
            out[cur].append(line.strip())
    return out


def rolling(b, header):
    for line in b[header]:
        if line.startswith("rolling horizon"):
            return float(re.search(MT, line).group(1))
    raise ValueError(header)


def solve_s(b, header):
    """Total solve time of the rolling horizon's re-plans [s]."""
    for line in b[header]:
        if line.startswith("rolling horizon"):
            return float(re.search(r"solves ([0-9.]+) s", line).group(1))
    raise ValueError(header)


def collect():
    rows = []
    for d in sorted(ROOT.glob("start_*")):
        for f in sorted(d.glob("r*_full_luo6h.txt")):
            route = int(f.name[1])
            files = [f, d / f"r{route}_luo30min.txt"] + sorted((ROOT / "epochs" / d.name).glob(f"r{route}_luo*.txt"))
            b = {}
            for x in files:
                b.update(blocks(x.read_text()))
            pi = next(float(re.search(MT, l).group(1)) for l in b["Full graph"] if l.startswith("perfect"))
            const = float(re.search(r"^Constant SOG [0-9.]+ kn: ([0-9.]+) mt", f.read_text(), re.M).group(1))
            row = {"route": route, "start": d.name[6:], "perfect_info_mt": pi,
                   "full_graph_rolling_mt": rolling(b, "Full graph"), "constant_sog_mt": const,
                   "full_graph_rolling_s": solve_s(b, "Full graph")}
            for e in EPOCHS:
                tag = f"{e:g}"
                for pricing in ("start point", "piece by piece"):
                    key = f"luo_{tag}h_{pricing.replace(' ', '_')}"
                    row[key + "_mt"] = rolling(b, f"Luo {tag} h, {pricing}")
                    row[key + "_s"] = solve_s(b, f"Luo {tag} h, {pricing}")
            rows.append(row)
    with open(ROOT / "epochs.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    return rows


def main():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    rows = collect()
    pct = lambda r, k: 100 * (r[k] / r["perfect_info_mt"] - 1)
    # Reference palette (dataviz skill): categorical slots 1-2, text and grid tokens.
    BLUE, ORANGE = "#2a78d6", "#eb6834"
    INK, INK2, MUTED, GRID, SURFACE = "#0b0b0b", "#52514e", "#8a8984", "#e4e3df", "#fcfcfb"
    plt.rcParams.update({"font.family": "sans-serif", "font.size": 9, "axes.edgecolor": GRID,
                         "axes.labelcolor": INK2, "xtick.color": INK2, "ytick.color": INK2,
                         "axes.titlecolor": INK, "figure.facecolor": SURFACE, "axes.facecolor": SURFACE})
    routes = sorted({r["route"] for r in rows})
    fig, axes = plt.subplots(2, 2, figsize=(10, 7.2), sharex=True, sharey=True)
    xs = list(range(len(EPOCHS)))
    for ax, k in zip(axes.flat, routes):
        rs = [r for r in rows if r["route"] == k]
        for pricing, color, label in (("start_point", ORANGE, "Luo, start-point pricing"),
                                      ("piece_by_piece", BLUE, "Luo, piece-by-piece pricing")):
            series = [[pct(r, f"luo_{e:g}h_{pricing}_mt") for r in rs] for e in EPOCHS]
            means = [st.mean(s) for s in series]
            ax.fill_between(xs, [min(s) for s in series], [max(s) for s in series], color=color,
                            alpha=0.10, linewidth=0)
            ax.plot(xs, means, color=color, linewidth=2, solid_capstyle="round", label=label, zorder=3)
            ax.scatter(xs, means, s=36, color=color, edgecolor=SURFACE, linewidth=2, zorder=4)
        full = st.mean(pct(r, "full_graph_rolling_mt") for r in rs)
        const = st.mean(pct(r, "constant_sog_mt") for r in rs)
        ax.axhline(full, color=INK, linewidth=1.5, zorder=2, label="Full graph (time + distance)")
        ax.axhline(const, color=MUTED, linewidth=1.5, linestyle=(0, (4, 3)), zorder=2, label="Constant SOG")
        ax.axhline(0, color=GRID, linewidth=1, zorder=1)
        box = {"facecolor": SURFACE, "edgecolor": "none", "pad": 1.5, "alpha": 0.85}
        ax.annotate(f"full graph {full:+.2f}%", (2.5, full), xytext=(0, -4), textcoords="offset points",
                    va="top", ha="center", color=INK, fontsize=8, bbox=box, zorder=6)
        ax.annotate(f"constant SOG {const:+.2f}%", (len(EPOCHS) - 1, const), xytext=(0, 4),
                    textcoords="offset points", va="bottom", ha="right", color=INK2, fontsize=8, bbox=box, zorder=6)
        sp0 = st.mean(pct(r, "luo_6h_start_point_mt") for r in rs)
        ax.annotate("Luo et al.", (0, sp0), xytext=(8, 4), textcoords="offset points", color=INK2, fontsize=8)
        ax.set_title(f"{ROUTE_NAMES[k]}  ({len(rs)} voyages)", loc="left", fontsize=10)
        ax.grid(axis="y", color=GRID, linewidth=1)
        ax.set_axisbelow(True)
        for s in ("top", "right"):
            ax.spines[s].set_visible(False)
        ax.set_xticks(xs, [f"{e:g} h" for e in EPOCHS])
        ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:+.0f}%" if v else "0%"))
    for ax in axes[1]:
        ax.set_xlabel("Luo decision epoch (constant SOG within each epoch)")
    for ax in axes[:, 0]:
        ax.set_ylabel("Realized fuel above perfect information")
    handles, labels = axes[0, 0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", ncol=4, frameon=False, bbox_to_anchor=(0.5, 0.985))
    fig.text(0.5, 0.925, "Rolling horizon, re-planning every 6 h with the forecast known 6 h earlier; route means, "
             "band = min–max over voyages (departures every 48 h, 21 Oct – 2 Nov 2026)",
             ha="center", color=INK2, fontsize=8.5)
    fig.tight_layout(rect=(0, 0, 1, 0.91))
    for ext in ("png", "pdf"):
        fig.savefig(ROOT / f"epoch_convergence.{ext}", dpi=200)

    # Trade-off: fuel above perfect information against the computation, the DP arcs relaxed, summed
    # over all re-plans (ops/r<R>_<start>.csv from count_ops.py; machine-independent). Arcs, not SWS
    # evaluations: Luo caches the fuel rate per (subsegment, step, advance) within an epoch, so its
    # SWS evaluations hardly grow with finer epochs while its graph does.
    ops = {}
    for f in (ROOT / "ops").glob("r*_*.csv"):
        route, start = int(f.name[1]), f.stem.split("_", 1)[1]
        for o in csv.DictReader(open(f)):
            ops[(route, start, o["method"])] = int(o["arcs"])
    if len({(r["route"], r["start"]) for r in rows} - {key[:2] for key in ops}):
        print("ops/ incomplete: trade-off chart skipped")
        return

    def evals(r, method):
        return ops[(r["route"], r["start"], method)]

    fig, axes = plt.subplots(2, 2, figsize=(10, 7.2), sharey=True, sharex=True)
    for ax, k in zip(axes.flat, routes):
        rs = [r for r in rows if r["route"] == k]
        for pricing, color, label in (("start_point", ORANGE, "Luo, start-point pricing"),
                                      ("piece_by_piece", BLUE, "Luo, piece-by-piece pricing")):
            t = [st.mean(evals(r, f"Luo {e:g} h, {pricing.replace('_', ' ')}") for r in rs) for e in EPOCHS]
            f = [st.mean(pct(r, f"luo_{e:g}h_{pricing}_mt") for r in rs) for e in EPOCHS]
            ax.plot(t, f, color=color, linewidth=2, solid_capstyle="round", label=label, zorder=3)
            ax.scatter(t, f, s=36, color=color, edgecolor=SURFACE, linewidth=2, zorder=4)
            if pricing == "piece_by_piece":
                for e, x, y in zip(EPOCHS, t, f):
                    ax.annotate(f"{e:g} h", (x, y), xytext=(0, -12), textcoords="offset points",
                                ha="center", color=INK2, fontsize=7.5)
            else:
                ax.annotate("Luo et al. (6 h)", (t[0], f[0]), xytext=(6, 2), textcoords="offset points",
                            color=INK2, fontsize=8)
        tf = st.mean(evals(r, "Full graph") for r in rs)
        ff = st.mean(pct(r, "full_graph_rolling_mt") for r in rs)
        ax.scatter([tf], [ff], s=64, marker="D", color=INK, edgecolor=SURFACE, linewidth=2, zorder=5,
                   label="Full graph (time + distance)")
        ax.annotate(f"full graph\n{tf / 1e9:.1f} G arcs", (tf, ff), xytext=(0, 10),
                    textcoords="offset points", ha="center", va="bottom", color=INK, fontsize=8)
        const = st.mean(pct(r, "constant_sog_mt") for r in rs)
        ax.axhline(const, color=MUTED, linewidth=1.5, linestyle=(0, (4, 3)), zorder=2, label="Constant SOG (no solve)")
        ax.axhline(0, color=GRID, linewidth=1, zorder=1)
        ax.set_xscale("log")
        ax.set_xlim(2e5, 4e10)
        ax.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(
            lambda v, _: f"{v / 1e9:g} G" if v >= 1e9 else f"{v / 1e6:g} M" if v >= 1e6 else f"{v / 1e3:g} K"))
        ax.set_title(f"{ROUTE_NAMES[k]}  ({len(rs)} voyages)", loc="left", fontsize=10)
        ax.grid(color=GRID, linewidth=1)
        ax.set_axisbelow(True)
        for s in ("top", "right"):
            ax.spines[s].set_visible(False)
        ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:+.0f}%" if v else "0%"))
    for ax in axes[1]:
        ax.set_xlabel("DP arcs per voyage, all re-plans (log scale)")
    for ax in axes[:, 0]:
        ax.set_ylabel("Realized fuel above perfect information")
    handles, labels = axes[0, 0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", ncol=4, frameon=False, bbox_to_anchor=(0.5, 0.985))
    fig.text(0.5, 0.925, "Route means. Luo from 6 h (left) to 0.25 h epochs; both pricings use the same graph. "
             "Arcs counted by the C++ core (machine-independent)",
             ha="center", color=INK2, fontsize=8.5)
    fig.tight_layout(rect=(0, 0, 1, 0.91))
    for ext in ("png", "pdf"):
        fig.savefig(ROOT / f"epoch_tradeoff.{ext}", dpi=200)


if __name__ == "__main__":
    main()

"""Summarize the 2-day-spaced rolling-horizon runs (6 h information lag) on Routes 3-6.

Reads start_*/r<route>_full_luo6h.txt and r<route>_luo30min.txt, writes voyages.csv (one row per
voyage, realized fuel in mt) and prints per-method statistics of the realized fuel above the full
graph with perfect information, as in ../2026-10-31_rolling_lag6h/README.md.

    python3 summarize.py [RESULTS_DIR]
"""
import csv
import re
import statistics as st
import sys
from pathlib import Path

ROOT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).parent

# (row label, file suffix, section header, line prefix)
METHODS = [
    ("Full graph, departure forecast 6 h before, no re-planning", "full_luo6h", "Full graph", "forecast 6 h before departure"),
    ("Full graph, rolling horizon (ours)", "full_luo6h", "Full graph", "rolling horizon"),
    ("Luo 0.5 h, piece by piece, rolling", "luo30min", "Luo 0.5 h, piece by piece", "rolling horizon"),
    ("Luo 6 h, piece by piece, rolling", "full_luo6h", "Luo 6 h, piece by piece", "rolling horizon"),
    ("Luo 0.5 h, start point, rolling", "luo30min", "Luo 0.5 h, start point", "rolling horizon"),
    ("Luo 6 h, start point (Luo et al.), rolling", "full_luo6h", "Luo 6 h, start point", "rolling horizon"),
    ("Constant SOG", "full_luo6h", None, "Constant SOG"),
]
MT = r"([0-9.]+) mt"


def sections(text):
    """{section header: [lines]} for the method blocks after 'Rolling'."""
    out, cur = {}, None
    for line in text.splitlines():
        if line and not line.startswith(" "):
            cur = line.strip()
            out[cur] = []
        elif cur is not None:
            out[cur].append(line.strip())
    return out


def value(text, header, prefix):
    if header is None:
        m = re.search(r"^Constant SOG [0-9.]+ kn: " + MT, text, re.M)
        return float(m.group(1))
    for line in sections(text)[header]:
        if line.startswith(prefix):
            return float(re.search(r":\s+" + MT, line).group(1))
    raise ValueError(f"{header} / {prefix} not found")


def main():
    rows = []
    for d in sorted(ROOT.glob("start_*")):
        for f in sorted(d.glob("r*_full_luo6h.txt")):
            route = int(f.name[1])
            texts = {"full_luo6h": f.read_text(), "luo30min": (d / f"r{route}_luo30min.txt").read_text()}
            row = {"route": route, "start": d.name[6:],
                   "perfect_info_mt": value(texts["full_luo6h"], "Full graph", "perfect information")}
            for label, suffix, header, prefix in METHODS:
                row[label] = value(texts[suffix], header, prefix)
            rows.append(row)
    with open(ROOT / "voyages.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)

    def pct(r, label):
        return 100 * (r[label] / r["perfect_info_mt"] - 1)

    # Every route is summarized on its own (routes differ in length, fuel and weather; no pooling).
    ours = "Full graph, rolling horizon (ours)"
    routes = sorted({r["route"] for r in rows})
    for k in routes:
        rs = [r for r in rows if r["route"] == k]
        pis = [r["perfect_info_mt"] for r in rs]
        print(f"\n### Route {k}: {len(rs)} voyages ({', '.join(r['start'][:10] for r in rs)}); "
              f"perfect information {min(pis):.1f}-{max(pis):.1f} mt\n")
        head = ["Method", "mean", "median", "sd", "min", "max", "vs ours (mean)", "ours lower on",
                "beats const. SOG"]
        print("| " + " | ".join(head) + " |")
        print("|" + "---|" * len(head))
        for label, *_ in METHODS:
            p = [pct(r, label) for r in rs]
            d = [100 * (r[label] / r[ours] - 1) for r in rs]
            beats = sum(r[label] < r["Constant SOG"] for r in rs)
            cells = [f"{st.mean(p):+.2f}%", f"{st.median(p):+.2f}%", f"{st.stdev(p):.2f}",
                     f"{min(p):+.2f}%", f"{max(p):+.2f}%",
                     "-" if label == ours else f"{st.mean(d):+.2f}%",
                     "-" if label == ours else f"{sum(x > 0 for x in d)}/{len(rs)}",
                     "-" if label == "Constant SOG" else f"{beats}/{len(rs)}"]
            name = f"**{label}**" if label == ours else label
            print(f"| {name} | " + " | ".join(cells) + " |")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Generate the §7.1 perfect-foresight LaTeX tables in the format the paper
actually uses, with 95% percentile bootstrap CIs.

`make_results_tables.py` emits mean ± s.d. and has drifted out of sync with
tab:modec, which carries bracket CIs. This script reproduces the paper's
format. Its bootstrap was validated against the published route-2 figures
(SR 196.75 [192.1, 201.8] and SR-Luo -2.60 [-2.89, -2.31]) and agrees to the
digit, so the CIs here are comparable with the ones already in the paper.

Reads the C++ PF driver's output:
    <run_dir>/<partition>/results.csv        SR + Luo
    <run_dir>/naive_<partition>/results.csv  Naive (--naive_only pass)
joined on (route, sh_base).

Usage::
    python3 make_pf_tables.py --run_dir ../../runs/2026_09_08_pf_chain41 \
        --partition waypoint [--out /tmp/pf_tables.tex]
"""
from __future__ import annotations

import argparse
import csv
import random
import statistics as st
import sys
from pathlib import Path

ROUTE_ROWS = (("route1", "Indian Ocean", 280), ("route2", "North Atlantic", 168))
B = 20000          # bootstrap resamples
SEED = 12345       # fixed so the table is reproducible


def _read(path: Path) -> dict:
    if not path.exists():
        sys.exit(f"missing: {path}")
    out = {}
    for r in csv.DictReader(open(path)):
        out[(r["route"], int(r["sh_base"]))] = r
    return out


def _pct(a: float, b: float) -> float:
    """Gap of a relative to b, in percent. Negative = a burns less."""
    return 100.0 * (a - b) / b if b else float("nan")


def _boot_ci(vecs: list, stat, seed: int = SEED) -> tuple:
    """Percentile bootstrap over voyages. `vecs` are resampled together, so
    every method sees the same resampled voyage set -- this is the paired
    resampling the paper's CIs use."""
    rnd = random.Random(seed)
    n = len(vecs[0])
    vals = []
    for _ in range(B):
        idx = [rnd.randrange(n) for _ in range(n)]
        vals.append(stat(*[[v[i] for i in idx] for v in vecs]))
    vals.sort()
    return vals[int(0.025 * B)], vals[int(0.975 * B)]


def collect(run_dir: Path, partition: str) -> dict:
    main = _read(run_dir / partition / "results.csv")
    naive = _read(run_dir / f"naive_{partition}" / "results.csv")
    per = {}
    for rk, _label, _eta in ROUTE_ROWS:
        keys = sorted([k for k in main if k[0] == rk], key=lambda k: k[1])
        rows = []
        for k in keys:
            if k not in naive:
                sys.exit(f"no Naive row for {k}; run --naive_only for {partition}")
            rows.append({
                "sh": k[1],
                "sr": float(main[k]["sr_fuel_mt"]),
                "luo": float(main[k]["luo_fuel_mt"]),
                "naive": float(naive[k]["naive_fuel_mt"]),
            })
        per[rk] = rows
    return per


def aggregate_table(per: dict, n_total: int) -> str:
    out = [
        r"\begin{table}[ht]", r"\centering", r"\tiny",
        rf"\caption{{Perfect-foresight aggregates ({n_total} voyages). Naive is the fixed mean-SOG "
        r"constant speed under",
        r"the same actual weather. Spread is a 95\% paired bootstrap CI (a paired $t$-interval "
        r"cross-check",
        r"agreed closely throughout, not shown); negative gap = the first method burns less fuel.}",
        r"\label{tab:modec}",
        r"\begin{tabular}{lrrrrrrr}", r"\toprule",
        (r"Route & $n$ & SR (mt) & Luo (mt) & Naive (mt) & SR$-$Luo (\%) & "
         r"SR$-$Naive (\%) & Luo$-$Naive (\%) \\"),
        r"\midrule",
    ]
    for rk, label, _eta in ROUTE_ROWS:
        rows = per[rk]
        sr = [r["sr"] for r in rows]
        lu = [r["luo"] for r in rows]
        nv = [r["naive"] for r in rows]
        vecs = [sr, lu, nv]          # index 0 = SR, 1 = Luo, 2 = Naive
        cells = [label, str(len(rows))]
        for i in (0, 1, 2):
            lo, hi = _boot_ci(vecs, lambda *v, _i=i: st.mean(v[_i]))
            cells.append(f"{st.mean(vecs[i]):.2f} [{lo:.1f}, {hi:.1f}]")
        for i, j in ((0, 1), (0, 2), (1, 2)):
            m = _pct(st.mean(vecs[i]), st.mean(vecs[j]))
            lo, hi = _boot_ci(vecs,
                              lambda *v, _i=i, _j=j: _pct(st.mean(v[_i]), st.mean(v[_j])))
            cells.append(f"${m:.2f}$ [${lo:.2f},{hi:.2f}$]")
        out.append(" & ".join(cells) + r" \\")
    out += [r"\bottomrule", r"\end{tabular}", r"\end{table}"]
    return "\n".join(out)


def per_voyage_table(per: dict, rk: str, label: str, eta: int, tag: str) -> str:
    rows = per[rk]
    route_phrase = (f"Indian Ocean route (Malacca, ETA {eta} h)" if rk == "route1"
                    else f"North Atlantic route (ETA {eta} h)")
    out = [
        r"\begin{table}[ht]", r"\centering",
        rf"\caption{{Perfect-foresight per-voyage fuel, {route_phrase}. "
        r"$\mathrm{sh}_0$ = departure",
        r"sample hour. Negative gap = SR burns less fuel than Luo.}",
        rf"\label{{tab:modec-{tag}}}",
        r"\begin{tabular}{", r"  S[table-format=2.0]", r"  S[table-format=4.0]",
        r"  S[table-format=3.2]", r"  S[table-format=3.2]", r"  S[table-format=3.2]",
        r"  S[table-format=-1.2]", r"}", r"\toprule",
        (r"{Voyage} & {$\mathrm{sh}_0$} & {SR (mt)} & {Luo (mt)} & {Naive (mt)} & "
         r"{SR$-$Luo (\%)} \\"),
        r"\midrule",
    ]
    for i, r in enumerate(rows, 1):
        out.append(f"{i:<2} & {r['sh']:<4} & {r['sr']:.2f} & {r['luo']:.2f} & "
                   f"{r['naive']:.2f} & {_pct(r['sr'], r['luo']):.2f} \\\\")
    out += [r"\bottomrule", r"\end{tabular}", r"\end{table}"]
    return "\n".join(out)


def prose_stats(per: dict) -> str:
    L = ["", "%" + "=" * 70, "% PROSE STATS -- every derived number used in the §7.1 text",
         "%" + "=" * 70]
    n_tot = sum(len(v) for v in per.values())
    wins = sum(1 for v in per.values() for r in v if r["sr"] < r["luo"])
    L.append(f"% voyages: {n_tot} total; SR < Luo in {wins}/{n_tot}")
    for rk, label, _eta in ROUTE_ROWS:
        rows = per[rk]
        adv = [r["luo"] - r["sr"] for r in rows]
        sr = [r["sr"] for r in rows]
        L.append(f"% {label}: n={len(rows)}  SR-advantage range "
                 f"{min(adv):.2f}-{max(adv):.2f} mt, mean {st.mean(adv):.2f} mt")
        L.append(f"%   gap vs Luo {_pct(st.mean(sr), st.mean([r['luo'] for r in rows])):.2f}%  "
                 f"vs Naive {_pct(st.mean(sr), st.mean([r['naive'] for r in rows])):.2f}%  "
                 f"Luo vs Naive "
                 f"{_pct(st.mean([r['luo'] for r in rows]), st.mean([r['naive'] for r in rows])):.2f}%")
        L.append(f"%   fuel spread: best {min(sr):.2f} worst {max(sr):.2f} mt "
                 f"-> {100*(max(sr)-min(sr))/min(sr):.1f}% above best")
    return "\n".join(L)


def main() -> int:
    ap = argparse.ArgumentParser(prog="make_pf_tables")
    ap.add_argument("--run_dir", required=True)
    ap.add_argument("--partition", choices=["geo", "waypoint"], required=True)
    ap.add_argument("--out")
    args = ap.parse_args()

    per = collect(Path(args.run_dir).resolve(), args.partition)
    n_total = sum(len(v) for v in per.values())
    blocks = [
        f"% partition = {args.partition}; {n_total} voyages; "
        f"bootstrap B={B}, seed={SEED}",
        aggregate_table(per, n_total),
        "",
        per_voyage_table(per, "route1", "Indian Ocean", 280, "r1"),
        "",
        per_voyage_table(per, "route2", "North Atlantic", 168, "r2"),
        prose_stats(per),
    ]
    text = "\n".join(blocks)
    if args.out:
        Path(args.out).write_text(text + "\n")
        print(f"wrote {args.out}")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())

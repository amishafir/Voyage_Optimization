"""
Generate the §6 (Results) LaTeX tables + prose statistics from the fresh
oracle and rolling-horizon sweep CSVs.

Reads:
    <oracle_dir>/results.csv   (run_chain_sweep output)
    <rh_dir>/results.csv       (run_rh_sweep output)

If --rh_dir is a paper-baseline reuse (RH-Luo/Naive from the current paper
tables), pass --paper_rh to merge those columns; otherwise RH-Luo/Naive are
taken from the RH CSV.

Emits to stdout (and --out if given):
    tab:modec, tab:modec-r1, tab:modec-r2      (perfect foresight)
    tab:rh, tab:rh-r1, tab:rh-r2               (rolling horizon)
    A "PROSE STATS" block with every derived number used in §6 text.

Usage::
    python3 make_results_tables.py \
        --oracle_dir runs/2026_07_16_nf_oracle_full \
        --rh_dir     runs/2026_07_16_rh_sweep \
        [--out ../paper_workspace/generated_tables.tex]
"""
from __future__ import annotations

import argparse
import csv
import math
import sys
from pathlib import Path
from typing import Dict, List

ROUTE_LABEL = {"route1": "Malacca", "route2": "Atlantic"}
ROUTE_ETA = {"route1": 280, "route2": 168}


def _read_csv(path: Path) -> List[dict]:
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def _f(x) -> float:
    try:
        return float(x)
    except (TypeError, ValueError):
        return float("nan")


def _mean_sd(xs: List[float]) -> tuple:
    xs = [x for x in xs if x == x]
    n = len(xs)
    if n == 0:
        return float("nan"), float("nan")
    m = sum(xs) / n
    if n < 2:
        return m, 0.0
    var = sum((x - m) ** 2 for x in xs) / (n - 1)
    return m, math.sqrt(var)


# ----------------------------------------------------------------------
# Oracle tables (§6.1)
# ----------------------------------------------------------------------

def oracle_per_voyage(rows: List[dict], route: str) -> str:
    rr = [r for r in rows if r["route"] == route]
    rr.sort(key=lambda r: int(r["sh_base"]))
    label, eta = ROUTE_LABEL[route], ROUTE_ETA[route]
    tag = "r1" if route == "route1" else "r2"
    out = [
        r"\begin{table}[ht]", r"\centering",
        (r"\caption{Perfect-foresight per-voyage fuel, "
         f"{'Route 1' if route == 'route1' else 'Route 2'} "
         f"({label}, ETA {eta} h). $\\mathrm{{sh}}_0$ = departure sample "
         r"hour. Negative gap = SR burns less fuel.}"),
        f"\\label{{tab:modec-{tag}}}",
        r"\begin{tabular}{rrrrrr}", r"\toprule",
        r"Voyage & $\mathrm{sh}_0$ & SR (mt) & Luo (mt) & Gap (mt) & Gap (\%) \\",
        r"\midrule",
    ]
    for i, r in enumerate(rr):
        sr, luo = _f(r["sr_fuel_mt"]), _f(r["luo_fuel_mt"])
        gap = sr - luo
        gpct = gap / luo * 100.0 if luo else float("nan")
        out.append(f"{i} & {int(r['sh_base'])} & {sr:.2f} & {luo:.2f} & "
                   f"${gap:+.2f}$ & ${gpct:+.2f}$ \\\\")
    out += [r"\bottomrule", r"\end{tabular}", r"\end{table}"]
    return "\n".join(out)


def oracle_aggregate(rows: List[dict]) -> str:
    out = [
        r"\begin{table}[ht]", r"\centering",
        r"\caption{Perfect-foresight aggregates. Negative gap = SR burns less fuel.}",
        r"\label{tab:modec}",
        r"\begin{tabular}{lrrrrr}", r"\toprule",
        (r"Route & $n$ & SR mean $\pm$ s.d.\ (mt) & Luo mean $\pm$ s.d.\ (mt) & "
         r"Mean gap (mt) & Mean gap (\%) \\"),
        r"\midrule",
    ]
    for route in ("route1", "route2"):
        rr = [r for r in rows if r["route"] == route]
        srs = [_f(r["sr_fuel_mt"]) for r in rr]
        luos = [_f(r["luo_fuel_mt"]) for r in rr]
        gaps = [s - l for s, l in zip(srs, luos)]
        sm, ss = _mean_sd(srs)
        lm, ls = _mean_sd(luos)
        gm, _ = _mean_sd(gaps)
        gpct = gm / lm * 100.0 if lm else float("nan")
        rlabel = ("1 (Malacca)" if route == "route1" else "2 (Atlantic)")
        out.append(f"{rlabel} & {len(rr)} & ${sm:.2f} \\pm {ss:.2f}$ & "
                   f"${lm:.2f} \\pm {ls:.2f}$ & ${gm:.2f}$ & ${gpct:.1f}$ \\\\")
    out += [r"\bottomrule", r"\end{tabular}", r"\end{table}"]
    return "\n".join(out)


# ----------------------------------------------------------------------
# RH tables (§6.2)
# ----------------------------------------------------------------------

def rh_per_voyage(rows: List[dict], route: str) -> str:
    rr = [r for r in rows if r["route"] == route]
    rr.sort(key=lambda r: int(r["sh_base"]))
    label, eta = ROUTE_LABEL[route], ROUTE_ETA[route]
    tag = "r1" if route == "route1" else "r2"
    out = [
        r"\begin{table}[ht]", r"\centering",
        (r"\caption{Rolling-horizon per-voyage realised fuel, "
         f"{'Route 1' if route == 'route1' else 'Route 2'} "
         f"({label}, ETA {eta} h). $\\mathrm{{sh}}_0$ = "
         r"departure sample hour. Negative \% = saving vs the Naive "
         r"set-and-forget baseline.}"),
        f"\\label{{tab:rh-{tag}}}",
        r"\begin{tabular}{rrrrrr}", r"\toprule",
        (r"$\mathrm{sh}_0$ & Naive (mt) & RH-SR (mt) & RH-Luo (mt) & "
         r"RH-SR vs Naive (\%) & RH-Luo vs Naive (\%) \\"),
        r"\midrule",
    ]
    for r in rr:
        nv, sr, luo = _f(r["naive_mt"]), _f(r["rh_sr_mt"]), _f(r["rh_luo_mt"])
        spct, lpct = _f(r["rh_sr_vs_naive_pct"]), _f(r["rh_luo_vs_naive_pct"])
        luo_s = f"{luo:.2f}" if luo == luo else "---"
        lpct_s = f"${lpct:+.2f}$" if lpct == lpct else "---"
        out.append(f"{int(r['sh_base'])} & {nv:.2f} & {sr:.2f} & {luo_s} & "
                   f"${spct:+.2f}$ & {lpct_s} \\\\")
    out += [r"\bottomrule", r"\end{tabular}", r"\end{table}"]
    return "\n".join(out)


def rh_aggregate(rows: List[dict]) -> str:
    out = [
        r"\begin{table}[ht]", r"\centering",
        (r"\caption{Rolling-horizon realised fuel relative to the Naive "
         r"set-and-forget baseline.}"),
        r"\label{tab:rh}",
        r"\begin{tabular}{lrrrr}", r"\toprule",
        (r"Route & $n$ & RH-SR vs Naive (mean \%) & RH-Luo vs Naive (mean \%) & "
         r"RH-SR saves on \\"),
        r"\midrule",
    ]
    for route in ("route2", "route1"):  # paper orders Atlantic first here
        rr = [r for r in rows if r["route"] == route]
        spct = [_f(r["rh_sr_vs_naive_pct"]) for r in rr]
        lpct = [_f(r["rh_luo_vs_naive_pct"]) for r in rr]
        sm, _ = _mean_sd(spct)
        lm, _ = _mean_sd(lpct)
        saves = sum(1 for x in spct if x == x and x < 0)
        lm_s = f"${lm:.1f}$" if lm == lm else "---"
        rlabel = ("2 (Atlantic)" if route == "route2" else "1 (Malacca)")
        out.append(f"{rlabel} & {len(rr)} & ${sm:.1f}$ & {lm_s} & "
                   f"{saves}/{len(rr)} \\\\")
    out += [r"\bottomrule", r"\end{tabular}", r"\end{table}"]
    return "\n".join(out)


# ----------------------------------------------------------------------
# Prose stats
# ----------------------------------------------------------------------

def prose_stats(oracle: List[dict], rh: List[dict]) -> str:
    lines = ["=" * 64, "PROSE STATS (§6.1 oracle)", "=" * 64]
    all_sr_lt_luo = 0
    total = 0
    for route in ("route1", "route2"):
        rr = [r for r in oracle if r["route"] == route]
        gaps = [_f(r["sr_fuel_mt"]) - _f(r["luo_fuel_mt"]) for r in rr]
        srs = [_f(r["sr_fuel_mt"]) for r in rr]
        n_sr_lt = sum(1 for g in gaps if g < 0)
        all_sr_lt_luo += n_sr_lt
        total += len(rr)
        sm, ss = _mean_sd(srs)
        lm, ls = _mean_sd([_f(r["luo_fuel_mt"]) for r in rr])
        gm, _ = _mean_sd(gaps)
        adv = sorted(-g for g in gaps)  # positive saving magnitudes
        lines += [
            f"\n{route} ({ROUTE_LABEL[route]}), n={len(rr)}:",
            f"  SR mean±sd  : {sm:.2f} ± {ss:.2f}",
            f"  Luo mean±sd : {lm:.2f} ± {ls:.2f}",
            f"  mean gap    : {gm:.2f} mt ({gm/lm*100:.1f}%)",
            f"  SR<Luo on   : {n_sr_lt}/{len(rr)}",
            f"  advantage range: {adv[0]:.2f} .. {adv[-1]:.2f} mt",
            f"  SR fuel spread : min {min(srs):.2f}  max {max(srs):.2f}  "
            f"({(max(srs)-min(srs))/min(srs)*100:.1f}%)",
        ]
    lines.append(f"\nSR<Luo overall: {all_sr_lt_luo}/{total}")

    lines += ["", "=" * 64, "PROSE STATS (§6.2 rolling horizon)", "=" * 64]
    all_sr_saves = 0
    total_rh = 0
    for route in ("route1", "route2"):
        rr = [r for r in rh if r["route"] == route]
        if not rr:
            continue
        spct = [_f(r["rh_sr_vs_naive_pct"]) for r in rr]
        lpct = [_f(r["rh_luo_vs_naive_pct"]) for r in rr]
        sm, _ = _mean_sd(spct)
        lm, _ = _mean_sd(lpct)
        saves = sum(1 for x in spct if x == x and x < 0)
        all_sr_saves += saves
        total_rh += len(rr)
        valid_s = [x for x in spct if x == x]
        lines += [
            f"\n{route} ({ROUTE_LABEL[route]}), n={len(rr)}:",
            f"  RH-SR vs Naive mean : {sm:+.2f}%   (best {min(valid_s):+.2f}%)",
            f"  RH-Luo vs Naive mean: {lm:+.2f}%" if lm == lm else
            "  RH-Luo vs Naive mean: --- (reused from paper)",
            f"  RH-SR saves on      : {saves}/{len(rr)}",
        ]
    lines.append(f"\nRH-SR saves overall: {all_sr_saves}/{total_rh}")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(prog="make_results_tables")
    ap.add_argument("--oracle_dir", required=True)
    ap.add_argument("--rh_dir", default=None,
                    help="RH sweep dir. If omitted, only oracle tables emit.")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    root = Path(__file__).resolve().parent.parent.parent

    def _resolve(p: str) -> Path:
        pp = Path(p)
        return pp if pp.is_absolute() else (root / pp)

    oracle = _read_csv(_resolve(args.oracle_dir) / "results.csv")
    rh = _read_csv(_resolve(args.rh_dir) / "results.csv") if args.rh_dir else []

    blocks = [
        "%% ===== §6.1 perfect foresight =====",
        oracle_aggregate(oracle),
        oracle_per_voyage(oracle, "route1"),
        oracle_per_voyage(oracle, "route2"),
    ]
    if rh:
        blocks += [
            "\n%% ===== §6.2 rolling horizon =====",
            rh_aggregate(rh),
            rh_per_voyage(rh, "route1"),
            rh_per_voyage(rh, "route2"),
        ]
    tex = "\n\n".join(blocks)

    print(tex)
    print("\n\n" + prose_stats(oracle, rh))

    if args.out:
        outp = _resolve(args.out)
        outp.write_text(tex + "\n")
        print(f"\n[wrote LaTeX tables to {outp}]", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())

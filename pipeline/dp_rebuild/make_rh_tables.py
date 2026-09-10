#!/usr/bin/env python3
"""
Generate the §7.2 rolling-horizon LaTeX tables and the §8.2 re-plan diagnostic.

Reads the per-voyage `summary.json` files that `run_rh_chain.py` writes, rather
than its `results.csv`: when two route processes share one --out_dir they each
write results.csv at exit and clobber one another, while the per-voyage
summaries are namespaced by route and always intact.

    <run_dir>/<route>/voyage_NN/summary.json        fuel, gates, oracle
    <run_dir>/<route>/voyage_NN/rh_{sr,luo}_replans.csv   divergence per re-plan

Emits tab:rh, tab:rh-r1, tab:rh-r2 in the format the paper uses, plus a PROSE
STATS block covering every derived number in §7.2 and the §8.2 diagnostic.

Usage::
    python3 make_rh_tables.py --run_dir ../../runs/2026_09_09_rh_chain41_waypoint \
        [--out /tmp/rh_tables.tex]
"""
from __future__ import annotations

import argparse
import csv
import json
import statistics as st
import sys
from pathlib import Path

# Paper order: North Atlantic first in the aggregate table.
ROUTES = (("route2", "North Atlantic", 168, "r2"), ("route1", "Indian Ocean", 280, "r1"))


def load(run_dir: Path) -> dict:
    per = {}
    for rk, _label, _eta, _tag in ROUTES:
        rows = []
        for sd in sorted((run_dir / rk).glob("voyage_*")):
            f = sd / "summary.json"
            if not f.exists():
                continue
            s = json.loads(f.read_text())
            res, g = s["results"], s["gates"]
            rows.append({
                "sh": s["sh_base"],
                "naive": s["naive_mt"],
                "sr": res["sr"]["realised_mt"],
                "luo": res["luo"]["realised_mt"],
                "sr_pct": res["sr"]["vs_naive_pct"],
                "luo_pct": res["luo"]["vs_naive_pct"],
                "sr_vs_oracle": res["sr"]["vs_oracle_mt"],
                "luo_vs_oracle": res["luo"]["vs_oracle_mt"],
                "oracle_sr": s.get("oracle_ref", {}).get("sr", float("nan")),
                "n_replans": s.get("n_replans", 0),
                "gates_sr": all(g["sr"].values()),
                "gates_luo": all(g["luo"].values()),
                "gate_detail_luo": g["luo"],
                "dir": sd,
            })
        rows.sort(key=lambda r: r["sh"])
        per[rk] = rows
    return per


def _revisions(path: Path) -> tuple:
    """(n_revised, n_replans_with_a_previous_plan) from a replans CSV.

    k=0 has no previous plan, so its blank divergence is not a decision.
    """
    if not path.exists():
        return (0, 0)
    rev = tot = 0
    for r in csv.DictReader(open(path)):
        d = (r.get("divergence_kn") or "").strip()
        if not d:
            continue
        tot += 1
        if abs(float(d)) > 1e-9:
            rev += 1
    return (rev, tot)


def aggregate_table(per: dict) -> str:
    out = [
        r"\begin{table}[ht]", r"\centering",
        r"\caption{Rolling-horizon realised fuel relative to the Naive set-and-forget baseline.}",
        r"\label{tab:rh}",
        r"\begin{tabular}{lrrrr}", r"\toprule",
        (r"Route & $n$ & RH-SR vs Naive (mean \%) & RH-Luo vs Naive (mean \%) & "
         r"RH-SR saves on \\"),
        r"\midrule",
    ]
    for rk, label, _eta, _tag in ROUTES:
        rows = per[rk]
        if not rows:
            continue
        sm = st.mean([r["sr_pct"] for r in rows])
        lm = st.mean([r["luo_pct"] for r in rows])
        wins = sum(1 for r in rows if r["sr_pct"] < 0)
        out.append(f"{label} & {len(rows)} & ${sm:.1f}$ & ${lm:.1f}$ & "
                   f"{wins}/{len(rows)} \\\\")
    out += [r"\bottomrule", r"\end{tabular}", r"\end{table}"]
    return "\n".join(out)


def per_voyage_table(per: dict, rk: str, label: str, eta: int, tag: str) -> str:
    rows = per[rk]
    phrase = (f"Indian Ocean route (Malacca, ETA {eta} h)" if rk == "route1"
              else f"North Atlantic route (ETA {eta} h)")
    out = [
        r"\begin{table}[ht]", r"\centering",
        rf"\caption{{Rolling-horizon per-voyage realised fuel, {phrase}. "
        r"$\mathrm{sh}_0$ =",
        r"departure sample hour. Negative \% = saving vs the Naive set-and-forget baseline.}",
        rf"\label{{tab:rh-{tag}}}",
        r"\begin{tabular}{rrrrrr}", r"\toprule",
        (r"$\mathrm{sh}_0$ & Naive (mt) & RH-SR (mt) & RH-Luo (mt) & "
         r"RH-SR vs Naive (\%) & RH-Luo vs Naive (\%) \\"),
        r"\midrule",
    ]
    for r in rows:
        out.append(f"{r['sh']:<4} & {r['naive']:.2f} & {r['sr']:.2f} & {r['luo']:.2f} & "
                   f"${r['sr_pct']:+.2f}$ & ${r['luo_pct']:+.2f}$ \\\\")
    out += [r"\bottomrule", r"\end{tabular}", r"\end{table}"]
    return "\n".join(out)


def prose_stats(per: dict) -> str:
    L = ["", "%" + "=" * 70,
         "% PROSE STATS -- §7.2 text and the §8.2 re-plan diagnostic",
         "%" + "=" * 70]
    allr = [r for rk, _l, _e, _t in ROUTES for r in per[rk]]
    n = len(allr)
    sr_wins = sum(1 for r in allr if r["sr_pct"] < 0)
    luo_wins = sum(1 for r in allr if r["luo_pct"] < 0)
    L.append(f"% voyages: {n}")
    L.append(f"% RH-SR  saves vs Naive on {sr_wins}/{n}")
    L.append(f"% RH-Luo saves vs Naive on {luo_wins}/{n}")
    if allr:
        best = min(allr, key=lambda r: r["sr_pct"])
        L.append(f"% best RH-SR saving {best['sr_pct']:+.2f}% (sh {best['sh']})")
        exc = [r for r in allr if r["sr_pct"] >= 0]
        if exc:
            L.append("% RH-SR exceptions: " +
                     ", ".join(f"{r['sr_pct']:+.2f}% (sh {r['sh']})" for r in exc))
        else:
            L.append("% RH-SR exceptions: none -- saved on every voyage")
    for rk, label, _eta, _tag in ROUTES:
        rows = per[rk]
        if not rows:
            continue
        L.append(f"% {label}: n={len(rows)}  RH-SR mean {st.mean([r['sr_pct'] for r in rows]):+.2f}%  "
                 f"RH-Luo mean {st.mean([r['luo_pct'] for r in rows]):+.2f}%")
        L.append(f"%   RH-SR vs oracle: mean {st.mean([r['sr_vs_oracle'] for r in rows]):+.3f} mt; "
                 f"RH-Luo vs oracle mean {st.mean([r['luo_vs_oracle'] for r in rows]):+.3f} mt")
        gs = sum(1 for r in rows if r["gates_sr"])
        gl = sum(1 for r in rows if r["gates_luo"])
        L.append(f"%   gates all-pass: SR {gs}/{len(rows)}, Luo {gl}/{len(rows)}")
        bad = {}
        for r in rows:
            if not r["gates_luo"]:
                for k, v in r["gate_detail_luo"].items():
                    if not v:
                        bad[k] = bad.get(k, 0) + 1
        if bad:
            L.append("%   Luo gate failures: " +
                     ", ".join(f"{k} x{v}" for k, v in sorted(bad.items())))
    # §8.2 diagnostic
    L.append("%")
    L.append("% §8.2 re-plan diagnostic (first-block speed revised / re-plans with a prior plan):")
    for rk, label, _eta, _tag in ROUTES:
        tot_sr = tot_luo = rev_sr = rev_luo = 0
        for r in per[rk]:
            a, b = _revisions(r["dir"] / "rh_sr_replans.csv")
            c, d = _revisions(r["dir"] / "rh_luo_replans.csv")
            rev_sr += a; tot_sr += b; rev_luo += c; tot_luo += d
        if tot_sr or tot_luo:
            L.append(f"%   {label}: SR {rev_sr}/{tot_sr}, Luo {rev_luo}/{tot_luo}")
    return "\n".join(L)


def main() -> int:
    ap = argparse.ArgumentParser(prog="make_rh_tables")
    ap.add_argument("--run_dir", required=True)
    ap.add_argument("--out")
    args = ap.parse_args()

    run_dir = Path(args.run_dir).resolve()
    per = load(run_dir)
    n = sum(len(v) for v in per.values())
    if n == 0:
        sys.exit(f"no summary.json found under {run_dir}")
    blocks = [
        f"% rolling horizon, {n} voyages, from {run_dir.name}",
        aggregate_table(per), "",
    ]
    for rk, label, eta, tag in ROUTES:
        if per[rk]:
            blocks += [per_voyage_table(per, rk, label, eta, tag), ""]
    blocks.append(prose_stats(per))
    text = "\n".join(blocks)
    if args.out:
        Path(args.out).write_text(text + "\n")
        print(f"wrote {args.out}  ({n} voyages)")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())

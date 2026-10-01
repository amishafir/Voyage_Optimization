"""Paired t-tests for the paper's planner comparisons (Section 6).

Four comparisons per route: SR against Naive and Luo against Naive, under each
of the two information regimes. Both planners are measured against the same
baseline rather than against each other. Pairing is by departure hour -- every planner sails
the same 41 departures (Section 5.3), so the per-voyage differences are paired
and the departure-to-departure variation, which dwarfs the planner differences,
cancels out.

Reads the rolling-horizon chain run, which carries both regimes in one file:
``oracle_sr``/``oracle_luo`` are the perfect-foresight results and
``rh_sr_mt``/``rh_luo_mt`` the forecast ones, against a common ``naive_mt``
that does not re-plan and is therefore identical under both.

Student-t tail probabilities come from the regularised incomplete beta function
evaluated by a Lentz continued fraction, so the module has no SciPy dependency
(SciPy is not installed in this project's venv).

Usage (from pipeline/dp_rebuild/):
    ../../venv/bin/python make_ttests.py              # table to stdout
    ../../venv/bin/python make_ttests.py --latex      # LaTeX tabular
"""
from __future__ import annotations

import argparse
import csv
import math
from pathlib import Path
from typing import List, Sequence, Tuple

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "runs" / "2026_09_09_rh_chain41_waypoint" / "results.csv"

ROUTE_NAME = {"route1": "Indian Ocean", "route2": "North Atlantic"}

# (regime label, comparison label, column, baseline column)
# Every comparison is against Naive: it is the common reference, it does not
# re-plan, and it is identical under both regimes, so each row is readable on
# its own and the two planners are never measured against each other.
COMPARISONS = [
    ("Perfect foresight", "SR vs Naive", "oracle_sr", "naive_mt"),
    ("Perfect foresight", "Luo vs Naive", "oracle_luo", "naive_mt"),
    ("Rolling horizon", "SR vs Naive", "rh_sr_mt", "naive_mt"),
    ("Rolling horizon", "Luo vs Naive", "rh_luo_mt", "naive_mt"),
]


def _betacf(a: float, b: float, x: float, itmax: int = 300, eps: float = 3e-16) -> float:
    """Continued fraction for the incomplete beta function (Lentz's method)."""
    tiny = 1e-300
    qab, qap, qam = a + b, a + 1.0, a - 1.0
    c = 1.0
    d = 1.0 - qab * x / qap
    if abs(d) < tiny:
        d = tiny
    d = 1.0 / d
    h = d
    for m in range(1, itmax + 1):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        c = 1.0 + aa / c
        if abs(d) < tiny:
            d = tiny
        if abs(c) < tiny:
            c = tiny
        d = 1.0 / d
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        c = 1.0 + aa / c
        if abs(d) < tiny:
            d = tiny
        if abs(c) < tiny:
            c = tiny
        d = 1.0 / d
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < eps:
            break
    return h


def t_two_sided_p(t: float, df: int) -> float:
    """P(|T| > |t|) for Student's t with df degrees of freedom."""
    t = abs(t)
    x = df / (df + t * t)
    a, b = df / 2.0, 0.5
    lbeta = math.lgamma(a) + math.lgamma(b) - math.lgamma(a + b)
    if x < (a + 1.0) / (a + b + 2.0):
        return math.exp(a * math.log(x) + b * math.log1p(-x) - lbeta) * _betacf(a, b, x) / a
    return 1.0 - math.exp(b * math.log1p(-x) + a * math.log(x) - lbeta) * _betacf(b, a, 1 - x) / b


def paired_t(diffs: Sequence[float]) -> dict:
    """Paired t-test on the per-voyage differences, plus a 95% CI and Cohen's dz."""
    n = len(diffs)
    mean = sum(diffs) / n
    sd = math.sqrt(sum((d - mean) ** 2 for d in diffs) / (n - 1))
    se = sd / math.sqrt(n)
    t = mean / se if se else math.inf
    return {
        "n": n,
        "mean": mean,
        "sd": sd,
        "t": t,
        "p": t_two_sided_p(t, n - 1),
        "lo": mean - 1.96 * se,
        "hi": mean + 1.96 * se,
        "dz": mean / sd if sd else math.inf,
    }


def load(path: Path) -> List[dict]:
    with path.open() as fh:
        return list(csv.DictReader(fh))


def results(rows: List[dict]) -> List[Tuple[str, str, str, dict]]:
    out = []
    for route in ("route1", "route2"):
        subset = [r for r in rows if r["route"] == route]
        for regime, label, col, base in COMPARISONS:
            diffs = [float(r[col]) - float(r[base]) for r in subset]
            out.append((ROUTE_NAME[route], regime, label, paired_t(diffs)))
    return out


def fmt_p(p: float) -> str:
    """Plain-text p-value."""
    return f"{p:.3f}" if p >= 1e-3 else f"{p:.0e}".replace("e-0", "e-")


def fmt_p_tex(p: float) -> str:
    """p-value as LaTeX math; small values in scientific notation, not '5e-11'."""
    if p >= 1e-3:
        return f"{p:.3f}"
    mantissa, exponent = f"{p:.0e}".split("e")
    return rf"{mantissa}\times 10^{{{int(exponent)}}}"


def print_plain(rows) -> None:
    head = f"{'Route':16}{'Regime':19}{'Test':13}{'mean (mt)':>10}{'95% CI':>20}{'t':>8}{'p':>10}{'dz':>8}"
    print(head)
    print("-" * len(head))
    for route, regime, label, s in rows:
        ci = f"[{s['lo']:6.2f},{s['hi']:6.2f}]"
        print(f"{route:16}{regime:19}{label:13}{s['mean']:10.2f}{ci:>20}{s['t']:8.2f}{fmt_p(s['p']):>10}{s['dz']:8.2f}")


def print_latex(rows) -> None:
    print(r"\begin{table}[ht]")
    print(r"\centering")
    print(r"\caption{Paired $t$-tests on per-voyage realised fuel, pairing by departure hour")
    print(r"(Section~\ref{sec:protocol}). A negative mean difference is fuel saved against Naive. The")
    print(r"interval is a 95\% confidence interval on that difference. Per-voyage figures are in")
    print(r"\ref{app:pervoyage}.}")
    print(r"\label{tab:ttests}")
    print(r"\begin{tabular}{lllrrrrr}")
    print(r"\toprule")
    print(r"Route & Regime & Test & $n$ & Mean diff.\ (mt) & 95\% CI (mt) & $t$ & $p$ \\")
    print(r"\midrule")
    prev = None
    for route, regime, label, s in rows:
        if prev is not None and route != prev:
            print(r"\midrule")
        prev = route
        ci = f"[${s['lo']:.2f}$, ${s['hi']:.2f}$]"
        print(f"{route} & {regime} & {label} & {s['n']} & ${s['mean']:.2f}$ & {ci} & "
              f"${s['t']:.2f}$ & ${fmt_p_tex(s['p'])}$ \\\\")
    print(r"\bottomrule")
    print(r"\end{tabular}")
    print(r"\end{table}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--latex", action="store_true", help="emit a LaTeX tabular instead of plain text")
    args = ap.parse_args()
    rows = results(load(SRC))
    (print_latex if args.latex else print_plain)(rows)


if __name__ == "__main__":
    main()

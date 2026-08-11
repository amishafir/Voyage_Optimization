"""
Analyse the chain-sweep results.csv produced by run_chain_sweep.py.

Prints:
  - Per-route summary table (count, mean / median / 95% CI / min / max for
    SR fuel, Luo fuel, Baseline (Naive constant-speed) fuel, and the three
    paired gaps: SR-Luo, SR-Baseline, Luo-Baseline)
  - Per-voyage table (fuel and gaps by sh_base)
  - Markdown-formatted block ready to paste into the meeting prep doc

Spread is reported as a 95% confidence interval, not standard deviation
(see ../../00_design/G7_v2_evidence_refresh.md §C.2): SR, Luo, and Baseline
all run on the *same* voyages/weather, so the three gap columns are paired
differences, not independent samples. Primary interval is a paired bootstrap
percentile CI (no normality assumption -- matters at n~13-22 voyages/route);
a paired t-interval is reported alongside the three gap columns as a
cross-check (see ``_t_interval``) -- a large divergence between the two
methods is a flag to trust the bootstrap and look closer, not to average them.

Usage::

    python3 analyze_chain_sweep.py
        [--results PATH]   path to results.csv (default: ../../results/2026_08_11_chain_sweep_v2/results.csv)
        [--n_boot N]       bootstrap resamples per CI (default: 10000)
"""
from __future__ import annotations

import argparse
import csv
import math
import random
import statistics
import sys
from collections import defaultdict
from pathlib import Path

from scipy import stats as spstats

_HERE = Path(__file__).resolve().parent
DEFAULT_RESULTS = (_HERE.parent.parent / "results" / "2026_08_11_chain_sweep_v2"
                   / "results.csv")

# Fixed seed: bootstrap CIs are reproducible run-to-run on the same data.
_BOOT_SEED = 20260811


def _bootstrap_ci(values, n_iter=10000, alpha=0.05, seed=_BOOT_SEED):
    """Percentile bootstrap CI for the mean of ``values``.

    Resamples voyages with replacement and recomputes the mean each time.
    When ``values`` is itself a per-voyage difference (SR-Luo, SR-Baseline,
    Luo-Baseline gap), this is a *paired* bootstrap -- the pairing is already
    baked into each element before resampling.
    """
    n = len(values)
    if n == 0:
        return (float("nan"), float("nan"))
    if n == 1:
        return (values[0], values[0])
    rng = random.Random(seed)
    means = []
    for _ in range(n_iter):
        resample_sum = 0.0
        for _ in range(n):
            resample_sum += values[rng.randrange(n)]
        means.append(resample_sum / n)
    means.sort()
    lo = means[int(round((alpha / 2) * n_iter))]
    hi = means[min(int(round((1 - alpha / 2) * n_iter)), n_iter - 1)]
    return (lo, hi)


def _t_interval(values, alpha=0.05):
    """Paired/one-sample Student's-t interval for the mean of ``values``."""
    n = len(values)
    if n < 2:
        return (float("nan"), float("nan"))
    m = statistics.mean(values)
    s = statistics.stdev(values)  # sample stdev, ddof=1
    tcrit = spstats.t.ppf(1 - alpha / 2, df=n - 1)
    half = tcrit * s / math.sqrt(n)
    return (m - half, m + half)


def _stat(values, label, n_boot=10000):
    """Descriptive line: n, mean, median, 95% bootstrap CI, min, max."""
    if not values:
        return f"{label}: (no rows)"
    lo, hi = _bootstrap_ci(values, n_iter=n_boot)
    return (f"{label}: n={len(values):>2}  "
            f"mean={statistics.mean(values):8.3f}  "
            f"median={statistics.median(values):8.3f}  "
            f"95% CI=[{lo:7.3f}, {hi:7.3f}] (bootstrap)  "
            f"min={min(values):8.3f}  max={max(values):8.3f}")


def _gap_line(values, label, n_boot=10000):
    """Gap line with BOTH intervals shown side by side (bootstrap + t)."""
    if not values:
        return f"{label}: (no rows)"
    b_lo, b_hi = _bootstrap_ci(values, n_iter=n_boot)
    t_lo, t_hi = _t_interval(values)
    return (f"{label}: n={len(values):>2}  mean={statistics.mean(values):+8.3f}  "
            f"bootstrap 95% CI=[{b_lo:+7.3f}, {b_hi:+7.3f}]  "
            f"t-interval 95% CI=[{t_lo:+7.3f}, {t_hi:+7.3f}]")


def _fmt_ci_md(values, n_boot=10000):
    """``mean [lo, hi]`` cell for a markdown table, bootstrap CI."""
    lo, hi = _bootstrap_ci(values, n_iter=n_boot)
    return f"{statistics.mean(values):.2f} [{lo:.2f}, {hi:.2f}]"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", type=Path, default=DEFAULT_RESULTS)
    ap.add_argument("--n_boot", type=int, default=10000,
                    help="Bootstrap resamples per confidence interval (default: 10000)")
    args = ap.parse_args()

    if not args.results.exists():
        print(f"results.csv not found: {args.results}", file=sys.stderr)
        return 1

    rows_by_route = defaultdict(list)
    with open(args.results) as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows_by_route[row["route"]].append(row)

    print(f"Source: {args.results}")
    print(f"Total voyages: {sum(len(v) for v in rows_by_route.values())}")
    print(f"Bootstrap resamples per CI: {args.n_boot}  (seed={_BOOT_SEED})")
    print()

    for route_key in sorted(rows_by_route):
        rows = rows_by_route[route_key]
        sr_fuels = [float(r["sr_fuel_mt"]) for r in rows]
        luo_fuels = [float(r["luo_fuel_mt"]) for r in rows]
        baseline_fuels = [float(r["baseline_fuel_mt"]) for r in rows]
        gaps = [float(r["gap_mt"]) for r in rows]
        gap_pcts = [float(r["gap_pct"]) for r in rows]
        gaps_sr_base = [float(r["gap_sr_baseline_mt"]) for r in rows]
        gaps_sr_base_pct = [float(r["gap_sr_baseline_pct"]) for r in rows]
        gaps_luo_base = [float(r["gap_luo_baseline_mt"]) for r in rows]
        gaps_luo_base_pct = [float(r["gap_luo_baseline_pct"]) for r in rows]
        sr_slacks = [float(r["sr_slack_h"]) for r in rows]
        luo_slacks = [float(r["luo_slack_h"]) for r in rows]
        label = rows[0]["label"]

        print(f"== {route_key} ({label}) — {len(rows)} voyages ==")
        print(_stat(sr_fuels,       "SR fuel (mt)        ", args.n_boot))
        print(_stat(luo_fuels,      "Luo fuel (mt)       ", args.n_boot))
        print(_stat(baseline_fuels, "Baseline fuel (mt)  ", args.n_boot))
        print()
        print(_gap_line(gaps,             "SR-Luo gap (mt)     ", args.n_boot))
        print(_gap_line(gap_pcts,         "SR-Luo gap (%)      ", args.n_boot))
        print(_gap_line(gaps_sr_base,     "SR-Baseline gap (mt)", args.n_boot))
        print(_gap_line(gaps_sr_base_pct, "SR-Baseline gap (%) ", args.n_boot))
        print(_gap_line(gaps_luo_base,    "Luo-Baseline gap (mt)", args.n_boot))
        print(_gap_line(gaps_luo_base_pct,"Luo-Baseline gap (%) ", args.n_boot))
        print()
        print(_stat(sr_slacks,  "SR slack (h)        ", args.n_boot))
        print(_stat(luo_slacks, "Luo slack (h)       ", args.n_boot))
        print()

        print(f"Voyage detail ({route_key}):")
        print(f"  {'idx':>3}  {'sh_base':>7}  {'SR (mt)':>10}  {'Luo (mt)':>10}  "
              f"{'Base (mt)':>10}  {'SR-Luo':>9}  {'SR-Base':>9}  {'Luo-Base':>9}")
        for r in rows:
            print(f"  {int(r['voyage_idx']):>3}  {int(r['sh_base']):>7}  "
                  f"{float(r['sr_fuel_mt']):>10.3f}  {float(r['luo_fuel_mt']):>10.3f}  "
                  f"{float(r['baseline_fuel_mt']):>10.3f}  "
                  f"{float(r['gap_mt']):>+9.3f}  "
                  f"{float(r['gap_sr_baseline_mt']):>+9.3f}  "
                  f"{float(r['gap_luo_baseline_mt']):>+9.3f}")
        print()

    # ------------------------------------------------------------------
    # Markdown summary table — for pasting into the meeting-prep doc
    # ------------------------------------------------------------------
    print("=" * 72)
    print("MARKDOWN — per-route summary (spread = 95% bootstrap CI, not std)")
    print("=" * 72)
    print()
    print("| Route | n | SR fuel (mt) | Luo fuel (mt) | Baseline fuel (mt) | "
          "SR−Luo gap (mt) | SR−Base gap (mt) | Luo−Base gap (mt) | Gap % (SR−Luo) |")
    print("|---|---:|---:|---:|---:|---:|---:|---:|---:|")
    for route_key in sorted(rows_by_route):
        rows = rows_by_route[route_key]
        sr_fuels = [float(r["sr_fuel_mt"]) for r in rows]
        luo_fuels = [float(r["luo_fuel_mt"]) for r in rows]
        baseline_fuels = [float(r["baseline_fuel_mt"]) for r in rows]
        gaps = [float(r["gap_mt"]) for r in rows]
        gap_pcts = [float(r["gap_pct"]) for r in rows]
        gaps_sr_base = [float(r["gap_sr_baseline_mt"]) for r in rows]
        gaps_luo_base = [float(r["gap_luo_baseline_mt"]) for r in rows]
        label = rows[0]["label"]
        print(f"| {route_key} ({label}) | {len(rows)} | "
              f"{_fmt_ci_md(sr_fuels, args.n_boot)} | "
              f"{_fmt_ci_md(luo_fuels, args.n_boot)} | "
              f"{_fmt_ci_md(baseline_fuels, args.n_boot)} | "
              f"{_fmt_ci_md(gaps, args.n_boot)} | "
              f"{_fmt_ci_md(gaps_sr_base, args.n_boot)} | "
              f"{_fmt_ci_md(gaps_luo_base, args.n_boot)} | "
              f"{_fmt_ci_md(gap_pcts, args.n_boot)} |")

    print()
    print("=" * 72)
    print("MARKDOWN — per-voyage detail")
    print("=" * 72)
    for route_key in sorted(rows_by_route):
        rows = rows_by_route[route_key]
        label = rows[0]["label"]
        print()
        print(f"**{route_key} ({label})** — ETA {rows[0]['eta_h']} h")
        print()
        print("| voyage | sh_base | SR (mt) | Luo (mt) | Baseline (mt) | "
              "SR-Luo (mt) | SR-Base (mt) | Luo-Base (mt) |")
        print("|---:|---:|---:|---:|---:|---:|---:|---:|")
        for r in rows:
            print(f"| {int(r['voyage_idx'])} | {int(r['sh_base'])} | "
                  f"{float(r['sr_fuel_mt']):.3f} | {float(r['luo_fuel_mt']):.3f} | "
                  f"{float(r['baseline_fuel_mt']):.3f} | "
                  f"{float(r['gap_mt']):+.3f} | "
                  f"{float(r['gap_sr_baseline_mt']):+.3f} | "
                  f"{float(r['gap_luo_baseline_mt']):+.3f} |")

    return 0


if __name__ == "__main__":
    sys.exit(main())

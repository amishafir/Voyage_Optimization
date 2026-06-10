"""
Analyse the chain-sweep results.csv produced by run_chain_sweep.py.

Prints:
  - Per-route summary table (count, mean / median / std / min / max for
    SR fuel, Luo fuel, SR-Luo gap, arrival slack)
  - Per-voyage table (fuel and gap by sh_base)
  - Markdown-formatted block ready to paste into the meeting prep doc

Usage::

    python3 analyze_chain_sweep.py
        [--results PATH]   path to results.csv (default: runs/2026_06_01_chain_sweep/results.csv)
"""
from __future__ import annotations

import argparse
import csv
import statistics
import sys
from collections import defaultdict
from pathlib import Path

_HERE = Path(__file__).resolve().parent
DEFAULT_RESULTS = _HERE.parent.parent / "runs" / "2026_06_01_chain_sweep" / "results.csv"


def _stat(values, label):
    if not values:
        return f"{label}: (no rows)"
    return (f"{label}: n={len(values):>2}  "
            f"mean={statistics.mean(values):8.3f}  "
            f"median={statistics.median(values):8.3f}  "
            f"std={statistics.pstdev(values):6.3f}  "
            f"min={min(values):8.3f}  max={max(values):8.3f}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", type=Path, default=DEFAULT_RESULTS)
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
    print()

    for route_key in sorted(rows_by_route):
        rows = rows_by_route[route_key]
        sr_fuels = [float(r["sr_fuel_mt"]) for r in rows]
        luo_fuels = [float(r["luo_fuel_mt"]) for r in rows]
        gaps = [float(r["gap_mt"]) for r in rows]
        gap_pcts = [float(r["gap_pct"]) for r in rows]
        sr_slacks = [float(r["sr_slack_h"]) for r in rows]
        luo_slacks = [float(r["luo_slack_h"]) for r in rows]
        label = rows[0]["label"]

        print(f"== {route_key} ({label}) — {len(rows)} voyages ==")
        print(_stat(sr_fuels,   "SR fuel (mt)    "))
        print(_stat(luo_fuels,  "Luo fuel (mt)   "))
        print(_stat(gaps,       "SR-Luo gap (mt) "))
        print(_stat(gap_pcts,   "Gap %           "))
        print(_stat(sr_slacks,  "SR slack (h)    "))
        print(_stat(luo_slacks, "Luo slack (h)   "))
        print()

        print(f"Voyage detail ({route_key}):")
        print(f"  {'idx':>3}  {'sh_base':>7}  {'SR (mt)':>10}  {'Luo (mt)':>10}  "
              f"{'gap (mt)':>9}  {'gap %':>7}  {'SR slack':>8}  {'Luo slack':>9}")
        for r in rows:
            print(f"  {int(r['voyage_idx']):>3}  {int(r['sh_base']):>7}  "
                  f"{float(r['sr_fuel_mt']):>10.3f}  {float(r['luo_fuel_mt']):>10.3f}  "
                  f"{float(r['gap_mt']):>+9.3f}  {float(r['gap_pct']):>+7.2f}  "
                  f"{float(r['sr_slack_h']):>+8.3f}  {float(r['luo_slack_h']):>+9.3f}")
        print()

    # ------------------------------------------------------------------
    # Markdown summary table — for pasting into the meeting-prep doc
    # ------------------------------------------------------------------
    print("=" * 72)
    print("MARKDOWN — per-route summary")
    print("=" * 72)
    print()
    print("| Route | n | SR fuel (mt) mean ± std | Luo fuel (mt) mean ± std | "
          "SR−Luo gap (mt) mean | Gap % mean | SR slack (h) mean |")
    print("|---|---:|---:|---:|---:|---:|---:|")
    for route_key in sorted(rows_by_route):
        rows = rows_by_route[route_key]
        sr_fuels = [float(r["sr_fuel_mt"]) for r in rows]
        luo_fuels = [float(r["luo_fuel_mt"]) for r in rows]
        gaps = [float(r["gap_mt"]) for r in rows]
        gap_pcts = [float(r["gap_pct"]) for r in rows]
        sr_slacks = [float(r["sr_slack_h"]) for r in rows]
        label = rows[0]["label"]
        print(f"| {route_key} ({label}) | {len(rows)} | "
              f"{statistics.mean(sr_fuels):.2f} ± {statistics.pstdev(sr_fuels):.2f} | "
              f"{statistics.mean(luo_fuels):.2f} ± {statistics.pstdev(luo_fuels):.2f} | "
              f"{statistics.mean(gaps):+.3f} | "
              f"{statistics.mean(gap_pcts):+.2f} | "
              f"{statistics.mean(sr_slacks):+.3f} |")

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
        print("| voyage | sh_base | SR (mt) | Luo (mt) | gap (mt) | gap % | "
              "SR slack (h) | Luo slack (h) |")
        print("|---:|---:|---:|---:|---:|---:|---:|---:|")
        for r in rows:
            print(f"| {int(r['voyage_idx'])} | {int(r['sh_base'])} | "
                  f"{float(r['sr_fuel_mt']):.3f} | {float(r['luo_fuel_mt']):.3f} | "
                  f"{float(r['gap_mt']):+.3f} | {float(r['gap_pct']):+.2f} | "
                  f"{float(r['sr_slack_h']):+.3f} | {float(r['luo_slack_h']):+.3f} |")

    return 0


if __name__ == "__main__":
    sys.exit(main())

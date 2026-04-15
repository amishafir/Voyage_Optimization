#!/usr/bin/env python3
"""
Experiment 1 — DP vs Luo head-to-head (single plan, full hindsight).

Runs both free-DP and locked-DP on the same HDF5 data and departure hour,
then prints a side-by-side comparison table.

Usage:
    cd pipeline
    python -m experiments.run_exp1 \
        --hdf5 data/experiment_d_391wp.h5 \
        --departure 0 \
        [--departure 60] \
        [--lock-hours 6] \
        [--speed-range 9 15]
"""

import argparse
import copy
import logging
import os
import sys
import time

import yaml

# Ensure pipeline root is on PYTHONPATH
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dynamic_det.transform import transform
from dynamic_det.optimize import optimize

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)-20s %(levelname)-5s %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("exp1")


def load_config(speed_range=None):
    """Load the Exp 1 config YAML."""
    cfg_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "config", "experiment_exp1_luo.yaml",
    )
    with open(cfg_path) as f:
        config = yaml.safe_load(f)

    if speed_range:
        config["ship"]["speed_range_knots"] = list(speed_range)

    return config


def run_variant(hdf5_path, config, departure_hour, lock_hours):
    """Run one DP variant and return the result dict."""
    cfg = copy.deepcopy(config)
    cfg["dynamic_det"]["forecast_origin"] = departure_hour
    cfg["dynamic_det"]["weather_source"] = "actual_hindsight"

    if lock_hours is None:
        cfg["dynamic_det"].pop("speed_lock_hours", None)
        label = "free"
    else:
        cfg["dynamic_det"]["speed_lock_hours"] = lock_hours
        label = f"locked_{lock_hours}h"

    logger.info("=== Running %s (departure SH=%d) ===", label, departure_hour)
    t0 = time.time()

    data = transform(hdf5_path, cfg)
    result = optimize(data, cfg)

    result["label"] = label
    result["departure_hour"] = departure_hour
    result["wall_time_s"] = round(time.time() - t0, 2)

    return result


def print_comparison(results):
    """Print a side-by-side comparison table."""
    print("\n" + "=" * 80)
    print("EXPERIMENT 1 — RESULTS")
    print("=" * 80)

    # Group by departure hour
    departures = sorted(set(r["departure_hour"] for r in results))

    for dep in departures:
        dep_results = [r for r in results if r["departure_hour"] == dep]
        print(f"\n--- Departure SH={dep} ---\n")

        header = f"{'Variant':<20} {'Fuel (mt)':>10} {'Time (h)':>10} {'Delay (h)':>10} {'Status':<12} {'Solver':<22} {'Compute (s)':>12}"
        print(header)
        print("-" * len(header))

        fuels = []
        for r in sorted(dep_results, key=lambda x: x["label"]):
            fuel = r.get("planned_fuel_mt", 0)
            fuels.append(fuel)
            print(
                f"{r['label']:<20} "
                f"{fuel:>10.2f} "
                f"{r.get('planned_time_h', 0):>10.2f} "
                f"{r.get('planned_delay_h', 0):>10.2f} "
                f"{r.get('status', '?'):<12} "
                f"{r.get('solver', '?'):<22} "
                f"{r.get('wall_time_s', 0):>12.2f}"
            )

        if len(fuels) >= 2:
            free_fuel = next(
                (r.get("planned_fuel_mt", 0) for r in dep_results
                 if r["label"] == "free"), None)
            locked_fuel = next(
                (r.get("planned_fuel_mt", 0) for r in dep_results
                 if r["label"] != "free"), None)

            if free_fuel and locked_fuel and locked_fuel > 0:
                gap = locked_fuel - free_fuel
                gap_pct = 100.0 * gap / locked_fuel
                print(f"\n  Gap: {gap:+.2f} mt ({gap_pct:+.2f}%) — "
                      f"fine-grained saves {gap:.2f} mt vs locked")

        # Speed change counts
        for r in dep_results:
            sched = r.get("speed_schedule", [])
            if len(sched) < 2:
                continue
            changes = sum(
                1 for i in range(1, len(sched))
                if abs(sched[i]["sws_knots"] - sched[i - 1]["sws_knots"]) > 0.01
            )
            print(f"  {r['label']}: {changes} speed changes across {len(sched)} legs")

    print("\n" + "=" * 80)


def main():
    parser = argparse.ArgumentParser(description="Exp 1: DP vs Luo head-to-head")
    parser.add_argument("--hdf5", required=True, help="Path to HDF5 weather file")
    parser.add_argument("--departure", type=int, nargs="+", default=[0],
                        help="Departure sample hours (e.g. 0 60)")
    parser.add_argument("--lock-hours", type=float, default=6.0,
                        help="Lock block duration for Luo-style (default: 6)")
    parser.add_argument("--speed-range", type=float, nargs=2, default=None,
                        help="Override speed range (e.g. 9 15)")
    args = parser.parse_args()

    config = load_config(speed_range=args.speed_range)
    results = []

    for dep in args.departure:
        # Variant A: free (ours)
        r_free = run_variant(args.hdf5, config, dep, lock_hours=None)
        results.append(r_free)

        # Variant B: locked (Luo-style)
        r_locked = run_variant(args.hdf5, config, dep, lock_hours=args.lock_hours)
        results.append(r_locked)

    print_comparison(results)


if __name__ == "__main__":
    main()

"""Run all experiments on exp_a / exp_b data.

Steps:
  1. Validate HDF5 files
  2. Full forecast error curve (0-143h) from exp_b
  3. 2x2 spatial x temporal decomposition (exp_a + exp_b)
  4. Horizon sweep on shorter route (exp_b)
  5. Generalizability comparison with old route

Usage:
    cd pipeline
    python3 run_exp_ab.py                    # Run all
    python3 run_exp_ab.py --step validate    # Just validate
    python3 run_exp_ab.py --step forecast    # Just forecast error
    python3 run_exp_ab.py --step decomp      # Just 2x2 decomposition
    python3 run_exp_ab.py --step horizon     # Just horizon sweep
    python3 run_exp_ab.py --step compare     # Just generalizability
"""

import argparse
import json
import logging
import os
import sys
import yaml

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
OUTPUT_DIR = os.path.join(BASE_DIR, "output", "exp_ab")

HDF5_A = os.path.join(DATA_DIR, "experiment_a_7wp.h5")
HDF5_B = os.path.join(DATA_DIR, "experiment_b_138wp.h5")
HDF5_OLD = os.path.join(DATA_DIR, "voyage_weather.h5")

CONFIG_A = os.path.join(BASE_DIR, "config", "experiment_exp_a.yaml")
CONFIG_B = os.path.join(BASE_DIR, "config", "experiment_exp_b.yaml")
CONFIG_OLD = os.path.join(BASE_DIR, "config", "experiment.yaml")


def load_config(path):
    with open(path) as f:
        return yaml.safe_load(f)


def step_validate():
    """Step 1: Validate both HDF5 files."""
    from validate_experiments import validate_hdf5

    print("\n" + "=" * 70)
    print("STEP 1: VALIDATE HDF5 FILES")
    print("=" * 70)

    ok_a = validate_hdf5(HDF5_A, expected_nodes=7)
    ok_b = validate_hdf5(HDF5_B)

    if not ok_a or not ok_b:
        print("\nWARNING: Validation issues detected. Continuing anyway...")
    return ok_a and ok_b


def step_forecast_error():
    """Step 2: Full forecast error curve (0-143h) from exp_b."""
    from compare.thesis_analysis import analysis_forecast_error

    print("\n" + "=" * 70)
    print("STEP 2: FULL FORECAST ERROR CURVE (0-143h)")
    print("=" * 70)

    result = analysis_forecast_error(hdf5_path=HDF5_B, output_suffix="_full")
    return result


def step_decomposition():
    """Step 3: 2x2 spatial x temporal decomposition."""
    from compare.sensitivity import run_2x2_decomposition

    print("\n" + "=" * 70)
    print("STEP 3: 2x2 DECOMPOSITION (spatial x temporal)")
    print("=" * 70)

    config_a = load_config(CONFIG_A)
    config_b = load_config(CONFIG_B)

    decomp_dir = os.path.join(OUTPUT_DIR, "decomposition")
    result = run_2x2_decomposition(config_a, config_b, HDF5_A, HDF5_B, decomp_dir)
    return result


def step_horizon_sweep():
    """Step 4: Horizon sweep on shorter route."""
    from compare.sensitivity import run_short_route_horizon_sweep

    print("\n" + "=" * 70)
    print("STEP 4: SHORT-ROUTE HORIZON SWEEP")
    print("=" * 70)

    config_b = load_config(CONFIG_B)

    horizon_dir = os.path.join(OUTPUT_DIR, "horizon_sweep")
    result = run_short_route_horizon_sweep(config_b, HDF5_B, horizon_dir)
    return result


def step_generalizability():
    """Step 5: Lightweight comparison between old route and new route."""
    from shared.hdf5_io import read_metadata, read_actual, get_completed_runs

    import numpy as np
    import pandas as pd

    print("\n" + "=" * 70)
    print("STEP 5: GENERALIZABILITY CHECK (old route vs new route)")
    print("=" * 70)

    compare_dir = os.path.join(OUTPUT_DIR, "generalizability")
    os.makedirs(compare_dir, exist_ok=True)

    datasets = {
        "old_route": {"path": HDF5_OLD, "desc": "13 WP, 3,394 nm, 280h, Feb 14-15"},
        "new_route": {"path": HDF5_B, "desc": "7 WP, 1,678 nm, ~140h, Feb 17-23"},
    }

    weather_fields = [
        "wind_speed_10m_kmh", "wave_height_m", "ocean_current_velocity_kmh",
    ]

    comparison = {}
    for name, info in datasets.items():
        path = info["path"]
        if not os.path.isfile(path):
            print(f"  {name}: file not found, skipping")
            continue

        meta = read_metadata(path)
        actual = read_actual(path)
        runs = get_completed_runs(path)

        stats = {
            "description": info["desc"],
            "nodes": len(meta),
            "original_waypoints": int(meta["is_original"].sum()),
            "total_distance_nm": float(meta.iloc[-1]["distance_from_start_nm"]),
            "sample_hours": len(runs),
        }

        for field in weather_fields:
            vals = actual[field].dropna()
            stats[f"{field}_mean"] = float(vals.mean())
            stats[f"{field}_std"] = float(vals.std())
            stats[f"{field}_range"] = [float(vals.min()), float(vals.max())]

        comparison[name] = stats

    # Print comparison table
    print(f"\n{'Metric':<35} {'Old Route':>15} {'New Route':>15}")
    print("-" * 68)
    if "old_route" in comparison and "new_route" in comparison:
        old = comparison["old_route"]
        new = comparison["new_route"]

        for key in ["nodes", "original_waypoints", "total_distance_nm", "sample_hours"]:
            print(f"{key:<35} {old[key]:>15} {new[key]:>15}")

        for field in weather_fields:
            short = field.replace("_10m_kmh", "").replace("_m", "").replace("_kmh", "")
            m_old = old[f"{field}_mean"]
            m_new = new[f"{field}_mean"]
            s_old = old[f"{field}_std"]
            s_new = new[f"{field}_std"]
            print(f"{short+'_mean':<35} {m_old:>15.2f} {m_new:>15.2f}")
            print(f"{short+'_std':<35} {s_old:>15.2f} {s_new:>15.2f}")

    # Load results from decomposition and horizon sweep if available
    decomp_path = os.path.join(OUTPUT_DIR, "decomposition", "decomposition_2x2.json")
    if os.path.isfile(decomp_path):
        with open(decomp_path) as f:
            decomp = json.load(f)
        comparison["new_route_decomposition"] = decomp

    # Save
    compare_path = os.path.join(compare_dir, "generalizability_comparison.json")
    with open(compare_path, "w") as f:
        json.dump(comparison, f, indent=2, default=str)
    print(f"\nSaved: {compare_path}")

    return comparison


def main():
    parser = argparse.ArgumentParser(description="Run exp_a/exp_b experiments")
    parser.add_argument("--step", type=str, default="all",
                        choices=["all", "validate", "forecast", "decomp", "horizon", "compare"],
                        help="Which step to run")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s: %(message)s",
    )

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    steps = {
        "validate": step_validate,
        "forecast": step_forecast_error,
        "decomp": step_decomposition,
        "horizon": step_horizon_sweep,
        "compare": step_generalizability,
    }

    if args.step == "all":
        for name, fn in steps.items():
            try:
                fn()
            except Exception as e:
                print(f"\nERROR in {name}: {e}")
                import traceback
                traceback.print_exc()
    else:
        steps[args.step]()


if __name__ == "__main__":
    main()

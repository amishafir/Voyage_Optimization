#!/usr/bin/env python3
"""
Experiment C — Run Pipeline on Partial Data
=============================================
Analyzes whatever data exists in the HDF5 file.

1. Reports how many sample hours are collected
2. Determines reachable distance at 12 kn average
3. Trims nodes to those reachable within collected hours
4. Runs LP, DP, RH on the trimmed dataset
5. Prints comparison table

Usage:
    python3 pipeline/run_partial_exp_c.py
    python3 pipeline/run_partial_exp_c.py pipeline/data/experiment_c_968wp.h5
"""

import os
import sys
import time

pipeline_dir = os.path.dirname(os.path.abspath(__file__))
if pipeline_dir not in sys.path:
    sys.path.insert(0, pipeline_dir)

import yaml
from shared.hdf5_io import get_completed_runs, read_metadata

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

CONFIG_PATH = os.path.join(pipeline_dir, "config", "experiment_exp_c.yaml")
DEFAULT_HDF5 = os.path.join(pipeline_dir, "data", "experiment_c_968wp.h5")
VOYAGE_SPEED_KN = 12  # average speed for reachability estimate


def load_config():
    with open(CONFIG_PATH) as f:
        return yaml.safe_load(f)


def assess_data(hdf5_path):
    """Determine what's runnable from the available data."""
    completed = get_completed_runs(hdf5_path)
    n_hours = len(completed)
    max_hour = max(completed) if completed else 0

    metadata = read_metadata(hdf5_path)
    total_nodes = len(metadata)
    total_nm = metadata["distance_from_start_nm"].max()

    # Reachable distance at average speed
    reachable_nm = max_hour * VOYAGE_SPEED_KN
    usable = metadata[metadata["distance_from_start_nm"] <= reachable_nm]
    n_usable = len(usable)

    # Original waypoints within reach (for LP segments)
    usable_originals = usable[usable["is_original"] == True]
    n_segments = max(len(usable_originals) - 1, 0)

    return {
        "completed": completed,
        "n_hours": n_hours,
        "max_hour": max_hour,
        "total_nodes": total_nodes,
        "total_nm": total_nm,
        "reachable_nm": reachable_nm,
        "n_usable_nodes": n_usable,
        "n_segments": n_segments,
        "n_original_waypoints": len(usable_originals),
        "full_voyage_ready": reachable_nm >= total_nm,
    }


def print_assessment(info):
    """Print data availability report."""
    print("\n" + "=" * 65)
    print("  DATA ASSESSMENT")
    print("=" * 65)
    print(f"  Sample hours collected:  {info['n_hours']} (max hour: {info['max_hour']})")
    print(f"  Reachable at {VOYAGE_SPEED_KN} kn:    {info['reachable_nm']:.0f} / {info['total_nm']:.0f} nm "
          f"({100*info['reachable_nm']/info['total_nm']:.0f}%)")
    print(f"  Usable nodes:            {info['n_usable_nodes']} / {info['total_nodes']}")
    print(f"  LP segments:             {info['n_segments']} "
          f"({info['n_original_waypoints']} original waypoints)")

    if info['full_voyage_ready']:
        print(f"  Status:                  FULL VOYAGE — all approaches runnable")
    elif info['n_segments'] >= 2:
        print(f"  Status:                  PARTIAL — running on reachable portion")
    else:
        print(f"  Status:                  INSUFFICIENT — need at least 2 LP segments")
        print(f"                           (collect ~{2*info['total_nm']/info['total_nodes']/VOYAGE_SPEED_KN:.0f}+ hours)")
    print("=" * 65)


# ---------------------------------------------------------------------------
# Approach runners
# ---------------------------------------------------------------------------

def run_lp(hdf5_path, config):
    from static_det.transform import transform
    from static_det.optimize import optimize
    from shared.simulation import simulate_voyage

    t0 = time.time()
    t_out = transform(hdf5_path, config)
    planned = optimize(t_out, config)
    comp_time = time.time() - t0

    if planned.get("status") != "Optimal":
        return None, f"LP status: {planned.get('status')}", comp_time

    simulated = simulate_voyage(
        planned["speed_schedule"], hdf5_path, config,
        sample_hour=config["static_det"]["weather_snapshot"],
    )
    return (planned, simulated), None, comp_time


def run_dp(hdf5_path, config):
    from dynamic_det.transform import transform
    from dynamic_det.optimize import optimize
    from shared.simulation import simulate_voyage

    t0 = time.time()
    t_out = transform(hdf5_path, config)
    planned = optimize(t_out, config)
    comp_time = time.time() - t0

    if planned.get("status") not in ("Optimal", "Feasible"):
        return None, f"DP status: {planned.get('status')}", comp_time

    simulated = simulate_voyage(
        planned["speed_schedule"], hdf5_path, config,
        sample_hour=config["dynamic_det"]["forecast_origin"],
    )
    return (planned, simulated), None, comp_time


def run_rh(hdf5_path, config):
    from dynamic_rh.transform import transform
    from dynamic_rh.optimize import optimize
    from shared.simulation import simulate_voyage

    t0 = time.time()
    t_out = transform(hdf5_path, config)
    planned = optimize(t_out, config)
    comp_time = time.time() - t0

    if planned.get("status") not in ("Optimal", "Feasible"):
        return None, f"RH status: {planned.get('status')}", comp_time

    simulated = simulate_voyage(
        planned["speed_schedule"], hdf5_path, config,
        sample_hour=0,
    )
    return (planned, simulated), None, comp_time


# ---------------------------------------------------------------------------
# Results display
# ---------------------------------------------------------------------------

def print_comparison(results):
    """Print side-by-side comparison table."""
    print("\n" + "=" * 80)
    print("  RESULTS COMPARISON")
    print("=" * 80)

    header = f"  {'Metric':<30} {'LP':>14} {'DP':>14} {'RH':>14}"
    print(header)
    print("  " + "-" * 72)

    def val(result, key_planned, key_sim=None):
        if result is None:
            return "—"
        planned, simulated = result
        if key_sim and key_sim in simulated:
            return f"{simulated[key_sim]:.2f}"
        if key_planned in planned:
            return f"{planned[key_planned]:.2f}"
        return "—"

    rows = [
        ("Planned fuel (mt)", "planned_fuel_mt", None),
        ("Simulated fuel (mt)", None, "total_fuel_mt"),
        ("Planned time (h)", "planned_time_h", None),
        ("Simulated time (h)", None, "total_time_h"),
        ("SWS violations", None, "sws_violations"),
    ]

    for label, pk, sk in rows:
        lp_val = val(results.get("LP"), pk, sk) if results.get("LP") else "—"
        dp_val = val(results.get("DP"), pk, sk) if results.get("DP") else "—"
        rh_val = val(results.get("RH"), pk, sk) if results.get("RH") else "—"
        print(f"  {label:<30} {lp_val:>14} {dp_val:>14} {rh_val:>14}")

    # Computation times
    print("  " + "-" * 72)
    for name in ["LP", "DP", "RH"]:
        ct = results.get(f"{name}_time", 0)
        print(f"  {'Computation time (s)':<30} " if name == "LP" else f"  {'':<30} ", end="")
        # Print all on one line
    lp_t = results.get("LP_time", 0)
    dp_t = results.get("DP_time", 0)
    rh_t = results.get("RH_time", 0)
    print(f"\r  {'Computation time (s)':<30} {lp_t:>14.1f} {dp_t:>14.1f} {rh_t:>14.1f}")

    print("=" * 80)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    hdf5_path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_HDF5

    if not os.path.exists(hdf5_path):
        print(f"HDF5 file not found: {hdf5_path}")
        print("Download from server first:")
        print("  scp user@Shlomo1-pcl.eng.tau.ac.il:~/Ami/experiment_c_968wp.h5 pipeline/data/")
        sys.exit(1)

    config = load_config()
    info = assess_data(hdf5_path)
    print_assessment(info)

    if info["n_segments"] < 2:
        print("\nNot enough data to run optimizers. Collect more hours first.")
        sys.exit(0)

    # Adjust config for partial data
    if not info["full_voyage_ready"]:
        config["ship"]["eta_hours"] = info["max_hour"]
        config["static_det"]["segments"] = info["n_segments"]
        print(f"\n  Adjusted ETA: {info['max_hour']}h, LP segments: {info['n_segments']}")

    results = {}

    # Run LP
    print("\nRunning LP (Static Deterministic)...")
    lp_result, lp_err, lp_time = run_lp(hdf5_path, config)
    results["LP_time"] = lp_time
    if lp_err:
        print(f"  {lp_err}")
    else:
        results["LP"] = lp_result
        print(f"  Done ({lp_time:.1f}s)")

    # Run DP
    print("Running DP (Dynamic Deterministic)...")
    dp_result, dp_err, dp_time = run_dp(hdf5_path, config)
    results["DP_time"] = dp_time
    if dp_err:
        print(f"  {dp_err}")
    else:
        results["DP"] = dp_result
        print(f"  Done ({dp_time:.1f}s)")

    # Run RH
    print("Running RH (Dynamic Rolling Horizon)...")
    rh_result, rh_err, rh_time = run_rh(hdf5_path, config)
    results["RH_time"] = rh_time
    if rh_err:
        print(f"  {rh_err}")
    else:
        results["RH"] = rh_result
        print(f"  Done ({rh_time:.1f}s)")

    print_comparison(results)


if __name__ == "__main__":
    main()

"""
Sensitivity analysis: theoretical bounds and replan frequency sweep.

- Lower bound: DP with perfect (actual) weather information
- Upper bound: Constant-speed schedule (no optimization)
- Replan sweep: Rolling Horizon at varying replan frequencies
"""

import copy
import json
import logging
import os

from shared.metrics import compute_result_metrics, build_result_json, save_result
from shared.simulation import simulate_voyage

logger = logging.getLogger(__name__)


def run_lower_bound(config, hdf5_path, output_dir):
    """Run DP optimizer with actual weather (perfect information).

    This represents the theoretical floor — the best possible fuel consumption
    if the optimizer had perfect knowledge of future weather.

    Returns:
        Result dict (also saved as result_lower_bound.json).
    """
    from dynamic_det.transform import transform
    from dynamic_det.optimize import optimize

    cfg = copy.deepcopy(config)
    cfg["dynamic_det"]["weather_source"] = "actual"
    cfg["dynamic_det"]["nodes"] = "all"

    # Relax ETA by 10% — actual weather may be harsher than predicted,
    # making the nominal ETA infeasible under real conditions.
    # The lower bound answers: "minimum fuel with perfect information"
    # regardless of the original time constraint.
    nominal_eta = cfg["ship"]["eta_hours"]
    cfg["ship"]["eta_hours"] = int(nominal_eta * 1.1)

    print("--- Lower Bound: Transform (actual weather) ---")
    t_out = transform(hdf5_path, cfg)

    print("--- Lower Bound: Optimize (DP) ---")
    planned = optimize(t_out, cfg)
    if planned.get("status") not in ("Optimal", "Feasible"):
        logger.warning("Lower bound DP status: %s", planned.get("status"))
        return None

    print("--- Lower Bound: Simulate ---")
    simulated = simulate_voyage(
        planned["speed_schedule"], hdf5_path, cfg,
        sample_hour=cfg["dynamic_det"]["forecast_origin"],
    )

    total_dist = sum(t_out["distances"])
    metrics = compute_result_metrics(planned, simulated, total_dist)

    ts_path = os.path.join(output_dir, "timeseries_lower_bound.csv")
    simulated["time_series"].to_csv(ts_path, index=False)

    result = build_result_json(
        approach="lower_bound",
        config=cfg,
        planned=planned,
        simulated=simulated,
        metrics=metrics,
        time_series_file=ts_path,
    )
    json_path = os.path.join(output_dir, "result_lower_bound.json")
    save_result(result, json_path)

    print(f"  Lower bound: {simulated['total_fuel_kg']:.2f} kg fuel, "
          f"{simulated['total_time_h']:.2f} h")
    return result


def run_upper_bound(config, hdf5_path, output_dir):
    """Simulate a constant-speed voyage (no optimization).

    Uses the mean of the speed range as SWS for all legs.
    Represents the theoretical ceiling — what happens without optimization.

    Returns:
        Result dict (also saved as result_upper_bound.json).
    """
    from shared.hdf5_io import read_metadata

    metadata = read_metadata(hdf5_path)
    metadata = metadata.sort_values("node_id").reset_index(drop=True)
    num_nodes = len(metadata)
    num_legs = num_nodes - 1

    min_speed, max_speed = config["ship"]["speed_range_knots"]
    # Use max speed for upper bound — worst-case fuel while ensuring
    # the ship meets the ETA. Mean speed may violate ETA under harsh weather.
    avg_sws = max_speed

    # Build constant-speed schedule (one entry per leg, keyed by node_id)
    schedule = []
    for i in range(num_legs):
        node_a = metadata.iloc[i]
        node_b = metadata.iloc[i + 1]
        dist = node_b["distance_from_start_nm"] - node_a["distance_from_start_nm"]
        schedule.append({
            "leg": i,
            "node_id": int(node_a["node_id"]),
            "segment": int(node_a["segment"]),
            "sws_knots": avg_sws,
            "distance_nm": max(dist, 0.001),
        })

    print("--- Upper Bound: Simulate (constant speed) ---")
    simulated = simulate_voyage(
        schedule, hdf5_path, config,
        sample_hour=0,
    )

    total_dist = sum(e["distance_nm"] for e in schedule)

    # For upper bound, planned == simulated (no optimizer)
    planned_stub = {
        "planned_fuel_kg": simulated["total_fuel_kg"],
        "planned_time_h": simulated["total_time_h"],
        "speed_schedule": schedule,
        "computation_time_s": 0.0,
        "status": "N/A",
    }
    metrics = compute_result_metrics(planned_stub, simulated, total_dist)

    ts_path = os.path.join(output_dir, "timeseries_upper_bound.csv")
    simulated["time_series"].to_csv(ts_path, index=False)

    result = build_result_json(
        approach="upper_bound",
        config=config,
        planned=planned_stub,
        simulated=simulated,
        metrics=metrics,
        time_series_file=ts_path,
    )
    json_path = os.path.join(output_dir, "result_upper_bound.json")
    save_result(result, json_path)

    print(f"  Upper bound: {simulated['total_fuel_kg']:.2f} kg fuel, "
          f"{simulated['total_time_h']:.2f} h (constant SWS={max_speed:.1f} kn)")
    return result


def run_replan_sweep(config, hdf5_path, output_dir, frequencies=None):
    """Run rolling horizon at multiple replan frequencies.

    Args:
        frequencies: List of replan frequencies in hours.
            Default: [3, 6, 12, 24, 48]

    Returns:
        List of result dicts (each also saved as result_dynamic_rh_replan_{freq}h.json).
    """
    from dynamic_rh.transform import transform
    from dynamic_rh.optimize import optimize

    if frequencies is None:
        frequencies = [3, 6, 12, 24, 48]

    results = []
    for freq in frequencies:
        cfg = copy.deepcopy(config)
        cfg["dynamic_rh"]["replan_frequency_hours"] = freq
        approach_name = f"dynamic_rh_replan_{freq}h"

        print(f"\n--- Replan Sweep: freq={freq}h ---")

        print(f"  Transform...")
        t_out = transform(hdf5_path, cfg)

        print(f"  Optimize (RH, replan every {freq}h)...")
        planned = optimize(t_out, cfg)
        if planned.get("status") not in ("Optimal", "Feasible"):
            logger.warning("Replan sweep freq=%d: status=%s", freq, planned.get("status"))
            continue

        print(f"  Simulate...")
        simulated = simulate_voyage(
            planned["speed_schedule"], hdf5_path, cfg,
            sample_hour=0,
        )

        total_dist = sum(t_out["distances"])
        metrics = compute_result_metrics(planned, simulated, total_dist)

        ts_path = os.path.join(output_dir, f"timeseries_{approach_name}.csv")
        simulated["time_series"].to_csv(ts_path, index=False)

        result = build_result_json(
            approach=approach_name,
            config=cfg,
            planned=planned,
            simulated=simulated,
            metrics=metrics,
            time_series_file=ts_path,
        )
        result["decision_points"] = planned.get("decision_points", [])
        json_path = os.path.join(output_dir, f"result_{approach_name}.json")
        save_result(result, json_path)

        print(f"  {approach_name}: {simulated['total_fuel_kg']:.2f} kg fuel, "
              f"{simulated['total_time_h']:.2f} h")
        results.append(result)

    return results


def run_sensitivity(config, output_dir, hdf5_path):
    """Top-level orchestrator for all sensitivity experiments.

    Runs bounds and replan sweep, prints summary table.

    Returns:
        Path to output directory.
    """
    os.makedirs(output_dir, exist_ok=True)

    print("=" * 60)
    print("SENSITIVITY ANALYSIS")
    print("=" * 60)

    # 1. Lower bound
    print("\n[1/3] Lower bound (perfect information)...")
    lb = run_lower_bound(config, hdf5_path, output_dir)

    # 2. Upper bound
    print("\n[2/3] Upper bound (constant speed)...")
    ub = run_upper_bound(config, hdf5_path, output_dir)

    # 3. Replan sweep
    print("\n[3/3] Replan frequency sweep...")
    sweep = run_replan_sweep(config, hdf5_path, output_dir)

    # Summary table
    print("\n" + "=" * 60)
    print("SENSITIVITY SUMMARY")
    print("=" * 60)
    print(f"{'Approach':<30}  {'Sim Fuel (kg)':>14}  {'Sim Time (h)':>13}")
    print("-" * 60)

    all_results = []
    if lb:
        all_results.append(lb)
    if ub:
        all_results.append(ub)
    all_results.extend(sweep)

    for r in all_results:
        name = r["approach"]
        fuel = r["simulated"]["total_fuel_kg"]
        time_h = r["simulated"]["voyage_time_h"]
        print(f"{name:<30}  {fuel:>14.2f}  {time_h:>13.2f}")

    print("=" * 60)
    return output_dir

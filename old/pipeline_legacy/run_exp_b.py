#!/usr/bin/env python3
"""Run all 3 approaches on experiment_b and report violations."""

import os
import sys

pipeline_dir = os.path.dirname(os.path.abspath(__file__))
if pipeline_dir not in sys.path:
    sys.path.insert(0, pipeline_dir)

import yaml
from shared.simulation import simulate_voyage

config_path = os.path.join(pipeline_dir, "config", "experiment_exp_b.yaml")
with open(config_path) as f:
    config = yaml.safe_load(f)

hdf5_path = os.path.join(pipeline_dir, "data", "experiment_b_138wp.h5")


def run_lp():
    from static_det.transform import transform
    from static_det.optimize import optimize

    t_out = transform(hdf5_path, config)
    planned = optimize(t_out, config)
    if planned.get("status") != "Optimal":
        print(f"  LP status: {planned.get('status')}")
        return
    simulated = simulate_voyage(
        planned["speed_schedule"], hdf5_path, config,
        sample_hour=config["static_det"]["weather_snapshot"],
    )
    return planned, simulated


def run_dp():
    from dynamic_det.transform import transform
    from dynamic_det.optimize import optimize

    t_out = transform(hdf5_path, config)
    planned = optimize(t_out, config)
    if planned.get("status") not in ("Optimal", "Feasible"):
        print(f"  DP status: {planned.get('status')}")
        return
    simulated = simulate_voyage(
        planned["speed_schedule"], hdf5_path, config,
        sample_hour=config["dynamic_det"]["forecast_origin"],
    )
    return planned, simulated


def run_rh():
    from dynamic_rh.transform import transform
    from dynamic_rh.optimize import optimize

    t_out = transform(hdf5_path, config)
    planned = optimize(t_out, config)
    if planned.get("status") not in ("Optimal", "Feasible"):
        print(f"  RH status: {planned.get('status')}")
        return
    simulated = simulate_voyage(
        planned["speed_schedule"], hdf5_path, config,
        sample_hour=0, time_varying=True,
    )
    return planned, simulated


def print_result(name, planned, simulated):
    # Check plan SWS range
    sws_values = [s["sws_knots"] for s in planned["speed_schedule"]]
    plan_min_sws = min(sws_values)
    plan_max_sws = max(sws_values)

    print(f"\n{'=' * 60}")
    print(f"  {name}")
    print(f"{'=' * 60}")
    print(f"  Plan:  fuel={planned['planned_fuel_mt']:.2f} mt, time={planned['planned_time_h']:.2f}h")
    print(f"  Plan SWS range: [{plan_min_sws:.2f}, {plan_max_sws:.2f}] kn")
    print(f"  Sim:   fuel={simulated['total_fuel_mt']:.2f} mt, time={simulated['total_time_h']:.2f}h")
    print(f"  Gap:   {simulated['total_fuel_mt'] - planned['planned_fuel_mt']:+.2f} mt")
    print(f"  SWS violations: {simulated['sws_violations']}")

    # Check simulation SWS details
    ts = simulated["time_series"]
    if "actual_sws_knots" in ts.columns and "planned_sws_knots" in ts.columns:
        sim_sws = ts["actual_sws_knots"]
        plan_sws_sim = ts["planned_sws_knots"]
        violations = ts[abs(ts["actual_sws_knots"] - ts["planned_sws_knots"]) > 0.01]
        print(f"  Sim SWS range: [{sim_sws.min():.4f}, {sim_sws.max():.4f}] kn")
        print(f"  Sim planned SWS range: [{plan_sws_sim.min():.4f}, {plan_sws_sim.max():.4f}] kn")
        if len(violations) > 0:
            print(f"  Violation details ({len(violations)} legs):")
            for _, row in violations.head(5).iterrows():
                print(f"    node {int(row['node_id'])}: needed SWS={row['planned_sws_knots']:.3f}, "
                      f"clamped to {row['actual_sws_knots']:.3f}")
            if len(violations) > 5:
                print(f"    ... and {len(violations) - 5} more")


print("Running LP on exp_b...")
lp_result = run_lp()
if lp_result:
    print_result("B-LP (Static Deterministic)", *lp_result)

print("\nRunning DP on exp_b...")
dp_result = run_dp()
if dp_result:
    print_result("B-DP (Dynamic Deterministic)", *dp_result)

print("\nRunning RH on exp_b...")
rh_result = run_rh()
if rh_result:
    print_result("B-RH (Dynamic Rolling Horizon)", *rh_result)

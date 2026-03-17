#!/usr/bin/env python3
"""Run all approaches on experiment_d (Route 2, North Atlantic) and compare."""

import os
import sys

pipeline_dir = os.path.dirname(os.path.abspath(__file__))
if pipeline_dir not in sys.path:
    sys.path.insert(0, pipeline_dir)

import yaml
from shared.simulation import simulate_voyage

config_path = os.path.join(pipeline_dir, "config", "experiment_exp_d.yaml")
with open(config_path) as f:
    config = yaml.safe_load(f)

hdf5_path = os.path.join(pipeline_dir, "data", "experiment_d_391wp.h5")
output_dir = os.path.join(pipeline_dir, "output")
os.makedirs(output_dir, exist_ok=True)

VALID_STATUS = ("Optimal", "Feasible", "ETA_relaxed")


def run_constant_speed():
    from compare.sensitivity import run_constant_speed_bound
    result = run_constant_speed_bound(config, hdf5_path, output_dir)
    # Extract simulated dict from sensitivity result format
    sim = result.get("simulated", result)
    return None, sim


def run_lp():
    from static_det.transform import transform
    from static_det.optimize import optimize

    t_out = transform(hdf5_path, config)
    planned = optimize(t_out, config)
    if planned.get("status") not in VALID_STATUS:
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
    if planned.get("status") not in VALID_STATUS:
        print(f"  DP status: {planned.get('status')}")
        return
    simulated = simulate_voyage(
        planned["speed_schedule"], hdf5_path, config,
        sample_hour=config["dynamic_det"]["forecast_origin"],
    )
    return planned, simulated


def run_rh_dp():
    from dynamic_rh.transform import transform
    from dynamic_rh.optimize import optimize

    t_out = transform(hdf5_path, config)
    planned = optimize(t_out, config)
    if planned.get("status") not in VALID_STATUS:
        print(f"  RH-DP status: {planned.get('status')}")
        return
    simulated = simulate_voyage(
        planned["speed_schedule"], hdf5_path, config,
        sample_hour=0, time_varying=True,
    )
    return planned, simulated


def run_rh_lp():
    from dynamic_rh.transform import transform
    from dynamic_rh.optimize_lp import optimize

    t_out = transform(hdf5_path, config)
    planned = optimize(t_out, config)
    if planned.get("status") not in VALID_STATUS:
        print(f"  RH-LP status: {planned.get('status')}")
        return
    simulated = simulate_voyage(
        planned["speed_schedule"], hdf5_path, config,
        sample_hour=0, time_varying=True,
    )
    return planned, simulated


def print_result(name, planned, simulated, weather_info=""):
    print(f"\n{'=' * 70}")
    print(f"  {name}")
    if weather_info:
        print(f"  {weather_info}")
    print(f"{'=' * 70}")

    if planned:
        sws_values = [s["sws_knots"] for s in planned["speed_schedule"]]
        delay_h = planned.get('planned_delay_h', 0)
        cost_mt = planned.get('planned_total_cost_mt', planned['planned_fuel_mt'])
        print(f"  Plan:  fuel={planned['planned_fuel_mt']:.2f} mt, "
              f"time={planned['planned_time_h']:.2f}h, "
              f"delay={delay_h:.2f}h, "
              f"cost={cost_mt:.2f} mt, "
              f"status={planned.get('status', '?')}")
        print(f"  Plan SWS range: [{min(sws_values):.2f}, {max(sws_values):.2f}] kn")

    sim_time = simulated.get('total_time_h', simulated.get('voyage_time_h', 0))
    sim_fuel = simulated.get('total_fuel_mt', 0)
    arr_dev = simulated.get('arrival_deviation_h', 0)
    adj = simulated.get('sws_adjustments', simulated.get('sws_violations', 0))
    print(f"  Sim:   fuel={sim_fuel:.2f} mt, time={sim_time:.2f}h")
    print(f"  Arrival deviation: {arr_dev:+.2f} h")
    print(f"  SWS adjustments: {adj}")

    if planned:
        gap = sim_fuel - planned['planned_fuel_mt']
        print(f"  Plan→Sim gap: {gap:+.2f} mt ({gap/planned['planned_fuel_mt']*100:+.1f}%)")


# ── Run all approaches ──────────────────────────────────────────────

print("=" * 70)
print("  EXPERIMENT D — Route 2 (North Atlantic, 389 nodes, ~163 h)")
print("=" * 70)

print("\nRunning constant speed baseline...")
cs_result = run_constant_speed()
if cs_result:
    print_result("Constant Speed (baseline)",
                 *cs_result,
                 weather_info="plan=constant SOG | sim=actual@hour0")

print("\nRunning LP...")
lp_result = run_lp()
if lp_result:
    print_result("D-LP (Static Deterministic)",
                 *lp_result,
                 weather_info="plan=actual@hour0 (segment-avg) | sim=actual@hour0 (per-node)")

print("\nRunning DP...")
dp_result = run_dp()
if dp_result:
    print_result("D-DP (Dynamic Deterministic)",
                 *dp_result,
                 weather_info="plan=predicted@hour0 (per-node) | sim=actual@hour0 (per-node)")

print("\nRunning RH-DP...")
rh_dp_result = run_rh_dp()
if rh_dp_result:
    print_result("D-RH-DP (Rolling Horizon, DP solver)",
                 *rh_dp_result,
                 weather_info="plan=predicted+actual@6h | sim=actual (time-varying)")

print("\nRunning RH-LP...")
rh_lp_result = run_rh_lp()
if rh_lp_result:
    print_result("D-RH-LP (Rolling Horizon, LP solver)",
                 *rh_lp_result,
                 weather_info="plan=actual@6h (segment-avg) | sim=actual (time-varying)")

# ── Summary table ────────────────────────────────────────────────────
lambda_val = config.get("ship", {}).get("eta_penalty_mt_per_hour", None)
lambda_str = f"λ={lambda_val}" if lambda_val is not None else "λ=∞ (hard ETA)"

print(f"\n\n{'=' * 70}")
print(f"  SUMMARY  ({lambda_str})")
print(f"{'=' * 70}")
print(f"  {'Approach':<25} {'Fuel(mt)':>10} {'Delay(h)':>10} {'Cost(mt)':>10} {'Arrival':>10} {'Adj':>5}")
print(f"  {'-'*75}")

for name, result in [
    ("Constant Speed", cs_result),
    ("LP", lp_result),
    ("DP", dp_result),
    ("RH-DP", rh_dp_result),
    ("RH-LP", rh_lp_result),
]:
    if result:
        planned, sim = result
        fuel = sim.get('total_fuel_mt', 0)
        dev = sim.get('arrival_deviation_h', 0)
        adj = sim.get('sws_adjustments', sim.get('sws_violations', 0))
        delay = planned.get('planned_delay_h', 0) if planned else 0
        cost = planned.get('planned_total_cost_mt', fuel) if planned else fuel
        print(f"  {name:<25} {fuel:>10.2f} {delay:>10.2f} {cost:>10.2f} {dev:>+10.2f}h {adj:>5}")

print(f"  {'-'*75}")

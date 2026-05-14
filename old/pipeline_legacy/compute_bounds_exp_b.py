#!/usr/bin/env python3
"""
Compute fuel upper and lower bounds for experiment_b (138 nodes, ~140h).

Upper bound: SWS = max (13 kn) at every node, SOG varies with weather.
Lower bound: Lagrangian optimization with actual weather.
             Finds the true minimum-fuel SWS at every node, subject to
             ETA constraint and SWS in [11, 13]. Continuous (no DP discretization).
"""

import math
import os
import sys

pipeline_dir = os.path.dirname(os.path.abspath(__file__))
if pipeline_dir not in sys.path:
    sys.path.insert(0, pipeline_dir)

import yaml
from shared.hdf5_io import read_metadata, read_actual
from shared.physics import (
    calculate_speed_over_ground,
    calculate_fuel_consumption_rate,
    calculate_ship_heading,
    load_ship_parameters,
)

# Load exp_b config
config_path = os.path.join(pipeline_dir, "config", "experiment_exp_b.yaml")
with open(config_path) as f:
    config = yaml.safe_load(f)

hdf5_path = os.path.join(pipeline_dir, "data", "experiment_b_138wp.h5")

# Read data
metadata = read_metadata(hdf5_path)
metadata = metadata.sort_values("node_id").reset_index(drop=True)
weather = read_actual(hdf5_path, sample_hour=0)
merged = metadata.merge(weather, on="node_id", how="left")
merged = merged.sort_values("node_id").reset_index(drop=True)

ship_params = load_ship_parameters(config)
num_nodes = len(merged)
num_legs = num_nodes - 1
total_dist = merged.iloc[-1]["distance_from_start_nm"]
min_speed, max_speed = config["ship"]["speed_range_knots"]
eta = config["ship"]["eta_hours"]

print(f"Route: {total_dist:.1f} nm, {num_nodes} nodes, {num_legs} legs")
print(f"ETA: {eta}h, SWS range: [{min_speed}, {max_speed}] kn")
print()


def _safe(val, default=0.0):
    if val is None:
        return default
    try:
        if math.isnan(val):
            return default
    except (TypeError, ValueError):
        pass
    return float(val)


# ── Precompute per-leg data ──
legs = []
for idx in range(num_legs):
    node_a = merged.iloc[idx]
    node_b = merged.iloc[idx + 1]

    dist = node_b["distance_from_start_nm"] - node_a["distance_from_start_nm"]
    if dist <= 0:
        dist = 0.001

    heading_deg = calculate_ship_heading(
        node_a["lat"], node_a["lon"], node_b["lat"], node_b["lon"]
    )

    legs.append({
        "dist": dist,
        "heading_rad": math.radians(heading_deg),
        "wind_dir_rad": math.radians(_safe(node_a.get("wind_direction_10m_deg"))),
        "beaufort": int(round(_safe(node_a.get("beaufort_number"), 3))),
        "wave_height": _safe(node_a.get("wave_height_m"), 1.0),
        "current_knots": _safe(node_a.get("ocean_current_velocity_kmh")) / 1.852,
        "current_dir_rad": math.radians(_safe(node_a.get("ocean_current_direction_deg"))),
    })


# ── Precompute SOG tables for each leg at fine SWS grid ──
SWS_STEP = 0.001
sws_grid = []
s = min_speed
while s <= max_speed + SWS_STEP / 2:
    sws_grid.append(round(s, 4))
    s += SWS_STEP

print(f"Precomputing SOG for {len(legs)} legs × {len(sws_grid)} SWS values...")

# For each leg: list of (sws, sog, fcr, time, fuel)
leg_tables = []
for leg in legs:
    table = []
    for sws in sws_grid:
        sog = calculate_speed_over_ground(
            ship_speed=sws,
            ocean_current=leg["current_knots"],
            current_direction=leg["current_dir_rad"],
            ship_heading=leg["heading_rad"],
            wind_direction=leg["wind_dir_rad"],
            beaufort_scale=leg["beaufort"],
            wave_height=leg["wave_height"],
            ship_parameters=ship_params,
        )
        sog = max(sog, 0.1)
        fcr = calculate_fuel_consumption_rate(sws)
        t = leg["dist"] / sog
        f = fcr * t
        table.append((sws, sog, fcr, t, f))
    leg_tables.append(table)

print("Done.\n")


# ── UPPER BOUND: SWS = max ──
print("=" * 60)
print(f"UPPER BOUND — SWS = {max_speed} kn (max engine speed)")
print("=" * 60)

fuel_ub = sum(table[-1][4] for table in leg_tables)  # last entry = max SWS
time_ub = sum(table[-1][3] for table in leg_tables)

print(f"  SWS = {max_speed} kn")
print(f"  Fuel = {fuel_ub:.2f} mt")
print(f"  Time = {time_ub:.2f}h (arrives {eta - time_ub:.1f}h early)")
print()


# ── LOWER BOUND: Lagrangian optimization ──
# Minimize sum fuel_i(SWS_i) subject to sum time_i(SWS_i) <= ETA
#
# Lagrangian: L = sum [fuel_i + lambda * time_i]
# For each leg, find SWS_i minimizing fuel_i + lambda * time_i
# Binary search on lambda until total_time = ETA

print("=" * 60)
print("LOWER BOUND — Lagrangian optimization (actual weather)")
print("=" * 60)


def solve_for_lambda(lam):
    """For a given lambda, find optimal SWS per leg and return totals."""
    total_fuel = 0.0
    total_time = 0.0
    chosen_sws = []

    for table in leg_tables:
        best_cost = float("inf")
        best_idx = 0
        for j, (sws, sog, fcr, t, f) in enumerate(table):
            cost = f + lam * t  # fuel + lambda * time
            if cost < best_cost:
                best_cost = cost
                best_idx = j

        sws, sog, fcr, t, f = table[best_idx]
        total_fuel += f
        total_time += t
        chosen_sws.append(sws)

    return total_fuel, total_time, chosen_sws


# Binary search on lambda
# lambda=0 → minimize fuel only → slowest speeds → longest time
# lambda=large → minimize time → fastest speeds → shortest time
print("  Searching for optimal lambda...")

lo_lam, hi_lam = 0.0, 10.0

# Check if ETA is feasible at all
_, min_time, _ = solve_for_lambda(hi_lam)
_, max_time, _ = solve_for_lambda(lo_lam)

if min_time > eta:
    print(f"  WARNING: ETA={eta}h is infeasible. Min time at max speed = {min_time:.2f}h")
    # Use fastest possible
    fuel_lb, time_lb, opt_sws = solve_for_lambda(hi_lam)
else:
    for iteration in range(100):
        mid_lam = (lo_lam + hi_lam) / 2
        _, t, _ = solve_for_lambda(mid_lam)

        if t > eta:
            lo_lam = mid_lam  # need to go faster (increase penalty)
        else:
            hi_lam = mid_lam  # can go slower (decrease penalty)

        if hi_lam - lo_lam < 1e-10:
            break

    best_lam = (lo_lam + hi_lam) / 2
    fuel_lb, time_lb, opt_sws = solve_for_lambda(best_lam)
    print(f"  Lambda = {best_lam:.6f}")

print(f"  Fuel = {fuel_lb:.2f} mt")
print(f"  Time = {time_lb:.2f}h (target: {eta}h)")
print(f"  SWS range: [{min(opt_sws):.4f}, {max(opt_sws):.4f}] kn")
print(f"  SWS mean:  {sum(opt_sws)/len(opt_sws):.4f} kn")
print()


# ── SUMMARY ──
print("=" * 60)
print("SUMMARY")
print("=" * 60)
span = fuel_ub - fuel_lb
print(f"  Upper bound: {fuel_ub:.2f} mt  (SWS={max_speed} kn, arrives {eta - time_ub:.1f}h early)")
print(f"  Lower bound: {fuel_lb:.2f} mt  (optimal per-node SWS, actual weather)")
print(f"  Span:        {span:.2f} mt")
print()

# Where do the 3 approaches fall?
if span > 0:
    print("  Optimization results (from exp_b):")
    for label, fuel in [("B-LP", 180.6), ("B-RH", 180.9), ("B-DP", 182.2)]:
        captured = (fuel_ub - fuel) / span * 100
        print(f"    {label} = {fuel} mt→  {captured:.1f}% of span captured")

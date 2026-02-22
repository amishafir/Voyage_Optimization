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
    """Compute the theoretical lower bound: constant speed in calm water.

    Lower bound = FCR(V_const) * ETA, where V_const = total_distance / ETA.

    By Jensen's inequality on the convex cubic FCR, any speed variation
    increases fuel above this floor.  Weather effects only raise fuel
    further (SWS must deviate from SOG to compensate).

    Also simulates the constant-SOG voyage under actual weather to show
    the gap between the analytical floor and real-world constant speed.

    Returns:
        Result dict (also saved as result_lower_bound.json).
    """
    from shared.hdf5_io import read_metadata
    from shared.physics import calculate_fuel_consumption_rate

    metadata = read_metadata(hdf5_path)
    metadata = metadata.sort_values("node_id").reset_index(drop=True)
    num_nodes = len(metadata)
    num_legs = num_nodes - 1

    total_dist = metadata.iloc[-1]["distance_from_start_nm"]
    eta = config["ship"]["eta_hours"]
    constant_sog = total_dist / eta

    # --- Analytical lower bound (calm water) ---
    fcr_calm = calculate_fuel_consumption_rate(constant_sog)
    analytical_fuel = fcr_calm * eta

    print(f"  Analytical lower bound (calm water):")
    print(f"    Constant SOG = {constant_sog:.4f} kn")
    print(f"    FCR           = {fcr_calm:.6f} kg/h")
    print(f"    Fuel           = {analytical_fuel:.2f} kg")

    # --- Simulated constant-SOG voyage under actual weather ---
    schedule = []
    for i in range(num_legs):
        node_a = metadata.iloc[i]
        node_b = metadata.iloc[i + 1]
        dist = node_b["distance_from_start_nm"] - node_a["distance_from_start_nm"]
        schedule.append({
            "leg": i,
            "node_id": int(node_a["node_id"]),
            "segment": int(node_a["segment"]),
            "sog_knots": constant_sog,
            "sws_knots": constant_sog,  # reference only — simulation computes actual SWS
            "distance_nm": max(dist, 0.001),
        })

    print("--- Lower Bound: Simulate (constant SOG under actual weather) ---")
    simulated = simulate_voyage(schedule, hdf5_path, config, sample_hour=0)

    planned_stub = {
        "planned_fuel_kg": analytical_fuel,
        "planned_time_h": eta,
        "speed_schedule": schedule,
        "computation_time_s": 0.0,
        "status": "Analytical",
    }
    metrics = compute_result_metrics(planned_stub, simulated, total_dist)

    ts_path = os.path.join(output_dir, "timeseries_lower_bound.csv")
    simulated["time_series"].to_csv(ts_path, index=False)

    result = build_result_json(
        approach="lower_bound",
        config=config,
        planned=planned_stub,
        simulated=simulated,
        metrics=metrics,
        time_series_file=ts_path,
    )
    result["analytical_fuel_kg"] = round(analytical_fuel, 4)
    result["constant_sog_knots"] = round(constant_sog, 4)
    json_path = os.path.join(output_dir, "result_lower_bound.json")
    save_result(result, json_path)

    print(f"  Lower bound (analytical): {analytical_fuel:.2f} kg fuel (calm water)")
    print(f"  Lower bound (simulated):  {simulated['total_fuel_kg']:.2f} kg fuel (actual weather)")
    return result


def run_upper_bound(config, hdf5_path, output_dir):
    """Simulate a constant-SOG voyage at max speed (no optimization).

    Uses max_speed as target SOG for all legs.  The ship adjusts SWS to
    maintain this SOG under actual weather.  This represents the theoretical
    ceiling — maximum fuel consumption at constant maximum speed.

    Returns:
        Result dict (also saved as result_upper_bound.json).
    """
    from shared.hdf5_io import read_metadata
    from shared.physics import calculate_fuel_consumption_rate

    metadata = read_metadata(hdf5_path)
    metadata = metadata.sort_values("node_id").reset_index(drop=True)
    num_nodes = len(metadata)
    num_legs = num_nodes - 1

    min_speed, max_speed = config["ship"]["speed_range_knots"]
    total_dist = metadata.iloc[-1]["distance_from_start_nm"]

    # Analytical upper bound: FCR(max_speed) * (total_dist / max_speed)
    fcr_max = calculate_fuel_consumption_rate(max_speed)
    analytical_time = total_dist / max_speed
    analytical_fuel = fcr_max * analytical_time

    # Build constant-SOG schedule at max speed
    schedule = []
    for i in range(num_legs):
        node_a = metadata.iloc[i]
        node_b = metadata.iloc[i + 1]
        dist = node_b["distance_from_start_nm"] - node_a["distance_from_start_nm"]
        schedule.append({
            "leg": i,
            "node_id": int(node_a["node_id"]),
            "segment": int(node_a["segment"]),
            "sog_knots": max_speed,
            "sws_knots": max_speed,
            "distance_nm": max(dist, 0.001),
        })

    print("--- Upper Bound: Simulate (constant SOG = max speed) ---")
    simulated = simulate_voyage(schedule, hdf5_path, config, sample_hour=0)

    planned_stub = {
        "planned_fuel_kg": analytical_fuel,
        "planned_time_h": analytical_time,
        "speed_schedule": schedule,
        "computation_time_s": 0.0,
        "status": "Analytical",
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
    result["analytical_fuel_kg"] = round(analytical_fuel, 4)
    result["constant_sog_knots"] = max_speed
    json_path = os.path.join(output_dir, "result_upper_bound.json")
    save_result(result, json_path)

    print(f"  Upper bound (analytical): {analytical_fuel:.2f} kg fuel (calm water, SOG={max_speed} kn)")
    print(f"  Upper bound (simulated):  {simulated['total_fuel_kg']:.2f} kg fuel (actual weather)")
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


def run_horizon_sweep(config, hdf5_path, output_dir, horizons=None):
    """Run dynamic_det and dynamic_rh at multiple forecast horizons.

    Truncates forecast data to simulate having shorter-range forecasts
    (e.g. 3-day or 5-day instead of 7-day).

    Args:
        horizons: List of forecast horizon caps in hours.
            Default: [72, 120, 168] (3, 5, 7 days)

    Returns:
        List of result dicts.
    """
    from dynamic_det.transform import transform as dd_transform
    from dynamic_det.optimize import optimize as dd_optimize
    from dynamic_rh.transform import transform as rh_transform
    from dynamic_rh.optimize import optimize as rh_optimize

    if horizons is None:
        horizons = [72, 120, 168]

    # Relax ETA slightly — the nominal ETA is tight (DP barely fits at 280h
    # with full forecast). Shorter horizons lose favorable weather windows,
    # causing infeasibility. A small buffer ensures all horizons are comparable.
    nominal_eta = config["ship"]["eta_hours"]
    relaxed_eta = int(nominal_eta * 1.02)

    results = []
    for horizon in horizons:
        days = horizon / 24

        # --- Dynamic Det at this horizon ---
        cfg = copy.deepcopy(config)
        cfg["dynamic_det"]["max_forecast_horizon"] = horizon
        cfg["ship"]["eta_hours"] = relaxed_eta
        approach_name = f"dynamic_det_horizon_{horizon}h"

        print(f"\n--- Horizon Sweep: {horizon}h ({days:.0f}d) — Dynamic Det ---")

        print(f"  Transform...")
        t_out = dd_transform(hdf5_path, cfg)

        print(f"  Optimize (DP, horizon={horizon}h)...")
        planned = dd_optimize(t_out, cfg)
        if planned.get("status") not in ("Optimal", "Feasible"):
            logger.warning("Horizon sweep %dh dynamic_det: status=%s",
                           horizon, planned.get("status"))
        else:
            print(f"  Simulate...")
            simulated = simulate_voyage(
                planned["speed_schedule"], hdf5_path, cfg,
                sample_hour=cfg["dynamic_det"]["forecast_origin"],
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
            json_path = os.path.join(output_dir, f"result_{approach_name}.json")
            save_result(result, json_path)

            print(f"  {approach_name}: {simulated['total_fuel_kg']:.2f} kg fuel")
            results.append(result)

        # --- Rolling Horizon at this horizon ---
        cfg_rh = copy.deepcopy(config)
        cfg_rh["dynamic_det"]["max_forecast_horizon"] = horizon
        cfg_rh["ship"]["eta_hours"] = relaxed_eta
        approach_name_rh = f"dynamic_rh_horizon_{horizon}h"

        print(f"\n--- Horizon Sweep: {horizon}h ({days:.0f}d) — Rolling Horizon ---")

        print(f"  Transform...")
        t_out_rh = rh_transform(hdf5_path, cfg_rh)

        print(f"  Optimize (RH, horizon={horizon}h)...")
        planned_rh = rh_optimize(t_out_rh, cfg_rh)
        if planned_rh.get("status") not in ("Optimal", "Feasible"):
            logger.warning("Horizon sweep %dh dynamic_rh: status=%s",
                           horizon, planned_rh.get("status"))
            continue

        print(f"  Simulate...")
        simulated_rh = simulate_voyage(
            planned_rh["speed_schedule"], hdf5_path, cfg_rh,
            sample_hour=0,
        )

        total_dist_rh = sum(t_out_rh["distances"])
        metrics_rh = compute_result_metrics(planned_rh, simulated_rh, total_dist_rh)

        ts_path_rh = os.path.join(output_dir, f"timeseries_{approach_name_rh}.csv")
        simulated_rh["time_series"].to_csv(ts_path_rh, index=False)

        result_rh = build_result_json(
            approach=approach_name_rh,
            config=cfg_rh,
            planned=planned_rh,
            simulated=simulated_rh,
            metrics=metrics_rh,
            time_series_file=ts_path_rh,
        )
        result_rh["decision_points"] = planned_rh.get("decision_points", [])
        json_path_rh = os.path.join(output_dir, f"result_{approach_name_rh}.json")
        save_result(result_rh, json_path_rh)

        print(f"  {approach_name_rh}: {simulated_rh['total_fuel_kg']:.2f} kg fuel")
        results.append(result_rh)

    return results


def run_lp_predicted(config, hdf5_path, output_dir):
    """Run the LP optimizer using predicted weather instead of actual.

    This isolates whether the LP's disadvantage comes from segment-averaging
    or from using actual (vs predicted) weather.  The LP plans on
    predicted weather at forecast_origin=0, forecast_hour=0, then is
    simulated under actual weather (same as all other approaches).

    Returns:
        Result dict (also saved as result_static_det_predicted.json).
    """
    from static_det.transform import transform
    from static_det.optimize import optimize

    cfg = copy.deepcopy(config)
    cfg["static_det"]["weather_source"] = "predicted"
    cfg["static_det"]["forecast_origin"] = 0
    approach_name = "static_det_predicted"

    print(f"\n--- LP with Predicted Weather ---")

    print(f"  Transform (predicted weather)...")
    t_out = transform(hdf5_path, cfg)

    print(f"  Optimize (LP)...")
    planned = optimize(t_out, cfg)
    if planned.get("status") != "Optimal":
        logger.warning("LP predicted: status=%s", planned.get("status"))
        return None

    print(f"  Simulate (actual weather)...")
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
    json_path = os.path.join(output_dir, f"result_{approach_name}.json")
    save_result(result, json_path)

    print(f"  {approach_name}: plan={planned['planned_fuel_kg']:.2f} kg, "
          f"sim={simulated['total_fuel_kg']:.2f} kg, "
          f"gap={metrics['fuel_gap_percent']:.2f}%, "
          f"SWS violations={simulated.get('sws_violations', 0)}")
    return result


def run_2x2_decomposition(config_a, config_b, hdf5_a, hdf5_b, output_dir):
    """Run 2x2 spatial x temporal decomposition.

    Four configurations:
        A-LP: exp_a (7 nodes), LP (6 segments) — baseline
        A-DP: exp_a (7 nodes), DP (7 nodes)   — temporal effect only
        B-LP: exp_b (~138 nodes), LP (6 segments) — spatial averaging effect
        B-DP: exp_b (~138 nodes), DP (~138 nodes) — full spatial + temporal

    Also runs RH on exp_b for the complete picture.

    Decomposition:
        temporal_effect  = A_DP_fuel - A_LP_fuel  (same 7 nodes)
        spatial_effect   = B_LP_fuel - A_LP_fuel  (both static, different resolution)
        interaction      = B_DP_fuel - A_LP_fuel - temporal - spatial

    Returns:
        Dict with all results and decomposition values.
    """
    from static_det.transform import transform as lp_transform
    from static_det.optimize import optimize as lp_optimize
    from dynamic_det.transform import transform as dd_transform
    from dynamic_det.optimize import optimize as dd_optimize
    from dynamic_rh.transform import transform as rh_transform
    from dynamic_rh.optimize import optimize as rh_optimize

    os.makedirs(output_dir, exist_ok=True)
    results = {}

    configs = {
        "A_LP": (config_a, hdf5_a, "static_det",  lp_transform, lp_optimize),
        "A_DP": (config_a, hdf5_a, "dynamic_det",  dd_transform, dd_optimize),
        "B_LP": (config_b, hdf5_b, "static_det",  lp_transform, lp_optimize),
        "B_DP": (config_b, hdf5_b, "dynamic_det",  dd_transform, dd_optimize),
        "B_RH": (config_b, hdf5_b, "dynamic_rh",  rh_transform, rh_optimize),
    }

    for label, (cfg, hdf5, approach, transform_fn, optimize_fn) in configs.items():
        print(f"\n--- 2x2 Decomposition: {label} ({approach}) ---")

        print(f"  Transform...")
        t_out = transform_fn(hdf5, cfg)

        print(f"  Optimize...")
        planned = optimize_fn(t_out, cfg)
        status = planned.get("status", "unknown")
        if status not in ("Optimal", "Feasible"):
            logger.warning("2x2 %s: status=%s", label, status)
            print(f"  WARNING: {label} status={status}, skipping")
            continue

        print(f"  Simulate...")
        simulated = simulate_voyage(
            planned["speed_schedule"], hdf5, cfg,
            sample_hour=0,
        )

        total_dist = sum(t_out["distances"])
        metrics = compute_result_metrics(planned, simulated, total_dist)

        approach_name = f"decomp_{label}"
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
        json_path = os.path.join(output_dir, f"result_{approach_name}.json")
        save_result(result, json_path)

        fuel = simulated["total_fuel_kg"]
        time_h = simulated["total_time_h"]
        violations = simulated.get("sws_violations", 0)
        print(f"  {label}: {fuel:.2f} kg fuel, {time_h:.2f} h, {violations} SWS violations")
        results[label] = result

    # Compute decomposition if all 4 core configs succeeded
    decomp = {}
    if all(k in results for k in ("A_LP", "A_DP", "B_LP", "B_DP")):
        a_lp = results["A_LP"]["simulated"]["total_fuel_kg"]
        a_dp = results["A_DP"]["simulated"]["total_fuel_kg"]
        b_lp = results["B_LP"]["simulated"]["total_fuel_kg"]
        b_dp = results["B_DP"]["simulated"]["total_fuel_kg"]

        temporal = a_dp - a_lp
        spatial = b_lp - a_lp
        interaction = b_dp - a_lp - temporal - spatial

        decomp = {
            "A_LP_fuel": round(a_lp, 4),
            "A_DP_fuel": round(a_dp, 4),
            "B_LP_fuel": round(b_lp, 4),
            "B_DP_fuel": round(b_dp, 4),
            "temporal_effect_kg": round(temporal, 4),
            "spatial_effect_kg": round(spatial, 4),
            "interaction_kg": round(interaction, 4),
        }

        if "B_RH" in results:
            b_rh = results["B_RH"]["simulated"]["total_fuel_kg"]
            decomp["B_RH_fuel"] = round(b_rh, 4)
            decomp["rh_additional_kg"] = round(b_rh - b_dp, 4)

        print("\n" + "=" * 60)
        print("2x2 DECOMPOSITION RESULTS")
        print("=" * 60)
        print(f"{'Config':<10} {'Fuel (kg)':>12} {'vs A-LP':>10}")
        print("-" * 35)
        print(f"{'A-LP':<10} {a_lp:>12.2f} {'baseline':>10}")
        print(f"{'A-DP':<10} {a_dp:>12.2f} {temporal:>+10.2f}")
        print(f"{'B-LP':<10} {b_lp:>12.2f} {spatial:>+10.2f}")
        print(f"{'B-DP':<10} {b_dp:>12.2f} {b_dp - a_lp:>+10.2f}")
        if "B_RH" in results:
            print(f"{'B-RH':<10} {b_rh:>12.2f} {b_rh - a_lp:>+10.2f}")
        print("-" * 35)
        print(f"Temporal effect (A-DP - A-LP):  {temporal:+.2f} kg")
        print(f"Spatial effect  (B-LP - A-LP):  {spatial:+.2f} kg")
        print(f"Interaction:                    {interaction:+.2f} kg")
        print("=" * 60)

        # Save decomposition
        decomp_path = os.path.join(output_dir, "decomposition_2x2.json")
        with open(decomp_path, "w") as f:
            json.dump(decomp, f, indent=2)
        print(f"Saved: {decomp_path}")

    return {"results": results, "decomposition": decomp}


def run_short_route_horizon_sweep(config, hdf5_path, output_dir, horizons=None):
    """Run horizon sweep on the shorter route (exp_b, ~140h voyage).

    Since the route is ~140h, the horizon sweep becomes more interesting:
        72h  = 51% of voyage
        120h = 86% of voyage
        144h = 103% (full coverage!)

    This tests the Section 4.5 hypothesis: does the plateau shift when
    forecast_horizon / voyage_duration changes?

    Args:
        config: Experiment config for the short route.
        hdf5_path: Path to exp_b HDF5.
        output_dir: Output directory.
        horizons: List of forecast horizons in hours.
            Default: [24, 48, 72, 96, 120, 144]

    Returns:
        List of result dicts.
    """
    from dynamic_det.transform import transform as dd_transform
    from dynamic_det.optimize import optimize as dd_optimize
    from dynamic_rh.transform import transform as rh_transform
    from dynamic_rh.optimize import optimize as rh_optimize

    if horizons is None:
        horizons = [24, 48, 72, 96, 120, 144]

    os.makedirs(output_dir, exist_ok=True)

    eta = config["ship"]["eta_hours"]
    relaxed_eta = int(eta * 1.02)

    results = []

    print("=" * 60)
    print(f"SHORT-ROUTE HORIZON SWEEP (ETA={eta}h, relaxed={relaxed_eta}h)")
    print("=" * 60)

    for horizon in horizons:
        ratio = horizon / eta * 100

        # --- Dynamic Det ---
        cfg = copy.deepcopy(config)
        cfg["dynamic_det"]["max_forecast_horizon"] = horizon
        cfg["ship"]["eta_hours"] = relaxed_eta
        approach_name = f"short_dd_horizon_{horizon}h"

        print(f"\n--- Horizon {horizon}h ({ratio:.0f}% of voyage) — Dynamic Det ---")

        print(f"  Transform...")
        t_out = dd_transform(hdf5_path, cfg)

        print(f"  Optimize (DP, horizon={horizon}h)...")
        planned = dd_optimize(t_out, cfg)
        if planned.get("status") not in ("Optimal", "Feasible"):
            logger.warning("Short route horizon %dh DP: status=%s",
                           horizon, planned.get("status"))
            print(f"  WARNING: DP status={planned.get('status')}")
        else:
            print(f"  Simulate...")
            simulated = simulate_voyage(
                planned["speed_schedule"], hdf5_path, cfg,
                sample_hour=cfg["dynamic_det"]["forecast_origin"],
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
            result["horizon_ratio_pct"] = round(ratio, 1)
            json_path = os.path.join(output_dir, f"result_{approach_name}.json")
            save_result(result, json_path)

            print(f"  {approach_name}: {simulated['total_fuel_kg']:.2f} kg, "
                  f"ratio={ratio:.0f}%")
            results.append(result)

        # --- Rolling Horizon ---
        cfg_rh = copy.deepcopy(config)
        cfg_rh["dynamic_det"]["max_forecast_horizon"] = horizon
        cfg_rh["ship"]["eta_hours"] = relaxed_eta
        approach_name_rh = f"short_rh_horizon_{horizon}h"

        print(f"\n--- Horizon {horizon}h ({ratio:.0f}% of voyage) — Rolling Horizon ---")

        print(f"  Transform...")
        t_out_rh = rh_transform(hdf5_path, cfg_rh)

        print(f"  Optimize (RH, horizon={horizon}h)...")
        planned_rh = rh_optimize(t_out_rh, cfg_rh)
        if planned_rh.get("status") not in ("Optimal", "Feasible"):
            logger.warning("Short route horizon %dh RH: status=%s",
                           horizon, planned_rh.get("status"))
            print(f"  WARNING: RH status={planned_rh.get('status')}")
            continue

        print(f"  Simulate...")
        simulated_rh = simulate_voyage(
            planned_rh["speed_schedule"], hdf5_path, cfg_rh,
            sample_hour=0,
        )

        total_dist_rh = sum(t_out_rh["distances"])
        metrics_rh = compute_result_metrics(planned_rh, simulated_rh, total_dist_rh)

        ts_path_rh = os.path.join(output_dir, f"timeseries_{approach_name_rh}.csv")
        simulated_rh["time_series"].to_csv(ts_path_rh, index=False)

        result_rh = build_result_json(
            approach=approach_name_rh,
            config=cfg_rh,
            planned=planned_rh,
            simulated=simulated_rh,
            metrics=metrics_rh,
            time_series_file=ts_path_rh,
        )
        result_rh["decision_points"] = planned_rh.get("decision_points", [])
        result_rh["horizon_ratio_pct"] = round(ratio, 1)
        json_path_rh = os.path.join(output_dir, f"result_{approach_name_rh}.json")
        save_result(result_rh, json_path_rh)

        print(f"  {approach_name_rh}: {simulated_rh['total_fuel_kg']:.2f} kg, "
              f"ratio={ratio:.0f}%")
        results.append(result_rh)

    # Summary table
    print("\n" + "=" * 60)
    print("SHORT-ROUTE HORIZON SWEEP SUMMARY")
    print("=" * 60)
    print(f"{'Approach':<30} {'Horizon':>8} {'Ratio':>7} {'Sim Fuel':>10} {'Time':>8}")
    print("-" * 68)

    for r in results:
        name = r["approach"]
        fuel = r["simulated"]["total_fuel_kg"]
        time_h = r["simulated"]["voyage_time_h"]
        ratio = r.get("horizon_ratio_pct", 0)
        h = name.split("_")[-1]  # e.g. "144h"
        print(f"{name:<30} {h:>8} {ratio:>6.0f}% {fuel:>10.2f} {time_h:>8.2f}")

    print("=" * 68)
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
    print("\n[1/4] Lower bound (perfect information)...")
    lb = run_lower_bound(config, hdf5_path, output_dir)

    # 2. Upper bound
    print("\n[2/4] Upper bound (constant speed)...")
    ub = run_upper_bound(config, hdf5_path, output_dir)

    # 3. Replan sweep
    print("\n[3/4] Replan frequency sweep...")
    sweep = run_replan_sweep(config, hdf5_path, output_dir)

    # 4. Forecast horizon sweep
    print("\n[4/4] Forecast horizon sweep...")
    horizon = run_horizon_sweep(config, hdf5_path, output_dir)

    # Summary table
    print("\n" + "=" * 60)
    print("SENSITIVITY SUMMARY")
    print("=" * 60)
    print(f"{'Approach':<35}  {'Sim Fuel (kg)':>14}  {'Sim Time (h)':>13}")
    print("-" * 65)

    all_results = []
    if lb:
        all_results.append(lb)
    if ub:
        all_results.append(ub)
    all_results.extend(sweep)
    all_results.extend(horizon)

    for r in all_results:
        name = r["approach"]
        fuel = r["simulated"]["total_fuel_kg"]
        time_h = r["simulated"]["voyage_time_h"]
        print(f"{name:<35}  {fuel:>14.2f}  {time_h:>13.2f}")

    print("=" * 65)
    return output_dir

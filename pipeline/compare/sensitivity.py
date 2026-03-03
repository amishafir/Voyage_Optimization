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
    print(f"    FCR           = {fcr_calm:.6f} mt/h")
    print(f"    Fuel           = {analytical_fuel:.2f} mt")

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
        "planned_fuel_mt": analytical_fuel,
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
    result["analytical_fuel_mt"] = round(analytical_fuel, 4)
    result["constant_sog_knots"] = round(constant_sog, 4)
    json_path = os.path.join(output_dir, "result_lower_bound.json")
    save_result(result, json_path)

    print(f"  Lower bound (analytical): {analytical_fuel:.2f} mt fuel (calm water)")
    print(f"  Lower bound (simulated):  {simulated['total_fuel_mt']:.2f} mt fuel (actual weather)")
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
        "planned_fuel_mt": analytical_fuel,
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
    result["analytical_fuel_mt"] = round(analytical_fuel, 4)
    result["constant_sog_knots"] = max_speed
    json_path = os.path.join(output_dir, "result_upper_bound.json")
    save_result(result, json_path)

    print(f"  Upper bound (analytical): {analytical_fuel:.2f} mt fuel (calm water, SOG={max_speed} kn)")
    print(f"  Upper bound (simulated):  {simulated['total_fuel_mt']:.2f} mt fuel (actual weather)")
    return result


def run_constant_speed_bound(config, hdf5_path, output_dir):
    """Simulate a naive captain: constant speed that meets ETA, recalculated per leg.

    At each leg, the captain computes:
        target_sog = remaining_distance / remaining_time
    then sets SWS to achieve that SOG under actual weather, clamped to
    [min_speed, max_speed].  Zero SWS violations by design.

    This is tighter than the max-speed upper bound because the captain
    targets the ETA rather than going full speed.

    Returns:
        Result dict (also saved as result_constant_speed_bound.json).
    """
    import math
    import pandas as pd
    from shared.hdf5_io import read_metadata, read_actual
    from shared.physics import (
        calculate_ship_heading,
        calculate_sws_from_sog,
        calculate_speed_over_ground,
        calculate_fuel_consumption_rate,
        calculate_co2_emissions,
        load_ship_parameters,
    )

    ship_params = load_ship_parameters(config)
    eta = config["ship"]["eta_hours"]
    min_speed, max_speed = config["ship"]["speed_range_knots"]

    metadata = read_metadata(hdf5_path)
    metadata = metadata.sort_values("node_id").reset_index(drop=True)

    weather = read_actual(hdf5_path, sample_hour=0)
    merged = metadata.merge(weather, on="node_id", how="left")
    merged = merged.sort_values("node_id").reset_index(drop=True)

    num_nodes = len(merged)
    total_dist = merged.iloc[-1]["distance_from_start_nm"]
    initial_sog = total_dist / eta

    weather_fields = [
        "wind_speed_10m_kmh", "wind_direction_10m_deg", "beaufort_number",
        "wave_height_m", "ocean_current_velocity_kmh", "ocean_current_direction_deg",
    ]

    print(f"  Initial constant SOG = {initial_sog:.4f} kn (total_dist={total_dist:.1f} nm, ETA={eta} h)")

    rows = []
    cum_distance = 0.0
    cum_time = 0.0
    cum_fuel = 0.0
    sws_violations = 0

    for idx in range(num_nodes - 1):
        node_a = merged.iloc[idx]
        node_b = merged.iloc[idx + 1]

        dist = node_b["distance_from_start_nm"] - node_a["distance_from_start_nm"]
        if dist <= 0:
            continue

        # Recalculate target SOG based on remaining voyage
        remaining_dist = total_dist - cum_distance
        remaining_time = eta - cum_time
        if remaining_time <= 0:
            target_sog = max_speed
        else:
            target_sog = remaining_dist / remaining_time

        # Heading from node_a to node_b
        heading_deg = calculate_ship_heading(
            node_a["lat"], node_a["lon"], node_b["lat"], node_b["lon"]
        )

        # Weather at node_a
        wx = {}
        for field in weather_fields:
            val = node_a.get(field)
            if val is None or (isinstance(val, float) and math.isnan(val)):
                wx[field] = 0.0
            else:
                wx[field] = float(val)

        # Inverse: SWS needed to achieve target SOG under weather
        required_sws = calculate_sws_from_sog(
            target_sog=target_sog,
            weather=wx,
            ship_heading_deg=heading_deg,
            ship_parameters=ship_params,
        )

        # Clamp SWS — guarantees zero violations
        clamped_sws = max(min_speed, min(max_speed, required_sws))
        if abs(clamped_sws - required_sws) > 0.01:
            sws_violations += 1

        # Forward: actual SOG with clamped SWS
        if abs(clamped_sws - required_sws) > 0.01:
            heading_rad = math.radians(heading_deg)
            wind_dir_rad = math.radians(wx["wind_direction_10m_deg"])
            current_knots = wx["ocean_current_velocity_kmh"] / 1.852
            current_dir_rad = math.radians(wx["ocean_current_direction_deg"])
            beaufort = int(round(wx["beaufort_number"]))
            wave_height = wx["wave_height_m"]

            actual_sog = calculate_speed_over_ground(
                ship_speed=clamped_sws,
                ocean_current=current_knots,
                current_direction=current_dir_rad,
                ship_heading=heading_rad,
                wind_direction=wind_dir_rad,
                beaufort_scale=beaufort,
                wave_height=wave_height,
                ship_parameters=ship_params,
            )
            actual_sog = max(actual_sog, 0.1)
        else:
            actual_sog = target_sog

        fcr = calculate_fuel_consumption_rate(clamped_sws)
        leg_time = dist / actual_sog
        leg_fuel = fcr * leg_time

        cum_distance += dist
        cum_time += leg_time
        cum_fuel += leg_fuel

        rows.append({
            "node_id": int(node_a["node_id"]),
            "segment": int(node_a["segment"]),
            "lat": float(node_a["lat"]),
            "lon": float(node_a["lon"]),
            "target_sog_knots": target_sog,
            "actual_sog_knots": actual_sog,
            "required_sws_knots": required_sws,
            "clamped_sws_knots": clamped_sws,
            "distance_nm": dist,
            "time_h": leg_time,
            "fuel_mt": leg_fuel,
            "cum_distance_nm": cum_distance,
            "cum_time_h": cum_time,
            "cum_fuel_mt": cum_fuel,
            "beaufort": int(round(wx["beaufort_number"])),
            "wave_height_m": wx["wave_height_m"],
            "current_knots": wx["ocean_current_velocity_kmh"] / 1.852,
            "heading_deg": heading_deg,
        })

    time_series = pd.DataFrame(rows)
    co2 = calculate_co2_emissions(cum_fuel)

    # Build result using standard helpers
    simulated = {
        "total_fuel_mt": cum_fuel,
        "total_time_h": cum_time,
        "arrival_deviation_h": cum_time - eta,
        "speed_changes": 0,
        "sws_violations": sws_violations,
        "co2_emissions_mt": co2,
        "time_series": time_series,
    }

    planned_stub = {
        "planned_fuel_mt": cum_fuel,  # no separate planning phase
        "planned_time_h": eta,
        "speed_schedule": [],
        "computation_time_s": 0.0,
        "status": "Analytical",
    }
    metrics = compute_result_metrics(planned_stub, simulated, total_dist)

    ts_path = os.path.join(output_dir, "timeseries_constant_speed_bound.csv")
    time_series.to_csv(ts_path, index=False)

    result = build_result_json(
        approach="constant_speed_bound",
        config=config,
        planned=planned_stub,
        simulated=simulated,
        metrics=metrics,
        time_series_file=ts_path,
    )
    result["initial_sog_knots"] = round(initial_sog, 4)
    json_path = os.path.join(output_dir, "result_constant_speed_bound.json")
    save_result(result, json_path)

    print(f"  Constant-speed bound: {cum_fuel:.2f} mt fuel, {cum_time:.2f} h")
    print(f"    Arrival deviation: {cum_time - eta:+.2f} h, SWS violations: {sws_violations}")
    return result


def _feasible_sog_bounds(hdf5_path, seg_idx, sample_hours_range,
                         ship_params, heading_rad):
    """Find the feasible SOG band for a segment across all waypoints and hours.

    Ceiling: min SOG at SWS=max_speed across all (waypoint, hour) pairs.
             Any committed SOG above this causes max-speed violations.
    Floor:   max SOG at SWS=min_speed across all (waypoint, hour) pairs.
             Any committed SOG below this causes min-speed violations.

    Returns:
        (sog_floor, sog_ceiling)
    """
    import math
    from shared.hdf5_io import read_metadata, read_actual
    from shared.physics import calculate_speed_over_ground

    metadata = read_metadata(hdf5_path)
    max_sws = ship_params["max_speed"]
    min_sws = ship_params["min_speed"]
    sog_ceiling = float("inf")
    sog_floor = 0.0

    for sh in sample_hours_range:
        wx = read_actual(hdf5_path, sample_hour=sh)
        merged = metadata[["node_id", "segment"]].merge(wx, on="node_id", how="left")
        seg_nodes = merged[merged["segment"] == seg_idx]

        for _, node in seg_nodes.iterrows():
            wind_dir = node.get("wind_direction_10m_deg", 0.0)
            current_vel = node.get("ocean_current_velocity_kmh", 0.0)
            current_dir = node.get("ocean_current_direction_deg", 0.0)
            beaufort = node.get("beaufort_number", 0)
            wave_h = node.get("wave_height_m", 0.0)

            if math.isnan(wind_dir): wind_dir = 0.0
            if math.isnan(current_vel): current_vel = 0.0
            if math.isnan(current_dir): current_dir = 0.0
            if math.isnan(beaufort) or beaufort < 0: beaufort = 0
            if math.isnan(wave_h): wave_h = 0.0

            sog_at_max = calculate_speed_over_ground(
                ship_speed=max_sws,
                ocean_current=current_vel / 1.852,
                current_direction=math.radians(current_dir),
                ship_heading=heading_rad,
                wind_direction=math.radians(wind_dir),
                beaufort_scale=int(round(beaufort)),
                wave_height=wave_h,
                ship_parameters=ship_params,
            )
            sog_at_min = calculate_speed_over_ground(
                ship_speed=min_sws,
                ocean_current=current_vel / 1.852,
                current_direction=math.radians(current_dir),
                ship_heading=heading_rad,
                wind_direction=math.radians(wind_dir),
                beaufort_scale=int(round(beaufort)),
                wave_height=wave_h,
                ship_parameters=ship_params,
            )

            if sog_at_max < sog_ceiling:
                sog_ceiling = sog_at_max
            if sog_at_min > sog_floor:
                sog_floor = sog_at_min

    return sog_floor, sog_ceiling


def run_rolling_lp(config, hdf5_path, output_dir):
    """Rolling LP: re-solve the LP at each segment boundary with fresh weather.

    At each segment, re-run transform with the actual weather closest to the
    current cumulative transit time, slice to remaining segments, adjust ETA,
    and solve.  Commit only the first segment's speed from each re-solve.

    Post-solve clamp: after the LP picks a speed, caps the committed SOG
    at the worst-case feasibility ceiling (min SOG at max SWS across all
    waypoints and transit hours) to eliminate SWS violations.

    Returns:
        Result dict (also saved as result_rolling_lp.json).
    """
    from static_det.transform import transform
    from static_det.optimize import optimize
    from shared.hdf5_io import get_completed_runs
    from shared.physics import load_ship_parameters

    available_hours = get_completed_runs(hdf5_path)
    if not available_hours:
        logger.warning("Rolling LP: no sample hours in HDF5")
        return None

    eta = config["ship"]["eta_hours"]
    sd_cfg = config["static_det"]
    num_segments = sd_cfg["segments"]
    ship_params = load_ship_parameters(config)

    committed = []  # one entry per segment: {segment, sws_knots, sog_knots, ...}
    cum_time = 0.0
    hours_used = []

    print(f"  Rolling LP: {num_segments} segments, ETA={eta} h, "
          f"available sample hours: {available_hours}")

    for seg_idx in range(num_segments):
        # Pick closest sample_hour <= cum_time (or smallest available)
        candidates = [h for h in available_hours if h <= cum_time]
        sample_hour = max(candidates) if candidates else available_hours[0]
        hours_used.append(sample_hour)

        # Deep-copy config and override weather snapshot
        cfg = copy.deepcopy(config)
        cfg["static_det"]["weather_snapshot"] = sample_hour

        # Transform with fresh weather
        t_out = transform(hdf5_path, cfg)

        # Slice to remaining segments [seg_idx : num_segments]
        remaining_eta = eta - cum_time
        remaining_segments = num_segments - seg_idx
        t_sub = {
            "ETA": remaining_eta,
            "num_segments": remaining_segments,
            "num_speeds": t_out["num_speeds"],
            "distances": t_out["distances"][seg_idx:],
            "speeds": t_out["speeds"],
            "fcr": t_out["fcr"],
            "sog_matrix": t_out["sog_matrix"][seg_idx:],
            "sog_lower": t_out["sog_lower"][seg_idx:],
            "sog_upper": t_out["sog_upper"][seg_idx:],
        }

        # Solve LP for remaining segments
        planned = optimize(t_sub, cfg)

        if planned.get("status") != "Optimal":
            # Fallback: max speed for this segment
            max_speed = config["ship"]["speed_range_knots"][1]
            # Use the SOG at max speed from the transform output
            max_sog = t_out["sog_matrix"][seg_idx][-1]  # last speed = max
            max_fcr = t_out["fcr"][-1]
            seg_dist = t_out["distances"][seg_idx]
            seg_time = seg_dist / max_sog
            logger.warning("Rolling LP seg %d: infeasible (remaining_eta=%.1f h), "
                           "using max speed", seg_idx, remaining_eta)
            committed.append({
                "segment": seg_idx,
                "sws_knots": t_out["speeds"][-1],
                "sog_knots": max_sog,
                "distance_nm": seg_dist,
                "time_h": seg_time,
                "fuel_mt": seg_dist * max_fcr / max_sog,
                "fcr_mt_h": max_fcr,
            })
            cum_time += seg_time
        else:
            # Commit only the first segment from this re-solve
            first = planned["speed_schedule"][0]

            # Post-solve clamp: cap SOG at the worst-case feasibility ceiling
            # to prevent SWS violations from within-segment weather variability
            # and time-varying weather during transit.
            import math as _math
            from shared.hdf5_io import read_metadata as _read_meta
            from shared.physics import calculate_ship_heading as _calc_heading

            _meta = _read_meta(hdf5_path)
            _orig = _meta[_meta["is_original"]].sort_values("node_id").reset_index(drop=True)
            _wp_a, _wp_b = _orig.iloc[seg_idx], _orig.iloc[seg_idx + 1]
            _heading_rad = _math.radians(_calc_heading(
                _wp_a["lat"], _wp_a["lon"], _wp_b["lat"], _wp_b["lon"]))

            min_speed = config["ship"]["speed_range_knots"][0]
            seg_dist = first["distance_nm"]
            max_seg_time = seg_dist / min_speed
            w_start = int(cum_time)
            w_end = min(int(cum_time + max_seg_time) + 1, max(available_hours))
            transit_hours = [h for h in available_hours if w_start <= h <= w_end]
            if not transit_hours:
                transit_hours = [sample_hour]

            sog_floor, sog_ceiling = _feasible_sog_bounds(
                hdf5_path, seg_idx, transit_hours, ship_params, _heading_rad)

            committed_sog = first["sog_knots"]
            if committed_sog > sog_ceiling:
                logger.info("Rolling LP seg %d: clamping SOG %.4f -> %.4f "
                            "(max-speed ceiling)", seg_idx, committed_sog, sog_ceiling)
                committed_sog = sog_ceiling
            elif committed_sog < sog_floor:
                logger.info("Rolling LP seg %d: raising SOG %.4f -> %.4f "
                            "(min-speed floor)", seg_idx, committed_sog, sog_floor)
                committed_sog = sog_floor

            seg_time = seg_dist / committed_sog
            committed.append({
                "segment": seg_idx,
                "sws_knots": first["sws_knots"],
                "sog_knots": committed_sog,
                "distance_nm": seg_dist,
                "time_h": seg_time,
                "fuel_mt": first["fcr_mt_h"] * seg_time,
                "fcr_mt_h": first["fcr_mt_h"],
            })
            cum_time += seg_time

        print(f"    Seg {seg_idx}: sample_hour={sample_hour}, "
              f"SWS={committed[-1]['sws_knots']:.2f} kn, "
              f"SOG={committed[-1]['sog_knots']:.2f} kn, "
              f"cum_time={cum_time:.1f} h")

    # Planned totals
    planned_fuel = sum(c["fuel_mt"] for c in committed)
    planned_time = sum(c["time_h"] for c in committed)

    print(f"  Rolling LP planned: {planned_fuel:.2f} mt fuel, {planned_time:.2f} h")
    print(f"  Sample hours used per segment: {hours_used}")

    # Simulate under actual weather (time_varying=True, same as run_exp_b.py)
    print("  Simulate (actual weather, time-varying)...")
    simulated = simulate_voyage(committed, hdf5_path, config,
                                sample_hour=0, time_varying=True)

    total_dist = sum(c["distance_nm"] for c in committed)
    planned_stub = {
        "planned_fuel_mt": planned_fuel,
        "planned_time_h": planned_time,
        "speed_schedule": committed,
        "computation_time_s": 0.0,
        "status": "Optimal",
    }
    metrics = compute_result_metrics(planned_stub, simulated, total_dist)

    ts_path = os.path.join(output_dir, "timeseries_rolling_lp.csv")
    simulated["time_series"].to_csv(ts_path, index=False)

    result = build_result_json(
        approach="rolling_lp",
        config=config,
        planned=planned_stub,
        simulated=simulated,
        metrics=metrics,
        time_series_file=ts_path,
    )
    result["sample_hours_per_segment"] = hours_used
    json_path = os.path.join(output_dir, "result_rolling_lp.json")
    save_result(result, json_path)

    print(f"  Rolling LP: plan={planned_fuel:.2f} mt, "
          f"sim={simulated['total_fuel_mt']:.2f} mt, "
          f"gap={metrics['fuel_gap_percent']:.2f}%, "
          f"SWS violations={simulated.get('sws_violations', 0)}")
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

        print(f"  {approach_name}: {simulated['total_fuel_mt']:.2f} mt fuel, "
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

            print(f"  {approach_name}: {simulated['total_fuel_mt']:.2f} mt fuel")
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

        print(f"  {approach_name_rh}: {simulated_rh['total_fuel_mt']:.2f} mt fuel")
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

    print(f"  {approach_name}: plan={planned['planned_fuel_mt']:.2f} mt, "
          f"sim={simulated['total_fuel_mt']:.2f} mt, "
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

        fuel = simulated["total_fuel_mt"]
        time_h = simulated["total_time_h"]
        violations = simulated.get("sws_violations", 0)
        print(f"  {label}: {fuel:.2f} mt fuel, {time_h:.2f} h, {violations} SWS violations")
        results[label] = result

    # Compute decomposition if all 4 core configs succeeded
    decomp = {}
    if all(k in results for k in ("A_LP", "A_DP", "B_LP", "B_DP")):
        a_lp = results["A_LP"]["simulated"]["total_fuel_mt"]
        a_dp = results["A_DP"]["simulated"]["total_fuel_mt"]
        b_lp = results["B_LP"]["simulated"]["total_fuel_mt"]
        b_dp = results["B_DP"]["simulated"]["total_fuel_mt"]

        temporal = a_dp - a_lp
        spatial = b_lp - a_lp
        interaction = b_dp - a_lp - temporal - spatial

        decomp = {
            "A_LP_fuel": round(a_lp, 4),
            "A_DP_fuel": round(a_dp, 4),
            "B_LP_fuel": round(b_lp, 4),
            "B_DP_fuel": round(b_dp, 4),
            "temporal_effect_mt": round(temporal, 4),
            "spatial_effect_mt": round(spatial, 4),
            "interaction_mt": round(interaction, 4),
        }

        if "B_RH" in results:
            b_rh = results["B_RH"]["simulated"]["total_fuel_mt"]
            decomp["B_RH_fuel"] = round(b_rh, 4)
            decomp["rh_additional_mt"] = round(b_rh - b_dp, 4)

        print("\n" + "=" * 60)
        print("2x2 DECOMPOSITION RESULTS")
        print("=" * 60)
        print(f"{'Config':<10} {'Fuel (mt)':>12} {'vs A-LP':>10}")
        print("-" * 35)
        print(f"{'A-LP':<10} {a_lp:>12.2f} {'baseline':>10}")
        print(f"{'A-DP':<10} {a_dp:>12.2f} {temporal:>+10.2f}")
        print(f"{'B-LP':<10} {b_lp:>12.2f} {spatial:>+10.2f}")
        print(f"{'B-DP':<10} {b_dp:>12.2f} {b_dp - a_lp:>+10.2f}")
        if "B_RH" in results:
            print(f"{'B-RH':<10} {b_rh:>12.2f} {b_rh - a_lp:>+10.2f}")
        print("-" * 35)
        print(f"Temporal effect (A-DP - A-LP):  {temporal:+.2f} mt")
        print(f"Spatial effect  (B-LP - A-LP):  {spatial:+.2f} mt")
        print(f"Interaction:                    {interaction:+.2f} mt")
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

            print(f"  {approach_name}: {simulated['total_fuel_mt']:.2f} mt, "
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

        print(f"  {approach_name_rh}: {simulated_rh['total_fuel_mt']:.2f} mt, "
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
        fuel = r["simulated"]["total_fuel_mt"]
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
    print("\n[1/6] Lower bound (perfect information)...")
    lb = run_lower_bound(config, hdf5_path, output_dir)

    # 2. Constant-speed bound (ETA-meeting)
    print("\n[2/6] Constant-speed bound (ETA-meeting)...")
    csb = run_constant_speed_bound(config, hdf5_path, output_dir)

    # 3. Rolling LP (segment-wise re-planning)
    print("\n[3/6] Rolling LP (segment-wise re-planning)...")
    rlp = run_rolling_lp(config, hdf5_path, output_dir)

    # 4. Upper bound
    print("\n[4/6] Upper bound (constant speed = max)...")
    ub = run_upper_bound(config, hdf5_path, output_dir)

    # 5. Replan sweep
    print("\n[5/6] Replan frequency sweep...")
    sweep = run_replan_sweep(config, hdf5_path, output_dir)

    # 6. Forecast horizon sweep
    print("\n[6/6] Forecast horizon sweep...")
    horizon = run_horizon_sweep(config, hdf5_path, output_dir)

    # Summary table
    print("\n" + "=" * 60)
    print("SENSITIVITY SUMMARY")
    print("=" * 60)
    print(f"{'Approach':<35}  {'Sim Fuel (mt)':>14}  {'Sim Time (h)':>13}")
    print("-" * 65)

    all_results = []
    if lb:
        all_results.append(lb)
    if csb:
        all_results.append(csb)
    if rlp:
        all_results.append(rlp)
    if ub:
        all_results.append(ub)
    all_results.extend(sweep)
    all_results.extend(horizon)

    for r in all_results:
        name = r["approach"]
        fuel = r["simulated"]["total_fuel_mt"]
        time_h = r["simulated"]["voyage_time_h"]
        print(f"{name:<35}  {fuel:>14.2f}  {time_h:>13.2f}")

    print("=" * 65)
    return output_dir

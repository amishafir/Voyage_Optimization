"""Cycle executor — 6h NWP-aligned re-planning for 3-agent experiments.

All three agents (Naive, Deterministic, Stochastic) re-plan on the same
6-hour NWP cycle. They differ only in what weather information they use
at re-plan time:
    - Naive: none (constant SOG = remaining_dist / remaining_time)
    - Deterministic: actual weather at all waypoints, treated as constant
    - Stochastic: actuals for current 6h + forecast for future legs

Between re-plans, all agents execute rigidly: follow planned SOG, clamp
SWS to [min, max], record Flow classification but no reactive response.
"""

import logging
import math
import time as time_module

import pandas as pd

from shared.hdf5_io import read_metadata, read_predicted, read_actual
from shared.physics import (
    calculate_ship_heading,
    calculate_speed_over_ground,
    calculate_sws_from_sog,
    calculate_fuel_consumption_rate,
    calculate_co2_emissions,
    load_ship_parameters,
)
from dynamic_det.optimize import optimize as dp_optimize
from agent.weather_assembler import (
    assemble_naive,
    assemble_deterministic,
    assemble_stochastic,
)

logger = logging.getLogger(__name__)

WEATHER_FIELDS = [
    "wind_speed_10m_kmh", "wind_direction_10m_deg", "beaufort_number",
    "wave_height_m", "ocean_current_velocity_kmh", "ocean_current_direction_deg",
]


def execute_cycle_voyage(agent_type: str, hdf5_path: str, config: dict,
                         departure_sample_hour: int = 0) -> dict:
    """Execute a voyage with 6h NWP-aligned re-planning.

    Args:
        agent_type: "naive", "deterministic", or "stochastic"
        hdf5_path: Path to HDF5 weather file.
        config: Full experiment config.
        departure_sample_hour: Which sample_hour the voyage departs at.

    Returns:
        Dict with planned/executed results, flow events, replan log.
    """
    start_wall = time_module.time()
    ship_params = load_ship_parameters(config)
    dd_cfg = config["dynamic_det"]

    # Ship speed limits
    min_sws, max_sws = config["ship"]["speed_range_knots"]
    eta_hours = config["ship"]["eta_hours"]
    replan_freq = config.get("three_agent", {}).get("replan_frequency_hours", 6)

    # ------------------------------------------------------------------
    # Pre-load: structural data (once)
    # ------------------------------------------------------------------
    metadata = read_metadata(hdf5_path)
    metadata = metadata.sort_values("node_id").reset_index(drop=True)

    nodes_mode = dd_cfg.get("nodes", "all")
    if nodes_mode == "original":
        metadata = metadata[metadata["is_original"]].reset_index(drop=True)

    num_nodes = len(metadata)
    active_node_ids = [int(r["node_id"]) for _, r in metadata.iterrows()]

    # Per-leg distances and headings
    legs = []
    for i in range(num_nodes - 1):
        node_a = metadata.iloc[i]
        node_b = metadata.iloc[i + 1]
        dist = node_b["distance_from_start_nm"] - node_a["distance_from_start_nm"]
        dist = max(dist, 0.001)
        heading = calculate_ship_heading(
            node_a["lat"], node_a["lon"], node_b["lat"], node_b["lon"]
        )
        legs.append({
            "idx": len(legs),
            "node_id": int(node_a["node_id"]),
            "segment": int(node_a["segment"]),
            "dist": dist,
            "heading_deg": heading,
            "lat": float(node_a["lat"]),
            "lon": float(node_a["lon"]),
        })

    num_legs = len(legs)
    distances = [l["dist"] for l in legs]
    headings_deg = [l["heading_deg"] for l in legs]
    total_distance = sum(distances)

    # Speed and FCR arrays (for DP)
    granularity = dd_cfg["speed_granularity"]
    num_speeds = int(round((max_sws - min_sws) / granularity)) + 1
    speeds = [min_sws + k * granularity for k in range(num_speeds)]
    fcr_array = [calculate_fuel_consumption_rate(s) for s in speeds]

    # Node metadata list (for DP sub-problems)
    node_metadata = []
    for _, row in metadata.iterrows():
        node_metadata.append({
            "node_id": int(row["node_id"]),
            "lat": float(row["lat"]),
            "lon": float(row["lon"]),
            "segment": int(row["segment"]),
        })

    # ------------------------------------------------------------------
    # Pre-load: weather data (once)
    # ------------------------------------------------------------------
    # Actual weather (all sample hours)
    all_actual_df = read_actual(hdf5_path)
    actual_weather = {}
    available_actual_hours = []
    if len(all_actual_df) > 0:
        available_actual_hours = sorted(int(s) for s in all_actual_df["sample_hour"].unique())
        active_set = set(active_node_ids)
        for sh in available_actual_hours:
            sh_data = all_actual_df[all_actual_df["sample_hour"] == sh]
            grid = {}
            for _, row in sh_data.iterrows():
                nid = int(row["node_id"])
                if nid not in active_set:
                    continue
                wx = {}
                for field in WEATHER_FIELDS:
                    val = float(row[field])
                    if math.isnan(val):
                        val = 0.0
                    wx[field] = val
                grid[nid] = wx
            actual_weather[sh] = grid

    # Predicted weather (all sample hours) — only needed for stochastic
    predicted_grids = {}
    max_forecast_hours = {}
    available_predicted_hours = []

    if agent_type == "stochastic":
        all_predicted_df = read_predicted(hdf5_path)
        if len(all_predicted_df) > 0:
            available_predicted_hours = sorted(
                int(s) for s in all_predicted_df["sample_hour"].unique()
            )
            active_set = set(active_node_ids)
            for sh in available_predicted_hours:
                sh_data = all_predicted_df[all_predicted_df["sample_hour"] == sh]
                grid = {}
                max_fh = 0
                for _, row in sh_data.iterrows():
                    nid = int(row["node_id"])
                    if nid not in active_set:
                        continue
                    fh = int(row["forecast_hour"])
                    if nid not in grid:
                        grid[nid] = {}
                    wx = {}
                    for field in WEATHER_FIELDS:
                        val = float(row[field])
                        if math.isnan(val):
                            val = 0.0
                        wx[field] = val
                    grid[nid][fh] = wx
                    if fh > max_fh:
                        max_fh = fh
                predicted_grids[sh] = grid
                max_forecast_hours[sh] = max_fh

    logger.info("Cycle executor [%s]: %d legs, %.1f nm, ETA=%dh, replan every %dh",
                agent_type, num_legs, total_distance, eta_hours, replan_freq)
    logger.info("  Actual weather: %d sample hours, Predicted: %d sample hours",
                len(available_actual_hours), len(available_predicted_hours))

    # ------------------------------------------------------------------
    # Build NWP-aligned re-plan schedule
    # ------------------------------------------------------------------
    nwp_hours = list(range(departure_sample_hour, int(eta_hours) + replan_freq, replan_freq))

    # ------------------------------------------------------------------
    # Cycle loop: PLAN then EXECUTE
    # ------------------------------------------------------------------
    current_leg = 0
    cum_time = 0.0
    cum_fuel = 0.0
    cum_distance = 0.0

    sog_schedule = [total_distance / eta_hours] * num_legs  # initial naive default
    rows = []
    replan_log = []
    replan_count = 0

    for cycle_idx, nwp_hour in enumerate(nwp_hours):
        if current_leg >= num_legs:
            break

        is_last_cycle = (cycle_idx + 1 >= len(nwp_hours))
        next_replan_time = nwp_hours[cycle_idx + 1] if not is_last_cycle else float("inf")

        # ---- PLAN ----
        remaining_legs = num_legs - current_leg
        remaining_dist = sum(distances[current_leg:])
        remaining_eta = max(eta_hours - cum_time, 0.1)

        sample_hour = _pick_sample_hour(available_actual_hours, nwp_hour)

        if agent_type == "naive":
            target_sog = remaining_dist / remaining_eta
            # Clamp to achievable SOG range (approximate: assume SOG ≈ SWS)
            target_sog = max(min_sws, min(max_sws, target_sog))
            sog_schedule = _fill_schedule(target_sog, current_leg, num_legs)
            plan_fuel = 0.0
            plan_time = remaining_dist / target_sog
            plan_status = "Optimal"

        elif agent_type == "deterministic":
            weather_grid, max_fh = assemble_deterministic(
                actual_weather, sample_hour, active_node_ids[current_leg:],
                max_forecast_hour_needed=remaining_eta,
            )
            result = _run_dp(
                current_leg, remaining_eta, cum_time,
                distances, headings_deg, node_metadata,
                speeds, fcr_array, ship_params, weather_grid, max_fh, config,
            )
            if result is not None:
                sog_schedule = _apply_dp_result(result, current_leg, num_legs, sog_schedule)
                plan_fuel = result.get("planned_fuel_mt", 0)
                plan_time = result.get("planned_time_h", 0)
                plan_status = result["status"]
            else:
                plan_fuel = 0.0
                plan_time = remaining_eta
                plan_status = "Fallback"

        elif agent_type == "stochastic":
            pred_sh = _pick_sample_hour(available_predicted_hours, nwp_hour) if available_predicted_hours else sample_hour
            weather_grid, max_fh = assemble_stochastic(
                actual_weather, predicted_grids, max_forecast_hours,
                pred_sh, active_node_ids[current_leg:],
                cum_time, replan_freq,
            )
            result = _run_dp(
                current_leg, remaining_eta, cum_time,
                distances, headings_deg, node_metadata,
                speeds, fcr_array, ship_params, weather_grid, max_fh, config,
            )
            if result is not None:
                sog_schedule = _apply_dp_result(result, current_leg, num_legs, sog_schedule)
                plan_fuel = result.get("planned_fuel_mt", 0)
                plan_time = result.get("planned_time_h", 0)
                plan_status = result["status"]
            else:
                plan_fuel = 0.0
                plan_time = remaining_eta
                plan_status = "Fallback"
        else:
            raise ValueError(f"Unknown agent type: {agent_type}")

        replan_log.append({
            "cycle": cycle_idx,
            "nwp_hour": nwp_hour,
            "sample_hour": sample_hour,
            "hour": round(cum_time, 2),
            "leg": current_leg,
            "remaining_legs": remaining_legs,
            "remaining_dist_nm": round(remaining_dist, 2),
            "remaining_eta_h": round(remaining_eta, 2),
            "plan_status": plan_status,
            "plan_fuel_mt": round(plan_fuel, 4),
            "plan_time_h": round(plan_time, 4),
        })
        replan_count += 1

        logger.info("  Cycle %d [%s]: NWP=%d, SH=%d, leg=%d, remaining=%.0f nm / %.1fh, status=%s",
                     cycle_idx, agent_type, nwp_hour, sample_hour,
                     current_leg, remaining_dist, remaining_eta, plan_status)

        # ---- EXECUTE legs until next re-plan ----
        while current_leg < num_legs:
            leg = legs[current_leg]
            i = leg["idx"]
            nid = leg["node_id"]
            dist = leg["dist"]
            heading_deg = leg["heading_deg"]

            target_sog = sog_schedule[current_leg]

            # OBSERVE: actual weather (time-varying)
            wx = _get_actual_weather(actual_weather, available_actual_hours,
                                     cum_time, nid)

            # ASSESS: required SWS for target SOG
            required_sws = calculate_sws_from_sog(
                target_sog=target_sog,
                weather=wx,
                ship_heading_deg=heading_deg,
                ship_parameters=ship_params,
            )

            # CLASSIFY
            if required_sws > max_sws + 0.01:
                flow = "FLOW2"
            elif required_sws < min_sws - 0.01:
                flow = "FLOW3"
            else:
                flow = "FLOW1"

            # EXECUTE: clamp SWS
            actual_sws = max(min_sws, min(max_sws, required_sws))

            if abs(actual_sws - required_sws) > 0.01:
                heading_rad = math.radians(heading_deg)
                wind_dir_rad = math.radians(wx["wind_direction_10m_deg"])
                current_knots = wx["ocean_current_velocity_kmh"] / 1.852
                current_dir_rad = math.radians(wx["ocean_current_direction_deg"])
                beaufort = int(round(wx["beaufort_number"]))
                wave_height = wx["wave_height_m"]

                actual_sog = calculate_speed_over_ground(
                    ship_speed=actual_sws,
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

            fcr = calculate_fuel_consumption_rate(actual_sws)
            leg_time = dist / actual_sog
            leg_fuel = fcr * leg_time

            cum_distance += dist
            cum_time += leg_time
            cum_fuel += leg_fuel

            rows.append({
                "node_id": nid,
                "segment": leg["segment"],
                "lat": leg["lat"],
                "lon": leg["lon"],
                "planned_sog_knots": target_sog,
                "actual_sog_knots": actual_sog,
                "planned_sws_knots": required_sws,
                "actual_sws_knots": actual_sws,
                "distance_nm": dist,
                "time_h": leg_time,
                "fuel_mt": leg_fuel,
                "cum_distance_nm": cum_distance,
                "cum_time_h": cum_time,
                "cum_fuel_mt": cum_fuel,
                "beaufort": int(round(wx.get("beaufort_number", 0))),
                "wave_height_m": wx.get("wave_height_m", 0.0),
                "current_knots": wx.get("ocean_current_velocity_kmh", 0.0) / 1.852,
                "heading_deg": heading_deg,
                "flow": flow,
            })

            current_leg += 1

            # Check re-plan trigger (deferred to leg boundary)
            if cum_time >= next_replan_time and not is_last_cycle:
                break

    # ------------------------------------------------------------------
    # Results
    # ------------------------------------------------------------------
    elapsed_wall = time_module.time() - start_wall
    time_series = pd.DataFrame(rows)
    co2 = calculate_co2_emissions(cum_fuel)

    flow2_count = sum(1 for r in rows if r["flow"] == "FLOW2")
    flow3_count = sum(1 for r in rows if r["flow"] == "FLOW3")
    sws_adjustments = sum(
        1 for r in rows if abs(r["actual_sws_knots"] - r["planned_sws_knots"]) > 0.01
    )

    return {
        "status": "Completed",
        "agent": agent_type.capitalize(),
        "total_fuel_mt": cum_fuel,
        "total_time_h": cum_time,
        "arrival_deviation_h": cum_time - eta_hours,
        "sws_adjustments": sws_adjustments,
        "co2_emissions_mt": co2,
        "flow2_count": flow2_count,
        "flow3_count": flow3_count,
        "replan_count": replan_count,
        "replan_log": replan_log,
        "computation_time_s": round(elapsed_wall, 4),
        "time_series": time_series,
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _pick_sample_hour(available, target):
    """Pick largest available sample_hour <= target, or smallest if none."""
    if not available:
        return 0
    target_int = int(target)
    candidates = [s for s in available if s <= target_int]
    if candidates:
        return max(candidates)
    return available[0]


def _get_actual_weather(actual_weather, available_hours, cum_time, node_id):
    """Get actual weather for a node at the current voyage time."""
    if not available_hours:
        return {f: 0.0 for f in WEATHER_FIELDS}
    sh = _pick_sample_hour(available_hours, cum_time)
    grid = actual_weather.get(sh, {})
    wx = grid.get(node_id)
    if wx is not None:
        return wx
    return {f: 0.0 for f in WEATHER_FIELDS}


def _fill_schedule(sog, from_leg, num_legs):
    """Build a flat SOG schedule from from_leg onward."""
    schedule = [0.0] * num_legs
    for i in range(from_leg, num_legs):
        schedule[i] = sog
    return schedule


def _run_dp(current_leg, remaining_eta, elapsed_time,
            distances, headings_deg, node_metadata,
            speeds, fcr, ship_params, weather_grid, max_fh, config):
    """Build DP sub-problem and optimize remaining voyage."""
    remaining_legs = len(distances) - current_leg

    sub_transform = {
        "ETA": remaining_eta,
        "num_nodes": remaining_legs + 1,
        "num_legs": remaining_legs,
        "speeds": speeds,
        "fcr": fcr,
        "distances": distances[current_leg:],
        "headings_deg": headings_deg[current_leg:],
        "weather_grid": weather_grid,
        "max_forecast_hour": max_fh,
        "node_metadata": node_metadata[current_leg:],
        "ship_params": ship_params,
        "time_offset": elapsed_time,
    }

    try:
        result = dp_optimize(sub_transform, config)
    except Exception as e:
        logger.warning("DP optimize failed: %s", e)
        return None

    if result.get("status") not in ("Optimal", "Feasible", "ETA_relaxed"):
        logger.warning("DP infeasible: %s", result.get("status"))
        return None

    return result


def _apply_dp_result(result, current_leg, num_legs, old_schedule):
    """Merge DP speed schedule into the global schedule."""
    schedule = list(old_schedule)
    dp_schedule = result["speed_schedule"]

    for entry in dp_schedule:
        global_leg = entry["leg"] + current_leg
        if global_leg < num_legs:
            schedule[global_leg] = entry["sog_knots"]

    return schedule

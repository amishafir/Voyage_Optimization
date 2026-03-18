"""Voyage executor — leg-by-leg simulation with policy-driven re-planning.

This is the runtime that wires agent components together. At each leg:
  OBSERVE → ASSESS → CLASSIFY → EXECUTE → UPDATE → DECIDE

Replaces both shared/simulation.py (for Basic agents) and
dynamic_rh/optimize.py (for Connected agents) with a unified loop.
"""

import logging
import math
import time as time_module

import pandas as pd

from shared.hdf5_io import read_metadata, read_actual
from shared.physics import (
    calculate_ship_heading,
    calculate_speed_over_ground,
    calculate_sws_from_sog,
    calculate_fuel_consumption_rate,
    calculate_co2_emissions,
    load_ship_parameters,
)
from agent.policies import Action, FlowType, VoyageState

logger = logging.getLogger(__name__)

WEATHER_FIELDS = [
    "wind_speed_10m_kmh", "wind_direction_10m_deg", "beaufort_number",
    "wave_height_m", "ocean_current_velocity_kmh", "ocean_current_direction_deg",
]


def execute_voyage(agent, hdf5_path: str, config: dict,
                   initial_plan: dict = None,
                   transform_output: dict = None,
                   replan_transform: dict = None,
                   time_varying: bool = False,
                   sample_hour: int = 0) -> dict:
    """Execute a voyage with the given agent.

    Args:
        agent: Assembled Agent object.
        hdf5_path: Path to HDF5 weather file.
        config: Full experiment config.
        initial_plan: Pre-computed plan dict (if None, agent plans from transform_output).
        transform_output: Transform data for initial planning (required if initial_plan is None).
        replan_transform: Transform data for re-planning (if different from transform_output).
                          LP agents need the DP transform for re-planning (has node_metadata).
        time_varying: Use time-varying actual weather for simulation (for Connected).
        sample_hour: Which actual-weather snapshot to use (for Basic/Mid).

    Returns:
        Dict with planned results, executed results, flow events, replan log.
    """
    start_wall = time_module.time()
    spec = agent.spec
    ship_params = load_ship_parameters(config)

    # ------------------------------------------------------------------
    # Initial planning
    # ------------------------------------------------------------------
    if initial_plan is None:
        if transform_output is None:
            raise ValueError("Either initial_plan or transform_output must be provided")
        initial_plan = agent.plan.optimize(transform_output, config)

    if initial_plan.get("status") not in ("Optimal", "Feasible", "ETA_relaxed"):
        return {
            "status": initial_plan.get("status", "Infeasible"),
            "agent": agent.name,
            "computation_time_s": time_module.time() - start_wall,
        }

    # ------------------------------------------------------------------
    # Load weather and route data from HDF5
    # ------------------------------------------------------------------
    metadata = read_metadata(hdf5_path)
    metadata = metadata.sort_values("node_id").reset_index(drop=True)
    num_nodes = len(metadata)

    # Build actual weather lookup
    if time_varying:
        all_actual = read_actual(hdf5_path)
        avail_sh = sorted(int(h) for h in all_actual["sample_hour"].unique())
        wx_by_sh = {}
        for sh in avail_sh:
            sh_data = all_actual[all_actual["sample_hour"] == sh]
            wx_by_sh[sh] = {}
            for _, row in sh_data.iterrows():
                nid = int(row["node_id"])
                wx_by_sh[sh][nid] = {f: _safe(row.get(f), 0.0) for f in WEATHER_FIELDS}
    else:
        weather_df = read_actual(hdf5_path, sample_hour=sample_hour)
        merged = metadata.merge(weather_df, on="node_id", how="left")
        merged = merged.sort_values("node_id").reset_index(drop=True)
        avail_sh = None
        wx_by_sh = None

    # Pre-compute per-leg data: distances, headings, node IDs
    legs = []
    for idx in range(num_nodes - 1):
        node_a = metadata.iloc[idx]
        node_b = metadata.iloc[idx + 1]
        dist = node_b["distance_from_start_nm"] - node_a["distance_from_start_nm"]
        if dist <= 0:
            continue
        heading_deg = calculate_ship_heading(
            node_a["lat"], node_a["lon"], node_b["lat"], node_b["lon"]
        )
        legs.append({
            "idx": len(legs),
            "node_id": int(node_a["node_id"]),
            "segment": int(node_a["segment"]),
            "dist": dist,
            "heading_deg": heading_deg,
            "lat": float(node_a["lat"]),
            "lon": float(node_a["lon"]),
        })

    num_legs = len(legs)

    # ------------------------------------------------------------------
    # Build SOG schedule from initial plan
    # ------------------------------------------------------------------
    schedule = initial_plan["speed_schedule"]
    sog_schedule = _build_sog_lookup(schedule, num_legs, legs)

    # ------------------------------------------------------------------
    # Leg-by-leg execution
    # ------------------------------------------------------------------
    state = VoyageState(total_legs=num_legs)
    rows = []
    replan_log = []
    flow2_events = []
    flow3_events = []

    cum_distance = 0.0
    cum_time = 0.0
    cum_fuel = 0.0
    planned_cum_time = 0.0
    time_since_replan = 0.0
    prev_flow2_streak = 0

    for leg in legs:
        i = leg["idx"]
        nid = leg["node_id"]
        dist = leg["dist"]
        heading_deg = leg["heading_deg"]

        target_sog = sog_schedule[i]

        # 1. OBSERVE — actual weather
        if time_varying:
            sh = _pick_closest_hour(avail_sh, cum_time)
            wx = wx_by_sh.get(sh, {}).get(nid, {f: 0.0 for f in WEATHER_FIELDS})
        else:
            row = merged[merged["node_id"] == nid]
            if len(row) > 0:
                row = row.iloc[0]
                wx = {f: _safe(row.get(f), 0.0) for f in WEATHER_FIELDS}
            else:
                wx = {f: 0.0 for f in WEATHER_FIELDS}

        # 2. ASSESS — required SWS
        required_sws = calculate_sws_from_sog(
            target_sog=target_sog,
            weather=wx,
            ship_heading_deg=heading_deg,
            ship_parameters=ship_params,
        )

        # 3. CLASSIFY
        if required_sws > spec.max_sws + 0.01:
            flow = FlowType.FLOW2
        elif required_sws < spec.min_sws - 0.01:
            flow = FlowType.FLOW3
        else:
            flow = FlowType.FLOW1

        # 4. EXECUTE — clamp SWS
        actual_sws = max(spec.min_sws, min(spec.max_sws, required_sws))

        if abs(actual_sws - required_sws) > 0.01:
            # SWS was clamped — recompute actual SOG
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

        # 5. UPDATE STATE
        planned_leg_time = dist / target_sog
        planned_cum_time += planned_leg_time
        cum_distance += dist
        cum_time += leg_time
        cum_fuel += leg_fuel
        time_since_replan += leg_time

        # Track Flow 2 streak
        if flow == FlowType.FLOW2:
            prev_flow2_streak += 1
            flow2_events.append({"leg": i, "node_id": nid, "required_sws": required_sws})
        else:
            flow2_streak_ended = prev_flow2_streak
            prev_flow2_streak = 0

        if flow == FlowType.FLOW3:
            flow3_events.append({"leg": i, "node_id": nid, "required_sws": required_sws})

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
            "flow": flow.name,
        })

        # 6. DECIDE — ask policy
        state.leg_idx = i
        state.cumulative_time_h = cum_time
        state.cumulative_fuel_mt = cum_fuel
        state.planned_cumulative_time_h = planned_cum_time
        state.delay_h = cum_time - planned_cum_time
        state.flow_type = flow
        state.flow2_streak = prev_flow2_streak if flow == FlowType.FLOW2 else flow2_streak_ended if flow != FlowType.FLOW2 and 'flow2_streak_ended' in dir() else 0
        state.time_since_replan_h = time_since_replan
        state.flow_history.append(flow)

        action = agent.policy.on_leg_complete(state)

        # Reset flow2 streak tracking after policy check
        if flow != FlowType.FLOW2:
            state.flow2_streak = 0

        # Handle re-plan
        if action != Action.CONTINUE and i < num_legs - 1:
            can_replan = (
                (action == Action.REPLAN and agent.environment.can_compute) or
                (action == Action.REPLAN_FRESH and agent.environment.can_compute)
            )
            if can_replan:
                replan_data = replan_transform if replan_transform is not None else transform_output
                new_schedule = _do_replan(
                    agent=agent,
                    action=action,
                    current_leg=i,
                    legs=legs,
                    cum_time=cum_time,
                    config=config,
                    hdf5_path=hdf5_path,
                    transform_output=replan_data,
                )
                if new_schedule is not None:
                    sog_schedule = _merge_schedule(sog_schedule, new_schedule, i + 1)
                    state.replan_count += 1
                    time_since_replan = 0.0
                    replan_log.append({
                        "leg": i,
                        "hour": round(cum_time, 2),
                        "trigger": action.name,
                        "flow": flow.name,
                        "delay_h": round(cum_time - planned_cum_time, 2),
                        "remaining_legs": num_legs - i - 1,
                    })
                    logger.info("Executor re-plan at leg %d (%.1fh): %s, delay=%.1fh",
                                i, cum_time, action.name, cum_time - planned_cum_time)

    # ------------------------------------------------------------------
    # Results
    # ------------------------------------------------------------------
    elapsed_wall = time_module.time() - start_wall
    time_series = pd.DataFrame(rows)
    co2 = calculate_co2_emissions(cum_fuel)
    eta = spec.eta_hours

    # Count SWS adjustments (backward compat with simulation.py)
    sws_adjustments = sum(1 for r in rows if abs(r["actual_sws_knots"] - r["planned_sws_knots"]) > 0.01)

    flow2_count = sum(1 for r in rows if r["flow"] == "FLOW2")
    flow3_count = sum(1 for r in rows if r["flow"] == "FLOW3")

    return {
        "status": "Completed",
        "agent": agent.name,
        # Plan results (from initial planning)
        "planned_fuel_mt": initial_plan.get("planned_fuel_mt", 0),
        "planned_time_h": initial_plan.get("planned_time_h", 0),
        "planned_delay_h": initial_plan.get("planned_delay_h", 0),
        "planned_total_cost_mt": initial_plan.get("planned_total_cost_mt", 0),
        # Execution results
        "total_fuel_mt": cum_fuel,
        "total_time_h": cum_time,
        "arrival_deviation_h": cum_time - eta,
        "sws_adjustments": sws_adjustments,
        "sws_violations": sws_adjustments,  # backward compat
        "co2_emissions_mt": co2,
        # Agent-specific
        "flow2_count": flow2_count,
        "flow3_count": flow3_count,
        "replan_count": state.replan_count,
        "flow2_events": flow2_events,
        "replan_log": replan_log,
        # Meta
        "computation_time_s": round(elapsed_wall, 4),
        "time_series": time_series,
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_sog_lookup(schedule: list, num_legs: int, legs: list) -> list:
    """Build a per-leg SOG array from a speed schedule.

    Handles both per-leg (node_id key) and per-segment schedules.
    """
    if not schedule:
        return [12.0] * num_legs

    if "node_id" in schedule[0]:
        # Per-leg schedule (from DP or RH)
        node_sog = {entry["node_id"]: entry["sog_knots"] for entry in schedule}
        result = []
        for leg in legs:
            result.append(node_sog.get(leg["node_id"], schedule[0]["sog_knots"]))
        return result
    elif "segment" in schedule[0]:
        # Per-segment schedule (from LP)
        seg_sog = {entry["segment"]: entry["sog_knots"] for entry in schedule}
        result = []
        for leg in legs:
            result.append(seg_sog.get(leg["segment"], schedule[0]["sog_knots"]))
        return result
    else:
        # Per-leg by index (from Naive)
        result = []
        for i, leg in enumerate(legs):
            if i < len(schedule):
                result.append(schedule[i]["sog_knots"])
            else:
                result.append(schedule[-1]["sog_knots"])
        return result


def _do_replan(agent, action, current_leg, legs, cum_time, config, hdf5_path,
               transform_output):
    """Build a sub-problem and re-plan remaining voyage.

    Returns a new SOG list for legs [current_leg+1:], or None on failure.
    """
    remaining_start = current_leg + 1
    remaining_legs_data = legs[remaining_start:]
    if not remaining_legs_data:
        return None

    eta = agent.spec.eta_hours
    lambda_val = agent.spec.eta_penalty_mt_per_hour
    soft_eta = lambda_val is not None and lambda_val != float("inf")

    remaining_eta = eta - cum_time
    if remaining_eta <= 0:
        if soft_eta:
            remaining_dist = sum(l["dist"] for l in remaining_legs_data)
            remaining_eta = remaining_dist / 8.0  # conservative
        else:
            return None  # infeasible with hard ETA

    # Build sub-problem based on plan type
    if agent.plan.name == "dp":
        return _replan_dp(agent, remaining_start, remaining_eta, cum_time,
                          config, transform_output, action)
    elif agent.plan.name == "lp":
        return _replan_lp(agent, remaining_start, remaining_eta, cum_time,
                          config, transform_output, action)
    else:
        # Naive: recalculate constant SOG for remaining distance/ETA
        remaining_dist = sum(l["dist"] for l in remaining_legs_data)
        new_sog = remaining_dist / max(remaining_eta, 0.1)
        return [new_sog] * len(remaining_legs_data)


def _replan_dp(agent, remaining_start, remaining_eta, elapsed_time,
               config, transform_output, action):
    """Re-plan with DP optimizer for remaining voyage."""
    if transform_output is None:
        return None

    # For Connected (REPLAN_FRESH): get fresh forecast from environment
    if action == Action.REPLAN_FRESH and agent.environment.can_communicate:
        forecast_data = agent.environment.get_forecast(elapsed_time, None, config)
        if forecast_data is not None:
            weather_grid = forecast_data["weather_grid"]
            max_fh = forecast_data["max_forecast_hour"]
        else:
            weather_grid = transform_output.get("weather_grid", {})
            max_fh = transform_output.get("max_forecast_hour", 0)
    else:
        # Mid (REPLAN): use stale forecast
        weather_grid = transform_output.get("weather_grid", {})
        max_fh = transform_output.get("max_forecast_hour", 0)

    sub_transform = {
        "ETA": remaining_eta,
        "num_nodes": transform_output["num_legs"] - remaining_start + 1,
        "num_legs": transform_output["num_legs"] - remaining_start,
        "speeds": transform_output["speeds"],
        "fcr": transform_output["fcr"],
        "distances": transform_output["distances"][remaining_start:],
        "headings_deg": transform_output["headings_deg"][remaining_start:],
        "weather_grid": weather_grid,
        "max_forecast_hour": max_fh,
        "node_metadata": transform_output["node_metadata"][remaining_start:],
        "ship_params": transform_output["ship_params"],
        "time_offset": elapsed_time,
    }

    result = agent.plan.optimize(sub_transform, config)
    if result.get("status") not in ("Optimal", "Feasible", "ETA_relaxed"):
        return None

    return [entry["sog_knots"] for entry in result["speed_schedule"]]


def _replan_lp(agent, remaining_start, remaining_eta, elapsed_time,
               config, transform_output, action):
    """Re-plan with LP optimizer for remaining voyage.

    Uses _build_lp_sub_problem from dynamic_rh/optimize_lp.py pattern.
    """
    if transform_output is None:
        return None

    # For Connected: get fresh weather snapshot
    if action == Action.REPLAN_FRESH and agent.environment.can_communicate:
        forecast_data = agent.environment.get_forecast(elapsed_time, None, config)
        if forecast_data is not None:
            # Build per-node weather from grid at closest forecast hour
            grid = forecast_data["weather_grid"]
            max_fh = forecast_data["max_forecast_hour"]
            fh_target = min(int(round(elapsed_time)), max_fh)
            weather_for_nodes = {}
            for nid, fh_dict in grid.items():
                wx = fh_dict.get(fh_target)
                if wx is None:
                    available_fh = sorted(fh_dict.keys())
                    if available_fh:
                        closest = min(available_fh, key=lambda h: abs(h - fh_target))
                        wx = fh_dict[closest]
                if wx:
                    weather_for_nodes[nid] = wx
        else:
            weather_for_nodes = _extract_weather_for_nodes(transform_output, elapsed_time)
    else:
        weather_for_nodes = _extract_weather_for_nodes(transform_output, elapsed_time)

    # Use the LP sub-problem builder from optimize_lp
    try:
        from dynamic_rh.optimize_lp import _build_lp_sub_problem
        import numpy as np

        lp_input = _build_lp_sub_problem(
            remaining_start=remaining_start,
            num_legs=transform_output.get("num_legs", len(transform_output.get("distances", []))),
            node_metadata=transform_output["node_metadata"],
            distances=transform_output["distances"],
            headings_deg=transform_output["headings_deg"],
            weather_for_nodes=weather_for_nodes,
            speeds=np.array(transform_output["speeds"]),
            fcr=np.array(transform_output["fcr"]),
            ship_params=transform_output["ship_params"],
            remaining_eta=remaining_eta,
            config=config,
        )

        if lp_input is None:
            return None

        result = agent.plan.optimize(lp_input, config)
        if result.get("status") not in ("Optimal", "Feasible", "ETA_relaxed"):
            return None

        # Map segment SOG back to per-leg SOG
        seg_order = lp_input["_seg_order"]
        seg_sog_map = {}
        for entry in result["speed_schedule"]:
            orig_seg = seg_order[entry["segment"]]
            seg_sog_map[orig_seg] = entry["sog_knots"]

        remaining_meta = transform_output["node_metadata"][remaining_start:]
        sog_list = []
        for meta in remaining_meta:
            seg = meta["segment"]
            sog_list.append(seg_sog_map.get(seg, 12.0))
        return sog_list

    except Exception as e:
        logger.warning("LP re-plan failed: %s", e)
        return None


def _extract_weather_for_nodes(transform_output, elapsed_time):
    """Extract per-node weather from DP transform output at a given time."""
    weather_grid = transform_output.get("weather_grid", {})
    max_fh = transform_output.get("max_forecast_hour", 0)
    fh_target = min(int(round(elapsed_time)), max_fh)

    weather_for_nodes = {}
    for nid, fh_dict in weather_grid.items():
        wx = fh_dict.get(fh_target)
        if wx is None:
            available_fh = sorted(fh_dict.keys())
            if available_fh:
                closest = min(available_fh, key=lambda h: abs(h - fh_target))
                wx = fh_dict[closest]
        if wx:
            weather_for_nodes[nid] = wx
    return weather_for_nodes


def _merge_schedule(old_sog: list, new_sog: list, from_idx: int) -> list:
    """Replace SOG values from from_idx onward with new schedule."""
    result = list(old_sog)
    for i, sog in enumerate(new_sog):
        target_idx = from_idx + i
        if target_idx < len(result):
            result[target_idx] = sog
    return result


def _pick_closest_hour(available_hours, target_time):
    """Pick the largest available hour <= target_time, or smallest if none."""
    target = int(target_time)
    candidates = [h for h in available_hours if h <= target]
    if candidates:
        return max(candidates)
    return available_hours[0]


def _safe(val, default):
    """Return default if val is None or NaN."""
    if val is None:
        return default
    try:
        if math.isnan(val):
            return default
    except (TypeError, ValueError):
        pass
    return float(val)

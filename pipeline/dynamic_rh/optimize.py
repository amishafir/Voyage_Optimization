"""
Rolling Horizon optimizer: re-plan the voyage at regular decision points.

At each decision point, builds a sub-voyage (remaining nodes, fresh forecast,
reduced ETA) and calls dynamic_det.optimize() to get the optimal speed schedule.
Executes the plan until the next decision point, then re-plans with a fresher
forecast.

The final output is a stitched speed schedule covering all legs, plus a
decision_points log showing how the plan evolved.
"""

import logging
import time

from dynamic_det.optimize import optimize as dp_optimize

logger = logging.getLogger(__name__)


def optimize(transform_output: dict, config: dict) -> dict:
    """Run rolling horizon optimization.

    Args:
        transform_output: Dict from dynamic_rh.transform().
        config: Full experiment config.

    Returns:
        Dict with: status, planned_fuel_kg, planned_time_h,
        speed_schedule (stitched), computation_time_s, solver,
        decision_points (log of each re-plan).
    """
    ETA = transform_output["ETA"]
    num_legs = transform_output["num_legs"]
    distances = transform_output["distances"]
    headings_deg = transform_output["headings_deg"]
    node_metadata = transform_output["node_metadata"]
    speeds = transform_output["speeds"]
    fcr = transform_output["fcr"]
    ship_params = transform_output["ship_params"]
    weather_grids = transform_output["weather_grids"]
    max_forecast_hours = transform_output["max_forecast_hours"]
    available_sample_hours = transform_output["available_sample_hours"]

    rh_cfg = config["dynamic_rh"]
    replan_freq = rh_cfg["replan_frequency_hours"]

    # Decision points: [0, replan_freq, 2*replan_freq, ...]
    decision_hours = []
    h = 0
    while h < ETA:
        decision_hours.append(h)
        h += replan_freq
    logger.info("RH: %d decision points, replan every %d h", len(decision_hours), replan_freq)

    # State tracking
    current_node_idx = 0
    elapsed_time = 0.0
    elapsed_fuel = 0.0
    committed_legs = []
    decision_log = []

    total_start = time.time()

    for dp_idx, nominal_hour in enumerate(decision_hours):
        if current_node_idx >= num_legs:
            break  # already at destination

        # 1. Pick best available sample_hour <= elapsed_time
        sample_hour = _pick_sample_hour(available_sample_hours, elapsed_time)

        # 2. Build sub-voyage transform dict
        remaining_legs = num_legs - current_node_idx
        remaining_eta = ETA - elapsed_time

        if remaining_eta <= 0:
            logger.warning("RH: No remaining ETA at decision point %d (elapsed=%.1f h)",
                           dp_idx, elapsed_time)
            break

        sub_transform = {
            "ETA": remaining_eta,
            "num_nodes": remaining_legs + 1,
            "num_legs": remaining_legs,
            "speeds": speeds,
            "fcr": fcr,
            "distances": distances[current_node_idx:],
            "headings_deg": headings_deg[current_node_idx:],
            "weather_grid": weather_grids[sample_hour],
            "max_forecast_hour": max_forecast_hours[sample_hour],
            "node_metadata": node_metadata[current_node_idx:],
            "ship_params": ship_params,
            "time_offset": elapsed_time,
        }

        # 3. Run DP on remaining voyage
        dp_result = dp_optimize(sub_transform, config)

        if dp_result.get("status") not in ("Optimal", "Feasible"):
            logger.warning("RH: DP infeasible at decision point %d (node=%d, remaining_eta=%.1f h). "
                           "Trying last decision point with all remaining legs.",
                           dp_idx, current_node_idx, remaining_eta)
            decision_log.append({
                "decision_hour": nominal_hour,
                "actual_hour": round(elapsed_time, 4),
                "sample_hour": sample_hour,
                "node_idx": current_node_idx,
                "legs_committed": 0,
                "elapsed_fuel_kg": round(elapsed_fuel, 4),
                "elapsed_time_h": round(elapsed_time, 4),
                "dp_status": dp_result.get("status", "Infeasible"),
                "dp_solve_time_s": dp_result.get("computation_time_s", 0),
            })
            break

        schedule = dp_result["speed_schedule"]

        # 4. Execute: commit legs that START before next decision hour
        next_decision = decision_hours[dp_idx + 1] if dp_idx + 1 < len(decision_hours) else float("inf")
        time_budget = next_decision - nominal_hour

        # For the last decision point, commit everything
        is_last = dp_idx + 1 >= len(decision_hours)

        legs_this_round = []
        sub_elapsed = 0.0
        sub_fuel = 0.0

        for leg in schedule:
            if not is_last and sub_elapsed >= time_budget:
                break  # don't start a leg past the next decision hour

            # Remap leg index to global
            remapped = dict(leg)
            remapped["leg"] = leg["leg"] + current_node_idx
            legs_this_round.append(remapped)
            sub_elapsed += leg["time_h"]
            sub_fuel += leg["fuel_kg"]

        committed_legs.extend(legs_this_round)

        # 5. Update state
        current_node_idx += len(legs_this_round)
        elapsed_time += sub_elapsed
        elapsed_fuel += sub_fuel

        decision_log.append({
            "decision_hour": nominal_hour,
            "actual_hour": round(elapsed_time - sub_elapsed, 4),
            "sample_hour": sample_hour,
            "node_idx": current_node_idx - len(legs_this_round),
            "legs_committed": len(legs_this_round),
            "elapsed_fuel_kg": round(elapsed_fuel, 4),
            "elapsed_time_h": round(elapsed_time, 4),
            "remaining_legs": num_legs - current_node_idx,
            "remaining_eta_h": round(ETA - elapsed_time, 4),
            "dp_planned_fuel_kg": round(dp_result["planned_fuel_kg"], 4),
            "dp_planned_time_h": round(dp_result["planned_time_h"], 4),
            "dp_status": dp_result["status"],
            "dp_solve_time_s": round(dp_result["computation_time_s"], 4),
        })

        logger.info("RH decision %d: hour=%.1f, SH=%d, node=%d, committed=%d legs, "
                     "fuel=%.2f kg, time=%.2f h",
                     dp_idx, nominal_hour, sample_hour,
                     current_node_idx - len(legs_this_round),
                     len(legs_this_round), sub_fuel, sub_elapsed)

    total_elapsed = time.time() - total_start

    # Verify all legs are covered
    if current_node_idx < num_legs:
        logger.warning("RH: Only covered %d/%d legs. %d legs remaining.",
                       current_node_idx, num_legs, num_legs - current_node_idx)

    total_fuel = sum(l["fuel_kg"] for l in committed_legs)
    total_time = sum(l["time_h"] for l in committed_legs)

    status = "Optimal" if current_node_idx >= num_legs else "Feasible"

    result = {
        "status": status,
        "planned_fuel_kg": total_fuel,
        "planned_time_h": total_time,
        "speed_schedule": committed_legs,
        "computation_time_s": round(total_elapsed, 4),
        "solver": "bellman_dp_rh",
        "decision_points": decision_log,
    }

    logger.info("RH complete: %.2f kg fuel, %.2f h, %d decision points, %.2f s total",
                total_fuel, total_time, len(decision_log), total_elapsed)
    return result


def _pick_sample_hour(available, elapsed_time):
    """Pick the best available sample_hour <= elapsed_time.

    Falls back to the smallest available if none is <= elapsed_time.
    """
    elapsed_int = int(elapsed_time)
    candidates = [s for s in available if s <= elapsed_int]
    if candidates:
        return max(candidates)
    return available[0]

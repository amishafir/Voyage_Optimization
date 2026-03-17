"""
Dynamic Deterministic optimizer: Forward Bellman DP over 279-node graph.

Uses time-varying predicted weather to find the minimum-fuel speed schedule
across 278 legs, subject to an ETA constraint.

Algorithm:
    cost[node=0][t=0] = 0
    For each node i (0..277), each reachable time slot t:
        Look up weather at forecast_hour = min(t * dt, max_forecast_hour)
        For each candidate speed k:
            Compute SOG, travel time, fuel
            Update cost[i+1][t_next] if cheaper
    Find min cost[278][t] for t * dt <= ETA
    Backtrack for per-leg speed choices
"""

import logging
import math
import time

from shared.physics import calculate_speed_over_ground

logger = logging.getLogger(__name__)


def optimize(transform_output: dict, config: dict) -> dict:
    """Solve the DP for minimum-fuel speed schedule.

    Args:
        transform_output: Dict from transform.transform().
        config: Full experiment config.

    Returns:
        Dict with: status, planned_fuel_mt, planned_time_h,
        speed_schedule (278 per-leg dicts), computation_time_s, solver.
    """
    ETA = transform_output["ETA"]
    num_nodes = transform_output["num_nodes"]
    num_legs = transform_output["num_legs"]
    speeds = transform_output["speeds"]
    fcr = transform_output["fcr"]
    distances = transform_output["distances"]
    headings_deg = transform_output["headings_deg"]
    weather_grid = transform_output["weather_grid"]
    max_fh = transform_output["max_forecast_hour"]
    node_meta = transform_output["node_metadata"]
    ship_params = transform_output["ship_params"]
    time_offset = transform_output.get("time_offset", 0)

    dd_cfg = config["dynamic_det"]
    dt = dd_cfg["time_granularity"]  # hours per time slot

    num_speeds = len(speeds)
    # Time slots: enough to cover ETA + buffer for ceil rounding
    max_time_slots = int(math.ceil(ETA / dt)) + int(math.ceil(50 / dt))

    logger.info("DP: %d nodes, %d time slots, %d speeds = %.1fM edges",
                num_nodes, max_time_slots, num_speeds,
                num_legs * max_time_slots * num_speeds / 1e6)

    start_time = time.time()

    # ------------------------------------------------------------------
    # Precompute unit conversions for headings
    # ------------------------------------------------------------------
    headings_rad = [math.radians(h) for h in headings_deg]

    # ------------------------------------------------------------------
    # Forward DP
    # ------------------------------------------------------------------
    INF = float("inf")

    # cost[node][time_slot] = minimum fuel to reach (node, time_slot)
    # parent[node][time_slot] = (prev_time_slot, speed_index)
    # Using dicts of dicts for sparse storage (most states unreachable)
    cost = [{} for _ in range(num_nodes)]
    parent = [{} for _ in range(num_nodes)]

    cost[0][0] = 0.0

    for i in range(num_legs):
        nid = node_meta[i]["node_id"]
        heading_rad = headings_rad[i]
        dist = distances[i]

        for t, fuel_so_far in cost[i].items():
            if fuel_so_far == INF:
                continue

            # Current time in hours
            current_hour = t * dt

            # Forecast hour: clamp to available range (persistence fallback)
            fh = min(int(round(current_hour + time_offset)), max_fh)

            # Look up weather for this node at this forecast hour
            node_wx = weather_grid.get(nid, {})
            wx = node_wx.get(fh)
            if wx is None:
                # Fallback: try nearest available forecast hour
                available = sorted(node_wx.keys())
                if available:
                    closest = min(available, key=lambda h: abs(h - fh))
                    wx = node_wx[closest]
                else:
                    # No weather at all for this node — use calm defaults
                    wx = {
                        "wind_speed_10m_kmh": 0.0,
                        "wind_direction_10m_deg": 0.0,
                        "beaufort_number": 0.0,
                        "wave_height_m": 0.0,
                        "ocean_current_velocity_kmh": 0.0,
                        "ocean_current_direction_deg": 0.0,
                    }

            # Convert weather to physics units
            wind_dir_rad = math.radians(wx["wind_direction_10m_deg"])
            current_knots = wx["ocean_current_velocity_kmh"] / 1.852
            current_dir_rad = math.radians(wx["ocean_current_direction_deg"])
            beaufort = int(round(wx["beaufort_number"]))
            wave_height = wx["wave_height_m"]

            for k in range(num_speeds):
                sog = calculate_speed_over_ground(
                    ship_speed=speeds[k],
                    ocean_current=current_knots,
                    current_direction=current_dir_rad,
                    ship_heading=heading_rad,
                    wind_direction=wind_dir_rad,
                    beaufort_scale=beaufort,
                    wave_height=wave_height,
                    ship_parameters=ship_params,
                )

                # Clamp SOG
                sog = max(sog, 0.1)

                travel_time = dist / sog  # hours
                leg_fuel = fcr[k] * travel_time

                arrival_time = current_hour + travel_time
                t_next = int(math.ceil(arrival_time / dt))

                if t_next >= max_time_slots:
                    continue  # exceeds time horizon

                new_cost = fuel_so_far + leg_fuel
                next_node = i + 1

                if t_next not in cost[next_node] or new_cost < cost[next_node][t_next]:
                    cost[next_node][t_next] = new_cost
                    parent[next_node][t_next] = (t, k)

    # ------------------------------------------------------------------
    # Find optimal arrival at destination
    # ------------------------------------------------------------------
    dest = num_legs  # node index 278 (0-based)
    lambda_val = config.get("ship", {}).get("eta_penalty_mt_per_hour", None)
    soft_eta = lambda_val is not None and lambda_val != float("inf")

    best_t = None
    best_fuel = INF
    best_cost = INF

    for t, fuel in cost[dest].items():
        arrival = t * dt
        delay = max(0.0, arrival - ETA)
        if soft_eta:
            total_cost = fuel + lambda_val * delay
        else:
            if delay > 1e-6:
                continue  # hard constraint: skip late arrivals
            total_cost = fuel
        if total_cost < best_cost:
            best_cost = total_cost
            best_fuel = fuel
            best_t = t

    elapsed = time.time() - start_time

    status = "Optimal"
    delay_hours = 0.0

    if best_t is None:
        if soft_eta:
            # Soft constraint should always find something if any path exists
            logger.error("DP: No reachable path even with soft ETA (λ=%s)", lambda_val)
            return {
                "status": "Infeasible",
                "computation_time_s": elapsed,
                "solver": "bellman_dp",
            }
        # Hard ETA fallback: find min-fuel path regardless of arrival time
        for t, fuel in cost[dest].items():
            if fuel < best_fuel:
                best_fuel = fuel
                best_t = t
        if best_t is None:
            logger.warning("DP: No reachable path to destination")
            return {
                "status": "Infeasible",
                "computation_time_s": elapsed,
                "solver": "bellman_dp",
            }
        status = "ETA_relaxed"
        logger.warning("DP: No path within ETA=%d h — relaxed to %.1f h (soft-ETA)",
                       ETA, best_t * dt)

    delay_hours = max(0.0, best_t * dt - ETA)

    planned_time = best_t * dt
    logger.info("DP %s: %.2f mt fuel, %.1f h, solved in %.2f s",
                status.lower(), best_fuel, planned_time, elapsed)

    # ------------------------------------------------------------------
    # Backtrack to extract per-leg schedule
    # ------------------------------------------------------------------
    schedule = []
    t_cur = best_t

    for i in range(num_legs - 1, -1, -1):
        t_prev, k = parent[i + 1][t_cur]

        nid = node_meta[i]["node_id"]
        seg = node_meta[i]["segment"]
        dist = distances[i]

        # Recompute SOG for the schedule record
        current_hour = t_prev * dt
        fh = min(int(round(current_hour + time_offset)), max_fh)
        node_wx = weather_grid.get(nid, {})
        wx = node_wx.get(fh)
        if wx is None:
            available = sorted(node_wx.keys())
            if available:
                closest = min(available, key=lambda h: abs(h - fh))
                wx = node_wx[closest]
            else:
                wx = {
                    "wind_speed_10m_kmh": 0.0, "wind_direction_10m_deg": 0.0,
                    "beaufort_number": 0.0, "wave_height_m": 0.0,
                    "ocean_current_velocity_kmh": 0.0, "ocean_current_direction_deg": 0.0,
                }

        wind_dir_rad = math.radians(wx["wind_direction_10m_deg"])
        current_knots = wx["ocean_current_velocity_kmh"] / 1.852
        current_dir_rad = math.radians(wx["ocean_current_direction_deg"])
        beaufort = int(round(wx["beaufort_number"]))
        wave_height = wx["wave_height_m"]

        sog = calculate_speed_over_ground(
            ship_speed=speeds[k],
            ocean_current=current_knots,
            current_direction=current_dir_rad,
            ship_heading=headings_rad[i],
            wind_direction=wind_dir_rad,
            beaufort_scale=beaufort,
            wave_height=wave_height,
            ship_parameters=ship_params,
        )
        sog = max(sog, 0.1)

        leg_time = dist / sog
        leg_fuel = fcr[k] * leg_time

        schedule.append({
            "leg": i,
            "node_id": nid,
            "segment": seg,
            "sws_knots": speeds[k],
            "sog_knots": round(sog, 4),
            "distance_nm": round(dist, 4),
            "time_h": round(leg_time, 4),
            "fuel_mt": round(leg_fuel, 4),
        })

        t_cur = t_prev

    schedule.reverse()

    # Verify totals from schedule
    total_fuel = sum(e["fuel_mt"] for e in schedule)
    total_time = sum(e["time_h"] for e in schedule)

    status = "Optimal" if abs(best_fuel - total_fuel) < 1.0 else "Feasible"

    # Recompute delay from actual schedule time (more precise than slot-based)
    delay_hours = max(0.0, total_time - ETA)

    result = {
        "status": status,
        "planned_fuel_mt": total_fuel,
        "planned_time_h": total_time,
        "planned_delay_h": delay_hours,
        "speed_schedule": schedule,
        "computation_time_s": round(elapsed, 4),
        "solver": "bellman_dp",
    }

    if soft_eta:
        result["planned_total_cost_mt"] = total_fuel + lambda_val * delay_hours
    else:
        result["planned_total_cost_mt"] = total_fuel

    return result

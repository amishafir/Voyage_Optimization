"""
Dynamic Deterministic optimizer: Forward Bellman DP over 279-node graph.

Uses time-varying predicted weather to find the minimum-fuel speed schedule
across 278 legs, subject to an ETA constraint.

Two solver modes controlled by ``speed_lock_hours`` config:

* ``null`` (default) — free Bellman DP: speed can change at every leg.
* integer (e.g. 6) — locked DP: speed is fixed for each N-hour block,
  matching Luo et al. 2024's multistage structure.

Algorithm (free):
    cost[node=0][t=0] = 0
    For each node i (0..277), each reachable time slot t:
        Look up weather at forecast_hour = min(t * dt, max_forecast_hour)
        For each candidate speed k:
            Compute SOG, travel time, fuel
            Update cost[i+1][t_next] if cheaper
    Find min cost[278][t] for t * dt <= ETA
    Backtrack for per-leg speed choices

Algorithm (locked):
    Same state space (leg, time_slot), but each transition simulates
    an entire lock-block: sail at fixed SWS for lock_hours, traversing
    multiple legs.  Solved via Dijkstra (edges are non-negative, states
    only reachable as block boundaries).
"""

import heapq
import logging
import math
import time

from shared.physics import calculate_speed_over_ground

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------
# Default calm weather (fallback when no data available)
# ------------------------------------------------------------------
_CALM_WX = {
    "wind_speed_10m_kmh": 0.0,
    "wind_direction_10m_deg": 0.0,
    "beaufort_number": 0.0,
    "wave_height_m": 0.0,
    "ocean_current_velocity_kmh": 0.0,
    "ocean_current_direction_deg": 0.0,
}


def _lookup_weather(weather_grid, nid, fh):
    """Look up weather for *nid* at forecast hour *fh* with fallback."""
    node_wx = weather_grid.get(nid, {})
    wx = node_wx.get(fh)
    if wx is not None:
        return wx
    available = sorted(node_wx.keys())
    if available:
        closest = min(available, key=lambda h: abs(h - fh))
        return node_wx[closest]
    return _CALM_WX


def _sog_for(sws, wx, heading_rad, ship_params):
    """Compute SOG from SWS + weather, clamped to >= 0.1 kn."""
    sog = calculate_speed_over_ground(
        ship_speed=sws,
        ocean_current=wx["ocean_current_velocity_kmh"] / 1.852,
        current_direction=math.radians(wx["ocean_current_direction_deg"]),
        ship_heading=heading_rad,
        wind_direction=math.radians(wx["wind_direction_10m_deg"]),
        beaufort_scale=int(round(wx["beaufort_number"])),
        wave_height=wx["wave_height_m"],
        ship_parameters=ship_params,
    )
    return max(sog, 0.1)


def optimize(transform_output: dict, config: dict) -> dict:
    """Solve the DP for minimum-fuel speed schedule.

    Args:
        transform_output: Dict from transform.transform().
        config: Full experiment config.

    Returns:
        Dict with: status, planned_fuel_mt, planned_time_h,
        speed_schedule (278 per-leg dicts), computation_time_s, solver.
    """
    dd_cfg = config["dynamic_det"]
    lock_hours = dd_cfg.get("speed_lock_hours")
    solver = dd_cfg.get("solver")

    if solver == "luo_lattice":
        from dynamic_det.luo2024_reconstruction import optimize_luo_lattice
        return optimize_luo_lattice(transform_output, config)
    if solver == "fast_locked":
        from dynamic_det.luo_style_fast import optimize_fast_locked
        return optimize_fast_locked(transform_output, config)

    if lock_hours is not None:
        return _optimize_locked(transform_output, config)
    return _optimize_free(transform_output, config)


# ======================================================================
# Free Bellman DP — speed can change at every leg
# ======================================================================

def _optimize_free(transform_output: dict, config: dict) -> dict:
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
    max_time_slots = int(math.ceil(ETA / dt)) + int(math.ceil(50 / dt))

    logger.info("Free DP: %d nodes, %d time slots, %d speeds = %.1fM edges",
                num_nodes, max_time_slots, num_speeds,
                num_legs * max_time_slots * num_speeds / 1e6)

    start_time = time.time()

    headings_rad = [math.radians(h) for h in headings_deg]

    # Forward DP
    INF = float("inf")
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

            current_hour = t * dt
            fh = min(int(round(current_hour + time_offset)), max_fh)
            wx = _lookup_weather(weather_grid, nid, fh)

            for k in range(num_speeds):
                sog = _sog_for(speeds[k], wx, heading_rad, ship_params)

                travel_time = dist / sog
                leg_fuel = fcr[k] * travel_time

                arrival_time = current_hour + travel_time
                t_next = int(math.ceil(arrival_time / dt))

                if t_next >= max_time_slots:
                    continue

                new_cost = fuel_so_far + leg_fuel
                next_node = i + 1

                if t_next not in cost[next_node] or new_cost < cost[next_node][t_next]:
                    cost[next_node][t_next] = new_cost
                    parent[next_node][t_next] = (t, k)

    # Find optimal arrival
    elapsed = time.time() - start_time
    best_t, best_fuel, status = _find_best_arrival(
        cost, num_legs, ETA, dt, config, elapsed)

    if best_t is None:
        return {"status": "Infeasible", "computation_time_s": elapsed,
                "solver": "bellman_dp_free"}

    # Backtrack
    schedule = _backtrack_free(
        parent, best_t, num_legs, speeds, fcr, distances, headings_rad,
        weather_grid, max_fh, node_meta, ship_params, time_offset, dt)

    return _build_result(schedule, best_fuel, ETA, config, elapsed,
                         solver="bellman_dp_free")


# ======================================================================
# Locked DP — speed fixed per N-hour block (Luo-style)
# ======================================================================

def _simulate_block(start_leg, start_hour, sws, fcr_val, lock_hours,
                    distances, headings_rad, weather_grid, max_fh,
                    node_meta, ship_params, time_offset, num_legs):
    """Simulate one lock-block at fixed SWS.

    Returns (fuel, time_elapsed, end_leg, per_leg_details).
    per_leg_details is a list of dicts for schedule reconstruction.
    """
    sim_fuel = 0.0
    sim_time = 0.0
    sim_leg = start_leg
    details = []

    while sim_leg < num_legs:
        actual_time = start_hour + sim_time
        fh = min(int(round(actual_time + time_offset)), max_fh)
        nid = node_meta[sim_leg]["node_id"]
        wx = _lookup_weather(weather_grid, nid, fh)

        sog = _sog_for(sws, wx, headings_rad[sim_leg], ship_params)

        travel = distances[sim_leg] / sog
        leg_fuel = fcr_val * travel

        details.append({
            "leg": sim_leg,
            "node_id": nid,
            "segment": node_meta[sim_leg]["segment"],
            "sws_knots": sws,
            "sog_knots": round(sog, 4),
            "distance_nm": round(distances[sim_leg], 4),
            "time_h": round(travel, 4),
            "fuel_mt": round(leg_fuel, 4),
        })

        sim_fuel += leg_fuel
        sim_time += travel
        sim_leg += 1

        # Block time exhausted — finish the current leg, then stop
        if sim_time >= lock_hours:
            break

    return sim_fuel, sim_time, sim_leg, details


def _optimize_locked(transform_output: dict, config: dict) -> dict:
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
    dt = dd_cfg["time_granularity"]
    lock_hours = float(dd_cfg["speed_lock_hours"])

    num_speeds = len(speeds)
    max_time_slots = int(math.ceil(ETA / dt)) + int(math.ceil(50 / dt))

    logger.info("Locked DP (lock=%gh): %d nodes, %d speeds",
                lock_hours, num_nodes, num_speeds)

    start_time = time.time()

    headings_rad = [math.radians(h) for h in headings_deg]

    # ------------------------------------------------------------------
    # Dijkstra over block-boundary states (leg, time_slot)
    # ------------------------------------------------------------------
    INF = float("inf")
    cost = [{} for _ in range(num_nodes)]
    parent = [{} for _ in range(num_nodes)]  # (prev_leg, prev_t, speed_idx)
    cost[0][0] = 0.0

    # Priority queue: (cost_so_far, time_slot, leg_index)
    pq = [(0.0, 0, 0)]

    while pq:
        fuel_so_far, t, leg_i = heapq.heappop(pq)

        # Skip if we already found a better path to this state
        if leg_i >= num_nodes:
            continue
        current_best = cost[leg_i].get(t)
        if current_best is not None and fuel_so_far > current_best:
            continue

        # Reached destination
        if leg_i >= num_legs:
            continue

        current_hour = t * dt

        for k in range(num_speeds):
            block_fuel, block_time, end_leg, _ = _simulate_block(
                leg_i, current_hour, speeds[k], fcr[k], lock_hours,
                distances, headings_rad, weather_grid, max_fh,
                node_meta, ship_params, time_offset, num_legs)

            t_next = int(math.ceil((current_hour + block_time) / dt))
            if t_next >= max_time_slots:
                continue

            new_cost = fuel_so_far + block_fuel

            if t_next not in cost[end_leg] or new_cost < cost[end_leg][t_next]:
                cost[end_leg][t_next] = new_cost
                parent[end_leg][t_next] = (leg_i, t, k)
                heapq.heappush(pq, (new_cost, t_next, end_leg))

    # Find optimal arrival
    elapsed = time.time() - start_time
    best_t, best_fuel, status = _find_best_arrival(
        cost, num_legs, ETA, dt, config, elapsed)

    if best_t is None:
        return {"status": "Infeasible", "computation_time_s": elapsed,
                "solver": "dijkstra_dp_locked"}

    # ------------------------------------------------------------------
    # Backtrack — reconstruct per-leg schedule by re-simulating blocks
    # ------------------------------------------------------------------
    blocks = []
    cur_leg, cur_t = num_legs, best_t

    while cur_leg > 0 or cur_t > 0:
        prev_leg, prev_t, k = parent[cur_leg][cur_t]
        blocks.append((prev_leg, prev_t, k))
        cur_leg, cur_t = prev_leg, prev_t

    blocks.reverse()

    schedule = []
    for (blk_leg, blk_t, k) in blocks:
        blk_hour = blk_t * dt
        _, _, _, details = _simulate_block(
            blk_leg, blk_hour, speeds[k], fcr[k], lock_hours,
            distances, headings_rad, weather_grid, max_fh,
            node_meta, ship_params, time_offset, num_legs)
        schedule.extend(details)

    return _build_result(schedule, best_fuel, ETA, config, elapsed,
                         solver="dijkstra_dp_locked")


# ======================================================================
# Shared helpers
# ======================================================================

def _find_best_arrival(cost, num_legs, ETA, dt, config, elapsed):
    """Find the min-cost arrival at destination across all time slots."""
    dest = num_legs
    lambda_val = config.get("ship", {}).get("eta_penalty_mt_per_hour", None)
    soft_eta = lambda_val is not None and lambda_val != float("inf")

    INF = float("inf")
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
                continue
            total_cost = fuel
        if total_cost < best_cost:
            best_cost = total_cost
            best_fuel = fuel
            best_t = t

    status = "Optimal"

    if best_t is None:
        if soft_eta:
            logger.error("DP: No reachable path even with soft ETA (λ=%s)", lambda_val)
            return None, INF, "Infeasible"
        # Hard ETA fallback
        for t, fuel in cost[dest].items():
            if fuel < best_fuel:
                best_fuel = fuel
                best_t = t
        if best_t is None:
            logger.warning("DP: No reachable path to destination")
            return None, INF, "Infeasible"
        status = "ETA_relaxed"
        logger.warning("DP: No path within ETA=%d h — relaxed to %.1f h",
                       ETA, best_t * dt)

    logger.info("DP %s: %.2f mt fuel, %.1f h, solved in %.2f s",
                status.lower(), best_fuel, best_t * dt, elapsed)
    return best_t, best_fuel, status


def _backtrack_free(parent, best_t, num_legs, speeds, fcr, distances,
                    headings_rad, weather_grid, max_fh, node_meta,
                    ship_params, time_offset, dt):
    """Backtrack the free DP to extract per-leg schedule."""
    schedule = []
    t_cur = best_t

    for i in range(num_legs - 1, -1, -1):
        t_prev, k = parent[i + 1][t_cur]

        nid = node_meta[i]["node_id"]
        dist = distances[i]

        current_hour = t_prev * dt
        fh = min(int(round(current_hour + time_offset)), max_fh)
        wx = _lookup_weather(weather_grid, nid, fh)
        sog = _sog_for(speeds[k], wx, headings_rad[i], ship_params)

        leg_time = dist / sog
        leg_fuel = fcr[k] * leg_time

        schedule.append({
            "leg": i,
            "node_id": nid,
            "segment": node_meta[i]["segment"],
            "sws_knots": speeds[k],
            "sog_knots": round(sog, 4),
            "distance_nm": round(dist, 4),
            "time_h": round(leg_time, 4),
            "fuel_mt": round(leg_fuel, 4),
        })
        t_cur = t_prev

    schedule.reverse()
    return schedule


def _build_result(schedule, dp_fuel, ETA, config, elapsed, solver):
    """Assemble the result dict from a per-leg schedule."""
    total_fuel = sum(e["fuel_mt"] for e in schedule)
    total_time = sum(e["time_h"] for e in schedule)
    delay_hours = max(0.0, total_time - ETA)

    status = "Optimal" if abs(dp_fuel - total_fuel) < 1.0 else "Feasible"

    lambda_val = config.get("ship", {}).get("eta_penalty_mt_per_hour", None)
    soft_eta = lambda_val is not None and lambda_val != float("inf")

    result = {
        "status": status,
        "planned_fuel_mt": total_fuel,
        "planned_time_h": total_time,
        "planned_delay_h": delay_hours,
        "speed_schedule": schedule,
        "computation_time_s": round(elapsed, 4),
        "solver": solver,
    }

    if soft_eta:
        result["planned_total_cost_mt"] = total_fuel + lambda_val * delay_hours
    else:
        result["planned_total_cost_mt"] = total_fuel

    return result

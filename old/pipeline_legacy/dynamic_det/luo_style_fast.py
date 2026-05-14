"""
Fast Luo-style locked DP with coarser state and memoized block simulation.

Same *policy* as ``optimize._optimize_locked`` (fix SWS for N-hour blocks,
let SOG/distance vary inside the block), but restructured for speed:

* State uses ``dt_locked`` (default 0.5 h) instead of inheriting the free
  DP's ``time_granularity``. The locked DP only makes decisions at block
  boundaries, so sub-hour resolution on the outer state serves no purpose.
* ``_simulate_block`` is memoized on ``(start_leg, time_bucket, sws_idx)``.
  The weather lookup uses ``int(round(actual_time))``, so two outer states
  at the same bucket produce identical block sims by construction.

Expected to match ``_optimize_locked`` results within rounding noise while
running ~50-100x faster on the Route D [9,15] kn matrix.
"""

import heapq
import logging
import math
import time

from shared.physics import calculate_speed_over_ground

logger = logging.getLogger(__name__)


_CALM_WX = {
    "wind_speed_10m_kmh": 0.0,
    "wind_direction_10m_deg": 0.0,
    "beaufort_number": 0.0,
    "wave_height_m": 0.0,
    "ocean_current_velocity_kmh": 0.0,
    "ocean_current_direction_deg": 0.0,
}


def _lookup_weather(weather_grid, nid, fh):
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


def optimize_fast_locked(transform_output: dict, config: dict) -> dict:
    """Fast locked DP: coarser state + memoized block sim."""
    dd_cfg = config["dynamic_det"]
    lock_hours = float(dd_cfg["speed_lock_hours"])
    # Default dt_locked = 0.1 h: balances ceiling-rounding drift over the
    # ~27 block boundaries (27 * 0.05h = 1.35h phantom, small relative to ETA)
    # against runtime. Set explicitly to match free DP's dt for a strict
    # legacy-match sanity check (slower but fuel-identical).
    dt_locked = float(dd_cfg.get("dt_locked", 0.1))

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

    num_speeds = len(speeds)
    max_buckets = int(math.ceil(ETA / dt_locked)) + int(math.ceil(50 / dt_locked))
    headings_rad = [math.radians(h) for h in headings_deg]

    logger.info(
        "Fast locked DP: lock=%gh, dt_locked=%gh, %d nodes, %d speeds, %d max buckets",
        lock_hours, dt_locked, num_nodes, num_speeds, max_buckets,
    )

    start_time = time.time()

    # ------------------------------------------------------------------
    # Memoized block simulation
    # ------------------------------------------------------------------
    block_cache = {}
    cache_stats = {"hits": 0, "misses": 0}

    def simulate_block(start_leg, t_bucket, sws_idx):
        key = (start_leg, t_bucket, sws_idx)
        cached = block_cache.get(key)
        if cached is not None:
            cache_stats["hits"] += 1
            return cached
        cache_stats["misses"] += 1

        start_hour = t_bucket * dt_locked
        sws = speeds[sws_idx]
        fcr_val = fcr[sws_idx]

        sim_fuel = 0.0
        sim_time = 0.0
        sim_leg = start_leg

        while sim_leg < num_legs:
            actual_time = start_hour + sim_time
            fh = min(int(round(actual_time + time_offset)), max_fh)
            nid = node_meta[sim_leg]["node_id"]
            wx = _lookup_weather(weather_grid, nid, fh)

            sog = _sog_for(sws, wx, headings_rad[sim_leg], ship_params)

            travel = distances[sim_leg] / sog
            leg_fuel = fcr_val * travel

            sim_fuel += leg_fuel
            sim_time += travel
            sim_leg += 1

            if sim_time >= lock_hours:
                break

        result = (sim_fuel, sim_time, sim_leg)
        block_cache[key] = result
        return result

    def simulate_block_with_details(start_leg, t_bucket, sws_idx):
        """Re-run a block and collect per-leg details (used only for backtracking)."""
        start_hour = t_bucket * dt_locked
        sws = speeds[sws_idx]
        fcr_val = fcr[sws_idx]

        details = []
        sim_time = 0.0
        sim_leg = start_leg

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

            sim_time += travel
            sim_leg += 1

            if sim_time >= lock_hours:
                break

        return details

    # ------------------------------------------------------------------
    # Dijkstra over (leg, time_bucket)
    # ------------------------------------------------------------------
    INF = float("inf")
    cost = {(0, 0): 0.0}
    parent = {}  # (leg, bucket) -> (prev_leg, prev_bucket, sws_idx)
    pq = [(0.0, 0, 0)]  # (fuel, bucket, leg)

    while pq:
        fuel_so_far, t_bucket, leg_i = heapq.heappop(pq)

        if cost.get((leg_i, t_bucket), INF) < fuel_so_far - 1e-9:
            continue
        if leg_i >= num_legs:
            continue

        for k in range(num_speeds):
            block_fuel, block_time, end_leg = simulate_block(leg_i, t_bucket, k)

            if block_time <= 0:
                continue

            new_hour = t_bucket * dt_locked + block_time
            new_bucket = int(math.ceil(new_hour / dt_locked))
            if new_bucket >= max_buckets:
                continue

            new_cost = fuel_so_far + block_fuel
            state = (end_leg, new_bucket)
            if new_cost < cost.get(state, INF):
                cost[state] = new_cost
                parent[state] = (leg_i, t_bucket, k)
                heapq.heappush(pq, (new_cost, new_bucket, end_leg))

    elapsed = time.time() - start_time

    # ------------------------------------------------------------------
    # Find best arrival at destination within ETA
    # ------------------------------------------------------------------
    lambda_val = config.get("ship", {}).get("eta_penalty_mt_per_hour", None)
    soft_eta = lambda_val is not None and lambda_val != float("inf")

    best_bucket = None
    best_fuel = INF
    best_total = INF

    for (leg, bucket), fuel in cost.items():
        if leg != num_legs:
            continue
        arrival = bucket * dt_locked
        delay = max(0.0, arrival - ETA)
        if soft_eta:
            total = fuel + lambda_val * delay
        else:
            if delay > 1e-6:
                continue
            total = fuel
        if total < best_total:
            best_total = total
            best_fuel = fuel
            best_bucket = bucket

    status = "Optimal"
    if best_bucket is None:
        if soft_eta:
            logger.error("Fast locked DP: no reachable path (lambda=%s)", lambda_val)
            return {"status": "Infeasible",
                    "computation_time_s": round(elapsed, 4),
                    "solver": "dijkstra_dp_fast_locked"}
        # Hard ETA fallback: accept earliest overshoot
        for (leg, bucket), fuel in cost.items():
            if leg != num_legs:
                continue
            if fuel < best_fuel:
                best_fuel = fuel
                best_bucket = bucket
        if best_bucket is None:
            logger.warning("Fast locked DP: no path to destination")
            return {"status": "Infeasible",
                    "computation_time_s": round(elapsed, 4),
                    "solver": "dijkstra_dp_fast_locked"}
        status = "ETA_relaxed"
        logger.warning("Fast locked DP: ETA relaxed to %.1f h",
                       best_bucket * dt_locked)

    logger.info(
        "Fast locked DP %s: %.2f mt, %.1f h, %d states, cache %d/%d hit-rate=%.1f%%, %.2fs",
        status.lower(), best_fuel, best_bucket * dt_locked, len(cost),
        cache_stats["hits"], cache_stats["hits"] + cache_stats["misses"],
        100.0 * cache_stats["hits"] / max(1, cache_stats["hits"] + cache_stats["misses"]),
        elapsed,
    )

    # ------------------------------------------------------------------
    # Backtrack and expand per-leg schedule
    # ------------------------------------------------------------------
    blocks = []
    cur = (num_legs, best_bucket)
    while cur[0] > 0 or cur[1] > 0:
        prev_leg, prev_bucket, k = parent[cur]
        blocks.append((prev_leg, prev_bucket, k))
        cur = (prev_leg, prev_bucket)
    blocks.reverse()

    schedule = []
    for (blk_leg, blk_bucket, k) in blocks:
        schedule.extend(simulate_block_with_details(blk_leg, blk_bucket, k))

    total_fuel = sum(e["fuel_mt"] for e in schedule)
    total_time = sum(e["time_h"] for e in schedule)
    delay_hours = max(0.0, total_time - ETA)
    if status == "Optimal" and abs(best_fuel - total_fuel) >= 1.0:
        status = "Feasible"

    result = {
        "status": status,
        "planned_fuel_mt": total_fuel,
        "planned_time_h": total_time,
        "planned_delay_h": delay_hours,
        "speed_schedule": schedule,
        "computation_time_s": round(elapsed, 4),
        "solver": "dijkstra_dp_fast_locked",
    }
    if soft_eta:
        result["planned_total_cost_mt"] = total_fuel + lambda_val * delay_hours
    else:
        result["planned_total_cost_mt"] = total_fuel
    return result

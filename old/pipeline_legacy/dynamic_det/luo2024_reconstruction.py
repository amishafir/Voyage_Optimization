"""
Faithful reconstruction of Luo et al. 2024's DP architecture.

Builds a 2D (distance, time) lattice and finds the minimum-fuel path via
Dijkstra. Unlike ``luo_style_fast``, which imposes a 6h speed lock on our
explicit-SWS framework, this module rebuilds Luo's graph geometry from
scratch: speed is *implicit* in the edge slope and the discretization
forces Δv = ζ/T.

Lattice structure
-----------------
Nodes:      (k, j) where k is a distance cell (kζ nm from origin) and j
            is a stage index (time j*T hours from departure).
Edges:      (k_a, j) -> (k_b, j+1) with k_b > k_a, implied ground speed
            v = (k_b - k_a)*ζ / T.

Weather model
-------------
One weather value per (cell, stage) at the stage's midpoint time. An
edge picks up weather at its *starting cell* — this matches Luo's
coarse spatial/temporal granularity while avoiding cross-boundary
averaging headaches. Switch via ``lattice_weather_mode``:

* ``"start"`` (default) — weather at (k_a, j)
* ``"avg"``             — average weather across cells (k_a, k_a+1, ..., k_b-1)

Speed interpretation
--------------------
Luo's lattice forces the ship to arrive at (k_b, j+1), so v *must* be
interpreted as SOG — otherwise the arrival point is inconsistent with
weather-driven slip. We compute the required SWS via our inverse:

    SWS_required = calculate_sws_from_sog(target_sog=v, weather=avg_wx)
    fuel         = FCR(SWS_required) * T

Set ``v_interpretation: "sws"`` to reproduce the simpler (inconsistent)
reading where fuel = FCR(v) * T with no weather dependence.

FCR
---
Cubic ``0.000706 × SWS³``. Using ANN-based FCR (Luo's actual) would
confound the architectural comparison per Exp 1 Section 2.3.
"""

import heapq
import logging
import math
import time

from shared.physics import (
    calculate_speed_over_ground,
    calculate_fuel_consumption_rate,
    calculate_sws_from_sog,
)

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


def _circular_mean_rad(angles_rad):
    if not angles_rad:
        return 0.0
    s = sum(math.sin(a) for a in angles_rad) / len(angles_rad)
    c = sum(math.cos(a) for a in angles_rad) / len(angles_rad)
    return math.atan2(s, c)


def _average_weather(wx_list):
    """Average a list of weather dicts, using circular mean for directions."""
    if not wx_list:
        return _CALM_WX
    scalar_fields = ["wind_speed_10m_kmh", "beaufort_number",
                     "wave_height_m", "ocean_current_velocity_kmh"]
    dir_fields = ["wind_direction_10m_deg", "ocean_current_direction_deg"]

    avg = {}
    n = len(wx_list)
    for f in scalar_fields:
        avg[f] = sum(w[f] for w in wx_list) / n
    for f in dir_fields:
        rads = [math.radians(w[f]) for w in wx_list]
        avg[f] = math.degrees(_circular_mean_rad(rads)) % 360
    return avg


def optimize_luo_lattice(transform_output: dict, config: dict) -> dict:
    """Solve Luo's (distance, time) lattice via Dijkstra."""
    dd_cfg = config["dynamic_det"]
    ship_cfg = config["ship"]

    zeta = float(dd_cfg.get("lattice_zeta_nm", 1.0))
    stage_T = float(dd_cfg.get("lattice_stage_hours", 6.0))
    allow_partial = bool(dd_cfg.get("lattice_allow_partial_final", True))
    v_interp = dd_cfg.get("v_interpretation", "sog")
    weather_mode = dd_cfg.get("lattice_weather_mode", "start")

    ETA = transform_output["ETA"]
    num_nodes = transform_output["num_nodes"]
    num_legs = transform_output["num_legs"]
    distances = transform_output["distances"]
    headings_deg = transform_output["headings_deg"]
    weather_grid = transform_output["weather_grid"]
    max_fh = transform_output["max_forecast_hour"]
    node_meta = transform_output["node_metadata"]
    ship_params = transform_output["ship_params"]
    time_offset = transform_output.get("time_offset", 0)

    v_min, v_max = ship_cfg["speed_range_knots"]
    lambda_val = ship_cfg.get("eta_penalty_mt_per_hour", None)
    soft_eta = lambda_val is not None and lambda_val != float("inf")

    # ------------------------------------------------------------------
    # Route -> cumulative distances
    # ------------------------------------------------------------------
    cum_dist = [0.0]
    for d in distances:
        cum_dist.append(cum_dist[-1] + d)
    total_distance = cum_dist[-1]

    K_total = int(round(total_distance / zeta))
    J_full = int(math.floor(ETA / stage_T))
    final_duration = ETA - J_full * stage_T
    J_max = J_full + 1 if (allow_partial and final_duration > 1e-6) else J_full

    # Step bounds for full stages and partial final
    min_step_full = max(1, int(math.floor(v_min * stage_T / zeta)))
    max_step_full = int(math.ceil(v_max * stage_T / zeta))
    if allow_partial and final_duration > 1e-6:
        min_step_partial = max(1, int(math.floor(v_min * final_duration / zeta)))
        max_step_partial = int(math.ceil(v_max * final_duration / zeta))
    else:
        min_step_partial = max_step_partial = 0

    logger.info(
        "Luo lattice: K=%d cells (zeta=%g nm, L=%.1f nm), J=%d stages "
        "(T=%g h, ETA=%.1f h, partial=%.2f h, v_interp=%s)",
        K_total, zeta, total_distance, J_max, stage_T, ETA,
        final_duration, v_interp,
    )

    # ------------------------------------------------------------------
    # Cell -> nearest waypoint index (for weather/heading lookup)
    # ------------------------------------------------------------------
    headings_rad = [math.radians(h) for h in headings_deg]

    cell_to_wp = []
    wp_i = 0
    for k in range(K_total + 1):
        target = k * zeta
        while wp_i + 1 < num_nodes and cum_dist[wp_i + 1] < target:
            wp_i += 1
        if wp_i + 1 < num_nodes:
            if abs(cum_dist[wp_i + 1] - target) < abs(cum_dist[wp_i] - target):
                cell_to_wp.append(wp_i + 1)
            else:
                cell_to_wp.append(wp_i)
        else:
            cell_to_wp.append(wp_i)

    def _cell_heading_rad(k):
        wp = cell_to_wp[k]
        return headings_rad[min(wp, num_legs - 1)]

    def _cell_weather(k, j, duration):
        wp = cell_to_wp[k]
        nid = node_meta[wp]["node_id"]
        fh_mid = min(int(round(j * stage_T + duration / 2 + time_offset)), max_fh)
        return _lookup_weather(weather_grid, nid, fh_mid)

    # ------------------------------------------------------------------
    # SOG lookup tables per (k, j) — used to invert SOG -> SWS fast
    # ------------------------------------------------------------------
    sws_samples = [v_min - 2, v_min - 1, v_min, v_min + 1, v_min + 2, v_min + 3,
                   v_min + 4, v_min + 5,
                   v_max - 2, v_max - 1, v_max, v_max + 1, v_max + 2]
    # Dedupe + sort
    sws_samples = sorted(set(max(1.0, s) for s in sws_samples))

    sog_table_cache = {}

    def _get_sog_table(k, j, duration):
        key = (k, j)
        cached = sog_table_cache.get(key)
        if cached is not None:
            return cached
        wx = _cell_weather(k, j, duration)
        heading = _cell_heading_rad(k)
        sogs = []
        for s in sws_samples:
            sog = calculate_speed_over_ground(
                ship_speed=s,
                ocean_current=wx["ocean_current_velocity_kmh"] / 1.852,
                current_direction=math.radians(wx["ocean_current_direction_deg"]),
                ship_heading=heading,
                wind_direction=math.radians(wx["wind_direction_10m_deg"]),
                beaufort_scale=int(round(wx["beaufort_number"])),
                wave_height=wx["wave_height_m"],
                ship_parameters=ship_params,
            )
            sogs.append(max(sog, 0.1))
        entry = (sws_samples, sogs, wx, heading)
        sog_table_cache[key] = entry
        return entry

    def _sws_from_sog_fast(target_sog, k, j, duration):
        samples, sogs, wx, heading = _get_sog_table(k, j, duration)
        # Linear interpolation between bracketing samples
        if target_sog <= sogs[0]:
            return max(samples[0] * target_sog / sogs[0], 1.0)
        if target_sog >= sogs[-1]:
            return samples[-1] * target_sog / sogs[-1]
        for i in range(len(sogs) - 1):
            lo, hi = sogs[i], sogs[i + 1]
            if lo <= target_sog <= hi:
                if hi - lo < 1e-9:
                    return samples[i]
                frac = (target_sog - lo) / (hi - lo)
                return samples[i] + frac * (samples[i + 1] - samples[i])
        return target_sog  # fallback

    # ------------------------------------------------------------------
    # Edge fuel
    # ------------------------------------------------------------------
    def _edge_fuel_and_sws(k_a, k_b, j, duration):
        distance = (k_b - k_a) * zeta
        v_sog = distance / duration  # ground speed implied by lattice

        if v_interp == "sws":
            sws = v_sog
        else:  # "sog" — physically consistent
            if weather_mode == "avg":
                wx_list = [_cell_weather(kk, j, duration)
                           for kk in range(k_a, min(k_b, K_total + 1))]
                wx = _average_weather(wx_list)
                # Fall back to full inverse (no cached table for averaged weather)
                heading_list = [_cell_heading_rad(kk)
                                for kk in range(k_a, min(k_b, K_total + 1))]
                heading_deg = math.degrees(_circular_mean_rad(heading_list))
                sws = calculate_sws_from_sog(
                    target_sog=v_sog,
                    weather=wx,
                    ship_heading_deg=heading_deg,
                    ship_parameters=ship_params,
                )
            else:  # "start"
                sws = _sws_from_sog_fast(v_sog, k_a, j, duration)

        fuel = calculate_fuel_consumption_rate(sws) * duration
        return fuel, sws, v_sog

    # ------------------------------------------------------------------
    # Dijkstra on the lattice
    # ------------------------------------------------------------------
    start_time = time.time()

    INF = float("inf")
    dist = {(0, 0): 0.0}
    parent = {}  # (k, j) -> (prev_k, prev_j, sws, v_sog, fuel_edge)
    pq = [(0.0, 0, 0)]

    edges_examined = 0

    while pq:
        fuel_so_far, k, j = heapq.heappop(pq)

        if dist.get((k, j), INF) < fuel_so_far - 1e-9:
            continue
        if k >= K_total:
            continue
        if j >= J_max:
            continue

        # Edge duration: stage_T for all stages except the partial final
        next_j = j + 1
        if allow_partial and final_duration > 1e-6 and next_j == J_max:
            duration = final_duration
            min_step = min_step_partial
            max_step = max_step_partial
        else:
            duration = stage_T
            min_step = min_step_full
            max_step = max_step_full

        k_lo = k + min_step
        k_hi = min(K_total, k + max_step)

        for k_next in range(k_lo, k_hi + 1):
            edges_examined += 1
            fuel_edge, sws_req, v_sog = _edge_fuel_and_sws(k, k_next, j, duration)
            new_fuel = fuel_so_far + fuel_edge
            state = (k_next, next_j)
            if new_fuel < dist.get(state, INF):
                dist[state] = new_fuel
                parent[state] = (k, j, sws_req, v_sog, fuel_edge, duration)
                heapq.heappush(pq, (new_fuel, k_next, next_j))

    elapsed = time.time() - start_time

    # ------------------------------------------------------------------
    # Find best arrival at (K_total, any j)
    # ------------------------------------------------------------------
    best_state = None
    best_fuel = INF
    best_total = INF

    for (k, j), f in dist.items():
        if k != K_total:
            continue
        # Arrival time
        if allow_partial and final_duration > 1e-6 and j == J_max:
            arrival = ETA
        else:
            arrival = j * stage_T
        delay = max(0.0, arrival - ETA)
        if soft_eta:
            total = f + lambda_val * delay
        else:
            if delay > 1e-6:
                continue
            total = f
        if total < best_total:
            best_total = total
            best_fuel = f
            best_state = (k, j)

    status = "Optimal"
    if best_state is None:
        # Hard ETA fallback: accept any K_total arrival
        for (k, j), f in dist.items():
            if k != K_total:
                continue
            if f < best_fuel:
                best_fuel = f
                best_state = (k, j)
        if best_state is None:
            logger.warning("Luo lattice: no path to destination (K=%d)", K_total)
            return {"status": "Infeasible",
                    "computation_time_s": round(elapsed, 4),
                    "solver": "luo_lattice"}
        status = "ETA_relaxed"

    # ------------------------------------------------------------------
    # Backtrack stage decisions
    # ------------------------------------------------------------------
    stages = []
    cur = best_state
    while cur in parent:
        prev_k, prev_j, sws, v_sog, fuel_edge, dur = parent[cur]
        stages.append({
            "stage": prev_j,
            "k_start": prev_k,
            "k_end": cur[0],
            "distance_nm": round((cur[0] - prev_k) * zeta, 4),
            "time_h": round(dur, 4),
            "sws_knots": round(sws, 3),
            "sog_knots": round(v_sog, 3),
            "fuel_mt": round(fuel_edge, 4),
        })
        cur = (prev_k, prev_j)
    stages.reverse()

    total_fuel = sum(s["fuel_mt"] for s in stages)
    total_time = sum(s["time_h"] for s in stages)
    delay_hours = max(0.0, total_time - ETA)

    logger.info(
        "Luo lattice %s: %.2f mt, %.1f h, %d stages, %d edges examined, "
        "%d states, %.2fs",
        status.lower(), total_fuel, total_time, len(stages),
        edges_examined, len(dist), elapsed,
    )

    # Emit schedule in the same per-stage form — runner handles either shape
    result = {
        "status": status,
        "planned_fuel_mt": total_fuel,
        "planned_time_h": total_time,
        "planned_delay_h": delay_hours,
        "speed_schedule": stages,
        "computation_time_s": round(elapsed, 4),
        "solver": "luo_lattice",
        "lattice_config": {
            "zeta_nm": zeta,
            "stage_hours": stage_T,
            "K_total": K_total,
            "J_max": J_max,
            "v_interpretation": v_interp,
            "weather_mode": weather_mode,
        },
    }
    if soft_eta:
        result["planned_total_cost_mt"] = total_fuel + lambda_val * delay_hours
    else:
        result["planned_total_cost_mt"] = total_fuel
    return result

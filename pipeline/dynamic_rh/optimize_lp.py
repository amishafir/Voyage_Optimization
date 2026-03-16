"""
Rolling Horizon optimizer with LP solver: re-plan at 6h decision points using
segment-averaged weather and LP optimization.

Same RH loop as optimize.py (DP variant), but each sub-problem is solved as
an LP over segments rather than a DP over nodes. This tests whether LP's
segment averaging is acceptable when combined with frequent re-planning.
"""

import logging
import math
import time

import numpy as np

from static_det.optimize import optimize as lp_optimize
from shared.physics import (
    calculate_speed_over_ground,
    calculate_fuel_consumption_rate,
    calculate_ship_heading,
)

logger = logging.getLogger(__name__)


def _build_lp_sub_problem(
    remaining_start,
    num_legs,
    node_metadata,
    distances,
    headings_deg,
    weather_for_nodes,
    speeds,
    fcr,
    ship_params,
    remaining_eta,
    config,
):
    """Build LP transform_output for the remaining voyage.

    Groups remaining legs by segment, averages weather per segment,
    builds SOG matrix, and returns a dict matching static_det.optimize's input.
    """
    remaining_meta = node_metadata[remaining_start:]
    remaining_dists = distances[remaining_start:]
    remaining_heads = headings_deg[remaining_start:]
    n_remaining = num_legs - remaining_start

    if n_remaining <= 0:
        return None

    # Group remaining legs by segment
    segments_seen = []
    seg_distances = {}
    seg_headings_sin = {}
    seg_headings_cos = {}
    seg_weather = {}  # {seg_idx: list of weather dicts}

    for i in range(n_remaining):
        meta = remaining_meta[i]
        seg = meta["segment"]
        nid = meta["node_id"]

        if seg not in seg_distances:
            segments_seen.append(seg)
            seg_distances[seg] = 0.0
            seg_headings_sin[seg] = []
            seg_headings_cos[seg] = []
            seg_weather[seg] = []

        seg_distances[seg] += remaining_dists[i]
        h_rad = math.radians(remaining_heads[i])
        seg_headings_sin[seg].append(math.sin(h_rad))
        seg_headings_cos[seg].append(math.cos(h_rad))

        wx = weather_for_nodes.get(nid, {})
        if wx:
            seg_weather[seg].append(wx)

    # Reindex segments to 0..N-1
    seg_order = segments_seen  # preserve order of first appearance
    num_segments = len(seg_order)

    if num_segments == 0:
        return None

    seg_dists_list = []
    seg_heads_list = []
    seg_wx_avg = []

    for seg in seg_order:
        seg_dists_list.append(seg_distances[seg])

        # Circular mean heading
        mean_sin = np.mean(seg_headings_sin[seg])
        mean_cos = np.mean(seg_headings_cos[seg])
        seg_heads_list.append(math.degrees(math.atan2(mean_sin, mean_cos)) % 360)

        # Average weather across nodes in this segment
        wx_list = seg_weather[seg]
        if not wx_list:
            seg_wx_avg.append({
                "wind_speed_10m_kmh": 0.0,
                "wind_direction_10m_deg": 0.0,
                "beaufort_number": 0,
                "wave_height_m": 0.0,
                "ocean_current_velocity_kmh": 0.0,
                "ocean_current_direction_deg": 0.0,
            })
            continue

        avg = {}
        for field in ["wind_speed_10m_kmh", "beaufort_number", "wave_height_m",
                       "ocean_current_velocity_kmh"]:
            vals = [w.get(field, 0.0) for w in wx_list if w.get(field) is not None]
            avg[field] = np.nanmean(vals) if vals else 0.0

        # Circular mean for directions
        for field in ["wind_direction_10m_deg", "ocean_current_direction_deg"]:
            rads = [math.radians(w.get(field, 0.0)) for w in wx_list if w.get(field) is not None]
            if rads:
                mean_s = np.mean([math.sin(r) for r in rads])
                mean_c = np.mean([math.cos(r) for r in rads])
                avg[field] = math.degrees(math.atan2(mean_s, mean_c)) % 360
            else:
                avg[field] = 0.0

        seg_wx_avg.append(avg)

    # Build SOG matrix [num_segments x num_speeds]
    num_speeds = len(speeds)
    sog_matrix = []

    for s_idx in range(num_segments):
        wx = seg_wx_avg[s_idx]
        heading_rad = math.radians(seg_heads_list[s_idx])

        current_knots = wx["ocean_current_velocity_kmh"] / 1.852
        current_dir_rad = math.radians(wx["ocean_current_direction_deg"])
        wind_dir_rad = math.radians(wx["wind_direction_10m_deg"])
        beaufort = int(round(wx["beaufort_number"]))
        wave_height = wx["wave_height_m"]

        # Handle NaN
        if math.isnan(current_knots): current_knots = 0.0
        if math.isnan(wave_height): wave_height = 0.0
        if math.isnan(beaufort) or beaufort < 0: beaufort = 0

        row = []
        for sws in speeds:
            sog = calculate_speed_over_ground(
                ship_speed=sws,
                ocean_current=current_knots,
                current_direction=current_dir_rad,
                ship_heading=heading_rad,
                wind_direction=wind_dir_rad,
                beaufort_scale=beaufort,
                wave_height=wave_height,
                ship_parameters=ship_params,
            )
            row.append(max(sog, 0.1))
        sog_matrix.append(row)

    sog_lower = [min(row) for row in sog_matrix]
    sog_upper = [max(row) for row in sog_matrix]

    return {
        "ETA": remaining_eta,
        "num_segments": num_segments,
        "num_speeds": num_speeds,
        "distances": seg_dists_list,
        "speeds": list(speeds),
        "fcr": list(fcr),
        "sog_matrix": sog_matrix,
        "sog_lower": sog_lower,
        "sog_upper": sog_upper,
        # Extra info for leg mapping
        "_seg_order": seg_order,
        "_remaining_start": remaining_start,
    }


def optimize(transform_output: dict, config: dict) -> dict:
    """Run rolling horizon optimization with LP solver at each decision point.

    Uses the same transform as RH-DP (loads all sample hours, actual weather).
    At each decision point, builds a segment-level LP sub-problem and solves it.
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

    actual_weather = transform_output.get("actual_weather", {})
    available_actual_hours = transform_output.get("available_actual_hours", [])

    rh_cfg = config["dynamic_rh"]
    replan_freq = rh_cfg["replan_frequency_hours"]
    use_actual = rh_cfg.get("use_actual_at_replan", False)

    # Decision points
    decision_hours = []
    h = 0
    while h < ETA:
        decision_hours.append(h)
        h += replan_freq

    logger.info("RH-LP: %d decision points, replan every %d h, use_actual=%s",
                len(decision_hours), replan_freq, use_actual)

    # State tracking
    current_node_idx = 0
    elapsed_time = 0.0
    elapsed_fuel = 0.0
    committed_legs = []
    decision_log = []

    total_start = time.time()

    for dp_idx, nominal_hour in enumerate(decision_hours):
        if current_node_idx >= num_legs:
            break

        # 1. Pick best available sample_hour
        sample_hour = _pick_sample_hour(available_sample_hours, elapsed_time)
        remaining_eta = ETA - elapsed_time

        if remaining_eta <= 0:
            logger.warning("RH-LP: No remaining ETA at decision %d", dp_idx)
            break

        # 2. Build weather dict for each node at the chosen sample_hour
        #    Use forecast_hour closest to elapsed_time
        grid = weather_grids[sample_hour]
        max_fh = max_forecast_hours[sample_hour]

        weather_for_nodes = {}
        for nid, fh_dict in grid.items():
            fh_target = min(int(round(elapsed_time)), max_fh)
            wx = fh_dict.get(fh_target)
            if wx is None:
                available_fh = sorted(fh_dict.keys())
                if available_fh:
                    closest = min(available_fh, key=lambda h: abs(h - fh_target))
                    wx = fh_dict[closest]
            if wx:
                weather_for_nodes[nid] = wx

        # 2b. Inject actual weather for nodes in committed window
        if use_actual and actual_weather:
            actual_sh = _pick_sample_hour(available_actual_hours, elapsed_time)
            actual_grid = actual_weather.get(actual_sh, {})
            for nid in actual_grid:
                weather_for_nodes[nid] = actual_grid[nid]

        # 3. Build LP sub-problem
        lp_input = _build_lp_sub_problem(
            remaining_start=current_node_idx,
            num_legs=num_legs,
            node_metadata=node_metadata,
            distances=distances,
            headings_deg=headings_deg,
            weather_for_nodes=weather_for_nodes,
            speeds=np.array(speeds),
            fcr=np.array(fcr),
            ship_params=ship_params,
            remaining_eta=remaining_eta,
            config=config,
        )

        if lp_input is None:
            break

        # 4. Solve LP
        lp_result = lp_optimize(lp_input, config)

        if lp_result.get("status") not in ("Optimal", "Feasible", "ETA_relaxed"):
            logger.warning("RH-LP: LP infeasible at decision %d (node=%d)",
                           dp_idx, current_node_idx)
            decision_log.append({
                "decision_hour": nominal_hour,
                "actual_hour": round(elapsed_time, 4),
                "sample_hour": sample_hour,
                "node_idx": current_node_idx,
                "legs_committed": 0,
                "lp_status": lp_result.get("status", "Infeasible"),
            })
            break

        # 5. Map segment SOG back to individual legs
        seg_order = lp_input["_seg_order"]
        seg_sog_map = {}
        seg_sws_map = {}
        for entry in lp_result["speed_schedule"]:
            orig_seg = seg_order[entry["segment"]]
            seg_sog_map[orig_seg] = entry["sog_knots"]
            seg_sws_map[orig_seg] = entry["sws_knots"]

        # Build per-leg schedule for remaining legs
        remaining_meta = node_metadata[current_node_idx:]
        remaining_dists = distances[current_node_idx:]
        n_remaining = num_legs - current_node_idx

        # 6. Commit legs within the time budget
        next_decision = decision_hours[dp_idx + 1] if dp_idx + 1 < len(decision_hours) else float("inf")
        time_budget = next_decision - nominal_hour
        is_last = dp_idx + 1 >= len(decision_hours)

        legs_this_round = []
        sub_elapsed = 0.0
        sub_fuel = 0.0

        for i in range(n_remaining):
            if not is_last and sub_elapsed >= time_budget:
                break

            meta = remaining_meta[i]
            seg = meta["segment"]
            dist = remaining_dists[i]

            sog = seg_sog_map.get(seg, speeds[len(speeds) // 2])  # fallback to mid-speed
            sws = seg_sws_map.get(seg, speeds[len(speeds) // 2])
            leg_time = dist / max(sog, 0.1)
            leg_fcr = calculate_fuel_consumption_rate(sws)
            leg_fuel = leg_fcr * leg_time

            legs_this_round.append({
                "leg": current_node_idx + i,
                "node_id": meta["node_id"],
                "sog_knots": sog,
                "sws_knots": sws,
                "distance_nm": dist,
                "time_h": leg_time,
                "fuel_mt": leg_fuel,
                "fcr_mt_h": leg_fcr,
            })
            sub_elapsed += leg_time
            sub_fuel += leg_fuel

        committed_legs.extend(legs_this_round)
        current_node_idx += len(legs_this_round)
        elapsed_time += sub_elapsed
        elapsed_fuel += sub_fuel

        decision_log.append({
            "decision_hour": nominal_hour,
            "actual_hour": round(elapsed_time - sub_elapsed, 4),
            "sample_hour": sample_hour,
            "node_idx": current_node_idx - len(legs_this_round),
            "legs_committed": len(legs_this_round),
            "elapsed_fuel_mt": round(elapsed_fuel, 4),
            "elapsed_time_h": round(elapsed_time, 4),
            "remaining_legs": num_legs - current_node_idx,
            "remaining_eta_h": round(ETA - elapsed_time, 4),
            "lp_planned_fuel_mt": round(lp_result["planned_fuel_mt"], 4),
            "lp_planned_time_h": round(lp_result["planned_time_h"], 4),
            "lp_status": lp_result["status"],
            "lp_solve_time_s": round(lp_result["computation_time_s"], 4),
        })

        logger.info("RH-LP decision %d: hour=%.1f, SH=%d, node=%d, committed=%d legs, "
                     "fuel=%.2f mt, time=%.2f h",
                     dp_idx, nominal_hour, sample_hour,
                     current_node_idx - len(legs_this_round),
                     len(legs_this_round), sub_fuel, sub_elapsed)

    total_elapsed = time.time() - total_start

    if current_node_idx < num_legs:
        logger.warning("RH-LP: Only covered %d/%d legs.", current_node_idx, num_legs)

    total_fuel = sum(l["fuel_mt"] for l in committed_legs)
    total_time = sum(l["time_h"] for l in committed_legs)

    status = "Optimal" if current_node_idx >= num_legs else "Feasible"

    result = {
        "status": status,
        "planned_fuel_mt": total_fuel,
        "planned_time_h": total_time,
        "speed_schedule": committed_legs,
        "computation_time_s": round(total_elapsed, 4),
        "solver": "lp_rh",
        "decision_points": decision_log,
    }

    logger.info("RH-LP complete: %.2f mt fuel, %.2f h, %d decisions, %.2f s",
                total_fuel, total_time, len(decision_log), total_elapsed)
    return result


def _pick_sample_hour(available, elapsed_time):
    """Pick the best available sample_hour <= elapsed_time."""
    elapsed_int = int(elapsed_time)
    candidates = [s for s in available if s <= elapsed_int]
    if candidates:
        return max(candidates)
    return available[0]

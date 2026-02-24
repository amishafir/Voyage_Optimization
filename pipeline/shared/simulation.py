"""
Voyage simulation engine.

Simulates a voyage using per-waypoint (279-node) actual weather.
The ship *targets* the planned SOG at each leg and adjusts SWS
(engine speed) to achieve it under actual conditions.

    Optimizer → SOG schedule → Ship adjusts SWS to hit SOG
    → ETA is deterministic (distance / SOG)
    → Fuel varies (FCR depends on required SWS)

If the required SWS exceeds engine limits [min_speed, max_speed],
it is clamped, the achieved SOG will differ, and a violation is logged.

Reused by all three optimization strategies (static_det, dynamic_det,
dynamic_rh).
"""

import logging
import math

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

logger = logging.getLogger(__name__)


def simulate_voyage(
    speed_schedule: list,
    hdf5_path: str,
    config: dict,
    sample_hour: int = 0,
) -> dict:
    """Simulate a voyage targeting the planned SOG at each leg.

    The ship adjusts SWS (engine speed) to maintain the planned SOG
    under actual weather.  Time is deterministic; fuel varies.

    Args:
        speed_schedule: List of dicts with ``sog_knots`` (target SOG)
                        and ``sws_knots`` (planned SWS, for reference).
        hdf5_path:      Path to HDF5 weather file.
        config:         Full experiment config.
        sample_hour:    Which actual-weather snapshot to use.

    Returns:
        Dict with: total_fuel_mt, total_time_h, arrival_deviation_h,
        speed_changes, co2_emissions_mt, sws_violations, time_series (DataFrame).
    """
    ship_params = load_ship_parameters(config)
    eta = config["ship"]["eta_hours"]
    min_speed = config["ship"]["speed_range_knots"][0]
    max_speed = config["ship"]["speed_range_knots"][1]

    # ------------------------------------------------------------------
    # 1. Read per-waypoint data
    # ------------------------------------------------------------------
    metadata = read_metadata(hdf5_path)
    weather = read_actual(hdf5_path, sample_hour=sample_hour)

    merged = metadata.merge(weather, on="node_id", how="left")
    merged = merged.sort_values("node_id").reset_index(drop=True)

    num_nodes = len(merged)

    # Detect schedule type: per-leg (node_id) vs per-segment
    if speed_schedule and "node_id" in speed_schedule[0]:
        leg_sog = {entry["node_id"]: entry["sog_knots"] for entry in speed_schedule}
        seg_sog = None
    else:
        leg_sog = None
        seg_sog = {entry["segment"]: entry["sog_knots"] for entry in speed_schedule}

    # ------------------------------------------------------------------
    # 2. Walk through consecutive waypoint pairs
    # ------------------------------------------------------------------
    weather_fields = [
        "wind_speed_10m_kmh", "wind_direction_10m_deg", "beaufort_number",
        "wave_height_m", "ocean_current_velocity_kmh", "ocean_current_direction_deg",
    ]

    rows = []
    cum_distance = 0.0
    cum_time = 0.0
    cum_fuel = 0.0
    sws_violations = 0

    for idx in range(num_nodes - 1):
        node_a = merged.iloc[idx]
        node_b = merged.iloc[idx + 1]

        segment = int(node_a["segment"])
        if leg_sog is not None:
            target_sog = leg_sog.get(int(node_a["node_id"]))
        else:
            target_sog = seg_sog.get(segment)
        if target_sog is None:
            continue  # safety

        # Distance between consecutive nodes
        dist = node_b["distance_from_start_nm"] - node_a["distance_from_start_nm"]
        if dist <= 0:
            continue

        # Heading from node_a to node_b
        heading_deg = calculate_ship_heading(
            node_a["lat"], node_a["lon"], node_b["lat"], node_b["lon"]
        )

        # Build weather dict for this node
        wx = {}
        for field in weather_fields:
            wx[field] = _safe(node_a.get(field), 0.0)

        # Inverse: find SWS required to achieve target SOG under actual weather
        required_sws = calculate_sws_from_sog(
            target_sog=target_sog,
            weather=wx,
            ship_heading_deg=heading_deg,
            ship_parameters=ship_params,
        )

        # Clamp SWS to engine limits
        clamped_sws = max(min_speed, min(max_speed, required_sws))
        if abs(clamped_sws - required_sws) > 0.01:
            sws_violations += 1

        # Compute actual SOG achieved with clamped SWS
        heading_rad = math.radians(heading_deg)
        wind_dir_rad = math.radians(wx["wind_direction_10m_deg"])
        current_knots = wx["ocean_current_velocity_kmh"] / 1.852
        current_dir_rad = math.radians(wx["ocean_current_direction_deg"])
        beaufort = int(round(wx["beaufort_number"]))
        wave_height = wx["wave_height_m"]

        if abs(clamped_sws - required_sws) > 0.01:
            # SWS was clamped — recompute actual SOG
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
            "segment": segment,
            "lat": float(node_a["lat"]),
            "lon": float(node_a["lon"]),
            "planned_sog_knots": target_sog,
            "actual_sog_knots": actual_sog,
            "planned_sws_knots": required_sws,
            "actual_sws_knots": clamped_sws,
            "distance_nm": dist,
            "time_h": leg_time,
            "fuel_mt": leg_fuel,
            "cum_distance_nm": cum_distance,
            "cum_time_h": cum_time,
            "cum_fuel_mt": cum_fuel,
            "beaufort": beaufort,
            "wave_height_m": wave_height,
            "current_knots": current_knots,
            "heading_deg": heading_deg,
        })

    time_series = pd.DataFrame(rows)
    co2 = calculate_co2_emissions(cum_fuel)

    # Count SOG changes in the plan
    speed_changes = 0
    if len(speed_schedule) > 1:
        for i in range(1, len(speed_schedule)):
            if speed_schedule[i]["sog_knots"] != speed_schedule[i - 1]["sog_knots"]:
                speed_changes += 1

    result = {
        "total_fuel_mt": cum_fuel,
        "total_time_h": cum_time,
        "arrival_deviation_h": cum_time - eta,
        "speed_changes": speed_changes,
        "sws_violations": sws_violations,
        "co2_emissions_mt": co2,
        "time_series": time_series,
    }

    logger.info(
        "Simulation: %.1f mt fuel, %.1f h, deviation %.1f h, "
        "%d speed changes, %d SWS violations",
        cum_fuel, cum_time, result["arrival_deviation_h"],
        speed_changes, sws_violations,
    )
    return result


def _safe(val, default):
    """Return *default* if val is None or NaN."""
    if val is None:
        return default
    try:
        if math.isnan(val):
            return default
    except (TypeError, ValueError):
        pass
    return float(val)

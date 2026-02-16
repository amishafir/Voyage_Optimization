"""
Voyage simulation engine.

Simulates a voyage using per-waypoint (279-node) weather rather than
the segment-averaged weather used by the LP optimizer.  This reveals
the fuel gap caused by spatial averaging.

Reused by all three optimization strategies (static_det, dynamic_det,
dynamic_stoch).
"""

import logging
import math

import pandas as pd

from shared.hdf5_io import read_metadata, read_actual
from shared.physics import (
    calculate_ship_heading,
    calculate_speed_over_ground,
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
    """Simulate a voyage with per-waypoint weather.

    Args:
        speed_schedule: List of dicts (one per segment) with at least
                        ``sws_knots`` key.
        hdf5_path:      Path to HDF5 weather file.
        config:         Full experiment config.
        sample_hour:    Which actual-weather snapshot to use.

    Returns:
        Dict with: total_fuel_kg, total_time_h, arrival_deviation_h,
        speed_changes, co2_emissions_kg, time_series (DataFrame).
    """
    ship_params = load_ship_parameters(config)
    eta = config["ship"]["eta_hours"]

    # ------------------------------------------------------------------
    # 1. Read per-waypoint data
    # ------------------------------------------------------------------
    metadata = read_metadata(hdf5_path)
    weather = read_actual(hdf5_path, sample_hour=sample_hour)

    merged = metadata.merge(weather, on="node_id", how="left")
    merged = merged.sort_values("node_id").reset_index(drop=True)

    num_nodes = len(merged)

    # Map segment -> SWS from the schedule
    seg_sws = {}
    for entry in speed_schedule:
        seg_sws[entry["segment"]] = entry["sws_knots"]

    # ------------------------------------------------------------------
    # 2. Walk through consecutive waypoint pairs
    # ------------------------------------------------------------------
    rows = []
    cum_distance = 0.0
    cum_time = 0.0
    cum_fuel = 0.0

    for idx in range(num_nodes - 1):
        node_a = merged.iloc[idx]
        node_b = merged.iloc[idx + 1]

        segment = int(node_a["segment"])
        sws = seg_sws.get(segment)
        if sws is None:
            continue  # safety

        # Distance between consecutive nodes
        dist = node_b["distance_from_start_nm"] - node_a["distance_from_start_nm"]
        if dist <= 0:
            continue

        # Heading from node_a to node_b
        heading_deg = calculate_ship_heading(
            node_a["lat"], node_a["lon"], node_b["lat"], node_b["lon"]
        )
        heading_rad = math.radians(heading_deg)

        # Weather at node_a (use for this leg)
        wind_dir_rad = math.radians(_safe(node_a.get("wind_direction_10m_deg"), 0.0))
        current_dir_rad = math.radians(_safe(node_a.get("ocean_current_direction_deg"), 0.0))
        current_knots = _safe(node_a.get("ocean_current_velocity_kmh"), 0.0) / 1.852
        beaufort = int(round(_safe(node_a.get("beaufort_number"), 0)))
        wave_height = _safe(node_a.get("wave_height_m"), 0.0)

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

        # Clamp SOG to prevent division by zero
        sog = max(sog, 0.1)

        fcr = calculate_fuel_consumption_rate(sws)
        leg_time = dist / sog
        leg_fuel = fcr * leg_time

        cum_distance += dist
        cum_time += leg_time
        cum_fuel += leg_fuel

        rows.append({
            "node_id": int(node_a["node_id"]),
            "segment": segment,
            "lat": float(node_a["lat"]),
            "lon": float(node_a["lon"]),
            "sws_knots": sws,
            "sog_knots": sog,
            "distance_nm": dist,
            "time_h": leg_time,
            "fuel_kg": leg_fuel,
            "cum_distance_nm": cum_distance,
            "cum_time_h": cum_time,
            "cum_fuel_kg": cum_fuel,
            "beaufort": beaufort,
            "wave_height_m": wave_height,
            "current_knots": current_knots,
            "heading_deg": heading_deg,
        })

    time_series = pd.DataFrame(rows)
    co2 = calculate_co2_emissions(cum_fuel)

    # Count speed changes (transitions between segments with different SWS)
    speed_changes = 0
    if len(speed_schedule) > 1:
        for i in range(1, len(speed_schedule)):
            if speed_schedule[i]["sws_knots"] != speed_schedule[i - 1]["sws_knots"]:
                speed_changes += 1

    result = {
        "total_fuel_kg": cum_fuel,
        "total_time_h": cum_time,
        "arrival_deviation_h": cum_time - eta,
        "speed_changes": speed_changes,
        "co2_emissions_kg": co2,
        "time_series": time_series,
    }

    logger.info(
        "Simulation: %.1f kg fuel, %.1f h, deviation %.1f h, %d speed changes",
        cum_fuel, cum_time, result["arrival_deviation_h"], speed_changes,
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

"""
Dynamic Deterministic transform: HDF5 predicted weather -> DP-ready inputs.

Reads metadata (279 nodes) and predicted weather at a given sample_hour,
builds a per-node/per-forecast-hour weather grid, computes per-leg headings
and distances, and returns the data structures consumed by the Bellman DP.
"""

import math
import logging

import numpy as np
import pandas as pd

from shared.hdf5_io import read_metadata, read_predicted, read_actual
from shared.physics import (
    calculate_ship_heading,
    calculate_fuel_consumption_rate,
    load_ship_parameters,
)

logger = logging.getLogger(__name__)


def _circular_mean_deg(angles_deg):
    """Mean of angles in degrees, handling the 0/360 wrap-around."""
    vals = [v for v in angles_deg if not math.isnan(v)]
    if not vals:
        return 0.0
    rads = [math.radians(a) for a in vals]
    mean_sin = sum(math.sin(r) for r in rads) / len(rads)
    mean_cos = sum(math.cos(r) for r in rads) / len(rads)
    return math.degrees(math.atan2(mean_sin, mean_cos)) % 360


def _segment_average_weather(all_metadata, weather_df, weather_fields):
    """Average weather per segment across all nodes, matching LP's approach.

    Returns dict: segment_index -> weather dict (6 fields).
    """
    merged = all_metadata[["node_id", "segment"]].merge(weather_df, on="node_id")

    scalar_cols = [f for f in weather_fields
                   if "direction" not in f]
    direction_cols = [f for f in weather_fields
                      if "direction" in f]

    result = {}
    for seg, group in merged.groupby("segment"):
        wx = {}
        for col in scalar_cols:
            vals = group[col].dropna()
            wx[col] = float(vals.mean()) if len(vals) > 0 else 0.0
        for col in direction_cols:
            wx[col] = _circular_mean_deg(group[col].tolist())
        # Clean NaN
        for k, v in wx.items():
            if math.isnan(v):
                wx[k] = 0.0
        result[int(seg)] = wx

    return result


def transform(hdf5_path: str, config: dict) -> dict:
    """Transform HDF5 predicted weather data into DP-ready inputs.

    Returns dict with keys:
        ETA, num_nodes, num_legs, speeds, fcr, distances, headings_deg,
        weather_grid, max_forecast_hour, node_metadata, ship_params
    """
    dd_cfg = config["dynamic_det"]
    ship_params = load_ship_parameters(config)
    sample_hour = dd_cfg["forecast_origin"]

    nodes_mode = dd_cfg.get("nodes", "all")
    time_windows = dd_cfg.get("time_windows", "all")
    weather_source = dd_cfg.get("weather_source", "predicted")

    # ------------------------------------------------------------------
    # 1. Read HDF5
    # ------------------------------------------------------------------
    metadata = read_metadata(hdf5_path)
    metadata = metadata.sort_values("node_id").reset_index(drop=True)

    # Filter to original waypoints only if configured
    if nodes_mode == "original":
        metadata = metadata[metadata["is_original"]].reset_index(drop=True)
        logger.info("Filtered to %d original waypoints", len(metadata))

    num_nodes = len(metadata)
    num_legs = num_nodes - 1

    # ------------------------------------------------------------------
    # 2. Build weather grid: weather_grid[node_id][forecast_hour] -> dict
    # ------------------------------------------------------------------
    weather_fields = [
        "wind_speed_10m_kmh", "wind_direction_10m_deg", "beaufort_number",
        "wave_height_m", "ocean_current_velocity_kmh", "ocean_current_direction_deg",
    ]

    # Set of node_ids we actually use
    active_node_ids = set(int(r["node_id"]) for _, r in metadata.iterrows())

    weather_grid = {}
    max_forecast_hour = 0

    if weather_source == "actual":
        # Use actual (observed) weather — single snapshot
        actual_df = read_actual(hdf5_path, sample_hour=sample_hour)
        logger.info("Using ACTUAL weather: %d rows (sample_hour=%d)",
                     len(actual_df), sample_hour)

        if nodes_mode == "original":
            # Segment-averaged weather from ALL 279 nodes, like the LP
            all_metadata = read_metadata(hdf5_path)
            all_metadata = all_metadata.sort_values("node_id").reset_index(drop=True)
            seg_avg = _segment_average_weather(all_metadata, actual_df, weather_fields)
            logger.info("Segment-averaged actual weather for %d segments", len(seg_avg))

            # Assign segment-averaged weather to each original waypoint
            for _, row in metadata.iterrows():
                nid = int(row["node_id"])
                seg = int(row["segment"])
                wx = seg_avg.get(seg)
                if wx is not None:
                    weather_grid[nid] = {0: wx}
        else:
            # Per-node actual weather
            for _, row in actual_df.iterrows():
                nid = int(row["node_id"])
                if nid not in active_node_ids:
                    continue
                if nid not in weather_grid:
                    weather_grid[nid] = {}
                wx = {}
                for field in weather_fields:
                    val = float(row[field])
                    if math.isnan(val):
                        val = 0.0
                    wx[field] = val
                weather_grid[nid][0] = wx

        max_forecast_hour = 0
    else:
        # Use predicted weather (default)
        predicted = read_predicted(hdf5_path, sample_hour=sample_hour)
        logger.info("Using PREDICTED weather: %d rows (sample_hour=%d)",
                     len(predicted), sample_hour)

        single_window = (time_windows == 1 or time_windows == "1")
        if single_window:
            predicted = predicted[predicted["forecast_hour"] == 0]
            logger.info("Single time window: filtered to forecast_hour=0 (%d rows)",
                         len(predicted))

        # Cap forecast horizon if configured (for sensitivity experiments)
        max_horizon = dd_cfg.get("max_forecast_horizon")
        if max_horizon is not None:
            predicted = predicted[predicted["forecast_hour"] <= int(max_horizon)]
            logger.info("Forecast horizon capped at %dh (%d rows)",
                         max_horizon, len(predicted))

        for _, row in predicted.iterrows():
            nid = int(row["node_id"])
            if nid not in active_node_ids:
                continue
            fh = int(row["forecast_hour"])
            if nid not in weather_grid:
                weather_grid[nid] = {}
            wx = {}
            for field in weather_fields:
                val = float(row[field])
                if math.isnan(val):
                    val = 0.0
                wx[field] = val
            weather_grid[nid][fh] = wx
            if fh > max_forecast_hour:
                max_forecast_hour = fh

    logger.info("Weather grid: %d nodes with forecasts, max_forecast_hour=%d",
                len(weather_grid), max_forecast_hour)

    # ------------------------------------------------------------------
    # 3. Per-leg headings and distances
    # ------------------------------------------------------------------
    headings_deg = []
    distances = []

    for i in range(num_legs):
        node_a = metadata.iloc[i]
        node_b = metadata.iloc[i + 1]

        heading = calculate_ship_heading(
            node_a["lat"], node_a["lon"],
            node_b["lat"], node_b["lon"],
        )
        headings_deg.append(heading)

        dist = node_b["distance_from_start_nm"] - node_a["distance_from_start_nm"]
        distances.append(max(dist, 0.001))  # guard against zero

    logger.info("Legs: %d, total distance: %.1f nm", num_legs, sum(distances))

    # ------------------------------------------------------------------
    # 4. Speed array and FCR array
    # ------------------------------------------------------------------
    min_speed, max_speed = config["ship"]["speed_range_knots"]
    granularity = dd_cfg["speed_granularity"]
    num_speeds = int(round((max_speed - min_speed) / granularity)) + 1
    speeds = [min_speed + k * granularity for k in range(num_speeds)]
    fcr = [calculate_fuel_consumption_rate(s) for s in speeds]

    # ------------------------------------------------------------------
    # 5. Node metadata for reference
    # ------------------------------------------------------------------
    node_metadata = []
    for _, row in metadata.iterrows():
        node_metadata.append({
            "node_id": int(row["node_id"]),
            "lat": float(row["lat"]),
            "lon": float(row["lon"]),
            "segment": int(row["segment"]),
        })

    ETA = config["ship"]["eta_hours"]

    result = {
        "ETA": ETA,
        "num_nodes": num_nodes,
        "num_legs": num_legs,
        "speeds": speeds,
        "fcr": fcr,
        "distances": distances,
        "headings_deg": headings_deg,
        "weather_grid": weather_grid,
        "max_forecast_hour": max_forecast_hour,
        "node_metadata": node_metadata,
        "ship_params": ship_params,
    }

    logger.info("Transform complete: ETA=%d h, %d nodes, %d legs, %d speeds, "
                "forecast range 0-%d h",
                ETA, num_nodes, num_legs, num_speeds, max_forecast_hour)
    return result

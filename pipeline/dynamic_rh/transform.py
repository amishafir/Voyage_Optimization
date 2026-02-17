"""
Rolling Horizon transform: HDF5 predicted weather -> multi-sample-hour inputs.

Loads structural data (headings, distances, speeds, FCR) once,
plus weather grids for ALL available sample hours. The RH optimizer
picks the freshest grid at each decision point.
"""

import math
import logging

import pandas as pd

from shared.hdf5_io import read_metadata, read_predicted
from shared.physics import (
    calculate_ship_heading,
    calculate_fuel_consumption_rate,
    load_ship_parameters,
)

logger = logging.getLogger(__name__)

WEATHER_FIELDS = [
    "wind_speed_10m_kmh", "wind_direction_10m_deg", "beaufort_number",
    "wave_height_m", "ocean_current_velocity_kmh", "ocean_current_direction_deg",
]


def transform(hdf5_path: str, config: dict) -> dict:
    """Transform HDF5 predicted weather into RH-ready inputs.

    Returns dict with keys:
        ETA, num_nodes, num_legs, speeds, fcr, distances, headings_deg,
        node_metadata, ship_params, weather_grids, max_forecast_hours,
        available_sample_hours
    """
    dd_cfg = config["dynamic_det"]
    ship_params = load_ship_parameters(config)

    nodes_mode = dd_cfg.get("nodes", "all")

    # ------------------------------------------------------------------
    # 1. Read metadata
    # ------------------------------------------------------------------
    metadata = read_metadata(hdf5_path)
    metadata = metadata.sort_values("node_id").reset_index(drop=True)

    if nodes_mode == "original":
        metadata = metadata[metadata["is_original"]].reset_index(drop=True)
        logger.info("Filtered to %d original waypoints", len(metadata))

    num_nodes = len(metadata)
    num_legs = num_nodes - 1
    active_node_ids = set(int(r["node_id"]) for _, r in metadata.iterrows())

    # ------------------------------------------------------------------
    # 2. Per-leg headings and distances
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
        distances.append(max(dist, 0.001))

    logger.info("Legs: %d, total distance: %.1f nm", num_legs, sum(distances))

    # ------------------------------------------------------------------
    # 3. Speed array and FCR array
    # ------------------------------------------------------------------
    min_speed, max_speed = config["ship"]["speed_range_knots"]
    granularity = dd_cfg["speed_granularity"]
    num_speeds = int(round((max_speed - min_speed) / granularity)) + 1
    speeds = [min_speed + k * granularity for k in range(num_speeds)]
    fcr = [calculate_fuel_consumption_rate(s) for s in speeds]

    # ------------------------------------------------------------------
    # 4. Node metadata
    # ------------------------------------------------------------------
    node_metadata = []
    for _, row in metadata.iterrows():
        node_metadata.append({
            "node_id": int(row["node_id"]),
            "lat": float(row["lat"]),
            "lon": float(row["lon"]),
            "segment": int(row["segment"]),
        })

    # ------------------------------------------------------------------
    # 5. Load weather grids for ALL sample hours
    # ------------------------------------------------------------------
    all_predicted = read_predicted(hdf5_path)
    logger.info("Read %d total predicted rows", len(all_predicted))

    available_sample_hours = sorted(int(s) for s in all_predicted["sample_hour"].unique())

    weather_grids = {}
    max_forecast_hours = {}

    for sh in available_sample_hours:
        sh_data = all_predicted[all_predicted["sample_hour"] == sh]
        grid = {}
        max_fh = 0

        for _, row in sh_data.iterrows():
            nid = int(row["node_id"])
            if nid not in active_node_ids:
                continue
            fh = int(row["forecast_hour"])
            if nid not in grid:
                grid[nid] = {}
            wx = {}
            for field in WEATHER_FIELDS:
                val = float(row[field])
                if math.isnan(val):
                    val = 0.0
                wx[field] = val
            grid[nid][fh] = wx
            if fh > max_fh:
                max_fh = fh

        weather_grids[sh] = grid
        max_forecast_hours[sh] = max_fh

    logger.info("Loaded weather grids for %d sample hours, nodes per grid: %d",
                len(available_sample_hours), len(active_node_ids))

    ETA = config["ship"]["eta_hours"]

    result = {
        "ETA": ETA,
        "num_nodes": num_nodes,
        "num_legs": num_legs,
        "speeds": speeds,
        "fcr": fcr,
        "distances": distances,
        "headings_deg": headings_deg,
        "node_metadata": node_metadata,
        "ship_params": ship_params,
        "weather_grids": weather_grids,
        "max_forecast_hours": max_forecast_hours,
        "available_sample_hours": available_sample_hours,
    }

    logger.info("RH Transform complete: ETA=%d h, %d nodes, %d legs, %d speeds, "
                "%d sample hours",
                ETA, num_nodes, num_legs, num_speeds, len(available_sample_hours))
    return result

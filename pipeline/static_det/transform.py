"""
Static Deterministic transform: HDF5 weather data -> LP-ready matrices.

Reads metadata (279 nodes) and actual weather at sample_hour=0,
aggregates into 12 segment averages, and builds the SOG matrix and
FCR array consumed by the LP optimizer.
"""

import math
import logging

import numpy as np
import pandas as pd

from shared.hdf5_io import read_metadata, read_actual
from shared.physics import (
    calculate_ship_heading,
    calculate_speed_over_ground,
    calculate_fuel_consumption_rate,
    load_ship_parameters,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _circular_mean_deg(angles_deg: pd.Series) -> float:
    """Mean of angles in degrees, handling the 0/360 wrap-around."""
    rads = np.radians(angles_deg.dropna().values)
    if len(rads) == 0:
        return 0.0
    mean_sin = np.mean(np.sin(rads))
    mean_cos = np.mean(np.cos(rads))
    return np.degrees(np.arctan2(mean_sin, mean_cos)) % 360


def _segment_weather(weather_df: pd.DataFrame, metadata: pd.DataFrame) -> pd.DataFrame:
    """Average weather per segment (0..11).

    Scalar fields: nanmean.  Direction fields: circular mean.
    """
    merged = metadata[["node_id", "segment"]].merge(weather_df, on="node_id")

    scalar_cols = [
        "wind_speed_10m_kmh",
        "beaufort_number",
        "wave_height_m",
        "ocean_current_velocity_kmh",
    ]
    direction_cols = [
        "wind_direction_10m_deg",
        "ocean_current_direction_deg",
    ]

    scalar_agg = merged.groupby("segment")[scalar_cols].mean()  # nanmean by default
    direction_agg = merged.groupby("segment")[direction_cols].agg(_circular_mean_deg)

    return scalar_agg.join(direction_agg).sort_index()


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def transform(hdf5_path: str, config: dict) -> dict:
    """Transform HDF5 weather data into LP-ready inputs.

    Returns dict with keys:
        ETA, num_segments, num_speeds, distances, speeds, fcr,
        sog_matrix, sog_lower, sog_upper, segment_headings_deg,
        segment_weather
    """
    sd_cfg = config["static_det"]
    ship_params = load_ship_parameters(config)
    sample_hour = sd_cfg["weather_snapshot"]
    num_speeds = sd_cfg["speed_choices"]

    # ------------------------------------------------------------------
    # 1. Read HDF5
    # ------------------------------------------------------------------
    metadata = read_metadata(hdf5_path)
    weather = read_actual(hdf5_path, sample_hour=sample_hour)
    logger.info("Read %d nodes, %d weather rows (sample_hour=%d)",
                len(metadata), len(weather), sample_hour)

    # ------------------------------------------------------------------
    # 2. Original waypoints -> segment headings & distances
    # ------------------------------------------------------------------
    originals = metadata[metadata["is_original"]].sort_values("node_id").reset_index(drop=True)
    num_segments = len(originals) - 1
    assert num_segments == sd_cfg["segments"], (
        f"Expected {sd_cfg['segments']} segments, got {num_segments}"
    )

    headings_deg = []
    distances = []
    for i in range(num_segments):
        wp_a = originals.iloc[i]
        wp_b = originals.iloc[i + 1]
        heading = calculate_ship_heading(wp_a["lat"], wp_a["lon"],
                                         wp_b["lat"], wp_b["lon"])
        headings_deg.append(heading)
        dist = wp_b["distance_from_start_nm"] - wp_a["distance_from_start_nm"]
        distances.append(dist)

    logger.info("Segments: %d, total distance: %.1f nm", num_segments, sum(distances))

    # ------------------------------------------------------------------
    # 3. Average weather per segment
    # ------------------------------------------------------------------
    seg_wx = _segment_weather(weather, metadata)

    # ------------------------------------------------------------------
    # 4. Speed array and FCR array
    # ------------------------------------------------------------------
    min_speed = ship_params["min_speed"]
    max_speed = ship_params["max_speed"]
    speeds = np.linspace(min_speed, max_speed, num_speeds)
    fcr = np.array([calculate_fuel_consumption_rate(s) for s in speeds])

    # ------------------------------------------------------------------
    # 5. SOG matrix [num_segments x num_speeds]
    # ------------------------------------------------------------------
    sog_matrix = np.zeros((num_segments, num_speeds))

    for seg_idx in range(num_segments):
        wx = seg_wx.loc[seg_idx]
        heading_rad = math.radians(headings_deg[seg_idx])
        wind_dir_rad = math.radians(wx["wind_direction_10m_deg"])
        current_dir_rad = math.radians(wx["ocean_current_direction_deg"])
        current_knots = wx["ocean_current_velocity_kmh"] / 1.852
        beaufort = int(round(wx["beaufort_number"]))
        wave_height = wx["wave_height_m"]

        # Handle NaN (Port B segment edge case)
        if math.isnan(current_knots):
            current_knots = 0.0
        if math.isnan(wave_height):
            wave_height = 0.0
        if math.isnan(beaufort) or beaufort < 0:
            beaufort = 0

        for k, sws in enumerate(speeds):
            sog_matrix[seg_idx, k] = calculate_speed_over_ground(
                ship_speed=sws,
                ocean_current=current_knots,
                current_direction=current_dir_rad,
                ship_heading=heading_rad,
                wind_direction=wind_dir_rad,
                beaufort_scale=beaufort,
                wave_height=wave_height,
                ship_parameters=ship_params,
            )

    # ------------------------------------------------------------------
    # 6. SOG bounds per segment
    # ------------------------------------------------------------------
    sog_lower = sog_matrix.min(axis=1).tolist()
    sog_upper = sog_matrix.max(axis=1).tolist()

    # ------------------------------------------------------------------
    # 7. Build segment weather list for reference / simulation
    # ------------------------------------------------------------------
    segment_weather = []
    for seg_idx in range(num_segments):
        wx = seg_wx.loc[seg_idx]
        segment_weather.append({
            "wind_speed_10m_kmh": float(wx["wind_speed_10m_kmh"]),
            "wind_direction_10m_deg": float(wx["wind_direction_10m_deg"]),
            "beaufort_number": int(round(wx["beaufort_number"])),
            "wave_height_m": float(wx["wave_height_m"]) if not math.isnan(wx["wave_height_m"]) else 0.0,
            "ocean_current_velocity_kmh": float(wx["ocean_current_velocity_kmh"]) if not math.isnan(wx["ocean_current_velocity_kmh"]) else 0.0,
            "ocean_current_direction_deg": float(wx["ocean_current_direction_deg"]),
        })

    ETA = config["ship"]["eta_hours"]

    result = {
        "ETA": ETA,
        "num_segments": num_segments,
        "num_speeds": num_speeds,
        "distances": distances,
        "speeds": speeds.tolist(),
        "fcr": fcr.tolist(),
        "sog_matrix": sog_matrix.tolist(),
        "sog_lower": sog_lower,
        "sog_upper": sog_upper,
        "segment_headings_deg": headings_deg,
        "segment_weather": segment_weather,
    }

    logger.info("Transform complete: ETA=%.0f h, %d segments, %d speeds",
                ETA, num_segments, num_speeds)
    return result

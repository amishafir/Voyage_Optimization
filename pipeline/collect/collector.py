"""
Weather data collector for the maritime route.

Ported from: test_files/multi_location_forecast_170wp.py
Key changes:
  - Config-driven (experiment.yaml), no hardcoded constants
  - Output to HDF5 via shared.hdf5_io, not pickle
  - Uses shared.beaufort.wind_speed_to_beaufort
  - Resume-aware via get_completed_runs()
  - Single waypoint failure logs warning + NaN row, doesn't abort
"""

import logging
import os
import signal
import time
from datetime import datetime

import pandas as pd
import openmeteo_requests
import requests_cache
from retry_requests import retry

from shared.beaufort import wind_speed_to_beaufort
from shared.hdf5_io import (
    create_hdf5,
    append_actual,
    append_predicted,
    get_completed_runs,
)
from collect.waypoints import generate_waypoints, load_route_config

logger = logging.getLogger(__name__)

# API endpoints
WIND_API_URL = "https://api.open-meteo.com/v1/forecast"
MARINE_API_URL = "https://marine-api.open-meteo.com/v1/marine"

WIND_HOURLY_VARIABLES = ["wind_speed_10m", "wind_direction_10m"]
WIND_CURRENT_VARIABLES = ["wind_speed_10m", "wind_direction_10m"]
MARINE_HOURLY_VARIABLES = ["ocean_current_velocity", "ocean_current_direction", "wave_height"]
MARINE_CURRENT_VARIABLES = ["wave_height", "ocean_current_velocity", "ocean_current_direction"]


# ---------------------------------------------------------------------------
# API setup
# ---------------------------------------------------------------------------

def setup_api_client():
    """Setup Open-Meteo API client with caching and retry logic."""
    cache_session = requests_cache.CachedSession(".cache_pipeline", expire_after=3600)
    retry_session = retry(cache_session, retries=5, backoff_factor=0.2)
    return openmeteo_requests.Client(session=retry_session)


# ---------------------------------------------------------------------------
# Data fetching
# ---------------------------------------------------------------------------

def fetch_wind_data(client, lat, lon):
    """Fetch wind data for a single location.

    Returns:
        (hourly_list, current_dict) — each entry has wind_speed_10m_kmh,
        wind_direction_10m_deg, beaufort_number.
    """
    params = {
        "latitude": lat,
        "longitude": lon,
        "hourly": ",".join(WIND_HOURLY_VARIABLES),
        "current": ",".join(WIND_CURRENT_VARIABLES),
        "timezone": "GMT",
    }

    responses = client.weather_api(WIND_API_URL, params=params)
    response = responses[0]

    # Hourly data
    hourly = response.Hourly()
    hourly_time = pd.date_range(
        start=pd.to_datetime(hourly.Time(), unit="s", utc=True),
        end=pd.to_datetime(hourly.TimeEnd(), unit="s", utc=True),
        freq=pd.Timedelta(seconds=hourly.Interval()),
        inclusive="left",
    )

    wind_speed_values = hourly.Variables(0).ValuesAsNumpy()
    wind_dir_values = hourly.Variables(1).ValuesAsNumpy()

    hourly_data = []
    for i, t in enumerate(hourly_time):
        ws = float(wind_speed_values[i])
        hourly_data.append({
            "time": t.to_pydatetime(),
            "wind_speed_10m_kmh": ws,
            "wind_direction_10m_deg": float(wind_dir_values[i]),
            "beaufort_number": wind_speed_to_beaufort(ws),
        })

    # Current data
    current = response.Current()
    ws_curr = current.Variables(0).Value()
    current_data = {
        "wind_speed_10m_kmh": ws_curr,
        "wind_direction_10m_deg": current.Variables(1).Value(),
        "beaufort_number": wind_speed_to_beaufort(ws_curr),
    }

    return hourly_data, current_data


def fetch_marine_data(client, lat, lon):
    """Fetch marine (wave/current) data for a single location.

    Returns:
        (hourly_list, current_dict) — each entry has wave_height_m,
        ocean_current_velocity_kmh, ocean_current_direction_deg.
    """
    params = {
        "latitude": lat,
        "longitude": lon,
        "hourly": ",".join(MARINE_HOURLY_VARIABLES),
        "current": ",".join(MARINE_CURRENT_VARIABLES),
        "timezone": "GMT",
    }

    responses = client.weather_api(MARINE_API_URL, params=params)
    response = responses[0]

    # Hourly data
    hourly = response.Hourly()
    hourly_time = pd.date_range(
        start=pd.to_datetime(hourly.Time(), unit="s", utc=True),
        end=pd.to_datetime(hourly.TimeEnd(), unit="s", utc=True),
        freq=pd.Timedelta(seconds=hourly.Interval()),
        inclusive="left",
    )

    current_vel_values = hourly.Variables(0).ValuesAsNumpy()
    current_dir_values = hourly.Variables(1).ValuesAsNumpy()
    wave_height_values = hourly.Variables(2).ValuesAsNumpy()

    hourly_data = []
    for i, t in enumerate(hourly_time):
        hourly_data.append({
            "time": t.to_pydatetime(),
            "ocean_current_velocity_kmh": float(current_vel_values[i]),
            "ocean_current_direction_deg": float(current_dir_values[i]),
            "wave_height_m": float(wave_height_values[i]),
        })

    # Current data
    current = response.Current()
    current_data = {
        "wave_height_m": current.Variables(0).Value(),
        "ocean_current_velocity_kmh": current.Variables(1).Value(),
        "ocean_current_direction_deg": current.Variables(2).Value(),
    }

    return hourly_data, current_data


def fetch_waypoint_weather(client, lat, lon, sample_hour, voyage_start_time):
    """Fetch both wind and marine data for a waypoint and combine them.

    Args:
        client: Open-Meteo API client.
        lat, lon: Waypoint coordinates.
        sample_hour: Integer sample hour index.
        voyage_start_time: datetime of voyage start.

    Returns:
        (actual_dict, predicted_rows_list, error_str_or_None)
        actual_dict has the 6 weather fields.
        predicted_rows_list is a list of dicts with forecast_hour, sample_hour, + 6 weather fields.
    """
    try:
        wind_hourly, wind_current = fetch_wind_data(client, lat, lon)
        marine_hourly, marine_current = fetch_marine_data(client, lat, lon)

        # Combine current (actual) conditions
        actual = {
            "wind_speed_10m_kmh": wind_current["wind_speed_10m_kmh"],
            "wind_direction_10m_deg": wind_current["wind_direction_10m_deg"],
            "beaufort_number": wind_current["beaufort_number"],
            "wave_height_m": marine_current["wave_height_m"],
            "ocean_current_velocity_kmh": marine_current["ocean_current_velocity_kmh"],
            "ocean_current_direction_deg": marine_current["ocean_current_direction_deg"],
        }

        # Combine hourly forecasts (predicted conditions)
        marine_by_time = {m["time"]: m for m in marine_hourly}
        predicted_rows = []

        for wind_entry in wind_hourly:
            forecast_time = wind_entry["time"]
            forecast_hours = (forecast_time.replace(tzinfo=None) - voyage_start_time).total_seconds() / 3600
            forecast_hour = round(forecast_hours)

            row = {
                "forecast_hour": forecast_hour,
                "sample_hour": sample_hour,
                "wind_speed_10m_kmh": wind_entry["wind_speed_10m_kmh"],
                "wind_direction_10m_deg": wind_entry["wind_direction_10m_deg"],
                "beaufort_number": wind_entry["beaufort_number"],
            }

            if forecast_time in marine_by_time:
                marine = marine_by_time[forecast_time]
                row["wave_height_m"] = marine["wave_height_m"]
                row["ocean_current_velocity_kmh"] = marine["ocean_current_velocity_kmh"]
                row["ocean_current_direction_deg"] = marine["ocean_current_direction_deg"]
            else:
                row["wave_height_m"] = float("nan")
                row["ocean_current_velocity_kmh"] = float("nan")
                row["ocean_current_direction_deg"] = float("nan")

            predicted_rows.append(row)

        return actual, predicted_rows, None

    except Exception as e:
        return None, None, str(e)


def _nan_actual_row(node_id, sample_hour):
    """Create a NaN actual row for a failed waypoint."""
    return {
        "node_id": node_id,
        "sample_hour": sample_hour,
        "wind_speed_10m_kmh": float("nan"),
        "wind_direction_10m_deg": float("nan"),
        "beaufort_number": 0,
        "wave_height_m": float("nan"),
        "ocean_current_velocity_kmh": float("nan"),
        "ocean_current_direction_deg": float("nan"),
    }


# ---------------------------------------------------------------------------
# Main collection loop
# ---------------------------------------------------------------------------

def collect(config, hdf5_path=None):
    """Run the weather collection loop.

    Args:
        config: Full experiment config dict.
        hdf5_path: Override output path (default: pipeline/data/voyage_weather.h5).

    Supports indefinite collection when hours=0: runs until interrupted.
    Handles SIGINT/SIGTERM gracefully — finishes the current sample, then exits.
    Resumes from the last completed sample_hour on restart.
    """
    # Load route config and generate waypoints
    route_config = load_route_config(config)
    interval_nm = config["collection"].get("interval_nm", 1.0)
    hours = config["collection"].get("hours", 72)
    api_delay = config["collection"].get("api_delay_seconds", 0.1)
    indefinite = hours == 0

    if hdf5_path is None:
        pipeline_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        hdf5_path = os.path.join(pipeline_dir, "data", "voyage_weather.h5")

    waypoints_df = generate_waypoints(route_config, interval_nm=interval_nm)
    print(f"Generated {len(waypoints_df)} waypoints at {interval_nm} nm intervals")

    # Create HDF5 if it doesn't exist
    if not os.path.exists(hdf5_path):
        attrs = {
            "route_name": route_config.get("name", "unknown"),
            "interval_nm": interval_nm,
            "planned_hours": hours,
            "source": "live_collection",
        }
        create_hdf5(hdf5_path, waypoints_df, attrs)
        print(f"Created HDF5 file: {hdf5_path}")

    # Check what's already collected
    completed = get_completed_runs(hdf5_path)
    print(f"Already completed: {len(completed)} runs ({sorted(completed)[-5:] if completed else []})")

    # Determine starting sample_hour for resume
    next_hour = max(completed) + 1 if completed else 0

    # Graceful shutdown via SIGINT/SIGTERM
    shutdown_requested = [False]

    def _signal_handler(signum, frame):
        sig_name = signal.Signals(signum).name
        print(f"\n  [{sig_name}] Shutdown requested — finishing current sample...")
        shutdown_requested[0] = True

    prev_sigint = signal.signal(signal.SIGINT, _signal_handler)
    prev_sigterm = signal.signal(signal.SIGTERM, _signal_handler)

    # Setup API client
    client = setup_api_client()
    voyage_start_time = datetime.now()
    collection_start = time.time()

    try:
        sample_hour = next_hour
        while True:
            # Check bounds for finite mode
            if not indefinite and sample_hour >= hours:
                break

            if sample_hour in completed:
                sample_hour += 1
                continue

            if indefinite:
                print(f"\n--- Sample hour {sample_hour} (indefinite mode) ---")
            else:
                print(f"\n--- Sample hour {sample_hour}/{hours - 1} ---")
            start_time = time.time()

            actual_rows = []
            predicted_rows = []
            successful = 0
            failed = 0

            for _, wp in waypoints_df.iterrows():
                node_id = wp["node_id"]
                lat, lon = wp["lat"], wp["lon"]

                actual, predicted, error = fetch_waypoint_weather(
                    client, lat, lon, sample_hour, voyage_start_time,
                )

                if error:
                    failed += 1
                    if failed <= 5:
                        logger.warning("Node %d (%s): %s", node_id, wp["waypoint_name"], error)
                    actual_rows.append(_nan_actual_row(node_id, sample_hour))
                else:
                    row = {"node_id": node_id, "sample_hour": sample_hour}
                    row.update(actual)
                    actual_rows.append(row)

                    for pr in predicted:
                        pr["node_id"] = node_id
                        predicted_rows.append(pr)
                    successful += 1

                time.sleep(api_delay)

            # Batch append to HDF5
            append_actual(hdf5_path, pd.DataFrame(actual_rows))
            if predicted_rows:
                append_predicted(hdf5_path, pd.DataFrame(predicted_rows))

            elapsed = time.time() - start_time
            wall_hours = (time.time() - collection_start) / 3600
            h5_size_mb = os.path.getsize(hdf5_path) / (1024 * 1024)
            total_collected = len(completed) + (sample_hour - next_hour + 1)
            print(f"  {successful}/{len(waypoints_df)} OK, {failed} failed, {elapsed:.1f}s")
            print(f"  Actual: {len(actual_rows)} rows, Predicted: {len(predicted_rows)} rows")
            print(f"  Total hours collected: {total_collected}, HDF5: {h5_size_mb:.1f} MB, wall: {wall_hours:.1f}h")

            # Check for shutdown request
            if shutdown_requested[0]:
                print(f"\nGraceful shutdown after sample hour {sample_hour}. Output: {hdf5_path}")
                return

            # Wait before next hour
            is_last = not indefinite and sample_hour >= hours - 1
            if not is_last:
                wait = max(0, 3600 - elapsed)
                if wait > 0:
                    print(f"  Waiting {wait/60:.0f} min until next sample...")
                    try:
                        time.sleep(wait)
                    except (KeyboardInterrupt, SystemExit):
                        print(f"\nShutdown during wait after sample hour {sample_hour}. Output: {hdf5_path}")
                        return
                    if shutdown_requested[0]:
                        print(f"\nGraceful shutdown after sample hour {sample_hour}. Output: {hdf5_path}")
                        return

            sample_hour += 1
    finally:
        # Restore original signal handlers
        signal.signal(signal.SIGINT, prev_sigint)
        signal.signal(signal.SIGTERM, prev_sigterm)

    print(f"\nCollection complete. Output: {hdf5_path}")

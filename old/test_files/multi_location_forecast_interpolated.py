#!/usr/bin/env python3
"""
Multi-Location Wind and Wave Forecasting Script - INTERPOLATED WAYPOINTS VERSION

Fetches wind and marine weather data from Open-Meteo API for all 3,388 interpolated
waypoints (at 1 nautical mile intervals) and saves results as pickle files.

Output:
- voyage_nodes_interpolated_weather.pickle: List of Node objects with weather data
"""

import os
import sys
import time
import pickle
from datetime import datetime
from pathlib import Path

import pandas as pd
import openmeteo_requests
import requests_cache
from retry_requests import retry

# ============================================================================
# NODE CLASS
# ============================================================================

class Node:
    def __init__(self):
        self.node_index = None  # Tuple of (longitude, latitude)
        self.Actual_weather_conditions = None  # Dict: {time_from_start: weather_dict}
        self.Predicted_weather_conditions = None  # Dict: {forecast_time: {sample_time: weather_dict}}
        self.waypoint_info = None  # Dict with id, name, is_original, segment, distance_from_start_nm

    def __repr__(self):
        name = self.waypoint_info.get('name', 'Unknown') if self.waypoint_info else 'Unknown'
        return f"Node({name}, index={self.node_index}, actual_samples={len(self.Actual_weather_conditions) if self.Actual_weather_conditions else 0})"


# ============================================================================
# CONFIGURATION
# ============================================================================

# API Configuration
WIND_API_URL = "https://api.open-meteo.com/v1/forecast"
MARINE_API_URL = "https://marine-api.open-meteo.com/v1/marine"

# Schedule Configuration
INTERVAL_MINUTES = 60  # 1 hour
TOTAL_RUNS = 72  # 72 hours (3 days)
DURATION_HOURS = 72

# Output Configuration
SCRIPT_DIR = Path(__file__).parent.absolute()
WAYPOINTS_FILE = SCRIPT_DIR / "waypoints_interpolated.txt"
OUTPUT_FILENAME = "voyage_nodes_interpolated_weather.pickle"
OUTPUT_PATH = SCRIPT_DIR / OUTPUT_FILENAME

# API Variables
WIND_HOURLY_VARIABLES = ["wind_speed_10m", "wind_direction_10m"]
WIND_CURRENT_VARIABLES = ["wind_speed_10m", "wind_direction_10m"]
MARINE_HOURLY_VARIABLES = ["ocean_current_velocity", "ocean_current_direction", "wave_height"]
MARINE_CURRENT_VARIABLES = ["wave_height", "ocean_current_velocity", "ocean_current_direction"]

# Rate limiting - be nice to the API
API_DELAY_SECONDS = 0.1  # Delay between API calls


# ============================================================================
# LOAD WAYPOINTS FROM FILE
# ============================================================================

def load_waypoints_from_file(filepath):
    """Parse waypoints_interpolated.txt and return list of waypoint dicts."""
    waypoints = []

    with open(filepath, 'r') as f:
        lines = f.readlines()

    # Skip header and separator (first 2 lines)
    for line in lines[2:]:
        line = line.strip()
        if not line:
            continue

        # Parse: "   ID |         Name         |        Lat |        Lon |   Dist(nm) | Original"
        parts = [p.strip() for p in line.split('|')]
        if len(parts) >= 6:
            try:
                wp_id = int(parts[0])
                name = parts[1]
                lat = float(parts[2])
                lon = float(parts[3])
                dist_nm = float(parts[4])
                is_original = parts[5].lower() == 'yes'

                waypoints.append({
                    "id": wp_id,
                    "name": name,
                    "lat": lat,
                    "lon": lon,
                    "distance_from_start_nm": dist_nm,
                    "is_original": is_original
                })
            except (ValueError, IndexError):
                continue

    return waypoints


# ============================================================================
# API SETUP
# ============================================================================

def setup_api_client():
    """Setup Open-Meteo API client with caching and retry logic."""
    cache_session = requests_cache.CachedSession('.cache_interpolated', expire_after=3600)
    retry_session = retry(cache_session, retries=5, backoff_factor=0.2)
    return openmeteo_requests.Client(session=retry_session)


# ============================================================================
# BEAUFORT SCALE CONVERSION
# ============================================================================

def wind_speed_to_beaufort(wind_speed_kmh):
    """Convert wind speed (km/h) to Beaufort number."""
    wind_speed_ms = wind_speed_kmh / 3.6

    if wind_speed_ms < 0.5:
        return 0
    elif wind_speed_ms < 1.6:
        return 1
    elif wind_speed_ms < 3.4:
        return 2
    elif wind_speed_ms < 5.5:
        return 3
    elif wind_speed_ms < 8.0:
        return 4
    elif wind_speed_ms < 10.8:
        return 5
    elif wind_speed_ms < 13.9:
        return 6
    elif wind_speed_ms < 17.2:
        return 7
    elif wind_speed_ms < 20.8:
        return 8
    elif wind_speed_ms < 24.5:
        return 9
    elif wind_speed_ms < 28.5:
        return 10
    elif wind_speed_ms < 32.7:
        return 11
    else:
        return 12


# ============================================================================
# DATA FETCHING
# ============================================================================

def fetch_wind_data(client, waypoint):
    """Fetch wind data for a single waypoint."""
    params = {
        "latitude": waypoint["lat"],
        "longitude": waypoint["lon"],
        "hourly": ",".join(WIND_HOURLY_VARIABLES),
        "current": ",".join(WIND_CURRENT_VARIABLES),
        "timezone": "GMT"
    }

    responses = client.weather_api(WIND_API_URL, params=params)
    response = responses[0]

    # Process hourly data
    hourly = response.Hourly()
    hourly_time = pd.date_range(
        start=pd.to_datetime(hourly.Time(), unit="s", utc=True),
        end=pd.to_datetime(hourly.TimeEnd(), unit="s", utc=True),
        freq=pd.Timedelta(seconds=hourly.Interval()),
        inclusive="left"
    )

    hourly_data = []
    wind_speed_values = hourly.Variables(0).ValuesAsNumpy()
    wind_dir_values = hourly.Variables(1).ValuesAsNumpy()

    for i, t in enumerate(hourly_time):
        hourly_data.append({
            "time": t.to_pydatetime(),
            "wind_speed_10m_kmh": float(wind_speed_values[i]),
            "wind_direction_10m_deg": float(wind_dir_values[i]),
            "beaufort_number": wind_speed_to_beaufort(float(wind_speed_values[i]))
        })

    # Process current data
    current = response.Current()
    current_data = {
        "wind_speed_10m_kmh": current.Variables(0).Value(),
        "wind_direction_10m_deg": current.Variables(1).Value(),
        "beaufort_number": wind_speed_to_beaufort(current.Variables(0).Value())
    }

    return hourly_data, current_data


def fetch_marine_data(client, waypoint):
    """Fetch marine (wave/current) data for a single waypoint."""
    params = {
        "latitude": waypoint["lat"],
        "longitude": waypoint["lon"],
        "hourly": ",".join(MARINE_HOURLY_VARIABLES),
        "current": ",".join(MARINE_CURRENT_VARIABLES),
        "timezone": "GMT"
    }

    responses = client.weather_api(MARINE_API_URL, params=params)
    response = responses[0]

    # Process hourly data
    hourly = response.Hourly()
    hourly_time = pd.date_range(
        start=pd.to_datetime(hourly.Time(), unit="s", utc=True),
        end=pd.to_datetime(hourly.TimeEnd(), unit="s", utc=True),
        freq=pd.Timedelta(seconds=hourly.Interval()),
        inclusive="left"
    )

    hourly_data = []
    current_vel_values = hourly.Variables(0).ValuesAsNumpy()
    current_dir_values = hourly.Variables(1).ValuesAsNumpy()
    wave_height_values = hourly.Variables(2).ValuesAsNumpy()

    for i, t in enumerate(hourly_time):
        hourly_data.append({
            "time": t.to_pydatetime(),
            "ocean_current_velocity_kmh": float(current_vel_values[i]),
            "ocean_current_direction_deg": float(current_dir_values[i]),
            "wave_height_m": float(wave_height_values[i])
        })

    # Process current data
    current = response.Current()
    current_data = {
        "wave_height_m": current.Variables(0).Value(),
        "ocean_current_velocity_kmh": current.Variables(1).Value(),
        "ocean_current_direction_deg": current.Variables(2).Value()
    }

    return hourly_data, current_data


def fetch_all_data_for_waypoint(client, waypoint, sample_time, voyage_start_time):
    """Fetch both wind and marine data for a waypoint and combine them."""
    try:
        wind_hourly, wind_current = fetch_wind_data(client, waypoint)
        time.sleep(API_DELAY_SECONDS)  # Rate limiting

        marine_hourly, marine_current = fetch_marine_data(client, waypoint)
        time.sleep(API_DELAY_SECONDS)  # Rate limiting

        # Combine current (actual) conditions
        time_from_start = (sample_time - voyage_start_time).total_seconds() / 3600  # hours

        actual_weather = {
            "wind_speed_10m_kmh": wind_current["wind_speed_10m_kmh"],
            "wind_direction_10m_deg": wind_current["wind_direction_10m_deg"],
            "beaufort_number": wind_current["beaufort_number"],
            "wave_height_m": marine_current["wave_height_m"],
            "ocean_current_velocity_kmh": marine_current["ocean_current_velocity_kmh"],
            "ocean_current_direction_deg": marine_current["ocean_current_direction_deg"]
        }

        # Combine hourly forecasts (predicted conditions)
        predicted_weather = {}
        marine_by_time = {m["time"]: m for m in marine_hourly}

        for wind_entry in wind_hourly:
            forecast_time = wind_entry["time"]
            forecast_hours_from_start = (forecast_time.replace(tzinfo=None) - voyage_start_time).total_seconds() / 3600

            combined = {
                "wind_speed_10m_kmh": wind_entry["wind_speed_10m_kmh"],
                "wind_direction_10m_deg": wind_entry["wind_direction_10m_deg"],
                "beaufort_number": wind_entry["beaufort_number"],
            }

            if forecast_time in marine_by_time:
                marine_entry = marine_by_time[forecast_time]
                combined["wave_height_m"] = marine_entry["wave_height_m"]
                combined["ocean_current_velocity_kmh"] = marine_entry["ocean_current_velocity_kmh"]
                combined["ocean_current_direction_deg"] = marine_entry["ocean_current_direction_deg"]
            else:
                combined["wave_height_m"] = None
                combined["ocean_current_velocity_kmh"] = None
                combined["ocean_current_direction_deg"] = None

            predicted_weather[forecast_hours_from_start] = combined

        return time_from_start, actual_weather, predicted_weather, None

    except Exception as e:
        return None, None, None, str(e)


# ============================================================================
# PICKLE FILE HANDLING
# ============================================================================

def save_data_to_pickle(nodes, voyage_start_time, filepath):
    """Save nodes and voyage_start_time to pickle file."""
    data = {
        'nodes': nodes,
        'voyage_start_time': voyage_start_time
    }
    with open(filepath, 'wb') as f:
        pickle.dump(data, f)


def load_data_from_pickle(filepath):
    """Load nodes and voyage_start_time from pickle file."""
    if not os.path.exists(filepath):
        return None, None

    try:
        with open(filepath, 'rb') as f:
            data = pickle.load(f)
        # Handle both old format (list) and new format (dict)
        if isinstance(data, dict):
            return data.get('nodes'), data.get('voyage_start_time')
        else:
            # Old format - just nodes list
            return data, None
    except Exception as e:
        print(f"Warning: Could not load existing pickle file: {e}")
        return None, None


def initialize_nodes(waypoints):
    """Create Node objects for all waypoints."""
    nodes = []
    for wp in waypoints:
        node = Node()
        node.node_index = (wp["lon"], wp["lat"])
        node.Actual_weather_conditions = {}
        node.Predicted_weather_conditions = {}
        node.waypoint_info = {
            "id": wp["id"],
            "name": wp["name"],
            "is_original": wp["is_original"],
            "distance_from_start_nm": wp["distance_from_start_nm"]
        }
        nodes.append(node)
    return nodes


# ============================================================================
# MAIN EXECUTION
# ============================================================================

def main():
    """Main execution function."""
    print("=" * 70)
    print("Multi-Location Forecast - INTERPOLATED WAYPOINTS (3,388 points)")
    print("=" * 70)
    print(f"Output file: {OUTPUT_PATH}")
    print(f"Schedule: Every {INTERVAL_MINUTES} minutes for {DURATION_HOURS} hours ({TOTAL_RUNS} runs)")
    print("=" * 70)
    print()

    # Load waypoints from file
    print(f"Loading waypoints from: {WAYPOINTS_FILE}")
    waypoints = load_waypoints_from_file(WAYPOINTS_FILE)
    print(f"Loaded {len(waypoints)} waypoints")
    print()

    # Estimate time
    est_time_per_run = len(waypoints) * 2 * API_DELAY_SECONDS / 60  # minutes
    print(f"Estimated time per run: ~{est_time_per_run:.1f} minutes (plus API response time)")
    print()

    # Setup API client
    try:
        client = setup_api_client()
        print("✓ API client initialized")
    except Exception as e:
        print(f"✗ Failed to initialize API client: {e}")
        sys.exit(1)

    # Load existing data or initialize new nodes
    nodes, saved_voyage_start_time = load_data_from_pickle(OUTPUT_PATH)
    if nodes is not None and len(nodes) == len(waypoints):
        completed_runs = len(nodes[0].Actual_weather_conditions) if nodes[0].Actual_weather_conditions else 0
        print(f"Resuming: {completed_runs}/{TOTAL_RUNS} runs already completed")
        if saved_voyage_start_time is not None:
            voyage_start_time = saved_voyage_start_time
        else:
            # Fallback for old format - start fresh timing
            voyage_start_time = datetime.now()
            print("Warning: No saved voyage_start_time, using current time")
    else:
        nodes = initialize_nodes(waypoints)
        completed_runs = 0
        voyage_start_time = datetime.now()
        print("Starting fresh - no previous data found")

    print(f"Voyage start time: {voyage_start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    # Main loop
    run_count = completed_runs

    while run_count < TOTAL_RUNS:
        run_count += 1
        sample_time = datetime.now()

        print(f"\n{'=' * 70}")
        print(f"Run {run_count}/{TOTAL_RUNS} - {sample_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'=' * 70}")

        print(f"Fetching data for {len(waypoints)} waypoints...")

        successful = 0
        failed = 0
        start_time = time.time()

        # Use clean integer sample time (hours from start)
        sample_hour = run_count - 1  # 0, 1, 2, 3, ...

        for i, (wp, node) in enumerate(zip(waypoints, nodes)):
            time_from_start, actual, predicted, error = fetch_all_data_for_waypoint(
                client, wp, sample_time, voyage_start_time
            )

            if error:
                failed += 1
                if failed <= 5:  # Only show first 5 errors
                    print(f"  ✗ [{i+1}/{len(waypoints)}] {wp['name']}: {error}")
            else:
                # Store actual conditions with clean integer key
                node.Actual_weather_conditions[sample_hour] = actual

                # Store predicted conditions with clean integer sample_hour
                for forecast_hours, weather in predicted.items():
                    # Round forecast_hours to nearest integer for cleaner keys
                    forecast_hour_key = round(forecast_hours)
                    if forecast_hour_key not in node.Predicted_weather_conditions:
                        node.Predicted_weather_conditions[forecast_hour_key] = {}
                    node.Predicted_weather_conditions[forecast_hour_key][sample_hour] = weather

                successful += 1

            # Progress update every 100 waypoints
            if (i + 1) % 100 == 0:
                elapsed = time.time() - start_time
                rate = (i + 1) / elapsed
                remaining = (len(waypoints) - i - 1) / rate / 60
                print(f"  Progress: {i+1}/{len(waypoints)} ({successful} ok, {failed} failed) - ETA: {remaining:.1f} min")

        # Save to pickle after each run
        print("\nSaving to pickle file...")
        save_data_to_pickle(nodes, voyage_start_time, OUTPUT_PATH)
        print(f"✓ Data saved to {OUTPUT_PATH}")

        elapsed_total = (time.time() - start_time) / 60
        print(f"✓ Run {run_count}/{TOTAL_RUNS} completed in {elapsed_total:.1f} min: {successful}/{len(waypoints)} successful")

        # Wait before next run
        if run_count < TOTAL_RUNS:
            wait_seconds = INTERVAL_MINUTES * 60
            print(f"\n⏳ Waiting {INTERVAL_MINUTES} minutes until next run...")
            time.sleep(wait_seconds)

    # Final summary
    print("\n" + "=" * 70)
    print("All runs completed!")
    print(f"Output file: {OUTPUT_PATH}")
    print("=" * 70)

    # Print sample of data structure
    print("\nData structure summary:")
    for i, node in enumerate(nodes[:3]):
        print(f"\nNode {i+1}: {node}")
        print(f"  Location: lon={node.node_index[0]}, lat={node.node_index[1]}")
        print(f"  Actual samples: {len(node.Actual_weather_conditions)}")
        print(f"  Forecast times: {len(node.Predicted_weather_conditions)}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nScript interrupted by user")
        print(f"Progress saved to: {OUTPUT_PATH}")
        sys.exit(0)
    except Exception as e:
        print(f"\n\nFatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

#!/usr/bin/env python3
"""
Multi-Location Current and Wave Height Forecasting Script

Fetches marine weather data from Open-Meteo API for all 13 waypoints
from the ship voyage optimization route (Port A to Port B).

Output:
- One Excel file per waypoint OR one combined Excel file with all waypoints
"""

import os
import sys
import time
from datetime import datetime
from pathlib import Path

import pandas as pd
import openmeteo_requests
import requests_cache
from retry_requests import retry

# ============================================================================
# VOYAGE WAYPOINTS (from Table 8 of the research paper)
# ============================================================================

WAYPOINTS = [
    {"id": 1, "name": "Port A", "lat": 24.75, "lon": 52.83},
    {"id": 2, "name": "Waypoint 2", "lat": 26.55, "lon": 56.45},
    {"id": 3, "name": "Waypoint 3", "lat": 24.08, "lon": 60.88},
    {"id": 4, "name": "Waypoint 4", "lat": 21.73, "lon": 65.73},
    {"id": 5, "name": "Waypoint 5", "lat": 17.96, "lon": 69.19},
    {"id": 6, "name": "Waypoint 6", "lat": 14.18, "lon": 72.07},
    {"id": 7, "name": "Waypoint 7", "lat": 10.45, "lon": 75.16},
    {"id": 8, "name": "Waypoint 8", "lat": 7.00, "lon": 78.46},
    {"id": 9, "name": "Waypoint 9", "lat": 5.64, "lon": 82.12},
    {"id": 10, "name": "Waypoint 10", "lat": 4.54, "lon": 87.04},
    {"id": 11, "name": "Waypoint 11", "lat": 5.20, "lon": 92.27},
    {"id": 12, "name": "Waypoint 12", "lat": 5.64, "lon": 97.16},
    {"id": 13, "name": "Port B", "lat": 1.81, "lon": 100.10},
]

# ============================================================================
# CONFIGURATION
# ============================================================================

# API Configuration
API_URL = "https://marine-api.open-meteo.com/v1/marine"

# Schedule Configuration
INTERVAL_MINUTES = 15
TOTAL_RUNS = 12
DURATION_HOURS = 3

# Output Configuration
SCRIPT_DIR = Path(__file__).parent.absolute()
OUTPUT_FILENAME = "multi_location_wave_forecast.xlsx"
OUTPUT_PATH = SCRIPT_DIR / OUTPUT_FILENAME

# API Variables
HOURLY_VARIABLES = ["ocean_current_velocity", "ocean_current_direction", "wave_height"]
CURRENT_VARIABLES = ["wave_height", "ocean_current_velocity", "ocean_current_direction"]

# ============================================================================
# API SETUP
# ============================================================================

def setup_api_client():
    """Setup Open-Meteo API client with caching and retry logic."""
    cache_session = requests_cache.CachedSession('.cache', expire_after=3600)
    retry_session = retry(cache_session, retries=5, backoff_factor=0.2)
    return openmeteo_requests.Client(session=retry_session)


# ============================================================================
# DATA FETCHING
# ============================================================================

def fetch_marine_data_for_waypoint(client, waypoint):
    """
    Fetch marine weather data for a single waypoint.

    Returns:
        tuple: (hourly_data, current_data, metadata)
    """
    params = {
        "latitude": waypoint["lat"],
        "longitude": waypoint["lon"],
        "hourly": ",".join(HOURLY_VARIABLES),
        "current": ",".join(CURRENT_VARIABLES),
        "timezone": "GMT"
    }

    try:
        responses = client.weather_api(API_URL, params=params)
        response = responses[0]

        metadata = {
            "waypoint_id": waypoint["id"],
            "waypoint_name": waypoint["name"],
            "latitude": response.Latitude(),
            "longitude": response.Longitude(),
            "elevation": response.Elevation(),
            "timezone": response.Timezone(),
        }

        # Process hourly data
        hourly = response.Hourly()
        hourly_time = pd.date_range(
            start=pd.to_datetime(hourly.Time(), unit="s", utc=True),
            end=pd.to_datetime(hourly.TimeEnd(), unit="s", utc=True),
            freq=pd.Timedelta(seconds=hourly.Interval()),
            inclusive="left"
        )

        hourly_data = pd.DataFrame({"time": hourly_time})

        for i, variable in enumerate(HOURLY_VARIABLES):
            values = hourly.Variables(i).ValuesAsNumpy()
            if variable == "ocean_current_velocity":
                hourly_data["ocean_current_velocity (km/h)"] = values
            elif variable == "ocean_current_direction":
                hourly_data["ocean_current_direction (°)"] = values
            elif variable == "wave_height":
                hourly_data["wave_height (m)"] = values

        # Process current data
        current = response.Current()
        current_data = {}
        for i, variable in enumerate(CURRENT_VARIABLES):
            if variable == "wave_height":
                current_data["wave_height (m)"] = current.Variables(i).Value()
            elif variable == "ocean_current_velocity":
                current_data["ocean_current_velocity (km/h)"] = current.Variables(i).Value()
            elif variable == "ocean_current_direction":
                current_data["ocean_current_direction (°)"] = current.Variables(i).Value()

        return hourly_data, current_data, metadata

    except Exception as e:
        raise Exception(f"Failed to fetch data for {waypoint['name']}: {str(e)}")


def fetch_all_waypoints(client, sample_time):
    """
    Fetch marine data for all waypoints.

    Returns:
        list of dicts with waypoint data
    """
    all_data = []

    for waypoint in WAYPOINTS:
        try:
            hourly_data, current_data, metadata = fetch_marine_data_for_waypoint(client, waypoint)

            all_data.append({
                "waypoint": waypoint,
                "hourly_data": hourly_data,
                "current_data": current_data,
                "metadata": metadata,
                "sample_time": sample_time
            })

            print(f"  ✓ {waypoint['name']} ({waypoint['lat']}, {waypoint['lon']}): "
                  f"wave={current_data['wave_height (m)']:.2f}m, "
                  f"current={current_data['ocean_current_velocity (km/h)']:.2f}km/h @ "
                  f"{current_data['ocean_current_direction (°)']:.0f}°")

        except Exception as e:
            print(f"  ✗ {waypoint['name']}: {e}")
            all_data.append({
                "waypoint": waypoint,
                "error": str(e),
                "sample_time": sample_time
            })

    return all_data


# ============================================================================
# EXCEL FILE HANDLING
# ============================================================================

def write_combined_excel(excel_path, all_runs_data):
    """
    Write all waypoint data to a single Excel file.

    Structure:
    - Sheet 'summary': Current conditions for all waypoints per sample
    - Sheet 'hourly_forecast': Current conditions at each API call time (same as summary)
    - Sheet 'wp_XX': Hourly forecasts for each waypoint
    """
    with pd.ExcelWriter(excel_path, engine='openpyxl', mode='w') as writer:
        # Build summary sheet
        summary_rows = []

        for run_data in all_runs_data:
            sample_time = run_data["sample_time"]

            for wp_data in run_data["waypoints"]:
                if "error" in wp_data:
                    continue

                waypoint = wp_data["waypoint"]
                current = wp_data["current_data"]

                summary_rows.append({
                    "sample_time": sample_time,
                    "waypoint_id": waypoint["id"],
                    "waypoint_name": waypoint["name"],
                    "latitude": waypoint["lat"],
                    "longitude": waypoint["lon"],
                    "wave_height (m)": current["wave_height (m)"],
                    "ocean_current_velocity (km/h)": current["ocean_current_velocity (km/h)"],
                    "ocean_current_direction (°)": current["ocean_current_direction (°)"],
                })

        if summary_rows:
            summary_df = pd.DataFrame(summary_rows)
            summary_df.to_excel(writer, sheet_name='summary', index=False)
            # Also write as hourly_forecast for consistency with test output format
            summary_df.to_excel(writer, sheet_name='hourly_forecast', index=False)

        # Write hourly forecast for each waypoint (accumulated from ALL runs)
        if all_runs_data:
            # Collect hourly data for each waypoint across all runs
            waypoint_hourly_data = {wp["id"]: [] for wp in WAYPOINTS}

            for run_data in all_runs_data:
                sample_time = run_data["sample_time"]
                for wp_data in run_data["waypoints"]:
                    if "error" in wp_data:
                        continue
                    if wp_data["hourly_data"].empty:
                        continue

                    waypoint = wp_data["waypoint"]
                    hourly_data = wp_data["hourly_data"].copy()

                    # Convert timezone-aware datetime
                    if hourly_data["time"].dt.tz is not None:
                        hourly_data["time"] = hourly_data["time"].dt.tz_localize(None)

                    # Add sample_time to track when this forecast was retrieved
                    hourly_data["sample_time"] = sample_time
                    hourly_data["waypoint_id"] = waypoint["id"]
                    hourly_data["waypoint_name"] = waypoint["name"]
                    hourly_data["latitude"] = waypoint["lat"]
                    hourly_data["longitude"] = waypoint["lon"]

                    waypoint_hourly_data[waypoint["id"]].append(hourly_data)

            # Write accumulated data for each waypoint
            for wp in WAYPOINTS:
                if waypoint_hourly_data[wp["id"]]:
                    combined_hourly = pd.concat(waypoint_hourly_data[wp["id"]], ignore_index=True)

                    # Reorder columns with sample_time first
                    cols = ["sample_time", "waypoint_id", "waypoint_name", "latitude", "longitude", "time",
                            "wave_height (m)", "ocean_current_velocity (km/h)", "ocean_current_direction (°)"]
                    combined_hourly = combined_hourly[cols]

                    sheet_name = f"wp_{wp['id']:02d}"
                    combined_hourly.to_excel(writer, sheet_name=sheet_name, index=False)


def read_existing_data(excel_path):
    """Read existing run data from Excel file."""
    if not os.path.exists(excel_path):
        return []

    try:
        summary_df = pd.read_excel(excel_path, sheet_name='summary')

        # Reconstruct runs from summary
        runs = []
        for sample_time in summary_df['sample_time'].unique():
            sample_data = summary_df[summary_df['sample_time'] == sample_time]

            waypoints_data = []
            for _, row in sample_data.iterrows():
                waypoints_data.append({
                    "waypoint": {
                        "id": row["waypoint_id"],
                        "name": row["waypoint_name"],
                        "lat": row["latitude"],
                        "lon": row["longitude"]
                    },
                    "current_data": {
                        "wave_height (m)": row["wave_height (m)"],
                        "ocean_current_velocity (km/h)": row["ocean_current_velocity (km/h)"],
                        "ocean_current_direction (°)": row["ocean_current_direction (°)"]
                    },
                    "hourly_data": pd.DataFrame(),  # Not restored from summary
                    "sample_time": sample_time
                })

            runs.append({
                "sample_time": sample_time,
                "waypoints": waypoints_data
            })

        return runs

    except Exception as e:
        print(f"Warning: Could not read existing data: {e}")
        return []


# ============================================================================
# MAIN EXECUTION
# ============================================================================

def main():
    """Main execution function."""
    print("=" * 70)
    print("Multi-Location Current and Wave Height Forecasting")
    print("=" * 70)
    print(f"Output file: {OUTPUT_PATH}")
    print(f"Schedule: Every {INTERVAL_MINUTES} minutes for {DURATION_HOURS} hours ({TOTAL_RUNS} runs)")
    print(f"Waypoints: {len(WAYPOINTS)} locations along the voyage route")
    print("=" * 70)
    print()

    # Print waypoints
    print("Waypoints to fetch:")
    for wp in WAYPOINTS:
        print(f"  {wp['id']:2d}. {wp['name']:15s} ({wp['lat']:7.2f}, {wp['lon']:7.2f})")
    print()

    # Setup API client
    try:
        client = setup_api_client()
        print("✓ API client initialized")
    except Exception as e:
        print(f"✗ Failed to initialize API client: {e}")
        sys.exit(1)

    # Load existing data
    all_runs_data = read_existing_data(OUTPUT_PATH)
    completed_runs = len(all_runs_data)

    if completed_runs > 0:
        print(f"Resuming: {completed_runs}/{TOTAL_RUNS} runs already completed")
    else:
        print("Starting fresh - no previous data found")
    print()

    # Main loop
    run_count = completed_runs
    start_time = datetime.now()

    while run_count < TOTAL_RUNS:
        run_count += 1
        sample_time = datetime.now()

        print(f"\n{'=' * 70}")
        print(f"Run {run_count}/{TOTAL_RUNS} - {sample_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'=' * 70}")

        print("Fetching data for all waypoints...")
        waypoints_data = fetch_all_waypoints(client, sample_time)

        # Store run data
        all_runs_data.append({
            "sample_time": sample_time,
            "waypoints": waypoints_data
        })

        # Write to Excel
        print("\nWriting to Excel file...")
        write_combined_excel(OUTPUT_PATH, all_runs_data)
        print(f"✓ Data written to {OUTPUT_PATH}")

        successful = sum(1 for wp in waypoints_data if "error" not in wp)
        print(f"✓ Run {run_count}/{TOTAL_RUNS} completed: {successful}/{len(WAYPOINTS)} waypoints successful")

        # Wait before next run
        if run_count < TOTAL_RUNS:
            wait_seconds = INTERVAL_MINUTES * 60
            print(f"\n⏳ Waiting {INTERVAL_MINUTES} minutes until next run...")
            time.sleep(wait_seconds)

    # Final summary
    elapsed_time = datetime.now() - start_time
    print("\n" + "=" * 70)
    print("All runs completed!")
    print(f"Total time: {elapsed_time}")
    print(f"Output file: {OUTPUT_PATH}")
    print("=" * 70)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nScript interrupted by user")
        print(f"Progress saved to: {OUTPUT_PATH}")
        sys.exit(0)
    except Exception as e:
        print(f"\n\nFatal error: {e}")
        sys.exit(1)

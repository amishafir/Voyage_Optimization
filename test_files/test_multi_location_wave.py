#!/usr/bin/env python3
"""
Test script for multi_location_wave_forecasting.py

Uses pytest parameterization to test wave/current data fetching
across multiple GPS locations from the voyage route.

Compatible with gps-test-scaler agent patterns.
"""

import os
import sys
from datetime import datetime
from pathlib import Path

import pytest
import pandas as pd
import openmeteo_requests
import requests_cache
from retry_requests import retry

# ============================================================================
# GPS TEST LOCATIONS
# Centralized location data following gps-test-scaler agent patterns
# ============================================================================

# Voyage waypoints from Table 8 of the research paper
VOYAGE_WAYPOINTS = [
    {"id": 1, "name": "Port A (Persian Gulf)", "lat": 24.75, "lon": 52.83},
    {"id": 2, "name": "Waypoint 2 (Gulf of Oman)", "lat": 26.55, "lon": 56.45},
    {"id": 3, "name": "Waypoint 3 (Arabian Sea)", "lat": 24.08, "lon": 60.88},
    {"id": 4, "name": "Waypoint 4 (Arabian Sea)", "lat": 21.73, "lon": 65.73},
    {"id": 5, "name": "Waypoint 5 (Arabian Sea)", "lat": 17.96, "lon": 69.19},
    {"id": 6, "name": "Waypoint 6 (Arabian Sea)", "lat": 14.18, "lon": 72.07},
    {"id": 7, "name": "Waypoint 7 (Indian Ocean)", "lat": 10.45, "lon": 75.16},
    {"id": 8, "name": "Waypoint 8 (Indian Ocean)", "lat": 7.00, "lon": 78.46},
    {"id": 9, "name": "Waypoint 9 (Bay of Bengal)", "lat": 5.64, "lon": 82.12},
    {"id": 10, "name": "Waypoint 10 (Indian Ocean)", "lat": 4.54, "lon": 87.04},
    {"id": 11, "name": "Waypoint 11 (Andaman Sea)", "lat": 5.20, "lon": 92.27},
    {"id": 12, "name": "Waypoint 12 (Andaman Sea)", "lat": 5.64, "lon": 97.16},
    {"id": 13, "name": "Port B (Strait of Malacca)", "lat": 1.81, "lon": 100.10},
]

# Edge case locations for comprehensive testing
EDGE_CASE_LOCATIONS = [
    {"id": 100, "name": "Equator Indian Ocean", "lat": 0.0, "lon": 80.0},
    {"id": 101, "name": "Southern Hemisphere", "lat": -10.0, "lon": 85.0},
    {"id": 102, "name": "Deep Ocean (Mid-Atlantic)", "lat": 30.0, "lon": -40.0},
]

# Combined test locations
GPS_TEST_LOCATIONS = VOYAGE_WAYPOINTS + EDGE_CASE_LOCATIONS

# ============================================================================
# CONFIGURATION
# ============================================================================

API_URL = "https://marine-api.open-meteo.com/v1/marine"
HOURLY_VARIABLES = ["ocean_current_velocity", "ocean_current_direction", "wave_height"]
CURRENT_VARIABLES = ["wave_height", "ocean_current_velocity", "ocean_current_direction"]

SCRIPT_DIR = Path(__file__).parent.absolute()
OUTPUT_FILENAME = "test_multi_wave_forecast.xlsx"
OUTPUT_PATH = SCRIPT_DIR / OUTPUT_FILENAME

# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture(scope="module")
def api_client():
    """Setup Open-Meteo API client with caching."""
    cache_session = requests_cache.CachedSession('.cache', expire_after=300)
    retry_session = retry(cache_session, retries=5, backoff_factor=0.2)
    return openmeteo_requests.Client(session=retry_session)


@pytest.fixture(scope="module")
def all_results():
    """Shared storage for collecting results across parameterized tests."""
    return {"waypoints": [], "sample_time": None}


# ============================================================================
# API FUNCTIONS
# ============================================================================

def fetch_marine_data(client, lat, lon):
    """
    Fetch marine weather data for a single GPS coordinate.

    Args:
        client: Open-Meteo API client
        lat: Latitude
        lon: Longitude

    Returns:
        tuple: (hourly_data, current_data, success)
    """
    params = {
        "latitude": lat,
        "longitude": lon,
        "hourly": ",".join(HOURLY_VARIABLES),
        "current": ",".join(CURRENT_VARIABLES),
        "timezone": "GMT"
    }

    try:
        responses = client.weather_api(API_URL, params=params)
        response = responses[0]

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
        current_data = {
            "wave_height (m)": current.Variables(0).Value(),
            "ocean_current_velocity (km/h)": current.Variables(1).Value(),
            "ocean_current_direction (°)": current.Variables(2).Value(),
        }

        return hourly_data, current_data, True

    except Exception as e:
        return None, {"error": str(e)}, False


# ============================================================================
# PARAMETERIZED TESTS
# ============================================================================

class TestMarineDataFetching:
    """Test suite for marine data fetching across multiple GPS locations."""

    @pytest.mark.parametrize(
        "location",
        VOYAGE_WAYPOINTS,
        ids=[wp["name"] for wp in VOYAGE_WAYPOINTS]
    )
    def test_fetch_voyage_waypoint(self, api_client, location):
        """Test fetching marine data for each voyage waypoint."""
        hourly_data, current_data, success = fetch_marine_data(
            api_client, location["lat"], location["lon"]
        )

        # API call should succeed
        assert success, f"API call failed for {location['name']}: {current_data.get('error')}"

        # Should return hourly data
        assert hourly_data is not None, f"No hourly data for {location['name']}"
        assert len(hourly_data) > 0, f"Empty hourly data for {location['name']}"

        # Check data structure
        expected_columns = ["time", "wave_height (m)", "ocean_current_velocity (km/h)", "ocean_current_direction (°)"]
        for col in expected_columns:
            assert col in hourly_data.columns, f"Missing column {col} for {location['name']}"

        # Log results (some locations may have NaN for marine data near coasts)
        wave = current_data.get("wave_height (m)")
        current_vel = current_data.get("ocean_current_velocity (km/h)")
        print(f"\n  {location['name']}: wave={wave}, current={current_vel}")

    @pytest.mark.parametrize(
        "location",
        EDGE_CASE_LOCATIONS,
        ids=[loc["name"] for loc in EDGE_CASE_LOCATIONS]
    )
    def test_fetch_edge_case_location(self, api_client, location):
        """Test fetching marine data for edge case GPS locations."""
        hourly_data, current_data, success = fetch_marine_data(
            api_client, location["lat"], location["lon"]
        )

        # API call should succeed (even if data is NaN)
        assert success, f"API call failed for {location['name']}: {current_data.get('error')}"

        print(f"\n  {location['name']} ({location['lat']}, {location['lon']}): "
              f"wave={current_data.get('wave_height (m)')}, "
              f"current={current_data.get('ocean_current_velocity (km/h)')}")


class TestDataValidation:
    """Test suite for validating marine data values."""

    @pytest.mark.parametrize(
        "location",
        [wp for wp in VOYAGE_WAYPOINTS if wp["id"] <= 12],  # Exclude Port B which has NaN
        ids=[wp["name"] for wp in VOYAGE_WAYPOINTS if wp["id"] <= 12]
    )
    def test_wave_height_reasonable(self, api_client, location):
        """Test that wave height values are within reasonable bounds."""
        _, current_data, success = fetch_marine_data(
            api_client, location["lat"], location["lon"]
        )

        if success:
            wave_height = current_data.get("wave_height (m)")
            if wave_height is not None and not pd.isna(wave_height):
                # Wave height should be between 0 and 20 meters (reasonable ocean range)
                assert 0 <= wave_height <= 20, \
                    f"Unreasonable wave height {wave_height}m at {location['name']}"

    @pytest.mark.parametrize(
        "location",
        [wp for wp in VOYAGE_WAYPOINTS if wp["id"] <= 12],
        ids=[wp["name"] for wp in VOYAGE_WAYPOINTS if wp["id"] <= 12]
    )
    def test_current_direction_valid(self, api_client, location):
        """Test that ocean current direction is within valid range (0-360 degrees)."""
        _, current_data, success = fetch_marine_data(
            api_client, location["lat"], location["lon"]
        )

        if success:
            direction = current_data.get("ocean_current_direction (°)")
            if direction is not None and not pd.isna(direction):
                assert 0 <= direction <= 360, \
                    f"Invalid current direction {direction}° at {location['name']}"


class TestExcelOutput:
    """Test suite for Excel output generation."""

    def test_generate_combined_excel(self, api_client):
        """Test generating combined Excel output for all waypoints."""
        sample_time = datetime.now()
        all_data = []

        # Fetch data for all voyage waypoints
        for location in VOYAGE_WAYPOINTS:
            hourly_data, current_data, success = fetch_marine_data(
                api_client, location["lat"], location["lon"]
            )

            all_data.append({
                "location": location,
                "hourly_data": hourly_data,
                "current_data": current_data,
                "success": success,
                "sample_time": sample_time
            })

        # Write to Excel
        write_test_excel(OUTPUT_PATH, all_data, sample_time)

        # Verify file was created
        assert OUTPUT_PATH.exists(), f"Excel file not created at {OUTPUT_PATH}"

        # Verify sheet structure
        xls = pd.ExcelFile(OUTPUT_PATH)
        assert "summary" in xls.sheet_names, "Missing 'summary' sheet"
        assert "hourly_forecast" in xls.sheet_names, "Missing 'hourly_forecast' sheet"
        assert len(xls.sheet_names) == 15, f"Expected 15 sheets, got {len(xls.sheet_names)}"

        # Verify summary content
        summary = pd.read_excel(OUTPUT_PATH, sheet_name="summary")
        assert len(summary) == len(VOYAGE_WAYPOINTS), \
            f"Summary should have {len(VOYAGE_WAYPOINTS)} rows"

        print(f"\n  Excel file created: {OUTPUT_PATH}")
        print(f"  Sheets: {xls.sheet_names}")


# ============================================================================
# EXCEL OUTPUT HELPER
# ============================================================================

def write_test_excel(excel_path, all_data, sample_time):
    """Write test results to Excel file."""
    # Read existing hourly_forecast data if file exists
    existing_hourly = None
    if os.path.exists(excel_path):
        try:
            existing_hourly = pd.read_excel(excel_path, sheet_name='hourly_forecast')
        except (ValueError, KeyError):
            pass

    with pd.ExcelWriter(excel_path, engine='openpyxl', mode='w') as writer:
        # Build summary sheet (current conditions for all waypoints)
        summary_rows = []
        for item in all_data:
            if not item["success"]:
                continue

            location = item["location"]
            current = item["current_data"]

            summary_rows.append({
                "sample_time": sample_time,
                "waypoint_id": location["id"],
                "waypoint_name": location["name"],
                "latitude": location["lat"],
                "longitude": location["lon"],
                "wave_height (m)": current.get("wave_height (m)"),
                "ocean_current_velocity (km/h)": current.get("ocean_current_velocity (km/h)"),
                "ocean_current_direction (°)": current.get("ocean_current_direction (°)"),
            })

        if summary_rows:
            summary_df = pd.DataFrame(summary_rows)
            summary_df.to_excel(writer, sheet_name='summary', index=False)

        # Build hourly_forecast sheet (current conditions at each sample time)
        # This accumulates across multiple test runs
        hourly_rows = []
        for item in all_data:
            if not item["success"]:
                continue

            location = item["location"]
            current = item["current_data"]

            hourly_rows.append({
                "sample_time": sample_time,
                "waypoint_id": location["id"],
                "waypoint_name": location["name"],
                "latitude": location["lat"],
                "longitude": location["lon"],
                "wave_height (m)": current.get("wave_height (m)"),
                "ocean_current_velocity (km/h)": current.get("ocean_current_velocity (km/h)"),
                "ocean_current_direction (°)": current.get("ocean_current_direction (°)"),
            })

        if hourly_rows:
            new_hourly_df = pd.DataFrame(hourly_rows)
            # Combine with existing data
            if existing_hourly is not None:
                hourly_df = pd.concat([existing_hourly, new_hourly_df], ignore_index=True)
            else:
                hourly_df = new_hourly_df
            hourly_df.to_excel(writer, sheet_name='hourly_forecast', index=False)

        # Write per-waypoint sheets
        for item in all_data:
            if not item["success"] or item["hourly_data"] is None:
                continue

            location = item["location"]
            hourly_data = item["hourly_data"].copy()

            if hourly_data["time"].dt.tz is not None:
                hourly_data["time"] = hourly_data["time"].dt.tz_localize(None)

            hourly_data["waypoint_id"] = location["id"]
            hourly_data["waypoint_name"] = location["name"]
            hourly_data["latitude"] = location["lat"]
            hourly_data["longitude"] = location["lon"]

            cols = ["waypoint_id", "waypoint_name", "latitude", "longitude", "time",
                    "wave_height (m)", "ocean_current_velocity (km/h)", "ocean_current_direction (°)"]
            hourly_data = hourly_data[cols]

            sheet_name = f"wp_{location['id']:02d}"
            hourly_data.to_excel(writer, sheet_name=sheet_name, index=False)


# ============================================================================
# STANDALONE EXECUTION (for quick testing without pytest)
# ============================================================================

def run_standalone_test():
    """Run a quick standalone test without pytest."""
    print("=" * 70)
    print("STANDALONE TEST: Multi-Location Wave Forecasting")
    print("=" * 70)

    # Setup client
    cache_session = requests_cache.CachedSession('.cache', expire_after=300)
    retry_session = retry(cache_session, retries=5, backoff_factor=0.2)
    client = openmeteo_requests.Client(session=retry_session)

    print(f"\nTesting {len(GPS_TEST_LOCATIONS)} locations...")

    success_count = 0
    for location in GPS_TEST_LOCATIONS:
        hourly_data, current_data, success = fetch_marine_data(
            client, location["lat"], location["lon"]
        )

        status = "✓" if success else "✗"
        wave = current_data.get("wave_height (m)", "N/A")
        current_vel = current_data.get("ocean_current_velocity (km/h)", "N/A")

        print(f"  {status} {location['name']:35s} ({location['lat']:7.2f}, {location['lon']:7.2f}): "
              f"wave={wave}, current={current_vel}")

        if success:
            success_count += 1

    print(f"\nResults: {success_count}/{len(GPS_TEST_LOCATIONS)} locations successful")
    print("=" * 70)


if __name__ == "__main__":
    # If run directly, execute standalone test
    # For pytest, run: pytest test_multi_location_wave.py -v
    run_standalone_test()

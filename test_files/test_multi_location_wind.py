#!/usr/bin/env python3
"""
Test script for multi_location_wind_forecasting.py

Uses pytest parameterization to test wind data fetching
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
    {"id": 103, "name": "High Latitude (North Sea)", "lat": 55.0, "lon": 3.0},
]

# Combined test locations
GPS_TEST_LOCATIONS = VOYAGE_WAYPOINTS + EDGE_CASE_LOCATIONS

# ============================================================================
# CONFIGURATION
# ============================================================================

API_URL = "https://api.open-meteo.com/v1/forecast"
HOURLY_VARIABLES = ["wind_speed_10m", "wind_direction_10m"]
CURRENT_VARIABLES = ["wind_speed_10m", "wind_direction_10m"]

SCRIPT_DIR = Path(__file__).parent.absolute()
OUTPUT_FILENAME = "test_multi_wind_forecast.xlsx"
OUTPUT_PATH = SCRIPT_DIR / OUTPUT_FILENAME

# ============================================================================
# BEAUFORT SCALE CONVERSION
# ============================================================================

def wind_speed_to_beaufort(wind_speed_kmh):
    """
    Convert wind speed (km/h) to Beaufort number.

    The Beaufort scale is used in the research paper for speed correction
    calculations (Tables 2-4 in the paper).
    """
    if wind_speed_kmh is None or pd.isna(wind_speed_kmh):
        return None

    wind_speed_ms = wind_speed_kmh / 3.6

    if wind_speed_ms < 0.5:
        return 0   # Calm
    elif wind_speed_ms < 1.6:
        return 1   # Light air
    elif wind_speed_ms < 3.4:
        return 2   # Light breeze
    elif wind_speed_ms < 5.5:
        return 3   # Gentle breeze
    elif wind_speed_ms < 8.0:
        return 4   # Moderate breeze
    elif wind_speed_ms < 10.8:
        return 5   # Fresh breeze
    elif wind_speed_ms < 13.9:
        return 6   # Strong breeze
    elif wind_speed_ms < 17.2:
        return 7   # High wind
    elif wind_speed_ms < 20.8:
        return 8   # Gale
    elif wind_speed_ms < 24.5:
        return 9   # Strong gale
    elif wind_speed_ms < 28.5:
        return 10  # Storm
    elif wind_speed_ms < 32.7:
        return 11  # Violent storm
    else:
        return 12  # Hurricane


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture(scope="module")
def api_client():
    """Setup Open-Meteo API client with caching."""
    cache_session = requests_cache.CachedSession('.cache', expire_after=300)
    retry_session = retry(cache_session, retries=5, backoff_factor=0.2)
    return openmeteo_requests.Client(session=retry_session)


# ============================================================================
# API FUNCTIONS
# ============================================================================

def fetch_wind_data(client, lat, lon):
    """
    Fetch wind weather data for a single GPS coordinate.

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
            if variable == "wind_speed_10m":
                hourly_data["wind_speed_10m (km/h)"] = values
            elif variable == "wind_direction_10m":
                hourly_data["wind_direction_10m (°)"] = values

        # Process current data
        current = response.Current()
        wind_speed = current.Variables(0).Value()
        current_data = {
            "wind_speed_10m (km/h)": wind_speed,
            "wind_direction_10m (°)": current.Variables(1).Value(),
            "beaufort_number": wind_speed_to_beaufort(wind_speed),
        }

        return hourly_data, current_data, True

    except Exception as e:
        return None, {"error": str(e)}, False


# ============================================================================
# PARAMETERIZED TESTS
# ============================================================================

class TestWindDataFetching:
    """Test suite for wind data fetching across multiple GPS locations."""

    @pytest.mark.parametrize(
        "location",
        VOYAGE_WAYPOINTS,
        ids=[wp["name"] for wp in VOYAGE_WAYPOINTS]
    )
    def test_fetch_voyage_waypoint(self, api_client, location):
        """Test fetching wind data for each voyage waypoint."""
        hourly_data, current_data, success = fetch_wind_data(
            api_client, location["lat"], location["lon"]
        )

        # API call should succeed
        assert success, f"API call failed for {location['name']}: {current_data.get('error')}"

        # Should return hourly data
        assert hourly_data is not None, f"No hourly data for {location['name']}"
        assert len(hourly_data) > 0, f"Empty hourly data for {location['name']}"

        # Check data structure
        expected_columns = ["time", "wind_speed_10m (km/h)", "wind_direction_10m (°)"]
        for col in expected_columns:
            assert col in hourly_data.columns, f"Missing column {col} for {location['name']}"

        # Log results
        wind_speed = current_data.get("wind_speed_10m (km/h)")
        beaufort = current_data.get("beaufort_number")
        direction = current_data.get("wind_direction_10m (°)")
        print(f"\n  {location['name']}: wind={wind_speed:.1f}km/h (BN={beaufort}) @ {direction:.0f}°")

    @pytest.mark.parametrize(
        "location",
        EDGE_CASE_LOCATIONS,
        ids=[loc["name"] for loc in EDGE_CASE_LOCATIONS]
    )
    def test_fetch_edge_case_location(self, api_client, location):
        """Test fetching wind data for edge case GPS locations."""
        hourly_data, current_data, success = fetch_wind_data(
            api_client, location["lat"], location["lon"]
        )

        # API call should succeed
        assert success, f"API call failed for {location['name']}: {current_data.get('error')}"

        wind_speed = current_data.get("wind_speed_10m (km/h)")
        beaufort = current_data.get("beaufort_number")
        print(f"\n  {location['name']} ({location['lat']}, {location['lon']}): "
              f"wind={wind_speed:.1f}km/h (BN={beaufort})")


class TestBeaufortConversion:
    """Test suite for Beaufort scale conversion."""

    @pytest.mark.parametrize(
        "wind_kmh,expected_bn",
        [
            (0, 0),      # Calm
            (8, 2),      # Light breeze (2.2 m/s)
            (15, 3),     # Gentle breeze
            (25, 4),     # Moderate breeze
            (35, 5),     # Fresh breeze
            (50, 6),     # Strong breeze
            (70, 8),     # Gale
            (100, 10),   # Storm
            (120, 12),   # Hurricane
        ],
        ids=["calm", "light_breeze", "gentle", "moderate", "fresh", "strong", "gale", "storm", "hurricane"]
    )
    def test_beaufort_conversion(self, wind_kmh, expected_bn):
        """Test Beaufort scale conversion accuracy."""
        result = wind_speed_to_beaufort(wind_kmh)
        assert result == expected_bn, f"Expected BN {expected_bn} for {wind_kmh}km/h, got {result}"

    def test_beaufort_none_handling(self):
        """Test that None and NaN inputs are handled gracefully."""
        assert wind_speed_to_beaufort(None) is None
        assert wind_speed_to_beaufort(float('nan')) is None


class TestDataValidation:
    """Test suite for validating wind data values."""

    @pytest.mark.parametrize(
        "location",
        VOYAGE_WAYPOINTS,
        ids=[wp["name"] for wp in VOYAGE_WAYPOINTS]
    )
    def test_wind_speed_reasonable(self, api_client, location):
        """Test that wind speed values are within reasonable bounds."""
        _, current_data, success = fetch_wind_data(
            api_client, location["lat"], location["lon"]
        )

        if success:
            wind_speed = current_data.get("wind_speed_10m (km/h)")
            if wind_speed is not None and not pd.isna(wind_speed):
                # Wind speed should be between 0 and 200 km/h (reasonable range)
                assert 0 <= wind_speed <= 200, \
                    f"Unreasonable wind speed {wind_speed}km/h at {location['name']}"

    @pytest.mark.parametrize(
        "location",
        VOYAGE_WAYPOINTS,
        ids=[wp["name"] for wp in VOYAGE_WAYPOINTS]
    )
    def test_wind_direction_valid(self, api_client, location):
        """Test that wind direction is within valid range (0-360 degrees)."""
        _, current_data, success = fetch_wind_data(
            api_client, location["lat"], location["lon"]
        )

        if success:
            direction = current_data.get("wind_direction_10m (°)")
            if direction is not None and not pd.isna(direction):
                assert 0 <= direction <= 360, \
                    f"Invalid wind direction {direction}° at {location['name']}"

    @pytest.mark.parametrize(
        "location",
        VOYAGE_WAYPOINTS,
        ids=[wp["name"] for wp in VOYAGE_WAYPOINTS]
    )
    def test_beaufort_in_valid_range(self, api_client, location):
        """Test that Beaufort number is within valid range (0-12)."""
        _, current_data, success = fetch_wind_data(
            api_client, location["lat"], location["lon"]
        )

        if success:
            beaufort = current_data.get("beaufort_number")
            if beaufort is not None:
                assert 0 <= beaufort <= 12, \
                    f"Invalid Beaufort number {beaufort} at {location['name']}"


class TestExcelOutput:
    """Test suite for Excel output generation."""

    def test_generate_combined_excel(self, api_client):
        """Test generating combined Excel output for all waypoints."""
        sample_time = datetime.now()
        all_data = []

        # Fetch data for all voyage waypoints
        for location in VOYAGE_WAYPOINTS:
            hourly_data, current_data, success = fetch_wind_data(
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
        assert "beaufort_number" in summary.columns, "Missing beaufort_number column"

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
                "wind_speed_10m (km/h)": current.get("wind_speed_10m (km/h)"),
                "wind_direction_10m (°)": current.get("wind_direction_10m (°)"),
                "beaufort_number": current.get("beaufort_number"),
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
                "wind_speed_10m (km/h)": current.get("wind_speed_10m (km/h)"),
                "wind_direction_10m (°)": current.get("wind_direction_10m (°)"),
                "beaufort_number": current.get("beaufort_number"),
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

            # Add Beaufort number
            hourly_data["beaufort_number"] = hourly_data["wind_speed_10m (km/h)"].apply(wind_speed_to_beaufort)

            hourly_data["waypoint_id"] = location["id"]
            hourly_data["waypoint_name"] = location["name"]
            hourly_data["latitude"] = location["lat"]
            hourly_data["longitude"] = location["lon"]

            cols = ["waypoint_id", "waypoint_name", "latitude", "longitude", "time",
                    "wind_speed_10m (km/h)", "wind_direction_10m (°)", "beaufort_number"]
            hourly_data = hourly_data[cols]

            sheet_name = f"wp_{location['id']:02d}"
            hourly_data.to_excel(writer, sheet_name=sheet_name, index=False)


# ============================================================================
# STANDALONE EXECUTION (for quick testing without pytest)
# ============================================================================

def run_standalone_test():
    """Run a quick standalone test without pytest."""
    print("=" * 70)
    print("STANDALONE TEST: Multi-Location Wind Forecasting")
    print("=" * 70)

    # Setup client
    cache_session = requests_cache.CachedSession('.cache', expire_after=300)
    retry_session = retry(cache_session, retries=5, backoff_factor=0.2)
    client = openmeteo_requests.Client(session=retry_session)

    print(f"\nTesting {len(GPS_TEST_LOCATIONS)} locations...")

    success_count = 0
    for location in GPS_TEST_LOCATIONS:
        hourly_data, current_data, success = fetch_wind_data(
            client, location["lat"], location["lon"]
        )

        status = "✓" if success else "✗"
        wind_speed = current_data.get("wind_speed_10m (km/h)", 0)
        beaufort = current_data.get("beaufort_number", "N/A")
        direction = current_data.get("wind_direction_10m (°)", 0)

        if success:
            print(f"  {status} {location['name']:35s} ({location['lat']:7.2f}, {location['lon']:7.2f}): "
                  f"wind={wind_speed:.1f}km/h (BN={beaufort}) @ {direction:.0f}°")
            success_count += 1
        else:
            print(f"  {status} {location['name']:35s}: ERROR - {current_data.get('error')}")

    print(f"\nResults: {success_count}/{len(GPS_TEST_LOCATIONS)} locations successful")
    print("=" * 70)


if __name__ == "__main__":
    # If run directly, execute standalone test
    # For pytest, run: pytest test_multi_location_wind.py -v
    run_standalone_test()

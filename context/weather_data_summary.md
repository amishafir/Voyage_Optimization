# Weather Forecast Data Summary

**Data Collection Period:** January 28 - February 1, 2026
**Total Runs:** 288 samples (every 15 minutes for ~72 hours)
**Route:** Persian Gulf (Port A) to Strait of Malacca (Port B)

---

## Overview

Two Excel files containing marine weather forecasts for 13 waypoints along the voyage route:

| File | Size | Contents |
|------|------|----------|
| `multi_location_wave_forecast.xlsx` | 22 MB | Wave height, ocean current velocity & direction |
| `multi_location_wind_forecast.xlsx` | 30 MB | Wind speed, direction, Beaufort number |

### Data Volume

| Metric | Value |
|--------|-------|
| Summary samples | 3,744 per file (288 runs × 13 waypoints) |
| Hourly forecast rows | 602,784 per file |
| Forecast horizon | 168 hours (7 days) per sample |

---

## File Structure

Both files contain **15 sheets**:

| Sheet | Description |
|-------|-------------|
| `summary` | Current conditions at sample time (288 samples × 13 waypoints) |
| `hourly_forecast` | Duplicate of summary sheet |
| `wp_01` - `wp_13` | 7-day hourly forecasts for each waypoint (168 hours × 276 samples) |

### Column Definitions

**Wave Forecast Columns:**
- `sample_time` - When the data was collected
- `waypoint_id` - Waypoint number (1-13)
- `waypoint_name` - Location name
- `latitude`, `longitude` - GPS coordinates
- `time` - Forecast timestamp (in wp sheets)
- `wave_height (m)` - Significant wave height in meters
- `ocean_current_velocity (km/h)` - Current speed
- `ocean_current_direction (°)` - Current direction (meteorological)

**Wind Forecast Columns:**
- `wind_speed_10m (km/h)` - Wind speed at 10m height
- `wind_direction_10m (°)` - Wind direction (meteorological)
- `beaufort_number` - Calculated Beaufort scale (0-12)

---

## Waypoint Coordinates

| WP | Name | Latitude | Longitude | Location |
|----|------|----------|-----------|----------|
| 1 | Port A | 24.75 | 52.83 | Persian Gulf |
| 2 | Waypoint 2 | 26.55 | 56.45 | Gulf of Oman |
| 3 | Waypoint 3 | 24.08 | 60.88 | Arabian Sea |
| 4 | Waypoint 4 | 21.73 | 65.73 | Arabian Sea |
| 5 | Waypoint 5 | 17.96 | 69.19 | Arabian Sea |
| 6 | Waypoint 6 | 14.18 | 72.07 | Arabian Sea |
| 7 | Waypoint 7 | 10.45 | 75.16 | Indian Ocean |
| 8 | Waypoint 8 | 7.00 | 78.46 | Indian Ocean |
| 9 | Waypoint 9 | 5.64 | 82.12 | Bay of Bengal |
| 10 | Waypoint 10 | 4.54 | 87.04 | Indian Ocean |
| 11 | Waypoint 11 | 5.20 | 92.27 | Andaman Sea |
| 12 | Waypoint 12 | 5.64 | 97.16 | Andaman Sea |
| 13 | Port B | 1.81 | 100.10 | Strait of Malacca |

---

## Wave & Current Statistics

### Wave Height (meters)

| Waypoint | Mean | Std Dev | Min | Max |
|----------|------|---------|-----|-----|
| Port A | 0.47 | 0.27 | 0.12 | 0.94 |
| Waypoint 2 | 0.48 | 0.21 | 0.20 | 0.78 |
| Waypoint 3 | 0.61 | 0.10 | 0.48 | 0.80 |
| Waypoint 4 | 0.75 | 0.05 | 0.66 | 0.84 |
| Waypoint 5 | 0.84 | 0.15 | 0.70 | 1.38 |
| Waypoint 6 | 1.02 | 0.10 | 0.84 | 1.22 |
| Waypoint 7 | 0.98 | 0.11 | 0.86 | 1.28 |
| **Waypoint 8** | **1.67** | 0.09 | 1.46 | **1.92** |
| Waypoint 9 | 1.56 | 0.15 | 1.34 | 1.82 |
| Waypoint 10 | 1.54 | 0.07 | 1.40 | 1.64 |
| Waypoint 11 | 1.54 | 0.04 | 1.46 | 1.60 |
| Waypoint 12 | 0.51 | 0.09 | 0.40 | 0.70 |
| Port B | NaN | NaN | NaN | NaN |

### Ocean Current Velocity (km/h)

| Waypoint | Mean | Std Dev | Min | Max |
|----------|------|---------|-----|-----|
| Port A | 1.03 | 0.44 | 0.26 | 2.17 |
| **Waypoint 2** | 1.48 | 0.99 | 0.18 | **3.85** |
| Waypoint 3 | 0.56 | 0.14 | 0.26 | 0.81 |
| Waypoint 4 | 0.99 | 0.15 | 0.72 | 1.37 |
| Waypoint 5 | 0.82 | 0.16 | 0.26 | 1.05 |
| Waypoint 6 | 1.15 | 0.34 | 0.65 | 1.91 |
| Waypoint 7 | 1.32 | 0.43 | 0.40 | 2.31 |
| Waypoint 8 | 0.97 | 0.24 | 0.54 | 1.44 |
| **Waypoint 9** | **2.20** | 0.34 | 1.66 | 2.75 |
| Waypoint 10 | 0.72 | 0.16 | 0.36 | 1.02 |
| Waypoint 11 | 0.61 | 0.40 | 0.00 | 1.31 |
| Waypoint 12 | 0.46 | 0.19 | 0.00 | 0.81 |
| Port B | NaN | NaN | NaN | NaN |

---

## Wind Statistics

### Wind Speed (km/h)

| Waypoint | Mean | Std Dev | Min | Max | Avg Beaufort |
|----------|------|---------|-----|-----|--------------|
| Port A | 14.1 | 9.6 | 1.6 | 33.1 | 2.6 |
| Waypoint 2 | 21.4 | 7.8 | 3.6 | 34.2 | 3.6 |
| Waypoint 3 | 12.3 | 4.0 | 1.3 | 18.4 | 2.5 |
| Waypoint 4 | 18.4 | 2.7 | 12.4 | 23.1 | 3.3 |
| Waypoint 5 | 13.7 | 4.9 | 4.4 | 29.7 | 2.7 |
| Waypoint 6 | 17.7 | 5.5 | 5.4 | 29.6 | 3.2 |
| Waypoint 7 | 12.2 | 5.7 | 3.2 | 25.0 | 2.4 |
| **Waypoint 8** | **32.4** | 2.2 | 27.0 | **38.3** | **4.9** |
| Waypoint 9 | 24.0 | 4.4 | 15.0 | 33.0 | 3.9 |
| Waypoint 10 | 8.3 | 3.3 | 3.4 | 17.6 | 1.9 |
| Waypoint 11 | 15.6 | 5.2 | 5.5 | 25.0 | 2.9 |
| Waypoint 12 | 15.6 | 4.9 | 7.3 | 24.4 | 2.9 |
| Port B | 4.3 | 2.2 | 0.0 | 9.2 | 1.1 |

### Beaufort Scale Reference

| BN | Description | Wind Speed (km/h) |
|----|-------------|-------------------|
| 0-1 | Calm to Light Air | 0 - 5.8 |
| 2-3 | Light to Gentle Breeze | 5.8 - 19.8 |
| 4-5 | Moderate to Fresh Breeze | 19.8 - 38.9 |
| 6-7 | Strong Breeze to High Wind | 38.9 - 61.9 |

---

## Daily Trends

### Wave Conditions

| Date | Avg Wave Height (m) | Avg Current (km/h) |
|------|---------------------|-------------------|
| Jan 28 | 1.05 | 1.02 |
| Jan 29 | 0.99 | 1.03 |
| Jan 30 | 1.01 | 1.04 |
| Jan 31 | 1.00 | 1.04 |
| Feb 01 | 0.96 | 0.97 |

### Wind Conditions

| Date | Avg Wind Speed (km/h) | Avg Beaufort |
|------|----------------------|--------------|
| Jan 28 | 18.4 | 3.2 |
| Jan 29 | 13.8 | 2.6 |
| Jan 30 | 16.5 | 3.0 |
| Jan 31 | 16.6 | 3.0 |
| Feb 01 | 16.7 | 3.0 |

---

## Critical Segments Analysis

Segments ranked by combined environmental difficulty (normalized wave height + wind speed + current velocity):

| Rank | Waypoint | Wave (m) | Wind (km/h) | Current (km/h) | Difficulty Score |
|------|----------|----------|-------------|----------------|------------------|
| 1 | **Waypoint 9** | 1.70 | 24.0 | 2.20 | 0.91 |
| 2 | **Waypoint 8** | 1.92 | 32.4 | 0.97 | 0.81 |
| 3 | Waypoint 5 | 1.32 | 13.7 | 0.82 | 0.58 |
| 4 | Waypoint 6 | 1.16 | 17.7 | 1.15 | 0.56 |
| 5 | Waypoint 11 | 1.46 | 15.6 | 0.61 | 0.55 |

**Key Finding:** Waypoints 8 and 9 (Bay of Bengal / Indian Ocean crossing) present the most challenging conditions with:
- Highest wave heights (1.67-1.70m average)
- Strongest winds (24-32 km/h, Beaufort 4-5)
- Strong currents at WP9 (2.2 km/h average)

---

## Environmental Correlations

| Variables | Correlation |
|-----------|-------------|
| Wave height ↔ Wind speed | 0.69 |
| Wave height ↔ Beaufort number | 0.63 |
| Wind speed ↔ Beaufort number | 0.97 |
| Current velocity ↔ Wave height | 0.26 |

Strong correlation between wind and waves confirms wind-driven wave generation. Ocean currents show weak correlation with other variables, operating more independently.

---

## Data Quality Notes

1. **Port B (Waypoint 13)**: Returns NaN values for wave and current data. This is expected as the location (1.81°N, 100.10°E) is near the coast of Malaysia, outside Open-Meteo Marine API coverage.

2. **Wind data**: Complete coverage for all 13 waypoints including Port B.

3. **Missing values**: 288 NaN entries in wave/current data (all from Port B, 288 samples × 1 waypoint).

---

## Usage for Speed Optimization

This data feeds into the ship speed optimization models:

1. **Linear Programming Model**: Uses segment-averaged conditions from the summary sheet
2. **Dynamic Graph Model**: Uses time-varying hourly forecasts from waypoint sheets

Key parameters for SOG/FCR calculations:
- Wave height → Wave resistance (Tables 2-4 coefficients based on Beaufort)
- Wind speed/direction → Wind resistance coefficient
- Current velocity/direction → Effective speed adjustment (favorable/adverse)

---

*Generated: February 1, 2026*

# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Maritime ship speed optimization research project for minimizing fuel consumption and GHG emissions. Compares Linear Programming with graph-based dynamic optimization for multi-segment voyages under varying environmental conditions (ocean currents, wind, waves).

## Common Commands

### Install Dependencies

```bash
# For weather forecasting scripts (root level)
pip3 install -r requirements_marine.txt

# For optimization modules
pip3 install -r "Linear programing/requirements.txt"
```

### Run Weather Forecasting

```bash
# Wind data from Open-Meteo API
python3 wind_forecasting.py

# Ocean currents and wave data
python3 current_wave_forecasting.py
```

### Run Optimization

```bash
# Linear programming with PuLP (open-source)
python3 "Linear programing/ship_speed_optimization_pulp.py"

# Linear programming with Gurobi (requires license)
python3 "Linear programing/Gurobi.py"

# Dynamic graph-based optimization
python3 "Dynamic speed optimization/speed_control_optimizer.py"
```

### Run Tests

```bash
cd test_files
python3 test_forecasting.py
```

### Remote Server Execution

```bash
cd remote_server_scripts
./run_remote_python.sh <script_name.py>
```

## Architecture

### Two Optimization Approaches

1. **Linear Programming** (`Linear programing/`): Static optimization where weather is constant per segment. Uses SOS2 (Special Ordered Set Type 2) variables for piecewise linear approximation of nonlinear SOG-FCR relationships.

2. **Dynamic Optimization** (`Dynamic speed optimization/`): Graph-based approach with time-distance nodes that handles time-varying weather conditions. Creates a directed graph where edges represent speed choices and Dijkstra-like algorithms find minimum fuel paths.

### Core Mathematical Functions

`utility_functions.py` (exists in both modules) implements the research paper formulas:
- **SOG calculation**: Speed Over Ground as function of Ship Speed in Still Water, wind, waves, currents
- **FCR calculation**: Fuel Consumption Rate (cubic relationship with power)
- **Resistance components**: Wind resistance, wave resistance, current effects

### Data Flow

```
Weather API (Open-Meteo)
    ↓
wind_forecasting.py / current_wave_forecasting.py
    ↓
Excel output (2 sheets: daily_forecast, hourly_forecast)
    ↓
ship_parameters.yaml + weather_forecasts.yaml
    ↓
Optimizer (LP or Dynamic Graph)
    ↓
Optimal speed schedule per segment
```

### Key Configuration Files

- `Dynamic speed optimization/ship_parameters.yaml`: Ship specs (200m length, 32m beam, 10,000 kW, 11-13 knot range)
- `Dynamic speed optimization/weather_forecasts.yaml`: Time-windowed environmental conditions
- `Linear programing/voyage_data.py`: 12-segment route with per-segment environmental data

### Interactive Calculators

- `interactive_sog_calculator.py`: Forward calculation (SWS → SOG given environmental conditions)
- `interactive_sws_calculator.py`: Inverse calculation (desired SOG → required SWS)

## Output Format

Weather forecasting scripts produce Excel files with two sheets:
- `daily_forecast`: Hourly forecasts for 7 days with metadata rows
- `hourly_forecast`: Current condition samples (one row per API call)

Multi-location scripts (`multi_location_wind_forecasting.py`, `multi_location_wave_forecasting.py`) produce Excel files with 14 sheets:
- `summary`: Current conditions for all 13 waypoints
- `wp_01` through `wp_13`: Hourly forecasts for each waypoint

## Important Technical Notes

### Beaufort Number Calculation

The Beaufort number is **calculated from wind speed**, not obtained from the Open-Meteo API. The API only provides `wind_speed_10m` (km/h) and `wind_direction_10m` (degrees).

**Conversion formula** (used in `multi_location_wind_forecasting.py` and test files):
```python
# Convert km/h to m/s, then map to Beaufort scale
wind_speed_ms = wind_speed_kmh / 3.6

# Beaufort thresholds (m/s):
# BN 0: < 0.5    (Calm)
# BN 1: < 1.6    (Light air)
# BN 2: < 3.4    (Light breeze)
# BN 3: < 5.5    (Gentle breeze)
# BN 4: < 8.0    (Moderate breeze)
# BN 5: < 10.8   (Fresh breeze)
# BN 6: < 13.9   (Strong breeze)
# BN 7: < 17.2   (High wind)
# BN 8: < 20.8   (Gale)
# BN 9: < 24.5   (Strong gale)
# BN 10: < 28.5  (Storm)
# BN 11: < 32.7  (Violent storm)
# BN 12: >= 32.7 (Hurricane)
```

**Why this matters**: The research paper uses Beaufort number as an index into Tables 2-4 for wind and wave resistance correction coefficients. These tables provide `C1`-`C6` coefficients for calculating speed reduction due to environmental conditions.

### GPS Waypoints

The 13 waypoints (defining 12 voyage segments) are from Table 8 of the research paper, covering the route from Port A (Persian Gulf) to Port B (Strait of Malacca):

| WP | Latitude | Longitude | Location |
|----|----------|-----------|----------|
| 1 | 24.75 | 52.83 | Port A (Persian Gulf) |
| 2 | 26.55 | 56.45 | Gulf of Oman |
| 3 | 24.08 | 60.88 | Arabian Sea |
| 4 | 21.73 | 65.73 | Arabian Sea |
| 5 | 17.96 | 69.19 | Arabian Sea |
| 6 | 14.18 | 72.07 | Arabian Sea |
| 7 | 10.45 | 75.16 | Indian Ocean |
| 8 | 7.00 | 78.46 | Indian Ocean |
| 9 | 5.64 | 82.12 | Bay of Bengal |
| 10 | 4.54 | 87.04 | Indian Ocean |
| 11 | 5.20 | 92.27 | Andaman Sea |
| 12 | 5.64 | 97.16 | Andaman Sea |
| 13 | 1.81 | 100.10 | Port B (Strait of Malacca) |

**Note**: Port B (waypoint 13) may return NaN for marine data as it's close to the coast, outside Open-Meteo Marine API coverage.

### Pickle-Based Weather Data Collection

The `multi_location_forecast_pickle.py` script collects weather data and stores it in a pickle file using the `Node` class structure for use with the dynamic optimization approach.

**Run command:**
```bash
cd test_files
python3 multi_location_forecast_pickle.py
```

**Deploy to server:**
```bash
cd remote_server_scripts
./deploy_pickle_forecast.sh
```

**Node Class Structure** (`class.py`):
```python
class Node:
    node_index = (longitude, latitude)  # Tuple
    Actual_weather_conditions = {
        time_from_start_hours: {weather_dict}
    }
    Predicted_weather_conditions = {
        forecast_time_hours: {
            sample_time_hours: {weather_dict}
        }
    }
```

**Weather dict fields:**
- `wind_speed_10m_kmh`
- `wind_direction_10m_deg`
- `beaufort_number`
- `wave_height_m`
- `ocean_current_velocity_kmh`
- `ocean_current_direction_deg`

**Data structure visualization:**
```
voyage_nodes.pickle
└── List[Node] (13 nodes)
    └── Node[i]
        ├── node_index: (lon, lat)
        ├── Actual_weather_conditions: {t_hours: {weather}}
        └── Predicted_weather_conditions: {forecast_t: {sample_t: {weather}}}
```

**Visualize pickle contents:**
```bash
cd test_files
python3 visualize_pickle_data.py
```

### Intermediate Waypoint Generation

The `generate_intermediate_waypoints.py` script creates additional waypoints at 1 nautical mile intervals along the geodesic (great circle) path between the original 13 waypoints.

**Run command:**
```bash
cd test_files
python3 generate_intermediate_waypoints.py
```

**Output:**
- `voyage_nodes_interpolated.pickle` - 3,388 Node objects (original + intermediate)
- `waypoints_interpolated.txt` - Human-readable waypoint list
- `voyage_route_map.html` - Interactive map visualization

**Statistics:**
- Original waypoints: 13
- Total waypoints: 3,388 (at 1 nm intervals)
- Total voyage distance: 3,393.5 nm

**Interpolated Node structure:**
```python
node.node_index = (lon, lat)
node.Actual_weather_conditions = {}
node.Predicted_weather_conditions = {}
node.waypoint_info = {
    "id": 5,
    "name": "WP1-2_5nm",
    "is_original": False,
    "segment": 0,
    "distance_from_start_nm": 5.0
}
```

**Segment distances:**
| Segment | From | To | Distance (nm) |
|---------|------|-----|---------------|
| 1 | Port A | WP 2 | 223.8 |
| 2 | WP 2 | WP 3 | 282.5 |
| 3 | WP 3 | WP 4 | 303.2 |
| 4 | WP 4 | WP 5 | 298.4 |
| 5 | WP 5 | WP 6 | 280.5 |
| 6 | WP 6 | WP 7 | 287.3 |
| 7 | WP 7 | WP 8 | 284.4 |
| 8 | WP 8 | WP 9 | 233.3 |
| 9 | WP 9 | WP 10 | 301.8 |
| 10 | WP 10 | WP 11 | 315.7 |
| 11 | WP 11 | WP 12 | 293.8 |
| 12 | WP 12 | Port B | 288.8 |

### Speed Control Optimizer Analysis

For detailed analysis of the dynamic programming optimizer, voyage strategies comparison, and simulation framework, see:

**[.claude/speed_control_optimizer_analysis.md](.claude/speed_control_optimizer_analysis.md)**

Contents:
- Voyage optimization strategies evolution (Research Paper → LP → DP → Simulation)
- Strategy comparison matrix (LP vs DP approaches)
- Time window integration (6-hour windows)
- Multi-forecast ensemble techniques
- Voyage simulation & comparison framework
- Data transformation pipeline (API → YAML format)
- Uncertainty-aware optimization methods

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

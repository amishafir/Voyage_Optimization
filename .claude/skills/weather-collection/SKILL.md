# Pickle-Based Weather Data Collection

## Overview

The `multi_location_forecast_pickle.py` script collects weather data and stores it in a pickle file using the `Node` class structure for use with the dynamic optimization approach.

## Run Command

```bash
cd test_files
python3 multi_location_forecast_pickle.py
```

## Deploy to Server

```bash
cd remote_server_scripts
./deploy_pickle_forecast.sh
```

## Node Class Structure (`class.py`)

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

## Weather Dict Fields

- `wind_speed_10m_kmh`
- `wind_direction_10m_deg`
- `beaufort_number`
- `wave_height_m`
- `ocean_current_velocity_kmh`
- `ocean_current_direction_deg`

## Data Structure Visualization

```
voyage_nodes.pickle
└── List[Node] (13 nodes)
    └── Node[i]
        ├── node_index: (lon, lat)
        ├── Actual_weather_conditions: {t_hours: {weather}}
        └── Predicted_weather_conditions: {forecast_t: {sample_t: {weather}}}
```

## Visualize Pickle Contents

```bash
cd test_files
python3 visualize_pickle_data.py
```

## Collection Parameters

- 13 original waypoints (or 3,388 interpolated)
- 72 hourly samples over 3 days
- 7-day (168-hour) forecast horizon per sample
- Both actual conditions and forecasts stored per waypoint

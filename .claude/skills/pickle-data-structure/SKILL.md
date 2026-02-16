# Pickle Data Structure Documentation

## Overview

The `voyage_nodes_interpolated_weather.pickle` file stores weather data for all 3,388 waypoints collected over 72 hours. The structure is designed to support all three optimization approaches.

## File Structure

```python
{
    'nodes': List[Node],           # 3,388 Node objects
    'voyage_start_time': datetime  # When data collection began
}
```

## Node Class Structure

```python
class Node:
    node_index: (longitude, latitude)  # Tuple
    waypoint_info: {
        'id': int,                      # 1 to 3388
        'name': str,                    # "Port A", "WP1-2_5nm", etc.
        'is_original': bool,            # True for 13 original waypoints
        'distance_from_start_nm': float # Nautical miles from Port A
    }
    Actual_weather_conditions: {
        sample_hour: weather_dict       # Key: 0, 1, 2, ... 71
    }
    Predicted_weather_conditions: {
        forecast_hour: {
            sample_hour: weather_dict   # Nested: forecast[t][s]
        }
    }
```

## Weather Dict Fields

```python
weather_dict = {
    'wind_speed_10m_kmh': float,
    'wind_direction_10m_deg': float,    # 0-360, from North
    'beaufort_number': int,              # 0-12, calculated from wind speed
    'wave_height_m': float,
    'ocean_current_velocity_kmh': float,
    'ocean_current_direction_deg': float # Direction current flows TO
}
```

## Key Design: Integer Sample Times

Sample times use **clean integers** (0, 1, 2, ...) representing hours from voyage start:

```
Run 1 → sample_hour = 0
Run 2 → sample_hour = 1
Run 3 → sample_hour = 2
...
Run 72 → sample_hour = 71
```

This ensures predictable keys for all optimization approaches.

## Data Access Patterns

### Actual Weather (Ground Truth)

```python
# Weather at waypoint i, at hour t
actual = nodes[i].Actual_weather_conditions[t]
```

**Example:** Actual weather at Port A at hour 5
```python
nodes[0].Actual_weather_conditions[5]
# Returns: {'wind_speed_10m_kmh': 12.3, 'wave_height_m': 1.2, ...}
```

### Predicted Weather (Forecasts)

```python
# Forecast for hour t, made at sample hour s
forecast = nodes[i].Predicted_weather_conditions[t][s]
```

**Example:** Forecast for hour 24, made at hour 0 (voyage start)
```python
nodes[0].Predicted_weather_conditions[24][0]
```

**Example:** Forecast for hour 24, made at hour 6 (updated forecast)
```python
nodes[0].Predicted_weather_conditions[24][6]
```

## Supporting the Three Approaches

### 1. Static Deterministic (Baseline / LP)

**Needs:** Single weather snapshot, constant for entire voyage

**Data Access:**
```python
# Use actual weather from hour 0 (or average)
for node in nodes:
    weather = node.Actual_weather_conditions[0]
```

**Aggregation:** Average per segment (12 segments from 13 original waypoints)

---

### 2. Dynamic Deterministic

**Needs:** Time-varying forecast made at voyage start (hour 0)

**Data Access:**
```python
# For each future hour t, use forecast made at hour 0
for t in range(0, voyage_duration):
    for node in nodes:
        weather = node.Predicted_weather_conditions[t][0]
```

**Key insight:** Uses `Predicted[t][0]` - forecast for time t, made at sample time 0

---

### 3. Dynamic Rolling Horizon (Online Re-planning)

**Needs:** At decision point t, use latest forecast for remaining voyage

**Data Access:**
```python
# At decision point t=6, re-plan remaining voyage
decision_hour = 6
for future_t in range(decision_hour, voyage_duration):
    for node in nodes:
        # Use forecast made at decision time
        weather = node.Predicted_weather_conditions[future_t][decision_hour]
```

**Key insight:** Uses `Predicted[future_t][decision_hour]` - forecast for future time, made at current decision point

---

## Visualization of Data Structure

```
voyage_nodes_interpolated_weather.pickle
│
├── voyage_start_time: datetime
│
└── nodes: List[Node] (3,388 nodes)
    │
    ├── Node[0] (Port A)
    │   ├── node_index: (52.83, 24.75)
    │   ├── waypoint_info: {id: 1, name: "Port A", is_original: True, ...}
    │   │
    │   ├── Actual_weather_conditions:
    │   │   ├── 0: {wind: 5.2, wave: 0.3, ...}   ← Hour 0 actual
    │   │   ├── 1: {wind: 5.8, wave: 0.4, ...}   ← Hour 1 actual
    │   │   ├── 2: {wind: 6.1, wave: 0.4, ...}   ← Hour 2 actual
    │   │   └── ... (72 samples total)
    │   │
    │   └── Predicted_weather_conditions:
    │       ├── 0:  {0: {...}}                   ← Forecast for hour 0
    │       ├── 1:  {0: {...}, 1: {...}}         ← Forecast for hour 1
    │       ├── 2:  {0: {...}, 1: {...}, 2: {...}}
    │       ├── ...
    │       ├── 24: {0: {...}, 1: {...}, ..., 24: {...}}
    │       │        ↑         ↑              ↑
    │       │        │         │              └── Made at hour 24
    │       │        │         └── Made at hour 1
    │       │        └── Made at hour 0
    │       └── ... (168 forecast hours, up to 7 days ahead)
    │
    ├── Node[1] (WP1-2_1nm)
    │   └── ... (same structure)
    │
    └── ... (3,388 nodes total)
```

## Forecast Horizon

The Open-Meteo API provides **7-day (168-hour)** forecasts. At each sample time:

| Sample Hour | Forecasts Available |
|-------------|---------------------|
| 0 | Hours 0 to 167 |
| 1 | Hours 1 to 168 |
| 6 | Hours 6 to 173 |
| 24 | Hours 24 to 191 |

## Resume Logic

The pickle stores `voyage_start_time` to enable correct resumption:

```python
# On save
data = {
    'nodes': nodes,
    'voyage_start_time': voyage_start_time
}

# On load
nodes, voyage_start_time = load_data_from_pickle(filepath)
completed_runs = len(nodes[0].Actual_weather_conditions)
# Resume from run (completed_runs + 1)
```

## Data Validation

After collection, verify structure supports all approaches:

```python
node = nodes[0]

# Check actual samples
assert len(node.Actual_weather_conditions) == 72
assert all(h in node.Actual_weather_conditions for h in range(72))

# Check forecasts from hour 0 exist for all future hours
assert all(0 in node.Predicted_weather_conditions.get(t, {})
           for t in range(168))

# Check forecasts from each decision hour exist
for decision_hour in range(72):
    for future_hour in range(decision_hour, min(decision_hour + 168, 240)):
        assert decision_hour in node.Predicted_weather_conditions.get(future_hour, {}), \
            f"Missing forecast for hour {future_hour} made at hour {decision_hour}"
```

## File Size Estimate

- 3,388 nodes
- 72 actual samples per node
- ~168 forecast hours x ~72 sample times per forecast
- ~6 weather fields per dict

Estimated size: **150-200 MB**

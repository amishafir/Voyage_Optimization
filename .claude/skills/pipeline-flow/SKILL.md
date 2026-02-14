# Voyage Optimization Pipeline Flow

## Overview

A structured pipeline for comparing voyage optimization strategies. One data collection feeds multiple optimization approaches, all evaluated against actual weather conditions.

## Three Approaches

| Approach | Weather Model | Forecast Certainty | Re-planning | Optimizer |
|----------|--------------|-------------------|-------------|-----------|
| **Static Deterministic** | Constant (single value) | Assumes perfect | No | LP |
| **Dynamic Deterministic** | Time-varying | Assumes perfect | No | DP |
| **Dynamic Stochastic** | Time-varying | Acknowledges uncertainty | Yes | DP |

### Static Deterministic (Baseline / LP)
- Weather: Static (same everywhere, entire voyage)
- Forecast: Deterministic (one forecast, assumed correct)
- Planning: Once before departure
- Optimizer: LP

### Dynamic Deterministic
- Weather: Dynamic (varies by location + time)
- Forecast: Deterministic (one forecast, assumed correct)
- Planning: Once before departure
- Optimizer: DP

### Dynamic Stochastic
- Weather: Dynamic (varies by location + time)
- Forecast: Stochastic (forecast evolves, has uncertainty)
- Planning: Multiple times during voyage (rolling horizon)
- Optimizer: DP (repeatedly)

## Pipeline Diagram

```
┌─────────────────────────────────────────────────────────────┐
│  1. DATA COLLECTION                                         │
│     - 3,388 waypoints (1nm intervals)                       │
│     - 72h hourly samples                                    │
│     - Forecasts + Actuals                                   │
│     Output: voyage_nodes.pickle                             │
└─────────────────────────┬───────────────────────────────────┘
                          │
        ┌─────────────────┴─────────────────┐
        ↓                                   ↓
┌───────────────────┐               ┌───────────────────┐
│ 2a. TRANSFORM(LP) │               │ 2b. TRANSFORM(DP) │
│                   │               │                   │
│ - Aggregate per   │               │ - Time-window     │
│   segment (12)    │               │   slices          │
│ - Static average  │               │ - Per-node        │
│                   │               │   weather         │
│ Output: YAML      │               │ Output: YAML      │
└────────┬──────────┘               └─────────┬─────────┘
         ↓                                    ↓
┌───────────────────┐               ┌───────────────────┐
│ 3a. LP OPTIMIZER  │               │ 3b. DP OPTIMIZER  │
│                   │               │                   │
│ - Static weather  │               │ - Time-varying    │
│ - Single solution │               │ - Graph-based     │
│                   │               │                   │
│ Output:           │               │ Output:           │
│ speed_plan_lp     │               │ speed_plan_dp     │
└────────┬──────────┘               └─────────┬─────────┘
         │                                    │
         └──────────────┬─────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────────┐
│  4. SIMULATION                                              │
│                                                             │
│     Strategy A: Static Deterministic (Baseline / LP)        │
│       - Plan once before voyage                             │
│       - Assume static weather                               │
│       - Execute fixed plan                                  │
│                                                             │
│     Strategy B: Dynamic Deterministic                       │
│       - Plan once before voyage                             │
│       - Use time-varying forecast                           │
│       - Execute fixed plan                                  │
│                                                             │
│     Strategy C: Dynamic Stochastic (rolling horizon)        │
│       - Re-plan at decision points during voyage            │
│       - Use latest available forecast                       │
│       - Execute next segment, repeat                        │
│                                                             │
│  All strategies executed against ACTUAL weather             │
│  Output: voyage_results_{static_det, dyn_det, dyn_stoch}    │
└─────────────────────────┬───────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│  5. COMPARISON                                              │
│     - Fuel consumption                                      │
│     - Arrival time                                          │
│     - Plan vs Reality deviation                             │
│     - Value of DP over LP                                   │
│     - Value of online adaptation                            │
│     Output: analysis_report                                 │
└─────────────────────────────────────────────────────────────┘
```

## Stages Detail

### 1. Data Collection

**Script:** `test_files/multi_location_forecast_interpolated.py`

**Input:**
- GPS coordinates (3,388 waypoints at 1nm intervals)

**Output:**
- `voyage_nodes.pickle` - List of Node objects

**Data Structure:**
```python
Node:
  node_index: (lon, lat)
  waypoint_info: {id, name, is_original, distance_from_start_nm}
  Actual_weather_conditions: {
    time_from_start_hours: {weather_dict}
  }
  Predicted_weather_conditions: {
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

---

### 2a. Transform (LP)

**Purpose:** Prepare data for Linear Programming optimizer

**Aggregation:**
- Spatial: 12 segments (average conditions between waypoints)
- Temporal: Single static value per segment

**Output Format:** YAML compatible with LP optimizer

---

### 2b. Transform (DP)

**Purpose:** Prepare data for Dynamic Programming optimizer

**Aggregation:**
- Spatial: Per-node (3,388 waypoints)
- Temporal: Time-windowed (e.g., 6-hour windows)

**Output Format:** YAML compatible with DP optimizer

---

### 3a. LP Optimizer

**Script:** `Linear programing/ship_speed_optimization_pulp.py`

**Approach:**
- Static weather per segment
- SOS2 variables for piecewise linear FCR
- Single optimization run

**Output:** Speed schedule (one speed per segment)

---

### 3b. DP Optimizer

**Script:** `Dynamic speed optimization/speed_control_optimizer.py`

**Approach:**
- Time-varying weather
- Graph-based (nodes = time-distance states)
- Dijkstra-like shortest path for minimum fuel

**Output:** Speed schedule (speed at each time-distance node)

---

### 4. Simulation

**Purpose:** Execute optimization plans against actual weather

**Three Strategies:**

| Strategy | Optimizer | Re-planning | Description |
|----------|-----------|-------------|-------------|
| Static Deterministic | LP | None | Baseline - static weather, plan once |
| Dynamic Deterministic | DP | None | Time-varying weather, plan once |
| Dynamic Stochastic | DP | At decision points | Rolling horizon re-planning |

**Dynamic Stochastic Decision Points:**
- Option A: Every N hours (e.g., 6h)
- Option B: At each original waypoint (13 points)
- TBD based on analysis

**Simulation tracks:**
- Position over time
- Actual speed achieved (SOG)
- Fuel consumed
- Deviation from plan

---

### 5. Comparison

**Metrics:**

| Metric | Description |
|--------|-------------|
| Total fuel | Sum of fuel consumed over voyage |
| Voyage time | Total time from Port A to Port B |
| Arrival accuracy | Deviation from target arrival time |
| Plan stability | How much speed schedule changed (online) |
| Forecast error impact | Correlation between forecast error and performance |

**Key Questions Answered:**
1. Value of dynamic weather modeling? (Dynamic Det. vs Static Det.)
2. Value of adapting to forecast uncertainty? (Dynamic Stoch. vs Dynamic Det.)
3. When is re-planning most valuable? (high forecast uncertainty periods)

---

## File Structure

```
test_files/
├── multi_location_forecast_interpolated.py  # Stage 1: Data Collection
├── waypoints_interpolated.txt
├── transform_static_det.py                  # Stage 2a: Transform for LP (TBD)
├── transform_dynamic.py                     # Stage 2b: Transform for DP (TBD)
├── simulate_voyage.py                       # Stage 4: Simulation (TBD)
└── compare_strategies.py                    # Stage 5: Comparison (TBD)

Linear programing/
└── ship_speed_optimization_pulp.py          # Stage 3a: Static Deterministic

Dynamic speed optimization/
└── speed_control_optimizer.py               # Stage 3b: Dynamic Det. & Stoch.
```

---

## Current Status

- [x] Stage 1: Data Collection - running on server (72h)
- [ ] Stage 2a: Transform (Static Deterministic) - TBD
- [ ] Stage 2b: Transform (Dynamic) - TBD
- [ ] Stage 3a: Static Deterministic Optimizer (LP) - exists, may need updates
- [ ] Stage 3b: Dynamic Optimizer (DP) - exists, may need updates
- [ ] Stage 4: Simulation framework - TBD
- [ ] Stage 5: Comparison framework - TBD

## Research Questions

| Comparison | Tests the value of... |
|------------|----------------------|
| Dynamic Det. vs Static Det. | Modeling weather as time-varying |
| Dynamic Stoch. vs Dynamic Det. | Adapting to forecast uncertainty |

# Work Breakdown Structure (WBS) - Next Phases

## Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              PIPELINE STRUCTURE                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────────────┐                                                       │
│  │  DATA COLLECTION │  (Shared)                                             │
│  │  voyage_nodes    │                                                       │
│  │  .pickle         │                                                       │
│  └────────┬─────────┘                                                       │
│           │                                                                  │
│     ┌─────┼─────────────────┬─────────────────────┐                         │
│     ▼     ▼                 ▼                     ▼                         │
│  ┌─────────────┐     ┌─────────────┐     ┌─────────────┐                   │
│  │   STATIC    │     │  DYNAMIC    │     │  DYNAMIC    │                   │
│  │DETERMINISTIC│     │DETERMINISTIC│     │ STOCHASTIC  │                   │
│  │             │     │             │     │             │                   │
│  │ transform   │     │ transform   │     │ transform   │                   │
│  │ optimize    │     │ optimize    │     │ optimize    │                   │
│  │ simulate    │     │ simulate    │     │ simulate    │                   │
│  │ evaluate    │     │ evaluate    │     │ evaluate    │                   │
│  └──────┬──────┘     └──────┬──────┘     └──────┬──────┘                   │
│         │                   │                   │                           │
│         └───────────────────┼───────────────────┘                           │
│                             ▼                                                │
│                    ┌─────────────────┐                                      │
│                    │   COMPARISON    │  (Shared)                            │
│                    │   compare_all   │                                      │
│                    │   plot_results  │                                      │
│                    │   report        │                                      │
│                    └─────────────────┘                                      │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Folder Structure

```
project/
│
├── data_collection/                    # SHARED - Collect weather data
│   ├── multi_location_forecast_interpolated.py
│   ├── waypoints_interpolated.txt
│   ├── generate_intermediate_waypoints.py
│   ├── visualize_pickle_data.py
│   └── output/
│       └── voyage_nodes.pickle
│
├── static_deterministic/               # APPROACH 1: LP-based
│   ├── transform.py
│   ├── optimize.py
│   ├── simulate.py
│   ├── evaluate.py
│   ├── config.yaml
│   └── output/
│
├── dynamic_deterministic/              # APPROACH 2: DP (plan once)
│   ├── transform.py
│   ├── optimize.py
│   ├── simulate.py
│   ├── evaluate.py
│   ├── config.yaml
│   └── output/
│
├── dynamic_stochastic/                 # APPROACH 3: DP (rolling horizon)
│   ├── transform.py
│   ├── optimize.py
│   ├── simulate.py
│   ├── evaluate.py
│   ├── config.yaml
│   └── output/
│
├── shared/                             # SHARED utilities
│   ├── node_class.py
│   ├── weather_utils.py
│   ├── simulation_engine.py
│   └── metrics.py
│
└── comparison/                         # SHARED - Compare all approaches
    ├── compare_all.py
    ├── plot_results.py
    ├── generate_report.py
    └── output/
```

---

## Common Interface Per Approach

Each approach folder has **4 scripts** with consistent interface:

| Script | Input | Output | Purpose |
|--------|-------|--------|---------|
| `transform.py` | `voyage_nodes.pickle` | `output/transformed_data.yaml` | Prepare data for optimizer |
| `optimize.py` | `transformed_data.yaml` | `output/speed_schedule.json` | Run optimization |
| `simulate.py` | `speed_schedule.json` + pickle | `output/simulation_results.json` | Execute vs actual weather |
| `evaluate.py` | `simulation_results.json` | `output/metrics.json` | Calculate performance metrics |

---

## Data Collection (Shared)

**Status: ✓ Running on server (72h)**

| Task ID | Task | Script | Status |
|---------|------|--------|--------|
| DC.1 | Collect weather for 3,388 waypoints | `multi_location_forecast_interpolated.py` | ✓ Running |
| DC.2 | Integer sample keys (0,1,2...) | (in script) | ✓ Fixed |
| DC.3 | Store voyage_start_time in pickle | (in script) | ✓ Fixed |
| DC.4 | 72h hourly samples | Server deployment | ✓ Running |

**Output:** `data_collection/output/voyage_nodes.pickle`

---

## Static Deterministic (Approach 1)

**Characteristics:**
- Weather: Constant (single snapshot)
- Optimizer: Linear Programming (LP)
- Planning: Once before voyage
- Data access: `Actual_weather_conditions[0]`

### Scripts

| Task ID | Script | Purpose | Status |
|---------|--------|---------|--------|
| SD.1 | `transform.py` | Aggregate to 12 segments, static average | To Create |
| SD.2 | `optimize.py` | Run LP optimizer (PuLP) | To Create |
| SD.3 | `simulate.py` | Execute fixed plan vs actual weather | To Create |
| SD.4 | `evaluate.py` | Calculate fuel, time, metrics | To Create |

### transform.py Details

```python
# Input: voyage_nodes.pickle
# Output: transformed_data.yaml

# Data access:
weather = node.Actual_weather_conditions[0]  # Snapshot at t=0

# Aggregation:
# - 3,388 waypoints → 12 segments
# - Average weather per segment
# - Single static value
```

### config.yaml

```yaml
approach: static_deterministic
optimizer: LP
segments: 12
weather_source: actual
weather_time: 0  # Use t=0 snapshot
```

---

## Dynamic Deterministic (Approach 2)

**Characteristics:**
- Weather: Time-varying (forecast)
- Optimizer: Dynamic Programming (DP)
- Planning: Once before voyage
- Data access: `Predicted_weather_conditions[t][0]`

### Scripts

| Task ID | Script | Purpose | Status |
|---------|--------|---------|--------|
| DD.1 | `transform.py` | Extract time-varying forecasts | To Create |
| DD.2 | `optimize.py` | Run DP optimizer | To Create |
| DD.3 | `simulate.py` | Execute fixed plan vs actual weather | To Create |
| DD.4 | `evaluate.py` | Calculate fuel, time, metrics | To Create |

### transform.py Details

```python
# Input: voyage_nodes.pickle
# Output: transformed_data.yaml

# Data access:
for forecast_hour in range(voyage_duration):
    weather = node.Predicted_weather_conditions[forecast_hour][0]
    # Forecast for hour t, made at voyage start (sample=0)

# Output:
# - Weather per node per time window
# - 6-hour time windows
```

### config.yaml

```yaml
approach: dynamic_deterministic
optimizer: DP
time_window_hours: 6
weather_source: predicted
sample_time: 0  # Use forecasts from t=0
nodes: 3388
```

---

## Dynamic Stochastic (Approach 3)

**Characteristics:**
- Weather: Time-varying (updated forecasts)
- Optimizer: Dynamic Programming (DP) with re-planning
- Planning: Multiple times during voyage
- Data access: `Predicted_weather_conditions[future_t][current_t]`

### Scripts

| Task ID | Script | Purpose | Status |
|---------|--------|---------|--------|
| DS.1 | `transform.py` | Extract forecasts at each decision point | To Create |
| DS.2 | `optimize.py` | DP with rolling horizon logic | To Create |
| DS.3 | `simulate.py` | Execute with re-planning at decision points | To Create |
| DS.4 | `evaluate.py` | Calculate fuel, time, plan stability | To Create |

### transform.py Details

```python
# Input: voyage_nodes.pickle
# Output: transformed_data.yaml (multiple, per decision point)

# Data access at decision point t:
for future_hour in range(current_hour, voyage_duration):
    weather = node.Predicted_weather_conditions[future_hour][current_hour]
    # Forecast for future hour, made at current decision point
```

### config.yaml

```yaml
approach: dynamic_stochastic
optimizer: DP
time_window_hours: 6
weather_source: predicted
replan_frequency_hours: 6  # Re-plan every 6 hours
decision_points: [0, 6, 12, 18, 24, ...]  # Or at waypoints
```

### simulate.py Flow

```
Start at t=0
│
├─→ Get forecast at t=0
├─→ Run DP optimizer for remaining voyage
├─→ Execute plan until next decision point (t=6)
│
├─→ At t=6: Get latest forecast
├─→ Re-run DP optimizer for remaining voyage
├─→ Execute plan until next decision point (t=12)
│
└─→ ... repeat until arrival
```

---

## Shared Utilities

| Script | Purpose |
|--------|---------|
| `node_class.py` | Node class definition for pickle loading |
| `weather_utils.py` | SOG calculation, FCR calculation, resistance |
| `simulation_engine.py` | Core simulation logic (used by all simulate.py) |
| `metrics.py` | Metric calculations (fuel, time, deviation) |

---

## Comparison (Shared)

| Task ID | Script | Purpose | Status |
|---------|--------|---------|--------|
| CMP.1 | `compare_all.py` | Load results from all 3 approaches, compare | To Create |
| CMP.2 | `plot_results.py` | Speed profiles, fuel curves, trajectories | To Create |
| CMP.3 | `generate_report.py` | Markdown/HTML summary report | To Create |

### Metrics Compared

| Metric | Description |
|--------|-------------|
| Total Fuel (MT) | Sum of fuel consumed |
| Voyage Time (h) | Port A to Port B duration |
| Arrival Deviation (h) | vs target arrival |
| Speed Changes (#) | Plan stability |
| Computation Time (s) | Optimizer runtime |

### Research Questions Answered

| Comparison | Question |
|------------|----------|
| Dynamic Det. vs Static Det. | Value of time-varying weather modeling? |
| Dynamic Stoch. vs Dynamic Det. | Value of forecast adaptation? |
| Re-plan frequency sensitivity | Optimal decision point interval? |

---

## Implementation Priority

### Phase 1: Core Framework

| # | Task | Folder | Script |
|---|------|--------|--------|
| 1 | Create folder structure | All | - |
| 2 | Shared utilities | `shared/` | All 4 scripts |
| 3 | Static Det. transform | `static_deterministic/` | `transform.py` |
| 4 | Static Det. optimize | `static_deterministic/` | `optimize.py` |
| 5 | Static Det. simulate | `static_deterministic/` | `simulate.py` |
| 6 | Static Det. evaluate | `static_deterministic/` | `evaluate.py` |

### Phase 2: Dynamic Deterministic

| # | Task | Folder | Script |
|---|------|--------|--------|
| 7 | Dynamic Det. transform | `dynamic_deterministic/` | `transform.py` |
| 8 | Dynamic Det. optimize | `dynamic_deterministic/` | `optimize.py` |
| 9 | Dynamic Det. simulate | `dynamic_deterministic/` | `simulate.py` |
| 10 | Dynamic Det. evaluate | `dynamic_deterministic/` | `evaluate.py` |

### Phase 3: Dynamic Stochastic

| # | Task | Folder | Script |
|---|------|--------|--------|
| 11 | Dynamic Stoch. transform | `dynamic_stochastic/` | `transform.py` |
| 12 | Dynamic Stoch. optimize | `dynamic_stochastic/` | `optimize.py` |
| 13 | Dynamic Stoch. simulate | `dynamic_stochastic/` | `simulate.py` |
| 14 | Dynamic Stoch. evaluate | `dynamic_stochastic/` | `evaluate.py` |

### Phase 4: Comparison

| # | Task | Folder | Script |
|---|------|--------|--------|
| 15 | Compare all approaches | `comparison/` | `compare_all.py` |
| 16 | Visualizations | `comparison/` | `plot_results.py` |
| 17 | Final report | `comparison/` | `generate_report.py` |

---

## Current Status

| Component | Status |
|-----------|--------|
| Data Collection | ✓ Running (72h on server) |
| Folder Structure | To Create |
| Shared Utilities | To Create |
| Static Deterministic | To Create |
| Dynamic Deterministic | To Create |
| Dynamic Stochastic | To Create |
| Comparison | To Create |

---

## Next Steps

1. **Now:** Wait for 72h data collection (~3 days)
2. **While waiting:**
   - Create folder structure
   - Implement `shared/` utilities
   - Start `static_deterministic/transform.py`
3. **After collection:** Run full pipeline for Static Det.
4. **Then:** Implement Dynamic Det. and Dynamic Stoch.
5. **Finally:** Run comparison and generate report

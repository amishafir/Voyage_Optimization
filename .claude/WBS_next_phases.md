# Work Breakdown Structure (WBS) - Next Phases

## Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         PROJECT PHASES                                       │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  Phase 1          Phase 2          Phase 3          Phase 4                 │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐              │
│  │   DATA   │ -> │  TRANS-  │ -> │  OPTIM-  │ -> │  COMPARE │              │
│  │COLLECTION│    │  FORM    │    │  IZATION │    │  & EVAL  │              │
│  └──────────┘    └──────────┘    └──────────┘    └──────────┘              │
│                                                                              │
│  API calls       Scripts to       Run LP & DP     Simulation &              │
│  for weather     convert data     optimizers      comparison                │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Phase 1: Data Collection (API Calls)

### 1.1 Weather Data Collection - Original 13 Waypoints

| Task ID | Task | Script | API | Status |
|---------|------|--------|-----|--------|
| 1.1.1 | Collect wind data (13 WPs, 72h) | `multi_location_forecast_pickle.py` | Open-Meteo Forecast | ✓ Exists |
| 1.1.2 | Collect marine data (13 WPs, 72h) | `multi_location_forecast_pickle.py` | Open-Meteo Marine | ✓ Exists |
| 1.1.3 | Store in Node class structure | `class.py` | - | ✓ Exists |
| 1.1.4 | Run for full 72h collection | Deploy script | - | Pending |

### 1.2 Weather Data Collection - Interpolated Waypoints (3,388 points)

| Task ID | Task | Script | API | Status |
|---------|------|--------|-----|--------|
| 1.2.1 | Batch API calls for 3,388 waypoints | `collect_interpolated_weather.py` | Open-Meteo | To Create |
| 1.2.2 | Rate limiting & retry logic | (in script) | - | To Create |
| 1.2.3 | Incremental save (resume capability) | (in script) | - | To Create |
| 1.2.4 | Validate coverage (handle NaN coastal) | (in script) | - | To Create |

**API Considerations:**
- Open-Meteo allows ~10,000 calls/day (free tier)
- 3,388 waypoints × 2 APIs (wind + marine) = 6,776 calls per sample
- Strategy: Batch by segment, parallel calls where allowed

### 1.3 Historical Weather Data (Optional - for validation)

| Task ID | Task | Script | API | Status |
|---------|------|--------|-----|--------|
| 1.3.1 | Fetch historical wind data | `collect_historical_weather.py` | Open-Meteo Historical | To Create |
| 1.3.2 | Fetch historical marine data | (same script) | Open-Meteo Marine | To Create |
| 1.3.3 | Compare forecast vs actual | `forecast_accuracy_analysis.py` | - | To Create |

---

## Phase 2: Data Transformation

### 2.1 Pickle to YAML Conversion

| Task ID | Task | Script | Input | Output | Status |
|---------|------|--------|-------|--------|--------|
| 2.1.1 | Convert Node pickle to optimizer YAML | `pickle_to_yaml.py` | `voyage_nodes.pickle` | `weather_forecasts.yaml` | To Create |
| 2.1.2 | Aggregate hourly data to 6h windows | (in script) | Hourly data | 6h averages | To Create |
| 2.1.3 | Calculate segment weather (avg endpoints) | (in script) | Waypoint data | Segment data | To Create |
| 2.1.4 | Convert units (km/h → knots, etc.) | (in script) | API units | Optimizer units | To Create |

### 2.2 Segment Calculations

| Task ID | Task | Script | Input | Output | Status |
|---------|------|--------|-------|--------|--------|
| 2.2.1 | Calculate ship heading per segment | `calculate_segments.py` | Waypoint coords | Headings (degrees) | To Create |
| 2.2.2 | Calculate segment distances | (in script) | Waypoint coords | Distances (nm) | ✓ Exists (in interpolation) |
| 2.2.3 | Map time windows to voyage timeline | (in script) | Voyage start time | Window assignments | To Create |

### 2.3 Data Validation

| Task ID | Task | Script | Input | Output | Status |
|---------|------|--------|-------|--------|--------|
| 2.3.1 | Validate YAML structure | `validate_optimizer_input.py` | YAML files | Validation report | To Create |
| 2.3.2 | Check for missing/NaN values | (in script) | YAML files | Error list | To Create |
| 2.3.3 | Verify unit conversions | (in script) | Original + converted | Comparison | To Create |

---

## Phase 3: Optimization

### 3.1 Dynamic Programming (DP) Optimizer

| Task ID | Task | Script | Input | Output | Status |
|---------|------|--------|-------|--------|--------|
| 3.1.1 | Run DP optimizer | `speed_control_optimizer.py` | YAML configs | Optimal path | ✓ Exists |
| 3.1.2 | Extract speed schedule | `extract_dp_schedule.py` | Optimizer output | Speed schedule JSON | To Create |
| 3.1.3 | Visualize optimal path | `visualize_dp_solution.py` | Optimizer output | Plots | To Create |

### 3.2 Linear Programming (LP) Optimizer

| Task ID | Task | Script | Input | Output | Status |
|---------|------|--------|-------|--------|--------|
| 3.2.1 | Run LP optimizer (PuLP) | `ship_speed_optimization_pulp.py` | voyage_data.py | Optimal speeds | ✓ Exists |
| 3.2.2 | Update LP with new weather data | `update_lp_weather.py` | YAML → voyage_data.py | Updated LP input | To Create |
| 3.2.3 | Extract LP speed schedule | `extract_lp_schedule.py` | LP output | Speed schedule JSON | To Create |

### 3.3 Baseline Schedules

| Task ID | Task | Script | Input | Output | Status |
|---------|------|--------|-------|--------|--------|
| 3.3.1 | Generate constant speed baseline | `generate_baselines.py` | Speed value (12 kts) | Schedule JSON | To Create |
| 3.3.2 | Generate average weather baseline | (same script) | Weather data | Schedule JSON | To Create |
| 3.3.3 | Generate segment-static baseline | (same script) | Weather per segment | Schedule JSON | To Create |

---

## Phase 4: Simulation & Comparison Framework

### 4.1 Voyage Simulator

| Task ID | Task | Script | Input | Output | Status |
|---------|------|--------|-------|--------|--------|
| 4.1.1 | Core simulation engine | `voyage_simulator.py` | Speed schedule + Weather | Voyage trajectory | To Create |
| 4.1.2 | Fuel consumption tracking | (in engine) | SWS values | Fuel per step | To Create |
| 4.1.3 | Position/time tracking | (in engine) | SOG values | Trajectory | To Create |
| 4.1.4 | Weather application | (in engine) | Forecast/Actual weather | SOG calculation | To Create |

### 4.2 Comparison Framework

| Task ID | Task | Script | Input | Output | Status |
|---------|------|--------|-------|--------|--------|
| 4.2.1 | Run all strategies on same weather | `run_comparison.py` | All schedules + Weather | Results dict | To Create |
| 4.2.2 | Calculate comparison metrics | `calculate_metrics.py` | Simulation results | Metrics table | To Create |
| 4.2.3 | Generate comparison report | `generate_report.py` | Metrics | Markdown/HTML report | To Create |

### 4.3 Visualization

| Task ID | Task | Script | Input | Output | Status |
|---------|------|--------|-------|--------|--------|
| 4.3.1 | Speed profile comparison plot | `plot_comparison.py` | All schedules | Speed vs time plot | To Create |
| 4.3.2 | Fuel consumption comparison | (same script) | Simulation results | Cumulative fuel plot | To Create |
| 4.3.3 | Position-time trajectory | (same script) | Trajectories | Trajectory plot | To Create |
| 4.3.4 | Weather overlay visualization | (same script) | Weather + decisions | Combined plot | To Create |

### 4.4 Ensemble Analysis (Advanced)

| Task ID | Task | Script | Input | Output | Status |
|---------|------|--------|-------|--------|--------|
| 4.4.1 | Multi-forecast comparison | `ensemble_analysis.py` | Multiple forecasts | Uncertainty bounds | To Create |
| 4.4.2 | Forecast accuracy by lead time | (same script) | Forecasts + Actuals | Accuracy metrics | To Create |
| 4.4.3 | Robust optimization (ensemble) | `robust_optimizer.py` | Forecast ensemble | Robust schedule | To Create |

---

## Script Dependency Graph

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         SCRIPT DEPENDENCIES                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  DATA COLLECTION                                                             │
│  ┌─────────────────────────┐                                                │
│  │ multi_location_forecast │─────┐                                          │
│  │ _pickle.py              │     │                                          │
│  └─────────────────────────┘     │                                          │
│                                  ▼                                          │
│  ┌─────────────────────────┐   ┌─────────────────────┐                     │
│  │ collect_interpolated_   │──>│ voyage_nodes.pickle │                     │
│  │ weather.py              │   │ voyage_nodes_       │                     │
│  └─────────────────────────┘   │ interpolated.pickle │                     │
│                                └─────────────────────┘                     │
│                                          │                                  │
│  TRANSFORMATION                          ▼                                  │
│                                ┌─────────────────────┐                     │
│                                │ pickle_to_yaml.py   │                     │
│                                └─────────────────────┘                     │
│                                          │                                  │
│                    ┌─────────────────────┼─────────────────────┐           │
│                    ▼                     ▼                     ▼           │
│  ┌─────────────────────┐  ┌─────────────────────┐  ┌─────────────────────┐│
│  │ weather_forecasts   │  │ ship_parameters     │  │ voyage_data.py      ││
│  │ .yaml               │  │ .yaml               │  │ (for LP)            ││
│  └─────────────────────┘  └─────────────────────┘  └─────────────────────┘│
│            │                         │                        │            │
│  OPTIMIZATION                        │                        │            │
│            ▼                         ▼                        ▼            │
│  ┌─────────────────────┐  ┌─────────────────────┐  ┌─────────────────────┐│
│  │ speed_control_      │  │ generate_baselines  │  │ ship_speed_         ││
│  │ optimizer.py (DP)   │  │ .py                 │  │ optimization_pulp.py││
│  └─────────────────────┘  └─────────────────────┘  └─────────────────────┘│
│            │                         │                        │            │
│            └─────────────────────────┼────────────────────────┘            │
│                                      ▼                                      │
│  SIMULATION                ┌─────────────────────┐                         │
│                            │ Speed Schedules     │                         │
│                            │ (DP, LP, Baselines) │                         │
│                            └─────────────────────┘                         │
│                                      │                                      │
│                                      ▼                                      │
│                            ┌─────────────────────┐                         │
│                            │ voyage_simulator.py │                         │
│                            └─────────────────────┘                         │
│                                      │                                      │
│                                      ▼                                      │
│  COMPARISON                ┌─────────────────────┐                         │
│                            │ run_comparison.py   │                         │
│                            └─────────────────────┘                         │
│                                      │                                      │
│                    ┌─────────────────┼─────────────────┐                   │
│                    ▼                 ▼                 ▼                   │
│           ┌──────────────┐  ┌──────────────┐  ┌──────────────┐            │
│           │ Metrics      │  │ Plots        │  │ Report       │            │
│           │ (JSON/CSV)   │  │ (PNG/HTML)   │  │ (MD/HTML)    │            │
│           └──────────────┘  └──────────────┘  └──────────────┘            │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## API Call Summary

| API | Endpoint | Purpose | Calls/Run | Rate Limit |
|-----|----------|---------|-----------|------------|
| Open-Meteo Forecast | `/v1/forecast` | Wind speed, direction | 13-3388 | 10,000/day |
| Open-Meteo Marine | `/v1/marine` | Wave height, currents | 13-3388 | 10,000/day |
| Open-Meteo Historical | `/v1/archive` | Historical validation | As needed | 10,000/day |

### API Call Strategy for 3,388 Waypoints

```
Option A: Sequential (Safe)
├── 3,388 wind calls + 3,388 marine calls = 6,776 calls
├── At 1 call/second = ~2 hours per sample
└── Fits within daily limit

Option B: Batch by Location (Faster)
├── Open-Meteo supports multiple locations per call
├── Batch 50 locations per call = 68 calls per API
├── Total: 136 calls per sample
└── ~2-3 minutes per sample

Option C: Segment-Based (Practical)
├── Only fetch weather for segment midpoints
├── 12 segments × 2 APIs = 24 calls per sample
├── Interpolate between for fine granularity
└── Fastest, slight accuracy tradeoff
```

---

## Scripts To Create - Priority Order

### Priority 1: Core Pipeline (Minimum Viable)

| # | Script | Purpose | Depends On |
|---|--------|---------|------------|
| 1 | `pickle_to_yaml.py` | Convert collected data to optimizer format | voyage_nodes.pickle |
| 2 | `calculate_segments.py` | Calculate headings and distances | Waypoint coordinates |
| 3 | `extract_dp_schedule.py` | Get speed schedule from DP optimizer | DP optimizer output |
| 4 | `voyage_simulator.py` | Simulate voyage with schedule | Speed schedule + weather |
| 5 | `run_comparison.py` | Compare DP vs baselines | Simulator + schedules |

### Priority 2: Complete Framework

| # | Script | Purpose | Depends On |
|---|--------|---------|------------|
| 6 | `generate_baselines.py` | Create constant/static schedules | Weather data |
| 7 | `update_lp_weather.py` | Update LP with new weather | YAML data |
| 8 | `calculate_metrics.py` | Compute comparison metrics | Simulation results |
| 9 | `plot_comparison.py` | Visualize results | Metrics |
| 10 | `generate_report.py` | Create summary report | All results |

### Priority 3: Advanced Features

| # | Script | Purpose | Depends On |
|---|--------|---------|------------|
| 11 | `collect_interpolated_weather.py` | Weather for 3,388 points | Interpolated waypoints |
| 12 | `ensemble_analysis.py` | Multi-forecast uncertainty | Multiple pickle files |
| 13 | `robust_optimizer.py` | Ensemble-based optimization | Ensemble data |
| 14 | `forecast_accuracy_analysis.py` | Validate forecasts | Historical + forecast data |

---

## Estimated Timeline

| Phase | Tasks | Est. Duration | Dependencies |
|-------|-------|---------------|--------------|
| Phase 1.1 | Original 13 WP collection | 72 hours (running) | None |
| Phase 2 | Data transformation | 2-3 days | Phase 1.1 |
| Phase 3 | Run optimizers | 1 day | Phase 2 |
| Phase 4.1-4.2 | Simulation & comparison | 2-3 days | Phase 3 |
| Phase 4.3 | Visualization | 1-2 days | Phase 4.2 |
| Phase 1.2 | Interpolated collection | 1 week | Phase 1.1 validated |
| Phase 4.4 | Ensemble analysis | 3-5 days | Multiple collections |

---

## File Structure (Proposed)

```
test_files/
├── data/
│   ├── raw/
│   │   ├── voyage_nodes.pickle           # 13 WP collection
│   │   └── voyage_nodes_interpolated.pickle  # 3388 WP collection
│   ├── processed/
│   │   ├── weather_forecasts.yaml        # Optimizer input
│   │   └── voyage_data_updated.py        # LP input
│   └── results/
│       ├── dp_schedule.json
│       ├── lp_schedule.json
│       ├── baseline_schedules.json
│       └── simulation_results.json
├── scripts/
│   ├── collection/
│   │   ├── multi_location_forecast_pickle.py
│   │   └── collect_interpolated_weather.py
│   ├── transformation/
│   │   ├── pickle_to_yaml.py
│   │   ├── calculate_segments.py
│   │   └── validate_optimizer_input.py
│   ├── optimization/
│   │   ├── extract_dp_schedule.py
│   │   ├── extract_lp_schedule.py
│   │   └── generate_baselines.py
│   ├── simulation/
│   │   ├── voyage_simulator.py
│   │   └── run_comparison.py
│   └── analysis/
│       ├── calculate_metrics.py
│       ├── plot_comparison.py
│       ├── generate_report.py
│       └── ensemble_analysis.py
└── reports/
    ├── comparison_report.md
    └── figures/
        ├── speed_profile.png
        ├── fuel_comparison.png
        └── trajectory.png
```

---

## Next Steps

1. **Immediate**: Wait for 72h data collection to complete
2. **While waiting**: Create `pickle_to_yaml.py` transformation script
3. **After collection**: Run transformation and validate YAML output
4. **Then**: Run DP optimizer with real weather data
5. **Finally**: Build simulator and comparison framework

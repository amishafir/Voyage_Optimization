# Work Breakdown Structure (WBS) - Research Pipeline

## 1. Pipeline Overview

A configurable research pipeline for comparing voyage optimization strategies. All parameters (route, ship, collection duration, approach knobs) are configurable via YAML + CLI. One shared data collection feeds three independent optimization approaches, all evaluated against actual weather.

```
        config/experiment.yaml + CLI flags
                    |
                    v
            ┌──────────────┐
            │    cli.py     │
            │  entry point  │
            └──────┬───────┘
                   |
        ┌──────────┼──────────┐
        v          v          v
    collect     run <X>    compare
        |          |          |
        v          v          v
┌─────────────────────────────────────────────┐
│              SHARED DATA LAYER              │
│  voyage_weather.h5 (HDF5)                   │
│  shared/physics.py (SOG, FCR, resistance)   │
│  shared/simulation.py (forward sim engine)  │
│  shared/metrics.py (fuel, time, deviation)  │
└─────────────────────┬───────────────────────┘
                      |
          ┌───────────┼───────────┐
          v           v           v
   ┌────────────┐ ┌────────────┐ ┌────────────┐
   │ Static Det │ │Dynamic Det │ │Dynamic Sto │
   │            │ │            │ │            │
   │ LP solver  │ │ DP graph   │ │ DP graph   │
   │ 12 segments│ │ 3388 nodes │ │ + re-plan  │
   │ PuLP/Gurobi│ │ Dijkstra   │ │ rolling    │
   │            │ │            │ │ horizon    │
   │ transform  │ │ transform  │ │ transform  │
   │ optimize   │ │ optimize   │ │ optimize   │
   └─────┬──────┘ └─────┬──────┘ └─────┬──────┘
         |               |               |
         v               v               v
   result_static   result_dyn_det  result_dyn_stoch
   .json           .json           .json
         |               |               |
         └───────────────┼───────────────┘
                         v
                ┌─────────────────┐
                │   COMPARISON    │
                │   compare.py    │
                │   plots.py      │
                │   report.py     │
                └─────────────────┘
                         |
                         v
                output/comparison/
                figures/ tables/ report.md
```

**Key design principle**: The three approaches share the **input** (same HDF5 data) and the **output contract** (same result JSON format), but transform and optimize logic is approach-specific. No false uniformity.

---

## 2. Directory Structure

```
pipeline/
├── cli.py                              # Single entry point (argparse)
├── Makefile                            # Easy deploy + run targets
├── requirements.txt
│
├── config/
│   ├── experiment.yaml                 # Master config (ship, approaches, comparison)
│   └── routes/
│       └── persian_gulf_malacca.yaml   # Waypoints for this route
│
├── shared/
│   ├── physics.py                      # SOG, FCR, resistance (from utility_functions.py)
│   ├── hdf5_io.py                      # Read/write/append/query HDF5
│   ├── simulation.py                   # Forward simulation engine
│   ├── metrics.py                      # Metric computation
│   └── beaufort.py                     # Wind speed to Beaufort conversion
│
├── collect/
│   ├── collector.py                    # API fetcher + HDF5 appender
│   └── waypoints.py                    # Load/generate interpolated waypoints
│
├── static_det/
│   ├── transform.py                    # HDF5 -> 12-segment averaged weather + SOG matrix
│   └── optimize.py                     # PuLP/Gurobi LP solver
│
├── dynamic_det/
│   ├── transform.py                    # HDF5 -> time-windowed weather per node
│   └── optimize.py                     # Graph-based DP (Dijkstra)
│
├── dynamic_stoch/
│   ├── transform.py                    # HDF5 -> per-decision-point forecast extracts
│   └── optimize.py                     # Rolling horizon (calls dynamic_det.optimize repeatedly)
│
├── compare/
│   ├── compare.py                      # Load result JSONs, compute deltas
│   ├── plots.py                        # Matplotlib figures for paper
│   └── report.py                       # Generate markdown comparison report
│
├── data/                               # gitignored
│   └── voyage_weather.h5
│
└── output/                             # gitignored
    ├── result_static_det.json
    ├── result_dynamic_det.json
    ├── result_dynamic_stoch.json
    ├── timeseries_*.csv
    └── comparison/
        ├── figures/
        ├── tables/
        └── report.md
```

**Note**: Each approach has only `transform.py` + `optimize.py`. Simulation and evaluation use the shared engine — no need for per-approach `simulate.py` / `evaluate.py` since the physics and metrics are identical. The `cli.py run` command chains: transform -> optimize -> simulate -> evaluate -> save result JSON.

---

## 3. Configuration

### 3.1 Master Config (`config/experiment.yaml`)

```yaml
collection:
  route: persian_gulf_malacca       # Matches file in config/routes/
  interval_nm: 1                    # Waypoint spacing (nautical miles)
  hours: 72                         # Collection duration
  api_delay_seconds: 0.1            # Rate limiting between API calls

ship:
  length_m: 200.0
  beam_m: 32.0
  draft_m: 12.0
  displacement_tonnes: 50000.0
  block_coefficient: 0.75
  rated_power_kw: 10000.0
  speed_range_knots: [11, 13]       # [min, max]
  eta_hours: 280                    # Estimated Time of Arrival constraint

# Each approach has its OWN section — no false uniformity
static_det:
  enabled: true
  segments: 12                      # Aggregate to N segments
  weather_snapshot: 0               # Which hour of actual weather to use
  optimizer: gurobi                 # pulp or gurobi
  speed_choices: 21                 # Number of discrete speeds between min-max

dynamic_det:
  enabled: true
  time_window_hours: 6              # Graph time resolution
  forecast_origin: 0                # Use forecasts from this sample hour
  speed_granularity: 0.1            # Knots between speed choices
  time_granularity: 1               # Hours between time nodes
  distance_granularity: 1           # NM between distance nodes

dynamic_stoch:
  enabled: true
  time_window_hours: 6
  replan_frequency_hours: 6         # Re-plan every N hours
  # Alternative: replan_at_waypoints: true

comparison:
  metrics:
    - total_fuel_mt
    - voyage_time_h
    - arrival_deviation_h
    - plan_stability
    - computation_time_s
    - fuel_per_nm
```

### 3.2 Route File (`config/routes/persian_gulf_malacca.yaml`)

```yaml
name: Persian Gulf to Strait of Malacca
waypoints:
  - {lat: 24.75, lon: 52.83, name: "Port A (Persian Gulf)"}
  - {lat: 26.55, lon: 56.45, name: "Gulf of Oman"}
  - {lat: 24.08, lon: 60.88, name: "Arabian Sea 1"}
  - {lat: 21.73, lon: 65.73, name: "Arabian Sea 2"}
  - {lat: 17.96, lon: 69.19, name: "Arabian Sea 3"}
  - {lat: 14.18, lon: 72.07, name: "Arabian Sea 4"}
  - {lat: 10.45, lon: 75.16, name: "Indian Ocean 1"}
  - {lat:  7.00, lon: 78.46, name: "Indian Ocean 2"}
  - {lat:  5.64, lon: 82.12, name: "Bay of Bengal"}
  - {lat:  4.54, lon: 87.04, name: "Indian Ocean 3"}
  - {lat:  5.20, lon: 92.27, name: "Andaman Sea 1"}
  - {lat:  5.64, lon: 97.16, name: "Andaman Sea 2"}
  - {lat:  1.81, lon: 100.10, name: "Port B (Strait of Malacca)"}
```

To add a new route: create a new YAML in `config/routes/`, then `--route new_route_name`.

### 3.3 CLI Overrides

CLI flags override YAML values for quick experiments:

```bash
python3 cli.py collect --route persian_gulf_malacca --interval-nm 1 --hours 72
python3 cli.py run static_det --weather-snapshot 0 --optimizer pulp
python3 cli.py run dynamic_det --time-window 6 --forecast-origin 0
python3 cli.py run dynamic_stoch --replan-hours 6
python3 cli.py run all
python3 cli.py compare
python3 cli.py convert-pickle <pickle_path> <hdf5_path>
```

---

## 4. HDF5 Data Schema

Replaces pickle. Table-oriented (not nested arrays) for queryability and appendability.

```
voyage_weather.h5
│
├── attrs (global)
│   ├── schema_version: 1
│   ├── route_name: "persian_gulf_malacca"
│   ├── voyage_start_time: "2026-02-14T00:00:00"
│   └── interval_nm: 1.0
│
├── /metadata (table)
│   │  node_id (int)  │  lon (f64)  │  lat (f64)  │  waypoint_name (str)  │
│   │  is_original (bool)  │  distance_from_start_nm (f64)  │  segment (int)  │
│   └── 3,388 rows (one per waypoint)
│
├── /actual_weather (appendable table)
│   │  node_id (int)  │  sample_hour (int)  │  wind_speed_10m_kmh (f32)  │
│   │  wind_direction_10m_deg (f32)  │  beaufort_number (int8)  │
│   │  wave_height_m (f32)  │  ocean_current_velocity_kmh (f32)  │
│   │  ocean_current_direction_deg (f32)  │
│   └── ~244K rows for 72h collection (3,388 nodes x 72 hours)
│
└── /predicted_weather (appendable table)
    │  node_id (int)  │  forecast_hour (int)  │  sample_hour (int)  │
    │  wind_speed_10m_kmh (f32)  │  wind_direction_10m_deg (f32)  │
    │  beaufort_number (int8)  │  wave_height_m (f32)  │
    │  ocean_current_velocity_kmh (f32)  │  ocean_current_direction_deg (f32)  │
    └── ~3.9M rows (3,388 nodes x 168 forecast hours x variable samples)
```

**Why tables over nested arrays**: No ragged dimensions, append-friendly (new collection runs don't rewrite file), efficient filtered queries, GZIP compression (~100-150 MB vs 248 MB pickle).

**Resume logic**: `get_completed_runs()` counts distinct `sample_hour` values in `/actual_weather`. New runs append rows.

---

## 5. Shared Modules

### 5.1 `shared/physics.py`

Consolidates the two identical `utility_functions.py` files into one import.

**Ported from existing code** (exact same paper formulas):

| Function | Paper Reference |
|----------|----------------|
| `calculate_speed_over_ground()` | 8-step composite (Eqs 7-16) |
| `calculate_fuel_consumption_rate(sws)` | FCR = 0.000706 x SWS^3 |
| `calculate_direction_reduction_coefficient(theta, bn)` | Table 2 (C_beta) |
| `calculate_speed_reduction_coefficient(froude, cb)` | Table 3 (C_U) |
| `calculate_ship_form_coefficient(bn, displacement)` | Table 4 (C_Form) |
| `calculate_travel_time(distance, sog)` | distance / SOG |
| `calculate_total_fuel_consumption(distance, fcr, sog)` | FCR x travel_time |

**New functions**:

| Function | Purpose |
|----------|---------|
| `calculate_sws_from_sog(target_sog, weather, ship_params)` | Binary search inverse (from DP optimizer) |
| `calculate_ship_heading(lat1, lon1, lat2, lon2)` | Initial bearing between waypoints |
| `load_ship_parameters(config)` | Build params dict from experiment.yaml |

### 5.2 `shared/hdf5_io.py`

All HDF5 read/write. Library: PyTables (`tables`) for appendable table pattern.

| Function | Purpose |
|----------|---------|
| `create_hdf5(path, metadata_df, attrs)` | Create new file with metadata + global attrs |
| `append_actual(path, records_df)` | Append rows to `/actual_weather` |
| `append_predicted(path, records_df)` | Append rows to `/predicted_weather` |
| `read_metadata(path)` | Read `/metadata` -> DataFrame |
| `read_actual(path, node_ids, hours)` | Filtered read -> DataFrame |
| `read_predicted(path, node_ids, forecast_hours, sample_hours)` | Filtered read -> DataFrame |
| `get_attrs(path)` | Read global attributes |
| `get_completed_runs(path)` | Count distinct sample_hours (for resume) |
| `import_from_pickle(pickle_path, hdf5_path)` | One-time migration tool |

### 5.3 `shared/simulation.py`

Forward simulation engine. Given a speed schedule + actual weather, simulate the voyage.

```python
def simulate_voyage(speed_schedule, actual_weather_df, metadata_df, ship_params) -> SimulationResult
```

**Handles both schedule types**:
- `SegmentSpeedSchedule` (from LP): look up SWS by segment
- `PathSpeedSchedule` (from DP): interpolate SWS by (time, distance)

**SimulationResult** includes:
- `time_series` DataFrame (hour, distance, sws, sog, fcr, cumulative_fuel, weather)
- `total_fuel_kg`, `total_time_hours`, `arrival_deviation_hours`
- `speed_changes` (plan stability count)

### 5.4 `shared/metrics.py`

| Function | Purpose |
|----------|---------|
| `compute_result_metrics(sim_result)` | Full metric dict from simulation |
| `compute_comparison(results_dict)` | Side-by-side comparison DataFrame |
| `compute_forecast_error(predicted_df, actual_df)` | RMSE, MAE per field |

### 5.5 `shared/beaufort.py`

- `wind_speed_to_beaufort(wind_speed_kmh) -> int` (BN 0-12 from thresholds)

---

## 6. Per-Approach Specifications

### 6.1 Static Deterministic (LP)

**What makes it different**: Pre-computes all weather effects into a lookup matrix. Solves a small LP (12 segments x N speeds). Fast but ignores time-varying weather.

#### `static_det/transform.py`

| | |
|---|---|
| **Reads** | HDF5 `/actual_weather` at `sample_hour=config.weather_snapshot`, `/metadata` |
| **Logic** | 1. Get 13 original waypoints as segment boundaries. 2. For each of 12 segments, average weather across all nodes in segment. 3. Compute SOG matrix `f[i][k]` for each (segment, speed) pair using `physics.calculate_speed_over_ground()`. 4. Compute FCR for each speed. |
| **Produces** | Dict: `{ETA, segments, speeds, distances[], sog_matrix[][], fcr[], sog_bounds[]}` |
| **Config** | `static_det.segments`, `static_det.weather_snapshot`, `ship.speed_range_knots`, `static_det.speed_choices` |

#### `static_det/optimize.py`

| | |
|---|---|
| **Reads** | Transform output dict |
| **Logic** | PuLP LP: binary `x[i,k]` variables, minimize fuel, ETA constraint, one-speed-per-segment, SOG bounds. Port of `ship_speed_optimization_pulp.py`. |
| **Produces** | `SegmentSpeedSchedule`: one SWS per segment, planned fuel/time |
| **Config** | `static_det.optimizer` (pulp/gurobi) |

### 6.2 Dynamic Deterministic (DP)

**What makes it different**: Builds a time-distance graph with weather varying over time. Finds minimum-fuel path through the graph. Accounts for forecast but plans once.

#### `dynamic_det/transform.py`

| | |
|---|---|
| **Reads** | HDF5 `/predicted_weather` at `sample_hour=config.forecast_origin`, `/metadata` |
| **Logic** | 1. Query forecasts from departure (sample_hour=0) for all nodes and forecast hours. 2. Group into time windows of `config.time_window_hours`. 3. Build weather-per-node-per-window structure. |
| **Produces** | Dict: time-windowed weather compatible with DP graph builder |
| **Config** | `dynamic_det.time_window_hours`, `dynamic_det.forecast_origin` |

#### `dynamic_det/optimize.py`

| | |
|---|---|
| **Reads** | Transform output + ship params from config |
| **Logic** | 1. Create 2D graph (time x distance). 2. For each arc, compute SOG and FCR using `physics`. 3. Dijkstra-like shortest path for minimum fuel. Port of `speed_control_optimizer.py`. |
| **Produces** | `PathSpeedSchedule`: SWS at each (time, distance) node, planned fuel/time |
| **Config** | `dynamic_det.speed_granularity`, `dynamic_det.time_granularity`, `dynamic_det.distance_granularity` |

### 6.3 Dynamic Stochastic (DP + Re-planning)

**What makes it different**: Runs the DP optimizer **repeatedly** at decision points, each time using the latest available forecast. The speed plan evolves during the voyage.

#### `dynamic_stoch/transform.py`

| | |
|---|---|
| **Reads** | HDF5 `/predicted_weather` at **multiple** `sample_hour` values, `/metadata` |
| **Logic** | 1. Determine decision points (every `replan_frequency_hours`). 2. For each decision point `t`, extract forecasts where `sample_hour=t` for `forecast_hour >= t`. 3. Build one transform output per decision point. |
| **Produces** | List of `{decision_hour, remaining_distance, weather_data}` dicts |
| **Config** | `dynamic_stoch.replan_frequency_hours`, `dynamic_stoch.time_window_hours` |

#### `dynamic_stoch/optimize.py`

| | |
|---|---|
| **Reads** | List of per-decision-point transform outputs + ship params |
| **Logic** | Rolling horizon: for each decision point, call `dynamic_det.optimize()` for remaining voyage, execute until next decision point, advance position/time, repeat. |
| **Produces** | `PathSpeedSchedule` (stitched from re-plans) + `decision_points` list showing how the plan evolved |
| **Config** | Same as `dynamic_det` + `dynamic_stoch.replan_frequency_hours` |

---

## 7. Common Output Contract

All approaches must produce result JSONs that comparison can consume uniformly.

### 7.1 Result JSON Structure

```json
{
  "approach": "static_det",
  "config": {"weather_snapshot": 0, "optimizer": "pulp", "segments": 12},
  "planned": {
    "total_fuel_kg": 372370,
    "voyage_time_h": 278.5
  },
  "simulated": {
    "total_fuel_kg": 385200,
    "voyage_time_h": 280.1,
    "arrival_deviation_h": 1.6,
    "speed_changes": 0,
    "co2_emissions_kg": 1221100
  },
  "metrics": {
    "fuel_gap_percent": 3.44,
    "fuel_per_nm": 113.5,
    "avg_sog_knots": 12.12
  },
  "computation_time_s": 0.8,
  "time_series_file": "output/timeseries_static_det.csv",
  "timestamp": "2026-02-14T10:30:00Z"
}
```

### 7.2 Required Metrics (all approaches)

| Metric | Key | Unit |
|--------|-----|------|
| Total fuel (planned by optimizer) | `planned.total_fuel_kg` | kg |
| Total fuel (simulated vs actual weather) | `simulated.total_fuel_kg` | kg |
| Fuel gap (plan vs reality) | `metrics.fuel_gap_percent` | % |
| Voyage time | `simulated.voyage_time_h` | hours |
| Arrival deviation vs ETA | `simulated.arrival_deviation_h` | hours |
| Plan stability | `simulated.speed_changes` | count |
| CO2 emissions | `simulated.co2_emissions_kg` | kg |
| Computation time | `computation_time_s` | seconds |
| Fuel efficiency | `metrics.fuel_per_nm` | kg/nm |

---

## 8. CLI & Makefile

### 8.1 CLI Commands

```bash
# Collect weather data
python3 cli.py collect --route persian_gulf_malacca --hours 72 --resume

# Run approaches
python3 cli.py run static_det
python3 cli.py run dynamic_det --time-window 6
python3 cli.py run dynamic_stoch --replan-hours 6
python3 cli.py run all                            # All enabled approaches

# Compare results
python3 cli.py compare

# Migrate existing pickle data
python3 cli.py convert-pickle path/to/file.pickle data/voyage_weather.h5
```

### 8.2 Makefile Targets

```makefile
REMOTE_HOST = Shlomo1-pcl.eng.tau.ac.il
REMOTE_USER = user
REMOTE_DIR  = ~/Ami/pipeline

install:        pip3 install -r requirements.txt
deploy:         scp -r . $(REMOTE_USER)@$(REMOTE_HOST):$(REMOTE_DIR)/
collect:        python3 cli.py collect --resume
collect-remote: ssh $(REMOTE_USER)@$(REMOTE_HOST) \
                  "cd $(REMOTE_DIR) && tmux new-session -d -s collect 'python3 cli.py collect --resume'"
status:         ssh $(REMOTE_USER)@$(REMOTE_HOST) "tmux capture-pane -t collect -p -S -20"
download:       scp $(REMOTE_USER)@$(REMOTE_HOST):$(REMOTE_DIR)/data/voyage_weather.h5 data/
run-all:        python3 cli.py run all
compare:        python3 cli.py compare
convert:        python3 cli.py convert-pickle ../test_files/voyage_nodes_interpolated_weather.pickle data/voyage_weather.h5
clean:          rm -rf output/ data/voyage_weather.h5
```

---

## 9. Implementation Phases

### Phase 0: Foundation — COMPLETE

| # | Task | File(s) | Status |
|---|------|---------|--------|
| 0.1 | Create `pipeline/` directory structure | All dirs, `__init__.py` | Done |
| 0.2 | Write `experiment.yaml` + route YAML | `config/` | Done |
| 0.3 | Port `shared/physics.py` | `shared/physics.py` | Done — 8-step SOG, FCR, SWS inverse, ship heading, load_ship_parameters |
| 0.4 | Write `shared/beaufort.py` | `shared/beaufort.py` | Done |
| 0.5 | Implement `shared/hdf5_io.py` | `shared/hdf5_io.py` | Done — create, append, read, pickle import |
| 0.6 | Write `requirements.txt` | `requirements.txt` | Done |
| 0.7 | Write CLI skeleton | `cli.py` | Done |

**Gate**: Passed. Committed `6d513d4`.

### Phase 1: Data Layer — COMPLETE

| # | Task | File(s) | Status |
|---|------|---------|--------|
| 1.1 | Port `collect/waypoints.py` | `collect/waypoints.py` | Done |
| 1.2 | Port `collect/collector.py` | `collect/collector.py` | Done |
| 1.3 | Implement `convert-pickle` command | `cli.py`, `hdf5_io.py` | Done |
| 1.4 | Wire `cli.py collect` command | `cli.py` | Done |
| 1.5 | Validate HDF5 output | manual test | Done — 279 nodes, 12 sample hours, 562K predicted rows |

**Gate**: Passed. Committed `cb5c5eb`. HDF5 at `pipeline/data/voyage_weather.h5`.

### Phase 2: Static Deterministic (baseline) — COMPLETE

| # | Task | File(s) | Status |
|---|------|---------|--------|
| 2.1 | Implement `static_det/transform.py` | `static_det/transform.py` | Done — reads HDF5, 12 segments, SOG matrix, FCR array, circular mean for directions, nanmean for NaN |
| 2.2 | Port `static_det/optimize.py` | `static_det/optimize.py` | Done — supports both PuLP CBC and Gurobi solvers via `config.static_det.optimizer` |
| 2.3 | Implement `shared/simulation.py` | `shared/simulation.py` | Done — per-waypoint (279-node) simulation, reveals fuel gap from spatial averaging |
| 2.4 | Implement `shared/metrics.py` | `shared/metrics.py` | Done — `compute_result_metrics()`, `build_result_json()`, `save_result()` |
| 2.5 | Wire `cli.py run static_det` | `cli.py` | Done — transform -> optimize -> simulate -> metrics -> JSON + CSV |
| 2.6 | Validate against known result | manual test | Done — see results below |

**Gate**: Passed. Committed `33862b7`.

#### Validation Results

**Paper data (Table 8 weather, 13 waypoints, 78 speeds 8.0–15.7 kn):**

| Solver | Fuel (kg) | Time (h) | Solve time | Delta vs legacy |
|--------|-----------|----------|------------|-----------------|
| Legacy PuLP (old script) | 372.37 | 280.00 | 0.18 s | — |
| New pipeline + PuLP | 372.47 | 280.00 | 0.10 s | +0.03% |
| New pipeline + Gurobi | 372.49 | 280.00 | 0.005 s | +0.03% |

The +0.03% delta comes from GPS-computed headings differing by 0.1–0.9 degrees from the paper's hardcoded headings.

**Real API weather (HDF5, 279 waypoints, 21 speeds 11–13 kn):**

| Metric | Planned | Simulated |
|--------|---------|-----------|
| Total fuel | 358.36 kg | 361.82 kg |
| Voyage time | 280.00 h | 282.76 h |
| Fuel gap | — | 0.97% |
| CO2 emissions | — | 1,146.98 kg |
| Avg SOG | — | 12.01 knots |
| Solve time (Gurobi) | 0.004 s | — |

The fuel gap (planned < simulated) is expected: the LP averages weather across 12 segments, while the simulation uses per-waypoint weather (279 nodes). Gurobi solves ~350x faster than PuLP CBC.

### Phase 3: Dynamic Deterministic

| # | Task | File(s) | Depends on |
|---|------|---------|------------|
| 3.1 | Implement `dynamic_det/transform.py` | `dynamic_det/transform.py` | 0.3, 0.5 |
| 3.2 | Port + refactor `dynamic_det/optimize.py` | `dynamic_det/optimize.py` | 0.3, 3.1 |
| 3.3 | Extend `shared/simulation.py` for PathSpeedSchedule | `shared/simulation.py` | 2.3 |
| 3.4 | Wire `cli.py run dynamic_det` | `cli.py` | 3.1-3.3 |
| 3.5 | Validate DP results | manual test | 3.4 |

**Gate**: `python3 cli.py run dynamic_det` produces result JSON. Fuel < static_det fuel.

**Note**: Phase 3 is the largest refactoring effort — the DP optimizer has hardcoded paths and inline YAML loading that must be replaced with config-driven inputs.

### Phase 4: Dynamic Stochastic

| # | Task | File(s) | Depends on |
|---|------|---------|------------|
| 4.1 | Implement `dynamic_stoch/transform.py` | `dynamic_stoch/transform.py` | 0.5, 3.1 |
| 4.2 | Implement `dynamic_stoch/optimize.py` | `dynamic_stoch/optimize.py` | 3.2, 4.1 |
| 4.3 | Wire `cli.py run dynamic_stoch` | `cli.py` | 4.1, 4.2 |
| 4.4 | Validate re-planning behavior | manual test | 4.3 |

**Gate**: `python3 cli.py run dynamic_stoch --replan-hours 6` produces result JSON with decision_points visible.

### Phase 5: Comparison & Paper Outputs

| # | Task | File(s) | Depends on |
|---|------|---------|------------|
| 5.1 | Implement `compare/compare.py` | `compare/compare.py` | 2.4 |
| 5.2 | Implement `compare/plots.py` | `compare/plots.py` | 5.1 |
| 5.3 | Implement `compare/report.py` | `compare/report.py` | 5.1, 5.2 |
| 5.4 | Wire `cli.py compare` | `cli.py` | 5.1-5.3 |
| 5.5 | Write Makefile | `Makefile` | all |

**Gate**: `python3 cli.py run all && python3 cli.py compare` produces `output/comparison/report.md` with all metrics and figures.

### Phase 6: Sensitivity & Polish (optional, for paper quality)

| # | Task | Notes |
|---|------|-------|
| 6.1 | Re-plan frequency sweep | Run dynamic_stoch with replan_hours = 1, 3, 6, 12, 24 |
| 6.2 | Time window sweep | Run dynamic_det with time_window = 1, 3, 6, 12 |
| 6.3 | Forecast error correlation | Correlate forecast error magnitude with fuel gap |
| 6.4 | Lower bound (tight) — perfect information | Run dynamic_det using **actual weather** instead of forecasts |
| 6.5 | Upper bound (loose) — naive baseline | Sail at **constant average speed** (no optimization) |

#### 6.4 Lower Bound: Perfect Information (Tight)

Run the dynamic deterministic optimizer, but feed it `actual_weather` instead of `predicted_weather`. This means the optimizer has *perfect hindsight* — it knows exactly what the weather was at every waypoint at every hour. No forecast error, no uncertainty.

- **Data source**: `actual_weather` table (not `predicted_weather`)
- **Query**: `actual_weather WHERE sample_hour = t` (where `t` is the hour the ship reaches each waypoint)
- **Interpretation**: The absolute best fuel consumption achievable if we had a perfect weather oracle. No real strategy can beat this — it is the theoretical floor.
- **Use in paper**: All 3 strategies should be compared against this bound. The gap between any strategy and this bound represents the "cost of imperfect information."

#### 6.5 Upper Bound: Naive Constant Speed (Loose)

Sail the entire voyage at a single constant speed (the average of the allowed speed range), ignoring all weather data entirely. No optimization is performed.

- **Speed**: `(V_min + V_max) / 2` (e.g., (11 + 13) / 2 = 12 knots SWS)
- **Fuel calculation**: Simulate the voyage at constant SWS, applying actual weather to compute SOG and FCR at each waypoint
- **Interpretation**: What a captain would burn with zero planning — just pick a speed and go. This is the ceiling; any optimization strategy must beat this.
- **Use in paper**: The improvement of each strategy over this naive baseline quantifies the "value of optimization."

#### Bounding the Strategies

```
Upper bound (naive)     >=  Static Det (LP)  >=  Dynamic Det (DP)  >=  Dynamic Stoch (DP)  >=  Lower bound (perfect info)
  constant speed            frozen weather       one forecast          re-planned forecasts      actual weather, optimized
```

All 3 strategies should fall between these bounds. The tighter the gap between a strategy and the lower bound, the less room for improvement remains.

### Critical Path

```
Phase 0 ─> Phase 1 ─> Phase 2 (simulation engine built here)
  DONE       DONE       DONE
                           |
                           ├─> Phase 3 (largest effort) ─> Phase 4 ─> Phase 5
                           |       NEXT
                           └─> Phase 5 (can start comparison framework in parallel)
```

---

## 10. Research Paper Mapping

### Figures

| Figure | Description | Source |
|--------|-------------|--------|
| Fig 1 | Route map with 13 waypoints | `config/routes/`, `plots.py::plot_route_map()` |
| Fig 2 | Speed profiles (SWS vs distance, all 3 overlaid) | Time series CSVs, `plots.py::plot_speed_profiles()` |
| Fig 3 | Cumulative fuel vs distance | Time series CSVs, `plots.py::plot_fuel_curves()` |
| Fig 4 | Planned vs actual fuel (bar chart, 3 approaches) | Result JSONs, `plots.py::plot_fuel_comparison()` |
| Fig 5 | Forecast error vs lead time | HDF5 predicted vs actual, `plots.py::plot_forecast_error()` |
| Fig 6 | Fuel vs re-plan frequency (sensitivity) | Phase 6 sweep, `plots.py::plot_sensitivity()` |
| Fig 7 | Speed plan evolution at decision points (stochastic) | decision_points data, `plots.py::plot_replan_evolution()` |

### Tables

| Table | Description | Source |
|-------|-------------|--------|
| Table 1 | 3-way approach comparison summary | `compare.py` output |
| Table 2 | Per-segment fuel breakdown (static det) | `result_static_det.json` |
| Table 3 | Value of dynamic modeling (static vs dynamic det delta) | Comparison metrics |
| Table 4 | Value of re-planning (dynamic det vs stochastic delta) | Comparison metrics |
| Table 5 | Forecast error statistics (RMSE/MAE by field, by lead time) | `metrics.compute_forecast_error()` |

### Research Questions

| Question | Comparison | Expected Finding |
|----------|-----------|-----------------|
| Value of time-varying weather modeling? | Dynamic Det. vs Static Det. | 3-5% fuel savings from DP |
| Value of forecast adaptation? | Dynamic Stoch. vs Dynamic Det. | 1-3% additional savings |
| Optimal re-plan frequency? | Stochastic sweep | Diminishing returns past 6h |
| Lower bound (perfect info)? | Dynamic Det. with actuals | Floor on achievable fuel — cost of imperfect information |
| Upper bound (naive baseline)? | Constant avg speed, no optimization | Ceiling on fuel — value of any optimization |
| Which segments benefit most from dynamic planning? | Per-segment delta | High-variability segments |

---

## 11. Current Status

| Component | Status | Notes |
|-----------|--------|-------|
| Weather data (pickle) | Complete | 248 MB, 3,388 nodes, 72h on server |
| Weather data (HDF5) | Complete | `pipeline/data/voyage_weather.h5` — 279 nodes, 12 sample hours, 562K predicted rows |
| Existing LP optimizer | Working | `Linear programing/ship_speed_optimization_pulp.py` (legacy) |
| Existing DP optimizer | Working | `Dynamic speed optimization/speed_control_optimizer.py` (legacy) |
| Physics functions | Ported | `pipeline/shared/physics.py` — consolidated, added heading + config loader |
| Pipeline Phase 0 | **Complete** | Foundation: directory structure, config, physics, beaufort, HDF5 I/O, CLI skeleton |
| Pipeline Phase 1 | **Complete** | Data layer: waypoint generation, weather collection, pickle import |
| Pipeline Phase 2 | **Complete** | Static det: transform, LP optimizer (PuLP + Gurobi), simulation engine, metrics, JSON output |
| Pipeline Phase 3 | Not started | Dynamic deterministic (DP graph) |
| Pipeline Phase 4 | Not started | Dynamic stochastic (DP + re-planning) |
| Comparison framework | Not started | Phase 5 |

### Source Files for Porting

| New Module | Port From | Key Changes | Status |
|------------|-----------|-------------|--------|
| `shared/physics.py` | `Linear programing/utility_functions.py` | Drop unused functions, add `sws_from_sog()`, `calculate_ship_heading()`, `load_ship_parameters()` | **Done** |
| `shared/simulation.py` | New | Per-waypoint forward simulation engine, reused by all approaches | **Done** |
| `shared/metrics.py` | New | Result metrics, JSON builder, output contract | **Done** |
| `static_det/transform.py` | New | HDF5 -> 12-segment averaged weather + SOG matrix + FCR array | **Done** |
| `static_det/optimize.py` | `Linear programing/ship_speed_optimization_pulp.py` | Replace .dat parsing with in-memory dict, dual solver (PuLP + Gurobi) | **Done** |
| `collect/collector.py` | `test_files/multi_location_forecast_170wp.py` | Replace pickle with HDF5 append | **Done** |
| `collect/waypoints.py` | `test_files/generate_intermediate_waypoints.py` | Config-driven interval and route | **Done** |
| `dynamic_det/optimize.py` | `Dynamic speed optimization/speed_control_optimizer.py` | Replace hardcoded paths, use shared physics | Not started |

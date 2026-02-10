# Ship Speed Optimization: Modeling Approaches Comparison

## Overview

This document organizes all modeling approaches for ship speed optimization, from the baseline research paper methodology to advanced stochastic methods enabled by real-time weather forecasting.

---

## Problem Definition Evolution

| Aspect | Level 1: Static | Level 2: Time-Varying | Level 3: Stochastic |
|--------|-----------------|----------------------|---------------------|
| **Weather Knowledge** | Single snapshot | Deterministic forecast | Ensemble forecasts |
| **Planning Horizon** | One-shot (voyage start) | Rolling windows | Multi-scenario |
| **Adaptability** | None | Re-optimize at windows | Robust + MPC |
| **Uncertainty** | Ignored | Ignored | Quantified |

---

## Master Comparison Table

### Planning Methods (How we decide speeds)

| # | Method | Planning Horizon | Weather Assumption | Speed Decision | Solution Method | Status |
|---|--------|------------------|-------------------|----------------|-----------------|--------|
| **1a** | GA (Article) | Single (voyage start) | Constant all segments | 1 per segment | Genetic Algorithm | ✓ Reference |
| **1b** | LP (Static) | Single (voyage start) | Constant all segments | 1 per segment | Linear Programming | ✓ Implemented |
| **2** | DP (Dynamic) | 6-hour windows | Time-varying per window | Per time-window | Dijkstra graph | ✓ Implemented |
| **3** | Constant Speed | None | N/A | Fixed 12 knots | No optimization | ✓ Baseline |
| **4** | Ensemble Robust | Multi-scenario | 12 forecasts (uncertain) | Robust across scenarios | Minimax / CVaR | ⏳ Planned |
| **5** | MPC | Rolling | Latest at each window | Re-optimize each window | DP + replanning | ⏳ Planned |

### Validation Framework (How we evaluate plans)

| Scenario | Plan With | Evaluate Against | Purpose |
|----------|-----------|------------------|---------|
| **V1** | Run 1 forecast (oldest) | Run 12 forecast (newest) | Proxy validation - immediate |
| **V2** | Run 1 forecast (oldest) | Historical API (true obs) | True validation - future |
| **V3** | Run 12 forecast (newest) | Run 12 forecast (newest) | Perfect information bound |

### Full Evaluation Matrix

| Plan Method | Planned Fuel | V1: Actual (Run 12) | V2: Actual (Historical) | Gap V1 | Gap V2 |
|-------------|--------------|---------------------|-------------------------|--------|--------|
| GA (Article) | 372.62 kg | TBD | TBD | TBD | TBD |
| LP (Static) | 372.37 kg | TBD | TBD | TBD | TBD |
| DP (Dynamic) | ~355 kg | TBD | TBD | TBD | TBD |
| Constant 12kt | ~390 kg | TBD | TBD | TBD | TBD |
| Ensemble | TBD | TBD | TBD | TBD | TBD |
| MPC | TBD | TBD | TBD | TBD | TBD |

*Gap = (Actual - Planned) / Planned × 100%*

---

## Detailed Approach Descriptions

### 1a. Article Baseline (Genetic Algorithm)

```
Problem Definition:
- Decide: One speed per segment (12 segments)
- Given: Static weather conditions (same for entire voyage)
- Objective: Minimize total fuel consumption
- Constraint: Arrive within ETA

Assumptions:
- Weather does not change during voyage
- All information known at voyage start
- No opportunity to adapt plan en-route

Result: 372.62 kg total fuel (reference baseline)
```

### 1b. LP Replication

```
Same problem definition as 1a, different solution method:
- Binary decision variables x[i][j] for segment i, speed j
- SOS2 constraints for piecewise linear SOG-FCR approximation
- Commercial (Gurobi) and open-source (PuLP) solvers

Result: 372.37 kg total fuel (+0.07% improvement over GA)
```

### 2. Dynamic Programming (Time-Varying Weather)

```
Problem Definition:
- Decide: Speed at each (time, distance) node
- Given: Weather changes at 6-hour window boundaries
- Objective: Minimize total fuel consumption
- Constraint: Arrive within ETA

Key Difference:
- Weather is DIFFERENT in each 6-hour window
- Can choose different speeds as conditions change
- Graph-based state space: time × distance × speed

Expected Result: 5-15% fuel savings vs static methods
```

### 3. Simulation Validation Framework

```
Purpose: Validate optimization strategies using real forecast data

Setup:
┌─────────────────────────────────────────────────────────────┐
│  Run 1 (oldest)         ...         Run 12 (newest)         │
│  │                                   │                      │
│  ▼                                   ▼                      │
│  PLAN with this        →→→→→→       EVALUATE against this   │
│  (what captain sees)                 (what actually happens) │
└─────────────────────────────────────────────────────────────┘

Scenarios to Compare:
┌──────────────────┬─────────────────────┬────────────────────────┐
│ Scenario         │ Plan Based On       │ Simulated Against      │
├──────────────────┼─────────────────────┼────────────────────────┤
│ A: Dynamic DP    │ Run 1 forecast      │ Run 12 (ground truth)  │
│ B: Static LP     │ Run 1 average       │ Run 12 (ground truth)  │
│ C: Constant 12kt │ No optimization     │ Run 12 (ground truth)  │
│ D: Industry Std  │ Segment averages    │ Run 12 (ground truth)  │
└──────────────────┴─────────────────────┴────────────────────────┘

Data Required: multi_location_wind_forecast.xlsx, multi_location_wave_forecast.xlsx
```

### 4. Ensemble-Based Robust Optimization

```
Problem Definition:
- Decide: Speed schedule that performs well across ALL scenarios
- Given: 12 different forecasts (ensemble members)
- Objective: Minimize worst-case or expected fuel consumption
- Constraint: Robust ETA satisfaction

Uncertainty Quantification:
┌─────────────────────────────────────────────────┐
│  For each (segment, time_window):               │
│                                                 │
│  wave_heights = [run1, run2, ..., run12]        │
│  μ = mean(wave_heights)                         │
│  σ = std(wave_heights)                          │
│                                                 │
│  Scenarios:                                     │
│    Optimistic:  μ - σ  (calm conditions)        │
│    Expected:    μ      (most likely)            │
│    Pessimistic: μ + σ  (rough conditions)       │
│                                                 │
│  Confidence = 1 - (σ / μ)                       │
└─────────────────────────────────────────────────┘

Solution Methods:
- Minimax: minimize maximum fuel across scenarios
- Expected value: minimize weighted average fuel
- CVaR: minimize conditional value at risk (worst 15%)
```

### 5. Model Predictive Control (MPC)

```
Problem Definition:
- Decide: Speed for next window only
- Given: Latest available forecast
- Objective: Minimize fuel for remaining voyage
- Constraint: Maintain ETA feasibility

Rolling Horizon Process:
┌────────────────────────────────────────────────────────────┐
│ Time 0:  Fetch forecast → Optimize full voyage → Execute   │
│          window 1 speed                                    │
│                                                            │
│ Time 6h: Fetch NEW forecast → Re-optimize remaining →      │
│          Execute window 2 speed                            │
│                                                            │
│ Time 12h: Fetch NEW forecast → Re-optimize remaining →     │
│           Execute window 3 speed                           │
│                                                            │
│ ... continue until arrival                                 │
└────────────────────────────────────────────────────────────┘

Advantage: Always uses freshest information
Requirement: Real-time API access during voyage
```

---

## Data Requirements Matrix

| Approach | Ship Params | Route Data | Weather Data | Forecast Updates |
|----------|-------------|------------|--------------|------------------|
| 1a/1b (Static) | ✓ | 12 segments | Single snapshot | None |
| 2 (DP) | ✓ | 12 segments | Per 6-hour window | None (pre-loaded) |
| 3 (Simulation) | ✓ | 13 waypoints | 12 runs × 168 hours | Batch (server) |
| 4 (Ensemble) | ✓ | 13 waypoints | 12 runs × 168 hours | Batch (server) |
| 5 (MPC) | ✓ | 13 waypoints | Latest forecast | Real-time API |

---

## Server Data Integration

### Current Server Runs (Enabling Approaches 3-5)

```
Running on: Shlomo1-pcl.eng.tau.ac.il
Session: wave_forecast, wind_forecast

Output Files:
├── multi_location_wave_forecast.xlsx (11 MB)
│   ├── summary: Current conditions all 13 waypoints
│   └── wp_01..wp_13: Hourly forecasts (168 hours each)
│
└── multi_location_wind_forecast.xlsx (15 MB)
    ├── summary: Current conditions all 13 waypoints
    └── wp_01..wp_13: Hourly forecasts (168 hours each)

Collection Schedule:
- Every 15 minutes
- 288 runs total (72 hours of collection)
- Progress: ~50% complete (run 146/288)
```

### How Server Data Enables New Approaches

```
                    ┌─────────────────────────────────────┐
                    │     Open-Meteo Marine API           │
                    └──────────────┬──────────────────────┘
                                   │
                    ┌──────────────▼──────────────────────┐
                    │  multi_location_*_forecasting.py    │
                    │  (running on TAU server)            │
                    └──────────────┬──────────────────────┘
                                   │
              ┌────────────────────┼────────────────────┐
              │                    │                    │
              ▼                    ▼                    ▼
    ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
    │  Run 1 (oldest) │  │  Run 6 (mid)    │  │  Run 12 (newest)│
    │  Forecast t-72h │  │  Forecast t-36h │  │  Forecast t-0h  │
    └────────┬────────┘  └────────┬────────┘  └────────┬────────┘
             │                    │                    │
             └────────────────────┼────────────────────┘
                                  │
                    ┌─────────────▼─────────────────────┐
                    │      ENSEMBLE (12 members)        │
                    │  - Uncertainty quantification     │
                    │  - Forecast accuracy analysis     │
                    │  - Robust optimization input      │
                    └───────────────────────────────────┘
```

---

## Expected Results Comparison

| Approach | Fuel (kg) | vs Baseline | Computational Cost | Practical Feasibility |
|----------|-----------|-------------|-------------------|----------------------|
| 1a. GA (Article) | 372.62 | 0% (baseline) | Medium | ✓ Pre-voyage |
| 1b. LP | 372.37 | +0.07% | Low | ✓ Pre-voyage |
| 2. DP | ~355-360 | +3-5% | Medium | ✓ Pre-voyage |
| 3. Simulation | (validation) | (measures gap) | Low | ✓ Post-hoc analysis |
| 4. Ensemble | ~340-350 | +6-9% | High | ✓ Pre-voyage |
| 5. MPC | ~330-345 | +8-12% | High | ⚠ Requires connectivity |

*Note: Results for approaches 3-5 are estimates pending implementation*

---

## Implementation Roadmap

```
Phase 1: COMPLETE
├── [✓] Article baseline replication (GA reference)
├── [✓] LP implementation (PuLP + Gurobi)
├── [✓] DP implementation (time-varying weather)
└── [✓] Weather data collection infrastructure

Phase 2: IN PROGRESS
├── [⏳] Server data collection (146/288 runs complete)
├── [ ] Excel → YAML converter for DP input
└── [ ] Simulation framework skeleton

Phase 3: PLANNED
├── [ ] Simulation validation (Approach 3)
├── [ ] Ensemble robust optimization (Approach 4)
└── [ ] Results comparison & paper writing

Phase 4: FUTURE
├── [ ] MPC real-time optimization (Approach 5)
└── [ ] Operational deployment considerations
```

---

## Validation Framework: Plan vs Actuals

### Core Concept

Every optimization plan is evaluated by simulating the voyage with **actual weather conditions**:

```
┌────────────────────────────────────────────────────────────────────────┐
│  PLAN (using forecast available at departure)                          │
│  ════════════════════════════════════════════                          │
│  Input: Run 1 forecast (oldest, what captain sees)                     │
│  Output: speed_schedule[segment] or speed_schedule[segment][hour]      │
│                                                                        │
│  Methods:                                                              │
│  • LP → single speed per segment                                       │
│  • DP → speed per time-window                                          │
│  • Constant → 12 knots everywhere                                      │
│  • GA (article baseline)                                               │
└────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│  SIMULATE (execute plan against actual weather)                        │
│  ══════════════════════════════════════════════                        │
│  For each segment, for each hour:                                      │
│    planned_SWS = speed_schedule[segment][hour]                         │
│    actual_weather = actuals[segment][hour]  # wind, wave, current      │
│    actual_SOG = calculate_SOG(planned_SWS, actual_weather)             │
│    actual_fuel += FCR(planned_SWS) × Δt                                │
│    distance_covered += actual_SOG × Δt                                 │
│                                                                        │
│  Result: actual_total_fuel, actual_arrival_time                        │
└────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│  COMPARE                                                               │
│  ═══════                                                               │
│  │ Method   │ Planned Fuel │ Actual Fuel │ Gap   │ Arrival Delay │    │
│  ├──────────┼──────────────┼─────────────┼───────┼───────────────┤    │
│  │ LP       │ 372 kg       │ 385 kg      │ +3.5% │ +2.1 hours    │    │
│  │ DP       │ 355 kg       │ 360 kg      │ +1.4% │ +0.8 hours    │    │
│  │ Constant │ 390 kg       │ 395 kg      │ +1.3% │ +1.5 hours    │    │
│  │ GA       │ 372 kg       │ 388 kg      │ +4.3% │ +2.4 hours    │    │
│  └──────────┴──────────────┴─────────────┴───────┴───────────────┘    │
└────────────────────────────────────────────────────────────────────────┘
```

### "Actuals" Data Sources

| Source | Description | Availability | Accuracy |
|--------|-------------|--------------|----------|
| **Run 12 (newest forecast)** | Most recent API forecast as proxy | ✓ Already collecting | Good (forecast ≈ actuals for near-term) |
| **Historical API** | Open-Meteo historical marine data | Post-voyage fetch | Best (true observations) |

### Approach A: Forecast Ensemble Validation (Current)

Uses server data already being collected:

```
Timeline:
────────────────────────────────────────────────────────────────►
T-72h        T-36h        T-12h        T=0          T+168h
  │            │            │            │              │
  ▼            ▼            ▼            ▼              ▼
Run 1        Run 6        Run 10       Run 12        End of
(oldest)     (mid)        (recent)     (newest)      forecast
  │                                      │
  │                                      │
  ▼                                      ▼
PLAN with this ──────────────────► EVALUATE against this
(captain's view)                   (proxy for actuals)
```

**Advantages:**
- Data already being collected on server
- Shows forecast degradation impact
- Enables immediate validation

**Limitations:**
- Run 12 is still a forecast, not true observations
- Weather may change after Run 12 was fetched

### Approach B: Historical Validation (Future)

Uses Open-Meteo Historical Marine API:

```python
# Fetch actual historical weather for a completed voyage
import openmeteo_requests

url = "https://marine-api.open-meteo.com/v1/marine"
params = {
    "latitude": waypoint_lat,
    "longitude": waypoint_lon,
    "start_date": "2026-01-15",  # voyage start
    "end_date": "2026-01-22",    # voyage end
    "hourly": ["wave_height", "wave_direction", "wave_period",
               "wind_wave_height", "swell_wave_height"]
}
# + Ocean currents from separate historical API
```

**Advantages:**
- True observed conditions (not forecasts)
- Can validate any historical voyage
- Most accurate evaluation

**Limitations:**
- Requires voyage to be completed first
- Need to implement historical data fetcher
- Ocean current historical data availability varies

### Metrics to Compare

| Metric | Formula | Meaning |
|--------|---------|---------|
| **Fuel Gap** | (actual - planned) / planned × 100% | Forecast error impact on fuel |
| **Arrival Delay** | actual_time - planned_time | ETA reliability |
| **Fuel Efficiency** | actual_fuel / distance | kg per nautical mile |
| **Plan Robustness** | std(actual_fuel across scenarios) | Consistency across conditions |
| **Value of DP** | fuel_LP - fuel_DP | Benefit of dynamic planning |

### Validation Scenarios Matrix

| Scenario | Plan Method | Plan Data | Actual Data | Purpose |
|----------|-------------|-----------|-------------|---------|
| **S1** | LP (static) | Run 1 avg | Run 12 hourly | Baseline industry practice |
| **S2** | DP (dynamic) | Run 1 hourly | Run 12 hourly | Time-varying planning value |
| **S3** | Constant 12kt | None | Run 12 hourly | No-optimization baseline |
| **S4** | LP (static) | Run 1 avg | Historical | True validation (future) |
| **S5** | DP (dynamic) | Run 1 hourly | Historical | True validation (future) |
| **S6** | Perfect info | Run 12 | Run 12 | Upper bound (hindsight) |

### Expected Insights

1. **Forecast Error Quantification**: How much does weather forecast error impact fuel consumption?

2. **DP vs LP Value**: Does time-varying planning recover some of the forecast error penalty?

3. **Robustness Ranking**: Which planning method has smallest gap between planned and actual?

4. **Perfect Information Bound**: How much could we save with perfect weather knowledge?

---

## Key Insights

1. **Static → Dynamic**: Moving from constant weather to time-varying weather captures the reality that conditions change during multi-day voyages.

2. **Deterministic → Stochastic**: The 12-run ensemble from server data enables uncertainty quantification - we can measure how much forecasts vary and plan accordingly.

3. **One-shot → Rolling**: MPC approach acknowledges that we'll get better forecasts as the voyage progresses - why not use them?

4. **Plan vs Actuals Validation**: The critical test is not planned fuel, but actual fuel when following the plan through real weather conditions.

---

## References

- Research Paper: "Ship Speed Optimization Considering Ocean Currents to Enhance Environmental Sustainability in Maritime Shipping"
- Table 8: Voyage data (12 segments, 13 waypoints)
- Tables 2-4: Correction coefficients for speed reduction
- Equations 7-16: SOG and FCR calculations

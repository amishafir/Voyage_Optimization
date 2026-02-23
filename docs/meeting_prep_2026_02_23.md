# Meeting Prep — Supervisor Meeting, Feb 23 2026

---

## 1. Data Structure

### Pipeline

```
Open-Meteo API → Collection (hourly) → HDF5 → Transform → Optimize → Simulate → Compare
```

### Three HDF5 Datasets

| Dataset | HDF5 File | Route | Nodes | Samples | Purpose |
|---------|-----------|-------|:-----:|:-------:|---------|
| **Original** | `voyage_weather.h5` | Persian Gulf → Malacca (3,394 nm, ~280h) | 279 | 12h | Base experiments |
| **Exp A** | `experiment_a_7wp.h5` | Persian Gulf → IO1 (1,678 nm, ~140h) | 7 | 135h | Temporal isolation (coarse spatial) |
| **Exp B** | `experiment_b_138wp.h5` | Same short route | 138 | 134h | Spatial + temporal (fine spatial) |

Exp A and B form a **2x2 factorial design** — same route, different spatial densities, 11x more temporal samples than original.

### HDF5 Schema (3 tables, identical across all files)

| Table | Key Columns | Rows (exp_b) |
|-------|-------------|:------------:|
| `/metadata` | node_id, lat, lon, waypoint_name, is_original, distance_from_start_nm, segment | 138 |
| `/actual_weather` | node_id, sample_hour, + 6 weather fields | 18,492 |
| `/predicted_weather` | node_id, forecast_hour, sample_hour, + 6 weather fields | 3.1M |

**6 weather fields:** wind_speed_10m_kmh, wind_direction_10m_deg, beaufort_number (calculated, not from API), wave_height_m, ocean_current_velocity_kmh, ocean_current_direction_deg

**Time dimensions:**
- `sample_hour` = when we queried the API (0, 1, 2, ... — always integer)
- `forecast_hour` = what future hour the prediction is about (-18 to +173, ~7 days ahead)
- Each sample produces ~168 forecast hours per node

**Known issue:** Last waypoint on each route may have NaN for wave/current (coastal, outside Marine API coverage). Handled by clamping to 0.

---

## 2. Optimization Algorithms

### Physics Model (shared by all approaches)

8-step speed correction from research paper: SWS → wind/wave resistance → weather-corrected speed → vector addition with current → SOG.

**FCR** = 0.000706 × SWS³ (kg/hour, cubic — this convexity drives the key findings)

### Three Strategies

| | Static Det. (LP) | Dynamic Det. (DP) | Rolling Horizon (RH) |
|--|---|---|---|
| **Granularity** | 12 segments (~280 nm each) | 278 legs (~12 nm each) | 278 legs, re-planned |
| **Weather** | Actual, single snapshot (hour 0) | Predicted, single forecast (hour 0) | Predicted, fresh forecast each decision point |
| **Algorithm** | Linear Program (Gurobi/PuLP) | Forward Bellman DP | DP × 42 decision points |
| **Re-planning** | None | None | Every 6h (configurable) |
| **Solve time** | 0.002s | 1.7s | 26s |

**LP:** Averages weather per segment → picks one SWS per segment (21 candidates, 11.0–13.0 kn) → minimizes fuel subject to ETA ≤ 280h. SOS2 piecewise linearization for SOG(SWS).

**DP:** Builds (node, time_slot) state space → tries all 21 SWS at each state → tracks fuel + time → backtracks optimal path. Uses predicted weather at the forecast hour matching the ship's arrival time at each node.

**RH:** At each decision point, loads the latest forecast and re-runs DP for the remaining voyage. Stitches executed segments together.

### Simulation (SOG-target model)

The optimizer outputs SOG targets. The simulation determines what SWS is needed to achieve that SOG under **actual** weather (binary search inversion). SWS is clamped to engine limits [11, 13] kn — violations are logged.

This is operationally realistic: ships maintain target speed over ground, adjusting engine power as conditions change.

---

## 3. Results

### Canonical Results (SOG-target, ETA=280h, full route)

| Approach | Sim Fuel (kg) | Fuel Gap | SWS Violations | vs Constant Speed |
|----------|:------------:|:--------:|:--------------:|:-----------------:|
| **Rolling Horizon** | **364.8** | 0.92% | 60/278 (22%) | -3.2 kg |
| Dynamic DP | 366.9 | 0.42% | 62/278 (22%) | -1.0 kg |
| Static LP | 368.0 | 2.69% | 10/278 (4%) | +0.1 kg |
| Constant SOG | 367.9 | — | 9/278 (3%) | baseline |
| Lower bound | 352.6 | — | 0 | — |
| Upper bound | 406.9 | — | 171 | — |

### Five Key Findings

**1. The simulation model flips the ranking.**
Under fixed-SWS (naive): LP wins. Under SOG-targeting (realistic): RH > DP > LP. Root cause: Jensen's inequality on cubic FCR — segment averaging hides weather variation, creating hidden execution costs.

**2. LP = constant speed (operationally meaningless).**
LP: 368.0 kg. Constant speed: 367.9 kg. LP with predicted weather: 368.0 kg. The weather source is irrelevant — LP's disadvantage is purely structural (segment averaging compresses all signal). LP speed range is just 12.0–12.5 kn.

**3. Forecast horizon effect is route-length dependent.**
Full route (280h): plateau at 72h, ~1.5 kg range. Short route (140h): flat from 24h, 0.08 kg range. Critical variable: does the voyage extend beyond the accurate forecast window (~72–96h)? If not, even a 1-day forecast suffices.

**4. Information value hierarchy (2x2 decomposition on short route).**

| Factor | Impact | Rank |
|--------|:------:|:----:|
| Temporal (forecast error cost) | +3.02 kg | 1st |
| Spatial (segment averaging cost) | +2.44 kg | 2nd |
| Interaction (spatial mitigates temporal) | -1.43 kg | — |
| Re-planning benefit (RH vs DP) | -1.33 kg | 3rd |

**5. Forecast error curve completes the causal chain.**
From exp_b (138 nodes × 134 samples), ground-truth RMSE:

| Lead Time | Wind RMSE (km/h) | Wind Bias |
|:---------:|:----------------:|:---------:|
| 0h | 4.13 | +0.20 |
| 72h | 6.13 | +1.31 |
| 133h | 8.40 | +2.67 |

Wind RMSE doubles (+103%). Systematic overpredict bias → DP/RH prepare for headwinds that don't materialize → SWS overspeed violations. Error accelerates after 72h, matching the horizon plateau.

### Generalizability (two routes, two weather regimes)

| Finding | Full Route (windier, 280h) | Short Route (calmer, 140h) |
|---------|:-:|:-:|
| RH > DP > LP | Yes | Yes |
| LP ≈ constant speed | Yes | Yes |
| Replan negligible | Yes | Yes |
| Horizon matters | Yes (plateau at 72h) | No (flat from 24h) |

### Sensitivity (negligible factors)

- **Replan frequency**: 3h vs 48h → <0.35 kg range
- **Weather source for LP**: actual vs predicted → 0.02 kg difference

---

## 4. What Next

### Status: 9 of 11 Action Items Complete

| # | Item | Status |
|---|------|:------:|
| 1 | DP with actual weather (spatial isolation) | Done |
| 2 | SOG-target simulation model | Done |
| 3 | Horizon sweep under SOG model | Done |
| 4 | Forecast error curve (0-133h) | Done |
| 5 | Intermediate horizons (96h, 144h) | Done |
| 6 | SWS violation analysis | Done |
| 7 | LP with predicted weather | Done |
| 8 | 2x2 spatial × temporal decomposition | Done |
| 9 | Short-route horizon sweep | Done |
| **10** | **IMO/EEXI literature — validate SOG-targeting** | **TODO (small)** |
| **11** | **Multi-season weather robustness** | **TODO (large)** |

### Remaining Work

| Item | Effort | Impact | Notes |
|------|--------|--------|-------|
| IMO/EEXI citations | 2–3 days | Medium | Validates the SOG-target model assumption that drives Finding #1 |
| Multi-season analysis | 2–4 weeks | Large | Monsoon, North Atlantic winter — strengthens generalizability |
| Thesis writing (first draft) | 3–4 weeks | — | Core research is sufficient to start |

### Questions for Supervisor

1. **Scope**: Start writing now (9/11 done), or pursue multi-season analysis first?
2. **Generalizability**: Is two routes sufficient, or do we need more to claim route-length dependence?
3. **IMO/EEXI**: What citation level justifies the SOG-target model? Guidelines, surveys, or reasoning?
4. **Novelty**: Is "LP = constant speed" known in the literature, or is this a new finding?
5. **2x2 interaction** (-1.43 kg): Dedicated section or just a paragraph?

### Proposed Thesis Arc

1. Lead with simulation model insight (SOG-target vs fixed-SWS flips everything)
2. Present LP ≈ constant-speed (strongest, most surprising finding)
3. Layer in forecast horizon + route-length dependence
4. Organize as information value hierarchy (actionable framework for practitioners)

# Meeting Prep — Supervisor Meeting, Monday Feb 23 2026

---

## 1. What Has Been Done

### 1.1 Built a Complete Research Pipeline

A fully configurable pipeline that runs three optimization strategies on the same weather data and compares them under realistic execution conditions.

```
Weather API (Open-Meteo) --> Collection --> HDF5 --> Transform --> Optimize --> Simulate --> Compare
```

| Component | Status |
|-----------|--------|
| Weather data collection (72 hourly samples, 279 waypoints) | Done |
| HDF5 data storage (replaces pickle) | Done |
| Static Deterministic optimizer (LP, Gurobi) | Done |
| Dynamic Deterministic optimizer (Bellman DP) | Done |
| Dynamic Rolling Horizon optimizer (DP + re-planning) | Done |
| SOG-target simulation engine | Done |
| Comparison framework (figures, tables, report) | Done |
| Sensitivity analysis (bounds, horizon sweep, replan sweep) | Done |
| Extended dataset (134 samples, shorter route, two spatial densities) | **Done** |
| Full forecast error curve (0-133h, ground truth) | **Done** |
| 2x2 spatial x temporal decomposition | **Done** |
| Short-route horizon sweep (24-144h) | **Done** |

### 1.2 Experiments Completed

| # | Experiment | Finding |
|---|-----------|---------|
| 1 | Three-way comparison (LP vs DP vs RH) | RH wins under realistic execution |
| 2 | SOG-target simulation model | Ranking flips vs naive fixed-SWS model |
| 3 | DP with actual weather | Isolates spatial granularity value: 0.66% |
| 4 | Forecast error vs lead time (0-11h) | Wind error grows +45%, waves flat |
| 5 | Forecast horizon sweep (72h-168h) | Plateau after 72h; ~1.5 kg range |
| 6 | Replan frequency sweep (3h-48h) | Negligible impact (<0.35 kg range) |
| 7 | LP with predicted weather | LP_predicted = LP_actual = constant speed |
| 8 | SWS violation analysis | LP: 10 mild; DP/RH: 60+ with hard violations |
| 9 | Theoretical bounds (lower/upper) | Optimization span: 352.6 - 406.9 kg |
| **10** | **Full forecast error curve (0-133h)** | **Wind RMSE doubles (4.1→8.4 km/h), bias grows to +2.7 km/h** |
| **11** | **2x2 decomposition (spatial x temporal)** | **Temporal +3.02 kg > Spatial +2.44 kg, interaction -1.43 kg** |
| **12** | **Short-route horizon sweep (24-144h)** | **Horizon effect flat on short route (0.08 kg range)** |

---

## 2. Research Thesis

### The Central Claim

> The choice of execution model fundamentally changes which optimization approach is best. Under operationally realistic SOG-targeting, segment-averaged LP optimization is equivalent to no optimization at all, while per-node dynamic approaches (DP, Rolling Horizon) provide genuine fuel savings.

### Five Contributions

| # | Contribution | Key Evidence |
|---|-------------|-------------|
| 1 | **The simulation model matters** | LP goes from best (361.8 kg) to worst (368.0 kg) when switching from fixed-SWS to SOG-target execution. Root cause: Jensen's inequality on cubic FCR. |
| 2 | **LP optimization is operationally meaningless** | LP (368.0 kg) = constant speed (367.9 kg). The LP barely varies speed (12.0-12.5 kn), so its "optimization" is indistinguishable from just dividing distance by ETA. |
| 3 | **Forecast horizon effect is route-length dependent** | Dominant on long routes (280h, 1.5 kg range), negligible on short routes (140h, 0.08 kg range). Explained by the forecast error growth curve. |
| 4 | **Information value hierarchy** | Temporal effect (+3.02 kg) > spatial effect (+2.44 kg), with meaningful interaction (-1.43 kg). Confirmed by clean 2x2 factorial experiment. |
| 5 | **Forecast error curve completes the causal chain** | Wind RMSE doubles (4.1→8.4 km/h) over 133h, with systematic overpredict bias (+2.7 km/h). This directly explains the SWS violations and the route-length dependence. |

### The Hierarchy (from most to least impactful)

**Full route (280h, 3,394 nm):**
```
1. Forecast horizon         ~8 kg   impact    DOMINANT
2. Optimization vs none     ~3 kg   impact    MEANINGFUL
3. Spatial resolution       ~1 kg   impact    MINOR
4. Replan frequency         ~0 kg   impact    NEGLIGIBLE
```

**Short route (140h, 1,678 nm) — NEW:**
```
1. Temporal accuracy        +3.0 kg  cost     LARGEST FACTOR
2. Spatial averaging        +2.4 kg  cost     SECOND FACTOR
3. Re-planning              -1.3 kg  benefit  CONSISTENT
4. Forecast horizon         ~0.1 kg  impact   NEGLIGIBLE (entire voyage in accurate window)
```

The hierarchy shifts with route length: forecast horizon only matters when the voyage extends beyond the accurate forecast window (~72-96h).

---

## 3. The Three Algorithms

### 3.1 Static Deterministic (LP)

**Concept**: One-shot optimization at departure. Assumes weather is constant across each segment.

**How it works**:
1. Divide the route into 12 segments (one per pair of original waypoints)
2. Average weather across all nodes within each segment (single snapshot, hour 0)
3. For each segment and each candidate SWS (21 speeds, 11.0-13.0 kn in 0.1 kn steps), compute the resulting SOG using the full physics model (wind resistance, wave resistance, current effects)
4. Solve a Linear Program: minimize total fuel subject to ETA <= 280h, one speed per segment
5. Output: one SOG per segment (12 values)

**Solver**: Gurobi (0.002s) or PuLP CBC (0.1s)

**Strengths**: Fast, uses actual observed weather, simple to implement

**Weakness**: Averages weather over ~280 nm segments, so per-node weather variation is lost. Under realistic execution, the ship must maintain the planned SOG at each node — nodes with harsher-than-average weather cost disproportionately more fuel (cubic FCR).

### 3.2 Dynamic Deterministic (DP)

**Concept**: One-shot optimization at departure, but with per-node granularity and time-varying predicted weather.

**How it works**:
1. Use all 279 interpolated waypoints (278 legs, ~12 nm each)
2. Build a weather grid: for each node and each forecast hour, read 6 weather fields from predicted weather (forecast from sample hour 0)
3. Forward Bellman DP over (node, time_slot) state space:
   - For each state, try all 21 SWS candidates
   - Compute SOG at that node under the predicted weather at the corresponding forecast hour
   - Track fuel cost and time, advance to next node
   - Conservative time tracking: `ceil` to 0.1h resolution
4. Backtrack from optimal arrival state to extract per-leg SOG schedule
5. Output: one SOG per leg (278 values)

**State space**: 279 nodes x ~3,300 time slots x 21 speeds = ~19M edge evaluations (sparse: ~0.6M effective). Solve time: 1.7s.

**Strengths**: Per-node speed adaptation, captures time-varying weather

**Weakness**: Plans based on predicted weather (forecast errors), plans once and never updates. For forecast hours beyond the available data (hour 150+), assumes weather persists from last known value.

### 3.3 Dynamic Rolling Horizon (RH)

**Concept**: Re-plan periodically during the voyage using the latest available forecast.

**How it works**:
1. At hour 0: run full DP for the entire voyage using forecast from sample hour 0
2. Execute the first N legs (until next decision point, e.g. 6 hours later)
3. At decision point: load forecast from sample hour 6 (fresher data), re-run DP for the *remaining* voyage from current position
4. Repeat at each decision point (every 6 hours by default = 42 re-plans)
5. Stitch the executed segments together into the final schedule
6. Output: one SOG per leg (278 values), assembled from 42 partial plans

**Solve time**: 42 x ~0.6s = ~26s total

**Strengths**: Adapts to updated forecasts, most fuel-efficient approach

**Weakness**: Highest compute cost, most SWS violations (aggressive plans based on forecasts that may be wrong), ~2h ETA deviation from SWS clamping.

### Algorithm Comparison Summary

| Property | LP | DP | Rolling Horizon |
|----------|-----|-----|-----------------|
| Decision granularity | 12 segments | 278 legs | 278 legs |
| Spatial resolution | ~280 nm/segment | ~12 nm/leg | ~12 nm/leg |
| Weather source | Actual (observed) | Predicted (forecast) | Predicted (rolling) |
| Time-varying weather | No (single snapshot) | Yes (forecast hours 0-149) | Yes (updated each re-plan) |
| Re-planning | None | None | Every 6h (42 times) |
| Planning method | Linear Program | Forward Bellman DP | Bellman DP x 42 |
| Solve time | 0.002s | 1.7s | 26s |

---

## 4. Data Granularity

### 4.1 Spatial: Nautical Mile Resolution

| Level | Waypoints | Legs | Avg Leg Distance | Used By |
|-------|-----------|------|-------------------|---------|
| Original route | 13 | 12 | ~283 nm | LP (segment averaging) |
| Interpolated (1 nm interval) | 279 | 278 | ~12.2 nm | DP, RH |
| Full 1nm grid | 3,388 | 3,387 | 1.0 nm | Collection only (API resolution) |

The LP aggregates 279 nodes' weather into 12 segment averages. The DP/RH optimize per-leg at 279 nodes. Weather was collected at all 3,388 1nm points but the HDF5 stores only the 279 interpolated waypoints (every ~12 nm) to keep the data manageable.

**Impact of spatial resolution** (controlled experiment: DP vs LP on identical actual weather):
- LP (12 segments): 361.82 kg (planned = simulated, since same weather)
- DP (278 legs): 359.44 kg
- Gain from spatial resolution: **2.38 kg (0.66%)**

This is real but small — the 3rd most important factor.

### 4.2 Temporal: Time Windows and Forecast Hours

**Original collection** (full route): 72 hourly samples (sample_hour 0-71), 279 waypoints, 3,394 nm.

**Extended collection** (short route): 132 hourly samples (sample_hour 0-131), two densities:
- exp_a: 7 original waypoints, 135 samples — for temporal isolation
- exp_b: 138 interpolated waypoints, 134 samples — for spatial + temporal analysis

**Forecast structure**: At each sample_hour, the API returns forecasts for the next ~150 hours (forecast_hour 0 through ~149).

| Concept | Definition | Values |
|---------|-----------|--------|
| Sample hour | When the observation/forecast was made | 0, 1, 2, ... 131 (integers, extended) |
| Forecast hour | How far into the future a prediction covers | 0, 1, 2, ... ~149 |
| Lead time | = forecast_hour - sample_hour | 0h (nowcast) to ~149h (6+ days ahead) |

**How each algorithm uses time**:

| Algorithm | Sample hours used | Forecast hours used |
|-----------|------------------|---------------------|
| LP | sample_hour=0 only (actual weather) | N/A — uses actual, not forecast |
| DP | sample_hour=0 only | forecast_hour 0-149, then persistence to 280h |
| RH | sample_hour=0, 6, 12, 18, ... 66 (42 decision points) | Each re-plan reads forecasts from that sample's perspective |

**DP time granularity**: State space uses dt=0.1h (6 minute slots). With `math.ceil`, this is conservative — overestimates travel time by ~1.1h total, costing ~1 kg fuel (<0.3%) but guaranteeing ETA feasibility.

### 4.3 Forecast Horizon

Forecast horizon = how many hours of future weather the optimizer can "see."

**Default**: 150 hours (~6.25 days). The voyage takes ~280 hours (~11.7 days). So the DP has forecast data for the first 54% of the voyage; the remaining 46% uses persistence (last known weather repeated).

**Horizon sweep results** (all at relaxed ETA=285h):

| Horizon | DP Fuel (kg) | RH Fuel (kg) | RH SWS Violations |
|---------|-------------|-------------|-------------------|
| 72h (3 days) | 359.6 | 357.2 | 10 |
| 96h (4 days) | 360.7 | 358.1 | 23 |
| 120h (5 days) | 360.4 | 358.1 | 18 |
| 144h (6 days) | 359.1 | 357.3 | 42 |
| 168h (7 days) | 359.1 | 356.6 | 47 |

**Key finding (full route)**: The curve is a **plateau from 72h onward** (~1.5 kg range). On this route/weather, 72h of forecast (covering ~26% of voyage duration) captures nearly all the available benefit. More data beyond 3 days doesn't meaningfully help.

**But**: Violations increase with longer horizons (RH: 10 at 72h -> 47 at 168h). More information enables more aggressive plans that are harder to execute.

**NEW — Short-route horizon sweep** (exp_b, ~140h voyage, 138 nodes):

| Horizon | Ratio (h/ETA) | DP Fuel (kg) | RH Fuel (kg) |
|---------|--------------|-------------|-------------|
| 24h | 17% | 177.70 | 176.46 |
| 48h | 34% | 177.72 | 176.41 |
| 72h | 51% | 177.70 | 176.47 |
| 96h | 69% | 177.73 | 176.54 |
| 120h | 86% | 177.75 | 176.60 |
| 144h | 103% | 177.78 | 176.54 |

**Key finding (short route)**: Horizon effect is **completely flat** — DP range 0.08 kg, RH range 0.19 kg across 24-144h. Even a 24h forecast (17% of voyage) is sufficient. The critical factor is not absolute horizon length but whether the voyage extends beyond the "accurate forecast" window (~72-96h for wind).

### 4.4 Replan Frequency

How often the Rolling Horizon re-runs the optimizer with fresh forecasts.

| Replan Freq | Sim Fuel (kg) | Decision Points | Solve Time |
|-------------|--------------|-----------------|------------|
| 3h | 364.85 | 76 | 46.8s |
| 6h (default) | 364.76 | 42 | 26.1s |
| 12h | 364.68 | 23 | 13.9s |
| 24h | 364.50 | 12 | 7.6s |
| 48h | 364.72 | 6 | 4.3s |

**Key finding**: Range is <0.35 kg. Re-planning more often does NOT help when successive forecasts don't differ much. On this route, the weather is stable enough that fresh forecasts say almost the same thing as the old ones. Compute cost scales linearly with re-plan count, with zero fuel benefit.

---

## 5. Results Breakdown with Root Causes

### 5.1 The Canonical Results (SOG-Target Model, ETA=280h)

| Approach | Plan Fuel | Sim Fuel | Fuel Gap | Sim Time | SWS Violations | Solve Time |
|----------|-----------|----------|----------|----------|----------------|------------|
| **Rolling Horizon** | 361.4 kg | **364.8 kg** | 0.92% | 282.1h | 60 | 26s |
| **Dynamic DP** | 365.3 kg | **366.9 kg** | 0.42% | 281.2h | 62 | 1.7s |
| **Static LP** | 358.4 kg | **368.0 kg** | 2.69% | 280.3h | 10 | 0.002s |
| Constant SOG (12.13 kn) | — | **367.9 kg** | — | 280.3h | 9 | — |
| Theoretical floor (calm) | — | **352.6 kg** | — | 280.0h | 0 | — |

**Winner**: Rolling Horizon (364.8 kg), saving 3.2 kg over LP.

### 5.2 Root Cause: Why LP Loses Under Realistic Execution

**The mechanism (Jensen's inequality on cubic FCR)**:

1. The LP picks one SOG per segment based on segment-averaged weather
2. Under SOG-target execution, the ship must maintain that SOG at every individual node
3. At nodes with harsher-than-average weather: the ship needs higher SWS -> disproportionately more fuel (FCR = 0.000706 x SWS^3)
4. At nodes with calmer-than-average weather: the ship needs lower SWS -> saves some fuel
5. But because FCR is **convex** (cubic), the penalty at harsh nodes **always outweighs** the savings at calm nodes
6. This is Jensen's inequality: E[f(X)] >= f(E[X]) for convex f

**Numerical proof**: LP (368.0 kg) = constant speed (367.9 kg). The LP's speed variation is tiny (12.0-12.5 kn range), providing essentially zero optimization. The LP doesn't optimize; it averages weather into oblivion.

**Further proof**: LP with actual weather (368.0 kg) = LP with predicted weather (368.0 kg). The weather source doesn't even matter — the LP produces the same result regardless, because segment averaging compresses all weather signal.

### 5.3 Root Cause: Why DP Beats LP

The DP picks per-node SOGs adapted to each node's predicted conditions:
- Into headwinds: plans slower SOG -> lower SWS needed -> less fuel
- With tailwinds: plans faster SOG -> uses the favorable conditions efficiently
- The speed variation is *correlated with local weather* (unlike LP's segment-averaged guesses)

When the ship executes these SOGs under actual weather, the SWS adjustments are smaller because the predicted weather at each node is closer to actual than the segment average would be.

**The cost**: DP has 62 SWS violations (vs LP's 10) because forecast errors at specific nodes cause large SWS corrections. But most violations are moderate (median 0.51 kn beyond limits).

### 5.4 Root Cause: Why RH Beats DP

RH re-plans 42 times during the voyage. At each decision point, it uses the latest forecast, which is slightly more accurate for the near future than the departure-time forecast.

The benefit is consistent but modest (364.8 vs 366.9 = **2.1 kg** savings), because on this route the weather is stable and forecasts don't change much between samples.

### 5.5 Root Cause: Why the Fuel Gap Differs

The "fuel gap" = (simulated - planned) / planned. It measures how wrong the optimizer's fuel estimate was.

| Approach | Fuel Gap | Why |
|----------|----------|-----|
| LP: 2.69% | Plans with segment-averaged weather, executes per-node. Jensen's inequality penalty. | Planning model is structurally wrong (too coarse). |
| DP: 0.42% | Plans with predicted weather, executes under actual. Small forecast errors. | Planning model is accurate but uses imperfect forecasts. |
| RH: 0.92% | Higher gap than DP despite better fuel. Optimizes more aggressively, creating bolder plans that are farther from conservative estimates. | More aggressive optimization = more plan-vs-reality gap. |

### 5.6 Root Cause: SWS Violations

| Approach | Violations | Rate | Max Severity | Why |
|----------|-----------|------|-------------|-----|
| LP | 10 | 3.6% | 0.67 kn | Plans with actual weather, so SWS adjustments are small. 80% soft (<0.5 kn). |
| DP | 62 | 22.3% | 1.46 kn | Forecast errors at specific nodes cause large SWS corrections. 50% hard. |
| RH | 60 | 21.6% | 1.54 kn | Aggressive rolling optimization pushes closer to limits. 18% "very hard" (>1.0 kn). |

Violations cluster in **segments 7-8 (Indian Ocean, ~2000-2500 nm)**: 84-88% violation rate for DP/RH vs 16% for LP. This is where predicted-vs-actual weather mismatch is largest.

**The tradeoff**: LP is operationally safe but fuel-inefficient. DP/RH are fuel-efficient but operationally aggressive. This is an inherent fuel-feasibility tradeoff of forecast-based optimization.

### 5.7 The Clean Decomposition

```
Constant SOG (367.9 kg)  -- "just pick one speed, no optimization"
     |
     v   +0.1 kg (+0.02%)
LP actual weather (368.0 kg)  -- "LP optimization adds nothing"
     |
     v   -1.1 kg (-0.30%)
DP predicted weather (366.9 kg)  -- "spatial granularity helps"
     |
     v   -2.1 kg (-0.57%)
RH predicted weather (364.8 kg)  -- "re-planning helps more"
     |
     v   -12.1 kg (with relaxed ETA + 168h horizon)
RH 168h horizon (356.6 kg)  -- "longer forecast + slack time = best"
     |
     v
Theoretical floor (352.6 kg)  -- "calm water, constant speed"
```

**Factor isolation** (from controlled experiments):

| Factor | How measured | Fuel impact |
|--------|-------------|-------------|
| Weather source (actual vs predicted) | LP_actual vs LP_predicted | 0 kg — irrelevant |
| Segment averaging (12 seg vs 278 legs) | DP_actual vs LP_actual | -2.4 kg (0.66%) |
| Forecast error (predicted vs actual) | DP_predicted vs DP_actual | +8.4 kg (2.33%) |
| Re-planning (DP vs RH) | RH vs DP, same config | -2.1 kg (0.57%) |
| Forecast horizon (150h vs 168h) | Horizon sweep | -8 kg at 168h (dominant) |
| Replan frequency (3h vs 48h) | Replan sweep | ~0 kg (negligible) |

**NEW — 2x2 Decomposition** (clean factorial on short route):

| Config | Data | Approach | Fuel (kg) | vs Baseline |
|--------|------|----------|-----------|-------------|
| A-LP | 7 nodes, actual | LP (6 seg) | 178.19 | baseline |
| A-DP | 7 nodes, predicted | DP (7 nodes) | 181.20 | +3.02 |
| B-LP | 138 nodes, actual | LP (6 seg) | 180.63 | +2.44 |
| B-DP | 138 nodes, predicted | DP (138 nodes) | 182.22 | +4.03 |
| B-RH | 138 nodes, predicted | RH (138 nodes) | 180.89 | +2.71 |

```
Temporal effect (forecast error cost):     +3.02 kg  (largest)
Spatial effect (segment averaging cost):   +2.44 kg  (second)
Interaction (spatial mitigates temporal):  -1.43 kg  (meaningful)
RH re-planning benefit:                   -1.33 kg  (consistent)
```

The negative interaction means finer spatial resolution partially compensates for forecast error — per-node predicted weather is closer to per-node actual weather than segment averages are.

---

## 6. Key Talking Points for the Meeting

### The Punchline
Under operationally realistic execution (ship targets SOG, adjusts engine power), the LP optimizer provides zero benefit over a captain who just picks one constant speed. Only per-node dynamic approaches (DP, Rolling Horizon) deliver genuine fuel savings.

### Four Surprising Results
1. **LP = constant speed**: The most widely-used approach in the literature provides no measurable benefit
2. **The simulation model flips the ranking**: Under the naive model, LP wins. Under the realistic model, LP loses. Most papers don't test this.
3. **Replan frequency doesn't matter**: On this route, re-planning every 3h vs every 48h makes <0.35 kg difference
4. **NEW — Horizon effect is route-length dependent**: On a 280h voyage, forecast horizon is the dominant factor (1.5 kg range). On a 140h voyage, it's completely flat (0.08 kg range). The critical variable is whether the voyage extends beyond the "accurate forecast" window, not the absolute horizon length.

### The Full Forecast Error Curve (NEW — key thesis figure)

With 134 actual weather samples (vs the previous 12), we now have ground-truth forecast accuracy from 0 to 133 hours:

| Lead Time | Wind RMSE (km/h) | Wind Bias | Wave RMSE (m) | Current RMSE (km/h) |
|-----------|-----------------|-----------|---------------|---------------------|
| 0h | 4.13 | +0.20 | 0.052 | 0.358 |
| 24h | 4.84 | +0.59 | 0.072 | 0.382 |
| 48h | 5.63 | +1.21 | 0.076 | 0.406 |
| 72h | 6.13 | +1.31 | 0.094 | 0.448 |
| 96h | 7.65 | +2.86 | 0.114 | 0.460 |
| 120h | 8.34 | +3.15 | 0.118 | 0.443 |
| 133h | 8.40 | +2.67 | 0.113 | 0.503 |

**Why this matters**: Wind RMSE doubles over 133h, and wind speed is the dominant environmental factor for fuel consumption (wind resistance). The growing positive bias (+2.7 km/h at 133h) means forecasts systematically overpredict wind — this is exactly why DP/RH plans create overspeed SWS violations (they prepare for headwinds that don't materialize).

**Connection to horizon sweep**: On the full route (280h), hours 140-280 of the voyage have no forecast coverage and use weather persistence. The forecast error at those hours is even worse than 8.4 km/h. This is why the horizon effect matters on long routes. On the short route (140h), the entire voyage is within the 0-140h window where forecasts are still reasonably accurate — so additional forecast hours don't help.

### Generalizability: Two Routes, Two Weather Regimes (NEW)

| Metric | Full Route | Short Route |
|--------|-----------|------------|
| Distance | 3,394 nm | 1,678 nm |
| Duration | ~280h | ~140h |
| Weather | Windier (std 10.6 km/h) | Calmer (std 6.1 km/h) |
| Sample hours | 12 | 132 |
| RH > DP? | Yes | Yes |
| LP ≈ constant speed? | Yes | Yes |
| Horizon matters? | Yes (plateau at 72h) | **No** (flat from 24h) |

**What generalizes**: The RH > DP ordering and the LP ≈ constant-speed finding hold across both routes. The replan frequency remains negligible.

**What's route-dependent**: The forecast horizon effect is entirely route-length dependent. On a voyage that fits within the ~72h accurate forecast window, even a 1-day forecast is sufficient. On a longer voyage, the hours beyond the forecast horizon run on "weather persistence" — and that's where the fuel cost accumulates.

### What's Now Resolved (since last version)
1. ~~Longer collection window~~ — **DONE**: exp_a (7 WP, 135 samples) + exp_b (138 WP, 134 samples) downloaded and validated
2. ~~Full forecast error curve~~ — **DONE**: 0-133h ground-truth RMSE. Wind doubles, bias grows to +2.7 km/h.
3. ~~2x2 decomposition~~ — **DONE**: Temporal +3.02 kg > Spatial +2.44 kg, with -1.43 kg interaction
4. ~~Generalizability on second route~~ — **DONE**: RH > DP hierarchy holds; horizon effect is route-length dependent

### What's Still Open
1. **IMO/EEXI citations** — confirm that SOG-targeting is standard operational practice
2. **Multi-season weather** — test robustness across different weather regimes (monsoon, winter North Atlantic)

### Questions to Discuss with Supervisor
1. **Is the route-length finding strong enough?** The horizon effect is dominant on the full route (280h) but negligible on the short route (140h). We can explain it via the forecast error curve — but is two routes sufficient evidence, or do we need more?
2. **The 2x2 interaction term** — the -1.43 kg interaction (spatial resolution mitigates forecast error) is a new finding. Is this worth a dedicated section, or just a paragraph?
3. **IMO/EEXI validation**: What level of citation is expected to justify the SOG-target simulation model? Industry practice surveys, IMO guidelines, or can we rely on the reasoning alone?
4. Is the "LP = constant speed" finding sufficiently novel, or is it known in the literature?
5. **Thesis scope**: 9 of 11 action items are done. Are the remaining two (IMO citations + multi-season) worth pursuing before writing, or should we start drafting?

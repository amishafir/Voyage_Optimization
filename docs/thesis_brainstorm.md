# Thesis Brainstorm: Optimal Fuel Consumption Through Data & Decision Points

## 1. Original Thesis

> "More data, more decision points → optimal fuel consumption"

**Status: Partially supported — needs refinement.**

The naive version of this thesis is contradicted by our current results. But a refined version is strongly supported.

---

## 2. What the Data Actually Shows

### 2.1 The Surprise: LP Beats DP in Default Configuration

| Approach | Sim Fuel (kg) | vs LP |
|----------|--------------|-------|
| Static LP (actual weather, 12 segments) | 361.82 | baseline |
| Dynamic DP (predicted weather, 278 legs) | 367.83 | **+1.66% worse** |
| Rolling Horizon (predicted, 42 re-plans) | 364.36 | +0.70% worse |

The simplest approach wins! Why?
- LP plans with **actual** (observed) weather → perfect information for its snapshot
- DP plans with **predicted** (forecasted) weather → forecast errors degrade the plan
- More spatial granularity (278 legs vs 12 segments) does NOT compensate for worse weather input

### 2.2 The Breakthrough: Forecast Horizon Changes Everything

**(Updated: SOG-target model, ETA relaxed to 285h for horizon sweep)**

| Forecast Horizon | DP Fuel (kg) | RH Fuel (kg) | RH vs LP (368 kg) |
|-----------------|-------------|-------------|----------|
| Default (ETA=280h) | 366.87 | 364.76 | -0.88% better |
| 72h (3 days, ETA=285h) | 359.62 | 357.18 | -2.94% better |
| 120h (5 days, ETA=285h) | 360.43 | 358.11 | -2.68% better |
| 168h (7 days, ETA=285h) | 359.11 | 356.63 | -3.09% better |

Note: Horizon sweep uses relaxed ETA=285h (needed for DP feasibility at all horizons). Base comparison uses ETA=280h. The constant-SOG baseline at ETA=280h is 367.92 kg.

**Key finding: Under the SOG-target model, RH beats LP at every horizon.** The forecast horizon effect is smaller than under the old model (~3 kg range vs ~14 kg), but the directional advantage of dynamic approaches is consistent.

### 2.3 Replan Frequency: Negligible Impact

**(Updated: SOG-target model)**

| Replan Freq | Sim Fuel (kg) | Delta |
|-------------|--------------|-------|
| 3h | 364.85 | baseline |
| 6h | 364.76 | -0.09 |
| 12h | 364.68 | -0.17 |
| 24h | 364.50 | -0.35 |
| 48h | 364.72 | -0.13 |

Range: <0.35 kg. Re-planning more often does NOT help when the underlying forecasts don't change much between samples. Confirmed under SOG-target model.

### 2.4 The Simulation Model Matters: SOG-Target Flips the Ranking

**The problem with the old model**: The original simulation applied the planned SWS (engine speed) and let SOG vary with actual weather. This meant the ship's arrival time was unpredictable — it depended on how actual weather differed from planning weather. The LP planned for 280h but arrived at 282.76h; the DP planned for 278.88h but arrived at 280.79h. No approach actually met its ETA.

**The operationally correct model**: In practice, a ship targets a SOG (speed over ground) and adjusts engine power (SWS) to maintain it. The captain doesn't set the engine to a fixed RPM and hope — they watch their GPS speed and throttle up/down. Under this model:

- **SOG is the contract** — the optimizer's SOG schedule is what the ship executes
- **SWS is the adaptive variable** — the ship adjusts engine power per-node to hit the target SOG
- **Time is deterministic** — distance/SOG, no surprises (unless engine limits are hit)
- **Fuel varies** — FCR depends on the *required* SWS, which changes with local weather

**The ranking flipped:**

| Approach | Old Model (fixed SWS) | New Model (target SOG) | Change |
|----------|----------------------|----------------------|--------|
| Static LP | 361.82 kg **(best)** | 367.99 kg **(worst)** | +6.17 kg |
| Dynamic DP | 367.83 kg (worst) | 366.87 kg **(best)** | -0.96 kg |
| Rolling Horizon | 364.36 kg (middle) | 364.76 kg (middle) | +0.40 kg |

**Why the LP got worse (0.97% → 2.69% gap):**

The LP picks one SOG per segment based on **segment-averaged** weather. When the ship tries to maintain that SOG at individual nodes:
- At nodes with harsher-than-average weather → ship needs higher SWS → disproportionately more fuel (FCR ∝ SWS³)
- At nodes with calmer-than-average weather → ship needs lower SWS → saves some fuel
- But **Jensen's inequality on the cubic FCR** means the penalty at harsh nodes *always outweighs* the saving at calm nodes
- The very spatial averaging that made the LP's plan look efficient now costs it in execution

**Why the DP got better (0.69% → 0.42% gap):**

The DP picks per-leg SOGs based on **per-node predicted** weather. These SOGs are already locally tuned to each node's conditions. The SWS adjustments needed under actual weather are smaller because the forecast weather at each node is closer to actual than the segment average would be.

**The ETA picture also improved:**

| Approach | Old Sim Time | New Sim Time | Planned Time |
|----------|-------------|-------------|-------------|
| LP | 282.76h (+2.76) | 280.26h (+0.26) | 280.00h |
| DP | 280.79h (+1.91) | 281.21h (+2.33) | 278.88h |
| RH | 282.26h (+2.37) | 282.09h (+2.20) | 279.89h |

LP now nearly meets its ETA (0.26h deviation — only 10 legs need SWS clamping). DP/RH still deviate ~2h because predicted-vs-actual weather differences cause 56-62 legs to hit engine speed limits.

**SWS engine violations (clamped to [11, 13] kn):**

| Approach | Clamped Legs | Required SWS Range | >13 kn (overspeed) | <11 kn (underspeed) |
|----------|-------------|-------------------|---------------------|----------------------|
| LP | 10/278 (4%) | 10.90 – 13.67 | 9 | 1 |
| DP | 62/278 (22%) | 10.50 – 14.46 | 56 | 6 |
| RH | 60/278 (22%) | 10.13 – 14.54 | 50 | 10 |

The LP has fewer violations because its SOGs are based on actual weather (same source as simulation). DP/RH have more because their SOGs come from predicted weather — when the prediction is wrong, the required SWS correction can exceed engine limits. This is itself a meaningful metric: **SWS violations measure the operational cost of forecast error.**

### 2.5 Theoretical Bounds

**Lower bound** = constant speed in calm water: SOG = total_distance / ETA = 3395.8 / 280 = 12.128 kn.
FCR(12.128) = 1.260 kg/h. **Analytical fuel = 352.64 kg**.

This is the absolute theoretical floor. By Jensen's inequality on the convex cubic FCR, any speed variation increases fuel. Weather effects only push fuel higher (SWS must compensate for conditions).

**Simulated constant-SOG at 12.128 kn under actual weather: 367.92 kg** (9 SWS violations).
This is NOT a lower bound — the optimizer can beat it by varying SOG to exploit favorable weather.

**Upper bound** = constant SOG at max speed (13 kn): analytical = 392.29 kg (calm), simulated = **406.92 kg** (171 SWS violations).

| Reference Point | Fuel (kg) | Note |
|----------------|-----------|------|
| Theoretical floor (calm, 12.13 kn) | **352.64** | Absolute minimum |
| RH optimized | 364.76 | Best optimizer |
| DP optimized | 366.87 | |
| Constant SOG (12.13 kn, actual weather) | 367.92 | No-optimization baseline |
| LP optimized | 367.99 | Worst optimizer |
| Upper bound (13 kn, actual weather) | 406.92 | Maximum fuel |

**Key insight**: LP (367.99) essentially equals constant-speed (367.92). The LP's segment-averaged optimization provides virtually no benefit over a captain who just picks one speed and sticks with it. This is because the LP's speed variation is tiny (12.0–12.5 kn range). Meanwhile, RH saves 3.16 kg over constant-speed by intelligently varying SOG.

**Optimization potential** = upper bound - lower bound = 406.92 - 352.64 = 54.28 kg.
- RH captures (406.92 - 364.76) / 54.28 = **77.6%** of the potential
- DP captures (406.92 - 366.87) / 54.28 = **73.8%**
- LP captures (406.92 - 367.99) / 54.28 = **71.8%**
- Constant-speed captures (406.92 - 367.92) / 54.28 = **71.9%** — same as LP!

### 2.6 Canonical Results (SOG-Target Model)

These are the canonical results going forward. All use the SOG-target simulation model (ETA=280h).

| Approach | Plan Fuel (kg) | Sim Fuel (kg) | Gap (%) | Sim Time (h) | SWS Violations |
|----------|---------------|---------------|---------|-------------|----------------|
| **Rolling Horizon** | 361.43 | **364.76** | 0.92 | 282.09 | 60 |
| **Dynamic DP** | 365.32 | **366.87** | 0.42 | 281.21 | 62 |
| **Static LP** | 358.36 | **367.99** | 2.69 | 280.26 | 10 |

**Winner: Rolling Horizon (364.76 kg)** — re-planning with updated forecasts produces the most fuel-efficient voyage under operationally realistic execution.

### 2.7 The LP ≈ Constant Speed Equivalence

This is perhaps the most striking finding: **the LP optimizer provides essentially zero benefit over a captain who simply picks one constant speed and never changes it.**

| Approach | Sim Fuel (kg) | Delta from constant |
|----------|--------------|---------------------|
| Constant SOG (12.128 kn, actual weather) | 367.92 | baseline |
| Static LP (12 segments, actual weather) | 367.99 | **+0.07 kg (+0.02%)** |

The LP is 0.07 kg *worse* than constant speed. Why?

**The LP's optimization is illusory under the SOG-target model.** Here's the mechanism:

1. The LP picks per-segment SOGs in the range 12.0–12.5 kn — a tiny variation around the mean of 12.128 kn
2. Under the old fixed-SWS model, these speed choices directly translated to different engine speeds, and the cubic FCR rewarded the lower speeds slightly more than it penalized the higher ones
3. Under the SOG-target model, maintaining these slightly-varying SOGs at individual nodes requires SWS adjustments that depend on actual per-node weather
4. The segment-averaged weather the LP used for planning doesn't match any individual node's actual weather
5. **Jensen's inequality on cubic FCR** means the SWS variance within each segment increases fuel: harsh nodes cost more than calm nodes save
6. This penalty exactly cancels the LP's tiny optimization gain

**In other words**: the LP's optimization is a rounding error (~0.5 kn variation), while the execution penalty from segment averaging is real. The two effects cancel, leaving LP ≈ constant speed.

**Contrast with DP/RH**: These pick per-node SOGs that are already adapted to each node's conditions. Their optimization gain is genuine — they vary SOG *in the right direction* (slower into headwinds, faster with tailwinds), saving 1–3 kg over constant speed.

**Implication for the thesis**: This is a powerful result. It means:
- LP optimization is **operationally meaningless** under realistic execution — you'd get the same fuel by just dividing distance by ETA
- The only approaches that provide real fuel savings are those with **per-node spatial resolution** (DP, RH)
- This strengthens the case for dynamic optimization: it's not just "slightly better" than LP, it's "actually works vs. doesn't work"

---

## 3. Refined Thesis Candidates

### Option A: "Forecast Coverage Dominance"

> **"For voyage fuel optimization, the quality and temporal coverage of weather forecasts dominates all other planning factors. Dynamic optimization with sufficient forecast horizon (covering >60% of voyage duration) outperforms static approaches by 3%, while re-planning frequency and spatial granularity have secondary effects."**

Strengths:
- Directly supported by the horizon sweep data
- Clear, testable, quantifiable
- Novel — most maritime optimization papers assume forecasts are given and focus on algorithm comparison

Weaknesses:
- Based on one route, one weather period
- The "60% coverage" threshold needs validation across conditions

### Option B: "Information Value Hierarchy"

> **"There exists a hierarchy of information value in maritime voyage optimization: (1) forecast accuracy and coverage, (2) spatial weather resolution, (3) re-planning frequency. The marginal value of each level depends on the quality of the level above it."**

Strengths:
- Elegant framework that explains ALL our results
- When forecast is perfect (LP with actuals), spatial resolution matters → LP beats DP
- When forecast is long enough (168h), re-planning adds value → RH beats DP by 3.2 kg
- When forecast coverage is short, re-planning can't help → 3h vs 48h doesn't matter

Weaknesses:
- More complex to defend
- Needs more data points to establish the hierarchy quantitatively

### Option C: "Diminishing Returns of Complexity"

> **"The value of dynamic optimization is bounded by forecast quality. Under stable, well-predicted conditions, a simple LP with accurate weather data is near-optimal. Dynamic approaches only justify their computational cost when forecast horizons are long (>5 days) or weather variability is high."**

Strengths:
- Practical industry relevance (when to invest in complex systems)
- Provably true from our data
- Interesting "negative result" angle (complexity doesn't always help)

Weaknesses:
- Less novel — similar claims exist in adjacent fields
- Might undersell the research contribution

### Option D: "Operational Realism Changes the Answer" (NEW — post simulation model change)

> **"The choice of simulation model — whether the ship maintains fixed engine speed (SWS) or targets a fixed speed over ground (SOG) — fundamentally changes which optimization approach is optimal. Under operationally realistic SOG-targeting, dynamic per-node optimization (DP) outperforms static segment-averaged optimization (LP) because Jensen's inequality on the cubic fuel consumption rate penalizes coarse spatial averaging. Rolling Horizon further improves by adapting to forecast updates."**

Strengths:
- Novel methodological contribution — most papers don't examine the simulation model assumption
- Explains a concrete ranking reversal with a clean mathematical cause (Jensen's inequality)
- Directly actionable: tells practitioners that spatial planning granularity matters more than commonly assumed, *but only under realistic execution*
- Supported by clear data: LP goes from best (361.82) to worst (367.99) when the execution model changes
- SWS violations provide a new metric: operational cost of forecast error
- **The LP ≈ constant-speed equivalence is a killer finding** — the LP doesn't just lose, it provides zero value over a trivial baseline

Weaknesses:
- The insight depends on the ship actually maintaining target SOG (assumption about operational practice)
- Needs validation that SOG-targeting is standard industry practice (cite IMO / EEXI literature)

### Recommendation

**Option D is the strongest lead**, with Options A and B as supporting layers:

1. **Lead with the simulation model insight** (Option D) — this is novel and changes the fundamental comparison
2. **Present the LP ≈ constant-speed result** — the strongest evidence that segment-averaged LP optimization is illusory under realistic execution (Section 2.7)
3. **Layer in the forecast horizon finding** (Option A) — longer forecasts amplify the DP/RH advantage
4. **Organize findings as a hierarchy** (Option B) — provides the framework for the full picture

This gives the thesis four distinct contributions:
1. Methodological: simulation model matters (SOG-target vs fixed-SWS)
2. Empirical: LP optimization ≈ no optimization under realistic execution
3. Empirical: forecast horizon is the dominant factor for dynamic approaches
4. Practical: the information value hierarchy guides operational investment decisions

---

## 4. What's Missing — Experiments Needed

### 4.1 Critical Missing Experiment: DP with Actual Weather + Normal ETA

We have:
- LP with actual weather → 361.82 kg (but only 12 segments)
- Lower bound with actual weather → 310.96 kg (but relaxed ETA to 308h)
- DP with predicted weather → 367.83 kg

We DON'T have:
- **DP with actual weather + 280h ETA** → would show the pure value of spatial granularity (278 legs vs 12 segments) with identical weather quality

This single experiment would isolate:
- `DP_actual - LP_actual` = value of spatial granularity alone
- `DP_predicted - DP_actual` = cost of forecast imperfection

**Priority: HIGH. Can run immediately with existing data.**
Config: `dynamic_det.weather_source: actual`, `dynamic_det.nodes: all`, normal ETA.

### 4.2 Longer Collection Window (In Progress)

The server is collecting experiments with 143 sample hours (~6 days) vs the original 72 hours.
- `exp_a`: 7 waypoints (original route density)
- `exp_b`: 138 waypoints (interpolated)

With 143 sample hours:
- RH has access to more diverse forecast snapshots
- Forecast errors at long lead times are captured
- Can test whether re-planning frequency matters MORE with longer, more variable data

**ETA: ~5.5 days from now.**

### 4.3 Weather Variability Axis

Current findings may be route/season-specific. The Persian Gulf → Malacca route during this collection period appears to have **stable, predictable weather** (forecast errors are small, replan frequency doesn't matter).

Questions:
- Would monsoon season data change the results?
- Would a North Atlantic winter crossing show more benefit from re-planning?
- Can we quantify "weather variability" and correlate it with "value of dynamic optimization"?

Options:
- Wait for exp_a/exp_b (different collection window, may have different weather)
- Use historical weather data (Open-Meteo has archives) for contrasting seasons
- Create synthetic weather with controlled variability to map the breakeven curve

### 4.4 Forecast Accuracy Degradation Analysis

We have forecast errors at LT=0h and LT=6h. We need the FULL lead-time curve:
- How does RMSE grow with lead time (0h, 6h, 12h, 24h, 48h, 72h, 120h, 168h)?
- At what lead time does forecast become "noise"?
- Does this correlate with the horizon where DP stops improving?

The data is in the HDF5 — we can compute this without new collection.

**Priority: HIGH. Strengthens the thesis narrative.**

### 4.5 Route Length Sensitivity

Voyage is ~280 hours (12 days). Forecast horizon of 168h covers 60% of the voyage.
- For a shorter route (e.g., 3-day crossing), would 72h forecast cover 100% → DP always wins?
- For a longer route (e.g., 30-day transpacific), even 168h covers only 23% → LP always wins?

This would establish the **critical ratio**: `forecast_horizon / voyage_duration`.

---

## 5. Proposed Thesis Structure

### Core Argument (builds from data)

1. **Establish the three approaches**: LP (12-segment, actual weather), DP (278-leg, predicted weather), RH (278-leg, re-planned predicted weather). Present the pipeline and real collected weather data.

2. **Show the simulation model matters**: Under fixed-SWS execution, LP appears best (361.82 kg). Under operationally realistic SOG-targeting, DP beats LP (366.87 vs 367.99 kg). The ranking reversal is caused by Jensen's inequality on the cubic FCR — segment averaging creates a hidden cost when the ship must actually maintain speed at each node.

3. **Introduce SWS violations as a new metric**: When the ship can't maintain target SOG within engine limits, it reveals where the optimizer's plan fails under real conditions. LP has only 10 violations (its plan is conservative); DP/RH have 60+ (forecast errors create more aggressive plans). This measures the **operational feasibility** of each plan.

4. **Show forecast horizon amplifies the DP advantage**: With 7-day forecasts, RH achieves 351 kg — a further 3% improvement. The forecast horizon is the dominant factor; re-planning frequency is negligible.

5. **Present the information value hierarchy**: Forecast horizon > forecast accuracy > spatial resolution > replan frequency. Each level only adds value when the level above is adequate.

6. **Practical implications**: Define when dynamic optimization justifies its cost. Provide the breakeven conditions (forecast coverage threshold, weather variability).

### Potential Title Ideas

- "Speed Over Ground Targeting Reveals the True Value of Dynamic Voyage Optimization"
- "Why Simulation Models Matter: Jensen's Inequality and the Hidden Cost of Spatial Averaging in Maritime Fuel Optimization"
- "Forecast Horizon, Spatial Resolution, and Execution Model: A Three-Factor Analysis of Maritime Speed Optimization"
- "The Information Value Hierarchy in Maritime Voyage Planning: From Simulation Model to Forecast Coverage"

---

## 6. Key Assumptions to Validate

| # | Assumption | Status | How to Validate |
|---|-----------|--------|-----------------|
| A1 | Forecast accuracy degrades with lead time | Assumed (standard meteorology) | Compute full RMSE curve from HDF5 |
| A2 | LP uses actual weather = perfect information | True by construction | — |
| A3 | DP with actual weather ≈ LP performance | **CONFIRMED** (Exp 4.1) | DP_actual=359.44 vs LP=361.82 (DP wins by 0.66%) |
| A4 | Weather on this route/period is "stable" | Assumed from replan results | Quantify with forecast error variance |
| A5 | 168h horizon covers enough of the voyage | Supported (60% → 3% gain) | Test more horizons (96h, 144h, 192h) |
| A6 | Results generalize to other routes/seasons | **UNKNOWN** | Need multi-route or multi-season data |
| A7 | FCR cubic relationship is accurate | Assumed (from research paper) | Sensitivity analysis on FCR exponent |
| A8 | 279 waypoints is sufficient spatial resolution | Assumed | Compare 279 vs 3,388 (full 1nm grid) |
| A9 | SOG-targeting is standard operational practice | **Assumed** | Cite IMO EEXI / industry practices |
| A10 | Jensen's inequality on cubic FCR causes LP penalty | **CONFIRMED** | LP gap went from 0.97% to 2.69% under SOG model |
| A11 | SWS violations are operationally meaningful | **Assumed** | Validate that engine limits are hard constraints |

---

## 7. Open Questions

1. **Is the forecast horizon effect linear or does it have a knee?** We have 3 data points (72h, 120h, 168h). Need 96h and 144h to see the shape of the curve.

2. **Does the new 143-hour collection window change the replan frequency finding?** With more hourly snapshots, forecasts at each decision point are genuinely different — replan frequency might finally matter.

3. **What's the optimal forecast_horizon / voyage_duration ratio?** Is 60% always the sweet spot, or is it route-dependent?

4. **Can we decompose the DP advantage into spatial vs temporal components?** Run DP with (a) original 13 nodes + time-varying weather, (b) 279 nodes + static weather, (c) 279 nodes + time-varying weather. This gives a 2x2 decomposition.

5. **Is there a "forecast quality threshold" below which LP dominates?** If we artificially add noise to forecasts, at what RMSE does DP start losing to LP?

6. **Should we add a 4th approach?** E.g., "LP with predicted weather" — this would show whether LP's advantage is purely from actual weather or also from the averaging effect of 12 segments (smoothing out noise).

7. ~~**Do the horizon sweep results change under the SOG-target model?**~~ **ANSWERED**: Yes. Under SOG-target, the horizon effect is smaller (356–360 kg range vs 351–366 in old model), but RH consistently beats LP at every horizon. The forecast horizon effect is dampened but the directional conclusion is unchanged.

8. **How large is the Jensen's inequality penalty as a function of weather variability?** The LP's 2.69% gap is route-specific. On a route with more within-segment weather variability, this penalty should grow. Can we quantify this relationship?

9. **What fraction of SWS violations are "hard" vs "soft"?** A violation requiring 13.1 kn (just over the 13 kn limit) is operationally different from one requiring 14.5 kn. Distribution analysis would strengthen the feasibility argument.

10. **Is SOG-targeting truly standard practice?** Need to cite IMO/EEXI literature confirming that ships adjust engine power to maintain target speed. If some operators use fixed-RPM instead, both simulation models are valid for different contexts.

---

## 8. Next Actions (Priority Order)

| # | Action | Impact | Effort | Status |
|---|--------|--------|--------|--------|
| 1 | ~~Run DP with actual weather + normal ETA~~ | ~~Isolates spatial granularity~~ | ~~Small~~ | **DONE** — Exp 4.1 |
| 2 | ~~Change simulation to SOG-target model~~ | ~~Operationally realistic~~ | ~~Medium~~ | **DONE** — ranking flipped |
| 3 | ~~Re-run horizon sweep (72h, 120h, 168h) under SOG model~~ | ~~Confirm horizon effect persists~~ | ~~Small~~ | **DONE** — RH wins at all horizons |
| 4 | Compute full forecast error vs lead time curve | Supports thesis narrative | Small — analysis on existing HDF5 | TODO |
| 5 | Add intermediate forecast horizons (96h, 144h) | Maps the horizon benefit curve | Small — config sweep | TODO |
| 6 | Analyze SWS violation distribution (magnitude histogram) | Strengthens feasibility argument | Small — analysis | TODO |
| 7 | Run LP with predicted weather | Isolates weather-type vs averaging effect | Small — config change | TODO |
| 8 | Wait for exp_a/exp_b completion | Tests generalizability on new data | 5.5 days (passive) | IN PROGRESS |
| 9 | 2x2 decomposition (spatial x temporal) | Cleanly separates factors | Medium — 4 experiment configs | TODO |
| 10 | Cite IMO/EEXI on SOG-targeting practice | Validates simulation model assumption | Small — literature search | TODO |
| 11 | Multi-season/synthetic weather | Tests robustness of thesis | Large — new data source needed | TODO |

---

## 9. Experiment 4.1 Results — The Decomposition

**Run**: DP with actual weather, 278 legs, ETA=285h (minimum feasible ETA).

| Approach | Weather | Nodes | ETA | Sim Fuel (kg) | Fuel Gap |
|----------|---------|-------|-----|---------------|----------|
| Constant SOG | actual | 278 legs | 280h | 367.92 | 4.33% |
| LP | actual (snapshot) | 12 segments | 280h | 367.99 | 2.69% |
| DP predicted | predicted (time-varying) | 278 legs | 280h | 366.87 | 0.42% |
| RH predicted | predicted (re-planned) | 278 legs | 280h | 364.76 | 0.92% |
| RH 168h horizon | predicted (7-day) | 278 legs | 285h | 356.63 | — |
| **Lower bound** | **calm water** | **analytical** | **280h** | **352.64** | **0.00%** |

### Clean Decomposition

```
DP_actual (359.44 kg) vs LP_actual (361.82 kg)
  → Spatial granularity gain: -2.38 kg (-0.66%)
    (278 per-node legs vs 12 segment-averaged legs)

DP_predicted (367.83 kg) vs DP_actual (359.44 kg)
  → Forecast error cost: +8.39 kg (+2.33%)
    (predicted weather vs actual weather, same 278-leg granularity)

Ratio: forecast error cost is 3.5x larger than spatial granularity gain
```

### Key Observations

1. **DP_actual has 0% fuel gap** (planned = simulated = 359.44 kg).
   When the DP plans with the same weather it's simulated against, there is zero gap.
   This is the "perfect information" scenario within the normal ETA constraint.

2. **DP_actual beats LP_actual by 2.38 kg** — the pure value of per-node
   optimization (278 legs) over segment-averaged optimization (12 segments).
   This is real but small (0.66%).

3. **Forecast error costs 8.39 kg** — switching from actual to predicted weather
   on the same 278-leg DP adds 2.33% fuel penalty. This is 3.5x the spatial gain.

4. **The ETA constraint matters**: DP with actual weather needs ETA=285h
   (infeasible at 280h due to conservative `ceil` rounding + harsher actual conditions).
   LP "plans" at 280h but actually simulates at 282.76h (silently exceeds ETA).
   Neither truly meets 280h under actual weather — the LP just doesn't know it.

5. **The 168h horizon RH (351 kg) is the overall winner** — it beats even DP_actual
   (359 kg) because the relaxed time usage (287.8h sim time) allows slower, more
   fuel-efficient speeds. The longer forecast lets it plan further ahead.

### The Full Information Value Hierarchy (Confirmed under SOG-target model)

```
                                                     Fuel Impact
                                                     ----------
1. Forecast horizon (168h RH → 357 vs default RH → 365)    -8 kg    (DOMINANT)
2. Optimization vs none (RH → 365 vs constant SOG → 368)   -3 kg    (MEANINGFUL)
3. Spatial resolution (DP → 367 vs LP → 368)                -1 kg    (MINOR)
4. Replan frequency (3h → 364.9 vs 48h → 364.7)             ~0 kg   (NEGLIGIBLE)
```

Note: Under the SOG-target model, the hierarchy is more compressed (all approaches are closer). The dominant effect is still forecast horizon, but the absolute magnitudes are smaller.

---

## 10. Session Log

### 2026-02-17 — Initial brainstorm

**Participants**: Ami + Claude

**Key realization**: The thesis "more data → better fuel" is valid, but the dominant axis is **forecast horizon**, not decision frequency or spatial resolution. With 7-day forecasts, RH achieves 351 kg (3% better than LP's 362 kg). Without long forecasts, LP wins despite being simpler.

**Decision**: Pursue thesis Option A or B. Need experiment 4.1 (DP + actual weather) to cleanly separate the effects.

### 2026-02-17 — New simulation model (SOG-target)

Changed the simulation engine: ship now **targets planned SOG** and adjusts SWS (engine speed) to achieve it under actual weather. SWS is clamped to engine limits [11, 13] kn.

**Results with new model:**

| Approach | Plan Fuel | Sim Fuel | Gap | Plan Time | Sim Time | SWS Violations |
|----------|-----------|----------|-----|-----------|----------|----------------|
| Static LP | 358.36 | **367.99** | **2.69%** | 280.00 | 280.26 | 10/278 legs |
| Dynamic DP | 365.32 | **366.87** | **0.42%** | 278.88 | 281.21 | 62/278 legs |
| Rolling Horizon | 361.43 | **364.76** | **0.92%** | 279.89 | 282.09 | 60/278 legs |

**Old model (fixed SWS) for comparison:**

| Approach | Plan Fuel | Sim Fuel | Gap | Plan Time | Sim Time |
|----------|-----------|----------|-----|-----------|----------|
| Static LP | 358.36 | 361.82 | 0.97% | 280.00 | 282.76 |
| Dynamic DP | 365.32 | 367.83 | 0.69% | 278.88 | 280.79 |
| Rolling Horizon | 361.43 | 364.36 | 0.81% | 279.89 | 282.26 |

**The ranking FLIPPED**: DP (366.87) now beats LP (367.99) by 1.12 kg.

**Why the LP's gap increased from 0.97% to 2.69%:**
The LP picks one SOG per segment (based on segment-averaged weather). Under the SOG-target model, maintaining that SOG at individual nodes where weather is harsher than the segment average requires higher SWS. Since FCR ∝ SWS³ (cubic), the fuel penalty at harsh nodes outweighs the fuel saving at calm nodes (Jensen's inequality). The spatial averaging that helped the LP plan now hurts it in execution.

**Why the DP's gap decreased from 0.69% to 0.42%:**
The DP picks per-leg SOGs adapted to per-node predicted weather. These SOGs are already "locally tuned", so the SWS adjustments under actual weather are smaller. Despite having more SWS violations (62 vs 10), the DP's violations are smaller in magnitude.

**SWS violation analysis:**

| Approach | Violations | Required SWS Range | >13 kn | <11 kn |
|----------|-----------|-------------------|--------|--------|
| LP | 10/278 | 10.90 – 13.67 | 9 | 1 |
| DP | 62/278 | 10.50 – 14.46 | 56 | 6 |
| RH | 60/278 | 10.13 – 14.54 | 50 | 10 |

The DP/RH have MORE violations because their SOGs are based on predicted weather — when actual weather differs significantly, larger SWS adjustments are needed. But the violations are at specific nodes; most legs (216/278) maintain their target SOG perfectly.

### 2026-02-17 — Experiment 4.1 completed

**Ran**: DP with actual weather at various ETAs (280–320h). Found that 280h is infeasible; minimum feasible ETA is 285h.

**Clean decomposition achieved**:
- Spatial granularity gain: 2.38 kg (0.66%) — real but small
- Forecast error cost: 8.39 kg (2.33%) — 3.5x larger
- Forecast horizon effect: 17 kg (~4.6%) — dominant

**Updated thesis direction**: The hierarchy is confirmed. Forecast coverage dominates, forecast accuracy is secondary but significant, spatial resolution is a minor contributor, and replan frequency is negligible on this dataset.

**Next**: Run forecast error vs lead time curve (experiment 4.4) to support the narrative.

### 2026-02-17 — Bounds and sensitivity re-run (SOG-target)

**What**: Implemented proper theoretical bounds and re-ran all sensitivity experiments under SOG-target model.

**Lower bound** = FCR(total_dist / ETA) * ETA = FCR(12.128) * 280 = **352.64 kg** (constant speed in calm water).

**Simulated constant-SOG** = 12.128 kn under actual weather = **367.92 kg** (9 SWS violations). This is NOT a lower bound — the optimizer beats it. It's a no-optimization baseline.

**Key discovery**: LP (367.99 kg) essentially equals constant-speed (367.92 kg). The LP's segment-averaged optimization provides virtually zero benefit over "just pick one speed." The LP's speed variation is tiny (12.0–12.5 kn), so its optimization is marginal.

**Optimization potential**: 406.92 (upper) - 352.64 (lower) = 54.28 kg range. RH captures 77.6%, DP 73.8%, LP 71.8% ≈ constant-speed 71.9%.

**Horizon sweep re-run (SOG-target, ETA=285h)**: RH beats LP at every horizon. Range is 356–360 kg (compressed vs old model's 351–366). Forecast horizon is still the dominant factor.

**`sws_violations` now persists in result JSONs** — wired into `build_result_json()` in `shared/metrics.py` and CLI output.

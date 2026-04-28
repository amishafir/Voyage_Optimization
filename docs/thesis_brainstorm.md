# Thesis Brainstorm: Maritime Speed Optimization Under Operational Realism

---

## 1. Central Claim

> Under operationally realistic SOG-targeting, segment-averaged LP optimization is equivalent to no optimization at all. Only per-node dynamic approaches (DP, Rolling Horizon) provide genuine fuel savings. The value of dynamic optimization depends primarily on forecast accuracy relative to voyage duration.

**Six contributions:**
1. **Simulation model matters** — SOG-target vs fixed-SWS reverses the LP/DP ranking (Jensen's inequality on cubic FCR)
2. **RH with actual weather ≈ optimal bound** — RH (176.40 mt) within 0.1% of theoretical optimal (176.23 mt, DP with perfect foresight); LP and DP are 2.5–3.4% above optimal
3. **Forecast horizon is route-length dependent** — dominant on long routes (280h), negligible on short routes (140h)
4. **Information value hierarchy** — temporal > spatial > re-planning, confirmed by 2x2 factorial
5. **Forecast error curve** — wind RMSE doubles over 133h with systematic overpredict bias, completing the causal chain
6. **NWP cycle alignment** — 6h replan frequency matches GFS model refresh; sub-6h replanning provides no new information (empirically confirmed: 86% of hourly API calls return identical data)

---

## 2. Simulation Credibility

| Dataset | Voyage Duration | Actual Weather Samples | Simulation Quality |
|---------|:-:|:-:|--|
| `voyage_weather.h5` (full route) | ~280h | **12h** | **Weak** — ship at hour 200 tested against hour 0 weather |
| `experiment_b_138wp.h5` (short route) | ~140h | **134h** | **Strong** — real weather at nearly every hour |

Full-route results show larger algorithm separations (3.2 kg RH advantage) but rely on frozen weather for a 280h voyage. The spatial variation across 279 nodes is real; the temporal realism is not. These results are **indicative but not fully trustworthy**.

Short-route results (exp_b) have near-complete temporal coverage and are the **credible primary evidence**. However, differences are small on this calm route (1.6 kg total range).

The forecast error curve and 2x2 decomposition are **fully credible** — they compare predicted vs actual observations directly, with no simulation assumptions.

---

## 3. Results

### Theoretical Bounds — Short Route (exp_b)

| Bound | Fuel (mt) | Method | Time |
|-------|:---------:|--------|:----:|
| **Upper** | **203.91** | SWS = 13 kn (max engine) at every node, SOG varies with weather | 131.5h (8.5h early) |
| **Optimal** | **176.23** | DP with time-varying actual weather (perfect foresight), 0 violations | 139.5h |
| **Span** | **27.68** | The total optimization opportunity on this route | |

### Credible Results — Short Route (exp_b, 138 nodes, ~140h)

| | B-LP | B-DP | B-RH (old) | **B-RH (new)** |
|--|:--:|:--:|:--:|:--:|
| **Planned fuel** | 175.96 mt | 177.63 mt | 174.21 mt | **175.52 mt** |
| **Actual fuel (simulated)** | 180.63 mt | 182.22 mt | 180.84 mt | **176.40 mt** |
| **Gap (plan→actual)** | +4.67 (+2.7%) | +4.59 (+2.6%) | +6.63 (+3.8%) | **+0.88 (+0.5%)** |
| **SWS violations** | 4/137 (2.9%) | 17/137 (12.4%) | 10/137 (7.3%) | **1/137 (0.7%)** |
| **Avg SOG (kn)** | 11.98 | 12.03 | — | **12.01** |
| **vs optimal bound** | +4.40 (+2.5%) | +5.99 (+3.4%) | +4.61 (+2.6%) | **+0.17 (+0.1%)** |

**B-RH (old)** = actual weather injected for first leg only at each decision point.
**B-RH (new)** = actual weather injected for ALL nodes within the committed 6h window + time-varying simulation.

RH (new) achieves 176.40 mt — within 0.1% of the theoretical optimal (176.23 mt). It captures **99.4%** of the optimization span. On this calm route (wind std 6.07 km/h), the new RH clearly separates from LP and DP for the first time.

### Plan vs Simulation: Two-Phase Evaluation Framework

Every approach is evaluated in two phases: **planning** (choose speeds) then **simulation** (test them under actual weather). The plan-vs-sim gap and SWS violations reveal how well each optimizer's assumptions hold in reality.

**Phase 1 — Planning: each optimizer sees different weather**

| Approach | Weather Used for Planning | Resolution | Temporal Info |
|----------|--------------------------|------------|---------------|
| LP | **Actual** weather at hour 0 | 6 segment averages (~23 nodes each) | Single snapshot |
| DP | **Predicted** weather from forecast origin 0 | Per-node (~138 nodes) | Time-varying forecast |
| RH | **Predicted** + **actual** at each 6h decision point | Per-node (~138 nodes) | Fresh forecast every 6h; actual weather injected for committed 6h window |

- LP plans with **actual** (observed) weather — but segment-averaged. It sees the real conditions, just spatially smoothed.
- DP plans with **predicted** (forecast) weather from hour 0 — full spatial resolution, but the forecast degrades with lead time (wind RMSE doubles over 133h, see Section 6).
- RH plans with **predicted** weather that it refreshes every 6h, and replaces the committed window's forecast with **actual** observations. This means every committed speed is planned against ground-truth weather for the nodes it actually covers.

All three optimizers produce valid schedules with SWS within [11, 13] kn — **zero violations at planning time**.

**Phase 2 — Simulation: all tested against actual weather**

The simulation is the "real world": it takes the planned SOG schedule and determines what SWS the engine must set at each of the ~137 legs to maintain that SOG under **actual** weather.

| Approach | Simulation Weather | Mode |
|----------|--------------------|------|
| LP | Actual at hour 0 | Static (`sample_hour=0`) |
| DP | Actual at hour 0 | Static (`sample_hour=0`) |
| RH | Actual at each leg's transit time | Time-varying (`time_varying=True`) |

- LP and DP are simulated against a **frozen** actual-weather snapshot (hour 0). This is a simplification, but both plan and simulate against the same temporal reference.
- RH is simulated with **time-varying** actual weather — the simulator picks the closest available sample hour to each leg's cumulative transit time. This matches RH's planning assumption: it planned each committed window using actual weather at that decision time.

**Why LP and DP use static simulation:** Both plan against a single temporal reference (hour 0). Simulating them against time-varying weather would penalize them for temporal drift they never planned for. Static simulation isolates the effect of each optimizer's *spatial* and *forecast-error* assumptions.

**Why RH uses time-varying simulation:** RH explicitly plans each 6h window with the weather at that decision time. Simulating against static hour-0 weather would unfairly penalize RH for *matching* the right temporal conditions.

**How violations arise**

```
Plan:  optimizer picks SOG for segment/leg → implies SWS under planning weather
Sim:   simulator targets that SOG → computes required SWS under actual weather
       If required SWS ∉ [11, 13] kn → clamped → violation
```

| | Sim Fuel | Violations | Gap | Mechanism |
|--|:-:|:-:|:-:|--|
| *Average bound* (170.06 mt) | 170.06 | **0** | — | Constant SWS = SOG = 11.98 kn (total distance / ETA) in calm water. No weather effects, so SWS = SOG throughout — zero violations by construction. By Jensen's inequality on the convex cubic FCR, any speed variation above or below this constant increases total fuel. *Theoretical floor in ideal conditions.* |
| **RH** (176.40 mt) | 176.40 | **1** | +0.50% | Plans each 6h window with actual weather → committed speeds match reality. Only 1 violation: a boundary effect at the last decision point where remaining ETA margin was < 0.1h, forcing the optimizer to use forecast weather for the final legs. *Actual weather injection nearly eliminates the plan-sim gap.* |
| *Optimal bound* (176.23 mt) | 176.23 | **0** | 0% | DP with time-varying actual weather (perfect foresight). Per-node resolution + ground-truth weather at every hour = zero plan-sim mismatch. *Best achievable under real weather.* |
| **LP** (180.63 mt) | 180.63 | **4** | +2.65% | Plans with segment-averaged weather. Individual nodes within a segment have worse conditions than the average → require SWS > 13 kn to hit the planned SOG. *Averaging hides within-segment extremes.* |
| **DP** (182.22 mt) | 182.22 | **17** | +2.58% | Plans with predicted weather; simulated against actual. Forecast errors accumulate over the voyage (wind bias overpredicts by ~1-3 km/h). The optimizer plans for headwinds that don't materialize → SWS is systematically off. *Forecast error is the dominant violation source.* |

**The two bounds frame the problem:**
- **Average bound** (170.06 mt): the minimum fuel if the ship sailed at constant speed in calm water. Weather effects and speed variation can only increase fuel above this floor. Zero violations because SWS = 11.98 kn stays within [11, 13].
- **Optimal bound** (176.23 mt): the minimum fuel achievable under actual weather with perfect foresight and per-node resolution. The gap from average to optimal (176.23 − 170.06 = **6.17 mt**) is the unavoidable *weather tax* — the cost of operating in non-uniform conditions, even with a perfect optimizer.

All three approaches pay the weather tax plus an additional *information penalty*: LP +4.40 mt above optimal (segment averaging), DP +5.99 mt (forecast error), RH +0.17 mt (near-zero — actual weather injection eliminates most of the penalty).

**Why RH has the lowest fuel despite planning with actual weather being "easy":**
RH's advantage is not that it sees perfect weather (LP also plans with actual weather). The advantage is threefold:
1. **Per-node resolution** — no segment averaging, so no Jensen's inequality penalty from cubic FCR
2. **Temporal freshness** — weather is observed at the time the ship is actually there, not extrapolated from hour 0
3. **Re-planning** — if conditions change between decision points, the next solve adapts

LP has (1) negated by averaging, (2) only at hour 0, and (3) none.
DP has (1) but not (2) or (3) — it uses a single forecast that degrades over time.

**Plan-sim gap interpretation:**
- LP: +4.67 mt (+2.65%) — segment averaging creates a systematic gap. The LP "thinks" its plan is efficient, but individual nodes pay more than the average predicted.
- DP: +4.59 mt (+2.58%) — forecast error creates a comparable gap. The plan optimizes for predicted conditions that don't match reality.
- RH: +0.88 mt (+0.50%) — near-zero gap. Plans with actual weather → simulation confirms the plan.

### Full-Route Results (indicative, weak simulation)

| Approach | Plan Fuel | Sim Fuel | Gap | SWS Violations |
|----------|:---------:|:--------:|:---:|:--------------:|
| **Rolling Horizon** | 361.4 kg | **364.8 kg** | 0.92% | 60/278 (22%) |
| **Dynamic DP** | 365.3 kg | **366.9 kg** | 0.42% | 62/278 (22%) |
| **Static LP** | 358.4 kg | **368.0 kg** | 2.69% | 10/278 (4%) |
| Constant SOG | — | **367.9 kg** | — | 9/278 (3%) |

Larger separations here (LP = constant speed, RH saves 3.2 kg), but temporal realism is weak.

### The Ranking Reversal (observed on both routes)

| Approach | Fixed-SWS (old) | SOG-Target (new) |
|----------|:---------------:|:----------------:|
| LP | **361.8 kg (best)** | 368.0 kg (worst) |
| DP | 367.8 kg (worst) | **366.9 kg (best)** |
| RH | 364.4 kg | 364.8 kg |

**Mechanism:** LP picks one SOG per segment from averaged weather. Under SOG-targeting, maintaining that SOG at individual nodes where weather differs from the average requires SWS adjustments. Cubic FCR (0.000706 × SWS³) means harsh-node penalties always outweigh calm-node savings (Jensen's inequality).

---

## 4. Factor Decomposition

### Full Route (indicative — weak simulation)

| Factor | How Measured | Impact |
|--------|-------------|:------:|
| Weather source (actual vs predicted) | LP_actual vs LP_predicted | **0 kg** |
| Segment averaging (12 seg vs 278 legs) | DP_actual vs LP_actual | **-2.4 kg** |
| Forecast error (predicted vs actual) | DP_predicted vs DP_actual | **+8.4 kg** |
| Re-planning (DP vs RH) | RH vs DP, same config | **-2.1 kg** |
| Forecast horizon (default vs 168h) | Horizon sweep at ETA=285h | **-8 kg** |
| Replan frequency (3h vs 48h) | Replan sweep | **~0 kg** |

### 2x2 Factorial (credible — short route, exp_a/b)

| Config | Nodes | Weather | Approach | Fuel (kg) |
|--------|:-----:|---------|----------|:---------:|
| A-LP | 7 | actual | LP (6 seg) | **178.19** |
| A-DP | 7 | predicted | DP | **181.20** |
| B-LP | 138 | actual | LP (6 seg) | **180.63** |
| B-DP | 138 | predicted | DP | **182.22** |
| B-RH | 138 | predicted | RH | **180.89** |

```
Temporal effect (forecast error):    +3.02 kg  ← largest
Spatial effect (segment averaging):  +2.44 kg
Interaction (spatial mitigates):     -1.43 kg
RH benefit (re-planning):           -1.33 kg  ← consistent
```

The negative interaction means finer spatial resolution partially compensates for forecast error — per-node predicted weather is closer to per-node actual weather than segment averages are.

---

## 5. Sensitivity Analyses

### Horizon Sweep — Full Route (indicative, ETA=285h)

| Horizon | DP Fuel | RH Fuel | RH Violations |
|---------|:-------:|:-------:|:-------------:|
| 72h | 359.6 | 357.2 | 10 |
| 96h | 360.7 | 358.1 | 23 |
| 120h | 360.4 | 358.1 | 18 |
| 144h | 359.1 | 357.3 | 42 |
| 168h | 359.1 | 356.6 | 47 |

**Plateau from 72h onward** (~1.5 kg range). 72h (26% of voyage) captures nearly all benefit. Violations increase with horizon — more information enables more aggressive plans.

### Horizon Sweep — Short Route (credible, exp_b, ~140h voyage)

| Horizon | Ratio | DP Fuel | RH Fuel |
|---------|:-----:|:-------:|:-------:|
| 24h | 17% | 177.70 | 176.46 |
| 48h | 34% | 177.72 | 176.41 |
| 72h | 51% | 177.70 | 176.47 |
| 144h | 103% | 177.78 | 176.54 |

**Completely flat** — DP range 0.08 kg, RH range 0.19 kg. Even a 24h forecast (17% of voyage) is sufficient. The short route fits entirely within the accurate forecast window.

**Critical insight:** The relevant variable is not absolute horizon length but `voyage_duration / forecast_accuracy_horizon`. If the voyage fits within the accurate forecast window (~72-96h for wind), any horizon suffices. If it extends beyond, longer horizons help up to the accuracy limit.

### Replan Frequency — Short Route (credible, exp_b)

| Frequency | Sim Fuel (mt) | Delta vs 1h | Decision Points | New Info Rate |
|:-:|:-:|:-:|:-:|:-:|
| 1h | 180.63 | baseline | 73 | 53% |
| 2h | 180.70 | +0.07 (+0.04%) | 50 | 70% |
| 3h | 180.73 | +0.11 (+0.06%) | 37 | 76% |
| **6h** | **180.84** | **+0.21 (+0.12%)** | **21** | **100%** |
| 12h | 180.69 | +0.06 (+0.04%) | 12 | 100% |
| 24h | 181.22 | +0.59 (+0.33%) | 6 | 100% |

**Key finding:** 1h vs 6h fuel difference is only 0.21 mt (0.12%) — negligible. At 1h frequency, only 53% of decision points receive genuinely different forecasts. At 6h, every decision point gets new data. **6h is the sweet spot** — it matches the GFS model refresh cycle (see NWP analysis below).

### Replan Frequency (indicative, full route)

| Freq | Fuel (mt) | Delta |
|------|:---------:|:-----:|
| 3h | 364.85 | — |
| 6h | 364.76 | -0.09 |
| 24h | 364.50 | -0.35 |
| 48h | 364.72 | -0.13 |

Range <0.35 mt — negligible. Consistent with exp_b: replan frequency has minimal impact on fuel.

---

## 6. Forecast Error Curve (credible — ground truth, 0-133h)

From exp_b (138 nodes × 134 samples):

| Lead Time | Wind RMSE (km/h) | Wind Bias | Wave RMSE (m) | Current RMSE (km/h) |
|:---------:|:----------------:|:---------:|:-------------:|:-------------------:|
| 0h | 4.13 | +0.20 | 0.052 | 0.358 |
| 24h | 4.84 | +0.59 | 0.072 | 0.382 |
| 48h | 5.63 | +1.21 | 0.076 | 0.406 |
| 72h | 6.13 | +1.31 | 0.094 | 0.448 |
| 96h | 7.65 | +2.86 | 0.114 | 0.460 |
| 120h | 8.34 | +3.15 | 0.118 | 0.443 |
| 133h | 8.40 | +2.67 | 0.113 | 0.503 |

**Wind RMSE doubles** (+103%). Error accelerates after 72h (atmospheric predictability limit). Systematic positive bias means forecasts overpredict wind → DP/RH prepare for headwinds that don't materialize → overspeed SWS violations.

This directly explains: (1) the horizon plateau at 72h, (2) the route-length dependence, (3) the SWS violation pattern.

---

## 6b. NWP Model Cycle Analysis (credible — empirical verification)

Analyzed predicted weather from exp_b (3.1M rows) to determine exactly when the API returns new data. Cross-referenced with Open-Meteo documentation.

### Model refresh rates

| Parameter | NWP Model | Documented Cycle | Empirical (our data) |
|-----------|-----------|:-:|:-:|
| Wind speed/direction | GFS | **6h** (00/06/12/18z) | 6h median, 86% unchanged hourly |
| Wave height | MFWAM (Meteo-France) | **12h** (2x/day) | 12h median, 94% unchanged hourly |
| Ocean current vel/dir | SMOC (Meteo-France) | **24h** (1x/day) | 24h median, 97% unchanged hourly |

### Propagation delay

GFS initializes at 00/06/12/18 UTC. Open-Meteo processes and serves the data with a ~5h delay:

```
GFS cycle:     00z       06z       12z       18z
                 ↓         ↓         ↓         ↓  (~5h processing delay)
Data arrives:  05 UTC    11 UTC    17 UTC    23 UTC
```

Verified empirically: 9 out of 10 update events in our data landed at `hour % 6 == 5`. At each update, ~98–100% of all 138 nodes change simultaneously (global model refresh, not per-location drift).

### SOG sensitivity — hourly deltas are below noise

| Gap | Wind Change Rate | Median Wind Delta | SOG Impact |
|-----|:-:|:-:|:-:|
| 1h | 14% | 0 km/h | 0.001 kn |
| 6h | 84% | 1.17 km/h | 0.03 kn |

Typical 1h wind delta (0.30 km/h) translates to 0.001 kn SOG change — below any operational threshold. Even 6h wind delta only causes 0.03 kn mean SOG impact. Wave and current deltas have effectively zero SOG impact at any gap size.

**Conclusion:** 6h replan frequency is optimal because it aligns with the fastest NWP model cycle (GFS wind). Sub-6h replanning wastes computation on identical data. This explains why the replan frequency sweep shows negligible fuel difference between 1h and 6h.

---

## 7. SWS Violation Analysis

### Credible — Short Route (exp_b)

During **planning**: zero violations. All algorithms choose SWS within [11, 13] kn.

During **simulation**: violations occur because actual weather differs from what was used for planning.

| | Violations | Needed SWS range | Cause |
|--|:--:|:--:|--|
| LP | 4/137 (2.9%) | up to 13.21 kn | Segment average hides per-node extremes |
| DP | 17/137 (12.4%) | 10.6 – 13.99 kn | Predicted weather ≠ actual weather |
| RH (old, first leg only) | 10/137 (7.3%) | 10.9 – 13.29 kn | Fewer than DP — fresher forecasts help |
| **RH (new, full 6h window)** | **1/137 (0.7%)** | **13.08 kn** | **Near-zero — plans with actual weather for committed legs** |

**Progression of RH violation reduction:**
- DP baseline: 17 violations (plans with single stale forecast)
- RH with forecast only: 12 violations (fresher forecasts at each decision point)
- RH + actual weather at first leg: 10 violations (current node uses ground truth)
- **RH + actual weather for full 6h window: 1 violation** (all committed legs use ground truth)

The single remaining violation (node 132, SWS=13.079) occurs at the last decision point where the optimizer fell back to forecast weather because the ETA margin was < 0.1h. This is a boundary effect, not a systematic limitation.

DP has the most violations: it plans on a single forecast from hour 0, which grows stale. LP has the fewest among forecast-based approaches because segment averaging smooths extremes (but this also means LP can't exploit per-node variation).

### Indicative — Full Route (weak simulation)

| Approach | Violations | Rate | Max Severity | Soft (<0.5 kn) | Very Hard (≥1.0 kn) |
|----------|:---------:|:----:|:------------:|:--------------:|:--------------------:|
| LP | 10 | 3.6% | 0.67 kn | 80% | 0% |
| DP | 62 | 22.3% | 1.46 kn | 50% | 6% |
| RH | 60 | 21.6% | 1.54 kn | 52% | 18% |

Violations cluster in segments 7-8 (Indian Ocean, ~2000-2500 nm) — 84-88% rate for DP/RH vs 16% for LP. Geographic pattern confirms weather-driven mechanism, not algorithmic failure.

**Fuel-feasibility tradeoff:** LP is safe but provides no fuel benefit. DP/RH save fuel but 22% of legs exceed engine limits (mostly soft violations).

---

## 8. Generalizability (two routes, two weather regimes)

| Finding | Full Route (3,394 nm, windier) | Short Route (1,678 nm, calmer) |
|---------|:--:|:--:|
| RH > DP > LP | Yes (indicative) | Yes (credible) |
| LP ≈ constant speed | Yes (indicative) | Yes (credible) |
| Replan negligible | Yes (indicative) | Yes (credible) |
| Horizon matters | Yes, plateau at 72h (indicative) | No, flat from 24h (credible) |

Weather comparison: wind std 10.63 vs 6.07 km/h, wave std 0.50 vs 0.26 m. Despite different conditions, the hierarchy holds. Horizon effect is the only route-dependent finding.

**Caveat:** Full-route column is indicative (12h actual for 280h voyage). The hierarchy is consistent across routes, but confidence levels differ. Re-collection of full-route data (280+ hours) would make both columns credible.

### New Routes in Collection (Feb 2026)

Two harsh-weather routes are collecting data on the TAU server, designed to test RH under extreme conditions and decompose the RH advantage:

| | Exp D (St. John's → Liverpool) | Exp C (Yokohama → Long Beach) |
|---|---|---|
| Ocean | North Atlantic storm track | North Pacific Great Circle |
| Distance | 1,955 nm (~7 days) | 4,782 nm (~17 days) |
| Conditions | BN 8–10, waves 4–6m | BN 8–10, Aleutian storm track |
| Nodes | 389 (5nm spacing) | 947 (5nm spacing) |
| DD forecast coverage | Full voyage (168h covers 163h) | First 7 of 17 days only |
| RH advantage source | **Freshness effect** only | Freshness **+ horizon effect** |
| Thesis value | Isolates pure forecast freshness advantage | Shows combined effect + DD blind for 58% |
| Collection started | Feb 25 | Feb 24 |
| Full data ready | **~Mar 4** | ~Mar 11 |

**Why two routes:** Exp D fits within the 168h forecast horizon, so any RH advantage comes purely from using fresher forecasts. Exp C extends well beyond the horizon, so DD falls back to persistence for the latter 58% of the voyage — RH should show a much larger advantage. Together they decompose the RH advantage into its freshness and horizon components.

---

## 9. Thesis Structure

### Proposed Arc

1. **Lead with simulation model insight** — SOG-target vs fixed-SWS flips everything. Novel methodological contribution.
2. **Present 2x2 decomposition** (credible, from exp_a/b) as primary quantitative evidence.
3. **Present forecast error curve** (credible ground truth, no simulation needed) — completes causal chain.
4. **Layer in forecast horizon + route-length dependence** — explains when dynamic optimization matters.
5. **Full-route results as supporting/indicative evidence** (or re-collect to make credible).
6. **Organize as information value hierarchy** — actionable framework for practitioners.

### Title Ideas

- "Speed Over Ground Targeting Reveals the True Value of Dynamic Voyage Optimization"
- "Why Simulation Models Matter: Jensen's Inequality and the Hidden Cost of Spatial Averaging"
- "The Information Value Hierarchy in Maritime Voyage Planning"

---

## 10. Assumptions & Validation

| # | Assumption | Status | Evidence |
|---|-----------|:------:|----------|
| A1 | Forecast accuracy degrades with lead time | **Confirmed** | Wind RMSE 4.1→8.4 km/h over 0-133h |
| A2 | LP uses actual weather = perfect information | By construction | — |
| A3 | DP with actual weather ≈ LP | **Confirmed** | DP_actual 359.44 vs LP 361.82 (DP wins 0.66%) |
| A4 | Weather is "stable" on both routes | **Confirmed** | Wind std 6.07 (new) vs 10.63 (old); replan negligible |
| A5 | 168h horizon covers enough of voyage | **Route-dependent** | Full: plateau at 72h. Short: 24h is enough |
| A6 | Results generalize across routes | **Partially confirmed** | RH>DP holds on both; horizon effect is route-dependent |
| A7 | FCR cubic relationship is accurate | Assumed | From research paper; sensitivity analysis TODO |
| A8 | 279 waypoints is sufficient resolution | Partially tested | 138 vs 7 in 2x2; full 3,388 untested |
| A9 | SOG-targeting is standard practice | **Assumed** | Need IMO/EEXI citations |
| A10 | Jensen's inequality on cubic FCR causes LP penalty | **Confirmed** | LP gap 2.69%; spatial effect +2.44 kg in 2x2 |
| A11 | SWS violations are operationally meaningful | **Supported** | Consistent across routes; fewer on calmer route |

---

## 11. Action Items

| # | Action | Status |
|---|--------|:------:|
| 1 | DP with actual weather + normal ETA | **Done** |
| 2 | SOG-target simulation model | **Done** |
| 3 | Horizon sweep under SOG model | **Done** |
| 4 | Forecast error curve (0-133h) | **Done** |
| 5 | Intermediate horizons (96h, 144h) | **Done** |
| 6 | SWS violation analysis | **Done** |
| 7 | LP with predicted weather | **Done** |
| 8 | exp_a/exp_b generalizability | **Done** |
| 9 | 2x2 decomposition | **Done** |
| **10** | **IMO/EEXI literature — validate SOG-targeting** | **TODO** (small) |
| **11** | **Full-route re-collection (280+ hours actual weather)** | Superseded by exp C/D |
| **12** | **Multi-season weather robustness** | **TODO** (large) |
| 13 | RH re-planning every hour (not 6h) | **Done** — sweep [1,2,3,6,12,24]h shows 6h optimal (0.12% diff vs 1h) |
| 14 | Open-Meteo API update cycle deep dive | **Done** — GFS 6h, MFWAM 12h, SMOC 24h; 86% hourly calls redundant |
| 15 | RH actual weather at decision points | **Done** — extended to full 6h window: violations 10→1, gap 3.8%→0.5% |
| 16 | Collect data on longer, harsher route (5+ days) | **Done** — exp C (Yokohama→LB, 17d) + exp D (St. John's→Liverpool, 7d) running |
| **17** | **Run exp D analysis when data ready (~Mar 4)** | **TODO** |
| **18** | **Run exp C partial analysis (~Mar 6)** | **TODO** |

---

## 12. Open Questions

### Resolved

1. ~~Horizon linear or knee?~~ → **Plateau** from 72h onward (~1.5 kg range)
2. ~~Does extended data change replan finding?~~ → **No.** RH-DP gap stable at ~1.3 kg
3. ~~Optimal horizon/voyage ratio?~~ → **Wrong framing.** Critical variable: `voyage_duration / forecast_accuracy_horizon`
4. ~~Can we decompose DP advantage?~~ → **Yes.** Temporal +3.02 > Spatial +2.44, interaction -1.43
5. ~~Should we add LP with predicted weather?~~ → **Yes.** Proves LP ≈ constant-speed
6. ~~Horizon sweep under SOG model?~~ → **Yes.** RH wins at every horizon
7. ~~SWS violation distribution?~~ → **80% soft for LP; 50/50 for DP/RH; clusters in segments 7-8**

8. ~~Does hourly RH re-planning improve results, or is 6h optimal?~~ → **6h is optimal.** Replan sweep [1,2,3,6,12,24]h shows 0.12% fuel diff between 1h and 6h. At 1h, only 53% of decision points get new data; at 6h, 100% do.
9. ~~What is the Open-Meteo weather model update frequency for this region?~~ → **GFS 6h (wind), MFWAM 12h (waves), SMOC 24h (currents).** Verified from documentation and confirmed empirically: 86% of hourly API calls return identical wind data, 94% waves, 97% currents.
10. ~~Can RH eliminate violations by using actual weather at decision points?~~ → **Nearly.** Injecting actual weather for the full 6h committed window reduced violations from 10→1. The single remaining violation is a boundary effect at the last decision point (ETA margin < 0.1h).

### Still Open

1. **Is there a forecast quality threshold below which LP dominates?** (synthetic noise experiment)
2. **Is the route-length finding robust with 3-4 more routes?** (establishes breakeven curve — exp C/D will help)
3. **How does the hierarchy shift in extreme weather?** (exp C/D North Pacific + North Atlantic will test this)
4. **Is SOG-targeting truly standard practice?** (IMO/EEXI citation needed)
5. **FCR exponent sensitivity?** (how sensitive are conclusions to ±0.05 on the cubic?)
6. **Does the RH advantage increase on longer voyages beyond forecast horizon?** (exp C will test — 17-day voyage, DD blind for 58%)

---

## 13. Session Log

### 2026-02-17 — Initial brainstorm + simulation model change
- Three-way comparison showed LP wins under fixed-SWS
- Changed to SOG-target simulation → **ranking flipped** (RH > DP > LP)
- Root cause: Jensen's inequality on cubic FCR penalizes segment averaging
- Ran DP with actual weather → spatial granularity gain 2.38 kg (0.66%), forecast error cost 8.39 kg (2.33%)
- Discovered LP ≈ constant speed (367.99 vs 367.92 kg)
- Computed theoretical bounds: 352.6 (lower) to 406.9 kg (upper)

### 2026-02-18 — Forecast error + SWS violations
- Ground-truth RMSE for 0-11h: wind grows +45%, waves flat, current +27%
- SWS violation analysis: LP 10 (mild), DP 62 (50% hard), RH 60 (18% very hard)
- Violations cluster geographically in segments 7-8 (Indian Ocean)

### 2026-02-19 — Horizon curve + LP predicted
- Filled horizon curve (72h-168h): flat plateau, ~1.5 kg range
- LP with predicted weather = LP with actual = constant speed (all within 0.07 kg)

### 2026-02-22 — exp_a/exp_b experiments
- Downloaded exp_a (7 WP, 135 samples) and exp_b (138 WP, 134 samples)
- Full forecast error curve (0-133h): wind RMSE doubles (4.13→8.40), bias grows to +2.7 km/h
- 2x2 decomposition: temporal +3.02 > spatial +2.44, interaction -1.43, RH benefit -1.33
- Short-route horizon sweep: completely flat (0.08 kg DP range across 24h-144h)
- Generalizability confirmed: RH > DP > LP holds on both routes; horizon effect is route-dependent

### 2026-02-23 — Simulation credibility caveat + bounds + meeting prep
- Identified critical limitation: full-route simulation uses 12h actual weather for 280h voyage (frozen hour-0 weather)
- Short-route (exp_b) has 134h actual for ~140h voyage — **credible primary evidence**
- Relabeled all results: full-route = "indicative", short-route = "credible"
- Forecast error curve and 2x2 decomposition are fully credible (no simulation assumptions)
- Computed theoretical bounds for exp_b: upper 203.91 kg (SWS=13), lower 180.59 kg (Lagrangian), span 23.33 kg
- All approaches capture >93% of optimization span (LP 99.9%, RH 98.7%, DP 93.1%)
- Corrected exp_b planned fuel numbers: LP 175.96, DP 177.63, RH 174.20 kg
- Corrected gaps: LP +4.67 (+2.7%), DP +4.59 (+2.6%), RH +6.70 (+3.8%)
- Confirmed: zero SWS violations during planning, violations only during simulation

### 2026-02-23 — Supervisor meeting outcomes
- **RH frequency**: test hourly re-planning (not just 6h) — may reduce violations further
- **API update cycle**: need to understand when Open-Meteo model actually refreshes (GFS every 6h?) — determines minimum useful re-planning interval
- **Actual weather at decision points**: RH should use actual weather for first leg of each re-plan (ship is physically there, no forecast uncertainty)
- **Harsher route needed**: current exp_b is too calm (1.6 kg range) to differentiate algorithms — need 5+ day route with more weather variability

### 2026-02-24 — Replan frequency sweep + NWP cycle analysis
- Ran replan frequency sweep [1,2,3,6,12,24]h on exp_b: **6h is optimal** (0.12% diff vs 1h)
- At 1h frequency, only 53% of decision points receive genuinely different forecasts; at 6h, 100% do
- NWP model cycle analysis: GFS 6h (wind), MFWAM 12h (waves), SMOC 24h (currents)
- Empirical verification: tracked 3.1M predicted_weather rows, confirmed ~5h propagation delay from GFS initialization
- 86% of hourly API calls return identical wind data → hourly collection wastes API calls
- Added `sample_interval_hours` and `nwp_offset_utc` config options for NWP-aligned collection (83% fewer API calls, zero information loss)

### 2026-02-25 — RH actual weather + optimal bound + new routes deployed
- **RH actual weather for full 6h window**: at each decision point, replace forecast with actual observations for ALL nodes within the committed window (not just first leg)
- Added `time_varying=True` simulation mode: picks closest actual-weather snapshot per leg based on cumulative transit time
- Added DP infeasibility fallback: if actual weather makes sub-problem infeasible, retry with forecast only
- **Results**: violations 10→1, plan-sim gap 3.8%→0.5%, sim fuel 180.84→176.40 mt
- **Optimal bound computed**: DP with time-varying actual weather (perfect foresight) = 176.23 mt, 0 violations
- RH (176.40 mt) within **0.1%** of optimal bound — captures 99.4% of optimization span (27.51 of 27.68 mt)
- Upper bound: constant SWS=13 kn = 203.91 mt (avg SOG 12.78 kn)
- **Exp C deployed** (Yokohama → Long Beach, 4,782 nm, ~17 days, 947 nodes) — collection running on TAU server since Feb 24
- **Exp D deployed** (St. John's → Liverpool, 1,955 nm, ~7 days, 389 nodes) — collection running since Feb 25
- Together exp C and D decompose RH advantage into freshness (D, within horizon) and horizon (C, beyond horizon) components

### 2026-03-04 — API quota crisis → bulk collection refactor + 6h deployment

**Problem:** All 6 collection sessions (3 experiments × 2 servers) hit Open-Meteo daily API quota. Per-node collection = 2N calls/sample (N = nodes). exp_c alone: 947 × 2 = 1,894 calls/sample, ~45,456/day with hourly sampling.

**Fix — two stacked optimizations:**
1. **Bulk multi-location API**: single request with comma-separated lat/lon per endpoint. Chunked at 100 locations to avoid 414 URI Too Large. Reduces per-sample calls from O(N) to O(N/100).
2. **6h NWP-aligned sampling**: deployed `sample_interval_hours: 6` + `nwp_offset_utc: 5` to all 6 sessions. Matches GFS refresh cycle — empirically validated: 86% of hourly calls return identical data.

**Combined reduction:**
- exp_c: ~45,456 → ~80 calls/day (99.8% reduction)
- exp_b: ~6,624 → ~16 calls/day
- exp_d: ~18,672 → ~32 calls/day
- All 6 sessions total: ~256 calls/day — well within free tier

**Data status at time of refactor:**
- exp_b (Shlomo1): 161 hours collected (50 MB) — near complete
- exp_c (Shlomo1): 98 hours (146 MB) — gaps from rate limiting
- exp_d (Shlomo1): 81 hours (53 MB) — gaps from rate limiting
- Shlomo2 copies: 31 hours each (started later)

**Thesis relevance:** The NWP cycle analysis (Section 6b) isn't just an academic finding — it directly solved an engineering constraint. The 86% redundancy finding drove the 6h sampling decision, and the bulk API refactor transforms collection from quota-limited to practically unlimited. This is a clean example of how understanding the data source (NWP model cycles) informs both the optimization algorithm (6h replan frequency) and the data collection infrastructure.

### 2026-03-05 — Paper-writing infrastructure + server recovery

**Server reboot recovery:** Both Shlomo1 and Shlomo2 rebooted (cause unknown). All 6 tmux sessions lost. Discovered system Python 3.7 lacks `openmeteo_requests` — switched to `~/miniconda3/bin/python3` for all restarts. All 6 collection processes restored. Data intact: exp_b 166h (complete), exp_d 86h (53%), exp_c 103h (25%).

**Paper infrastructure created — targeting Transportation Research Part C (exp_b + exp_d):**

Directory: `paper/` with `sections/`, `tables/`, `bibliography/`

Core documents:
- `paper/paper_outline.md` — 9-section outline, 8,000–10,000 words, 6 contributions mapped to sections, 11 tables, 5 figures
- `paper/style_guide.md` — TR-C conventions, notation, voice, terminology

Skills (quick-reference, invoked with `/`):
| Skill | Purpose |
|-------|---------|
| `paper-outline` | Section targets, contribution mapping, word counts |
| `paper-style` | Notation, voice, terminology, formatting |
| `paper-results` | All quantitative results (exp_b complete, exp_d placeholder) |
| `paper-equations` | 17 numbered equations with LaTeX |

Agents (autonomous writers/reviewers):
| Agent | Model | Purpose |
|-------|-------|---------|
| `section-writer` | opus | Write/revise a single section |
| `paper-reviewer` | opus | Review with CRITICAL/MAJOR/MINOR severity |
| `table-builder` | sonnet | Generate 11 tables (markdown + LaTeX) |
| `bib-builder` | sonnet | Build references.bib from pillar files |
| `paper-assembler` | sonnet | Concatenate sections, resolve placeholders, word count |

Writing workflow: outline → sections (intro first) → tables → bibliography → review → assembly.

**FIRST TASK FOR TOMORROW (Mar 6):** Start writing the paper — begin with `01_introduction` using the `section-writer` agent. The introduction establishes all 6 gaps and states the numbered contributions, so it anchors the rest of the paper.

### 2026-03-15 — Route 2 (exp_d) analysis complete

**Data download & merge:** Downloaded exp_d HDF5 from Shlomo2 (29 samples, 389 nodes, 23 MB). Shlomo2 was missing predicted hours 6 and 12 — spliced from Edison. Final: 29/29 predicted hours, zero gaps.

**Validation:** 389 nodes, BN 6–8 dominant, wind 46.6±16.8 km/h (2.7× Route 1), waves 5.05±2.10 m (6.2× Route 1). Genuinely harsh North Atlantic winter conditions.

**DP infeasibility fix:** DP returned "Infeasible" with dt=0.1h — cumulative time rounding over 388 legs (5nm spacing) added ~17h. Fixed by reducing `time_granularity` to 0.01h in exp_d config. Root cause: 21 speeds collapse to only 2 distinct arrival time slots per 5nm leg at dt=0.1h.

**Route 2 results:**

| | D-LP | D-DP | D-RH | Optimal | Constant Speed |
|--|--|--|--|--|--|
| Sim fuel (mt) | 215.60 | 214.24 | **217.28** | 216.44 | 216.57 |
| Violations | 64 (16.5%) | **161 (41.5%)** | **15 (3.9%)** | 0 | 73 |
| Arrival dev | +0.4h | **+1.5h late** | **+0.03h** | 0 | 0 |

**Key findings:**
- Weather tax 17.78 mt (2.9× Route 1's 6.17 mt) — scales super-linearly with weather severity
- DP/LP sim fuel falls *below* optimal bound — artefact of SWS clamping (ship arrives late, burns less)
- RH within 0.4% of optimal, only approach arriving on time
- Forecast error: wind RMSE +286% over 144h (vs +103% on Route 1)
- Replan sweep: 0.50 mt range across all frequencies — 6h optimal confirmed
- LP ≈ constant speed confirmed on harsh route too

**Paper updates:** Rewrote §6 with both routes, updated §5.4, §7, §8 with Route 2 findings. All 6 contributions validated (C3 partially — both routes fit within forecast horizon).

### 2026-03-16 — Supervisor meeting → four major decisions

**D1: No SWS violations — relax ETA instead.** Plan limits [11, 13] kn are hard constraints; ETA is soft. If weather requires SWS > 13, use SWS = 13 and accept late arrival. Report arrival deviation instead of violation count. Eliminates the "below optimal bound" artefact on Route 2.

**D2: Test RH with LP.** New approach: RH-LP — re-solve LP at every 6h decision point with fresh weather. If RH-LP ≈ RH-DP, LP is sufficient with re-planning (simpler operational recommendation).

**D3: Realistic upper bound = constant speed.** Replace SWS=13 bound with constant SOG = D/ETA. This is "what a captain does with no optimization tool." Optimization span becomes: constant-speed fuel − optimized fuel.

**D4: Clarify plan vs simulation framework.** Clear matrix of what each optimizer sees during planning and what the simulation tests.

**Implementation (same day):**
- DP optimizer: added soft-ETA fallback (status="ETA_relaxed" when no path within ETA)
- LP optimizer: added soft-ETA fallback (min-SWS plan when infeasible)
- RH-DP: accepts "ETA_relaxed" sub-problems
- Simulation: renamed `sws_violations` → `sws_adjustments` (backward compat kept)
- **New file: `dynamic_rh/optimize_lp.py`** — RH-LP optimizer. Same RH loop as RH-DP but calls LP at each decision point. Groups remaining legs by segment, averages weather, solves LP, maps segment SOG back to legs.
- Constant-speed baseline added to runner via existing `sensitivity.run_constant_speed_bound()`

**Route 2 results with all 5 approaches:**

| Approach | Fuel (mt) | Arrival Dev | SWS Adj |
|----------|----------|------------|---------|
| Constant Speed | 216.57 | +0.00h | 73 |
| LP | 215.60 | +0.43h | 64 |
| DP | 214.24 | +1.53h late | 161 |
| **RH-DP** | **217.28** | **+0.03h** | **15** |
| RH-LP | 215.56 | +0.43h | 51 |

**Interpretation:**
- LP ≈ constant speed (215.60 vs 216.57 mt) — optimization adds nothing with segment averaging
- RH-LP (215.56 mt) slightly better than static LP — re-planning helps but doesn't fix averaging
- RH-DP is the only approach with near-zero arrival deviation AND low SWS adjustments
- DP is operationally infeasible: 161 adjustments, 1.5h late

### 2026-03-17 — API outage recovery + collector fixes

**Problem:** exp_b wind endpoint (`/v1/forecast`) timing out on both servers since ~Mar 16 05:00 UTC. 30+ hours of consecutive failures. exp_d marine endpoint unaffected.

**Root cause:** The old retry logic only retried on rate limits, not timeouts. Also, 60s inter-experiment delay was insufficient.

**Fixes deployed to both servers:**
1. **Retry on timeouts/504s/503s** — 5 retries with 2/4/6/8 min backoff (was: give up after first timeout)
2. **5-minute gap between experiments** — `INTER_EXPERIMENT_DELAY` 60s → 300s (prevents API throttling)

**Result:** Both exp_b and exp_d succeeded immediately on both servers after deploying the fix. exp_b recovered from ~30h outage. Shlomo2: 37 samples, Edison: 35 samples.

**Gap-free Route 1 data:** The API outage created a permanent gap at hours 174–198 (both servers failed simultaneously). A new gap-free window starting from hour 222 will be ready by ~Mar 23 (need 24 consecutive 6h samples). The old Shlomo1 data (171 hourly samples, hours 0–225) remains the best Route 1 dataset.

### 2026-03-17 — Experiment framework redesign

**Major reframing** of the experimental setup. See `docs/experiment_framework.md` for full document.

**Core idea:** Every experiment has two phases — **planning** (optimizer creates speed policy from forecast) and **realization** (ship executes policy under actual weather). Two possible flows during realization:
- **Flow 1**: Ship achieves planned SOG → on schedule, fuel may differ
- **Flow 2**: Weather too harsh for planned SOG at max SWS → ship falls behind → decision needed

**3 environment settings × 2 model types = 6 combinations:**

| | No compute (A) | Compute, stale forecast (B) | Compute, fresh forecast (C) |
|--|--|--|--|
| **LP** | Follow initial plan; sail max SWS if SOG unachievable, continue after segment | Re-solve LP from current position with original forecast | Re-solve LP from current position with fresh forecast |
| **DP** | Follow initial plan; sail max SWS if SOG unachievable, continue after | Re-solve DP from current position with original forecast | Re-solve DP from current position with fresh forecast |

**Fuel boundaries redefined:**
- **Optimal**: Plan with actual weather, realization matches perfectly (zero gap)
- **Upper bound (constant speed)**: SOG = D/ETA everywhere; same Flow 2 rules apply (re-plan constant speed after delay)

**What this decomposition isolates:**
1. **Averaging effect**: LP-A vs DP-A (same forecast, different resolution)
2. **Re-planning effect**: X-A vs X-B (same forecast, with/without re-plan on Flow 2)
3. **Forecast freshness effect**: X-B vs X-C (re-plan with stale vs fresh weather)

**Implementation status:**
- LP-A, DP-A, DP-C, LP-C: exist
- LP-B, DP-B: **need implementation** (re-plan on Flow 2 with stale forecast)
- Simulation Flow 2 detection: needs update (currently doesn't trigger re-planning mid-voyage)
- Constant-speed Flow 2: needs update (re-plan constant SOG after delay)
- **ETA penalty (λ)**: needs implementation in both LP and DP objectives + λ sensitivity sweep

**ETA as soft constraint with penalty λ (mt/h):**
- Objective becomes: minimize fuel + λ × max(0, arrival_time − ETA)
- λ converts delay hours to fuel-equivalent cost
- LP: linearize with delay variable δ ≥ 0, δ ≥ total_time − ETA, minimize fuel + λδ
- DP: select min(fuel + λ × max(0, t − ETA)) across all reachable final states
- Sweep λ ∈ [0.5, 1, 2, 5, 10, ∞] to map Pareto frontier per approach
- **Key question**: At what λ does LP-C become competitive with DP-A?

### 2026-03-18 — Agent-based reframing of the research

**Motivation:** Reframe the thesis not as "LP vs DP for ship speed optimization" but as an autonomous agent problem: "Given an agent with fixed hardware, which combination of optimization plan + environment capabilities produces the best cost-performance trade-off for a given task?"

---

#### Agent Definition

An **agent** is defined by five components:

```
Agent = (Planering Spec, Measurement System, Plan, Policy, Environment)
```

| Component | Role | Fixed/Variable | Our implementation |
|-----------|------|---------------|-------------------|
| Planering Spec | Physical constants of the platform | Fixed per agent | Ship params: 200m, 32m beam, 12m draft, 50,000t, 10,000 kW, SWS ∈ [11,13] kn |
| Measurement System | Equations linking control input to cost | Fixed per agent | SOG from SWS (wind/wave/current resistance), FCR = 0.000706 × V_s³ |
| Plan | Optimization algorithm that produces a speed schedule | Variable (3 choices) | Naive (constant SOG = D/ETA), LP (segment-averaged), DP (per-node, time-varying) |
| Policy | Rules for when/how to execute and revise the plan | Variable | "Follow plan" / "Re-plan on trigger" / "Re-plan with fresh data" |
| Environment | Capabilities available to the agent during the task | Variable (3 tiers) | Basic / Mid / Connected |

**Planering Spec** — all constant inputs from the ship design: length, beam, draft, displacement, block coefficient, rated power, speed range. These don't change during a voyage.

**Measurement System** — the set of equations (mostly derived from the engineering spec) that let the agent measure the relationship between SWS (control input) and fuel consumption (cost output). Includes: Holtrop-Mennen resistance decomposition, wind resistance (Isherwood coefficients), wave added resistance, current vector projection, and the cubic power-speed relationship.

**Plan** — the optimization algorithm that, given a route, weather forecast, and constraints, produces a speed schedule. Three plans:
1. **Naive**: constant SOG = total_distance / ETA. No optimization — just divide evenly.
2. **LP**: linear program over segments. Weather averaged per segment, one SWS per segment. Fast, simple, but loses spatial/temporal resolution.
3. **DP**: dynamic programming over per-node graph. Time-varying weather per node, fine-grained speed choices. Slower but captures environmental variation.

**Policy** — the rules governing how the agent uses its plan during the voyage:
- When to invoke the plan (once at departure? on schedule? on trigger?)
- What data to feed the plan (departure forecast? stale forecast? fresh forecast?)
- How to handle Flow 2 events (SWS hits physical limit, can't achieve planned SOG)

Policy is coupled to environment (you can't re-plan without compute), but within an environment tier, multiple policies are possible (e.g., re-plan every 6h vs every 12h vs only on Flow 2).

**Environment** — the capability tier the agent operates under:

| Environment | Compute | Communication | Planning behavior |
|-------------|---------|--------------|-------------------|
| **Basic** | None | None | One-time plan at departure. Agent follows plan rigidly. On Flow 2: sail at max SWS, accept delay. Like a ship with no onboard optimization. |
| **Mid** | Yes | None | Can re-plan during voyage, but only with the forecast loaded at departure (stale). On Flow 2: re-optimize remaining voyage with original forecast data. |
| **Connected** | Yes | Yes | Can re-plan AND download fresh forecasts mid-voyage. On Flow 2 or on schedule: re-optimize with up-to-date weather. |

---

#### The 9 Combinations (3 Plans × 3 Environments)

| | Basic (A) | Mid (B) | Connected (C) |
|--|-----------|---------|---------------|
| **Naive** | Constant speed, no re-plan | Re-plan constant speed on Flow 2 (stale) | Re-plan constant speed on Flow 2 (fresh) |
| **LP** | LP plan at departure, follow rigidly | Re-solve LP on Flow 2 with departure forecast | Re-solve LP on Flow 2 with fresh forecast |
| **DP** | DP plan at departure, follow rigidly | Re-solve DP on Flow 2 with departure forecast | Re-solve DP on Flow 2 with fresh forecast |

Not all 9 are equally interesting:
- **Naive-A** = constant speed baseline (already implemented)
- **Naive-B/C** = re-planning a constant speed doesn't gain much (just recalculates D_remaining/ETA_remaining)
- **LP-A, DP-A** = current static LP and static DP
- **LP-B, DP-B** = re-plan on Flow 2 with stale forecast (need implementation)
- **LP-C, DP-C** = current RH-LP and RH-DP (re-plan on schedule with fresh weather)

Meaningful comparisons reduce to ~7 configurations: Naive-A, LP-A, LP-B, LP-C, DP-A, DP-B, DP-C.

---

#### Task Definition

A **task** is what the agent is asked to do:

```
Task = (Route, Weather regime, ETA, λ)
```

| Parameter | What it captures | Our experiments |
|-----------|-----------------|----------------|
| Route | Distance, waypoints, heading changes | Route B (1,678 nm, Persian Gulf) vs Route D (1,955 nm, North Atlantic) |
| Weather regime | Severity, variability, predictability | Mild/stable (PG) vs harsh/variable (NA) |
| ETA | Time deadline | ~140h (Route B), ~163h (Route D) |
| λ | Mission priority: fuel vs punctuality | Sweep [0, 0.5, 1, 2, 5, 10, ∞] |

---

#### Research Questions (reframed)

1. **Plan value**: For a given environment, does upgrading the plan (Naive → LP → DP) improve performance? By how much? Is the improvement route-dependent?

2. **Environment value**: For a given plan, does upgrading the environment (Basic → Mid → Connected) improve performance? What's the marginal value of compute? Of communication?

3. **Interaction effects**: Does the plan × environment interaction matter? E.g., is DP-Basic better than LP-Connected? If so, plan choice matters more than environment. If not, even a simple plan benefits enough from re-planning to match a sophisticated plan without it.

4. **Task sensitivity**: How do answers 1-3 change across tasks? On a calm route, maybe Naive-A ≈ DP-C. On a stormy route, maybe only DP-C achieves acceptable performance.

5. **Cost-performance frontier**: For each task, what is the minimum-capability agent that achieves near-optimal performance? This is the practical recommendation: "don't deploy expensive compute/comms infrastructure if LP-Basic gets you within 2% of optimal."

---

#### What This Reframing Buys Us

1. **Generalizability**: The agent framework applies beyond ships — any autonomous platform (drones, trucks, EVs) with a physics model, route, and weather uncertainty.

2. **Clean taxonomy**: Instead of ad-hoc approach names (static det, dynamic det, rolling horizon), we have a structured decomposition: Plan × Environment × Policy.

3. **Practical recommendations**: Operators don't ask "should I use LP or DP?" They ask "given my ship's capabilities and this route, what should I deploy?" The agent framework answers this directly.

4. **λ fits naturally**: λ is a task parameter (mission priority), not an agent parameter. Same agent, different λ → different behavior. This separates the optimization question from the business question.

5. **Narrative strength**: "We study autonomous agents under uncertainty" is a stronger story than "we compared two optimization algorithms for ships."

---

#### Mapping to Existing Work

| Current name | Agent framing |
|-------------|--------------|
| Constant speed baseline | Naive-A |
| Static LP | LP-A |
| Static DP | DP-A |
| RH-DP (stale forecast) | DP-B (if re-plan on Flow 2 only) |
| RH-DP (fresh forecast) | DP-C |
| RH-LP (fresh forecast) | LP-C |
| New (not yet built) | LP-B, DP-B (re-plan on Flow 2 with stale forecast) |

#### Open Questions

1. **Is Naive-B/C worth implementing?** Re-planning a constant speed after Flow 2 just gives a new D_remaining/ETA_remaining — trivial but could be a useful data point.
2. **Policy as a separate dimension?** Currently policy is locked to environment tier. Should we also vary policy within a tier (e.g., Mid with "re-plan every 6h" vs "re-plan on Flow 2 only")?
3. **Paper venue**: Does this reframing point toward a different target journal? Autonomous systems / AI planning vs pure maritime OR?
4. **Title candidates**: "Autonomous Speed Control Under Environmental Uncertainty: An Agent-Based Analysis of Maritime Voyage Optimization" or similar?

### 2026-03-18 — Agent implementation deep dive: Policy and the execution loop

---

#### Agent Construction

An agent is composed by selecting one option from each variable component:

```python
agent = Agent(
    spec=ship_params,                      # fixed hardware
    measurement=PhysicsModel(ship_params),  # fixed equations
    plan=DPPlan(),                          # or LPPlan() or NaivePlan()
    policy=ReplanOnFlow2Policy(),           # or FollowPlanPolicy() or ScheduledReplanPolicy()
    environment=ConnectedEnvironment(),     # or BasicEnvironment() or MidEnvironment()
)
```

The **spec** and **measurement system** are always the same — they're the ship. What varies between experiments is **plan × policy × environment**.

---

#### The Voyage Execution Loop (leg by leg)

This is the core of how an agent operates. Every leg follows the same sequence:

```
For each leg i = 0, 1, ..., N-1:

  1. OBSERVE
     Read actual weather at current position and time.

  2. ASSESS
     What SWS do I need to achieve my planned SOG?
     required_sws = measurement.inverse_sog(planned_sog[i], actual_weather)

  3. CLASSIFY
     if 11 ≤ required_sws ≤ 13  →  FLOW 1 (nominal)
     if required_sws > 13        →  FLOW 2 (adverse — can't keep up)
     if required_sws < 11        →  FLOW 3 (favorable — would overshoot)

  4. EXECUTE
     Flow 1: set SWS = required_sws → achieve planned SOG exactly
     Flow 2: set SWS = 13 (max)    → achieve SOG < planned, fall behind
     Flow 3: set SWS = 11 (min)    → achieve SOG > planned, get ahead

  5. UPDATE STATE
     actual_sog = measurement.forward_sog(actual_sws, actual_weather)
     leg_time = distance[i] / actual_sog
     leg_fuel = fcr(actual_sws) * leg_time
     cumulative_time += leg_time
     cumulative_fuel += leg_fuel
     delay = cumulative_time - planned_cumulative_time

  6. POLICY DECISION
     Does the agent re-plan? → This is where environments diverge.
```

---

#### The Three Policies in Detail

**Basic Policy — "follow the plan, no matter what"**

```
Step 6: Never re-plan.
  - Flow 2 → accept delay, continue with next leg's planned SOG
  - Flow 3 → accept being ahead, continue with next leg's planned SOG
  - Delay accumulates with no correction mechanism.
```

After a Flow 2 event, the agent is behind schedule. The next leg's planned SOG was computed assuming on-time arrival at this node. The agent is late but still targets the same SOG — so it arrives even later. **Delay compounds.**

Critical property: the agent does NOT try to recover by going faster. It can't recalculate. It just follows the original speed schedule blindly.

**Mid Policy — "re-plan with what I have"**

```
Step 6: On Flow 2 event:
  a. Remaining route = legs [i+1 ... N-1]
  b. Remaining ETA = original_ETA - cumulative_time
  c. Re-run plan optimizer with STALE forecast (loaded at departure)
  d. Get new speed schedule for remaining legs
  e. Replace planned_sog[i+1:] with new schedule
  f. Continue
```

Key properties:
- Re-plans **reactively** — only when something goes wrong (Flow 2)
- Uses **departure forecast** — weather data may be hours or days old
- The re-plan knows the agent is behind and can try to recover (speed up) or accept delay (via λ)
- Does NOT re-plan on Flow 3 (favorable). This is a policy choice — could be varied.

**Connected Policy — "re-plan with fresh information"**

```
Step 6: On Flow 2 event OR on schedule (every 6h):
  a. Download fresh weather forecast  ← key difference from Mid
  b. Remaining route = legs [i+1 ... N-1]
  c. Remaining ETA = original_ETA - cumulative_time
  d. Re-run plan optimizer with FRESH forecast
  e. Replace planned_sog[i+1:] with new schedule
  f. Continue
```

Two differences from Mid:
1. Fresh forecast → re-plan based on current reality, not stale assumptions
2. Re-plans proactively on schedule, not just reactively on Flow 2

---

#### Flow 3: The Underexplored Case

Flow 3 = favorable conditions, ship would go faster than planned. Agent is ahead of schedule. What should it do?

- **Basic**: nothing. Keep following plan. Arrive early.
- **Mid/Connected**: could re-plan to slow down and save fuel, exploiting the time buffer.

With λ penalty: arriving early has no cost (delay = max(0, time - ETA)), so the fuel savings from slowing down are pure benefit. A Mid/Connected agent SHOULD re-plan on Flow 3 too. But Basic can't.

**Design decision**: Should Flow 3 trigger re-planning in Mid/Connected? Probably yes — any significant divergence from plan is an opportunity to re-optimize.

**Revised trigger logic:**
- Basic: never re-plan
- Mid: re-plan on Flow 2 (reactive, stale forecast)
- Connected: re-plan on Flow 2 OR on schedule every 6h (proactive + reactive, fresh forecast)
- Possible Mid variant: re-plan on Flow 2 OR Flow 3 (any divergence, stale forecast)

---

#### Delay Compounding Under Basic Policy

After Flow 2 on leg i, the agent is Δt hours late. For remaining legs, the original plan assumed weather at time T_planned, but the agent experiences weather at time T_planned + Δt.

On Route D (North Atlantic), weather changes significantly over hours. The delay shifts the agent into **different weather** than planned:
- If the new weather is worse → more Flow 2 events → more delay → **cascading failure**
- If the new weather is better → partial recovery → less total delay

This cascading effect is the fundamental weakness of the Basic agent. Mid and Connected agents break the cascade by re-planning.

**Testable prediction**: Basic agent delay variance should be much higher than Mid/Connected on harsh routes, but similar on calm routes.

---

#### Re-plan Mechanics: What Happens Inside

When a Mid or Connected agent re-plans, it constructs a **sub-problem**:

```
Sub-problem at leg i:
  - Remaining legs: [i+1 ... N-1]
  - Remaining distance: sum(distances[i+1:])
  - Remaining ETA: original_ETA - cumulative_time_so_far
  - Weather: stale forecast (Mid) or fresh forecast (Connected)
  - λ: same as original (mission priority doesn't change mid-voyage)
  - Constraints: same SWS ∈ [11, 13]
```

The plan optimizer (LP or DP) solves this sub-problem from scratch. The new plan replaces everything from leg i+1 onward. Legs already executed are sunk cost — the optimizer only controls the future.

**Key insight**: remaining_ETA can be negative (if already late). With hard ETA (λ=null), the sub-problem is infeasible. With soft ETA (λ finite), the optimizer naturally handles this — it minimizes fuel + λ × additional_delay.

This is why λ is essential for the Mid/Connected agents. Without it, re-planning after delay is often infeasible.

---

#### Open Implementation Questions

1. **Re-plan granularity**: Does the agent re-plan after every Flow 2 leg, or batch them? E.g., if legs 50-55 are all Flow 2, does it re-plan 6 times or once after leg 55?
   - Proposal: re-plan once when transitioning OUT of a Flow 2 sequence (first Flow 1 after one or more Flow 2 legs). This avoids wasteful re-computation during a storm.

2. **Connected re-plan schedule**: Every 6h aligns with NWP cycles (proven: 86% data redundancy at sub-6h). Should it ALSO re-plan on Flow 2 between scheduled points?
   - Proposal: yes, hybrid trigger. Scheduled every 6h + reactive on Flow 2. This catches both gradual drift and sudden adverse events.

3. **Flow 3 re-plan**: Worth the compute cost?
   - Proposal: yes for Connected (cheap, and fresh forecast makes it valuable). Skip for Mid (stale forecast limits the benefit, and the agent is ahead anyway — low urgency).

4. **State passed to re-planner**: Just remaining route + ETA? Or also the history of Flow 2/3 events? History could inform the re-planner about forecast reliability (if many Flow 2 events, maybe add a safety margin).
   - Proposal: keep it simple for now — just remaining route + remaining ETA + weather. History-aware re-planning is future work.

---

#### Mapping to Existing Code

| Agent concept | Existing code |
|--------------|--------------|
| Engineering Spec | `config['ship']` in experiment YAML |
| Measurement System | `shared/physics.py` (calculate_speed_over_ground, calculate_fuel_consumption_rate) |
| Naive Plan | `compare/sensitivity.py::run_constant_speed_bound()` |
| LP Plan | `static_det/optimize.py::optimize()` |
| DP Plan | `dynamic_det/optimize.py::optimize()` |
| Basic Policy (execute loop) | `shared/simulation.py::simulate_voyage()` — currently does the leg loop but no re-planning |
| Mid Policy | **New** — needs voyage executor with Flow 2 detection + re-plan with stale forecast |
| Connected Policy | `dynamic_rh/optimize.py` — currently does scheduled re-plan, needs refactor to leg-by-leg execution |
| Sub-problem builder (DP) | `dynamic_rh/optimize.py` lines 113-126 (slice arrays from current node) |
| Sub-problem builder (LP) | `dynamic_rh/optimize_lp.py::_build_lp_sub_problem()` |

**The missing piece is `pipeline/shared/voyage_executor.py`** — the unified leg-by-leg execution loop that implements all three policies. This is Phase 4 from the batch 2 plan.

### 2026-03-18 — Composable agent architecture

---

#### Design Principle

Every piece is a swappable component with a standard interface. You assemble an agent by picking one implementation per slot:

```python
agent = assemble(
    spec = BulkCarrier200m(),
    measurement = HoltropMennen(),
    plan = DPPlan(granularity=0.1),
    policy = ReactivePolicy(trigger="flow2"),
    environment = Connected(forecast_source="open_meteo"),
)

result = agent.execute(route, initial_forecast, eta, lambda_val)
```

---

#### Component Interfaces

**Spec** — pure data container, no logic:
```
spec.length_m → 200
spec.beam_m → 32
spec.speed_range → (11, 13)
spec.fcr_coefficient → 0.000706
```

**Measurement** — translates between control input (SWS) and outcomes (SOG, fuel). Two directions:
```
measurement.forward(sws, weather) → sog, fcr
measurement.inverse(target_sog, weather) → required_sws
```
Currently `shared/physics.py`. Swappable in future work (e.g., Hollenbach instead of Holtrop-Mennen). Fixed for this thesis.

**Plan** — static optimizer. Takes a snapshot problem, returns a speed schedule:
```
plan.optimize(route_segment, weather_data, eta, lambda_val) → speed_schedule
```
Same interface for Naive (trivial), LP, and DP. The plan knows nothing about voyage execution — it solves a one-shot optimization when asked.

**Policy** — the decision brain. After each leg, decides what to do next:
```
policy.on_leg_complete(state) → CONTINUE | REPLAN | REPLAN_FRESH
```
The policy sees full state (current leg, delay, flow type, time since last replan) and decides. Implementations:
- `PassivePolicy()` — always CONTINUE
- `ReactivePolicy(trigger="flow2")` — REPLAN on Flow 2 only
- `ReactivePolicy(trigger="any_divergence")` — REPLAN on Flow 2 or Flow 3
- `ProactivePolicy(interval=6, also_on_flow2=True)` — REPLAN_FRESH every 6h + reactive on Flow 2

**Environment** — provides capabilities that constrain what the policy can actually do:
```
environment.can_compute → bool
environment.can_communicate → bool
environment.get_forecast(time) → weather_data  # fresh download or stale cache
```

---

#### Key Design Insight: Policy and Environment Are Separate Concerns

- **Policy** decides WHEN to re-plan
- **Environment** decides HOW (with what data, or not at all)

A ReactivePolicy on a Basic environment = policy wants to re-plan but can't → same as PassivePolicy. Upgrade the environment to Mid → same policy now works. This separation is clean and testable.

Default pairings (can be overridden):
```
Basic()       → PassivePolicy()
Mid()         → ReactivePolicy(trigger="flow2")
Connected()   → ProactivePolicy(interval=6, also_on_flow2=True)
```

---

#### The Executor — Wires Components Together

The executor is NOT a component — it's the runtime loop:

```python
def execute_voyage(agent, route, initial_forecast, eta, lambda_val):

    # Initial planning
    weather = initial_forecast
    schedule = agent.plan.optimize(route, weather, eta, lambda_val)
    state = VoyageState(position=0, time=0, fuel=0, schedule=schedule)

    for leg_idx in range(route.num_legs):

        # 1. OBSERVE — actual weather at current position and time
        actual_wx = route.actual_weather(leg_idx, state.time)

        # 2. ASSESS — what SWS needed?
        required_sws = agent.measurement.inverse(schedule[leg_idx].sog, actual_wx)

        # 3. CLASSIFY
        flow = classify(required_sws, agent.spec.speed_range)

        # 4. EXECUTE
        actual_sws = clamp(required_sws, agent.spec.speed_range)
        actual_sog, fcr = agent.measurement.forward(actual_sws, actual_wx)
        leg_time = route.distances[leg_idx] / actual_sog
        leg_fuel = fcr * leg_time

        # 5. UPDATE STATE
        state.advance(leg_time, leg_fuel, flow)

        # 6. POLICY DECISION
        action = agent.policy.on_leg_complete(state)

        if action != CONTINUE and agent.environment.can_compute:
            if action == REPLAN_FRESH and agent.environment.can_communicate:
                weather = agent.environment.get_fresh_forecast(state.time)

            remaining = route.slice(leg_idx + 1)
            remaining_eta = eta - state.time
            new_schedule = agent.plan.optimize(remaining, weather, remaining_eta, lambda_val)
            state.replace_schedule(leg_idx + 1, new_schedule)

    return state.to_result()
```

---

#### Experiment Runner — Combinatorial

```python
for plan in [NaivePlan(), LPPlan(), DPPlan()]:
    for env in [Basic(), Mid(), Connected()]:
        for route in [route_b, route_d]:
            for lam in [0.5, 1, 2, 5, None]:
                agent = assemble(spec, measurement, plan, policy_for(env), env)
                result = execute_voyage(agent, route, forecast, eta, lam)
                results.append(result)
```

---

#### Scope Decisions for This Thesis

- **Measurement system**: Fixed (Holtrop-Mennen + Isherwood). Swappable interface is designed in but only one implementation. Alternative models (Hollenbach, CFD-based) are future work.
- **Spec**: Fixed (single bulk carrier). Multi-vessel comparison is future work.
- **Plan**: Three implementations (Naive, LP, DP). Interface supports adding MPC, GA, RL in future.
- **Policy**: Three implementations (Passive, Reactive, Proactive). Flow 3 re-planning tested as a variant of Reactive.
- **Environment**: Three tiers (Basic, Mid, Connected). Fleet-connected (ship-to-ship weather sharing) is future work.

---

## 14. New DP Graph Structure — Brainstorm (2026-04-20)

**Motivation.** Exp 1 (Apr 20 prep) landed on a tie: free DP and 6h-locked DP within 0.25% fuel
under hard ETA. Both Track A and Track B exposed accumulated ceiling-rounding drift and a Track B
anomaly where Luo's lattice beat the "free" solver (theoretically impossible). Before running more
experiments on top of a graph that is already leaking ~1–2 mt of phantom fuel from rounding, the
cleaner move is to rebuild the graph from first principles, using the legacy
`Dynamic speed optimization/speed_control_optimizer.py` as the reference point for what's
worth keeping.

### 14.1 What the legacy DP actually does

Three moving parts — the spine of any DP graph:

**A. Grid / spacing**
- Dense 2D numpy array indexed by `(time_hours, distance_nm)`.
- Time rows: 0 → ~280h at `time_granularity = 1h` → 281 rows.
- Distance cols: 0 → 3,393 nm at `distance_granularity = 1 nm` → 3,394 cols.
- Total ≈ 953K `Node` objects allocated, most never touched.
- Reachable region carved out by `Side` BFS: vertical sides at cumulative segment distances,
  horizontal sides at time-window boundaries.

**B. Edge (Arc) creation — `connect_sides()` + `connect()`**
- For every pair (source_node in src_side, dest_node in dst_side), compute:
  - `distance_diff = d2 − d1`, `time_diff = t2 − t1`
  - `sog = round(distance_diff / time_diff, 1)`
  - **Filter**: arc exists only if `sog ∈ speed_values_list` (e.g. 11.0, 11.1, …, 13.0)
- If filter passes, **SWS inverse**: binary-search `calculate_sws_from_sog(sog, segment_weather)`
  to get the engine setting that produces that SOG under the segment's weather.
- `FCR = 0.000706 × SWS³` (mt/h).
- `arc.fuel_consumption = FCR × time_diff`.
- `arc.fuel_load = source.minimal_fuel_consumption` (cumulative fuel carried into this node).

**C. Backward fuel calculation — inline Bellman relaxation + pointer backtrack**
- Relaxation in `connect_sides()` line 523:
  ```
  if d_node.minimal_fuel_consumption > arc.fuel_load + arc.fuel_consumption:
      d_node.minimal_fuel_consumption = arc.fuel_load + arc.fuel_consumption
      d_node.minimal_input_arc = arc
  ```
- `find_solution_path()`: scan the destination column (`col = 3393`), pick the node with minimum
  `minimal_fuel_consumption`, then walk `minimal_input_arc` pointers backwards to the source.
- The speed schedule is reconstructed from the `SWS`/`SOG` fields stored on each arc along the
  path.

### 14.2 What's right about this design (keep)

- **Explicit `Arc` carrying SWS, SOG, travel_time, distance, FCR, fuel_consumption, fuel_load.**
  Backtrack gives you the entire schedule for free — no post-hoc recomputation.
- **Inline Bellman relaxation** (no priority queue). DP on a DAG doesn't need Dijkstra; a forward
  sweep is cleaner and faster.
- **`Side` boundaries** as segment / window markers — even if we drop the dense grid, the concept
  of "nodes aligned with segment distances" and "nodes aligned with window times" is useful
  bookkeeping.
- **Pointer-based backtrack** is elegant. The pipeline DP uses a parent dict; same info, same
  cost, but the legacy style puts the schedule on the arcs, which is nicer.

### 14.3 What's wrong about this design (fix)

- **Dense array is mostly empty.** 953K nodes allocated, maybe 5–10% reachable.
- **`dt = 1h` is fatal.** 1h × 1 nm means many legitimate SOGs are unreachable: `(d2−d1)/(t2−t1)`
  must round exactly to a 0.1 kn grid point. Most (src, dst) pairs fail the filter → sparse
  connectivity even though the array is dense.
- **SOG-matching filter is the wrong primitive.** It couples speed resolution to grid spacing
  (same trap as Luo). Pipeline DP's forward SWS loop is the right primitive — speed is an
  explicit config knob, independent of geometry.
- **Inverse SWS = binary search per arc.** Pipeline DP computes SOG forward from SWS (one shot);
  legacy burns 50 iterations per arc. O(arcs) binary searches is pure overhead.
- **Weather hardcoded to `weather_forecasts_list[0]`** (line 577). The multi-window YAML
  infrastructure is there but the code never indexes by time. Time-varying weather is a must-have
  from day one of the rebuild.
- **No explicit ETA constraint**, only the grid boundary. Soft ETA (λ penalty) is not
  expressible.
- **No rolling horizon.** One-shot solve, no replan loop.
- **Ceiling-rounding is implicit and uncontrolled.** `round(.. , 1)` in the SOG filter silently
  drops feasible arcs. Rounding policy should be a deliberate design decision, not a side effect.

### 14.4 Candidate topologies for the rebuild

Four designs, each a deliberate choice about which axis floats and what a node means:

**Option A — `(waypoint_idx, time_slot)` sparse (current pipeline DP, cleaned up)**
- Axes: route position (discrete waypoints), time (slots of `dt`).
- Decision: SWS (forward physics → SOG → travel time → arrival slot).
- Pro: matches thesis infrastructure (HDF5, physics module), supports time-varying weather
  natively (`fh = f(current_hour)`), sparse → small memory.
- Con: ceiling-rounding per leg accumulates over 391 legs (documented drift).
- Fix in rebuild: accumulate continuous travel time, round only at decision/replan boundaries.

**Option B — `(distance, time)` dense grid (legacy, modernized)**
- Axes: cumulative distance (nm), absolute time (hours).
- Decision: SWS at each arc (forward, not inverse).
- Pro: keeps the legacy `Side` bookkeeping and segment alignment; every (d, t) cell carries
  accumulated fuel which is conceptually clean.
- Con: dense array wasteful; forces pre-commitment to an integer `(dt, dx)` lattice.
- Fix in rebuild: replace numpy array with sparse dict-of-dicts, keep Sides as logical markers.

**Option C — `(stage, remaining_distance)` lattice (Luo-style)**
- Axes: forecast cycle index (6h stages), remaining distance to destination.
- Decision: speed per stage (one decision per stage, held for the full cycle).
- Pro: aligns with NWP cycles and rolling horizon naturally; smallest graph.
- Con: throws away within-stage granularity; couples speed resolution to geometry (Luo's trap).
- Verdict: worth supporting as a **comparison mode**, not as the primary topology.

**Option D — Two-layer: `(cell, heading)` decision units × `(time_slot)` for fuel**
- Outer layer: consecutive waypoints collapsed into a decision unit whenever heading and
  weather-cell are unchanged (brainstorm from Apr 20 §3). Pipeline DP at 391 waypoints may only
  have ~50–100 true decision units.
- Inner layer: within a unit, SWS is constant; arrival-time slot computed from actual physics.
- Pro: matches the physics — speed shouldn't change if nothing physical has changed. Small state
  space without throwing away spatial weather resolution.
- Con: requires a route preprocessing step (cell-assignment, heading-bucketing).

**Working recommendation**: Option A with two disciplined upgrades — (i) continuous time carried
in state, ceilings only at decision/replan boundaries; (ii) decision-unit collapsing from
Option D available as a preprocessing step that reduces the edge count without changing the
state definition. Option C kept as a solver variant for direct Luo comparison.

### 14.5 Three independent axes (non-negotiable)

The rebuild must keep these **independent** (the Luo-lesson from Apr 20 §4.8):

| Axis | Knob | Set by |
|---|---|---|
| Spatial resolution | waypoint spacing | route geometry (or cell collapse) |
| Temporal resolution | `dt` | config |
| Speed resolution | `Δv` (SWS step) | config |

No axis implies another. This is the structural fix to Luo's coupling and to the legacy DP's
SOG-matching filter.

### 14.6 Edge semantics — forward, explicit, honest

For every (source, candidate_SWS) pair:
1. Look up weather at source position, at forecast_hour = f(source.time).
2. Compute SOG = `physics.forward(SWS, weather, heading)` (one shot, no binary search).
3. Compute `leg_time = leg_distance / SOG` (continuous float).
4. Arrival state = `(next_waypoint, source.time + leg_time)` — keep continuous time in state.
5. Edge weight = `FCR(SWS) × leg_time` (continuous, no ceilings).

Ceilings enter **only** when we map continuous time to a time-slot for dict keying during
relaxation, and we do it in one place with a documented policy (round-down + epsilon, or
round-nearest, or two-slot dispersion — we pick one and defend it).

### 14.7 Backward fuel calculation — two styles, pick one

**Style 1 — Arc-as-record (legacy).** Each arc carries SWS, SOG, travel_time, fuel, and a
pointer from dest to best incoming arc. Backtrack = walk pointers, read fields.
- Pro: schedule reconstruction is trivial, no recomputation.
- Con: memory per relaxed edge is larger.

**Style 2 — Parent dict + recompute (pipeline).** Store only `parent[(i, t_slot)] = (i-1, t_slot', sws)`.
Backtrack = walk parents, recompute SOG/time/fuel from SWS + stored weather.
- Pro: minimal memory.
- Con: slight recomputation at the end, needs weather still accessible.

**Preference**: Style 1 (legacy). The backward pass is the one place where we want the full story
on each leg (SWS, SOG, travel time, fuel, clamped-or-not) for the paper's plots. Paying the
memory is worth it; backtrack clarity is a feature.

### 14.8 ETA — both hard and soft as first-class

- **Hard ETA**: reject any arrival state with `time > ETA`. Simple boundary filter.
- **Soft ETA**: at destination, cost = `total_fuel + λ × max(0, arrival_time − ETA)`.
- The graph is built once; ETA mode changes only the terminal cost. Both must be supported
  natively — no monkey-patching.

### 14.9 Time-varying weather and rolling horizon from day one

- **Static (hard-ETA, single plan)**: weather grid `w[node][fh]`, `fh = round(current_time + offset)`.
- **Replan every 6h (RH)**: at each replan, rebuild the subgraph from current state with the
  latest forecast; carry state (fuel-so-far, time-so-far, position) forward.
- Both modes must use the **same `optimize()` entry point** — differ only in how weather is
  sourced and how the subgraph is sliced.

### 14.10 Decision-unit collapsing (preprocessing)

Before building the graph, walk the route once and collapse consecutive waypoints sharing
`(weather_cell_id, heading_bucket)` into a single decision node. Output: a reduced route where
each node has the same decision semantics but the total edge count is a fraction of the raw
waypoint count.

- Weather cell: grid_id from the NWP source (0.5° GEFS ≈ 30 nm, 0.1° Open-Meteo ≈ 6 nm).
- Heading bucket: discretize heading to, say, 10° buckets.
- Store the underlying waypoint list per unit — the executor still needs them for simulation,
  but the optimizer decides once per unit.

This is the mechanical form of the Apr 20 §3 brainstorm. It doesn't change the physics; it
removes the optimizer's ability to fit noise.

### 14.11 Sanity checks the rebuild must pass

Before trusting any Exp 1 / Exp 2 result:
1. **Degenerate lock check**: with `lock = dt` (no locking), locked-mode must equal free-mode
   fuel to within <0.01 mt. (Fails today — Exp 1 had +0.76 mt drift.)
2. **Single-speed check**: force SWS constant → must match hand-computed grid search over
   constants.
3. **Zero-weather check**: flat weather everywhere → optimizer picks `v = L / T_max`, matches
   closed-form answer.
4. **Lock-monotonicity**: `fuel(6h lock) ≥ fuel(3h lock) ≥ fuel(1h lock) ≥ fuel(free)`. Today
   this fails by 0.76 mt on [11,13] dt=0.01h.
5. **Cross-solver agreement at Luo's published resolution**: Track A, rebuilt free DP, and
   Luo-lattice mode must agree within <0.1% at `dt=1h, Δv=0.167 kn, lock=6h`.
6. **Backtrack reconstruction**: total fuel from backtrack path must equal `minimal_fuel_consumption`
   at the chosen destination node. No discrepancy.

### 14.12 Questions this brainstorm leaves open

- How do we treat **partial legs** at replan boundaries — interpolate weather at mid-leg, or snap
  the replan moment to the next waypoint?
- If Option D (cell × heading collapsing) removes 70% of the edges, do the sanity checks in §14.11
  still hold, or does the optimizer systematically prefer collapsed routes (which could be a real
  finding or an artifact)?
- Is **soft ETA via λ** the right formulation, or do we want a CII-style nonlinear penalty
  that's cheap before ETA and steep after?
- For the paper: do we present **one rebuilt graph with a config knob** for lock-hours and
  topology, or **two explicit modes** (free / locked) documented as siblings? The former is more
  honest as a "unified framework"; the latter is easier to explain.

### 14.13 Next steps

1. Write a one-page walkthrough of the legacy DP (A, B, C of §14.1) for the record — treat it as
   the baseline documentation.
2. Pick a topology (recommendation: Option A with Option D preprocessing).
3. Define the data classes: `Node`, `Arc`, `Route`, `WeatherGrid`, `Result`. Shared across solver
   modes.
4. Implement the forward relaxation with continuous time + arc-as-record backtrack.
5. Run §14.11 sanity checks before touching any experiment.
6. Only then rerun Exp 1 free vs locked on the new graph and confirm the tie holds (or not)
   without rounding drift.

### 14.14 Spec Decisions — Q&A Session (2026-04-20, convention flipped 2026-04-23)

Working session with supervisor/Ami to lock the concrete graph spec. Setup: 4000 nm voyage,
400 h ETA, **x-axis = time** from voyage start, **y-axis = distance** from voyage start.

**Geometric convention (as of 2026-04-23):**
- **Vertical line (V)** = constant time — time-decision boundary (every dt_h hours,
  default 6 h). Geometrically parallel to the distance axis.
- **Horizontal line (H)** = constant distance — course-change / weather-cell / terminal-sink
  boundary. Geometrically parallel to the time axis.

Nodes live only on V and H lines; the space between lines is empty. Q&A answers below were
originally logged under the inverse labels (H=time, V=distance) and have been re-cast to the
geometric convention. Semantics of every decision are unchanged — only labels flipped.

**Q1 — Edge destination rule:** **(a)** Every edge terminates at the **very first boundary line**
it crosses going forward (V or H — whichever is closer in (t, d) space). Every line crossing is a
forced decision stop. No edges skip lines.
- *Implication:* Keeps DP layers clean. Max edges per source ≈ |speed range discretization|.
  Graph size stays bounded. Matches legacy Sides BFS in spirit.

**Q2 — V-line (constant-time) spacing:** **(b)** V lines at every `dt_h` hours, **configurable**
(default 6 h, aligned conceptually to GFS NWP cycle). Plus a synthetic terminal V line at
exactly `t = ETA` for sink convergence.
- *Implication:* Config knob lets us sweep lock-hours (1h, 3h, 6h, 12h) without touching graph
  code. Terminal line handles ETAs that aren't integer multiples of `dt_h`.
- **Tail policy (Apr 22):** keep every regular multiple of `dt_h` that is `< ETA`, *and* append
  `t = ETA` even if the gap is smaller. Example for `dt_h=6, ETA=400`:
  `[6, 12, ..., 390, 396, 400]` — 66 regular 6h blocks + 1 short 4h tail block.

**Q3 — H-line (constant-distance) placement:** **Resolved via Q8**. H lines are placed at
**course changes UNION weather-cell boundaries**. Both types of physical change force a
decision stop.
- *Implication:* On Route D (391 smooth-heading waypoints), H lines are driven primarily by
  weather-cell transitions (NWP grid ~30 nm for GFS, ~6 nm for Open-Meteo). A route preprocessing
  pass emits an H line wherever `(heading_bucket, weather_cell_id)` changes. Number of H lines
  is route- and grid-dependent.

**Q4 — Node density on a V line (varying distance):** **(b)** Nodes at every `ζ` nm across the
full `[0, L]` distance axis on each V line. `ζ` **configurable, default 1 nm**. No reachability
pruning at node creation — pruning happens via edge feasibility (Q1 + Q7 speed range).
- *Implication:* With default `dt_h=6, L=4000, ζ=1`: 4001 nodes per V line × 67 V lines
  ≈ 268K V-line nodes. Preserves the "three independent axes" principle.

**Q5 — Node density on an H line (varying time):** **(a)** Nodes at every `τ` h across the full
`[0, ETA]` time axis on each H line. `τ` **configurable, default 0.1 h**. Matches Q4's treatment
of the distance axis — both line types use a dense, uniform, configurable discretization.
- *Implication:* With default `τ=0.1, ETA=400`: 4001 nodes per H line. Total H-line nodes
  scale linearly with the number of H lines (Q3).

**Q6 — Speed = Δd/Δt — SOG or SWS?** **(a)** Edge geometry fixes **SOG** (ground speed). For
each edge, **SWS is recovered** by inverse-solving under the source-node weather (binary search
or analytic inverse over the physics model). **FCR = 0.000706 × SWS³** then drives the edge
cost. Legacy-DP style. Preserves the thesis's SWS/SOG split.
- *Implication:* The speed-range filter (Q7) is applied to SOG (what the edge geometry
  determines). SWS may land outside [v_min, v_max] in bad weather — that's exactly the **Flow 2
  event** the thesis measures. Treat those edges as either (a) infeasible / pruned, or (b)
  clamped with a penalty — deferred to a later question if needed.
- *Implication:* Physics inverse is the bottleneck. If too slow, switch to a tabulated
  `SWS(SOG, weather)` lookup precomputed per weather cell.

**Q7 — Speed range filter:** **(a)** Continuous interval `[v_min, v_max]`. An edge is valid iff
`v_min ≤ SOG ≤ v_max`, where `SOG = Δd/Δt`. No exact-match filter, no rounding to a discrete
speed grid. Legacy's `round(sog, 1) in speed_values_list` filter is **dropped**.
- *Implication:* Massively more edges per source than legacy. With Q4/Q5 dense grids
  (V-line ζ=1 nm, H-line τ=0.1 h) and `v_range=[9, 13]` kn, each source fans out to the full
  band on the next boundary. Real fan-out is bounded by `(v_max − v_min) × Δt / ζ` per V-line
  target and `(1/v_min − 1/v_max) × Δd / τ` per H-line target.
- *Implication:* Speed resolution is now set by the node grid (ζ, τ), not by a separate speed
  list. Effective speed granularity on the next V line ≈ `ζ / Δt` kn. For ζ=1 nm, Δt=6h →
  0.167 kn — matches Luo's implicit granularity. If we want finer speed resolution, lower ζ
  (not a separate Δv knob). This re-couples speed to geometry — worth noting as a tension with
  §14.5 "three independent axes". We lose one axis of independence here, but gain simplicity.

**Q8 — Weather used for an edge:** **Deferred on formulation, locked on assumption.** For now,
assume **weather stays constant between nodes** — one representative weather per edge (source-node
weather is the natural choice). The formulation (source / midpoint / integrated) is left open
because the structural fix in Q3 (vertical lines at weather-cell boundaries) guarantees no edge
ever crosses a weather-cell boundary, so all three formulations collapse to the same value
within a decision unit.
- *Implication:* Couples Q8 to Q3 — the "weather constant between nodes" invariant **requires**
  vertical lines at weather changes. Drop that requirement and Q8 becomes the hard question it
  was.
- *Implication:* Temporal weather drift within a single horizontal cycle (6h default) is ignored
  by this assumption. If NWP cycle = horizontal line spacing, that drift is zero by construction
  (forecast doesn't refresh within a cycle). If we ever decouple horizontal spacing from NWP
  cycle, revisit.
- *Open:* Later, if we want within-edge weather evolution (e.g., integrated FCR along a 6h
  edge), this becomes a real design decision. For the first cut, constant is fine.

**Q9 — Terminal node / ETA:** **(d)** Both **hard ETA** and **soft ETA** are supported as
first-class modes, selected by config.
- **Hard ETA mode**: sink is the **column of nodes at `d = route_length`, `t ∈ [t_min, ETA]`**.
  Early arrival is allowed. Pick the minimum-cumulative-fuel sink node among all reachable ones
  in that column. Paths that would arrive after ETA are pruned.
- **Soft ETA mode**: sink is the **column `d = route_length, t ≥ t_min`** (no upper cap on t
  beyond the graph extent). Terminal cost = `cumulative_fuel + λ × max(0, t_arrive − ETA)`. Pick
  minimum terminal cost.
- *Implication:* Graph is built once; only the terminal-node selection logic differs between
  modes. No monkey-patching. `λ` is a config parameter in soft mode.
- *Implication:* Early arrival in hard mode surfaces the Flow 3 story naturally — the optimizer
  *chooses* to finish early when that's cheaper than holding min-SWS through favorable weather.

**Q10 — Source node:** **(a)** Single source node at `(t=0, d=0)`. One voyage, one start.

### 14.15 Spec Summary — The Graph We're Building (geometric convention)

Putting Q1–Q10 together. Axes: **x = time, y = distance**.

**Two line families:**
- **Vertical lines (V)** — constant time. At `t = dt_h, 2·dt_h, ..., ETA` with default
  `dt_h = 6h`, configurable. Tail policy: keep every multiple `< ETA`, append `t = ETA`.
- **Horizontal lines (H)** — constant distance. At every **course change OR weather-cell
  boundary**. Placement driven by route preprocessing over `(heading_bucket, weather_cell_id)`.
- Plus a **dense terminal H line at `d = L`** for the sink column at `τ` granularity.

**Node density:**
- V lines: nodes every `ζ` nm across full `[0, L]` distance axis (default `ζ = 1 nm`).
- H lines: nodes every `τ` h across full `[0, ETA]` time axis (default `τ = 0.1 h`).
- Source: single node at `(0, 0)`.
- Sinks: all nodes at `d = L` (on the terminal H line + intersections with every V line).

**Edges:**
- Every edge goes from a source to a node on the **very first boundary line** it reaches
  (whichever comes first — next V or next H) with `Δt > 0, Δd > 0`.
- Implied `SOG = Δd/Δt` must lie in continuous interval `[v_min, v_max]`.
- For each valid edge: `SWS` recovered by physics inverse under **source-node weather**;
  `FCR = 0.000706 × SWS³`; edge fuel `= FCR × Δt`.
- Weather constant over each edge by construction (H lines at every weather-cell boundary
  guarantee no edge crosses one).

**Objective:**
- Forward Bellman relaxation: each node stores `minimal_cumulative_fuel` and
  `minimal_input_arc`.
- Arc-as-record: edges carry SWS, SOG, Δt, Δd, FCR, fuel for trivial backtrack.
- Terminal selection: min cumulative fuel (hard ETA) or min `fuel + λ · delay⁺` (soft ETA).

**Still open:**
- Heading bucket granularity for H-line placement.
- Weather cell granularity (Open-Meteo 0.1° atmosphere, 0.5° marine, or GFS 0.25°/0.5°?).
- Flow 2 handling when physics inverse says `SWS > v_max` (prune vs clamp + penalty).
- Rolling-horizon replan mechanics on this graph structure.

### 14.16 Implementation Status (2026-04-23)

- `pipeline/dp_rebuild/build_nodes.py` — Stage 1: nodes only. Under default config
  (L=4000 nm, ETA=400 h, dt_h=6 h, ζ=1 nm, τ=0.1 h, 39 H lines at 100 nm intervals +
  1 terminal H line at d=L): **428,108 nodes** (1 source + 268,067 on 67 V lines +
  160,040 on 40 H lines).
- `pipeline/dp_rebuild/build_edges.py` — Stage 2: edges, no weather yet. **6,118,450 edges**,
  avg fan-out 14.43, SOG range exactly `[9.0, 13.0]` kn.
- Convention flipped 2026-04-23 from (H=time, V=distance) to geometric (V=time, H=distance).
  Pure rename; node/edge counts identical before and after.

### 14.17 YAML Integration — Q&A (2026-04-23)

Locked decisions to switch from the 4000/400 toy to the YAML's real route
(`Dynamic speed optimization/weather_forecasts.yaml`, 3393.24 nm, 280 h ETA, 12 segments).

- **Q_yaml_1 — Default size.** Switch default `__main__` to YAML's **3393.24 nm / 280 h**. The
  4000/400 toy is retired in favor of real data.
- **Q_yaml_2 — `current_dir` vs `current_angle`.** Derived duplicates (identical in every
  segment). Keep `current_dir`, drop `current_angle` at load.
- **Q_yaml_3 — Segment 6 duplicate `distance` line.** Typo. Rely on YAML parser behavior
  (last key wins) → 287.34.
- **Q_yaml_4 — Multiple forecast windows.** Populate the structure with multiple 6 h windows
  so the graph exercises time-varying weather from the start, even if the YAML only ships
  with one (0-280) window. Implementation: `synthesize_multi_window(route, window_h=6.0)`
  replicates the single window into multiple equal-length windows; a hook allows injecting
  per-window variation when real multi-window data is available.
- **Q_yaml_5 — Weather-cell sub-H-lines.** Add H lines every 30 nm (marine Open-Meteo cell
  radius) *inside* each segment, all using the same segment weather. Gives the DP more
  decision points without inventing physics. Segment boundaries remain the heading/weather
  decision points; sub-H-lines are purely geometric checkpoints.

### 14.18 H-line Geographic Reconstruction — Q&A (2026-04-28)

Triggered by a quieter issue with the original H-line placement: weather-cell boundaries
were anchored at the *midpoint between adjacent 12 nm interpolated waypoints* whose
(lat, lon) fall in different 0.5° NWP cells. That's a heuristic — only an approximation
of where the route actually crosses a NWP grid line. Goal: replace the heuristic with
real geographic crossings.

- **Qg1 — Segment endpoints (lat, lon).** **(c)** Paper Table 1 — 13 waypoints with
  explicit `(lat°, lon°)`. Loaded into `pipeline/dp_rebuild/route_waypoints.py` along
  with each segment's heading, distance, BN, wind, wave, current. Confirmed match with
  HDF5's first-waypoint-of-each-segment within rounding.
- **Qg2 — Path shape inside a segment.** **(a)** Rhumb line (loxodrome). Constant
  compass bearing, matches the YAML's `ship_heading`. Implemented in
  `geo_grid.rhumb_distance_nm` / `rhumb_bearing_deg`.
- **Qg3 — NWP grid resolution + alignment.** **(a)** 0.5° marine grid axis-aligned at
  integer multiples of 0.5°. Single source of truth for now; can union with finer
  atmosphere grid later.
- **Qg4 — Distance metric for cumulative `d`.** **(a)** Rhumb-line distance. YAML segment
  lengths become a sanity check (within ±1 nm/segment, ±0.4 nm cumulative on the full
  voyage — accumulated paper-rounding).
- **Qg5 — Weather lookup.** **(b)** Per-cell aggregation: one canonical weather row per
  (cell_id, sample_hour). **Deferred** until the geometry was validated visually; will be
  the next change once we cut over from waypoint-midpoint H-lines to grid-crossing H-lines.
- **Qg6 — Implement immediately?** **(b)** No — first build a map-style visualizer to
  confirm crossings translate sanely from globe to (t, d) graph. *Did this; numbers are
  clean (see §15.18).*
- **Qg7 — Visualization scope.** Started with WP1 → WP2 → WP3, extended to full
  12-segment voyage once the math checked out.
- **Qg8 — Map projection.** **(b)** Cartopy / Mercator. Bonus: rhumb lines render as
  straight lines on Mercator, which makes the math visually obvious.

**Implementation status (Qg-set):**

| Done | What |
|---|---|
| ✓ | `route_waypoints.py` with the 13-waypoint table |
| ✓ | `geo_grid.py` rhumb-line + crossing primitives |
| ✓ | `visualize_geo_grid.py` (Mercator chart + (t, d) translation) |
| ✓ | Verified all 12 segments — 152 grid crossings, ±0.2° bearing match, ±0.4 nm cumulative distance |
| TODO | Cut over `build_nodes.h_line_distances_from_h5` → use new `geo_grid` crossings |
| TODO | Per-cell weather aggregation (Qg5(b)) — depends on cut-over |
| TODO | Validator label_at update for new cell semantics |

---

## 15. Graph Rebuild — Implementation Log

Chronological record of the new DP graph construction in `pipeline/dp_rebuild/`. §14 holds
the design spec and Q&A; this section is the running **build log**.

### 15.1 Stage 1 — `build_nodes.py` initial toy (2026-04-22)

- Created `Node` (frozen `(time_h, distance_nm, line_type, is_source, is_sink)`) and
  `GraphConfig` (length, ETA, dt_h, ζ, τ, v_min, v_max).
- Horizontal/vertical line generators; source at (0, 0).
- **Tail policy**: V lines at `[6, 12, ..., 390, 396, 400]` — 66 regular 6 h blocks + one
  shorter 4 h tail ending at ETA.
- **First toy run** (L=4000 nm, ETA=400 h, only time lines, no distance lines):
  67 lines × 4001 nodes + 1 source = **268,068 nodes**.

### 15.2 Course-change H lines every 100 nm (2026-04-22)

- Added `regular_course_change_distances(cfg, spacing_nm=100)` — excludes d=0 and d=L.
- Result: 39 H lines at `[100, 200, ..., 3900]`. Total **424,107 nodes**.

### 15.3 Dense terminal sink column (2026-04-22)

- Per Q9: sink is a full column at d=L, not isolated points. Added d=L to H distances so
  the last H line is dense at τ=0.1 h.
- Result: 40 H lines. Total **428,108 nodes**. 4,068 sink candidates (67 from V-line
  endpoints + 4001 from terminal H line; 67 duplicates at intersections — dedup deferred).

### 15.4 Stage 2 — `build_edges.py` (2026-04-22 → 04-23)

- Created `Edge` (frozen `(src_t, src_d, dst_t, dst_d, sog)`).
- `index_nodes()` groups nodes into `by_v[t]` (sorted by distance) and `by_h[d]` (sorted
  by time).
- `edges_from_source()` emits edges per Q1 + Q7: enumerate candidates on the next V line
  and the next H line; clamp so edges never overshoot the corner (enforces "first
  boundary crossed").
- **Result on the toy**: **6,118,450 edges**, avg fan-out 14.43, SOG exactly
  `[9.0000, 13.0000]`.

### 15.5 Convention flip — geometric V/H labels (2026-04-23)

- Original Q&A labelled time boundaries as "horizontal" and distance boundaries as
  "vertical". The whiteboard's geometric convention is the opposite (x=time, y=distance).
- Renamed throughout both files: `line_type="V"` now means constant-time,
  `line_type="H"` means constant-distance.
- Pure rename. Node count and edge count identical before and after (sanity check).

### 15.6 YAML integration — `load_route.py` (2026-04-23)

- New file `load_route.py` with dataclasses `Segment`, `ForecastWindow`, `Route`.
- Parses the legacy `weather_forecasts.yaml` — drops `current_angle` (Q_yaml_2 duplicate),
  lets YAML parser pick last `distance:` for segment 6 (Q_yaml_3 typo = 287.34).
- `Route.cumulative_segment_endpoints()`, `segment_for_distance()`, `window_for_time()`,
  `weather_at(t, d)`.
- `synthesize_multi_window(route, window_h=6)` replicates the single-window YAML into
  equal-length windows so the graph exercises multi-window infrastructure (Q_yaml_4).
- Loader validated on the YAML: **12 segments, 3393.24 nm, ETA=280 h**; multi-window
  synthesis produces 47 windows (46 × 6 h + 1 × 4 h tail).

### 15.7 `build_nodes.py` rewired for Route (2026-04-23)

- `GraphConfig.from_route(route, **overrides)` — length and ETA flow from the Route,
  everything else configurable.
- `v_line_times_from_route(cfg, route)` = union of `dt_h` cadence + forecast-window
  boundaries. (When `dt_h` matches window length they coincide.)
- `h_line_distances_from_route(cfg, route)` = segment boundaries UNION weather-cell
  sub-lines every `cfg.weather_cell_nm` UNION terminal sink column at d=L (Q_yaml_5).
- Removed the old `regular_course_change_distances` (YAML-driven now).
- Added `weather_cell_nm` (default 30, marine Open-Meteo cell radius) to `GraphConfig`.

### 15.8 `build_edges.py` pointed at the Route (2026-04-23)

- `__main__` now loads the YAML, synthesizes windows, builds nodes from the Route, then
  builds edges. Edge construction logic itself is unchanged (still pure geometric — no
  weather yet).

### 15.9 Current numbers (2026-04-23)

| Metric | Toy (4000/400, uniform 100 nm) | YAML (3393/280, segments + 30 nm cells) |
|---|---|---|
| Forecast windows | 1 | 47 (synthesized 6 h) |
| V lines (time) | 67 | 47 |
| H lines (distance) | 40 | 119 (11 segment + 107 weather-cell sub + 1 terminal) |
| Nodes | 428,108 | **492,885** |
| Edges | 6,118,450 | **3,268,555** |
| Avg fan-out | 14.43 | **6.67** |
| SOG range | [9.0, 13.0] | [9.0, 13.0] |

**Why edge count dropped** despite more nodes: H-line spacing shrank from 100 nm to 30 nm,
so `v* = 30/6 = 5 kn < v_min`. Every source now reaches an H line before reaching the next
V line → smaller fan-out band per source.

**Skew** (2.47 M H-targeted edges vs 0.80 M V-targeted): H lines are now close enough that
almost every source terminates on an H line before hitting the next V line.

### 15.10 What's in place

```
pipeline/dp_rebuild/
  load_route.py     # YAML -> Route (Segment, ForecastWindow, synthesize_multi_window)
  build_nodes.py    # GraphConfig.from_route(), V + H line node emission, sink flags
  build_edges.py    # Edge enumeration under Q1 + Q7; no weather yet
```

### 15.11 What's still missing

- **Weather on edges** — look up `route.weather_at(src_t, src_d)` per edge and store it.
- **SWS inverse + FCR** — `Arc.SWS = inverse(SOG, weather)`, `Arc.FCR = 0.000706 × SWS³`,
  `Arc.fuel = FCR × Δt`.
- **Forward Bellman relaxation** — `node.min_cumulative_fuel`, `node.min_input_arc`;
  backtrack to reconstruct schedule.
- **Terminal selection** — hard ETA (Q9.b) and soft ETA with λ (Q9.c) modes.
- **Visualization** — (t, d) scatter with line overlays, edge sample, sanity-check plots.
- **§14.11 sanity checks** — degenerate lock, zero-weather, lock-monotonicity,
  backtrack fidelity.
- **Sink dedup** — 47 duplicated (t, L) pairs at V × terminal-H intersections; defer to
  edge-construction / DP solve time.
- **Heading-bucket / weather-cell switch to real data** — currently segments are the
  only heading granularity and weather cells are uniform 30 nm placeholders; wire in real
  (lat, lon) → NWP cell lookup when route geometry is available.

### 15.12 Open design questions carried from §14

- **Flow 2 handling** when inverse produces `SWS > v_max` — prune edge vs clamp + penalty.
- **Rolling-horizon** mechanics on this graph structure.
- **Weather cell source** — commit to marine Open-Meteo 0.5° everywhere, or mix sources
  per variable (atmosphere 0.1°, marine 0.5°).
- **Heading bucket size** — currently implicit at the YAML's segment granularity; if we
  move beyond YAML-style routes we need to re-decide.

### 15.13 HDF5 weather integration — `h5_weather.py` (2026-04-23)

- Identified `pipeline/data/voyage_weather.h5` as the Persian Gulf → Malacca weather data
  matching the YAML route. Verified: same route name, same 12 segments, same length (3395.84
  nm HDF5 vs 3393.24 nm YAML — interpolation rounding). Local copy from Feb 16; servers were
  flaky on SSH port 22 so we used the local copy directly.
- Schema: `metadata` (279 waypoints with `node_id, lon, lat, distance_from_start_nm,
  segment`), `actual_weather` (279 × 12 sample-hours), `predicted_weather` (279 × 192
  forecast-hours × 12 sample-hours). Six weather fields per row: wind speed/dir, Beaufort
  number, wave height, ocean current velocity/dir.
- New file `pipeline/dp_rebuild/h5_weather.py` with `VoyageWeather` class exposing:
  - `length_nm`, `waypoints`, `sample_hours`, `forecast_hours`, `route_name`
  - `nearest_waypoint(d)` — O(log n) via `np.searchsorted`
  - `segment_boundaries_nm()` — distances at segment transitions (midpoint between the last
    waypoint of segment *k* and the first waypoint of segment *k+1*; segments don't share a
    boundary waypoint in the HDF5 — e.g. seg 0 ends at 204 nm, seg 1 starts at 223.74 nm)
  - `weather_cell_boundaries_nm(grid_deg=0.5)` — detects NWP grid-cell transitions between
    consecutive waypoints and places the boundary at their midpoint. Parameterised by grid
    resolution: 0.5° marine, 0.25° GFS, 0.1° Open-Meteo atmosphere.
  - `weather_at(d, sample_hour=0, forecast_hour=None)` — `forecast_hour=None` reads
    `actual_weather`, else reads `predicted_weather` at that lead.
- `build_nodes.py`:
  - New helper `h_line_distances_from_h5(cfg, voyage, grid_deg=0.5)`: segment boundaries
    ∪ weather-cell crossings ∪ {terminal at L}.
  - `build_nodes()` now takes an optional `h_line_distances` parameter so callers can
    swap the YAML-derived list for the HDF5-derived list without touching the core.
  - `__main__` runs both paths for comparison.

**Numbers (Persian Gulf → Malacca, L=3393.24 nm, ETA=280 h, dt_h=6, ζ=1, τ=0.1,
v∈[9,13]):**

| Metric | Path A (YAML + uniform 30 nm) | Path B (HDF5 real 0.5° cells) |
|---|---|---|
| H lines | 119 | **138** (11 seg + 126 cells + 1 terminal) |
| Nodes | 492,885 | **546,104** |

The 19 extra H lines in Path B are real marine-grid crossings that didn't land on the
uniform-30-nm multiples of Path A. At 0.25° grid: 230 cell boundaries; at 0.1° atmosphere
grid: 278 (≈ one per waypoint).

Known data caveat: waypoints near Port B (d ≈ 3000 nm) have `nan` for some marine fields
(Malacca coastal proximity is outside Open-Meteo Marine API coverage, per memory). We'll
handle when weather hits edges — probably clamp NaN to neighbouring-waypoint values.

### 15.14 Weather on edges — `build_edges.py` refactor (2026-04-23)

- New `Weather` dataclass (frozen, 6 fields matching `h5_weather.WEATHER_FIELDS`) with
  `from_dict()` constructor and `has_nan()` check.
- `Edge` now carries `weather: Weather` — the source-node snapshot used for later SWS
  inverse + FCR.
- `lookup_source_weather(src, voyage, sample_hour=0, forecast_hour=None)` isolates the
  lookup policy. Default = actual weather at sample_hour 0; switch to predicted weather
  by passing a `forecast_hour` (for RH experiments).
- `build_edges()` now takes `voyage: VoyageWeather` plus `sample_hour` / `forecast_hour`
  params. One HDF5 lookup per source node (not per destination) — O(|nodes| log |wps|)
  total weather queries.
- `edges_from_source()` signature gains `wx: Weather`, passed into every emitted Edge.

**Numbers (Path B, HDF5 real geometry + weather on edges, sample_hour=0):**

| Metric | Value |
|---|---|
| Nodes | 546,104 |
| Edges | **3,344,167** |
| Avg fan-out | 6.16 |
| SOG range | [9.0, 13.0] kn |
| Wind speed range (edges) | 1.94–42.41 kmh (mean 15.44) |
| Wave height range (edges) | 0.08–1.98 m (mean 0.93) |
| Beaufort range (edges) | 1–6 |
| **NaN-weather edges** | **159,435 (4.77%)** — near Port B (Malacca coastal, marine API gap) |

**Topology shift from v13→v14:** the first H line now sits at d = 6 nm (a 0.5° lon cell
boundary detected between Port A at d=0 and the first interpolated waypoint at d=12 nm,
placed at their midpoint). Edges from source therefore span only 6 nm / 6 h → v* = 1 kn,
way below v_min=9. All feasible speeds [9, 13] reach the H line well before the V line,
so source fan-out is constrained by τ = 0.1 h resolution on the destination H line.

**NaN handling (deferred to next stage):** 4.77% of edges carry NaN in wave_height or
similar. Options for when SWS inverse hits these: (a) fall back to nearest-valid waypoint;
(b) use climatology; (c) treat as infeasible and prune. Decide when we wire the physics
inverse in.

### 15.15 File tree (2026-04-23)

```
pipeline/dp_rebuild/
  load_route.py     # YAML -> Route (+ synthesize_multi_window)
  h5_weather.py     # voyage_weather.h5 -> VoyageWeather (segments, cells, weather_at)
  build_nodes.py    # GraphConfig.from_route + V/H line node emission
                    #   (H lines from YAML OR from HDF5 geometry)
  build_edges.py    # Edge(src, dst, sog, weather) enumeration under Q1 + Q7
  validate_graph.py # Structural validator: C1 square uniformity, C2 edge
                    #   weather fidelity, C3 topology basics
```

### 15.16 Structural validator + square-center weather policy (2026-04-23)

- Added `pipeline/dp_rebuild/validate_graph.py` — first of the §14.11
  sanity checks.
- **C1 Square uniformity**: for each pair of adjacent V band × H band,
  samples 25 interior points and verifies every one produces the same
  `(segment_id, weather_cell_id, forecast_window_id)` label. A failure
  here means an H line (segment or cell boundary) or V line (window
  boundary) is missing.
- **C2 Edge weather fidelity**: samples 2000 edges and confirms the
  stored `Weather` equals `voyage.weather_at(enter-square center)`.
- **C3 Topology basics**: source uniqueness, sink placement, SOG ∈
  `[v_min, v_max]`, Δt > 0, Δd > 0, first-line-crossed rule.

**Bug caught and fixed (square-center weather policy).** First run
showed C2 failing on 881/2000 edges (44%). Root cause: a source sitting
exactly on a boundary line (e.g., at `d = 496.97`, the midpoint between
HDF5 waypoints 487.74 and 506.20 → the segment 1/2 boundary) triggered
a `nearest_waypoint` tie; the tie-break picked the left waypoint
(segment 1), but every edge from that source enters the square on the
right (segment 2). Edges stored wrong-side weather.

Fix: `lookup_source_weather` now probes at the **center of the
enter-square**, not at the source's exact coordinates. The center is
always unambiguously inside one segment and one cell, so the weather
read matches the square the edges traverse. Same policy used in C2 →
validator now passes cleanly.

**Validator output (2026-04-23):**

```
  546,104 nodes, 3,344,167 edges, 138 H lines
  [C1] Square uniformity …            PASS (6,486 squares)
  [C2] Edge weather fidelity …        PASS (2000 sampled)
  [C3] Topology basics …              PASS
  Validator exit code: 0
```

**Invariant established**: every edge's `weather` field equals the
weather at the center of the first square it enters. All edges leaving
the same square share that weather (by construction). This is the
weather the SWS inverse + FCR calculation will consume in the next stage.

### 15.17 Locked-mode (Luo-style) edge builder + sanity check (2026-04-26..28)

Added `pipeline/dp_rebuild/build_edges_locked.py` and
`run_demo_locked.py` to compare a Luo-style "one constant SWS per 6 h
block" decision policy against the per-square free DP, on the same node
set.

**Two real bugs caught by the sanity check (`verify_locked_schedule`)**

1. **Snap-drift.** First implementation enumerated SWS at 0.1 kn step,
   simulated each block forward, and snapped the resulting `dst_d` to
   the 1 nm V-line grid. Bellman picked the cheapest = lowest SWS in
   each snap bucket → continuous `final_d` always at the lower edge of
   the bucket → **systematic undershoot of 25.6 nm cumulative** by the
   end of the voyage. Bellman claimed the schedule reached L = 3393.24
   nm in 280 h burning 360.7 mt, but the actual continuous trajectory
   landed at d = 3367.6 nm. Phantom voyage 25 nm short of Port B.

2. **Wrong fuel-time on early-arrival blocks.** Replaced (1) with
   inverse integration: for each `(src, integer-nm dst)` pair, binary-
   search SWS so simulate ends *exactly* at `dst`. First run reported
   the last block's fuel as 156 mt — turned out the formula was
   `FCR × final_t_solved` (absolute time 279.9 h) instead of
   `FCR × (final_t_solved − t_k)` (elapsed time 3.9 h). One-line fix.

**Final clean numbers** (after both fixes):

| Mode | Total fuel | End time | End d |
|---|---|---|---|
| Free DP | 367.561 mt | 280.000 h | 3393.240 nm |
| Locked DP (Bellman) | 366.480 mt | 280.000 h | 3393.240 nm |
| Locked DP (continuous resim) | 366.491 mt | 279.991 h | 3393.240 nm |
| **Δ (locked vs free)** | **−1.081 mt (−0.29 %)** | | |

Continuous resim matches Bellman fuel to 0.01 mt. Per-block drift over
all 47 blocks ≤ 0.12 nm. Trajectory genuinely reaches Port B in 280 h.

**Why locked is *still* slightly under free** (0.29 %): both grids are
discrete, but the locked mode's inverse-search SWS lands each integer-nm
dst exactly, while free-DP's per-edge SOG must round to the (1 nm × 0.1 h)
grid. The residual ~0.3 % gap is grid-resolution noise, not a correctness
bug. Refining the free-DP grid (smaller τ on H lines) should close it.

### 15.18 Geographic H-line reconstruction — exploration (2026-04-28)

Per §14.18 (Qg-set), built `route_waypoints.py`, `geo_grid.py`,
`visualize_geo_grid.py` to compute and visualise where the 12 rhumb-line
segments of the YAML voyage actually cross the 0.5° NWP grid.

**Numbers across all 12 segments**:

| | Total |
|---|---|
| Rhumb sum | 3,393.595 nm |
| Paper sum | 3,393.240 nm |
| Δ | +0.36 nm (+0.01 %) — paper-rounding |
| Bearings vs paper β | match within ±0.2° per segment |
| Grid crossings | 152 (95 lon + 57 lat) |
| + segment-boundary H-lines | 11 |
| + terminal H-line at d = L | 1 |
| **Total H-lines (new)** | **164** |
| Total H-lines (old midpoint policy) | 146 |

The new generator is exact (analytical rhumb-vs-grid intersection on
Mercator) and within 0.4 nm of the paper across the whole voyage.
Per-segment crossing distribution behaves as expected: diagonal
segments produce more crossings, axis-aligned segments fewer.

**Status**: the new generator works as a stand-alone module used by the
visualizer. Cut-over into `build_nodes.h_line_distances_from_h5` is the
next change, alongside the per-cell weather aggregation deferred from
Qg5(b).

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

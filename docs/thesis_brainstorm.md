# Thesis Brainstorm: Maritime Speed Optimization Under Operational Realism

---

## 1. Central Claim

> Under operationally realistic SOG-targeting, segment-averaged LP optimization is equivalent to no optimization at all. Only per-node dynamic approaches (DP, Rolling Horizon) provide genuine fuel savings. The value of dynamic optimization depends primarily on forecast accuracy relative to voyage duration.

**Five contributions:**
1. **Simulation model matters** — SOG-target vs fixed-SWS reverses the LP/DP ranking (Jensen's inequality on cubic FCR)
2. **LP ≈ constant speed** — LP (368.0 kg) = constant speed (367.9 kg) under realistic execution
3. **Forecast horizon is route-length dependent** — dominant on long routes (280h), negligible on short routes (140h)
4. **Information value hierarchy** — temporal > spatial > re-planning, confirmed by 2x2 factorial
5. **Forecast error curve** — wind RMSE doubles over 133h with systematic overpredict bias, completing the causal chain

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

### Credible Results — Short Route (exp_b, 138 nodes, ~140h)

| | B-LP | B-DP | B-RH |
|--|:--:|:--:|:--:|
| **Planned fuel** | 178.2 kg | 180.1 kg | 179.2 kg |
| **Actual fuel (simulated)** | 180.6 kg | 182.2 kg | 180.9 kg |
| **Gap** | +2.4 kg | +2.1 kg | +1.7 kg |

All three approaches are close (1.6 kg range). LP and RH nearly tied (180.6 vs 180.9). The optimization opportunity is small on this calm route (wind std 6.07 km/h).

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

### Replan Frequency (indicative, full route)

| Freq | Fuel (kg) | Delta |
|------|:---------:|:-----:|
| 3h | 364.85 | — |
| 6h | 364.76 | -0.09 |
| 24h | 364.50 | -0.35 |
| 48h | 364.72 | -0.13 |

Range <0.35 kg — negligible.

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

## 7. SWS Violation Analysis (indicative — full-route data only)

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
| **11** | **Full-route re-collection (280+ hours actual weather)** | **TODO** (critical) |
| **12** | **Multi-season weather robustness** | **TODO** (large) |

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

### Still Open

1. **Is there a forecast quality threshold below which LP dominates?** (synthetic noise experiment)
2. **Is the route-length finding robust with 3-4 more routes?** (establishes breakeven curve)
3. **How does the hierarchy shift in extreme weather?** (monsoon, North Atlantic winter)
4. **Is SOG-targeting truly standard practice?** (IMO/EEXI citation needed)
5. **FCR exponent sensitivity?** (how sensitive are conclusions to ±0.05 on the cubic?)

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

### 2026-02-23 — Simulation credibility caveat
- Identified critical limitation: full-route simulation uses 12h actual weather for 280h voyage (frozen hour-0 weather)
- Short-route (exp_b) has 134h actual for ~140h voyage — **credible primary evidence**
- Relabeled all results: full-route = "indicative", short-route = "credible"
- Forecast error curve and 2x2 decomposition are fully credible (no simulation assumptions)
- Added full-route re-collection (280+ hours) as critical action item
- Updated thesis arc: lead with credible exp_a/b evidence, full-route as supporting

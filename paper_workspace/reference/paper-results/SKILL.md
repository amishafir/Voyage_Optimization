# Paper Results Reference

> Quick-reference for all quantitative results. All numbers here are copy-pasteable for paper sections.

## Usage

```
/paper-results
```

## Exp B — Persian Gulf → Malacca (credible, 138 nodes, ~140h, mild weather)

### Main Results

| Approach | Plan Fuel (mt) | Sim Fuel (mt) | Plan→Sim Gap | Violations | vs Optimal |
|---|---|---|---|---|---|
| *Upper bound (SWS=13)* | — | 203.91 | — | — | — |
| **DP** (dynamic det.) | 177.63 | 182.22 | +4.59 (+2.6%) | 17/137 (12.4%) | +5.99 (+3.4%) |
| **LP** (static det.) | 175.96 | 180.63 | +4.67 (+2.7%) | 4/137 (2.9%) | +4.40 (+2.5%) |
| **RH** (rolling horizon) | **175.52** | **176.40** | **+0.88 (+0.5%)** | **1/137 (0.7%)** | **+0.17 (+0.1%)** |
| *Optimal bound (DP w/ actual)* | — | 176.23 | 0% | 0 | — |

### Theoretical Bounds

| Bound | Fuel (mt) | Definition |
|---|---|---|
| Upper | 203.91 | SWS=13 kn at every node |
| Average | 170.06 | Constant SWS = SOG = 11.98 kn (calm water) |
| Optimal | 176.23 | DP with time-varying actual weather (perfect foresight) |
| Span | 27.68 | Upper − Optimal |
| Weather tax | 6.17 | Optimal − Average |

RH captures **99.4%** of optimization span (27.51 of 27.68 mt).

### Ranking Reversal

| Approach | Fixed-SWS Sim | SOG-Target Sim |
|---|---|---|
| LP | **361.8 mt (best)** | 368.0 mt (worst) |
| DP | 367.8 mt (worst) | **366.9 mt (best)** |
| RH | 364.4 mt | 364.8 mt |

### 2×2 Factorial Decomposition

| Config | Nodes | Weather | Approach | Fuel (mt) |
|---|---|---|---|---|
| A-LP | 7 | actual | LP (6 seg) | 178.19 |
| A-DP | 7 | predicted | DP | 181.20 |
| B-LP | 138 | actual | LP (6 seg) | 180.63 |
| B-DP | 138 | predicted | DP | 182.22 |

```
Temporal effect (forecast error):    +3.02 mt  ← largest
Spatial effect (segment averaging):  +2.44 mt
Interaction (spatial mitigates):     -1.43 mt
RH benefit (re-planning):           -1.33 mt
```

### Information Penalty (above optimal)

| Approach | Penalty | Mechanism |
|---|---|---|
| LP | +4.40 mt | Segment averaging (Jensen's inequality) |
| DP | +5.99 mt | Forecast error accumulation |
| RH | +0.17 mt | Near-zero (actual weather injection) |

### Forecast Error Curve (0–133h, ground truth)

| Lead Time | Wind RMSE (km/h) | Wind Bias (km/h) | Wave RMSE (m) | Current RMSE (km/h) |
|---|---|---|---|---|
| 0h | 4.13 | +0.20 | 0.052 | 0.358 |
| 24h | 4.84 | +0.59 | 0.072 | 0.382 |
| 48h | 5.63 | +1.21 | 0.076 | 0.406 |
| 72h | 6.13 | +1.31 | 0.094 | 0.448 |
| 96h | 7.65 | +2.86 | 0.114 | 0.460 |
| 120h | 8.34 | +3.15 | 0.118 | 0.443 |
| 133h | 8.40 | +2.67 | 0.113 | 0.503 |

Wind RMSE doubles (+103%). Systematic positive bias = forecasts overpredict wind.

### NWP Model Cycles

| Parameter | Model | Cycle | % Unchanged Hourly |
|---|---|---|---|
| Wind speed/direction | GFS | 6h | 86% |
| Wave height | MFWAM | 12h | 94% |
| Current velocity/direction | SMOC | 24h | 97% |

GFS propagation delay: ~5h from initialization. Updates at 05/11/17/23 UTC.

### Replan Frequency Sweep

| Frequency | Sim Fuel (mt) | Delta vs 1h | New Info Rate |
|---|---|---|---|
| 1h | 180.63 | baseline | 53% |
| 6h | 180.84 | +0.21 (+0.12%) | 100% |
| 24h | 181.22 | +0.59 (+0.33%) | 100% |

6h is optimal: every decision point gets new data, fuel diff vs 1h is negligible.

### Horizon Sweep — Short Route (exp_b, ~140h voyage)

| Horizon | DP Fuel (mt) | RH Fuel (mt) |
|---|---|---|
| 24h | 177.70 | 176.46 |
| 48h | 177.72 | 176.41 |
| 72h | 177.70 | 176.47 |
| 144h | 177.78 | 176.54 |

Completely flat — even 24h horizon sufficient on short route.

### SWS Violation Analysis

| Approach | Violations | Max Severity | Cause |
|---|---|---|---|
| LP | 4/137 (2.9%) | 13.21 kn | Segment average hides extremes |
| DP | 17/137 (12.4%) | 13.99 kn | Forecast error |
| RH | 1/137 (0.7%) | 13.08 kn | Boundary effect (last decision point) |

### Weather Statistics

| Metric | exp_b |
|---|---|
| Wind speed mean | 16.2 km/h |
| Wind speed std | 6.07 km/h |
| Wave height mean | 0.72 m |
| Wave height std | 0.26 m |

---

## Exp D — St. John's → Liverpool (389 nodes, ~163h, harsh weather)

> **Status: Data collection in progress. Expected complete ~Mar 8.**
> Numbers below will be filled when analysis is run.

### Main Results

| Approach | Plan Fuel (mt) | Sim Fuel (mt) | Plan→Sim Gap | Violations | vs Optimal |
|---|---|---|---|---|---|
| *Upper bound (SWS=13)* | — | ? | — | — | — |
| **DP** | ? | ? | ? | ? | ? |
| **LP** | ? | ? | ? | ? | ? |
| **RH** | ? | ? | ? | ? | ? |
| *Optimal bound* | — | ? | 0% | 0 | — |

### Forecast Error Curve

| Lead Time | Wind RMSE (km/h) | exp_b for comparison |
|---|---|---|
| 0h | ? | 4.13 |
| 24h | ? | 4.84 |
| 48h | ? | 5.63 |
| 72h | ? | 6.13 |
| 96h | ? | 7.65 |
| 120h | ? | 8.34 |

**Hypothesis:** North Atlantic RMSE should be significantly higher.

---

## Generalizability (both routes)

| Finding | exp_b (mild) | exp_d (harsh) |
|---|---|---|
| RH > DP > LP | Yes | ? |
| LP ≈ constant speed | Yes | ? |
| Replan ≈ negligible | Yes | ? |
| Horizon matters | No (flat) | ? |

## Process

When invoked, present these results tables. If any `?` values have been filled (check `paper/sections/06_results.md` or updated brainstorm), show the latest numbers.

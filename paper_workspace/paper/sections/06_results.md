# 6. Results

<!-- ~2,500 words -->
<!-- Contributions carried: C2, C3, C5, C6 -->

This section presents results for both routes: Route 1 (Persian Gulf, mild weather, 138 nodes, ~140 h) and Route 2 (North Atlantic, harsh weather, 389 nodes, ~163 h).

## 6.1 Theoretical Bounds

Three bounds frame the optimization opportunity on each route.

| Bound | Definition | Route 1 (mt) | Route 2 (mt) |
|---|---|---|---|
| Upper | SWS = 13 kn at every node; SOG varies with weather | 203.91 | 239.65 |
| Optimal | DP with time-varying actual weather (perfect foresight) | 176.23 | 216.44 |
| Average | Constant SOG in calm water ($D_{total}/T$) | 170.06 | 198.66 |
| Optimization span | Upper − Optimal | 27.68 | 23.20 |
| Weather tax | Optimal − Average | 6.17 | 17.78 |

The weather tax — the unavoidable cost of operating in non-uniform weather even with a perfect optimizer — is 2.9× larger on Route 2 (17.78 mt vs 6.17 mt), reflecting the substantially harsher North Atlantic conditions (mean wind 46.6 vs 17.4 km/h, mean wave height 5.05 vs 0.82 m). Despite this, the optimization span is slightly smaller on Route 2 (23.20 vs 27.68 mt) because the harsh weather compresses the feasible speed range: at many nodes, even the maximum SWS of 13 kn produces SOG well below the no-weather equivalent, leaving less room for speed variation.

## 6.2 Main Comparison

### Route 1 (Mild Weather)

All three optimizers produce valid schedules with zero SWS violations during planning; violations arise only during simulation when actual weather differs from planning assumptions.

| Approach | Plan (mt) | Sim (mt) | Gap | Violations | vs Optimal |
|---|---|---|---|---|---|
| LP (static det.) | 175.96 | 180.63 | +4.67 (+2.7%) | 4/137 (2.9%) | +4.40 (+2.5%) |
| DP (dynamic det.) | 177.63 | 182.22 | +4.59 (+2.6%) | 17/137 (12.4%) | +5.99 (+3.4%) |
| **RH (rolling horizon)** | **175.52** | **176.40** | **+0.88 (+0.5%)** | **1/137 (0.7%)** | **+0.17 (+0.1%)** |
| Optimal bound | — | 176.23 | 0% | 0 | — |

RH achieved 176.40 mt — within 0.1% of the theoretical optimal (176.23 mt) — capturing 99.4% of the optimization span.

### Route 2 (Harsh Weather)

| Approach | Plan (mt) | Sim (mt) | Gap | Violations | vs Optimal |
|---|---|---|---|---|---|
| LP (static det.) | 208.91 | 215.60 | +6.69 (+3.2%) | 64/388 (16.5%) | −0.84 (−0.4%) |
| DP (dynamic det.) | 222.60 | 214.24 | −8.36 (−3.8%) | 161/388 (41.5%) | −2.20 (−1.0%) |
| **RH (rolling horizon)** | **218.79** | **217.28** | **−1.51 (−0.7%)** | **15/388 (3.9%)** | **+0.84 (+0.4%)** |
| Optimal bound | — | 216.44 | 0% | 0 | — |

The harsh weather amplifies all effects. LP's plan-simulation gap widens to +6.69 mt (+3.2%), and violations increase from 2.9% to 16.5%. DP's violations surge to 41.5% of all legs, with required SWS reaching 14.26 kn — over 1.2 kn above the engine limit. RH maintains the lowest violation rate (3.9%) and the smallest gap magnitude (1.51 mt).

A notable feature of Route 2 is that LP and DP simulated fuel falls *below* the optimal bound (215.60 and 214.24 vs 216.44 mt). This is an artefact of SWS clamping: when the required SWS exceeds 13 kn, the engine is clamped to maximum power, the ship fails to achieve the planned SOG, and arrives late (LP: 163.4 h, DP: 164.5 h vs 163 h ETA). The apparent fuel "savings" are not genuine optimization but reflect the ship consuming less fuel because it could not maintain its planned speed. Only RH arrives near the ETA (163.0 h) with meaningful optimization.

DP exhibits a *negative* plan-simulation gap (−8.36 mt, −3.8%): the plan overestimated fuel because the predicted weather at hour 0 was systematically harsher than the actual weather encountered during the voyage. The forecast's positive wind bias (mean +0.29 km/h at lead 0, growing to +3.31 km/h at lead 96 h) caused the optimizer to plan for headwinds that did not fully materialize.

## 6.3 Ranking Reversal Under SOG-Targeting

The simulation model fundamentally altered the ranking of optimization approaches. This was demonstrated on Route 1 with full-route data:

| Approach | Fixed-SWS (mt) | SOG-Targeting (mt) |
|---|---|---|
| LP | **361.8 (best)** | 368.0 (worst) |
| DP | 367.8 (worst) | **366.9 (best)** |
| RH | 364.4 | 364.8 |

Under fixed-SWS simulation, LP appeared to be the best approach (361.8 mt) and DP the worst (367.8 mt). Under SOG-targeting, the ranking reversed: DP became best (366.9 mt) and LP worst (368.0 mt), equivalent to constant-speed sailing (367.9 mt). The mechanism is Jensen's inequality on the convex cubic FCR: LP assigns one SOG per segment from averaged weather, but maintaining that SOG at individual nodes where weather differs from the average requires SWS adjustments. The cubic relationship ensures that harsh-node penalties always outweigh calm-node savings.

## 6.4 SWS Violation Analysis

### Route 1

During planning, all three optimizers produced schedules with SWS within [11, 13] kn — zero violations by construction. During simulation, violations arose because actual weather at specific nodes differed from the weather used in planning.

| Approach | Violations | Max SWS (kn) | Primary Cause |
|---|---|---|---|
| LP | 4/137 (2.9%) | 13.21 | Segment averaging hides per-node extremes |
| DP | 17/137 (12.4%) | 13.99 | Forecast error accumulates over voyage |
| **RH** | **1/137 (0.7%)** | **13.08** | **Boundary effect at last decision point** |

### Route 2

| Approach | Violations | Max SWS (kn) | Primary Cause |
|---|---|---|---|
| LP | 64/388 (16.5%) | 13.44 | Segment averaging under extreme variability |
| DP | 161/388 (41.5%) | 14.26 | Forecast error in harsh, variable conditions |
| **RH** | **15/388 (3.9%)** | **14.01** | **Residual forecast error between decision points** |

The harsh weather of Route 2 amplifies violation rates across all approaches. LP violations increase from 2.9% to 16.5%: the within-segment weather variability in North Atlantic winter is far larger than in the Persian Gulf, so segment averages are a poorer representation of individual node conditions. DP violations quadruple from 12.4% to 41.5%, with maximum severity exceeding 14 kn — the forecast errors in harsh weather are larger and more consequential. RH violations increase from 1 to 15 (0.7% to 3.9%), still an order of magnitude below DP, confirming that actual weather injection at decision points remains effective even under extreme conditions.

## 6.5 Factorial Decomposition

A 2×2 factorial design on Route 1 isolates the effects of spatial resolution (7 vs 138 nodes) and weather source (actual vs predicted) on fuel outcomes.

| Config | Nodes | Weather | Approach | Sim Fuel (mt) |
|---|---|---|---|---|
| A-LP | 7 | actual | LP (6 seg) | 178.19 |
| A-DP | 7 | predicted | DP | 181.20 |
| B-LP | 138 | actual | LP (6 seg) | 180.63 |
| B-DP | 138 | predicted | DP | 182.22 |
| B-RH | 138 | pred + actual | RH | 176.40 |

Decomposition:

| Factor | Effect (mt) | Mechanism |
|---|---|---|
| Temporal (forecast error) | +3.02 | Largest: predicted weather ≠ actual weather |
| Spatial (segment averaging) | +2.44 | Second: segment averages hide per-node extremes |
| Interaction | −1.43 | Finer spatial resolution partially compensates for forecast error |
| RH benefit (re-planning) | −1.33 | Consistent additional improvement from fresh forecasts |

The information value hierarchy is: temporal freshness > spatial resolution > re-planning frequency. The negative interaction means that per-node predicted weather is closer to per-node actual weather than segment averages are to either — finer spatial resolution partially compensates for forecast error.

This factorial design is available only for Route 1, where a coarse-resolution dataset (Experiment A, 7 nodes) was collected alongside the full-resolution dataset.

## 6.6 Forecast Error Curves

Forecast accuracy was measured by comparing predicted weather at each lead time with actual observations.

| Lead Time (h) | Route 1 Wind RMSE | Route 2 Wind RMSE | Route 1 Wave RMSE | Route 2 Wave RMSE |
|---|---|---|---|---|
| 0 | 4.13 | 6.41 | 0.052 | 0.612 |
| 24 | 4.84 | 9.67 | 0.072 | 0.757 |
| 48 | 5.63 | 10.65 | 0.076 | 0.911 |
| 72 | 6.13 | 12.69 | 0.094 | 1.222 |
| 96 | 7.65 | 14.90 | 0.114 | 1.403 |
| 120 | 8.34 | 19.49 | 0.118 | 2.056 |
| 133/144 | 8.40 | 24.75 | 0.113 | 1.568 |

On Route 1, wind RMSE doubles from 4.13 to 8.40 km/h over 133 h (+103%), with a systematic positive bias (forecast overpredicts wind). On Route 2, wind RMSE nearly quadruples from 6.41 to 24.75 km/h over 144 h (+286%), with the same positive bias pattern but much larger absolute errors. Wave forecast errors show an even starker contrast: Route 2 wave RMSE reaches 2.06 m at 120 h lead time, compared to 0.12 m on Route 1.

The steeper error growth on Route 2 directly explains the larger DP violation rate (41.5% vs 12.4%): the optimizer plans against a forecast that degrades faster and further from reality, producing speed plans that are increasingly inappropriate for the actual conditions encountered.

Both routes show error acceleration after 72 h, consistent with the atmospheric predictability limit. This explains the forecast horizon plateau observed in Route 1 sensitivity analysis: extending the forecast horizon beyond ~72 h provides diminishing returns because the additional forecast data is too inaccurate to improve optimization.

## 6.7 Re-planning Frequency Sweep

<!-- Route 1 results: -->

On Route 1, a sweep across replan frequencies [1, 2, 3, 6, 12, 24] h showed negligible fuel differences:

| Frequency | Sim Fuel (mt) | Delta vs 1 h | Decision Points | New Info Rate |
|---|---|---|---|---|
| 1 h | 180.63 | baseline | 73 | 53% |
| 6 h | 180.84 | +0.21 (+0.12%) | 21 | 100% |
| 24 h | 181.22 | +0.59 (+0.33%) | 6 | 100% |

At 1 h frequency, only 53% of decision points received genuinely different forecasts — the remaining 47% returned identical data from the API. At 6 h, every decision point receives fresh GFS data. The fuel difference between 1 h and 6 h replanning is 0.21 mt (0.12%) — negligible. The 6 h interval is optimal: it matches the GFS model refresh cycle, maximizes new information per decision point, and minimizes computational overhead.

On Route 2, the pattern is even more pronounced:

| Frequency | Sim Fuel (mt) | Delta vs 1 h | Decision Points | New Info Rate |
|---|---|---|---|---|
| 1 h | 217.12 | baseline | 130 | 22% |
| 6 h | 217.28 | +0.15 (+0.07%) | 27 | 100% |
| 24 h | 217.22 | +0.10 (+0.04%) | 7 | 100% |

The fuel range across all frequencies is only 0.50 mt — even smaller than Route 1's range. At 1 h frequency, only 22% of decision points receive new information (compared to 53% on Route 1), because the harsher weather does not change the NWP model update frequency. The 6 h interval remains optimal on both routes.

## 6.8 Generalizability Across Routes

| Finding | Route 1 (mild) | Route 2 (harsh) | Consistent? |
|---|---|---|---|
| RH has fewest violations | 1/137 (0.7%) | 15/388 (3.9%) | Yes — RH lowest on both |
| DP has most violations | 17/137 (12.4%) | 161/388 (41.5%) | Yes — DP highest on both |
| LP gap from segment averaging | +4.67 mt (+2.7%) | +6.69 mt (+3.2%) | Yes — amplified in harsh weather |
| RH near optimal bound | +0.17 mt (+0.1%) | +0.84 mt (+0.4%) | Yes — within 0.5% on both |
| Weather tax | 6.17 mt (3.5% of optimal) | 17.78 mt (8.2% of optimal) | Scales with weather severity |
| Forecast error growth | Wind RMSE +103% over 133 h | Wind RMSE +286% over 144 h | Same pattern, steeper in harsh weather |
| Plan-sim gap: RH smallest | 0.88 mt (0.5%) | 1.51 mt (0.7%) | Yes — consistently smallest |

The core findings are robust across routes: RH consistently achieves the lowest violation rate, the smallest plan-simulation gap, and the closest fuel to the optimal bound. All effects amplify under harsh weather — violations, forecast errors, and the weather tax all increase — but the relative ranking and mechanisms are preserved.

The key route-dependent finding is the magnitude of the DP penalty. On Route 1, DP's information penalty was +5.99 mt (+3.4% above optimal). On Route 2, DP's 161 violations and SWS clamping distort the comparison: the simulated fuel (214.24 mt) falls below the optimal bound because the ship failed to maintain planned speeds and arrived late. This is not a genuine optimization advantage but an artefact of engine limits — a critical distinction for practitioners evaluating these approaches.

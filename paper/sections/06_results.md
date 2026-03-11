# 6. Results

<!-- ~2,000 words -->
<!-- Contributions carried: C2, C3, C5, C6 -->

This section presents results for Route 1 (Persian Gulf, mild weather, 138 nodes, ~140 h voyage). Results for Route 2 (North Atlantic, harsh weather) will be added upon completion of data collection.

## 6.1 Theoretical Bounds

Three bounds frame the optimization opportunity on the Route 1 route.

| Bound | Definition | Fuel (mt) | Violations |
|---|---|---|---|
| Upper | SWS = 13 kn at every node; SOG varies with weather | 203.91 | — |
| Optimal | DP with time-varying actual weather (perfect foresight) | 176.23 | 0 |
| Average | Constant SOG = 11.98 kn in calm water ($D_{total}/T$) | 170.06 | 0 |
| Optimization span | Upper − Optimal | 27.68 | |
| Weather tax | Optimal − Average | 6.17 | |

The optimization span of 27.68 mt represents the total fuel that speed optimization can save relative to maximum-speed sailing. The weather tax of 6.17 mt is the unavoidable cost of operating in non-uniform weather even with a perfect optimizer. Each approach's fuel above the optimal bound constitutes its information penalty — the cost of imperfect weather knowledge or spatial averaging.

## 6.2 Main Comparison

All three optimizers produce valid schedules with zero SWS violations during planning; violations arise only during simulation when actual weather differs from planning assumptions.

| Approach | Plan (mt) | Sim (mt) | Gap | Violations | vs Optimal |
|---|---|---|---|---|---|
| LP (static det.) | 175.96 | 180.63 | +4.67 (+2.7%) | 4/137 (2.9%) | +4.40 (+2.5%) |
| DP (dynamic det.) | 177.63 | 182.22 | +4.59 (+2.6%) | 17/137 (12.4%) | +5.99 (+3.4%) |
| **RH (rolling horizon)** | **175.52** | **176.40** | **+0.88 (+0.5%)** | **1/137 (0.7%)** | **+0.17 (+0.1%)** |
| Optimal bound | — | 176.23 | 0% | 0 | — |

The RH approach achieved 176.40 mt — within 0.1% of the theoretical optimal bound (176.23 mt) — capturing 99.4% of the optimization span (27.51 of 27.68 mt). The plan-simulation gap for RH was 0.88 mt (0.5%), compared to 4.67 mt (2.7%) for LP and 4.59 mt (2.6%) for DP. The near-zero gap confirms that actual weather injection at each decision point effectively eliminates the mismatch between planned and realized conditions.

LP and DP exhibited comparable plan-simulation gaps but from different mechanisms. LP's gap arose from segment averaging: individual nodes within a segment experienced worse conditions than the segment mean, requiring SWS above 13 kn to maintain the planned SOG. DP's gap arose from forecast error: predicted weather at planning time differed from actual weather at simulation time, with the divergence growing over the voyage duration.

## 6.3 Ranking Reversal Under SOG-Targeting

The simulation model fundamentally altered the ranking of optimization approaches.

| Approach | Fixed-SWS (mt) | SOG-Targeting (mt) |
|---|---|---|
| LP | **361.8 (best)** | 368.0 (worst) |
| DP | 367.8 (worst) | **366.9 (best)** |
| RH | 364.4 | 364.8 |

Under fixed-SWS simulation, LP appeared to be the best approach (361.8 mt) and DP the worst (367.8 mt). Under SOG-targeting, the ranking reversed: DP became best (366.9 mt) and LP worst (368.0 mt), equivalent to constant-speed sailing (367.9 mt). The mechanism is Jensen's inequality on the convex cubic FCR: LP assigns one SOG per segment from averaged weather, but maintaining that SOG at individual nodes where weather differs from the average requires SWS adjustments. The cubic relationship ensures that harsh-node penalties always outweigh calm-node savings.

## 6.4 SWS Violation Analysis

During planning, all three optimizers produced schedules with SWS within [11, 13] kn — zero violations by construction. During simulation, violations arose because actual weather at specific nodes differed from the weather used in planning.

| Approach | Violations | Max SWS (kn) | Primary Cause |
|---|---|---|---|
| LP | 4/137 (2.9%) | 13.21 | Segment averaging hides per-node extremes |
| DP | 17/137 (12.4%) | 13.99 | Forecast error accumulates over voyage |
| **RH** | **1/137 (0.7%)** | **13.08** | **Boundary effect at last decision point** |

DP had the most violations (12.4%), with required SWS reaching 13.99 kn — nearly 1 kn above the engine limit. These violations arose because the forecast from hour 0 overpredicted wind speed (positive bias), causing the optimizer to plan for headwinds that did not materialize; the resulting planned SOG was lower than necessary, and the simulation required higher SWS to maintain it under calmer actual conditions.

LP had fewer violations (2.9%) but for a different reason: segment averaging smoothed within-segment extremes, so individual nodes with worse-than-average conditions occasionally required SWS above 13 kn. The maximum severity was mild (13.21 kn, only 0.21 kn above the limit).

RH had a single violation (0.7%) at node 132, where the required SWS was 13.08 kn. This occurred at the last decision point, where the remaining ETA margin was less than 0.1 h and the optimizer fell back to forecast weather for the final legs. This was a boundary effect, not a systematic limitation.

The progression of RH violation reduction through successive design improvements was: DP baseline (17 violations) → RH with forecast only (12) → RH with actual weather at first leg (10) → RH with actual weather for the full 6-hour committed window (1). Each step narrowed the gap between planning assumptions and simulation reality.

## 6.5 Factorial Decomposition

<!-- TODO: Table with 2x2 results -->
<!-- Temporal freshness: +3.02 mt -->
<!-- Spatial resolution: +2.44 mt -->
<!-- Re-planning: -1.33 mt -->
<!-- Information value hierarchy: temporal > spatial > re-planning -->

## 6.6 Forecast Error Curves

<!-- TODO: Wind RMSE doubles from 4.13 to 8.40 km/h over 0-133h -->
<!-- Systematic positive bias -->
<!-- Explains horizon plateau and SWS violation patterns -->

## 6.7 Re-planning Frequency Sweep

<!-- TODO: 1h to 24h sweep -->
<!-- 0.12% fuel difference between 1h and 6h -->
<!-- 86% API redundancy at 1h -->
<!-- 6h = optimal: every call gets fresh GFS data -->

## 6.8 Generalizability Across Routes

<!-- TABLE: findings that hold across both routes — see tables/T12_generalizability.md -->

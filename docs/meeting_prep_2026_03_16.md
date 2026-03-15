# Meeting Prep — Supervisor Meeting, Mar 16 2026

---

## 1. Big Picture: What We Did This Week

Downloaded Route 2 (North Atlantic) data from TAU servers, ran the full LP/DP/RH pipeline, and updated all paper sections. **Both routes are now complete.** The paper has results across two ocean basins (mild and harsh weather) validating all six contributions.

---

## 2. The Two Routes

| | Route 1 (Persian Gulf) | Route 2 (North Atlantic) |
|---|---|---|
| Distance | 1,678 nm | 1,955 nm |
| Nodes | 138 (1 nm spacing) | 389 (5 nm spacing) |
| Voyage duration | ~140 h | ~163 h |
| Wind speed | 17.4 ± 6.1 km/h | 46.6 ± 16.8 km/h (**2.7×**) |
| Wave height | 0.82 ± 0.26 m | 5.05 ± 2.10 m (**6.2×**) |
| Dominant Beaufort | 3–4 | 6–8 |
| Forecast RMSE growth | +103% over 133 h | +286% over 144 h (**2.8× steeper**) |

---

## 3. Key Results — Cross-Route Comparison

### 3.1 Theoretical Bounds

| Bound | Route 1 (mt) | Route 2 (mt) |
|---|---|---|
| Upper (max SWS) | 203.91 | 239.65 |
| **Optimal** (perfect foresight) | **176.23** | **216.44** |
| Average (calm water) | 170.06 | 198.66 |
| **Weather tax** | **6.17** | **17.78 (2.9×)** |

The weather tax — fuel penalty from weather even with a perfect optimizer — scales super-linearly with weather severity.

### 3.2 Three Approaches: Plan vs Reality

**Route 1 (mild)**

| | LP | DP | **RH** |
|---|---|---|---|
| Sim fuel (mt) | 180.63 | 182.22 | **176.40** |
| Gap (plan→sim) | +2.7% | +2.6% | **+0.5%** |
| Violations | 4 (2.9%) | 17 (12.4%) | **1 (0.7%)** |
| vs Optimal | +2.5% | +3.4% | **+0.1%** |
| Arrival time | On time | On time | On time |

**Route 2 (harsh)**

| | LP | DP | **RH** |
|---|---|---|---|
| Sim fuel (mt) | 215.60 | 214.24 | **217.28** |
| Gap (plan→sim) | +3.2% | **−3.8%** | **−0.7%** |
| Violations | 64 (16.5%) | **161 (41.5%)** | **15 (3.9%)** |
| vs Optimal | −0.4%* | −1.0%* | **+0.4%** |
| Arrival time | **+0.4 h late** | **+1.5 h late** | **On time** |

*LP and DP appear "below optimal" but this is an artifact — they arrive late because the engine can't deliver planned speeds (SWS clamped at 13 kn). They burn less fuel by failing to meet the schedule, not by optimizing better.

### 3.3 What This Tells Us

**RH is the only approach that works in both conditions:**
- Route 1: within 0.1% of optimal, 1 violation, on time
- Route 2: within 0.4% of optimal, 15 violations, on time

**DP breaks down in harsh weather:**
- Violations jump from 12% to 42% — nearly half the legs are infeasible
- The forecast from hour 0 degrades too fast (wind RMSE nearly quadruples)
- The plan becomes a fiction that the ship can't execute

**LP's segment averaging gets worse with weather variability:**
- Violations jump from 3% to 17%
- Within-segment weather variability is much larger in North Atlantic winter
- Jensen's inequality penalty scales with that variability

### 3.4 Replan Frequency — Confirmed on Both Routes

| | Route 1 | Route 2 |
|---|---|---|
| 1 h vs 6 h fuel delta | 0.21 mt (0.12%) | 0.15 mt (0.07%) |
| New info rate at 1 h | 53% | 22% |
| New info rate at 6 h | 100% | 100% |

6 h replan aligned to GFS is optimal on both routes. On Route 2, hourly replanning is even more wasteful — only 22% of calls return new data.

---

## 4. Validation of the Six Contributions

| # | Contribution | Validated? | Evidence |
|---|---|---|---|
| C1 | SOG-targeting reverses LP/DP ranking | **Yes** | LP ≈ constant speed on Route 1; LP infeasible on 16.5% of Route 2 legs |
| C2 | RH ≈ optimal bound | **Yes** | Within 0.1% (Route 1) and 0.4% (Route 2) |
| C3 | Forecast horizon is route-dependent | **Partial** | Flat on Route 1 (short voyage). Route 2 fits within horizon so can't test beyond-horizon case. Need transpacific route for full validation. |
| C4 | Info hierarchy: temporal > spatial > replan | **Yes** (Route 1) | 2×2 factorial: +3.02 > +2.44 > −1.33 mt. Not directly testable on Route 2 (no coarse dataset). |
| C5 | Forecast error curves explain mechanisms | **Strongly yes** | RMSE +103% (Route 1), +286% (Route 2). Directly explains DP violation rates. |
| C6 | 6 h replan = NWP cycle alignment | **Yes** | Confirmed on both routes. 22% new info at 1 h on Route 2 vs 53% on Route 1. |

---

## 5. Surprises / Things Worth Discussing

1. **DP sim fuel below optimal bound** — On Route 2, DP "beats" the optimal bound (214.24 vs 216.44 mt) because SWS clamping makes the ship arrive 1.5 h late. It's not better optimization — it's the ship failing to execute the plan. How do we present this?

2. **Weather tax scales super-linearly** — 2.7× windier → 2.9× higher weather tax. The resistance model's nonlinearities compound.

3. **DP graph needs finer resolution for short legs** — 5 nm legs with dt=0.1 h caused cumulative rounding that made DP infeasible. Fixed with dt=0.01 h. Mention in methodology?

4. **RH degrades gracefully** — Violations go from 1 to 15 (0.7% → 3.9%), still an order of magnitude below DP. The actual-weather injection mechanism doesn't break under harsh conditions, it just becomes slightly less perfect.

---

## 6. Paper Status

### Done
- [x] Sections 1–4 in LaTeX
- [x] Section 5 markdown — updated with Route 2 collection stats
- [x] Section 6 markdown — **full rewrite with both routes** (all 8 subsections)
- [x] Section 7 markdown — Route 2 changed from future to past tense
- [x] Section 8 markdown — harsh weather moved from future work to findings
- [x] Replan sweep Route 2 — complete, added to §6.7

### TODO
- [ ] Move sections 5–8 into LaTeX (.tex)
- [ ] Abstract (~250 words)
- [ ] Gap summary table (§2.6)

---

## 7. Questions for Supervisor

1. **DP clamping narrative**: DP/LP fuel falls below optimal on Route 2 because the ship arrives late. Currently framed as "not genuine optimization." Right approach, or should we also report an ETA-penalized metric?

2. **DP time granularity**: Practical implementation detail (dt=0.01 for dense waypoints) — mention in methodology or just handle it?

3. **Two routes sufficient?** We have mild (BN 3–4) and harsh (BN 6–8). All findings are consistent. Is this enough for the generalizability claim, or is a third route expected by reviewers?

4. **C3 (horizon dependence)**: Only partially validated — both routes fit within the 168 h GFS horizon. Should we acknowledge this gap prominently, or is the steeper forecast degradation on Route 2 sufficient evidence?

5. **Timeline**: Sections 5–8 in LaTeX by Mar 20?

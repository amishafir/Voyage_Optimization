# Meeting Prep — Supervisor Meeting, Mar 9 2026

---

## Progress Since Last Meeting (Mar 2)

### 1. Server reboot recovery & dual-server redundancy ✅

**Problem:** Shlomo1 rebooted on Feb 26, killing both collection processes. Discovered Mar 2 — 4-day data gap made pre-gap hours unusable for exp_c and exp_d.

**Resolution:**
- Restarted collection on shlomo1 (exp_b, exp_c, exp_d)
- Deployed pipeline to **shlomo2** as redundancy (exp_b, exp_c, exp_d)
- All 6 processes running in tmux sessions across both servers

| Experiment | shlomo1 | shlomo2 |
|---|---|---|
| exp_b (Persian Gulf, 131 nodes) | Running | Running |
| exp_c (Yokohama→LB, 947 nodes) | Running | Running |
| exp_d (St. John's→Liverpool, 389 nodes) | Running | Running |

If either server goes down, all experiments continue on the other.

### 2. Experiment D — St. John's → Liverpool (expected complete)

**Status:** Collection started Mar 2, needed ~163 continuous hours (~6.8 days). **Should be complete by this meeting.**

- Route: 1,955 nm, 389 nodes at 5nm spacing
- Usable data: hours 29+ (post-gap, continuous from Mar 2)
- Weather: North Atlantic storm track, winter BN 8–10, waves 4–6m mean

**Analysis to present (pending data verification):**

| Analysis | Description | Status |
|---|---|---|
| LP / DP / RH comparison | Same 3-approach comparison as exp_b, on harsh weather | TODO |
| Replan frequency sweep | Does 6h remain optimal on stormy route? | TODO |
| Forecast error vs lead time | RMSE curves for wind/wave/current on North Atlantic data | TODO |
| DD vs RH fuel gap | Quantify freshness-only advantage (DD has full 168h coverage) | TODO |
| Violation count | Does harsh weather increase SWS violations? | TODO |

### 3. Experiment B — Persian Gulf → Malacca (fresh re-collection)

**Status:** Fresh collection started Mar 2 on both servers. ~163 hours collected by this meeting.

- Same route as original exp_b (131 nodes at 25nm), but fresh weather data
- Provides a second independent dataset on the original route for result validation
- Can compare March weather vs February weather on the same route

### 4. Experiment C — Yokohama → Long Beach (in progress)

**Status:** Needs ~408 continuous hours (~17 days). About 168 hours collected by this meeting (~41%).

- Usable data: hours 46+ (shlomo1), hours 0+ (shlomo2)
- Partial analysis possible with ~7 days of data (covers the DD forecast horizon)
- Full data expected ~**Mar 19**

### 5. API quota crisis & bulk collection refactor (Mar 4) ✅

**Problem:** All 6 collection processes hit Open-Meteo daily API quota limits. The per-node approach made 2 API calls per node per sample (1 wind + 1 marine). For exp_c alone, that's ~1,894 calls per sample hour, ~45,456 calls/day with hourly collection — far exceeding the free tier.

**Root cause:** Two independent multiplicative problems:
1. **Per-node API calls**: N nodes × 2 endpoints = O(N) calls per sample
2. **Hourly sampling**: NWP models only update every 6h, so ~86% of hourly samples return identical data

**Solution — two optimizations stacked:**

| Optimization | Mechanism | Reduction |
|---|---|---|
| **Bulk multi-location API** | Comma-separated lat/lon in one request; chunked at 100 locations to avoid URI limits | ~1,894 → ~20 calls/sample (exp_c) |
| **6h NWP-aligned sampling** | Collect every 6h aligned to GFS cycle arrival (05/11/17/23 UTC) | 24 → 4 samples/day |
| **Combined** | | **~45,456 → ~80 calls/day** (99.8% reduction) |

Deployed to all 6 sessions across both servers. Collection resumes from last completed sample hour (resume-aware HDF5).

**API call budget (per experiment per day):**

| Experiment | Nodes | Chunks (×100) | Calls/sample (wind + marine) | Samples/day | Calls/day |
|---|---|---|---|---|---|
| exp_b | 138 | 2 | 4 | 4 | **16** |
| exp_c | 947 | 10 | 20 | 4 | **80** |
| exp_d | 389 | 4 | 8 | 4 | **32** |

Both servers combined: ~256 calls/day total. Well within free tier (~10,000/day).

### 6. Literature review — next steps

22 articles filed across 6 pillars (completed Mar 2). Potential work this week:

- [ ] Begin narrative literature review chapter draft
- [ ] Identify remaining gaps (target: 30–35 articles total)
- [ ] Add 2–3 more Pillar 5 (rolling horizon) papers — currently weakest at 3 articles

---

## Data Collection Status (updated Mar 5, 18:00)

### Second server reboot (Mar 5)

Both Shlomo1 and Shlomo2 rebooted again on Mar 5 (~17:30). All 6 tmux sessions killed. Restarted all processes at 18:00 using `~/miniconda3/bin/python3` (system Python 3.7 lost packages on reboot; miniconda Python 3.13/3.11 has all deps).

**HDF5 data is preserved** — collection scripts are resume-aware and append to existing files. No data lost, only a ~12h gap (last write 07:00 Mar 5, restart 18:00 Mar 5 = 2 missed 6h samples).

### Verified HDF5 contents (Shlomo1, best copy, Mar 5 18:00)

| Experiment | Actual Hours | Range | Predicted Hours | Range | HDF5 Size | Gaps |
|---|---|---|---|---|---|---|
| **exp_b** | **166** | 0–195 | 154 | 0–195 | 50 MB | None >6h |
| **exp_d** | **86** | 0–115 | 63 | 0–77 | 53 MB | None >6h |
| **exp_c** | **103** | 0–132 | 82 | 0–94 | 146 MB | None >6h |

### Completion projections (by Mar 9 meeting)

| Experiment | Voyage Duration | Current Hours | +84h by Mar 9 | Status |
|---|---|---|---|---|
| **exp_b** | ~163h | **166h** | — | **COMPLETE — ready for analysis** |
| **exp_d** | ~163h | **86h** | ~170h | **Should be complete ~Mar 8** |
| **exp_c** | ~408h | **103h** | ~187h | **~46% — partial analysis possible** (covers 168h DD horizon) |

### Shlomo2 (backup copy)

| Experiment | Actual Hours | HDF5 Size |
|---|---|---|
| exp_b | 36 | 8.6 MB |
| exp_d | 36 | 24 MB |
| exp_c | 36 | 50 MB |

Shlomo2 started later (Mar 3) and has less data. Shlomo1 is the primary copy for all experiments.

---

## Presentation Structure

### Part 1: Methodology — How Each Approach Uses Data

Explain the two-phase evaluation framework before showing any numbers.

**Phase 1 — Planning: each optimizer sees different weather**

| Approach | Weather Source | Spatial Resolution | Temporal Info | Re-planning |
|---|---|---|---|---|
| **LP** (static det.) | **Actual** at hour 0 | 6 segment averages (~23 nodes each) | Single snapshot | None |
| **DP** (dynamic det.) | **Predicted** from forecast origin 0 | Per-node | Time-varying forecast | None |
| **RH** (rolling horizon) | **Predicted** + **actual** at each 6h decision point | Per-node | Fresh forecast every 6h; actual weather for committed 6h window | Every 6h |

Key points to explain:
- LP sees **real** weather but spatially smoothed → Jensen's inequality on cubic FCR penalizes averaging
- DP sees **forecast** weather at full resolution → forecast degrades with lead time (RMSE doubles over 133h)
- RH sees **forecast** refreshed every 6h + **actual** injected for committed window → plans match reality
- All three produce zero SWS violations at planning time

**Phase 2 — Simulation: testing plans against reality**

| Approach | Simulation Weather | Mode | Why |
|---|---|---|---|
| **LP** | Actual at hour 0 | Static | Plans against single temporal reference → simulate against same reference |
| **DP** | Actual at hour 0 | Static | Same — isolates forecast-error effect |
| **RH** | Actual at each leg's transit time | Time-varying | Plans each 6h window at that decision time → simulate against matching conditions |

**How violations arise:**
```
Plan:  optimizer picks SOG → implies SWS under planning weather
Sim:   simulator targets that SOG → computes required SWS under actual weather
       If required SWS ∉ [11, 13] kn → clamped → violation
```

### Part 2: Bounds — Framing the Optimization Opportunity

Present for each experiment to frame how much fuel is at stake.

**Template (fill with actual numbers):**

| Bound | Definition | exp_b | exp_d |
|---|---|---|---|
| **Upper bound** | SWS = 13 kn (max engine) at every node, SOG varies with weather. No optimization. | 203.91 mt | ? |
| **Average bound** | Constant SWS = SOG = distance/ETA. Theoretical floor — Jensen's inequality means any speed variation increases fuel. | 170.06 mt | ? |
| **Optimal bound** | DP with time-varying actual weather (perfect foresight). Best achievable under real weather. | 176.23 mt | ? |
| **Optimization span** | Upper − Optimal. The total fuel that optimization can save. | 27.68 mt | ? |
| **Weather tax** | Optimal − Average. Unavoidable cost of non-uniform weather, even with perfect optimizer. | 6.17 mt | ? |

### Part 3: Results — Plan vs Simulation per Approach

**Main results table (like the image, expanded with plan column):**

#### Exp B — Persian Gulf → Malacca (138 nodes, ~140h, mild weather)

| Approach | Plan Fuel (mt) | Sim Fuel (mt) | Plan→Sim Gap | Violations | vs Optimal |
|---|---|---|---|---|---|
| *Upper bound (SWS=13)* | — | 203.91 | — | — | — |
| **DP** (dynamic det.) | 177.63 | 182.22 | +4.59 (+2.6%) | 17/137 (12.4%) | +5.99 (+3.4%) |
| **LP** (static det.) | 175.96 | 180.63 | +4.67 (+2.7%) | 4/137 (2.9%) | +4.40 (+2.5%) |
| **RH** (rolling horizon) | **175.52** | **176.40** | **+0.88 (+0.5%)** | **1/137 (0.7%)** | **+0.17 (+0.1%)** |
| *Optimal bound (DP w/ actual)* | — | 176.23 | 0% | 0 | — |

Key takeaways:
- RH captures **99.4%** of optimization span (27.51 of 27.68 mt)
- RH plan-sim gap is near zero (+0.5%) — plans match reality because of actual weather injection
- LP and DP have comparable gaps (~2.6%) from different causes: LP = segment averaging, DP = forecast error
- DP has the most violations (12.4%) — stale forecast is the dominant violation source

#### Exp D — St. John's → Liverpool (389 nodes, ~163h, harsh weather)

| Approach | Plan Fuel (mt) | Sim Fuel (mt) | Plan→Sim Gap | Violations | vs Optimal |
|---|---|---|---|---|---|
| *Upper bound (SWS=13)* | — | ? | — | — | — |
| **DP** (dynamic det.) | ? | ? | ? | ? | ? |
| **LP** (static det.) | ? | ? | ? | ? | ? |
| **RH** (rolling horizon) | **?** | **?** | **?** | **?** | **?** |
| *Optimal bound (DP w/ actual)* | — | ? | 0% | 0 | — |

**Hypotheses for exp_d vs exp_b:**
- Larger optimization span (more weather variability → more fuel at stake)
- Larger RH advantage (higher wind RMSE → more room for forecast freshness to help)
- More SWS violations across all approaches (harsher conditions)
- Plan-sim gaps may increase for LP/DP but stay low for RH

### Part 4: Information Penalty Decomposition

Show how much fuel each "information limitation" costs above the optimal bound:

| Information Penalty | Mechanism | exp_b | exp_d |
|---|---|---|---|
| **Segment averaging** (LP) | Jensen's inequality on cubic FCR — averaging hides per-node extremes | +4.40 mt | ? |
| **Forecast error** (DP) | Predicted ≠ actual — errors accumulate over voyage | +5.99 mt | ? |
| **Near-zero** (RH) | Actual weather injection eliminates most penalty | +0.17 mt | ? |

From 2x2 factorial (exp_b):
```
Temporal effect (forecast error):    +3.02 mt  ← largest
Spatial effect (segment averaging):  +2.44 mt
Interaction (spatial mitigates):     -1.43 mt
RH benefit (re-planning):           -1.33 mt
```

### Part 5: Forecast Error Curves

Compare forecast accuracy across ocean basins — direct ground-truth comparison, no simulation assumptions.

| Lead Time | exp_b Wind RMSE (km/h) | exp_d Wind RMSE (km/h) |
|---|---|---|
| 0h | 4.13 | ? |
| 24h | 4.84 | ? |
| 48h | 5.63 | ? |
| 72h | 6.13 | ? |
| 96h | 7.65 | ? |
| 120h | 8.34 | ? |
| 133h | 8.40 | ? |

**Expected:** North Atlantic RMSE should be significantly higher (stormier, more variable). This directly explains any larger RH advantage on exp_d.

### Part 6: Exp B Reproducibility — February vs March

Side-by-side comparison of the same route under different weather conditions.

| Metric | exp_b Feb | exp_b Mar |
|---|---|---|
| Wind std (km/h) | 6.07 | ? |
| Wave std (m) | 0.26 | ? |
| RH sim fuel (mt) | 176.40 | ? |
| LP sim fuel (mt) | 180.63 | ? |
| DP sim fuel (mt) | 182.22 | ? |
| RH vs LP saving | 2.3% | ? |
| RH vs DP saving | 3.2% | ? |
| Hierarchy RH > DP > LP | Yes | ? |

If hierarchy and magnitudes are consistent → result generalizes. If different → seasonal sensitivity finding.

### Part 7 (if time): Exp C Early Signal

~187h of 408h voyage collected. Partial analysis showing:
- Forecast error curves for North Pacific (third ocean basin)
- The point where DD forecast coverage ends (~168h) — what happens to DP accuracy beyond this?

---

### Risk: server stability

Two reboots in 8 days (Feb 26, Mar 5). If servers go down again before Mar 8, exp_d won't be complete. exp_b is safe (already done). Consider mentioning server reliability issue to supervisor — may need IT intervention or alternative infrastructure.

---

## Questions for Discussion

1. **Exp B reproducibility:** Do March results confirm February findings? If the hierarchy (RH > DP > LP) and magnitudes are consistent, this significantly strengthens the thesis.

2. **Exp D results** (if ready): What's the RH advantage on harsh weather? Is 6h replan still optimal, or does storm variability favor more frequent replanning?

3. **Partial exp_c analysis:** With ~7 days of data available, should we run a partial analysis to get early signal on the beyond-horizon effect?

4. **Server reliability:** Two reboots in 8 days. Should we explore alternative hosting (cloud VM, university HPC) for the remaining ~10 days of exp_c collection?

5. **Literature review chapter:** Should we start drafting the narrative now, or wait until exp_c/d results inform which papers to emphasize?

6. **Thesis timeline:** With exp_b done, exp_d expected Mar 8, and exp_c at ~Mar 22 (revised due to reboots), what's the realistic target for a complete results chapter draft?

# Meeting Prep — Supervisor Meeting, Mar 9 2026

---

## 1. Server & Collection Status (updated Mar 9, 11:30 UTC)

### What happened since Mar 2

- **Shlomo1**: Down since Mar 8. All data on it inaccessible.
- **Shlomo2**: Persistent Open-Meteo rate limiting — most collection cycles failed. exp_c (947 waypoints) never got a single successful predicted weather sample.
- **exp_c removed**: The Yokohama→Long Beach route is too large for Open-Meteo's free tier. Dropped from all servers.
- **Edison** (`edison-pc.eng.tau.ac.il`): New server deployed today. Fresh IP, first cycle completed successfully.

### What's running now

| Server | Experiments | Current Hour | Status |
|---|---|---|---|
| **Edison** | exp_b, exp_d | 6 | Collecting cleanly (131/131, 389/389 OK) |
| **Shlomo2** | exp_b, exp_d | 24 | Now collecting cleanly after exp_c removed (131/131, 389/389 OK) |
| **Shlomo1** | — | — | Idle (online, available as backup) |

### When data is ready

| Experiment | Best Server | Current Samples | Samples Needed | Ready Date |
|---|---|---|---|---|
| **exp_b** (Persian Gulf → Malacca, 131 wp) | Shlomo2 (24h head start) | 4 | 24 (144h) | **~Mar 15** |
| **exp_d** (St. John's → Liverpool, 389 wp) | Shlomo2 (24h head start) | 5 | 28 (168h) | **~Mar 16** |

Edison provides a fully gap-free backup for both experiments.

### Risk

Four incidents in two weeks (Feb 26 reboot, Mar 5 reboot, Mar 8 Shlomo1 down, Shlomo2 rate limits). Now mitigated with 2 active servers + 1 standby.

---

## 2. Exp B Results (from Shlomo1 data, pre-crash)

### Bounds

| Bound | Definition | Fuel (mt) |
|---|---|---|
| **Upper bound** | SWS = 13 kn everywhere, no optimization | 203.91 |
| **Average bound** | Constant speed = distance/ETA (Jensen floor) | 170.06 |
| **Optimal bound** | DP with actual weather (perfect foresight) | 176.23 |
| **Optimization span** | Upper − Optimal | 27.68 |
| **Weather tax** | Optimal − Average | 6.17 |

### Three-approach comparison

| Approach | Plan Fuel (mt) | Sim Fuel (mt) | Plan→Sim Gap | Violations | vs Optimal |
|---|---|---|---|---|---|
| *Upper bound (SWS=13)* | — | 203.91 | — | — | — |
| **DP** (dynamic det.) | 177.63 | 182.22 | +4.59 (+2.6%) | 17/137 (12.4%) | +5.99 (+3.4%) |
| **LP** (static det.) | 175.96 | 180.63 | +4.67 (+2.7%) | 4/137 (2.9%) | +4.40 (+2.5%) |
| **RH** (rolling horizon) | **175.52** | **176.40** | **+0.88 (+0.5%)** | **1/137 (0.7%)** | **+0.17 (+0.1%)** |
| *Optimal bound (DP w/ actual)* | — | 176.23 | 0% | 0 | — |

Key takeaways:
- RH captures **99.4%** of optimization span (27.51 of 27.68 mt)
- RH plan-sim gap near zero (+0.5%) — actual weather injection keeps plans aligned with reality
- LP and DP have comparable gaps (~2.6%) from different causes: LP = segment averaging, DP = forecast error
- DP has the most violations (12.4%) — stale forecast is the dominant violation source

---

## 3. Literature Review

22 articles filed across 6 pillars. Next steps:

- [ ] Begin narrative literature review chapter draft
- [ ] Identify remaining gaps (target: 30–35 articles total)
- [ ] Add 2–3 more Pillar 5 (rolling horizon) papers — currently weakest at 3 articles

---

## 4. Paper Sections 5–8: Summary and Direction

### What we set out to prove

1. **Real-time weather collection and optimization every 6 hours is feasible and transformative.** We built an automated pipeline that collects live NWP forecasts (GFS wind, MFWAM waves, SMOC currents) via the Open-Meteo API every 6 hours — aligned with the GFS initialization cycle — and runs full optimization on each fresh forecast. This operational capability is a major innovation: no prior maritime speed optimization study has demonstrated a system that ingests real forecast updates and re-optimizes in real time. The infrastructure itself is a contribution.

2. **Rolling horizon with 6h re-planning dominates all static approaches.** RH captures 99.4% of the optimization span (27.51 of 27.68 mt) and comes within 0.1% of the theoretical optimal bound. The mechanism: every 6h decision point injects *actual* weather for the committed window, so the ship never executes a plan based on stale data.

3. **SOG-targeting reveals a ranking reversal invisible to the prior literature.** Under fixed-SWS simulation (what everyone else uses), LP looks best. Under SOG-targeting (what ships actually do), LP's segment averaging triggers Jensen's inequality on the cubic FCR, inflating realized fuel. DP and RH, operating at node-level resolution, avoid this bias.

4. **Forecast error propagation is measurable and method-dependent.** Wind RMSE doubles from 4.1 to 8.4 km/h over 133h lead time. LP is insensitive (plans on averages anyway); DP degrades with lead time; RH resets the error every 6h by re-planning on fresh data.

### Experimental setup (Section 5)

- **Data source:** Open-Meteo API — GFS (wind, 6h cycle), MFWAM (waves, 12h), SMOC (currents, 24h)
- **exp_b:** Persian Gulf → Indian Ocean, 1,678 nm, 138 nodes, mild weather (BN 3–4). 134 hourly samples collected. Near-complete voyage coverage (96%).
- **exp_d:** St. John's → Liverpool, 1,955 nm, 389 nodes, North Atlantic winter (expected BN 8–10). Collection in progress — 6h NWP-aligned sampling.
- **Key empirical finding:** At 1h collection, 86% of API calls return identical data. 6h sampling captures every GFS update with zero information loss and 83% fewer calls. This directly motivates the RH re-planning interval.
- **2×2 factorial:** (7 vs 138 nodes) × (actual vs predicted weather) decomposes temporal freshness (+3.02 mt) vs spatial resolution (+2.44 mt) vs re-planning (−1.33 mt).

### Results (Section 6) — exp_b numbers

| Metric | LP | DP | RH | Optimal |
|---|---|---|---|---|
| Plan fuel (mt) | 175.96 | 177.63 | 175.52 | — |
| Sim fuel (mt) | 180.63 | 182.22 | 176.40 | 176.23 |
| Plan→Sim gap | +2.7% | +2.6% | +0.5% | 0% |
| SWS violations | 4/137 (2.9%) | 17/137 (12.4%) | 1/137 (0.7%) | 0 |
| vs Optimal | +4.40 mt | +5.99 mt | +0.17 mt | — |

- **Optimization span:** 27.68 mt (upper 203.91 − optimal 176.23)
- **Weather tax:** 6.17 mt (optimal − calm-water floor)
- RH captures 99.4% of span; LP and DP capture ~84% and ~79% respectively

### Discussion (Section 7) — mechanisms

- **Jensen's inequality mechanism (C1):** LP assigns one SOG per segment → SWS varies within segment under SOG-targeting → cubic FCR amplifies variation → systematic fuel overrun. DP assigns per-node, avoiding this.
- **Information value hierarchy (C4):** Temporal freshness (+3.02 mt) > spatial resolution (+2.44 mt) > re-planning frequency (−1.33 mt). Forecast quality matters more than node count.
- **Weather tax vs information penalty:** The 6.17 mt weather tax is unavoidable (non-uniform weather). The information penalty varies: LP +4.40 (averaging), DP +5.99 (forecast staleness), RH +0.17 (near-zero).
- **Route-length dependence (C3):** When voyage fits within accurate forecast window (~72h), horizon length barely matters. When it exceeds the window, RH's periodic refresh becomes critical.
- **Limitations:** Mild weather on exp_b (effects may be larger under harsh conditions — exp_d will test this); single ship type; cubic FCR assumed not validated against engine data; two routes only.

### Conclusion (Section 8) — recommendations

- **Use RH with 6h re-planning aligned to GFS cycles.** Near-optimal fuel at near-zero computational cost increment.
- **SOG-targeting simulation is essential** for valid method comparison. Fixed-SWS evaluation hides the LP ranking reversal.
- **Future work:** exp_d (harsh weather), FCR exponent sensitivity analysis, forecast quality threshold where LP might dominate, multi-season robustness.

---

## Questions for Discussion

1. **exp_b/d timeline**: Data ready Mar 14–15. Realistic to have results chapter draft by Mar 20?
2. **exp_c**: Dropped due to API limits. Is 2 experiments (2 routes, 2 ocean basins) sufficient for the thesis, or do we need a third?
3. **Literature review**: Start narrative draft now, or wait for exp_d results?
4. **Real-time pipeline as contribution**: Should we frame the 6h collection+optimization infrastructure as a standalone contribution, or keep it as part of the RH methodology?

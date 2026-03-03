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

### 5. Literature review — next steps

22 articles filed across 6 pillars (completed Mar 2). Potential work this week:

- [ ] Begin narrative literature review chapter draft
- [ ] Identify remaining gaps (target: 30–35 articles total)
- [ ] Add 2–3 more Pillar 5 (rolling horizon) papers — currently weakest at 3 articles

---

## Data Collection Status (as of Mar 9)

| Experiment | Route | Nodes | Usable Start | Hours by Mar 9 | Hours Needed | Complete? |
|---|---|---|---|---|---|---|
| **exp_b** | Persian Gulf → Malacca | 131 | hour 0 | ~163 | ~163 | ~Yes |
| **exp_c** | Yokohama → Long Beach | 947 | hour 46 (s1) / hour 0 (s2) | ~168 | ~408 | ~41% |
| **exp_d** | St. John's → Liverpool | 389 | hour 29 | ~163 | ~163 | ~Yes |

---

## Expected Key Results

### Exp D: Freshness-only RH advantage

Exp D is designed so DD has full forecast coverage (168h horizon ≥ 163h voyage). Any RH advantage comes purely from **forecast freshness** — using updated weather at each 6h decision point vs the single stale forecast DD relies on.

**Hypothesis:** RH advantage should be **larger** than on exp_b (mild weather) because:
- Higher wind variability → forecast errors are larger → more room for RH to correct
- Larger wave heights → stronger added resistance → forecast errors have bigger fuel impact
- More weather changes within the voyage → more decision points where fresh data matters

**Comparison with exp_b results:**

| Metric | exp_b (Persian Gulf, mild) | exp_d (North Atlantic, harsh) |
|---|---|---|
| RH vs LP fuel saving | 2.3% | ? |
| RH vs DP fuel saving | 3.2% | ? |
| Plan–sim gap (RH) | 0.5% | ? |
| Violations (RH) | 1 | ? |

### Exp B (fresh): Reproducibility check

Running the same route with new weather data tests whether the exp_b results are robust or weather-dependent. If RH advantage is similar (~2–3% vs LP/DP), the result generalizes.

---

## Questions for Discussion

1. **Exp D results:** What's the RH advantage on harsh weather? Is 6h replan still optimal, or does storm variability favor more frequent replanning?

2. **Partial exp_c analysis:** With ~7 days of data available, should we run a partial analysis to get early signal on the beyond-horizon effect?

3. **Fresh exp_b comparison:** If March results differ significantly from February, what does that tell us about seasonal sensitivity?

4. **Literature review chapter:** Should we start drafting the narrative now, or wait until exp_c/d results inform which papers to emphasize?

5. **Thesis timeline:** With exp_d done and exp_c at ~Mar 19, what's the realistic target for a complete results chapter draft?

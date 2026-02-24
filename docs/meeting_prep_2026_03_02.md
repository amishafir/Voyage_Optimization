# Meeting Prep — Supervisor Meeting, Mar 2 2026

---

## Progress Since Last Meeting (Feb 23)

### Action Item 1: RH re-planning frequency ✅

**Question:** Does hourly re-planning improve RH results vs 6-hourly?

**Answer: No.** Ran replan frequency sweep at [1, 2, 3, 6, 12, 24] hours on exp_b (138 nodes, 134 sample hours).

| Frequency | Sim Fuel (mt) | Delta vs 1h | Decision Points | New Info Rate |
|:-:|:-:|:-:|:-:|:-:|
| 1h | 180.63 | baseline | 73 | 53% |
| 2h | 180.70 | +0.07 (+0.04%) | 50 | 70% |
| 3h | 180.73 | +0.11 (+0.06%) | 37 | 76% |
| **6h** | **180.84** | **+0.21 (+0.12%)** | **21** | **100%** |
| 12h | 180.69 | +0.06 (+0.04%) | 12 | 100% |
| 24h | 181.22 | +0.59 (+0.33%) | 6 | 100% |

**Key finding:** 1h vs 6h fuel difference is only 0.21 mt (0.12%) — negligible. At 1h frequency, only 53% of decision points receive genuinely different forecasts. At 6h, every decision point gets new data. **6h is the sweet spot.**

### Action Item 2: Open-Meteo API update cycle ✅

**Question:** How often does the underlying NWP model actually refresh?

**Answer:** Verified from Open-Meteo API documentation:

| Parameter | Model | Update Frequency | Empirical (our data) |
|-----------|-------|:-:|:-:|
| Wind speed/direction | GFS / ECMWF IFS / ICON Global | **6h** (4x/day at 00/06/12/18z) | 6h median, 86% unchanged hourly |
| Wave height | MFWAM (Meteo-France) | **12h** (2x/day) | 12h median, 94% unchanged hourly |
| Ocean current vel/dir | SMOC (Meteo-France) | **24h** (1x/day) | 24h median, 97% unchanged hourly |

Note: ECMWF WAM also provides waves at 6h, but our route (Persian Gulf–Indian Ocean) is served by MFWAM.

**Conclusion:** Hourly collection wastes ~86–97% of API calls on identical data. 6-hourly collection aligns with the fastest model cycle (GFS wind) and captures all new information.

### Action Item 3: RH actual weather at decision points ✅

**Done in commit `d21cecd`.** When RH re-plans, the first leg now uses actual weather (not predicted) for the current node. The ship is physically there — no forecast uncertainty. Result: SWS violations reduced from 12 → 10 on exp_b.

### Action Item 4: Longer, harsher route ❌ Not started

Still need to identify and collect data for a route with higher weather variability to show meaningful LP/DP/RH differentiation.

---

## Forecast Staleness Analysis (new script)

Three analyses on the exp_b HDF5 data confirm the API cycle findings empirically:

**1. Update intervals (run-length of unchanged predictions)**

| Field | Median Run Length | % Unchanged Hourly | NWP Cycle |
|-------|:-:|:-:|:-:|
| Wind Speed | 6.0h | 86% | 6h |
| Wind Direction | 6.0h | 86% | 6h |
| Wave Height | 12.0h | 94% | 12h |
| Current Velocity | 24.0h | 97% | 24h |
| Current Direction | 24.0h | 97% | 24h |

**2. Gap deltas — diminishing returns above model cycle**

At 1h gap: only 14% of wind values changed (median delta = 0).
At 6h gap: 84% changed (median delta = 1.17 km/h).
Beyond 6h: marginal increase — most new information arrives at the 6h boundary.

**3. SOG sensitivity — hourly deltas are below noise**

Typical 1h wind delta (0.30 km/h) translates to 0.001 kn SOG change.
Even 6h wind delta (1.79 km/h) only causes 0.03 kn mean SOG impact.
Wave and current deltas have effectively zero SOG impact at any gap size.

---

## Thesis-Ready Conclusions from This Week

1. **6h is the optimal replan frequency.** Matches the fastest NWP model cycle. Sub-6h replanning provides no new information and negligible fuel benefit.

2. **Hourly collection is wasteful.** 86–97% of API calls return identical data. Future collection should use 6h intervals.

3. **The three weather parameters have very different information refresh rates.** Wind drives re-planning value (6h cycle). Waves (12h) and currents (24h) are much more stable — a replan triggered by wind changes will rarely see updated wave/current data.

4. **Actual weather at decision points reduces violations.** Simple improvement with no downside — should be standard for RH.

---

## Questions for Discussion

1. **Is the 6h replan result sufficient for the thesis, or do we need to repeat on the harsher route?** On this calm route, all frequencies converge. A harsh route might show more differentiation.

2. **Should we collect a new dataset at 6h intervals instead of hourly?** Would be cleaner for thesis presentation but means new ~6-day collection run.

3. **Route selection for action item 4:** Arabian Sea (monsoon), North Atlantic (winter storms), or Southern Ocean? Need high weather variability + practical shipping route.

4. **How to present the staleness analysis in the thesis?** Section 4.X as a standalone finding, or fold into the replan frequency discussion?

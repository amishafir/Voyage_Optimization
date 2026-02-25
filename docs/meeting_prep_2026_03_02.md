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

**Empirical verification — exact NWP propagation timing:**

Tracked `predicted_weather.csv` from exp_b (3.1M rows, 138 nodes, 134 sample hours). For a fixed `forecast_hour=50`, compared predictions across consecutive `sample_hour` values to find exactly when the API returns new data:

```
GFS cycle:     00z       06z       12z       18z
                 ↓         ↓         ↓         ↓  (~5h processing delay)
Data arrives:  05 UTC    11 UTC    17 UTC    23 UTC
```

Change events in our data (node 0): sample hours 2, 8, 14, 20, 28, 32, 38, 44, 50, 56 — gaps are consistently 6h (median=6, mean=6.0). Mapped to UTC, 9 out of 10 updates landed at `hour % 6 == 5`, confirming the ~5h propagation delay from GFS initialization.

At each update, ~98-100% of all 138 nodes change simultaneously — this is a global model refresh, not per-location drift.

**NWP-aligned collection (implemented):**

Added `sample_interval_hours` and `nwp_offset_utc` config options to `collector.py`. Instead of hourly collection with 86% redundancy, future experiments can collect at 6h intervals synchronized to GFS availability:

```yaml
collection:
  sample_interval_hours: 6    # 4 samples/day (was 24)
  nwp_offset_utc: 5           # target 05/11/17/23 UTC
```

This cuts API calls by ~83% with zero information loss. Sample hours become 0, 6, 12, 18, ... — the RH optimizer already selects the closest available sample_hour at each decision point, so this is fully compatible.

### Action Item 3: RH actual weather at decision points ✅ (extended)

**Original** (commit `d21cecd`): Injected actual weather for the first leg only (current node). Violations reduced from 12 → 10 on exp_b.

**Extended: actual weather for the full committed window.** At each 6h decision point, the RH now uses actual weather observations (not forecasts) for ALL nodes within the 6h window it commits to, and forecast weather for hours beyond that. The optimizer plans with ground truth for the legs it will actually execute.

Two changes:
1. **Optimizer** (`dynamic_rh/optimize.py`): injects `actual_weather[closest_sh][node_id]` for all forecast_hours in `[elapsed_time, elapsed_time + replan_freq]`. Falls back to forecast if actual weather makes the DP infeasible (only happens when ETA margin is < 0.1h).
2. **Simulation** (`shared/simulation.py`): new `time_varying=True` mode that picks the closest actual-weather snapshot for each leg based on cumulative transit time, matching what the RH optimizer sees.

**Results on exp_b (138 nodes, 134 sample hours):**

| Approach | Plan Fuel (mt) | Sim Fuel (mt) | Plan–Sim Gap | Violations | Avg SOG (kn) | Fuel Saved vs Upper Bound |
|---|--:|--:|--:|--:|--:|--:|
| *Upper bound (SWS=13 kn always)* | *—* | *203.91* | *—* | *—* | *12.78* | *baseline* |
| LP (static det.) | 175.96 | 180.63 | +4.67 (+2.7%) | 4 | 11.98 | 23.28 (11.4%) |
| DP (dynamic det.) | 177.63 | 182.22 | +4.59 (+2.6%) | 17 | 12.03 | 21.69 (10.6%) |
| RH (old, first leg only) | 174.21 | 180.84 | +6.63 (+3.8%) | 10 | — | 23.07 (11.3%) |
| **RH (new, full 6h window)** | **175.52** | **176.40** | **+0.88 (+0.5%)** | **1** | **12.01** | **27.51 (13.5%)** |

**Key improvements:**
- **Violations: 10 → 1.** The single remaining violation (node 132, SWS=13.079) occurs at the last decision point where the fallback to forecast was triggered (ETA margin < 0.1h).
- **Plan–sim gap: 3.8% → 0.5%.** The optimizer plans with the same weather the ship encounters, so the plan is almost perfectly achievable.
- **Simulated fuel: 180.84 → 176.40 mt.** Now **2.3% less than LP** and **3.2% less than DP** — a clear RH advantage because it doesn't waste fuel compensating for forecast errors.

### Action Item 4: Longer, harsher route ✅ Two new routes deployed

Selected two new routes targeting heavy weather, designed to maximize RH advantage over DD:

**Experiment C — Yokohama → Long Beach (North Pacific Great Circle)**
- 4,782 nm, ~17 days at 12 kn. Arcs to 47.65°N through the Aleutian storm track (winter BN 8-10, waves 4-6m mean, 8-20m storms).
- 947 nodes at 5nm spacing, ~1,936 API calls per hourly sample.
- **Collection running since Feb 24** on TAU server (`tmux exp_c`). As of Feb 25: **18 sample hours collected, 32.5 MB, 0 failures.**
- Full voyage data by ~Mar 11. Partial analysis (10 days, 240h) by ~Mar 6.
- Route file: `pipeline/config/routes/yokohama_long_beach.yaml`

**Experiment D — St. John's → Liverpool (North Atlantic Storm Track)**
- 1,955 nm, ~6.8 days at 12 kn. Crosses the heart of the North Atlantic storm track (45-56°N) — the most extreme wave climate on Earth per NASA.
- 389 nodes at 5nm spacing, ~782 API calls per hourly sample.
- **Collection running since Feb 25** on TAU server (`tmux exp_d`). First sample: 389/389 OK, 0 failures.
- Full voyage data by ~**Mar 4** (7 days). This is the priority route for analysis.
- Route file: `pipeline/config/routes/st_johns_liverpool.yaml`

**Why two routes with different lengths:**

| | Exp D (7 days) | Exp C (17 days) |
|---|---|---|
| DD forecast coverage | Full voyage (168h horizon covers ~163h voyage) | First 7 of 17 days only |
| RH advantage source | **Freshness effect** only — DD has data but it degrades | Freshness **+ horizon effect** — DD is blind for 58% of voyage |
| Thesis value | Isolates the pure forecast freshness advantage | Shows combined effect + how much worse DD gets without any forecast |
| Results ready | **Mar 4** | Mar 6 (partial) / Mar 11 (full) |

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

## Pipeline Infrastructure Improvements

### Indefinite collection mode
Modified `collector.py` to support `hours: 0` for indefinite collection:
- Loop runs `while True` instead of `for sample_hour in range(hours)`
- Graceful shutdown: SIGINT/SIGTERM finishes current sample, then exits cleanly (no partial writes)
- Resume-aware: restarts from `max(completed) + 1`
- Status summary each sample: nodes OK/failed, HDF5 size, total hours, wall time

### Partial analysis workflow
New scripts for analyzing data while collection is still running:
- `check_exp_c_status.py` — lightweight status checker (no optimizer imports), runs locally or via SSH
- `run_partial_exp_c.py` — runs LP/DP/RH on whatever data exists, auto-adjusts ETA and segments to reachable nodes

Workflow: `scp` the HDF5 anytime → run partial analysis locally → collection continues on server.

---

## Thesis-Ready Conclusions from This Week

1. **6h is the optimal replan frequency.** Matches the fastest NWP model cycle. Sub-6h replanning provides no new information and negligible fuel benefit.

2. **Hourly collection is wasteful.** 86–97% of API calls return identical data. Future collection should use 6h intervals.

3. **The three weather parameters have very different information refresh rates.** Wind drives re-planning value (6h cycle). Waves (12h) and currents (24h) are much more stable — a replan triggered by wind changes will rarely see updated wave/current data.

4. **Actual weather for the committed window nearly eliminates violations.** Extending actual weather injection from one leg to the full 6h committed window dropped violations from 10 → 1 and the plan–sim gap from 3.8% → 0.5%. RH simulated fuel (176.40 mt) now beats both LP (180.63) and DP (182.22).

5. **Forecast horizon (168h) is the key driver of RH advantage.** On voyages ≤ 7 days, DD has full coverage and the RH advantage comes only from freshness (~0.7% on exp_b). On voyages > 7 days, DD falls back to persistence — RH should show a much larger advantage. Exp C and D are designed to test both regimes.

---

## Questions for Discussion

1. **Exp D results expected by Mar 4 — what analysis should we prioritize?** Options: (a) repeat the replan frequency sweep on harsh weather, (b) forecast error vs lead time comparison, (c) fuel gap analysis DD vs RH.

2. **How to present the two-route comparison in the thesis?** Exp D (within horizon) shows freshness effect; Exp C (beyond horizon) shows combined effect. Together they decompose the RH advantage into its two components.

3. **Should we present the staleness analysis as a standalone section?** It explains *why* 6h replanning is optimal and connects to the NWP model cycles. Could be Section 4.X or folded into the replan discussion.

4. **Port B NaN issue on new routes:** The last waypoint on the original route had NaN marine data (coastal proximity). Need to verify whether Liverpool and Long Beach have the same issue — if so, the existing NaN handling covers it.

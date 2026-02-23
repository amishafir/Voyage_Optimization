# Meeting Prep — Supervisor Meeting, Feb 23 2026

---

## 1. The Dataset: `experiment_b_138wp.h5`

### What we collected

A Python script queried the Open-Meteo API every hour for **134 hours** (~5.5 days), collecting weather data for 138 waypoints along a 1,678 nm route from the Persian Gulf to the Indian Ocean.

```
Route:    Port A (Persian Gulf) → Indian Ocean 1
Distance: 1,678 nm (~140 hours at 12 kn)
Nodes:    138 (7 original waypoints + 131 interpolated at ~12 nm spacing)
Samples:  134 hours of continuous collection
```

### HDF5 structure (3 tables)

**`/metadata`** — 138 rows, one per waypoint. Static.

| node_id | lat | lon | waypoint_name | distance_from_start_nm | segment |
|:--:|:--:|:--:|:--|:--:|:--:|
| 0 | 24.75 | 52.83 | Port A (Persian Gulf) | 0.0 | 0 |
| 1 | 56.45 | 26.55 | Gulf of Oman | 223.7 | 1 |
| ... | ... | ... | ... | ... | ... |
| 137 | 10.45 | 75.16 | Indian Ocean 1 | 1677.6 | 5 |

**`/actual_weather`** — 18,492 rows (138 nodes × 134 hours). What really happened.

Each row: at node X, at sample_hour Y, the conditions were: wind, waves, current.

**`/predicted_weather`** — 3.1M rows (138 nodes × 134 hours × ~168 forecast hours). What the forecast said would happen.

Each row: at node X, when we asked at sample_hour Y, the forecast predicted that at forecast_hour Z the conditions would be: wind, waves, current.

### The two time dimensions

- **`sample_hour`** = when we queried the API (0, 1, 2, ... 133). Real wall-clock time. The script ran for 134 hours.
- **`forecast_hour`** = what future hour the prediction is about (-18 to +173). Each query produces ~168 forecast hours. Negative = hindcast.

### 6 weather fields (identical across both tables)

`wind_speed_10m_kmh`, `wind_direction_10m_deg`, `beaufort_number` (calculated from wind, not from API), `wave_height_m`, `ocean_current_velocity_kmh`, `ocean_current_direction_deg`

### Why this dataset is credible

The voyage takes ~140 hours. We collected 134 hours of actual weather. That means the simulation can test the ship against **real weather at nearly every hour it passes through a node**.

---

## 2. The Experiment: Plan vs Actual

### The core concept

```
                    PLAN                              ACTUAL (simulation)
    ┌──────────────────────────┐          ┌──────────────────────────────┐
    │ Optimizer sees weather   │          │ Ship sails through ACTUAL    │
    │ (actual or predicted)    │          │ weather from actual_weather  │
    │          ↓               │          │          ↓                   │
    │ Outputs: SOG target per  │   ──→    │ At each node: what SWS is   │
    │ leg (speed over ground)  │          │ needed to achieve that SOG?  │
    │          ↓               │          │          ↓                   │
    │ Plan fuel = FCR × time   │          │ Actual fuel = FCR(SWS) × t  │
    └──────────────────────────┘          └──────────────────────────────┘
```

### SOG-targeting (operationally realistic)

Ships in the real world maintain a **target speed over ground** (SOG). The engine adjusts power (SWS = speed through water) to compensate for weather:
- Headwind → increase SWS to maintain SOG
- Tailwind → decrease SWS to maintain SOG

The simulation mirrors this: for each node, given the planned SOG and actual weather, it uses binary search to find the SWS needed. If SWS exceeds engine limits [11, 13] kn, it's **clamped** and a violation is logged.

### Why the gap matters

**FCR = 0.000706 × SWS³** — fuel consumption is cubic in engine speed.

The plan uses one version of weather (predicted or averaged). The actual weather is different at each node. The SWS adjustments needed to maintain the planned SOG under actual weather cost more fuel than the plan estimated — because the cubic FCR means **penalties at harsh nodes always outweigh savings at calm nodes** (Jensen's inequality).

The gap between plan and actual = the cost of imperfect information.

### What creates SWS violations

| Source | Direction | Mechanism |
|--------|:---------:|-----------|
| Forecast overpredicts wind | SWS > 13 kn needed | Plan expects headwind, actual is calmer → ship overspeeds |
| Forecast underpredicts wind | SWS < 11 kn needed | Plan expects calm, actual has headwind → ship can't keep up |
| Segment averaging hides extremes | Both | LP sees mild average, but individual nodes have harsh weather |

---

## 3. The Three Algorithms

### Shared physics model

8-step speed correction from research paper:

```
SWS → weather direction angle → Froude number → direction/speed/form coefficients
    → speed loss % → weather-corrected speed → vector addition with current → SOG
```

**FCR = 0.000706 × SWS³** (kg/hour). This cubic convexity is what makes the choice of algorithm matter.

### Algorithm comparison (on exp_b: 138 nodes, 6 segments, ~140h)

| | Static Det. (LP) | Dynamic Det. (DP) | Rolling Horizon (RH) |
|--|---|---|---|
| **Weather source** | `/actual_weather` at hour 0 | `/predicted_weather` at hour 0 | `/predicted_weather`, re-queried each decision point |
| **Spatial granularity** | 6 segments (~280 nm each) | 137 legs (~12 nm each) | 137 legs, re-planned |
| **What it sees** | Segment-averaged actual weather | Per-node predicted weather (single forecast) | Per-node predicted weather (latest forecast) |
| **Algorithm** | Linear Program (Gurobi) | Forward Bellman DP | DP × ~23 decision points |
| **Re-planning** | None | None | Every 6h |
| **SWS choices** | 21 options (11.0–13.0 kn) | 21 options per node | 21 options per node |

**LP:** Averages weather across all nodes in each segment → picks one SWS per segment → minimizes total fuel subject to arriving within ETA. Uses SOS2 piecewise linearization for the nonlinear SOG(SWS) relationship.

**RH:** At each decision point (every 6h of voyage time), loads the latest forecast (`sample_hour = current_hour`) and re-runs DP for the remaining voyage. Stitches executed legs together. Benefits from forecast drift — newer predictions are more accurate.

### DP algorithm in detail

The DP models the voyage as a **2D grid**: nodes (space) × time slots (time).

```
         time →  t=0    t=1    t=2    t=3   ...   t=T (ETA)
node 0    ●─────┬──────┬──────┬─────────────────────
node 1          ●      ●      ●
node 2                 ●      ●      ●
node 3                        ●      ●      ●
  ...                                         ...
node 137                                          ●  ← destination
```

**State** = `(node_i, time_slot_t)` — the ship is at node `i` at time `t × dt`. Start: `(node 0, t=0)` with fuel = 0. Goal: reach node 137 at any `t` where `t × dt ≤ ETA`.

On exp_b: `dt = 0.1h`, ETA = 140h → 1,400 time slots + 500 buffer = 1,900 slots.

**Forward pass** — for every reachable state `(node_i, t)`:

1. Look up predicted weather at node `i` for `forecast_hour = t × dt` (the weather the ship will encounter when it arrives)
2. Try all 21 SWS options (11.0, 11.1, ... 13.0 kn). For each:
   - SOG = physics_model(SWS, weather)
   - travel_time = distance_to_next_node / SOG
   - fuel = FCR(SWS) × travel_time
   - t_next = ceil(arrival_time / dt)
3. Update `cost[i+1][t_next]` if this path is cheaper than any previously found
4. Store `parent[i+1][t_next] = (t, speed_k)` for backtracking

**Backtrack** — scan `cost[137][t]` for all `t ≤ ETA/dt`, pick minimum fuel. Follow `parent` pointers backwards to reconstruct the per-leg SWS/SOG schedule.

**Complexity: O(N × T × K)**

| Symbol | Meaning | exp_b value |
|:--:|:--|:--:|
| N | Legs | 137 |
| T | Time slots | 1,900 |
| K | SWS options | 21 |

Worst case: 137 × 1,900 × 21 = **5.5M edge evaluations**. Each calls the 8-step physics model (constant time). In practice less, because `cost` is sparse — not all 1,900 time slots are reachable at each node (the code uses dicts, not arrays).

| Change | Effect |
|:--|:--|
| More nodes (279 vs 137) | ~2× time |
| Finer time granularity (dt=0.05 vs 0.1) | ~2× time |
| Finer speed granularity (0.01 vs 0.1) | ~10× time |
| Longer voyage (280h vs 140h) | ~2× time |

### Why DP is polynomial, not exponential

A naive brute-force approach would enumerate **every possible combination** of speed choices across all legs:

```
Brute force: 21 choices at leg 1 × 21 at leg 2 × ... × 21 at leg 137 = 21^137 ≈ 10^181
```

That's more than the number of atoms in the universe (~10^80). Completely intractable.

DP avoids this through **Bellman's principle of optimality**: the optimal path from node `i` to the destination does not depend on how the ship reached node `i`. This means:

```
Brute force:                              DP:

leg 0 → leg 1 → leg 2 → ... → leg 137    leg 0 → leg 1 → leg 2 → ... → leg 137
  21  ×   21  ×   21   × ... ×   21        21  +   21  +   21   + ... +   21
        21^137 combinations                       137 × 21 decisions
        ≈ 10^181                                  = 2,877 (× T time slots)
```

At each node, DP only keeps **the cheapest way to reach each time slot**. If two different paths arrive at node 5 at time slot 200, only the one with lower fuel survives. All future decisions are identical regardless of which path got there — so the worse path is discarded.

This collapses the exponential tree into a polynomial grid: **O(N × T × K) = 5.5M** operations instead of 10^181.

### Why LP uses actual weather but DP/RH use predicted

LP represents the simplest planning approach: look at current conditions, assume they persist. It reads `/actual_weather` (what's happening now) and treats it as constant for the whole voyage.

DP/RH represent more sophisticated planning: use the 7-day forecast to anticipate future conditions. They read `/predicted_weather` to get weather at each future hour the ship will arrive at each node.

The simulation always tests against `/actual_weather` — the ground truth.

---

## 4. Results

### Theoretical bounds (exp_b)

| Bound | Fuel (kg) | Method | Time |
|-------|:---------:|--------|:----:|
| **Upper** | **203.91** | SWS = 13 kn (max engine) at every node, SOG varies with weather | 131.5h (8.5h early) |
| **Lower** | **180.59** | Optimal per-node SWS with actual weather, Lagrangian optimization | 140.0h (exact ETA) |
| **Span** | **23.33** | The total optimization opportunity on this route | |

The lower bound is the absolute minimum fuel achievable: perfect weather knowledge, continuous SWS optimization at every node, within engine limits, arriving exactly at ETA.

### Three approaches: plan vs actual

| | B-LP | B-DP | B-RH |
|--|:--:|:--:|:--:|
| **Planned fuel** | 175.96 kg | 177.63 kg | 174.20 kg |
| **Simulated fuel** | 180.63 kg | 182.22 kg | 180.89 kg |
| **Gap (plan→actual)** | +4.67 kg (+2.7%) | +4.59 kg (+2.6%) | +6.70 kg (+3.8%) |
| **SWS violations** | 4/137 (2.9%) | 17/137 (12.4%) | 12/137 (8.8%) |
| **% of span captured** | 99.9% | 93.1% | 98.7% |

### Where each approach sits within the bounds

```
Lower bound                                                Upper bound
180.59 ──────────────────────────────────────────────────── 203.91 kg
  |  LP   RH           DP                                      |
  |  180.6 180.9       182.2                                   |
  |  99.9% 98.7%       93.1%                                   |
  └─────── 23.33 kg span ─────────────────────────────────────┘
```

All three approaches capture >93% of the optimization potential. On this calm route (wind std 6.07 km/h), the differences are small (1.6 kg range).

### SWS violation details

During **planning**: zero violations. All algorithms choose SWS within [11, 13] kn.

During **simulation**: violations occur because actual weather differs from what was used for planning.

| | Violations | Needed SWS range | Cause |
|--|:--:|:--:|--|
| LP | 4 | up to 13.21 kn | Segment average hides per-node extremes |
| DP | 17 | 10.6 – 13.99 kn | Predicted weather ≠ actual weather |
| RH | 12 | 10.6 – 13.38 kn | Fewer than DP — fresher forecasts help |

DP has the most violations: it plans on a single forecast from hour 0, which grows stale. RH re-plans with newer forecasts, reducing violations. LP has the fewest because segment averaging smooths extremes (but this also means LP can't exploit per-node variation).

### Key findings

**1. All approaches converge on calm routes.**
On this calm, short route: 1.6 kg total range (180.6–182.2 kg). The optimization opportunity is small because weather variability is low and the voyage fits within the accurate forecast window.

**2. LP ≈ lower bound.**
LP (180.63 kg) is within 0.04 kg of the theoretical lower bound (180.59 kg). On calm routes, even segment-averaged planning is near-optimal.

**3. The plan-vs-actual gap reveals information cost.**
Every approach overestimates its efficiency. The gap (2.6–3.8%) is the real-world cost of using imperfect weather data. RH has the largest gap because its plan is the most optimistic (it uses the freshest forecasts, which don't fully anticipate reality).

**4. Forecast error curve (ground truth from exp_b).**

For each lead time, we compare every prediction to what actually happened — across all 138 nodes and all valid starting hours (~15,000 samples per lead time). No simulation needed, pure measurement.

| Lead Time | Wind RMSE (km/h) | Wind Bias | What this means |
|:---------:|:----------------:|:---------:|:--|
| 0h | 4.13 | +0.20 | Forecast's "current conditions" — already 4 km/h off |
| 24h | 4.84 | +0.59 | 1-day forecast — slightly worse |
| 48h | 5.63 | +1.21 | 2-day — bias growing |
| 72h | 6.13 | +1.31 | 3-day — accuracy starts degrading fast |
| 96h | 7.65 | +2.86 | 4-day — big jump in RMSE and bias |
| 133h | 8.40 | +2.67 | 5.5-day — RMSE has doubled vs hour 0 |

**Two patterns:**

- **RMSE doubles** (4.13 → 8.40, +103%). After ~72h, errors grow fast — the fundamental limit of atmospheric prediction.
- **Positive bias grows** (+0.20 → +2.67). Forecasts systematically **overpredict** wind. DP/RH plan for worse conditions than actually occur → set SOG too conservatively → SWS needed under calmer actual weather exceeds 13 kn → violations.

**Why this matters for the algorithms:**

- **DP** uses one forecast from hour 0. For nodes the ship reaches at hour 100+, the forecast is 100h stale (RMSE ~8 km/h).
- **RH** re-plans every 6h. For those same nodes, the lead time drops to ~40h (RMSE ~5.5 km/h).
- That's why RH has fewer violations (12) than DP (17) — its forecasts are always fresher.

On this calm 140h route, the advantage is small. On a longer route with harsher weather, DP's stale forecasts would be much more costly.


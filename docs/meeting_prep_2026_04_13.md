# Meeting Prep — Supervisor Meeting, Apr 13 2026

---

## 1. Action Items from Mar 31 Meeting

| # | Task | Status |
|---|------|--------|
| 1 | Deep-dive into Luo 2024 weather forecast resolution | **DONE** (Section 2) |
| 2 | Revisit `speed_control_optimizer.py` DP graph structure | TODO |
| 3 | Adjust DP algorithm for forecast resolution awareness | TODO |

---

## 2. Deep Dive: Luo et al. 2024 — Slice and Dice

### 2.1 The Big Picture

Luo's method is a **two-phase system**:
1. **Phase 1**: Train an ANN to predict hourly FCR from (speed, weather, operational conditions)
2. **Phase 2**: Use that ANN inside a rolling-horizon Dijkstra graph optimizer, re-solving every 6h with fresh NOAA forecasts

The paper does NOT simulate a voyage. There is no executor, no plan-vs-reality gap, no SWS clamping. The "fuel consumption" numbers in their results come from **feeding actual weather into the ANN** — not from simulating what a ship would actually do if it followed the planned speeds.

### 2.2 Their "Simulation" — It's Not a Simulation

This is the most critical finding. Luo evaluates fuel consumption using **four formulas** (Eq. 24-27), ALL of which use the same ANN:

| Metric | Speed source | Weather source | Formula |
|--------|-------------|---------------|---------|
| `FC_proposed` | Rolling-horizon optimized speeds | **ERA5 actual** weather | Eq. 24 |
| `FC_constant_speed` | Best constant speed (optimized) | **ERA5 actual** weather | Eq. 25 |
| `FC_static` | Departure-only optimized speeds | **ERA5 actual** weather | Eq. 26 |
| `FC_actual` | Actual ship speeds (from noon reports) | **ERA5 actual** weather | Eq. 27 |

**Key insight: ALL four metrics use ERA5 actual weather for evaluation.** The differences come ONLY from the speed profile. There is no "execution against different weather than planned." They never ask: "what happens if the ship tries to sail at speed v but the weather is different from what the optimizer assumed?"

This means:
- **No SWS/SOG distinction** — speed in = speed achieved
- **No Flow 2 events** — no clamping, no infeasibility
- **No Jensen's inequality effect** — no within-segment speed variation
- **No plan-vs-execution gap** — the planned speed IS the executed speed

Their e3 metric (4.1% and 15.3%) measures: "how much more fuel does the ANN predict when using forecast-optimized speeds vs actual-weather-optimized speeds, both evaluated under actual weather?" It's a **planning quality** metric, not an **execution quality** metric.

### 2.3 The DP Graph — Multistage Construction

**Segmentation**: Time-based, not spatial. Each segment = one NWP forecast cycle (T = 6h).

For the k-th run (re-plan):
- Remaining distance: `L^k = L - sum of distances already sailed`
- Remaining max time: `T^k = T_max - sum of times already sailed`
- Number of stages: `N^k = floor((T^k - (T - Δt)) / T) + 2`

Where `Δt = T^k_start - T^k_nearest` is the offset between the ship's departure for this run and the nearest forecast issuance time.

**Stages** (graph layers):
- Stage 1: Source node (current position, value = L^k = remaining distance)
- Stages 2 to N^k-1: Intermediate layers, nodes represent possible remaining distances
- Stage N^k: Sink node (destination, value = 0)

**Nodes within each stage**: Discretized remaining distance values at interval ζ (= 1 nm in their experiments).
- Lower bound: `lb = max(0, L^k - sum(v_max × t^k_j) for j up to this stage)`
- Upper bound: `ub = max(0, L^k - sum(v_min × t^k_j) for j up to this stage)`
- Node values: `lb, lb+ζ, lb+2ζ, ..., ub`

**Edges**: Node a in stage i connects to node b in stage i+1 if the distance between them can be covered within the time limit for that stage at a speed within [v_min, v_max].

**Edge weights**: `w(a→b) = f^ANN(v^k_j(a→b), w(a), u(a)) × t^k_{i+l-1}`

Where:
- `v^k_j(a→b)` = speed needed = `(L^k_i(a) - L^k_{i+1}(b)) / t^k_{i+l-1}` (Eq. 15)
- `w(a)` = weather at node a's location (from forecast for wind/temp, from ERA5 for waves)
- `u(a)` = draught and sailing condition (from nearest noon report)

**Pruning**: After building the graph, remove all nodes with zero outdegree (can't reach destination), starting from the penultimate stage. This eliminates infeasible paths.

**Solver**: Dijkstra via NetworkX Python library. Complexity: O(n²) where n = number of nodes.

### 2.4 The Sailing Time per Segment — Non-Uniform

This is subtle and important. The sailing time per segment is NOT always 6h:

```
t^k_j = {
    T - Δt,           if j = k (first segment of this run)
    T,                 if j ∈ {k+1, ..., n-1} (middle segments)
    T^k - T×(N^k-1) + Δt,  if j = n (last segment)
}
```

- **First segment**: `T - Δt` — shorter than 6h if the ship departed between forecast cycles
- **Middle segments**: exactly T = 6h
- **Last segment**: variable — whatever time remains to reach T_max

This means segments are NOT equal duration. The first and last are different. Our cycle executor handles this naturally (deferred to leg boundary, last cycle runs until voyage ends).

### 2.5 Weather Data — The Hybrid Problem

**For optimization** (building the graph): Weather at each node comes from the **latest NOAA GEFS forecast**. But GEFS only provides 3 variables: wind speed, wind direction, 2m temperature. The ANN needs 8 inputs (6 weather + 2 operational). Where do the other 3 weather variables come from?

The paper says (Section 3.3): "we use solely the control member forecast as a description of future meteorological conditions." But the ANN was trained on ERA5 data which includes wave height, wave direction, and surface roughness. **The paper never addresses how these 3 variables are provided during optimization.**

Possibilities (not stated in paper):
1. Set to zero or climatological averages (would degrade ANN predictions)
2. Use ERA5 values from the most recent available time (effectively using hindcast for waves)
3. Use the noon report values from the most recent report

This is a significant methodological gap. Their optimizer plans without wave data but evaluates with wave data.

**For evaluation** (computing FC metrics): ALL variables from ERA5 — the full 6 weather fields plus noon report operational data. This is the "ground truth" evaluation.

### 2.6 The Rolling Horizon Loop — Algorithm 1

Pseudocode (simplified):

```
Input: route length L, T_max, T (=6h), departure time, speed range
Output: speed profile (v_1, ..., v_m)

speed_profile = []
time_profile = []

for k = 1, ..., n:
    # Ship has sailed k-1 segments
    L^k = L - sum(v_j × t_j for j=1..k-1)        # remaining distance
    T^k = T_max - sum(t_j for j=1..k-1)           # remaining time
    T^k_start = departure + sum(t_j for j=1..k-1) # current absolute time

    # Number of stages in this run's graph
    N^k = floor((T^k - (T - Δt)) / T) + 2

    # Calculate sailing time per stage (Eq. 14)
    # Build multistage graph (Algorithm 2)
    # Dijkstra shortest path → optimal speeds for all remaining segments
    # Take the FIRST speed as v_k (committed speed for this segment)

    speed_profile.append(v_k)
    time_profile.append(t_k)

    # Check if voyage complete
    if sum(v_j × t_j) >= L:
        break
```

**Critical detail**: At each run, the optimizer solves for ALL remaining segments but **only commits to the first speed**. This is classic rolling horizon — solve the full problem, commit one step, re-solve with new information.

### 2.7 Graph Size and Complexity

From Appendix C (Table C1):

| Distance (nm) | ζ (nm) | Nodes | Time (min) |
|---------------|--------|-------|-----------|
| 3584 | 1.0 | 34,621 | 18.86 |
| 3584 | 1.5 | 23,096 | 7.32 |
| 3584 | 2.0 | 17,327 | 5.11 |
| 3584 | 5.0 | 6,834 | 1.40 |
| 3584 | 10.0 | 3,320 | 0.98 |

Their experiments use ζ = 1 nm. With ~35K nodes and Dijkstra at O(n²), each run takes ~19 minutes for the full 3584 nm graph. With rolling horizon, the remaining distance shrinks each run, so later runs are faster.

**Total computation**: 146 min for Voyage I (261h, ~44 runs), 220 min for Voyage II (266h, ~45 runs).

**Comparison to ours**: Our DP with 391 nodes × 21,300 time slots × 61 speeds = 504M edges takes ~160s per run. Luo's is ~19 min per run. They have more nodes (35K vs 391) but fewer edges per node (speeds are not discretized the same way).

### 2.8 What They Actually Show in Results (Table 5)

| | Voyage I (2702 nm, 261h) | Voyage II (3585 nm, 266h) |
|---|---|---|
| **FC_proposed** (rolling forecast) | 323.01 mt | 455.91 mt |
| **FC_predicted** (noon report speeds) | 355.33 mt | 456.52 mt |
| **FC_constant** (best constant speed) | 356.75 mt | 466.23 mt |
| **FC_static** (departure forecast only) | 373.43 mt | 467.19 mt |
| **FC_actual** (perfect knowledge) | 310.29 mt | 395.27 mt |

Key observations:
- **Voyage I**: FC_proposed saves 9.46% vs constant, 4.10% gap vs perfect. Significant savings.
- **Voyage II**: FC_proposed saves 2.21% vs constant, 15.34% gap vs perfect. Small savings but large gap to perfect knowledge.
- **Voyage II is problematic**: The proposed method barely beats constant speed (2.21%) but is 15.34% away from perfect knowledge. This suggests the forecast quality was much worse for Voyage II.

### 2.9 The Noon Report Data — Appendix A

From Tables A1/A2, the actual voyage data:

**Voyage I** (Jul 14-25, 2020):
- 12 daily noon reports, draught 17.5m, laden, 2702 nm
- Speed range: 9.33-10.96 kn (actual), much narrower than their [8, 18] optimization range
- Fuel rate: 1.3478-1.3542 mt/h (very consistent — bulk carrier at near-constant speed)
- Actual fuel: 352.98 mt over 261h

**Voyage II** (Feb 13-24, 2019):
- 12 daily noon reports, draught 17m, laden, 3585 nm
- Speed range: 9.83-12.08 kn (actual), wider variation
- Fuel rate: 1.3478-1.3750 mt/h
- Actual fuel: 361.24 mt over 266h

**Key observation**: The actual ships sailed at 9-12 kn, well below the 18 kn max in the optimization range. The optimizer's ability to assign speeds up to 18 kn (which the actual ship never used) is what generates the large savings — it can rush through bad-weather segments at high speed and cruise through good-weather segments slowly.

### 2.10 Dark Corners and Vague Places

| Issue | What's unclear | Impact |
|-------|---------------|--------|
| **Wave data in forecast** | 3/6 ANN weather inputs missing from GEFS forecast. How are wave height, wave direction, surface roughness provided during optimization? | Potentially large — ANN trained with waves but optimizes without them |
| **No execution simulation** | All FC metrics computed by feeding speeds + actual weather into ANN. No plan-vs-reality gap. | Makes their results optimistic — real execution would be worse |
| **Speed as single variable** | No SWS/SOG distinction. ANN input "v" is "sailing speed" — unclear if SWS or SOG | Can't separate engine effort from ground progress |
| **Weather spatial interpolation** | "Meteorological conditions at the beginning of the segment represent those along the whole segment" | Coarse — weather changes within 6h sailing distance (72-108 nm at 12-18 kn) |
| **Graph rebuilt from scratch** | Each run builds a new graph topology from remaining distance. No warm-start from previous solution | Computationally wasteful but guarantees optimality |
| **Constant speed per segment** | Speed is fixed for 6h — no within-segment variation | Matches our setup but misses intra-segment weather variation |
| **No schedule constraint** | `T_max` is hard but there's no soft ETA or delay penalty | Similar to our hard ETA |
| **Only 2 voyages tested** | Two voyages from the same ship, same loading condition | No multi-departure, no sensitivity analysis, no route comparison |
| **Data not shared** | "The authors do not have permission to share data" | Can't reproduce |

### 2.11 Structural Comparison: Luo's Graph vs Our Graph

| Dimension | Luo's Multistage Graph | Our DP Graph |
|-----------|----------------------|-------------|
| **Axes** | Stages (time-based, 6h each) × Remaining distance (nm) | Time slots (dt hours each) × Spatial nodes (waypoints) |
| **What nodes represent** | (stage, remaining_distance_to_destination) | (time_slot, node_index) |
| **What edges represent** | Speed choice for one 6h segment | Speed choice for one time step at one spatial node |
| **Node values** | Remaining distance in nm, discretized at ζ = 1 nm | Cumulative time, discretized at dt |
| **Edge weight** | `ANN(speed, weather, ops) × segment_time` | `FCR(speed) × dt` |
| **Weather lookup** | By (lat/lon at node position, forecast lead time) — nearest grid point | By (node_id, forecast_hour) — exact waypoint |
| **Spatial resolution** | ζ = 1 nm (distance from destination) | Fixed waypoints at 1-5 nm intervals along route |
| **Temporal resolution** | T = 6h per stage (fixed) | dt = 0.01-0.1h per time slot (configurable) |
| **Speed discretization** | [8, 18] at 0.1 kn = 101 speeds | [11, 13] at 0.1 kn = 21 speeds (or [9,15] = 61) |
| **Graph size (typical)** | ~35K nodes, O(n²) edges | 391 nodes × 21K time slots × 21-61 speeds = 170-500M edges |
| **Solver** | Dijkstra (NetworkX) | Forward Bellman DP (custom) |
| **Re-plan** | Rebuild entire graph from scratch | Slice sub-problem from current position |

### 2.12 What We Can Learn / Borrow

1. **Their time-based segmentation is actually simpler and may be better for forecast alignment.** Each segment = one forecast cycle. Weather is naturally constant within a segment because the forecast doesn't change within 6h. Our spatial segmentation means nodes within the same 6h window share a forecast but the DP doesn't explicitly know this.

2. **Their node value = remaining distance is elegant.** It naturally handles the constraint "must reach destination" (node value = 0 is the only valid endpoint). Our graph uses time slots and node indices, which requires a separate ETA constraint.

3. **Their graph pruning (zero-outdegree removal) is important for efficiency.** We do similar pruning in our DP but differently — we check reachability forward rather than removing backward.

4. **Their e3 metric (forecast vs actual gap) is what our Stochastic vs Deterministic comparison measures.** We should report it in the same format for direct comparison.

5. **Their speed range [8, 18] kn is key to their savings.** We should test with the same range to see if our framework produces comparable results.

---

## 3. DP Graph Structure Revisited

### Current structure (`speed_control_optimizer.py`)
*(to be filled after review)*

### How forecast resolution enters the graph
*(to be filled)*

### Proposed changes
*(to be filled)*

---

## 4. Data Collection Status

| Server | Status | Route B | Route D |
|--------|--------|---------|---------|
| Shlomo1 | Offline | - | - |
| Shlomo2 | Running | 27 MB | 80 MB |
| Edison | Running | 27 MB | 79 MB |

---

## 5. Results

*(to be filled as new experiments complete)*

---

## 6. Questions for Supervisor

1. **Luo's missing wave data**: Their ANN was trained with wave data (ERA5) but optimizes without it (GEFS has no waves). Should we highlight this as a methodological weakness in our paper?

2. **Luo's "simulation" isn't a simulation**: They evaluate all scenarios by feeding speeds + actual weather into the ANN. No plan-vs-reality gap. This is a fundamental limitation — their results assume the ship achieves exactly the planned speed. Should we position our SOG-targeting execution as a key differentiator?

3. **Speed range**: Should we match their [8, 18] kn for a direct comparison, or stick with a realistic EEXI range and argue that narrow ranges are more operationally relevant?

4. **Graph structure**: Should we adopt their time-based segmentation (stages = 6h forecast cycles) or keep our spatial segmentation? Time-based aligns better with forecast resolution; spatial aligns better with route structure.

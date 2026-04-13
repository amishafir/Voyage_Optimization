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

### 3.1 Current structure (`speed_control_optimizer.py`)

The legacy DP builds a **2D time-distance grid** and connects nodes via a custom "Sides" BFS algorithm.

**Classes:**
- `Node`: Holds `(time, distance)` index, `minimal_fuel_consumption`, `minimal_input_arc`, list of `arcs`
- `Side`: A row or column of nodes along a boundary (vertical = constant distance, horizontal = constant time)
- `Arc`: An edge with `SWS`, `SOG`, `Travel_time`, `Distance`, `FCR`, `fuel_load`

**Graph axes:**
- **X-axis (columns):** Distance in nm, from 0 to 3,393 nm at `distance_granularity` = 1 nm → 3,394 columns
- **Y-axis (rows):** Time in hours, from 0 to 280h at `time_granularity` = 1h → 281 rows
- **Total grid:** 281 × 3,394 = **953,714 nodes** (dense numpy array, most unreachable)

**Graph construction — Sides BFS:**
1. Create initial vertical side: nodes at distance=0, time ∈ [0, cumulative_time_list[0]]
2. For each side in queue, `locate_sides()` finds the next vertical boundary (at next cumulative segment distance) and horizontal boundary (at the time window end)
3. `connect_sides()` creates arcs between all node pairs in source and destination sides
4. Arcs are only created if the implied SOG falls within `speed_values_list` (11.0–13.0 at 0.1 kn step)

**Weather lookup (line 577):** `self.weather_forecasts_list[0][index_of_segment]` — **always uses forecast window 0**, regardless of the node's time position. Weather is looked up by spatial segment only (which of the 12 segments the node's distance falls into). There is no time-varying weather — all nodes see the same static weather.

**SWS inverse calculation:** Given a required SOG (from distance/time), binary search finds the SWS needed to achieve that SOG under the segment's weather conditions. FCR is then computed as `0.000706 × SWS³`.

**Key limitations:**
1. **No forecast resolution awareness** — hardcoded to `weather_forecasts_list[0]` (single forecast window)
2. **Dense grid is wasteful** — 953K nodes allocated, most never touched by the Sides BFS
3. **weather_forecasts.yaml is fully commented out** for multi-window mode — only the single 0–280h window is active
4. **Sides BFS is complex** — custom graph traversal that's hard to extend for time-varying weather
5. **Speed discretization is SOG-based** — arcs exist only where distance/time gives an exact SOG matching a speed value (0.1 kn grid). This misses some valid speed combinations

**Comparison with pipeline DP (`pipeline/dynamic_det/optimize.py`):**

| Dimension | Legacy DP | Pipeline DP |
|-----------|-----------|-------------|
| **Graph storage** | Dense 2D numpy array (953K nodes) | Sparse dict-of-dicts (reachable states only) |
| **Spatial axis** | Distance in nm (1 nm steps) | Waypoint node index (138–391 nodes) |
| **Temporal axis** | Time in hours (1h steps) | Time slots (0.1h steps) |
| **Speed axis** | Implicit (SOG must match grid) | Explicit loop over candidate SWS values |
| **Weather lookup** | By segment ID, single forecast window | By node_id × forecast_hour, time-varying |
| **Forecast resolution** | None — static weather | `fh = min(round(current_hour + time_offset), max_fh)` |
| **SWS/SOG** | SOG determines arc existence, then inverse for SWS | SWS is the decision variable, SOG computed forward |
| **Solver** | Forward BFS via Sides, backtrack via `minimal_input_arc` | Forward Bellman DP, backtrack via parent pointers |

### 3.2 How forecast resolution enters the graph

**Legacy DP: it doesn't.** Line 577 always reads `self.weather_forecasts_list[0]`. The YAML was designed to support multiple forecast windows (commented-out examples show 0–2h, 2–4h, 4–6h windows), but the code never indexes by time. Every arc uses the same weather regardless of when the ship reaches that segment.

**Pipeline DP: partial support.** The key line (optimize.py:95):
```python
fh = min(int(round(current_hour + time_offset)), max_fh)
```
This maps the ship's current time to a forecast hour in the weather grid. As the ship progresses through the voyage, later nodes see weather from later forecast hours. This creates **time-varying weather** — but it treats all forecast hours as equally reliable. There's no distinction between:
- Forecast hour 1 (just issued, highly accurate)
- Forecast hour 100 (issued days ago, heavily degraded)

**Luo's approach: explicit forecast cycles.** Each graph stage = one 6h NWP cycle. Weather within a stage comes from a single forecast issuance. At each re-plan, the graph is rebuilt from scratch with the latest forecast. The structure guarantees that:
- All nodes in stage k use the same forecast vintage
- The first stage uses the freshest forecast (highest accuracy)
- Later stages use increasingly stale forecast data (lower accuracy)

**The gap:** Neither our legacy nor pipeline DP explicitly models **forecast degradation with lead time**. The pipeline DP does use different forecast hours for different times, but doesn't weight them by accuracy or distinguish "forecast issued 1h ago for 1h ahead" from "forecast issued 1h ago for 100h ahead."

In the rolling-horizon executor, this is partially addressed: re-planning every 6h means the ship always gets a fresh forecast for the near future. But within a single DP solve, the optimizer doesn't know that forecast hour 50 is less reliable than forecast hour 5.

### 3.3 Proposed changes

Three levels of intervention, from simplest to most ambitious:

**Level 1: Make the legacy DP time-aware (minimal change)**

Modify `connect()` (line 577) to index weather by the source node's time position:
```python
# Current: always forecast window 0
segment_data = self.weather_forecasts_list[0][index_of_segment]

# Proposed: select forecast window based on node time
time_hour = source_node.node_index[0]
window_idx = self.get_forecast_window_for_time(time_hour)
segment_data = self.weather_forecasts_list[window_idx][index_of_segment]
```
And un-comment the multi-window YAML config (e.g., 6h windows with different weather per window).

**Effort:** Small. **Impact:** Enables time-varying weather in the legacy DP. Doesn't address forecast degradation.

**Level 2: Add forecast confidence weighting to the pipeline DP**

Currently, the pipeline DP treats all forecast hours equally in the cost function. We could add a **forecast confidence factor** that increases the uncertainty (and thus the conservatism) of speed choices at longer lead times:

```python
# In the DP inner loop:
lead_time_hours = fh - sample_hour  # how old is this forecast?
confidence = max(0.5, 1.0 - 0.005 * lead_time_hours)  # degrades with lead time

# Option A: Add uncertainty penalty to fuel cost
edge_cost = fuel + lambda_uncertainty * (1 - confidence) * fuel

# Option B: Blend forecast weather with climatological mean
wx_effective = confidence * wx_forecast + (1 - confidence) * wx_climatology
```

**Effort:** Medium. **Impact:** The optimizer would favor conservative speeds for distant segments (where forecast is unreliable) and aggressive optimization for near segments (where forecast is accurate). This directly models the "value of forecast freshness."

**Level 3: Adopt Luo's time-based segmentation (structural change)**

Restructure the DP graph so stages correspond to forecast cycles rather than spatial waypoints:
- Stage boundaries at 0h, 6h, 12h, 18h, ... (NWP issuance times)
- Nodes within each stage represent possible positions (remaining distance, discretized)
- Weather within a stage comes from a single forecast vintage
- At re-plan time, rebuild the graph from the ship's current position with fresh forecast

This is Luo's architecture. It aligns the DP structure with the forecast structure.

**Effort:** Large — essentially a rewrite. **Impact:** Direct comparability with Luo, natural forecast resolution alignment.

**Recommendation for the meeting:**

Present all three levels to the supervisor. The argument:

- **Level 1** is already partially done in the pipeline DP (time-varying weather lookup). We should complete this for the legacy DP if we want legacy/pipeline parity.
- **Level 2** is our **differentiator vs Luo**. They don't model forecast degradation at all — their optimizer trusts the forecast equally regardless of lead time. We can show that accounting for forecast confidence changes the optimal speed profile.
- **Level 3** is interesting but risky for the timeline. It would make our results directly comparable to Luo's but requires significant implementation effort for marginal benefit over Level 2.

Ask the supervisor: **Should we pursue Level 2 (forecast confidence weighting) as our primary contribution, or is the 3-agent information hierarchy experiment already sufficient differentiation from Luo?**

---

## 3.4 Full Architectural Comparison: Luo's DP vs Ours

### 3.4.1 Graph Topology

**Luo — Time-based stages.** The graph is a DAG of stages, each stage = one NWP forecast cycle (T = 6h).

```
Stage 1          Stage 2          Stage 3         ...    Stage N
(0 → T-Δt h)    (6h window)      (6h window)            (variable)

  [L^k]           [lb..ub]         [lb..ub]              [0] ← sink
   source          ζ=1nm            ζ=1nm
```

- Nodes = `(stage, remaining_distance_to_destination)`, discretized at ζ = 1 nm
- Stages = time windows, not spatial positions. Count: `N^k = floor((T^k - (T - Δt)) / T) + 2`
- Node count per stage: bounded by reachability from [v_min, v_max]. ~35,000 total nodes for a 3,584 nm voyage
- Graph shrinks at each re-plan (remaining distance smaller → fewer stages and nodes)

**Legacy DP (`speed_control_optimizer.py`) — Dense 2D grid.** A full numpy array indexed by `(time, distance)`.

```
Time (rows)  ↓
  0h    [d=0] [d=1] [d=2] ... [d=3393]
  1h    [d=0] [d=1] [d=2] ... [d=3393]
  ...
  280h  [d=0] [d=1] [d=2] ... [d=3393]
```

- Nodes = `(time_hours, distance_nm)` — every integer combination pre-allocated
- Grid size: 281 rows × 3,394 columns = **953,714 Node objects** — most never touched
- Time granularity: 1h. Distance granularity: 1 nm (from `ship_parameters.yaml`)

**Pipeline DP (`pipeline/dynamic_det/optimize.py`) — Sparse forward Bellman.**

```
Node 0    Node 1    Node 2    ...   Node 278
  t=0       t=?       t=?             t=?
  t=1       t=?       t=?             t=?
  ...       ...                       ...
```

- Nodes = `(waypoint_index, time_slot)`. Waypoints 0..278 (279 spatial nodes), time slots = `hours / dt` with dt = 0.1h
- Only reachable `(node, time_slot)` pairs stored (dict-of-dicts, not a dense array)
- Max time slots: `ceil(ETA/dt) + ceil(50/dt)` ≈ 21,300 for a 163h voyage at dt=0.1h

### 3.4.2 What Nodes Represent

| | Luo | Legacy DP | Pipeline DP |
|---|---|---|---|
| **Meaning** | "Ship has X nm remaining at stage k" | "Ship is at distance X nm at time T hours" | "Ship is at waypoint i at time slot t" |
| **Spatial** | Remaining distance (continuous, ζ=1nm) | Absolute distance from origin (1nm) | Discrete waypoint index (irregular spacing) |
| **Temporal** | Stage index (maps to 6h window) | Absolute time row (1h) | Time slot (dt=0.1h) |
| **Destination** | remaining_distance = 0 | Column d = 3,393 | Node index = 278 |

Luo's spatial axis is **continuous distance** (any 1 nm mark). Our pipeline DP uses **discrete waypoints** (138 or 391 pre-defined locations). This means Luo's optimizer can place the ship at any 1 nm mark after each 6h segment; our pipeline DP constrains the ship to be at a named waypoint.

### 3.4.3 What Edges Represent and How Speed Works

**Luo:** An edge from `(stage i, remaining L_a)` to `(stage i+1, remaining L_b)` implies speed `v = (L_a - L_b) / t_stage`. Speed is **not discretized into a candidate list** — it's a continuous variable determined by the (source, dest) pair. At ζ=1nm and T=6h, possible speeds are spaced at 1/6 ≈ 0.167 kn apart. Edge weight = `ANN(v, weather, ops) × t_stage`.

**Legacy DP:** An edge from `(t1, d1)` to `(t2, d2)` requires the implied SOG = `(d2-d1)/(t2-t1)` to be **exactly in** `speed_values_list` (11.0, 11.1, ..., 13.0 at 0.1 kn). If SOG doesn't match after rounding to 1 decimal → no edge (line 551). This is a hard filter that severely limits connectivity. The SOG is then inverse-solved (binary search, lines 399–515) to find the SWS that produces that SOG under segment weather, and `FCR = 0.000706 × SWS³`.

**Pipeline DP:** The inner loop (line 124) iterates over **every candidate SWS** (11.0, 11.1, ..., 13.0). For each SWS, SOG is computed forward via the physics model. Travel time = `distance / SOG`. Arrival time slot = `ceil(arrival_time / dt)`. Edge weight = `FCR[k] × travel_time`. Every SWS is tried; the physics determines SOG.

### 3.4.4 Decision Variable: SWS vs SOG

This is a fundamental architectural difference.

| | Luo | Legacy DP | Pipeline DP |
|---|---|---|---|
| **Decision** | Speed (ambiguous — paper says "sailing speed") | SOG (implied by distance/time geometry) | **SWS** (explicit loop over engine speeds) |
| **Weather effect** | Baked into ANN — speed → fuel, no SOG/SWS split | SOG → inverse → SWS → FCR | SWS → forward → SOG → travel time |
| **Direction** | Forward (speed → fuel via ANN) | **Inverse** (target SOG → binary search → SWS) | **Forward** (SWS → physics → SOG) |

Luo doesn't distinguish SWS from SOG. Their ANN takes "speed" as input and returns fuel rate. The ship achieves exactly the planned speed — there's no concept of the engine setting one speed and ground speed being different.

Our pipeline DP makes the split cleanly: the captain chooses SWS (engine setting), weather modifies it to SOG (actual progress), and the optimizer accounts for this gap. The legacy DP does it backwards — it needs a specific SOG to connect two grid points, then binary-searches for the SWS that produces that SOG.

### 3.4.5 FCR Model

| | Luo | Ours (both) |
|---|---|---|
| **Type** | ANN (neural network) | Physics formula |
| **Formula** | Black box: `ANN(v, wind_speed, wind_dir, wave_ht, wave_dir, temp, roughness, draught, condition)` → FCR | `0.000706 × SWS³` (mt/h) |
| **Inputs** | 8 variables (6 weather + 2 operational) | 1 variable (SWS only) |
| **Weather in FCR** | Yes — weather directly affects fuel consumption | No — weather affects SOG only; FCR is purely speed-dependent |
| **Transferability** | None without retraining (vessel-specific) | Direct — change the cubic coefficient |

Critical implication: in Luo's model, headwinds increase fuel *directly* (ANN input). In ours, headwinds slow the ship (lower SOG) → longer travel time → more total fuel. The pathway is indirect: weather → SOG loss → more hours at sea → more fuel.

### 3.4.6 Weather Data Handling

**Luo — during optimization:** NOAA GEFS forecast (0.5° spatial, 6h temporal). But GEFS only provides 3 of the 8 ANN inputs (wind speed, wind direction, 2m temperature). Wave height, wave direction, and surface roughness are needed by the ANN but **never explained** in the paper. "Meteorological conditions at the beginning of the segment represent those along the whole segment" — weather is constant within a 6h stage. Within a single DP solve, all stages use the same forecast issuance. No degradation modeling.

**Luo — during evaluation:** ERA5 reanalysis (all 6 weather fields + noon report ops). All four FC metrics use ERA5 actual weather.

**Legacy DP:** Always `self.weather_forecasts_list[0][index_of_segment]` (line 577). Weather varies by **spatial segment** (which of the 12 segments) but NOT by time. The YAML supports multiple forecast windows (commented out) but the code never indexes by time. Every node sees the same static weather regardless of when the ship reaches that segment.

**Pipeline DP:** Weather grid `weather_grid[node_id][forecast_hour]`. Forecast hour selected as `fh = min(int(round(current_hour + time_offset)), max_fh)` (line 95). Later legs see weather from later forecast hours → **time-varying weather** is supported. But no distinction between forecast accuracy at different lead times. Hour 1 and hour 100 are treated equally. Falls back to nearest available hour if a forecast hour is missing.

### 3.4.7 Graph Construction & Solver

**Luo — Build-and-Dijkstra:**
1. Compute stage durations (first stage shorter if between forecast cycles, last stage variable)
2. For each stage, compute reachable remaining-distance bounds from [v_min, v_max]
3. Enumerate all nodes within bounds at ζ spacing
4. Connect all valid (source, dest) pairs across adjacent stages
5. Prune: remove zero-outdegree nodes backwards from penultimate stage
6. Dijkstra (NetworkX) shortest path
7. ~35K nodes, O(n²) edges, ~19 min per solve

**Legacy DP — Sides BFS:**
1. Allocate 953K-node dense grid
2. Create initial "Side" (vertical boundary at distance=0)
3. BFS queue: for each Side, `locate_sides()` finds the next vertical boundary (at next cumulative segment distance) and horizontal boundary (at time window end)
4. `connect_sides()` tries all (source_node, dest_node) pairs between Sides
5. For each pair, compute SOG from distance/time. If SOG ∈ speed_values_list → create Arc
6. Relaxation inline: `d_node.minimal_fuel_consumption` updated immediately (line 523)
7. Solution: scan destination column for minimum fuel, backtrack via `minimal_input_arc` pointers
8. Essentially Bellman-Ford relaxation embedded in a BFS over boundary Sides (not Dijkstra)

**Pipeline DP — Forward Bellman:**
1. `cost[0][0] = 0.0` (node 0, time slot 0)
2. Triple loop: for each waypoint i, for each reachable time slot t, for each candidate SWS k:
   - Compute SOG via physics, travel time, fuel
   - `t_next = ceil(arrival_time / dt)`
   - Update `cost[i+1][t_next]` if cheaper, record parent
3. At destination, find min-cost time slot (fuel + optional λ × delay)
4. Backtrack via parent pointers
5. `O(num_legs × time_slots × num_speeds)` = 278 × 21,300 × 61 ≈ 360M edge evaluations, ~160s

### 3.4.8 Rolling Horizon

**Luo:**
- Re-plan every 6h with fresh GEFS forecast
- Rebuild **entire graph from scratch** (remaining distance shrinks → fewer stages/nodes)
- Solve for all remaining segments, **commit only the first speed** (classic receding horizon)
- ~44 re-plans for a 261h voyage, 146 min total compute

**Ours (cycle executor):**
- Re-plan every 6h aligned to NWP boundaries
- Re-run the full DP (or LP) from current position for all remaining legs
- Commit to the first 6h of speeds, then re-plan
- Weather assembler provides different data by agent type:
  - Naive: no weather (constant SOG assumption)
  - Deterministic: actual weather at current time, assumed persistent
  - Stochastic: actual for current window + forecast for future windows
- Graph topology (waypoint structure) doesn't change between re-plans — only weather data and starting position

### 3.4.9 Evaluation / Simulation — The Biggest Gap

**Luo — No execution simulation.** All four FC metrics (Eq. 24–27) work the same way: take a speed profile, feed those speeds + ERA5 actual weather into the ANN, sum fuel. No executor. No plan-vs-reality gap. If the optimizer says "sail at 12 kn," the evaluation assumes the ship sailed at exactly 12 kn and asks the ANN "how much fuel for 12 kn in this weather?"

Their e3 metric (4.1% and 15.3%) measures: "how much more fuel does the ANN predict when using forecast-optimized speeds vs actual-weather-optimized speeds, both evaluated under actual weather?" This is a **planning quality** metric, not an execution quality metric.

**Ours — Full execution simulation.** The cycle executor simulates what actually happens:
1. Optimizer produces a SWS schedule
2. At each leg, executor computes resulting SOG under **actual** weather
3. If SOG too slow (can't make ETA) → Flow 2: SWS clamped to max
4. If SOG too fast (would arrive early) → Flow 3: SWS reduced to min
5. Actual travel time = distance / actual_SOG
6. Actual fuel = FCR(actual_SWS) × actual_travel_time

This creates the plan-vs-execution gap that Luo ignores entirely. It's why our Stochastic agent without re-planning burns 220.09 mt while planning for less — planned speeds were wrong, execution deviated, and Jensen's inequality on the cubic FCR penalizes speed variation.

### 3.4.10 Full Summary Table

| Dimension | Luo 2024 | Legacy DP | Pipeline DP |
|---|---|---|---|
| **Graph type** | DAG (stages × remaining dist) | Dense 2D grid (time × distance) | Sparse (waypoint × time slot) |
| **Spatial axis** | Remaining distance, ζ=1nm | Absolute distance, 1nm | Waypoint index (irregular) |
| **Temporal axis** | Stages (6h each) | Time rows (1h each) | Time slots (0.1h each) |
| **Decision variable** | Speed (no SWS/SOG split) | SOG (inverse → SWS) | **SWS** (forward → SOG) |
| **Speed range** | [8, 18] kn continuous | [11, 13] kn, 0.1 grid, SOG must match | [11, 13] or [9, 15] kn, 0.1 grid on SWS |
| **FCR model** | ANN (8 inputs, vessel-specific) | `0.000706 × SWS³` | `0.000706 × SWS³` |
| **Weather in FCR** | Yes (direct ANN input) | No (weather → SOG only) | No (weather → SOG only) |
| **Weather source** | GEFS forecast (3/8 fields??) | YAML static, single window | HDF5, time-varying lookup |
| **Time-varying wx** | By stage (one forecast per stage) | **No** — always window 0 | **Yes** — `fh = f(current_hour)` |
| **Forecast degradation** | Not modeled | Not modeled | Not modeled |
| **Solver** | Dijkstra (NetworkX) | Sides BFS + inline relaxation | Forward Bellman DP |
| **Graph size** | ~35K nodes | 953K nodes (mostly empty) | ~278 × reachable time slots |
| **Solve time** | ~19 min | Not benchmarked (legacy) | ~160s |
| **Execution sim** | **None** — ANN evaluation only | None (optimizer only) | Full (SOG-targeting, Flow 2/3) |
| **Re-plan** | Rebuild from scratch, commit 1st speed | Not supported | 6h cycle, three agent types |
| **ETA constraint** | Hard (T_max) | Hard (grid boundary) | Hard or soft (λ penalty) |

---

## 3.5 Q&A Session — Refined Understanding (Apr 11)

A working session walked through Luo's planning logic step by step and clarified several over-stated differences from the prior comparison. Key refinements:

### 3.5.1 The Axis Inversion (Core Insight)

Both methods are structurally the same DP — they just **swap which axis is fixed and which floats**:

| | Luo | Ours |
|---|---|---|
| **Fixed per step** | Time (6h stage) | Distance (waypoint spacing) |
| **Floats per step** | Distance covered | Travel time |
| **One step** | 6h of sailing | One waypoint-to-waypoint leg |
| **Decision variable** | Speed for the next 6h | SWS for the next leg |
| **Solve scope** | All remaining stages at once | All remaining legs at once |
| **Commit** | First stage speed only | First 6h of speeds only |

Everything else (build full graph, find min-cost path, commit near-term, re-plan) is identical in both.

### 3.5.2 Luo's Stage Structure — How Nodes and Edges Work

Each stage is a fixed 6h time window. Distance covered depends on chosen speed (12 kn → 72 nm, 18 kn → 108 nm). Nodes within a stage = possible remaining-distance values, discretized at ζ = 1 nm.

**Connectivity**: Node `a` (remaining L_a) connects to every node `b` in the next stage where the implied speed `v = (L_a − L_b) / 6h` falls within [v_min, v_max]. This produces a band of reachable next nodes.

**Why ζ = 1 nm?** Because speed is implied by node geometry: `Δv = ζ / t_stage = 1/6 ≈ 0.167 kn`. So ζ is the indirect knob for speed resolution. In ours, speed resolution is set explicitly via the SWS list (0.1 kn).

**Solve**: Build the entire graph (all stages), prune zero-outdegree nodes, run Dijkstra once globally (not stage-by-stage). Commit only v_1, then re-plan.

### 3.5.3 Weather Logic — Both Methods Use the Same Principle

Both methods use **weather at the source node's position** for all edges leaving that node. The earlier framing that Luo "uses one weather for all edges from a" while we use "different weather per edge" was wrong — both follow the same per-source-node rule.

The real difference is **spatial granularity**:

| | Spatial step | Weather updates every... |
|---|---|---|
| Luo | 72–108 nm (= speed × 6h) | 72–108 nm |
| Ours | 1–5 nm (route-dependent waypoint spacing, fixed per route) | 1–5 nm |

**Our finer waypoint spacing is a substantial advantage** — much better spatial weather resolution along the route. This wasn't emphasized enough in the previous comparison.

For temporal alignment, both methods get the right forecast time per stage/leg:
- Luo: stage k uses GEFS forecast at `t + (k−1)×6h`
- Ours: leg at time t uses `weather_grid[node_id][fh]` where `fh = round(t + time_offset)`

Within a 6h cycle the optimizer assumes weather is constant — true for both.

### 3.5.4 The Conditional Equivalence (Important Honest Finding)

**If actual weather keeps SOG within [v_min, v_max] for every leg, then SWS = SOG and our method becomes equivalent to Luo's** in terms of execution behavior:
- Planned speed = actual speed
- Planned arrival = actual arrival
- No Flow 2/3 events

The two implementations only diverge at the boundaries:
- **Flow 2** (weather too bad): even at SWS = max, SOG drops below the speed needed to make ETA → ship falls behind
- **Flow 3** (weather too favorable): at SWS = min, SOG exceeds what's needed → ship arrives early

Luo has no mechanism for either — his ship always achieves exactly the planned speed regardless of weather feasibility.

**Implication for experiments**:
- Narrow speed range [11, 13] kn → Flow 2/3 events frequent → big difference from Luo
- Wide range [8, 18] kn (Luo's setup) → Flow 2/3 events rare → results converge toward Luo's

This is the strongest argument for testing with [8, 18] kn — it isolates whether the remaining differences (FCR model, waypoint structure) matter independently of the SWS/SOG gap.

### 3.5.5 The Real Fundamental Difference: FCR Model

The previous comparison overstated the "execution simulation" difference. With known weather over a 6h cycle, both methods know exactly where the ship will be. The actual fundamental difference is the **FCR model**:

```
Luo:  fuel = ANN(speed, weather) × 6h
            ↑ weather directly affects fuel rate

Ours: fuel = 0.000706 × SWS³ × travel_time
            ↑ weather only affects SOG → travel_time
              weather has NO direct effect on fuel rate
```

In Luo, headwinds increase fuel directly (same speed → more fuel in bad weather). In ours, headwinds slow the ship → longer travel time → more total fuel. The pathway differs even when end results converge.

### 3.5.6 Luo's "Simulation" — Refined Understanding

Luo does re-plan ~44 times (every 6h) for a 261h voyage — that's the rolling horizon. But evaluation is post-hoc:

```
Planning phase:  44 re-plans → committed speed profile (v_1, v_2, ..., v_44)
Evaluation:      feed (v_1..v_44) + ERA5 actual weather → ANN → total fuel
```

No ship movement, no execution loop. Just one ANN evaluation pass at the end.

His four metrics (FC_proposed, FC_constant, FC_static, FC_actual) all use the same evaluation: ANN(speed, ERA5 actual weather). The differences come only from the **speed profile**, not from any plan-vs-reality gap.

**FC_constant** = optimal constant speed = `v_c = L / T_max` (slowest feasible, since FCR is convex increasing). Same v_c every segment, weather varies → fuel rate varies.

His 9.46% claim ("rolling horizon vs constant speed") is therefore a **planning quality** comparison — "were our planned speeds better than constant?" — not an **execution quality** claim.

### 3.5.7 ETA Constraint — Both Hard

Luo enforces T_max as a hard constraint via graph construction: `N^k = floor((T^k − (T − Δt)) / T) + 2`. Reachable node bounds per stage are computed from [v_min, v_max], and pruning removes nodes that can't reach the sink at remaining_distance = 0 within remaining time.

Ours does the same via the time-slot iteration: paths exceeding `max_time_slots` are dropped, and the final selection picks min-cost arrival within ETA (or with λ penalty for soft-ETA).

Identical in spirit.

### 3.5.8 Algorithm Choice — Bellman vs Dijkstra

Both graphs are DAGs (Luo's stages and our waypoints both go forward). Either algorithm works on either graph.

- **Luo uses Dijkstra** (NetworkX): O(E log V) — general-purpose, discovers traversal order via priority queue
- **Ours uses forward Bellman**: O(W × T × S) — exploits known topological order, sweep forward, no priority queue needed

For a DAG, forward Bellman is slightly more efficient. Luo's Dijkstra choice is a minor inefficiency.

### 3.5.9 Complexity Side-by-Side

| | Luo | Ours |
|---|---|---|
| **Total nodes** | ~35K | ~8.3M (391 wp × 21,300 time slots) |
| **Fan-out per node** | ~60 (speed band) | 61 (SWS candidates) |
| **Total edges** | ~2.1M | ~500M |
| **Solver** | Dijkstra O(E log V) → ~30M ops | Bellman O(W·T·S) → ~500M ops |
| **Solve time** | ~19 min | ~160 s |

Why the gap? Luo's coarse 6h time steps (44 stages for a 261h voyage) keep the graph small at the cost of temporal resolution. Our fine 0.1h time slots (21,300 per voyage) explode the state space but give much better travel time accuracy.

### 3.5.10 Time-Granularity Gotcha (dt Matters)

For our DP with dt = 1h (legacy): a typical leg takes `2 nm / 12 kn ≈ 0.167h`, ceiled to 1h — huge overestimate. With dt = 0.1h (pipeline): same leg ceiled to 0.2h — much better. **Finer waypoint spacing demands finer dt** to avoid accumulating rounding error across hundreds of legs.

### 3.5.11 Updated Honest Differentiation Summary

The cleaner story to tell the supervisor:

| Aspect | Real difference? |
|---|---|
| Graph topology (time-stages vs waypoints) | Cosmetic — axis inversion of the same DP |
| Solve algorithm (Dijkstra vs Bellman) | Cosmetic — both work on DAGs |
| Per-cycle weather assumption | Same — both treat weather as constant within 6h |
| Replan logic | Same — both rebuild and commit first speed |
| ETA constraint | Same — both hard |
| **Spatial weather resolution** | **Real — ours is 1–5 nm, theirs is 72–108 nm** |
| **FCR model** | **Real — ANN with weather input vs cubic without** |
| **SWS/SOG split** | **Real, but only matters at Flow 2/3 boundaries** |
| **Execution simulation** | **Real, but only meaningful when SOG escapes [v_min, v_max]** |

The narrow [11, 13] kn range amplifies the SWS/SOG and execution differences. A direct test against Luo at [8, 18] kn would isolate the FCR model and spatial resolution as the remaining distinguishers.

---

## 4. Data Collection Status (updated Apr 8)

| Server | Status | Route B (138 wp) | Route D (391 wp) | Uptime |
|--------|--------|-------------------|-------------------|--------|
| Shlomo1 | **Offline** (no ping) | - | - | Down since ~Mar 21 |
| Shlomo2 | Running | 37 MB (+10) | 107 MB (+27) | 33 days, load 4.25 |
| Edison | Running | 37 MB (+10) | 107 MB (+28) | 30 days, load 0.00 |

Both `collect_all` tmux sessions active since Mar 17-18. Shlomo2 under heavy load from other users' ML jobs (3 active python processes at ~140% CPU each). Edison is idle — collection running smoothly.

Exp C (Yokohama-Long Beach) stalled at ~92 KB on both servers — still removed from `run_all.py`.

---

## 5. Results

*(to be filled as new experiments complete)*

---

## 6. Questions for Supervisor

1. **Luo's missing wave data**: Their ANN was trained with wave data (ERA5) but optimizes without it (GEFS has no waves). Should we highlight this as a methodological weakness in our paper?

2. **Luo's "simulation" isn't a simulation**: They evaluate all scenarios by feeding speeds + actual weather into the ANN. No plan-vs-reality gap. This is a fundamental limitation — their results assume the ship achieves exactly the planned speed. Should we position our SOG-targeting execution as a key differentiator?

3. **Speed range**: Should we match their [8, 18] kn for a direct comparison, or stick with a realistic EEXI range and argue that narrow ranges are more operationally relevant?

4. **Graph structure**: Should we adopt their time-based segmentation (stages = 6h forecast cycles) or keep our spatial segmentation? Time-based aligns better with forecast resolution; spatial aligns better with route structure.

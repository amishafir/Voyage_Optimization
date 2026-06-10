# Meeting Prep — Supervisor Meeting, Mar 30 2026

---

## 1. Action Items from Mar 23 Meeting

| # | Task | Status |
|---|------|--------|
| 1 | Implement new 3-agent setup (Naive, Deterministic, Stochastic) | **DONE** |
| 2 | All agents re-plan on same 6h cycle | **DONE** |
| 3 | Run experiments on collected data (Route B + Route D) | **DONE** |
| 4 | Design decisions documented (agent_design_QA.md) | **DONE** |

---

## 2. Data Collection Status

| Server | Status | Route B (138 wp) | Route D (391 wp) |
|--------|--------|-------------------|-------------------|
| Shlomo1 | Offline (since Mar 21+) | - | - |
| Shlomo2 | Running (since Mar 18) | 26 MB | 77 MB |
| Edison | Running (since Mar 17) | 26 MB | 76 MB |

Exp C (Yokohama-Long Beach, 968 wp) stalled since Mar 9 — removed from `run_all.py`.

---

## 3. 3-Agent Implementation

New cycle executor: all three agents re-plan every 6h on NWP-aligned boundaries. Differences are purely in weather information used at re-plan time.

| Agent | Weather at re-plan | Beyond 6h assumption |
|-------|-------------------|---------------------|
| **Naive** | None | Constant SOG = remaining_dist / remaining_time |
| **Deterministic** | Actual at all waypoints | Current actuals persist forever |
| **Stochastic** | Actual (current 6h) + forecast (future) | NWP forecast degrades with lead time |

Design decisions: `docs/agent_design_QA.md` (8 questions, all answered).

Code: `pipeline/agent/cycle_executor.py`, `weather_assembler.py`, `new_runner.py`. 11 tests passing.

---

## 4. Results — 3-Agent Experiments

### Summary table — Fuel (mt), all experiments, 6h replan

| Agent | Route B dep=6 [11,13] | Route D dep=0 [11,13] | Route D dep=60 [11,13] | Route D dep=0 [9,15] | Route D dep=60 [9,15] |
|-------|----------------------|----------------------|------------------------|---------------------|----------------------|
| **Naive** | 352.85 | 216.61 | 216.68 | 216.54 | 216.54 |
| **Deterministic** | 355.01 | 216.58 | 217.03 | 216.44 | 216.40 |
| **Stochastic** | 354.49 | 216.79 | 216.93 | 217.59 | 217.44 |
| **Spread** | 2.15 (0.6%) | 0.21 (0.1%) | 0.35 (0.2%) | 1.15 (0.5%) | 1.04 (0.5%) |
| **Best** | Naive | Det | Naive | Det | Det |

Spread = worst agent fuel - best agent fuel. All differences under 1%.

### 4.1 Initial runs with [11, 13] kn speed range

**Route D, Departure SH=0 (mild)**: All agents within 0.21 mt (0.1%).
**Route D, Departure SH=60 (storm)**: All agents within 0.35 mt (0.2%).
**Route B, Departure SH=6 (calm)**: All agents within 2.15 mt (0.6%).

Conclusion: [11, 13] kn is too narrow — optimizer has no room to differentiate.

### 4.2 Widened speed range [9, 15] kn — 6h replan only

**Route D, Departure SH=60 (storm)**:

| Agent | Fuel (mt) | Time (h) | Delay | Flow2 |
|-------|----------|----------|-------|-------|
| Deterministic | **216.40** | 163.0 | -0.01 | 0 |
| Naive | 216.54 | 163.0 | +0.00 | 0 |
| Stochastic | 217.44 | 163.0 | -0.01 | 0 |

Spread: 1.04 mt (0.5%). Better than [11,13] kn but still small.

### 4.3 Full 3x2 matrix — no-replan vs 6h replan (KEY RESULT)

**Route D, Departure SH=60 (storm), speed range [9, 15] kn**:

| Agent | No-replan | 6h replan | Savings from replan |
|-------|----------|----------|-------------------|
| **Naive** | 216.54 | 216.54 | 0.00 mt (0.0%) |
| **Deterministic** | 218.01 | **216.40** | 1.61 mt (0.7%) |
| **Stochastic** | 220.09 | 217.44 | 2.65 mt (1.2%) |

Full table with details:

| Agent | Fuel (mt) | Time (h) | Delay | Flow2 | Re-plans |
|-------|----------|----------|-------|-------|----------|
| Naive (no-replan) | 216.54 | 163.0 | -0.00 | 0 | 1 |
| Deterministic (no-replan) | 218.01 | 162.7 | -0.27 | 1 | 1 |
| Stochastic (no-replan) | **220.09** | 162.6 | -0.41 | 1 | 1 |
| Naive (6h) | 216.54 | 163.0 | +0.00 | 0 | 18 |
| **Deterministic (6h)** | **216.40** | 163.0 | -0.01 | 0 | 18 |
| Stochastic (6h) | 217.44 | 163.0 | -0.01 | 0 | 18 |

### 4.4 Key findings

1. **Without re-planning, more information = more fuel.** Stochastic (220.09) > Deterministic (218.01) > Naive (216.54). The optimizer creates aggressive variable-speed profiles based on weather predictions that don't match reality. The planned speed variation interacts with actual weather through Jensen's inequality on the cubic FCR: `E[FCR(V_s)] >= FCR(E[V_s])`. Constant speed (Naive) avoids this penalty entirely.

2. **Re-planning reverses the ranking for Deterministic.** With 6h updates, Deterministic becomes cheapest (216.40 mt). It corrects its stale plans before errors accumulate. This is the "value of re-planning with observations."

3. **Re-planning helps informed agents more.** Stochastic saves 2.65 mt from re-planning (1.2%), Deterministic saves 1.61 mt (0.7%), Naive saves nothing. Re-planning has no value without information to update.

4. **Naive is remarkably robust.** 216.54 mt regardless of re-planning mode. It's the baseline that neither over-optimizes nor under-optimizes. This is a publishable result: constant-speed sailing is hard to beat when re-planning is available.

5. **Stochastic underperforms Deterministic in both modes.** The forecast adds noise that hurts the optimizer. The "value of forecast" over observations is negative in these experiments. Possible explanation: forecast errors at 6h+ lead time inject systematic bias that makes the DP plan worse, not better.

6. **Total spread: 3.69 mt (1.7%).** Modest compared to Luo's 4-15%, but Luo uses [8, 18] kn range (10 kn span vs our 6 kn) and a different ship/route.

---

## 5. Competing Papers Analysis

Supervisor provided 3 papers. Two are direct competitors:

### Paper 1: Luo et al. 2024 (Transportation Research Part C) — **HIGH THREAT**

**"Ship sailing speed optimization considering dynamic meteorological conditions"**

- ANN-based FCR + multistage graph (Dijkstra) re-optimized every 6h aligned to NOAA GFS
- Capesize bulk carrier, speed range [8, 18] kn, two 11-day voyages
- Results: 5.35% savings vs constant speed, 7.34% vs static optimization
- Forecast-vs-actual gap: **4.10% and 15.34%** on two voyages
- Published in **TRC** (our target journal)
- Same core architecture as ours (graph + 6h NWP re-plan)

**What they don't have (our advantages)**:
- No SWS/SOG distinction — no Jensen's inequality analysis
- ANN black-box FCR (vessel-specific, non-transferable) vs our physics-based model
- No LP formulation — graph-only
- Only 2 voyages, no departure sensitivity or multi-route comparison
- No clean information hierarchy experiment (our 3-agent design)
- Speed range 10 kn wide — their optimizer has much more room to maneuver

### Paper 2: Marjanovic et al. 2026 (J. Mar. Sci. Eng.) — **MEDIUM THREAT**

**"Waypoint-Sequencing MPC for Ship Weather Routing Under Forecast Uncertainty"**

- MPC with waypoint sequencing (heading + speed), 6h control / 24h prediction horizon
- NN ship speed model from NTPro 5000 simulator (R²=0.999)
- Multi-objective: 60% fuel, 30% safety, 10% smoothness, discount factor gamma=0.95
- 21 transatlantic voyages (Rotterdam-New York), hindcast weather
- Results: 6.1% vs traditional, 2.6% gap vs perfect information

**What they don't have**:
- Only 3 discrete speeds {12.0, 13.5, 14.5} kn — extremely coarse
- Multi-objective muddles fuel signal (safety + smoothness penalties)
- Simulator-trained NN, not real operational data
- No LP vs DP comparison
- Route optimization (different problem — they change heading, we fix route)

### Paper 3: Li et al. 2022 (J. Mar. Sci. Eng.) — **LOW THREAT**

**"Speed Optimization of Container Ship Considering Route Segmentation and Weather Data Loading"**

- ML-based FCR (Extra Trees + polynomial regression), container ship 12-24 kn
- Iterative weather loading at departure — **no rolling horizon, no re-planning**
- 2.1% and 5.2% fuel savings vs actual
- Static optimization with smarter weather loading, that's all

### Comparative Matrix

| Dimension | Li 2022 | Luo 2024 | Marjanovic 2026 | **Ours** |
|-----------|---------|----------|-----------------|---------|
| FCR model | ML | ML (ANN) | ML (NN) | **Physics** |
| Optimizer | Single-pass | Dijkstra | MPC | **LP + DP** |
| Re-planning | None | 6h NWP | 6h MPC | **6h NWP** |
| Speed range | 12-24 kn | 8-18 kn | 3 speeds | 11-13 kn |
| SWS vs SOG | No | No | Partial | **Yes** |
| Jensen's ineq. | No | No | No | **Yes** |
| Info hierarchy | No | Post-hoc e3 | No | **3-agent design** |
| Weather data | ERA5 | NOAA GEFS | GFS hindcast | **Live Open-Meteo** |

---

## 6. Critical Issue: Speed Range

Our [11, 13] kn range may be too narrow to produce meaningful differences between agents. Comparison:

| Paper | Speed range | Span | Fuel savings |
|-------|-----------|------|-------------|
| Li 2022 | 12-24 kn | 12 kn | 2.1-5.2% |
| Luo 2024 | 8-18 kn | 10 kn | 5.35-7.34% |
| Marjanovic 2026 | 12-14.5 kn | 2.5 kn | 6.1% |
| **Ours** | **11-13 kn** | **2 kn** | **0.1-0.6%** |

Marjanovic gets 6.1% with only 2.5 kn span but they also optimize heading (route changes). With fixed route + 2 kn span, there may not be enough decision space for weather information to matter.

**Question: Should we widen the speed range for the paper experiments?** Even [10, 14] kn (4 kn span) would double the optimizer's decision space.

---

## 7. Questions for Supervisor

1. **Speed range**: Current [11, 13] kn produces <1% differences between agents. Widen to [10, 14] or [9, 15] kn? Or is the narrow range itself a finding (EEXI-constrained vessels have limited optimization potential)?

2. **Luo 2024 differentiation**: They published in TRC with the same architecture (graph + 6h NWP re-plan). Our strongest differentiators are physics-based FCR, SWS/SOG distinction, Jensen's inequality, and the 3-agent information hierarchy. Is this enough, or do we need additional contributions?

3. **Paper framing**: The supervisor's proposed contributions from the .tex feedback are:
   - Static speed control (LP)
   - Dynamic speed control (DP with time-varying weather)
   - Online control in stochastic environment (RH)
   - **Evaluating the value of forecast** (3-agent experiment)

   Should the "value of forecast" be the primary contribution, with LP/DP/RH as the methodological tools?

4. **No-replan baseline**: Should we add experiments with single-plan-at-departure (no re-planning) alongside the 6h cycle? The gap between replan and no-replan would isolate the value of re-planning itself.

5. **Supervisor's .tex feedback**: Several structural comments need addressing:
   - "Don't claim contribution is empirical comparison" — need methodological novelty
   - "What's the difference from Tzortzis 2021?" — and now also from Luo 2024
   - "List is too long" — narrow to 2-4 strongest contributions
   - Various writing style issues (long dashes, acronyms, citation format)

---

## 8. Meeting Outcome — Mar 31

### Strategic shift: focus on Luo 2024 comparison

Supervisor directed a shift in priorities. The primary effort is now to understand and position against Luo et al. 2024 (TRC), our closest competitor. Three action items:

**Action 1: Deep-dive into Luo's weather forecast resolution**

Luo's key structural difference: they segment the voyage by **time** (6h forecast cycles), not by **space** (waypoints). Each segment = one NWP cycle. Weather within a segment is constant (conditions at segment start from the latest forecast). We need to understand:
- How their 0.5 degree spatial resolution maps to segment-level weather
- How the 6h temporal resolution creates the graph stages
- What happens at forecast boundaries (does the ship see a "jump" in weather?)

**Action 2: Revisit the DP graph structure in `speed_control_optimizer.py`**

The existing DP builds a time-distance graph where:
- X-axis = distance (remaining nm to destination)
- Y-axis = time (hours from departure)
- Nodes = (distance, time) pairs at discretized intervals
- Edges = speed choices connecting nodes across time steps

The supervisor's sketch shows this graph with time layers at 6, 11, 18h and distance at 100, 200, 300 nm. The critical question: **where does forecast resolution enter this graph?**

Currently, each node looks up weather at `forecast_hour = round(time + time_offset)`. All nodes at the same time see the same forecast vintage. The Luo approach is similar but their graph stages ARE the forecast cycles.

What needs to change: the DP should be aware that weather data quality changes at 6h boundaries. Nodes within the same 6h window share one forecast; nodes in the next window get a fresher forecast (if re-planning) or a more degraded one (if not).

**Action 3: Adjust algorithm for forecast resolution awareness**

The DP optimizer currently treats the weather grid as a flat lookup: `weather_grid[node_id][forecast_hour]`. It doesn't distinguish between:
- Forecast hour 1 (very accurate, just issued)
- Forecast hour 100 (highly degraded, issued days ago)

To match Luo's structure and properly evaluate forecast value, the optimizer should incorporate forecast resolution — either through the weather assembler (providing different quality data at different lead times) or through the graph structure itself (weighting edges differently based on forecast confidence).

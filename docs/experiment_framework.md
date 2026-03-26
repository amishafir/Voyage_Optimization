# Experiment Framework — Planning vs Realization

---

## 1. Two-Phase Structure

Every experiment follows the same two-phase structure:

### Phase 1: Planning
The optimizer creates a speed plan (target SOG per segment/leg) based on the **weather forecast available at departure**. The plan provides:
- Target SOG for each segment
- Estimated fuel consumption
- Estimated arrival time

The plan assumes the weather forecast is representative of actual conditions during the voyage.

**ETA is a soft constraint with penalty:**

The optimizer minimizes:

```
Total Cost = Fuel (mt) + λ × max(0, arrival_time − ETA)
```

Where λ (mt/hour) is the **ETA penalty** — the cost of being late, expressed in fuel-equivalent units. This allows the optimizer to trade off fuel savings against schedule adherence:
- λ = 0: minimize fuel only, ignore ETA entirely
- λ → ∞: hard ETA constraint (current behavior)
- λ = practical value: balance fuel and punctuality

The penalty converts delay hours into equivalent fuel cost, making the objective single-dimensional. For example, λ = 2 mt/h means each hour of delay "costs" 2 mt of fuel — the optimizer will accept a 1-hour delay only if it saves more than 2 mt of fuel.

**Choosing λ:** In practice, the penalty reflects the economic cost of late arrival (port fees, demurrage, charter costs) converted to fuel-equivalent units. For the experiments, we test multiple λ values to show how the fuel-vs-punctuality trade-off changes across approaches. A sensitivity sweep of λ ∈ [0.5, 1, 2, 5, 10, ∞] maps the Pareto frontier for each approach.

### Phase 2: Realization (Simulation)
The ship executes the plan under **actual weather**. At each leg:
1. Determine the target SOG from the plan
2. Compute the SWS required to achieve that SOG under actual weather
3. **Never violate SWS bounds** [11, 13] kn
4. If required SWS > 13 → use SWS = 13, accept lower SOG, accumulate delay
5. Compute actual fuel = FCR(actual_SWS) × actual_time

**Realization total cost** = actual fuel + λ × max(0, actual_arrival − ETA)

This makes all approaches comparable on a single metric: total cost in fuel-equivalent units. An approach that saves fuel but arrives late may have higher total cost than one that burns more fuel but arrives on time.

---

## 2. Two Realistic Flows During Realization

### Flow 1: Ship achieves planned SOG
- Actual weather is close enough to forecast that the required SWS stays within [11, 13]
- Ship arrives at each segment boundary on time
- Fuel may differ from plan (because actual FCR depends on actual SWS, not planned SWS)
- **No re-planning needed**

### Flow 2: Ship cannot achieve planned SOG
- Weather is harsher than forecast → required SWS > 13 kn
- Ship sails at SWS = 13 (maximum allowed), actual SOG < planned SOG
- Ship falls behind schedule → **a decision must be made**
- How the decision is handled depends on the environment setting (see Section 3)

---

## 3. Environment Settings (3 levels)

| Setting | Description | Re-planning | Weather for re-plan |
|---------|-------------|-------------|---------------------|
| **A. No compute during voyage** | Ship follows the initial plan, no re-optimization | None | N/A |
| **B. Compute, no weather update** | Ship can re-optimize from current position | Yes, when Flow 2 occurs | Original forecast (stale) |
| **C. Compute, with weather update** | Ship can re-optimize with fresh forecast | Yes, when Flow 2 occurs | Fresh forecast at current time |

---

## 4. Model Types (2 levels)

| Model | Planning Resolution | Description |
|-------|--------------------|-------------|
| **LP** | Segment-averaged | One SOG per segment, weather averaged across nodes |
| **DP** | Per-node | One SOG per leg, time-varying weather |

---

## 5. The 6 Experiment Combinations

### LP-A: LP, No compute during voyage
- **Plan**: LP solves once at departure with forecast weather (segment-averaged)
- **Flow 1**: Ship sails planned SOG per segment. Fuel differs from plan due to within-segment weather variation.
- **Flow 2**: Ship sails at SWS = 13 until end of current segment. Then continues with original plan for remaining segments. Accumulates delay.
- **Key question**: How much does segment averaging cost when weather varies within segments?

### LP-B: LP, Compute without weather update
- **Plan**: LP solves at departure with forecast weather
- **Flow 1**: Same as LP-A
- **Flow 2**: Ship reaches current position (mid-segment or segment boundary). Re-solves LP for remaining voyage from current position using **original forecast**. New plan accounts for accumulated delay (adjusted remaining ETA).
- **Key question**: Does re-planning with stale weather help LP recover from delays?

### LP-C: LP, Compute with weather update
- **Plan**: LP solves at departure with forecast weather
- **Flow 1**: Same as LP-A
- **Flow 2**: Re-solves LP for remaining voyage from current position using **fresh forecast**. New plan benefits from updated weather information.
- **Key question**: Does fresh weather + re-planning make LP competitive with DP?

### DP-A: DP, No compute during voyage
- **Plan**: DP solves once at departure with forecast weather (per-node, time-varying)
- **Flow 1**: Ship sails planned SOG per leg. Fuel differs from plan due to forecast error.
- **Flow 2**: Ship sails at SWS = 13 until end of current leg/segment. Then continues with original plan. Accumulates delay.
- **Key question**: How well does a single forecast hold over the full voyage?

### DP-B: DP, Compute without weather update
- **Plan**: DP solves at departure with forecast weather
- **Flow 1**: Same as DP-A
- **Flow 2**: Re-solves DP for remaining voyage from current position using **original forecast** (re-indexed from current time). Adjusts for accumulated delay.
- **Key question**: Does re-planning help DP even with the same forecast?

### DP-C: DP, Compute with weather update
- **Plan**: DP solves at departure with forecast weather
- **Flow 1**: Same as DP-C
- **Flow 2**: Re-solves DP for remaining voyage from current position using **fresh forecast**. This is the Rolling Horizon approach.
- **Key question**: How much does forecast freshness improve DP's performance?

---

## 6. Fuel Consumption Boundaries

### Optimal Bound
- **Plan**: Optimizer uses **actual weather** (perfect foresight) with penalty λ
- **Realization**: Weather during voyage equals the planning weather exactly
- **Result**: Zero plan-realization gap. No Flow 2 events (plan perfectly matches reality)
- **Meaning**: Best achievable total cost — no forecast error, no averaging error
- **Note**: At high λ, the optimal bound arrives on time. At low λ, it may accept delay for fuel savings.

### Upper Bound (Constant Speed)
- **Plan**: Constant SOG = total_distance / ETA at every leg
- **Realization**: Ship targets constant SOG under actual weather
- **Flow 2 handling**: If SOG cannot be achieved at SWS = 13, sail at SWS = 13 until end of current segment, then re-plan with a new constant SOG = remaining_distance / remaining_ETA
- **Meaning**: "No optimization" baseline — what a captain does without any tool
- **Total cost**: fuel + λ × delay (if any)

### Optimization Value
- **Definition**: Upper bound total cost − optimized total cost
- **Meaning**: The practical value each approach delivers over naive constant-speed sailing, accounting for both fuel and punctuality

---

## 7. When Does Re-Planning Trigger?

Re-planning (in settings B and C) triggers when **Flow 2** occurs — i.e., when the ship cannot achieve the planned SOG because required SWS exceeds 13 kn.

In practice, for the Rolling Horizon variant (DP-C / LP-C), re-planning also occurs at **fixed 6h intervals** aligned with the GFS NWP cycle, even if Flow 2 has not occurred. This captures two benefits:
1. **Reactive**: Recover from delays caused by harsh weather (Flow 2)
2. **Proactive**: Use fresher forecasts even when the plan is on track (Flow 1)

For settings B (no weather update), re-planning only makes sense reactively (triggered by Flow 2), since the forecast data is unchanged.

---

## 8. Mapping to Current Implementation

| Framework | Current Code | Notes |
|-----------|-------------|-------|
| LP-A | `static_det` (LP, no re-plan) | Exists — `run_exp_d.py::run_lp()` |
| LP-C | `dynamic_rh/optimize_lp.py` (RH-LP) | Exists — just implemented |
| LP-B | Not yet implemented | LP re-plan with stale forecast — new |
| DP-A | `dynamic_det` (DP, no re-plan) | Exists — `run_exp_d.py::run_dp()` |
| DP-C | `dynamic_rh/optimize.py` (RH-DP) | Exists — `run_exp_d.py::run_rh_dp()` |
| DP-B | Not yet implemented | DP re-plan with stale forecast — new |
| Optimal | `compute_bounds` (Lagrangian) | Exists |
| Upper (constant speed) | `sensitivity.run_constant_speed_bound()` | Exists |

### Still needed:
- **LP-B**: LP re-planning triggered by Flow 2, using original forecast
- **DP-B**: DP re-planning triggered by Flow 2, using original forecast
- **Simulation updates**: Flow 2 detection and re-planning trigger logic
- **Constant-speed Flow 2**: Re-plan constant speed after delay

---

## 9. Optimizer Formulation with ETA Penalty

### LP Formulation
```
Minimize:  Σ (distance_i × FCR_k / SOG_ik × x_ik)  +  λ × max(0, Σ(distance_i / SOG_ik × x_ik) − ETA)

Subject to:
  Σ x_ik = 1           for each segment i  (one speed per segment)
  SWS_k ∈ [11, 13]     engine limits (built into speed choices)
  x_ik ∈ {0, 1}        binary selection
```

The penalty term can be linearized for LP:
```
  δ ≥ 0                 (delay variable)
  δ ≥ Σ(distance_i / SOG_ik × x_ik) − ETA
  Minimize: fuel + λ × δ
```

### DP Formulation
The DP graph already explores all arrival times. The change is in the final-node selection:

Instead of: `find min fuel among states where t ≤ ETA`
Now: `find min (fuel + λ × max(0, t − ETA)) among all reachable states`

This naturally allows the DP to pick paths that exceed ETA if the fuel savings justify it.

---

## 10. Expected Results Pattern

| Approach | Forecast Error | Averaging Error | Re-planning | Expected Cost Rank |
|----------|---------------|-----------------|-------------|-------------------|
| Constant speed | N/A | N/A | Reactive only | Worst (baseline) |
| LP-A | Yes | Yes | None | Near constant speed |
| LP-B | Yes (stale) | Yes | Reactive | Slightly better than LP-A |
| LP-C | Reduced | Yes | Proactive + reactive | Better — fresh weather helps |
| DP-A | Yes | No | None | Better than LP (no averaging) |
| DP-B | Yes (stale) | No | Reactive | Slightly better than DP-A |
| DP-C | Reduced | No | Proactive + reactive | Best — fresh weather + no averaging |
| Optimal | None | No | N/A | Theoretical minimum |

The hierarchy should be: Optimal < DP-C < DP-B < DP-A < LP-C < LP-B < LP-A ≈ Constant Speed

This decomposition isolates three effects:
1. **Averaging effect**: LP-A vs DP-A (same forecast, different resolution)
2. **Re-planning effect**: X-A vs X-B (same forecast, with/without re-plan)
3. **Forecast freshness effect**: X-B vs X-C (re-plan with stale vs fresh forecast)

Additionally, sweeping λ produces a **Pareto frontier** for each approach: the trade-off between fuel and delay. Approaches with better forecasts and finer resolution should dominate (lower fuel at every delay level).

---

## 11. λ Sensitivity Analysis

Running each approach at multiple λ values reveals:

| λ (mt/h) | Interpretation | Expected behavior |
|----------|---------------|-------------------|
| 0 | No ETA penalty | Min fuel, possibly very late |
| 0.5 | Low penalty | Accept significant delay for fuel savings |
| 1 | Moderate | Balance fuel and punctuality |
| 2 | High | Strongly prefer on-time arrival |
| 5 | Very high | Accept almost no delay |
| ∞ | Hard constraint | Current behavior (must arrive on time) |

**Key research question**: At what λ does each approach's ranking change? If LP-C (re-planning LP with fresh weather) becomes competitive with DP-A at moderate λ, that's a strong practical recommendation — LP is simpler to implement operationally.

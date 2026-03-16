# Meeting Prep — Supervisor Meeting, Mar 23 2026

---

## 1. Action Items from Mar 16 Meeting

| # | Task | Status | Notes |
|---|------|--------|-------|
| D1 | No SWS violations — relax ETA | TODO | Change simulation: SWS never exceeds [11, 13], accept late arrival |
| D2 | Test RH with LP | TODO | New approach: LP re-solved every 6h with fresh weather |
| D3 | Realistic upper bound (constant speed) | TODO | Replace SWS=13 bound with constant SOG = D/ETA |
| D4 | Clarify plan vs simulation framework | TODO | Write clear matrix for all approaches |

---

## 2. Planning vs Simulation Framework (D4)

### What is the experiment?

Each approach is evaluated in two phases:
1. **Planning**: The optimizer chooses a speed schedule (SOG per leg) using whatever weather data it has access to.
2. **Simulation**: The ship executes the plan under actual weather. At each leg, the simulator determines what SWS the engine must set to achieve the planned SOG given actual conditions.

The gap between plan and simulation reveals how well each optimizer's assumptions hold in reality.

### The Four Approaches

#### LP (Static Deterministic)
| Phase | Details |
|-------|---------|
| **Plans with** | Actual weather at hour 0, averaged across segments (~39 nodes per segment) |
| **Resolution** | 10 segments (Route 2) or 6 segments (Route 1) — one SOG per segment |
| **Objective** | Minimize total fuel subject to ETA, SWS ∈ [11, 13] |
| **Simulated against** | Actual weather at hour 0, per-node |
| **Mismatch tested** | Segment averaging: does the average represent the individual nodes? |

#### DP (Dynamic Deterministic)
| Phase | Details |
|-------|---------|
| **Plans with** | Predicted weather from forecast origin (hour 0), time-varying per node |
| **Resolution** | Per-node (389 or 138 nodes), forecast_hour = cumulative transit time |
| **Objective** | Minimize total fuel subject to ETA, SWS ∈ [11, 13] |
| **Simulated against** | Actual weather at hour 0, per-node |
| **Mismatch tested** | Forecast error: does the forecast match reality? |

#### RH-DP (Rolling Horizon with DP)
| Phase | Details |
|-------|---------|
| **Plans with** | At each 6h decision point: fresh predicted weather + actual weather injected for committed window |
| **Resolution** | Per-node, re-solved every 6h |
| **Objective** | Minimize remaining fuel subject to remaining ETA, SWS ∈ [11, 13] |
| **Simulated against** | Actual weather at each leg's transit time (time-varying) |
| **Mismatch tested** | Residual forecast error within 6h windows |

#### RH-LP (Rolling Horizon with LP) — NEW
| Phase | Details |
|-------|---------|
| **Plans with** | At each 6h decision point: fresh actual weather, segment-averaged |
| **Resolution** | Segments (re-computed per window), re-solved every 6h |
| **Objective** | Minimize remaining fuel subject to remaining ETA, SWS ∈ [11, 13] |
| **Simulated against** | Actual weather at each leg's transit time (time-varying) |
| **Mismatch tested** | Segment averaging with fresh weather — does re-planning compensate for averaging? |

### Key Questions Each Approach Answers

| Approach | Question |
|----------|----------|
| LP | What happens when you average weather across segments? |
| DP | What happens when you use a single forecast for the whole voyage? |
| RH-DP | What happens when you refresh the forecast every 6h? |
| **RH-LP** | **What happens when you re-average segments every 6h with fresh weather?** |

The RH-LP question is important: if LP's problem is segment averaging AND stale weather, does fixing the staleness (via 6h re-planning) compensate for the averaging? If RH-LP ≈ RH-DP, then the simpler LP approach is sufficient when combined with re-planning.

---

## 3. Simulation Changes for No-Violation Mode (D1)

### Current behavior (violation mode)
```
For each leg:
  1. Look up planned SOG
  2. Compute required SWS given actual weather
  3. If SWS > 13: clamp to 13, record violation, SOG < planned
  4. If SWS < 11: clamp to 11, record violation, SOG > planned
  5. Compute fuel = FCR(clamped_SWS) × time
```

### New behavior (soft-ETA mode)
```
For each leg:
  1. Look up planned SOG
  2. Compute required SWS given actual weather
  3. If SWS > 13: use SWS = 13, compute actual SOG (< planned), accept delay
  4. If SWS < 11: use SWS = 11, compute actual SOG (> planned), arrive early
  5. Compute fuel = FCR(actual_SWS) × actual_time
  6. Track cumulative delay / advance
```

### What changes in the results
- **No more "violations"** — every leg uses valid SWS
- **Arrival deviation** becomes the key feasibility metric
- LP and DP on Route 2 will show **higher fuel** (no clamping discount) and **late arrival**
- The "below optimal bound" artifact disappears
- RH should still arrive near on-time (small deviations)

---

## 4. Constant-Speed Baseline (D3)

### Definition
- SOG = total_distance / ETA at every leg
- Route 1: SOG = 1678 / 140 = 11.99 kn
- Route 2: SOG = 1955 / 163 = 12.00 kn

### In the simulation
- At each leg, compute SWS needed to achieve constant SOG under actual weather
- If required SWS is outside [11, 13], use the limit (soft-ETA mode)
- Report fuel and arrival deviation

### Why this is the right baseline
- Represents "what a captain does with no optimization tool" — pick a constant speed and go
- The optimization span becomes: constant-speed fuel − optimized fuel
- This is the **practical value** of the optimizer to an operator

### Expected results
- On Route 1 (mild): constant speed ≈ LP (we already showed LP ≈ constant speed at 367.9 vs 368.0 mt)
- On Route 2 (harsh): constant speed should be worse than RH, comparable to or worse than LP
- This reframes the narrative: RH's value is measured against "doing nothing smart"

---

## 5. RH-LP Implementation Plan (D2)

### Architecture
```
For each 6h decision window:
  1. Determine remaining legs and remaining ETA
  2. Aggregate remaining legs into segments (recompute segment boundaries)
  3. Read actual weather at current decision hour
  4. Average weather per segment
  5. Solve LP: minimize fuel subject to remaining ETA, SWS ∈ [11, 13]
  6. Extract SOG for the committed 6h window
  7. Advance ship position, update cumulative time/fuel
  8. Repeat
```

### Key design decisions
- **Segment re-computation**: At each decision point, the remaining legs are re-segmented. Use same segment count logic as static LP (proportional to remaining distance).
- **Weather source**: Actual weather at decision hour (same as RH-DP's actual weather injection)
- **Committed window**: 6h of legs, same as RH-DP
- **LP solver**: PuLP or Gurobi, same as static LP

### Files to create/modify
- `pipeline/dynamic_rh/optimize_lp.py` — new RH-LP optimizer
- `pipeline/run_exp_d.py` — add RH-LP to the comparison
- `pipeline/run_exp_b.py` — add RH-LP to the comparison

---

## 6. Updated Results Table Format (after all changes)

Once D1–D4 are implemented, the results table becomes:

| Approach | Sim Fuel (mt) | Arrival Deviation (h) | vs Constant Speed |
|----------|--------------|----------------------|-------------------|
| Constant speed (baseline) | ??? | ??? | — |
| LP (static det.) | ??? | ??? | ??? |
| DP (dynamic det.) | ??? | ??? | ??? |
| RH-DP (rolling horizon, DP) | ??? | ??? | ??? |
| **RH-LP (rolling horizon, LP)** | **???** | **???** | **???** |
| *Optimal bound* | ??? | 0 | ??? |

- No violations column needed (SWS always valid)
- Arrival deviation replaces violation count as feasibility metric
- "vs Constant Speed" shows practical value of each optimizer

---

## 7. Revised TODO List

### This week (Mar 16–23)

| # | Task | Priority | Est. |
|---|------|----------|------|
| 1 | Implement soft-ETA simulation mode (D1) | **High** | 2h |
| 2 | Implement constant-speed baseline (D3) | **High** | 1h |
| 3 | Re-run Route 1 + Route 2 with soft-ETA mode | **High** | 1h |
| 4 | Implement RH-LP optimizer (D2) | **High** | 4h |
| 5 | Run RH-LP on both routes | **High** | 2h |
| 6 | Write plan vs simulation framework doc (D4) | **Medium** | 1h |
| 7 | Update §6 (Results) with new tables | **Medium** | 2h |
| 8 | Move sections 5–8 into LaTeX | Low | 3h |

### Deferred
- Abstract — after results stabilize
- Gap summary table (§2.6)
- Gap-free Route 1 re-run (data accumulating, ready ~Mar 18)

---

## 8. Questions for Next Meeting

1. **RH-LP segment count**: How many segments per window? Same ratio as static LP (6 segments for 138 nodes), or fewer for shorter windows?
2. **Soft-ETA penalty**: Should we add a fuel penalty for late arrival in the objective, or just report deviation as a separate metric?
3. **Optimal bound update**: The current optimal bound uses time-varying actual weather with no ETA constraint. Under soft-ETA mode, should we redefine it as "best achievable with on-time arrival"?
4. **Paper structure**: With 5 approaches (constant, LP, DP, RH-DP, RH-LP) plus optimal bound, the results tables grow. Should we split into "main comparison" (4 approaches) and "sensitivity" (sweeps)?

# Meeting Prep — Supervisor Meeting, Mar 23 2026

---

## 1. Action Items from Mar 16 Meeting

| # | Task | Status | Notes |
|---|------|--------|-------|
| D1 | No SWS violations — relax ETA | **DONE** | Implemented λ penalty in all optimizers (LP, DP, RH-DP, RH-LP). `ship.eta_penalty_mt_per_hour` config. |
| D2 | Test RH with LP | **DONE** | RH-LP implemented and tested on both routes |
| D3 | Realistic upper bound (constant speed) | **DONE** | Constant SOG = D/ETA baseline implemented |
| D4 | Clarify plan vs simulation framework | **DONE** | Section 2 below + `pipeline/output/lambda_penalty_report.md` |

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

## 8. λ Penalty — Implementation & Results (Batch 1 done)

### What is λ?

`ship.eta_penalty_mt_per_hour` (λ) controls how the optimizer treats the ETA deadline:

- **λ = null (hard ETA)**: The optimizer **must** produce a plan where `sum(distance/SOG) ≤ ETA`. This is a constraint in the math — if no feasible solution exists, the solver fails.
- **λ = finite value (soft ETA)**: The objective becomes `min(fuel + λ × delay)`, where `delay = max(0, voyage_time − ETA)`. The optimizer **can** arrive late but pays a penalty.
- **λ = 0**: No penalty at all — pure fuel minimization. Ship picks slowest speed.
- **λ = ∞**: Equivalent to hard ETA (infinite cost for any lateness).

### How it works end-to-end

1. **Optimizer** (LP or DP): solves `min(fuel + λ × delay)`. With finite λ, this is always feasible — no more infeasibility fallbacks.
2. **Simulator**: executes the plan with actual weather. For each leg, computes what SWS is needed to hit planned SOG. If SWS falls outside [11, 13] kn, it's clamped → actual SOG ≠ planned SOG → arrival time drifts.

**SWS adjustments are NOT caused by the ETA constraint.** They come from weather mismatch between planning and simulation. The optimizer assumes certain weather → picks speeds → simulator runs with different weather → required SWS hits the physical limits.

### Why RH has fewer adjustments

RH re-plans every 6h with fresh weather. Each sub-plan is based on near-current conditions → fewer surprises in simulation → fewer clamps.

### Results Summary

**Hard ETA (λ = null) — Route D, North Atlantic:**

| Approach | Plan Fuel | Sim Fuel | SWS Adj | Arrival Dev |
|----------|----------|---------|---------|------------|
| CS       | —        | 216.57  | 73      | +0.00 h    |
| LP       | 208.91   | 215.60  | 64      | +0.43 h    |
| DP       | 222.60   | 214.24  | 161     | +1.53 h    |
| RH-DP    | 218.79   | 217.28  | 15      | +0.03 h    |
| RH-LP    | 210.84   | 215.56  | 51      | +0.43 h    |

Note: DP plan fuel > sim fuel because forecast predicted harder conditions than actual → optimizer picked faster (more expensive) speeds unnecessarily.

**Soft ETA (λ = 2.0) — Route D:**

| Approach | Fuel (mt) | Delay (h) | Cost (mt) |
|----------|----------|-----------|-----------|
| LP       | 191.72   | 7.83      | 207.38    |
| DP       | 222.60   | 0.00      | 222.60    |
| RH-DP    | 199.23   | 9.35      | 217.92    |
| RH-LP    | 193.10   | 10.09     | 213.27    |

DP chose zero delay — its hard-ETA solution was already within ETA so no trade-off needed. LP/RH saved 8–9% fuel by accepting 8–10h delay.

**Soft ETA (λ = 2.0) — Route B, Persian Gulf:**

| Approach | Fuel (mt) | Delay (h) | Cost (mt) |
|----------|----------|-----------|-----------|
| LP       | 153.93   | 9.94      | 173.81    |
| DP       | 156.47   | 8.01      | 172.49    |
| RH-DP    | 158.98   | 6.90      | 172.79    |
| RH-LP    | 154.56   | 9.89      | 174.34    |

All four approaches converge to nearly identical total cost (~172–174 mt). The Pareto frontier is flat on this route.

### What λ = 2.0 means intuitively

The ship burns ~1.0 mt/h at 11 kn and ~1.55 mt/h at 13 kn. With λ=2, one hour of delay "costs" 2 mt fuel-equivalent — roughly 1.3–2× the hourly fuel burn. This is a moderate penalty: the optimizer will slow down when it saves more than 2 mt/h of fuel, but won't dawdle.

### Files changed

Implemented in LP (PuLP + Gurobi), DP, RH-DP, RH-LP. Config: `ship.eta_penalty_mt_per_hour: null` (backward compatible). Full report: `pipeline/output/lambda_penalty_report.md`.

---

## 9. Questions for Next Meeting

1. **RH-LP segment count**: How many segments per window? Same ratio as static LP (6 segments for 138 nodes), or fewer for shorter windows?
2. **Soft-ETA penalty**: Should we add a fuel penalty for late arrival in the objective, or just report deviation as a separate metric?
3. **Optimal bound update**: The current optimal bound uses time-varying actual weather with no ETA constraint. Under soft-ETA mode, should we redefine it as "best achievable with on-time arrival"?
4. **Paper structure**: With 5 approaches (constant, LP, DP, RH-DP, RH-LP) plus optimal bound, the results tables grow. Should we split into "main comparison" (4 approaches) and "sensitivity" (sweeps)?

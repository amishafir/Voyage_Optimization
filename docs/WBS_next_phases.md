# Work Breakdown Structure (WBS) — Agent-Based Voyage Optimization

## 1. Research Overview

Study autonomous ship agents under environmental uncertainty. An agent with fixed hardware sails a route, executing a speed plan under actual weather. We measure how **plan sophistication** and **environment capabilities** affect fuel consumption and schedule adherence.

```
Agent = (Spec, Measurement, Plan, Policy, Environment)
         fixed   fixed       choice  choice   tier
```

### The 7 Agent Configurations

| Agent | Plan | Policy | Environment | Description |
|-------|------|--------|-------------|-------------|
| **Naive-A** | Naive | Passive | Basic | Constant SOG = D/ETA, no re-plan |
| **LP-A** | LP | Passive | Basic | LP plan at departure, follow rigidly |
| **LP-B** | LP | Reactive | Mid | LP plan, re-plan on Flow 2 (stale forecast) |
| **LP-C** | LP | Proactive | Connected | LP plan, re-plan every 6h (fresh forecast) |
| **DP-A** | DP | Passive | Basic | DP plan at departure, follow rigidly |
| **DP-B** | DP | Reactive | Mid | DP plan, re-plan on Flow 2 (stale forecast) |
| **DP-C** | DP | Proactive | Connected | DP plan, re-plan every 6h (fresh forecast) |

### Task Parameters

| Parameter | Route B (Persian Gulf) | Route D (North Atlantic) |
|-----------|----------------------|-------------------------|
| Distance | 1,678 nm | 1,955 nm |
| Waypoints | 138 interpolated | 389 interpolated |
| ETA | 140 h | 163 h |
| Weather | Mild, stable | Harsh, variable |
| λ sweep | [0, 0.5, 1, 2, 5, ∞] | [0, 0.5, 1, 2, 5, ∞] |

### Research Questions

1. **Plan value**: Does upgrading Naive → LP → DP improve performance? Route-dependent?
2. **Environment value**: Does Basic → Mid → Connected improve? Marginal value of compute? Of comms?
3. **Interaction**: Is DP-Basic better than LP-Connected? (plan vs environment importance)
4. **Task sensitivity**: How do answers change across calm vs stormy routes?
5. **Cost-performance frontier**: Minimum-capability agent for near-optimal performance?

---

## 2. Architecture

```
pipeline/
├── agent/                          # NEW — agent framework
│   ├── __init__.py                 # assemble() factory
│   ├── spec.py                     # ShipSpec dataclass
│   ├── measurement.py              # forward/inverse physics wrapper
│   ├── plans.py                    # NaivePlan, LPPlan, DPPlan
│   ├── policies.py                 # PassivePolicy, ReactivePolicy, ProactivePolicy
│   ├── environments.py             # Basic, Mid, Connected
│   ├── executor.py                 # execute_voyage() — leg-by-leg loop
│   └── runner.py                   # run_experiment_matrix()
│
├── config/
│   ├── experiment_exp_b.yaml       # Route B config
│   ├── experiment_exp_d.yaml       # Route D config
│   └── routes/                     # Waypoint definitions
│
├── shared/                         # Physics, HDF5 I/O, simulation
│   ├── physics.py                  # SOG, FCR, resistance (8-step composite)
│   ├── hdf5_io.py                  # Read/write/query HDF5
│   ├── simulation.py               # Legacy simulator (being replaced by executor)
│   ├── metrics.py                  # Metric computation
│   └── beaufort.py                 # Wind speed to Beaufort
│
├── collect/                        # Weather data collection
│   ├── collector.py                # API fetcher + HDF5 appender
│   └── waypoints.py                # Waypoint generation
│
├── static_det/                     # LP optimizer (used by LPPlan)
│   ├── transform.py                # HDF5 → segment-averaged SOG matrix
│   └── optimize.py                 # PuLP/Gurobi LP with λ penalty
│
├── dynamic_det/                    # DP optimizer (used by DPPlan)
│   ├── transform.py                # HDF5 → per-node weather grid
│   └── optimize.py                 # Forward Bellman DP with λ penalty
│
├── dynamic_rh/                     # Rolling horizon (legacy, to be replaced by executor)
│   ├── transform.py                # Multi-sample-hour weather loader
│   ├── optimize.py                 # RH-DP
│   └── optimize_lp.py             # RH-LP
│
├── compare/                        # Comparison and bounds
│   ├── sensitivity.py              # Constant speed bound, replan sweep
│   └── ...
│
├── tests/
│   └── test_agent_backward_compat.py  # 10 regression tests (all passing)
│
├── data/                           # HDF5 weather files (gitignored)
└── output/                         # Results (gitignored)
```

---

## 3. Component Specifications

### 3.1 Spec (data only)

Constructed from `config['ship']`:

```yaml
ship:
  length_m: 200.0
  beam_m: 32.0
  draft_m: 12.0
  displacement_tonnes: 50000.0
  block_coefficient: 0.75
  rated_power_kw: 10000.0
  speed_range_knots: [11, 13]
  eta_hours: 163
  eta_penalty_mt_per_hour: null    # null = hard ETA, finite = soft ETA
```

### 3.2 Measurement

Wraps `shared/physics.py`. Two directions:

| Function | Direction | Implementation |
|----------|-----------|---------------|
| `forward(sws, weather, heading)` | SWS → SOG + FCR | `calculate_speed_over_ground()` + `calculate_fuel_consumption_rate()` |
| `inverse(target_sog, weather, heading)` | SOG → required SWS | `calculate_sws_from_sog()` (binary search) |

Physics: Holtrop-Mennen resistance, Isherwood wind coefficients, wave added resistance, current vector projection. FCR = 0.000706 × V_s³.

### 3.3 Plan (3 implementations)

All share: `plan.optimize(route_data, weather_data, eta, lambda_val, config) -> speed_schedule`

| Plan | Algorithm | Resolution | Speed | λ support |
|------|-----------|-----------|-------|-----------|
| **Naive** | SOG = D/ETA | Uniform | Instant | N/A |
| **LP** | PuLP/Gurobi LP, binary x[i,k] | Per-segment (6-10 segs) | <0.01s | Yes — `min(fuel + λδ)` |
| **DP** | Forward Bellman, sparse dict | Per-node (138-389 nodes) | 1-3s | Yes — `min(fuel + λ × delay)` over final states |

### 3.4 Policy (3 implementations)

`policy.on_leg_complete(state) -> CONTINUE | REPLAN | REPLAN_FRESH`

| Policy | Trigger | Behavior |
|--------|---------|----------|
| **Passive** | Never | Always CONTINUE. Follow original plan. |
| **Reactive** | Flow 2 event | REPLAN when exiting a Flow 2 sequence. Uses stale forecast. |
| **Proactive** | Every 6h + Flow 2 | REPLAN_FRESH on schedule + reactive on Flow 2. Downloads fresh forecast. |

### 3.5 Environment (3 tiers)

| Tier | `can_compute` | `can_communicate` | Forecast access |
|------|--------------|-------------------|----------------|
| **Basic (A)** | No | No | None — follows original plan only |
| **Mid (B)** | Yes | No | Stale — departure forecast only |
| **Connected (C)** | Yes | Yes | Fresh — downloads current forecast |

### 3.6 Voyage Executor

The leg-by-leg execution loop:

```
For each leg i:
  1. OBSERVE  — actual weather at (position, time)
  2. ASSESS   — required_sws = measurement.inverse(planned_sog, actual_wx)
  3. CLASSIFY — Flow 1 (nominal) | Flow 2 (adverse) | Flow 3 (favorable)
  4. EXECUTE  — clamp SWS to [11, 13], compute actual SOG and fuel
  5. UPDATE   — advance position, time, fuel, delay
  6. DECIDE   — policy.on_leg_complete(state) → re-plan or continue
```

Flow classification:
- **Flow 1**: 11 ≤ required_sws ≤ 13 — execute as planned
- **Flow 2**: required_sws > 13 — set SWS=13, SOG < planned, accumulate delay
- **Flow 3**: required_sws < 11 — set SWS=11, SOG > planned, gain time buffer

---

## 4. Data Layer

### HDF5 Schema

```
experiment_*.h5
├── /metadata          — node_id, lat, lon, segment, distance_from_start_nm
├── /actual_weather    — node_id, sample_hour, 6 weather fields
└── /predicted_weather — node_id, forecast_hour, sample_hour, 6 weather fields
```

Weather fields: `wind_speed_10m_kmh`, `wind_direction_10m_deg`, `beaufort_number`, `wave_height_m`, `ocean_current_velocity_kmh`, `ocean_current_direction_deg`.

### Data Access by Environment

| Environment | HDF5 Access |
|-------------|-------------|
| Basic (A) — LP | `/actual_weather` at `sample_hour=0` (segment-averaged) |
| Basic (A) — DP | `/predicted_weather` at `sample_hour=0` (time-varying per node) |
| Mid (B) | Same as Basic — stale forecast from departure |
| Connected (C) | `/predicted_weather` at `sample_hour=decision_hour` (fresh per re-plan) |

### Active Data Collection

| Server | Route B | Route D | Status |
|--------|---------|---------|--------|
| Edison | ~40 samples | ~40 samples | Running |
| Shlomo2 | ~37 samples | ~38 samples | Running |
| Shlomo1 | — | — | Down |

---

## 5. Config Structure

```yaml
# Existing sections (backward compat — used by legacy runners)
ship: { ... }
static_det: { ... }
dynamic_det: { ... }
dynamic_rh: { ... }

# New agent section (used by agent runner)
agents:
  - name: LP-A
    plan: lp
    policy: passive
    environment: basic
  - name: DP-B
    plan: dp
    policy: reactive
    environment: mid
    policy_config:
      trigger: flow2
  - name: DP-C
    plan: dp
    policy: proactive
    environment: connected
    policy_config:
      interval_h: 6
      also_on_flow2: true
```

---

## 6. Output Contract

All agents produce results with:

```json
{
  "agent": "DP-C",
  "plan": "dp",
  "policy": "proactive",
  "environment": "connected",
  "lambda": 2.0,
  "planned": {
    "fuel_mt": 199.23,
    "time_h": 172.35,
    "delay_h": 9.35,
    "cost_mt": 217.92
  },
  "executed": {
    "fuel_mt": 198.50,
    "time_h": 173.10,
    "delay_h": 10.10,
    "flow2_count": 12,
    "flow3_count": 45,
    "replan_count": 5
  },
  "computation_time_s": 14.2,
  "route": "st_johns_liverpool",
  "hdf5": "experiment_d_391wp.h5"
}
```

---

## 7. Implementation Status

### Completed (Phases 0-7)

| Phase | What | Key Deliverable |
|-------|------|----------------|
| 0 | Foundation | Directory structure, config, physics, HDF5 I/O |
| 1 | Data layer | Waypoint generation, weather collection, pickle import |
| 2 | Static Det (LP) | LP optimizer (PuLP + Gurobi), SOG-target simulation |
| 3 | Dynamic Det (DP) | Forward Bellman DP, 279-node graph, per-leg scheduling |
| 4 | Rolling Horizon | RH-DP, re-plan loop, 42 decision points |
| 5 | Comparison | Figures, reports, forecast error analysis |
| 6 | Sensitivity | Bounds (optimal/constant-speed), replan frequency sweep |
| 7 | λ Penalty | Soft ETA in LP + DP + RH-DP + RH-LP. λ=null backward compat. |

All phases validated. Key reference values (Route D, λ=null):

| Agent Config | Plan Fuel (mt) | Sim Fuel (mt) | SWS Adj |
|-------------|---------------|---------------|---------|
| Naive-A | — | 216.57 | 73 |
| LP-A | 208.91 | 215.60 | 64 |
| DP-A | 222.60 | 214.24 | 161 |
| DP-C (RH-DP) | 218.79 | 217.28 | 15 |
| LP-C (RH-LP) | 210.84 | 215.56 | 51 |

### Phase 8: Agent Framework — IN PROGRESS

#### 8.0 Infrastructure — DONE

| # | Task | Status |
|---|------|--------|
| 8.0.1 | Rules: `.claude/rules/agent-framework.md` | Done |
| 8.0.2 | Tests: `pipeline/tests/test_agent_backward_compat.py` (10 tests, all passing) | Done |
| 8.0.3 | WBS update | Done |

#### 8.1 Component Interfaces — TODO

| # | Task | File | Wraps |
|---|------|------|-------|
| 8.1.1 | ShipSpec dataclass | `agent/spec.py` | `config['ship']` |
| 8.1.2 | Measurement (forward/inverse) | `agent/measurement.py` | `shared/physics.py` |
| 8.1.3 | NaivePlan, LPPlan, DPPlan | `agent/plans.py` | `static_det/optimize.py`, `dynamic_det/optimize.py` |
| 8.1.4 | PassivePolicy, ReactivePolicy, ProactivePolicy | `agent/policies.py` | New |
| 8.1.5 | Basic, Mid, Connected | `agent/environments.py` | HDF5 access patterns |
| 8.1.6 | `assemble()` factory | `agent/__init__.py` | Composes above |

**Gate**: All components instantiate. Types check.

#### 8.2 Voyage Executor — TODO

| # | Task | File |
|---|------|------|
| 8.2.1 | VoyageState class | `agent/executor.py` |
| 8.2.2 | Flow 1/2/3 classification | `agent/executor.py` |
| 8.2.3 | Leg execution loop (OBSERVE → DECIDE) | `agent/executor.py` |
| 8.2.4 | Re-plan dispatch | `agent/executor.py` |
| 8.2.5 | Sub-problem builder (DP) | `agent/executor.py` |
| 8.2.6 | Sub-problem builder (LP) | `agent/executor.py` |

**Gate**: Backward compat — must match these exactly:

| Check | Agent | Reference (Route D) |
|-------|-------|-------------------|
| S1 | Naive-A | sim: 216.57 mt, 163.00h |
| S2 | LP-A (λ=null) | plan: 208.91 mt, sim: 215.60 mt |
| S3 | DP-A (λ=null) | plan: 222.60 mt, sim: 214.24 mt |
| S4 | DP-C (6h) | plan: 218.79 mt, sim: 217.28 mt |
| S5 | LP-C (6h) | plan: 210.84 mt, sim: 215.56 mt |
| S6 | LP-A (λ=2) | plan: 191.72 mt, delay: 7.83h |
| S7 | LP-A (λ=0) | SWS=11.0 everywhere |

#### 8.3 Experiment Runner — TODO

| # | Task | File |
|---|------|------|
| 8.3.1 | Combinatorial runner | `agent/runner.py` |
| 8.3.2 | Results table (fuel, delay, cost, flow2, replans) | `agent/runner.py` |
| 8.3.3 | Agent config in YAML | `config/experiment_exp_*.yaml` |

**Gate**: Full matrix (7 agents × 2 routes × 4 λ values) completes.

#### Edge Cases

| Case | Handling |
|------|----------|
| `remaining_eta ≤ 0` during re-plan | λ finite: estimate from remaining_dist/min_sog. λ=null: skip re-plan. |
| All remaining legs Flow 2 | Re-plan once when exiting sequence, not per-leg |
| Flow 2 on last leg | No re-plan. Execute and report. |
| Re-plan triggers immediate Flow 2 | Don't re-plan again. Continue. |
| Port B NaN weather | Return calm defaults |
| λ=null + re-plan when already late | Sub-problem infeasible → min-SWS fallback |

### Critical Path

```
Phases 0-7: DONE
Phase 8.0 (infrastructure): DONE
Phase 8.1 (components) → Phase 8.2 (executor) → Phase 8.3 (runner)
       TODO                    TODO                    TODO
```

---

## 8. Validation Design Decisions (reference)

Key decisions from Phases 2-6, preserved for reference:

1. **Forward Bellman DP** (not Dijkstra) — natural time ordering, no explicit graph in memory, sparse dict storage.

2. **`time_granularity: 0.1` with `math.ceil`** — prevents cumulative time undercount. Cost: ~1h unused ETA slack (~0.3% fuel penalty).

3. **SOG-target execution model** — optimizer outputs SOG schedule, simulator computes required SWS. Fuel gap comes from weather mismatch, not time drift.

4. **LP segment averaging + Jensen's inequality** — maintaining segment-averaged SOG at individual nodes costs more fuel (cubic FCR). This is why LP-A ≈ Naive-A on harsh routes.

5. **Forecast persistence** — beyond `max_forecast_hour`, DP uses last available forecast hour. Affects second half of long voyages.

6. **NWP cycle alignment** — 6h replan frequency matches GFS refresh. Sub-6h re-planning returns identical data 86% of the time.

7. **λ penalty** — `min(fuel + λ × delay)`. λ=null = hard ETA (backward compat). λ finite = always feasible. λ=2.0 ≈ typical bulk demurrage rates (~$900/h at $450/mt fuel).

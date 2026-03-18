# Meeting Prep — Supervisor Meeting, Mar 23 2026

---

## 1. Action Items from Mar 16 Meeting — All Done

| # | Task | Status |
|---|------|--------|
| D1 | Relax ETA (no SWS violations) | **DONE** — λ penalty in all optimizers |
| D2 | Test RH with LP | **DONE** — RH-LP implemented |
| D3 | Realistic upper bound (constant speed) | **DONE** — Naive agent baseline |
| D4 | Clarify plan vs simulation framework | **DONE** — Agent framework replaces old framing |

---

## 2. Major Development: Agent-Based Reframing

Reframed the entire research as an **autonomous agent problem**. An agent is assembled from composable components:

```
Agent = (Spec, Measurement, Plan, Policy, Environment)
         fixed   fixed       choice  choice   tier
```

| Component | What it is | Our implementation |
|-----------|-----------|-------------------|
| **Spec** | Ship hardware constants | 200m, 32m beam, SWS ∈ [11,13] kn |
| **Measurement** | Physics equations (SOG ↔ SWS) | Holtrop-Mennen + FCR = 0.000706 × V³ |
| **Plan** | Optimization algorithm | Naive (constant SOG), LP (segment-avg), DP (per-node) |
| **Policy** | When to re-plan | Passive (never), Reactive (on Flow 2), Proactive (every 6h) |
| **Environment** | Agent capabilities | Basic (no compute), Mid (compute only), Connected (compute + comms) |

### Flow classification (replaces "SWS violations")

At each leg, the executor classifies the outcome:
- **Flow 1** (nominal): required SWS within [11, 13] — execute as planned
- **Flow 2** (adverse): required SWS > 13 — can't keep up, falls behind
- **Flow 3** (favorable): required SWS < 11 — would overshoot, gains time

Policy decides what happens after Flow 2: Passive does nothing, Reactive re-plans with stale forecast, Proactive re-plans with fresh forecast.

### The 7 agent configurations

| Agent | Plan | Environment | Re-plan behavior |
|-------|------|-------------|-----------------|
| Naive-A | Constant SOG | Basic | Never |
| LP-A | LP | Basic | Never |
| LP-B | LP | Mid | On Flow 2 exit, stale forecast |
| LP-C | LP | Connected | Every 6h + Flow 2, fresh forecast |
| DP-A | DP | Basic | Never |
| DP-B | DP | Mid | On Flow 2 exit, stale forecast |
| DP-C | DP | Connected | Every 6h + Flow 2, fresh forecast |

---

## 3. λ Penalty (Soft ETA)

`ship.eta_penalty_mt_per_hour` (λ) controls how the optimizer treats ETA:

| λ value | Meaning | Behavior |
|---------|---------|----------|
| null / ∞ | Hard ETA | Must arrive on time. Infeasible if impossible. |
| finite (e.g., 2.0) | Soft ETA | Objective: `min(fuel + λ × delay)`. Always feasible. |
| 0 | No penalty | Pure fuel minimization, arrive whenever. |

λ = 2.0 mt/h ≈ typical bulk demurrage rates (~$900/h at $450/mt fuel). Literature reference: Psaraftis & Kontovas 2013 (inventory cost), Zaccone 2018 (Pareto slope), Fagerholt 2001 (soft time windows). No paper uses this exact formulation — it's a contribution.

---

## 4. Results — Route B (Persian Gulf, 1,678 nm, ETA=140h, calm)

Hard ETA (λ = null):

| Agent | Fuel (mt) | Time (h) | Delay | Flow 2 | Re-plans |
|-------|----------|----------|-------|--------|----------|
| **LP-C** | **175.83** | 140.0 | -0.01 | 0 | 21 |
| DP-C | 176.13 | 139.9 | -0.10 | 1 | 21 |
| Naive-A | 180.53 | 140.1 | +0.06 | 8 | 0 |
| LP-A | 180.63 | 140.1 | +0.05 | 4 | 0 |
| LP-B | 180.82 | 140.0 | -0.01 | 6 | 4 |
| DP-B | 182.09 | 139.6 | -0.42 | 13 | 8 |
| DP-A | 182.22 | 139.6 | -0.45 | 13 | 0 |

**Takeaway**: Connected agents dominate (~3% savings). LP-C ≈ DP-C — cheap LP + fresh weather matches expensive DP.

---

## 5. Results — Route D (North Atlantic, 1,955 nm, ETA=163h, harsh)

Hard ETA (λ = null):

| Agent | Fuel (mt) | Time (h) | Delay | Flow 2 | Re-plans |
|-------|----------|----------|-------|--------|----------|
| Naive-A | 214.06 | 164.0 | +1.04 | 70 | 0 |
| DP-A | 214.24 | 164.5 | +1.53 | 117 | 0 |
| LP-C | 214.68 | 164.5 | +1.45 | 51 | 30 |
| LP-A | 215.60 | 163.4 | +0.43 | 64 | 0 |
| **LP-B** | **217.03** | **163.0** | **-0.01** | 74 | 10 |
| **DP-C** | **217.27** | **163.0** | **-0.01** | 75 | 34 |
| **DP-B** | **217.84** | **162.8** | **-0.17** | 129 | 14 |

**Takeaway**: Fuel vs punctuality trade-off. Basic agents are cheapest but 1–1.5h late. Mid/Connected arrive on time but burn 2–3 mt more. LP-B is the cheapest on-time option (10 re-plans, no comms needed).

Soft ETA (λ = 2.0):

| Agent | Fuel (mt) | Time (h) | Delay | Flow 2 |
|-------|----------|----------|-------|--------|
| LP-B | 196.39 | 172.3 | +9.3h | 10 |
| LP-A | 198.71 | 171.0 | +8.0h | 62 |
| DP-B | 213.92 | 164.5 | +1.5h | 116 |
| DP-A | 214.24 | 164.5 | +1.5h | 117 |

LP with λ=2 saves ~17 mt by accepting 8–9h delay. DP barely changes — its hard-ETA plan was already near-optimal.

---

## 6. Key Findings

1. **Environment > Plan on calm routes**: LP-C ≈ DP-C (175.83 vs 176.13 mt). Fresh weather re-planning compensates for LP's segment averaging. Practical: deploy LP with comms, save compute.

2. **Re-planning costs fuel on harsh routes**: DP-C (217.27 mt) burns more than DP-A (214.24 mt). Why? Re-planning speeds up remaining legs to recover from Flow 2 delays. This is the price of punctuality.

3. **Basic DP is paradoxically fuel-cheapest on harsh routes**: It doesn't try to recover — just sails slower when it can't keep up. If you don't care about arrival time, don't re-plan.

4. **Mid (B) is the pragmatic sweet spot**: LP-B arrives on time with 10 re-plans and no comms. For routes where satellite comms are expensive, this is the answer.

5. **Flow 2 count is the key route characteristic**: Route B: 0–13 events (mild). Route D: 51–129 (harsh). This drives the value of re-planning.

6. **λ enables meaningful trade-offs**: With hard ETA, the only question is "on time or not." With λ, operators can quantify: "2 mt fuel per hour of lateness" and let the optimizer decide.

---

## 7. What Was Built

~1,700 lines of new code in `pipeline/agent/`:

| Component | File |
|-----------|------|
| Spec, Measurement, Plans, Policies, Environments | `agent/*.py` (6 files) |
| Voyage Executor (leg-by-leg loop) | `agent/executor.py` |
| Experiment Runner (combinatorial matrix) | `agent/runner.py` |
| Backward compat tests (10 tests, all passing) | `tests/test_agent_backward_compat.py` |
| Coding rules | `.claude/rules/agent-framework.md` |

Backward compat: LP-A and DP-A executor results match old `simulate_voyage()` to 0.0000 mt.

---

## 8. Questions for Supervisor

1. **Paper framing**: Present as autonomous agent study or keep maritime optimization language? Agent framing is more general and publishable, but maritime audience may prefer domain terms.

2. **Results table**: The 7-agent table is rich but dense. Suggest: main table (7 agents, hard ETA, both routes) + sensitivity table (λ sweep).

3. **Flow 2 geography**: Should we analyze where Flow 2 events cluster on the route? Would show which segments drive re-planning value.

4. **λ for the paper**: Use λ=2.0 as default (literature-backed), show Pareto frontier via sweep?

5. **Next priority**: Run agents on fresh data (servers collecting since Mar 17, ~40+ samples). Or focus on paper writing with current results?

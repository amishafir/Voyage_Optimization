# Agent Framework Standards

## Component Architecture

An agent is assembled from five components:

```
Agent = (Spec, Measurement, Plan, Policy, Environment)
```

All agent code lives in `pipeline/agent/`. Components have standard interfaces — swap one implementation without changing others.

## Component Interfaces

### Spec (data only)
- Access via `spec.length_m`, `spec.speed_range`, etc.
- Constructed from `config['ship']` dict
- NO logic, NO methods that compute anything

### Measurement
- `measurement.forward(sws, weather, heading) -> (sog, fcr)` — SWS to SOG + fuel rate
- `measurement.inverse(target_sog, weather, heading) -> required_sws` — SOG to required SWS
- Wraps `shared/physics.py` — do NOT duplicate physics logic

### Plan
- `plan.optimize(route_data, weather_data, eta, lambda_val, config) -> speed_schedule`
- Three implementations: `NaivePlan`, `LPPlan`, `DPPlan`
- Plan is STATELESS — it solves a one-shot problem when called
- Plan does NOT know about the voyage execution loop

### Policy
- `policy.on_leg_complete(state) -> Action` where Action is `CONTINUE | REPLAN | REPLAN_FRESH`
- Policy sees: `state.flow_type`, `state.delay`, `state.time_since_replan`, `state.leg_idx`
- Three implementations: `PassivePolicy`, `ReactivePolicy`, `ProactivePolicy`

### Environment
- `environment.can_compute -> bool`
- `environment.can_communicate -> bool`
- `environment.get_forecast(time, hdf5_path) -> weather_data`

## Naming Conventions

- **Flow 1**: nominal — required SWS within [min, max]
- **Flow 2**: adverse — required SWS > max (can't keep up)
- **Flow 3**: favorable — required SWS < min (would overshoot)
- Do NOT use "violation" or "adjustment" — use "Flow 2 event" or "flow2_count"

- **Agent names**: `{Plan}-{Environment}` e.g., `LP-A`, `DP-B`, `Naive-C`
  - A = Basic, B = Mid, C = Connected

## Testing Requirements

- **Backward compatibility is mandatory**: every new component must reproduce existing results when configured equivalently
- Sanity checks in `pipeline/tests/test_agent_backward_compat.py` must pass before any PR
- Known reference values (Route D, λ=null):
  - LP-A: plan 208.91 mt, sim 215.60 mt
  - DP-A: plan 222.60 mt, sim 214.24 mt
  - Naive-A: sim 216.57 mt
  - DP-C (RH-DP): plan 218.79 mt, sim 217.28 mt
  - LP-C (RH-LP): plan 210.84 mt, sim 215.56 mt

## Config Structure

Agent experiments are defined in YAML:
```yaml
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
```

The old `static_det`/`dynamic_det`/`dynamic_rh` sections remain for backward compat.

## Do NOT

- Duplicate physics logic — always call `shared/physics.py` through `measurement`
- Import from legacy `Linear programing/` or `Dynamic speed optimization/`
- Hardcode ship parameters, speed ranges, or ETA values
- Use floats or strings for time keys — always `int`
- Re-plan on every consecutive Flow 2 leg — batch them (re-plan once when exiting Flow 2 sequence)

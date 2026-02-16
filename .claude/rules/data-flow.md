# Data Flow & Access Patterns

## Pipeline
```
Weather API (Open-Meteo) → Collection → HDF5 → Transform → Optimize → Simulate → Compare
```

## Data Format

**New pipeline** (`pipeline/`): HDF5 with tables (`/metadata`, `/actual_weather`, `/predicted_weather`)
**Legacy** (`test_files/`): Pickle with Node objects (two wrapper formats: `dict_wrapper` and `raw_list`)

## Three Optimization Strategies

| Strategy | Data Access (HDF5) | Data Access (legacy pickle) | Re-planning |
|----------|-------------------|---------------------------|-------------|
| Static Deterministic (LP) | `actual_weather` where `sample_hour=0` | `node.Actual_weather_conditions[0]` | None |
| Dynamic Deterministic (DP) | `predicted_weather` where `sample_hour=0` | `node.Predicted_weather_conditions[t][0]` | None |
| Dynamic Rolling Horizon (DP) | `predicted_weather` where `sample_hour=decision_hour` | `node.Predicted_weather_conditions[future_t][decision_hour]` | At decision points |

## Critical Gotchas

- **Port B (WP 13)** returns NaN for marine data — coastal proximity, outside Open-Meteo Marine API coverage
- **Integer time keys only**: Sample hours are `0, 1, 2, ...` (int), never floats or strings
- **Beaufort number** is calculated from wind speed, NOT obtained from the API
- **Two legacy pickle wrapper formats** exist (see naming-conventions rule) — always detect format before accessing data
- Full pipeline architecture details: `docs/WBS_next_phases.md`

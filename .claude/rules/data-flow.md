# Data Flow & Access Patterns

## Pipeline
```
Weather API (Open-Meteo) → Collection → Pickle → Transform → Optimize → Simulate → Compare
```

## Three Optimization Strategies

| Strategy | Data Access Pattern | Re-planning |
|----------|-------------------|-------------|
| Static Deterministic (LP) | `node.Actual_weather_conditions[0]` | None |
| Dynamic Deterministic (DP) | `node.Predicted_weather_conditions[t][0]` | None |
| Dynamic Stochastic (DP) | `node.Predicted_weather_conditions[future_t][decision_hour]` | At decision points |

## Critical Gotchas

- **Port B (WP 13)** returns NaN for marine data — coastal proximity, outside Open-Meteo Marine API coverage
- **Integer time keys only**: Sample hours are `0, 1, 2, ...` (int), never floats or strings
- **Beaufort number** is calculated from wind speed, NOT obtained from the API
- **Two pickle wrapper formats** exist (see naming-conventions rule) — always detect format before accessing data

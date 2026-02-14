# LP Optimizer Architecture Reference

## Files

| File | Purpose |
|------|---------|
| `Linear programing/ship_speed_optimization_pulp.py` | Main LP solver |
| `Linear programing/utility_functions.py` | Paper formulas (SOG, FCR, Tables 2-4) |
| `Linear programing/generate_optimization_data.py` | SOG matrix builder |
| `Linear programing/voyage_data.py` | Hardcoded 12-segment route data |
| `Linear programing/Gurobi.py` | Alternative solver (requires license) |

## Data Flow

```
voyage_data.py (SEGMENT_DATA, SHIP_PARAMETERS)
    |
    v
generate_optimization_data.py
    |  - Iterates all (segment, speed) pairs
    |  - Calls calculate_speed_over_ground() for each
    |  - Writes f[i][k] SOG matrix to .dat file
    v
ship_speed_optimization_pulp.py
    |  - Parses .dat file
    |  - Builds PuLP LP model
    |  - Binary x[i,k] variables: 1 if segment i uses speed k
    |  - Minimizes total fuel subject to ETA constraint
    |  - Solves
    v
Output: Speed per segment, total fuel ~372 kg
```

## LP Model

**Decision Variables:**
- `x[i][k]` (Binary): 1 if segment `i` uses speed choice `k`

**Objective:**
```
minimize sum_i sum_k (FCR(speed_k) * distance_i / f[i][k]) * x[i][k]
```

**Constraints:**
1. One speed per segment: `sum_k(x[i][k]) == 1` for all `i`
2. ETA: `sum_i(distance_i / SOG_i) <= ETA_hours`
3. SOG bounds: applied through valid speed range

## SOG Matrix (`f[i][k]`)

- `i` = segment index (0-11, total 12 segments)
- `k` = speed index (0-20, total 21 speed choices)
- Speed range: 8.0 to 15.7 knots (step: (15.7-8.0)/20 = 0.385 knots)
- Each `f[i][k]` = SOG in knots for segment `i` at SWS `speed_k`

## Hardcoded Values

| Variable | Location | Value |
|----------|----------|-------|
| `SEGMENT_DATA` | `voyage_data.py` | 12 dicts with weather per segment |
| `SEGMENT_DISTANCES` | `voyage_data.py` | `[223.8, 282.5, 303.2, 298.4, 280.5, 287.3, 284.4, 233.3, 301.8, 315.7, 293.8, 288.8]` |
| `SEGMENT_HEADINGS` | `voyage_data.py` | Heading degrees per segment |
| `SHIP_PARAMETERS` | `voyage_data.py` | `{L: 200, B: 32, T: 12, Cb: 0.75, P: 10000}` |
| Speed range | `generate_optimization_data.py` | 8.0 to 15.7, 21 steps |
| ETA | `ship_speed_optimization_pulp.py` | 280 hours |

## FCR Formula

```python
FCR = 0.000706 * SWS**3  # kg/hour
```

## Key Validation

- Total fuel for 12 segments with known weather: ~372 kg
- Each segment produces one speed assignment
- SOG always less than SWS (weather resistance reduces speed)

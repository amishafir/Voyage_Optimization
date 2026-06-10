# Research Paper Reference

## Paper Location

| Document | Path |
|----------|------|
| Main paper | `context/Ship Speed Optimization Considering Ocean Currents...pdf` |
| Research description | `context/Research Description.pdf` |

## Key Equations

### Speed Over Ground (SOG) — 8-step composite

| Step | Equation | Purpose |
|------|----------|---------|
| 1 | `Fn = V_s / sqrt(g * L)` | Froude number |
| 2 | Table 3 lookup by `(Fn, Cb)` | Speed reduction coefficient C_U |
| 3 | Table 4 lookup by `(BN, displacement)` | Ship form coefficient C_Form |
| 4 | Eqs 7-9: wind resistance | `delta_V_wind` from BN, heading, C_beta (Table 2) |
| 5 | Wave added resistance | `delta_V_wave` from wave height, ship dimensions |
| 6 | Current effect | Vector projection of current onto heading |
| 7 | `SOG = SWS - delta_V_wind - delta_V_wave + V_current_along` | Combine all effects |
| 8 | `SOG = max(0, SOG)` | Non-negative bound |

### Fuel Consumption Rate (FCR)

```
FCR = 0.000706 * SWS^3   (kg/hour, SWS in knots)
```

### Total Fuel for a Segment

```
fuel = FCR * (distance / SOG)   (kg)
```

## Coefficient Tables

### Table 2: Direction Reduction Coefficient (C_beta)

- **Index**: Beaufort Number (0-12) x Heading angle category
- **Returns**: C1 through C6 coefficients
- **Used for**: Wind resistance calculation
- **Heading categories**: Head seas (0-30), Bow (30-60), Beam (60-120), Quarter (120-150), Following (150-180)

### Table 3: Speed Reduction Coefficient (C_U)

- **Index**: Froude number range x Block coefficient range
- **Returns**: Multiplier (0.0 to 1.0)
- **Used for**: Scaling weather effect based on ship speed

### Table 4: Ship Form Coefficient (C_Form)

- **Index**: Beaufort Number (0-12) x Displacement category
- **Returns**: Form factor
- **Used for**: Resistance based on hull shape and sea state

## Ship Parameters (from paper Table 8)

| Parameter | Value |
|-----------|-------|
| Length (L) | 200 m |
| Beam (B) | 32 m |
| Draft (T) | 12 m |
| Block coefficient (Cb) | 0.75 |
| Displacement | 50,000 tonnes |
| Installed power | 10,000 kW |
| Speed range | 11-13 knots |
| ETA | 280 hours |

## Route (from paper Table 8)

13 waypoints, 12 segments, Persian Gulf to Strait of Malacca. See `/waypoints` skill for full GPS table.

## Validation Targets

| Metric | Expected Value | Source |
|--------|---------------|--------|
| LP total fuel | ~372 kg | Existing LP optimizer output |
| Voyage distance | 3,393.5 nm | Interpolated waypoints |
| Segment count | 12 | Paper Table 8 |
| Waypoint count | 13 (original), 3,388 (interpolated) | Paper + interpolation script |

## Code-to-Paper Mapping

| Code Function | Paper Reference |
|---------------|----------------|
| `calculate_speed_over_ground()` | Eqs 7-16 composite |
| `calculate_fuel_consumption_rate()` | Empirical FCR formula |
| `calculate_direction_reduction_coefficient()` | Table 2 |
| `calculate_speed_reduction_coefficient()` | Table 3 |
| `calculate_ship_form_coefficient()` | Table 4 |
| `calculate_weather_factor()` | Eqs 14-16 |
| `f[i][k]` SOG matrix | Section 3.2 |
| Binary `x[i,k]` LP variables | Section 3.3 |
| Time-distance graph | Section 4 (DP approach) |

## Implementation Status

Both `utility_functions.py` files (LP and DP) implement ALL paper formulas correctly and are byte-for-byte identical. The new `pipeline/shared/physics.py` consolidates them into one module.

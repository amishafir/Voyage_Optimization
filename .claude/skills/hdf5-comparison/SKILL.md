# HDF5 Comparison Reference

## API Model Mapping

The two collection methods query different Open-Meteo endpoints, backed by different meteorological models:

| Data Source | API Endpoint | Atmosphere Model | Marine Model | Temporal Resolution |
|-------------|-------------|-----------------|--------------|-------------------|
| **Live collection** | `api.open-meteo.com/v1/forecast` | ICON/GFS (operational NWP) | ERA5 Ocean (0.5° grid) | Hourly, up to 16-day horizon |
| **Historical bulk** | `archive-api.open-meteo.com/v1/archive` | ERA5 Reanalysis (0.25° grid) | ERA5 Ocean (0.5° grid) | Hourly, any past date |

### Field-to-Model Mapping

| HDF5 Field | Live Source | Historical Source | Expected Difference |
|-----------|------------|------------------|-------------------|
| `wind_speed_10m_kmh` | ICON/GFS forecast | ERA5 reanalysis | ±3-5 km/h typical |
| `wind_direction_10m_deg` | ICON/GFS forecast | ERA5 reanalysis | ±10-20° typical |
| `beaufort_number` | Calculated from wind speed | Calculated from wind speed | ±0-1 BN |
| `wave_height_m` | ERA5 marine forecast | ERA5 marine reanalysis | ±0.05-0.15m typical |
| `ocean_current_velocity_kmh` | ERA5 ocean reanalysis | ERA5 ocean reanalysis | ±0.1-0.3 km/h (temporal aliasing) |
| `ocean_current_direction_deg` | ERA5 ocean reanalysis | ERA5 ocean reanalysis | ±5-15° typical |

### Why Values Differ

1. **Atmospheric data** (wind): Live captures the operational NWP forecast at query time. Historical uses ERA5 reanalysis — the post-processed "best guess" computed ~5 days after the fact. NWP forecasts have random errors that ERA5 largely removes.

2. **Marine data** (waves, currents): Both nominally use ERA5 ocean products, but the live API serves the most recent ERA5 cycle available at query time, while the historical API serves the final reanalysis. Minor temporal resolution differences exist.

3. **Predicted weather**: In the live-collected file, `predicted_weather[forecast_hour=t][sample_hour=s]` captures genuine forecast degradation (forecast made at hour `s` for conditions `t` hours ahead). In the historical file, all forecasts are filled with the same ERA5 reanalysis value — there is **zero forecast error**. This makes `dynamic_det` and `dynamic_rh` behave identically on historical data.

## Circular Angle Difference

Direction fields wrap around at 0°/360°. A naive `abs(a - b)` gives wrong results near the boundary (e.g., 5° vs 355° → naive diff = 350°, correct diff = 10°).

**Formula:**
```
diff = abs(a - b) mod 360
circular_diff = min(diff, 360 - diff)
```

Result is always in [0°, 180°]. RMSE and max_abs_diff use this corrected difference.

## Substitutability Thresholds

| Field | RMSE Threshold | Rationale |
|-------|---------------|-----------|
| `wind_speed_10m_kmh` | < 5 km/h | Half a Beaufort number (~1.5 m/s) |
| `wave_height_m` | < 0.3 m | Within WMO sea-state class uncertainty |
| `ocean_current_velocity_kmh` | < 0.5 km/h | Translates to < 0.27 kn effect on SOG |
| `wind_direction_10m_deg` | < 30° | Within one compass sector (32-point) |
| `ocean_current_direction_deg` | < 30° | Within one compass sector |
| Optimization fuel delta | < 2% | Within LP/DP model uncertainty |

## Substitutability Decision Tree

```
For each weather field:
  IF RMSE > threshold → FAIL
  ELIF RMSE > 70% of threshold → WARNING

For each optimizer (LP, DP, RH):
  IF |fuel_delta_%| > 2% → FAIL
  ELIF |fuel_delta_%| > 1.4% → WARNING

Final verdict:
  Any FAIL → NOT_RECOMMENDED
  Any WARNING (no FAIL) → VALID_WITH_CAVEATS
  All clear → VALID
```

## How to Run

```bash
cd pipeline

# Full comparison (weather + optimization)
python3 compare/hdf5_compare.py \
    --original  data/experiment_b_138wp.h5 \
    --historical data/experiment_b_138wp_historical.h5 \
    --config config/experiment_exp_b.yaml

# Weather-only (faster, skips LP/DP/RH)
python3 compare/hdf5_compare.py \
    --original  data/experiment_b_138wp.h5 \
    --historical data/experiment_b_138wp_historical.h5 \
    --config config/experiment_exp_b.yaml \
    --skip-optimization

# Custom output path
python3 compare/hdf5_compare.py \
    --original data/A.h5 --historical data/B.h5 \
    --config config/experiment_exp_b.yaml \
    --output results/custom_comparison.json
```

## Output Format

The JSON report has four sections:

```json
{
  "files": {"original": "...", "historical": "...", "config": "..."},
  "actual_weather": {
    "matched_rows": 19872,
    "overall": {
      "wind_speed_10m_kmh": {"n": 19872, "mean_diff": 0.42, "rmse": 3.41, "r_squared": 0.93, "max_abs_diff": 18.2},
      ...
    },
    "per_segment": {
      "0": {"wind_speed_10m_kmh": {...}, ...},
      ...
    }
  },
  "predicted_weather": { ... },
  "optimization": {
    "static_det":  {"original": {"fuel_mt": 180.63}, "historical": {"fuel_mt": 178.41}, "fuel_delta_pct": -1.23},
    "dynamic_det": {...},
    "dynamic_rh":  {...}
  },
  "assessment": {
    "verdict": "VALID_WITH_CAVEATS",
    "failures": [],
    "warnings": [{"field": "wind_speed_10m_kmh", "rmse": 3.41, "threshold": 5.0}]
  }
}
```

## Interpreting Results

- **High wind RMSE but low fuel delta**: Wind effect is small at these Beaufort numbers; the resistance terms are dominated by wave height and currents.
- **Large direction RMSE**: Check if direction magnitudes are small — a 90° difference on a 0.1 km/h current is negligible.
- **DP ≈ RH on historical data**: Expected, because historical data has zero forecast error (no benefit to re-planning).
- **Per-segment outliers**: Segment 5 (near WP 7-8) often shows larger differences due to the Strait of Hormuz coastal effects.

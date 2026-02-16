# Pipeline Coding Standards

## Import Rules

- **Physics**: `from shared.physics import calculate_speed_over_ground, calculate_fuel_consumption_rate`
- **HDF5**: `from shared.hdf5_io import read_actual, read_predicted, read_metadata`
- **Simulation**: `from shared.simulation import simulate_voyage`
- **Metrics**: `from shared.metrics import compute_result_metrics`
- **Beaufort**: `from shared.beaufort import wind_speed_to_beaufort`
- **NEVER** import from `Linear programing/` or `Dynamic speed optimization/` — those are legacy reference code

## Config Access

- All configuration comes from `experiment.yaml` (loaded by `cli.py` and passed as `config` dict)
- Approach-specific config: `config['static_det']`, `config['dynamic_det']`, `config['dynamic_rh']`
- Ship params: `config['ship']`
- Route: `config['collection']['route']` -> loads `config/routes/<name>.yaml`
- **No hardcoded** ship parameters, speed ranges, segment counts, file paths, or ETA values

## Function Signatures

Every `transform.py` must expose:
```python
def transform(hdf5_path: str, config: dict) -> dict
```

Every `optimize.py` must expose:
```python
def optimize(transform_output: dict, config: dict) -> dict
```

## Output Contract

All approaches must produce result JSONs matching the contract in `docs/WBS_next_phases.md` Section 7:
- `approach`: string identifier
- `planned.total_fuel_kg`, `planned.voyage_time_h`
- `simulated.total_fuel_kg`, `simulated.voyage_time_h`, `simulated.arrival_deviation_h`
- `metrics.fuel_gap_percent`, `metrics.fuel_per_nm`
- `time_series_file`: path to detailed CSV

## Data Access Patterns

| Approach | HDF5 Query |
|----------|-----------|
| Static Deterministic | `/actual_weather` WHERE `sample_hour = config.weather_snapshot` |
| Dynamic Deterministic | `/predicted_weather` WHERE `sample_hour = config.forecast_origin` |
| Dynamic Rolling Horizon | `/predicted_weather` WHERE `sample_hour = decision_hour` (per re-plan) |

## Weather Dict Field Names

Always use HDF5 column names: `wind_speed_10m_kmh`, `wind_direction_10m_deg`, `beaufort_number`, `wave_height_m`, `ocean_current_velocity_kmh`, `ocean_current_direction_deg`

## Integer Keys Only

Sample hours and forecast hours are always `int` (0, 1, 2, ...) — never floats or strings.

## Error Handling

- Port B (last waypoint) may have NaN marine data — handle gracefully
- SOG can be <= 0 in extreme weather — clamp to small positive value, log warning
- HDF5 file may be incomplete (interrupted collection) — check `get_completed_runs()` first

# Naming Conventions

## Pickle Files
- Pattern: `voyage_nodes_*.pickle` (e.g., `voyage_nodes_interpolated_weather.pickle`)
- Two wrapper formats exist:
  - **dict_wrapper**: `{'nodes': List[Node], 'voyage_start_time': datetime}` — used by collection scripts
  - **raw_list**: bare `List[Node]` — used by waypoint generation, visualization

## Weather Dict Fields
- Convention: `{measurement}_{height}_{unit}` (e.g., `wind_speed_10m_kmh`)
- Six fields: `wind_speed_10m_kmh`, `wind_direction_10m_deg`, `beaufort_number`, `wave_height_m`, `ocean_current_velocity_kmh`, `ocean_current_direction_deg`

## Node Class
- Preserves research paper naming: `Actual_weather_conditions`, `Predicted_weather_conditions` (capitalized)
- `class.py` at project root is the canonical (empty) definition
- Each producer script defines its own local Node class — keep them in sync

## Directory Names
- `Linear programing/` — note the single "m" (legacy spelling, do not rename)
- `Dynamic speed optimization/` — existing module

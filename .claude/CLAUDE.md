# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Maritime ship speed optimization research project for minimizing fuel consumption and GHG emissions. Compares Linear Programming with graph-based dynamic optimization for multi-segment voyages under varying environmental conditions (ocean currents, wind, waves).

## Common Commands

### Install Dependencies

```bash
pip3 install -r requirements_marine.txt                      # Weather forecasting (root)
pip3 install -r "Linear programing/requirements.txt"         # Optimization modules
```

### Run Weather Forecasting

```bash
python3 wind_forecasting.py              # Wind data from Open-Meteo API
python3 current_wave_forecasting.py      # Ocean currents and wave data
```

### Run Optimization

```bash
python3 "Linear programing/ship_speed_optimization_pulp.py"            # LP with PuLP
python3 "Linear programing/Gurobi.py"                                  # LP with Gurobi
python3 "Dynamic speed optimization/speed_control_optimizer.py"        # Dynamic graph-based
```

### Run Tests

```bash
cd test_files
python3 test_forecasting.py
```

### Remote Server Execution

Use the `remote-server` agent for all server operations (deploy, run, check status, download). Quick reference: `/remote-server`

## Architecture

### Two Optimization Approaches

1. **Linear Programming** (`Linear programing/`): Static optimization where weather is constant per segment. Uses SOS2 variables for piecewise linear approximation of nonlinear SOG-FCR relationships.

2. **Dynamic Optimization** (`Dynamic speed optimization/`): Graph-based approach with time-distance nodes that handles time-varying weather. Directed graph where edges represent speed choices; Dijkstra-like algorithms find minimum fuel paths.

### Core Mathematical Functions

`utility_functions.py` (exists in both modules) implements:
- **SOG calculation**: Speed Over Ground from SWS, wind, waves, currents
- **FCR calculation**: Fuel Consumption Rate (cubic relationship with power)
- **Resistance components**: Wind resistance, wave resistance, current effects

### Key Configuration Files

- `Dynamic speed optimization/ship_parameters.yaml`: Ship specs (200m, 32m beam, 10,000 kW, 11-13 knot range)
- `Dynamic speed optimization/weather_forecasts.yaml`: Time-windowed environmental conditions
- `Linear programing/voyage_data.py`: 12-segment route with per-segment environmental data

### Interactive Calculators

- `interactive_sog_calculator.py`: Forward calculation (SWS -> SOG)
- `interactive_sws_calculator.py`: Inverse calculation (desired SOG -> required SWS)

## Output Format

Weather forecasting scripts produce Excel files with two sheets:
- `daily_forecast`: Hourly forecasts for 7 days with metadata rows
- `hourly_forecast`: Current condition samples (one row per API call)

Multi-location scripts produce Excel files with 14 sheets:
- `summary`: Current conditions for all 13 waypoints
- `wp_01` through `wp_13`: Hourly forecasts for each waypoint

## Key Gotchas

- **Beaufort is calculated**, not from API. Wind speed (km/h) -> m/s -> Beaufort scale. Details: `/beaufort-scale`
- **Port B (WP 13) returns NaN** for marine data (coastal proximity, outside Open-Meteo Marine API coverage)
- **Two pickle wrapper formats**: `dict_wrapper` (dict with nodes + voyage_start_time) vs `raw_list` (bare List[Node])
- **Integer time keys only**: Sample hours are `0, 1, 2, ...` (int), never floats or strings
- **Local Node class per producer**: Each producer defines its own Node class (not imported from class.py)
- **`Linear programing/`**: Note the single "m" — legacy spelling, do not rename


## Reference Skills

Detailed reference material is available on-demand via skills:

| Skill | Content |
|-------|---------|
| `/pickle-data-structure` | Node class, weather dict fields, data access patterns, validation |
| `/pipeline-flow` | 5-stage pipeline, 3 strategies, file locations, current status |
| `/waypoints` | 13 GPS waypoints (lat/lon table), 12 segment distances |
| `/beaufort-scale` | Beaufort thresholds (BN 0-12), conversion formula, C1-C6 coefficients |
| `/waypoint-interpolation` | Intermediate waypoint generation (13 -> 3,388), output files, statistics |
| `/weather-collection` | Pickle collection script, run/deploy commands, data structure tree |
| `/remote-server` | TAU server connection details, SSH/SCP commands, tmux workflows |
| `/lp-optimizer` | LP architecture: data flow, SOG matrix, PuLP model, hardcoded values |
| `/dp-optimizer` | DP architecture: graph classes, Dijkstra, known bugs, SWS inverse |
| `/research-paper` | Paper equations (7-16), Tables 2-4, coefficient lookups, validation targets |
| `/lit-search` | Search for papers: web search, Semantic Scholar API, local PDFs |
| `/lit-validate` | Validate citation: DOI resolution, metadata cross-check, existence confirmation |
| `/lit-read` | Read PDF and extract structured literature entry matching template |
| `/lit-file` | Append reviewed entry to pillar file and update index |

## Pipeline Porting Agents

For implementing the new pipeline (`pipeline/`), use these specialized agents:

| Agent | Purpose |
|-------|---------|
| `lp-porter` | Port LP optimizer to `pipeline/static_det/` (transform + optimize) |
| `dp-porter` | Port DP optimizer to `pipeline/dynamic_det/` and `dynamic_rh/` |
| `physics-porter` | Consolidate `utility_functions.py` into `pipeline/shared/physics.py` |

## Literature Review Agent

| Agent | Purpose |
|-------|---------|
| `lit-reviewer` | Full pipeline: validate paper, read PDF, assess relevance, produce entry for review |

## Project Planning

- Work breakdown structure: `docs/WBS_next_phases.md`

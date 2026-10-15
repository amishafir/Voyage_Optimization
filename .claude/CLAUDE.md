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

## Live Weather Collector (`pipeline/`, since Oct 2026)

Archives every model run, once, for Route 1 (`persian_gulf_malacca`) and Route 2 (`st_johns_liverpool`). It replaces the old collector that sampled every 5 or 25 NM and let Open-Meteo choose models and grid cells.

```bash
cd pipeline
python3 run_all.py --route all --dry-run                   # partition and API budget only, no API calls
python3 run_all.py --route all                             # run until stopped (Ctrl+C finishes the current step)
python3 run_all.py --route all --backfill-wind --dry-run   # missed wind runs and their cost
python3 tests/test_collector.py                            # offline tests (fake API on a fake clock)
python3 -m pytest tests/test_subsegments.py
```

- **Subsegments** (`shared/subsegments.py`, `shared/rhumb.py`, `shared/weather_grids.py`): each leg (a rhumb line) is cut at the edges of the wind and current grid cells, so a subsegment has one bearing, one wind cell and one current cell. The first and last 2 NM of a route are trimmed (`PORT_TRIM_NM`).
- **Pinned models**: wind = ECMWF IFS (`models=ecmwf_ifs`, O1280 reduced Gaussian grid, nearest point); currents = Meteo-France SMOC (`models=meteofrance_currents`, Marine API, 1/12 deg grid). Every request pins `models` and `cell_selection=sea`. Under the default `best_match`, the wind grid switches to regional models east of 31 W in the Atlantic and in the Persian Gulf.
- **One query per distinct cell**, at a route point at least 0.05 NM inside it. Budget: about 7,800 calls/day for both routes, under the 10,000/day free limit.
- **Wind runs** (00/06/12/18 UTC) come from the Single Runs API, fetched once Open-Meteo's metadata shows the run published (+10 min) and a probe shows its full span (+144 h for 06/18 UTC, +360 h for 00/12 UTC). The archive answers while ECMWF output is still streaming in, so an early fetch gets only +0..+72 h. Missed or short wind runs are refetched automatically a day later (or with `--backfill-wind`).
- **Current runs** (daily SMOC, 00 UTC) are polled from 11:00 UTC and fetched over their full span. A missed current run is lost: Open-Meteo keeps no archive of them.
- **Wave runs** (since 2026-10-15): the 00 UTC Meteo-France MFWAM run (`models=meteofrance_wave`; height, direction "from", period), asked in the same requests as the currents (2 models x 5 variables still counts one call per location, so no extra calls). Same 1/12 deg grid as the currents: stored under `/wave` with rows of `/plan/current_cells`. Near coasts its land mask differs (48 of 1,635 cells read a neighbouring sea point, none NaN), and a combined request reports only the currents' grid point, so wave `served_lat/lon` are NaN. Height runs to +227 h. The 12 UTC MFWAM run is skipped to stay well under the daily limit. The present fuel model does not read wave height.
- **Storage**: one HDF5 archive per route, `pipeline/data/route1_runs.h5` and `route2_runs.h5`; layout in the docstring of `shared/run_archive.py`. The `/runs` table lists every expected run with its status, so restarts resume. The collector refuses to append if the route waypoints have changed; start a new file instead.
- **Routes** were revised on 2026-10-14 (`config/routes/*.yaml`) so no leg crosses land. Port B of Route 1 moved from inland Sumatra into the Strait of Malacca, which removes the old Port B NaN.
- **Known mismatch**: `dp_rebuild/geo_grid.py` interpolates legs in Mercator latitude, while `shared/rhumb.py` is linear in distance. Mid-leg points differ by up to 1.2 NM. `geo_grid.py` is unchanged so far.

### Deployment on edison

- Runs on `edison` (`edison-pc.eng.tau.ac.il`, user `user`) from `~/Ami/pipeline_v2` (a copy of `pipeline/`), as `python3 run_all.py --route all` in tmux session `collector_v2`.
- Cron entries are in `pipeline/deploy/edison/collector.crontab` (installed 2026-10-14; server time is UTC):
  - `ensure_collector.sh`, every 10 min: starts the collector if it is not running (reboot, crash). To stop it on purpose, `touch ~/Ami/pipeline_v2/STOP`, then Ctrl+C in the tmux session. Delete `STOP` to let it restart.
  - `backup_collector.sh`, daily at 04:30 UTC: rsyncs archives and logs to the lab NAS, `/tsl-disk/ami/voyage_weather_collector_backup` (`latest/` daily, `weekly/YYYY-MM-DD` on Sundays).
- Logs in `~/Ami/pipeline_v2/data/`: `collector_route1_route2.log`, `watchdog.log`, `backup.log`.

### Weather products (design decided by Tal, 2026-10-14/15; builder not written yet)

The optimizers will use 15-minute weather products built offline from the archived runs:

- **Pseudo real-time** at time t: the newest run started at or before t (wind leads 0-5 h, currents 0-23 h), interpolated to 15 min.
- **Forecasts** at each 6-hourly decision point, with zero publication delay (assumption: vessels can pay for timely forecasts). This is optimistic (ECMWF 00 UTC reaches paying users around 06 UTC, currents around midday), so the paper must state it as an idealization.
- **Horizon** fixed at 884 periods (221 h) for both components. The 06/18 UTC wind runs (+144 h) are extended by the previous 00/12 UTC run (+360 h). The binding constraint is the daily current run (+239 h) at the 18 UTC decision.
- **Interpolation** of wind and current as east/north components, not speed and angle. Wind direction is "from", current direction is "to".
- **Missed current run D**: real-time from Open-Meteo's history (it should still hold run D's leads 0-23 h; verify), fallback run D-1. Forecasts from run D-1, with the last day of the horizon taken from run D+1 (an accepted look-ahead in the tail). Record the source run of every value for sensitivity checks.

## v2 (`v2/`, since 2026-10-15)

A clean restart of the optimizer on the live collector's archives. Python (`v2/voyage_v2/`) reads the CLI and the HDF5 archive; the C++ core (`v2/cpp/`, no dependencies, compiled by Python on first use and called via `ctypes`) does the weather lookup, arc costs and the DP. Rolling-horizon re-planning is not written yet. Details: `v2/README.md`.

```bash
cd v2
python3 -m voyage_v2 ../pipeline/data/route1_runs.h5 --start "2026-10-14 13:20" --eta 280 --arc 100 12 40 20
python3 -m voyage_v2 ../pipeline/data/route1_runs.h5 --start "2026-10-14 13:20" --eta 280 --solve --plan-csv plan.csv
python3 tests/test_physics.py && python3 tests/test_voyage.py && python3 tests/test_dp.py
```

- Time = integer quarter-hour steps from the start (rounded to the nearest 0.25 h); ETA in hours, a multiple of 0.25.
- Weather at step t known at step tau: newest run issued by tau that reaches t, else the next older one; u/v interpolation between hours; if no run reaches t, hold the latest value before t (Tal, 2026-10-15). A start not covered by the archive is an error.
- `arc_cost(sub, sog, t, tau=None)` [mt]: SWS via the exact closed-form inverse, FCR = 0.000706 SWS^3; 9999 mt when the SWS is outside 2-25 kn (hardcoded for now).
- `--solve` / `Voyage.solve()`: DP on the full graph (distance lines at every subsegment boundary after merging < 0.15 NM, each merged piece still priced with its own cells and bearing, 4 s nodes; time lines every 0.25 h, 25 m nodes; SOG mean +/- 3 kn; arcs generated on the fly, 12 B per node). One core: Route 1 116 M nodes, 5.0 G arcs, 64 s, 1.5 GB; Route 2 47 M nodes, 24 s, 0.6 GB. Matches an explicit Python DP exactly on a test archive (`v2/tests/test_dp.py`).
- Beaufort uses the WMO m/s table (`pipeline/shared/beaufort.py`); `pipeline/dp_cpp` uses a different km/h table.

## Output Format

Weather forecasting scripts produce Excel files with two sheets:
- `daily_forecast`: Hourly forecasts for 7 days with metadata rows
- `hourly_forecast`: Current condition samples (one row per API call)

Multi-location scripts produce Excel files with 14 sheets:
- `summary`: Current conditions for all 13 waypoints
- `wp_01` through `wp_13`: Hourly forecasts for each waypoint

## Key Gotchas

- **Beaufort is calculated**, not from API. Wind speed (km/h) -> m/s -> Beaufort scale. Details: `/beaufort-scale`
- **Port B (WP 13) returns NaN** for marine data in the legacy data and pre-Oct-2026 HDF5 files (the old Port B was inland). The revised route fixes this for the live collector.
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
| `/hdf5-comparison` | Live vs historical data differences, API model mapping, interpretation |

## Pipeline Porting Agents

For implementing the new pipeline (`pipeline/`), use these specialized agents:

| Agent | Purpose |
|-------|---------|
| `lp-porter` | Port LP optimizer to `pipeline/static_det/` (transform + optimize) |
| `dp-porter` | Port DP optimizer to `pipeline/dynamic_det/` and `dynamic_rh/` |
| `physics-porter` | Consolidate `utility_functions.py` into `pipeline/shared/physics.py` |
| `hdf5-comparator` | Compare two HDF5 files (live vs historical): weather stats, optimization, substitutability |

## Literature Review Agent

| Agent | Purpose |
|-------|---------|
| `lit-reviewer` | Full pipeline: validate paper, read PDF, assess relevance, produce entry for review |

## Paper Quality Agents

| Agent | Purpose |
|-------|---------|
| `paper-reviewer` | Constructive review: checklist-based quality, style, and completeness check |
| `paper-critic` | Adversarial review: verify quotes in PDFs, find logical holes, flag vague writing, check citation accuracy |

## Project Planning

- Work breakdown structure: `docs/WBS_next_phases.md`

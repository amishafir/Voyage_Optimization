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
- **Wave runs** (since 2026-10-15): the 00 UTC Meteo-France MFWAM run (`models=meteofrance_wave`; height, direction "from", period), asked in the same requests as the currents (2 models x 5 variables still counts one call per location, so no extra calls). Same 1/12 deg grid as the currents: stored under `/wave` with rows of `/plan/current_cells`. Near coasts its land mask differs (48 of 1,635 cells read a neighbouring sea point, none NaN), and a combined request reports only the currents' grid point, so wave `served_lat/lon` are NaN. The 00 UTC runs fill the whole 240 h window (+0..+239 h, like the currents); the 12 UTC MFWAM run, which ends at +227 h, is skipped to stay well under the daily limit. The present fuel model does not read wave height.
- **Currents backup** (2026-10-21): Open-Meteo's `meteofrance_currents` stalled after the 2026-10-19 run (reported as open-meteo/open-meteo#2246) while Copernicus Marine kept publishing SMOC. If current run D is not on Open-Meteo by D 18:00 UTC, or Open-Meteo skips it, the collector fetches it from Copernicus Marine (`cmems_mod_glo_phy_anfc_merged-uv_PT1H-i`, `utotal`/`vtotal`, which include tides and Stokes drift) at the Copernicus point half a cell south-west of each Open-Meteo grid point (tidal cells correlate 0.99 with Open-Meteo), or the nearest sea point within 3 cells where that is land, through `collect/cmems_fetch.py` run in `~/cmems-venv` (with a Copernicus Marine login, `copernicusmarine login`, on edison, talraviv-pcl and the Mac). Copernicus keeps only its newest run, so it is tried hourly and stored only when it is run D; runs record `source` (`open-meteo` or `copernicus_marine`). The 2026-10-20 current run is lost (`missed` on all six routes); 2026-10-21 and 2026-10-22 came from Copernicus. The stall was a delayed Copernicus sea-level product that blocks Open-Meteo's SMOC downloader; Open-Meteo resumed with the 2026-10-23 run and cannot recover the runs it skipped (issue closed 2026-10-23), so its history has no 2026-10-20 real-time either. A rescued copy of that run (Routes 1-7, the four Copernicus points around every cell, 19-30 Oct) is in `pipeline/data/cmems_rescue/` (git-ignored).
- **Storage**: one HDF5 archive per route, `pipeline/data/route1_runs.h5` and `route2_runs.h5`; layout in the docstring of `shared/run_archive.py`. The `/runs` table lists every expected run with its status, so restarts resume. The collector refuses to append if the route waypoints have changed; start a new file instead.
- **Routes** were revised on 2026-10-14 (`config/routes/*.yaml`) so no leg crosses land. Port B of Route 1 moved from inland Sumatra into the Strait of Malacca, which removes the old Port B NaN.
- **Routes 3-7** (2026-10-19, Tal: short volatile routes, at most about 10 days / 2,500 NM): 3 = Tacoma - Anchorage (`tacoma_anchorage`, Gulf of Alaska, 1,414 NM, planned from Admiralty Inlet since the currents model has no data in Puget Sound), 4 = Rotterdam - Algeciras (`rotterdam_algeciras`, Channel and Biscay, 1,400 NM), 5 = Kaohsiung - Yokohama (`kaohsiung_yokohama`, Ryukyus and Kuroshio, 1,416 NM), 6 = Durban - Cape Town (`durban_cape_town`, Agulhas Current, 806 NM), 7 = Sydney - Auckland (`sydney_auckland`, Tasman Sea, 1,285 NM; in no set: Routes 3-7 would need 8,666 calls/day typical, too close to the limit once a rolling 24 h holds five wind runs). Traced along the World Bank / IMF commercial AIS density (2015-2021) as the densest-traffic path at most 5% longer than the shortest sea path, then thinned to rhumb legs; tools and method in `pipeline/tools/routes/README.md` (the AIS and coastline data are downloads, not in the repo). `run_all.py --route` takes a key, a list (`3,4,5`) or a set: `all` = 1,2 (edison), `volatile` = 3,4,5,6 (about 7,000 calls/day, at most 7,500; its own machine).
- **Known mismatch**: `dp_rebuild/geo_grid.py` interpolates legs in Mercator latitude, while `shared/rhumb.py` is linear in distance. Mid-leg points differ by up to 1.2 NM. `geo_grid.py` is unchanged so far.

### Deployment on edison

- Runs on `edison` (`edison-pc.eng.tau.ac.il`, user `user`) from `~/Ami/pipeline_v2` (a copy of `pipeline/`), as `python3 run_all.py --route all` in tmux session `collector_v2`.
- Cron entries are in `pipeline/deploy/edison/collector.crontab` (installed 2026-10-14; server time is UTC):
  - `ensure_collector.sh`, every 10 min: starts the collector if it is not running (reboot, crash). To stop it on purpose, `touch ~/Ami/pipeline_v2/STOP`, then Ctrl+C in the tmux session. Delete `STOP` to let it restart.
  - `backup_collector.sh`, daily at 04:30 UTC: rsyncs archives and logs to the lab NAS, `/tsl-disk/ami/voyage_weather_collector_backup` (`latest/` daily, `weekly/YYYY-MM-DD` on Sundays; weekly copies older than 3 months are deleted).
- Logs in `~/Ami/pipeline_v2/data/`: `collector_route1_route2.log`, `watchdog.log`, `backup.log`.

### Deployment on talraviv-pcl (Routes 3-6)

- Account `ami@talraviv-pcl.eng.tau.ac.il` (key `~/.ssh/id_ed25519_claude`; in the sudo group, but sudo needs its password, so root steps are Tal's). Its own public IP (132.66.50.222), so its own Open-Meteo quota. Ubuntu 24.04, Python 3.12; packages in the virtual environment `~/collector-venv` (numpy, h5py, pandas 3, PyYAML).
- Code in `~/voyage_collector` (a copy of `pipeline/` without data), run as `~/collector-venv/bin/python run_all.py --route volatile` in tmux session `collector_volatile`; archives `data/route{3,4,5,6}_runs.h5`, log `data/collector_route3_route4_route5_route6.log` (Route 6 added 2026-10-19; the earlier log was renamed to this).
- Started 2026-10-19 19:10 UTC (first runs: currents and waves 2026-10-19T00, wind 2026-10-19T12). Cron (`pipeline/deploy/talraviv-pcl/collector.crontab`, installed the same day): `ensure_collector.sh` every 10 min (`touch ~/voyage_collector/STOP` to stop on purpose), and edison's `backup_collector.sh` daily at 04:30 Israel time with this machine's paths, to `/tsl-disk/ami/voyage_weather_collector_backup_talraviv-pcl`. The server clock is Israel time. `/tsl-disk` (the lab NAS) is mounted from `/etc/fstab` (`auto,_netdev,nofail`).

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
python3 -m voyage_v2 ../pipeline/data/route1_runs.h5 --start "2026-10-14 13:20" --eta 280 --solve --luo
python3 tests/test_physics.py && python3 tests/test_voyage.py && python3 tests/test_dp.py && python3 tests/test_luo.py
```

- Time = integer quarter-hour steps from the start (rounded to the nearest 0.25 h); ETA in hours, a multiple of 0.25.
- Weather at step t known at step tau: newest run issued by tau that reaches t, else the next older one; u/v interpolation between hours; if no run reaches t, hold the latest value before t (Tal, 2026-10-15). A start not covered by the archive is an error.
- `arc_cost(sub, sog, t, tau=None)` [mt]: SWS via the exact closed-form inverse, FCR = 0.000706 SWS^3; 9999 mt when the SWS is outside 2-25 kn (hardcoded for now).
- `--solve` / `Voyage.solve()`: DP on the full graph (distance lines at every subsegment boundary after merging < 0.15 NM, each merged piece still priced with its own cells and bearing, 4 s nodes; time lines every 0.25 h, 25 m nodes; SOG mean +/- 3 kn; arcs generated on the fly, 12 B per node). One core: Route 1 116 M nodes, 5.0 G arcs, 64 s, 1.5 GB; Route 2 47 M nodes, 24 s, 0.6 GB. Matches an explicit Python DP exactly on a test archive (`v2/tests/test_dp.py`).
- `--luo` / `Voyage.solve_luo()`: Luo et al. multistage DP on the same data: constant SOG within decision epochs of `--epoch` 0.25 h steps (24 = 6 h), nodes only on epoch lines every `--dist-step` NM (default 0.1 kn x epoch, 0.6 NM at 6 h), fuel integrated per subsegment and weather step, no merging or length snapping. Route 1 at 6 h: 2.6 s; at 0.25 h: 117 s. `--luo-pricing start` prices each arc at its start point as Luo et al. do; every plan reports planned fuel and realized fuel (its SOG profile in the actual weather, every subsegment-by-step piece priced). On the Oct 14 archive, start-priced 6 h Luo realizes +0.90% (Route 1) and +1.60% (Route 2) over the full graph, worse than constant SOG. Rerun on the 2026-10-19 snapshot (`pipeline/data/snapshot_2026-10-19_12Z`, start 2026-10-14 12:00 UTC, the earliest covered): full graph saves 0.29% / 0.61% over constant SOG; start-priced Luo +1.37% / +2.70% over the full graph at 6 h, +0.22% / +0.54% at 1 h, +0.07% / +0.16% at 0.25 h; results in `v2/results/2026-10-19_full_graph_vs_luo/`. Routes 3-6 (snapshot `pipeline/data/snapshot_2026-10-25_15Z`, copied from talraviv-pcl; also at `ami@talraviv-pcl:~/voyage_collector/data/snapshots/2026-10-25_15Z/`; start 2026-10-21 00:00 UTC, ETAs 118/117/118/67 h): full graph saves 2.23% / 2.08% / 4.00% / 0.63% over constant SOG; start-priced Luo +2.06% / +3.07% / +6.81% / +3.43% over the full graph at 6 h, +0.43% / +0.64% / +1.32% / +0.73% at 1 h, +0.21% / +0.33% / +0.46% / +0.47% at 0.25 h; Luo priced piece by piece within 0.02% at 0.25 h, 0.12% at 1 h, 0.77% at 6 h; results in `v2/results/2026-10-25_routes3-6/`.
- Run time is about the number of SWS evaluations (50-56 ns each); relaxing an arc costs a few ns. The full graph shares an FCR only where a speed repeats (its distance-to-distance table by duration and time-to-time table by advance); 99% of its evaluations (Route 3: 603 of 611 M) are on distance-to-time-line and time-to-distance-line arcs, whose speeds are all distinct, so no FCR cache helps it. In Luo's graph an epoch has only about 61 speeds (grid advances), so `luo.cpp` caches the FCR per (subsegment, step, advance) once per epoch (default since commit `4515546`; same plans, tests unchanged): on tsl2, Route 3, 0.25 h piece by piece 23.0 s to 2.7 s, 0.5 h 10.0 s to 1.4 s, against 11.0 s for the full graph. A possible next step: cumulative fuel along the route per advance would make each Luo arc O(1).
- tsl2 rerun of Routes 3-6 (`v2/results/2026-10-25_routes3-6_tsl2/` before the cache, `..._tsl2_fcrcache/` with it; tables in the Routes 3-6 README): Luo 0.5 h piece by piece within 0.06% of the full graph, start point +0.36% to +0.72%; at 0.25 h the SOG step hardly matters (0.2 / 0.1 / 0.05 kn piece by piece within 0.04% / 0.02% / 0.02%; start point improves only on Route 5, +0.61% / +0.46% / +0.39%). Halving the SOG step quadruples Luo's work; with the cache every Luo variant is faster than the full graph.
- Beaufort uses the WMO m/s table (`pipeline/shared/beaufort.py`); `pipeline/dp_cpp` uses a different km/h table.
- Run experiments on the lab machines, not the laptop. tsl2-mac (M3 Ultra) shares this Dropbox folder: run in place with `ssh tsl2 'cd ~/Library/CloudStorage/Dropbox/research/SpeedControl/Voyage_Optimization && /opt/miniconda3/envs/voyage/bin/python ...'`; archives in `pipeline/data/` (git-ignored, Dropbox-synced). Linux boxes: `v2/deploy/sync_to_host.sh shlomo1` copies code to `~/Ami/voyage` and archives from edison (Routes 1-2 only; copy Route 3-6 archives or snapshots from talraviv-pcl yourself). Each host builds the C++ core into `v2/cpp/build/<host>/`. `v2/tools/benchmark.py DATA_DIR` times the full graph and the Luo variants. shlomo7's system `python3` (3.8) has numpy, h5py, pandas and PyYAML; shlomo6's does not. tsl2-mac has FileVault on: after an unattended restart (it crashed on 2026-10-25 when another project's jobs used up its 96 GB) it accepts SSH only with a password, which unlocks the disk, and its Dropbox stays stopped until someone logs in at the screen or through Screen Sharing, so the shared folder there is stale until then. Size parallel jobs there by memory, not cores.

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

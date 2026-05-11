# dp_cpp — C++ Voyage Optimization Solvers

Two standalone programs that compute minimum-fuel ship speed schedules for a fixed route and ETA. Both read the same YAML route file and HDF5 weather file.

## Programs

| Executable | Model | Source |
|------------|-------|--------|
| `dp_SR` | **Shafir-Raviv free DP** — unconstrained speed per arc | `SR_main.cpp` |
| `dp_luo` | **Luo block DP + baseline** — SOG may be changed every 6 hours. | `luo_main.cpp` |

---

## Build

**Dependencies:** CMake ≥ 3.17, a C++17 compiler, HDF5 (C library), yaml-cpp.

```bash
# macOS
brew install cmake hdf5 yaml-cpp

cd pipeline/dp_cpp
cmake -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build -j
```

Both executables land in `build/`.

---

## dp_SR — Shafir-Raviv Free DP

Builds a time-distance graph where each node is a `(t, d)` point on either a V-line (time boundary, every `dt_h = 6 h`) or an H-line (distance boundary at weather-zone and course-change crossings). Every arc carries the fuel cost of one atomic edge: the realized SOG, SWS, FCR, and weather are computed on the arc itself.

The optimal schedule is the shortest path (minimum fuel) from `(0, 0)` to any sink node `(·, L)` with arrival ≤ ETA, found by a single-pass Bellman relaxation in topological order.

```
./build/dp_SR [OPTIONS]
  --yaml PATH       Route YAML  (default: route.yaml)
  --h5   PATH       HDF5 file   (default: voyage_weather.h5)
  --eta  HOURS      Override ETA in hours
  --min_speed KNOTS Minimum SOG in knots  (default: mean_sog - 3)
  --max_speed KNOTS Maximum SOG in knots  (default: mean_sog + 3)
  --zeta_nm  NM     Distance snap for H-line arc destinations (default: 1.0)
  --tau_h    HOURS  Time snap for V-line arc destinations     (default: 0.1)
  --csv             Write per-arc schedule to free_dp.csv
```

`--zeta_nm` controls how finely H-line arc endpoints are quantized along the distance axis; `--tau_h` does the same for the time axis on V-line arcs. Halving both roughly doubles the number of distinct nodes and increases graph build time and memory accordingly.

The default speed range is centered on the mean SOG `L / ETA`. If `--eta` is supplied, the mean SOG (and therefore the defaults) updates accordingly.

### Output

```
dp_SR — SUMMARY
  Total fuel:  359.594 mt
  Voyage time: 280.000 h  (ETA = 280.0 h)
  Graph: 115932 nodes, 4705132 atomic edges
  Build: 14.1 s  Solve: 0.27 s
```

With `--csv`, writes **free_dp.csv** — one row per atomic edge in the optimal schedule:

| Column | Description |
|--------|-------------|
| `time_h` | Departure time of arc [h] |
| `distance_nm` | Departure distance along route [nm] |
| `lat_deg`, `lon_deg` | Position at departure |
| `bearing_deg` | Ship heading [°] |
| `sog_kn` | Realized SOG = Δd/Δt [kn] |
| `sws_kn` | Speed through water [kn] |
| `fcr_mt_per_h` | Fuel consumption rate [mt/h] |
| `fuel_mt` | Fuel for this arc [mt] |
| `duration_h` | Arc duration [h] |
| `wind_speed_kmh`, `wind_dir_deg`, `beaufort` | Wind |
| `wave_height_m` | Significant wave height [m] |
| `current_vel_kmh`, `current_dir_deg` | Ocean current |

---

## dp_luo — Luo Block DP

Uses a graph where nodes are `(col, d_idx)` with distance indices `d_idx ∈ {0, 1, …, L_scaled}` and time columns `col ∈ {0, 1, …, T}`. Physical distance = `d_idx × res_nm`. Within each 6 h block the SOG is constant, equal to `(d2 − d1) × res_nm / dt_h`. The cost of each arc is computed by walking through weather-zone and course-change sub-segment boundaries between the physical endpoints, summing the fuel at the fixed SOG for each sub-segment.

The distance resolution defaults to 1 NM and can be set with `--res_nm` anywhere in [0.1, 10] NM. Finer resolution expands the set of reachable SOGs per block (smaller quantization error) at the cost of a larger DP table — the number of grid points scales as `L / res_nm`, and solve time roughly as `(L / res_nm)²`.

When ETA is not an exact multiple of 6 h, a partial final block of duration `dt_last = ETA mod 6` is added.

`dp_luo` also provides a **baseline mode**: no graph, single linear walk at the fixed mean SOG `= L / ETA`, splitting the route at the same boundaries and computing sub-segment SWS/FCR/fuel for each.

```
./build/dp_luo [OPTIONS]
  --yaml PATH       Route YAML  (default: route.yaml)
  --h5   PATH       HDF5 file   (default: voyage_weather.h5)
  --eta  HOURS      Override ETA in hours
  --min_speed KNOTS Minimum SOG in knots  (default: mean_sog - 3)
  --max_speed KNOTS Maximum SOG in knots  (default: mean_sog + 3)
  --res_nm  NM      Distance grid resolution (default: 1.0, range [0.1, 10])
  --baseline        Compute fixed mean-SOG baseline (no graph)
  --csv             Write schedule CSV(s)
                      Luo DP  → luo_dp.csv
                      Baseline → baseline.csv
```

### Resolution vs. solve time (Route 1, ETA 280 h)

| `--res_nm` | Grid points | Fuel (mt) | Solve time |
|------------|-------------|-----------|------------|
| 5.0 | 679 | 367.4 | ~3 s |
| 1.0 (default) | 3 393 | 366.1 | ~30 s |
| 0.5 | 6 786 | 366.1 | ~120 s |

### Output

```
Luo DP  (1.00 nm grid resolution)
Route:      3393.24 nm  →  L_scaled = 3393  (3393.00 nm)
Speed:      [9.1, 15.1] kn
Regular:    46 blocks × 6 h, step [55, 91] idx  ([55.00, 91.00] nm)
ETA block:  1 × 4.0 h (t=276→280), step [37, 61] idx
H-lines:    162 boundaries
Total fuel:  366.140 mt
```

With `--csv`, writes **luo_dp.csv** — one row per sub-segment in the optimal schedule:

| Column | Description |
|--------|-------------|
| `block` | 6 h block index |
| `time_h` | Sub-segment departure time [h] |
| `distance_nm` | Sub-segment departure distance [nm] |
| `lat_deg`, `lon_deg` | Position |
| `bearing_deg` | Ship heading [°] |
| `sog_kn` | Block SOG — constant within block [kn] |
| `sws_kn` | Speed through water for this sub-segment [kn] |
| `fcr_mt_per_h` | Fuel rate for this sub-segment [mt/h] |
| `fuel_mt` | Fuel for this sub-segment [mt] |
| `duration_h` | Sub-segment duration [h] |
| `wind_speed_kmh`, `wind_dir_deg`, `beaufort` | Wind |
| `wave_height_m` | Wave height [m] |
| `current_vel_kmh`, `current_dir_deg` | Current |

**baseline.csv** has the same columns minus `block`.

---

## Input Files

### Route YAML (`route.yaml`)

Defines the voyage: one forecast window with route segments, each carrying `id`, `distance` (nm), and `ship_heading` (deg). The ETA is the window end time. The route is synthesized into 6 h sub-windows internally. Weather data is not read from this file — it comes entirely from the HDF5 file.

### HDF5 Weather (`voyage_weather.h5`)

| Table | Content |
|-------|---------|
| `/actual_weather` | Static deterministic snapshot (`sample_hour = 0`) |
| `/predicted_weather` | Forecast data indexed by `sample_hour` and `forecast_hour` |
| `/metadata` | Route waypoints — lat, lon, node IDs, cumulative distances |

Both programs query `sample_hour = 0` (static-deterministic mode).

---

## Source Layout

```
src/
  common.hpp             TDKey hash, ShipParameters, WeatherDict
  physics.cpp/.hpp       Ship physics: SOG↔SWS inverse, FCR, weather corrections
  geo_grid.cpp/.hpp      Rhumb-line geometry, NWP-grid H-line crossing detection
  route.cpp/.hpp         Route/YAML loading, segment lookup, paper waypoints
  nodes.cpp/.hpp         GraphConfig, V-line and H-line grid construction
  weather.cpp/.hpp       HDF5 weather reader, Weather and WeatherDict structs
  frame.cpp/.hpp         Frame: cfg + route + weather assembled into one object
  atomic_edges.cpp/.hpp  BFS atomic-edge builder            (dp_SR only)
  bellman.cpp/.hpp       Topological Bellman shortest-path  (dp_SR only)
  SR_main.cpp            dp_SR entry point
  luo_main.cpp           dp_luo entry point (Luo block DP + baseline)
```

### Key types

**`GraphConfig`** — solver parameters: `length_nm`, `eta_h`, `dt_h` (block duration 6 h), `tau_h` (time snap 0.1 h, dp_SR only), `zeta_nm` (distance snap 1 nm, dp_SR only), `v_min`/`v_max` (SOG range). For dp_luo the distance resolution is a separate `res_nm` CLI parameter, not stored in `GraphConfig`.

**`AtomicEdge`** — one arc in the dp_SR graph: `(src_t, src_d) → (dst_t, dst_d)` carrying `sog` (realized Δd/Δt), `target_sog` (decision speed, used as Luo lock label), `sws`, `fcr`, `fuel_mt`, and `crosses_v_line`.

**`Frame`** — assembled solver context. `cell_weather_at(d, sample_hour, forecast_hour)` queries the HDF5 file for the NWP cell covering distance `d` along the route. `sog_grid()` returns the discretized speed decisions in `[v_min, v_max]` at 0.1 kn steps.

**`BellmanSolver`** — single-source shortest path by forward relaxation in topological `(t, d)` order. `result("hard", eta_h)` returns the minimum-fuel path arriving at or before ETA.

---

## Physics Model

Implemented in `physics.cpp`, following the research paper (Eqs 7–16):

1. **Speed loss** from wind and waves: `Δv% = Cβ × CU × CForm`  (Table 2–4 coefficients)
2. **Weather-corrected speed**: `vw = SWS × (1 − Δv/100)`
3. **SOG vector synthesis**: resolves `vw` and ocean current into ground speed
4. **FCR**: `0.000706 × SWS³` [mt/h]
5. **SWS from SOG**: binary-search inverse of the forward model (tolerance 0.001 kn, 50 iterations max)

Ship parameters are fixed in `ShipParameters` (`common.hpp`): 200 m length, 32 m beam, 10 000 kW, block coefficient 0.75.

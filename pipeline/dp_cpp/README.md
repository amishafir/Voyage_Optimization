# dp_cpp — C++ Dynamic Programming Solver

High-performance C++ port of the Python `dp_rebuild` pipeline stage.
Builds an atomic-edge graph over a (time, distance) grid and solves it
with two Bellman DP modes: **Free DP** (unconstrained SOG) and **Luo DP**
(SOG locked per 6-hour block, as in the Luo et al. formulation).

## Dependencies

| Library | Purpose | Install |
|---------|---------|---------|
| HDF5 (C) | Read voyage weather data | `brew install hdf5` |
| yaml-cpp | Parse route YAML | `brew install yaml-cpp` |
| CMake ≥ 3.17 | Build system | `brew install cmake` |

## Build

```bash
cd pipeline/dp_cpp
mkdir -p build && cd build
cmake ..
cmake --build . -j$(sysctl -n hw.ncpu)   # macOS
# cmake --build . -j$(nproc)             # Linux
```

The binary is placed at `pipeline/dp_cpp/build/dp_rebuild`.

## Run

```bash
./dp_rebuild [OPTIONS]

Options:
  --yaml PATH       Route YAML  (default: ../../Dynamic speed optimization/weather_forecasts.yaml)
  --h5   PATH       HDF5 file   (default: ../data/voyage_weather.h5)
  --eta  HOURS      Override ETA in hours            (e.g. --eta 240)
  --min_speed KNOTS Override minimum SOG in knots    (e.g. --min_speed 9)
  --max_speed KNOTS Override maximum SOG in knots    (e.g. --max_speed 21)
  --help            Show this message
```

Example:

```bash
./dp_rebuild --eta 240 --min_speed 14 --max_speed 21
./dp_rebuild --yaml /path/to/route.yaml --h5 /path/to/voyage_weather.h5
```

The HDF5 file (`voyage_weather.h5`) is produced by the data-collection pipeline
and lives on the remote server at `pipeline/data/voyage_weather.h5`.

## Output

The solver prints a frame summary, graph build statistics, and results for both
DP modes:

```
Free DP:   208.123 mt  (solve 0.04 s)
Luo DP:    210.456 mt  (solve 0.12 s)
Δ (Luo-Free): +2.333 mt  (Luo ≥ Free by construction)
Graph: 4821 nodes, 38764 atomic edges, build 1.3 s
```

## Module Overview

| File | Responsibility |
|------|---------------|
| `common.hpp` | Shared types: `TDKey`, `ShipParameters`, `WeatherDict` |
| `physics.{hpp,cpp}` | SOG, FCR, SWS inverse (binary search), Beaufort |
| `geo_grid.{hpp,cpp}` | Rhumb-line geometry, NWP-grid crossings, cell index |
| `route.{hpp,cpp}` | Route/segment types, YAML loader, multi-window synthesis |
| `nodes.{hpp,cpp}` | `Node`, `GraphConfig`, V-line / H-line grid builders |
| `weather.{hpp,cpp}` | HDF5 reader, cell-canonical weather aggregation |
| `frame.{hpp,cpp}` | `Frame`: combines config + route + weather into one object |
| `atomic_edges.{hpp,cpp}` | BFS over (t, d) grid → `AtomicEdge` list |
| `bellman.{hpp,cpp}` | Free DP: forward Bellman, hard/soft ETA |
| `bellman_locked.{hpp,cpp}` | Luo DP: state = (node, SOG lock), unlocks on V-lines |
| `main.cpp` | CLI driver: load → frame → graph → solve → print |

## Graph Construction

The solver discretises the voyage into a (time, distance) grid:

- **V-lines** (constant time): placed at every `dt_h` hours (default 6 h),
  at forecast-window boundaries, and at the ETA.
- **H-lines** (constant distance): placed at segment boundaries and at every
  NWP cell crossing along the rhumb-line track; infeasible sub-gaps (no integer
  multiple of `tau_h` fits within the speed range) are dropped.

From each grid node, one **atomic edge** is emitted per target SOG in
`[v_min, v_max]`. Each edge reaches either the next H-line (speed crossing)
or the next V-line (time crossing), whichever comes first. Edge cost is
fuel consumed (mt), computed from SWS via the cubic FCR law.

## DP Modes

**Free DP** — standard shortest-path on the atomic-edge DAG. Any SOG may be
chosen on any edge; the solver finds the globally minimum-fuel path to any
sink node at or before the ETA.

**Luo DP** — augments each node with a *lock* state (the target SOG chosen at
the start of the current 6 h block). Within a block only edges matching the
locked SOG are admissible; the lock is released at every V-line (block
boundary). State space: `(node_id, lock_sog | UNLOCKED)`.

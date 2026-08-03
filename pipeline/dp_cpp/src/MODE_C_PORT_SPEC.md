# Mode C Port Spec — C++ DP Solver

**Goal:** Mirror the Python Mode C wiring (per-block actual weather) in the
C++ DP solver at `pipeline/dp_cpp/`. Currently the C++ runs Mode A only
(single weather snapshot at `sample_hour = 0`). After this port both
languages will be functionally equivalent.

**Reference Python diff:** commit `ef59dd9` on `main`. Files:
- `pipeline/dp_rebuild/frame.py`
- `pipeline/dp_rebuild/build_edges_locked.py`
- `pipeline/dp_rebuild/run_route1.py` / `run_route2.py`

**Reference results to reproduce after porting:**
- §5.4 / §5.5 of `docs/meeting_prep_2026_05_18.md`
- `pipeline/dp_rebuild/results/speed_sweep_2026_05_17.md`
- `pipeline/dp_rebuild/results/eta_sweep_2026_05_18.md`

**Effort:** ~30-60 min mechanical edits + rebuild + sanity-check runs.

---

## Behavior contract after porting

| Invocation | Per-block sample_hour | Mode |
|---|---|---|
| `--sample_hour` **omitted** | All blocks read `sh = 0` | A (backward-compat) |
| `--sample_hour 222` | Block `k` reads `sh = 222 + 6·k` | C |
| `--sample_hour 0` (explicit) | Block `k` reads `sh = 6·k` | C |

When `--sample_hour` is omitted, the §2.4 C++↔Python parity numbers
must still hold exactly (Mode A, sh=0). Do not break Mode A behaviour.

---

## File 1 — `pipeline/dp_cpp/src/frame.hpp`

### Edit 1a — add a field

In `class Frame`, after the existing line:
```cpp
double                 sog_step  = 0.1; // kn
```
**add**:
```cpp
int                    base_sample_hour = 0; // Mode C offset; 0 = Mode A
```

### Edit 1b — apply the offset in `sample_hour_for_block`

Replace the existing two-line method:
```cpp
int    sample_hour_for_block(double t) const {
    return static_cast<int>(std::round(block_start_time(t))); }
```
with:
```cpp
int    sample_hour_for_block(double t) const {
    return base_sample_hour
         + static_cast<int>(std::round(block_start_time(t))); }
```

### Edit 1c — extend `make_frame` declaration

Replace:
```cpp
Frame make_frame(const Route& route, const VoyageWeather& voyage,
                  const std::vector<Waypoint>& waypoints,
                  const GraphConfig* cfg_override = nullptr,
                  double grid_deg = 0.5, double sog_step = 0.1);
```
with:
```cpp
Frame make_frame(const Route& route, const VoyageWeather& voyage,
                  const std::vector<Waypoint>& waypoints,
                  const GraphConfig* cfg_override = nullptr,
                  double grid_deg = 0.5, double sog_step = 0.1,
                  int base_sample_hour = 0);
```

---

## File 2 — `pipeline/dp_cpp/src/frame.cpp`

### Edit 2 — propagate `base_sample_hour` through `make_frame`

Replace the existing `make_frame` body (around line 42-61):
```cpp
Frame make_frame(const Route& route, const VoyageWeather& voyage,
                  const std::vector<Waypoint>& waypoints,
                  const GraphConfig* cfg_override,
                  double grid_deg, double sog_step) {
    Frame f;
    f.route    = route;
    f.voyage   = &voyage;
    f.waypoints= waypoints;
    f.grid_deg = grid_deg;
    f.sog_step = sog_step;

    if (cfg_override)
        f.cfg = *cfg_override;
    else
        f.cfg = GraphConfig::from_route(route, 6.0, 1.0, 0.1, 30.0, 9.0, 13.0);

    f.v_line_times    = v_line_times_from_route(f.cfg, route);
    f.h_line_distances = h_line_distances_from_geo(f.cfg, waypoints, grid_deg);
    return f;
}
```
with:
```cpp
Frame make_frame(const Route& route, const VoyageWeather& voyage,
                  const std::vector<Waypoint>& waypoints,
                  const GraphConfig* cfg_override,
                  double grid_deg, double sog_step,
                  int base_sample_hour) {
    Frame f;
    f.route    = route;
    f.voyage   = &voyage;
    f.waypoints= waypoints;
    f.grid_deg = grid_deg;
    f.sog_step = sog_step;
    f.base_sample_hour = base_sample_hour;

    if (cfg_override)
        f.cfg = *cfg_override;
    else
        f.cfg = GraphConfig::from_route(route, 6.0, 1.0, 0.1, 30.0, 9.0, 13.0);

    f.v_line_times    = v_line_times_from_route(f.cfg, route);
    f.h_line_distances = h_line_distances_from_geo(f.cfg, waypoints, grid_deg);
    return f;
}
```

---

## File 3 — `pipeline/dp_cpp/src/SR_main.cpp`

### Edit 3a — add `--sample_hour` CLI option

In the `optional` declarations block (around line 76-81), after the existing
`std::optional<...>` lines, **add**:
```cpp
std::optional<int> sample_hour_override;
```

In the CLI parsing block (around line 92-99), after the line:
```cpp
else if (arg == "--tau_h")     tau_h_override     = std::stod(need_next());
```
**add**:
```cpp
else if (arg == "--sample_hour") sample_hour_override = std::stoi(need_next());
```

### Edit 3b — extend usage() docstring

In the `usage()` function (around line 59-71), in the format string after
`--tau_h    HOURS  ...`, **add a line**:
```
"  --sample_hour N   Mode C: voyage-start sample_hour; per-block lookup reads N+6k\n"
"                    (default: omitted → Mode A at sh=0)\n"
```

### Edit 3c — pass `base_sample_hour` to `make_frame`

Replace the existing line (around line 126):
```cpp
Frame frame = make_frame(route, voyage, WAYPOINTS, &base_cfg);
```
with:
```cpp
int base_sh = sample_hour_override.value_or(0);
Frame frame = make_frame(route, voyage, WAYPOINTS, &base_cfg,
                          0.5, 0.1, base_sh);
```

### Edit 3d — switch atomic-edge build to per-block lookup in Mode C

Replace the existing lines (around line 132-134):
```cpp
auto [nodes, edges] = build_atomic_edges(frame, /*forecast_hour=*/-1,
                                          /*override_sample_hour=*/0,
                                          /*verbose=*/false);
```
with:
```cpp
// -1 = use frame.sample_hour_for_block per arc (Mode C);
//  0 = single-snapshot at sh=0 (Mode A — preserved default).
int ovr_sh = sample_hour_override ? -1 : 0;
auto [nodes, edges] = build_atomic_edges(frame, /*forecast_hour=*/-1,
                                          /*override_sample_hour=*/ovr_sh,
                                          /*verbose=*/false);
```

---

## File 4 — `pipeline/dp_cpp/src/luo_main.cpp`

### Edit 4a — add `--sample_hour` CLI option

Find the CLI option declarations (search for `std::optional<double> eta_override`
or similar). Add an `std::optional<int> sample_hour_override;` alongside.

Find the CLI parser block (search for `else if (arg == "--csv")` or similar).
**Add** a parsing case for `--sample_hour`:
```cpp
else if (arg == "--sample_hour") sample_hour_override = std::stoi(need_next());
```

### Edit 4b — extend usage()

Add a line documenting `--sample_hour N` analogous to Edit 3b.

### Edit 4c — pass `base_sample_hour` to `make_frame`

Find the `make_frame(...)` call site. Mirror Edit 3c — pass
`sample_hour_override.value_or(0)` as the new last argument.

### Edit 4d — switch `eval_arc`'s weather lookup to per-block

In `eval_arc` (around line 63-100), replace line 82:
```cpp
Weather wx = fr.cell_weather_at(sd, /*sample_hour=*/0, /*forecast_hour=*/-1);
```
with:
```cpp
// Mode C: block-constant sample_hour computed once at block start
int sh_block = fr.sample_hour_for_block(t_h);
Weather wx = fr.cell_weather_at(sd, sh_block, /*forecast_hour=*/-1);
```
Hoist `sh_block` outside the sub-segment loop if you prefer — it is constant
across all sub-segments of a single arc (entire arc is one 6 h block).

**Important:** when `--sample_hour` is omitted, `base_sample_hour=0` and
`sh_block = 6·block_index(t_h)`. This is **not** the original Mode A
behaviour (which always read sh=0 regardless of block). To preserve
backward-compat for the §2.4 parity numbers, gate the change on whether
Mode C was requested. Use a function parameter or thread the flag through
`Frame` — simplest is to add a `Frame` field:

In `frame.hpp` after `int base_sample_hour = 0;`, also add:
```cpp
bool mode_c_enabled = false;
```

Then in `eval_arc` (and `eval_baseline`, Edit 4e):
```cpp
int sh_block = fr.mode_c_enabled ? fr.sample_hour_for_block(t_h) : 0;
Weather wx = fr.cell_weather_at(sd, sh_block, -1);
```

In `make_frame` set `f.mode_c_enabled = (base_sample_hour != 0)` — or pass
an explicit bool. Simplest: add `bool mode_c` param to `make_frame` and
set from `sample_hour_override.has_value()` at the call sites.

### Edit 4e — same change in `eval_baseline`

In `eval_baseline` (around line 103-129), replace line 114:
```cpp
Weather wx = fr.cell_weather_at(sd, /*sample_hour=*/0, /*forecast_hour=*/-1);
```
with:
```cpp
// Mode C: per-sub-segment block (voyage time = sd / sog)
double t_at_sd = sd / sog;
int sh = fr.mode_c_enabled ? fr.sample_hour_for_block(t_at_sd) : 0;
Weather wx = fr.cell_weather_at(sd, sh, /*forecast_hour=*/-1);
```

---

## Build

```bash
cd /Users/ami/Desktop/university/pipeline/dp_cpp/build
cmake --build . -j
```

If cmake complains about stale CMakeCache, `rm -rf build && mkdir build && cd build && cmake .. && cmake --build . -j`.

Build deps (already installed if existing binaries work): `cmake ≥ 3.17`,
`hdf5`, `yaml-cpp`.

---

## Validation runs

### Test 1 — Mode A backward compatibility (parity preserved)

```bash
cd /Users/ami/Desktop/university/pipeline/dp_cpp/build
./dp_SR --yaml ../../config/routes/persian_gulf_malacca.yaml \
        --h5 ../../data/experiment_b_138wp.h5 \
        --eta 280 --min_speed 9.13333 --max_speed 15.13333
```

**Expected:** SR fuel ≈ **359.594 mt** (matches §2.4 parity row).
If different by more than 0.001 mt, Mode A is broken — debug.

### Test 2 — Mode C reproduces §5.4 v_max=15 R1 row

```bash
./dp_SR --yaml ../../config/routes/persian_gulf_malacca.yaml \
        --h5 ../../data/experiment_b_138wp.h5 \
        --eta 280 --min_speed 9 --max_speed 15 \
        --sample_hour 222
```

**Expected:** SR fuel ≈ **358.168 mt** (Python value; C++ should be within
±0.001 mt of Python from §5.4 numbers — typically C++ is ~0.05% higher
due to FP ordering, so anywhere in [358.0, 358.4] is acceptable).

### Test 3 — Mode C reproduces §5.5 R1 ETA=200 (the headline result)

```bash
./dp_SR --yaml ../../config/routes/persian_gulf_malacca.yaml \
        --h5 ../../data/experiment_b_138wp.h5 \
        --eta 200 --min_speed 9 --max_speed 25 \
        --sample_hour 222
```

**Expected:** SR fuel ≈ **692.316 mt**. (Python value from §5.5.) Acceptable
range: [692.0, 692.7].

### Test 4 — Luo parity at R2 storm

```bash
./dp_luo --yaml ../../config/routes/st_johns_liverpool.yaml \
         --h5 ../../data/experiment_d_391wp.h5 \
         --eta 168 --min_speed 9 --max_speed 15 \
         --sample_hour 180
```

**Expected:** Luo fuel ≈ **195.641 mt** (Python value from §5.4).

### Test 5 — Baseline parity at R2 storm

```bash
./dp_luo --yaml ../../config/routes/st_johns_liverpool.yaml \
         --h5 ../../data/experiment_d_391wp.h5 \
         --eta 168 \
         --sample_hour 180 --baseline
```

**Expected:** Baseline fuel ≈ **203.457 mt** (Python value from §5.4).

---

## Deliverable checklist

- [ ] `frame.hpp`: added `base_sample_hour` field + `mode_c_enabled` field
      (or equivalent), modified `sample_hour_for_block`, extended
      `make_frame` declaration
- [ ] `frame.cpp`: `make_frame` propagates the new params into Frame
- [ ] `SR_main.cpp`: `--sample_hour` CLI flag, usage docstring updated,
      `make_frame` call passes base_sh, `build_atomic_edges` uses
      `override_sample_hour = sample_hour_override ? -1 : 0`
- [ ] `luo_main.cpp`: `--sample_hour` CLI flag, usage docstring updated,
      `make_frame` call passes base_sh + mode_c, `eval_arc` and
      `eval_baseline` use `fr.sample_hour_for_block(...)` gated on
      `mode_c_enabled`
- [ ] Build succeeds with no warnings
- [ ] **Test 1 passes** (Mode A backward-compat)
- [ ] **Test 2 passes** (Mode C R1 v_max=15)
- [ ] **Test 3 passes** (Mode C R1 ETA=200 headline)
- [ ] **Test 4 passes** (Luo Mode C R2 storm)
- [ ] **Test 5 passes** (Baseline Mode C R2 storm)
- [ ] Commit message: `"Port Mode C (per-block actual weather) to C++
      dp_SR / dp_luo"` with co-author trailer

---

## Notes for the implementing agent

1. **Do not** change the SR DP / Luo DP / Bellman algorithm itself. Only
   the weather lookup path.
2. The C++ uses **`override_sample_hour = -1`** as the sentinel to mean
   "use `Frame::sample_hour_for_block(t)` per arc." The build code at
   `atomic_edges.cpp:28-30` already handles this branch correctly — you
   only need to flip the sentinel from `0` to `-1` in `SR_main.cpp` /
   `luo_main.cpp` when Mode C is active.
3. The Luo DP path goes through `eval_arc` (Edit 4d), **not** through
   `build_atomic_edges`. Don't forget Edit 4d/4e or Luo will silently keep
   reading sh=0 even when SR is Mode-C-aware.
4. The Baseline path in `dp_luo --baseline` goes through `eval_baseline`
   (Edit 4e) — separate weather lookup, easy to miss.
5. If `sample_hour_for_block` is hot-pathed and you're worried about
   per-arc branch cost, hoist `mode_c_enabled` once outside the inner
   loop — but the compiler will inline a member-bool read trivially.
6. After porting, re-run the Python `run_eta_sweep.py` matrix in C++ for
   the same 9 voyages. Expected ~5-10× wall-time speedup (Python 102 min
   → C++ ~10-20 min). Save side-by-side comparison to
   `pipeline/dp_cpp/reference_runs/mode_c_parity_2026_05_XX.md`.

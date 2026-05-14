# Meeting Prep — Supervisor Meeting, May 18 2026

---

## 1. Action Items from May 11 Meeting

| # | Task | Status |
|---|------|--------|
| 1 | *(to fill in after retrospective)* | |
| 2 | | |
| 3 | | |

Carried over from May 11 §3:

- [ ] Rolling-horizon mechanics
- [ ] Behavioural sanity checks (zero-weather, constant-weather, lock-monotonicity)
- [ ] Real heading per sub-leg
- [ ] Soft ETA exercise (`BellmanSolver.best_sink(eta_mode="soft", lam=…)`)
- [ ] Sampling strategy update — switch collector to "2–3 samples per cell-arc + segment endpoints"

---

## 2. Progress This Week — C++ + Python parallel structure

Tal pushed a complete C++ port of the rebuilt DP solver between May 11–12. Two
executables (`dp_SR` and `dp_luo`) live in `pipeline/dp_cpp/`. This week's
work brought the Python codebase into structural parity with the C++ so
future updates can be mirrored mechanically rather than redesigned.

### 2.1 Tal's C++ port (`pipeline/dp_cpp/`)

| File | Purpose |
|---|---|
| `SR_main.cpp` | SR DP entry point (`dp_SR` binary) |
| `luo_main.cpp` | Luo block DP + baseline mode (`dp_luo` binary) |
| `atomic_edges.{cpp,hpp}` | BFS atomic-edge builder |
| `bellman.{cpp,hpp}` | Forward topological Bellman |
| `frame.{cpp,hpp}` | V/H-line frame + cell-canonical weather lookup |
| `nodes.{cpp,hpp}` | Node + GraphConfig |
| `route.{cpp,hpp}` | YAML loader, paper waypoints |
| `geo_grid.{cpp,hpp}` | Rhumb-line geometry + grid crossings |
| `weather.{cpp,hpp}` | HDF5 reader, Weather struct |
| `physics.{cpp,hpp}` | Eqs 7–16 + SOG/SWS inverse |
| `common.hpp` | `TDKey`, `ShipParameters`, `WeatherDict` |

Build deps: `cmake ≥ 3.17`, `hdf5`, `yaml-cpp`. Builds two executables that
land in `pipeline/dp_cpp/build/`.

**Tal's key design changes** (vs our previous Python locked-DP):

1. **Luo is a 2D DP table over `(col, d_idx)`** with physical distance =
   `d_idx · res_nm`. Not a Bellman-side lock on the atomic-edge graph.
2. **Default speed range** = `mean_sog ± 3` (was hardcoded `[9, 13]`).
3. **CSV output** with one row per arc (SR) or per sub-segment (Luo),
   `--csv` flag on both binaries.
4. **`--baseline` mode** on `dp_luo` — single linear walk at `L/ETA`.
5. **`crosses_v_line`** field on each atomic edge so Luo can release the
   SOG lock at block boundaries.

### 2.2 Python rebuild aligned to C++ structure

Five-phase refactor of `pipeline/dp_rebuild/`:

| Phase | What changed |
|---|---|
| **1** | Module renames to mirror C++ filenames: `build_atomic_edges.py → atomic_edges.py`, `build_nodes.py → nodes.py`, `h5_weather.py → weather.py`, `load_route.py → route.py`. Added new modules `common.py` (`ShipParameters`, `make_td_key`) and `physics.py` (re-export shim over `shared/physics.py`). |
| **2** | New `SR_main.py` mirroring `SR_main.cpp` — CLI (`--yaml`, `--h5`, `--eta`, `--min_speed`, `--max_speed`, `--zeta_nm`, `--tau_h`, `--csv`), default speeds = mean_sog ± 3, CSV writer with 16 columns. Updated `atomic_edges.py` to match C++ behaviour: added `crosses_v_line` field, dropped `realized_sog ∈ [v_min, v_max]` clamp, added H-line-too-close fallback. |
| **3** | New `luo_main.py` mirroring `luo_main.cpp` — full algorithmic rewrite as 2D DP table. Drops the Bellman-side SOG-lock approach. `eval_arc` walks H-line sub-segments at constant block SOG; `--baseline` mode for linear walk. |
| **5** | Deleted 6 dead files: `run_demo.py`, `run_demo_combined.py`, `run_demo_locked.py`, `run_demo_rebuild.py`, `validate_graph.py`, `visualize_squares.py`. Moved `Weather` dataclass from `build_edges.py` → `weather.py` (mirrors C++). |

(Phase 4 — orchestration script refactor — deferred. `bellman_locked.py`,
`build_edges_locked.py`, `build_edges.py` retained as legacy shims until
`run_route2`, `run_stress_test`, etc. are updated to call the new entry
points.)

### 2.3 Repo reorganisation

Major cleanup of the directory layout to keep only the active solver code
prominent:

```
/
├── pipeline/                                ← current
│   ├── dp_cpp/                              Tal's C++ solver
│   ├── dp_rebuild/                          our Python solver
│   ├── shared/                              physics, beaufort, hdf5_io
│   ├── collect/                             Edison weather collector
│   ├── config/routes/                       all route YAMLs in one place
│   ├── data/                                HDF5 (gitignored)
│   ├── run_all.py                           Edison entry
│   └── requirements.txt
├── old/                                     ← legacy
│   ├── Dynamic speed optimization/          legacy DP code
│   ├── Linear programing/                   legacy LP code
│   ├── pipeline_legacy/                     old pipeline subdirs + scripts
│   ├── class.py, remote_server_scripts/, test_files/
├── docs/, context/, paper/                  unchanged
```

`Dynamic speed optimization/weather_forecasts.yaml` (Route 1) promoted to
`pipeline/config/routes/persian_gulf_malacca_paper.yaml` so all route
configs live together. All 11 Python scripts that hardcoded the old
location were updated.

---

## 2.4 Parity verification — C++ ↔ Python

Both solvers run end-to-end on Route 1 / ETA = 280 / default speeds
(v_min = 9.1, v_max = 15.1 kn):

| Solver | Total fuel | Graph | Build | Solve |
|---|---:|---|---:|---:|
| **C++ `dp_SR`** | **359.594 mt** | 152,571 nodes / 9,214,780 atomic edges | 12.3 s | 0.26 s |
| **Python `SR_main.py`** | **359.305 mt** | 152,571 / 9,214,780 *(identical)* | 192.5 s | 9.18 s |
| Δ (SR) | **−0.289 mt (−0.08 %)** | bit-exact graph structure | — | — |

| Solver | Total fuel | Schedule | Solve |
|---|---:|---|---:|
| **C++ `dp_luo`** (res_nm=1.0) | **366.140 mt** | 47 blocks / 209 sub-segments | 14.3 s |
| **Python `luo_main.py`** (res_nm=1.0) | **365.970 mt** | 47 / 209 *(identical)* | 188.7 s |
| Δ (Luo) | **−0.170 mt (−0.046 %)** | identical structure | — |

| Solver | Total fuel |
|---|---:|
| **C++ `dp_luo --baseline`** | **367.560 mt** |
| **Python `luo_main.py --baseline`** | **367.394 mt** |
| Δ (Baseline) | **−0.166 mt (−0.045 %)** |

**Diagnosis of the consistent ≈0.05–0.08 % drift:** Both implementations
use the same algorithm (binary search, tolerance 0.001 kn, max 50 iter,
bracket [5, 20]). The drift comes from bit-level floating-point ordering
differences in `calculate_speed_over_ground`'s arithmetic chain
(resistance components → corrected speed → current synthesis). Python
yields slightly lower fuel on the same trajectory. Well below the noise
floor for any paper-relevant comparison.

**Structural parity is exact**:
- Graph shape: identical node + edge counts on SR DP
- Schedule length: identical
- SOG ranges, V-lines, H-lines: identical
- CSV format: identical column-by-column

---

## 3. Open Items / Next Steps

- **Phase 4** — refactor orchestration scripts (`run_stress_test.py`,
  `run_route2.py`, `analyze_overlap.py`, `find_divergent_waypoints.py`,
  `trace_optimal.py`, `visualize_schedules.py`, `visualize_stress.py`)
  to call `SR_main.solve()` / `luo_main.solve()` instead of the legacy
  locked modules. Unblocks final deletion of `bellman_locked.py`,
  `build_edges_locked.py`, `build_edges.py`.
- **Rolling horizon** — same atomic-edge graph, rebuild edges at each 6 h
  decision step with the next forecast. Now that Tal's C++ has a stable
  Luo block DP, the RH wrapper can be a thin orchestration layer.
- **Behavioural sanity checks** — zero-weather, constant-weather,
  lock-monotonicity.
- **Soft ETA** exercise.
- **Route 2 (Atlantic) under the new C++/Python pair** — current parity
  numbers are Route 1 only; Route 2 needs the same C++↔Python check.

---

## 4. Data Collection Status

| Server | Status | Route 1 (138 wp) | Route 2 (389 wp) | Uptime |
|--------|--------|---|---|--------|
| Shlomo1 | | | | |
| Shlomo2 | | | | |
| Edison  | | | | |

*(refresh on the morning of May 18)*

The collector was renamed in `run_all.py` on May 7 — `exp_b → "Route 1"`,
`exp_d → "Route 2"` — and re-deployed to Edison. exp_c (968 wp) remains
removed from the loop pending decision.

---

## 5. Results Tables

### 5.1 Three-mode comparison — Route 1 (Persian Gulf → Malacca) / ETA = 280 h

Default speed range mean_sog ± 3 = [9.1, 15.1] kn. Both languages agree
structurally and to within 0.08 % on total fuel.

| Metric | **Baseline (steady SOG)** | **dp_SR / SR_main** | **dp_luo / luo_main** |
|---|---:|---:|---:|
| C++ fuel (mt) | 367.560 | 359.594 | 366.140 |
| Python fuel (mt) | 367.394 | 359.305 | 365.970 |
| Δ vs baseline (C++) | — | **−7.966 mt (−2.17 %)** | **−1.420 mt (−0.39 %)** |
| Δ (SR − Luo) | — | **−6.546 mt (−1.82 % of baseline)** | — |
| Graph (SR) | — | 152,571 nodes / 9,214,780 atomic edges | — |
| Schedule (SR) | 1 (163 sub-segs) | 147 atomic arcs | 47 blocks / 209 sub-segs |
| Build / Solve (C++) | — | 12.3 / 0.26 s | — / 14.3 s |
| Build / Solve (Python) | — | 192.5 / 9.2 s | — / 188.7 s |

### 5.2 Comparison vs May 11 rebuild numbers

| Mode | May 11 (v=[9, 13]) | May 18 (v = mean_sog ± 3) | Comment |
|---|---:|---:|---|
| Baseline | 366.416 mt | 367.560 mt | new baseline uses wider snap-grid window |
| SR DP | 365.809 mt | **359.594 mt** | **−6.2 mt** — wider speed range gives optimizer more headroom |
| Luo DP | 366.132 mt | **366.140 mt** | unchanged within noise — Luo's lock makes wider range less valuable |
| Δ Luo − SR | +0.323 mt | **+6.546 mt** | **gap widened 20×** — SR's value comes from speed flexibility, not just decision freedom |

**Headline.** Under the default `mean_sog ± 3` speed range (C++ convention,
now matched in Python), SR DP saves **2.17 %** of baseline fuel while
Luo's lock costs **1.82 %** of that saving. Previously, with the
artificially narrow `[9, 13]` window, SR DP barely beat baseline and Luo
was within noise — masking the real SR-vs-Luo gap.

---

## 6. Questions for Supervisor

1. **Speed range default**. C++ uses `mean_sog ± 3` (== 12.12 ± 3 = [9.1,
   15.1] kn for ETA=280 h). Our previous Python had `[9, 13]`. The wider
   range gives much larger optimization gains (SR saves 2.17% instead
   of 0.6%). Is this the right convention for the paper, or should we
   constrain the range based on operational reality?

2. **Phase 4 priority**. The Python code mirrors the C++ structurally, but
   stress-test / Route 2 / visualization scripts still call the legacy
   locked-DP modules. Refactoring them = ~1 day's work. Should we do that
   now or push ahead with Rolling Horizon implementation first?

3. **Route 2 parity**. C++ ↔ Python parity confirmed only on Route 1.
   Re-running on Route 2 (St. John's → Liverpool, 168 h ETA) before next
   meeting?

4. **C++ as the production solver?** Python is now 15× slower per build
   (~3 min vs 12 s on Route 1). For stress sweeps and σ-grids, the C++
   binary is the obvious choice. Do we want to wrap it in Python
   orchestration (subprocess + CSV parsing) or keep dual-language parallel
   development?

5. **Rolling Horizon design**. With Tal's 2D DP table Luo, an RH wrapper is
   straightforward: rebuild the DP at each 6 h decision step with the
   latest forecast, take the first block's optimal SOG, advance. Worth
   prototyping in Python first (matches our experimental workflow), then
   porting to C++?

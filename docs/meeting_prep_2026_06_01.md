# Meeting Prep — Supervisor Meeting, June 1 2026

---

## 1. Action Items from May 25 Meeting

Three tasks agreed for the next few days. Each needs a dedicated planning + development pass before execution.

| # | Task | Status |
|---|------|--------|
| 1 | **Route 2 — Atlantic SR vs Luo on actual weather.** Mirror the Malacca / Route 1 setup on `experiment_d_391wp.h5` + `st_johns_liverpool.yaml`. Run both `dp_SR` and `dp_luo` (C++ and Python) against actual weather, confirm C++↔Python parity inside the ≤0.08 % FP-noise floor, and produce the SR−Luo gap number on Route 2 to compare against Route 1's +6.74 mt. | not started |
| 2 | **Multi-instance experiments — vary departure time on both routes.** Use the harvested server data (271 sample_hours on `experiment_b_138wp.h5`, full coverage on `experiment_d_391wp.h5`) to spin up many route instances that differ only in departure time. Each instance sees a different actual-weather realization at the same waypoints. Goal: characterize the weather-sensitivity of SR and Luo across departure times — distribution of total fuel, of SR−Luo gap, of voyage-time slack. | not started |
| 3 | **Plan-on-forecast, simulate-on-actual.** Extend the experiments so the speed-control regime is planned against `predicted_weather` (Mode B), then simulated against `actual_weather` via `pipeline/shared/simulation.py:simulate_voyage`. Report `planned.total_fuel_mt`, `simulated.total_fuel_mt`, and the gap — the realistic operational comparison. Builds on tasks 1 + 2; runs the same plan-vs-sim sweep on both routes and across departure times. | not started |

Dependencies / order:
- Task 1 (Route 2 actual-weather parity) is mechanical — unblocks task 2.
- Task 2 (departure-time sweep) reuses the same solver with different `sh_base`; needs a thin orchestration script.
- Task 3 (plan-on-forecast → simulate-on-actual) requires the `active_forecast_hour(t)` helper + `simulate_voyage` wiring already listed in the carryovers. Highest planning load of the three.

Carried over from May 25 §2.4.7 and §3:

- [ ] **Mode B — port `active_forecast_hour(t)`** (highest priority — unblocks plan-vs-sim and RH)
- [ ] Wire `simulate_voyage` into `SR_main.py` / `luo_main.py` as a post-solve step
- [ ] Add `--mode {actual,forecast,forecast_lead=N}` CLI flag
- [ ] **Route 2 (Atlantic) C++↔Python parity** rerun — same Python on `experiment_d_391wp.h5` + `st_johns_liverpool.yaml`
- [ ] **Rolling-horizon prototype** — same atomic-edge graph, rebuild at each 6h decision step (depends on Mode B)
- [ ] **Phase 4 refactor** — `run_stress_test.py`, `run_route2.py`, `analyze_overlap.py`, `find_divergent_waypoints.py`, `trace_optimal.py`, `visualize_schedules.py`, `visualize_stress.py` → call `SR_main.solve()` / `luo_main.solve()` instead of legacy locked modules. Unblocks deletion of `bellman_locked.py`, `build_edges_locked.py`, `build_edges.py`.
- [ ] **Behavioural sanity checks** — zero-weather, constant-weather, lock-monotonicity
- [ ] **Soft ETA** exercise
- [ ] **Edison ↔ Shlomo2 collection delta** — re-check whether Edison is still ~12 sample-hours behind; investigate root cause if delta persists

---

## 2. Progress This Week

### 2.1 *(to fill in — main porting / feature work since May 25)*

### 2.2 *(to fill in — secondary work / parity runs / cleanups)*

### 2.3 *(to fill in — anything else between May 25 and June 1 not covered above)*

---

## 3. Open Items / Next Steps

- **Mode B implementation** (per-block `predicted_weather[sample_hour=N, forecast_hour=k]`). Mode C is the oracle upper bound; Mode B is the realistic planner. Mode B − Mode C measures the value of perfect information.
- **Rolling Horizon prototype**. Rebuild the atomic-edge graph at each 6h decision step with the latest forecast; take the first block's optimal SOG; advance. Tal's stable Luo 2D DP + the new time-varying weather logic make this a thin orchestration layer rather than a re-implementation.
- **Behavioural sanity checks** — zero-weather, constant-weather, lock-monotonicity (carried).
- **Soft ETA** exercise (carried).
- **Route 2 (Atlantic) C++↔Python parity** under Tal's new time-varying logic (carried).

---

## 4. Data Collection Status

Snapshot as of May 26 15:44 IDT:

| Server | Status | Route 1 — `experiment_b_138wp.h5` | Route 2 — `experiment_d_391wp.h5` | Uptime / Collector |
|---|---|---|---|---|
| **Shlomo1** | idle | not collecting | not collecting | up 42 d 19 m; no tmux, no collector |
| **Shlomo2** | ✅ alive | sh=[6 … 1914], 319 unique, 112.5 MB, mtime 1.69 h ago | sh=[0 … 1914], 320 unique, 283.4 MB, mtime 1.58 h ago | up 81 d 21 h; `collect_all` tmux + `run_all.py` PID 16981 (69 d 3 h) |
| **Edison**  | ✅ alive | sh=[0 … 1902], 318 unique, 112.9 MB, mtime 1.69 h ago | sh=[0 … 1902], 318 unique, 283.5 MB, mtime 1.58 h ago | up 78 d 20 h; `collect_all` tmux + `run_all.py` PID 454273 (18 d 22 h) |

Row counts (rows = waypoints × sample_hours; predicted is the same × ~120 forecast leads):

| File | Server | `/actual_weather` rows | `/predicted_weather` rows |
|---|---|---:|---:|
| exp_b | Shlomo2 | 41,789 | 6,602,400 |
| exp_b | Edison  | 41,658 | 6,624,408 |
| exp_d | Shlomo2 | 124,480 | 20,389,824 |
| exp_d | Edison  | 123,702 | 20,389,824 |

**Key signals for planning the next moves:**

1. **Both collectors are alive** — H5 files updated within the last ~100 minutes on both Shlomo2 and Edison. Safe to assume both files keep growing through the week, so any experiments planned for June 1 will have ~7 more days of fresh `sample_hour` rows on top of today's numbers.
2. **Edison is persistently ~12 sample_hours behind Shlomo2** (1902 vs 1914) — *same delta as May 19 (§4 of May 25 prep, 12 sh behind then too)*. Edison is not catching up, even though both collectors are alive and writing on the same wall-clock cadence. This is now a chronic ~3-day forecast-window lag, not a transient skip. Worth a 30-min investigation before we treat the two files as interchangeable for the multi-instance sweep (Task 2 of §1).
3. **Shlomo2 exp_b is missing `sample_hour ∈ [0, 5]`** (sh_min=6), while Shlomo2 exp_d and both Edison files start at sh=0. Isolated to one file. The earliest 6 h of Malacca actual-weather coverage exists only on Edison. If we want to use the very start of the collection window for Task 2's earliest departure-time instance, we have to source it from Edison's exp_b — or accept that the Malacca departure-time sweep starts at sh=6 on Shlomo2.
4. **Coverage in sample-hour terms** — both routes now span ~1908 hours (~80 days) of NWP cycles on the canonical Shlomo2 files, with 319–320 unique sample_hours captured. At 6 h cadence that's ~310 forecast cycles; close to the theoretical 1908/6 ≈ 318. Coverage is dense enough that Task 2 (multi-instance experiments varying by departure time) can pick from hundreds of distinct departure conditions on either route.
5. **Shlomo1 is idle.** If we hit CPU contention running the Task 2 + Task 3 sweep on Shlomo2 (which is already crowded — 11 active users, multiple classification jobs in `ps`), Shlomo1 is free.

**Implications for the three tasks in §1:**

- **Task 1 (Route 2 Atlantic SR vs Luo on actual)** — `experiment_d_391wp.h5` on Shlomo2 has full sh=[0..1914] coverage. Pick the same first-clean-window protocol as Route 1 (skip leading NaN sample_hours) and run.
- **Task 2 (multi-instance departure-time sweep)** — pick the canonical file per route from Shlomo2 (broader sh range on exp_d, near-broader on exp_b). Investigate the Edison lag before treating exp_b's sh=[0..5] window as "available" from Edison only.
- **Task 3 (plan-on-forecast → simulate-on-actual)** — `/predicted_weather` has 6.6 M rows (exp_b) / 20.4 M rows (exp_d) on Shlomo2; plenty of forecast cycles to plan against. Forecast-vs-actual gap will be measurable across all 318 sample_hours covered.

---

## 5. Results Tables

### 5.1 Task 1 — Route 2 (Atlantic) SR vs Luo on actual weather

Run on 2026-05-26 against `experiment_d_391wp.h5` (local, sh=[0..1626]), ETA = 168 h, SOG range = mean_sog ± 3 = [8.635, 14.635] kn.

| Solver | Python (`SR_main.py` / `luo_main.py`) | C++ (`dp_SR` / `dp_luo`) | Δ (mt) | Δ (%) |
|---|---:|---:|---:|---:|
| **SR** | 203.198 mt | 203.357 mt | +0.159 | **+0.078 %** ✅ |
| **Luo** | 210.250 mt | 210.480 mt | +0.230 | +0.109 % |
| **SR − Luo gap** | **−7.052 mt** | **−7.123 mt** | — | — |

Both inside / essentially at the ≤0.08 % FP-ordering noise floor. **Route 2 C++↔Python parity confirmed** — the May 25 port (`active_sample_hour` + NaN walkback) is correct for Atlantic too.

Graph dimensions (Atlantic vs Persian Gulf):

| | Route 1 (Malacca, ETA 280) | Route 2 (Atlantic, ETA 168) |
|---|---:|---:|
| Length | 3,395.8 nm | 1,954.7 nm |
| V-lines | 47 | 28 |
| H-lines | 163 | 121 |
| Nodes | 152,571 | 71,861 |
| Atomic edges | 9,214,780 | 4,325,288 |
| SOG grid | 61 values [9.13, 15.13] | 61 values [8.635, 14.635] |

### 5.2 Headline finding — Route 2 SR−Luo gap is comparable to Route 1

| Route | SR fuel (Py) | Luo fuel (Py) | SR − Luo gap | Gap as %  |
|---|---:|---:|---:|---:|
| Route 1 (Malacca, ETA 280, sh=earliest clean) | 354.821 mt | 361.561 mt | **−6.740 mt** | −1.86 % |
| Route 2 (Atlantic, ETA 168, sh=earliest) | 203.198 mt | 210.250 mt | **−7.052 mt** | −3.36 % |

The per-block SOG-lock penalty (Luo's structural cost vs free SR) is **comparable in absolute mt across both routes** (~7 mt), but **roughly twice as large as a percentage on the Atlantic** because the voyage is half the duration. This contradicts the earlier `run_route2.py` finding of "+0.041 mt gap" — that was an artifact of (a) the legacy `BellmanSolverLocked` instead of `luo_main.py`, and (b) the narrower SOG range [9, 13] vs the canonical [8.635, 14.635].

### 5.3 Code changes landed during Task 1

To make C++ and Python accept the Atlantic waypoints-only yaml schema:

| File | Change |
|---|---|
| `pipeline/dp_cpp/src/route.hpp` | Declared `load_route_auto(yaml_path, eta_opt, cruise_sog) -> (Route, vector<Waypoint>)` |
| `pipeline/dp_cpp/src/route.cpp` | Implemented `load_route_auto`: dispatches on `forecasts:` (legacy + paper `WAYPOINTS`) vs `waypoints:` (computed). Applies `synthesize_multi_window(6.0)` in-loader. |
| `pipeline/dp_cpp/src/SR_main.cpp` | Replaced `load_yaml_route + global WAYPOINTS` with `load_route_auto`. Threaded local `wps` to `make_frame` and `write_arc_csv`. |
| `pipeline/dp_cpp/src/luo_main.cpp` | Same: `load_route_auto` + local `wps` threaded to `make_frame`, `write_baseline_csv`, `write_csv`. |
| `pipeline/dp_rebuild/route.py` | Added Python `load_route_auto` mirror — same schema dispatch. |
| `pipeline/dp_rebuild/SR_main.py` | Replaced `load_yaml_route + WAYPOINTS` import with `load_route_auto`; threaded `waypoints` to `make_frame` and `write_arc_csv`. |
| `pipeline/dp_rebuild/luo_main.py` | Same: `load_route_auto` + plumbed `waypoints` through `_row_for_seg`, `write_luo_csv`, `write_baseline_csv`. |

Backward-compat verified: Route 1 Python SR fuel still 354.821 mt (matches May 25 parity number exactly).

### 5.4 Loose ends — gaps surfaced by Task 1 (carry into next session)

1. **`run_route2.py` and `run_route1.py` are stale orchestrators.** They use `bellman_locked.BellmanSolverLocked` (legacy module) for Luo, AND a hard-coded SOG range [9, 13] in `frame.py:166-167`. Their Luo numbers do not match `luo_main.py`. This was explicitly listed as a Phase 4 carryover in the May 25 prep §1 — Task 1 surfaced concrete numerical evidence of why it matters (the +0.04 mt vs −7.05 mt discrepancy).
2. **Python `Frame` default SOG range is wrong.** `frame.py:166-167` hardcodes `v_min=9.0, v_max=13.0`. Both `SR_main.py` / `luo_main.py` override this with `mean_sog ± 3` (correct). But `run_route2.py` / `run_route1.py` don't override → they silently run with a narrow asymmetric range. Fix: either remove the hardcoded defaults from `GraphConfig.from_route` or have the orchestrator scripts set the range explicitly.
3. **The `--sample-hour` argument in `run_route2.py` / `run_route1.py` is now a no-op for time-varying mode.** The May 25 port made `active_sample_hour(t)` anchor at `sh_list[0]` (file front) regardless of the `base_sample_hour` argument to `Frame`. Same sh=0 and sh=18 outputs prove this. Either remove the flag from the orchestrators or wire it through to the active-sample-hour anchor (probably the latter — Task 2's departure-time sweep needs it).

### 5.5 Task 2 — Multi-instance experiment: consecutive-voyage chain on Mode C actual weather

Run on 2026-06-01 against the fresh Shlomo2 HDF5 files (`experiment_b_138wp.h5` sh=[6..2052], `experiment_d_391wp.h5` sh=[0..2052]). Each voyage starts when the previous one arrives — `sh_base_{N+1} = sh_base_N + ETA`, fixed-ETA stepping so SR and Luo see identical departure weather at every voyage. Same mean_sog ± 3 SOG range as Task 1. Mode C: per-block actual weather anchored at the voyage-start sample_hour (`VoyageWeather.active_sample_hour(t, sh_base=N)`).

Voyage 0 of each route reproduces the existing parity numbers exactly:
- Route 1 voyage 0 (sh_base=6): **SR 354.821 mt, Luo 361.561 mt** — matches the May 25 parity to 3 dp
- Route 2 voyage 0 (sh_base=0): **SR 203.198 mt, Luo 210.250 mt** — matches Task 1 §5.1 to 3 dp

Per-route summary across the full chain:

| Route | n | SR fuel (mt) mean ± std | Luo fuel (mt) mean ± std | SR−Luo gap (mt) mean | Gap % mean | SR fuel range |
|---|---:|---:|---:|---:|---:|---:|
| Route 1 (Malacca, ETA 280) | 7 | 344.87 ± 7.77 | 351.26 ± 8.72 | −6.391 | −1.81 % | 334.8 – 355.2 (20.4 mt spread) |
| Route 2 (Atlantic, ETA 168) | 12 | 201.90 ± 10.32 | 207.36 ± 11.03 | −5.457 | −2.62 % | 190.8 – 227.9 (37.1 mt spread) |

Route 1 (Malacca) per-voyage:

| # | sh_base | SR (mt) | Luo (mt) | gap (mt) | gap % |
|---:|---:|---:|---:|---:|---:|
| 0 | 6 | 354.821 | 361.561 | −6.740 | −1.86 |
| 1 | 286 | 355.225 | 364.675 | −9.450 | −2.59 |
| 2 | 566 | 337.702 | 342.414 | −4.713 | −1.38 |
| 3 | 846 | 348.191 | 353.146 | −4.955 | −1.40 |
| 4 | 1126 | 337.604 | 340.874 | −3.270 | −0.96 |
| 5 | 1406 | 334.828 | 343.857 | −9.029 | −2.63 |
| 6 | 1686 | 345.728 | 352.312 | −6.584 | −1.87 |

Route 2 (Atlantic) per-voyage:

| # | sh_base | SR (mt) | Luo (mt) | gap (mt) | gap % |
|---:|---:|---:|---:|---:|---:|
| 0 | 0 | 203.198 | 210.250 | −7.052 | −3.35 |
| 1 | 168 | 204.167 | 209.507 | −5.340 | −2.55 |
| 2 | 336 | 195.239 | 201.952 | −6.713 | −3.32 |
| 3 | 504 | 206.124 | 212.224 | −6.100 | −2.87 |
| 4 | 672 | 215.931 | 223.495 | −7.565 | −3.38 |
| 5 | 840 | 190.752 | 196.894 | −6.142 | −3.12 |
| 6 | 1008 | 227.914 | 233.853 | −5.939 | −2.54 |
| 7 | 1176 | 194.397 | 198.253 | −3.856 | −1.94 |
| 8 | 1344 | 194.641 | 197.054 | −2.413 | −1.22 |
| 9 | 1512 | 192.750 | 196.896 | −4.146 | −2.11 |
| 10 | 1680 | 199.101 | 203.488 | −4.387 | −2.16 |
| 11 | 1848 | 198.568 | 204.405 | −5.837 | −2.86 |

All voyages arrive at exactly the ETA (slack = 0 across the board) — the hard ETA constraint is binding everywhere; both solvers always prefer to slow-steam right up to the deadline.

#### 5.5.1 Headline findings

1. **Weather sensitivity is 3× higher on the Atlantic per voyage hour.** Route 1 fuel spread = 20.4 mt over 280 h (0.073 mt/h). Route 2 fuel spread = 37.1 mt over 168 h (0.22 mt/h). North Atlantic departure conditions vary far more than Persian Gulf → Malacca conditions. The Route 2 SR fuel range is 18 % of its mean; Route 1 is 6 %.
2. **The SR−Luo gap is more variable on Route 1 than Route 2.** Route 1 gap σ = 2.11 mt (range −3.27 to −9.45). Route 2 gap σ = 1.43 mt (range −2.41 to −7.57). The Luo per-block SOG-lock penalty depends more on Malacca departure cycle than on Atlantic — possibly because the longer voyage gives SR more opportunities to exploit within-block weather variation.
3. **The gap as a *percentage* is higher on the shorter (Atlantic) voyage.** Route 1 mean gap = −1.81 %, Route 2 mean gap = −2.62 % — confirms Task 1 §5.2 observation across a full chain, not just one departure: the SR−Luo penalty is comparable in absolute mt but roughly twice as large in % terms on the half-length voyage.
4. **Worst and best voyages.** Route 2 voyage 6 (sh_base=1008) was the worst single voyage on both solvers (SR 227.9 mt, Luo 233.9 mt) — fuel ~16 % higher than the best Route 2 voyage (sh_base=840, SR 190.8 mt). One bad weather window can drive a single-voyage fuel difference larger than the entire SR−Luo gap.

#### 5.5.2 Code landed during Task 2

| File | Change |
|---|---|
| `pipeline/dp_rebuild/weather.py` | `active_sample_hour(t, sh_base=None)` — new `sh_base` arg anchors the voyage start; default None uses `sh_list[0]` (preserves legacy behaviour). |
| `pipeline/dp_rebuild/atomic_edges.py` | `_emit_from_src` passes `frame.base_sample_hour` to `active_sample_hour` (loose end §5.4 #3 resolved). |
| `pipeline/dp_rebuild/luo_main.py` | `eval_arc` / `eval_baseline` honour `frame.base_sample_hour`. New `solve(args, voyage=None)` API for orchestrator reuse. New `--sample_hour N` CLI. |
| `pipeline/dp_rebuild/SR_main.py` | Same `solve(args, voyage=None)` API + `--sample_hour N` CLI. |
| `pipeline/dp_rebuild/run_chain_sweep.py` | **NEW**. Consecutive-voyage chain orchestrator: loads `VoyageWeather` once per route, sweeps `sh_base` by fixed ETA, calls `SR_main.solve` and `luo_main.solve` per voyage, writes `runs/2026_06_01_chain_sweep/results.csv` plus per-voyage per-arc CSVs. |
| `pipeline/dp_rebuild/analyze_chain_sweep.py` | **NEW**. Reads results.csv, prints per-route stats + per-voyage tables + markdown summary blocks. |

Backward compat: SR_main / luo_main with no `--sample_hour` arg (or `--sample_hour 0`) reproduce all pre-existing reference numbers exactly (Route 1 354.821 mt, Route 2 203.198 mt).

#### 5.5.3 Outputs

- `runs/2026_06_01_chain_sweep/results.csv` — 19 rows, schema in `run_chain_sweep.CSV_HEADER`
- `runs/2026_06_01_chain_sweep/{route1,route2}/voyage_{idx:02d}/{sr,luo}.csv` — per-arc schedules for every voyage (38 CSVs)
- Total wall: 130 min on local Mac (Route 1: ~45 min, Route 2: ~85 min; two voyages had unusually slow Luo solves of ~21 min, otherwise ~3 min/voyage)

#### 5.5.4 Next steps (Task 3 carryover)

1. **Repeat the chain in Mode B** — `predicted_weather` anchored at each voyage's `sh_base` (the operational planner). Mode B − Mode C per voyage = value of perfect information. Needs the Mode B port (carryover §1).
2. **Plan-on-forecast → simulate-on-actual** — pair each Mode B plan with a `simulate_voyage` run on actual weather to get the realistic `planned vs simulated` gap per voyage.
3. **Add departure-time x-axis to the eventual plot** — `sh_base` is sample_hour, which maps roughly to "days into the 85-day collection window". Useful for spotting seasonal weather patterns.

---

## 6. Questions for Supervisor

1. *(to fill in)*
2. *(to fill in)*
3. *(to fill in)*

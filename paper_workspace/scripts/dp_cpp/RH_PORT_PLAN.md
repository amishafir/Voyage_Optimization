# C++ Rolling-Horizon Port Plan

Bring `pipeline/dp_cpp/` to **full parity** with the Python `pipeline/dp_rebuild/`
so the rolling-horizon (RH) experiment runs in C++. C++ runs the same DP in
seconds — this port is the fix for the Python RH runtime blocker (single voyage
= 8.9 h in Python; the 19-voyage chain is days in Python, minutes in C++).

**Status of C++:** last synced at `752ae0b`. Python has since gained (a) the
departure-time sweep (`base_sample_hour`, Python commit `5756fc3`) and (b) the
RH work (`time_key` / `d_start` / `run_rh.py`). C++ has neither. The weather
layer already reads `predicted_weather` and `cell_weather_at(..., forecast_hour)`
works, and `cell_cache_` exists — so the forecast plumbing is present.

**Source of truth:** the Python files. Each C++ change mirrors a Python function.
- `pipeline/dp_rebuild/atomic_edges.py` → `src/atomic_edges.cpp/.hpp`
- `pipeline/dp_rebuild/luo_main.py` → `src/luo_main.cpp`
- `pipeline/dp_rebuild/SR_main.py` → `src/SR_main.cpp`
- `pipeline/dp_rebuild/frame.py` → `src/frame.cpp/.hpp`
- `pipeline/dp_rebuild/weather.py` → `src/weather.cpp/.hpp`
- `pipeline/dp_rebuild/run_rh.py` → new `src/run_rh.cpp`

**Conventions to keep:** C++ already uses `forecast_hour = -1` to mean "actual".
Reuse that sentinel for `time_key`'s forecast component (no `std::optional`
needed): `time_key(τ) -> std::pair<int,int>` = `(sample_hour, forecast_hour)`,
with `forecast_hour == -1` → actual. A default-constructed (empty)
`std::function` means "no time_key", preserving current behaviour.

---

## Phase 0 — `solve()` refactor (structural prerequisite, no behaviour change)

C++ has **only `main()`** in both `SR_main.cpp` and `luo_main.cpp`. The RH
orchestrator must call each solver ~56× in-process (reusing one `VoyageWeather`
so the cell cache stays warm). Extract a callable `solve()` from each `main()`.

**`src/SR_main.cpp`**
- Define a result struct (new `src/SR_main.hpp`):
  ```cpp
  struct SRResult {
      double total_fuel_mt, voyage_time_h;
      size_t n_nodes, n_edges;
      double build_s, solve_s;
      std::vector<AtomicEdge> schedule;
      std::vector<Waypoint>   waypoints;
      double eta_h; int sample_hour; double d_start;
  };
  struct SRArgs { std::string yaml, h5; double eta=-1, min_speed=-1, max_speed=-1,
                  zeta_nm=-1, tau_h=-1; int sample_hour=0; };
  SRResult sr_solve(const SRArgs&, const VoyageWeather* voyage=nullptr,
                    bool verbose=true, const TimeKey& time_key={}, double d_start=0.0);
  ```
- Move the body of `main()` (lines ~113–156: load route/weather, build frame,
  `build_atomic_edges`, `BellmanSolver`, summary) into `sr_solve`. `main()`
  becomes: parse args → `sr_solve` → optional CSV.
- Allow `voyage` to be passed in (skip reload) — mirror Python `solve(voyage=...)`.

**`src/luo_main.cpp`**
- Same pattern: `LuoResult { total_fuel_mt, voyage_time_h, n_blocks, solve_s,
  path_arcs, baseline_segs, waypoints, eta_h, sample_hour, d_start }`, `LuoArgs`
  (adds `res_nm`, `baseline`), `luo_solve(...)`.
- Move `main()` body (lines ~311–530) into `luo_solve`.

**Validation 0:** CLI executables still produce identical numbers to before
(Route 2 Mode C: SR 203.198 / Luo 210.250). Pure refactor — no number should move.

---

## Phase 1 — departure-time sweep (`base_sample_hour` anchoring)

Mirror Python commit `5756fc3`. Lets any voyage start at an arbitrary forecast
cycle. (For Route 2 voyage 0, `sh_base=0` already anchors at `sh[0]=0`, but full
parity needs this for Route 1 and the chain sweep.)

**`src/weather.cpp/.hpp`** — `active_sample_hour`:
```cpp
int active_sample_hour(double t_voyage_h, int sh_base = -1) const;
```
`sh_base < 0` → anchor at `sample_hours_.front()` (current behaviour). Else
`base = sh_base`, `target = base + floor(t)`, bisect to largest `sh ≤ target`,
clamp. Mirror `weather.py:176`.

**`src/frame.hpp`** — add field + use in `sample_hour_for_block`:
```cpp
int base_sample_hour = 0;
int sample_hour_for_block(double t) const {
    return base_sample_hour + (int)std::round(block_start_time(t)); }
```
**`src/frame.cpp`** — `make_frame(..., int base_sample_hour = 0)`.

**`src/SR_main.cpp` / `src/luo_main.cpp`** — add `--sample_hour` arg; pass
`args.sample_hour` into `make_frame(..., base_sample_hour=sample_hour)`.

**Validation 1:** with `--sample_hour 0`, all numbers unchanged. (No reference
values for `sh_base>0` in C++ yet; parity with Python chain sweep is the check if
those numbers are available.)

---

## Phase 2 — `time_key` + `d_start` in the solvers (RH core)

### 2a. Type (new, in `src/common.hpp` or `atomic_edges.hpp`)
```cpp
#include <functional>
using TimeKey = std::function<std::pair<int,int>(double)>; // τ -> (sample_hour, forecast_hour); fh==-1 → actual
```

### 2b. `src/atomic_edges.cpp` — `emit_from_src` (mirror `atomic_edges.py:94`)
Add params `const TimeKey& time_key`, used before the weather lookup:
```cpp
int sample_hour; int fh_eff = forecast_hour;
if (time_key) { auto [sh, fh] = time_key(src_t); sample_hour = sh; fh_eff = fh; }
else if (override_sample_hour >= 0) { sample_hour = override_sample_hour; }
else if (sh_list.empty()) return {};
else { sample_hour = frame.voyage->active_sample_hour(src_t,
            frame.base_sample_hour ? frame.base_sample_hour : -1); }
Weather wx = frame.cell_weather_at(src_d, sample_hour, fh_eff);
```
NaN walkback: change guard to `if (wx.has_nan() && override_sample_hour < 0)`
(drop the `&& time_key` exclusion) and walk back using `fh_eff` (not
`forecast_hour`) — mirror the Python fix that made the gate pass.

### 2c. `src/atomic_edges.cpp` — `build_atomic_edges` (mirror `atomic_edges.py:268`)
Add params `const TimeKey& time_key = {}, double d_start = 0.0`. Changes:
- `double src_d0 = round_key(d_start);`
- source node: `intern(0.0, d_start)`, queue seed `make_td_key(0.0, d_start)`.
- `is_src = (k == make_td_key(0.0, d_start))`.
- pass `time_key` into the `emit_from_src` call.
- Update `.hpp` signature.

### 2d. `src/luo_main.cpp` — `eval_arc` (mirror `luo_main.py:120`)
Currently has NO `sample_hour`/`forecast_hour` params (computes
`active_sample_hour` internally). Add three: `int sample_hour=-1,
int forecast_hour=-1, const TimeKey& time_key={}`. In the per-piece loop:
```cpp
int cur_sh; int cur_fh = forecast_hour;
if (time_key)            { auto [sh,fh]=time_key(ta); cur_sh=sh; cur_fh=fh; }
else if (sample_hour<0)  { cur_sh = fr.voyage->active_sample_hour(ta, sh_base_arg); }
else                     { cur_sh = sample_hour; }
Weather wx = fr.cell_weather_at(da, cur_sh, cur_fh);
if (wx.has_nan() && (sample_hour < 0 || time_key)) { /* walkback using cur_fh */ }
```
Also thread `base_sample_hour` into `sh_base` (Phase 1): `sh_base =
fr.base_sample_hour ? fr.base_sample_hour : sh_list.front()`.

### 2e. `src/luo_main.cpp` — `eval_baseline` (mirror `luo_main.py:246`)
Same per-piece change + `time_key` param (API completeness; Naive uses actual).

### 2f. `src/luo_main.cpp` — `luo_solve` DP (mirror `luo_main.py` solve)
- `d_start` param → `int d_start_idx = (int)round(d_start/res_nm); dp[d_start_idx]=0.0;`
  (replaces `dp[0]=0.0`).
- mean SOG band on remaining distance: `mean_sog = (length_nm - d_start)/eta`.
- pass `time_key` into all `eval_arc` calls (DP loop, ETA block, backtrack).

### 2g. `src/SR_main.cpp` — `sr_solve`
- mean SOG band on `(length_nm - d_start)`.
- pass `time_key`, `d_start` into `build_atomic_edges`.

**Validation 2 (BACKWARD-COMPAT GATE — non-negotiable):** build a `time_key`
that mirrors Mode C — `(active_sample_hour(τ), -1)` — and confirm `sr_solve` /
`luo_solve` reproduce the **C++ Mode C values exactly: SR 203.357 / Luo 210.480**
(Route 2, sh_base=0; the C++ golden, NOT the Python 203.198/210.250 — see
Validation 3 on the cross-language drift). This proves the `time_key` path is
wired right against C++'s own behaviour. Add as `src/run_rh_smoke.cpp` or a
`--smoke` flag.

---

## Phase 3 — `run_rh.cpp` orchestrator (mirror `run_rh.py`)

New executable. Mirrors `run_rh.py` exactly:

- **Forecast index** (`load_forecast_index`): from `predicted_weather`, sorted
  issue sample_hours + `{sh: max positive lead}`. (Add a `VoyageWeather`
  accessor for predicted sample_hours, or read the H5 directly as Python does.)
- **`make_time_key(t_wall, issues, max_lead)`**: `sh_fc = latest issue ≤ t_wall`;
  `staleness = t_wall - sh_fc`; returns lambda
  `τ < 6 ? (t_wall,-1) : (sh_fc, min(staleness+6*floor(τ/6), cap))`.
- **RH loop** `k=0..ceil(eta/6)-1`: `eta_sub = eta-6k`, `blk_dur = min(6,eta_sub)`,
  `t_wall = sh_base+6k`; `sr_solve`/`luo_solve` with `time_key` + `d_start`;
  extract block-0 (SR: edges with `src_t∈[0,blk_dur)`; Luo: `path_arcs` block 0);
  accumulate fuel, advance `d`, log divergence vs prev plan's block-1.
- **Partial-final-block**: `ceil` blocks, last = remainder, `arrival = Σ blk_dur`.
- **Naive**: `luo_solve` with `baseline=true` (actual weather, no time_key).
- **Outputs** (`runs/<date>_rh/<route>/voyage_NN/`): `summary.json`,
  `rh_{sr,luo}_replans.csv`, `rh_{sr,luo}_realized.csv`. Match the Python schema
  so analysis scripts are shared.

**`CMakeLists.txt`:** add `run_rh` (and `run_rh_smoke`) executable targets
linking the same object set as `SR_main` / `luo_main` (now that `sr_solve` /
`luo_solve` are library functions, not `main`).

**Validation 3 (CROSS-LANGUAGE):** NOTE — C++ and Python Mode C already differ
by ~0.1 % (golden capture 2026-06-06): C++ SR 203.357 / Luo 210.480 / Naive
212.609 vs Python 203.198 / 210.250 / 212.467 (C++ consistently ~0.07–0.11 %
higher; a pre-existing porting nuance, not from this work). So the cross-language
gate is **qualitative + tolerance**, not exact:
- C++ RH within ~0.2 % of the Python RH numbers (204.851 / 212.439), and
- same qualitative result: RH-SR saves ~3.5 % vs Naive, RH-Luo ≈ break-even,
  all four sanity gates pass, realised in the `oracle ≤ RH ≤ Naive` sandwich
  (C++ oracle = 203.357 / 210.480).

Then run Route 1 (280h, 47 re-plans) to exercise the partial-final-block path
end-to-end — the thing Python hasn't run yet.

(Optional side-investigation: root-cause the ~0.1 % C++/Python Mode C drift. Not
a blocker — Layer A locks C++ to itself — but worth understanding before the
thesis quotes cross-language parity.)

---

## Implementation order (next session)

1. **Phase 0** — `solve()` refactor (SR + Luo). Validate CLI numbers unchanged.
2. **Phase 1** — `base_sample_hour` anchoring + `--sample_hour`. Validate sh_base=0 unchanged.
3. **Phase 2** — `TimeKey` type, `time_key` + `d_start` through emit/build/eval. Build the backward-compat gate; **must hit 203.198 / 210.250**.
4. **Phase 3** — `run_rh.cpp` + CMake targets. **Must match Python 204.851 / 212.439**, then run Route 1.
5. Commit per phase; keep CLI `main()`s behaviourally identical throughout (regression safety).

## Regression & verification — "the current setup still gives the same results"

Two independent layers guard against breaking existing (non-RH, actual-weather)
behaviour. Both must pass after every phase.

### Layer A — golden-master diff on the non-RH default path

Harness: `tests/regression.sh` (committed). Modes:

```
./tests/regression.sh capture   # run ONCE on pristine C++ (before Phase 0) → tests/golden/  (COMMIT IT)
./tests/regression.sh verify    # run after each phase → diffs vs golden/  (exit!=0 on any drift)
```

Matrix = the current setup (actual weather, no RH, default sample_hour), 6 configs:

| config | binary | route | eta |
|---|---|---|---|
| sr_route1 / sr_route2     | `dp_SR`  | Malacca / Atlantic | 280 / 168 |
| luo_route1 / luo_route2   | `dp_luo` | Malacca / Atlantic | 280 / 168 |
| naive_route1 / naive_route2 | `dp_luo --baseline` | Malacca / Atlantic | 280 / 168 |

Each config runs with `--csv` and the **full per-arc CSV is sha256-hashed** —
every arc's fuel/SWS/SOG/heading/6 weather fields — so any drift in path,
weather lookup, or physics is caught, not just the fuel total. `verify` requires
a **byte-for-byte match**; mismatch prints a `diff` and exits non-zero.

**Why exact, not tolerance:** new params are inert by default (empty `time_key`,
`override_sample_hour=-1`, `d_start=0`). When inert, `emit_from_src`/`eval_arc`
run the original statements in the original order → bit-identical FP. Phase 0
*moves* code verbatim. So a single-ULP move signals a real bug.

**Ordering imperative:** `capture` MUST run on pristine C++ before Phase 0, and
`golden/` is never regenerated after edits — it is the frozen ground truth.

### Layer B — `time_key`-identity smoke (the new path agrees with Mode C)

`src/run_rh_smoke.cpp` (or a `--smoke` flag): feed a `time_key` that mirrors
Mode C — `(active_sample_hour(τ), -1)` — and require `sr_solve`/`luo_solve` to
reproduce **203.198 / 210.250 exactly**. This is the C++ analogue of
`run_rh_smoke.py`, already green in Python.

### What each phase must pass

| Phase | Layer A (verify) | Layer B (smoke) | Cross-language |
|---|---|---|---|
| 0 solve() refactor | byte-identical | — | — |
| 1 base_sample_hour | byte-identical (`--sample_hour 0`) | — | — |
| 2 time_key + d_start | byte-identical (defaults inert) | C++ 203.357 / 210.480 | — |
| 3 run_rh + CMake | byte-identical | C++ 203.357 / 210.480 | ~RH 204.851 / 212.439 (±0.2%, qualitative) |

(C++ Mode C = 203.357 / 210.480, ~0.1% above Python's 203.198 / 210.250 — golden
capture 2026-06-06. The smoke checks C++ against itself; cross-language is
tolerance + qualitative. See Validation 3.)

Layer A proves the RH params are inert when off; Layer B proves they are correct
when on. The combination is the guarantee that the existing setup is unchanged.

## Risks / watch-items

- **Cache vs cold cycles**: C++ `cell_cache_` is keyed identically; reuse one
  `VoyageWeather` across all 56 solves (as `run_rh.py` does). C++ is fast enough
  that even cold cycles are cheap, but keep the single-instance pattern.
- **`forecast_hour=-1` sentinel** must thread cleanly through `time_key`,
  `cell_weather_at`, and the walkback — the one place a bug would hide.
- **`std::round` key collisions**: SR `d_start` must land on the same `EPS_KEY=9`
  rounding grid used by `make_td_key` (it will, since `d_start` comes from a prior
  block's V-line-snapped `dst_d`).
- **Backward-compat `main()`s**: do not change their default output; the existing
  Mode C / chain-sweep behaviour must survive (mirror the Python "default None
  preserves Mode C" discipline).

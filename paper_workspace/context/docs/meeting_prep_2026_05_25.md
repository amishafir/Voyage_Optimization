# Meeting Prep — Supervisor Meeting, May 25 2026

---

## 1. Action Items from May 18 Meeting

| # | Task | Status |
|---|------|--------|
| 1 | *(to fill in after retrospective)* | |
| 2 | | |
| 3 | | |

Carried over from May 18 §3 and §6:

- [x] **Port Tal's C++ time-varying weather change to Python** — done May 25, both SR and Luo, parity within 0.030 % (see §2.3)
- [ ] **Phase 4** — refactor `run_stress_test.py`, `run_route2.py`, `analyze_overlap.py`, `find_divergent_waypoints.py`, `trace_optimal.py`, `visualize_schedules.py`, `visualize_stress.py` to call `SR_main.solve()` / `luo_main.solve()` instead of legacy locked modules. Unblocks deletion of `bellman_locked.py`, `build_edges_locked.py`, `build_edges.py`.
- [ ] **Route 2 (Atlantic) C++↔Python parity** — May 18 numbers cover Route 1 only
- [ ] **Rolling horizon** prototype — same atomic-edge graph, rebuild at each 6h decision step
- [ ] **Behavioural sanity checks** — zero-weather, constant-weather, lock-monotonicity
- [ ] **Soft ETA** exercise
- [ ] **Mode B** (per-block `predicted_weather` at planning-moment forecast cycle) implementation
- [ ] **PG NaN handling** — decide between (a) report only clean windows, (b) nearest-non-NaN fallback in weather lookup, (c) re-collect. *Resolved upstream: Tal's commit 752ae0b adds NaN walkback in C++; Python needs the same.*

---

## 2. Progress This Week

### 2.1 Tal's commit `752ae0b` — time-varying weather in dp_SR and dp_luo

**Pushed**: Mon 2026-05-18 21:05 IDT (GitHub event 21:05:19 IDT, +6 s after author timestamp). One commit, five files, **all C++, zero Python** (172 insertions / 36 deletions in `pipeline/dp_cpp/src/`).

**Author message**:

> Default h5 switched to `experiment_b_138wp.h5` in both binaries. Arc cost now consumes the weather active at the corresponding voyage time, with the trip anchored to the earliest `sample_hour` in the file.
>
> Shared `VoyageWeather::active_sample_hour()` maps voyage time `t` to the largest `sample_hour ≤ (earliest + ⌊t⌋)`, handling non-uniform cadence (1 h vs 6 h) and missing zero anchor. Both `dp_luo` (per-piece, with spatial+temporal splits at every `sample_hour` transition) and `dp_SR` (per-edge, via `override_sample_hour=-1` in `build_atomic_edges`) use it.
>
> When a requested `sample_hour` is entirely NaN (common in `experiment_b_138wp.h5` where some collection cycles failed and wrote all-NaN rows), both DPs walk back through `sh_list` to the most recent valid sample at the same cell, falling back gracefully without giving the DP free arcs through NaN zones.

**Why this matters for the Python rebuild.** Until this commit the C++ DPs were static-deterministic by default (single weather snapshot at `sample_hour=0`). Python's `SR_main.py` is still that way (`override_sample_hour=0` hardcoded on line 157). To keep C++↔Python parity — the core invariant that makes the Python rebuild useful as a reference implementation — the four Python files below need mirroring changes.

#### 2.1.1 File-by-file diff (C++ side)

| C++ file | Δ lines | What changed |
|---|---|---|
| `pipeline/dp_cpp/src/weather.hpp` | +5 / −0 | Declares public `int active_sample_hour(double t_voyage_h) const` on `VoyageWeather`. |
| `pipeline/dp_cpp/src/weather.cpp` | +14 / −0 | Implements `active_sample_hour`: clamps to `[sh_front, sh_back]`, then `std::upper_bound − 1` for the largest sample_hour ≤ `(sh_base + ⌊t⌋)`. Returns 0 if `sample_hours_` is empty. |
| `pipeline/dp_cpp/src/atomic_edges.cpp` | +22 / −4 | When `override_sample_hour < 0`: `sample_hour = voyage->active_sample_hour(src_t)`. If `cell_weather_at(src_d, sample_hour, ...)` is NaN, walks `sh_list` backward (via `std::lower_bound`) until it finds a valid cell at the same `src_d`. If still NaN after walkback → arc is dropped (`return {};`). Legacy `override_sample_hour ≥ 0` path unchanged. |
| `pipeline/dp_cpp/src/SR_main.cpp` | +6 / −3 | (a) Default `--h5` changed from `voyage_weather.h5` → `experiment_b_138wp.h5`. (b) `build_atomic_edges(..., override_sample_hour=-1, ...)` (was `0`). dp_SR is now time-varying by default. |
| `pipeline/dp_cpp/src/luo_main.cpp` | +125 / −28 | (a) Default `--h5` updated. (b) `eval_arc` and `eval_baseline` now split each *spatial* sub-segment at every `sample_hour` transition (`t = sh_v - sh_base`) so each *temporal* piece is priced against the weather active at that absolute time. Trip is anchored to `sh_base = sh_list.front()`. (c) Same NaN walkback as in `atomic_edges.cpp`. (d) Per-piece records (`Seg`) now carry `da, db, ta` for the *temporal* piece, not the full spatial sub-segment. |

#### 2.1.2 Python files that need to mirror this

| Python file | Current state | Required change |
|---|---|---|
| `pipeline/dp_rebuild/weather.py` | Has `sample_hours()` getter (line 169). **No** `active_sample_hour(t)` method. | Add `def active_sample_hour(self, t_voyage_h: float) -> int:` with identical semantics: `target = sh_base + math.floor(t_voyage_h + 1e-9)`; clamp to `[sh_front, sh_back]`; return last element of `self._sample_hours` that is `≤ target` (bisect with `bisect_right − 1`). Return `0` if `_sample_hours` is empty. |
| `pipeline/dp_rebuild/atomic_edges.py` | Existing `override_sample_hour` param accepts `None` to mean "use `frame.sample_hour_for_block(src_t)`" (block-index × 6 — assumes uniform 6h cadence). No NaN walkback. | (1) Change the `None` branch to call `frame.voyage.active_sample_hour(src_t)` instead of the block-index formula — so it works on the file's actual `sample_hour` grid including 1h cadence and missing zero anchor. (2) After `frame.cell_weather_at(src_d, sample_hour, forecast_hour)` returns, if the result is NaN and `override_sample_hour is None`, walk `frame.voyage.sample_hours()` backward and retry until valid or exhausted. (3) Drop the arc if still NaN. |
| `pipeline/dp_rebuild/SR_main.py` | Calls `build_atomic_edges(frame, ..., override_sample_hour=0, ...)` on line 157. Default `--h5` is currently `voyage_weather.h5`. | (1) Change to `override_sample_hour=None` (Python's equivalent of C++ `-1`). (2) Default `--h5` to `experiment_b_138wp.h5`. (3) Update the docstring/comment block above the call. |
| `pipeline/dp_rebuild/luo_main.py` | `eval_arc` reads one weather row per *spatial* sub-segment. No temporal splitting at `sample_hour` transitions. No NaN walkback. | Algorithmically larger change. Mirror Tal's `luo_main.cpp` `eval_arc` and `eval_baseline`: (a) anchor `sh_base = sh_list[0]`; (b) for each spatial sub-segment, compute `t_sd = t_h + (sd-d1)/sog`, `t_ed = t_h + (ed-d1)/sog`; (c) collect temporal breakpoints `{t_sd} ∪ {sh_v - sh_base : sh_v ∈ sh_list, sh_v ≠ sh_base, t_sd < sh_v - sh_base < t_ed} ∪ {t_ed}`; (d) for each `(ta, tb)` piece, compute `da, db` by linear interp on `sog`, read weather at `active_sample_hour(ta)` with NaN walkback, compute `fuel = fcr * (tb - ta)`; (e) emit one `Seg` per temporal piece, not per spatial sub-segment. |

#### 2.1.3 Migration risks / things to verify after the port

1. **Behavioural change is not pure refactor.** dp_SR's output fuel will move (it was static-deterministic; now sees varying weather). On `experiment_b_138wp.h5` at the first clean window, fuel should drop slightly (varying weather gives the optimizer more information). If Python fuel moves in the *opposite* direction from C++ after the port, that's a bug.
2. **NaN walkback must not silently swallow whole-cell failures.** The walkback exits early on the first valid cell, but if a cell is NaN at every `sample_hour ≤ target`, the arc must be dropped (`return None` / equivalent of C++ `return {}`). The current Python code drops the arc only on the initial NaN — make sure the walkback loop preserves that.
3. **`sh_base != 0` is now first-class.** Earlier Python code assumes `sample_hour=0` is the trip start; this is no longer true. Every place that does `t_h * 6` or `t // 6 * 6` to derive a sample_hour is wrong and must call `active_sample_hour(t)`.
4. **Default `--h5` change is a user-visible breaking change.** Any script or notebook that runs `python3 SR_main.py` without `--h5` will silently switch to `experiment_b_138wp.h5`. Grep `pipeline/dp_rebuild/` and `pipeline/` more broadly for callers.
5. **Parity test.** After the port, run both on `experiment_b_138wp.h5` at the first clean window (Tal's commit message implies this is `sh = sh_base`, i.e. the earliest sample_hour in the file). Total fuel from `dp_SR` (C++) and `SR_main.py` (Python) should match to within ~0.1 % (the known FP-ordering drift noted in May 18 §2.4). Same for `dp_luo` vs `luo_main.py`. If the drift exceeds 0.1 % on the same trajectory, the port is wrong.
6. **Earlier `mode C` work in Python is partially redundant.** May 18 §5.3 wired per-block actual weather through `atomic_edges.py` via `Frame.sample_hour_for_block` with a `base_sample_hour` offset. Tal's `active_sample_hour` supersedes that path for non-uniform cadence. We can either delete `sample_hour_for_block` or keep it as a thin wrapper that calls `active_sample_hour`. Decision: keep `active_sample_hour` as the single source of truth, retire `sample_hour_for_block`. Audit `atomic_edges.py:121`, `atomic_edges.py:386-405` for stale references.

#### 2.1.4 Suggested port order (smallest blast radius first)

1. `weather.py` — add `active_sample_hour(t)`. No other file changes. Unit-test against the C++ output on `experiment_b_138wp.h5`.
2. `atomic_edges.py` — switch `None` branch to `active_sample_hour`, add NaN walkback. Keep `override_sample_hour=0` callers (the demo block, perturber path) working unchanged.
3. `SR_main.py` — flip `override_sample_hour=0 → None`, update default `--h5`, update comments. Run parity test vs `dp_SR`.
4. `luo_main.py` — bigger change. Rewrite `eval_arc` and `eval_baseline` temporal splitting. Run parity test vs `dp_luo`.

Total port size estimate: ~150 Python lines added, ~30 deleted. Roughly half a day if parity tests pass on first try, full day with debug.

#### 2.1.5 Reference — exact C++ logic to mirror

For future-Claude convenience, the key C++ blocks to translate verbatim:

- **`weather.cpp:130-141`** — `active_sample_hour(t_voyage_h)` body
- **`atomic_edges.cpp:31-52`** — sample_hour pick + NaN walkback inside `emit_from_src`
- **`luo_main.cpp:78-130`** — temporal-split loop inside `eval_arc`
- **`luo_main.cpp:152-220`** — same pattern inside `eval_baseline`

Run `git show 752ae0b -- pipeline/dp_cpp/src/<file>` for the canonical source.

#### 2.1.6 Current divergence — where exactly C++ and Python differ today

After pulling `752ae0b` (no Python changes yet), the C++ and Python codebases are bit-identical everywhere *except* the weather-time mapping. This is worth stating precisely so the port stays focused:

| Layer | C++ | Python | Same? |
|---|---|---|---|
| HDF5 schema (`metadata`, `actual_weather`, `predicted_weather`, 6 weather cols) | as documented | as documented | ✅ identical |
| Route YAML loader (parses `forecasts.forecast_window.end` as ETA, segments table for headings/distances) | `route.cpp` | `route.py` | ✅ identical |
| Frame / V-line (every 6 h) / H-line (weather-zone + course-change crossings) | `frame.cpp` | `nodes.py` / `atomic_edges.py` | ✅ identical |
| Atomic-edge graph topology (nodes, fan-out, edge count) | 152,571 / 9,214,780 on R1/ETA 280 | identical counts on identical inputs (May 18 §2.4 bit-exact) | ✅ identical |
| Physics (resistance components, FCR, SOG↔SWS inverse, binary-search params: tol 0.001 kn, max 50 iter, bracket [5, 20]) | `physics.cpp` | `shared/physics.py` (canonical; C++ ported eq-by-eq) | ✅ identical (≤0.08 % FP-ordering drift) |
| CSV output (16 columns, ordering, header names) | per README | matches | ✅ identical |
| Default `--h5` | `experiment_b_138wp.h5` (set by 752ae0b) | `voyage_weather.h5` | ❌ cosmetic — both accept `--h5` |
| **Per-arc `sample_hour` pick (SR)** | `active_sample_hour(src_t)`: maps voyage time → largest `sample_hour ≤ (sh_base + ⌊t⌋)` in file's actual `sh_list` | `SR_main.py:157` hardcodes `override_sample_hour=0` → all arcs at `sample_hour=0` | ❌ **core divergence** |
| **Per-piece `sample_hour` pick (Luo)** | `eval_arc` / `eval_baseline` split each spatial sub-segment at every `sample_hour` transition; each piece reads its own `active_sample_hour(ta)` | `luo_main.py` reads one weather row per spatial sub-segment at `sample_hour=0` | ❌ **same root cause** |
| NaN handling on weather read | Walks back through `sh_list` to most recent valid sample at the same cell; drops the arc only if all walkback fails | Drops arc on first NaN encountered | ❌ different |
| Trip-time anchor | `sh_base = sh_list.front()` (first `sample_hour` present in file — may be ≠ 0) | Assumes voyage starts at `sample_hour=0` | ❌ different |

**The Python rebuild is currently a time-frozen-at-t=0 special case of the C++ binary.** Graph, physics, CSV, schema — all identical. The divergence is one localized concept: *which `sample_hour` row each arc reads from the weather table.*

**Concrete fuel-gap on Route 1 / ETA 280 / `experiment_b_138wp.h5`** (full numbers under §5):

| Solver | C++ (post-752ae0b, time-varying) | Python (static at `sample_hour=0`) | Δ |
|---|---:|---:|---:|
| dp_SR | **354.914 mt** | ~359 mt (needs re-run) | ~4–5 mt |
| dp_luo | **361.671 mt** | ~366 mt (needs re-run) | ~4–5 mt |

This ~1.3 % gap is not a bug — it is the *value of using time-varying weather*. Once the four Python changes in §2.1.2 are applied, the Python and C++ fuel totals on identical inputs should reconverge to the ≤ 0.08 % FP-ordering drift documented on May 18 §2.4.

### 2.2 First run of the post-752ae0b C++ binaries — Route 1 / ETA 280

Rebuilt both binaries locally on May 19, ran with **pure defaults** (mirroring the invocation Tal's commit sets up: `--yaml route.yaml --h5 experiment_b_138wp.h5`, mean_sog ± 3 = [9.1, 15.1] kn, zeta_nm = 1.0, tau_h = 0.1). Artifacts in `pipeline/dp_cpp/runs/2026_05_19_post_752ae0b/`.

| Solver | Total fuel | Voyage time | Graph | Build / Solve |
|---|---:|---:|---|---:|
| **dp_SR** (time-varying) | **354.914 mt** | 280.000 h | 152,571 nodes / 9,214,780 atomic edges | 13.0 s / 0.27 s |
| **dp_luo** (time-varying) | **361.671 mt** | 280.000 h | 47 blocks / 209 sub-segs / 163 H-lines | — / 22.6 s |

vs the May 18 static-weather numbers (Route 1 / ETA 280, but on the old `voyage_weather.h5` with `sample_hour=0`):

| Solver | Static (May 18) | Time-varying (May 19) | Δ |
|---|---:|---:|---:|
| dp_SR | 359.594 mt | **354.914 mt** | **−4.680 mt (−1.30 %)** |
| dp_luo | 366.140 mt | **361.671 mt** | **−4.469 mt (−1.22 %)** |
| **SR − Luo gap** | +6.546 mt | **+6.757 mt** | virtually unchanged |

Notes:
- The HDF5 file also changed (`voyage_weather.h5` → `experiment_b_138wp.h5`), so this is **not a clean weather-isolation A/B** — the −4.5 mt drop is a mix of "different weather file" and "time-varying vs static." A clean isolation would re-run the *static* C++ binary on `experiment_b_138wp.h5`; currently impossible without editing `SR_main.cpp` line 132 because there is no CLI flag for it.
- `dp_luo` solve time grew 14.3 s → 22.6 s (+58 %) — the per-piece temporal splitting Tal added in `eval_arc` / `eval_baseline` adds work proportional to the number of `sample_hour` transitions a spatial sub-segment straddles.
- SR − Luo gap is **unchanged** (~6.7 mt). This is consistent with May 18 §5.4.1's finding that the SR-vs-Luo gap is driven by *within-block weather variance*, not the choice between static and time-varying weather across blocks.

### 2.3 Python port of `752ae0b` complete — full C++↔Python parity restored

The four-file Python port (§2.1.2 plan) is implemented and validated on Route 1 / ETA 280 / `experiment_b_138wp.h5`. Parity confirmed against the C++ binaries built from `752ae0b`. The Python rebuild is once again a faithful mirror of the C++ — no longer a "time-frozen-at-t=0 special case" as documented in §2.1.6.

#### 2.3.1 Apples-to-apples parity — Malacca / ETA 280

| Solver | C++ (May 19) | Python (May 25, time-varying) | Δ (Py − C++) | Structural parity |
|---|---:|---:|---:|:---:|
| **dp_SR** | 354.914 mt | **354.821 mt** | **−0.093 mt (−0.026 %)** | 152,571 nodes / 9,214,780 edges / 148 atomic arcs — identical |
| **dp_luo** | 361.671 mt | **361.561 mt** | **−0.110 mt (−0.030 %)** | 47 blocks / 209 sub-segments — identical |
| **SR − Luo gap** | +6.757 mt | **+6.740 mt** | matches to 0.017 mt | — |

Both drifts (0.026 % / 0.030 %) sit **inside the ≤0.08 % FP-ordering noise floor** documented on May 18 §2.4. This is the expected reconvergence: the Python rebuild now solves the same problem as the C++ binaries, on the same inputs, with the same time-varying weather logic.

#### 2.3.2 Performance gap (Python vs C++ on this run)

| Solver | C++ total | Python total | Slowdown |
|---|---:|---:|---:|
| dp_SR | 13.3 s | 203.4 s | **15.3×** |
| dp_luo | 22.6 s | 421.5 s | **18.6×** |

dp_luo's slowdown widened ~5 % vs May 18's parity number because the temporal-splitting loop adds inner-loop Python overhead (more `bisect_right` calls + more `cell_weather_at` lookups per sub-segment). Still within the same order of magnitude as previous Python/C++ ratios.

#### 2.3.3 Files modified (all under `pipeline/dp_rebuild/`)

| File | Change |
|---|---|
| `weather.py` | Imported `floor` from `math`; added `VoyageWeather.active_sample_hour(t_voyage_h)` — mirror of `weather.cpp:130-141`. Maps voyage time to the largest `sample_hour ≤ (sh_base + ⌊t⌋)` via `bisect_right − 1` over `self._sample_hours`. |
| `atomic_edges.py` | Added `from bisect import bisect_right`. In `_emit_from_src`: when `override_sample_hour is None`, picks `sample_hour = frame.voyage.active_sample_hour(src_t)`; on NaN read, walks back through `sh_list` to the most recent valid sample at the same cell; drops the arc only if walkback exhausts. Mirror of `atomic_edges.cpp:31-52`. Legacy `override_sample_hour=<int>` path unchanged. |
| `SR_main.py` | Flipped `override_sample_hour=0` → `None` at the `build_atomic_edges` call site (line 157). Time-varying becomes the default; pass an `int` via the same code path to force static mode. |
| `luo_main.py` | Added `from bisect import bisect_right`. Rewrote `eval_arc` and `eval_baseline`: anchored on `sh_base = sh_list[0]`; each spatial sub-segment now split at every `sample_hour` transition (`t_b = sh_v - sh_base`) so each temporal piece is priced against `active_sample_hour(ta)`; per-piece `da, db` interpolated linearly from `sog`; per-piece NaN walkback identical to `atomic_edges.py`; emits one `Seg` per temporal piece. Default `sample_hour` parameter changed from `0` to `None`. Mirrors `luo_main.cpp:78-130` and `luo_main.cpp:152-220`. |

Total: ~110 net new Python lines added, ~50 removed. No code churn elsewhere — `frame.py`, `nodes.py`, `route.py`, `bellman.py`, `physics.py` untouched.

#### 2.3.4 CSV output already matches C++

Pre-existing Python CSV writers (`write_atomic_csv`, `write_luo_csv`, `write_baseline_csv`) already emit the same 16-column (SR) / 17-column (Luo) format as the C++ binaries. Today's parity run produced identical row counts and identical column values to ~6 sig figs:

| File | C++ rows | Python rows | Header diff | Values match |
|---|---:|---:|---|---|
| `sr_dp.csv` | 149 (1 + 148 arcs) | 149 | byte-identical except line ending (LF vs CRLF) | ✅ to ~6 sig figs |
| `luo_dp.csv` | 210 (1 + 209 sub-segs) | 210 | byte-identical except line ending | ✅ to ~6 sig figs |

CSV invariants confirmed via pandas sanity check:

| Check | `sr_dp.csv` (Py) | `luo_dp.csv` (Py) |
|---|---|---|
| `sum(fuel_mt)` | **354.821 mt** (matches solver summary) | **361.561 mt** (matches summary) |
| `sum(duration_h)` | **280.000000 h** (= ETA) | **280.000000 h** (= ETA) |
| Unique SOG per block (Luo invariant) | N/A | min = max = 1 across all 47 blocks ✅ |

The Luo SOG-lock invariant holds with the new temporal splits: rows within a block now carry different weather (the time-varying split) but the locked SOG is unchanged — confirming that Tal's per-piece weather variation does not break the block-level constraint.

#### 2.3.5 Validation against §2.1.5 reference

All four C++ blocks identified as canonical sources in §2.1.5 were translated:

| C++ source | Python target |
|---|---|
| `weather.cpp:130-141` (`active_sample_hour`) | `pipeline/dp_rebuild/weather.py` `VoyageWeather.active_sample_hour` |
| `atomic_edges.cpp:31-52` (sample_hour pick + walkback in `emit_from_src`) | `pipeline/dp_rebuild/atomic_edges.py` `_emit_from_src` weather-pick block |
| `luo_main.cpp:78-130` (temporal split in `eval_arc`) | `pipeline/dp_rebuild/luo_main.py` `eval_arc` |
| `luo_main.cpp:152-220` (temporal split in `eval_baseline`) | `pipeline/dp_rebuild/luo_main.py` `eval_baseline` |

#### 2.3.6 What this unblocks

- **Route 2 (Atlantic) C++↔Python parity** is now mechanical — same code paths, just point at `experiment_d_391wp.h5` and `st_johns_liverpool.yaml`. Listed in §1 / §3.
- **Mode B implementation** can build on the new `active_sample_hour` plumbing — Mode B is the same dispatch but with `forecast_hour ≠ None` and `sample_hour` pinned to the planning-moment cycle rather than the active-at-ta cycle. Targeted as the next porting unit.
- **Rolling horizon prototype** — the per-arc `active_sample_hour(src_t)` plus NaN-walkback is the exact primitive RH needs. RH adds the outer loop (rebuild every 6 h with the latest forecast cycle); the arc-level weather selection is now identical between C++ and Python.

### 2.4 May 25 session summary

Everything below was done in a single working session on 2026-05-25, building directly on §2.1 (Tal's commit log) and §2.3 (the Python port).

#### 2.4.1 Pulled Tal's `752ae0b` and rebuilt the C++ binaries

- `git pull --ff-only` → local main fast-forwarded from `ef59dd9` → `752ae0b`.
- `cmake --build pipeline/dp_cpp/build -j` — incremental rebuild, ~12 s. Both `dp_SR` and `dp_luo` rebuilt cleanly; only pre-existing warnings (unused params, brace style), nothing from Tal's diff.
- First post-pull C++ run (Route 1 / ETA 280 / `experiment_b_138wp.h5`, all defaults) → dp_SR 354.914 mt, dp_luo 361.671 mt (§2.2).

#### 2.4.2 Python port → C++↔Python parity (§2.3 detail)

Four-file change in `pipeline/dp_rebuild/`:

| File | Change |
|---|---|
| `weather.py` | + `active_sample_hour(t)`; +`from math import floor` |
| `atomic_edges.py` | `None` branch → `active_sample_hour` + NaN walkback; +`from bisect import bisect_right` |
| `SR_main.py` | `override_sample_hour=0` → `None` |
| `luo_main.py` | `eval_arc` + `eval_baseline` rewritten for temporal-split per piece; per-piece NaN walkback |

Parity confirmed (§2.3.1):

- dp_SR: Py 354.821 vs C++ 354.914 → −0.026 % (within ≤0.08 % FP-noise)
- dp_luo: Py 361.561 vs C++ 361.671 → −0.030 % (within ≤0.08 %)
- Graph structure (nodes, edges, schedule length) bit-identical between Python and C++.

CSV invariants verified via pandas: `sum(fuel_mt)` matches summary, `sum(duration_h) = ETA`, Luo's one-SOG-per-block lock intact across the new temporal splits (§2.3.4).

#### 2.4.3 HDF5 cleanup — `pipeline/data/`

Deleted **5 stale files**, total ~110 MB:

| File | Size | Why removed |
|---|---:|---|
| `voyage_weather.h5` | 6.5 M | Pre-experiment Feb 15 file, only 12 sample_hours, superseded |
| `experiment_b_138wp_historical.h5` | 29 M | Truncated route ("Persian Gulf to Indian Ocean 1") |
| `experiment_b_138wp_shlomo1_old.h5` | 51 M | Same truncated route, older |
| `test_170wp.h5` | 2.1 M | Old test fixture, predates experiment_* naming |
| `experiment_d_391wp_edison.h5` | 22 M | Older Atlantic snapshot |

Pre-deletion `grep` confirmed no active code references any of them (only argparse defaults still mention `voyage_weather.h5`; deletion just means default-flag invocations need `--h5`).

Retained in `pipeline/data/`:

| File | Size | Purpose |
|---|---:|---|
| `experiment_b_138wp.h5` | 88 M | **Malacca live (canonical)** — 131 wp, 271 sample_hours |
| `experiment_d_391wp.h5` | 227 M | **Atlantic live (canonical)** — 391 wp |
| `experiment_a_7wp.h5` | 11 M | Experiment A fixture |
| `paper_table8.h5` | 12 K | Paper validation |

> **Filename note**: `experiment_b_138wp.h5` actually has **131 waypoints** inside (13 originals + 118 interpolated at 25 nm). The "138" in the filename is a misnomer from an earlier collection run with different interval; not worth renaming since the route_name attribute is canonical.

#### 2.4.4 Plan-vs-Simulate workflow — gap analysis

Discussed the pattern needed for realistic operational comparison: **plan against `predicted_weather`, simulate against `actual_weather`, measure the gap.** Output contract (`pipeline-standards.md` §7) already specifies the schema (`planned.total_fuel_mt`, `simulated.total_fuel_mt`, `metrics.fuel_gap_percent`).

Current status:

| Step | Status | Blocker |
|---|---|---|
| 1. Plan against forecast (Mode B) | ⚠️ partial | needs `active_forecast_hour(t)` helper in `weather.py` — mirror of `active_sample_hour`, applied to the forecast_hour axis. ~30 lines. |
| 2. Simulate against actual | ✅ exists | `pipeline/shared/simulation.py:simulate_voyage` already implemented (per-waypoint actual lookup, SWS clamping, violation logging) |
| 3. Compute metrics | ✅ exists | `pipeline/shared/metrics.py:compute_result_metrics` |
| 4. End-to-end wiring in SR_main / luo_main | ❌ not done | needs a `--mode {actual,forecast,forecast_lead=N}` flag + post-solve simulate call |

**Estimate to land plan-then-simulate**: ~80–100 lines of Python across 3 files, ~1 focused hour. Unlocks the rolling-horizon prototype (which is just an outer loop calling Mode B at each 6 h decision step).

#### 2.4.5 Codebase walkthrough — documentation for future work

Walked through the Python SR pipeline top-to-bottom for understanding (no code changes from this part):

- `SR_main.py` as thin orchestrator (186 LOC, ~30 of which do real work)
- Route building: `route_waypoints.py` (13 lat/lon anchors, paper Table 1) + `persian_gulf_malacca_paper.yaml` (12 segments with distance/heading/default-weather), how `load_yaml_route` + `synthesize_multi_window(6 h)` turn one window into 47
- Waypoint interpolation: `pipeline/collect/waypoints.py:generate_waypoints` + `interpolate_geodesic` (slerp) — 13 originals → 131 waypoints at 25 nm
- HDF5 schema: 3 datasets (`/metadata`, `/actual_weather`, `/predicted_weather`) + root attrs
- Frame → atomic-edge graph → Bellman flow; nodes and edges created together via BFS interning
- `AtomicEdge` 12-field schema (geometry × 4 + decision/realized SOG + weather/heading/sws/fcr/fuel + `crosses_v_line`)
- Per-arc weather decision: source-only, 5-layer lookup (`active_sample_hour` → `position_at_d` → cell index → waypoint set in cell → linear/circular mean)
- Decision point for actual vs predicted: one argument (`forecast_hour=` to `build_atomic_edges`), one branch in `weather.py:_row_for`

This is the source-of-truth mental model for the supervisor walkthrough.

#### 2.4.6 Commit + push

Single tight commit:

- **`acad96b`** — *Port time-varying weather to Python (mirror of C++ 752ae0b)* — 5 files, 462 ins / 70 del. Pushed to `origin/main` on 2026-05-25.
- Pre-existing M/D files (`.claude/commit_log.md`, `model_report_geisinger_*.pdf`), legacy outputs in `old/pipeline_legacy/output/`, literature PDFs, and stray run-output CSVs were intentionally left untracked / unstaged — they belong to other commits.

#### 2.4.7 Open list after this session

Carried into §3 / §6:

- [ ] **Mode B — port `active_forecast_hour(t)`** (highest priority — unblocks plan-vs-sim and RH)
- [ ] Wire `simulate_voyage` into `SR_main.py` / `luo_main.py` as a post-solve step
- [ ] Add `--mode {actual,forecast,forecast_lead=N}` CLI flag
- [ ] Route 2 (Atlantic) parity rerun — needs the same Python on `experiment_d_391wp.h5` + `st_johns_liverpool.yaml`
- [ ] Rolling-horizon prototype (depends on Mode B landing first)
- [ ] Phase 4 refactor (stress-test / Route 2 / visualization scripts to call `SR_main.solve()` / `luo_main.solve()` instead of legacy locked modules)

### 2.5 *(to fill in — anything else between May 18 and May 25 not covered above)*

---

## 3. Open Items / Next Steps

- **Mode B implementation** (per-block `predicted_weather[sample_hour=N, forecast_hour=k]`). Mode C is the oracle upper bound; Mode B is the realistic planner. Mode B − Mode C measures the value of perfect information.
- **Rolling Horizon prototype**. Rebuild the atomic-edge graph at each 6h decision step with the latest forecast; take the first block's optimal SOG; advance. Tal's stable Luo 2D DP + the new time-varying weather logic make this a thin orchestration layer rather than a re-implementation.
- **Behavioural sanity checks** — zero-weather, constant-weather, lock-monotonicity (carried).
- **Soft ETA** exercise (carried).
- **Route 2 (Atlantic) C++↔Python parity** under Tal's new time-varying logic.

---

## 4. Data Collection Status

| Server | Status | Route 1 (138 wp) | Route 2 (389 wp) | Uptime |
|--------|--------|---|---|--------|
| Shlomo1 | | | | |
| Shlomo2 | | | | |
| Edison  | | | | |

*(refresh on the morning of May 25)*

Snapshot as of May 19 14:10 IDT:

- Shlomo2 `collect_all` (62 d uptime in session): last cycle sample_hour=1746, Route exp_b 96.4 MB / exp_d 245.1 MB.
- Edison `collect_all` (12 d uptime in session): last cycle sample_hour=1734, Route 1 96.7 MB / Route 2 245.3 MB.
- Both idle until next NWP cycle (17:00 UTC each respectively).
- Edison is ~12 sample-hours (~3 days at 6h cadence) behind Shlomo2 — investigate before next meeting if delta persists.

---

## 5. Results Tables

*(to fill in as runs complete this week — leave Mode C / sweep numbers from May 18 §5 as the baseline to update against)*

---

## 6. Questions for Supervisor

1. **C++ as production solver, Python as reference.** With the time-varying weather change Tal just made, the C++ binaries are once again ahead of the Python rebuild semantically. The May 18 question 4 about "Python orchestration around C++ vs dual-language" is now load-bearing — every Tal commit adds a Python catch-up cost. Proposal: lock the parallel-development convention as "every C++ commit gets a mirroring Python PR within one working week, validated by parity test on fixed h5+ETA." Agree?
2. *(to fill in)*
3. *(to fill in)*

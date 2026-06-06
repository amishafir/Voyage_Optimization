# Meeting Prep — Supervisor Meeting, June 15 2026

---

## 1. Action Items from June 1 Meeting

*(to fill in after the June 1 meeting — see `docs/meeting_prep_2026_06_01.md` §1 for the three Task 1/2/3 framing that was the going-in plan)*

| # | Task | Status |
|---|------|--------|
| 1 | *(to fill in)* | not started |
| 2 | *(to fill in)* | not started |
| 3 | *(to fill in)* | not started |

---

## 2. Progress This Week

### 2.1 *(to fill in — main porting / feature work since June 1)*

### 2.2 *(to fill in — secondary work / parity runs / cleanups)*

### 2.3 *(to fill in — anything else between June 1 and June 15 not covered above)*

---

## 3. Open Items / Next Steps

Carried over from June 1 §1, §3, §5.5.4:

- [ ] **Mode B — port `active_forecast_hour(t)`** (highest priority — unblocks plan-vs-sim and RH). The June 1 chain-sweep work was Mode C only; Mode B remains the missing realistic-planner path.
- [ ] **Wire `simulate_voyage` into `SR_main.py` / `luo_main.py`** as a post-solve step, so each voyage's `planned` result has a paired `simulated.total_fuel_mt` against actual weather.
- [ ] **Add `--mode {actual,forecast,forecast_lead=N}` CLI flag** (Task 3 prerequisite).
- [ ] **Plan-on-forecast → simulate-on-actual sweep** (Task 3 from June 1 §1). Run the same 19-voyage chain in Mode B (plan), then simulate each plan on Mode C actual weather; report planned/simulated/gap per voyage. Builds on the orchestrator landed in `5756fc3`.
- [ ] **Repeat chain sweep in Mode B** — Mode B − Mode C per voyage measures the value of perfect information (June 1 §5.5.4 step 1).
- [ ] **Rolling-horizon prototype** — see §4 for the locked design. NOT dependent on the full Mode B port any more; uses a narrow `time_key` callable instead.
- [ ] **Behavioural sanity checks** — zero-weather, constant-weather, lock-monotonicity (carried).
- [ ] **Soft ETA** exercise (carried).
- [ ] **Edison ↔ Shlomo2 collection delta** — re-check whether Edison is still ~12 sample-hours behind; investigate root cause if delta persists (carried).
- [ ] **Phase 4 cleanup tail** — `pipeline/dp_rebuild/results/` (stress_test_sweep artifacts, old block traces, eta_sweep_2026_05_18.md) and stale CSVs in `pipeline/dp_rebuild/` (`baseline.csv`, `luo_dp.csv`, `sr_dp.csv`) should either be archived or `.gitignore`d.
- [ ] **Add departure-time x-axis plot** to the chain-sweep analysis — `sh_base` maps to days into the collection window; useful for spotting seasonal patterns (June 1 §5.5.4 step 3).

---

## 4. Planned Experiment — Rolling Horizon (RH-SR / RH-Luo vs Naive)

The centerpiece for this meeting. Brainstormed and locked on 2026-06-01.

### 4.1 Setup

At each 6 h decision step `k = 0, 1, 2, …`:

1. **Look-ahead horizon** = remainder of the voyage from `(d_k, t_k = 6k)`
2. **Weather inputs for this re-plan**:
   - **First 6 h block** of the look-ahead: **actual** weather at `sample_hour = sh_base + 6k` (Mode C — "the captain can see current conditions")
   - **Rest of the look-ahead**: **forecast** issued at `sample_hour = sh_base + 6k`, with forecast leads `6, 12, 18, …` h (Mode B style)
3. **Solve** the sub-problem from `(d_k, τ = 0)` to destination in `ETA − 6k` h, with mixed weather
4. **Execute** the first block of the plan only (block 0's SOG/lock) — same as the planned block 0 fuel/distance, since the plan used actual weather for block 0
5. **Re-plan** at `k + 1` with the new sample_hour cycle and updated remaining horizon
6. **At voyage end**: total realised fuel = sum over executed first blocks; compare to **Naive fixed-mean-SOG baseline** run against actual weather

Solvers: **SR** and **Luo** run independently — each evolves its own `d_executed` because each makes its own block-0 decision.

### 4.2 Why "actual" for the first block

Strict semantic: the captain at decision time can observe current conditions (radar, satellite, on-board sensors) — those 6 h are effectively knowable. After that, only forecasts are available. This is realistic and clean to implement: at re-plan `k` the weather lookup at sub-voyage time `τ` is

```python
def time_key(τ: float) -> tuple[int, int | None]:
    if τ < 6.0:
        return (sh_base + 6k, None)              # actual_weather[sh=current_sh]
    return (sh_base + 6k, 6 * int(τ // 6))       # predicted[sh=current_sh, fh=6, 12, …]
```

### 4.3 Comparison story

| Comparison | Number | Meaning |
|---|---|---|
| **RH realised vs Naive (headline)** | mt and % | The selling number: "re-planning every 6 h with mixed nowcast/forecast saves X % vs the captain who picks one speed and stays there." |
| RH realised vs Mode C oracle (reference, not computed) | mt | Cost of imperfect forecast. From June 1 chain sweep: Mode C SR = 203.198 mt, Luo = 210.250 mt for Route 2 sh_base=0. RH should be just above these. |
| Per-replan SOG divergence | kn | Diagnostic: did the new forecast change the block-0 SOG decision vs the previous re-plan's plan-for-block-k? If rarely → RH adds little; if often → RH is doing real work. |

### 4.4 Implementation prerequisites

We are NOT bringing back the previous Mode B port (the `time_key` / `resolve_cell_weather` abstraction that was wiped in commit `5756fc3`). Three localised changes instead:

| Change | Files | Scope |
|---|---|---|
| `time_key: Callable[[float], (int, int|None)]` kwarg | `atomic_edges._emit_from_src`, `build_atomic_edges`, `luo_main.eval_arc`, `eval_baseline` | ~50 lines. Default `None` preserves current Mode C behaviour. |
| Sub-route trim from `d_start` | New `route.trim_from(d_start)` helper | Re-anchor distances so each sub-voyage starts at `d = 0`. Required for "build fresh frame each re-plan". |
| RH orchestrator | New `pipeline/dp_rebuild/run_rh.py` | Loop, time_key construction, divergence log, per-replan + per-block CSVs, summary. ~250 lines. |

### 4.5 Runtime budget — single-voyage validation (Route 2, sh_base=0)

ETA = 168 h → 28 re-plans. Sub-graph shrinks each iteration.

| | Build | Solve | Sub-iters |
|---|---:|---:|---:|
| SR k=0 (full graph) | ~95 s | ~4 s | |
| SR k=14 (half) | ~50 s | ~2 s | |
| SR k=27 (one block) | ~3 s | <1 s | |
| **SR total** | **~22 min** | ~50 s | 28 |
| **Luo total** | ~21 min | ~50 s | 28 |
| Naive baseline | ~2 s | — | 1 |
| **Total wall** | **~45 min** | | |

### 4.6 Sanity gates (success criteria for first run)

1. **Slack = 0** — RH arrival ≈ ETA exactly (matches June 1 chain sweep behaviour)
2. **RH ≤ Naive** — re-planning must beat set-and-forget; otherwise something is wrong
3. **RH ≥ Mode C oracle** — RH cannot beat perfect information. Reference: SR 203.198, Luo 210.250 from June 1 chain sweep §5.5 (Route 2 voyage 0)

If all three hold, scale up (full 19-voyage chain or Route 1).

### 4.7 Outputs

```
runs/2026_06_15_rh/route2/voyage_00/
    summary.json          # totals: naive, rh_sr, rh_luo, gaps, runtime, gates pass/fail
    rh_sr_replans.csv     # per re-plan: k, sub_eta, sub_L, planned_b0_sog, realised_b0_sog,
                          #              prev_plan_b0_sog, divergence_kn, sub_solve_s
    rh_luo_replans.csv    # same for Luo
    rh_sr_realized.csv    # 28-row realised voyage trajectory (one row per executed block)
    rh_luo_realized.csv   # same for Luo
    naive_realized.csv    # Naive fixed-SOG schedule against actual
```

### 4.8 What to bring to the supervisor

A single table (one row first; chain later if validation passes):

| Voyage | Naive (mt) | RH-SR (mt) | RH-Luo (mt) | RH-SR vs Naive | RH-Luo vs Naive |
|---|---:|---:|---:|---:|---:|
| Route 2, sh_base=0 | ? | ? | ? | ?% | ?% |

Plus a 1-page divergence summary (how often new forecasts changed the block-0 decision) and a citation of the Mode C reference (203.198 / 210.250 mt) for upper-bound context.

### 4.9 Implementation order (next session)

1. Add `time_key` callable kwarg to `atomic_edges` + `luo_main` (50 lines, default-None preserves Mode C)
2. Add `route.trim_from(d_start)` + supporting sub-frame construction
3. Write `pipeline/dp_rebuild/run_rh.py` orchestrator
4. Smoke test: one re-plan (`k = 0`) with `time_key` that returns `(sh_base, None)` always — should reproduce June 1 Mode C numbers exactly (203.198 SR / 210.250 Luo) — backward-compat gate
5. Full single-voyage RH run on Route 2 sh_base=0
6. Verify three sanity gates
7. If green, scale to chain

### 4.10 Executed process — how planning and simulation actually work

Implemented and run 2026-06-02/03. Code: `pipeline/dp_rebuild/run_rh.py` (orchestrator), with a `time_key` callable threaded through `atomic_edges.py` (SR) and `luo_main.py` (Luo). Single voyage = **56 plans** (28 SR + 28 Luo, one of each per 6 h re-plan) plus 1 Naive baseline.

**Planning — mixed actual/forecast weather.** At each re-plan `k` the solver receives weather through `time_key(τ)`, where `τ` is sub-voyage time from the decision point. It splits the look-ahead:

| Sub-voyage time | Weather source | Meaning |
|---|---|---|
| `τ < 6 h` (block 0) | **ACTUAL** at the decision wall-clock (`forecast_hour=None`) | nowcast — captain observes current conditions |
| `τ ≥ 6 h` (tail) | **FORECAST** from the most-recent cycle `sh_fc ≤ T_wall`, lead `= (T_wall − sh_fc) + 6·⌊τ/6⌋` | only forecasts available beyond the present |

Each plan is solved end-to-end against this *mix* — first 6 h on real weather, the entire remainder on (imperfect) forecast — producing a full speed schedule to the destination. Only block 0 is committed.

**Simulation — execution, not a separate simulator.** There is **no separate `simulate_voyage` pass.** The "simulation" is the execution loop: at each step we take **block 0** of the plan (its SOG, distance, fuel) and advance. Because block 0 was planned on *actual* weather, the realised fuel **equals** the planned block-0 fuel — there is no plan-vs-actual discrepancy *within* a block. Realised voyage fuel = **Σ of the 28 executed block-0 fuels**, each on actual weather.

The key consequence to state at the meeting: **forecast error does not appear as a within-block fuel gap — it appears as suboptimal speed *decisions*.** The block-0 SOG the captain commits to was chosen partly to suit a forecast tail that turned out wrong, so the speed profile is slightly off-optimal. That is exactly why RH realised fuel sits *above* the Mode C oracle (which chose every SOG knowing the true weather): the gap is the cost of deciding under imperfect foresight, evaluated on real weather.

The **Naive baseline** is the one genuine forward simulation: a single fixed mean SOG (`L/ETA`) sailed through the actual, time-varying weather (`eval_baseline`), no re-planning.

**Graphs built.** Only SR materialises an explicit `(t,d)` atomic-edge graph (one fresh build per re-plan → **28 SR graphs**, each smaller as `d_start` advances and `eta_sub` shrinks). Luo is a `(column, distance)` DP lattice evaluated arc-by-arc (**28 lattices**). Naive builds no graph.

### 4.11 First-run results (Route 2, sh_base=0) — all gates pass

| | Naive (mt) | RH-SR (mt) | RH-Luo (mt) |
|---|---:|---:|---:|
| realised fuel | 212.467 | **204.851** | **212.439** |
| vs Naive | — | **−3.58 %** | **−0.01 %** |
| vs Mode C oracle | — | +1.653 (oracle 203.198) | +2.189 (oracle 210.250) |

Gates (both solvers): reached destination ✓, slack = 0 (arrival = 168 h) ✓, RH ≤ Naive ✓, RH ≥ oracle ✓ — realised fuel lands cleanly in the `oracle ≤ RH ≤ Naive` sandwich.

**Headline finding:** SR (exploits within-block weather variation at H-line crossings) saves a meaningful **3.58 %**; Luo's block-level DP under forecast essentially **breaks even** (−0.01 %). Divergence diagnostic (did the refreshed forecast change the block-0 SOG vs the prior plan?): RH-SR **8/27 re-plans (30 %)**, mean |Δ| 0.19 kn; RH-Luo **17/27 (63 %)**, mean |Δ| 0.43 kn — Luo fidgets more but gains less.

Outputs: `runs/2026_06_15_rh/route2/voyage_00/` (`summary.json` + per-replan/realized CSVs).

### 4.12 Deviations from the locked design + findings

- **No `route.trim_from` (§4.4 item 2).** Geo/weather lookups key off *absolute* distance via the waypoint list, so re-anchoring each sub-voyage to `d=0` would read weather at the wrong location. Instead kept distances **absolute**, started the solver at `d_start`, reset only the time axis. Backward-compat gate confirms correctness (reproduces 203.198 / 210.250 exactly through the `time_key` path).
- **Forecasts are not issued every 6 h.** `predicted_weather` cycles are at sample_hours `[0, 18, 24, 30, …]` (`sh=6, 12` have no forecast). So the §4.2 `time_key` was refined to use the **most-recent available cycle** with a staleness-adjusted lead. For `sh_base=0` only `k=1,2` are stale (fall back to the hour-0 cycle); `k≥3` are fresh. More faithful to §4.2's intent.
- **Runtime (scaling blocker).** Single voyage took **8.9 h**, not the ~45 min estimate. RH forecast mode touches predicted cells at ~24 distinct leads per solve (each a distinct cache key), vs Mode C's single `fh=None` per sample; every fresh forecast cycle pays a cold-cache cost (~8 Luo solves spiked to 3000–4400 s). **Must optimise cell-weather caching before the 19-voyage chain sweep** (otherwise the chain is days).
- **Partial-final-block fix.** Orchestrator now handles ETAs that aren't multiples of 6 h (`ceil` blocks, final block = remainder, arrival = sum of durations). Needed for Route 1 (280 h → 47 re-plans, last block 4 h). Route 2 (168 h) unaffected.

---

## 5. Data Collection Status

*(to fill in close to the meeting — snapshot of Shlomo2 / Edison `experiment_b_138wp.h5` / `experiment_d_391wp.h5` extents at run time)*

Reference points from June 1:
- Shlomo2 exp_b: sh=[6..2052], 342 unique sample_hours
- Shlomo2 exp_d: sh=[0..2052], 343 unique sample_hours
- Edison consistently ~12 sample_hours behind Shlomo2
- Both collectors alive, ~6h cadence

By June 15 we should have ~14 more days of forecast cycles on each file (~56 additional sample_hours) — enough for **3 more Route 2 voyages** (ETA 168) or **2 more Route 1 voyages** (ETA 280) in the chain sweep if we re-run.

---

## 6. Results Tables

### 6.1 Rolling Horizon — Route 2, sh_base=0 (the §4.8 table)

Full detail in §4.11. Headline:

| Voyage | Naive (mt) | RH-SR (mt) | RH-Luo (mt) | RH-SR vs Naive | RH-Luo vs Naive |
|---|---:|---:|---:|---:|---:|
| Route 2, sh_base=0 | 212.467 | 204.851 | 212.439 | −3.58 % | −0.01 % |

All sanity gates pass for both solvers. Chain (19 voyages) and Route 1 pending the caching optimisation (§4.12).

---

## 7. Questions for Supervisor

1. *(to fill in)*
2. *(to fill in)*
3. *(to fill in)*

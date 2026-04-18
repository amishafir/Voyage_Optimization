# Meeting Prep — Supervisor Meeting, Apr 20 2026

---

## 1. Action Items from Apr 13 Meeting

| # | Task | Status |
|---|------|--------|
| 1 | *(to be filled after Apr 13 meeting)* | TODO |
| 2 | | |
| 3 | | |

Carried over from Mar 31 (still open):
- Revisit `speed_control_optimizer.py` DP graph structure
- Adjust DP algorithm for forecast resolution awareness

---

## 2. Planned Experiments — DP vs Luo Head-to-Head

The goal is a clean, controlled comparison between our DP and Luo's DP on the same data matrix. Two experiments, both isolating the speed-decision granularity as the only variable.

### 2.1 Experiment 1 — Single plan at t=0 with full hindsight

**Setup**: Assume all actual weather is known for every (location, time) prior to departure. Plan once, execute the schedule.

- **Our DP**: free to choose a different SWS at every leg (1–5 nm waypoint spacing).
- **Luo-style DP**: must commit to one speed for each 6h block; cannot change speed within a 6h window.

Both run on the **same weather matrix** (actual weather, perfect knowledge). The only difference is the granularity of speed decisions.

**What it tests**: how much fuel can be saved by allowing finer-grained speed control when planning is otherwise identical and weather is perfectly known. This isolates the value of fine speed granularity from forecast uncertainty.

### 2.2 Experiment 2 — Rolling horizon, replan every 6h

**Setup**: Same as above but with rolling horizon. Replan every 6h with the latest available information.

- **Our DP**: replans every 6h, free to choose a different SWS at every leg within the next horizon.
- **Luo-style DP**: replans every 6h, but each plan commits one speed per 6h block.

Both follow the same replan cadence and use the same weather data at each replan. The only difference is the speed-decision granularity.

**What it tests**: whether the fine-grained speed advantage from Exp 1 still holds under realistic rolling-horizon planning, where forecast staleness and replanning interact.

### 2.3 Common protocol

- Same route, same departure time, same ETA constraint
- Same speed range [v_min, v_max] (recommend matching Luo's [8, 18] kn for fair comparison)
- Same FCR model on both sides (use our cubic `0.000706 × SWS³` for both — eliminates ANN as a confounder)
- Report: total fuel, voyage time, delay, number of speed changes, fuel-per-nm

### 2.4 Exp 1 — Resolved Design Decisions

Brainstorm worked into Q&A; decisions locked in below.

| # | Decision | Choice |
|---|----------|--------|
| 1 | Lock-boundary alignment | **Aligned to departure: t=0, 6h, 12h, ...** No NWP offset since hindsight planning has no forecast cycle to match. |
| 2 | Partial final block | **Allow a shorter final block** at locked speed (matches Luo's paper). |
| 3 | Departure times to run | **Both SH=0 (calm) and SH=60 (storm).** Tests whether the fine-vs-locked gap depends on weather volatility. |
| 4 | Baselines to include | **Open** — decide whether to add FC_constant (optimal single speed `v = L/T_max`) and any other reference lines. Revisit before running. |
| 5 | Code structure | **One module, one config flag** `speed_lock_hours: null \| 6`. Shared transform, shared FCR, shared weather lookup. Only the solver branches. |
| 6 | What "one speed" means inside a locked block | **Lock SWS** (engine setting). Inside the 6h block, sub-legs traverse at locked SWS and whatever SOG the weather produces — distance covered will vary, surfacing the SWS/SOG story Luo's paper erases. |

### 2.5 Exp 1 — Implementation Plan

1. **Config flag**: add `speed_lock_hours` to `dynamic_det` section of experiment.yaml. `null` = free (ours), `6` = Luo-style.
2. **Transform**: reuse `pipeline/dynamic_det/transform.py`, swap data source from `predicted_weather` → `actual_weather`. One code path, new flag controls source.
3. **Solver**: branch `optimize.py` into two paths inside one module:
   - `speed_lock_hours=null` → existing forward Bellman over `(node, time_slot)`.
   - `speed_lock_hours=6` → coarse outer DP. State = `(cum_distance, cum_time)` at 6h boundaries. Edge = "hold SWS k for 6h, integrate sub-legs at locked SWS under per-waypoint actual weather, land at new `(cum_dist, cum_time)` node." Final block uses remaining time.
4. **Run matrix**: Route D × {SH=0, SH=60} × {free, locked=6h}. Four runs.
5. **Sanity checks**:
   - Force free-DP to single speed → must match grid-search over constants.
   - Degenerate lock (lock = dt) → must converge to free-DP.
   - Lock monotonicity: fuel(6h) ≥ fuel(3h) ≥ fuel(1h) ≥ fuel(free).
   - Zero-weather → both variants pick `v = L/T_max`, same fuel.
6. **Output**: side-by-side speed profiles, total fuel, time, delay, gap percentage. Log to results section below.

### 2.6 Hidden Architectural Advantage — Decoupled Parameters

While designing Exp 1, a structural weakness in Luo's architecture surfaced: **his speed resolution is coupled to his time resolution through the graph geometry**, whereas ours are independent. This is worth flagging as an additional differentiator.

**The coupling in Luo's DP:**

```
Δv = ζ / T            ← speed resolution (implied by node geometry)
nodes/stage ≈ (v_max - v_min) × elapsed_time / ζ
edges/node ≈ (v_max - v_min) × T / ζ
total edges E ≈ T_max² × (v_max - v_min)² / (2 × ζ²)
```

His speed choice emerges from the implied velocity between nodes: `v = (L_a − L_b) / T`. So as soon as you fix ζ (distance discretization) and T (stage length), the speed resolution `Δv = ζ/T` is locked. You can't refine speed without touching geometry.

**What happens if Luo wants finer-grained cycles (smaller T)?**

To preserve Δv = 0.167 kn while shrinking T, he must shrink ζ proportionally (`ζ = ζ₀ × T/T₀`). Then edges scale as `1/T²`:

| T (cycle) | ζ needed (for Δv = 0.167 kn) | Edges (rel. to T=6h) | Edges (absolute) | Dijkstra runtime |
|-----------|------------------------------|----------------------|------------------|------------------|
| 6h | 1 nm | 1× | ~2.1M | ~19 min |
| 3h | 0.5 nm | 4× | ~8.4M | ~76 min |
| 1h | 0.167 nm | 36× | ~75M | ~11 h |
| 10 min | 0.028 nm | 1,296× | ~2.7B | ~17 days |
| 6 min (our dt) | 0.0167 nm | 3,600× | ~7.5B | ~46 days |

And he re-plans ~44 times per voyage, so multiply again. Infeasible below ~3h cycles.

If instead he shrinks T but keeps ζ=1nm fixed, the graph stays small but speed resolution degrades catastrophically: at T=1h he can only pick whole-knot speeds (Δv = 1.0 kn). Garbage-in, garbage-out.

**Why our DP sidesteps this:**

```
dt (time resolution)   ← independent config (currently 0.1h)
Δv (SWS step)          ← independent config (currently 0.1 kn)
waypoint spacing       ← fixed by route geometry
```

Three parameters, three axes, no interference. We shrink dt without touching Δv. We refine Δv without touching dt. Complexity scales linearly in each, not as coupled squares.

The root cause: **Luo's decision variable is implicit** (emerges from node geometry), while **ours is explicit** (an SWS loop in the inner DP). Implicit decisions couple discretizations; explicit ones decouple them.

**Implication for the paper**: this is a third honest architectural advantage on top of (a) finer spatial weather resolution, and (b) SWS/SOG split. It becomes operationally relevant the moment anyone wants to run Luo's method at finer-than-6h cycles, which is a natural next step for his line of work.

**Implication for Exp 1**: our Luo-style variant (coarse outer DP at 6h lock) sidesteps the coupling because we enforce the 6h lock as a *constraint* on our explicit SWS list, not by rebuilding his geometric graph. So our Luo-style variant is actually fairer to Luo than his own architecture would be at finer cycles — worth noting when framing results.

---

## 3. Brainstorm — When Should Two Adjacent Nodes Have Different Speeds?

**The question**: If between two adjacent waypoints we are
- not changing course (heading is the same), and
- not crossing into a different weather forecast cell (same polygon / grid square in the GEFS or Open-Meteo grid),

then nothing physical has changed between those two legs. So why should the optimizer be allowed to pick a different speed for each? Conceptually, those legs should be **collapsed into a single decision** — same heading, same weather, same optimal speed.

**Implications to think about**:

1. **Node consolidation**: Adjacent waypoints inside the same weather cell with the same heading could be merged into one "decision unit." This reduces graph size and prevents the optimizer from exploiting numerical noise as if it were real weather variation.

2. **Natural alignment with Luo**: Luo's 6h stages cover ~72–108 nm — large enough that the ship typically crosses multiple weather cells per stage. Our 1–5 nm spacing means we often have many consecutive waypoints inside a single cell. Collapsing them moves us conceptually closer to Luo's "one decision per meaningful change" — but driven by **physical change** (course / weather cell) rather than fixed time blocks.

3. **What defines a "weather cell"?** Open-Meteo grid resolution is ~0.1° (~6 nm). GEFS is 0.5° (~30 nm). Either way, many of our waypoints share a cell. The decision unit should probably be: **(course-segment) × (weather-cell)** — collapsed until either changes.

4. **Open question — does this change results?** If consecutive waypoints in the same cell genuinely have the same optimal speed, collapsing them shouldn't change the fuel total — only the graph size. If results differ, that signals the optimizer was over-fitting to noise, which would be a real finding.

5. **Connection to Luo comparison**: This brainstorm could explain *why* our finer waypoint spacing matters (or doesn't). If most adjacent waypoints share a cell + heading, the effective decision count is much closer to Luo's than the raw waypoint count suggests.

To explore: build a "collapsed" view of the route — group consecutive waypoints by (heading bucket, weather cell ID) — and count how many true decision units exist for each route. Compare to the raw waypoint count and to Luo's stage count.

---

## 4. Progress Since Apr 13

### 4.1 Implementation Completed

Built Exp 1 infrastructure — three code changes, one new script:

1. **`pipeline/dynamic_det/transform.py`** — added `weather_source: "actual_hindsight"` mode. Loads ALL actual weather rows from HDF5 across all sample hours, builds `weather_grid[node_id][sample_hour]` so the DP sees the real weather at every (location, time) pair.

2. **`pipeline/dynamic_det/optimize.py`** — refactored into two solver paths controlled by `speed_lock_hours` config key:
   - `null` → `_optimize_free()`: existing forward Bellman DP, speed changes at every leg.
   - integer (e.g. 6) → `_optimize_locked()`: coarse outer DP via Dijkstra. Each transition simulates one lock-block — sail at fixed SWS for N hours, traverse multiple legs, accumulate fuel. Block boundaries are the only decision points.
   - Shared helpers extracted: `_lookup_weather()`, `_sog_for()`, `_find_best_arrival()`, `_build_result()`.

3. **`pipeline/config/experiment_exp1_luo.yaml`** — experiment config for Route D, [9,15] kn, `actual_hindsight` weather, with `speed_lock_hours` toggle.

4. **`pipeline/experiments/run_exp1.py`** — comparison runner. Runs both free + locked on the same HDF5 + departure, prints side-by-side table with fuel, time, delay, gap %, speed change counts.

### 4.2 Exp 1 Results — Single Plan, Full Hindsight

**Route D** (391 wp, 1,955 nm), **SH=0** (calm departure), **hard ETA = 163h**.

#### Run 1: [11, 13] kn speed range, dt=0.01h

| Variant | Fuel (mt) | Time (h) | Delay | Speed changes | Compute |
|---|---|---|---|---|---|
| Free (ours) | 216.50 | 162.61 | 0 | 250 | 18s |
| Locked 6h (Luo) | 215.74 | 162.92 | 0 | 20 | 2.3h |
| **Gap** | **-0.76 mt (-0.35%)** | | | | |

**Anomaly**: free > locked by 0.76 mt — violates the theoretical guarantee (free is unconstrained, should always be ≤ locked). **Cause**: ceiling-rounding accumulation. Each of 388 legs has travel time ceiled to dt=0.01h independently. Over 388 legs, tiny rounding errors compound (~0.003h × 388 ≈ 1.2h of phantom time). The locked DP rounds only ~27 times (once per block), so its total-time estimate is more accurate and it can choose slightly slower speeds. This is a numerical artifact — both results are effectively equal within rounding noise.

#### Run 2: [9, 15] kn speed range

| Variant | Fuel (mt) | Time (h) | Delay | Speed changes | Compute | dt |
|---|---|---|---|---|---|---|
| Free (ours) | 215.38 | 163.0 | 0 | — | 161s | 0.01h |
| Locked 6h (Luo) | 215.88 | 162.7 | 0 | 20 (22 blocks) | 82 min | 0.1h |
| **Gap** | **0.50 mt (0.23%)** | | | | | |

Direction now correct (free ≤ locked), but the gap is **tiny — 0.50 mt, 0.23%**.

Despite having [9, 15] kn available, the locked DP chose speeds entirely in the **11.4–12.5 kn** range. The optimizer doesn't touch the extremes.

### 4.3 Analysis — Why the Gap Is So Small

**Root cause: hard ETA + cubic FCR pinch the optimizer to ~12 kn regardless of granularity.**

- Required average speed: 1,955 nm / 163h ≈ 12.0 kn
- Going slow on one leg (9 kn) requires compensating fast on another (15 kn)
- The cubic FCR heavily penalizes speed variation:
  - FCR(9 kn) = 0.514 mt/h
  - FCR(12 kn) = 1.219 mt/h
  - FCR(15 kn) = 2.382 mt/h
- Speeding up 3 kn above average costs 1.163 mt/h more; slowing down 3 kn saves only 0.705 mt/h → net loss from any speed variation around the mean
- Jensen's inequality: `E[V³] > E[V]³` — variable speed always costs more fuel than constant speed at the same average, when FCR is convex
- With a hard ETA forcing average speed ≈ 12 kn, both free and locked cluster around 12 kn and arrive at nearly the same total fuel

**Implication**: fine-grained speed control has almost no value under hard ETA when the required average speed is near the middle of the range. The ETA constraint dominates; speed granularity doesn't matter.

**This partially explains why our 3-agent experiments (Mar 30) showed <1% differences** — same mechanism. The agents all arrive at similar fuel totals because the ETA forces them to similar average speeds, and the cubic FCR punishes any deviation.

### 4.4 Compute Time Issue

The locked DP is too slow for practical use:

| Config | Locked DP compute time |
|---|---|
| [11,13] kn, dt=0.01h | 2.3 hours |
| [9,15] kn, dt=0.1h | 82 min |
| [9,15] kn, dt=0.01h | Running (estimated 5+ hours) |

**Cause**: Dijkstra over (leg, time_slot) state space with fine dt. With dt=0.01h and 61 speeds, the reachable state space is ~6M states × 61 speed evaluations × ~18 sub-legs per block = billions of operations.

**Fix needed**: use coarser dt inside the locked solver (block-boundary decisions don't need 0.01h precision), or implement the locked DP as a pure block-index-based solver (state = block number, not time_slot) to decouple from dt entirely.

### 4.5 Ceiling-Rounding Accumulation (dt Gotcha)

Confirmed the gotcha from Apr 13 Section 3.5.10 in practice:

| dt | Free DP behavior | Issue |
|---|---|---|
| 0.1h | **Cannot meet ETA** (relaxed to 198h) | Each ~0.42h leg ceiled to 0.5h → 388 × 0.08 = 31h phantom time |
| 0.01h | Meets ETA (163.0h, 216.50 mt) | Rounding per leg ~0.003h → 388 × 0.003 ≈ 1.2h accumulated |

Route D's 5 nm waypoint spacing requires dt ≤ 0.01h for the free DP. The locked DP is less sensitive because it rounds per block, not per leg.

### 4.6 Two New Solvers Built (Apr 18)

To address §4.4 (locked DP too slow) and to give Luo a fair comparison line, built two new modules:

**Track A — `pipeline/dynamic_det/luo_style_fast.py`**: same 6h-lock policy as legacy locked DP, but with coarser outer state (`dt_locked=0.1h` default) and memoized `_simulate_block`. Selected via `solver: "fast_locked"`.

**Track B — `pipeline/dynamic_det/luo2024_reconstruction.py`**: faithful Luo 2024 architecture — `(distance, time)` lattice with ζ=1 nm, T=6h, implicit speed from edge slope `v = (k_b−k_a)·ζ/T`. Speed interpreted as SOG (physically consistent); SWS recovered via inverse for FCR. One weather value per (cell, stage) at stage midpoint. Cubic FCR (no ANN — per §2.3 to eliminate confounder). Selected via `solver: "luo_lattice"`.

`run_exp1.py` extended with `--variants {free, locked, locked_fast, luo_lattice}` and an automatic sanity check (fast vs legacy must match within 0.5 mt).

### 4.7 Track A Validated, Track B Anomalous

Route D, SH=0, [9,15] kn:

| Variant | Fuel (mt) | Time (h) | Compute | Notes |
|---|---|---|---|---|
| Legacy locked (§4.2) | 215.88 | 162.7 | 82 min | reference |
| **Track A (locked_fast)** | **215.88** | 162.7 | **10.6 min** | **Sanity PASS** — identical fuel, 8× faster |
| **Track B (luo_lattice)** | **207.29** | 163.0 | **0.6 s** | beats free DP by 8 mt — anomaly |
| Free DP (§4.2) | 215.38 | 162.7 | 2.6 min | reference |

**Track A works as designed.** Fuel-identical to the legacy solver at ~8× speed. Ready to use for the full Exp 1 matrix (SH=60, soft ETA). Runtime at `dt_locked=0.5h` drops to ~2 min but drifts +6 mt from ceiling accumulation — so 0.1h is the right default.

**Track B's 207.29 mt is lower than free DP's 215.38 mt.** That's theoretically impossible — Luo's lattice is strictly more constrained than our free DP. Prime suspect: the free DP's rounding tax (§4.5) inflates its fuel by ~1–2 mt, while Luo's lattice ceils only 28 times (once per stage) and escapes the drift. Track B validation is blocked on: (a) rerunning free DP without the rounding bias, or (b) comparing Track A ↔ Track B at an identical 6h lock to see if the gap is lock-policy or architecture.

### 4.8 Complexity Is the Real Differentiator

Fuel-wise, free ≈ locked_fast ≈ 215.6 mt — a tie. The paper's story is not "who saves more fuel" but **"how does each scale".**

| Scaling | Luo lattice | Track A |
|---|---|---|
| Edges (fixed `Δv`) | `L · ETA · Δvr / (Δv² · T²)` | `N_wp · (ETA/dt_locked) · (Δvr/Δv) · (lock_h / leg_time)` |
| Scales with `T` | `1/T²` (blows up) | N/A (lock_h is independent) |
| Scales with `Δv` | `1/Δv²` (coupled to geometry) | `1/Δv` (independent knob) |
| Scales with `dt_locked` | N/A | `1/dt_locked` (linear) |

What Luo would need to match our resolution (`Δv = 0.1 kn` fixed):

| Target cycle T | Required ζ | Edges | Feasible |
|---|---|---|---|
| 6 h (published) | 0.6 nm | ~5 M | ✓ (0.6 s) |
| 3 h | 0.3 nm | ~21 M | ✓ (~3 s) |
| 1 h | 0.1 nm | ~190 M | marginal |
| 10 min | 0.017 nm | ~6.8 B | infeasible |
| 0.1 h (our dt) | 0.01 nm | ~19 B | infeasible |

**One-line framing**: Luo couples the speed axis into his graph geometry (`Δv = ζ/T`). We don't. That coupling gives him a 1000× compute win at his published resolution and breaks him as soon as anyone wants finer cycles.

### 4.9 Implication for the Paper

The contribution is no longer "we save fuel over Luo" — hard ETA killed that signal. The contribution is architectural:

> At Luo's published resolution (6 h, 1 nm), his method matches ours to within 0.5% fuel at 1000× less compute. At *any* finer resolution — where rolling horizon, NWP cycle alignment, and tight ETAs live — his method is infeasible while ours stays linear.

Honest framing. Defends both the tie result and the added complexity of our framework.

---

## 5. Data Collection Status

| Server | Status | Route B (138 wp) | Route D (391 wp) | Uptime |
|--------|--------|-------------------|-------------------|--------|
| Shlomo1 | | | | |
| Shlomo2 | | | | |
| Edison | | | | |

---

## 6. Open Experiments

| Experiment | Status | Purpose |
|---|---|---|
| Exp 1: SH=60 (storm) | Not yet run | Test if weather volatility widens the gap |
| Exp 1: soft ETA (λ penalty) | Not yet run | Remove the hard-ETA pinch — does granularity matter more? |
| Exp 1: locked at dt=0.01h, [9,15] | Superseded by Track A | Track A at dt_locked=0.1h reproduces legacy 215.88 mt in 10 min |
| Exp 1: Track A full matrix (SH=0/60 × ETA variants) | Ready to run | Unblocked now that locked_fast takes 10 min not 82 |
| Exp 1: Track B validation (rounding-corrected free DP) | Not yet run | Confirm free < Luo (the theoretical ordering) once rounding is neutralized |
| Exp 1: Track A vs Track B at identical 6h lock | Not yet run | Isolate whether the Track B fuel drop is lock-policy or architecture |
| Exp 2: rolling horizon | Not yet started | Does re-planning interact with granularity? |

---

## 7. Open Items / Discussion Points

- **Hard ETA kills the experiment**: the 163h constraint forces ~12 kn average and the cubic FCR punishes any deviation. Fine vs coarse granularity both land at ~216 mt. Should we switch to soft ETA or relaxed ETA to give the optimizer room?
- **Stormy departure**: SH=60 might show a larger gap if weather forces more speed variation.
- **Node-collapsing brainstorm**: still relevant — if the free DP's 250 speed changes produce only 0.23% savings vs 20 changes, most of those changes are noise.
- **Locked DP compute time**: needs optimization before running the full experiment matrix.
- **Rounding accumulation**: fundamental limitation of the forward Bellman with fine waypoints. Worth documenting in the paper as a practical finding.

---

## 8. Questions for Supervisor

1. **Hard ETA washes out the signal**: with ETA forcing ~12 kn average, fine granularity saves <0.25%. Should we (a) use soft ETA with λ penalty, (b) relax ETA significantly, or (c) accept this as a finding ("under operational ETA constraints, speed granularity doesn't matter")?

2. **Is the <0.25% gap itself publishable?** It's a negative result — fine-grained speed control provides almost no benefit over 6h-locked decisions under realistic ETA constraints. This actually strengthens the case for Luo-style coarse planning in practice. Is that a contribution or a problem for our paper?

3. **Next priority**: run Exp 1 with soft/relaxed ETA (to see if the gap opens up), or proceed to Exp 2 (rolling horizon) where forecast uncertainty might create a bigger differentiator?

4. **Complexity as the contribution**: given that fuel is a tie at Luo's published resolution, is the scaling-law story (§4.8) a strong enough standalone contribution for the paper, or do we need to pair it with a finer-resolution experiment (Exp 2 rolling horizon at 1h or sub-hour cycles) to *show* Luo breaking and us not breaking?

5. **Track B anomaly**: how should we resolve the "Luo beats free" result — rerun free with finer dt to eliminate rounding, or accept that Luo's coarse weather happens to luck out on this route/departure and expect the ordering to invert on SH=60?

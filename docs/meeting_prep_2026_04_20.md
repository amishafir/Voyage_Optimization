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

*(to be filled)*

---

## 5. Data Collection Status

| Server | Status | Route B (138 wp) | Route D (391 wp) | Uptime |
|--------|--------|-------------------|-------------------|--------|
| Shlomo1 | | | | |
| Shlomo2 | | | | |
| Edison | | | | |

---

## 6. Results

*(to be filled as Exp 1 / Exp 2 complete)*

---

## 7. Open Items / Discussion Points

- Exp 1 and Exp 2 results (fine-speed vs 6h-locked speed, both on same data)
- Node-collapsing brainstorm — does collapsing (same heading, same weather cell) change results?

---

## 8. Questions for Supervisor

1.
2.
3.

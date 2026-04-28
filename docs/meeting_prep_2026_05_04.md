# Meeting Prep — Supervisor Meeting, May 4 2026

---

## 1. Action Items from Apr 27 Meeting

| # | Task | Status |
|---|------|--------|
| 1 | *(to be filled after Apr 27 meeting)* | TODO |
| 2 | | |
| 3 | | |

Carried over from Apr 27 §3.9:

- [x] Forward Bellman solver
- [x] Backtrack + schedule reconstruction
- [x] Sink dedup (canonical (t, d) keying in `BellmanSolver`)
- [x] NaN-weather policy at Port B (nearest-valid-waypoint fallback)
- [ ] Rolling-horizon mechanics
- [ ] Behavioural sanity checks (degenerate-lock, zero-weather)
- [ ] Real heading per sub-leg (currently uses representative source heading)

---

## 2. Progress This Week — Luo-Style Locked Mode + Sanity Check

### 2.1 New code

| File | Purpose |
|---|---|
| `pipeline/dp_rebuild/build_edges_locked.py` | Locked-mode edge builder: one constant SWS per 6 h V-band, simulated forward through every H-line crossing. |
| `pipeline/dp_rebuild/run_demo_locked.py` | End-to-end runner — same node set as free DP, swaps in locked edges. |
| `pipeline/dp_rebuild/build_edges_locked.verify_locked_schedule()` | Continuous resimulation of the chosen locked schedule, used as a sanity check. |

### 2.2 Two real bugs caught and fixed by the sanity check

1. **Snap-drift bias.** The first locked-mode build (forward enumeration of SWS, snap dst to 1 nm) produced a phantom voyage **25.6 nm short of L**. Bellman picked the cheapest SWS in each snap bucket → continuous `final_d` always at the lower edge of the bucket → systematic undershoot. Fix: switched to **inverse integration** — for each (src, integer-nm dst) pair, binary-search SWS so the block trajectory ends *exactly* at dst.

2. **Wrong fuel-time on early-arrival blocks.** First inverse-integration run reported the last block as **156 mt** (vs ~5 mt expected). Cause: `fuel = FCR × final_t_solved` instead of `FCR × (final_t_solved − t_k)`. One-line fix.

After both fixes, the continuous resim of the locked schedule lands at **(279.991 h, 3393.240 nm) — Δd = +0.000 nm**, with Bellman fuel matching continuous resim to 0.01 mt.

### 2.3 Final apples-to-apples result on the YAML voyage

| Mode | Total fuel | End time | End d |
|---|---|---|---|
| Free DP (per-square decisions) | **367.561 mt** | 280.000 h | 3393.240 nm |
| Locked DP (one SWS per 6 h block) | **366.480 mt** | 280.000 h | 3393.240 nm |
| **Δ** | **−1.081 mt (−0.29 %)** | | |

Both modes:
- Same node set (568 K)
- Same SOG ∈ [v_min, v_max] feasibility filter (no SWS bound)
- Same physics, weather, hard ETA
- Continuous trajectories land exactly at L; max per-block drift in locked = 0.12 nm

Both totals are within ~1.5 % of the LP validation target (~372 mt).

### 2.4 Why locked is still 0.29 % under free

Both grids are discrete:
- Free DP: per-edge SOG must round to grid points (1 nm × 0.1 h on H lines).
- Locked DP: per-block dst is on a 1 nm grid, but the **SWS is inverse-solved continuously** to land exactly on dst.

Locked DP can hit each integer-nm dst more precisely than free DP can match the equivalent per-leg SOG. So locked dominates by a small grid-noise margin. Refining free DP's H-line node spacing (smaller τ) should close the gap.

---

## 2.5 Geographic H-line Reconstruction — Q&A + First Pass (Apr 28)

After the locked-mode landed, opened a separate strand to fix a quieter
issue: the existing H-line generator anchors weather-cell boundaries at
the *midpoint between adjacent 12 nm interpolated waypoints* whose lat/lon
fall in different 0.5° cells. That's only an approximation of where the
route actually crosses a NWP grid line. Goal: replace the heuristic with
real geometry — compute exactly where each rhumb-line segment crosses the
0.5° marine grid.

### 2.5.1 Q&A session (logged in `thesis_brainstorm.md` §14.18)

Eight quick questions, locked the spec before any code:

| # | Question | Decision |
|---|---|---|
| **Qg1** | Where do segment endpoints (lat, lon) come from? | **(c)** Paper Table 1 — 13 waypoints with explicit (lat°, lon°). Already match the HDF5's first-waypoint-of-each-segment within rounding, so no new data file. |
| **Qg2** | Path shape inside a segment? | **(a)** Rhumb line (loxodrome) — constant compass bearing, matches YAML's `ship_heading`. |
| **Qg3** | NWP grid resolution + alignment? | **(a)** 0.5° marine grid axis-aligned at integer multiples of 0.5°. |
| **Qg4** | Distance metric for cumulative `d`? | **(a)** Rhumb-line distance (consistent with Qg2). YAML lengths become a sanity check. |
| **Qg5** | Weather lookup — per-waypoint or per-cell? | **(b)** Per-cell. For each (cell_id, sample_hour) precompute one canonical row by aggregating waypoints inside that cell. Cleaner; "weather constant inside a cell" becomes exact. *(deferred until after the geometry is validated)* |
| **Qg6** | Implement immediately? | **(b)** Defer — first build a map-style visualizer to see how rhumb crossings translate to graph H-lines on a sample. |
| **Qg7** | Visualization scope? | WP1 → WP2 → WP3, then extended to **all 12 segments** for the big-picture view. |
| **Qg8** | Map projection? | **(b)** Cartopy / Mercator (rhumb lines render as straight lines on Mercator — bonus). |

### 2.5.2 What's been built so far

| File | Purpose |
|---|---|
| `pipeline/dp_rebuild/route_waypoints.py` | 13 waypoints from paper Table 1, hard-coded. Each carries (lat, lon, heading, distance, BN, wind, wave, current). |
| `pipeline/dp_rebuild/geo_grid.py` | Rhumb-line primitives: `rhumb_distance_nm`, `rhumb_bearing_deg`, `rhumb_grid_crossings(p1, p2, grid_deg)` returning every point where the segment crosses a `lat = k·0.5°` or `lon = k·0.5°` grid line. Mathematically exact (no waypoint sampling). |
| `pipeline/dp_rebuild/visualize_geo_grid.py` | Cartopy/Mercator chart of the route + 0.5° grid overlay + crossings, plus a side-by-side (t, d) view showing the resulting H-lines. |

### 2.5.3 First-pass numbers (full voyage, all 12 segments)

| | Total |
|---|---|
| Rhumb sum | 3,393.595 nm |
| Paper sum | 3,393.240 nm |
| **Δ** | **+0.36 nm (+0.01 %)** — accumulated rounding in paper segment lengths |
| Bearings vs paper β | match within ±0.2° on every segment |
| **Grid crossings** | **152** (95 lon + 57 lat) |
| + segment-boundary H-lines | 11 |
| + terminal H-line at d = L | 1 |
| **Total H-lines (new)** | **164** |
| Total H-lines (old waypoint-midpoint policy) | 146 |

Per-segment crossing distribution behaves as expected:
- Diagonal segments (3, 4, 5, 6) → 13–15 crossings each (route slices both axes).
- East-dominant segments (8, 9, 10, 11) → 10–12 crossings, mostly lon (route runs near a constant lat band).
- Final SW dip (12) → 14 crossings (6 lon + 8 lat) as it cuts down 4° lat into Malacca.

### 2.5.4 What this gives us going forward

- **Exact** H-line placement at real cell crossings, not 12 nm interpolation midpoints.
- Distance on each H-line is the *actual* rhumb-line distance from voyage start, accurate to <0.5 nm.
- Spec-clean prerequisite for the per-cell weather migration in **Qg5(b)** — once we move to one canonical weather row per cell, the "weather constant within a cell" invariant holds by definition.
- Total H-line count (164) is in the same magnitude as before (146), so graph size and solve time will be comparable.

### 2.5.5 What's NOT done yet

- Wiring the new generator into `build_nodes.h_line_distances_from_h5` — currently `geo_grid` is a self-contained module the visualizer uses. Switch-over is a one-line change once the per-cell weather lookup (Qg5(b)) is in.
- The per-cell weather aggregation (Qg5(b)) — agreed to defer until the geometry was validated. Now that the geometry is solid we can come back to it.
- Validator updates — the current `validate_graph.py` C1 expects the segment/cell labels coming from the existing waypoint-based logic. Will need a small tweak when we cut over.

---

## 3. Open Items / Next Steps

- **Refine free-DP grid** to confirm the 0.29 % gap is grid noise — predicted: locked ≥ free as theory requires once free's grid is fine enough.
- **Rolling horizon** — replan every 6 h with fresh forecast. Both free and locked already structured around 6 h V-bands, so replumbing is small.
- **Behavioural sanity checks** — zero-weather (closed-form fuel), constant-weather (constant SWS), lock-monotonicity (fuel ↑ as lock_h ↑).
- **Soft ETA** — `BellmanSolver.best_sink(eta_mode="soft", lam=…)` is implemented; not yet exercised.
- **Heading per sub-leg** — currently the locked-edge record stores a representative source heading; the simulation already uses per-sub-leg heading. Cosmetic only.
- **Locked-edge build time** — ~15 min on the YAML voyage. The 30-iter binary search per (src, dst) is the bottleneck. Could cap at 8 iter or reuse cache more aggressively.

---

## 4. Data Collection Status

| Server | Status | exp_b (138 wp) | exp_d (391 wp) | exp_c (968 wp) | Uptime |
|--------|--------|---|---|---|--------|
| Shlomo1 | | | | | |
| Shlomo2 | | | | | |
| Edison | | | | | |

*(refresh on the morning of May 4)*

---

## 5. Results Tables

### 5.1 Free vs Locked, YAML voyage (Persian Gulf → Strait of Malacca, ETA = 280 h)

| Metric | Free DP | Locked DP |
|---|---|---|
| Total fuel | 367.561 mt | 366.480 mt |
| Voyage time | 280.000 h | 280.000 h |
| Average SOG | 12.119 kn | 12.119 kn |
| Schedule length | 190 edges | 47 blocks |
| SWS range used | [10.58, 13.56] kn | [11.38, 12.97] kn |
| Build time | ~2 min | ~15 min (inverse integration) |
| Solve time | ~4 s | ~2 s |
| NaN edges skipped | 0 | 0 |

### 5.2 Sanity check on locked schedule (continuous resim)

| | Bellman | Continuous |
|---|---|---|
| End t | 280.000 h | 279.991 h |
| End d | 3393.240 nm | 3393.240 nm |
| Total fuel | 366.480 mt | 366.491 mt |
| Δfuel | — | +0.011 mt |

Δd = 0.000 nm (lands exactly on Port B).
Max per-block drift over the 47 blocks: **0.12 nm**.

---

## 6. Questions for Supervisor

1. **Locked vs free is now within 0.3 %** — operationally indistinguishable. Is this enough to declare the rebuild "ready for experiments" and move on to RH / multi-route runs, or do you want the free-DP grid refined first to chase the residual gap?
2. **Locked-edge build is 15 min** — acceptable for one-shot experiments, slow if we sweep parameters (e.g. lock_h ∈ {3, 6, 12} h × 5 routes = 15 builds = 4 hours). Worth optimising before the experiment matrix?
3. **Rolling horizon next?** With both planning modes solid on a single forecast, RH is the next paper differentiator. Same graph, replan every 6 h with fresh forecast. Plan to do it on the rebuild?
4. **What's the Luo comparison story now?** Our locked mode = "Luo-style policy with our better physics" (sub-leg integration through course/weather changes vs Luo's single-snapshot-per-stage). The 366.5 mt vs Luo's published numbers is paper-relevant — how do we want to frame it?

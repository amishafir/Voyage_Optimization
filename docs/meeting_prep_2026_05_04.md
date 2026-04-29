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

## 2.6 Cut-Over Wave (Apr 28–29)

After the geometric reconstruction landed, finished the wiring + the policy switch supervisor flagged previously.

### 2.6.1 New analytic H-line generator wired into the graph

- `build_nodes.h_line_distances_from_geo` now produces H-lines from real rhumb-vs-grid crossings on the paper waypoints. Replaces the legacy waypoint-midpoint heuristic.
- Added a τ-grid feasibility filter: drops 2 H-lines per voyage that would create gaps the τ = 0.1 h × v ∈ [9, 13] grid can't span (deadzones at ~0.6 nm and ~1.4 nm). Without it the sink became unreachable. With it, voyage solves cleanly.
- Validator updated (`validate_graph.label_at` now uses `position_at_d` over the paper polyline). All three checks pass on the new graph: 7,614 squares, 162 H-lines, 39 V-bands, 613,328 nodes, 3,308,940 edges.

### 2.6.2 Per-cell mean weather aggregation (Qg5(b)) — IMPLEMENTED

Replaced nearest-waypoint-in-segment lookup with cell-canonical aggregation:

- `VoyageWeather.cell_weather(cell, hour)` — mean over every voyage waypoint that falls in the 0.5° cell at the given (sample, forecast) hour. Linear mean for scalars, **circular mean** (atan2 of mean-sin / mean-cos) for directions, int-rounded mean for Beaufort. NaN rows dropped before averaging.
- `VoyageWeather.cell_weather_at_d(d, waypoints, ...)` — convenience: derives (lat, lon) at d via `position_at_d`, then dispatches to `cell_weather`. Empty-cell fallback routes through `weather_at(d)` so the substitute is geographically near the probe (not the first valid row anywhere on route).
- Threaded through `build_edges.lookup_source_state`, `build_edges_locked.simulate_block_sog`, validator C2. All three demos updated.
- Validator C2 still PASSes — every edge's stored weather matches the cell-canonical lookup at the enter-square center.

### 2.6.3 Locked-mode policy fix: SWS-locking → SOG-locking (Luo 2024)

Supervisor flagged the previous locked builder was the wrong direction: it held SWS constant and let SOG drift. **Luo 2024 holds the target SOG constant, varying SWS per sub-leg.** Fully rewritten.

- `simulate_block_sog`: walks H-line by H-line at constant target SOG, per sub-leg looks up cell-canonical weather + paper heading, **inverse-solves SWS** to maintain target SOG, accumulates fuel = Σ FCR(SWS_i) · Δt_i. Drops the edge if any sub-leg's required SWS > 25 kn (engine bound) or NaN.
- `build_locked_edges`: dst is now **geometric** (`d_src + target_SOG · 6 h`), no inverse search. For each (V-line src, V-line dst), target_SOG = (dst_d − src_d) / dt, simulate, emit edge. Adds a 0.1-kn grid of early-terminal SOGs for the final block when d = L is reachable inside 6 h.
- Snap drift gone: every block's continuous Δd_snap = +0.000 nm. Bellman fuel = continuous-resim fuel **exactly** (Δfuel = 0.0 mt).
- Build time dropped from ~7–20 min (binary-searched SWS) to **108 s** (one simulate per dst).

### 2.6.4 Three-graph Bellman experiment

The free-DP and locked-DP graphs share the same node table by construction (verified by closing assertion in `build_locked_edges`). So the union of edge sets is a valid Bellman input — the combined optimum bounds both alone:

| Graph | Edges | Total fuel | Schedule | Solve |
|---|---:|---:|---:|---:|
| Free DP (per-square) | 3,308,940 | 366.769 mt | 206 edges | 2.91 s |
| Locked DP (SOG-locking, 6 h block) | 631,537 | 365.161 mt | 47 blocks | 1.89 s |
| **Combined (union)** | **3,940,477** | **362.965 mt** | **105 (74 free + 31 locked)** | **3.90 s** |

Both bounds satisfied: combined − free = −3.80 mt, combined − locked = −2.20 mt.

Schedule shape Bellman picked on the combined graph:
- 0–6 h: 4 free edges (fine-grained start, escapes the source corner)
- 6–264 h: 30 locked edges (bulk voyage at constant target SOG per 6 h)
- 264 h: 2 free edges (small re-alignment around an H-line)
- 264–280 h: 3 locked edges (including the new early-terminal edge that lands exactly at the sink)

The combined graph is the cleanest expression of the framework: a single Bellman gets you free-DP for fine-grained adjustments at boundaries and locked-DP for steady cruising — Bellman picks both where each helps.

### 2.6.5 Updated YAML voyage results

| Mode | Fuel | vs LP target (~372 mt) | vs free DP |
|---|---:|---:|---:|
| Free DP (per-square) | 366.769 mt | −1.4 % | — |
| Locked DP (SOG-locking) | **365.161 mt** | −1.8 % | −1.61 mt |
| **Combined** | **362.965 mt** | **−2.4 %** | **−3.80 mt** |

All three mode totals comfortably below the LP validation target. The combined gap to free is **5× larger** than the locked gap to free, which is the key result of the week.

---

## 3. Open Items / Next Steps

- **Sampling strategy for new voyages** — current Open-Meteo collector samples every 12 nm interpolated waypoint; with cell-canonical weather we can switch to "2–3 samples per 0.5° cell + segment endpoints" without losing fidelity (see one-pager §5).
- **Rolling horizon** — replan every 6 h with fresh forecast. Free, locked, and combined graphs all structured around 6 h V-bands, so replumbing is small.
- **Behavioural sanity checks** — zero-weather (closed-form fuel), constant-weather (constant SWS expected when SOG is locked), lock-monotonicity (fuel ↑ as lock_h ↑).
- **Soft ETA** — `BellmanSolver.best_sink(eta_mode="soft", lam=…)` is implemented; not yet exercised.
- **Combined-graph as default** — given the experiment above, the combined graph is strictly better. Worth promoting to the default `run_demo` and treating free/locked as ablations.

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

### 5.1 Three-graph comparison, YAML voyage (Persian Gulf → Strait of Malacca, ETA = 280 h)

| Metric | Free DP | Locked DP (SOG) | **Combined** |
|---|---|---|---|
| Total fuel | 366.769 mt | 365.161 mt | **362.965 mt** |
| Voyage time | 280.000 h | 280.000 h | 280.000 h |
| Schedule length | 206 edges | 47 blocks | 105 (74 free + 31 locked) |
| Average SOG | 12.120 kn | 12.120 kn | 12.120 kn |
| target SOG range | n/a (Δd/Δt grid) | [9.000, 13.000] kn | mix |
| mean SWS range | [9.78, 13.74] kn | [8.32, 14.23] kn | both |
| Edges built | 3,308,940 | 631,537 | 3,940,477 |
| Build time | 121 s | 109 s | 230 s (sum) |
| Solve time | 2.91 s | 1.89 s | 3.90 s |
| NaN edges skipped | 0 | 0 | 0 |

### 5.2 Sanity check on locked schedule (continuous resim, SOG-locking)

| | Bellman | Continuous |
|---|---|---|
| End t | 280.000 h | 280.000 h |
| End d | 3393.595 nm | 3393.595 nm |
| Total fuel | 365.161 mt | 365.161 mt |
| Δfuel | — | **+0.000 mt** |

Δd = +0.000 nm at sink. Per-block drift over the 47 blocks: **+0.000 nm everywhere** (constant-SOG trajectory is a straight line in (t, d), no accumulation by construction).

---

## 6. Questions for Supervisor

1. **Combined graph as the default** — the union (free + locked) gives 362.965 mt vs 366.769 (free) / 365.161 (locked). It's the strict better option for any single-shot run, and Bellman picks both edge types where each helps. OK to make it the default mode and treat free/locked as ablation studies?
2. **Sampling strategy** — with per-cell weather aggregation now in, the 12 nm interpolated-waypoint collector is over-sampling (most cells get 1–5 redundant waypoints averaged). Proposal: switch to "2–3 samples per cell-arc + segment endpoints" → ~half the API calls, same fidelity. Approve before I touch the collector?
3. **Rolling horizon next?** All three planning modes solid on a single forecast. RH = same graph, rebuild edges with fresh forecast at each decision step. Plan to do it on the rebuild?
4. **Luo comparison story** — our locked mode is now SOG-locking, exactly Luo 2024's policy, with sub-leg integration through cell + segment crossings (vs Luo's single-snapshot-per-stage). The 365.161 mt vs Luo's published numbers is paper-relevant — how do we want to frame it?
5. **Drift accumulation gone** — with SOG-locking the locked Bellman fuel == continuous-resim fuel exactly (Δfuel = 0.0 mt over 280 h). Worth a sentence in the paper as a method-side correctness result, or just internal sanity?

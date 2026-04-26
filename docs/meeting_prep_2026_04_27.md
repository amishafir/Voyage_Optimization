# Meeting Prep — Supervisor Meeting, Apr 27 2026

---

## 1. Action Items from Apr 20 Meeting

| # | Task | Status |
|---|------|--------|
| 1 | *(to be filled after Apr 20 meeting)* | TODO |
| 2 | | |
| 3 | | |

---

## 2. New Direction — Rebuild the DP Graph From Scratch

After the Exp 1 tie result (free ≈ locked within 0.25% under hard ETA) and the rounding-drift issues
in both Track A and Track B, the next step is **not** another experiment on top of the current
graph — it is to **reconstruct the graph itself from first principles**.

Reference: the legacy `Dynamic speed optimization/speed_control_optimizer.py` with its vertical /
horizontal `Side` boundaries. That design got several things right that the pipeline DP lost, and
several things wrong that we now know how to fix. The goal next week is to analyze it, keep what
works, and rebuild with the knowledge gained in the past few months.

### 2.1 What to analyze in the legacy DP

Three focus areas — the spine of any DP graph:

1. **Distance and time spacing**
   - How is the grid laid out? (`distance_granularity`, `time_granularity` from `ship_parameters.yaml`)
   - What do the axes mean? (rows = time in hours, cols = distance in nm)
   - How does `Side` (vertical/horizontal boundary) delimit the reachable region?
   - Where do the cumulative segment distances and time windows (`cumulative_segment_list`,
     `cumulative_time_list`) pin the boundaries?
   - What does the dense grid buy us vs the sparse forward-Bellman of the pipeline DP?

2. **Edge (Arc) creation**
   - `connect_sides()`: how are arcs enumerated between two sides?
   - The SOG filter (line ~551): an arc exists only if `(d2-d1)/(t2-t1)` rounds to a value in
     `speed_values_list`. What paths does this filter miss? What does it over-include?
   - SWS inverse: given target SOG + weather, binary-search for SWS; then `FCR = 0.000706 × SWS³`.
     Why inverse here but forward in pipeline DP? What does each approach get wrong?
   - Weather lookup per arc: line 577 always uses `weather_forecasts_list[0]` — we need to
     understand exactly where this comes from to rebuild it time-aware from scratch.

3. **Backward fuel calculation (Bellman relaxation)**
   - `connect_sides()` relaxes in-line: `d_node.minimal_fuel_consumption` is updated whenever a
     cheaper incoming arc is found (line ~523), and `minimal_input_arc` stores the optimal
     predecessor pointer.
   - `find_solution_path()` scans the destination column for the min-fuel node and walks
     `minimal_input_arc` pointers back to the source — that is the backward fuel / speed schedule
     reconstruction.
   - How does this compare to the pipeline DP's parent-pointer backtracking? Which is cleaner?

### 2.2 What we know now that the legacy version didn't

Knowledge accumulated since the start of the project that should shape the rebuild:

- **Time resolution matters enormously.** Legacy uses `dt=1h` which is fatal for 1–5 nm waypoint
  spacing (ceiling accumulation wipes out tens of hours per voyage). The rebuild must decouple
  `dt` from the spatial grid and let us dial it per route.
- **SWS vs SOG split is the cleaner decision variable.** Forward (SWS → SOG via physics) beats
  inverse (target SOG → binary-search SWS). Pipeline DP proved this; the rebuild should keep it.
- **Time-varying weather is non-negotiable.** Legacy hard-codes `weather_forecasts_list[0]`.
  The rebuild must index by forecast hour from day one.
- **Speed resolution must be independent of geometry** (the Luo lesson — §4.8 of Apr 20 prep).
  Legacy couples speed resolution to grid spacing via the SOG filter; the rebuild must keep
  speed as an explicit config knob.
- **Waypoint-cell collapsing** (brainstorm from Apr 20 §3): consecutive waypoints inside the same
  weather cell with the same heading carry no new physical information. The new graph should
  treat a "decision unit" as `(heading-segment) × (weather-cell)` rather than raw waypoint count.
- **Ceiling-rounding is a fundamental gotcha.** The rebuild must decide once, globally, how to
  handle travel-time discretization — continuous travel time per edge with a single ceiling at
  the end, or a fixed time-slot grid with a tighter dt.
- **Hard ETA dominates the optimum.** The rebuild should natively support both hard ETA (graph
  boundary) and soft ETA (λ penalty term) as first-class modes, not bolt-ons.

### 2.3 Proposed analysis plan for the week

1. **Read the legacy DP end-to-end** — write a one-page walkthrough of: graph init, side BFS,
   arc creation, weather lookup, relaxation, path extraction. No rewriting yet.
2. **Extract invariants** — what is actually necessary (cumulative segment distances, speed
   range, FCR model) vs what is implementation accident (dense array, Sides BFS, SOG-matching
   filter, single-window weather).
3. **Sketch the new graph** — axes, node identity, edge semantics, weather lookup, solver,
   backtrack. Decide: explicit `(waypoint, time_slot)` sparse like pipeline DP, or return to a
   dense `(distance, time)` grid with better spacing, or a hybrid stage-based layout à la Luo.
4. **Write the skeleton** — data classes (Node / Arc / maybe no Side), edge-building function,
   relaxation loop, backtrack. Run on Route D at SH=0 as a smoke test.
5. **Sanity-check against pipeline DP** — same route, same departure, same config → same fuel
   within rounding tolerance.

### 2.4 Open design questions (to raise in the meeting)

- **Graph topology**: time-major (rows = hours, stages go down) like legacy, or waypoint-major
  (columns = route position, time floats) like pipeline? Or a true lattice with both axes
  equally first-class?
- **State variable**: `(time, distance)` like legacy, `(waypoint_idx, time_slot)` like pipeline,
  or `(stage, remaining_distance)` like Luo? Each has pros and cons — which fits our use cases
  (hard + soft ETA, time-varying weather, rolling horizon) best?
- **Decision variable**: keep SWS (forward physics, pipeline style), or reintroduce SOG with a
  cleaner inverse? The SWS/SOG split story is a paper contribution — the graph should honor it.
- **Weather indexing**: by `(node_id, forecast_hour)` like pipeline, by `(segment_id, time_window)`
  like legacy, or by `(cell_id, stage)` like Luo? The collapsing brainstorm suggests `(cell × heading)`
  is the natural decision-unit anyway.
- **Backtrack representation**: `minimal_input_arc` pointer (legacy) vs parent dict (pipeline).
  Same thing really, but the legacy Arc carries SWS/SOG/FCR/Travel_time on it, which makes
  reconstruction cleaner.

---

## 3. Progress This Week — Graph Rebuild Stood Up End-to-End (Apr 22–23)

Design session + implementation landed the first working cut of the rebuilt DP graph in
`pipeline/dp_rebuild/`. Five modules, ~1.7 k lines. Full build + validate + render takes a
few minutes on the YAML example route (3,393 nm / 280 h, the Persian Gulf → Malacca voyage
from Table 8). Details in `docs/thesis_brainstorm.md` §14–§15.

### 3.1 Locked design — Q1–Q10 multiple-choice session (§14.14)

Answered 10 structural questions to pin the graph spec. Key decisions:

| Q | Decision |
|---|---|
| Q1 — Edge destination | Every edge terminates at the **first boundary line** it crosses (no line-skipping). |
| Q2 — V-line cadence | Fixed `dt_h` (default 6 h) + synthetic terminal line at `t = ETA`. |
| Q3 — H-line placement | At **course changes ∪ weather-cell boundaries** (physical changes only). |
| Q4/Q5 — Node density | V lines: every ζ=1 nm across distance. H lines: every τ=0.1 h across time. |
| Q6 — Speed | SOG is the edge geometry; **SWS recovered by inverse** under source-square weather. |
| Q7 — Speed range | Continuous `[v_min, v_max]` — drop legacy's exact-match SOG filter. |
| Q8 — Weather per edge | Constant between nodes by construction (H lines at every cell boundary). |
| Q9 — ETA | Both hard ETA and soft ETA (λ penalty) as first-class modes. |
| Q10 — Source | Single node at (0, 0). |

Plus a convention flip (Apr 23) to geometric labels: **V = constant-time (vertical in the
plane), H = constant-distance (horizontal in the plane)**. Matches the whiteboard picture.

### 3.2 YAML integration — `Q_yaml_1..5` (§14.17)

Switched default from the 4000/400 toy to the YAML's **3,393.24 nm / 280 h** route.
- `load_route.py` parses `weather_forecasts.yaml` into `Route / ForecastWindow / Segment`.
- `synthesize_multi_window(window_h=6)` replicates the single YAML window into 47 equal
  windows so the graph exercises time-varying-weather infrastructure from day one.
- Dropped `current_angle` (it's a derived duplicate of `current_dir`).

### 3.3 HDF5 weather loader — `h5_weather.py` (§15.13)

Found the weather data on the laptop (servers were in an ICMP-only VPN state that morning).
`pipeline/data/voyage_weather.h5` — 279 real interpolated waypoints with (lat, lon, segment,
distance), 12 sample hours of actual weather, 192-hour forecast matrix per node. Matches the
YAML route exactly (12 segments, 3,395.84 nm HDF5 vs 3,393.24 nm YAML — rounding).

`VoyageWeather` exposes:
- `segment_boundaries_nm()` / `weather_cell_boundaries_nm(grid_deg)` — drive H-line placement
- `weather_at(d, sample_hour, forecast_hour)` — for both actual and predicted lookups
- `nearest_waypoint_in_segment(d, seg)` — critical for correctness (see §3.6 below)

### 3.4 Node + edge construction

| Module | What it does |
|---|---|
| `build_nodes.py` | V lines from `v_line_times_from_route`; H lines from `h_line_distances_from_h5` (segments ∪ 0.5° marine cells ∪ terminal). GraphConfig decoupled from any hard-coded route. |
| `build_edges.py` | Q1 + Q7 edge enumeration; each Edge carries `weather` (from square center), `heading_deg`, `sws` (via `shared.physics.calculate_sws_from_sog`), `fcr_mt_per_h`, `fuel_mt`. NaN weather (Port B coastal gap) propagates to NaN fuel cleanly. |

**Final numbers** (YAML route, ETA=280 h, dt_h=6, ζ=1, τ=0.1, v∈[9,13] kn):

| | Value |
|---|---|
| V lines | 47 |
| H lines | 146 (11 segment + 134 marine-cell + 1 terminal) |
| Nodes | 568,512 |
| Edges | **3,344,829** |
| NaN-fuel edges | 4.68% (Port B) |
| SWS range | [8.25, 14.55] kn |
| FCR range | [0.40, 2.18] mt/h |
| Fuel per edge | [0.057, 6.37] mt (mean 2.07) |
| Full-graph build time | ~3 min |

### 3.5 Structural validator — `validate_graph.py` (§15.16)

Three checks, all passing on the final graph:
- **C1 Square uniformity** (6,862 squares) — every (V band × H band) square has one and only
  one `(segment, cell, forecast_window)` triple.
- **C2 Edge weather fidelity** (2,000 sampled) — every edge's stored `Weather` equals the
  weather at the center of the square the edge enters.
- **C3 Topology basics** — source unique at (0,0), sinks at d=L, SOG ∈ [v_min, v_max],
  Δt > 0, Δd > 0, first-line-crossed rule.

### 3.6 Two real bugs the validator caught

1. **Boundary-tie weather bug.** A source sitting exactly on a boundary line hit a
   `nearest_waypoint` tie; the tie-break picked the wrong-side waypoint for the square the
   edges actually enter. 44% of sampled edges stored wrong-side weather.
   **Fix**: probe weather at the *center* of the enter-square, not at the source's exact
   coordinate.

2. **YAML ↔ HDF5 segment-boundary mismatch (10 nm off).** The HDF5 has a 19.74 nm gap
   between the last waypoint of segment 0 (d=204) and the first of segment 1 (d=223.74).
   My original midpoint heuristic placed the segment boundary at **213.87**, but the YAML's
   cumulative-segment-length semantic (and the paper's Table 8) puts it at **223.86**. Every
   one of the 11 segment transitions was ~10 nm early → ~110 nm of the route was mis-segmented
   → wrong heading in any downstream physics on those stretches.
   **Fix**: segment-boundary H line at the first waypoint of the new segment (223.74 ≈ YAML
   223.86 within rounding); `weather_at` made segment-aware so gap-zone lookups read the
   correct-side waypoint.

### 3.7 Visualisation — `visualize_squares.py`

A matplotlib scatter of a 3×2 square patch around the segment 0/1 boundary showing:
- Each square's `(segment, cell, window, sample_hour)` label + the 6 weather fields.
- White-filled dots on every V-line / H-line node (ζ=1 nm and τ=0.1 h visible).
- Three sample edges with physics annotations — one of each type:
  - **V→H** (source on V line → destination on next H line)
  - **H→V** (source on H line → destination on next V line)
  - **H→H** (source on H line → destination on next H line)
- Footer note: **V→V is not realised in our graph** — max H-line gap (48 nm, between
  d=1875.58 and d=1923.58) is smaller than `v_max × Δt_h = 78 nm`, so every 6 h run at ≥ 9 kn
  crosses at least one H line.

Axis convention: x = time left→right, y = distance top→bottom (matches the whiteboard
picture — ship starts at top-left, moves right and down).

### 3.8 What the rebuild already delivers

- **Clean separation of the three independent axes** (ζ, τ, `dt_h`) — no more Luo-style
  speed/geometry coupling.
- **Weather correctly indexed per (segment, cell, forecast window)** — with validator proof.
- **Ship physics hooked in** via `shared.physics` (no new physics code; reuses the existing
  thesis implementation).
- **Hard and soft ETA both modelled as first-class sink policies** (sink column + optional λ).
- **Every commit reproducible**: `build_nodes.py` → `build_edges.py` → `validate_graph.py`
  → `visualize_squares.py`, all deterministic and independently runnable.

### 3.9 What's still missing (next-week work)

- **Forward Bellman solver** — consume the 3.34 M edges to produce a min-fuel path. The
  edge records already carry everything the DP needs (fuel per edge, SWS, SOG).
- **Backtrack + schedule reconstruction** — arc-as-record (legacy style) or parent-dict
  (pipeline style). Decide in the meeting.
- **Sink dedup** — 47 intersections at (t, d=L) appear in both the terminal H-line column
  and each V line. Harmless for validation, will need a canonical pick for the DP terminal.
- **NaN-weather policy at Port B** — currently edges with NaN fuel are kept but unusable
  in the DP. Options: (a) prune, (b) clamp to nearest valid waypoint, (c) use a default.
- **Rolling horizon mechanics** — graph is static right now; need to decide how to
  parameterise `sample_hour` / `forecast_hour` per decision cycle.
- **Sanity checks §14.11** — degenerate-lock check, lock-monotonicity, zero-weather.
  C1 / C2 / C3 handle structural correctness; these add behavioural correctness.

---

## 4. Supporting Material — Carry-Over From Apr 20

Still relevant if the rebuild discussion leaves time:

- Exp 1 Track A full matrix (SH=60, soft ETA) is ready to run but deprioritized in favor of
  the rebuild.
- Track B anomaly (Luo lattice beats free DP by 8 mt) remains unexplained — the rebuild may
  resolve it naturally by eliminating the free DP's ceiling-accumulation drift.
- Exp 2 rolling horizon is on hold until the new graph is in place.

---

## 5. Data Collection Status (Apr 23)

| Server | Status | exp_b (138 wp) | exp_d (391 wp) | exp_c (968 wp) | Uptime |
|--------|--------|---|---|---|--------|
| Shlomo1 | Back online (~Apr 15) but **no collection running** — tmux wiped by reboot | — | — | — | 8 d |
| Shlomo2 | ✅ Collecting | 55 M, updated Apr 23 08:03 | 153 M, updated Apr 23 08:10 | 96 KB (stalled) | 48 d |
| Edison | ✅ Collecting | 55 M, updated Apr 23 05:03 (=08:03 IST) | 153 M, updated Apr 23 05:10 | 90 KB (stalled) | 45 d |

Growth since Apr 13 (10 days): exp_b +18 M, exp_d +46 M (both servers identical). exp_c
remains dead.

**Action item**: kick off collection on Shlomo1? It's reachable again but idle.

---

## 6. Questions for Supervisor

1. **Rebuild topology — locked, but worth sanity-checking.** We went with explicit
   `(time, distance)` squares bounded by V and H lines (§14.15). Keeps both axes first-class,
   no waypoint-major or remaining-distance bias. Anything about this we should reconsider
   before building the solver on top?
2. **Segment-boundary placement.** We now use the first waypoint of each new segment
   (d=223.74 for the 0→1 join) to match the YAML cumulative distance (223.86) within
   interpolation rounding. Legacy midpoint was 213.87 — off by ~10 nm. Comfortable with
   this being the canonical rule?
3. **Fuel formula for the rebuild.** Using `shared.physics` (forward-physics SOG model +
   binary-search inverse for SWS + `0.000706 × SWS³` FCR). Same physics the existing pipeline
   uses. Any concern about staying with this or want to revisit the FCR coefficient /
   inverse tolerance?
4. **V→V edges don't exist in our graph.** Max H-line gap is 48 nm; `v_max × Δt_h = 78 nm`
   guarantees every 6 h edge hits at least one H line. This is an honest consequence of
   dense weather cells. Worth mentioning in the paper as a structural property, or a side
   note?
5. **What's in the first solver run?** Forward Bellman on the rebuilt graph, same YAML
   example, compare total fuel to legacy/pipeline DP for a sanity check. Is that the right
   first target, or go straight to Exp 1 / Exp 2 on the new graph?
6. **Where does this rebuild land in the paper story?** §14.16/§15 describes "one graph,
   three planning modes" (hard-ETA, soft-ETA, rolling-horizon all share the same V/H
   structure). Does that reframing replace the "ours vs Luo" pitch, or complement it?

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

## 3. Supporting Material — Carry-Over From Apr 20

Still relevant if the rebuild discussion leaves time:

- Exp 1 Track A full matrix (SH=60, soft ETA) is ready to run but deprioritized in favor of
  the rebuild.
- Track B anomaly (Luo lattice beats free DP by 8 mt) remains unexplained — the rebuild may
  resolve it naturally by eliminating the free DP's ceiling-accumulation drift.
- Exp 2 rolling horizon is on hold until the new graph is in place.

---

## 4. Data Collection Status

| Server | Status | Route B (138 wp) | Route D (391 wp) | Uptime |
|--------|--------|-------------------|-------------------|--------|
| Shlomo1 | | | | |
| Shlomo2 | | | | |
| Edison | | | | |

---

## 5. Questions for Supervisor

1. **Topology choice**: is there a preference between the three candidate layouts (time × distance
   grid, waypoint × time_slot sparse, stage × remaining_distance lattice)? Each matches a different
   paper the literature already tells stories about.
2. **Keep the Sides abstraction?** The legacy `Side` boundary concept is elegant for segment-based
   weather lookup, but adds complexity. Worth preserving or drop it in favor of per-node
   enumeration?
3. **How time-aware must the new graph be from day one?** Full forecast-hour indexing + rolling
   horizon support in the first cut, or staged (static first, then time-varying, then RH)?
4. **Where does this land in the paper story?** If the rebuild cleans up rounding drift and
   unifies the three solvers, do we reframe the paper around "one graph, three planning modes"
   rather than "ours vs Luo"?

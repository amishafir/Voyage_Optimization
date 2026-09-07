# Design — Realigning the graph partition to the sampling

Companion to [meeting_prep_2026_09_07.md](meeting_prep_2026_09_07.md) and
`weather_resolution_audit_FULL_2026_09_06.html`. This document specifies *where* the changes land, in
what order, and what verification each step needs. It does not re-argue the findings.

---

## 0. Three facts that set the scope

**0.1 The C++ engine is the production path.** The paper's reported results come from
`paper_workspace/results/2026_08_11_chain_sweep_v2_cpp/`. `pipeline/dp_cpp/src/` is 3,487 lines and
mirrors the Python solve path function-for-function. **Every change below lands twice.** Treating the
Python side as "the implementation" and the C++ as a port is how the two drift; the C++ is what produced
the numbers under discussion.

**0.2 Both regression harnesses break by construction.** Verification is golden-master:

| Harness | Baseline | Breaks because |
|---|---|---|
| Python | `pipeline/dp_rebuild/goldens/{quick,full}.json` | stores `schedule_sha256` + exact fuel strings |
| C++ | `pipeline/dp_cpp/reference_runs/*.csv` (3 files), driven by `tests/regression.sh` | per-edge CSV comparison |

Any change to the partition changes every node id, every edge, and therefore every hash. **The existing
goldens cannot validate this work — they can only report that it happened.** §5 proposes what to use
instead.

**0.3 The paper's §4 already has the right vocabulary.** Line 442 already says *"the rectangular areas
defined by the vertical and horizontal lines… each point represents a location and time at which the
heading of the vessel and the sea conditions are assumed fixed"*, and line 435 already notes that heading
is fixed between consecutive distance lines. The structure is correct. What changes is the **rule that
places the distance lines**, plus the word "cell" and the claim that the assumption is physical.

---

## 1. The invariant to establish

> A distance line is placed wherever the **cost coefficient** changes. That has exactly two causes: a new
> weather reading, and a change of course. Inside one rectangle the graph holds **one reading and one
> heading**, so conditions are constant there *in the model's information*, not in the atmosphere.

```
H = { d(w) : w ∈ weather sample points } ∪ { d(c) : c ∈ course-change points } ∪ { L }
V = { 0, Δt, 2Δt, … } ∪ { T }
```

Justification, which is stronger than "it is tidier": with the cost coefficient fixed across a rectangle,
FCR is convex in speed, so a constant speed across it beats any varying profile achieving the same
transit time. The partition on which the coefficient is piecewise constant is therefore **the optimal
control partition** — no finer partition can improve the solution, and any coarser one forfeits
optimality.

In the current data the course-change points are a subset of the sample points (`generate_waypoints`
emits every control point with `is_original=True`), so the union collapses to the waypoint set: **131 on
route 1, 389 on route 2.**

---

## 2. Code — Python (`pipeline/dp_rebuild/`)

| Site | Change | Notes |
|---|---|---|
| `nodes.py:160` `h_line_distances_from_geo` | **Replace.** New `h_line_distances_from_waypoints(cfg, waypoints)` returning the cumulative rhumb distances of the sample points. No crossings, no set-union, no dedupe. | The old function stays for the flag-gated comparison in §5, then goes. |
| `nodes.py:206-247` τ-feasibility filter | **Demote to assertion.** Verified 0/130 and 0/388 segments fail under uniform spacing. A firing now indicates an upstream problem. | This is what removes the ETA→grid coupling. Keep the `feasible()` predicate; drop the drop-loop. |
| `nodes.py:104,137` `..._from_route`, `..._from_h5` | **Delete.** Already dead — legacy generators. | Confirm no callers outside `__main__`. |
| `frame.py:45-59` `Frame` | Replace `grid_deg` with `segment_d: List[float]` (the H-line array) and drop `weather_cell_nm`. Add `segment_index(d) -> int`. | `weather_cell_nm=30.0` at `:165` is already marked "legacy; ignored". |
| `frame.py:114` `cell_weather_at` | **Replace** with `segment_weather_at(d, sample_hour, forecast_hour)`: `k = bisect_right(h_line_distances, d) - 1`, then read waypoint `k`'s stored row. | Verified exact: returns the departing segment at every H-line on both routes. No `floor()`, no derived coordinate. |
| `frame.py:131` `paper_heading_at` | **Replace** with `heading_at_segment(k)` = `rhumb_bearing(W[k], W[k+1])`. Removes the `position_at_d` call. | **This is the segment-boundary heading fix.** Also ends the dependence on Luo's 12-value `ship_heading` table. |
| `frame.py:143` `from_route` | Take the waypoint list as the polyline; drop `grid_deg`. | See §4 on which waypoints. |
| `weather.py:386` `_build_cell_index` | **Delete.** | |
| `weather.py:399` `cell_weather` | **Delete.** Removes the scalar-mean-of-magnitudes + circular-mean-of-directions aggregation, and `round(mean(BN))`. | Three findings die here. |
| `weather.py:463` `cell_weather_at_d` | **Replace** with `weather_at_waypoint(node_id, sample_hour, forecast_hour)` — a direct `_row_for` lookup. | |
| `weather.py:296-332` `nearest_valid_waypoint_in_segment` | **Delete** from the solve path. Every segment now has its own reading. | Retain a NaN guard: a NaN row is a data defect, not something to substitute around silently. |
| `weather.py:78` `_circular_mean_deg` | Keep only if still used elsewhere; otherwise delete. | |
| `atomic_edges.py:163-167` weather-dict conversion | Unchanged in form, but fed from the segment lookup. | Note the duplicate conversion flagged at `:158-161` — fold it now. |
| `atomic_edges.py:294` pricing | `frame.segment_weather_at(src_d, …)` | |
| `atomic_edges.py:303-311` NaN walkback | **Reconsider.** It steps to older `sample_hour` while holding the lead fixed, moving the valid time earlier. With no fallback chain ahead of it, this becomes the only NaN path. | Decide: fail loudly, or keep with a staleness cap and a counter. |
| `geo_grid.py:126` `rhumb_grid_crossings` | Off the solve path. Keep for the figures. | |
| `geo_grid.py:216` `cell_index` | Off the solve path. Keep for the figures. | |
| `geo_grid.py:222` `position_at_d` | Off the **pricing** path. Still used by `SR_main.py:33`-style output/plotting. | The `d <= cum + seg + 1e-9` boundary rule at `:246` should still be fixed for the plotting path. |
| `luo_main.py:167,214,515` | Same partition, same lookup. **The baseline must be exercised on the identical partition** or the comparison is meaningless. | |
| `SR_main.py:159-161` band derivation | Unchanged — but note it no longer feeds the H-line set, which is the point. | |

---

## 3. Code — C++ (`pipeline/dp_cpp/src/`)

One-to-one mirror. Sites confirmed by grep:

| Site | Mirrors |
|---|---|
| `nodes.cpp:49` `h_line_distances_from_geo` | `nodes.py:160` |
| `nodes.cpp:~90-102` drop-loop | `nodes.py:206-247` |
| `frame.cpp:30` `Frame::cell_weather_at` | `frame.py:114` |
| `frame.cpp:36` `position_at_d` for heading | `frame.py:131` |
| `weather.cpp` / `weather.hpp` (353 + 182 lines) | `weather.py` aggregation + fallback |
| `geo_grid.cpp:48` `rhumb_grid_crossings`, `:109` `cell_index` | demote both |
| `atomic_edges.cpp:56,63` pricing + walkback | `atomic_edges.py:294,303` |
| `luo_main.cpp:119,125,204,210` pricing; `:241,275` `position_at_d` | `luo_main.py` |
| `SR_main.cpp:33` `position_at_d` | output path |

**Cross-engine equivalence is the real test here.** The repo has prior art for it — the streaming
refactor was validated bit-exact across phases 0–2. Re-establish that: Python and C++ must agree
bit-exactly on the new partition before either is trusted, on at least one route × one departure.

---

## 4. Collection (`pipeline/collect/`) — future runs only

None of this can be applied retrospectively. Rolling-horizon needs forecasts issued in real time, so a
re-collection benefits **perfect-foresight runs only**.

| Site | Change | Why |
|---|---|---|
| `waypoints.py:37-66` `interpolate_geodesic` | **Interpolate along the rhumb line**, not the great circle. | Today the samples sit off the sailed legs by ≤1.4 NM (route 1) / ≤4.1 NM (route 2), and bearings drift within a leg by a median 0.52° / 4.32°, up to 6.30°. Fixing this makes "heading constant per leg" true *and* puts the samples on the path. |
| `waypoints.py:127` `num_intermediate = int(d/interval) - 1` | Drop the `-1`; distribute the remainder. | Twelve route-1 segments run to 48.99 NM — 446 NM, 13.1% of the route. |
| `collector.py:79-85` request params | Add `cell_selection=sea`. | Forecast API defaults to `land`; wind near coastal ends may be mis-sourced. |
| `collector.py:79-85` | Decide whether to pin `models`. | Unpinned gives ECMWF ~9 km. Pinning GFS would make the original §5.1.1 claim true but *lower* the resolution. Pinning is about reproducibility, not quality. |
| `collector.py:128-141` response parse | **Store the resolved `Latitude()`/`Longitude()`/`Model()`.** | Currently discarded, so the sample→tile offset is unrecoverable and the served model is unprovable. Three extra columns. |
| `collector.py:176-177` `forecast_hour` | Define it as **issue-relative lead** in the schema and assert on load (`run_rh.py:69-81`). | Collector writes process-start-relative; RH reads lead. The shipped file satisfies both only because of how it was run. |

---

## 5. What breaks, and how to proceed safely

The goldens cannot certify this change, so the change must certify itself.

**5.1 Flag-gate the partition.** Add `--h_lines={geo,waypoint}` to `SR_main`, `luo_main`, `run_rh` and
the C++ equivalents, defaulting to `geo`. Both partitions then run on identical inputs and the delta is
measurable rather than asserted.

**5.2 Measure the boundary-probe bug on the old partition first.** This is the one piece of "throwaway"
work I would still do. The `floor()` coin-flip and the segment-boundary heading affect **the published
numbers**. Fix them under `--h_lines=geo`, re-run the v2 chain sweep, and compare `gap_pct` against
`2026_08_11_chain_sweep_v2_cpp`. If the published 1.80% / 2.60% move materially, that needs a correction
note in the paper regardless of what happens to the partition. If they do not, that is a reassuring
sentence you can write. Either way you want to know before Tal takes the paper further.

**5.3 Then run the partition A/B**, per route:

| Check | Expectation |
|---|---|
| H-line count | route 1: 163 → 131; route 2: 121 → 389 |
| Lattice size | route 1 ≈ 0.8×; route 2 ≈ 3.2× |
| τ-filter drops | 0 (assertion never fires) |
| Python ↔ C++ | bit-exact |
| `gap_pct` movement | unknown — this is the result, not a check |

**5.4 Re-freeze both harnesses** only after the delta is accepted, and record in `goldens/*.json` which
partition the baseline describes. The `engine` field already exists for this purpose.

**5.5 Then the time block**, per route and separately measured: route 1 is cheap (1.6× at 3 h, 4.9× at
1 h), route 2 is not (6.4× / 19.3×). Keep the **re-plan cadence at 6 h** — that is the forecast issue
cycle and a different quantity from the constancy block. `run_rh.py` currently binds both.

---

## 6. Paper

Already applied today in §5.1.1 (commit `62befa8`): source granularity, wind model, MFWAM resolution,
horizon wording, 170-day window, three GFS attributions.

| Line | Current | Change |
|---|---|---|
| 114 | speed may change at "each $0.5\degree$ weather-cell crossing and each heading change" | "at each weather sample point and each heading change" — the union rule |
| 220 | "each weather-cell crossing, heading change, or six-hour time block" | same substitution |
| 245 | vessel "travels on a great circle between each pair of consecutive waypoints" | The solver sails rhumb legs, and line 417 already asserts constant heading per segment — the two are mutually exclusive. Resolve toward rhumb. |
| 247 | conditions "assumed fixed for each discretized time and space unit… cells of $0.5\degree\times0.5\degree$"; "chosen because it is used by global weather and forecast services" | Replace with the sampling-interval definition. Delete the justification clause: it is a category error, and no source uses 0.5°. |
| 274, 364 | `V_g = V_s − ΔV_wind − ΔV_wave + V_{c,∥}` | Neither half matches the code: one combined BN-driven loss, and the current enters as a 2-D vector magnitude. Rewrite the equation. |
| 358–359 | wave loss "scales with significant wave height $H_w$ and the beam-to-length ratio" | False, and contradicts line 247. Waves enter only via BN. |
| 422 | "Each time the route crosses a $0.5\degree$ latitude or longitude line, a new subsegment starts" | Subsegments start at each sample point and each heading change |
| 435 | "between any pair of consecutive distance lines the heading is fixed and it is in the same cell" | "…the heading is fixed and a single weather reading applies" |
| 442 | "rectangular areas… heading and sea conditions are **assumed** fixed" | Already correct in structure. Make the epistemic status explicit: constant in the model's information. |
| 528 | `Figure X` placeholder | fix |
| 756 | `NM` used as a speed unit | kn |
| 773–775 | MFWAM bullet | Decide: delete, or keep with "collected, not consumed" — `H_w` reaches the cost function and is discarded |
| 793, 1089 | "86% of hourly queries returned identical data" | Cannot be reconstructed and appears contradicted by the hourly series. It is what justifies the 6 h re-plan cadence — needs rework toward the **issue cycle** argument, which survives |
| 796–798 | "25 departure times… 3 ETA levels… 150 instances" | Describes an experiment absent from code and results. Needs a decision, not an edit |
| 63, 121, 125 | "nineteen voyages" | 35 (13 + 22) |
| Results tables | — | Regenerate after §5. `gap_pct`, per-voyage fuel and the SR–Luo comparison all move |

---

## 7. Ordering

```
A. Correctness fixes on the OLD partition  ──► measure vs published        (§5.2)
      boundary probe · segment heading · vector current mean
                    │
                    ▼
B. Flag-gate the new partition, both engines                               (§5.1)
      Python + C++ · bit-exact cross-check
                    │
                    ▼
C. A/B the partition, per route                                            (§5.3)
      route 1 free · route 2 is a runtime decision
                    │
                    ├──► accept ──► re-freeze goldens                      (§5.4)
                    │
                    ▼
D. Per-route time block                                                    (§5.5)
                    │
                    ▼
E. Paper: method text, Eq. (eq:sog), results tables                        (§6)

Independent of A–E, any time:  collection fixes (§4) · §5.1.1 wording · line 528, 756, 63/121/125
```

Paper §6 must follow C, not lead it: the method text describes a partition that does not exist yet, and
the results tables cannot be regenerated before the partition is fixed.

---

## 8. Not changing

- The **(t, d) node formulation** and node-first arc enumeration.
- The **rhumb geometry** — it reproduces Luo's table to 0.36 NM over 3,393 NM.
- The **streaming solver** and `bellman`.
- The **rolling-horizon vintage selection** — no lookahead leak was found; the planner never reads a
  forecast issued after the decision time.
- The **physics module**, other than the dead `wave_height` parameter. `Vg = |V_w·ĥ + V_c|` and the
  Kwon-style coefficients are faithful to the source paper; the cross-current SOG inflation is inherited,
  not introduced, and changing it is a modelling decision rather than a bug fix.

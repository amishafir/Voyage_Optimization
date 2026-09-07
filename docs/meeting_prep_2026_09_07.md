# Meeting Prep — Monday 2026-09-07 (Ami ↔ Tal)

Continues from [meeting_prep_2026_08_31.md](meeting_prep_2026_08_31.md).

Sections 4–6 of the Aug-24 and Aug-31 preps were never filled in, so both decision tables are carried
forward again below. Section 1 is new material: the discretization question was taken to the source APIs
and to the code, and **the premise the whole investigation rested on turned out to be wrong**.

Supporting documents:

- `docs/weather_resolution_audit_2026_09_06.html` — focused: sources, parameter map, computation chain,
  the rectangle. Full version with all twelve findings, the per-route graph redesign and the paper-impact
  table retained at `docs/weather_resolution_audit_FULL_2026_09_06.html`.
- [h_line_realignment_design.md](h_line_realignment_design.md) — **where the changes land**: every code
  site in both engines, the collection fixes, the verification strategy, the paper edits, and the
  dependency order. Summarised in §1H below.

---

## 1. The discretization question, resolved

### 1A. All three fields arrive at the *same* resolution — the premise was false

Established by probing the API's resolved cell coordinates (both endpoints, 50.4°N 41°W, 2026-09-06),
not by reading documentation. Open-Meteo performs no spatial interpolation and reports the cell it used,
so sweeping coordinates recovers each grid exactly.

| Endpoint | Grid recovered | Cell at 12.8°N | Cell at 52.4°N |
|---|---|---|---|
| Marine (waves, currents) | regular, **exactly 1/12°**, centres at (k+½)/12 | 5.00 × 4.88 NM | 5.00 × 3.05 NM |
| Forecast (wind) | **octahedral reduced Gaussian** — rows 0.0703° apart, within-row longitude 0.1584°, point count varying by row | ≈4.22 × 9.3 NM | ≈4.22 × 6.06 NM |

**All three fields arrive at ≈0.08°, or 3–5 NM.** Not 0.25° for wind against 0.08° for the marine fields.
There is no heterogeneity to reconcile, and the question "how do we compose three granularities into one
square" has no subject.

- [x] **Three corrections to the Aug-31 doc itself**, which should be recorded rather than quietly dropped:
  - §1A's table gives wind as GFS 0.25°. `models` is never set, so `best_match` applies and serves the
    highest-resolution applicable model — over open ocean that is ECMWF IFS HRES at ~9 km. Confirmed by
    grid probing; none of `gfs_seamless`, `ecmwf_ifs025`, `icon_global` matches either the grid or the values.
  - §1A says the grids are "not nested, not mutually aligned". Half wrong: the marine grid is regular and
    edge-registered on multiples of 1/12°, so it tiles cleanly against any box drawn on that lattice. It is
    the **wind** grid that aligns with nothing — Gaussian rows with a varying point count cannot tile
    against the marine grid, a regular box, or itself.
  - §1B's table ("~36 native cells per 0.5° square for currents and waves, ~4 for wind") describes an
    operation that never happens. We never hold fields, so we never average native cells. We average the
    **point samples that landed in the box** — 1 on route 1, 4 on route 2.

### 1B. Wave height is a dead input — the MFWAM correction is moot

`wave_height` is read from the weather dict, spatially averaged, threaded through the NaN fallback,
extracted at every pricing call, passed to `calculate_speed_over_ground` as a named argument — and never
referenced in the function body. Executed across a physically absurd range:

```
wave_height =  0.0 m  →  SOG = 12.679868708 kn
wave_height = 99.0 m  →  SOG = 12.679868708 kn
```

Bit-identical. **This is the method, not a defect.** The Yang2020 / Kwon-style formulation carries sea
state through the Beaufort number, whose scale definition already encodes a characteristic wave height.
There is no slot for `H_w` in these coefficients, so collecting significant wave height was never going to
reach the speed model.

- [x] So the MFWAM 0.25° → 0.08° fix, open since Aug 24, corrects a citation about **data we collect and
  discard**. Worth doing, changes nothing computational.
- [ ] **But the paper contradicts itself on this**, and one of the two statements has to go:
  - Line 247: "wave condition measured in **Beaufort units**" — matches the code.
  - Line 358: "the wave added-resistance loss scales with **significant wave height H_w and the
    beam-to-length ratio**" — false; neither quantity appears in the speed path.
- [ ] Decide whether the §5.1.1 wave bullet is deleted or kept with an explicit "collected, not consumed".

### 1C. What the model actually consumes

| Stored column | Enters at | Status |
|---|---|---|
| `wind_direction_10m_deg` | step 1 → θ → C_β | used |
| `beaufort_number` | steps 3, 5, 9 — C_β, C_form, BN≥5 rule | used |
| `ocean_current_velocity_kmh` | step 8 — vector synthesis | used |
| `ocean_current_direction_deg` | step 8 — vector synthesis | used |
| `wind_speed_10m_kmh` | never in a formula, but the **sole** determinant of BN | indirect |
| `wave_height_m` | extracted and passed every call, never referenced | **dead** |
| wave direction | never requested — φ doubles as the weather angle, so waves are assumed to run with the wind | absent |

`FCR = 0.000706 · V_s³` consumes **no weather at all**. Weather has exactly one point of entry into the
objective: the solver fixes an arc's SOG from distance and duration, inverts `V_s = g⁻¹(V_g; w)` by binary
search, and prices the resulting SWS cubically. Of the four values reaching that inversion, one is an
integer 0–12, two describe the current, one is a bearing. **That is the entire weather content of the cost
function**, against which §5.1.1 spends three bullets on resolution, cadence and horizon.

### 1D. The unit is a rectangle, and no achievable rectangle has constant weather

Two things were being conflated: the scale at which the forecast is **genuinely constant** (a property of
the data), and the scale at which **our sampling is entitled to assert it**.

- Genuinely constant: within one source tile. A **rectangle**, 5.00 NM tall at every latitude and
  5.00·cos(lat) NM wide — 4.88 NM on route 1, 3.05 NM on route 2. Never a square.
- What we can assert: nothing below our own sampling interval — 25 NM on route 1, 5 NM on route 2.

| | route 1 | route 2 |
|---|---|---|
| Sampling interval | 25 NM | 5 NM |
| Source tiles a segment crosses | median **8** (6–16) | median **3** (2–5) |
| Segments confined to one tile | **0.0%** | **0.0%** |

- [x] **No practical segment stays inside one tile.** A diagonal track crosses latitude and longitude
  boundaries alike. Getting inside one tile needs a segment of ~1 NM — below the 1.58 NM median distance
  between a sample and the position its value belongs to. Unachievable in principle, not merely
  unaffordable: we cannot localise a reading to a tile more precisely than the tile is wide.
- [x] So the graph square **is not and cannot be** a region of constant forecast. It is the region over
  which we hold exactly one reading. Route 2 is 2.7× better than route 1 on tiles crossed — a real quality
  difference, not a difference in kind.

**The claim that survives, stated exactly:** in the graph we build rectangles in *distance × time*. Their
distance edges come from two causes — **a new weather reading** and **a change of course** — because both
change the cost coefficient. Their time edges come from the forecast block. Inside one rectangle we hold
one reading and one heading, so the model treats conditions as constant there: constant *in our knowledge*,
not in fact. And that is the right partition regardless, because with the cost coefficient fixed across a
rectangle, **the fuel rate is convex in speed, so constant speed across it is optimal** — no finer
partition can improve the solution, and any coarser one forfeits optimality.

### 1E. H-line strategy — two separate decisions

Same rule both routes: `H = weather points ∪ course-change points`. In the current data the control points
are already waypoints (`generate_waypoints` emits every original), so the union collapses to the waypoints.
What differs is the binding constraint.

**Route 1 — sampling-limited. Free, adopt it.**

| | today (0.5° crossings) | at waypoints |
|---|---|---|
| H-lines | 163 | **131** |
| Segment | irregular 10.4–30.9 NM | 25.00–48.99, median 25.00 |
| Readings/segment | 0.83 — some blind | **exactly 1** |
| Lattice cost | 1.0× | **0.8×** |

Smaller *and* correct. No trade-off to weigh; needs only agreement that the rule is right.

**Route 2 — compute-limited. A runtime call.**

| | today | at waypoints | every 2nd |
|---|---|---|---|
| H-lines | 121 | **389** | 195 |
| Readings/segment | ≈4, averaged into one | **exactly 1** | 2, averaged |
| Lattice cost | 1.0× | **3.2×** | 1.6× |

Recovers ~3× the spatial information the route already holds and currently averages away. Recommendation:
pay the 3.2× and keep the clean rule; the 195-line fallback reintroduces the averaging the redesign exists
to remove. **Floor: do not go finer than 5 NM** — the 1.58 NM position offset is already 32% of that square.

**Construction** (replaces `nodes.h_line_distances_from_geo`) — the key move is to make the collected
waypoints the graph's polyline, which also removes the great-circle-vs-rhumb discrepancy:

```
1. d[0]=0 ;  d[i] = d[i-1] + rhumb_distance(W[i-1], W[i]) ;  L = d[n-1]
2. H = d                                    # one per waypoint, no crossings, no unions
3. heading[k] = rhumb_bearing(W[k], W[k+1]) ;  weather[k] = reading at waypoint k
4. V = { 0, Δt, 2Δt, ... } ∪ { T }
5. k = bisect_right(H, d_src) - 1            # exact: same numbers define the boundaries
6. assert [len/v_max, len/v_min] contains a multiple of τ
```

- [x] **The boundary ambiguity dies at the root.** Today the cell comes from `floor(lat/0.5)` on a derived
  coordinate, a coin-flip on the line. In the new construction the node distances *are* the segment
  boundaries, so the comparison is exact — verified that `bisect_right(H,d)−1` returns the departing
  segment at every H-line on both routes. `position_at_d` leaves the pricing path, taking the
  segment-boundary heading bug with it.
- [x] **The τ-feasibility filter becomes a no-op** — 0 of 130 segments fail on route 1, 0 of 388 on route 2.
  Keep it as an assertion. This is what removes the ETA dependence: the filter stops deleting lines, so the
  spatial grid stops being a function of the speed band.
- [ ] **Collector fix for future collection:** generate waypoints along the **rhumb line**, not the great
  circle. Today they sit off the sailed legs by up to 1.4 NM (route 1) / 4.1 NM (route 2), and bearings
  drift within a leg by a median 0.52° / 4.32°, up to 6.30° on route 2. One line; cannot be applied
  retrospectively.
- [ ] Also fix `num_intermediate = int(d/interval) − 1` — twelve route-1 segments run to 48.99 NM,
  together 446 NM or 13.1% of the route.

### 1F. Defects to decide on

| # | Defect | Severity |
|---|---|---|
| 1 | **Paper Eq. (eq:sog) misdescribes the code in both halves**: no separate ΔV_wind / ΔV_wave (one combined BN-driven loss), and the current is a 2-D vector magnitude, not the along-track projection `V_c cos θ_c`. A pure beam current *raises* SOG (12.50 → 12.86 kn at 3 kn abeam). | critical |
| 2 | **Segment-boundary heading** — `position_at_d` returns the segment that *ends* at a boundary, so route 1's first turn is priced 60° off. 11/11 and 9/9 interior boundaries. Independent of the squares; survives any re-placement. | critical |
| 3 | **The 0.5° cell** causes five faults that all die with it: `floor()` coin-flip (80/152 and 56/111 crossings), non-vector current averaging (1 kn@090° + 1 kn@270° → 1.000 kn@180°), `round(mean(BN))` rather than `BN(mean(V))`, empty cells on route 1 vs 4-sample means on route 2, and latitude-dependent cell size confounding the cross-route gap. | critical |
| 4 | **Spatial grid is a function of the ETA** — H-lines filtered against a band derived from `mean_sog ± 3` = f(L, ETA). The independent variable moves the discretization. Measured in §1J: 164 → 163 at τ=0.1, but 164 → 143 at τ=0.5. | high |
| 5 | **`forecast_hour` semantics undefined by the schema** — collector writes process-start-relative offsets, RH reads issue-relative leads. Shipped file satisfies both by accident of how it was run; a re-collection in one continuous process corrupts every vintage silently. | high, latent |
| 6 | **`cell_selection` unset** — Marine defaults to `sea` (correct), Forecast defaults to `land`. Wind near the coastal ends may be mis-sourced. One parameter. | medium |
| 7 | **Route 1 plans 112 h past its forecast horizon** (280 h ETA vs 168 h), silently reusing each issue's max lead. Undisclosed. | medium |

**Not found**, and worth recording: no forecast lookahead leak in the rolling horizon; the rhumb geometry
reproduces Luo's segment table to 0.36 NM over 3,393 NM; bearings use a circular mean so the 0°/350° wrap
bug is absent; wind FROM and current TOWARDS conventions are each used correctly.

### 1G. §5.1.1 updated today

Applied to `paper_workspace/paper_full_draft.tex`:

| Claim | Was | Now |
|---|---|---|
| System granularity | 0.25° × 0.25°, 6 h | ~0.08° (3–5 NM), hourly — 6 h stated as *our* sampling choice |
| Wind source | NOAA GFS at 0.25° | automatic selection; probed grid ~9 km, consistent with ECMWF IFS HRES |
| MFWAM | 0.25° | **0.08°** |
| Forecast horizon | "to 168 h" | "retrieved to a 168 h horizon" — ours, not the product's |
| Collection window | ~80 days | **~170 days** |

Also corrected three now-inconsistent GFS attributions (lines 793, 853, 1089 → "the wind product" / "the
wind model's cycle"). The 6 h refresh figure stays valid; Open-Meteo lists ECMWF IFS at every 6 h too.

- [x] **The collection window is 169.8 days** — `sample_hour` 6…4074 at 6 h, 680 issues, 8 Mar to 24 Aug.
  The paper's 80 was wrong *and* the "canonical 155" in the Aug-24 prep was also wrong.
- [ ] **Left untouched, needs your call: the 86% staleness claim** (lines 793, 1089). In the stored hourly
  forecast series wind changes at 99% of consecutive steps — median run 1 h — which contradicts "86% of
  hourly queries returned identical data". I could not reconstruct how the 86% was measured so did not
  overwrite it. It carries weight: the argument "sub-6 h re-planning carried no new information" is what
  justifies the 6 h cadence, and if the forecast genuinely varies hourly then the justification is the
  **issue cycle**, not value staleness. Different arguments; only the first survives.
- [ ] **Left untouched: the 150-instance paragraph.** "25 departure times spaced three days apart… 3 ETA
  levels… 150 instances" matches neither the code (one ETA per route, departures stepped *by* the ETA) nor
  any results table. Also uses NM as a speed unit. This is a description of a different study, not a wrong
  number.

### 1H. Where the changes land — and two facts that set the cost

Full specification in [h_line_realignment_design.md](h_line_realignment_design.md). Two things in it
change the size of this job and should be settled in the room.

**The C++ engine is the production path.** The paper's numbers come from
`paper_workspace/results/2026_08_11_chain_sweep_v2_cpp/`. `pipeline/dp_cpp/src/` is 3,487 lines mirroring
the Python solve path function-for-function, so **every change lands twice** — `nodes.cpp:49`,
`frame.cpp:30,36`, `weather.cpp` (353 + 182 lines), `geo_grid.cpp:48,109`, `atomic_edges.cpp:56,63`,
`luo_main.cpp:119,125,204,210,241,275`, `SR_main.cpp:33`. Cross-engine bit-exactness is the real gate,
as it was for the streaming refactor.

**Both regression harnesses break by construction.** Python goldens store `schedule_sha256`; the C++
harness compares per-edge CSVs. Changing the partition changes every node id, so
**the existing baselines cannot validate this work — only report that it happened.** Proposal: flag-gate
`--h_lines={geo,waypoint}` in both engines, run the two on identical inputs, accept the measured delta,
then re-freeze.

**Code sites, in brief:**

| Area | What happens |
|---|---|
| `nodes.py:160` / `nodes.cpp:49` | H-line generator replaced by the waypoint-distance list |
| `nodes.py:206-247` τ filter | demoted to an assertion (verified 0/130 and 0/388 fail) — this is what ends the ETA→grid coupling |
| `frame.py:114` / `frame.cpp:30` | `cell_weather_at` → `segment_weather_at`, via `bisect_right(H, d) − 1` |
| `frame.py:131` / `frame.cpp:36` | `paper_heading_at` → per-segment rhumb bearing — **the heading fix**, and it ends the dependence on Luo's 12-value heading table |
| `weather.py:386,399,463` | cell index, cell aggregation and the fallback chain all **deleted** |
| `geo_grid.py:126,216,222` | crossings, `cell_index`, `position_at_d` off the pricing path; kept for figures |
| `luo_main.*` | must be exercised on the identical partition or the comparison is meaningless |
| `collect/waypoints.py:37-66,127` | rhumb interpolation; drop the `−1` — **future collections only** |
| `collect/collector.py:79-85,128-141` | `cell_selection=sea`; store the resolved cell coordinates and model |

**One piece of deliberate throwaway work.** The boundary-probe coin-flip and the segment-boundary heading
affected **the published numbers**. Recommendation: fix those two on the *old* partition first, re-run the
v2 sweep, and compare `gap_pct` against `2026_08_11_chain_sweep_v2_cpp`. If the reported 1.80% / 2.60%
move materially, the paper needs a correction note regardless of what happens to the partition; if they
do not, that is a reassuring sentence worth being able to write. Either way it is better known now.

**Order.** Paper method text and results tables must *follow* the partition change, not lead it — the text
would otherwise describe a partition that does not exist, and the tables cannot be regenerated before it
is fixed. Only the §5.1.1 wording and the cosmetic fixes (line 528, 756, 63/121/125) are independent.

### 1I. Servers checked, fresh data pulled — 41 voyages now available

Checked all three collection hosts over the VPN.

| Host | Status | route 1 | route 2 |
|---|---|---|---|
| **Shlomo2** | **live, most current** | 269.4 MB, 2026-09-07 14:01 | 632.0 MB, 14:08 |
| Edison | live, ~3 h behind | 269.8 MB, 11:03 | 632.2 MB, 11:09 |
| Shlomo1 | **dead since 2026-03-10** | 1.7 MB | 4.8 MB |

- [x] **Shlomo1's collector has been dead for six months.** If anyone still believes three hosts are
  collecting, they are not — it stopped on 10 March. Its files never grew past the March snapshot.
- [x] Edison's files are marginally *larger* but older, so the two live hosts are not byte-identical —
  independent collectors with slightly different histories. Shlomo2 taken as the more current.
- [x] Downloaded to `paper_workspace/data/experiment_{b_138wp,d_391wp}_v4_sep07.h5` (269.4 + 632.0 MB,
  both complete). Named `_v4_sep07` so the `_v3_aug24` files the paper currently uses are untouched.

**Voyages extractable** — non-overlapping chain, departures stepped by the ETA:

| dataset | issues | sh range | span | gaps | chain | ran | gain |
|---|---|---|---|---|---|---|---|
| route 1 `v4_sep07` | 735 | 6..4410 | 183.5 d | **0** | **15** | 13 | **+2** |
| route 2 `v4_sep07` | 736 | 0..4410 | 183.8 d | **0** | **26** | 22 | **+4** |
| route 1 `v3_aug24` | 679 | 6..4074 | 169.5 d | 0 | 14 | 13 | +1 |
| route 2 `v3_aug24` | 680 | 0..4074 | 169.8 d | 0 | 24 | 22 | +2 |

**41 voyages are available on the new data** (15 + 26) against the 35 published — **+6**. Both routes are
gap-free at 6 h cadence across the full 183 days.

- [x] **The "35 vs 38" decision from Aug 24 is resolved and superseded.** 38 is exactly what `v3_aug24`
  supports (14 + 24); 35 is what was run, because `sh_bases` were sized for a snapshot ending ~3696. With
  the new data the question is **35 → 41**, not 35 → 38.
- [ ] **`sh_bases` are hardcoded lists and still hold the v1 values** — `run_chain_sweep.py:59,68` and
  `dp_cpp/run_rh_chain.py:40,46` each contain 7 + 12 = **19** departures, which is where the paper's stale
  "nineteen voyages" comes from. Extending to 41 means editing four literal lists across two engines, not
  changing a computation. Worth replacing with a computed list so the count follows the data.
- [ ] If overlapping departures were acceptable the ceiling is **1,396** (688 + 708 — every 6 h departure
  whose window fits). That is a different experimental design rather than a larger version of this one,
  but it is what the data supports, and it bears on the "150 instances" paragraph in §1G.
- [x] The new route 1 file carries **the same six dead nodes** (80, 126–130, 100% NaN in the consumed
  fields), so the `usable_node_ids` logic from §1E carries over unchanged. Route 2 has none.

### 1J. Sub-segment counts, and why the geo count is not a property of the route

The paper's §4 term: a sub-segment is the interval between two distance lines.

| | route 1 (Indian Ocean) | route 2 (North Atlantic) |
|---|---|---|
| **geo — raw geometry** | **164** | **121** |
| geo — after τ filter, τ = 0.1 (**production**) | **163** (1 dropped) | **121** (0 dropped) |
| geo — after τ filter, τ = 0.5 (coarse tests) | 143 (21 dropped) | 110 (11 dropped) |
| **waypoint partition** | **125** | **388** |

Route lengths 3393.24 / 1954.70 NM, so mean sub-segment length is 20.8 / 16.2 NM under geo
and 27.1 / 5.0 NM under the waypoint partition.

- [x] **163 and 121 are the production figures** — that is what the published results were computed on.
- [ ] **The geo count is not a property of the route.** It depends on τ and on the speed band, which is
      derived from `mean_sog = L/ETA`. At τ = 0.5 route 1 loses 21 sub-segments; change the ETA and the
      band moves and the count moves with it. So "how many sub-segments does route 1 have" has no answer
      under the current design without also stating the ETA and the time grid. This is §1F #4 in concrete
      numbers, and it is the strongest single argument for the redesign.
- [x] **Only route 1 loses anything at production settings** — 1 of 164. Small, but the published route 1
      graph is missing a decision point for a reason with nothing to do with geography.
- [x] **The partition flips which route is finer.** Under geo, route 1 has *more* sub-segments than
      route 2 (163 vs 121) despite being 1.7× longer, because 0.5° cells are wider at low latitude. Under
      the waypoint partition it inverts to 125 vs 388. That inversion is the point: route 2 is sampled 5×
      more densely and should have a correspondingly finer partition, which the 0.5° cell was masking.
- [x] Both waypoint counts are **configuration-independent** — no filter fires, so they are fixed by the
      sampling alone.

### 1K. Review of Tal's push `8995489` — mostly right, two new contradictions

He fixed the wave problem in both the code and the paper, and redrew Fig. 1. Reviewed against the
implementation.

**What is correct and now matches the code**

- [x] `ΔV_wave` removed from `eq:sog` in **both** SOG subsections; the `H_w` / beam-to-length claim at
      the old line 358 is gone. The paper's speed model now describes what the code computes.
- [x] MFWAM bullet removed from §5.1.1; waves removed from the refresh-cycle paragraph.
- [x] All four functional wave-NaN sites fixed — `Weather.has_nan()` (Python + C++),
      `_row_has_nan()`, the C++ private `WeatherRow::has_nan()`, and the C++ `cell_weather_at_d`
      fallback trigger — and fixed **globally**, not flag-gated.

**Measured effect of the NaN fix** (route 1, v3_aug24, coarse grid):

| | Python | C++ | cross-engine |
|---|---|---|---|
| geo, before | 362.97071551837325 | 363.02198563243803 | 0.0513 mt |
| geo, after | **361.99831751974130** | **362.04958763380608** | 0.0513 mt |
| shift | **−0.9724 mt (−0.27%)** | **−0.9724 mt** | unchanged |

- [x] Route 1's **published** path moves −0.27%, identically on both engines. Route 2 geo is unchanged
      (it has no dead nodes). Both waypoint results are bit-identical to before, which confirms his
      `has_nan()` and the `has_nan_consumed()` added in `c3ea2f8` are functionally equivalent.
- [ ] **Consolidate the two predicates.** `has_nan()` and `has_nan_consumed()` are now near-duplicates
      (mine additionally tests `isnan(beaufort_number)`), and `frame.weather_unusable()`'s partition
      dispatch is pointless — both branches do the same thing. Keep one.
- [ ] The goldens and `reference_runs` are now genuinely invalid, not just for the partition work.
- [ ] `gap_pct` impact is unmeasured: Luo shifts too, so the published 1.80% / 2.60% may move less than
      0.27%. Needs a Luo run to know.

**Two new contradictions the push introduces**

- [ ] **The paper now says 0.08° cells; the code still uses 0.5°.** Verified: `frame.py:56,200`,
      `nodes.py:215`, `frame.hpp:16,65` all default `grid_deg = 0.5`. Seven `0.08\degree` claims now sit
      in the text (intro line 114, the sea-conditions definition, the subsegment rule at 422). This is
      **worse than before**: previously the paper and code agreed on 0.5° and only the *justification*
      was wrong; now they disagree on the mechanism. Paper says subsegments are ~5 NM and M ≈ 680 on
      route 1; the code produces 163 at ~20.8 NM.
- [ ] **And 0.08° is the wrong target anyway.** Per §1D/1E, route 1 samples at 25 NM, so 0.08°
      subsegments leave **4 of every 5 blind** — 680 subsegments at 0.20 samples each. Substituting one
      wrong number for another. The defensible unit is the sampling interval, which is §1E's proposal.
      Line 247's new justification ("the native resolution at which the services deliver their fields")
      is closer to honest than the old category error but is still false of the implementation.
- [ ] **δ = 0.2 NM is claimed but the code uses 1.0 NM.** Line 441 and the new Fig. 1 caption both state
      δ = 0.2 NM as the experimental grid; `nodes.py:46` and `nodes.hpp:19` both have `zeta_nm = 1.0`.
      Either the paper is wrong or the runs need redoing at 0.2 NM — the latter would multiply the
      time-line node count fivefold.

**Figure 1**

- [x] Redrawn as a stacked two-panel schematic on a 5 NM subsegment, `d∈[240,245]`, `t∈[24,30]` h, all
      states as discs, one arc per candidate. The old fan thinning capped arcs at 8 while plotting every
      marker, leaving markers without arcs once the grid was refined — a real bug, correctly fixed.
- [ ] **It moved from real geometry to illustrative coordinates.** `state_neighbours_figure_redesign.md`
      §2 explicitly requires the opposite — "the geometry comes from the production analytic
      rhumb-line/grid frame, not from hand-picked illustration values" — with a reproducibility rule
      asserting regenerated values match to 1e-6. Either the doc should be updated to record the
      reversal, or the figure should go back to a real block. It should not silently contradict its own
      design doc.
- [ ] The caption's "5 NM is representative of a 0.08° cell on these routes" inherits the 0.08°-vs-0.5°
      problem above.

**Still outstanding, untouched by the push**

- [ ] `Figure X` placeholder still at line 530, in the very paragraph that describes the rectangle.
- [ ] The sub-segment definition at line 509, `i(d) = argmax_i{d_i < d}`, still uses a strict `<`, so a
      state exactly on distance line `d_k` is assigned to the sub-segment it is **leaving**. That is the
      same boundary error as the old `floor(lat/0.5)` coin-flip, and it now contradicts the
      `bisect_right` lookup committed in `c3ea2f8`. One of the two must move; the paper is the one that
      is wrong.

---

## 2. Actions still open

| Action | Ref | Status |
|---|---|---|
| Justify or cite the fixed-average-speed baseline (`Hvattum2013` supports it) | 24th §8 n1 | open |
| Strip all `---` em-dashes — 68 live instances, some in Tal's own text | 24th §8 n2 | open |
| Three-way resolution contradiction (247 / 767 / 774–777) | 24th §8 n5 | **closed by 1A + 1G** |
| Add `--grid_deg` flag + route2 sensitivity at 0.25° | 24th §8 n6 | **superseded — the 0.5° cell goes** |
| Route1 empty-cell fallback → along-track interpolation | 24th §8 n6 | **superseded — no cells** |
| Re-collect route1 at 5–10 NM (perfect-foresight only; RH cannot be backfilled) | 24th §8 n6 | open, better motivated by 1D |
| **Restart Shlomo1's collector, or retire the host** | **1I** | **new** — dead since 2026-03-10 |
| **Replace the hardcoded `sh_bases` with a computed list** | **1I** | **new** — four literal lists, two engines |
| **Re-run the chain sweep on `v4_sep07` at 41 voyages** | **1I** | **new** — blocked on the Luo/RH partition work in 1E |
| Tidal exposure on route2's Liverpool approach | 31st 1G | open — reframed as a between-block sampling issue |
| Consider a finer time block (data is hourly; block is 6 h) | 31st 1G | open, generalised beyond the tidal case |
| Fix `Figure X` placeholder at line 528 | 24th 1A | open |
| Fix the "19 voyages" sentences (canonical 35 = 13+22) | 24th 1D | open |
| `NM` used as a speed unit at line 756 (and in the 150-instance paragraph) | 24th 1E | open |
| Delete `tables` from requirements.txt; declare Python ≥ 3.10; pin versions | 24th 1O | open |
| Decide the fate of the §5.1.1 wave bullet | **1B** | **new** |
| Resolve line 247 vs line 358 on how waves enter | **1B** | **new** |
| Rewrite Eq. (eq:sog) to match the implementation | **1F #1** | **new** |
| Fix the segment-boundary heading lookup | **1F #2** | **new** |
| Generate future waypoints on the rhumb line; fix the `−1` off-by-one | **1E** | **new** |
| Set `cell_selection=sea` on the Forecast API | **1F #6** | **new** |
| Assert `forecast_hour` semantics in the schema or the loader | **1F #5** | **new** |
| Disclose route 1's 112 h beyond-horizon planning | **1F #7** | **new** |

## 3. Decisions still open

| Decision | Ref | Note |
|---|---|---|
| ~~35 vs 38 voyages~~ → **35 vs 41** | 24th 2B / **1I** | superseded: 38 was the v3_aug24 ceiling, 41 is the v4_sep07 ceiling |
| `v_max = D/T + 3` ratified? | 24th 2A | already written at line 807 — ratification, not design |
| Luo band: align, or restore 8–18 kn? | 24th 1M | code already aligned; text must match |
| Pin `requirements.txt`? | 24th 1O | decides whether a rerun reproduces or replaces |
| Implement Eq. (1) endpoint waiting in code? | 24th 1L | provably cannot change results |
| ETA-feasibility arc cut approved? | 24th 2A | ~14× arcs, 13× runtime in the quick test |
| Write §4.3, or fold it elsewhere? | 24th 1P | §4.3 does not exist — a write, not a rewrite |
| Definition of the discretization unit | 31st 1D | **answered by 1D: one sampling interval, stated as an information partition** |
| **Adopt the rule `H = weather points ∪ course-change points`?** | **1E** | the only question route 1 needs |
| **Route 2: pay 3.2×, or take the 195-line fallback?** | **1E** | runtime call; measure before committing |
| **Shrink the block below 6 h, per route?** | **1E** | route 1 cheap (1.6× at 3 h), route 2 not (6.4×) |
| **Re-collect with `models` pinned, or describe what was served?** | **1A** | §5.1.1 currently describes what was served |
| **Rework or drop the 86% staleness argument?** | **1G** | it justifies the 6 h re-plan cadence |
| **Which experiment does the 150-instance paragraph describe?** | **1G** | rewrite needs the answer, not a number |
| **Change both engines, or retire the Python path?** | **1H** | C++ produced the paper numbers; keeping both doubles the work but preserves the cross-check |
| **Measure the boundary-probe bug against the published results first?** | **1H** | throwaway work, but it tells us whether 1.80% / 2.60% need a correction note |
| **Flag-gate the partition, or change it outright?** | **1H** | the goldens cannot validate this either way; flag-gating makes the delta measurable |

## 4. Decisions made during the session

| Decision | Owner | Outcome | Follow-up |
|---|---|---|---|
| | | | |

## 5. Actions assigned during the session

| Action | Owner | Due/status |
|---|---|---|
| | | |

## 6. Running notes

_Live log — append as we go._

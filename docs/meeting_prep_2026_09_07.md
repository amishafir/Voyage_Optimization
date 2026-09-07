# Meeting Prep — Monday 2026-09-07 (Ami ↔ Tal)

Continues from [meeting_prep_2026_08_31.md](meeting_prep_2026_08_31.md).

Sections 4–6 of the Aug-24 and Aug-31 preps were never filled in, so both decision tables are carried
forward again below. Section 1 is new material: the discretization question was taken to the source APIs
and to the code, and **the premise the whole investigation rested on turned out to be wrong**.

Supporting document: `docs/weather_resolution_audit_2026_09_06.html` (focused version — sources, parameter
map, computation chain, the rectangle). Full version with all findings, the per-route graph redesign and
the paper-impact table retained at `docs/weather_resolution_audit_FULL_2026_09_06.html`.

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
| 4 | **Spatial grid is a function of the ETA** — H-lines filtered against a band derived from `mean_sog ± 3` = f(L, ETA). The independent variable moves the discretization. | high |
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
| 35 vs 38 voyages | 24th 2B | data pulled and verified; one config line either way |
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

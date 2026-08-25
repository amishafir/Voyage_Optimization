# Meeting Prep — Monday 2026-08-31 (Ami ↔ Tal)

Continues from [meeting_prep_2026_08_24.md](meeting_prep_2026_08_24.md).

Nothing in the Aug-24 decision table was filled in during the session, so every decision there is
still open and carried forward in Section 3 below. Section 1 is the substantive new material:
the discretization question, researched against Open-Meteo's own documentation on 2026-08-25.

---

## 1. What is a "square", when each weather component has its own granularity?

The model states that sea conditions are constant within each discretized unit — 0.5° × 0.5° and
six hours. Pushing on that revealed it is not a description of the data at all.

### 1A. There is no single square in the data — each variable has its own

Verified against the Open-Meteo data-sources tables (links at the end of this section):

| Field | Source model | Native grid | Temporal | Refresh |
|---|---|---|---|---|
| Wind (10 m) | NOAA GFS / auto-selected | 0.25° (~25 km) | hourly | every 6 h |
| Waves (sig. height) | MeteoFrance MFWAM | **0.08° (~8 km)** | 3-hourly | every 12 h |
| Ocean currents | MeteoFrance SMOC | **0.08° (~8 km)** | hourly | every 24 h |

These grids are not nested, not mutually aligned, and **none of them is 0.5°**. A "square in which
the weather is constant" therefore does not exist as a data object: wind is constant over one tile,
waves over a different and much smaller one, currents over a third.

- [ ] **Factual error to fix: the paper says MFWAM is at `0.25°`.** Open-Meteo's data-sources table
      says **`0.08°`**, 3-hourly, updated every 12 h. The `0.25°` figure belongs to other wave models
      in their catalogue (ECMWF WAM 0.25, NCEP GFS Wave, DWD GWAM), not to MFWAM. The "twice daily"
      claim is correct.

### 1B. Our square is a modelling choice, not an inherited property

This is the conceptual heart of it. The 0.5° cell is something **we impose**. "The weather is
constant in each square" is an **assumption we declare**, not a fact about the sources.

Which makes the justification sentence at line 247 — *"This discretization level was chosen because
it is used by global weather and forecast services"* — worse than factually wrong. It is a **category
error**: it presents our modelling decision as inherited from the data.

What one 0.5° square actually contains:

| Field | Native cells per 0.5° square |
|---|---|
| Currents | **~36** (6 per side) |
| Waves | **~36** (6 per side) |
| Wind | **~4** (2 per side) |

Different fields are flattened by different amounts inside the same box.

### 1C. The time axis has the same structure, running the other way

| Field | Data refresh | Our block | Relationship |
|---|---|---|---|
| Wind | 6 h | 6 h | matched |
| Waves | 12 h | 6 h | **our block is finer than the data** |
| Currents | 24 h | 6 h | **4x finer than the data** |

Spatially we are coarser than every source; temporally we are *finer* than two of the three. The 6 h
block is justified in §5.1.1 from the GFS cycle, which is right for wind and silent on the rest.

**Consequence for the rolling-horizon story:** if we re-plan every 6 h and currents refresh once
daily, **three of every four re-plans see an unchanged current field**. That is the same argument Tal
already makes for wind (86% of hourly queries unchanged) — it just needs extending to the other two
fields, and it strengthens rather than weakens the 6 h choice.

### 1D. Three defensible definitions of a square — pick one and say so

- [ ] **(i) Finest common unit** — the region where *all* fields are genuinely constant. With
      non-aligned 0.08° and 0.25° grids that is ~0.08° and irregular. Most faithful; multiplies the
      state space by roughly 36. Not realistic.
- [ ] **(ii) Coarsest source** — 0.25°, the wind grid. "Constant" is then true for wind and false for
      waves and currents. Halves our cell size; the natural target for the sensitivity run since it
      matches a real grid.
- [ ] **(iii) A declared modelling choice** — 0.5° for tractability, aggregation rule stated, gap to
      the sources acknowledged. **This is what we already do.** It is perfectly defensible; it just
      has to be stated rather than disguised as inherited.

**Recommendation: (iii), stated explicitly, with (ii) run once as a sensitivity bound.**

Proposed replacement for the §3 sentence:

> Sea conditions are assumed constant within a discretization unit of 0.5° × 0.5° and six hours. This
> unit is a modelling choice made for tractability, not a property of the source data: the underlying
> models are finer in space (0.25° for wind, 0.08° for waves and currents) and coarser in time for two
> of the three fields (12 h for waves, 24 h for currents). Weather is assigned to each unit by
> aggregating the route waypoints that fall inside it.

### 1E. A fourth granularity the paper never mentions — and it is the binding one

Open-Meteo **does not interpolate**: *"The API does not perform any spatial interpolation between
grid-cells, as interpolation can reduce accuracy and introduce unwanted artefacts."* So we do not hold
fields, we hold **point samples of grid cells** at our own waypoints. The real chain is:

> source grid → sampled at our waypoints → averaged into our 0.5° square → held constant for 6 h

Four granularities, three of them undocumented. And our sampling interval is hardcoded per route at
`pipeline/run_all.py:45,51`:

| Route | Sampling | vs coarsest source (0.25° ≈ 15 NM) |
|---|---|---|
| route1 / Indian Ocean | **25 NM** | **coarser than every source grid** |
| route2 / North Atlantic | 5 NM | finer than all three |

- [ ] So **route1's sampling is the binding constraint, not the 0.5° cell** — which is the same
      conclusion the Aug-24 fuel analysis reached from the other direction (note 6 there: 25% of
      route1's H-line segments sit in cells with no waypoint at all).

### 1F. Open question to test: `cell_selection` is never set

The collectors send **no `cell_selection` parameter**, so both APIs use their defaults — and the
defaults differ:

- **Marine API** (waves, currents) defaults to **`sea`**. Correct for us.
- **Weather API** (wind) defaults to **`land`**, which *"finds a suitable grid-cell on land with
  similar elevation to the requested coordinates using a 90-metre digital elevation model."*

- [ ] On an ocean route that may be selecting **land** cells for wind near coastal waypoints. Worth
      testing for land contamination in the wind field near the coastal ends of both routes. If
      confirmed, the fix is one parameter (`cell_selection=sea` or `nearest`) — but it would mean the
      wind record is partly mis-sourced, which is a data-quality issue rather than a discretization
      one. This may also explain the known Port B NaN behaviour.
- [ ] Also unset: `models`. The wind default is `auto` / "best match", which combines the
      *highest-resolution applicable* model rather than pinning GFS. **The paper attributes wind to
      GFS at 0.25°** — worth confirming that is what was actually served, since over open ocean the
      documented global fallback is ECMWF IFS HRES at 9 km, not GFS.

### 1G. The `0.08°` matters because it is **tidal** — and the exposure is temporal, not spatial

This is the most consequential item in this doc, and it is on an axis nothing else here touches.

**What SMOC actually is.** Not a general-circulation product. `SMOC` = **Surface Merged Ocean
Current**, 1/12° (= 0.0833° ≈ 0.08°), hourly, and it is a **sum of three components**:

> `u_total = u_geostrophic+Ekman (GLO12) + u_Stokes (wave drift) + u_tide`

That is *why* it is 0.08° and hourly. General circulation is smooth and slow and needs neither.
**Tides and Stokes drift do.** The resolution exists to carry the tidal signal.

**Why that lands on route 2.** Route 2 ends at **Liverpool**, through the Irish Sea and Liverpool
Bay — among the largest tidal ranges in the world, with tidal streams of several knots. The M2 tide
is **semi-diurnal, period 12.42 h**, reversing roughly every 6.2 h. We sample every **6 h** and hold
weather constant: **2.07 samples per tidal cycle**, essentially *at* the Nyquist limit of 2.0.
Formally above it, so not aliased — but at 2.07 samples per cycle the reconstructed amplitude and
phase are badly distorted, and the small offset from 2.0 produces a slow beat.

**Measured in the v3 data** (consecutive 6 h samples, absolute change in current direction):

| Region | median turn | reversals >135° | median speed |
|---|---:|---:|---:|
| mid-ocean (800–1100 NM) | **26.6°** | 4.7% | 0.918 kmh |
| **Liverpool approach (last 120 NM)** | **153.4°** | **64.1%** | 0.918 kmh |

**On the final 120 NM the current reverses between two-thirds of consecutive samples** — median turn
153°, essentially a flip, at the same speed as mid-ocean. That is the M2 tide, exactly as SMOC's
composition predicts.

**Why it is not negligible.** The DP holds weather constant for 6 h, so on that stretch it holds a
current that has physically reversed inside the block. At ~0.9 kmh (0.5 kn) against a ~11.6 kn mean
SOG, a flip is a ~1 kn swing in the required through-water speed; with FCR cubic, that is roughly a
**25% error in the fuel rate** on affected legs, over ~120 NM ≈ **6% of route 2**. And unlike the
spatial averaging, this is **not obviously common-mode** — it is a time-varying error that a
rolling-horizon planner acting on 6 h forecasts will actively chase.

**This reframes the whole investigation.** The question began as "0.08° is finer than our 0.5° cell —
are we discarding spatial detail?" Answer: barely, ~7–10% of variance, ≤0.2 pp of fuel (Aug-24
note 6). **The real exposure is temporal, and concentrated in the tidal approaches.** Consequences:

- [ ] **The 6 h block is the binding approximation, not the 0.5° cell.** Refining the spatial grid
      does nothing for this. Only finer *time* blocks would — and **SMOC is hourly**, so the data
      supports it. This is the opposite conclusion to everything else in Section 1.
- [ ] **A defensible framing exists and should be stated**: tidal currents are near-periodic with
      near-zero mean over a cycle, so their effect on *total voyage* fuel largely cancels even though
      it does not cancel per leg. That is an honest limitation rather than an error — but it must be
      written down, because a reviewer who knows the Irish Sea will ask.
- [ ] **Cheapest decisive test:** re-run route 2 with the last ~120 NM excluded, or with a finer time
      block over that stretch only, and see whether `gap_pct` (SR vs Luo) moves. **This is the first
      thing in the whole investigation with a plausible route to actually moving a number.**
- [ ] Check whether route 1 has any equivalent exposure — the Strait of Malacca and the Persian Gulf
      approaches are also tidal, though route 1's 26.1 NM / 6 h sampling would resolve it even less.

Sources: [Marine Weather API](https://open-meteo.com/en/docs/marine-weather-api) ·
[Weather Forecast API](https://open-meteo.com/en/docs) ·
[interpolation discussion](https://github.com/open-meteo/open-meteo/discussions/549) ·
[SMOC product](https://data.marine.copernicus.eu/product/GLOBAL_ANALYSISFORECAST_PHY_001_024/description) ·
[SMOC: a new global surface current product](https://marine.copernicus.eu/sites/default/files/wp-content/uploads/2019/04/Poster_SMOC_EGU2018APRIL.pdf)

---

## 2. Carried over: actions still open from Aug 24

| Action | Note | Status |
|---|---|---|
| Justify or cite the fixed-average-speed baseline (`Hvattum2013` already supports it) | 24th §8 n1 | open |
| Strip all `---` em-dashes — 68 live instances, some in Tal's own text | 24th §8 n2 | open |
| Reconcile the 0.5° justification — now superseded by **1B/1D** above | 24th §8 n3 | superseded |
| Route2's 0.08° sampling — answered: keep it, it is not the problem | 24th §8 n4/n6 | closed |
| Three-way resolution contradiction incl. Tal's line 767 | 24th §8 n5 | open |
| Add `--grid_deg` CLI flag + route2 sensitivity at 0.25° | 24th §8 n6 | open |
| **Route1 empty-cell fallback → along-track interpolation** (cheapest real test) | 24th §8 n6 | open |
| Re-collect route1 at 5–10 NM (perfect-foresight only; RH cannot be backfilled) | 24th §8 n6 | open |
| **Tidal exposure on route2's Liverpool approach — measure whether it moves `gap_pct`** | **1G** | **open** |
| Consider a finer time block over tidal approaches (SMOC is hourly) | 1G | open |
| Fix `Figure X` placeholder at line 528 | 24th 1A | open |
| Fix the "19 voyages" sentences (canonical is 35 = 13+22) | 24th 1D | open |
| `NM` used as a speed unit at line 756 | 24th 1E | open |
| Delete `tables` from requirements.txt; declare Python >= 3.10; pin versions | 24th 1O | open |

---

## 3. Carried over: decisions still open from Aug 24

| Decision | Ref | Note |
|---|---|---|
| 35 vs 38 voyages | 24th 2B | data pulled and verified; one config line either way |
| `v_max = D/T + 3` ratified? | 24th 2A | already written at line 807 — ratification, not design |
| Luo band: align, or restore 8–18 kn? | 24th 1M | code already aligned; text must match |
| Pin `requirements.txt`? | 24th 1O | decides whether a rerun reproduces or replaces |
| Implement Eq. (1) endpoint waiting in code? | 24th 1L | provably cannot change results |
| ETA-feasibility arc cut approved? | 24th 2A | ~14x arcs, 13x runtime in the quick test |
| Write §4.3, or fold it elsewhere? | 24th 1P | §4.3 does not exist — a write, not a rewrite |
| Definition of the discretization unit | **1D above** | new — pick (i), (ii) or (iii) |

---

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

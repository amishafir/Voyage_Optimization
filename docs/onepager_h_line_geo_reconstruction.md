# H-Line Geographic Reconstruction — Summary

**Apr 28–29, 2026** · Persian Gulf → Strait of Malacca voyage rebuild

---

## 1. Incentive

The DP graph relies on **H-lines** (constant-distance decision boundaries) to mark every distance at which a meaningful physical change happens — segment heading shifts and weather-cell crossings. The previous implementation placed weather-cell H-lines at the **midpoint between two consecutive 12 nm interpolated waypoints** whose `(lat, lon)` fall in different 0.5° NWP cells. That's a heuristic, off by up to ±6 nm per crossing, and unrelated to where the route actually crosses the grid on a globe.

Fix: replace the midpoint heuristic with **exact analytic crossings** between the voyage's rhumb-line segments and the 0.5° NWP grid, sourced from the paper's authoritative `(lat, lon)` waypoint table.

## 2. Locked Spec — Q&A Session

| # | Question | Decision |
|---|---|---|
| Qg1 | Source for segment endpoints | (c) **Paper Table 1** — 13 explicit `(lat°, lon°)` waypoints |
| Qg2 | Path shape inside a segment | (a) **Rhumb line** (constant compass bearing) |
| Qg3 | NWP grid resolution | (a) **0.5° marine grid**, axis-aligned |
| Qg4 | Cumulative-distance metric | (a) **Rhumb-line (loxodromic) distance** |
| Qg5 | Weather lookup | (b) **Per-cell mean aggregation** — implemented (see §5) |
| Qg6 | Implement immediately? | (b) **Visualise first**, then implement |
| Qg7 | Visualisation scope | WP1 → WP2 → WP3 → WP4 (sample) and full 12-segment |
| Qg8 | Map projection | (b) **Cartopy / Mercator** (rhumb lines render straight) |
| Qg9 | Robustness scope | (b) **Math + auto-projection** for arctic / antimeridian |
| Qg10 | High-lat test fixture | (a) **Iceland → Tromsø** (lat 64°→ 70°, lon −22° → 19°) |

## 3. Statistics — YAML voyage (3393.24 nm, 12 segments)

| Metric | Old (waypoint-midpoint) | New (analytic rhumb-vs-grid) |
|---|---|---|
| Total H-lines | 146 | **164** |
| Grid crossings | 134 | **152**  (95 lon + 57 lat) |
| Segment-boundary lines | 11 | 11 |
| Terminal sink line | 1 | 1 |
| Bearing accuracy vs paper β | n/a (heuristic) | **±0.2 °** per segment |
| Cumulative-distance error | n/a | **+0.36 nm** out of 3393.24 (+0.01 %) |
| Per-crossing position error | ≲ 6 nm (waypoint midpoints) | **< 1 m** (analytic) |
| Code modules added | — | `route_waypoints.py`, `geo_grid.py`, `test_routes.py`, `visualize_geo_grid.py` |

Robustness pass (Qg9 + Qg10) added: latitude clamp `|φ| ≤ 89.5°`, Δlon normalisation `(−180°, 180°]` for antimeridian routes, and a Cartopy projection auto-selector (Mercator → NorthPolarStereo / SouthPolarStereo / PlateCarree based on extent). Validated against the new Iceland → Tromsø fixture (1033 nm, 91 H-lines, lat 64°–70°N).

## 4. Visualisation

WP1 → WP2 → WP3 → WP4 — left: **Mercator chart with 0.5° NWP grid**, orange dots = lon-line crossings, teal dots = lat-line crossings, black stars = waypoints. Right: same crossings as **H-lines on the DP graph (t, d)** plane, with V-lines (blue dashed, every 6 h) marking the time-decision cadence.

![H-line geographic reconstruction — 3 segments](../pipeline/dp_rebuild/visualize_geo_grid.png)

## 5. Weather sampling strategy (Qg5(b))

### 5.1 What "per-cell aggregation" means

Once the route + 0.5° grid carve the (t, d) plane into squares, every square sits inside exactly one **cell** = 0.5° × 0.5° NWP tile. The DP graph treats the cell as the meteorological unit: every (t, d) probe inside one cell must read **the same** weather, otherwise edges leaving a single source see inconsistent conditions and the optimum is biased.

The lookup chain for any (t, d) probe:

```
(t, d)  ──position_at_d(d, WAYPOINTS)──►  (lat, lon, segment_idx)
                                                  │
                              cell = (⌊lat/0.5⌋, ⌊lon/0.5⌋)
                                                  │
                  cell_weather(cell, sample_hour, forecast_hour)
                                                  │
            mean over every voyage waypoint sitting in `cell`:
              · linear mean ─ wind speed, wave height, current speed
              · circular mean (atan2 of mean-sin / mean-cos) ─ directions
              · int-rounded mean ─ Beaufort
              · NaN rows dropped before averaging
                                                  │
                       fallback if cell has 0 valid rows:
                       weather_at(d) — segment-aware nearest-valid waypoint
```

Result is cell-canonical (every square in one cell agrees) and boundary-tie-free (probe at square center, never on a line).

### 5.2 Sampling strategy for a *new* voyage

Adding a new voyage = re-deciding where to query Open-Meteo along the rhumb-line polyline. Three options:

| Option | Query points | Avg per cell | Pros | Cons |
|---|---|---|---|---|
| **A. Dense (current)** | every 12 nm interpolated waypoint | 1–5 | smooths API noise via cell mean; matches the existing collector | ~280 API calls per route; many redundant calls inside one cell |
| **B. One-per-cell** | exit-midpoint of the rhumb arc inside each cell | 1 | minimum API calls (~80–150); cell mean is exactly the queried point | no smoothing; one outlier API row contaminates the whole cell |
| **C. Hybrid** | 2–3 evenly-spaced points per cell-arc, plus segment endpoints | 2–4 | smoothing + bounded API calls; segment heading change always sampled | slightly more bookkeeping; needs route-walker that knows about cell entries/exits |

### 5.3 Recommendation

Default to **C (hybrid)**: 2–3 samples per cell along the in-cell arc, and force a query at every segment endpoint so heading discontinuities are always anchored by data. This keeps the cell mean meaningful (averages out forecast micro-noise) without ballooning API calls when a cell happens to contain a long rhumb arc.

Falls back gracefully: if a cell turns out to contain only one voyage waypoint anyway, the per-cell mean degenerates to that single value — still cell-canonical, no special-case code.

### 5.4 What still needs to be decided

- **Sampling distance metric**: rhumb-distance (loxodromic) vs great-circle for the in-cell arc length. Consistent with §2 Qg4, default = rhumb.
- **Endpoint inclusion rule**: whether a sample lands *on* a cell boundary (skip → next cell, or duplicate → both cells). Current code uses strict `<` interior so a boundary point is unambiguous.
- **Forecast horizon density**: how many `(sample_hour, forecast_hour)` tuples per query point. Orthogonal to the spatial strategy above; driven by which optimization mode (LP / DP / RH) is being run.

## 6. Locked-mode policy & combined Bellman

### 6.1 SOG-locking (Luo 2024) — the captain holds ground speed, the engine adapts

The earlier "locked-mode" prototype held **SWS** constant per 6 h block; SOG drifted as weather changed underneath the ship. That was the wrong direction. The corrected model — **SOG-locking** — matches Luo 2024 exactly:

| | SWS-locking (deprecated) | **SOG-locking (current)** |
|---|---|---|
| Decision per block | one engine SWS | **one target SOG** |
| What varies inside the block | SOG (and trajectory bends) | **SWS** (engine adapts per sub-leg) |
| dst node lookup | inverse binary search | **geometric: `d_src + SOG · 6 h`** |
| Block fuel | `FCR(SWS) · 6h` (one term) | **`Σ FCR(SWS_i) · Δt_i`** (sum over sub-legs) |
| Build time | 7–20 min | **~110 s** |
| Bellman ↔ continuous-resim drift | up to 1.84 nm at sink | **0.000 nm everywhere** |

In code: each sub-leg looks up cell-canonical weather + paper-segment heading, **inverts SWS** from the target SOG, accumulates `FCR(SWS) · Δt`. If any sub-leg's required SWS exceeds the engine bound (default 25 kn) the edge is dropped — that target SOG is infeasible across that block under those conditions.

### 6.2 Combined Bellman — free ⊕ locked on the same nodes

Both edge sets share the free-DP node table by construction (verified by closing assertion). The union of edges is a valid Bellman input — Bellman picks the lowest-fuel outgoing edge at every node, regardless of type. The combined optimum is bounded above by both alone:

| Graph | Edges | Total fuel | Schedule | Δ vs baseline | Δ vs free |
|---|---:|---:|---:|---:|---:|
| **Baseline (steady SOG = 12.120 kn)** | — | **366.519 mt** | 1 (continuous) | — | −0.25 mt |
| Free DP (per-square) | 3,308,940 | 366.769 mt | 206 edges | **+0.25 mt** | — |
| Locked DP (SOG-locking) | 631,537 | 365.161 mt | 47 blocks | −1.36 mt | −1.61 mt |
| **Combined (union)** | **3,940,477** | **362.965 mt** | **105 (74 free + 31 locked)** | **−3.55 mt (−0.97 %)** | **−3.80 mt** |

The steady-SOG baseline holds `SOG = L/ETA` constant over the whole voyage,
inverse-solving SWS per H-line sub-leg under the same cell-canonical weather
the DP graphs see. Free DP is **+0.25 mt worse than the baseline** — its
1 nm × 0.1 h snap grid can't match the continuous SOG the baseline runs at
when the optimum is near-uniform. Locked DP wins by 1.36 mt (continuous
target SOG, no snap penalty) and combined wins by 3.55 mt (locked
sub-cruise + free boundary fixups). The combined-vs-baseline gap is the
**value-of-optimization headline number**.

Bellman's combined schedule mixes both policies:

```
0 .. 6 h     : 4 free edges        — fine-grained start (escape source)
6 .. 264 h   : 30 locked edges     — bulk voyage at constant SOG per 6h
264 h        : 2 free edges        — small re-alignment around an H-line
264 .. 280 h : 3 locked edges      — including the early-terminal edge
                                     that lands EXACTLY at (280h, 3393.595 nm)
```

Locked dominates the bulk because its target-SOG choices are continuous (any SOG in [9, 13]); free dominates at boundaries where a 6 h block is too coarse for the source corner / final-mile alignment.

### 6.3 Implication for the experimental matrix

The combined graph is the cleanest single-shot solver: one Bellman, one node table, two edge generators, strictly better fuel than either alone. All future single-forecast experiments default to combined; free and locked become ablations.

## 7. Complexity vs Luo 2024 (TRC 167, 2024)

Luo et al. 2024 report 146 min (voyage I, 2701 nm, 39 RH runs) and 220 min (voyage II, 3584 nm, 45 runs) for the full rolling-horizon solve — i.e. **~3.7–4.9 min per graph build + Dijkstra solve**. Our combined DP builds in ~230 s and Bellman-solves in 3.9 s on a 3393 nm voyage (~4 min per build). **Per-graph wall-clock is comparable**; the advantage is what we get for that cost.

| Aspect | Luo 2024 | **Combined DP (ours)** |
|---|---|---|
| Per-edge weight | ANN forward pass (10 inputs, hidden up to 32 neurons) | Closed-form `0.000706·SWS³` + analytic SWS inverse — **~5–10× cheaper per edge** |
| Speed range / discretisation | [8, 18] kn × 0.1 step → 101 speeds per node | [9, 13] kn × 0.1 step → 41 speeds — **~2.5× smaller per-source fan-out** |
| Locked-edge dst enumeration | n/a (single-policy) | **Geometric** `d_src + target_SOG·6h`, one edge per (V-src, V-dst), no inverse search |
| Edge sets per build | One graph per RH run | **Free ⊕ locked share the same node table** — one canonicalisation, one Bellman pass |
| Solver | Dijkstra (NetworkX, Python) — `O((V+E) log V)`, priority queue | Forward Bellman in lex topological order — **`O(V+E)`, no PQ** — solve **~10–15× faster** at our V, E |
| Decision per stage | One scalar speed (101 discrete options) | Per-square (1 nm × 0.1 h) free **+** continuous-SOG 6 h locked, mixed by Bellman |
| Within-stage weather | Single snapshot at segment start | **Sub-leg `Σ FCR(SWS_i)·Δt_i`** through every cell + segment crossing |
| Spatial weather aggregation | Point sample at segment-start coordinate | **Cell-canonical mean** (linear for scalars, circular for directions) over every voyage waypoint in the 0.5° NWP cell |
| Continuous SOG choice | Discretised at 0.1 kn | **Continuous in [9, 13] kn** in locked mode (snap-drift = +0.000 nm everywhere) |

**Honest framing**: our build-time edge over Luo is in the **constant factors** — closed-form physics vs ANN, geometric vs search-based locked-edge dst, single Bellman vs multiple Dijkstra runs — not in the asymptotic order. On the solve side, the asymptotic order does drop (`O(V+E)` topological Bellman vs `O((V+E) log V)` Dijkstra). At comparable per-graph wall-clock, we deliver **finer decision granularity** (per-square free + continuous-SOG locked, blended by Bellman) and **better weather fidelity** (sub-leg integration + cell-canonical aggregation). That is the paper-relevant complexity story.

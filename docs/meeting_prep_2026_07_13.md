# Meeting Prep — Supervisor Meeting, July 13 2026

---

## 1. Action Items from July 6 Meeting

*(to fill in after the July 6 meeting)*

| # | Task | Status |
|---|------|--------|
| 1 | *(to fill in)* | not started |
| 2 | *(to fill in)* | not started |
| 3 | *(to fill in)* | not started |

---

## 2. Progress This Week (July 6 → July 13)

### 2.1 §4.2 committed & pushed
- The §4.2 rewrite ("Solving the Bellman equation" — snap grid, Algorithm 1 enumeration, Algorithm 2 forward sweep, tractability) is committed (`c66d19d`) and **pushed to `origin/main`**. §4 and §4.1 left frozen; preamble untouched. Full detail in last week's prep §2.4.

### 2.2 Combined concept figure — cell crossings fixed (Tal's feedback) + committed/pushed
- Built the combined two-panel concept figure `combined_twin_D` (commit `5db3627`, pushed): **(a)** the real Strait-of-Hormuz route over the 0.5° weather cells with a full-route locator inset, **(b)** the same voyage on the time–distance plane (kink = speed change), and **(c)** a structured *point-types* table (cell crossing / 6 h block / heading change / start-arrival).
- **Addressed Tal's note that cell crossings were omitted.** Root cause was an over-aggressive merge (14 NM threshold) + snapping crossings to the nearest coarse track vertex. Rewrote detection to record **every 0.5° cell-index change** along a finely-sampled track → all 6 crossings now shown, faithful to the route.
- Also: forward-walk trajectory so **every numbered point is a real speed-change kink**; explicit per-point badge nudging (dot on line + leader) so clustered points stay legible; badge placements tuned (1,3,4 above; 2 above-left; 5 above-right; 6,7,8 below-left).

### 2.3 Section 4 walkthrough (personal prep aid)
- Built a line-by-line HTML explainer of Section 4 (DP setup, state space, forward Bellman with a two-case geometry diagram, solving algorithms, subtleties). A study companion for the meeting — **not** paper content. (Claude artifact, not in the repo.)

---

## 3. Open Items / Next Steps

### Decisions that need Tal's sign-off (touch frozen §4/§4.1 or the preamble)
1. **Snap grid `ζ`/`τ` into §4.1?** It is load-bearing for Contribution 1's "tractable single sweep" but currently lives only in §4.2. Rec: at least one sentence in §4.1 acknowledging the discretisation.
2. **`\usepackage{algorithm2e}`?** For real "Algorithm N" numbering + `\ref`s (currently package-free `tabbing`, numbers hardcoded). Preamble edit → needs sign-off. Also do a compile-check in Overleaf (watch the long Algorithm 1 "Input:" line).
3. **Wire `combined_twin_D` into §4.1** — replaces the `ADD A FIGURE` placeholder; adds `figures/combined_twin_D.pdf` to the Overleaf uploads. Also edits frozen §4.1.

### §4 / §4.1 clean-ups (still frozen, carried from July 6)
- **Coordinate-order clash** `(d,t)` vs `(t,d)` — pick one (§4.1 mixes both).
- **Recursion typos** in §4.1: `d_i = d_{i-1} + l_{i-1}` should be `+ l_i`; `j(t)` missing `=`; unbalanced parens.
- **`i(d)` strict-`<` corner ambiguity** — for a point on a distance line it names the cell *behind*; worked around in §4.2 prose.
- **leg → subsegment** rename — "leg" still appears.
- **Params before §4** — surface `L`, along-track `d` in §3; `V_s`/`Φ⁻¹` still only in the commented-out block.
- **Engine/attainability envelope undefined in active text** — max-SWS / attainable-SOG bound sits only in the commented block + appendix; a definition belongs in §3.

### §4.2 details to confirm
- **Time-line off-by-one:** §4.1's `{6i:6i<T}∪{T}` → 48 lines for `T=280` (`Θ=47`), code produces 47 — reconcile (likely terminal-`T` handling).
- **Realized vs target SOG:** snap makes `v̄=Δd/Δt` differ slightly from the grid speed; §4.2 uses `v̄` (matches code) — confirm intended.
- **Soft-ETA `λ`** mentioned in §4.2 though §3/§4.1 pose hard ETA only — keep or defer? (Results all hard-ETA.)
- **Tractability numbers** cite Route 1 only — add Route 2, or keep single illustrative instance?

### Related Work / Contributions
- Reword **C1 granularity-first** to match the rebalanced §2.1 (drafted; not yet applied). C2/C3 stay.
- Decide whether C3 ("data-driven evaluation") is a contribution or evidence for C1/C2.

---

## 4. Figures Status

| File | What it is | Status |
|---|---|---|
| `combined_twin_D` | **combined concept figure**: (a) map + cells + locator inset, (b) time–distance twin, (c) point-types table; all cell crossings shown | **lead for §4.1** (pending wire-in) |
| `combined_twin_A/B/C` | same figure, alternative (c) key styles (grouped / table / type-legend) | reference |
| `route_cells_zoom` | standalone spatial map: cell + 6 h + heading points over 0.5° cells | reference / backup |
| `state_space_optF` (+ `_key`) | abstract §4.1 time–distance schematic (`d₀…d_M`) | reference |
| `routes.pdf` | the two study-route maps | in paper |

---

## 5. Questions for Supervisor

1. OK to add one sentence to §4.1 acknowledging the snap-grid discretisation (backs the tractability claim), or keep it entirely in §4.2?
2. Adopt `combined_twin_D` as the §4.1 figure and wire it in? Any changes to the point selection / labels?
3. Add `algorithm2e` for proper algorithm numbering, or leave the current package-free boxes?
4. *(to fill in)*

---

## 6. Thoughts to validate — running log

*Tentative observations about our solution, logged as we go; each to be validated before it becomes a claim.*

**T1 — Weather cells are 0.5° squares in degrees but rectangles in distance, and their shape depends on latitude.** `[status: geometry verified; downstream implication unvalidated]`
- A weather cell is 0.5°×0.5° lat/lon. Using 1°lat = 60 NM and 1°lon = 60·cos(lat) NM:
  - **N–S side = 30 NM** (constant everywhere, ≈ 55.6 km).
  - **E–W side = 30·cos(lat) NM** (shrinks toward the poles).
  - **Diagonal = 30·√(1 + cos²lat) NM**.
- Concrete: Route 1 (Gulf → Malacca, lat ≈ 2–26.5° N) → cells ≈ **30 × 27–30 NM**, diagonal ≈ **40–42 NM**. Route 2 (N. Atlantic, lat ≈ 47–56° N) → cells ≈ **30 × 17–20 NM**, diagonal ≈ **34–36 NM** (much narrower E–W).
- **Implication to validate:** because the E–W side is shorter than the N–S side (except at the equator), the *density of cell-crossing decision points along the track depends on the route's heading*, not just its length — an east–west leg crosses longitude lines more often per NM than a north–south leg. Worth checking how this drives the subsegment count `M` / state-space size per route, and whether the granularity advantage correlates with a route's heading mix (e.g. Route 2's tighter cells → more crossings → more room for finer speed control).

**T2 — Graph orientation (our working convention).** `[status: verified; matches §4.1 + the figures]`
- **Horizontal axis = distance** `d`, left → right (`0` … `L`).
- **Vertical axis = time** `t`, top → bottom (`0` at top, `T` at bottom; time increases downward).
- **Departure** = upper-left corner `(0,0)`; **voyage complete** = bottom-right corner `(L, T)`.
- Any feasible trajectory only moves right-and-down; its steepness encodes speed. Consistent with §4.1 ("vertical distance lines / horizontal time lines") and the `combined_twin` / `state_space_optF` figures.

**T3 — Route → segments → subsegments → distance lines (map-to-graph bridge).** `[status: verified; matches §4]`
- The route is an ordered list of geographic waypoints. Each consecutive pair is a **segment**: a straight, constant-heading leg whose heading is the bearing from the earlier waypoint to the later one (direction fixed by the route order / start point).
- A segment passes through **multiple 0.5° weather cells**. The portion inside one cell is a **subsegment**; a new one starts at every 0.5° lat/lon crossing. Crossing frequency depends on heading (see T1).
- **Two kinds of breakpoint, both become distance lines:** (a) **cell crossings** — weather changes, heading stays; (b) **waypoints** (segment ends) — heading (course ψ) changes. Walking origin → destination interleaves them.
- **Bridge:** each breakpoint sits at a cumulative along-track distance; those distances are the vertical **distance lines** `d₀=0 < d₁ < … < d_M=L`. A subsegment is the stretch between two adjacent distance lines — one cell + one heading, so weather-in-space is fixed across it.
- Nuance: near a cell *corner* a lat-line and a lon-line crossing land within ~1–2 NM, so two distance lines can sit almost on top of each other (real, just close — as seen in the figure).

**T4 — Building the frame: two line families tile the plane into constant-condition rectangles.** `[status: verified; matches §4.1]`
- **Horizontal = time lines**, one every **6 h** (the GFS weather-refresh cycle — the cadence at which weather-in-time may change), plus endpoints at `t=0` and `t=T` (ETA, even if not a multiple of 6). Set `{0,6,12,…}∪{T}`, indexed `t₀=0 … t_Θ=T`.
- **Vertical = distance lines** (T3): (1) every segment change (heading/waypoint), (2) every 0.5° lat/lon cell crossing, plus `d₀=0` and `d_M=L`. Order of drawing the two families is irrelevant — they're independent.
- Together they make a **rectangular grid**; each rectangle = *one cell × one 6 h block* = fixed heading + fixed weather → a single fuel-rate function `φ` for that rectangle. Weather data plugs in here: **actual** weather populates rectangles for the deterministic/ground-truth run, **predicted** for rolling-horizon.
- **Frame ≠ nodes.** These lines are only the skeleton (`frame.py`). The nodes are the *discrete reachable points that land on the lines* — not the whole line — determined by the speed choices + the snap grid (next step).

**T5 — Movement is monotonic (right + down only); each arc stops at the first line ahead.** `[status: verified; matches §4.2.2 / Algorithm 1]`
- Allowed moves: **right** = forward in distance, **down** = forward in time. Forbidden: **left** (back in distance), **up** (back in time). Every trajectory is right-and-down only.
- From a point on a line, pick a speed → travel a straight line (slope = speed) down-and-right until the **first** gridline ahead: either the **next distance line to the right** `d̄(d)` (the immediately adjacent one — must stop there since conditions can change) **or** the **next time line below** `t̄(t)`.
- **Which line you land on is set by the speed, not chosen:** faster → reach the next *distance* line first (distance line binds); slower → reach the next *time* line first (time line binds). Over the whole speed set `V`, one state fans out to successors on *both* the next distance line and the next time line. This is the `δ_d=(d̄−d)/v` vs `δ_t=t̄−t` test in Algorithm 1 (smaller δ binds).
- Edge cases: land on `d=L` → **arrival** (sink); land on `t=T` with `d<L` → **out of time** (dead end).

**T6 — Moving between nodes: the full transition + node-spacing strategy.** `[status: verified; matches Algorithm 1 / atomic_edges]`
- **Flow (speed-first):** on a node `(d,t)` → pick a target speed `v` from the grid `V` → travel straight (slope = v) down-and-right to the **first line ahead** (next distance line right, or next time line below — whichever comes first, T5) → that landing point is the new node.
- **One coordinate is pinned exactly** by the line you hit (`d̄` or `t̄`); **the other (free) coordinate is a continuous arrival value** → **snap it** to the node grid (`τ=0.1 h` on distance lines, `ζ=1 NM` on time lines). Realized speed = `Δd/Δt` to the *snapped* node (slightly off the target — see T-realized/§4.2 "realized vs target").
- **Two distinct parameters — don't conflate them:**
  - `V` (speed grid, e.g. 61 values `v_min..v_max` @ 0.1 kn) = the **menu of speeds you choose from**; sets the fan-out (~61 arcs/node). Independent of node spacing.
  - `(ζ, τ)` (snap / node spacing) = the **rounding of each landing point's free coordinate**; NOT an up-front "dots every X" placement — it's applied per-landing.
- **Why the snap is mandatory (can't skip node spacing):** the free coordinate depends on the *entire* history of speeds (e.g. `t̲ + Σ lₖ/vₖ`), so without snapping no two paths share a node → node count grows `|V|^(lines crossed)` → exponential. Snapping merges near-coincident arrivals onto shared grid points → finite, tractable graph (§4.2.1).
- **Speed variety ≈ `min(|V|, landing-point resolution)`.** Snap-induced speed quantization scales as `δv ≈ ζ/Δt` (distance snap) or `δv ≈ v²·τ/Δd` (time snap) — so it's fine on short legs (V is the binding menu) but can approach/exceed the 0.1 kn V-step on long legs.

# Meeting Prep — Supervisor Meeting, June 29 2026

---

## 1. Action Items from June 15 Meeting

*(to fill in after the June 15 meeting)*

| # | Task | Status |
|---|------|--------|
| 1 | *(to fill in)* | not started |
| 2 | *(to fill in)* | not started |
| 3 | *(to fill in)* | not started |

### Action item for this week — define all parameters before §4 (Methods)

**Goal:** ensure every symbol/parameter used in §4 (Methods) of `paper_workspace/paper_full_draft.tex` is defined in the active (compiled) text *before* §4.

**Root cause found (2026-06-22):** the entire definitional block in §3 (lines ~181–271 — subsections *Vessel and voyage*, *Speed over ground*, *Fuel consumption*, *Decision variable and objective*) is wrapped in `\begin{comment}…\end{comment}`, so none of its symbol definitions compile. §4 then uses symbols that were only ever defined inside that commented-out block.

**Symbols used in §4 with no active definition before it:**

| Symbol | Role in §4 | Status |
|---|---|---|
| `L` | total route length / destination distance | never introduced in active text |
| `V_s` | still-water speed (SWS) | SWS concept absent in active §3 (only SOG named) |
| `V_g` | speed over ground (SOG) | named verbally, symbol unbound |
| `Φ⁻¹(·;w,ψ)` | inverse SOG response | referenced as "of Section 3", but no such function active |
| `w` | sea state | conditions described, symbol unbound |
| `ψ`, `ψ(d)` | heading / course | "course" described, symbol unbound |
| `FCR(V_s)=0.000706·V_s³` | DP cost rate | `eq:fcr` is inside the comment block |
| `[V̲, V̄]`, `V_s^max` | speed band / engine envelope | 11–13 kn only in commented table |
| `Δt` | decision period | 6 h discretisation mentioned, not bound as Δt |

**Knock-on issues to fix at the same time:**
- Broken cross-references: appendix `\eqref{eq:fcr}` and `\eqref{eq:legfuel}` point into the commented block → undefined refs on compile.
- Convexity inconsistency: active §3 states FCR is convex *in SOG*; §4/Discussion argue convexity *in SWS*. Reconcile.

**Fix options:** (a) un-comment and tighten the §3 block so the definitions compile; or (b) add a compact notation/parameter table at the end of §3. Either way, recompile and confirm no undefined references remain.

**Decided (2026-06-22): add these parameters to §3's definition list.** Define the following explicitly in the active §3 text (the `\begin{description}` block), each with its symbol, unit, and role:

| Parameter | Symbol | Unit | Note |
|---|---|---|---|
| Total route length | `L` | nm | currently never introduced as a symbol |
| Along-track distance | `d` | nm | the `d ∈ [0,L]` coordinate used throughout §4 |
| Total voyage time (ETA) | `T` | h | already named in §3 — keep, ensure symbol `T` is bound |
| Speed over ground | `SOG` (`V_g`) | kn | named verbally in §3 — bind the symbol |
| Fuel consumption rate | `FCR` | mt/h | described verbally in §3 — bind the symbol and state the cubic form |

### Action item for this week — rename "leg" → "sub-segment" throughout

**Goal:** refactor every use of the word **"leg"** to **"sub-segment"** in `paper_workspace/paper_full_draft.tex` (and any other paper files where it appears). Rationale: a *segment* is already defined in §3 as the stretch between two consecutive waypoints (constant heading); the finer stretch over which heading **and** weather are both constant is currently called a "leg" — "sub-segment" makes the hierarchy explicit (segment → sub-segments).

**Scope (16 occurrences as of 2026-06-22):**
- Active text — lines 175, 345, 539, 563, 744, 785, 791, 801, 884, 885.
- Commented-out §3 block — lines 186, 251, 254, 257, 261, 270 (only matters once that block is un-commented per the action item above).
- Watch the **compound form "per-leg"** (lines 563, 744, 785, 791, 801) → "per-sub-segment".
- Label/refs: `eq:legfuel` (defined line 254, referenced line 885) — rename label to `eq:subsegfuel` (or similar) and update the `\eqref`.

Sweep with `grep -rin "leg" paper_full_draft.tex` after the rename to confirm none remain (excluding unrelated words like "elegant"/"legacy").

### Idea to develop — a figure visualizing segment / sub-segment / time / space

**Goal:** a conceptual figure that takes a few **segments** of a route, breaks them into **sub-segments**, and visualizes how segment, sub-segment, time, and space relate. Intent is to make the §4 discretisation intuitive — segments (waypoint-to-waypoint, constant heading) subdivided by weather-cell boundaries into sub-segments, laid out in the time–distance plane (distance lines at heading + cell boundaries, time lines at the decision/refresh epochs).

**Status:** exploratory — *we will think about how best to render it.* Candidate directions to discuss:
- A time–distance grid (the §4 state-space picture): x = time, y = distance; horizontal distance lines at segment/cell boundaries, vertical time lines at decision epochs; a non-decreasing trajectory whose slope = SOG, changing speed at each sub-segment boundary.
- A schematic of one or two route segments overlaid on the 0.5°×0.5° weather grid, showing where cell crossings cut a segment into sub-segments.
- Possibly a small two-panel: geographic (segment crossing weather cells) → abstract (resulting sub-segments on the time–distance lattice).

Decide the framing at the meeting; no script written yet.

### Action item — add a grid figure to §4.1 (State space)

**Goal:** add a figure to **§4.1 "State space"** (`\label{sec:states}`) that makes the time–distance grid legible. The text defines two families of grid lines but has no illustration; a reader currently has to build the lattice mentally.

**What the figure must show:**
- Axes: **x = time `t`** (0…T), **y = distance `d`** (0…L).
- **Horizontal distance lines** (constant `d`) at the breakpoints `0 = d₀ < d₁ < … < d_M = L` — placed at every heading change (segment boundary) and every weather-cell crossing.
- **Vertical time lines** (constant `t`) at `0 = t₀ < t₁ < …` — spaced by the decision period `Δt` and the weather-refresh instants.
- **Nodes** at the line intersections / node spacings (`τ` along distance lines, `ζ` along time lines).
- Source `s₀ = (0,0)`, destination set `S_T = {(t,L) : t ≤ T}`, and a sample non-decreasing trajectory whose slope = SOG, bending at each boundary it hits.

This is the concrete, in-paper companion to the broader segment/sub-segment concept figure above (which is more schematic/geographic); keep them distinct — §4.1 grid is the formal state-space picture, the other is the intuition-builder. Decide at the meeting whether one figure can serve both. No script written yet.

---

## 2. Progress This Week

### 2.1 *(to fill in — main work since June 15)*

### 2.2 *(to fill in — secondary work / parity runs / cleanups)*

### 2.3 *(to fill in — anything else between June 15 and June 29 not covered above)*

---

## 3. Open Items / Next Steps

Carried over from June 15 §3 (prune as items close):

- [ ] **Cell-weather caching optimisation** — the RH forecast path paid a cold-cache cost (~8.9 h/voyage in Python); the C++ port fixed the chain but confirm the caching story is documented before scaling further (June 15 §4.12).
- [ ] **Behavioural sanity checks** — zero-weather, constant-weather, lock-monotonicity (carried).
- [ ] **Soft ETA** exercise (carried).
- [ ] **Edison ↔ Shlomo2 collection delta** — re-check whether Edison is still ~12 sample-hours behind; investigate root cause if delta persists (carried).
- [ ] **Phase 4 cleanup tail** — archive or `.gitignore` stale RH/DP result artifacts and CSVs (carried).
- [ ] **Add departure-time x-axis plot** — savings-vs-`sh_base` curve for the RH chain sweep (the §6.2 finding that RH ≤ Naive is departure-dependent is best shown this way).

---

## 4. Progress on Paper / Experiments

*(to fill in — where the SR-vs-Luo RH paper stands; any new runs since June 15)*

---

## 5. Data Collection Status

*(to fill in close to the meeting — snapshot of Shlomo2 / Edison `experiment_b_138wp.h5` / `experiment_d_391wp.h5` extents at run time)*

---

## 6. Results Tables

*(to fill in — any new results beyond the June 15 RH chain sweeps §6.2/§6.3)*

---

## 7. Questions for Supervisor

1. *(to fill in)*
2. *(to fill in)*
3. *(to fill in)*

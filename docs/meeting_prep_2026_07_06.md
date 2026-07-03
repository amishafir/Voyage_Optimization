# Meeting Prep — Supervisor Meeting, July 6 2026

---

## 1. Action Items from June 29 Meeting

*(to fill in after the June 29 meeting)*

| # | Task | Status |
|---|------|--------|
| 1 | *(to fill in)* | not started |
| 2 | *(to fill in)* | not started |
| 3 | *(to fill in)* | not started |

---

## 2. Progress This Week (June 29 → July 6)

### 2.1 Related Work §2.1 rebalanced (granularity-first)
- Reworked §2.1 so the headline is **"granularity of the speed decision is the binding factor"**; convexity is now framed as the *mechanism* (penalises constant speed under varying weather), not the contribution. Luo 2024 **demoted to baseline** (~3 sentences); detailed per-block construction deferred to §5 (`sec:data`). Citations switched to **author–year** (`\documentclass[review,authoryear]`). Commit `8edc979`.
- **Contributions block left unchanged** (C1 still reads method-first) — to reconcile with the granularity-first framing (see §3).

### 2.2 §4.1 state-space figure (Tal's "ADD A FIGURE")
- Built and iterated the state-space / DP-graph figure: `state_space_optF` — one voyage on the time–distance plane, every grid-line crossing a numbered speed-change point, with a **separate per-point key**. Several alternatives explored (A–F, plus `state_space_map`). Convention locked: **vertical = distance, horizontal = time**; heading-change vs cell-crossing distance lines distinguished; the **four boundary-crossing types** formalised (heading / weather-cell / 6 h block / arrival). Commit `ac1fa84`.

### 2.3 Spatial companion map (Tal's request 2026-06-29)
- Built the geographic twin: `route_cells_zoom` — the real **Persian Gulf → Strait of Hormuz → Gulf of Oman** route on a coastline basemap over the 0.5° weather cells, with **all point types** numbered: cell-boundary crossings (brown), **6 h time-block points (blue, placed from the constant-speed schedule)**, and the heading change (navy). Also kept `route_optf_twin` (an exact optF-correspondence variant). Commits `97d4593`, `0f10e93`, + 6 h points added since.

### 2.4 §4.2 written — "Solving the Bellman equation" (the two TODOs closed)
- Wrote the §4.2 stub ("TODO / add pseudo code / enumerate reachable states") into finished content and **deleted the stale old §4.2/§4.3** (the backward `J*`, `f(s,u)`, `Φ⁻¹`, `ρ` formulation). **§4 and §4.1 left untouched** (per instruction); the preamble too. Deleting old §4.3 also removed the **duplicate `\label{eq:cost-to-arrive}`**.
- New §4.2 has four subsubsections: **(i) Discretising the free coordinate** — introduces the snap grid `ζ = 1 NM`, `τ = 0.1 h`; **(ii) Enumerating the reachable states** — forward BFS closure from `(0,0)` + **Algorithm 1**; **(iii) The forward sweep** — lexicographic single-pass relaxation, hard-ETA sink (+ soft-ETA `λ` variant) + **Algorithm 2**; **(iv) Tractability** — real numbers.
- **Numbers grounded in a real SR run** (`experiment_d`, Route 1, ETA 280 h; 163 distance lines, 47 time lines, 61 SOGs): **≈1.5×10⁵ states, 9.2×10⁶ arcs, single Bellman sweep 8.3 s**; arc build ≈830 s (one-off, dominated by per-arc SWS inversion + FCR).
- Full notation audit done: every symbol in §4.2 traces to a definition in frozen §4/§4.1 or is defined at first use.

---

## 3. Open Items / Next Steps

### §4 reconciliation (carried from June 29)
**Update (July 3):** the §4.2 rewrite (2.4) closed items **1, 2, 6** below. Items **3–5, 7–8** concern §4/§4.1, which were **left frozen** on instruction, so they still stand and need Tal's sign-off to touch.
1. ~~**Decide the canonical formulation**~~ — **DONE**: kept forward `C*(d,t)`; old §4.2/§4.3 (`J*`, `f(s,u)`, `Φ⁻¹`, `ρ`) deleted.
2. ~~**Duplicate `\label{eq:cost-to-arrive}`**~~ — **DONE** (old §4.3 removed).
3. **Coordinate-order clash** `(d,t)` vs `(t,d)` — pick one. *(Still: §4.1 mixes both; §4.2 uses `(d,t)` for states and `(t,d)` only for the lex sort key.)*
4. **Define `i(d)`** (subsegment index) — *defined in §4.1 but with strict `<`; see corner ambiguity in "still to resolve" below.*
5. **Fix recursion typos** in §4.1 (`FCR_{i(d)-1}(v,)`, `j(t)` missing `=`, unbalanced parens) — **still open** (frozen).
6. ~~**Orphaned `τ`/`ζ` fragment**~~ — **DONE**: `ζ`/`τ` are now the properly-defined snap grid in §4.2.
7. **leg → subsegment** rename — "leg" still appears; unify. *(§4.2 uses "leg" once for the constant-speed span — keep or rename with §4.)*
8. **Params before §4** — surface `L`, along-track `d` in §3; `V_s`/`Φ⁻¹` still only in the commented-out block.

### §4.2 — considerations baked in (flag for Tal)
- **The snap grid is the tractability mechanism, and it lives only in §4.2.** §4.1 says the reachable set is finite "because `V` is finite" — true but it undersells: without snapping the set grows as `|V|^(lines crossed)` (distinct `Σ lₖ/vₖ` arrival times). `ζ`/`τ` merge coincident arrivals → `|S| = O(M·T/τ + Θ·L/ζ)`, polynomial. **This is what actually backs Contribution 1's "tractable single Bellman sweep."** If §4.1 stays as written, the paper states the tractability *claim* (C1) without the *reason* until §4.2.
- **Push form, not pull.** Pseudocode mirrors the implementation (BFS closure + relax in lex order) — consistent with, but not a literal transcription of, the pull-form `C*(d,t)` recursion in §4.1.
- **`F⋆`** introduced for the optimal-fuel scalar to avoid overloading `C*`.
- **Pseudocode is package-free** (`tabbing` in an `\fbox`, `\footnotesize`) because the preamble is off-limits; "Algorithm 1/2" are **hardcoded** (no auto-numbering, no `\ref`).
- **`φ(d,t;v̄)` corner convention** tied explicitly to the frozen equation's use of the lower-left corner `(d̲,t̲)`, so push-form cost matches the pull-form equation.
- Added a **`t ≥ T` guard** in Algorithm 1 so `t̄(t)=min{tⱼ>t}` is never over an empty set (late sinks still generated → soft-ETA unaffected).

### §4.2 — still to resolve
1. **Should the snap grid `ζ`/`τ` move up into §4.1?** It is load-bearing but §4.1 is frozen. Needs Tal's OK. (My rec: at least one sentence in §4.1 acknowledging the discretisation.)
2. **`algorithm2e`?** For real "Algorithm N" numbering + cross-refs, add `\usepackage{algorithm2e}` to the preamble (above §4.2 → needs sign-off). **No local LaTeX** — compile-check in Overleaf; watch the long Algorithm 1 "Input:" line for overflow.
3. **Latent corner ambiguity in §4.1's `i(d)=argmax{dᵢ<d}`** (strict `<`): for a point exactly on a distance line this names the cell *behind*. Worked around in §4.2 prose; the definition itself is frozen §4.1.
4. **Time-line off-by-one:** §4.1's set `{6i:6i<T}∪{T}` → 48 lines for `T=280` (`Θ=47`), but the code produces 47. §4.2 avoids citing a time-line count so it contradicts neither; reconcile the definition vs code (likely terminal-`T` handling).
5. **Realized vs target SOG:** snapping makes `v̄=Δd/Δt` differ slightly from the chosen grid speed; §4.2 uses `v̄` for both feasibility and fuel (matches code). Confirm this is the intended semantics.
6. **Engine/attainability envelope undefined in active text:** the max-SWS / attainable-SOG bound sits only in the commented block + appendix. §4.2 states feasibility self-contained ("`φ` undefined"), but a proper definition belongs in §3.
7. **Soft-ETA `λ`** is mentioned in §4.2 though §3/§4.1 pose a hard ETA only — keep it there or defer? (All results are hard-ETA; `λ=null`.)
8. **Tractability numbers** cite Route 1 only (`M=162`, `|V|=61`, ~1.5×10⁵ states / 9.2×10⁶ arcs / 8.3 s). Add Route 2, or keep as a single illustrative instance?

### Related Work / Contributions
- Reword **C1 granularity-first** to match the rebalanced §2.1 (drafted; not yet applied — left per instruction). C2/C3 stay.
- Decide whether C3 ("data-driven evaluation") stands as a contribution or is evidence for C1/C2.

### Figures — decisions to make at the meeting
- **Which §4.1 figure** to adopt (the `optF` time–distance figure is the lead candidate; `state_space_optF_key` as its key).
- **Pair** the §4.1 time–distance figure with the **spatial map** (`route_cells_zoom`) as a two-panel so the correspondence is explicit.
- Confirm the spatial map's **granularity** (currently strait → Gulf of Oman, ~11 points incl. 6 h time blocks) is right.

---

## 4. Figures Status

| File | What it is | Status |
|---|---|---|
| `state_space_optF` (+ `_key`) | §4.1 time–distance state space: every crossing a numbered speed-change point | lead candidate |
| `state_space_optA–E`, `state_space_map` | alternative §4.1 treatments (graph / voyages / cells / minimal) | reference |
| `route_cells_zoom` | spatial twin on real map: cell + 6 h time + heading points over 0.5° cells | per Tal's 06/29 note |
| `route_optf_twin` | optF voyage on a real basemap, exact 10-point correspondence | alternative |
| `routes.pdf` | the two study-route maps (existing) | in paper |

---

## 5. Questions for Supervisor

1. *(to fill in)*
2. *(to fill in)*
3. *(to fill in)*

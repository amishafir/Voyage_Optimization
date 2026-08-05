# Meeting Prep — Tuesday 2026-08-05 (Ami ↔ Tal)

Continues from [meeting_prep_2026_07_27.md](meeting_prep_2026_07_27.md). Repo HEAD at time of
writing: `c4f513c` (Tal, Aug 3). Everything below is committed & pushed on `main`.

---

## 0. LIVE MEETING NOTES — Aug 5 (running log)

1. **DECISION: the speed interval becomes 𝒱 = [0, v_max]** (was [v_min, v_max]). **Tal is changing
   it in the draft himself.** Zero speed becomes admissible — waiting/drifting is now a legal
   control.
2. **In progress (live): the pseudocode** — being reworked with Tal.
3. **APPROVED (corrected): the shortest-path paragraph (item 1C) goes at the end of §4.1,
   BEFORE the "Solving the Bellman equation" subsection** — a bridge into §4.2. Apply
   immediately after Tal's push (his region; don't collide with his live edit).
4. **DECISION: don't save all arcs — only the selected one.** Code check (Aug 5): today the
   Python builder (`atomic_edges.py`) materialises ~1.2M `Edge` records (each with Weather/SWS/
   FCR/fuel) and `bellman.py` copies them again into `_outgoing[]` adjacency lists; only
   `parent_arc[]` (the winner per node) is already selected-arc-only. Fix fuses builder+solver
   under cost-to-go: reverse sweep, enumerate Eq.-(5) candidates on the fly, price once per arc
   at its source, keep only (C*, chosen successor) per state — arcs never stored. Memory
   O(|arcs|) → O(|states|) (~10×; × replans in RH). Open choice: light states-only Stage 1 vs
   sweeping the full grid (~6×10⁵ pts, kills the closure/queue entirely). Side effect: audit
   item **B1 dissolves** (no arc accumulator to name). Validation: must reproduce the frozen
   reference values (19-voyage F_DP, backward-compat table). Same change mirrors to
   `dp_cpp/src/atomic_edges.cpp` (`vector<Edge>`).
5. **TO DESIGN LATER — code cleaning: paper-notation-faithful primitives.** The two central
   objects of the formulation must exist in the code as clean, named, single-home constructs
   mirroring the paper 1:1:
   - **`A(d, t)`** — the successor enumeration of Eq. (5) as one function (candidates on the two
     walls, v̄∈𝒱 built in, glide rule inside), instead of enumeration logic spread across
     `atomic_edges.py` builder internals;
   - **`arc_cost(d, t, d̃, t̃)`** = (t̃−t)·φ(d,t;(d̃−d)/(t̃−t)) — the leg-fuel expression as one
     function (derived speed → SWS inverse → FCR → ×Δt), one home for the pricing convention
     (source fixes the cell/block).
   Everything else (streaming solver of item 4, RH, certificate code) should call these two.
   Design session later; ties into item 4's builder+solver fusion and the [0, v_max] change.
6. **OPEN ISSUE (raised in meeting): how to implement a LOWER BOUND in our current
   implementation.** How does the discretised DP certify distance to the continuous optimum
   from below? Known starting points: the §4.3 node-slide polish gives only a tighter UPPER
   bound; the E3 interval-LB prototype (`ddd_lb.py --mode lb`) is sound but loose (~38% of
   F_DP — positional-credit leak); DDD-style refinement is the literature answer
   (Boland2017/Marshall2021) but doesn't port off-the-shelf (continuous move menu,
   geometry-dependent costs). To think through: what LB is achievable *inside the current
   grid/streaming implementation* — e.g., per-rectangle fuel-rate underestimation
   (min-φ over the cell × exact time), grid-refinement bracketing, or a Lagrangian/λ time
   price — and what guarantee each actually gives. Design discussion later; relates to §4.3's
   future-work line and the backbone-DDD sketch.

   **Tal's LB idea (from the meeting, node-first formulation — no snapping involved): travel to
   the chosen node, but pay the speed price of the ADJACENT SLOWER predefined node.** In
   node-first there is no rounding interval — every arc's speed is exact. The relaxation: the arc
   (d,t)→(d̃,t̃) still moves the vessel to (d̃,t̃) (geometry honest, no positional credit — unlike
   E3's box-corner teleport), but its fuel is charged at the speed of the *neighbouring, one-step-
   slower* candidate on the same wall: on the distance wall, arrival one τ later —
   v̄⁻ = (d̃−d)/(t̃+τ−t); on the time wall, advance one δ shorter — v̄⁻ = (d̃−δ−d)/(t̃−t).
   **Why it is a valid LB of the continuous optimum:** a continuous trajectory crosses each wall
   somewhere *between* two adjacent grid nodes; map that crossing to the adjacent FASTER node
   (arrival no later ⇒ ETA feasibility preserved), and the mapped arc's discounted price — the
   slower neighbour's speed — under-runs the true crossing speed, which lies between the two.
   FCR increasing in speed ⇒ every leg undercharged ⇒ the relaxed DP's optimum ≤ F*(continuous).
   **Gap control:** the discount is exactly one grid step per leg (τ or δ over the leg duration),
   so LB tightens automatically with the grid — unlike E3, whose looseness was structural.
   **Implementation:** same arc-pricing path — `arc_cost(…, lb=True)` on item 5's primitive
   prices the neighbour's slope instead of the arc's own; one extra DP run per voyage.
   To check in the design session: the slowest candidate in each window (its slower neighbour
   falls outside — clip at the wall / at v=0 under the new [0, v_max] band), glide-rule arcs
   (two-cell legs), and that the relaxed DP may select a different path (fine — the bound holds
   regardless).
7. **TAL'S FIRST PUSH LANDED (`8c083dd`, Aug 5 17:35) — analysis; HOLDING for his next push.**
   What it contains: (a) §3 band 𝒱 = [0, v_max] + "legs"→"sub-segments"; (b) Eq. (5) gains a
   `t < T` condition in both families (final-time-line states get 𝒜 = ∅); (c) **Algorithm 1
   rewritten: forward/to-arrive, one fused pass** — C*(0,0)=0 seed, priority queue popping
   lex-min (t,d), relax C*(d̃,t̃) ← C*(d,t)+φ(d,t;v̄)Δt, record pred(); extraction backtracks
   pred from (D,T); no arc set stored (= meeting decisions 4 + "one pseudocode"). The unique
   sink (D,T) works because v=0 lets the vessel wait after early arrival.
   **Direction clash:** Eq. (6) is still cost-to-go (successors, C*(d_M,·)=0, answer at origin)
   while the new algorithm is to-arrive (origin seed, answer at (D,T)) — mirrored version of the
   Aug-3 fallout; also the §4.2 intro's "single backward sweep" claim and the approved 1C
   paragraph's closing line depend on which direction wins.
   **Slips in the fresh lines (for Tal, same class as before):** line 9 pushes (d,t) — must be
   (d̃,t̃), else the queue never grows; (D,T) uses undefined D (→ L/d_M); Input line still says
   band [v_min,v_max]; title "Belman's"; line 12 stray "not empty"; waiting arcs at/near d=L need
   𝒜 to emit v̄=0 self-arcs (interacts with C1 anchoring) and φ(d,t;0) must be defined.
   **DECISION (Ami): wait for Tal's next push before touching anything** — walkthrough rewrite,
   1C paragraph, and Eq.-(6) reconciliation all queue behind it.
8. **NEXT TASK (after the meeting, once Tal pushes): rewrite the section after the pseudocode** —
   the flat-§4.2 walkthrough prose (single-pass construction → boundary details → pricing →
   backward sweep → extraction → tractability) must be rewritten to match **Tal's new version of
   the pseudocode** + the 𝒱 = [0, v_max] band. Wait for his push; his lines lead, forward-only,
   old-under-comment. ~~Zoom voice-note transcript to be read + logged~~ — **won't materialise**
   (per Ami); this running log is the record of the meeting's decisions.

**Ripple list to sweep once Tal's edit lands** (do NOT touch before his push):
- **Eq. (5)**: with v_min = 0 the family-1 window loses its slow-side clip (latest arrival
  (d̃−d)/v_min → ∞ ⇒ always clipped by the time wall / T), and family-2's shortest advance becomes
  d + 0·Δt = d ⇒ **Δd = 0 candidates (v̄ = 0) become legal** — the "degenerate arc" discard
  (Δd ≤ 0) and the v̄∈𝒱 filter no longer exclude waiting arcs.
- **Algorithm 1 / flat §4.2 prose**: κ grows (band width/δ,τ); "about eight candidates" and the
  |𝒜| numbers need re-measurement; unattainable-speed discard unchanged.
- **Physics**: φ(d,t;0) must be defined (FCR at zero speed — hotel load? zero? affects whether
  waiting is free or costed).
- **fig:state-neighbours**: cone opens to the vertical (v_min edge becomes the "stay put" line) —
  regenerate after the .tex settles.
- **Luo comparison (§5)**: Luo keeps v_min = 8; band alignment note must say how we handle the
  asymmetry (run Luo at [0,18]-equivalent? note the difference?).
- **Audit interactions**: B-items unaffected; A1/A2 unchanged; C-item "v_{min} typesetting" (C8)
  may become moot if v_min disappears from §3.
- **Code**: dp_rebuild / C++ enumeration read v_min from config — experiments re-run needed once
  the paper's 𝒱 changes are final.

## 1. TOP OF AGENDA — Tal's Aug 3 pass: the cost-to-go flip (finish it together)

Tal's `c4f513c` ("update Bellman formulation…") made two good structural changes to §4.1 and left a
mid-flight pass, same pattern as Jul 23:

**What changed (conceptually right):**
- **Eq. (5) 𝒜(d,t) tightened** — ranges now measured *from the current point* (⌊(t_𝒯−t)/τ⌋,
  ⌊(d_𝒟−d)/δ⌋), and the **speed-band condition v̄∈𝒱 is now inside 𝒜 itself**.
- **Bellman flipped to cost-to-go**: C*(d,t) = min over *successors* (d̃,t̃) ∈ 𝒜(d,t); ∞ when the
  successor sits on the final time line with d < d_M (deadline enforced inside the recursion);
  φ evaluated at the source (d,t) — matches the code's convention exactly.
- **V*(d,t) = the outgoing SOG** ("the subsegment that *starts* at (d,t)") — control-policy reading.
- Bonus consistency: §4.2.2's "the same set over which the recursion minimises" is now literally true
  (recursion and Algorithm 1 both range over 𝒜(d,t)).

**Fallout to close (verified against the current file):**

| # | Where | Problem | Fix type |
|---|---|---|---|
| a | L509 | boundary condition still `C*(0,0)=0` — under to-go must be `C*(d_M,·)=0`, answer = `C*(0,0)` | mechanical |
| b | L736 + §4.2.3 | `eq:opt-fuel` still `F*=min{C*(L,t)}`; the "forward sweep" prose + **Algorithm 2** still describe to-*arrive* (lex order, relax out-arcs, sink selection, soft-ETA at sinks) | **structural — decide who flips it** |
| c | L529 | recovery sentence: "minimising **predecessor** … **incoming** arc … back-tracking to the **origin**" contradicts to-go (record the *successor*, walk *forward* from the origin); its own formula is already outgoing | mechanical |
| d | Algorithm 1 | new line assigns `d̃ ← 𝒟(d)` (an *index*; should be `d_{𝒟(d)}`) and later lines still use the old `d̄/t̄` symbols | mechanical |
| e | §4.1 | typos: "We deonte", "soluton", roman "otherwise" | mechanical |
| f | §4.2.2 | cross-ref stale again: "…exactly as the predecessor (d̃,t̃) does" — in the new equation the rectangle is fixed by **(d,t) itself** | mechanical |

Eq numbering unchanged (eq:slide still (10) → §4.3 refs safe).

**STATUS UPDATE (Aug 4, done with Ami's sign-off): all six items closed, forward-only.** Per Tal's
instruction ("consolidate the pseudocode into one: building the graph via the enumeration is exactly
the calculation the backpropagation needs; end with one–two lines extracting the optimum"),
Algorithm 1 is now a **single three-stage box**:

- **Stage 1 — forward closure** (Tal's Input/Output/init/while/pop lines verbatim): discover
  reachable states, price every arc `(t̃−t)·φ(d,t;v̄)`; candidates = 𝒜(d,t) of Eq. (5) directly
  (v̄∈𝒱 now lives inside the equation → the explicit guard is gone), glide rule kept as an
  annotated boundary rule.
- **Stage 2 — backpropagation**: `C* ← ∞`, `C*(L,·) ← 0`, one pass in *reverse* lex (t,d) order
  (valid: every arc increases both coordinates); Eq. (6)'s ∞ case realised by initialization —
  dead-end states inherit ∞, no separate test. Records the minimising successor (d̃*,t̃*).
- **Stage 3 — extraction (the "one or two lines")**: `F* ← C*(0,0)`; walk forward emitting
  V*(d,t) of Eq. (7).

Consequences: (a) boundary condition now `C*(d_M,·)=0`, answer read at `C*(0,0)` ✔; (b) §4.2.3
retitled "The backward sweep and schedule extraction", prose flipped, **Algorithm 2 absorbed**
(archived under comment), `eq:opt-fuel` = `F* = C*(0,0)`, soft-ETA remark recast as λ·lateness on
Eq. (6)'s ∞ case ✔; (c) recovery sentence → successor/outgoing/forward-walk ✔; (d) dangling d̄/t̄
gone — the merged box references Eq. (5) instead of re-deriving it, so Tal's `d̃←𝒟(d)` index-vs-
coordinate wrinkle dissolved with the line ✔; (e) typos fixed (denote/solution/\text{otherwise}) ✔;
(f) §4.2.2 "as the predecessor does" → "as it does" ✔. Every superseded passage under
`\begin{comment}`; compiles clean (tectonic). **For Tal: eyeball the consolidated box + the flipped
§4.2.3 — his Aug-3 lines are carried verbatim.**

**FOLLOW-UP (Aug 4, same day): §4.2 restructured as a stage-mirrored walkthrough.** §4.1 untouched
(all equations stay there). New §4.2 reading order: intro ("what remains is computational" + the
guiding invariant *the pseudocode introduces no new mathematics — only the order of evaluation*) →
the **line-numbered box up front** (lines 1–16, stage banners cross-ref the subsections) → §4.2.1
"Stage 1: building the reachable graph" (walks one popped state through its two walls; snap
arithmetic + glide rule + arc pricing folded in; new FIG placeholder: one state, two walls, κ
candidates — realises one of §4.1's ADD FIGURE items) → §4.2.2 "Stage 2: backpropagating the
fuel-to-go" → §4.2.3 "Stage 3: reading off the plan" (eq:opt-fuel lives here) → §4.2.4 Tractability
(Eq. 8 moved here, where it's used). Each stage opens with the reader's question: *which decisions
exist / what does each cost to the destination / which do we take*. Former "Discretising" +
"Enumerating" subsections archived under comment; labels preserved (sec:snap, sec:enumerate on
Stage 1; new sec:extract).

Also from `c4f513c`: new `pipeline/dp_cpp/src/MODE_C_PORT_SPEC.md` (394 lines) — **ask Tal what he
wants driven from it** (C++ Mode C port work items?).

## 1B. Full notation & math audit of §3–§4 (Aug 4) — 22 items, none applied yet

Symbol-by-symbol consistency sweep of the active text (comments excluded), §3 through §4.3.
**Nothing has been changed in the .tex** — items below await the go-ahead; Tal-zone items need his
eyes (proposed fix ready for each). Zones: **[T]** = Tal's text/equations, **[A]** = Ami's text.

**Teaching version (why each change is needed, with watch-it-break examples):**
[`docs/audit_explained.html`](audit_explained.html) ·
https://claude.ai/code/artifact/31d3aef0-0e53-469b-b002-bf6f7b241672

### A. Math bugs (wrong as written)

| # | Where | Problem | Proposed fix |
|---|---|---|---|
| A1 **[T]** | Eq. (6), ∞ case | condition is `t̃=t_Θ, d<d_M` — true for **every** non-sink source, so every arc onto the final time line prices to ∞, **including a legal on-time arrival at (L,T)**. Algorithm + code treat (L,T) as feasible; the equation doesn't. | `d < d_M` → `d̃ < d_M` (one tilde) |
| A2 **[T]** | §4.1 cell maps | `i(d)=argmax{d_i < d}` (strict), φ uses rectangle of (d̲,t̲) — but every DP state sits ON a line, so a state at d=d_i selects the cell **behind** the vessel while the leg is priced **ahead** | `<` → `≤` in i(d) and j(t) |
| A3 **[T]** | §4.1 solution prose | "value … is the minimum fuel **to arrive on time at each state**" — to-arrive semantics, contradicts the cost-to-go flip; also "SOG at the **subsegment** that starts at (d,t)" — the object is a *leg* | "minimum fuel to complete the voyage from (d,t) while meeting the ETA, or ∞ if the ETA cannot be met from there"; subsegment → leg |
| A4 **[A]** | §4.2.3 soft-ETA remark | "replace the ∞ case with a lateness charge λ(t̃−T)" — vacuous: t̃≤T on the grid, charge never positive | "extend the time lines beyond T and charge λ·(t̃−T)₊", or revert to sink-side wording |
| A5 **[T]** | §4.1, above Eq. (6) | "formulated as the following **forward** Bellman equation" — stale after the flip | drop "forward" (or "backward") |

### B. Symbol collisions

| # | Where | Problem | Proposed fix |
|---|---|---|---|
| B1 **[T/A]** | Alg. 1 lines 1/7/13, Eq. (9), Stage-2 prose | **𝒜 double duty**: Eq. (5) neighbour set 𝒜(d,t) vs arc-set accumulator 𝒜 | rename arc set → ℰ everywhere (touches one token of Tal's init line) |
| B2 **[A]** | §3 vs §4.3 | `g⁻¹(V_g;w)` = SWS inversion vs `g(q_k)` = slide gain | gain → γ(q_k) in Eq. (10) + text |
| B3 **[A]** | §3 eq:legfuel/eq:obj | d_i = **leg length** in §3 vs d_i = **cumulative breakpoint** in §4 | §3 → l_i |
| B4 **[A]** | §3 eq:obj | M used before it is defined (only §4 defines it) | one clause at first use: "the voyage divides into M such legs" |
| B5 **[A]** | tab:certificate | column "n" = #voyages, colliding with grid-n (Eqs. 4–5) and q_0..q_n (§4.3) | column header → "Voyages" |
| B6 **[T/A]** | §4 intro | L first used (`d∈[0,L]`) but never defined | add "(L the total route length, NM)" |
| B7 **[A]** | Stage 1 vs §4.2.4 | κ used before definition; "typically κ≈8" (typical) vs "at most κ" (bound) | Stage 1: "typically about eight"; §4.2.4 owns κ |

### C. Precision / cosmetics

| # | Where | Problem | Proposed fix |
|---|---|---|---|
| C1 **[T — question, not a fix]** | Eq. (4) vs Stage 1 snap | Eq. (4) anchors grid points at line crossings going **backward** (d_i−nδ; d_i not δ-multiples) while ⟨x⟩_δ:=δ·round(x/δ) is **absolute** rounding — two different grids (τ case coincides since t_j are 0.1-multiples; T edge-case aside) | **ask Tal**: state d_i pre-snapped to the δ-grid, or define the snap anchored |
| C2 **[A]** | Stage 1 prose | "every τ-multiple / δ-multiple" — should be "τ-spaced grid points" (anchored per Eq. 4) | reword |
| C3 **[T]** | §4.1 | `𝒟(d)=argmin_i{i∈ℕ: d_i>d}` — argmin of a membership predicate | `min{i : d_i>d}` (also 𝒯, i(d), j(t)) |
| C4 **[T]** | §4.1 | "held constant across the rectangular sub-space it traverses" (singular) — overclaims under the glide rule (leg crosses two cells) | add the same caveat as §4.2.1 / tie to standing item 3a |
| C5 **[T]** | §4.1 | stale "Figure~X" placeholder | → \todo{FIG…} like the others |
| C6 | (info) | restructure swapped equation numbers: eq:opt-fuel now (8), eq:state-bound now (9); eq:slide still (10) → §4.3 refs safe; all refs are \eqref | no .tex action; prep item 1's "(8)=state-bound" note superseded by this row |
| C7 **[A]** | box/prose vs Eq. (6) | L vs d_M and T vs t_Θ mixed (legal — Input line states d_M=L, t_Θ=T) | harmonize prose/box to L, T; leave Tal's Eq. (6) as is |
| C8 **[A/T]** | §3 | `v_{min}` (italic sub) vs `v_{\min}` | normalize to \min |
| C9 **[T]** | §3 opening block | ~20 typos (controling, fule, utlizing, determinstic, stocastic, consuption, berifely, seleceted, "will satisfying", "and and", Beufor, …) | typo pass, forward-only |
| C10 **[A]** | §3→§4 seam | φ(d,t;v)=FCR(g⁻¹(v;w(d,t))) implied but never written | one sentence after Tal's φ definition |

**Proposed split (awaiting go-ahead):** apply B2–B5, C8, C10 directly (Ami text); apply A1–A3, A5,
B1, B6, C3–C5, C9 with old-under-comment + this table as Tal's review checklist; C1 is a design
question for the meeting, not a unilateral fix.

**Status update (Aug 4, later):** **A4, B7, C2 are RESOLVED** — they fell inside the sentences
rewritten by the flat-§4.2 pass below (soft-ETA now "extend time lines beyond T, charge
λ·max(0,t̃−T)"; κ removed from first mention; "τ/δ-spaced grid point" wording). C7 largely moot
(prose/box consistently L,T; Tal's Eq. (6) untouched). All other items still pending.

**FLAT §4.2 REWRITE (Aug 4, same day, Ami's direction):** §4.2 is now ONE section — no
4.2.1–4.2.4. The prose is built around the single claim, stated in the opening paragraph and
quantified at the end: *discovering the reachable states, placing them on the grid, and pricing
every arc with its FCR happen in one forward pass — the optimised graph construction (graph comes
out fully priced, expensive physics paid once per arc); solving then costs a single backward sweep
(one evaluation of Eq. (6) per state) yielding the optimal speed of every state — a full policy.*
Reading order: claim intro → line-numbered box (Stage 1/2/3 banners kept as visual chunking, section
cross-refs dropped) → single-pass walkthrough (one popped state, two walls, micro-example + FIG
placeholder) → boundary details → pricing → backward sweep → extraction → cost (Eq. 8/9 + Route-1
numbers). **FIG realised (Aug 4):** `figures/state_neighbours.pdf` (`plot_state_neighbours.py`) now
in §4.2 as `fig:state-neighbours` — one state, two walls, speed cone, the two Eq.-(5) families
(τ-dots on the distance wall, δ-squares on the time wall), clip + cap illustrated, κ=8. One §4
figure placeholder down; remaining: the two §4.1 ADD FIGUREs, §5 forecast-error, §7.3
savings-vs-departure. Old headings/openings archived; labels sec:snap/enumerate/sweep/extract/tractability
stacked under sec:solve so no \ref dangles.

## 1C. APPROVED IN MEETING — shortest-path paragraph, placed BEFORE §4.2 "Solving the Bellman equation"

**Decision (Aug 5 meeting, corrected): add it — placement is at the END of §4.1, immediately
BEFORE the \subsection{Solving the Bellman equation}** — a bridge: the equations just stated get
their graph reading, and §4.2 then opens as "how to compute these shortest distances". **Apply
right after Tal's push lands** (he is editing the same region live — do not touch §4 before
then). Text for the bridge position:

> ```latex
> Equations~\eqref{eq:cost-to-arrive}--\eqref{eq:opt-speed} admit a compact graph reading:
> the states of $\mathcal{S}$ are the vertices of a directed acyclic graph, and each admissible
> leg $(d,t)\to(\tilde d,\tilde t)$ with $(\tilde d,\tilde t)\in\mathcal{A}(d,t)$ is an arc
> weighted by its leg fuel, $(\tilde t-t)\,\phi(d,t;(\tilde d-d)/(\tilde t-t))$. Minimising the
> voyage fuel subject to the ETA is then a \emph{shortest-path problem} on this graph:
> $C^{*}(d,t)$ is the shortest distance from $(d,t)$ to the set of destination vertices
> $\{(d_M,t):t\le T\}$, and the optimal speed schedule \emph{is} the shortest path from $(0,0)$
> --- each of its arcs read as a leg speed via Eq.~\eqref{eq:opt-speed}. Because every arc
> strictly increases both coordinates, the graph is acyclic, so the shortest path requires no
> label-setting method such as Dijkstra's; the next section computes it with a single backward
> sweep.
> ```

> ```latex
> Equations~\eqref{eq:cost-to-arrive}--\eqref{eq:opt-speed} admit a compact graph reading: the
> states of $\mathcal{S}$ are the vertices of a directed acyclic graph whose arcs are the
> admissible legs, $(d,t)\to(\tilde d,\tilde t)$ for $(\tilde d,\tilde t)\in\mathcal{A}(d,t)$,
> each weighted by its leg fuel $(\tilde t-t)\,\phi(d,t;(\tilde d-d)/(\tilde t-t))$. Minimising
> the voyage fuel subject to the ETA is then a \emph{shortest-path problem} on this graph:
> $C^{*}(d,t)$ is the shortest distance from $(d,t)$ to the set of destination vertices
> $\{(d_M,t):t\le T\}$, the $\infty$ case marks vertices from which no destination vertex is
> reachable, and the optimal speed schedule \emph{is} the shortest path from $(0,0)$ --- each of
> its arcs read as a leg speed via Eq.~\eqref{eq:opt-speed}. Because every arc strictly increases
> both coordinates, the graph is acyclic, so the shortest path is found by the single backward
> sweep of Algorithm~1, with no need for a label-setting method such as Dijkstra's.
> ```

Notes: (i) purely additive — no existing sentence changes; (ii) "shortest distance = fuel" makes
arc weight vs edge length explicit; (iii) if Tal wants the Luo echo in the same breath, one more
sentence: "Luo (2024) solves an analogous multistage graph with Dijkstra's algorithm; the
time--distance DAG makes even that unnecessary." (iv) interacts with audit item A1 — the ∞
sentence above states the *intended* semantics (successor-side), so A1's tilde fix should land
with it.

## 2. NEW SINCE LAST PREP — §4.3: the discretisation certificate (Tal to review & bless)

Full story: `docs/ddd_experiment_plan.md` + running log T25–T26 + walkthrough HTML Part 5.

- **Origin:** Ami's question — "the optimal speed is decided between two grid nodes; is there a
  scientific way to bound the distance to a better decision?" → identified **Michael Hewitt** (EiC,
  Transportation Science) and **Dynamic Discretization Discovery** as the method family.
- **Experiments (all 19 voyages):** grid halving/doubling (E1: ±0.08 % / ±0.5 %, **non-monotone** —
  extrapolation unreliable); **node-slide certificate + iterated continuous polish** (E2): recovered
  **0.17–0.87 %, mean ≈ 0.4 %**, ≤ 20 sweeps; **SR–Luo gap exceeds recovery on every voyage — min
  2.3×, mean 7.6×**; polish improves only SR ⇒ conservative in the baseline's favour. Global DDD-style
  interval LB (E3): sound but loose (~38 %) — positional-credit leak; **future work**.
- **In the paper:** standalone **§4.3** "How much does the grid cost? A local-optimality certificate"
  (`f6086fb`) — purely additive (0 deletions), Eq. (10), `tab:certificate`, three observations, DDD
  future-work note. Refs **Boland2017** (OR 65(5)) + **Marshall2021** (TranSci 55(1)) DOI-validated,
  in refs.bib. **Related Work untouched** — the two drop-in §2.1 sentences await Tal's OK (carried
  from Jul-27 prep item 6).
- **Framing rule:** §4.3 is a *local* certificate "in the spirit of" DDD — never present it as an
  implementation of DDD.
- **New finding to flag:** **band-violation audit** — 7/19 optimal schedules contain 1–2 corner legs
  with v̄ rounded marginally outside 𝒱 (node-first range-end rounding; root cause of E1's
  non-monotonicity). Cheap clamp in the enumeration when convenient.
- **Follow-up-paper sketch (discuss if time):** backbone-DDD — memberships (which block each cell is
  crossed in) as the discovered objects; within a fixed backbone the timing problem is convex and
  exactly solvable (Norstad/Hvattum); toy 3×3 example worked end-to-end (LB₀ 13.41 → certified
  F* = 14.06 in one refinement; plot in scratchpad). Natural venue: Transportation Science.

## 3. Decisions needed from Tal (consolidated)

1. **Who completes the cost-to-go pass** (item 1b — §4.2.3 + Algorithm 2 flip); Ami can do it
   forward-only today.
2. **Bless §4.3** (content + placement + wording), then approve the **§2.1 two sentences**
   (drop-in text in the Jul-27 prep, item 6).
3. **Carryover from Jul 27** (confirm status):
   - 𝒜(d,t) vs glide-past corner (item 3a) — partially improved by the new Eq. (5) (ranges from the
     current point) but the glide-past successors beyond d_𝒟 are still not in Eq. (5).
   - Figures plan (2× `ADD FIGURE` in §4.1, `FIG` forecast-error §5, `FIG` savings-vs-departure §7.3,
     fused-voyage figure placement).
   - One-sentence §5 note that Luo's lattice is likewise node-first.
   - Overleaf sync discipline (repo = source of truth; sync before compiling).
4. **Certificate as method?** The polish is cheap (~40 s/voyage) and strictly improves SR — keep as
   §4.3 measurement (recommended) or make "SR + polish" the reported method (would need a matching
   baseline polish for fairness)?
5. Next milestones: figures → internal review pass (paper-reviewer / paper-critic) → TR-C submission
   logistics.

## 4. Reference — key artifacts & files

| What | Where |
|---|---|
| §4 walk-through (5 parts, incl. §4.3 + Eq. 10 breakdown) | `docs/state_space_evolution.html` · artifact e4d27d69 |
| DDD experiment plan + results (E1–E3, 19-voyage batch) | `docs/ddd_experiment_plan.md` · data `runs/2026_07_28_local_certificate/` |
| Certificate code | `pipeline/dp_rebuild/ddd_lb.py` (modes: local / lb / batch) |
| Running log T1–T26 | `docs/meeting_prep_2026_07_13.md` §6 · artifact c6f85de8 |
| §3–5 method change-log | `docs/method_changes_node_first.html` · artifact 929178ab |
| Node-first vs speed-first comparison | artifact 1b54698c |
| Tal's new C++ spec | `pipeline/dp_cpp/src/MODE_C_PORT_SPEC.md` |

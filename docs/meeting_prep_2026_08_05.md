# Meeting Prep — Tuesday 2026-08-05 (Ami ↔ Tal)

Continues from [meeting_prep_2026_07_27.md](meeting_prep_2026_07_27.md). Repo HEAD at time of
writing: `c4f513c` (Tal, Aug 3). Everything below is committed & pushed on `main`.

---

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

Also from `c4f513c`: new `pipeline/dp_cpp/src/MODE_C_PORT_SPEC.md` (394 lines) — **ask Tal what he
wants driven from it** (C++ Mode C port work items?).

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

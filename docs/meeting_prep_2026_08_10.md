# Meeting Prep — Monday 2026-08-10 (Ami ↔ Tal)

Continues from [meeting_prep_2026_08_05.md](meeting_prep_2026_08_05.md). Repo HEAD at time of
writing: `b807a71`. All items below are OPEN; everything closed since the Aug-5 meeting is listed
briefly at the bottom for context.

---

## 1. TOP OF AGENDA — settle the direction of Eq. (6) (Tal)

Tal's Aug-5 Algorithm 1 (`8c083dd`) is **forward / to-arrive**: seed `C*(0,0)=0`, relax successors,
`pred()` backtrack from the terminal state. But §4.1 still carries the **cost-to-go** version from
Aug 3: Eq. (6) minimises over successors with `C*(d̃,t̃)` inside, boundary `C*(d_M,·)=0`, and
`V*` (Eq. 7) defined via the minimising *successor* `(d̃*,t̃*)`.

**One decision resolves a whole cluster:**

| If Eq. (6) flips back to TO-ARRIVE (matches the algorithm) | If Eq. (6) stays COST-TO-GO |
|---|---|
| Eq. (6) rewritten: min over predecessors, `+φ` of the incoming leg | Algorithm 1 must flip (again) to a backward sweep |
| boundary reverts to `C*(0,0)=0` (matches Alg. line 1) | keep `C*(d_M,·)=0` |
| Tal's prose "minimum fuel **to arrive** on time" (audit A3) becomes **correct as is** | A3 needs the "fuel to complete the voyage from" rewrite |
| "the following **forward** Bellman equation" (A5) becomes **correct as is** | A5: drop "forward" |
| A1 (∞-case tilde) **disappears** with the case itself | A1: `d < d_M` → `d̃ < d_M` still needed |
| Eq. 7 V* redefined via pred (incoming leg) | Eq. 7 stays |

§4.2's walkthrough is already written to-arrive (matches the algorithm), and the 1C shortest-path
paragraph was worded direction-neutral — both survive either choice.

## 2. Tal's fresh pseudocode lines — five slips (same class as before)

1. **Line 9**: `if (d,t) ∉ Q then push(Q,(d,t))` — must push **(d̃,t̃)** (the improved successor);
   as written the queue never grows and the loop ends after one state.
2. **Extraction line 10**: `curr ← (D,T)` — `D` is undefined (→ `L` / `d_M`).
3. **Input line** still says speed band `[v_min, v_max]` — should be `[0, v_max]`.
4. Title: "Solve the **Belman's** equations" → "Bellman".
5. Line 12: "while curr ≠ (0,0) **not empty**" — stray words.

Also to confirm with Tal: the unique terminal state `(D,T)` relies on **waiting arcs** — Eq. (5)
must actually emit v̄=0 self-advancing arcs near/at `d = L` (𝒟(L) is an empty min — formalism gap),
and **φ(d,t;0) must be defined** (is waiting free, or hotel load?). The φ(·;0) decision also
**blocks the re-runs** (item 5).

## 3. Audit remainder (from prep-08-05 §1B; A4/B7/C2/C7 already resolved)

**Tal's zone [T]:** A2 (cell maps `<` → `≤`: on-line states currently price the leg with the
rectangle *behind* the vessel), C1 (**anchored vs absolute** δ-grid — design question), C3
(argmin-of-a-set notation), C4 (glide overclaim: "held constant across the rectangular sub-space"
vs two-cell glide legs — standing item 3a), C5 ("Figure X" → can now point at
`fig:state-neighbours`), C9 (§3 typo pass — the new band paragraph kept "seleceted",
"will satisfying", "and and"), **C11 (new, Aug 7)**: the sentence after Eq. (5) says arrivals are
"**snapped** to the τ-grid / δ-grid" — under node-first nothing is snapped post hoc; the
candidates are *drawn from* the grid and the leg speed between two known nodes is exact. Suggest
"drawn from the τ-grid / δ-grid". (Ami's §4.2 prose was corrected on the same point on Aug 7 —
the "half-a-step timing error" relic is gone; Eq.-(5)'s sentence is Tal's to fix.)

**Ami's zone [A], quick batch (~30 min, waiting for go-ahead):** B1 (arc set vs 𝒜(d,t) in Eq. 9 —
naming decision: ℰ?), B2 (§4.3 gain g→γ, collides with §3's g⁻¹), B3 (§3 d_i = leg length →
l_i), B4 (M used in §3 before definition), B5 (tab:certificate column "n" → "Voyages"), B6 (L
defined at first use), C8 (v_max typesetting consistency), C10 (one sentence:
φ(d,t;v) = FCR(g⁻¹(v; w(d,t))) — closes the §3→§4 seam).

## 4. Code work queued (designs agreed Aug 5, implementation pending)

1. **Don't save arcs** (decision 4): fuse builder+solver — stream Eq.-(5) candidates during the
   pass, keep only `(C*, pred)` per state. Python (`atomic_edges.py` + `bellman.py`) then the C++
   mirror. Must reproduce the frozen 19-voyage reference values bit-for-bit.
2. **Clean primitives** (decision 5): `A(d, t)` (Eq. 5 as one function: two walls, v̄∈𝒱 built in,
   glide rule inside) and `arc_cost(d,t,d̃,t̃)` (derived speed → SWS inverse → FCR → ×Δt; source
   fixes the rectangle). Everything (solver, RH, certificate) calls these two.
3. **Lower bound** (decision 6, Tal's idea): price each arc at the **adjacent slower node's**
   speed — real move, discounted rate; no positional credit (fixes E3's leak); gap = one grid step
   per leg. Implement as `arc_cost(..., lb=True)` + one extra DP run. Edge cases: slowest
   candidate in a window, glide arcs. Together with the §4.3 polish this gives
   **LB ≤ F*(continuous) ≤ F_polished ≤ F_DP** — a full bracket from the same machinery.

Items 1–3 interlock and land best as one refactor, after φ(·;0) and the Eq.-(6) direction settle.

**STATUS (Aug 7):**
- **Items 1+2 UNDERWAY — Python side green.** Design doc `docs/refactor_streaming_design.md`
  (approved). Phase 0: `regression_freeze.py` + goldens committed (quick + full 19-voyage sets;
  quick reproduces the July-16 sweep exactly). Phase 1: `neighbour_candidates()` (= A(d,t)) and
  `price_candidate()` (= arc_cost) extracted verbatim in `atomic_edges.py` — **bit-exact**.
  Phase 2: `streaming.py` one-pass fused engine behind `SR_main --engine streaming` —
  **bit-exact on the quick set** (fuel, schedule sha256, arc counts identical); full 19-voyage
  gate running. Remaining: flip default (Phase 3), C++ mirror (Phase 4), PhiOracle cleanup
  (Phase 5).
- **Memory finding:** the ~6–8 GB footprint is dominated by the **VoyageWeather/frame cache**,
  not the arc set (single-voyage RSS: legacy 6.21 GB vs streaming 6.03 GB). The arc-set saving
  matters mainly for RH (× replans) and C++; the weather-cache footprint is a **separate
  investigation** — add to the design-later list.
- **Item 3 (lower bound) STARTED in parallel** — background agent prototyping
  `pipeline/dp_rebuild/lb_bound.py` (neighbour-price relaxation on the current band, quick-set
  voyages, sanity vs goldens + bracket vs the §4.3 polish); plan/results to land in
  `docs/lb_neighbour_price_plan.md` + `runs/2026_08_07_lb_neighbour_price/`.

## 5. THE BIG ONE — re-run everything under 𝒱 = [0, v_max]

All §5–§7 results, the §4.3 certificate table, the Tractability numbers (marked "measured under
the pre-Aug-5 band"), and κ are all still pre-band-change. **Blocked on: φ(d,t;0) definition** (item
2 above). Note Luo keeps v_min = 8.0 — the §5 band-alignment note must say how the comparison
handles the asymmetry.

## 6. Carryovers (from Jul-27 / Aug-5, updated Aug 7)

- **§4.3 REMOVED from the rendered paper (Aug 7, Ami's decision)** — to be **re-written once the
  lower-bound analysis strategy is established** (the neighbour-price LB prototype is sound but
  16–18 % loose at the current grid; see `docs/lb_neighbour_price_plan.md`). Content preserved
  under `\begin{comment}` in place; labels sec:certificate / eq:slide / tab:certificate inactive;
  the one outside reference (§4.2 snap paragraph) rewired. Consequences: the **§2.1 two drop-in
  sentences are ON HOLD** (they referenced sec:certificate), the "§4.3 blessing" ask to Tal is
  superseded, and the "certificate as method?" question folds into the future LB-strategy design.
  The polish machinery (`ddd_lb.py`) and the 19-voyage results remain valid inputs for the
  rewrite.
- Figures remaining: §5 forecast-error, §7.3 savings-vs-departure, fused-voyage placement.
- One-sentence §5 note that Luo's lattice is likewise node-first.
- Overleaf sync discipline (repo = source of truth; **pull before compiling** — bit us again Aug 4
  with the missing figure binary).
- `pipeline/dp_cpp/src/MODE_C_PORT_SPEC.md` — what does Tal want driven from it?
- Next milestones: internal review pass (paper-reviewer / paper-critic) → TR-C submission.

## 7. Docs debt (Ami, no decisions needed)

- `docs/state_space_evolution.html` Parts 6–7 still describe the backward-sweep version → add
  Part 8 (Tal's forward algorithm + flat §4.2 + the two-panel figure).
- `docs/audit_explained.html` statuses stale (A3/A5 now direction-dependent; A4/B7/C2 resolved).

---

## Closed since Aug 5 (context)

- 𝒱 = [0, v_max] in §3 + Eq. (5) `t<T` guard + forward Algorithm 1 — **Tal** (`8c083dd`; his
  "failed push" had actually succeeded — the emailed file was byte-identical).
- 1C shortest-path paragraph inserted (end of §4.1, direction-neutral) — `81b27d1`.
- §4.2 walkthrough rewritten to the forward algorithm ("not four steps but one", only `(C*, pred)`
  stored, extraction backtracks from `(L,T)`, `eq:opt-fuel` = `C*(L,T)`) — `81b27d1`.
- `fig:state-neighbours` → **two-panel pair** (a: state on a distance line, κ=13; b: state on a
  time line, κ=17), clean half-width panels, one joint caption — `389e0ac`, `b807a71`.

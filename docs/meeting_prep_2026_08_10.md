# Meeting Prep — Monday 2026-08-10 (Ami ↔ Tal)

Continues from [meeting_prep_2026_08_05.md](meeting_prep_2026_08_05.md).
**Meeting summary (accomplished + attention points):**
[`docs/meeting_summary_2026_08_10.html`](meeting_summary_2026_08_10.html) ·
https://claude.ai/code/artifact/1e76aeac-0c53-4578-914e-fdc2fb9c8fd8
**Lean question card for the meeting:** [`docs/monday_questions_2026_08_10.html`](monday_questions_2026_08_10.html) ·
https://claude.ai/code/artifact/d290de53-5404-432f-8a0f-1f937e475b3a Repo HEAD at time of
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
and ~~φ(d,t;0) must be defined~~ **φ(d,t;0) DECIDED — see section 2A below**.

## 2A. DECIDED (Aug 7, Ami): φ(d,t;0) = 0 — waiting is FREE. Change inventory (designed, not yet applied)

**The decision:** waiting burns no fuel. It makes Tal's extraction argument exact — arrive early,
wait to T for free, so C\*(L,T) = min over all sinks and **(L,T) is the unique terminal state** —
at the price of one conscious modeling statement: the DP may wait out storms mid-ocean at zero
cost.

**The subtle consequence to state in the paper:** φ(·;0)=0 creates a **discontinuity at v=0 in
adverse weather** (as v→0⁺, station-keeping against the current needs positive SWS ⇒ φ(v)→φ₀>0,
while φ(0)≡0). So in adverse cells, mixing free waiting with faster sailing can beat constant slow
creeping — the DP finds this automatically (convex envelope through the origin), but §4's
structural claim "SOG constant within a rectangle" needs the caveat **"constant except possibly
mixed with waiting"**. In calm/following weather φ is continuous through 0 and the claim survives.

**Physics nuance (Ami's question, Aug 7): "SOG=0 still needs the engine because of currents —
correct?" Yes.** True station-keeping (position held) forces SWS = losses − V_c∥: strictly
positive against a head current (fuel > 0), and *unrepresentable* in a strong following current
(reverse thrust; g⁻¹(0;w) has no solution). Engine-off drifting IS free but does not hold
position. So φ(·;0)=0 is an **idealized free pause** — neither station-keeping nor drifting. It
is physically exact only **at the destination** (moored, engine off) — which is where the
convention does its load-bearing work (unique terminal state (L,T)). Mid-ocean, time-varying
weather will let the DP "park for free" ahead of a storm block — an idealization to state
explicitly. Three variants for Monday: **(a)** keep φ(·;0)=0 everywhere, declared as an
idealization (simplest; storm-parking becomes a discussion point); **(b)** waiting free **only at
d = d_M** (physically clean, keeps the unique-sink extraction, removes storm-parking; Eq. (5)'s
waiting candidate then restricted to the destination); **(c) — RECOMMENDED (Aug 7 discussion,
Ami's proposal): price mid-ocean waiting at the station-keeping cost, symmetric thrust, free only
at d = d_M.** φ(d,t;0) = FCR(|SWS needed to hold position|), with "same cost forward and
backward" declared as an assumption (the resistance model has no validity at SOG≈0/astern, and
real props deliver ~30–50% thrust astern — one honest sentence in the paper). What it buys:
continuity of φ through v=0 on the head-current side ⇒ **the constant-SOG-per-rectangle claim
survives with NO caveat**; storm-parking stays available but honestly priced (holding against a
2-kn current ≈ 0.05 mt/h vs ~1.2 mt/h sailing — cheap, not free); free-at-destination keeps the
(L,T) unique-sink extraction exact. Known quirk: in following currents φ(v) is V-shaped with its
zero at the drift speed (going slower than drift = braking) — physically sensible, worth knowing.
Implementation: K2 becomes "solve hold-thrust magnitude → FCR" instead of "return 0" — still one
home in arc_cost; K1 unchanged.

**Paper changes — Tal's zones [T]:**
1. Eq. (5): emit the **waiting candidate (d, t_𝒯(t)) unconditionally** — family 2 only yields
   d′=d when the cell width is δ-aligned (interacts with C1 anchoring).
2. Waiting at d = d_M: 𝒟(L) is an empty min ⇒ 𝒜(L,t) undefined — needs a d=d_M clause or a
   prose convention.
3. One sentence at the φ definition: "By convention φ(d,t;0)=0 — waiting burns no fuel."
4. §4 structural-property 3: the constant-SOG caveat above.
5. **Open (blocks re-runs):** what is **v_max** now (mean+3? vessel cap?), and the **Luo band
   policy** (keep Luo at its own 8–18? run at [0,v_max] where a v=0 block = waiting?).

**Paper changes — Ami's zones [A], ready on go-ahead:** §4.2 extraction paragraph gets the
explicit "waiting is free ⇒ C\*(L,T)=min over sinks ⇒ unique terminal state" justification;
intro's "continues to the deadline at zero speed" + "at zero cost"; figure captions note the
vertical cone edge is itself a candidate (the free wait); Tractability numbers pending
re-measurement.

**Code changes (Python then C++ mirror; gates per the streaming-refactor pattern):**
- K1 `neighbour_candidates`/C++ node-first block: emit the wait candidate (src_d, next_v) at
  every state (currently killed by the d′>d+ε guard); guard the family-1 t_slow = Δd/v_min
  division at v_min=0 (window clips at wall/T only).
- K2 `price_candidate`/C++ pricing: special-case Δd=0 → sog=sws=fcr=fuel=0. **The φ(·;0)=0
  convention lives here, in the arc_cost primitive — one home.**
- K3 band defaults: v_min=0 in GraphConfig (both languages); `--min_speed` kept as override so
  the frozen 19-voyage goldens stay reproducible.
- K4 extraction: NO code change — min-over-sinks best_sink ≡ (L,T)-unique-sink under free
  waiting (equivalence noted; no waiting-at-L arcs materialised).
- K5 streaming invariant survives (waiting arcs still have Δt>0; pop order stays topological).
- K6 new goldens `*_v0.json` minted after the change; old goldens retained.
- K7 `lb_bound`: v⁻ clips at 0; slowest-candidate discount hits φ(0)=0 ⇒ bound loosens further
  (already an open question in the LB plan).
- K8 RH band centring (`v_min = mean−3` in both sr_solves) → 0; interacts with the v_max
  convention (item 5 above).

**E-B TEST RESULTS (Aug 8, `runs/2026_08_08_variant_c_test/`, prototype behind
`--wait_arcs {off,free,hold}`, gate E-A bit-exact):** on both quick-set voyages, **the optimizer
never waits — not even for free** (0 wait legs in all configs; the 571k waiting arcs were
generated and priced, they just never win: with a hard ETA, slow-steaming beats wait-then-sail on
our weather). Variants (a) and (c) give **identical fuel to the last digit**; the band change
itself is a fuel non-event (R2 identical; R1 +0.017 mt = the regained deadzone H-line, not the
band). **⇒ the φ(·;0) choice is empirically free on this data — decide on formal grounds, where
(c) stays the recommendation.** Engineering finding: the open band inflates arcs ~14× / runtime
~13× for nothing — an **ETA-feasibility arc cut** (prune candidates from which the destination is
unreachable at v_max) is required before the full 19-voyage re-run. Caveats: 2 voyages; both
optima use the full ETA; RH/delay scenarios may differ.

**Sequence:** [A]-zone paper edits + K1–K6 implementable now behind config; the re-runs (section
5) additionally wait on the two [T] open points (v_max convention, Luo band policy) and Tal's
blessing of the Eq.-(5) waiting candidate.

## 2B. MEETING SUMMARY — SOG = 0: the decisions, and the paper/equation change list

### 1. Decisions regarding SOG = 0 (chronology → final state)

| # | Decision | Who/when | Status |
|---|---|---|---|
| 1 | Band 𝒱 = [0, v_max] — waiting becomes a legal control | Tal, Aug-5 meeting | in the draft (§3) |
| 2 | φ(d,t;0) = 0 — waiting free | Ami, Aug 7 | superseded by #4 |
| 3 | Physics check: SOG = 0 **requires the engine** in any along-track current (SWS = losses − V_c∥; unrepresentable in strong following current). φ=0 is an *idealized pause* — physically exact only at the destination (moored) | discussion, Aug 7 | recorded |
| 4 | **Variant (c) — RECOMMENDED**: mid-ocean waiting priced at the **station-keeping cost** (symmetric thrust, declared assumption); **free only at d = d_M** | Ami, Aug 7 | prototyped, awaiting Tal's ratification |
| 5 | **Empirical verdict (E-B, Aug 8)**: the optimizer **never waits — not even for free**; variants (a)/(c)/no-waiting give identical fuel to the last digit on both quick-set voyages. The φ(·;0) choice is a *formal* one only | test, Aug 8 | `runs/2026_08_08_variant_c_test/` |
| 6 | Code: prototype live behind `SR_main --wait_arcs {off,free,hold}`, default off (goldens intact); hold-pricing has one home (`price_candidate`) | Aug 8 | merged |

**For Tal to ratify Monday:** variant (c) as the paper's convention (or (a) if he prefers the
simpler sentence — the results are identical either way); the **v_max convention** (mean+3?
vessel cap?); the **Luo band policy**. Plus the engineering prerequisite: the **ETA-feasibility
arc cut** before any full re-run (open band = ~14× arcs / ~13× runtime otherwise).

### 2. Changes needed in the equations and the paper (under variant (c))

**Tal's zones [T]:**
1. **Eq. (5)**: add the waiting candidate **(d, t_𝒯(t)) unconditionally** (family 2 yields d′=d
   only when the cell width happens to be δ-aligned).
2. **Eq. (5) / prose, d = d_M**: 𝒟(L) is an empty min ⇒ 𝒜(L,t) undefined — a destination clause
   or prose convention for waiting at the port.
3. **φ definition (§4.1)**: one added sentence — mid-ocean φ(d,t;0) = FCR(|hold thrust|) with the
   symmetric-thrust assumption declared; waiting at d = d_M free (moored). *(Under (a) instead:
   "By convention φ(d,t;0)=0.")*
4. **§4 structural property 3**: under (c), **no caveat needed** (φ continuous through v=0);
   *(under (a): add "constant except possibly mixed with waiting")*. Optional footnote: V-shaped
   φ in following currents, zero at the drift speed.
5. **Algorithm 1 Input line**: band → [0, v_max] (already on the slips list, §2).
6. Interacts with the still-open **Eq. (6) direction** (§1) — none of the above depends on it.

**Ami's zones [A] (ready on go-ahead):**
7. §4.2 extraction paragraph: the justification "waiting at the destination is free (moored), so
   C\*(L,T) = min over all sinks — the terminal state is unique; mid-ocean waiting is priced at
   the station-keeping rate".
8. §4.2 intro: "continues to the deadline at zero speed" → "…at no cost (moored)".
9. Walkthrough window sentence: "the vessel may wait" → "+ priced at the station-keeping rate".
10. Figure captions (both panels): the vertical cone edge is itself a candidate — the wait leg.
11. Tractability: κ and the state/arc counts re-measured under [0, v_max] (after the
    ETA-feasibility cut); numbers currently marked pre-band-change.
12. §5: band statement + the Luo asymmetry note; §6–§7: full re-run numbers (blocked on the
    ratifications above).

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
- **Item 3 (lower bound): TWO iterations done.** Iteration 1 (`lb_bound.py`): sound,
  golden-anchored, but 16–18 % loose (intrinsic one-step discount + path-switch slack — see
  `docs/lb_neighbour_price_plan.md`). **Iteration 2 (grid-refinement study,
  `runs/2026_08_08_lb_refinement/`): the gap halves per grid halving (O(step) confirmed), and the
  finest level is itself a rigorous bound — the DP is provably within ~4 % of the continuous
  optimum (R1 4.18 %, R2 3.72 %), 4× better, minutes of compute.** Slack dies superlinearly (Q4
  matters less at fine grids). Richardson extrapolation invalid for now: F_DP(grid) drifts with
  refinement because the τ-dependent wall-feasibility filter returns dropped walls (non-nested
  grids — E1's mechanism caught red-handed). **Iteration 3 designed**: freeze the wall set across
  levels ⇒ valid extrapolation; also h/8 ⇒ ≈2 % certified. **§4.3 rewrite implication: a
  two-sided story exists today** — 0.2–0.4 % from above (polish), ~4 % certified from below,
  lower side linear in the step. Originally started as:
  **Item 3 (lower bound) STARTED in parallel** — background agent prototyping
  `pipeline/dp_rebuild/lb_bound.py` (neighbour-price relaxation on the current band, quick-set
  voyages, sanity vs goldens + bracket vs the §4.3 polish); plan/results to land in
  `docs/lb_neighbour_price_plan.md` + `runs/2026_08_07_lb_neighbour_price/`.

## 5. THE BIG ONE — re-run everything under 𝒱 = [0, v_max]

All §5–§7 results, the §4.3 certificate table, the Tractability numbers (marked "measured under
the pre-Aug-5 band"), and κ are all still pre-band-change. ~~Blocked on: φ(d,t;0) definition~~
**φ(·;0)=0 DECIDED (section 2A)** — remaining blockers: the **v_max convention** and the **Luo
band policy** (section 2A item 5), plus Tal's blessing of the Eq.-(5) waiting candidate. Note Luo
keeps v_min = 8.0 in the original article — the §5 band-alignment note must say how the comparison
handles the asymmetry.

## 6. NEW (Aug 7) — experiment capacity of the collected data

Audit of the local HDF5 files (`pipeline/data/`, the **Jun-1** snapshot) to answer "how many
voyages can we actually run?".

**Coverage.** Both files span `sample_hour` 6/0 → **2052** on the 6h NWP cycle — **85.5 days**,
342 (exp_b) / 343 (exp_d) cycles. Forecast cycles missing: **19** (exp_b) / **8** (exp_d), sharing
two outages (`sh 540`, `sh 732–756`). Forecast horizon **−26 → +160 h**, hourly.

| Design | route1 (Malacca, ETA 280 h) | route2 (Atlantic, ETA 168 h) | total |
|---|---|---|---|
| **Non-overlapping chain** (N+1 departs when N arrives) | 7 | 12 | **19** |
| departures every 72 h | 25 | 27 | 52 |
| departures every 24 h | 74 | 79 | 153 |
| every 6h grid point (max) | 295 | 315 | 610 |
| …with a forecast cycle present at departure | 276 | 307 | 583 |

**The frozen 19-voyage golden set IS the complete non-overlapping enumeration of the local data** —
`run_chain_sweep.ROUTES` steps by ETA and stops at 1966 / 2016, both just under 2052. No headroom
left at that design. Anything above 19 buys n at the cost of independence (daily route1 departures
overlap 91 % of their weather window ⇒ effective n barely above 7; would need block bootstrap /
cluster-robust errors, not more rows).

**Two structural limits (properties of the collection, not the solver):**
- **Forecast horizon 160 h < route1 ETA 280 h** — no single cycle covers a Malacca voyage; the
  deterministic-at-departure plan is blind for its last ~120 h. Route2 is 8 h short. Unchanged by
  fresh data. *Worth a sentence in the §5 band-alignment / Mode-C note.*
- **Compute, not data, bounds the RH sweeps** — deterministic is cheap (~30 s/voyage route1,
  ~12 s route2 ⇒ full 19-set ≈ 25 min); RH is 46 replans/voyage (route1) / 28 (route2), and the
  cold-cache run took **8.9 h**. At 8.25 GB peak RSS vs 48 GB local, ~4 concurrent, not 12.

**THE LEVER — pull fresh data.** Shlomo2/Edison are at `sample_hour` **3648** (152 days, **+78 %**),
both collectors green (0 failed waypoints, 478 s/cycle). That takes the independent-voyage count
**19 → 34** (route1 **13**, route2 **21**) with no design change and no independence compromise,
and it grows by one route2 voyage/week, one route1/~12 days.
**Decision for Monday:** re-freeze the goldens on the fresh pull (34 voyages) before the §5
re-runs, or keep the 19-voyage set for continuity and pull afterwards? (Download ≈ 740 MB over
VPN.) Note the bigger n also feeds the LB-strategy rewrite tracked in §7.

## 7. Carryovers (from Jul-27 / Aug-5, updated Aug 7)

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

## 8. Docs debt (Ami, no decisions needed)

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

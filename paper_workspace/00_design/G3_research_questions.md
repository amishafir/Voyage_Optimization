# G3 — Research Questions (the spine)

**Gate status:** DRAFT → review → freeze. Built on frozen `G2_claims.md` (3 contributions).
**Rule:** every RQ traces *forward* to a contribution+claim+evidence, and *backward* to a gap
(the gap text is a placeholder here — it gets filled at G5 from the literature pillars).
This file is the paper's backbone: the Introduction states these RQs, and the sections answer
them in order.

**Spine (one paragraph):**
> Voyage speed optimization under time-varying weather is usually solved by holding one speed
> per route block (e.g., Luo 2024). We ask whether *relaxing* that lock — choosing speed freely
> per leg — saves fuel, *why* it should, and *whether the saving holds up* when a real captain
> plans against imperfect forecasts rather than perfect hindsight. The answer is a single
> mechanism seen from three sides: per-leg freedom recovers a Jensen-inequality loss that
> per-block locking incurs on the convex fuel curve (RQ1); the recovered fuel is ~6 mt / 1.8–2.6 %
> across 19 voyages and two weather regimes under perfect foresight (RQ2); and it survives
> rolling-horizon operation under real forecasts, where free-speed re-planning saves while
> block-locked re-planning merely breaks even (RQ3).

---

## RQ1 — Does per-leg speed freedom reduce fuel relative to per-block SOG-locking, and why — at what computational cost?
*The mechanism question. The "why" is the intellectual core.*

- **Maps to:** Contribution **C-I** (mechanism + structural cost).
- **Answered by:** Claim 1 (Jensen on convex FCR), Claim 6 (structural cost — same freedom-cost coin).
- **Evidence:** G1 C-7 (mechanism, analytic), D-2/D-3 (graph sizes), corroborated by C-1.
- **Form of the answer:** Yes — per-block locking is sub-optimal whenever weather varies within
  a block, by Jensen's inequality on the convex (cubic) FCR; per-leg freedom recovers the loss.
  The freedom that enlarges SR's graph (O(V·H·K)) over Luo's block lattice (O(blocks·K)) is the
  same freedom that captures the fuel — cost and benefit are one design choice.
- **Gap it addresses (G5 placeholder):** prior speed-optimization work uses block/segment-constant
  speeds [Luo 2024; LP-segment-averaging] without isolating the convexity penalty this incurs.
  *(fill from pillars 1, 2 at G5.)*

## RQ2 — How large is the SR−Luo fuel gap under perfect foresight, and how does it vary across routes, weather regimes, and departure times?
*The quantification question. Establishes the ceiling and its robustness.*

- **Maps to:** Contribution **C-II** (quantification, oracle).
- **Answered by:** Claim 2 (19/19, ~6.4 mt R1 / ~5.5 mt R2), Claim 3 (route-length %-scaling).
- **Evidence:** G1 A.1–A.3, C-1, C-2.
- **Form of the answer:** SR < Luo on all 19 voyages; ~6 mt absolute on both routes, but ~1.4×
  larger in % on the shorter/harsher Atlantic; stable across the full ~80-day departure window.
- **Gap it addresses (G5 placeholder):** baselines are typically compared on a single route /
  single departure / synthetic weather; the gap's robustness across real departure conditions
  is unmeasured. *(fill from pillars 1, 3 at G5.)*

## RQ3 — Does the advantage survive realistic rolling-horizon planning under imperfect forecasts, versus set-and-forget operation?
*The operational question. Turns a hindsight result into an actionable one.*

- **Maps to:** Contribution **C-III** (operational validation).
- **Answered by:** Claim 4 (RH-SR saves 18/19, RH-Luo breaks even). Limitation: Claim 5 (boundedness, → Discussion).
- **Evidence:** G1 B.1–B.4, C-3, C-4; supporting S-1 (forecast error → oracle−RH gap), S-2 (6 h = GFS cycle).
- **Form of the answer:** Yes — under 6 h rolling-horizon re-planning with nowcast+forecast,
  free-speed re-planning (RH-SR) saves vs set-and-forget on 18/19 voyages (mean −1.9 % / −1.2 %),
  while block-locked re-planning (RH-Luo) only breaks even. *Limitation (Discussion):* the saving
  is bounded by weather variability and can reverse on near-uniform departures (Jensen).
- **Gap it addresses (G5 placeholder):** rolling horizon is established in OR but rarely applied
  to maritime speed optimization with real NWP forecasts and a faithful published baseline.
  *(fill from pillars 4, 5 at G5.)*

---

## How the RQs order the paper

| Order | RQ | Section(s) it drives | Why this order |
|---|---|---|---|
| 1 | RQ1 | Problem formulation + Methods (formulations) + the mechanism part of Discussion | Establish *why* before *how much* — the reader needs Jensen + the two graph formulations first. |
| 2 | RQ2 | Results §1 (Mode C oracle) | The clean ceiling result, full enumeration — the strongest, simplest evidence leads. |
| 3 | RQ3 | Results §2 (RH) + Discussion (boundedness limitation) | The operational payoff and its honest bound close the arc. |

**Supporting threads (not RQs):** forecast-error curve (S-1) and 6 h/GFS-cycle (S-2) appear in
Experimental Setup / Methods to *justify the RH design*, then are referenced in RQ3's answer.

---

## Freeze checklist — ✅ FROZEN 2026-06-08
- [x] 3 RQs ↔ 3 contributions, 1:1 and complete.
- [x] RQ ordering (why → how much → does it hold) agreed as the narrative arc.
- [x] Gap-placeholders specific enough to fill at G5.
- [x] Sign off. → Writing-forward begun (`../drafts/`); G4 still to design.

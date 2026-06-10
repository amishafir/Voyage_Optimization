<!--
DRAFT-BACKBONE — Introduction. Writes G3 (research questions) + G2 (contributions) forward.
This is the SKELETON the locked gates support: motivation, gap, RQs, contributions, organisation.
The motivation and gap paragraphs are PLACEHOLDERS [LIT→G5] — they cannot be finalised until the
literature gap is designed at G5. The RQ and contribution blocks ARE final (from frozen G3/G2).
Voice: TR-C — third person, passive, "this study". Citations as [CITE: Author Year].
-->

# 1. Introduction

## 1.1 Motivation [LIT→G5 — placeholder]

[LIT→G5: Maritime fuel and GHG reduction matters now — IMO 2023 GHG strategy, EEXI, CII.
2–3 sentences with regulatory citations from pillar 6.]

[LIT→G5: Speed optimisation is the most direct operational lever, and fuel consumption is
strongly convex (approximately cubic) in speed — citation from pillar 2. State the cubic FCR
fact here because the whole mechanism rests on it.]

## 1.2 The gap [LIT→G5 — placeholder, keyed to the three RQs]

[LIT→G5: Existing voyage-speed optimisers hold a single speed per route block or segment
(per-block dynamic programming, e.g. [CITE: Luo 2024]; segment-averaged linear programming).
The convexity penalty this incurs under within-block weather variation has not been isolated.
— pillars 1, 2.]

[LIT→G5: Baselines are typically compared on a single route, a single departure, or synthetic
weather, so the robustness of any advantage across real departure conditions is unmeasured.
— pillars 1, 3.]

[LIT→G5: Rolling horizon is well established in operations research but rarely applied to
maritime speed optimisation against real numerical weather prediction (NWP) forecasts with a
faithful published baseline. — pillars 4, 5.]

## 1.3 Research questions

This study addresses three questions, which form a single mechanism viewed from three sides.

**RQ1.** Does relaxing the per-block speed lock to per-leg speed freedom reduce voyage fuel,
what is the mechanism, and at what computational cost?

**RQ2.** Under perfect weather foresight, how large is the fuel gap between free-speed and
per-block-locked optimisation, and how does it vary across routes, weather regimes, and
departure times?

**RQ3.** Does the advantage survive realistic rolling-horizon planning under imperfect
forecasts, relative to set-and-forget operation?

## 1.4 Contributions

The contributions are threefold.

1. **Mechanism and its computational cost.** This study shows that per-block speed-locking is
   fuel-suboptimal whenever weather varies within a block, by Jensen's inequality applied to the
   convex fuel-consumption-rate curve, and that per-leg speed freedom recovers the loss. The same
   freedom that enlarges the optimisation graph — from the per-block lattice of order
   $O(\text{blocks} \times K)$ to the atomic-edge graph of order $O(V \cdot H \cdot K)$ — is what
   captures the fuel; computational cost and fuel benefit are two faces of one design choice.

2. **Quantification against a faithful baseline.** The fuel advantage of free-speed over the
   per-block-locked formulation of [CITE: Luo 2024] is quantified under perfect foresight across
   19 voyages on two routes spanning two weather regimes: a saving on every voyage, of comparable
   absolute magnitude across routes but proportionally larger on the shorter voyage.

3. **Operational validation.** The advantage is shown to survive realistic 6 h rolling-horizon
   planning against real NWP forecasts: free-speed re-planning saves fuel relative to
   set-and-forget operation, whereas per-block-locked re-planning does not. The boundedness of
   this operational saving is characterised (Section 7).

## 1.5 Organisation

[METHODS→G4 / structure once G4–G5 designed:] Section 2 reviews related work and states the gap.
Section 3 formulates the problem and the convex fuel model. Section 4 defines the free-speed and
per-block-locked formulations, the rolling-horizon scheme, and the structural-complexity measures.
Section 5 describes the data and routes. Section 6 reports results (Section 6.1, perfect foresight;
Section 6.2, rolling horizon). Section 7 discusses the mechanism, the operational boundedness, and
limitations. Section 8 concludes.

<!--
COVERAGE CHECK:
- G3 RQ1/RQ2/RQ3 → §1.3 verbatim-faithful ✓
- G2 3 contributions → §1.4 (C-I mechanism+cost, C-II quantification, C-III operational) ✓
- LP/DP framing absent (dropped) ✓; single foil = Luo 2024 ✓
- Boundedness flagged as §7 limitation, not a contribution ✓
BLOCKED until G5: §1.1 motivation, §1.2 gap (all [LIT→G5]). §1.5 organisation firms up after G4.
-->

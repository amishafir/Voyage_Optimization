<!--
DRAFT — standalone "Mechanism" section (G4 §4.5 promoted). Placed BETWEEN Methods and Results.
States the analytic prediction (Jensen on convex FCR) that Section 6 then confirms empirically.
Serves RQ1 / Contribution C-I. Voice: TR-C — present tense for the general/analytic truth.
NOTE: the formal inequality direction should be checked against the exact physics before freeze
(see CHECK comment at end).
-->

# 5. The convexity mechanism

The fuel-consumption rate is strictly convex in speed: $\text{FCR}(V_s) = 0.000706\, V_s^3$
[EQ: FCR] is cubic and therefore convex on the operating range. This single property predicts,
before any experiment, that per-block speed-locking must waste fuel relative to per-leg freedom
whenever weather varies within a block.

Consider one time block that spans several legs whose weather differs — a typical situation, since
ocean conditions change continuously along a route. A free-speed policy may set a different speed
on each leg; a block-locked policy must hold one speed across them all. To maintain a *constant*
SOG across legs of differing weather, the block-locked policy is forced to vary the still-water
speed (SWS) from leg to leg — more SWS where conditions are adverse, less where they are
favourable. Fuel depends on SWS through the convex FCR, so by Jensen's inequality the mean fuel of
this forced, varying SWS exceeds the fuel that the *mean* SWS would consume:

$$\mathbb{E}\!\left[\text{FCR}(V_s)\right] \;\ge\; \text{FCR}\!\left(\mathbb{E}[V_s]\right)
\qquad\text{[EQ: Jensen on FCR]}$$

The harsh-leg penalty always outweighs the favourable-leg saving. A free-speed policy is not bound
to a constant SOG and can allocate speed across legs so as to keep operation in a more efficient
regime, avoiding the forced excursions; it therefore consumes no more fuel than the block-locked
policy, and strictly less whenever within-block weather is non-uniform.

Two empirical predictions follow, both tested in Section 6.

1. **A systematic, signed gap.** SR should consume less fuel than Luo on essentially every voyage
   in which weather varies within blocks — not occasionally, but as a rule, because the inequality
   is directional.

2. **A gap that scales with weather variability.** The size of the penalty grows with the spread
   of within-block conditions. Routes or departures whose weather varies more should exhibit a
   larger gap; a shorter voyage that concentrates the same variability into fewer, denser blocks
   should show a proportionally larger effect.

The same convexity has a second consequence that is examined later as a limitation
(Section 7): on *uniform* weather a constant speed is itself fuel-optimal, so the value of any
speed variation — including the forecast-driven variation of a rolling-horizon policy — is bounded
by how much the weather actually varies. The mechanism thus explains both why free-speed
optimisation helps and why its benefit is bounded.

This argument is exact only for the convex FCR and the equal-time comparison used throughout;
it predicts the *direction* and the *scaling* of the effect, while its *magnitude* on real routes
is the empirical question answered next.

<!--
CODE VERIFICATION — ✅ PASS (2026-06-08). The convex-cost-on-SWS structure this section assumes
is implemented correctly. Jensen itself is taken as established from the cited reference (not
re-derived here); only the coding was checked.
- FCR is cubic in SWS: shared/physics.py:325-337 `calculate_fuel_consumption_rate` = 0.000706·SWS³.
- Luo holds one SOG per block, back-solves SWS per sub-segment, costs FCR(SWS):
  luo_main.py:229-239 (sog const; sws=calculate_sws_from_sog(sog,weather); fcr=FCR(sws)).
- SR picks SOG per leg, back-solves SWS, costs FCR(SWS): atomic_edges.py:236-247.
- calculate_sws_from_sog (physics.py:403+) is a monotone inverse → constant-SOG lock forces SWS
  to vary with within-block weather. The only SR/Luo difference is decision granularity.
TODO (writing, not verification): cross-link prediction 2 to Results route scaling (R2 2.6% >
R1 1.8%); prediction 1 ↔ G1 C-1 (19/19); prediction 2 ↔ G1 C-2.
-->

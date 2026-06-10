<!--
DRAFT — Discussion. Interprets Results (§6) through the Mechanism (§5). Carries the boundedness
LIMITATION (G2 Claim 5 decision). Literature comparison is [LIT→G5]. Voice: TR-C.
-->

# 7. Discussion

## 7.1 The mechanism predicted the result

The two predictions of the convexity mechanism (Section 5) were both borne out. First, the gap
was *signed and systematic*: under perfect foresight the free-speed formulation consumed less fuel
than the per-block baseline on all 19 of 19 voyages, with no exception on either route
(Section 6.1). This is the directional signature of Jensen's inequality acting on the convex fuel
curve — not an average tendency but a rule. Second, the gap *scaled with weather variability*: it
was proportionally larger on the harsher, more variable Atlantic route (2.6 %) than on the milder
Malacca route (1.8 %), as predicted for a penalty driven by within-block weather spread. The
empirical magnitude — roughly 6 mt per voyage — is thus explained, not merely reported.

## 7.2 Decision granularity, not data, is the limiting factor

That the free-speed advantage persisted under realistic rolling-horizon operation (Section 6.2) —
where it saved fuel against set-and-forget while the per-block baseline did not — confirms the
effect is not an artefact of perfect information. The per-block baseline re-planned *more* often
under refreshed forecasts yet gained *less*, because it lacked the within-block resolution to act
on the new information. The limiting factor is decision granularity, not data.

## 7.3 When re-planning helps — and when it does not (limitation)

The rolling-horizon benefit over set-and-forget is real but bounded, and this study does not
claim it is universal. On 1 of 19 voyages the free-speed rolling-horizon plan consumed slightly
*more* fuel than the fixed-speed baseline, and the per-block rolling-horizon plan did so on
several. The reason is the same convexity that drives the main result, seen from the other side:
on near-uniform weather a constant speed is itself fuel-optimal, so any forecast-driven speed
variation can only add a Jensen penalty unless the weather-routing gain exceeds it. The value of
re-planning is therefore bounded by how much the weather actually varies over a departure's window
— it is largest on variable departures and can vanish or reverse on calm, uniform ones. This is
best read as a savings-versus-departure relationship rather than a single figure
[FIG: savings vs departure]. Reported precisely, the relevant gate is "realised fuel ≤ Naive",
which the free-speed plan satisfied on 18 of 19 voyages and the per-block plan on a minority.

## 7.4 Relation to prior work [LIT→G5]

[LIT→G5: position against per-block / segment-constant speed optimisation (Luo 2024; segment-
averaged LP) — pillar 1; against rolling-horizon / MPC in OR and its limited maritime application
with real NWP — pillars 4, 5; against fuel-resistance modelling and the cubic exponent — pillar 2.
State what this study adds: an isolated convexity mechanism, a faithful published baseline, and
operational validation across real departures.]

## 7.5 Limitations

Several bounds on the present results should be noted. (i) Two routes were studied; while they
span two contrasting regimes, the route-length scaling of the gap is reported as a contrast, not a
curve, and additional routes would be needed to establish it as a law. (ii) The arrival constraint
was hard and binding (zero slack) throughout, so the results describe fuel at equal voyage time;
relaxing the ETA is left to future work. (iii) The rolling-horizon nowcast assumes the current 6 h
block is observable; the realism of this assumption depends on onboard sensing. (iv) The per-block
baseline, though implemented faithfully
from its published description, is one of several possible block formulations.

<!--
COVERAGE: §7.1 mechanism predictions confirmed (C-1/C-2) ✓ | §7.2 operational + structural cost
(C-3, C-I) ✓ | §7.3 boundedness LIMITATION (C-5, per G2 decision — not headline) ✓ |
§7.4 lit comparison [LIT→G5] | §7.5 limitations (two routes, structural compute, hard ETA, nowcast,
baseline) ✓. Reporting gate stated precisely (G1 F-2).
-->

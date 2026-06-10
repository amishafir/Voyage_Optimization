<!--
DRAFT — Conclusion. Summarises the 3 contributions; practical takeaway; future work.
No new claims. Voice: TR-C — past tense for what was done, present for standing conclusions.
-->

# 8. Conclusion

This study compared per-leg free-speed voyage optimisation (the Shafir–Raviv formulation) against
the per-block speed-locked formulation of [CITE: Luo 2024] for fuel-minimising ship routing under
time-varying weather, on two routes spanning two weather regimes.

Three conclusions follow. First, per-block speed-locking is fuel-suboptimal by a structural
mechanism: because the fuel-consumption rate is convex in still-water speed, holding one speed
across a block of varying weather forces inefficient speed excursions, and per-leg freedom recovers
the loss (Jensen's inequality). The same freedom that enlarges the optimisation graph is what
captures the fuel — cost and benefit are one design choice. Second, under perfect foresight the
free-speed advantage was realised on every one of 19 voyages — comparable in absolute fuel across
routes (~6 mt) but proportionally larger on the shorter, harsher voyage. Third, the advantage
survived realistic 6 h rolling-horizon operation against real forecasts: free-speed re-planning
saved fuel relative to set-and-forget operation on 18 of 19 voyages, whereas per-block re-planning
did not, its value being bounded by weather variability.

The practical implication is that the resolution of the speed decision — not the availability of
re-planning or fresh forecasts — is the binding factor: a per-block planner cannot convert better
information into fuel savings, while a per-leg planner can. Where computational budget permits the
larger problem, per-leg optimisation is preferable; where it does not, the expected saving can be
anticipated from the variability of the route's weather.

Future work includes extending the route set to establish the route-length scaling as a curve
rather than a contrast, relaxing the hard arrival constraint to a soft ETA penalty, and examining
the sensitivity of the conclusions to the fuel-speed exponent.

<!--
COVERAGE: 3 contributions restated (C-I mechanism+cost, C-II quantification, C-III operational) ✓ |
practical recommendation (granularity is binding) ✓ | future work (more routes, soft ETA, exponent
sensitivity) ✓. No claim beyond G2. [CITE: Luo 2024] only.
-->

<!--
DRAFT — Related Work. PLACEHOLDER: the prose is gated on G5 (literature gap map).
Structure is set (keyed to the six pillars and the three RQs); fill at G5 from context/literature/.
-->

# 2. Related work

> **[LIT→G5 — entire section pending the gap map.** Structure below is fixed; prose + citations
> filled from `context/literature/pillar_*` once G5 is designed. Each subsection ends in the gap
> that one of the three research questions closes.**]**

## 2.1 Ship speed optimisation methods
[LIT→G5: LP/segment-averaged, dynamic-programming/per-block (incl. [CITE: Luo 2024]),
metaheuristics, weather routing — pillar 1. **Gap → RQ1/RQ2:** per-block/segment-constant speed is
standard; the convexity penalty it incurs has not been isolated, nor quantified against a faithful
published baseline across real departures.]

## 2.2 Fuel consumption and the speed–power relationship
[LIT→G5: cubic/convex FCR, resistance decomposition, the speed exponent — pillar 2.
**Gap → RQ1:** convexity is well established but its consequence for *per-block speed-locking*
specifically is not drawn out.]

## 2.3 Weather forecasting in voyage optimisation
[LIT→G5: NWP products (GFS/ECMWF), forecast verification, Open-Meteo — pillar 3.
**Gap → RQ2/RQ3:** forecast-error propagation into the optimiser, and use of real NWP rather than
synthetic weather, is rarely measured.]

## 2.4 Rolling horizon and the value of information
[LIT→G5: rolling horizon / MPC in OR, replan frequency, value of information — pillars 4, 5.
**Gap → RQ3:** rolling horizon is mature in OR but seldom applied to maritime speed optimisation
with real forecasts and a faithful baseline, and the boundedness of its benefit is under-examined.]

## 2.5 Summary of gaps
[LIT→G5: gap table — pillar × what exists × what is missing × which RQ closes it.]

# Pillar 2: Fuel Consumption & Resistance Modeling

**Purpose:** Justify the physics model (Tables 2-4, Equations 7-16) and the cubic FCR relationship. Frame the Jensen's inequality insight.

**Gap to establish:** The cubic FCR convexity is well known in naval architecture, but its implication for segment-averaged LP optimization under SOG-targeting has not been analyzed. Jensen's inequality on cubic FCR is the mechanism, but nobody has connected it to the LP vs DP ranking reversal.

**Sub-topics:** Power-speed relationship (2.7-3.3 exponent), Resistance decomposition (Holtrop-Mennen, Hollenbach, ITTC-1957), Added resistance in waves, Current effects on SOG, FCR convexity / Jensen's inequality

---

## Articles

<!-- Paste entries from _template.md below this line -->

---

### [Tezdogan, T., Demirel, Y.K., Kellett, P., Khorasanchi, M., Incecik, A. & Turan, O. (2015)] Full-scale unsteady RANS CFD simulations of ship behaviour and performance in head seas due to slow steaming

- **Citation:** Tezdogan, T., Demirel, Y.K., Kellett, P., Khorasanchi, M., Incecik, A., Turan, O., 2015. *Full-scale unsteady RANS CFD simulations of ship behaviour and performance in head seas due to slow steaming*. Ocean Engineering, 97, 186-206. https://doi.org/10.1016/j.oceaneng.2015.01.011
- **PDF:** `context/literature/pdfs/Tezdogan2015_CFDSlowSteaming.pdf`
- **Tags:** `added-resistance-waves`, `slow-steaming`, `ITTC`, `resistance-decomposition`

**Summary:**
Performs fully nonlinear unsteady RANS CFD simulations to predict motions and added resistance of a full-scale KRISO Container Ship (KCS) in regular head waves at both design speed (24 knots) and slow steaming speed (19 knots). Estimates the increase in effective power and fuel consumption due to wave operation. Results validated against experimental data show good agreement.

**Key Findings:**
- Added resistance in waves can account for 15-30% of total calm-water resistance (citing Perez 2007)
- Full-scale CFD simulations at design speed (24 kn, Fn=0.26) and slow steaming speed (19 kn, Fn=0.195)
- CFD predictions within 0.42-9.39% of experimental data for heave transfer functions
- Wave-to-ship length ratios of 1-2 tested across 12 simulation cases (6 per speed)
- Open access CC-BY paper; first study to predict added resistance increase using full-scale RANS at slow steaming speeds
- Mentions "just-in-time" operation and virtual arrival as related slow steaming concepts (p. 186)

**Methodology:**
Full-scale unsteady RANS CFD using Star-CCM+ v9.0.2 on KRISO Container Ship (KCS: LBP 230m, beam 32.2m, design speed 24 kn). Head seas with wave steepness 1/60. Deep water conditions. Validated against model-scale experimental data and potential flow theory. University of Strathclyde HPC facilities. Open access.

**Relevance to Thesis:**
Provides high-fidelity CFD evidence that added resistance in waves changes significantly between design and slow steaming speeds, confirming that the fuel penalty from waves is speed-dependent. This supports our argument that weather effects are non-negligible: for a given SWS, the achieved SOG depends on wave conditions, and the resistance (hence fuel) depends nonlinearly on both SWS and wave interaction. The paper explicitly notes slow steaming as response to economic/regulatory pressure and mentions "just-in-time" arrival — concepts related to SOG-targeting. However, the paper treats speed as a fixed engine setting (SWS), never analyzing what happens when the ship must maintain a target SOG through varying wave conditions.

**Quotable Claims:**
- "Added resistance can account for up to 15-30% of the total resistance in calm water" (p. 187, citing Perez 2007)
- "no specific study exists which aims to predict the increase in the above mentioned parameters due to the operation in waves, using a Computational Fluid Dynamics (CFD)-based Reynolds Averaged Navier-Stokes (RANS) approach" (p. 187)
- "a typical operating speed is now significantly below the original design speeds" (p. 186)

**Limitations / Gaps:**
- Speed is a fixed engine setting (SWS) — no SOG-targeting, no analysis of speed achieved under waves
- Regular head waves only — no irregular seas, no current effects, no multi-directional wave fields
- Single ship type (KCS container ship) — no comparison across vessel types
- No optimization — purely hydrodynamic analysis of resistance at two fixed speeds
- No forecast uncertainty, rolling horizon, or re-planning
- Does not connect added resistance findings to speed optimization or fuel estimation bias

---

### [Psaraftis, H.N. & Lagouvardou, S. (2023)] Ship speed vs power or fuel consumption: Are laws of physics still valid? Regression analysis pitfalls and misguided policy implications

- **Citation:** Psaraftis, H.N., Lagouvardou, S., 2023. *Ship speed vs power or fuel consumption: Are laws of physics still valid? Regression analysis pitfalls and misguided policy implications*. Cleaner Logistics and Supply Chain, 7, 100111. https://doi.org/10.1016/j.clscn.2023.100111
- **PDF:** `context/literature/pdfs/Psaraftis2023_SpeedPowerPitfalls.pdf`
- **Tags:** `power-speed-exponent`, `FCR-convexity`, `survey`, `slow-steaming`

**Summary:**
Reviews recent papers using regression analysis on operational data that argue the traditional cubic speed-power law is invalid, finding exponents well below 3. Identifies specific statistical pitfalls (confounding variables: draft, weather, fouling) and argues the low exponents are artifacts of flawed methodology. Concludes the laws of physics remain valid and policy conclusions drawn from spuriously low exponents are misguided.

**Key Findings:**
- Recent operational regressions report speed-power exponents well below 3 (some below 2 or even below 1)
- Low exponents arise from regression pitfalls: confounding variables (draft, trim, displacement, hull fouling, weather) not controlled
- When confounders are controlled, the cubic or near-cubic (2.7-3.3) relationship holds, consistent with theory
- Policy implications from spuriously low exponents — such as slow steaming saving less fuel than expected — are misleading
- Defends the theoretical foundation that fuel consumption varies approximately as cube of speed

**Methodology:**
Critical review and re-analysis of recent regression-based studies on speed-power relationship. Examines published results from operational datasets (noon reports, AIS data, MRV reports) across multiple ship types. Identifies omitted variable bias, confounding, and improper data aggregation. Contrasts against theoretical naval architecture predictions.

**Relevance to Thesis:**
Directly reinforces our Jensen's inequality argument by defending the cubic law as physically valid. If the speed-power exponent were truly below 2, the convexity would be weaker and the LP vs DP ranking reversal under SOG-targeting would diminish. Psaraftis & Lagouvardou's confirmation that n is genuinely near 3 means our Jensen mechanism is strong and practically significant. The paper's identification of confounding variables (weather, loading) is relevant to our Contribution 2: the same environmental variability that confounds regressions is what causes SOG to differ from SWS and activates the Jensen effect. However, the paper never considers SOG vs SWS — it treats "ship speed" as a single variable.

**Quotable Claims:**
- "Using regression analyses for selected case studies, these papers show that in many cases the traditional 'cube law' is not valid, and exponents lower than 3 (and in some cases lower than 2 or even below 1) are more appropriate" (abstract)
- "This paper reviews some of these papers and shows that their results are partially based on pitfalls in the analysis which are identified" (abstract)
- Page-specific internal quotes require verification against PDF

**Limitations / Gaps:**
- Treats "ship speed" as single variable — never distinguishes SOG from SWS
- Does not consider how cubic convexity creates systematic bias in optimization models assuming constant speed per segment
- No optimization comparison (LP, DP, or otherwise) — paper is about estimating the exponent, not optimizing
- No simulation of planned vs actual performance under weather uncertainty
- No rolling horizon or forecast error analysis
- Does not connect regression confounders (weather, currents) to the plan-vs-actual gap under SOG-targeting

---

### [Taskar, B. & Andersen, P. (2020)] Benefit of speed reduction for ships in different weather conditions

- **Citation:** Taskar, B., Andersen, P., 2020. *Benefit of speed reduction for ships in different weather conditions*. Transportation Research Part D: Transport and Environment, 85, 102337. https://doi.org/10.1016/j.trd.2020.102337
- **PDF:** `context/literature/pdfs/Taskar2020_SpeedReductionWeather.pdf`
- **Tags:** `power-speed-exponent`, `added-resistance-waves`, `slow-steaming`, `resistance-decomposition`

**Summary:**
Investigates fuel savings from speed reduction using detailed ship performance modeling for 6 representative vessels (3 container ships, 2 bulk carriers, 1 tanker) across realistic weather conditions. Simulates voyages on the Los Angeles–Osaka route using ECMWF ERA5 monthly-averaged wave data, calm water resistance (updated Guldhammer & Harvald method), added wave resistance (DTU method), propeller efficiency, and engine load limits. Concludes the cubic speed-power assumption causes up to 15% error and that fuel savings from speed reduction are highly weather-dependent.

**Key Findings:**
- Speed exponent N varies significantly by ship type: C1=4.0, C4=3.3, C8=3.3, B75=4.2, B175=3.7, T300=3.4 (Table 3, p. 10) — cubic assumption is insufficient
- At 30% speed reduction, fuel savings vary from 2% to 45% depending on ship type, size, and weather (p. 1, abstract)
- Additional voyage fuel consumption due to waves is nearly independent of ship speed (p. 12) — added resistance decreases with speed but longer voyage time compensates
- Cubic assumption causes up to 15% error in fuel savings estimation at 30% speed reduction (p. 10)
- SFOC variation at different engine loads has relatively small effect (~3% at 30% speed reduction, p. 11)
- Fuel savings from speed reduction are largest in calm weather and smallest in rough weather (p. 13)
- At 10% speed reduction, ships B75 and C1 show >30% fuel savings vs 19% predicted by cubic assumption (p. 10)

**Methodology:**
Voyage simulation with 50 nm spacing along Los Angeles–Osaka route. Calm water resistance via updated Guldhammer & Harvald method (validated against KCS, KVLCC2, DTC, HTC model tests). Added wave resistance via DTU method (strip theory + Faltinsen short waves + WAMIT) and cross-validated with STAwave-2. Propeller design via B-series with engine-propeller matching. Engine load limits from MAN CEAS tool. Weather: ECMWF ERA5 monthly-averaged significant wave height and peak period for 2010 (January, March, July, October). 6 ships: 1100/4000/8000 TEU containers, 75k/175k dwt bulk carriers, 300k dwt VLCC.

**Relevance to Thesis:**
Highly relevant as it demonstrates that weather conditions fundamentally change the speed-fuel relationship. The finding that added fuel consumption from waves is independent of ship speed (p. 12) has direct implications for our work: under SOG-targeting, the ship adjusts SWS to maintain target SOG through varying waves, but the wave-induced fuel penalty persists regardless. This means LP models that use calm-water cubic FCR with a single segment-average speed systematically underestimate fuel when weather varies along a segment. The paper's variable speed exponents (3.3–4.2) also suggest the Jensen effect may be even stronger than our cubic assumption implies. However, the paper simulates at constant SWS per voyage — it never considers SOG-targeting, where the ship must adjust engine power to maintain a schedule through varying conditions. No optimization is performed, and no forecast uncertainty or rolling horizon is considered.

**Quotable Claims:**
- "the common assumption of cubic speed-power relation can cause a significant error in the estimation of bunker consumption" (p. 1, abstract)
- "fuel savings due to speed reduction are highly weather dependent" (p. 1, abstract)
- "when the speed is reduced by 30%, fuel savings vary from 2% to 45% depending on ship type, size and weather conditions" (p. 1, abstract)
- "The extra fuel consumption for a voyage because of rough weather is nearly independent of ship speed" (p. 12)
- "fuel savings at reduced speed are larger in calm weather and much smaller in rough weather conditions" (p. 13)
- "Assuming cubic relation between power and ship speed can cause a significant error (up to 15% for 30% speed reduction) in the calculation of fuel savings by speed reduction" (p. 15, conclusions)

**Limitations / Gaps:**
- Speed is constant SWS per voyage — no SOG-targeting, no analysis of maintaining schedule through varying weather
- No speed optimization — purely parametric study of fuel savings at fixed speed reductions
- Monthly-averaged weather only — no real-time forecasts, no storm events, no wave directionality beyond head/beam
- No distinction between SOG and SWS — treats "ship speed" as the engine setting
- No comparison of optimization methods (LP, DP, or otherwise)
- No forecast uncertainty, rolling horizon, or re-planning
- No current effects — only waves considered as weather perturbation
- Route simulations assume constant speed along entire voyage — no segment-by-segment variation

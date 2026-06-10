# Pillar 6: Regulatory & Industry Context

**Purpose:** Motivate the entire thesis — why does fuel optimization matter now?

**Gap to establish:** Regulations now mandate fuel efficiency, but the tools available (LP-based, constant-weather assumptions) are inadequate. Dynamic approaches with real forecast data are needed but underdeveloped.

**Sub-topics:** IMO GHG strategy (2023 revision), EEXI, CII, EU ETS for shipping (2024), SEEMP Part III

---

## Articles

<!-- Paste entries from _template.md below this line -->

---

### [Tadros, M., Ventura, M. & Guedes Soares, C. (2023)] Review of the IMO Initiatives for Ship Energy Efficiency and Their Implications

- **Citation:** Tadros, M., Ventura, M., Guedes Soares, C., 2023. *Review of the IMO Initiatives for Ship Energy Efficiency and Their Implications*. Journal of Marine Science and Application, 22(4), 662-680. https://doi.org/10.1007/s11804-023-00374-2
- **PDF:** `context/literature/pdfs/Tadros2023_IMOEnergyEfficiency.pdf`
- **Tags:** `IMO`, `EEDI`, `EEXI`, `CII`, `SEEMP`, `decarbonization`, `GHG-strategy`, `speed-reduction`

**Summary:**
Comprehensive review of all major IMO regulatory instruments for ship energy efficiency, from EEDI (2013) through EEXI and CII (2023), and long-term decarbonization strategies targeting 40% carbon intensity reduction by 2030 and 50% total GHG reduction by 2050 versus 2008 baselines. Categorizes five technical pathways (hull, propulsion, fuels, energy recovery, operations) with individual reduction potentials from 1% to 85%. Concludes that voyage speed optimization is the fastest-impact operational measure for existing fleets.

**Key Findings:**
- Speed reduction cuts fuel and emissions by over 20% (p. 663)
- CII enters force January 2023; ships rated A–E annually; D or E requires corrective SEEMP revision (p. 668)
- EEXI applies EEDI methodology to existing ships; uses 75% MCR or 83% MCR under engine power limitation (p. 668)
- Voyage planning in weather conditions identified as high-impact, near-term SEEMP-compliant solution (p. 667)
- CO2 reduction potential by category is 1%–85% depending on ship type and measure combination (pp. 665-666)
- IMO 2050 target revised to net-zero at MEPC 80 (July 2023) (p. 668)
- Ship performance data along routes in varying weather identified as essential for optimal decision-making (p. 673, Conclusion 8)

**Methodology:**
Systematic narrative review using Scopus database. Covers IMO MEPC sessions from MEPC 40 (1997) through MEPC 80 (July 2023). Organizes findings across five technical categories, three regulatory tiers (design indices EEDI/EEXI, operational indices CII/EEOI, management plans SEEMP), and two strategic horizons (short-term to 2030, long-term to 2050). Draws on IMO circulars, classification society guidance (DNV, LR, ABS, Bureau Veritas), and peer-reviewed literature.

**Relevance to Thesis:**
Directly motivates the regulatory backdrop. The thesis's three contributions — LP vs DP ranking reversal, forecast error propagation, and RH superiority — are all exercises in operational speed optimization, which this paper identifies as a primary SEEMP-compliant, near-term tool for CII rating improvement. The CII's annual rating structure means voyage-level fuel decisions directly determine regulatory standing. Conclusion 8 ("ship performance data along the route in different weather conditions will help achieve optimal decision-making solutions") is essentially a call for the weather-conditioned speed optimization the thesis develops. EEXI constrains maximum engine power, narrowing the feasible speed range and amplifying the Jensen's inequality effect.

**Quotable Claims:**
- "This technique allows the ship to reduce the level of engine loading to achieve lower speeds, thus making beneficial effects in reducing fuel consumption and cutting the level of emissions by more than 20%" (p. 663)
- "The CII, as an operational index, comes into force on the 1st of January 2023, and the first rating will be available in 2024" (p. 668)
- "The optimization of voyage planning while sailing in weather conditions [...] has the ability to be integrated into an on-board decision support system" (p. 667)
- "The availability of ship performance data along the route in different weather conditions will help achieve optimal decision-making solutions" (p. 673)
- "The companies can be charged with some fines and can be compelled to cancel the sailing licenses of the ships" (p. 663)

**Limitations / Gaps:**
- No quantitative treatment of speed optimization — identifies it as high-impact but provides no mathematical framework or algorithm
- Weather-conditioned optimization treated as undifferentiated category — no LP vs DP vs RH distinction
- Forecast quality ignored despite recommending weather-conditioned voyage planning
- Review horizon ends at MEPC 80 (July 2023) — subsequent amendments not covered
- No economic modeling of compliance cost pathways

---

### [Bouman, E.A., Lindstad, E., Rialland, A.I. & Stromman, A.H. (2017)] State-of-the-art technologies, measures, and potential for reducing GHG emissions from shipping — A review

- **Citation:** Bouman, E.A., Lindstad, E., Rialland, A.I., Stromman, A.H., 2017. *State-of-the-art technologies, measures, and potential for reducing GHG emissions from shipping — A review*. Transportation Research Part D: Transport and Environment, 52, 408-421. https://doi.org/10.1016/j.trd.2017.03.022
- **PDF:** `context/literature/pdfs/Bouman2017_GHGReductionReview.pdf`
- **Tags:** `GHG-review`, `slow-steaming`, `EEDI`, `SEEMP`, `speed-optimization`, `weather-routing`, `alternative-fuels`, `meta-analysis`

**Summary:**
Systematic review of approximately 150 studies cataloguing 22 individual GHG abatement measures for shipping across five categories — operational, hull/propulsion, machinery, alternative fuels, and regulatory. Finds maritime CO2 can be reduced by a factor of 4–6 per freight unit using current technologies, and reductions exceeding 75% are achievable by 2050 through combined deployment. Speed optimization emerges as the single operational measure with the widest reduction range (1–60%), making it the most tractable near-term lever.

**Key Findings:**
- Speed reduction / slow steaming: CO2 reduction potential of 1–60%, largest range of any single operational measure (pp. 412–416)
- Voyage optimization (including weather routing): 0.1–48% reduction potential (pp. 412–416)
- Emissions per freight unit can be reduced by a factor of 4–6 using the full portfolio of current technologies (p. 419)
- No single measure alone is sufficient; reaching >75% sector-wide reduction by 2050 requires simultaneous deployment under strong regulatory forcing (p. 419)
- Maritime CO2 represents ~3% of total anthropogenic GHG emissions; business-as-usual projects 150–250% growth by 2050 (pp. 408–409)
- EEDI and SEEMP identified as primary regulatory mechanisms already requiring energy efficiency improvements (pp. 409–410)

**Methodology:**
Systematic literature review and meta-analysis of ~150 studies. Harmonized heterogeneous reduction estimates across different ship types and baselines into common percentage-reduction framework. 22 measures classified across 5 categories. Combined potential assessed by assuming independent (multiplicative) measure effects. No new empirical data.

**Relevance to Thesis:**
Canonical justification for Pillar 6. Speed reduction is the highest-leverage single operational measure (1–60%). The thesis shows that the *method* used to operationalize speed reduction — LP with averaged weather vs DP with time-varying weather — produces systematically different outcomes due to Jensen's inequality on cubic FCR. Regulators relying on LP-computed plans overestimate actual compliance performance. Weather routing potential of "0.1–48%" implicitly assumes perfect forecasts; our Contribution 2 shows forecast error degrades realized savings. Bouman cites weather routing as major opportunity but does not distinguish static vs adaptive replanning — our RH contribution (Contribution 3) directly operationalizes the dynamic end of this spectrum.

**Quotable Claims:**
- "CO2 emissions from maritime transport represent around 3% of total annual anthropogenic greenhouse gas emissions [...] these emissions are assumed to increase by 150–250% in 2050" (p. 408; body text gives 2.6% for 2012 per Third IMO GHG Study, 3.5% for 2007)
- "In terms of emissions per freight unit transported it is possible to reduce emissions by a factor 4–6" (Abstract)
- Speed optimization: 1–60% CO2 reduction; voyage optimization: 0.1–48% (Table 2, p. 415; prose on p. 416 notes "many data points lie well beyond the 3rd quartile boundary, suggesting low agreement in the literature" and "most studies indicate a potential less than 10 percent" for voyage optimization)

**Limitations / Gaps:**
- Treats "speed optimization" as monolithic — no SWS vs SOG distinction, no LP vs DP comparison
- Weather routing and speed optimization treated as independent measures; in practice they are coupled
- No distinction between deterministic and stochastic/adaptive optimization
- Predates CII (2023), EU ETS for shipping (2024), and revised IMO 2023 GHG strategy
- All cited potentials are plan-level estimates, not realized savings from real voyages

---

### [Jia, H., Adland, R., Prakash, V. & Smith, T. (2017)] Energy efficiency with the application of Virtual Arrival policy

- **Citation:** Jia, H., Adland, R., Prakash, V., Smith, T., 2017. *Energy efficiency with the application of Virtual Arrival policy*. Transportation Research Part D: Transport and Environment, 54, 50–60. https://doi.org/10.1016/j.trd.2017.04.037
- **PDF:** `context/literature/pdfs/Jia2017_VirtualArrival.pdf`
- **Tags:** `Virtual-Arrival`, `SEEMP`, `speed-optimization`, `slow-steaming`, `AIS`, `VLCC`, `GHG-emissions`, `port-congestion`, `just-in-time`, `fuel-savings`, `charterparty`

**Summary:**
First global empirical study of the fuel and emissions savings achievable through Virtual Arrival (VA) policy, evaluated across 5,066 voyages by 483 VLCCs between 44 countries during 2013–2015 using AIS position data. VA is an operational process where a ship voluntarily reduces speed when a known berth delay at the destination port allows the extra sailing time to be used productively. The paper quantifies savings under four scenarios of excess port-time reduction (25–100%) and finds average fuel savings of 7.3–19% per voyage, with corresponding CO2 reductions of 240–653 tonnes, positioning VA alongside SEEMP as a near-term IMO-aligned operational measure.

**Key Findings:**
- Under the 50% excess port-time scenario, VA delivers an average 12.5% fuel saving and avoids 422 tonnes of CO2 and 6.7 tonnes of SOx per voyage (Abstract, p. 50)
- Fuel savings range from 7.26% (25% excess port time recovered) to 19.13% (100% excess port time recovered), corresponding to 77–226 tonnes of HFO saved per voyage (Table 5, Table 6, pp. 57–58)
- Average VLCC port call is 4.01 days vs. 22.66 days sailing time; port time represents ~21% of total voyage days (Table 1, p. 54)
- Average sailing speed across the sample is 11.26 knots; minimum feasible speed for VLCCs is taken as 7 knots (p. 56)
- Fuel consumption follows the cubic power law (n = 3) relative to speed, consistent with Psaraftis and Kontovas (2013) (Eqs. 3–7, pp. 53–55)
- Total fleet-level cost savings across 5,066 voyages reach USD 195 million under Scenario I (25% reduction) (p. 58)
- CO2 reduction per voyage ranges from 240 tonnes (Scenario I) to 653 tonnes (Scenario IV) (Table 7, p. 58)
- Charterparty "utmost dispatch" clauses identified as key contractual barrier preventing VA uptake (pp. 55, 59)

**Methodology:**
AIS bottom-up empirical analysis. Vessel positions at high temporal resolution from exactEarth (2013–2015) for 483 VLCCs. Fuel consumption calculated using the 3rd IMO GHG Study methodology (Smith et al., 2015a): cubic speed–FCR relationship normalised by vessel displacement and design speed (Eq. 2). Port calls identified algorithmically as SOG < 1 knot for ≥ 6 hours. Minimum port time estimated as DWT/pump capacity (laden) or 78 hours (ballast). Excess port time allocated to sailing across four scenarios (25%, 50%, 75%, 100%). Emissions computed via IMO emission coefficients. Bunker costs at Fujairah 380cst spot price on day of departure.

**Relevance to Thesis:**
Directly supports the regulatory motivation of Pillar 6. Demonstrates that existing commercial practice — ships steaming at full speed to congested ports under "utmost dispatch" clauses — is systematically inefficient, and that a simple operational reallocation of time can yield 7–19% fuel savings. This is the domain the thesis addresses: how to compute the optimal speed plan when a time window is available. However, the paper treats VA purely as an average speed-reduction problem: it uses a single average voyage speed and applies the cubic formula to that scalar (Eqs. 3–7). Jensen's inequality on the cubic FCR means that optimizing over a constant average speed underestimates fuel relative to a correctly segment-resolved plan (Contribution 1). Forecast uncertainty is structurally absent — the paper assumes the excess port time is known in advance, analogous to assuming perfect weather (Contribution 2). Contribution 3's Rolling Horizon approach operationalizes the adaptive re-planning that Jia et al. recommend but never implement.

**Quotable Claims:**
- "Key potential measures to improve energy efficiency and reduce emissions are speed optimization and improved communication with charterers and ports to work towards 'just in time' operation when there are known delays in port (Virtual Arrival)" (Abstract, p. 50)
- "Even if only 50% of the estimated waiting time can be avoided, the consequential slow-down in average sailing speeds leads to an average reduction of 422 tonnes of CO2 and 6.7 tonnes of SOx emissions per voyage" (Abstract, p. 50)
- "Fuel savings can range from 7.26% with only a 25% reduction in 'excess' port time, to 19% if all apparent inefficiencies can be removed" (p. 58)
- "There is the potential to deploy AIS data in real time to predict congestion and, hence, aid ship owners and operators in optimizing arrival times [...] the ability to adjust speed will also depend on other external factors like weather and contractual clauses" (p. 59)

**Limitations / Gaps:**
- Speed optimization modelled as a single average-speed scalar per voyage — no multi-segment routing, no intra-voyage speed variation, no weather effects on hull resistance
- Cubic FCR applied to average speed violates Jensen's inequality: true fuel cost of a varying-speed voyage exceeds the fuel cost at average speed, making all savings estimates optimistic lower bounds
- No weather conditioning — environmental resistance (wind, waves, currents) absent from the fuel model
- No distinction between LP, DP, or any optimization algorithm — VA is implemented as a simple speed ratio reduction
- Forecast uncertainty structurally absent: assumes excess port time is known in advance
- No adaptive re-planning mechanism — VA is a one-shot voyage-start decision
- Scope limited to VLCCs on tramp trades; may not generalize to liner services or the thesis's tanker route

---

### [IMO (2023)] 2023 IMO Strategy on Reduction of GHG Emissions from Ships

- **Citation:** IMO, 2023. *2023 IMO Strategy on Reduction of GHG Emissions from Ships*. Resolution MEPC.377(80), adopted 7 July 2023.
- **PDF:** `context/literature/pdfs/IMO2023_MEPC377_GHGStrategy.pdf`
- **Tags:** `IMO-GHG`, `decarbonization`, `net-zero`, `MEPC`

**Summary:**
The revised IMO GHG Strategy adopted at MEPC 80 (July 2023) significantly strengthens the ambition of the initial 2018 strategy. Sets net-zero GHG emissions from international shipping "by or around" 2050, with indicative checkpoints of at least 20% reduction by 2030 and at least 70% reduction by 2040 (striving for 30% and 80% respectively), all compared to 2008 levels. Identifies lifecycle GHG assessment, well-to-wake framework, and a basket of mid-term measures (carbon levy, fuel standard) as implementation mechanisms.

**Key Findings:**
- Net-zero target (s.3.3.4, p. 6): "to reach net-zero GHG emissions by or around, i.e. close to, 2050" — hedged language, not a hard 2050 deadline
- 2030 checkpoint (s.3.4.1, p. 6): "at least 20%, striving for 30%, by 2030, compared to 2008"
- 2040 checkpoint (s.3.4.2, p. 6): "at least 70%, striving for 80%, by 2040, compared to 2008"
- Carbon intensity target: "at least 40% by 2030" (s.3.3.2); zero/near-zero fuel uptake: "at least 5%, striving for 10%" of energy by 2030 (s.3.3.3)
- Well-to-wake explicitly mentioned in sections 3.2 (p. 5) and 4.7 (p. 8) in context of LCA guidelines
- Confirms EEXI, CII, and enhanced SEEMP as short-term measures already in force

**Methodology:**
IMO regulatory resolution adopted by the Marine Environment Protection Committee at its 80th session (MEPC 80), London, 3-7 July 2023. Consensus-based international negotiation among 175 member states. Builds on the initial 2018 strategy (MEPC.304(72)) with strengthened targets based on updated science and political commitments.

**Relevance to Thesis:**
The 2023 revised strategy is the current regulatory anchor motivating the entire thesis. The net-zero 2050 target and the 2030/2040 checkpoints create urgent demand for operational fuel efficiency measures — speed optimization being the highest-leverage near-term tool (Bouman et al., 2017: 1-60% potential). The CII annual rating system means that the accuracy of fuel estimation directly affects regulatory compliance planning: if LP-based tools systematically underestimate fuel (Jensen's inequality, Contribution 1), ships may receive worse CII ratings than planned. The thesis's RH approach (Contribution 3) provides a more accurate fuel estimation and optimization framework aligned with the regulatory need for reliable operational planning.

**Quotable Claims:**
- "to reach net-zero GHG emissions from international shipping by or around, i.e. close to, 2050" (s.3.3.4, p. 6)
- "at least 20%, striving for 30%, by 2030, compared to 2008" (s.3.4.1, p. 6)
- "at least 70%, striving for 80%, by 2040, compared to 2008" (s.3.4.2, p. 6)

**Limitations / Gaps:**
- Policy document, not technical — provides targets but no methodology for achieving them
- Does not specify which operational measures (speed optimization, weather routing, etc.) should be prioritized
- Mid-term economic measures (carbon levy, fuel standard) still under negotiation as of 2024
- No guidance on how voyage-level optimization tools should account for forecast uncertainty
- Does not address the SOG vs SWS distinction or its implications for CII calculation accuracy

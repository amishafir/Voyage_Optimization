# Pillar 4: Simulation Methodology & SOG-Targeting

**Purpose:** Defend SOG-targeting as the correct simulation model. This is the most novel methodological contribution.

**Gap to establish:** The maritime optimization literature overwhelmingly simulates plans by holding SWS constant (what the engine does). But ships target SOG (to meet arrival schedules). This difference, through Jensen's inequality on cubic FCR, reverses the LP vs DP ranking. Nobody has identified this.

**Sub-topics:** SOG-targeting in practice, Just-in-time arrival / virtual arrival, Plan-vs-actual simulation frameworks, Slow steaming literature, Jensen's inequality in applied optimization

---

## Articles

<!-- Paste entries from _template.md below this line -->

---

### [Huotari, J., Manderbacka, T., Ritari, A. & Tammi, K. (2021)] Convex Optimisation Model for Ship Speed Profile: Optimisation under Fixed Schedule

- **Citation:** Huotari, J., Manderbacka, T., Ritari, A., Tammi, K., 2021. *Convex Optimisation Model for Ship Speed Profile: Optimisation under Fixed Schedule*. Journal of Marine Science and Engineering, 9(7), 730. https://doi.org/10.3390/jmse9070730
- **PDF:** `context/literature/pdfs/Huotari2021_ConvexSpeedProfile.pdf`
- **Tags:** `SOG-targeting`, `plan-vs-actual`, `Jensen-inequality`

**Summary:**
Presents a convex optimization model for ship speed profile optimization under a fixed schedule, combined with Dijkstra-based DP. Tested on 5 ship types across 20 transatlantic voyages (Houston to London Gateway) using actual weather forecasts from NAPA/Tidetech. The combined DP+convex approach saves 1.1% fuel on average versus fixed speed, rising to 3.5% in voyages with significant weather variation.

**Key Findings:**
- Combined DP+convex method is 22% more effective than DP alone at finding fuel-saving speed profiles
- Average fuel savings of 1.1% across all ships/voyages vs. fixed speed operation; 3.5% when weather variation is significant
- Speed profile optimization benefits faster ships more (S175, WILS II container ships) than slower bulk carriers/tankers
- Convex optimization adds only 4.69s computational overhead vs. 2.84min for DP graph initialization
- In an example voyage, speed profile optimization avoided a storm region and saved 3.8% fuel (43 tons, ~136 tons CO2)
- "The fuel saving impact of speed profile optimisation of ships with a fixed schedule in general is small, although not negligible" (p. 18)

**Methodology:**
Convex optimization + Dijkstra's algorithm on a time-distance graph. Ship performance model with calm water resistance (ITTC-1957), wave added resistance, current effects (vector projection), and air resistance. Wave resistance linearized to maintain convexity. Minimizes cumulative resistance as proxy for fuel (since power = resistance x speed breaks convexity). 5 ship types (bulk carrier, cruise ship, KVLCC2 tanker, S175 and WILS II container ships). 20 voyages, 9,280 km each. Actual weather forecasts from Tidetech via NAPA Voyage Optimization. Fixed schedule constraint (= must arrive on time).

**Relevance to Thesis:**
This paper is highly relevant because its fixed schedule constraint is implicitly SOG-targeting — the ship must arrive at the destination on time, so it must achieve a target average SOG. However, the authors never explicitly frame this as "SOG-targeting" vs "SWS-targeting" — they simply constrain arrival time. This is exactly the gap we identify: the field uses SOG-targeting operationally (fixed schedule = arrive on time = target SOG) but never names it or analyzes the implications for the convexity/Jensen's inequality effect. Their use of convex optimization explicitly exploits the convexity of the resistance function, but they don't connect this to the averaging problem that arises when LP uses segment-mean speeds. Their finding that "models for liner network design typically assume a fixed speed between ports" (p. 17, ref [49]) and that "this assumption of fixed speed between ports does not interfere with the accuracy of such models in a major way" directly supports — and also contrasts with — our finding that the constant-speed LP assumption DOES matter under SOG-targeting.

**Quotable Claims:**
- "Models for liner network design and industrial and tramp routing and scheduling typically assume a fixed speed between ports" (p. 17)
- "the fuel saving impact of speed profile optimisation of ships with a fixed schedule in general is small, although not negligible" (p. 18)
- "the combined approach was approximately 22% more effective in saving fuel across all of the tested journeys and ships" (p. 13)

**Limitations / Gaps:**
- Never explicitly distinguishes SOG-targeting from SWS-targeting — the fixed schedule is implicitly SOG-targeting but the authors don't name this or analyze implications
- Single route (transatlantic) — no comparison across different route types
- No comparison of LP vs DP approaches — only DP+convex vs DP alone vs fixed speed
- No rolling horizon or re-planning — uses a single forecast for each voyage
- Minimizes resistance as proxy for fuel consumption (drops the speed multiplier for convexity) — doesn't directly address the cubic FCR and Jensen's inequality
- No forecast error analysis — uses actual weather forecasts without examining degradation with lead time
- Does not examine how different simulation models (SOG-target vs fixed-SWS) would change the ranking of methods

---

### [Fagerholt, K., Laporte, G. & Norstad, I. (2010)] Reducing fuel emissions by optimizing speed on shipping routes

- **Citation:** Fagerholt, K., Laporte, G., Norstad, I., 2010. *Reducing fuel emissions by optimizing speed on shipping routes*. Journal of the Operational Research Society, 61(3), 523-529. https://doi.org/10.1057/jors.2009.77
- **PDF:** `context/literature/pdfs/Fagerholt2010_FuelSpeedOptimization.pdf`
- **Tags:** `LP-based`, `SOG-targeting`, `Jensen-inequality`

**Summary:**
Addresses speed optimization on shipping routes where fuel consumption is a cubic function of speed. Given a sequence of ports with time windows, formulates the problem as a nonlinear continuous program and alternatively as a shortest path problem on a directed acyclic graph, where arrival times are discretized. The DAG approach is shown to be superior, and the paper reports 21% average fuel savings compared to design-speed operation for a ship with multiple port calls under varying sea conditions (as described in Huotari et al. 2021, p. 2).

**Key Findings:**
- Fuel consumption modeled as cubic function of speed — convexity is central to the solution approach
- Reformulation as shortest path on DAG outperforms nonlinear programming solver
- 21% average fuel savings compared to operation at design speed (as cited by Huotari et al. 2021)
- The convexity of the cubic fuel function means the optimal solution equalizes speeds across legs as much as time windows allow — this is Jensen's inequality in action (f(mean) <= mean(f) for convex f)
- Norstad et al. (2011) extended this with a "smoothing algorithm" that explicitly leverages convexity to equalize speeds

**Methodology:**
Nonlinear continuous program for speed optimization with port time windows. Alternative formulation: discretize arrival times, build directed acyclic graph, solve as shortest path. Fuel consumption = cubic function of speed. Multiple port calls with time windows. The smoothing algorithm (in the companion Norstad 2011 paper) recursively adjusts speeds on adjacent legs toward equality, exploiting the convexity property that equal speeds minimize total fuel for a given total time.

**Relevance to Thesis:**
This is the paper most directly relevant to our Jensen's inequality argument. The smoothing algorithm's core insight — that equalizing speeds across legs minimizes fuel because fuel is convex in speed — is precisely the mathematical property we identify as causing the LP vs DP ranking reversal under SOG-targeting. However, Fagerholt et al. use this convexity to generate better plans (equalize planned speeds). We use the same convexity to analyze what happens when plans are simulated under varying weather: if actual SOG varies from the planned constant speed (which it must under SOG-targeting), Jensen's inequality means actual fuel exceeds the plan's estimate. LP assumes constant speed per segment (which is optimal by Fagerholt's logic), but SOG-targeting simulation reveals this underestimates fuel — and DP, which captures the speed variation, doesn't have this bias. The paper establishes the mathematical foundation we build upon, while our contribution is applying it to the plan-vs-actual simulation gap.

**Quotable Claims:**
- "Fuel consumption and emissions on a shipping route are typically a cubic function of speed" (from abstract)
- "Extensive computational results confirm the superiority of the shortest path approach and the potential for fuel savings on shipping routes" (from abstract)
- Page-specific quotes require TAU access — download before thesis submission

**Limitations / Gaps:**
- Optimizes the plan — never analyzes what happens when the plan is executed under different weather than assumed
- No simulation of planned speeds under actual conditions (SOG-targeting vs fixed-SWS question not addressed)
- Assumes known, deterministic port time windows — no forecast uncertainty
- Single optimization method (DAG shortest path) — no comparison of LP vs DP approaches
- No rolling horizon or re-planning
- The convexity insight is used purely for plan optimization, not for analyzing the bias that convexity creates in plan-vs-actual fuel estimation

---

### [Cariou, P. (2011)] Is slow steaming a sustainable means of reducing CO2 emissions from container shipping?

- **Citation:** Cariou, P., 2011. *Is slow steaming a sustainable means of reducing CO2 emissions from container shipping?* Transportation Research Part D: Transport and Environment, 16(3), 260-264. https://doi.org/10.1016/j.trd.2010.12.005
- **PDF:** `context/literature/pdfs/Cariou2011_SlowSteamingCO2.pdf`
- **Tags:** `slow-steaming`, `Jensen-inequality`, `SOG-targeting`

**Summary:**
Measures the rate of CO2 emission reductions from slow steaming across major container trades (2008-2010) using fleet data for 2,051 containerships on 387 services. Estimates bunker break-even prices at which slow steaming is economically sustainable per trade. Finds an overall 11.1% CO2 reduction, but sustainability requires bunker prices of $350-400/ton for main east-west trades.

**Key Findings:**
- Overall 11.1% reduction in CO2 emissions from container shipping between 2008 and 2010 (from 170 Mt to 151 Mt CO2)
- Greatest reductions on multi-trade (-16.5%) and Europe/Far East (-16.4%) services; smallest on Australasia/Oceania (-4.1%)
- 42.9% of vessels were slow steaming in January 2010; proportion rises with vessel size (19.4% for 1000-2000 TEU vs 75.5% for 8000+ TEU)
- A 30% speed reduction yields 55% fuel consumption reduction (e.g., 4000 TEU ship: 182 tons/day at design speed vs 85 tons/day at 17-18 kn)
- Bunker break-even price: $259/ton for multi-trades, $345 for Europe/Far East, $440 for North Atlantic, >$550 for Australasia/Oceania and Latin America

**Methodology:**
Empirical fleet-level analysis. Fuel consumption estimated via SFOC x engine load x kW h (Eq. 2), with CO2 = 3.17 x fuel burned (Eq. 1). Speed-power relationship uses the "third power" rule of thumb. Data: Lloyd's Register-Fairplay (451 vessels with consumption data, 1,930 with engine kW h), Alphaliner (2,051 vessels on 387 services, January 2010). Break-even price model (Eq. 3) balances fuel savings against additional vessel operational costs and in-transit inventory costs ($27,331/TEU, 35% interest rate). Assumes SFOC of 195 g/kW h at design speed rising to 205 g/kW h at 30% speed reduction.

**Relevance to Thesis:**
Canonical slow steaming reference (407 citations) that exemplifies the assumption our thesis challenges. Cariou's framework treats speed as a single controllable variable — design speed Vds reduced to slow steaming speed Vss — with the "third power" rule giving fuel savings. "Speed" here is implicitly SWS: the engine is set to a lower output. There is no consideration of weather effects on the actual speed achieved (SOG). The paper notes "This value varies by engine type and can change in different weather conditions" (p. 261) but does not pursue it. The cubic fuel-speed relationship that Cariou uses to estimate a 55% fuel reduction is the same convexity that, under SOG-targeting with real weather, causes Jensen's inequality to inflate actual fuel consumption above the constant-speed estimate.

**Quotable Claims:**
- "a rule of thumb is that engine power is related to ship speed by a third power" (p. 261)
- "This value varies by engine type and can change in different weather conditions" (p. 261)
- "bunker consumption and CO2 emissions decreased by an estimated 11.1% in 2010 as a consequence of slow steaming" (p. 262)
- "slow steaming can only remain sustainable if bunker prices remain high or if powerful market-based solutions, such as tax levies and/or cap-and-trade systems, are implemented" (p. 263)

**Limitations / Gaps:**
- Speed is treated as a single controllable variable (SWS) — no distinction between SOG and SWS, no weather effects on actual speed achieved
- Uses the cubic "rule of thumb" without questioning whether the exponent varies with conditions
- No simulation of vessel performance under real weather — purely economic/fleet-level analysis
- No optimization comparison (LP, DP, or otherwise)
- No forecast uncertainty, rolling horizon, or re-planning considerations
- Assumes uniform 55% fuel reduction for all slow-steaming vessels regardless of route weather conditions

---

### [Yang, L., Chen, G., Zhao, J. & Rytter, N.G.M. (2020)] Ship Speed Optimization Considering Ocean Currents to Enhance Environmental Sustainability in Maritime Shipping

- **Citation:** Yang, L., Chen, G., Zhao, J., Rytter, N.G.M., 2020. *Ship Speed Optimization Considering Ocean Currents to Enhance Environmental Sustainability in Maritime Shipping*. Sustainability, 12(9), 3649. https://doi.org/10.3390/su12093649
- **PDF:** `context/literature/pdfs/Yang2020_SpeedOptOceanCurrents.pdf`
- **Tags:** `STW-SOG-distinction`, `ocean-currents`, `LP-optimization`, `genetic-algorithm`, `speed-correction-model`, `Kwon-method`, `DTU-SDU-method`, `tanker-case-study`, `SOG-targeting`

**Summary:**
Identifies a systematic error in the prior ship speed optimization literature: all existing models conflate Speed Through Water (STW) with Speed Over Ground (SOG) when formulating the fuel consumption function and the sailing time function. Proposes an LP-style speed optimization model that explicitly distinguishes the two, using Kwon's method for wind/wave speed loss and a vector decomposition model for ocean current correction. A case study on a 280-hour, 3,393 nm oil products tanker voyage (Persian Gulf to Strait of Malacca, 12 segments, 13 waypoints) demonstrates 2.20% bunker fuel savings and 26.12 MT CO2 reduction compared to the actual voyage.

**Key Findings:**
- Ignoring ocean currents produces an average SOG estimation error of 4.75% across 12 segments; incorporating currents reduces this to 1.36% (p. 16, Table 10)
- FCR is a function of SWS (via brake power), not SOG; sailing time is a function of SOG via distance/SOG — the paper establishes the explicit chain: SWS (decision) -> STW (wind/wave correction) -> SOG (current correction) -> sailing time (p. 5, Section 3.1; p. 6, Figure 1)
- Optimized total fuel consumption is 372.62 MT versus 381.01 MT estimated pre-optimization, a saving of 8.39 MT (2.20%) for the 280-hour voyage (p. 18, Table 12)
- The DTU-SDU fuel consumption model achieves a maximum relative error below 6.50% and average of 3.75% against measured data (p. 15, Table 9)
- Weather is treated as static per segment (constant Beaufort, wave height, current speed/direction within each 24-hour noon-report segment), not time-varying (p. 5, Section 3.1)

**Methodology:**
Genetic Algorithm (real-coded, population 200, 100 generations) to solve the nonlinear speed optimization model. Ship: oil products tanker, LOA 244.6 m, 109,672 MT DWT, rated power 15,260 kW, SWS range 8.0–15.7 knots. Route: Port A (24.75°N, 52.83°E, Persian Gulf) to Port B (1.81°N, 100.10°E, Strait of Malacca), 3,393.24 nm, 12 segments, 13 waypoints. Weather from actual ship noon reports. Fuel consumption model: physics-based DTU-SDU method (Kristensen and Lutzen). Speed correction: Kwon's empirical method for wind/wave speed loss combined with vector decomposition for ocean currents. ETA constraint (total sailing time <= 280 h) enforced via large-M penalty.

**Relevance to Thesis:**
Foundation paper for all three thesis contributions. **Contribution 1:** Establishes the definitive model in which the optimizer chooses SWS, FCR is computed from SWS (cubic-like relationship), and SOG is computed from SWS through weather corrections — precisely the regime where Jensen's inequality on cubic FCR applies. Table 12 shows SWS and SOG differing by 0.5–1.5 knots per segment, making the distinction quantitatively material. **Contribution 2:** Assumes deterministic, static weather per segment from historical noon reports with no forecast uncertainty — explicitly identifying the gap our second contribution fills. **Contribution 3:** Section 6 explicitly calls for future work using weather forecast data with 6-hour temporal resolution and speed adjustment every 6 hours — precisely the NWP refresh cycle our rolling horizon strategy exploits. The paper defines the problem our thesis solves and articulates the research direction our thesis pursues.

**Quotable Claims:**
- "Existing research on ship speed optimization does not differentiate speed through water (STW) from speed over ground (SOG) when formulating the fuel consumption function and the sailing time function." (p. 1, Abstract)
- "STW should not be confused with SOG in speed optimization models. Otherwise, incorrect calculations of fuel consumption and/or sailing time will be obtained." (pp. 2–3, Section 1)
- "When the influence of ocean currents is not considered, the average relative error of the speed correction model is 4.75%; when the influence of ocean currents is taken into account, this value becomes 1.36%." (p. 16, Section 5.1.2)
- "In practical applications, the proposed model can be refined by using the actual weather forecast data... it should be possible for us to include weather forecast data with a spatial resolution of 0.5° and a temporal resolution of 6 h in future studies... the set speed of the ship can be adjusted every 6 h." (p. 21, Section 6)

**Limitations / Gaps:**
- Weather is static per segment (24-hour noon reports) — cannot represent intra-segment weather variation or forecast updates during voyage
- No forecast uncertainty — all weather inputs treated as exact; no analysis of how forecast errors propagate to fuel consumption errors
- No rolling horizon re-planning — speed plan computed once at departure; explicitly noted as future work (Section 6)
- Single voyage, single ship type — results validated on one tanker voyage only
- Solver is GA, not structured LP or DP — no comparison between optimization paradigms under the same SOG-targeting framework
- No Jensen's inequality analysis — does not examine convexity consequences of evaluating plans at SWS vs SOG
- No DP or graph-based alternative for comparison

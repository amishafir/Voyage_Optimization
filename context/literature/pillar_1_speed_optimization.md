# Pillar 1: Ship Speed Optimization

**Purpose:** Show what exists in ship speed optimization, identify the gap — no one compares LP vs DP vs RH under realistic simulation on the same route with the same physics model.

**Gap to establish:** Most papers compare one method against a baseline. Nobody does LP vs DP vs RH on the same route with the same physics model, and nobody examines how the simulation model (SOG-target vs fixed-SWS) affects the ranking.

**Sub-topics:** LP-based voyage optimization, DP/graph-based approaches, Rolling horizon/MPC in maritime, Metaheuristics (GA, PSO), Weather routing vs speed optimization

---

## Articles

<!-- Paste entries from _template.md below this line -->

---

### [Psaraftis, H.N. & Kontovas, C.A. (2013)] Speed models for energy-efficient maritime transportation: A taxonomy and survey

- **Citation:** Psaraftis, H.N., Kontovas, C.A., 2013. *Speed models for energy-efficient maritime transportation: A taxonomy and survey*. Transportation Research Part C, 26, 331-351. https://doi.org/10.1016/j.trc.2012.09.012
- **PDF:** `context/literature/pdfs/Psaraftis2013_SpeedModelsSurvey.pdf`
- **Tags:** `survey`, `speed-optimization`, `slow-steaming`, `FCR-convexity`, `LP-based`

**Summary:**
Comprehensive survey and taxonomy of 40+ speed models in maritime transportation where ship speed is a decision variable. Classifies models along 13 taxonomy parameters and covers both emissions-aware and non-emissions models from 1981-2012. Establishes that the cubic fuel consumption function (f = Bv^n, n >= 3) is standard for tankers/bulkers while containerships may require n = 4-5.

**Key Findings:**
- Fuel consumption approximated as f(v) = A + Bv^n; most papers assume A = 0, n = 3 (cubic); containerships may need n = 4 or 5 (p. 335)
- Ship owner and time charterer face mathematically equivalent speed optimization problems — both depend on q = p/s ratio (p. 337)
- Weather routing noted as one domain where "ship speed is dynamically updated" — described as exception to general scarcity of dynamic speed models (p. 341)
- Zero papers found using rolling horizon / MPC for ship speed optimization across entire 40+ paper survey
- Most models assume speed is constant across a leg or the entire voyage
- Slow steaming widely practiced since ~2007 (Maersk trials reducing engine load to 10%), with super-slow-steaming reaching half of design speed (p. 334)

**Methodology:**
Literature review and taxonomy-based classification. 40+ papers classified across 13 parameters in Tables 2a-2e. Ship types covered: VLCC, tankers, containerships, bulk carriers, LNG/LPG carriers. Fuel consumption data based on real VLCC curves from IHS Fairplay database (2007 fleet, 45,620 ships).

**Relevance to Thesis:**
This is the definitive survey of the field. It confirms the cubic FCR is universal (n = 3), which underpins our Jensen's inequality argument. Critically, it treats speed as SWS throughout — "weather also plays a role in both bounds, with a usual approximation involving a speed margin for anything else than calm weather" (p. 340). The survey documents zero rolling horizon or MPC approaches: "the scarcity of 'dynamic' speed models" (p. 341). This directly establishes the three gaps our thesis fills: no RH, no SOG-targeting, no forecast error analysis in 40+ reviewed papers.

**Quotable Claims:**
- "A usual approximation is that function f is equal to A + Bv^n with A, B and n input parameters such that A >= 0, B > 0 and n >= 3. [...] Most papers in the literature assume a cubic function, that is, A = 0 and n = 3" (p. 335)
- "For these ships [containerships], exponent n can be 4 or 5 or conceivably even higher." (p. 335)
- "The other general observation is the scarcity of 'dynamic' speed models in the literature, even though a model that assumes no fixed cargo throughput within a certain time interval, but a rolling horizon in which costs or profits are optimized per unit time might want to consider ship speed as a key variable." (p. 341)
- "weather also plays a role in both bounds, with a usual approximation involving a 'speed margin' for anything else than calm weather." (p. 340)

**Limitations / Gaps:**
- No SOG vs SWS distinction — entire survey treats "speed" as a single variable without distinguishing speed through water from speed over ground
- No rolling horizon or MPC models found — survey explicitly flags this gap but does not fill it
- No forecast error analysis — weather uncertainty mentioned only for Lo & McCord (1998) ocean currents
- No simulation of plan vs actual — every surveyed model computes an optimal plan; none simulate what happens when that plan meets different weather
- Cubic FCR convexity is stated but Jensen's inequality implication for segment-averaged LP is never mentioned

---

### [Bektas, T. & Laporte, G. (2011)] The Pollution-Routing Problem

- **Citation:** Bektas, T., Laporte, G., 2011. *The Pollution-Routing Problem*. Transportation Research Part B: Methodological, 45(8), 1232-1250. https://doi.org/10.1016/j.trb.2011.02.004
- **PDF:** `context/literature/pdfs/Bektas2011_PollutionRouting.pdf`
- **Tags:** `LP-based`, `speed-optimization`, `FCR-convexity`, `power-speed-exponent`

**Summary:**
Introduces the Pollution-Routing Problem (PRP), extending the VRP to simultaneously optimize routes, speeds, and loads while minimizing fuel consumption, CO2 emissions, and driver costs. Uses a fuel model where fuel rate includes a speed-squared aerodynamic drag component (cubic in speed for fuel per unit time). Formulated as a MILP and tested on instances of 10-20 customers.

**Key Findings:**
- Fuel rate decomposes into load-dependent term (weight x distance) and speed-dependent term (speed-squared x distance, i.e., cubic for fuel per unit time)
- Minimizing emissions can increase total cost by up to 58% vs distance-minimizing VRP
- Optimal speeds significantly lower than fastest-path solutions — early formalization of "slow steaming" in OR
- Speed is a decision variable per arc, allowing different speeds on different segments
- PRP is computationally harder than classical VRP; 10-customer instances solved optimally, 20-customer require heuristics

**Methodology:**
MILP formulation for road freight. Fuel consumption model from Barth et al. (2005) Comprehensive Modal Emissions Model. Energy on arc (i,j) = alpha * d_ij * (w + f_ij) + beta * d_ij * v_ij^2 (Eq. 3-5), where alpha captures weight-dependent resistance, beta captures aerodynamic drag. Tested on modified Solomon VRPTW benchmark instances. Solved with CPLEX.

**Relevance to Thesis:**
Foundational reference for speed-dependent fuel optimization in OR (1,127 citations). The fuel model establishes the same mathematical structure we use: fuel consumption is convex (approximately cubic) in speed, meaning Jensen's inequality applies. The paper formulates speed optimization as LP/MILP — the paradigm we compare against. However, it is for road freight (no currents/waves), so the SOG vs SWS distinction is absent. The convexity is acknowledged but only exploited for planning, never analyzed for plan-vs-actual implications.

**Quotable Claims:**
- "The amount of pollution emitted by a vehicle depends on its load and speed, among other factors" (p. 1232)
- "the PRP is significantly more difficult to solve to optimality but has the potential of yielding savings in total cost" (p. 1232)

**Limitations / Gaps:**
- Road freight, not maritime — no ocean currents, waves, or wind creating SOG vs SWS distinction
- Deterministic conditions — no weather uncertainty, no forecast error propagation
- Static single-shot optimization — no rolling horizon or re-planning
- No plan-vs-actual simulation — speed is assumed achievable exactly
- No Jensen's inequality analysis despite convex fuel function

---

### [Norstad, I., Fagerholt, K. & Laporte, G. (2011)] Tramp ship routing and scheduling with speed optimization

- **Citation:** Norstad, I., Fagerholt, K., Laporte, G., 2011. *Tramp ship routing and scheduling with speed optimization*. Transportation Research Part C: Emerging Technologies, 19(5), 853-865. https://doi.org/10.1016/j.trc.2010.05.001
- **PDF:** `context/literature/pdfs/Norstad2011_TrampShipSpeedOpt.pdf`
- **Tags:** `speed-optimization`, `LP-based`, `FCR-convexity`, `Jensen-inequality`

**Summary:**
Extends Fagerholt et al. (2010) by integrating speed optimization into the full tramp ship routing and scheduling problem, where speed on each sailing leg is a continuous decision variable. Proposes a multi-start local search heuristic for routing and a recursive smoothing algorithm (RSA) for speed optimization that exploits convexity of the cubic fuel function to equalize speeds across legs.

**Key Findings:**
- Speed on each sailing leg introduced as a continuous decision variable
- Fuel consumption per distance unit modeled as convex quadratic: c(v) = 0.0036v^2 - 0.1015v + 0.8848
- RSA runs in O(n^2) time and exploits convexity to equalize speeds across legs (Jensen's inequality in action)
- RSA correctness formally proven in companion paper Hvattum et al. (2013)
- Incorporating speed optimization significantly improves fleet utilization and profit vs fixed-speed operation
- Combined routing + scheduling + speed optimization for tramp shipping with contracted and spot cargoes

**Methodology:**
Multi-start local search heuristic for routing/scheduling with embedded speed optimization via RSA. Fuel consumption is a convex function of speed. Port calls have time windows. Realistic tramp shipping instances with heterogeneous fleet. No weather effects — speed is still-water speed, deterministic.

**Relevance to Thesis:**
The RSA's core principle — convexity makes speed equalization optimal — is precisely the Jensen's inequality mechanism we identify. Norstad et al. use convexity to improve plans (equalize planned speeds). We show that under SOG-targeting simulation, the same convexity means LP's constant-speed assumption underestimates fuel when actual SOG varies. Together with Fagerholt et al. (2010), this 2010-2011 pair is the most direct predecessor to our work.

**Quotable Claims:**
- Fuel consumption per distance unit: c(v) = 0.0036v^2 - 0.1015v + 0.8848 (convex quadratic)
- "Taking speed into consideration in tramp ship routing and scheduling significantly improves the solutions" (from abstract)

**Limitations / Gaps:**
- No weather effects — speed is still-water speed with no wind, wave, or current perturbation
- No distinction between SWS and SOG — plan IS the outcome (deterministic)
- No forecast uncertainty or stochastic elements
- No rolling horizon or re-planning
- Convexity insight used only to improve plans, never to analyze bias in plan-vs-actual fuel estimation
- No comparison of LP vs DP optimization approaches

---

### [Hvattum, L.M., Norstad, I., Fagerholt, K. & Laporte, G. (2013)] Analysis of an exact algorithm for the vessel speed optimization problem

- **Citation:** Hvattum, L.M., Norstad, I., Fagerholt, K., Laporte, G., 2013. *Analysis of an exact algorithm for the vessel speed optimization problem*. Networks, 62(2), 132-135. https://doi.org/10.1002/net.21503
- **PDF:** `context/literature/pdfs/Hvattum2013_ExactAlgorithmSpeed.pdf`
- **Tags:** `speed-optimization`, `FCR-convexity`, `Jensen-inequality`

**Summary:**
Proves that a recursive O(n^2) algorithm for the vessel speed optimization problem (SOP) is exact. The proof relies on the convexity of fuel cost per distance unit as a function of speed: when the cost function is convex and non-decreasing, a constant speed across unconstrained segments is provably optimal, and binding time windows can be identified greedily.

**Key Findings:**
- Constant speed over an unconstrained sequence of ports is optimal when fuel cost is convex, non-decreasing (Proposition 1, p. 134)
- Recursive algorithm runs in O(n^2) worst case (Proposition 5, p. 135)
- Including speed as a decision variable reduces fuel consumption by ~14% on average vs fixed speeds (p. 132)
- 1% worldwide fuel reduction yields >1.2 billion USD savings and 10.5 million tonnes CO2 reduction (p. 132)
- Fuel consumption per distance unit is "approximately quadratic in speed" for most cargo ships (p. 133)

**Methodology:**
Pure algorithmic / mathematical proof. No simulation, no ship model, no weather data. Assumes generic convex, non-decreasing cost function c(v). 7-port numerical example (Durban to La Pallice, 14,500 nm, 40 days) with speeds 13.89-17.05 knots.

**Relevance to Thesis:**
Directly foundational. Proposition 1 is the mathematical statement that constant (averaged) speed is optimal under convexity — but this only holds for SWS in calm water. When weather varies and the ship targets SOG, the actual SWS fluctuates, and Jensen's inequality on cubic FCR means realized fuel exceeds the plan. This paper proves the LP-favorable result under idealized conditions; our thesis shows it breaks under SOG-targeting.

**Quotable Claims:**
- "as for most cargo ships fuel consumption per distance unit is approximately quadratic in speed over the domain [v, v_bar], the cost c(v_i) per distance unit will be a continuous and convex function" (p. 133)
- "including speed as a decision variable in route optimization reduces fuel consumption by 14% on average, compared with using fixed speeds" (p. 132)
- "Given a fuel oil price of 450 USD/tonne, a 1% worldwide reduction in the fuel consumption would yield cost reductions of more than 1.2 billion USD and a reduction in CO2 emissions of 10.5 million tonnes" (p. 132)

**Limitations / Gaps:**
- No weather modeling — speed is SWS in calm conditions, no wind/wave/current effects
- No distinction between SOG and SWS — proof assumes speed = distance/time, conflating the two
- Deterministic, static problem — no forecast uncertainty, no re-planning, no rolling horizon
- No simulation of plan execution under different conditions than assumed
- The "approximately quadratic" cost function (Ronen 1982) differs from cubic FCR itself — convexity is assumed but specific resistance model not detailed

---

### [Zaccone, R., Ottaviani, E., Figari, M. & Altosole, M. (2018)] Ship voyage optimization for safe and energy-efficient navigation: A dynamic programming approach

- **Citation:** Zaccone, R., Ottaviani, E., Figari, M., Altosole, M., 2018. *Ship voyage optimization for safe and energy-efficient navigation: A dynamic programming approach*. Ocean Engineering, 153, 215–224. https://doi.org/10.1016/j.oceaneng.2018.01.100
- **PDF:** `context/literature/pdfs/Zaccone2018_DPVoyageOptimization.pdf`
- **Tags:** `DP-based`, `voyage-optimization`, `weather-routing`, `Bellman-Ford`, `space-time-grid`, `NOAA`, `bulk-carrier`, `route-and-speed-optimization`

**Summary:**
Develops a 3D Dynamic Programming (Bellman-Ford) optimizer that simultaneously selects optimal route and speed profile on a discretized space-time grid, using NOAA WaveWatch III forecast maps as input. The ship model is physics-based: resistance is decomposed into still-water, wave-added, and wind components, and fuel consumption is evaluated via steady-state propulsion simulation (propeller open-water diagrams, engine performance maps) integrated over each segment. Results for a bulk carrier on a France-to-New York North Atlantic winter voyage show significant fuel savings over constant-speed great-circle sailing.

**Key Findings:**
- The DP optimizer produces a Pareto frontier of minimum fuel vs. ETA solutions, allowing the operator to read off the fuel cost of each hour of anticipation or delay (p. 221, Fig. 7)
- Full voyage optimization (speed + course) outperforms speed-only optimization; both outperform constant-speed great-circle, especially in head-sea westward conditions (p. 221)
- Eastward (following-sea) voyage shows much lower base fuel consumption and smaller optimization benefit, demonstrating strong directional asymmetry (p. 221, Fig. 20)
- Pruning strategies reduce Bellman-Ford computation to under 100 s for single-ETA cases; Pareto frontier (134 solutions) requires 100–5,000 s (p. 221, Table 3)
- Safety and comfort constraints (slamming probability < 3%, deck wetness < 7%, MSI < 10%) are integrated directly into the DP feasibility check (pp. 220–221, Eqs. 29–33)

**Methodology:**
3D DP on a discretized (stage x step x time) space-time graph; Bellman-Ford with problem-specific pruning; implemented in C++. Grid: 10 stages x 11 lateral steps, ~300 nm between waypoints, time discretized every 60 min. Ship: Bulk carrier, 182 m LOA, 31 m beam, 41,577 t displacement, 10 MW two-stroke diesel, fixed-pitch propeller. Route: North Atlantic, France to New York, winter 2016. Weather: NOAA WaveWatch III (GRIB, 6 h update cycle, 162 h forecast depth, 1.25° x 1° resolution). Physics: JONSWAP spectrum, RAO-based ship motions (6 DOF), Holtrop still-water resistance, Lewis added wave resistance, Blendermann wind resistance, propulsion chain from resistance through propeller KT/KQ diagrams to engine fuel map.

**Relevance to Thesis:**
The only DP/graph-based voyage optimization paper in Pillar 1, filling a critical gap. Zaccone's DP operates on constant speed per segment and evaluates fuel via a full propulsion model — it provides the canonical DP reference point against which our head-to-head LP vs DP comparison (same route, same physics) is novel. The paper explicitly acknowledges forecast uncertainty as a fundamental limitation of DP's determinism but provides no quantitative treatment — precisely the gap our forecast-error propagation analysis fills (Contribution 2). Plans once at departure using a single 162 h NOAA forecast and never re-plans — the direct gap our RH contribution addresses (Contribution 3). Does not isolate the cubic FCR or demonstrate Jensen's inequality (Contribution 1).

**Quotable Claims:**
- "DP is an exhaustive approach, i.e. it guarantees to identify the optimal solution associated to the discretization of the problem. Nevertheless, this advantage over heuristic global search algorithms is partially limited by the fact that input data is affected by significant uncertainties." (p. 220)
- "Decision making needs to be based on ship response, rather than on external conditions (Chen, 2013), in order to better fit different ship types, shapes and dimensions." (p. 215)
- "Note that Fig. 7 allows to easily estimate the cost of each hour of anticipation or delay in terms of tons of fuel consumed." (p. 221)

**Limitations / Gaps:**
- No comparison to LP or any other optimizer class on the same route and physics model — entirely single-method
- No quantitative analysis of forecast error sensitivity — acknowledges uncertainty qualitatively but never measures its effect on fuel estimates
- No rolling horizon or re-planning — voyage optimized once at departure using the full 162 h forecast
- Ship model uses constant speed per segment — does not isolate or analyze SOG-targeting vs fixed-SWS distinction
- Ocean currents absent from the resistance model
- No plan-vs-actual simulation — reports planned fuel but does not simulate executing the plan under realized weather
- Single test case (one departure date, one storm event); no statistical robustness across multiple scenarios

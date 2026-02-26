# Pillar 5: Rolling Horizon & Information Value

**Purpose:** Position RH as superior and explain why through information theory.

**Gap to establish:** Rolling horizon exists in OR theory but is rarely applied to ship speed optimization with real forecast data. Nobody has analyzed the interaction between NWP model refresh cycles and optimal replan frequency.

**Sub-topics:** Rolling horizon in stochastic optimization, Value of information (VOI), Stochastic weather routing, Re-planning frequency in operations, Forecast horizon vs decision horizon

---

## Articles

<!-- Paste entries from _template.md below this line -->

---

### [Zheng, J., Mao, C. & Zhang, Q. (2023)] Hybrid Dynamic Modeling and Receding Horizon Speed Optimization for Liner Shipping Operations from Schedule Reliability and Energy Efficiency Perspectives

- **Citation:** Zheng, J., Mao, C., Zhang, Q., 2023. *Hybrid Dynamic Modeling and Receding Horizon Speed Optimization for Liner Shipping Operations from Schedule Reliability and Energy Efficiency Perspectives*. Frontiers in Marine Science, 10, 1095283. https://doi.org/10.3389/fmars.2023.1095283
- **PDF:** `context/literature/pdfs/Zheng2023_RecedingHorizonSpeed.pdf`
- **Tags:** `rolling-horizon`, `MPC`, `ship-speed-optimization`, `schedule-reliability`, `re-planning`, `EEXI`, `liner-shipping`

**Summary:**
Proposes a Discrete Hybrid Automaton (DHA) model paired with Decentralized Model Predictive Control (DMPC) for real-time ship speed adjustment in liner operations. The receding horizon controller re-optimizes speed at every 1-hour time step to compensate for uncertain port handling efficiency. A case study on a 5-port circular route with 4 sister ships shows the controller reduces schedule deviations by 91.8% while integrating EEXI engine power limitation constraints.

**Key Findings:**
- Without control, cumulative schedule deviation reaches 879 hours; DMPC reduces to 72 hours — 91.8% reduction — at cost of higher fuel burn (2,193.61 t vs. 1,717.41 t) (p. 12, Table 5)
- Berthing-aware reference trajectory achieves 21.58% lower weighted cost vs only 10.79% for berthing-unaware reference (p. 12, Table 5)
- Single 7-hour port delay propagates without attenuation in uncontrolled scenario; DMPC eliminates delay transferability (p. 11)
- As EEXI reduction factor tightens from 20% to 40%, schedule deviation escalates from 72 h to 755 h because max speed drops to 14 kn (only 0.5 kn above service speed) (pp. 13–14, Table 7)
- MPC prediction and control horizons: 10 steps at 1-hour sampling (p. 7)
- Fuel consumption modeled via admiralty coefficient: N = 0.7355 · (D · v³ / C)^(2/3), confirming cubic speed–power relationship (pp. 5–6)

**Methodology:**
DHA with four modules (SAS, EG, MS, FSM) encoded as Mixed Logical Dynamical framework. DMPC with one local MPC controller per ship, solving MIP over 10-step horizon at each time step. Only first control action applied (receding horizon). Two reference trajectory designs compared. EEXI computed per IMO MEPC.350(78). Case study: circular route, 5 ports, 4 ships (24,336 DWT, MCR 12,268 kW, service speed 13.5 kn), 2 complete voyages (1,050 time steps). Disturbance: time-varying port handling efficiency.

**Relevance to Thesis:**
Most direct maritime precedent for MPC/receding-horizon ship speed optimization — key reference for Contribution 3. However, the uncertainty source is port handling efficiency (operational disturbance), not weather forecast error. Re-planning is triggered every time step regardless of forecast updates, whereas the thesis aligns re-planning with NWP refresh cycles (6h). The paper confirms the cubic fuel–speed relationship within MPC but does not compare against LP or DP baselines, does not model weather uncertainty, and does not study how forecast degradation with lead time affects fuel estimation.

**Quotable Claims:**
- "Traditional tactical-level planning often considers minimizing operating costs, fuel consumption, and carbon emissions as objectives [...] However, the service speed in tactical plans remains a fixed value for the voyage in adjacent ports and there are no indications for a ship to adjust sailing speed during a voyage." (p. 2)
- "In the receding horizon scheme, the prediction models predict future states in the prediction horizon after observing the current states; then, they calculate the tracking errors [...] At each step, only the first element of the control sequence is implemented and the rest are ignored." (p. 7)
- "The rolling optimization method considerably reduces fleet port delays; however, these improvements come at the expense of consuming more fuel and emitting more carbon emissions." (p. 14)
- "Wang et al. (2018) proposed a nonlinear model predictive control framework based on real-time updated environmental information and applied a particle swarm optimization algorithm to compute the optimal speed." (p. 2)

**Limitations / Gaps:**
- No weather forecast uncertainty — disturbance is port handling efficiency, not meteorological forecast error
- No NWP refresh cycle alignment — re-plans every 1-hour time step regardless of forecast update availability
- No forecast error propagation analysis
- No LP vs DP comparison — uses MIP/MPC exclusively
- Port-delay focus (schedule adherence weighted 4x over fuel) vs thesis's fuel-minimization focus
- Circular liner route with fleet synchronization vs thesis's single-vessel point-to-point voyage
- No connection to NWP forecast products (GFS, ECMWF, ICON)

---

### [Sethi, S.P. & Sorger, G. (1991)] A Theory of Rolling Horizon Decision Making

- **Citation:** Sethi, S.P., Sorger, G., 1991. *A Theory of Rolling Horizon Decision Making*. Annals of Operations Research, 29, 387-415. https://doi.org/10.1007/BF02283607
- **PDF:** `context/literature/pdfs/Sethi1991_RollingHorizonTheory.pdf`
- **Tags:** `rolling-horizon`, `dynamic-programming`, `stochastic-optimization`, `forecast-cost`, `information-value`, `replan-frequency`

**Summary:**
Develops the first rigorous theoretical framework for rolling horizon decision making in discrete-time stochastic dynamic optimization. The core thesis is that rolling horizon methods are not merely heuristic convenience but are *implied* by the economic cost of forecasting: forecasting the distant future is expensive and unreliable, so the optimal information acquisition policy endogenously produces a rolling structure. Proves that for discounted infinite-horizon problems, an optimal rolling horizon of finite, bounded length always exists when forecast costs grow sufficiently with lookahead distance.

**Key Findings:**
- Forecasting cost is the root cause of rolling horizons: "introducing forecasting costs may result in an optimal forecasting policy, which resembles the rolling horizon policy" (p. 390)
- Bounded optimal horizon (Theorem 3, pp. 404–405): exists a constant h independent of problem horizon N such that optimal rolling horizon never exceeds h periods ahead
- The bound is h = 1 + inf{j: c(i) > g_bar · a / (1-a) for all i >= j}, where c(i) is marginal forecast cost and g_bar is max per-period running cost
- Under stationarity and discounting, optimal rolling horizon and control laws are time-invariant (Theorem 6, p. 408) — justifies using a fixed re-plan frequency
- Framework generalizes to imperfect oracles (Section 6.1, pp. 408–410) and multiple/hierarchical forecast sources (Section 6.2, p. 410)
- Numerical example shows optimal horizon length varies with information state — fixed-length RH is suboptimal in general (pp. 411–413)

**Methodology:**
Pure theoretical. Discrete-time stochastic control model with forecast acquisition modeled as a stopping time. Two-level DP: outer stopping-time problem (how far to forecast) and inner control problem (what action to take). Augmented state X_t = (x_t, h_t, ξ_{h_t}) captures physical and information state. Proofs use measurable selection, conditional expectation, and contraction mapping. Single 5-period production planning numerical example.

**Relevance to Thesis:**
Provides the theoretical backbone for Contribution 3 (RH superiority through NWP refresh cycle alignment). Three direct connections: (1) Theorem 3's bounded optimal horizon maps to NWP refresh cycles — at what lookahead distance does fuel saving from better weather information cease to justify waiting for the next 6h NWP cycle? (2) The augmented DP state X_t = (x_t, h_t, ξ_{h_t}) is structurally identical to the thesis's RH optimizer with Predicted_weather_conditions[future_t][decision_hour] lookup. (3) Theorem 6 (stationarity) justifies using a fixed 6h re-plan interval rather than state-dependent variable intervals. The paper does not address Jensen's inequality/cubic FCR (Contribution 1) or forecast error propagation (Contribution 2).

**Quotable Claims:**
- "The main idea of our approach is that the usefulness of rolling horizon methods is, to a great extent, implied by the fact that forecasting the future is a costly activity." (p. 387)
- "Indeed, the forecast of the future is either expensive or unreliable or both. Also, the more distant the future, the more expensive, less reliable, or both, the forecast." (p. 389)
- "A forecast horizon is a finite horizon that is far enough off that the data beyond it have no effect on the optimal decisions in the current period." (p. 392)
- "The distinguishing feature of our paper, on the other hand, is that it integrates the forecasting activity as a decision variable to be determined simultaneously with other decision variables." (p. 392)

**Limitations / Gaps:**
- No domain-specific application — framework derived in production planning, never applied to transportation or fuel optimization
- Oracle cost is exogenous and stylized — in ship routing, forecast "cost" is implicit (fuel penalty from forecast error), not a direct monetary charge
- No stochastic model of forecast error — imperfect oracle extension is formal but not analyzed for effect on optimal horizon length
- Computational intractability acknowledged but unresolved — augmented state grows large quickly
- Discrete-time only — continuous-time extension described as "difficult, if not impossible" (p. 413)
- No multi-objective treatment — single-objective cost minimization only

---

### [Tzortzis, G.N. & Sakalis, G.N. (2021)] A dynamic ship speed optimization method with time horizon segmentation

- **Citation:** Tzortzis, G.N., Sakalis, G.N., 2021. *A dynamic ship speed optimization method with time horizon segmentation*. Ocean Engineering, 226, 108840. https://doi.org/10.1016/j.oceaneng.2021.108840
- **PDF:** `context/literature/pdfs/Tzortzis2021_TimeHorizonSegmentation.pdf`
- **Tags:** `time-horizon-segmentation`, `PSO`, `ship-speed-optimization`, `forecast-accuracy`, `dynamic-replanning`

**Summary:**
Proposes a dynamic ship speed optimization method that decomposes the full voyage time horizon into shorter sub-horizons, solving a separate PSO-based speed optimization problem within each segment using only forecast data reliable for that window. The core motivation is that meteorological forecasts degrade beyond approximately two days, making single-shot full-voyage optimization physically unjustified. Applied to a container ship route, the method demonstrates approximately 2% fuel savings over constant-speed and single-shot static optimization baselines.

**Key Findings:**
- Weather forecast accuracy degrades materially beyond approximately 48 hours, making single-shot voyage optimization unsound (p. 2)
- Decomposing the time horizon into smaller segments and re-optimizing at each boundary yields better fuel economy than optimizing once over the full route (p. 3)
- PSO applied independently within each time segment using the most up-to-date forecast at the re-planning point (p. 4)
- Case study on actual container ship route: approximately 2% fuel savings vs static constant-speed operation (p. 7)
- Number and size of time horizon segments is a tunable parameter — too few recovers static problem, too many loses optimization continuity (p. 5)

**Methodology:**
Fixed-route speed optimization with voyage time horizon partitioned into sequential sub-horizons. PSO applied at each sub-horizon start to select segment speeds given current weather forecast. Weather data: wind speed/direction, wave height, ocean currents per segment. Ship resistance via standard added-resistance components. Baseline comparisons: constant design speed and single static PSO over full horizon.

**Relevance to Thesis:**
Closest maritime precedent to Contribution 3 (RH superiority through NWP refresh cycle alignment). Tzortzis & Sakalis independently identify the same core insight: forecast degradation makes static optimization suboptimal, and periodic re-planning with fresh data improves fuel performance. However, they do not connect the re-planning interval to any specific NWP refresh cycle (GFS 6h, ECMWF 12h), treating segment length as a free empirical parameter. No comparison against LP or DP baselines (only constant speed). No Jensen's inequality analysis (Contribution 1). No forecast error propagation quantification (Contribution 2).

**Quotable Claims:**
- "The dependency of fuel consumption on speed, always in inseparable conjunction with the ever-changing weather conditions prevailing over any specified route, leads to the formulation of a (from mathematical point of view) not well-defined problem, when practical considerations regarding the capabilities of currently available weather forecast services are taken into account." (p. 1, Abstract)
- "Within the method, the problem of deteriorating accuracy of weather predictions for relatively long time periods is addressed with the segmentation of the route's total time horizon in smaller time periods." (p. 1, Abstract)
- "Meteorological forecasts are considered to be accurate for relatively short time horizons (approximately two days)." (p. 2)

**Limitations / Gaps:**
- No connection to NWP refresh cycles — re-plan interval is a free tuning parameter, not derived from GFS/ECMWF update cadence
- No LP vs DP comparison — only PSO (heuristic); optimality gap unknown
- No forecast error propagation analysis — acknowledges degradation qualitatively but doesn't quantify fuel estimation error
- No SOG vs SWS distinction — no Jensen's inequality analysis
- No plan-vs-actual simulation — doesn't simulate actual weather differing from forecast at re-plan boundary
- Only ~2% fuel savings — modest improvement with no sensitivity analysis
- Segment boundary design is empirical, not theoretically grounded

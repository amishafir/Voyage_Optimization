# Pillar 3: Weather Forecasting & NWP Models

**Purpose:** Ground the forecast error analysis and NWP cycle findings in meteorological literature.

**Gap to establish:** Speed optimization papers typically assume either perfect weather or a single forecast. Nobody has measured how forecast degradation with lead time propagates through the optimizer to affect fuel outcomes. Our forecast error curve + horizon sweep fills this.

**Sub-topics:** GFS/ECMWF forecast accuracy, NWP update cycles, Forecast accuracy in maritime context, Open-Meteo/reanalysis data, Atmospheric predictability limit

---

## Articles

<!-- Paste entries from _template.md below this line -->

---

### [Marjanovic, M., Prpic-Orsic, J., Turk, A. & Valcic, M. (2025)] Anomalous Behavior in Weather Forecast Uncertainty: Implications for Ship Weather Routing

- **Citation:** Marjanovic, M., Prpic-Orsic, J., Turk, A., Valcic, M., 2025. *Anomalous Behavior in Weather Forecast Uncertainty: Implications for Ship Weather Routing*. Journal of Marine Science and Engineering, 13(6), 1185. https://doi.org/10.3390/jmse13061185
- **PDF:** `context/literature/pdfs/Marjanovic2025_ForecastUncertaintyRouting.pdf`
- **Tags:** `NWP-accuracy-vs-lead-time`, `maritime-weather-routing`, `forecast-uncertainty`, `wave-wind-forecast-validation`, `NOAA-GFS`

**Summary:**
Quantifies temporal degradation of NOAA GFS forecast accuracy for wind speed, significant wave height, and wave period over a six-month North Atlantic winter dataset (October–March). Discovers that forecast uncertainty grows non-monotonically rather than steadily with lead time, with anomalous contraction at 96–120 h attributed to NWP model physics transitions. Integrates the uncertainty framework into a simulated annealing ship router, showing uncertainty-aware routing yields 3–7% longer voyage times for improved safety margins.

**Key Findings:**
- Wind speed RMSE grows from 0.5 m/s at 24 h to 4.0 m/s at 168 h (rate ~0.5 m/s per day); significant wave height RMSE degrades from 0.2 to 0.9 m (p. 11)
- Confidence intervals are non-monotonic: significant wave height 95% CI widens to 1.47 m at 72 h, *narrows* to 1.28 m at 120 h, then rises to 1.38 m at 168 h (pp. 16–17)
- Wind speed CRPS improved by 23% between 96–120 h; wave height CRPS actually *decreases* with lead time (trend slope −0.00036) (pp. 17–18)
- Anomalous behavior at 96–120 h corresponds to the transition between medium- and extended-range NWP model regimes (p. 17)
- Uncertainty-aware routes (Norfolk–Rotterdam, ~3,560–3,720 nm) are 3–7% longer in voyage time; in some cases uncertainty-aware routing uses *less* fuel by avoiding high-resistance weather (p. 22, Table 1)
- GEV distribution outperforms Gaussian for forecast error tails; negative shape parameters indicate bounded upper tails (p. 24)
- Temporal uncertainty model: U(v, t) = U₀(v) · e^(α_v · t + β_t), fit per variable with R² = 0.87–0.93 (p. 7)

**Methodology:**
NOAA GFS GRIB2 archive, 6-month winter period, 0.25° × 0.25° grid, North Atlantic (30°N–65°N, 80°W–10°E), four daily forecast cycles (00/06/12/18 UTC), horizons 0–168 h in 3-h steps. Pseudo-ensemble construction from multiple initialization times. Error metrics: RMSE, MAE, bias, CRPS. Distribution fitting from Normal/Lognormal/Weibull/Gamma/GEV families. Routing via simulated annealing with 8 intermediate waypoints, simplified linear speed loss model and cubic FCR. Test route: Norfolk VA to Rotterdam, bulk carrier 169.37 m, 14-knot service speed.

**Relevance to Thesis:**
Most directly relevant empirical foundation for Contribution 2 (forecast error propagation). Establishes the ground-truth degradation profile — wind RMSE growing from 0.5 to 4.0 m/s over 168 h — that our thesis uses to parameterize forecast uncertainty. The anomalous 96–120 h skill recovery directly motivates Contribution 3 (RH with NWP cycle alignment): the thesis argues that 6-hourly NWP re-initialization cycles produce this recovery, and that a Rolling Horizon exploiting these refresh boundaries outperforms static DP. However, the paper never propagates forecast error through a speed optimizer to measure fuel estimation error — the chain we complete. Their linearized speed model (Eq. 18) bypasses the cubic FCR nonlinearity, masking the Jensen's inequality mechanism (Contribution 1).

**Quotable Claims:**
- "Weather forecast uncertainty, which becomes increasingly pronounced beyond 72 h, presents a major operational blind spot." (p. 2)
- "This contradicts the common assumption that forecast uncertainty increases steadily with lead time, instead revealing distinct variable-specific patterns with important operational implications for ship-routing systems." (p. 16)
- "All variables show anomalous behavior around 96–120 h, corresponding to the transition from medium- to extended-range numerical forecast models." (p. 17)
- "[routing algorithms] treat uncertainty as a static parameter rather than a time-evolving function." (p. 3)
- "This differential error propagation rate of 0.5 m/s per day, coupled with the wider error dispersion at extended horizons (120–168 h), indicates that traditional uniform uncertainty models systematically underestimate risk in mid-to-long range voyage segments." (p. 11)

**Limitations / Gaps:**
- No fuel estimation error analysis by optimizer type — cannot distinguish whether LP or DP diverges more under increasing forecast RMSE
- Linearized speed model suppresses the cubic FCR nonlinearity and Jensen's inequality mechanism
- No rolling horizon / re-planning — single-shot optimization at departure time; 96–120 h skill recovery is never exploited through re-planning
- Optimizes waypoint geometry (route), not speed profile over a fixed route
- NOAA GFS data only; North Atlantic winter only — no ECMWF comparison, no tropical regions
- Pseudo-ensemble is not a true ensemble prediction system

---

### [Vettor, R. & Guedes Soares, C. (2022)] Reflecting the uncertainties of ensemble weather forecasts on the predictions of ship fuel consumption

- **Citation:** Vettor, R., Guedes Soares, C., 2022. *Reflecting the uncertainties of ensemble weather forecasts on the predictions of ship fuel consumption*. Ocean Engineering, 250, 111009. https://doi.org/10.1016/j.oceaneng.2022.111009
- **PDF:** `context/literature/pdfs/Vettor2022_EnsembleFuelUncertainty.pdf`
- **Tags:** `ensemble-forecasting`, `fuel-uncertainty-quantification`, `FOSM`, `wave-parameter-uncertainty`, `probabilistic-prediction`

**Summary:**
Investigates multiple methodologies for quantifying uncertainty in ship fuel consumption predictions arising from ensemble weather forecast spread, using a North Atlantic containership passage. Compares brute-force ensemble propagation against truncated-normal, lognormal, and first-order second-moment (FOSM) analytical methods. All four methods produce estimates in reasonable agreement, with observed fuel consumption falling within the 90% prediction interval, demonstrating that ensemble-derived weather spread translates into a material and quantifiable uncertainty band on fuel predictions.

**Key Findings:**
- Brute-force ensemble approach (one fuel prediction per ensemble member) serves as reference benchmark; all three analytical approximations replicate its mean and spread (pp. 6–9)
- Wave parameters (significant wave height, mean wave period) are the dominant drivers of fuel consumption uncertainty; wind plays a secondary role (pp. 4–5)
- Truncated-normal and lognormal fits to ensemble wave spread yield fuel uncertainty bounds closely matching brute-force reference (pp. 7–8)
- FOSM provides slightly wider but tractable analytical upper bound on fuel uncertainty (pp. 8–9)
- Observed fuel consumption falls within 90% prediction range for all four methods (p. 10)
- All methods converge on the same mean fuel estimate; differences are confined to uncertainty band width (pp. 9–10)

**Methodology:**
North Atlantic containership passage with fixed-speed (constant shaft power) assumption. Ensemble weather data comprising significant wave height and mean wave period from multi-member NWP ensemble forecast. Fuel modeled through added-resistance-in-waves framework with cubic speed-power-FCR relationship. Four uncertainty propagation strategies compared: brute-force ensemble sampling, truncated-normal fit, lognormal fit, and FOSM linearization. No route or speed optimization included.

**Relevance to Thesis:**
Closest existing work to Contribution 2 (forecast error propagation through the optimizer), yet stops critically short. Demonstrates that ensemble spread in wave parameters produces a measurable uncertainty band on fuel consumption — establishing the weather-to-fuel propagation channel is real and non-trivial. However, speed is held constant, so the cubic FCR nonlinearity is never exercised asymmetrically as Jensen's inequality (Contribution 1) demands. Their framework predicts symmetric uncertainty intervals; our thesis shows that when a speed optimizer responds to uncertain weather, the cubic relationship causes right-skewed fuel distribution. Furthermore, no study of how uncertainty bands narrow with fresher NWP initializations — precisely the RH mechanism (Contribution 3).

**Quotable Claims:**
- "The different approaches are compared for the North Atlantic passage of a containership showing reasonable agreement." (Abstract)
- "Ensemble weather forecasts are adopted to estimate the uncertainties associated with the environmental conditions the ship is asked to face." (Abstract)
- "A brute-force approach, consisting in repeating the fuel consumption predictions for each member of the ensemble, is compared with probabilistic approaches" (Abstract)

**Limitations / Gaps:**
- Speed held fixed — no speed optimizer present, so cubic FCR nonlinearity never exercised in response to varying weather; Jensen's inequality mechanism invisible
- No study of how uncertainty band width varies with forecast lead time
- No comparison of optimizer types (LP vs DP) — no optimizer at all
- No rolling horizon / re-planning — ensemble evaluated at departure time only
- Wave parameters only — ocean current uncertainty absent
- Fixed-speed added-resistance model, not SOG-targeting optimizer

---

### [Luo, X., Yan, R. & Wang, S. (2023)] Comparison of deterministic and ensemble weather forecasts on ship sailing speed optimization

- **Citation:** Luo, X., Yan, R., Wang, S., 2023. *Comparison of deterministic and ensemble weather forecasts on ship sailing speed optimization*. Transportation Research Part D, 121, 103801. https://doi.org/10.1016/j.trd.2023.103801
- **PDF:** `context/literature/pdfs/Luo2023_EnsembleSpeedOptimization.pdf`
- **Tags:** `ensemble-vs-deterministic-forecast`, `GEFS-NOAA`, `ECMWF-ERA5`, `speed-optimization-MILP`, `ML-fuel-model`, `data-fusion-noon-report`, `forecast-quality-speed-plan`

**Summary:**
Directly compares the downstream effect of deterministic versus ensemble weather forecasts (NOAA GEFS, 21 members) on ship sailing speed optimization over two real 9-day voyages. Introduces two meteorological data fusion methods for merging noon report records with ERA5 reanalysis data, then trains a Gradient Boosted Regression Tree (GBRT) model as the imperfect planning FCPM and an XGBoost model as the "actual" fuel consumption oracle. The ensemble-based speed plan achieves approximately 1% lower realized fuel consumption than the deterministic plan (556 vs. 550 tons combined across two voyages), with the authors projecting a 2 million ton annual global saving if the industry adopted ensemble forecasts.

**Key Findings:**
- Ensemble-optimized speed plan yields 1.00% lower actual fuel consumption than deterministic-optimized plan across the two test voyages combined: 550.74 tons vs. 556.08 tons (Table 12, p. 17)
- On voyage i (ballast) the ensemble plan saves 2.28% in actual fuel (290.28 t deterministic vs. 283.67 t ensemble); on voyage ii (laden) the ensemble plan marginally increases fuel by 0.47% (265.81 t vs. 267.07 t), illustrating that the advantage is not universal per voyage (Table 12, p. 17)
- Speed optimization alone (versus unoptimized noon-report speeds) already reduces combined fuel by 7.7% (596.56 t baseline vs. 556.08 t deterministic-optimized), demonstrating optimizer sensitivity to speed choice (p. 17)
- Rhumb line based data fusion method outperforms direct geographic matching: MAPE improves from 8.0% to 7.7% and R² from 0.721 to 0.777 on the XGBoost test set (Table 5, p. 15)
- The MILP speed optimizer (model M2, adapted from Yan et al. 2020) discretizes speeds at 0.1-knot intervals and solves with CPLEX; weather conditions are treated as static within each day-long segment
- The paper explicitly identifies the static forecast assumption as the key limitation and names the rolling horizon approach as the recommended future direction (Section 8, p. 18)

**Methodology:**
Noon report data from February 2019 to August 2020 (323 records total), with two held-out 9-day voyages (one ballast, one laden) used for the optimization comparison. Meteorological ground truth: ECMWF ERA5 reanalysis at 0.25° × 0.25° × 1 h (atmosphere) and 0.5° × 0.5° × 1 h (ocean waves). Forecast data: NOAA GEFS ensemble, 21 members (1 control + 20 perturbed), 0.5° × 0.5° × 6 h resolution, up to 16 days, four runs per day. Data fusion via rhumb-line interpolation (IDW over 24 interpolated hourly points per segment). Fuel model: XGBoost as oracle; GBRT as imperfect planning model (5% Gaussian noise added to features). Speed optimizer: MILP (M2) solved with CPLEX, speeds discretized at 0.1-knot intervals, weather fixed per 24-hour segment (static per voyage). Ensemble forecast aggregation: average predicted fuel across 20 perturbed members used as input to the optimizer.

**Relevance to Thesis:**
Most directly relevant existing paper to all three thesis contributions. Operationalizes the forecast-quality-to-fuel-outcome chain for the first time: imperfect GBRT model + deterministic or ensemble forecast input → MILP optimizer → realized fuel evaluated against ERA5 oracle. The 1% fuel gap between ensemble and deterministic plans directly quantifies what forecast quality buys in a speed optimization context. However, the paper does not decompose this gap by forecast lead time (Contribution 2), uses only a static MILP (LP-style) optimizer with no DP comparison (Contribution 1), and explicitly leaves rolling horizon as future work: "the vessel sailing speed optimization based on the static sea and weather conditions may not generate the optimal speeds throughout the voyage. In the future, we can implement the rolling-horizon approach" (Section 8, p. 18) — precisely Contribution 3.

**Quotable Claims:**
- "the total fuel consumption with the speed profile based on ensemble weather forecasts is 1 % lower than that based on deterministic weather forecasts." (p. 18, Conclusion)
- "speed optimization based on ensemble weather forecasts could save 2 million tons of fuel [annually], demonstrating the potential of ensemble weather forecasts in speed optimization." (p. 18)
- "the sea and weather conditions used for optimizing sailing speeds are static, as they are obtained through the latest updated weather forecasts before the ship's departure. However, the static sea and weather conditions cannot reflect the continuously changing environment at sea. Therefore, the vessel sailing speed optimization based on the static sea and weather conditions may not generate the optimal speeds throughout the voyage. In the future, we can implement the rolling-horizon approach." (Section 8, p. 18)
- "ship fuel consumption predictions rely on information about sea and weather conditions obtained from deterministic weather forecasts in phase two of these two-phase methods. However, due to chaos in the atmosphere and ocean and the imperfect depiction of their initial state, the forecast accuracy of deterministic weather forecasts decreases as the forecast period increases." (p. 4)

**Limitations / Gaps:**
- Static weather assumption: the entire voyage is planned at departure using the single best available forecast; weather is not updated mid-voyage — the paper explicitly flags this as the core open problem
- No rolling horizon / re-planning — the authors name it as explicit future work, which is precisely Contribution 3 of the thesis
- No analysis of how the ensemble-vs-deterministic fuel gap varies with forecast lead time; experiments use departure-time forecasts only
- Optimizer is a static MILP (LP-style); no DP or graph-based approach is tested — no comparison of optimizer architectures under forecast uncertainty
- Two test voyages only (n=2); ballast and laden results go in opposite directions, so statistical confidence in the 1% aggregate figure is limited
- The ML-based FCR model (XGBoost/GBRT) does not use the physics-based cubic SWS-FCR relationship; Jensen's inequality over the cubic is therefore not observable
- No decomposition of forecast error by variable: wind, waves, and current contributions to the fuel difference are not separated

---

### [Stopa, J.E. & Cheung, K.F. (2014)] Intercomparison of wind and wave data from the ECMWF Reanalysis Interim and the NCEP Climate Forecast System Reanalysis

- **Citation:** Stopa, J.E., Cheung, K.F., 2014. *Intercomparison of wind and wave data from the ECMWF Reanalysis Interim and the NCEP Climate Forecast System Reanalysis*. Ocean Modelling, 75, 65–83. https://doi.org/10.1016/j.ocemod.2013.12.006
- **PDF:** `context/literature/pdfs/Stopa2014_ECMWFvsNCEP.pdf`
- **Tags:** `ERA-Interim`, `ECMWF`, `NCEP-CFSR`, `reanalysis`, `wave-height`, `wind-speed`, `NWP-validation`, `buoy-validation`, `altimetry`, `temporal-homogeneity`

**Summary:**
Systematic head-to-head validation of ERA-Interim and NCEP CFSR wave and wind reanalysis products against 25 deep-water NDBC buoys and seven satellite altimeter missions covering 1979–2009. Quantifies bias, RMSE, scatter index, and temporal trend (Mann-Kendall) for wind speed and significant wave height across six global regions. ERA-I is found to be more temporally homogeneous and slightly more accurate in bulk error metrics, while CFSR better captures variability and extreme upper percentiles.

**Key Findings:**
- ERA-I generally underestimates wind speed (negative biases of 3–10% from 20th to 99th percentile) and wave height across all regions; ERA-I has lower RMSE and higher correlation in most regions (pp. 72–73, Table 1; p. 78, Table 2)
- ERA-I underestimates wave height standard deviation by approximately 30% relative to buoy observations due to smoother wind forcing; CFSR matches observed variability more closely (p. 78)
- CFSR exhibits an abrupt discontinuity beginning in 1994 linked to SSM/I satellite data assimilation, making it temporally inhomogeneous before that date; ERA-I shows no statistically significant Mann-Kendall trend, confirming homogeneity through time (pp. 73, 76–77)
- ERA-I underestimates extreme wave heights by 5–18% above the 90th percentile; CFSR-W biases are −8% to +4% in the same range (pp. 81–82, Fig. 16)
- Both products show RMSEs on the order of 0.5 m for wave height, correlation above 0.9, and comparable scatter indices across regions (p. 78)

**Methodology:**
Compares ERA-I (0.7° resolution, 6-hourly, WAM wave model with 4D-Var assimilation) and CFSR-W (0.5° WAVEWATCH III driven by 0.5° CFSR winds, 3-hourly, 3D-Var assimilation) against two independent observation types: 25 NDBC deep-water buoys in six regions (Peru, Hawaii, Gulf of Mexico, NW Atlantic, Alaska, NE Pacific) and seven satellite altimeter missions (1985–2010). Error metrics: normalized bias, RMSE, centered RMSE, correlation, scatter index, normalized standard deviation. Temporal homogeneity via seasonal Mann-Kendall test with Sen's slope. Coverage: 31 years (1979–2009), ~4.0 million buoy and ~6.9 million altimetry data pairs.

**Relevance to Thesis:**
Establishes the quantified error profile of the ECMWF reanalysis product — the upstream source of Open-Meteo forecasts used in the thesis. RMSE values (~0.3–0.6 m for wave height, ~1.3–1.7 m/s for wind speed) and negative bias in ERA-I wave heights constitute the baseline error magnitudes that propagate through the SOG and FCR calculations into the optimizer. ERA-I's demonstrated temporal homogeneity supports the modeling assumption that each fresh NWP cycle is drawn from a consistent-quality source, making the RH refresh cycle alignment argument (Contribution 3) tractable. This paper provides the credentialed anchor point for ECMWF data quality that the thesis builds upon for Contribution 2 (forecast error propagation). Note: ERA-I is the predecessor to ERA5 (0.25°, hourly), which is the current product underlying Open-Meteo; error magnitudes should be treated as approximate upper bounds on current product accuracy.

**Quotable Claims:**
- "ERA-I proves to be homogenous through time, while CFSR exhibits an abrupt decrease in the level of errors in the Southern Ocean beginning 1994." (p. 65, Abstract)
- "ERA-I generally underestimates the wind speed and wave height with lower standard deviations in comparison to observations, but maintains slightly better error metrics." (p. 65, Abstract)
- "Overall ERA-I has better homogeneity through time deeming it more reliable for modeling of long-term processes; however caution must be applied with analysis of the upper percentiles." (p. 65, Abstract)
- "ERA-I underestimates the wave height by 5% to 18% for the upper percentiles between 90th and 99.9th that are crucial in evaluation of extremes." (p. 82)

**Limitations / Gaps:**
- Evaluates reanalysis products (historical re-runs with full observation assimilation), not operational forecasts with a specific lead time — does not characterize forecast accuracy degradation with horizon, the central measurement our thesis performs
- No connection to downstream optimization or fuel consumption — stops at meteorological validation
- Global and climatological (31-year averages by region) — no route-specific error estimates for the Persian Gulf–Strait of Malacca corridor
- Does not examine forecast-vs-actual divergence at specific decision intervals (e.g., every 6 hours for rolling horizon)
- ERA-I (0.7°, 6-hourly) is predecessor to ERA5 (0.25°, hourly) — quantitative values are approximate for current products
- Wave height and wind speed errors reported independently; no joint error assessment for combined sea state descriptors (Beaufort) as used in the thesis resistance model

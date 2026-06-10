# 7. Discussion

<!-- ~1,500 words -->
<!-- Contributions carried: C1, C3, C4, C6 -->

## 7.1 Jensen's Inequality Mechanism

The ranking reversal observed in Section 6.3 — where LP goes from best under fixed-SWS to worst under SOG-targeting — is explained by Jensen's inequality on the convex cubic FCR. LP assigns a single SOG per segment based on segment-averaged weather. When the ship executes this plan under SOG-targeting, it must adjust SWS at each node to achieve the planned SOG given local conditions. Because weather varies within the segment, SWS varies node by node. The cubic FCR ensures that the fuel penalty at nodes requiring higher-than-average SWS always exceeds the fuel saving at nodes requiring lower-than-average SWS:

$$E[FCR(V_s)] \geq FCR(E[V_s])$$

DP avoids this bias because it assigns speed at each node given local weather — there is no within-segment averaging. RH inherits this advantage and adds forecast freshness: by injecting actual weather for the committed 6-hour window, the SWS computed during planning matches the SWS required during simulation almost exactly.

The magnitude of the Jensen's inequality effect depends on within-segment weather heterogeneity. Under the mild conditions of Route 1 (wind std 6.07 km/h, BN 3–4), LP's plan-simulation gap was +4.67 mt (+2.7%). Under the harsh conditions of Route 2 (wind std 16.8 km/h, BN 6–8), the gap widened to +6.69 mt (+3.2%) and violation rates increased from 2.9% to 16.5%, confirming that the Jensen's inequality penalty scales with weather variability.

## 7.2 Information Value Hierarchy

The 2×2 factorial decomposition (Section 6.5) separates three sources of fuel penalty:

- **Temporal freshness** (forecast error): +3.02 mt — the cost of using predicted weather instead of actual weather, holding spatial resolution constant.
- **Spatial resolution** (segment averaging): +2.44 mt — the cost of using 7 nodes instead of 138, holding weather source constant.
- **Re-planning benefit**: −1.33 mt — the additional saving from RH's periodic forecast refresh.

This establishes a clear hierarchy: forecast quality matters more than node count, which matters more than re-planning frequency. The practical implication is that investing in better forecasts (or fresher forecasts via more frequent NWP cycles) yields larger fuel savings than increasing spatial resolution of the optimization grid.

## 7.3 Weather Tax and Information Penalty

The theoretical bounds decompose total fuel into three components:

- **Average bound** (170.06 mt): the minimum fuel in calm water at constant speed.
- **Weather tax**: Route 1: 6.17 mt (3.5% of optimal); Route 2: 17.78 mt (8.2% of optimal). The 2.9× increase reflects the substantially harsher North Atlantic conditions.
- **Information penalty**: LP: +4.40 mt on Route 1 (segment averaging). DP: +5.99 mt on Route 1 (forecast staleness). RH: +0.17 mt on Route 1 (near-zero). On Route 2, RH's penalty remains small at +0.84 mt (+0.4%), while DP's violations make the penalty metric unreliable (simulated fuel falls below optimal due to SWS clamping).

RH's near-zero information penalty on both routes (0.1–0.4% of the optimal bound) confirms that the 6-hour re-planning cycle aligned to GFS updates effectively eliminates the practical consequences of forecast error for speed optimization, even under harsh conditions.

## 7.4 Route-Length Dependence

The forecast accuracy window — approximately 72 hours for reliable wind prediction — creates a route-length threshold. When the voyage fits within this window (as exp_b's 140 h nearly does), forecast error is modest across the entire voyage and the DP's single-forecast approach is adequate. When the voyage extends significantly beyond 72 hours, the final segments are planned on degraded forecasts, and RH's periodic refresh becomes critical.

This explains the observed pattern: on Route 1 (mild, 140 h), the DP-to-RH improvement is 5.82 mt (3.2%). On Route 2 (harsh, 163 h), forecast error accumulates far more aggressively — wind RMSE nearly quadruples over 144 h (+286%) compared to doubling on Route 1 (+103%). The DP's single-forecast approach produces 161 violations (41.5%), rendering the planned speed schedule largely infeasible. RH's periodic forecast refresh reduces violations to 15 (3.9%) and maintains fuel within 0.4% of the optimal bound.

The critical variable is the ratio of voyage duration to forecast accuracy horizon. When this ratio exceeds approximately 2 (voyage > ~144 h for GFS), RH provides material benefit. Below this threshold, the static DP is sufficient.

## 7.5 The 6-Hour Re-Planning Cycle as Operational Innovation

The alignment of the RH re-planning interval with the GFS initialization cycle is not a tuning choice — it is derived from the empirical finding that 86% of API calls at 1-hour frequency return identical data, while every call at 6-hour frequency returns genuinely fresh forecasts (Section 5.5). This means:

- **No information is lost** by re-planning every 6 hours instead of every hour: the NWP source has not updated in between.
- **Computational cost is reduced** by a factor of 6: 24 DP solves instead of 140 for Route 1.
- **API load is reduced by 83%**: critical for operational deployment on commercial vessels with limited bandwidth.

The re-planning frequency sweep (Section 6.7) confirmed this: fuel savings plateau at 6-hour intervals, with only 0.12% additional benefit from 1-hour re-planning. The marginal benefit of sub-6-hour re-planning is nil because the underlying forecast data are identical.

This finding bridges the gap between NWP infrastructure and maritime operations. The GFS 6-hour cycle, originally designed for atmospheric science, turns out to be the natural decision rhythm for ship speed optimization. Any operator with internet access and a simple optimization solver can capture 99.4% of the theoretical fuel savings by re-planning every 6 hours with the latest available forecast.

## 7.6 Comparison with Literature

The results are consistent with prior findings while extending them:

- **Norstad et al. (2011), Hvattum et al. (2013):** Speed equalization under convex FCR is confirmed. Our contribution adds the observation that this equalization breaks down under SOG-targeting simulation because weather variation within segments forces SWS variation.
- **Psaraftis and Kontovas (2013):** The "scarcity of dynamic speed models" remains largely unaddressed. Our RH implementation is among the first to use real NWP data rather than synthetic weather.
- **Zaccone (2018):** The single-forecast limitation acknowledged therein is now quantified: forecast staleness costs +5.99 mt (3.4%) on even a mild route.
- **Luo et al. (2023):** The ~1% ensemble forecast benefit they found is consistent with our temporal freshness effect (+3.02 mt). Their recommendation for rolling horizon is now implemented and validated.
- **Tzortzis and Sakalis (2021):** Their ~2% RH savings on a synthetic route are exceeded by our 3.2% RH-over-DP improvement, with the mechanism (NWP cycle alignment) now identified.

## 7.7 Limitations

1. **Two routes with contrasting but not extreme conditions.** Route 1 (BN 3–4) provides a calm baseline; Route 2 (BN 6–8) provides harsh winter conditions. The findings are consistent across both, but validation on additional routes (e.g., transpacific, tropical cyclone regions) would strengthen generalizability.
2. **Two routes.** Generalizability is limited to two ocean basins (Indian Ocean, North Atlantic). A third route (transpacific) was planned but dropped due to API rate limits on the 947-waypoint route.
3. **Single ship type.** The reference vessel is a medium tanker. Results may differ for container ships (higher speeds, different resistance profiles) or LNG carriers (lower speeds).
4. **Cubic FCR assumption.** The FCR coefficient (0.000706) and cubic exponent are not validated against engine-room data. Taskar and Andersen (2020) found exponents of 3.3–4.2, suggesting the cubic model may understate the Jensen's inequality effect.
5. **Simulation credibility.** Route 1 covers 134 of 140 voyage hours (96%). The missing 6 hours at the end use the last available weather observation, introducing a small approximation for the final legs.

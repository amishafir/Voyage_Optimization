# Literature Review Index

## Progress

| # | Pillar | Articles | Status |
|---|--------|:--------:|--------|
| 1 | Speed Optimization | 5 | In progress |
| 2 | Fuel Consumption & Resistance | 3 | In progress |
| 3 | Weather Forecasting & NWP | 4 | In progress |
| 4 | Simulation Methodology & SOG-Targeting | 4 | In progress |
| 5 | Rolling Horizon & Information Value | 3 | In progress |
| 6 | Regulatory & Industry Context | 3 | In progress |

**Total: 22 articles**

## All Articles

| Author(s) | Year | Pillar(s) | One-line Relevance |
|-----------|:----:|:---------:|-------------------|
| Huotari, Manderbacka, Ritari, Tammi | 2021 | 4 | Convex+DP speed profile optimization under fixed schedule; implicitly SOG-targeting but never names it |
| Fagerholt, Laporte, Norstad | 2010 | 4 | Cubic fuel → DAG speed optimization; convexity drives speed equalization (Jensen's inequality foundation) |
| Cariou | 2011 | 4, 6 | Canonical slow steaming reference; 11.1% CO2 reduction; cubic "rule of thumb" assumes SWS = SOG |
| Psaraftis, Kontovas | 2013 | 1 | Definitive survey of 40+ speed models; documents zero RH/MPC papers; cubic FCR standard |
| Bektas, Laporte | 2011 | 1, 2 | Pollution-Routing Problem; convex fuel-speed model; 1,127 citations; LP-based speed optimization |
| Norstad, Fagerholt, Laporte | 2011 | 1, 4 | Tramp routing + speed optimization; recursive smoothing algorithm exploits convexity to equalize speeds |
| Hvattum, Norstad, Fagerholt, Laporte | 2013 | 1, 2 | Proves constant speed is optimal under convex fuel cost — the result SOG-targeting overturns |
| Tezdogan, Demirel, Kellett, Khorasanchi, Incecik, Turan | 2015 | 2 | CFD: added resistance 15-30% of calm-water resistance; slow steaming vs design speed in waves |
| Psaraftis, Lagouvardou | 2023 | 2, 4 | Defends cubic law against regression pitfalls; exponent genuinely ~3; strengthens Jensen mechanism |
| Taskar, Andersen | 2020 | 2 | Speed exponent 3.3–4.2 across 6 ships; fuel savings 2–45% at 30% reduction; highly weather-dependent |
| Marjanovic, Prpic-Orsic, Turk, Valcic | 2025 | 3 | Forecast RMSE degradation curves (wind 0.5→4.0 m/s over 168h); non-monotonic uncertainty at 96–120h |
| Zheng, Mao, Zhang | 2023 | 5 | Receding horizon MPC for ship speed; 91.8% schedule deviation reduction; port-delay uncertainty (not weather) |
| Vettor, Guedes Soares | 2022 | 3 | Ensemble forecast uncertainty → fuel consumption bands; 90% prediction interval validated; no optimizer |
| Sethi, Sorger | 1991 | 5 | Foundational RH theory; proves bounded optimal horizon from forecast cost; 226 citations |
| Tzortzis, Sakalis | 2021 | 5 | Time horizon segmentation for speed optimization; ~2% fuel savings; recognizes forecast degradation but no NWP alignment |
| Tadros, Ventura, Guedes Soares | 2023 | 6 | EEDI/EEXI/CII review; speed reduction >20% emissions cut; voyage planning as SEEMP compliance tool |
| Bouman, Lindstad, Rialland, Stromman | 2017 | 6 | GHG reduction review (742 citations); speed optimization 1–60% potential; canonical regulatory motivation |
| Luo, Yan, Wang | 2023 | 3 | Ensemble vs deterministic forecast → MILP speed optimizer → 1% fuel saving; explicitly leaves RH as future work |
| Jia, Adland, Prakash, Smith | 2017 | 6 | Virtual Arrival policy; 7–19% fuel savings from speed reduction when port delays known; 5,066 VLCC voyages |
| Zaccone, Ottaviani, Figari, Altosole | 2018 | 1 | 3D DP (Bellman-Ford) voyage optimization on space-time grid with NOAA weather; acknowledges forecast uncertainty limits DP |
| Stopa, Cheung | 2014 | 3 | ECMWF ERA-I vs NCEP CFSR benchmark; ERA-I temporally homogeneous; validates ECMWF data quality for thesis |
| Yang, Chen, Zhao, Rytter | 2020 | 4 | Foundation paper: first to distinguish STW from SOG in speed optimization; 2.20% fuel saving; thesis route and ship |

## Cross-Pillar References

Articles spanning multiple pillars are listed here with their primary and secondary pillar assignments.

| Author(s) | Year | Primary | Secondary | Note |
|-----------|:----:|:-------:|:---------:|------|
| Huotari et al. | 2021 | 4 | 1, 2 | Also relevant to speed optimization (Pillar 1) and resistance modeling convexity (Pillar 2) |
| Fagerholt et al. | 2010 | 4 | 1, 2 | Also foundational for speed optimization (Pillar 1) and cubic fuel model (Pillar 2) |
| Cariou | 2011 | 4 | 6 | Also relevant to regulatory/industry context (Pillar 6) — slow steaming as emissions policy |
| Bektas & Laporte | 2011 | 1 | 2 | Also relevant to fuel consumption modeling (Pillar 2) — convex speed-fuel function |
| Norstad et al. | 2011 | 1 | 4 | Also relevant to simulation methodology (Pillar 4) — convexity/Jensen's inequality foundation |
| Hvattum et al. | 2013 | 1 | 2 | Also relevant to fuel consumption (Pillar 2) — proves convexity implies constant-speed optimality |
| Psaraftis & Lagouvardou | 2023 | 2 | 4 | Also relevant to simulation methodology (Pillar 4) — defends cubic exponent underpinning Jensen argument |
| Marjanovic et al. | 2025 | 3 | 5 | Also relevant to rolling horizon (Pillar 5) — 96–120h anomalous skill recovery motivates NWP-aligned re-planning |
| Bouman et al. | 2017 | 6 | 1 | Also relevant to speed optimization (Pillar 1) — speed reduction is highest-leverage single measure (1–60%) |
| Luo et al. | 2023 | 3 | 5 | Also relevant to rolling horizon (Pillar 5) — explicitly names RH as the solution to static forecast limitation |
| Jia et al. | 2017 | 6 | 1 | Also relevant to speed optimization (Pillar 1) — VA is speed optimization under time-window constraint |
| Yang et al. | 2020 | 4 | 1, 2 | Also relevant to speed optimization (Pillar 1) — LP-style optimizer with GA; also Pillar 2 — DTU-SDU fuel model |

# 7. Discussion

<!-- ~1,500 words -->
<!-- Contributions carried: C1, C3, C4, C6 -->

## 7.1 Jensen's Inequality Mechanism

<!-- Why SOG-targeting penalizes LP: segment averaging + cubic FCR -->
<!-- C1 -->

## 7.2 Information Value Hierarchy

<!-- temporal freshness > spatial resolution > re-planning -->
<!-- Supported by 2x2 decomposition: temporal +3.02 > spatial +2.44 > replan -1.33 -->
<!-- C4 -->

## 7.3 Weather Tax and Information Penalty

<!-- Average bound -> optimal bound = weather tax (6.17 mt) -->
<!-- Optimal -> LP/DP/RH = information penalty -->
<!-- LP: +4.40 mt (averaging), DP: +5.99 mt (forecast error), RH: +0.17 mt -->

## 7.4 Route-Length Dependence

<!-- When does dynamic optimization matter? -->
<!-- Critical variable: voyage_duration / forecast_accuracy_horizon -->
<!-- Short route fits within accurate window -> horizon irrelevant -->
<!-- C3 -->

## 7.5 Practical Implications

<!-- 6h replan = GFS cycle, 86% API redundancy -->
<!-- Bulk API reduces calls by 99.8% -->
<!-- C6 -->

## 7.6 Comparison with Literature

<!-- How our findings relate to Norstad2011, Psaraftis2013, Zaccone2018, etc. -->

## 7.7 Limitations

<!-- 1. Simulation credibility — exp_b 134/140h coverage, exp_d TBD -->
<!-- 2. Calm weather on exp_b (wind std 6.07 km/h) -->
<!-- 3. Two routes only (three with exp_c future work) -->
<!-- 4. Single ship type -->
<!-- 5. FCR cubic assumed, not validated against engine data -->


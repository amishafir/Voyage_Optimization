# 8. Conclusion

## 8.1 Summary of Contributions

This study compared three speed optimization approaches — LP, DP, and rolling horizon — on the same routes with the same physics model and real weather data, revealing mechanisms that are invisible to the prior literature:

1. **SOG-targeting reverses the LP/DP ranking.** Under the operationally realistic SOG-targeting simulation, LP's segment averaging triggers Jensen's inequality on the cubic FCR, inflating realized fuel to the level of constant-speed sailing. DP and RH, operating at node-level resolution, avoid this bias.

2. **RH with 6-hour re-planning achieves near-optimal fuel.** The rolling horizon captures 99.4% of the optimization span, coming within 0.1% of the perfect-foresight bound (176.40 vs 176.23 mt). The mechanism is actual weather injection at each decision point, which eliminates the mismatch between planned and realized conditions.

3. **The forecast horizon effect is route-length dependent.** On routes fitting within the ~72-hour accurate forecast window, the choice of forecast horizon has negligible impact. Beyond this window, RH's periodic refresh becomes critical.

4. **An information value hierarchy is established.** Temporal freshness (+3.02 mt) dominates spatial resolution (+2.44 mt), which dominates re-planning frequency (−1.33 mt).

5. **Empirical forecast error curves explain the mechanisms.** Wind speed RMSE doubles from 4.13 to 8.40 km/h over 133 hours, with a systematic positive bias that causes optimizers to prepare for headwinds that do not materialize.

6. **The optimal re-planning frequency aligns with the NWP model cycle.** A 6-hour interval captures every GFS update with zero information loss. Sub-6-hour re-planning provides only 0.12% additional benefit because the underlying data are identical.

## 8.2 Practical Recommendations

- **Adopt RH with 6-hour re-planning.** Any operator with internet access and a DP solver can capture 99.4% of theoretical fuel savings by re-planning every 6 hours aligned to the GFS cycle.
- **Use SOG-targeting simulation** for all method evaluations. Fixed-SWS simulation produces misleading rankings that favor LP.
- **Prioritize forecast quality over spatial resolution.** Fresher forecasts yield larger savings than finer waypoint spacing.
- **Deploy automated collection pipelines.** The 6-hour collection+optimization cycle demonstrated in this study is feasible with free API access and modest computing resources. The infrastructure itself is an operational innovation — not just a research tool.

## 8.3 Future Work

- **Harsh weather validation.** Route 2 (North Atlantic, winter) will test whether the mechanisms and rankings hold under Beaufort 8–10 conditions, where Jensen's inequality effects are expected to amplify.
- **FCR exponent sensitivity.** Varying the exponent from 3.0 to 4.2 (the range reported by Taskar and Andersen 2020) to quantify the sensitivity of the ranking reversal to FCR curvature.
- **Forecast quality threshold.** Identifying the forecast accuracy level at which LP's simplicity outweighs DP's precision — i.e., under what conditions does the ranking reversal disappear.
- **Multi-season robustness.** Repeating the experiments across seasons to confirm that the 6-hour re-planning interval remains optimal year-round.
- **Transpacific route.** A 17-day voyage (Yokohama to Long Beach, ~4,800 nm) would extend well beyond the GFS forecast horizon, testing RH under extreme forecast degradation.

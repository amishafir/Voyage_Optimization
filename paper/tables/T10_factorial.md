# Table 10: 2x2 Factorial Decomposition

<!-- Section 06 — Results -->

| Config | Nodes | Weather | Approach | Fuel (mt) |
|--------|:---:|---------|----------|:---:|
| A-LP | 7 | actual | LP (6 seg) | 178.19 |
| A-DP | 7 | predicted | DP | 181.20 |
| B-LP | 138 | actual | LP (6 seg) | 180.63 |
| B-DP | 138 | predicted | DP | 182.22 |
| B-RH | 138 | predicted | RH | 180.89 |

**Decomposition:**

| Effect | Value (mt) |
|--------|:---:|
| Temporal (forecast error) | +3.02 |
| Spatial (segment averaging) | +2.44 |
| Interaction (spatial mitigates temporal) | -1.43 |
| RH benefit (re-planning) | -1.33 |


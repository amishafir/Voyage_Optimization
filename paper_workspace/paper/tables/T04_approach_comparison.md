# Table 4: Optimization Approach Comparison

<!-- Section 04 — Methodology -->

| | LP | DP | RH |
|---|---|---|---|
| Weather source (planning) | Actual | Predicted | Predicted + Actual |
| Spatial resolution | 6 segments (~23 nodes each) | Per-node (138/389) | Per-node (138/389) |
| Temporal info | Single snapshot (hour 0) | Time-varying forecast | Fresh forecast every 6h |
| Re-planning | None | None | Every 6h |
| Simulation weather | Static (hour 0) | Static (hour 0) | Time-varying |
| Decision variable | SOG per segment | SOG per node | SOG per node |


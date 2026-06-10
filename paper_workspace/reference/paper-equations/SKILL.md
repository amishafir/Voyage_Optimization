# Paper Equations Reference

> All equations needed in the paper with LaTeX markup and numbering plan.

## Usage

```
/paper-equations
```

## Numbering Plan

| Eq # | Name | Section |
|------|------|---------|
| 1 | Froude number | 03 |
| 2 | Speed reduction coefficient lookup | 03 |
| 3 | Ship form coefficient lookup | 03 |
| 4 | Wind resistance (speed loss) | 03 |
| 5 | Wave added resistance | 03 |
| 6 | Current along-track component | 03 |
| 7 | SOG composite | 03 |
| 8 | FCR formula | 03 |
| 9 | Segment fuel | 03 |
| 10 | Total voyage fuel | 03 |
| 11 | LP objective | 04 |
| 12 | LP one-speed constraint | 04 |
| 13 | LP ETA constraint | 04 |
| 14 | DP edge cost | 04 |
| 15 | DP Bellman recursion | 04 |
| 16 | RH committed window | 04 |
| 17 | Jensen's inequality (FCR) | 04/07 |

---

## Physics Model (Eqs 1–10)

### Eq 1: Froude Number

$$F_n = \frac{V_s}{\sqrt{g \cdot L}}$$

where $V_s$ is SWS (m/s), $g = 9.81$ m/s², $L = 200$ m.

### Eq 2: Speed Reduction Coefficient

$$C_U = f(F_n, C_b)$$

Lookup from Table 3 (paper). Indexed by Froude number range and block coefficient ($C_b = 0.75$).

### Eq 3: Ship Form Coefficient

$$C_{Form} = f(BN, \Delta)$$

Lookup from Table 4 (paper). Indexed by Beaufort number and displacement ($\Delta = 50{,}000$ tonnes).

### Eq 4: Wind Resistance (Speed Loss)

$$\Delta V_{wind} = C_U \cdot C_{Form} \cdot BN \cdot (C_1 + C_2 \cos\theta_w + C_3 \cos^2\theta_w + C_4 \cos^3\theta_w + C_5 \cos^4\theta_w + C_6 \cos^5\theta_w)$$

where $C_1$–$C_6$ are direction reduction coefficients from Table 2, and $\theta_w$ is wind direction relative to ship heading.

### Eq 5: Wave Added Resistance

$$\Delta V_{wave} = \alpha \cdot H_w^{1.5} \cdot \frac{B}{L}$$

Empirical formulation based on significant wave height $H_w$, beam $B$, and length $L$.

### Eq 6: Current Along-Track Component

$$V_{c,\parallel} = V_c \cdot \cos(\theta_c)$$

where $V_c$ is current speed and $\theta_c$ is current direction relative to heading.

### Eq 7: Speed Over Ground (Composite)

$$SOG = V_s - \Delta V_{wind} - \Delta V_{wave} + V_{c,\parallel}$$

$$SOG = \max(0, SOG)$$

### Eq 8: Fuel Consumption Rate

$$FCR = 0.000706 \cdot V_s^3 \quad \text{(mt/h, } V_s \text{ in knots)}$$

### Eq 9: Segment Fuel

$$F_i = FCR(V_{s,i}) \cdot \frac{d_i}{SOG_i}$$

### Eq 10: Total Voyage Fuel

$$F_{total} = \sum_{i=1}^{N} F_i$$

---

## LP Formulation (Eqs 11–13)

### Eq 11: LP Objective

$$\min \sum_{i=1}^{S} \sum_{k=1}^{K} FCR(v_k) \cdot \frac{d_i}{SOG_{ik}} \cdot x_{ik}$$

where $S$ = number of segments, $K$ = number of speed choices, $v_k \in \{11.0, 11.1, \ldots, 13.0\}$ kn, and $SOG_{ik}$ is the SOG at segment $i$ with SWS $v_k$ under segment-averaged weather. $x_{ik}$ are SOS2 variables.

### Eq 12: One-Speed Constraint

$$\sum_{k=1}^{K} x_{ik} = 1 \quad \forall i$$

### Eq 13: ETA Constraint

$$\sum_{i=1}^{S} \frac{d_i}{SOG_i} \leq T$$

where $SOG_i = \sum_k SOG_{ik} \cdot x_{ik}$ and $T$ is the required arrival time.

---

## DP Formulation (Eqs 14–15)

### Eq 14: Edge Cost

$$c(i, t, k) = FCR(v_k) \cdot \frac{d_i}{SOG(v_k, w_{i,t})}$$

where $w_{i,t}$ is the weather at node $i$ at time $t$ (predicted or actual, depending on approach).

### Eq 15: Bellman Recursion (Forward)

$$J^*(i+1, t') = \min_{k} \left[ J^*(i, t) + c(i, t, k) \right]$$

where $t' = t + d_i / SOG(v_k, w_{i,t})$. The optimal path is recovered by backtracking parent pointers from the minimum-cost state at the destination.

---

## RH Formulation (Eq 16)

### Eq 16: Rolling Horizon Decision Rule

At each decision point $\tau = 0, \Delta\tau, 2\Delta\tau, \ldots$:

1. Load predicted weather with $\text{sample\_hour} = \tau$
2. Replace predicted weather with actual weather for nodes within $[\tau, \tau + \Delta\tau]$
3. Solve DP for remaining voyage (nodes $i_\tau$ to $N$)
4. Commit speeds for nodes within $[\tau, \tau + \Delta\tau]$
5. Advance to $\tau + \Delta\tau$

where $\Delta\tau = 6$ h (aligned to GFS cycle).

---

## Jensen's Inequality (Eq 17)

### Eq 17: Jensen's Inequality on Cubic FCR

For convex function $FCR(V_s) = 0.000706 \cdot V_s^3$:

$$E[FCR(V_s)] \geq FCR(E[V_s])$$

**Implication:** If LP assigns a single segment-averaged SOG, the implied SWS at individual nodes (where weather differs from the average) will vary. The average fuel of these varying SWS values exceeds the fuel at the average SWS. Segment averaging systematically underestimates fuel.

---

## Source Files

- `pipeline/shared/physics.py` — implementation of Eqs 1–10
- `pipeline/static_det/optimize.py` — LP formulation (Eqs 11–13)
- `pipeline/dynamic_det/optimize.py` — DP formulation (Eqs 14–15)
- `pipeline/dynamic_rh/optimize.py` — RH decision rule (Eq 16)
- `/research-paper` skill — coefficient tables, ship parameters
- `/lp-optimizer` skill — LP architecture details
- `/dp-optimizer` skill — DP architecture details

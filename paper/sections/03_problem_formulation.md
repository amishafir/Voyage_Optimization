# 3. Problem Formulation

This section defines the ship, the route, the physics model linking engine speed to fuel consumption under environmental conditions, and the SOG-targeting decision framework that underpins all three optimization approaches.

## 3.1 Vessel

The reference vessel is a medium-size oil products tanker with the parameters listed in [TABLE: ship parameters]. The still water speed (SWS) range of 11–13 kn reflects the operational envelope under the EEXI engine power limitation. All three optimization approaches select speeds from this range.

[TABLE: ship parameters]

## 3.2 Routes

Two routes are used in this study. Experiment B covers a 1,678 nm segment of the Persian Gulf to Strait of Malacca corridor under mild weather conditions, while Experiment D crosses the North Atlantic storm track from St. John's, Newfoundland to Liverpool under harsh winter conditions. Both routes are interpolated from their original waypoints to produce evenly spaced nodes at 1 nm (Experiment B) and 5 nm (Experiment D) intervals, yielding 138 and 389 computational nodes respectively. The LP formulation aggregates these nodes into 6 and 10 segments, while the DP and RH approaches operate at full node resolution. [TABLE: route summary] summarizes the route characteristics. [FIG: route maps] shows the two routes.

## 3.3 Speed Correction Model

The relationship between the engine's still water speed $V_s$ and the achieved speed over ground $V_g$ is governed by an eight-step speed correction model adapted from Yang et al. (2020) [CITE: Yang 2020]. The model accounts for three environmental resistance sources — wind, waves, and ocean currents — through empirical coefficient lookups and vector synthesis.

**Step 1: Froude number.** The Froude number characterizes the speed-to-length ratio of the vessel:

$$F_n = \frac{V_s}{\sqrt{g \cdot L}} \tag{1}$$

where $V_s$ is SWS converted to m/s (1 kn = 0.5144 m/s), $g = 9.81$ m/s², and $L = 200$ m is the ship length.

**Step 2: Weather direction angle.** The relative angle $\theta$ between the wind direction and the ship heading determines the directional exposure:

$$\theta = |\phi_{wind} - \alpha_{heading}| \tag{2}$$

normalized to $[0°, 180°]$, where $0°$ represents head winds and $180°$ following winds.

**Step 3: Direction reduction coefficient.** The coefficient $C_\beta$ captures how the angle of wind encounter modulates resistance. It is computed as a piecewise function of $\theta$ and Beaufort number $BN$:

$$C_\beta = \begin{cases}
2.0 & 0° \leq \theta \leq 30° \\
1.7 - 0.03(BN - 4)^2 & 30° < \theta \leq 60° \\
0.9 - 0.06(BN - 6)^2 & 60° < \theta \leq 150° \\
0.4 - 0.03(BN - 8)^2 & 150° < \theta \leq 180°
\end{cases} \tag{3}$$

with a minimum value of 0.1. Head winds ($\theta \leq 30°$) produce the largest resistance; following winds produce the least.

**Step 4: Speed reduction coefficient.** The coefficient $C_U$ depends on Froude number and block coefficient $C_b = 0.75$:

$$C_U = f(F_n, C_b) \tag{4}$$

obtained from a piecewise quadratic lookup (Table 3 of the reference paper). For $C_b \in (0.70, 0.75]$ under normal loading: $C_U = 2.4 - 10.6 F_n - 9.5 F_n^2$.

**Step 5: Ship form coefficient.** The coefficient $C_{Form}$ relates sea state severity to hull resistance as a function of Beaufort number and displacement volume $\nabla$:

$$C_{Form} = 0.5 \cdot BN + \frac{BN^{6.5}}{22 \cdot \nabla^{2/3}} \tag{5}$$

where $\nabla = \Delta / \rho_{sw}$ is the displacement volume in m³ ($\Delta = 50{,}000$ tonnes, $\rho_{sw} = 1025$ kg/m³).

**Step 6: Speed loss.** The combined speed loss percentage is:

$$\frac{\Delta V}{V_s} \times 100\% = C_\beta \cdot C_U \cdot C_{Form} \tag{6}$$

clamped to $[0, 50]\%$.

**Step 7: Weather-corrected speed.** The speed through water after accounting for wind and wave resistance is:

$$V_w = V_s \cdot \left(1 - \frac{\Delta V / V_s}{100}\right) \tag{7}$$

with a minimum of 1.0 kn.

**Step 8: Speed over ground via vector synthesis.** The final SOG incorporates ocean current effects through two-dimensional vector addition:

$$V_{g,x} = V_w \cdot \sin(\alpha) + V_c \cdot \sin(\gamma) \tag{8a}$$
$$V_{g,y} = V_w \cdot \cos(\alpha) + V_c \cdot \cos(\gamma) \tag{8b}$$
$$V_g = \sqrt{V_{g,x}^2 + V_{g,y}^2} \tag{8c}$$

where $\alpha$ is the ship heading, $\gamma$ is the current direction (both in radians from north), and $V_c$ is the ocean current velocity. An additional 3.5% reduction is applied when $BN \geq 5$ to account for involuntary speed loss in higher sea states.

The complete chain — Eqs. (1) through (8) — maps any combination of SWS $V_s$ and environmental conditions $(BN, \theta, H_w, V_c, \gamma)$ to a unique SOG $V_g$. This mapping is monotonically increasing in $V_s$: higher engine speed always yields higher ground speed, though the relationship is nonlinear and weather-dependent.

## 3.4 Beaufort Number Calculation

The Beaufort number is not obtained from the weather API but is calculated from the 10-metre wind speed $V_w$ (km/h) using the WMO-standard threshold scale:

$$BN = \max\{n \in \{0, 1, \ldots, 12\} : V_w \geq V_{threshold}(n)\} \tag{9}$$

with thresholds at 0, 1, 6, 12, 20, 29, 39, 50, 62, 75, 89, 103, 117 km/h for BN 0–12.

## 3.5 Fuel Consumption Rate

The fuel consumption rate follows the cubic relationship standard in maritime engineering [CITE: Psaraftis 2013]:

$$FCR = 0.000706 \cdot V_s^3 \tag{10}$$

where $FCR$ is in mt/h and $V_s$ is in knots. This function is strictly convex, a property central to the Jensen's inequality analysis in Section 7.1. The coefficient 0.000706 is calibrated for the reference vessel class; the cubic exponent is consistent with the empirical range of 2.7–3.3 reported across cargo vessel types [CITE: Psaraftis 2023; Taskar 2020].

## 3.6 Segment Fuel and Total Voyage Fuel

The fuel consumed on leg $i$ is the product of FCR and transit time:

$$F_i = FCR(V_{s,i}) \cdot \frac{d_i}{V_{g,i}} \tag{11}$$

where $d_i$ is the leg distance in nm and $V_{g,i}$ is the achieved SOG in knots. The total voyage fuel is:

$$F_{total} = \sum_{i=1}^{N} F_i \tag{12}$$

where $N$ is the number of legs (137 for Experiment B, 388 for Experiment D).

## 3.7 The SOG-Targeting Decision Framework

The decision variable in all three optimization approaches is $V_{g,i}$ — the target SOG for each segment or leg — not the engine speed $V_{s,i}$. This reflects operational practice: ships must meet an estimated time of arrival (ETA), which constrains the average ground speed over the voyage. The ETA constraint requires:

$$\sum_{i=1}^{N} \frac{d_i}{V_{g,i}} \leq T \tag{13}$$

where $T$ is the required voyage time (140 h for Experiment B, 163 h for Experiment D).

Given a target SOG $V_{g,i}$ and the environmental conditions at leg $i$, the required SWS is obtained by inverting the speed correction model (Eqs. 1–8) via binary search. The optimizer selects $V_{g,i}$; the physics model determines $V_{s,i}$; and the FCR is evaluated at $V_{s,i}$ via Eq. (10). This is the SOG-targeting paradigm: the ship adjusts its engine output to maintain a target ground speed under prevailing conditions.

The critical consequence is that even when the optimizer assigns a constant SOG across a segment (as LP does), the required SWS varies from node to node within that segment because weather conditions are not spatially uniform. Since FCR is cubic in SWS, the average fuel consumption under varying SWS exceeds the fuel consumption at the average SWS — this is Jensen's inequality on the convex FCR function. The magnitude of this effect, and its implications for the relative performance of LP, DP, and RH, are quantified in Sections 6 and 7.

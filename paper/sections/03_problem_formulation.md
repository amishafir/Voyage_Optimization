# 3. Problem Formulation

This section defines the ship, the route, the physics model linking engine speed to fuel consumption under environmental conditions, and the SOG-targeting decision framework that underpins all three optimization approaches.

## 3.1 Vessel

The reference vessel is a medium-size oil products tanker with the parameters listed in [TABLE: ship parameters]. The still water speed (SWS) range of 11–13 kn reflects the operational envelope under the EEXI engine power limitation. All three optimization approaches select speeds from this range.

[TABLE: ship parameters]

## 3.2 Routes

Two routes are used in this study. Experiment B covers a 1,678 nm segment of the Persian Gulf to Strait of Malacca corridor under mild weather conditions, while Experiment D crosses the North Atlantic storm track from St. John's, Newfoundland to Liverpool under harsh winter conditions. Both routes are interpolated from their original waypoints to produce evenly spaced nodes at 1 nm (Experiment B) and 5 nm (Experiment D) intervals, yielding 138 and 389 computational nodes respectively. The LP formulation aggregates these nodes into 6 and 10 segments, while the DP and RH approaches operate at full node resolution. [TABLE: route summary] summarizes the route characteristics. [FIG: route maps] shows the two routes.

## 3.3 Speed Correction Model

The relationship between the engine's still water speed $V_s$ and the achieved speed over ground $V_g$ is governed by the eight-step speed correction model of [CITE: Yang2020]. The model computes a percentage speed loss from three environmental resistance sources — wind, waves, and ocean currents — through empirical coefficient lookups that depend on the Froude number, Beaufort number, relative wind angle, block coefficient, and displacement volume. The weather-corrected speed through water is then combined with ocean current velocity via two-dimensional vector synthesis to yield the final SOG. The complete model maps any combination of SWS $V_s$ and environmental conditions $(BN, \theta, H_w, V_c, \gamma)$ to a unique SOG $V_g$. This mapping is monotonically increasing in $V_s$: higher engine speed always yields higher ground speed, though the relationship is nonlinear and weather-dependent. A detailed derivation with all coefficient tables is provided in [CITE: Yang2020].

The Beaufort number $BN$ is not obtained from the weather API but is calculated from the 10-metre wind speed using the WMO-standard threshold scale (BN 0–12).

## 3.4 Fuel Consumption Rate

The fuel consumption rate follows the cubic relationship $FCR(V_s)$ (mt/h) standard in maritime engineering, calibrated for the reference vessel class with a coefficient consistent with the empirical exponent range of 2.7–3.3 reported across cargo vessel types [CITE: Psaraftis2013, Psaraftis2023, Taskar2020]. This function is strictly convex — a property central to the Jensen's inequality analysis in Section 7.1.

## 3.5 Segment Fuel and Total Voyage Fuel

The fuel consumed on leg $i$ is the product of FCR and transit time:

$$F_i = FCR(V_{s,i}) \cdot \frac{d_i}{V_{g,i}} \tag{1}$$

where $d_i$ is the leg distance in nm and $V_{g,i}$ is the achieved SOG in knots. The total voyage fuel is:

$$F_{total} = \sum_{i=1}^{N} F_i \tag{2}$$

where $N$ is the number of legs (137 for Experiment B, 388 for Experiment D).

## 3.6 The SOG-Targeting Decision Framework

The decision variable in all three optimization approaches is $V_{g,i}$ — the target SOG for each segment or leg — not the engine speed $V_{s,i}$. This reflects operational practice: ships must meet an estimated time of arrival (ETA), which constrains the average ground speed over the voyage. The ETA constraint requires:

$$\sum_{i=1}^{N} \frac{d_i}{V_{g,i}} \leq T \tag{3}$$

where $T$ is the required voyage time (140 h for Experiment B, 163 h for Experiment D).

Given a target SOG $V_{g,i}$ and the environmental conditions at leg $i$, the required SWS is obtained by inverting the speed correction model via binary search. The optimizer selects $V_{g,i}$; the physics model determines $V_{s,i}$; and the FCR is evaluated at $V_{s,i}$. This is the SOG-targeting paradigm: the ship adjusts its engine output to maintain a target ground speed under prevailing conditions.

The critical consequence is that even when the optimizer assigns a constant SOG across a segment (as LP does), the required SWS varies from node to node within that segment because weather conditions are not spatially uniform. Since FCR is cubic in SWS, the average fuel consumption under varying SWS exceeds the fuel consumption at the average SWS — this is Jensen's inequality on the convex FCR function:

$$E[FCR(V_s)] \geq FCR(E[V_s]) \tag{4}$$

The magnitude of this effect, and its implications for the relative performance of LP, DP, and RH, are quantified in Sections 6 and 7.

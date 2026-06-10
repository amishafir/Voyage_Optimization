<!--
DRAFT — Problem Formulation. Fully unblocked: ship spec + physics chain + cubic FCR.
Equations 1–10 from reference/paper-equations/SKILL.md; coefficient tables (C1–C6, form/speed-
reduction) from the underlying physics-model paper → [CITE: Yang et al. 2020]. Establishes the
cubic FCR premise that the Mechanism section (drafts/05) and the SR/Luo methods (drafts/04) use.
Voice: TR-C — present tense for the model (general truths), passive. "This study".
-->

# 3. Problem formulation

## 3.1 Vessel and voyage

The vessel modelled in this study is a representative oil products tanker with the principal particulars in Table&nbsp;X.
A voyage is a fixed route of total length $L$ to be completed within a required arrival time $T$
(the ETA). The route is partitioned into legs $i = 1, \ldots, N$ of length $d_i$, with weather
specified per leg and time. The control problem is to choose a speed profile that minimises total
fuel while arriving within $T$.

**Table 1. Principal particulars of the representative oil products tanker; resistance model and
coefficient tables from [CITE: Yang et al. 2020].**

| Parameter | Symbol | Value |
|---|---|---|
| Length between perpendiculars | $L_{pp}$ | 200 m |
| Beam | $B$ | 32 m |
| Draft | — | 12 m |
| Displacement | $\Delta$ | 50,000 t |
| Block coefficient | $C_b$ | 0.75 |
| Installed power | — | 10,000 kW |
| Still-water speed range | $V_s$ | 11–13 kn |

Two routes are studied, chosen to contrast weather regimes: Route 1 (Persian Gulf → Strait of
Malacca, $L = 3{,}393$ nm, $T = 280$ h), in mild and relatively uniform conditions, and Route 2
(St. John's → Liverpool, North Atlantic, $L = 1{,}955$ nm, $T = 168$ h), in harsher and more
variable conditions. Full route and weather statistics are given in Section&nbsp;5.

## 3.2 Speed over ground

The vessel's still-water speed (SWS), $V_s$, is the speed it would make in calm water at a given
power setting. The speed actually achieved over the ground (SOG), $V_g$, is $V_s$ modified by the
environment: wind and waves reduce it, and the along-track component of the current adds to or
subtracts from it. This study uses the resistance-decomposition model of [CITE: Yang et al. 2020].

The wind- and wave-induced speed losses depend on the Beaufort number $BN$ (computed from the
10 m wind speed; see Section&nbsp;5), the Froude number [EQ: Froude number], and a set of
direction- and form-dependent coefficients tabulated by [CITE: Yang et al. 2020]
[EQ: speed reduction coefficient]–[EQ: ship form coefficient]. The wind speed loss is a
fifth-order function of the wind angle relative to heading [EQ: wind resistance], and the wave
added-resistance loss scales with significant wave height $H_w$ and the beam-to-length ratio
[EQ: wave added resistance]. The current contributes its along-track projection,
$V_{c,\parallel} = V_c \cos\theta_c$ [EQ: current along-track].

Combining these terms gives the speed over ground [EQ: SOG composite]:

$$V_g \;=\; V_s - \Delta V_\text{wind} - \Delta V_\text{wave} + V_{c,\parallel},
\qquad V_g \ge 0.$$

Two properties of this relation are used later. First, for fixed weather, $V_g$ increases
monotonically with $V_s$, so the relation is invertible: a target SOG implies a unique required
SWS, $V_s = g^{-1}(V_g; w)$, obtained here by binary search [METHODS→§4]. Second, that required
SWS rises as conditions worsen — holding a target SOG through adverse weather demands more SWS.
Both properties underlie the convexity mechanism of Section&nbsp;5.

## 3.3 Fuel consumption

Fuel consumption rate is a cubic function of still-water speed [CITE: Yang et al. 2020] [EQ: FCR]:

$$\text{FCR}(V_s) \;=\; 0.000706\, V_s^{3} \quad [\text{mt/h},\; V_s \text{ in kn}].$$

This cubic form is the central structural property of the problem: **FCR is strictly convex in
$V_s$.** Crucially, fuel depends on SWS — the speed the engine must produce — not on SOG. When a
target SOG is held through varying weather, the required SWS varies, and the convex FCR penalises
that variation (Section&nbsp;5).

The fuel for leg $i$ is the rate times the leg's transit time [EQ: segment fuel],

$$F_i \;=\; \text{FCR}(V_{s,i})\, \frac{d_i}{V_{g,i}},$$

and total voyage fuel is the sum over legs [EQ: total voyage fuel],
$F_\text{total} = \sum_{i=1}^{N} F_i$.

## 3.4 Decision variable and objective

This study optimises **SOG**, not SWS — a choice termed SOG-targeting. A speed plan specifies a
target SOG for each leg (or, for the baseline, each block); the SWS required to realise it follows
from the inverse SOG relation under the prevailing weather. The optimisation problem is

$$\min_{\{V_{g,i}\}} \; \sum_{i=1}^{N} \text{FCR}\big(g^{-1}(V_{g,i}; w_{i})\big)\, \frac{d_i}{V_{g,i}}
\quad\text{subject to}\quad \sum_{i=1}^{N} \frac{d_i}{V_{g,i}} \le T,
\;\; V_{s,i} \in [11, 13]\ \text{kn}.$$

The arrival constraint is hard; the still-water speed is bounded by the engine envelope. The two
formulations compared in this study (Section&nbsp;4) differ only in the granularity at which the
target SOG may be chosen — freely per leg, or once per time block.

<!--
COVERAGE: ship spec ✓ | routes (brief, full → §5) ✓ | SOG chain Eqs 1–7 ✓ | cubic FCR Eq 8 +
convexity premise ✓ | segment/total fuel Eqs 9–10 ✓ | SOG-targeting + objective ✓.
Sets up Mechanism (§5): monotone-invertible SOG→SWS + convex FCR on SWS.
RESOLVED: vessel = representative oil products tanker (Yang's case-study type), but Table 1
particulars are the thesis's own (200 m / 10,000 kW / 11–13 kn) — NOT Yang's Table 6 ship
(233 m / 15,260 kW / 8–15.7 kn). Yang (2020) cited for the resistance model + coefficient tables
(their Tables 3–4) and the cubic FCR form only, not for the particulars. Coefficient tables
(C1–C6, form, speed-reduction) → reproduce in an appendix or cite Yang.
-->

# 2. Literature Review

<!-- ~2,900 words -->

## 2.1 Ship Speed Optimization Methods

The reduction of greenhouse gas (GHG) emissions from international shipping has become a regulatory imperative.
The 2023 IMO GHG Strategy commits to "net-zero GHG emissions by or around, i.e. close to, 2050" [CITE: IMO 2023],
while the Carbon Intensity Indicator (CII), in force since January 2023 [CITE: Tadros 2023], subjects each vessel
to annual efficiency ratings that directly depend on voyage-level fuel decisions. Speed optimization — adjusting
engine power per voyage leg to minimize fuel consumption under arrival-time constraints — is widely recognized as
the highest-impact near-term operational measure [CITE: Bouman 2017], with reported reduction potentials of 1–60%
depending on vessel type and baseline speed.

In the operations research (OR) literature, ship speed optimization is formulated as a deterministic shortest-path
or resource-constrained optimization problem. When the voyage route is fixed and weather conditions are treated as
static per segment, the problem reduces to selecting a speed $V_{s,i}$ for each segment $i$ that minimizes total
fuel subject to an arrival-time constraint. This structure admits two canonical solution paradigms: linear
programming (LP) on continuous speed variables, and dynamic programming (DP) on a discretized time-distance graph.
LP formulations are polynomial in the number of segments and speed discretization points; DP formulations are
pseudo-polynomial in the time discretization, but both yield provably optimal solutions for their respective
problem representations.

[CITE: Psaraftis 2013] surveyed speed optimization models and classified them along 13 taxonomy parameters, establishing
that the cubic fuel consumption function ($FCR \propto V_s^3$; [EQ: 8]) is standard for tankers and bulk carriers.
The survey documented the scarcity of dynamic speed models and found no papers employing rolling horizon or
model predictive control for speed optimization. [CITE: Ronen 2011] formalized the economic rationale: a 20%
speed reduction yields approximately 50% bunker savings, following directly from the cubic relationship
($(0.8)^3 = 0.512$). [CITE: Wang 2012] calibrated the speed-power exponent from operational data on a global
liner network, finding values of 2.709–3.314 across five voyage legs — confirming that the cubic approximation is
reasonable but leg-dependent. The outer-approximation algorithm developed therein achieved optimality gaps below
0.1% in under 0.2 seconds for an 87-leg network.

On the LP side, [CITE: Bektas 2011] introduced the Pollution-Routing Problem, where fuel consumption per unit
time is cubic in speed and the resulting objective function is convex. Speed is a continuous decision variable per
arc, solved via mixed-integer linear programming. [CITE: Norstad 2011] extended this to tramp ship routing and
scheduling, introducing a recursive smoothing algorithm (RSA) that exploits convexity to equalize speeds across
legs. The RSA's optimality was formally proven by [CITE: Hvattum 2013], who showed that constant speed over
unconstrained port sequences is optimal when the fuel cost function is convex and non-decreasing. This result
is a direct consequence of Jensen's inequality ([EQ: 17]), though the original proof uses a constructive
equalization argument rather than invoking the inequality explicitly. [CITE: Fagerholt 2010] demonstrated the computational advantage
of the alternative DP formulation: a directed acyclic graph (DAG) with discretized arrival times solves the same
problem in approximately 2 ms versus 430 ms for nonlinear programming, with only 0.04% optimality gap.
Per-leg speed optimization achieved 24.3% fuel savings compared to 19.4% from uniform speed reduction — the
additional 5 percentage points arising precisely from the convexity-driven speed equalization.

On the DP side, [CITE: Zaccone 2018] developed a three-dimensional dynamic programming optimizer on a discretized
space-time grid, using NOAA WaveWatch III forecast maps as input. The ship model decomposes resistance into
still-water, wave-added, and wind components (analogous to [EQ: 4]–[EQ: 5]) and evaluates fuel via a full
propulsion chain including propeller diagrams and engine maps. The resulting Pareto frontier of fuel versus
arrival time allows operators to quantify the fuel cost of each hour of schedule deviation. However, the
optimization was performed once at departure using a single 162-hour forecast and was never re-planned — a
limitation the authors explicitly acknowledged: "this advantage over heuristic global search algorithms is
partially limited by the fact that input data is affected by significant uncertainties."

The most comprehensive taxonomy of weather routing methods is provided by [CITE: Zis 2020], who surveyed 280
journal papers and classified 40 in detail across 10 dimensions. The survey identified four dominant solution
families — modified isochrone, dynamic programming, pathfinding/genetic algorithms, and AI/ML — but LP did not
appear as a solution approach in any of the taxonomized papers. Rolling horizon was identified only as a future
research direction. The survey also called for standardized benchmarking, arguing that the weather routing community would
benefit from "a standardization of the reporting of savings through weather routing, to facilitate
comparisons between methodologies."

Despite this extensive body of work, a systematic gap persists: no study has compared LP and DP optimization on
the same route, with the same physics model, under the same weather data. Each paper evaluates a single method
against a fixed-speed baseline. Furthermore, none of the surveyed studies examines how the choice of simulation
model — whether fuel is evaluated at the planned SWS (fixed-SWS) or at the SWS required to achieve the planned
SOG under actual weather (SOG-targeting) — affects the relative ranking of optimization approaches. The present
study addresses both gaps.

## 2.2 Fuel Consumption Convexity and Jensen's Inequality

The mathematical foundation of ship speed optimization rests on the relationship between speed and fuel
consumption. From first principles, the power required to propel a displacement vessel at speed $V_s$ through
water is $P = \frac{1}{2} \rho C_T V_s^3 S$, where $\rho$ is water density, $C_T$ is the total resistance
coefficient, and $S$ is wetted surface area [CITE: Psaraftis 2023]. For a fixed-pitch propeller operating at
constant specific fuel oil consumption (SFOC), fuel consumption rate is therefore approximately cubic in speed:
$FCR = \alpha V_s^3$ ([EQ: 8]). This cubic relationship — and its convexity — is the physical mechanism
underlying the central contribution of the present study.

The resistance itself is not a single term. [CITE: Holtrop 1982] introduced a seven-component decomposition —
frictional (with form factor), appendages, wave-making, bulbous bow pressure, transom pressure, and
model-ship correlation — calibrated on over 200 hull shapes from the MARIN database. A subsequent re-analysis
using 334 model tests [CITE: Holtrop 1984] refined the coefficients and introduced explicit Froude number regime
boundaries, confirming the method's accuracy for low-speed displacement vessels ($F_n < 0.4$) such as the tanker
considered in the present study ($F_n \approx 0.13$–$0.15$). These calm-water resistance methods provide the
baseline upon which environmental corrections are applied.

Whether the cubic approximation holds under real operating conditions has been debated. [CITE: Psaraftis 2023]
reviewed recent regression analyses of operational data that report speed-power exponents well below 3 — in some
cases below 2 or even below 1 — and identified these as statistical artifacts: confounding variables such as
draft, hull fouling, and weather contaminate the regressions, biasing the exponent downward. When confounders
are controlled, the exponent cannot be less than 3 based on basic hydrodynamic principles. [CITE: Wang 2012]
calibrated exponents from operational data on five voyage legs, finding $b = 2.709$–$3.314$, consistent with
the cubic approximation being reasonable but route-dependent. [CITE: Taskar 2020] used detailed ship performance
modeling across six vessel types and found speed exponents ranging from 3.3 to 4.2, with the cubic assumption
causing up to 15% error in estimated fuel savings at 30% speed reduction. The conclusion across these studies is
that the exponent is at least 3 and often higher — the cubic model is conservative.

The convexity of $FCR(V_s)$ has a direct consequence through Jensen's inequality ([EQ: 17]): for any convex
function $f$, the expectation $E[f(X)] \geq f(E[X])$. Applied to fuel consumption, this means that if a ship's
actual SWS varies around a mean (as it must when targeting a fixed SOG through spatially varying weather), the
realized fuel consumption exceeds the fuel computed at the mean SWS. This inequality is well known in
optimization theory and has been exploited constructively: [CITE: Norstad 2011] developed a recursive smoothing
algorithm that equalizes speeds across legs, and [CITE: Hvattum 2013] proved its optimality for convex
non-decreasing cost functions. [CITE: Fagerholt 2010] demonstrated that per-leg speed optimization achieves 5 percentage points more
savings than uniform speed reduction, the difference arising from convexity-driven equalization.

However, the same convexity that makes speed equalization optimal for planning creates a systematic bias in
plan evaluation. An LP optimizer that assigns a single speed per segment implicitly assumes constant SWS across
all nodes within that segment. If the segment is simulated under SOG-targeting — where the ship adjusts SWS
at each node to achieve the planned SOG given local weather — the resulting SWS varies, and Jensen's inequality
guarantees the actual fuel exceeds the LP estimate. This connection between FCR convexity and the plan-simulation
gap under SOG-targeting has not been identified in the prior literature. [CITE: Tezdogan 2015] showed that added
wave resistance can reach 15–30% of calm-water resistance, confirming that weather perturbations are large enough
to generate meaningful SWS variation under SOG-targeting; [CITE: Taskar 2020] found that fuel savings from speed
reduction are "highly weather dependent" and that the extra fuel from rough weather is "nearly independent of
ship speed." Yet neither study connects these findings to the averaging bias inherent in segment-level
optimization.

## 2.3 SOG-Targeting versus Fixed-SWS Simulation

A fundamental distinction in ship speed optimization is between the speed the engine produces through the water
(still water speed, SWS, $V_s$) and the speed at which the vessel advances over the seabed (speed over ground,
SOG, $V_g$). The two differ by the cumulative effect of wind resistance, wave-added resistance, and ocean
current projection ([EQ: 4]–[EQ: 7]). Despite this, the majority of the speed optimization literature treats
"ship speed" as a single variable, implicitly equating SWS and SOG.

[CITE: Yang 2020] was the first to identify this conflation as a systematic error. The paper showed that ignoring
ocean currents produces an average SOG estimation error of 4.75% across 12 segments, reduced to 1.36% when
currents are incorporated. More fundamentally, it established the correct computational chain: the optimizer
chooses SWS, fuel is consumed at a rate determined by SWS ([EQ: 8]), but sailing time depends on SOG — which is
SWS corrected for wind, waves, and currents. This distinction is quantitatively material: on the Persian Gulf to
Strait of Malacca route, SWS and SOG differed by 0.5–1.5 kn per segment. However, [CITE: Yang 2020] treated
weather as static per segment and computed fuel from a single optimization pass; no simulation of plan execution
under different conditions was performed.

The question of how an optimized speed plan should be evaluated — what happens when the planned speeds encounter
actual weather — has received limited attention. Two paradigms exist. Under *fixed-SWS simulation*, the ship
maintains the planned engine setting regardless of weather; the realized SOG (and hence arrival time) becomes
a random variable. Under *SOG-targeting*, the ship adjusts its engine setting at each waypoint to achieve the
planned SOG given local weather conditions; the arrival time is preserved but the realized SWS (and hence fuel)
varies. The second paradigm reflects operational practice. [CITE: Jia 2017] demonstrated this empirically using
AIS data from 5,066 VLCC voyages: when berth delays at destination ports are known in advance, converting
excess port waiting time into slower sailing speeds yields 7–19% fuel savings per voyage (77–226 tonnes of HFO).
The "Virtual Arrival" policy studied therein is precisely SOG-targeting at the voyage level — the ship adjusts
speed to arrive just in time rather than steaming at full power and waiting at anchor. The average VLCC port
call lasts 4.0 days against 22.7 days of sailing (Table 1, p. 54), meaning approximately 15% of voyage time is
unproductive waiting that could fund slower transit. Under current charterparty "utmost dispatch" clauses,
however, most ships sail at maximum speed regardless of berth availability [CITE: Jia 2017], creating a
"sail-fast-then-wait" pattern that wastes fuel and inflates emissions.

The implications of SOG-targeting for fuel estimation follow directly from the convexity established in
Section 2.2. If the optimizer plans a constant SOG across a segment but actual weather varies within it, the SWS
required to maintain that SOG varies node by node. By Jensen's inequality on the cubic FCR ([EQ: 17]), the
average fuel of these varying SWS values exceeds the fuel at the average SWS. This bias is inherent to any
optimizer that assigns a single speed per segment — notably LP. A node-level DP optimizer, which assigns speed
at each waypoint given local weather, does not suffer this averaging bias.

[CITE: Huotari 2021] implicitly operated under SOG-targeting through a fixed-schedule constraint: the ship must
arrive on time, so it must achieve a target average SOG. The authors found that per-node speed optimization
saved 1.1% fuel on average versus fixed speed, rising to 3.5% when weather variation was significant. Yet the
paper never named the SOG-targeting paradigm or analyzed its implications for method comparison. Similarly, the
broader speed optimization literature — including [CITE: Psaraftis 2013], [CITE: Norstad 2011], [CITE: Bektas
2011], and [CITE: Ronen 2011] — treats speed as SWS throughout, never examining how simulating plans under
SOG-targeting might change the relative ranking of optimization methods. The present study demonstrates that it
does: LP and DP produce nearly identical planned fuel, but under SOG-targeting simulation, the LP plan incurs
higher realized fuel than the DP plan, reversing the conventional assessment.

## 2.4 Forecast Quality and Its Effect on Speed Optimization

The accuracy of numerical weather prediction (NWP) models degrades with forecast lead time, a consequence
of the chaotic dynamics first characterized by [CITE: Lorenz 1969], who demonstrated that atmospheric errors
double approximately every five days and that "the range of predictability would then be about two weeks."
Modern NWP systems such as NOAA GFS and ECMWF IFS operate within this theoretical bound, mitigating error
growth through frequent re-initialization: GFS produces a new forecast every 6 hours, ECMWF every 12 hours.
The relevance to ship speed optimization is direct: a voyage of 280 hours (approximately 12 days) spans nearly
the entire skillful forecast window, meaning weather conditions predicted at departure for the final voyage
segments carry substantially more error than those for the initial segments.

Empirical characterization of this degradation has been performed at the NWP product level. [CITE: Stopa 2014]
validated ECMWF ERA-Interim and NCEP CFSR reanalysis products against 25 deep-water buoys and seven satellite
altimeter missions over 31 years, reporting wave height RMSEs of approximately 0.5 m and wind speed RMSEs of
1.3–1.7 m/s. ERA-Interim was found to be more temporally homogeneous, supporting the assumption that each
fresh NWP cycle is drawn from a consistent-quality source. More recently, [CITE: Marjanovic 2025] quantified
GFS forecast degradation specifically for maritime applications: wind speed RMSE grows from 0.5 m/s at 24 hours
to 4.0 m/s at 168 hours (approximately 0.5 m/s per day), and significant wave height RMSE degrades from 0.2 to
0.9 m over the same interval. Notably, the degradation is non-monotonic: a skill recovery at 96–120 hours
corresponds to transitions between medium- and extended-range NWP model regimes.

Whether this degradation materially affects fuel estimation has been addressed only partially.
[CITE: Vettor 2022] demonstrated that ensemble forecast spread in wave parameters translates into a
quantifiable uncertainty band on fuel consumption, with observed fuel falling within the 90% prediction
interval. However, speed was held constant in that analysis, so the cubic FCR nonlinearity was never exercised
asymmetrically — the Jensen's inequality mechanism ([EQ: 17]) remained invisible. [CITE: Luo 2023] took a
critical step further by comparing deterministic versus ensemble (NOAA GEFS, 21 members) forecasts as inputs to
a MILP speed optimizer, finding that ensemble-optimized speed plans achieve approximately 1% lower realized fuel.
The paper explicitly identified the static forecast assumption as its key limitation: "the vessel sailing speed
optimization based on the static sea and weather conditions may not generate the optimal speeds throughout the
voyage. In the future, we can implement the rolling-horizon approach."

The chain from forecast error to fuel estimation error thus remains incomplete. [CITE: Marjanovic 2025]
characterizes the error growth; [CITE: Vettor 2022] shows it propagates to fuel uncertainty; [CITE: Luo 2023]
shows that better forecasts yield better plans. But no study has measured how forecast error at a given lead time
translates to fuel estimation bias in a specific optimizer — let alone whether LP and DP respond differently to
the same forecast degradation. The present study closes this chain by propagating empirical forecast error curves
through both LP and DP optimizers and measuring the resulting fuel estimation divergence as a function of forecast
horizon.

## 2.5 Rolling Horizon and Re-planning in Maritime Speed Optimization

The theoretical foundation for rolling horizon (RH) decision making was established by [CITE: Sethi 1991], who
proved that when forecasting the future is costly or unreliable, an optimal planning horizon of finite, bounded
length always exists. The key insight is that "the usefulness of rolling horizon methods is, to a great extent,
implied by the fact that forecasting the future is a costly activity." Under stationarity and discounting, the
optimal horizon and control laws are time-invariant (Theorem 6), providing theoretical justification for using a
fixed re-planning interval rather than a state-dependent variable one.

In the maritime domain, RH has been applied primarily to schedule adherence rather than fuel minimization.
[CITE: Zheng 2023] developed a decentralized model predictive control (DMPC) framework for liner shipping
that re-optimizes speed every hour to compensate for uncertain port handling times. The controller reduced
schedule deviations by 91.8% but at the cost of 27.7% higher fuel consumption — reflecting the
schedule-focused objective. The uncertainty source was operational (port delays), not meteorological, and
re-planning was triggered at every time step regardless of forecast availability.

For speed optimization under weather uncertainty, the most relevant precedent is [CITE: Tzortzis 2021], who
decomposed the voyage time horizon into shorter sub-horizons and re-optimized speed using PSO at each boundary
with the most current forecast. The approach achieved approximately 2% fuel savings over static optimization and
was motivated by the observation that "meteorological forecasts are considered to be accurate for relatively
short time horizons (approximately two days)." However, the sub-horizon length was treated as a free tuning
parameter, not derived from any specific NWP refresh cycle. No comparison against LP or DP baselines was
performed, and forecast error propagation was not quantified.

The value of information (VOI) concept — how much fuel could be saved by obtaining a more accurate forecast —
provides a natural framework for evaluating RH strategies. [CITE: Sethi 1991] formalized VOI through the
augmented state $X_t = (x_t, h_t, \xi_{h_t})$, where the information state $\xi$ determines the quality of
available forecasts. In the maritime context, VOI manifests as the fuel gap between an optimizer using a stale
forecast and one using a fresh forecast. [CITE: Luo 2023] measured a 1% fuel improvement from ensemble versus
deterministic forecasts; the present study extends this by measuring the fuel improvement from periodic forecast
refresh (RH) versus a single departure-time forecast (static DP), and by linking the optimal re-planning
interval to the 6-hour GFS initialization cycle.

The gap in this literature is threefold. First, no maritime RH study connects the re-planning frequency to NWP
refresh cycles — the mechanism that resets forecast error growth. Second, no study compares RH against both LP
and DP on the same route and physics, making it impossible to assess whether RH's advantage is due to better
information or better temporal resolution. Third, the interaction between SOG-targeting simulation and RH has
not been examined: RH commits speeds for shorter windows (6 hours versus full voyage), which reduces the
within-window weather variation and thereby attenuates the Jensen's inequality bias identified in Section 2.3.
The present study addresses all three gaps.

## 2.6 Summary of Gaps

[TABLE: gap summary]

The literature reviewed above reveals a consistent pattern: each study addresses one dimension of the ship speed
optimization problem in isolation. LP methods are evaluated without DP alternatives on the same instance;
DP methods plan once without re-planning; forecast quality is characterized without measuring its impact on
fuel estimation; and simulation universally assumes fixed SWS, never SOG-targeting. Table [TABLE: gap summary]
synthesizes these gaps against the six contributions of the present study. The columns indicate, for each
reviewed paper, whether it addresses the corresponding dimension (check) or leaves it as an open gap (dash).
No existing paper covers more than two of the six dimensions simultaneously.

The present study is positioned at the intersection of these gaps. It employs the same physics model ([EQ: 1]–
[EQ: 7]), the same route, and the same weather data across all three optimization approaches (LP, DP, RH),
enabling the first controlled comparison. The SOG-targeting simulation paradigm, combined with the cubic FCR
convexity ([EQ: 8], [EQ: 17]), reveals a plan-simulation gap that has been invisible to the prior literature.
And the alignment of RH re-planning with NWP refresh cycles connects the forecast quality literature to
operational speed optimization in a manner that has been called for [CITE: Yang 2020] [CITE: Luo 2023] but
not previously implemented.


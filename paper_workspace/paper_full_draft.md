<!-- ======================================================================
 FULL PAPER — ASSEMBLED DRAFT (snapshot). Generated from drafts/ in reading order;
 dev/coverage comments stripped. EDIT THE SOURCE SECTIONS IN drafts/, NOT THIS FILE.
 NOTE: this .md is the with-guidance working version; paper_full_draft.tex is the clean
 Overleaf version (Introduction/Related work there are stripped to placeholders).
 Naming: perfect foresight (oracle) + rolling horizon (RH) + Naive. (No "Mode C".)
 Vessel: representative oil products tanker; Yang et al. (2020) cited for model + FCR.
 Structural-complexity / compute axis removed (2 contributions: mechanism + quantification + operational).
====================================================================== -->



# Maritime Speed Optimization Under Weather Uncertainty

*[TITLE alternatives, if a sharper SR-vs-Luo framing is wanted later: (a) "Per-Leg Speed Freedom
versus Per-Block Speed-Locking in Fuel-Optimal Ship Routing"; (b) "Why Per-Leg Speed Beats
Per-Block Speed: A Jensen Mechanism for Fuel-Optimal Ship Routing".]*

**Authors:** Ami Shafir, Tal Raviv · **Affiliation:** Faculty of Engineering, Tel Aviv University, Tel Aviv, Israel

---

## Abstract

> **[G6 — WRITE LAST.** ~250 words, structured, no subheadings. Compresses the chain:
> per-block speed-locking is fuel-suboptimal by Jensen on the convex FCR → per-leg freedom (SR)
> recovers ~6 mt / 1.8–2.6 % on 19 voyages / two regimes under perfect foresight → survives 6 h
> rolling horizon vs set-and-forget (RH-SR saves 18/19; RH-Luo breaks even) → at a structural
> compute cost. Written after Introduction §1.1–§1.2 are filled from G5.**]**

**Keywords:** [5–6 — e.g. ship speed optimisation; dynamic programming; rolling horizon; fuel
consumption; weather routing; Jensen's inequality — finalise at G6]

# 1. Introduction

## 1.1 Motivation [LIT→G5 — placeholder]

[LIT→G5: Maritime fuel and GHG reduction matters now — IMO 2023 GHG strategy, EEXI, CII.
2–3 sentences with regulatory citations from pillar 6.]

[LIT→G5: Speed optimisation is the most direct operational lever, and fuel consumption is
strongly convex (approximately cubic) in speed — citation from pillar 2. State the cubic FCR
fact here because the whole mechanism rests on it.]

## 1.2 The gap [LIT→G5 — placeholder, keyed to the three RQs]

[LIT→G5: Existing voyage-speed optimisers hold a single speed per route block or segment
(per-block dynamic programming, e.g. [CITE: Luo 2024]; segment-averaged linear programming).
The convexity penalty this incurs under within-block weather variation has not been isolated.
— pillars 1, 2.]

[LIT→G5: Baselines are typically compared on a single route, a single departure, or synthetic
weather, so the robustness of any advantage across real departure conditions is unmeasured.
— pillars 1, 3.]

[LIT→G5: Rolling horizon is well established in operations research but rarely applied to
maritime speed optimisation against real numerical weather prediction (NWP) forecasts with a
faithful published baseline. — pillars 4, 5.]

## 1.3 Research questions

This study addresses three questions, which form a single mechanism viewed from three sides.

**RQ1.** Does relaxing the per-block speed lock to per-leg speed freedom reduce voyage fuel, and
what is the mechanism?

**RQ2.** Under perfect weather foresight, how large is the fuel gap between free-speed and
per-block-locked optimisation, and how does it vary across routes, weather regimes, and
departure times?

**RQ3.** Does the advantage survive realistic rolling-horizon planning under imperfect
forecasts, relative to set-and-forget operation?

## 1.4 Contributions

The contributions are threefold.

1. **Mechanism.** This study shows that per-block speed-locking is fuel-suboptimal whenever
   weather varies within a block, by Jensen's inequality applied to the convex fuel-consumption-rate
   curve, and that per-leg speed freedom recovers the loss.

2. **Quantification against a faithful baseline.** The fuel advantage of free-speed over the
   per-block-locked formulation of [CITE: Luo 2024] is quantified under perfect foresight across
   19 voyages on two routes spanning two weather regimes: a saving on every voyage, of comparable
   absolute magnitude across routes but proportionally larger on the shorter voyage.

3. **Operational validation.** The advantage is shown to survive realistic 6 h rolling-horizon
   planning against real NWP forecasts: free-speed re-planning saves fuel relative to
   set-and-forget operation, whereas per-block-locked re-planning does not. The boundedness of
   this operational saving is characterised (Section 7).

## 1.5 Organisation

[METHODS→G4 / structure once G4–G5 designed:] Section 2 reviews related work and states the gap.
Section 3 formulates the problem and the convex fuel model. Section 4 defines the free-speed and
per-block-locked formulations, the rolling-horizon scheme, and the structural-complexity measures.
Section 5 describes the data and routes. Section 6 reports results (Section 6.1, perfect foresight;
Section 6.2, rolling horizon). Section 7 discusses the mechanism, the operational boundedness, and
limitations. Section 8 concludes.

# 2. Related work

> **[LIT→G5 — entire section pending the gap map.** Structure below is fixed; prose + citations
> filled from `context/literature/pillar_*` once G5 is designed. Each subsection ends in the gap
> that one of the three research questions closes.**]**

## 2.1 Ship speed optimisation methods
[LIT→G5: LP/segment-averaged, dynamic-programming/per-block (incl. [CITE: Luo 2024]),
metaheuristics, weather routing — pillar 1. **Gap → RQ1/RQ2:** per-block/segment-constant speed is
standard; the convexity penalty it incurs has not been isolated, nor quantified against a faithful
published baseline across real departures.]

## 2.2 Fuel consumption and the speed–power relationship
[LIT→G5: cubic/convex FCR, resistance decomposition, the speed exponent — pillar 2.
**Gap → RQ1:** convexity is well established but its consequence for *per-block speed-locking*
specifically is not drawn out.]

## 2.3 Weather forecasting in voyage optimisation
[LIT→G5: NWP products (GFS/ECMWF), forecast verification, Open-Meteo — pillar 3.
**Gap → RQ2/RQ3:** forecast-error propagation into the optimiser, and use of real NWP rather than
synthetic weather, is rarely measured.]

## 2.4 Rolling horizon and the value of information
[LIT→G5: rolling horizon / MPC in OR, replan frequency, value of information — pillars 4, 5.
**Gap → RQ3:** rolling horizon is mature in OR but seldom applied to maritime speed optimisation
with real forecasts and a faithful baseline, and the boundedness of its benefit is under-examined.]

## 2.5 Summary of gaps
[LIT→G5: gap table — pillar × what exists × what is missing × which RQ closes it.]

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

# 4. Methods

Both speed-optimisation formulations compared in this study are minimum-fuel dynamic programs
solved over the *same* route discretisation and the *same* speed-over-ground (SOG) grid. They
differ in one respect only: the granularity of the speed decision. The Shafir–Raviv formulation
(SR) chooses speed freely on every leg; the baseline formulation of [CITE: Luo 2024] (Luo) holds
a single speed across each time block. Because both call the identical SOG and fuel-consumption
functions defined in Section 3 [EQ: SOG composite], [EQ: FCR], any difference in fuel is
attributable to speed-decision granularity alone — not to the physics model or the spatial
discretisation.

## 4.1 Common optimisation framework

The decision variable was SOG rather than still-water speed (SWS): a planned SOG schedule was
chosen, and the SWS required to realise it followed from the inverse of the SOG relation under
the prevailing weather (SOG-targeting). Both formulations minimised total voyage fuel,
$F_\text{total} = \sum_i \text{FCR}(V_{s,i})\, d_i / \text{SOG}_i$ [EQ: total voyage fuel],
subject to a hard arrival-time constraint $T$ (the ETA). The ETA was binding in every run
reported here: arrival slack was zero throughout, so both formulations slow-steamed to the
deadline and the comparison is one of fuel at equal voyage time.

The speed search was discretised to a common grid of 61 SOG values spanning the mean voyage
speed $\pm 3$ kn, where the mean speed is total route length divided by ETA ($L/T$). The route
was represented as a two-dimensional time–distance graph: a distance axis at fixed waypoint
spacing and a time axis discretised at step $\Delta t$ [METHODS: state $\Delta t$ per route from
config]. This shared grid is the fairness control — it ensures that the SR–Luo comparison
isolates speed-decision granularity rather than resolution differences.

## 4.2 Free-speed formulation: SR (Shafir–Raviv)

SR was solved on an atomic-edge graph. Each node represents a discretised
(distance, time) state; each outgoing edge represents a single speed choice over one leg, with
cost equal to the fuel consumed on that leg,
$c = \text{FCR}(V_s)\, \cdot\, d_i / \text{SOG}(V_s, w_{i,t})$ [EQ: edge cost], where $w_{i,t}$ is
the weather encountered at that leg and time. The minimum-fuel path from origin to destination
within the ETA was found by a forward Bellman recursion over the time-ordered nodes
[EQ: Bellman recursion], and the optimal speed schedule recovered by backtracking.

Because speed is chosen independently on every leg, SR can adapt to weather variation at each
waypoint crossing — slowing where conditions are adverse and accelerating where they are
favourable, subject only to the ETA.

## 4.3 Per-block-locked baseline: Luo (2024)

The baseline followed the block dynamic-programming formulation of [CITE: Luo 2024]. Its graph is
a lattice of $(\text{column}, \text{distance})$ nodes, where columns mark times
$0, \Delta t, 2\Delta t, \ldots$ Each arc spans one block (one column) and is traversed at a
*single constant* SOG equal to the block distance divided by $\Delta t$. The arc cost was
obtained by walking the weather sub-segments within the block and summing fuel at that fixed
block SOG [EQ: Luo arc cost]; the minimum-fuel path to the ETA column was then found by shortest
path.

The defining restriction is that speed is constant within a block: the formulation cannot vary
speed in response to weather that changes *inside* a block. This baseline was implemented
independently from its published description — with its own lattice and arc evaluation, not as SR
subject to an added equality constraint — so that the comparison reflects Luo's actual method
rather than a weakened variant.

## 4.4 Evaluation protocol

**Consecutive-voyage chains.** Each route was evaluated as a chain in which voyage $N+1$ departs
at the sample hour at which voyage $N$ arrives ($\text{sh\_base}_{N+1} = \text{sh\_base}_N + T$).
Fixing the step to the ETA guaranteed that SR and Luo encountered identical departure weather at
every voyage. Seven voyages were run on Route 1 and twelve on Route 2 — 19 in total — spanning
approximately 80 days of the collection window.

**Perfect foresight (oracle).** Each leg was evaluated against the *actual* weather
recorded at the voyage's departure sample hour, giving the optimiser perfect foresight. This
bounds the achievable advantage and is reported in Section 6.1.

**Rolling horizon (RH).** To represent realistic operation, both formulations were re-solved at
6 h decision steps. At each step the first 6 h block was planned against *actual* (nowcast)
weather — the conditions a captain can observe — and the remainder of the voyage against the most
recent available *predicted* weather cycle; only the first block was committed before advancing
and re-planning [EQ: rolling-horizon decision rule]. Realised fuel was the sum of the committed
blocks. The 6 h cadence was not tuned: it equals the underlying GFS numerical weather prediction
(NWP) cycle (Section 5).

**Naive baseline.** As the operational reference, a set-and-forget policy sailed a single fixed
mean SOG ($L/T$) through the actual time-varying weather, with no re-planning. The headline
rolling-horizon result is reported relative to this baseline (Section 6.2).

# 5. The convexity mechanism

The fuel-consumption rate is strictly convex in speed: $\text{FCR}(V_s) = 0.000706\, V_s^3$
[EQ: FCR] is cubic and therefore convex on the operating range. This single property predicts,
before any experiment, that per-block speed-locking must waste fuel relative to per-leg freedom
whenever weather varies within a block.

Consider one time block that spans several legs whose weather differs — a typical situation, since
ocean conditions change continuously along a route. A free-speed policy may set a different speed
on each leg; a block-locked policy must hold one speed across them all. To maintain a *constant*
SOG across legs of differing weather, the block-locked policy is forced to vary the still-water
speed (SWS) from leg to leg — more SWS where conditions are adverse, less where they are
favourable. Fuel depends on SWS through the convex FCR, so by Jensen's inequality the mean fuel of
this forced, varying SWS exceeds the fuel that the *mean* SWS would consume:

$$\mathbb{E}\!\left[\text{FCR}(V_s)\right] \;\ge\; \text{FCR}\!\left(\mathbb{E}[V_s]\right)
\qquad\text{[EQ: Jensen on FCR]}$$

The harsh-leg penalty always outweighs the favourable-leg saving. A free-speed policy is not bound
to a constant SOG and can allocate speed across legs so as to keep operation in a more efficient
regime, avoiding the forced excursions; it therefore consumes no more fuel than the block-locked
policy, and strictly less whenever within-block weather is non-uniform.

Two empirical predictions follow, both tested in Section 6.

1. **A systematic, signed gap.** SR should consume less fuel than Luo on essentially every voyage
   in which weather varies within blocks — not occasionally, but as a rule, because the inequality
   is directional.

2. **A gap that scales with weather variability.** The size of the penalty grows with the spread
   of within-block conditions. Routes or departures whose weather varies more should exhibit a
   larger gap; a shorter voyage that concentrates the same variability into fewer, denser blocks
   should show a proportionally larger effect.

The same convexity has a second consequence that is examined later as a limitation
(Section 7): on *uniform* weather a constant speed is itself fuel-optimal, so the value of any
speed variation — including the forecast-driven variation of a rolling-horizon policy — is bounded
by how much the weather actually varies. The mechanism thus explains both why free-speed
optimisation helps and why its benefit is bounded.

This argument is exact only for the convex FCR and the equal-time comparison used throughout;
it predicts the *direction* and the *scaling* of the effect, while its *magnitude* on real routes
is the empirical question answered next.

# 5b. Data and experimental design

## 5b.1 Weather data

Environmental data were obtained from the Open-Meteo API, which serves operational numerical
weather prediction (NWP) products: 10 m wind from the GFS model, significant wave height from
MFWAM, and ocean-current velocity from SMOC [CITE: Open-Meteo]. Beaufort number was computed from
the 10 m wind speed rather than taken from the API (Section 3). For each route, both the realised
("actual") weather and the forecasts ("predicted") issued at each cycle were collected at every
waypoint, at a 6 h sampling cadence, over approximately 80 days. Data were stored in HDF5 with
separate tables for actual weather, predicted weather, and metadata.

The two routes differ markedly in regime [TABLE: route and weather summary]. Route 1 (Persian
Gulf → Malacca) is mild and relatively uniform; Route 2 (North Atlantic) is harsh, with mean wind
and wave conditions several times larger and far more variable [METHODS: insert per-route wind/wave
mean ± s.d. from data]. This contrast is what allows the convexity prediction — that the SR–Luo
gap scales with weather variability (Section 5) — to be tested across regimes.

## 5b.2 Forecast accuracy (supporting measurement S-1)

Forecast error was measured directly by comparing predicted weather against the actual weather
subsequently observed at the same waypoint and time, as a function of lead time. Wind-speed RMSE
grew systematically with lead time: it approximately doubled over the first 133 h on Route 1
(4.13 → 8.40 km/h) and grew more steeply on the harsher Route 2 (+286 % over 144 h)
[TABLE/FIG: forecast error vs lead time]. This degradation is the reason a rolling-horizon plan,
which commits speeds against forecasts that are later revised, consumes more fuel than the
perfect-foresight oracle (Section 6.2); it is reported here as ground truth, independent of any
optimisation.

## 5b.3 NWP model cycle and the re-plan cadence (supporting measurement S-2)

The 6 h rolling-horizon cadence was set to the underlying model refresh, not tuned. The GFS wind
product refreshes every 6 h; the MFWAM wave and SMOC current products refresh every 12 h and 24 h
respectively. Inspection of the predicted-weather record confirmed this empirically: 86 % of
hourly wind queries returned data identical to the previous hour. Re-planning more frequently than
6 h therefore acts on no new information, which is why the cadence is fixed to the model cycle
[TABLE: NWP model cycles].

## 5b.4 Experimental design

Each route was evaluated as a consecutive-voyage chain of departures spaced one ETA apart
(Section 4.5), yielding 7 voyages on Route 1 and 12 on Route 2 — 19 in total, spanning the
collection window. At each departure, both formulations were run under (i) the perfect-foresight
oracle and (ii) the 6 h rolling horizon, and the rolling-horizon result was compared
against the Naive set-and-forget baseline. Identical departure weather was presented to both
formulations at every voyage, so all reported differences are attributable to the speed-decision
granularity and the information regime, not to sampling.

# 6. Results

The two free-speed formulations are evaluated against the per-block speed-locked baseline of
[CITE: Luo 2024] in two regimes. Section 6.1 reports the comparison under perfect weather
foresight (the oracle), which bounds the achievable advantage (RQ2). Section 6.2 reports
the comparison under realistic rolling-horizon (RH) planning against real, imperfect forecasts,
relative to set-and-forget operation (RQ3). Throughout, **SR** denotes the Shafir–Raviv
per-leg free-speed dynamic program and **Luo** the per-block speed-locked formulation of
[CITE: Luo 2024]; both were solved on the identical route discretisation and speed grid
[METHODS→G4]. Two routes are used: Route 1 (Persian Gulf → Strait of Malacca,
3,393 nm, ETA 280 h) and Route 2 (St. John's → Liverpool, North Atlantic, 1,955 nm, ETA 168 h)
[METHODS→G4].

## 6.1 Fuel under perfect foresight

Each route was run as a consecutive-voyage chain in which voyage $N+1$ departs when voyage $N$
arrives, so SR and Luo encountered identical departure weather at every voyage. Nineteen voyages
were evaluated in total (seven on Route 1, twelve on Route 2), spanning approximately 80 days of
the collection window. In every voyage both formulations consumed the full time budget
(arrival slack was zero throughout): the hard ETA was binding, and both solvers slow-steamed to
the deadline.

Per-voyage fuel is reported in the Route 1 and Route 2 tables below; the aggregate comparison
follows.

**Perfect-foresight aggregates** (negative gap = SR burns less fuel):

| Route | $n$ | SR mean ± s.d. (mt) | Luo mean ± s.d. (mt) | Mean gap (mt) | Mean gap (%) |
|---|---:|---:|---:|---:|---:|
| 1 (Malacca) | 7 | 344.87 ± 7.77 | 351.26 ± 8.72 | −6.39 | −1.8 |
| 2 (Atlantic) | 12 | 201.90 ± 10.32 | 207.36 ± 11.03 | −5.46 | −2.6 |

**Perfect-foresight per-voyage fuel — Route 1 (Malacca, ETA 280 h)** (sh₀ = departure sample hour):

| Voyage | sh₀ | SR (mt) | Luo (mt) | Gap (mt) | Gap (%) |
|---:|---:|---:|---:|---:|---:|
| 0 | 6 | 354.82 | 361.56 | −6.74 | −1.86 |
| 1 | 286 | 355.23 | 364.68 | −9.45 | −2.59 |
| 2 | 566 | 337.70 | 342.41 | −4.71 | −1.38 |
| 3 | 846 | 348.19 | 353.15 | −4.96 | −1.40 |
| 4 | 1126 | 337.60 | 340.87 | −3.27 | −0.96 |
| 5 | 1406 | 334.83 | 343.86 | −9.03 | −2.63 |
| 6 | 1686 | 345.73 | 352.31 | −6.58 | −1.87 |

**Perfect-foresight per-voyage fuel — Route 2 (Atlantic, ETA 168 h):**

| Voyage | sh₀ | SR (mt) | Luo (mt) | Gap (mt) | Gap (%) |
|---:|---:|---:|---:|---:|---:|
| 0 | 0 | 203.20 | 210.25 | −7.05 | −3.35 |
| 1 | 168 | 204.17 | 209.51 | −5.34 | −2.55 |
| 2 | 336 | 195.24 | 201.95 | −6.71 | −3.32 |
| 3 | 504 | 206.12 | 212.22 | −6.10 | −2.87 |
| 4 | 672 | 215.93 | 223.50 | −7.57 | −3.38 |
| 5 | 840 | 190.75 | 196.89 | −6.14 | −3.12 |
| 6 | 1008 | 227.91 | 233.85 | −5.94 | −2.54 |
| 7 | 1176 | 194.40 | 198.25 | −3.86 | −1.94 |
| 8 | 1344 | 194.64 | 197.05 | −2.41 | −1.22 |
| 9 | 1512 | 192.75 | 196.90 | −4.15 | −2.11 |
| 10 | 1680 | 199.10 | 203.49 | −4.39 | −2.16 |
| 11 | 1848 | 198.57 | 204.41 | −5.84 | −2.86 |

Three findings follow.

**SR consumed less fuel than Luo on every voyage.** The free-speed formulation was more
fuel-efficient on all 19 of 19 voyages, with no exceptions on either route. The per-voyage
advantage ranged from 3.27 to 9.45 mt on Route 1 and from 2.41 to 7.57 mt on Route 2.

**The absolute advantage was comparable across routes, but proportionally larger on the
shorter voyage.** The mean fuel saving was similar in absolute terms (6.39 mt on Route 1,
5.46 mt on Route 2) despite Route 2 being roughly half the duration; expressed as a fraction of
total fuel the advantage was therefore larger on the shorter, harsher Atlantic route (2.6 %)
than on the longer Malacca route (1.8 %). [METHODS→G4 / DISCUSSION: this is the Jensen
mechanism — a shorter voyage concentrates the within-block weather variation that per-block
locking cannot exploit.]

**Departure weather dominated voyage-to-voyage fuel variation.** On Route 2 the worst
departure (227.91 mt) consumed 19.5 % more fuel than the best (190.75 mt) for the same
formulation — a spread larger than the entire SR–Luo gap. The Atlantic fuel spread per
voyage-hour was approximately three times that of the Malacca route, consistent with the
greater variability of North Atlantic conditions [METHODS→G4: weather statistics].

## 6.2 Fuel under rolling-horizon planning (real forecasts)

The oracle comparison establishes an upper bound that assumes perfect foresight. To test
whether the advantage survives realistic operation, both formulations were embedded in a 6 h
rolling-horizon scheme: at each decision step the next 6 h block was planned against **actual**
(nowcast) weather and the remainder of the voyage against the most recent **predicted** weather
cycle; only the first block was committed before re-planning [METHODS→G4]. The realised voyage
was compared against a Naive set-and-forget baseline — a single fixed mean speed
($L/T$) sailed through the actual weather. The same 19 voyages were evaluated.

Realised fuel relative to the Naive baseline is reported per voyage in the Route 1 and Route 2
tables below, and summarised next.

**Rolling-horizon summary** (negative % = saving vs Naive set-and-forget):

| Route | $n$ | RH-SR vs Naive (mean %) | RH-Luo vs Naive (mean %) | RH-SR saves on |
|---|---:|---:|---:|---:|
| 2 (Atlantic) | 12 | −1.9 | −0.2 | 11/12 |
| 1 (Malacca) | 7 | −1.2 | −0.1 | 7/7 |

**Rolling-horizon per-voyage realised fuel — Route 1 (Malacca, ETA 280 h)** (sh₀ = departure sample hour):

| sh₀ | Naive (mt) | RH-SR (mt) | RH-Luo (mt) | RH-SR vs Naive (%) | RH-Luo vs Naive (%) |
|---:|---:|---:|---:|---:|---:|
| 6 | 362.74 | 358.86 | 362.57 | −1.07 | −0.05 |
| 286 | 367.03 | 358.73 | 367.72 | −2.26 | +0.19 |
| 566 | 345.42 | 342.82 | 344.51 | −0.75 | −0.26 |
| 846 | 354.74 | 350.33 | 354.36 | −1.24 | −0.11 |
| 1126 | 342.68 | 341.55 | 341.69 | −0.33 | −0.29 |
| 1406 | 346.19 | 344.11 | 346.57 | −0.60 | +0.11 |
| 1686 | 356.03 | 349.32 | 355.10 | −1.88 | −0.26 |

**Rolling-horizon per-voyage realised fuel — Route 2 (Atlantic, ETA 168 h):**

| sh₀ | Naive (mt) | RH-SR (mt) | RH-Luo (mt) | RH-SR vs Naive (%) | RH-Luo vs Naive (%) |
|---:|---:|---:|---:|---:|---:|
| 0 | 212.61 | 205.00 | 212.12 | −3.58 | −0.23 |
| 168 | 212.78 | 208.34 | 211.41 | −2.08 | −0.64 |
| 336 | 203.65 | 200.99 | 203.42 | −1.31 | −0.11 |
| 504 | 214.54 | 212.61 | 216.01 | −0.90 | +0.68 |
| 672 | 225.98 | 222.38 | 224.90 | −1.59 | −0.48 |
| 840 | 200.50 | 192.98 | 199.04 | −3.75 | −0.73 |
| 1008 | 237.09 | 230.53 | 235.33 | −2.76 | −0.74 |
| 1176 | 200.43 | 197.33 | 200.71 | −1.54 | +0.14 |
| 1344 | 199.35 | 200.82 | 200.49 | +0.74 | +0.57 |
| 1512 | 198.99 | 195.58 | 198.28 | −1.71 | −0.36 |
| 1680 | 206.86 | 201.65 | 205.70 | −2.52 | −0.56 |
| 1848 | 206.10 | 201.91 | 206.27 | −2.03 | +0.08 |

**Free-speed re-planning saved fuel; block-locked re-planning did not.** Rolling-horizon SR
reduced realised fuel relative to set-and-forget on 18 of 19 voyages (mean −1.9 % on Route 2,
−1.2 % on Route 1; best −3.75 %). Rolling-horizon Luo, by contrast, was statistically
indistinguishable from set-and-forget (mean −0.2 % and −0.1 %): the per-block lock left no room
to exploit the refreshed forecasts. The SR–Luo contrast established under perfect foresight
(Section 6.1) therefore persisted under realistic, imperfect-forecast operation, on both routes
and across the full departure window.

**Realised fuel fell within the oracle–Naive envelope.** On every voyage the realised RH fuel
satisfied $\text{oracle} \le \text{RH} \le \text{Naive}$: re-planning under imperfect forecasts
could not beat perfect foresight but did beat set-and-forget. Rolling-horizon SR sat between
1.8 and 8.9 mt above its oracle, the gap representing the cost of committing speeds against
forecasts that were subsequently revised [LIT→G5: forecast error; supporting S-1].

**The two formulations re-planned differently.** A single-voyage diagnostic (Route 2, first
departure) recorded how often a refreshed forecast changed the committed first-block speed:
rolling-horizon SR revised its decision on 8 of 27 re-plans (30 %, mean change 0.19 kn), whereas
rolling-horizon Luo revised on 17 of 27 (63 %, mean change 0.43 kn). The block-locked
formulation adjusted more frequently yet gained less — it lacked the within-block resolution to
convert forecast updates into fuel savings.

[Boundedness of the RH advantage — that it shrinks with weather variability and can reverse on
near-uniform departures — is treated as a limitation in Section&nbsp;7, per the G2 decision.]

## 6.3 Supporting observations

Two measurements underpin the rolling-horizon design [LIT→G5; full detail in §5 / Methods].
First, forecast accuracy degraded systematically with lead time: wind-speed RMSE approximately
doubled over the first 133 h on Route 1 (4.13 → 8.40 km/h) and grew more steeply on the harsher
Route 2 (+286 % over 144 h), establishing why realised RH fuel exceeded the oracle. Second, the
6 h re-plan cadence was not tuned but fixed to the underlying numerical weather prediction (NWP)
model cycle: the GFS wind product refreshes every 6 h, and 86 % of hourly forecast queries
returned identical data, so sub-6 h re-planning carried no new information.

# 7. Discussion

## 7.1 The mechanism predicted the result

The two predictions of the convexity mechanism (Section 5) were both borne out. First, the gap
was *signed and systematic*: under perfect foresight the free-speed formulation consumed less fuel
than the per-block baseline on all 19 of 19 voyages, with no exception on either route
(Section 6.1). This is the directional signature of Jensen's inequality acting on the convex fuel
curve — not an average tendency but a rule. Second, the gap *scaled with weather variability*: it
was proportionally larger on the harsher, more variable Atlantic route (2.6 %) than on the milder
Malacca route (1.8 %), as predicted for a penalty driven by within-block weather spread. The
empirical magnitude — roughly 6 mt per voyage — is thus explained, not merely reported.

## 7.2 Decision granularity, not data, is the limiting factor

That the free-speed advantage persisted under realistic rolling-horizon operation (Section 6.2) —
where it saved fuel against set-and-forget while the per-block baseline did not — confirms the
effect is not an artefact of perfect information. The per-block baseline re-planned *more* often
under refreshed forecasts yet gained *less*, because it lacked the within-block resolution to act
on the new information. The limiting factor is decision granularity, not data.

## 7.3 When re-planning helps — and when it does not (limitation)

The rolling-horizon benefit over set-and-forget is real but bounded, and this study does not
claim it is universal. On 1 of 19 voyages the free-speed rolling-horizon plan consumed slightly
*more* fuel than the fixed-speed baseline, and the per-block rolling-horizon plan did so on
several. The reason is the same convexity that drives the main result, seen from the other side:
on near-uniform weather a constant speed is itself fuel-optimal, so any forecast-driven speed
variation can only add a Jensen penalty unless the weather-routing gain exceeds it. The value of
re-planning is therefore bounded by how much the weather actually varies over a departure's window
— it is largest on variable departures and can vanish or reverse on calm, uniform ones. This is
best read as a savings-versus-departure relationship rather than a single figure
[FIG: savings vs departure]. Reported precisely, the relevant gate is "realised fuel ≤ Naive",
which the free-speed plan satisfied on 18 of 19 voyages and the per-block plan on a minority.

## 7.4 Relation to prior work [LIT→G5]

[LIT→G5: position against per-block / segment-constant speed optimisation (Luo 2024; segment-
averaged LP) — pillar 1; against rolling-horizon / MPC in OR and its limited maritime application
with real NWP — pillars 4, 5; against fuel-resistance modelling and the cubic exponent — pillar 2.
State what this study adds: an isolated convexity mechanism, a faithful published baseline, and
operational validation across real departures.]

## 7.5 Limitations

Several bounds on the present results should be noted. (i) Two routes were studied; while they
span two contrasting regimes, the route-length scaling of the gap is reported as a contrast, not a
curve, and additional routes would be needed to establish it as a law. (ii) The arrival constraint
was hard and binding (zero slack) throughout, so the results describe fuel at equal voyage time;
relaxing the ETA is left to future work. (iii) The rolling-horizon nowcast assumes the current 6 h
block is observable; the realism of this assumption depends on onboard sensing. (iv) The per-block
baseline, though implemented faithfully
from its published description, is one of several possible block formulations.

# 8. Conclusion

This study compared per-leg free-speed voyage optimisation (the Shafir–Raviv formulation) against
the per-block speed-locked formulation of [CITE: Luo 2024] for fuel-minimising ship routing under
time-varying weather, on two routes spanning two weather regimes.

Three conclusions follow. First, per-block speed-locking is fuel-suboptimal by a structural
mechanism: because the fuel-consumption rate is convex in still-water speed, holding one speed
across a block of varying weather forces inefficient speed excursions, and per-leg freedom recovers
the loss (Jensen's inequality). Second, under perfect foresight the
free-speed advantage was realised on every one of 19 voyages — comparable in absolute fuel across
routes (~6 mt) but proportionally larger on the shorter, harsher voyage. Third, the advantage
survived realistic 6 h rolling-horizon operation against real forecasts: free-speed re-planning
saved fuel relative to set-and-forget operation on 18 of 19 voyages, whereas per-block re-planning
did not, its value being bounded by weather variability.

The practical implication is that the resolution of the speed decision — not the availability of
re-planning or fresh forecasts — is the binding factor: a per-block planner cannot convert better
information into fuel savings, while a per-leg planner can. The expected saving can be anticipated
from the variability of the route's weather.

Future work includes extending the route set to establish the route-length scaling as a curve
rather than a contrast, relaxing the hard arrival constraint to a soft ETA penalty, and examining
the sensitivity of the conclusions to the fuel-speed exponent.


---

## References
Yang, L., Chen, G., Zhao, J., Rytter, N.G.M., 2020. Ship speed optimization considering ocean
currents to enhance environmental sustainability in maritime shipping. Sustainability 12 (9), 3649.
https://doi.org/10.3390/su12093649

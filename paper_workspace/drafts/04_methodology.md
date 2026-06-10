<!--
DRAFT — Methods. Writes G4 (§4.1–4.4, 4.6, 4.7) forward; Jensen (G4 §4.5) is split out into
drafts/05_mechanism.md per the standalone-section decision.
Physics (SOG chain, cubic FCR) is assumed defined in §3 Problem Formulation; referenced here.
Numbers from G1 (CSV-verified). Equation refs use [EQ: name] placeholders (numbered at assembly).
Voice: TR-C — third person, passive, past tense for methods. "This study", not "we".
-->

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

<!--
COVERAGE vs G4: 4.1 framework+shared grid ✓ | 4.2 SR ✓ | 4.3 Luo+fidelity ✓ |
4.4 structural complexity + structural-only caveat ✓ | 4.5 protocol (chain, perfect foresight, RH, Naive) ✓.
Jensen (G4 §4.5) → drafts/05_mechanism.md (standalone). Routes/weather stats → §5 [SETUP].
Resolves 06_results [METHODS→G4]: shared grid, routes, RH scheme, chain protocol.
OPEN: state Δt per route from config; confirm V/H-line definitions if used verbatim.
-->

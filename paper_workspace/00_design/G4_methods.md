# G4 — Methods Skeleton

**Gate status:** DRAFT → review → freeze. Built on frozen G1/G2/G3.
**Rule (the discipline of this gate):** include *only* the apparatus needed to make the
RQ→evidence chain legible. Anything the results/claims do not use is **excluded** (listed in
§Excluded). Every subsection names which RQ it serves and which `[METHODS→G4]` placeholder in
`../drafts/06_results.md` it resolves.

**Naming (confirmed 2026-06-08):** **SR = the Shafir–Raviv formulation** (per-leg free-speed
dynamic program). **Luo = the per-block speed-locked formulation of [CITE: Luo 2024]** — a
faithful re-implementation (its own `(column, distance)` lattice), not a strawman.

Equation content is available in `../reference/paper-equations/` and `../reference/research-paper/`
(FCR, SOG chain, resistance terms). Cite as `[EQ: n]`; do not invent equations here.

---

## Section plan (→ writes forward into `drafts/04_methodology.md` + part of `03_problem_formulation`)

### 4.1 Ship and fuel model (the measurement system)
- **Defines:** ship spec (length, beam, draft, displacement, rated power, SWS range [11,13] kn);
  the SOG-from-SWS chain under wind/wave/current `[EQ: SOG chain]`; the fuel-consumption-rate law
  **FCR = 0.000706·$V_s^3$ mt/h** `[EQ: FCR]`.
- **Why it's here / serves:** RQ1 — the **convexity** of FCR is the premise of the whole
  mechanism. State explicitly that FCR is strictly convex (cubic) in speed.
- **Resolves:** the cubic-FCR fact promised in `01_introduction §1.1` `[LIT→G5]` overlaps here.

### 4.2 Routes and shared discretisation (fairness control)
- **Defines:** Route 1 (Persian Gulf → Malacca, 3,393 nm, ETA 280 h) and Route 2
  (St. John's → Liverpool, N. Atlantic, 1,955 nm, ETA 168 h); waypoints `[CITE/skill: waypoints]`;
  the **shared** route discretisation and the common SOG grid (61 values, mean SOG ± 3 kn) used by
  *both* SR and Luo; weather regime statistics (wind/wave means and variability per route).
- **Serves:** RQ2/RQ3 (defines the test set) and the fairness of the SR–Luo and structural-size
  comparisons (same grid → comparison is apples-to-apples).
- **Resolves:** `06_results` placeholders — "identical route discretisation and speed grid",
  "Route 1/Route 2 … [METHODS→G4]", "weather statistics".

### 4.3 Free-speed formulation — SR (Shafir–Raviv)
- **Defines:** the atomic-edge graph (V-lines × H-lines), per-leg free SOG choice, edge fuel cost,
  forward Bellman minimisation of total fuel subject to the hard ETA, backtracking. `[EQ: edge cost, recursion]`
- **Serves:** RQ1 (the freedom), RQ2/RQ3 (the method under test).

### 4.4 Per-block-locked baseline — Luo (2024)
- **Defines:** the `(time-column, distance-index)` lattice; one constant SOG per block; arc cost
  as fuel summed over weather sub-segments at the fixed block SOG; shortest path to ETA.
- **Serves:** RQ1/RQ2 (the foil). **State fidelity explicitly:** this is Luo's own block-DP
  construction, independently implemented, so the comparison is not a weakened baseline.

### 4.5 → PROMOTED to a standalone "Mechanism" section (DECISION 2026-06-08)
> Jensen is **not** a Methods subsection. It becomes a **short standalone section placed between
> Methods and Results** ("The convexity mechanism"): it states the *analytic prediction* — for a
> convex FCR, one speed held across a block of non-uniform weather burns more fuel than per-leg
> speed at the same mean (Jensen's inequality) — which Section 6 then confirms empirically.
- **Content:** the formal Jensen statement `[EQ: Jensen on FCR]`; the prediction that the
  SR–Luo gap grows with within-block weather variation (later linked to the route-length scaling).
- **Serves:** RQ1 (Claim 1). Empirical size = Section 6; interpretation extends into Discussion.
- **Note:** may reference segment-averaged LP **once** as an analogous per-block lock (the single
  permitted nod to the dropped LP/DP framing) — no LP formulation, no SOS2.

### 4.6 Structural complexity (the freedom-cost axis — structural only)
- **Defines:** the size measures — node count |V|, edge count |E|, and decision-variable count —
  and the asymptotic forms **SR: $O(V \cdot H \cdot K)$** vs **Luo: $O(\text{blocks} \cdot K)$**.
  Plug in the on-disk counts (Route 1: 152,571 nodes / 9.2M edges; Route 2: 71,861 / 4.3M;
  Luo block count derived from ETA/Δt and route length). `[TABLE: formulation sizes]`
- **Serves:** RQ1 / Contribution C-I (freedom-cost coin).
- **HARD LIMIT (reaffirmed 2026-06-08):** structural/analytical only. **No** measured runtime,
  **no** fuel-vs-seconds Pareto, **no** benchmark apparatus described. Illustrative wall-times
  (C++ ≈ 2 min vs Python ≈ 532 min per voyage) may appear **once**, explicitly caveated as not a
  controlled benchmark.

### 4.7 Evaluation protocol — Mode C, rolling horizon, and the Naive baseline
- **Defines:**
  - **Consecutive-voyage chain:** voyage $N+1$ departs at $\text{sh\_base}_{N}+\text{ETA}$, so SR
    and Luo see identical departure weather; 7 voyages (Route 1) + 12 (Route 2) = 19.
  - **Mode C (oracle):** per-leg **actual** weather anchored at the voyage-start sample hour —
    perfect foresight; the achievable-advantage ceiling (RQ2).
  - **Rolling horizon (RH):** 6 h decision steps; first block planned on **actual** (nowcast)
    weather, remainder on the most-recent **predicted** cycle; commit first block, re-plan; the
    6 h cadence equals the GFS model cycle (supporting S-2). Realised fuel = Σ committed blocks (RQ3).
  - **Naive baseline:** single fixed mean SOG ($L/T$) sailed through actual weather — set-and-forget.
- **Serves:** RQ2 (Mode C) and RQ3 (RH vs Naive).
- **Resolves:** `06_results` placeholders — the RH scheme description, the chain protocol.
- **Reporting notes carried from G1 §F:** one oracle source per table (Python Mode-C chain *or*
  C++ RH-embedded oracle, not mixed); Route-2 RH numbers cite prep §6.2; when noting any
  RH ≤ Naive reversal, name the precise gate.

---

## Excluded (deliberately not in Methods — "nothing unused")
| Excluded | Why |
|---|---|
| LP formulation (objective, SOS2, segment averaging) | LP/DP foil dropped (G2). At most a one-line analogy in §4.5. |
| Mode A / Mode B; plan-vs-simulate `simulate_voyage` pass | Out of scope — RH + Mode C only. |
| Soft-ETA penalty λ, SWS-violation counting | Not used — ETA is hard, slack = 0 throughout; arrival deviation not a headline. |
| Measured-runtime benchmarking apparatus | Compute axis is structural only (§4.6 hard limit). |
| Forecast-error / NWP-cycle *derivation* detail | Belongs to Experimental Setup (§5) as supporting S-1/S-2; Methods only references it. |

## Traceability — every subsection earns its place
| Subsection | RQ | Claim/Contribution | Resolves placeholder |
|---|---|---|---|
| 4.1 ship + cubic FCR | RQ1 | C-I (convexity premise) | cubic-FCR fact |
| 4.2 routes + shared grid | RQ2/RQ3 | C-II/C-III (fair test) | discretisation, routes, weather stats |
| 4.3 SR | RQ1/RQ2/RQ3 | C-I/C-II/C-III | SR definition |
| 4.4 Luo | RQ1/RQ2 | C-I/C-II | Luo definition, fidelity |
| 4.5 Jensen | RQ1 | C-I (Claim 1) | mechanism "why" |
| 4.6 complexity | RQ1 | C-I (Claim 6) | O(V·H·K) vs O(blocks·K) |
| 4.7 protocol | RQ2/RQ3 | C-II/C-III | Mode C, RH scheme, chain |

## Freeze checklist — ✅ FROZEN 2026-06-08
- [x] Each results `[METHODS→G4]` placeholder maps to a subsection above.
- [x] §4.5 = **standalone "Mechanism" section** between Methods and Results (not a Methods subsection).
- [x] §4.6 structural-only limit **reaffirmed** (no benchmark apparatus).
- [x] Excluded list agreed (no LP formulation, no Mode A/B, no λ/violation machinery, no benchmark apparatus).
- [x] Sign off. → Next: write `drafts/04_methodology.md` + `drafts/05_mechanism.md` forward, and/or design G5 (gap map).

**Paper structure implied by G4 (numbering settled at assembly):**
Intro · Related work [G5] · Problem formulation (ship + cubic FCR) · Methods (SR, Luo, complexity, protocol) ·
**Mechanism (Jensen)** · Experimental setup (data, S-1/S-2) · Results (Mode C; RH) · Discussion (incl. boundedness) · Conclusion.

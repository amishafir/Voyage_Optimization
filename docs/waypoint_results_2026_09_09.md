# Results and conclusions on the `waypoint` partition

**Date:** 2026-09-09
**Scope:** every experiment re-run on `waypoint`, 41 voyages, current code. **No `geo` number is used
anywhere below.** Migration plan: [`waypoint_migration_design.md`](waypoint_migration_design.md).

| Experiment | Run | Status |
|---|---|---|
| Perfect foresight, SR + Luo | `runs/2026_09_08_pf_chain41/waypoint/` | 41/41 |
| Perfect foresight, Naive | `runs/2026_09_08_pf_chain41/naive_waypoint/` | 41/41 |
| Rolling horizon, Naive + RH-SR + RH-Luo | `runs/2026_09_09_rh_chain41_waypoint/` | 41/41, 0 failures |

All solves are the C++ binaries (`dp_SR`, `dp_luo`, `dp_run_rh`); the Python files are drivers only.
The RH oracle reproduces the PF run to the digit (route 1 SR 353.049 / Luo 360.431, Naive 360.476),
so PF and RH sit on one graph for the first time.

---

## 1. Perfect foresight

| | Malacca (n=15) | Atlantic (n=26) |
|---|---|---|
| mean block length | 27.15 nm | 5.04 nm |
| SR | 345.46 mt | 198.78 mt |
| Luo | 354.06 mt | 201.61 mt |
| Naive | 355.11 mt | 203.26 mt |
| **SR − Luo** | **−2.43 %** | **−1.40 %** |
| SR − Naive | −2.72 % | −2.20 % |
| Luo − Naive | −0.30 % | −0.81 % |
| SR advantage | 8.61 mt (6.06 – 13.24) | 2.82 mt (0.72 – 6.03) |

**SR beat Luo on 41 of 41 voyages.** No exceptions on either route, minimum margin 0.72 mt; also
41/41 under `geo`, so 82/82 solves.

### This is a theorem, not an observation

SR's decision points are **H-lines ∪ V-lines**. Every atomic edge terminates at whichever line comes
first — `next_v_time(src_t)` or `next_h_distance(src_d)` — and nodes are typed `LineType::V` /
`LineType::H`. The V-lines are the 6 h time grid, and they *are* Luo's blocks:

| Route | V-lines (`v_line_times_from_route`) | Luo blocks | |
|---|---|---|---|
| Malacca | 47 (6, 12, …, 276, 280) | 47 | identical |
| Atlantic | 28 (6, 12, …, 162, 168) | 28 | identical |

Both use the same speed bounds (`mean_sog ± 3`), and Luo's per-block distance quantum
(`res_nm = 1.0`) matches SR's distance snap (`ζ = 1.0 nm`). So any Luo plan — one speed held across a
6 h block — is reproducible by SR by choosing that same speed on every sub-arc inside the block.

**SR's feasible set contains Luo's.** Therefore `SR ≤ Luo` is guaranteed whenever the weather used
for planning is the weather used for evaluation — which is exactly perfect foresight. The 41/41 is
the only possible outcome, and the paper should present it as a property of the formulation rather
than as a finding. The empirical content is the **magnitude** (−2.43 % / −1.40 %), not the sign.

---

## 2. Rolling horizon

| Route | n | RH-SR vs Naive | RH-Luo vs Naive | RH-SR saves on |
|---|---|---|---|---|
| North Atlantic | 26 | **−0.26 %** | −0.12 % | **15/26** |
| Indian Ocean | 15 | **−1.46 %** | +0.10 % | **15/15** |

RH-SR saved on **30 of 41** voyages overall. Best saving −2.34 % (sh 286). Eleven exceptions, all on
the Atlantic, up to +1.48 %.

### The headline finding: nesting holds in-sample and fails out-of-sample

Under RH both planners re-solve against the *same forecast*, so the nesting of §1 still applies
in-sample: SR's plan is provably at least as good as Luo's **against the forecast**. Yet on realised
fuel against *actual* weather:

| Route | RH-SR worse than RH-Luo | SR legs per 6 h Luo block | wind RMSE at max lead |
|---|---|---|---|
| Indian Ocean | **0/15** | 2.0 – 2.9 | 8.40 km/h |
| North Atlantic | **12/26** | 10.7 – 15.5 | 24.75 km/h |

Worst cases, all Atlantic: +2.59 mt (sh 2352), +2.28 (sh 3024), +1.57 (sh 1848), +1.41 (sh 3192).

This is overfitting, and the nesting makes the argument airtight rather than suggestive:

> SR is *guaranteed* to fit the forecast at least as well as Luo, and is therefore more exposed when
> the forecast is wrong. Luo's 6 h constraint is not merely a limitation — it is regularisation.

The route split identifies the mechanism: the Atlantic gives SR 4–5× more freedom per Luo block and
carries 3× the forecast error. Malacca has neither, and SR wins 15/15.

The two failure sets are related but distinct — verified, not assumed:

| | voyages |
|---|---|
| RH-SR worse than Naive | 11 |
| RH-SR worse than Luo | 12 |
| both | 8 |
| only vs Naive | 3 (sh 504, 1344, 3696) |
| only vs Luo | 4 (sh 168, 2184, 3192, 4200) |
| **union** | **15 of 41** |

All 15 are on the Atlantic; Malacca has none of either kind. So on **more than half** the Atlantic
voyages (15/26), fine-grained rolling-horizon planning loses to something simpler.

### Gates

| Route | SR all-pass | Luo all-pass | Luo failure mode |
|---|---|---|---|
| Indian Ocean | **15/15** | 4/15 | `rh_le_naive` ×10, `rh_ge_oracle` ×1 |
| North Atlantic | 15/26 | 17/26 | `rh_le_naive` ×9 |

---

## 3. The finding that explains the RH results

Decompose each voyage into the **optimisation span** available (Naive − oracle) and the **cost of
imperfect information** (RH-SR − oracle). What RH captures is the difference.

| Route | span (Naive − oracle) | forecast cost (RH-SR − oracle) | span captured |
|---|---|---|---|
| Indian Ocean | 9.66 mt (median 9.43) | 4.46 mt (median 3.94) | **54.2 %** |
| North Atlantic | 4.47 mt (median 4.04) | 3.90 mt (median 3.68) | **1.9 %** |

On the Atlantic the forecast error consumes ~87 % of the entire span, and **in 11 of 26 voyages it
exceeds the span completely** — which is exactly the 11 voyages where RH-SR loses to Naive. On
Malacca that never happens: 0 of 15.

So the value of rolling-horizon planning is not "how rough the weather is". It is **whether the
optimisation span exceeds the forecast error.** On Malacca the span is more than twice the error and
RH captures half of it; on the Atlantic they are nearly equal and RH captures essentially nothing.

That is a sharper and more useful statement than the published "RH saves 1.8 %", and it is
quantitative rather than directional.

---

## 4. What changes in the paper's conclusions

### Strengthened

- **SR > Luo under perfect foresight: 41/41.** Was 35/35. But per §1 this is *guaranteed* by the
  nesting, so the strengthening is in the **magnitude and its CIs**, not in the count. The claim
  should be restated as a property of the formulation (see §8.2).
- **"Luo re-planning does not pay" — confirmed, and far more sharply.** The §8.2 diagnostic:

  | Route | SR first-block revisions | Luo first-block revisions |
  |---|---|---|
  | Indian Ocean | 274 / 690 | **464 / 690** |
  | North Atlantic | 288 / 702 | **557 / 702** |

  Luo revises roughly twice as often as SR and still gains nothing (−0.12 % / +0.10 %), failing
  `rh_le_naive` on 19 of 41 voyages. The published figures were 17/27 vs 12/27; the new ones rest on
  1,392 re-plans instead of 27.
- **Malacca RH: 15/15**, up from 6/7. RH-SR now saves on every Indian Ocean voyage.

### Weakened, and must be rewritten

- **RH on the Atlantic.** Published: −1.8 %, 11/12. Now: **−0.26 %, 15/26.** Decomposing partition
  from voyage count on the same 12 voyages the paper used: `geo` −1.80 % → `waypoint` −0.58 %, so
  **most of the change is the partition, not the added voyages**. The remaining drift to −0.26 %
  comes from the 14 later voyages.
- **"RH saved on 17 of 19 voyages."** Now 30 of 41, and the failures are concentrated entirely on the
  harsh route.
- **"SR re-planning saved fuel; Luo re-planning did not."** On the Atlantic RH-SR now loses to
  RH-Luo on **12 of 26** voyages. The sentence is true on Malacca and false on the Atlantic.
- The implicit expectation that RH helps *more* in rough weather is now **contradicted**: it helps
  more on the mild route, and on the harsh route fine-grained re-planning loses to something simpler
  on 15 of 26 voyages.

### Already retired for other reasons

The six "gap grows with weather variability" claims are deleted per the migration design §5 — no
evidence supports any scaling claim yet. The RH results above independently reinforce that: the two
routes again move in opposite directions under the partition change, exactly as in PF.

---

## 5. The pattern across both experiments

The `geo → waypoint` switch moves the two routes **oppositely, in both experiments**:

| | Malacca | Atlantic |
|---|---|---|
| PF: SR fuel | 347.07 → 345.46 (better) | 196.33 → 198.78 (worse) |
| PF: SR − Luo gap | −1.77 → −2.43 % (wider) | −2.54 → −1.40 % (narrower) |
| RH: SR vs Naive (same 12/7 voyages) | −1.30 → −1.67 % (better) | −1.80 → −0.58 % (worse) |

One mechanism plausibly drives all six cells: Atlantic `waypoint` blocks are 5.04 nm, giving SR
**10.7–15.5 legs per 6 h Luo block**, while Malacca's 27.15 nm blocks give 2.0–2.9. The Atlantic is
being planned at a resolution far finer than either the time grid or the forecast can resolve, so the
extra resolution buys nothing while the switch from cell-averaged to point weather bites.

**This is a hypothesis, not a result.** It is consistent with all six cells but has not been
isolated. Two cheap tests, both in the migration design:

1. **Point-weather probe (~30 min):** re-run `geo` with the cell's source-node value instead of the
   cell average. If SR then matches the `waypoint` figure, weather assignment explains everything and
   granularity contributes nothing.
2. **Stride sweep:** vary block length on `waypoint` with the weather rule held fixed. The only clean
   granularity manipulation available.

Until one of them lands, §7.1 and §7.2 should report the numbers without asserting a mechanism.

---

## 6. Not affected by the partition

- §7.3's supporting observations — forecast RMSE growth with lead time, and the 86 % identical-query
  rate — are measured on the raw weather, not the graph. They stand as published.
- **Course changes as decision points — verified a non-issue.** Every route control point is exactly
  a weather sample point (13/13 Malacca, 11/11 Atlantic, delta 0.000000), because the interpolated
  waypoints were produced by subdividing each control-point leg. So turns already carry an H-line and
  `segment_heading` picks up the new leg's bearing immediately; it matches the route's own headings to
  within 0.88° worst case. The single control point that places no H-line is Malacca's *last* sample
  (Port B, the known marine-NaN endpoint), not an interior turn.
  Residual, worth one sentence in the limitations: because `C_beta` is a step function of the
  bow-relative angle (0–30 / 30–60 / 60–150 / 150–180), that 0.88° can straddle a category boundary.
  Worst case over all heading × wind combinations is 0.22 kn at BN 4, 0.72 kn at BN 7 and 1.95 kn
  (16.3 % of SWS) at BN 8 — rare, but a property of the published coefficient table, not of our
  partition.
- The convexity argument itself. What changed is which measurements support which claim, not the
  theory.

---

## 7. Outstanding

- **Python ↔ C++ bit-exactness has not been re-established on `waypoint` at scale.** Both engines
  were changed for the partition and single voyages matched at the time, but the repaired golden
  matrix covers C++ only. These are about to become the paper's only numbers; the check is cheap.
- The `--sample_stride` flag (design §4) lands in both engines and needs the same treatment.
- §7.1/§7.2 prose is blocked on the mechanism question in §5 above.

---

## 8. How to present this — presentation design

The results have changed shape, not just value. The old paper had one finding repeated in six places
("SR wins, and wins more in rough weather"). The new results have **three distinct findings**, and
the middle one is the strongest. Presenting them in the old structure would bury it.

### 8.1 The three findings, in the order they should appear

| # | Finding | Where it belongs | Status |
|---|---|---|---|
| 1 | SR ≤ Luo is guaranteed by construction; the magnitude is 2.43 % / 1.40 % | **Methods**, then §7.1 for magnitude | theorem + measurement |
| 2 | Under real forecasts SR loses to Luo on 12/26 Atlantic voyages — nesting holds in-sample, fails out-of-sample | **§7.2, promoted to the paper's main empirical result** | measurement |
| 3 | The crossover is governed by span vs forecast error (54 % captured vs 1.9 %) | **§8**, as the mechanism uniting 1 and 2 | measurement + mechanism |

### 8.2 Move the dominance claim out of Results

Presenting "SR beat Luo on 41 of 41 voyages" as a *result* now understates and misdescribes it. It is
a property of the formulation (§1 of this document), and a referee who notices the nesting will ask
why it was reported as an empirical finding.

**Proposed:** a short paragraph in §5 (Methods) stating the nesting and its consequence, then §7.1
reports only the **magnitude** and its distribution. The sentence "the directional signature of
Jensen's inequality, not an average tendency" (line 1109) should go — direction is guaranteed;
Jensen explains the *size*, which is the part worth arguing.

### 8.3 Promote the RH reversal to the headline

Currently §7.2 says "SR re-planning saved fuel; Luo re-planning did not." That is now true on
Malacca and false on the Atlantic. Rewriting it as a bare correction wastes the finding.

**Proposed framing:**

> Rolling-horizon planning at fine granularity is not uniformly beneficial. On the mild route SR
> re-planning saved fuel on every voyage; on the North Atlantic it lost to the block-locked
> formulation on 12 of 26 voyages and to a constant-speed baseline on 11 of 26. Because SR's
> feasible set contains Luo's, SR necessarily fits the forecast at least as well — and is therefore
> more exposed when the forecast is wrong. The block constraint acts as regularisation.

This converts a weakened claim into a sharper one, and it is the kind of negative-and-explained
result that survives review.

### 8.4 Tables

| Table | Change |
|---|---|
| `tab:modec` | regenerate (`make_pf_tables.py --partition waypoint`); caption reports magnitude, not direction |
| `tab:modec-r1/r2` | regenerate, 15 and 26 rows |
| `tab:rh` | regenerate, **add two columns**: "RH-SR worse than Luo" and "RH-SR worse than Naive" — the failure counts are the finding and must be visible in the summary table, not only in prose |
| `tab:rh-r1/r2` | regenerate, 15 and 26 rows |
| **new** | span-vs-error table (§3 of this document): span, forecast cost, % captured, and voyages where cost exceeds span |

### 8.5 One new figure, and only one

The span-vs-error decomposition is the paper's mechanism and it is currently invisible. A per-voyage
scatter — **x = optimisation span (Naive − oracle), y = forecast cost (RH-SR − oracle)** — with the
45° line drawn, puts every voyage in one of two regions: below the line RH pays, above it RH loses.
Malacca clusters well below; the Atlantic straddles it with 11 points above.

That single figure carries findings 2 and 3 together and makes the crossover visual rather than
tabular. It replaces nothing — the paper currently has no figure for the RH section.

Everything else stays tabular. Resist a granularity figure until the stride sweep exists; there is
no dose–response to plot yet.

### 8.6 Claims to delete outright

Per the migration design §5, the six "gap grows with weather variability" claims are deleted, not
reworded — no scaling evidence exists. The RH results reinforce this: the routes again move in
opposite directions, and the Atlantic's *larger* weather variability now goes with a *smaller*
SR advantage in both regimes.

### 8.7 What the abstract should say

The current abstract claims a saving that "grows with weather variability", on nineteen voyages.
Proposed replacement scope, without inventing anything not measured:

- SR's per-leg formulation dominates the block-locked formulation by construction, and by 1.4–2.4 %
  of voyage fuel in practice, over 41 voyages on two routes.
- Under real forecasts that advantage is conditional: it holds throughout on the mild route and
  reverses on more than half the North Atlantic voyages.
- The governing quantity is the ratio of optimisation span to forecast error, which we measure.

### 8.8 Ordering constraint

Findings 2 and 3 depend on the RH run being on the same partition as the PF run — which is true for
the first time in this run set. Any future re-run must keep them paired; reporting a `waypoint` PF
table beside a `geo` RH table would silently break the span-vs-error decomposition, since the span is
computed from the PF oracle.

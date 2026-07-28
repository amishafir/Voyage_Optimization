# DDD-for-SR: certifying the discretisation gap — experiment plan + candidate section

*2026-07-28 · follows T25–T26 (running log). Goal: measure/certify the distance between our
grid-restricted DP optimum `F_DP` and the true continuous-𝒱 optimum `F*`, using the method family of
Michael Hewitt (EiC, Transportation Science): Dynamic Discretization Discovery (DDD). If the certified
gap ≪ the SR–Luo gap (1.9–2.8 %), we gain a new paper section + a Related-Work addition.*

---

## 1. The question, precisely

Our DP restricts decision points to the (δ=1 NM, τ=0.1 h) grid of Eq. (4). The continuous problem lets
the vessel cross each mandatory line (cell boundary / 6 h block / T) at **any** point, with any speed
in 𝒱. So:

```
F*  ≤  F_DP            (our solution is feasible ⇒ an UPPER bound)
gap = F_DP − F*        (unknown — “is there a better speed between two nodes?”)
```

We cannot compute `F*`, but we can compute a **rigorous lower bound `LB ≤ F*`**, giving the
certificate `gap ≤ F_DP − LB`.

**Key structural fact (from §4 preamble):** within a rectangle (one cell × one block) the optimal
speed is constant, so a continuous-optimal trajectory makes decisions **only at mandatory-line
crossings**. The continuous problem is therefore: *choose the (continuous) crossing coordinate on each
line encountered*. That is exactly the object DDD relaxes.

## 2. The LB construction (interval relaxation, à la Marshall–Boland–Savelsbergh–Hewitt 2021)

**States:** partition each mandatory line into **intervals**. Crucially, the mandatory crossings
(where distance lines meet time lines) are always interval boundaries ⇒ **an interval never straddles
a rectangle** ⇒ the weather/heading (hence φ) of any transition out of an interval is well defined.
The **coarsest sound partition is “one interval per rectangle edge”** — a tiny graph
(≈ 2·M·Θ intervals; Route 1 ≈ 15 k).

**Arcs:** interval I → interval J on the *first* line(s) ahead (in the continuous world every
distance line is resolvable — the grid-era glide-past corner does not exist here). Arc exists iff
*some* constant-speed transition with v ∈ 𝒱 connects a point of I to a point of J.

**Arc cost = certified minimum fuel over the transition family:**
```
c(I→J) = min { φ(rect; v)·Δt  :  p∈I, q∈J, v = Δd/Δt ∈ 𝒱 }
```
With fuel-per-mile `φ(v)/v` convex in v over 𝒱 (cubic FCR), this is a **1-D convex minimisation**
(ternary search / closed form) — cheap and rigorous.

**Soundness (the LB argument):** any continuous trajectory crosses the lines at points p₀,p₁,…; each
pᵢ lies in some interval; each true leg is a member of its arc’s transition family, so
`c(arc) ≤ true leg fuel`. Arrival is checked against the interval’s **lower** end (optimistic).
Hence `shortest-path(interval graph) = LB ≤ F*`. No probabilistic argument, no asymptotics — an
inequality per leg.

**Refinement (the “discovery” in DDD):** solve → take the LB path → bisect the intervals it uses
(or, DDD-style, add exactly the crossing coordinates at which the path’s legs are mutually
inconsistent) → re-solve. `LB_k` increases monotonically; stop when `F_DP − LB_k` stabilises or a
target ε is hit. Optional bonus: **repair** the LB path into a feasible schedule — if that ever beats
`F_DP`, we have *improved our own solution*.

## 3. The experiment (three stages, cheapest first)

| # | What | How | Cost | Output |
|---|---|---|---|---|
| **E1** | Empirical convergence (grid halving) | Re-run SR node-first at `--zeta_nm 0.5 --tau_h 0.05` (code keeps the ζ flag name) on R2 vy0 + R1 vy0; compare `F_DP` | minutes (existing code) | `ΔF` under h→h/2; Richardson-style residual estimate (T25 layer c) |
| **E2** | Certified LB, coarsest level | New script `pipeline/dp_rebuild/ddd_lb.py`: rectangle-edge interval graph, convex-min arc costs, shortest path | ~300 lines; seconds to solve | `LB₀`, certified `gap₀ = F_DP − LB₀` |
| **E3** | Refinement loop | Bisect along LB path, k rounds (k ≤ ~10) | minutes | `LB_k` ↑, converged certificate; refinement heat-map (where the gap lives — prediction: cell corners / weather fronts) |

**Instances:** Route 2 vy0 (`F_DP = 202.484`, small) first; Route 1 vy0 (`F_DP = 353.955`) to confirm.

**Success criteria:**
- E1: `|ΔF| ≲ 0.1 %` (expected from T19’s O(h²): per-leg speed quantisation ~1 % ⇒ fuel error ~10⁻⁴).
- E2+E3: converged certified gap **≤ 0.5 %**, ideally ≤ 0.1 % — i.e., at least ~4–25× smaller than the
  SR–Luo gap. That sentence *is* the new section’s punchline.

**Risks / honesty notes:**
- `LB₀` will be loose (interval min is over a whole rectangle edge); the claimable number is the
  *converged* `LB_k`. If refinement stalls with a gap ~ the SR–Luo gap, we report E1 only and frame
  DDD as future work (still a defensible outcome — nothing overclaimed).
- The convex-min arc cost must use the *source* rectangle exactly as the DP does (same φ convention),
  or the bound compares different models.
- Weather NaN cells (Port-B gap) need the same fallback as the DP, else LB/UB mismatch.

## 4. The candidate new section (write only if E2/E3 succeed)

**Placement — three coordinated touches, smallest sufficient footprint:**

1. **§2.1 Related Work (granularity axis), +2 sentences:** the tension between discretised
   time-expanded models and continuous-time optima is studied head-on by the DDD line
   (Boland–Hewitt–Marshall–Savelsbergh 2017, OR; Marshall et al. 2021, TranSci — partial networks
   < 1 % of the full expansion), and by convexity-certified ε-optimal speed optimisation
   (Wang & Meng 2012 — already cited; Meng et al. 2019, TR-B). We adopt their *certificate* viewpoint.
2. **New §4.2.5 “Certifying the discretisation gap”** (~half page): the interval relaxation, the arc
   cost min, the soundness inequality, the refinement rule. One displayed equation (`c(I→J)` above).
3. **§6 addition (one table + one paragraph),** e.g. §6.1.1 or a short §6.4:

   | Voyage | F_DP (mt) | LB (mt) | certified gap | SR–Luo gap |
   |---|---|---|---|---|
   | R2 vy0 | 202.48 | *(E3)* | *(≤ x %)* | 3.7 % |
   | R1 vy0 | 353.96 | *(E3)* | *(≤ x %)* | 2.1 % |

   Punchline sentence: *“The granularity advantage is an order of magnitude larger than the certified
   discretisation error — the gap between SR and the per-block baseline is not grid noise.”*
4. **§4.2.1 tweak:** replace the “timing error … negligible next to the FCR accuracy” hand-wave with a
   pointer to the certificate.

**Literature-review filing (per .claude/rules/literature-review.md — validation BEFORE filing):**
- Run `/lit-validate` (or the `lit-reviewer` agent) on: Boland et al. 2017 (OR, DOI
  10.1287/opre.2017.1624); Marshall et al. 2021 (TranSci, DOI 10.1287/trsc.2020.0994); Hewitt 2019
  (TranSci); Boland et al. 2019 “The price of discretizing time” (EJTL); Meng et al. 2019 (TR-B).
- Pillar: **1** (speed-optimisation & granularity methods), tags `DP-based`, `speed-optimization`;
  gap framing: “certificates for discretised optima exist in SND/liner-speed settings; none applied to
  per-cell weather-adaptive speed control — we adapt DDD’s relaxation to the time–distance grid.”

## 5. Order of work

1. **E1 now** (existing flags, ~30 min incl. both voyages).
2. **E2 prototype** (`ddd_lb.py`) — the main build.
3. **E3 refinement** + numbers table.
4. Decision point with Tal: section in this paper vs future-work note (depends on numbers + space).
5. If “in”: lit-validate the five refs → file to Pillar 1 → write §4.2.5 + §6 table + §2.1 sentences.

---

## 6. E1 RESULTS (2026-07-28) — motivates E2 rather than replacing it

| Instance | 2δ,2τ | δ,τ (paper) | δ/2,τ/2 |
|---|---|---|---|
| R2 vy0 | 203.118 (+0.313%) | **202.484** | 202.644 (+0.079%) |
| R1 vy0 | 355.721 (+0.499%) | **353.955** | 354.208 (+0.071%) |

- **Scale:** the h→h/2 spread is ~0.07–0.08 % — ~30× smaller than the SR–Luo gap. Coarsening to 2h
  costs 0.3–0.5 % (asymmetry consistent with O(h²) + feasible-set effects).
- **Non-monotone refinement (important):** the fine grid came out *above* the paper grid, although its
  node set is a superset. Cause: the **arc sets are not nested** — finer τ makes more distance lines
  resolvable (fewer glide-past arcs) and tightens band-edge rounding. Consequence: Richardson
  extrapolation is unreliable here ⇒ **the certified LB (E2/E3) is genuinely needed**, not decorative.
  This is the honest narrative for the section: "grid sensitivity is ~0.1 % empirically, but
  non-monotone; the relaxation certifies it."
- **Feasibility audit (pre-requisite for a certificate): PASS.** Optimal schedules use speeds strictly
  inside 𝒱 with ~0.7–0.9 kn margin (R2: [9.51, 13.91] in [8.64, 14.64], 0 violations; R1:
  [10.07, 14.21] in [9.12, 15.12], 0 violations). No band-edge cheating ⇒ F_DP is a legitimate UB.

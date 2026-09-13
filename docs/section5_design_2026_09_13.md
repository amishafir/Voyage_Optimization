# Design — rewrite of §5.1.2 to the end of §5

**Date:** 2026-09-13
**Scope:** `paper_full_draft.tex` lines 776–877 (from `\subsubsection{Sea conditions data}` to the
line before `\section{Results}`). §6 Results is **not** designed here.
**Inputs read:** `paper_full_draft.tex` (§3 239–312, §4 404–600, §5 720–877, §6 879–1100, §8–§9
1101–1200), `docs/waypoint_results_2026_09_09.md`, `docs/waypoint_migration_design.md`,
`.claude/skills/paper-style/SKILL.md`.
**Status:** design only. No LaTeX written. Nothing applied to the draft.

> Numbering note: `waypoint_results_2026_09_09.md` refers to Results as §7 and Discussion as §8.
> In the current draft they are **§6** and **§7**. All section numbers below follow the *current
> draft*: §4 Methods, §5 Data and experimental design, §6 Results, §7 Discussion.

---

## 0. The one-paragraph version

§5 currently spends its last 100 lines describing an experiment that was not run, in a partition it
does not name, with voyage counts that contradict §6, and it omits the two facts that make §6
readable: **the nesting** (why SR ≤ Luo is a theorem) and **the spatial-sampling asymmetry**
(why the two routes cannot be compared). The rewrite deletes one whole paragraph, rewrites three,
adds one new subsubsection and one new table, and comes out **shorter** than what it replaces.

**Proposed net change: −38 lines of stale/contradictory prose, +26 lines of new material, +1 table.**

---

## 1. Proposed structure

Current (lines 776–877):

```
5.1.2  Sea conditions data                    776–810   [~35 lines; last 3 are fiction]
5.2    Experimental design (intro + band)     813–830
5.2.1  Speed-decision granularity             832–847
5.2.2  Information regime                     853–862
5.2.3  Evaluation protocol                    864–876
```

Proposed:

```
5.1.2  Sea conditions data                    ~18 lines   (was 35)
5.1.3  Spatial sampling and the decision partition   ~14 lines   NEW
       + Table 3 (route and instance summary)                    NEW
5.2    Experimental design (intro + speed band + zero slack)  ~8 lines  (was 18)
5.2.1  Planners compared                      ~20 lines   (was "Speed-decision granularity", 16)
5.2.2  Information regimes                    ~14 lines   (was 10)
5.2.3  Evaluation protocol                    ~12 lines   (was 13)
5.2.4  Reported quantities                    ~12 lines   NEW
```

Target for §5.1.2–end: **~950 words + one table**, against ~1,250 words today.

### 5.1.2 Sea conditions data — *keep the name, halve the length*

**Intent.** Provenance and cadence of the weather record, in three short paragraphs: (a) source and
native grids; (b) what was collected — actual and predicted, 6 h **collection** cadence, ~170 days,
168 h horizon at hourly lead resolution; (c) the refresh-cycle measurement (86 % / 97 % identical
consecutive hourly queries) that fixes the 6 h **re-plan** cadence.

**Must establish.** That the predicted record is a real operational forecast archive, not a
perturbation model; that the archive supplies a value roughly every 4.8 nm and every hour, so any
coarser granularity downstream is *our* choice; that 6 h re-planning is set by the wind model's
cycle, not tuned.

**Sets up in §6.** §6.2's rolling-horizon arm exists only because a genuine predicted record exists;
§6.3's "forecast cost" term is only meaningful if the forecast is operational. The 86 %/97 % figure
is §6's answer to "why not re-plan hourly".

**Cut.** The "between 3 and 5 NM" hedge (harmonise to ~4.8 nm / 0.08°, matching §3's "roughly 5 NM");
the sentence at 779 about the 6 h interval being a tractability choice (it collides with 804–805 —
see §5 below); the bullet formatting (two bullets become two clauses).

### 5.1.3 Spatial sampling and the decision partition — **NEW, and the most important addition**

**Intent.** State, plainly and in one place, that Route 1 was sampled every 25.0 nm (131 points) and
Route 2 every 5.0 nm (389 points), against a source grid that could have supplied ~4.8 nm on both;
that decision boundaries are placed at the weather sample points, giving mean block lengths of
27.15 nm and 5.04 nm; and that each 6 h time block therefore contains 2.0–2.9 SR legs on Route 1 and
10.7–15.5 on Route 2. Then the partition fact: every route control point is exactly a weather sample
point (13/13 and 11/11, delta 0), because the interpolated sample points subdivide each control leg,
so every heading change already carries a decision boundary and the leg heading matches the route's
own to within 0.88°.

**Must establish.** (i) The sampling asymmetry is a **data-collection limitation**, stated as such —
Route 1's blocks are 27 nm because that is how often it was sampled, not because the weather is known
to be uniform over 27 nm. (ii) That the asymmetry **confounds the cross-route comparison**: the two
routes differ in block length by 5.4× *and* in weather regime, in opposite directions, so no
cross-route ordering can be attributed to either. (iii) That SR's per-leg freedom is real (turns
carry boundaries), which licenses §5.2.1's "adapts to each change of heading or sea conditions".

**Sets up in §6.** Every route difference in §6. Specifically:
- §6.1: why the magnitude differs between routes (−2.43 % vs −1.40 %) **without** the retired
  "grows with weather variability" claim.
- §6.2: why the Atlantic is where RH-SR fails — 4–5× more freedom per Luo block.
- §6.3: the reader needs the block-length contrast in hand before the span/cost table lands.

**Also fixes two defects outside §5.** §3 line 247 ("the space to *cells* of 0.08° × 0.08°") and §4
line ~412 ("Each time the route crosses a 0.08° latitude or longitude line, a new subsegment starts,
so a subsegment is about 5 NM long") are **true of Route 2 only**. §5.1.3 is where that is
reconciled; §3 and §4 need a qualifying clause each (out of scope here, flagged in §6 below).

**Terminology decision required.** The word "waypoint" is doing three jobs: the 13/11 route control
points in Table 2, the ~131/389 interpolated weather sample points, and the name of the partition in
the code (`waypoint` vs `geo`). §5.1.3 must fix a vocabulary and §5 must use it throughout.
Recommended: **control point** (13/11, Table 2), **sample point** (131/389, where weather is
observed and where decision boundaries sit), **block** (the interval between consecutive sample
points). The partition name never appears in the paper.

### 5.2 Experimental design — intro, speed band, zero slack

**Intent.** One sentence naming the design: three planners × two information regimes, with Naive
identical under both by construction. Then the speed band ($D/T \pm 3$ kn, Eq. speed-set) and the
zero-slack statement, both of which are already well written at 824–830.

**Cut.** The dead `\begin{comment}` block at 816–822 (the superseded "61 SOG values" text). It has
served its purpose; leaving it invites a future editor to re-enable the wrong version.

**Change.** "two independent axes: the *granularity* of the speed decision and the *information*
available" → keep the two-axis framing but say "three planners", because Naive is not a granularity
setting of the same DP.

### 5.2.1 Planners compared — *rename from "Speed-decision granularity"*

**Intent.** SR, Luo, Naive, in that order; then the nesting corollary.

**Must establish.**
1. SR = the DP of §4 applied without restriction (keep 833–835 nearly as is; the "adapts to each
   change of heading or sea conditions" claim is **verified correct** and now supported by §5.1.3).
2. Luo = the block-locked lattice, implemented **independently** from the published description
   (keep 837–845 — this is a fidelity claim and it survives intact).
3. Naive = fixed mean SOG $D/T$ through actual weather, no optimisation, no re-planning; and — worth
   one clause — because Naive is SOG-targeted it also arrives exactly at $T$, so it sits at equal
   voyage time with the other two.
4. **The nesting corollary**, instantiated: on these two routes the DP's time lines are the 6 h grid
   and are exactly Luo's blocks (47 on Route 1, 28 on Route 2 — identical counts); both draw speed
   from the same band; Luo's per-block distance quantum equals SR's distance snap (1.0 nm).
   Therefore the antecedent of the §4 lemma holds here, SR's feasible set contains Luo's, and
   SR ≤ Luo is guaranteed whenever the planning weather equals the evaluation weather.

**Sets up in §6.** §6.1 reports magnitude only, citing this corollary for the sign. §6.2's
overfitting argument is the same corollary applied to the forecast: SR provably fits the forecast at
least as well as Luo, hence is more exposed when the forecast is wrong; Luo's block acts as
regularisation.

**Critical drafting note — the two claims are not in conflict, and both must be stated.**
"Implemented independently, not as SR subject to an added equality constraint" is a claim about the
*implementation*: two separate solvers, separate lattices, separate arc evaluation. "SR's feasible
set contains Luo's" is a claim about the *mathematics* of the two feasible sets. A referee who reads
only the first will ask why the 41/41 is presented as evidence; a referee who reads only the second
will ask whether Luo was crippled. Say both, adjacently, and say explicitly that they are
compatible. Suggested one-liner for the draft: *"The two solvers share no code; the containment is a
property of their feasible sets, not of the implementation."*

**Rewrite required at 846–847.** Current: *"Any fuel difference from SR is therefore attributable to
decision granularity alone."* This is true **within an instance** and false **across routes** — and
as written it is exactly the licence for the six retired "gap grows with weather variability"
claims. Replace with a scoped version: within an instance both planners see the same weather values,
the same band and the same arrival constraint, so the difference is attributable to decision
granularity; across routes the comparison is confounded by §5.1.3.

### 5.2.2 Information regimes

**Intent.** Two regimes, defined precisely enough that §6.3's decomposition is unambiguous.

**Must establish.**
1. **Perfect foresight (oracle).** The planner sees the **time-varying actual weather along the whole
   voyage** — the active sample hour advances with voyage time, so a leg sailed at hour 96 is costed
   against the conditions actually realised at hour 96 at that location. This is an upper bound on
   achievable advantage, not a snapshot.
2. **Rolling horizon.** Re-solved at 6 h steps; the first 6 h block is planned against actual
   (nowcast) weather and the remainder against the most recent predicted cycle; only the first block
   is committed; realised fuel is the sum of committed blocks. Both SR and Luo are exercised here;
   Naive does not re-plan and is unchanged.
3. **Scope sentence.** There is **no "plan once from the departure forecast and sail it" arm.** Say
   so in one clause here, and list it in §7 Limitations. Do not let the text imply one exists.

**Sets up in §6.** §6.1 is the oracle arm. §6.2 is the RH arm. §6.3's span (Naive − oracle) and
forecast cost (RH-SR − oracle) are differences *between these two regimes*, so both must be defined
before §6.3 can be read.

**Rewrite required at 854–855.** Current: *"Each leg is evaluated against the actual weather recorded
at the voyage's departure sample hour, giving the planner perfect knowledge of conditions."* This
reads as a frozen departure snapshot and is **misleading**. It is also internally inconsistent: if
the oracle used a frozen snapshot, the RH arm's first-block nowcast could not agree with it, and the
verified fact that the RH harness reproduces the PF solve to the reported precision would be
impossible.

### 5.2.3 Evaluation protocol

**Intent.** The chain, the counts, and why the comparison is paired.

**Must establish.**
1. Consecutive-voyage chain: voyage $N{+}1$ departs at the sample hour at which voyage $N$ arrives;
   the step is the ETA. Because the arrival constraint binds with zero slack for **every** planner,
   all planners share the same departure hours, so the chain is common to all — that is the
   pairing, and it is what makes per-voyage differences meaningful.
2. **One ETA per route**: 280 h on Route 1, 168 h on Route 2 (implying mean SOG of 12.1 kn and
   11.6 kn respectively, both inside the engine envelope). ETA is a fixed property of each route in
   this study, not a varied factor.
3. **41 voyages: 15 on Route 1 + 26 on Route 2**, departures derived from the extent of the
   collected data rather than hardcoded, spanning the full ~170-day collection window.
4. **Both regimes cover all 41 voyages** — there is no longer a "19-voyage subset".
5. One sentence that the PF and RH runs use the same partition and the same voyages, and that the
   RH harness reproduces the PF solve to the reported precision. This is what licenses §6.3 to
   subtract a PF oracle from an RH result.

**Sets up in §6.** Every count in §6: 41/41, 12/26, 11/26, union 15/26, 0/15, 11/26.

### 5.2.4 Reported quantities — **NEW, small, and §6.3 is unreadable without it**

**Intent.** Define, once, the quantities §6 reports:
- **realised fuel** — fuel accumulated by sailing the committed plan through the actual weather;
- **optimisation span** = Naive − oracle, the fuel a perfect planner could have saved;
- **forecast cost** = RH-SR − oracle, the part of that span lost to imperfect information;
- **share of span captured** = 1 − cost/span;
- the per-voyage failure criteria §6.2 counts: RH-SR worse than RH-Luo, RH-SR worse than Naive, and
  their union — all on realised fuel, paired by departure hour;
- **aggregation convention** — ratio of means (matching the published convention), stated
  explicitly, with a note that mean-of-percentages differs slightly;
- **uncertainty convention** — 95 % paired bootstrap CI, currently buried in `tab:modec`'s caption.

**Sets up in §6.** §6.3 entirely; §6.1's CIs; §6.2's counts.

**Alternative placement.** These four definitions could open §6 instead. Recommendation: **§5**,
because (a) §6 should open with a result, not with definitions, and (b) the span/cost decomposition
is a *design* choice about what is measured, which is §5's job. If the authors prefer §6, the
subsection folds into §6's opening paragraph unchanged — but it must exist somewhere, and it does
not exist today.

---

## 2. Where the nesting result belongs

**Recommendation: split it. The lemma goes in §4 Methods; the instantiation goes in §5.2.1.**

**§4 Methods, after the shortest-path reading (currently ends ~line 580).** State it generally and
conditionally, in three or four sentences, with no route numbers:

> If a competing formulation restricts the speed to be constant over intervals whose endpoints are a
> subset of the DP's time lines, and draws its speeds from the same band on the same distance
> quantum, then every plan it admits is reproducible by the DP — hold that speed on every sub-arc
> inside the interval. The DP's feasible set therefore contains the competitor's, and the DP's
> optimum is no worse whenever both are optimised against the same weather.

**Why §4 and not only §5.** The statement is about $\mathcal{S}$, $\mathcal{A}(t,d)$ and
$\mathcal{V}(d)$ — objects that exist only after §4.1. Stating it in §5 would force §5 to re-import
the state space. It is also a property of the *formulation*, and §4 is where properties of the
formulation live (the convexity argument is already there). Finally, it belongs beside the
shortest-path reading, which is the other structural remark in §4 and reads as its natural sibling.

**Why the instantiation must nevertheless be in §5.2.1.** The antecedent is an *experimental* fact:
that the 6 h time lines coincide with Luo's blocks (47 and 28), that both use $D/T \pm 3$ kn, and
that the distance quanta agree at 1.0 nm. Those are route- and configuration-specific and have no
business in Methods. §5.2.1 verifies the antecedent and draws the corollary in two sentences.

**Why not §6.** `waypoint_results_2026_09_09.md` §8.2 is right that presenting "41 of 41" as a
*result* misdescribes it, and a referee who spots the nesting will ask why. Putting the lemma in §6
would repeat that error one section later.

**Consequence to carry into §6 (not designed here, noted for coherence).** §6.1 reports the
magnitude and its distribution only. The sentence at line 1109 of §7.1, *"the directional signature
of Jensen's inequality, not an average tendency"*, should go: direction is guaranteed; Jensen
explains the *size*.

---

## 3. Claim-by-claim disposition of the existing text

| Lines | Claim / text | Disposition | Reason |
|---|---|---|---|
| 720–723 | §5 intro: "We first present the input data … as well as the forecast data applicable for the dynamic and **stochastic** version of the speed optimization." | **Rewrite** | "stochastic" contradicts Contribution 2 (line ~207: "without assuming any probabilistic model linking forecast to realisation"). Nothing in the paper is stochastic. Also "bench marked" typo. Compress to two sentences. |
| 725–727 | §5.1 "Data" + "In this section we describe the input data that constitute our test bed problem instances:" | **Delete the sentence** | Verbatim restatement of 723, three lines later. |
| 729–736 | Two routes, lengths 3,393 / 1,955 nm, pointers to figure and table | **Keep**, add ETA | Lengths are needed for $D/T$. Add ETA + implied mean SOG here or in the new Table 3. |
| 738–744 | `fig:routes` | **Keep** | Only route figure; still correct. |
| 746–773 | `tab:waypoints` (13 + 11 rows) | **Keep, retitle** | Retitle "Route control points"; the caption must not call them waypoints once §5.1.3 distinguishes control points from sample points. |
| 776–779 | Open-Meteo / NWP provenance; "native grids of approximately 0.08° — between 3 and 5 NM"; 168 h horizon at hourly lead | **Rewrite (compress)** | Keep provenance and horizon. Harmonise "3 to 5 NM" with §3's "roughly 5 NM" and with the ~4.8 nm figure the sampling argument uses. |
| 779 | "The 6 h interval used throughout this study is a sampling choice made for tractability and API budget, not a property of the source data." | **Rewrite** | Collides head-on with 804–805 (see §5, contradiction C2). Disambiguate as the *collection* cadence. |
| 781–787 | Wind bullet: automatic model selection, octahedral reduced-Gaussian, 0.0703° rows / 0.1584° within-row, ~9 km, ECMWF IFS, 6 h refresh | **Keep, compress to ~3 lines** | This is the evidence that the source could supply ~4.8 nm. It now *matters* because §5.1.3 claims Route 1 took one point in five. Drop the bullet, keep the grid description and the IFS identification. |
| 788–789 | Currents bullet: Météo-France SMOC, 0.08°, daily refresh | **Keep, compress to 1 line** | Same. The 24 h refresh justifies why 6 h is set by *wind*, not currents. |
| 792–798 | "two records were collected at every **waypoint** on a 6 h sampling cadence over ~170 days … actual / predicted" | **Rewrite** | "waypoint" here means *sample point* (131/389), but Table 2 has just defined waypoint = control point (13/11). A reader concludes 13 sample points on Route 1 (contradiction C3). Otherwise the actual/predicted distinction is well put — keep it. |
| 800–805 | "NWP model refresh cycle" paragraph; 86 % / 97 % identical consecutive queries | **Keep, merge, relabel** | The measurement is good and §6 needs it. Fold into §5.1.2's third paragraph and label the cadence it justifies as the **re-plan** cadence. |
| 808–810 | "25 different departure times during the spring of 2026, spaced three days apart … $2\times25$ combinations … 3 ETA levels … 10, 12 and 14 NM … 150 instances" | **DELETE ENTIRELY** | Describes an experiment that was never run; contradicts the chain protocol three paragraphs later (C1); "NM" should be kn; the three ETA levels would give Route 1 ETAs of ~339/283/242 h, of which only the middle was run. **Recommend superseding, explicitly and without substitute.** Its one salvageable idea — that departure time changes the instance — is already carried by §5.2.3's chain. |
| 813–815, 823–830 | §5.2 opening; speed band $D/T\pm3$ kn; zero slack; the idle option never exercised | **Keep** | Well written. Reword "two independent axes" to name the three planners. |
| 816–822 | Dead `\begin{comment}` block (61 SOG values) | **Delete** | Superseded; risks being re-enabled. |
| 832–835 | SR definition; "adapts to each change of heading or sea conditions along the route" | **Keep** | **Verified correct**: every control point is a sample point (13/13, 11/11, delta 0), so turns carry a decision boundary; headings match the route's own to within 0.88°. §5.1.3 supplies the evidence. |
| 837–845 | Luo: lattice, block-constant SOG, arc cost by walking sub-segments, "implemented independently … not as SR subject to an added equality constraint" | **Keep** | Fidelity claim, still true and still necessary. Must sit adjacent to the nesting corollary with an explicit statement that the two are compatible. |
| 846–847 | "Any fuel difference from SR is therefore attributable to decision granularity alone." | **Rewrite (scope it)** | True within an instance, false across routes; as written it is the licence for the six retired scaling claims. |
| 849–851 | Naive definition | **Keep, extend one clause** | Add that Naive is SOG-targeted and therefore also arrives at $T$ — needed for the equal-voyage-time claim and for §6.3's span. |
| 853–856 | Perfect foresight: "the actual weather recorded at the voyage's departure sample hour" | **Rewrite** | Misleading frozen-snapshot reading; the oracle uses time-varying actual weather advancing with voyage time. Also internally inconsistent with the RH first-block nowcast. |
| 858–862 | Rolling horizon: 6 h steps, nowcast first block, predicted remainder, commit first only, cadence = NWP cycle | **Keep, add one clause** | Accurate. Add: no plan-once arm exists. |
| 864–867 | Chain protocol; "Fixing the step to the ETA guaranteed that every planner encountered identical departure weather at every voyage." | **Rewrite (expand the reasoning)** | The chain alone does not guarantee it; what guarantees it is that the arrival constraint binds with zero slack for all planners, so all arrive at $T$ and share the next departure. Two clauses, not one. |
| 868–872 | "thirteen … twenty-two … 35 in total … ~155 days. Rolling-horizon evaluation currently covers the original 19-voyage subset … extending it to the full 35 is left to future work" | **Rewrite** | Stale. Now 15 / 26 / 41, ~170 days, and **both** regimes cover all 41. |
| 872–876 | "At each departure SR and Luo were run under the perfect-foresight oracle and, on the 19-voyage subset, the 6 h rolling horizon …" + "differences are attributable to the experimental setting … not to sampling" | **Rewrite** | Same stale subset. The final clause ("not to sampling") is now dangerous next to §5.1.3, which says the *spatial* sampling differs by 5×. Disambiguate: it means voyage sampling, not weather sampling. |
| — | *(absent)* Spatial sampling asymmetry | **ADD** (§5.1.3) | See §1. |
| — | *(absent)* Nesting corollary | **ADD** (§5.2.1, lemma in §4) | See §2. |
| — | *(absent)* Reported quantities / span decomposition definitions | **ADD** (§5.2.4) | See §1. |
| — | *(absent)* Route/instance summary table | **ADD** (Table 3) | See §7. |
| — | *(absent)* Physics scope: waves are a descriptor, not a model input | **ADD** (one sentence, §5.1.3) | See §4. |

**Lines outside §5 that must move in lockstep** (flagged, not designed here):

| Lines | Issue |
|---|---|
| 247 (§3) | "the space to *cells* of 0.08° × 0.08°" — true of Route 2 only. Needs a qualifying clause pointing at §5.1.3. |
| ~412 (§4) | "Each time the route crosses a 0.08° latitude or longitude line, a new subsegment starts, so a subsegment is about 5 NM long." Same problem, stated more strongly. Must be softened to "at each weather sample point" with the spacing deferred to §5.1.3. |
| 1164–1172 (§7 Limitations) | Item (v) still says RH covers the 19-voyage subset. Also the right home for: no plan-once arm; single ETA per route; Route 1's 25 nm sampling; the 0.88°/`C_beta` step-boundary residual. |
| 1109 (§7.1) | "the directional signature of Jensen's inequality" — direction is now guaranteed. |

---

## 4. Physics scope — exactly one sentence, and it is nearly free

Sea state enters the speed model **only through the Beaufort number** (Kwon's method as used by
yang2020, Eqs 7–9). §3 line 247 already says the sea conditions are "the wind speed and direction,
summarised by the Beaufort number, and … the sea current speed and direction" — so the scope is
already correct in the paper. The only gap is that **significant wave height is collected and is
worth reporting as a route descriptor** while not being a model input, and the word "wave" currently
appears **nowhere** in the draft.

**Recommendation.** One clause in §5.1.3, attached to the route-descriptor table: significant wave
height is reported as a route descriptor only; it is not an input to the speed model, which takes
sea state through the Beaufort number.

**Do not concede yang2020's voluntary-speed-reduction constraint.** Its Eqs 11–13 / Constraint 21
belong to *its optimisation model*, which this study replaces with its own DP; this study adopts only
the speed-correction function. This is a scope statement, not a limitation, and it does not need to
appear in §5 at all — §3's FCR item already says the FCR function is taken as an input from
yang2020 and that its estimation is not this paper's contribution. **Recommend: say nothing further.**
If a referee raises it, the answer is a one-line rebuttal, not pre-emptive text.

---

## 5. Internal contradictions in the current text

**C1 — the 150-instance experiment (known). Lines 808–810 vs 864–876.**
808–810: 25 departures per route, three days apart, spring 2026, 2×25 combinations, 3 ETA levels,
150 instances. 866–872: a consecutive-voyage chain stepped by the ETA, 35 voyages, one ETA.
These are different experiments with different departure spacings (3 days vs 280 h / 168 h),
different instance counts (150 vs 35 vs the true 41) and different ETA treatments (3 levels vs 1).
**Decision: supersede 808–810. Delete the paragraph outright; do not substitute a reworded version.**
The chain protocol is what was run and it is already described. Also note "10, 12, and 14 **NM**"
should be knots.

**C2 — the two meanings of "6 h". Line 779 vs lines 804–805.**
779: *"The 6 h interval used throughout this study is a sampling choice made for tractability and API
budget, not a property of the source data."*
804–805: *"…which is why the 6 h cadence used below is set by the data rather than tuned."*
Both sentences say "the 6 h [interval|cadence] used throughout/below". A reader sees a flat
contradiction. The resolution is that they are different quantities: the **collection cadence**
(how often the archive was sampled — our choice, budget-driven) and the **re-plan cadence**
(fixed by the wind model's refresh — the data's choice). Both sentences are defensible once the two
are named separately. **This must be fixed; it is currently a real contradiction on the page.**

**C3 — "waypoint" overloaded. Line 793 vs Table 2 vs §5.1.3's 131/389.**
793 says records were collected "at every waypoint"; Table 2 defines waypoints as the 13 and 11
control points. Taken together the text asserts 13 weather sample points on Route 1, which is false
(131) and incompatible with a 27.15 nm mean block length. See the vocabulary decision in §1.

**C4 — stale voyage counts. Lines 868–872 (and 886, 985, 1109, 1171) vs §6's 41.**
13 / 22 / 35 / 19-subset / ~155 days, against 15 / 26 / 41 / 41 / ~170 days. Already logged in
`waypoint_migration_design.md` §5; repeated here because §5.2.3 is where the counts are *defined*
and every later occurrence inherits from it.

**C5 — "stochastic". Line 723 vs Contribution 2 (~line 207) and §3's framing.**
§5's intro promises "the forecast data applicable for the dynamic and **stochastic** version", while
Contribution 2 states the method works "without assuming any probabilistic model linking forecast to
realisation". §3 line 243 also uses "stochastic dynamic version" loosely for what is in fact a
deterministic re-solve on refreshed data. §5 should say **rolling horizon** / **imperfect
information**, never "stochastic". (§3's usage is out of scope here but has the same defect.)

**C6 — the oracle's information set. Line 855 vs lines 858–860.**
If the oracle used *"the actual weather recorded at the voyage's departure sample hour"* (a frozen
snapshot), the RH arm's first-block nowcast — also "actual" but at the *current* hour — would use a
different quantity, and the two arms could not be placed on one graph. The verified behaviour
(time-varying actual weather) is consistent; the text is not.

**C7 — "attributable to decision granularity alone". Lines 846–847 vs §5.1.3 and the retired claims.**
Unscoped, this sentence licenses cross-route attribution, which the migration design shows is
unidentified (block length differs 5.4× and weather regime differs, in opposite directions).

**C8 — "not to sampling". Line 875–876.**
*"Because identical departure weather was presented to all planners, the reported differences are
attributable to the experimental setting … not to sampling."* Once §5.1.3 exists, "sampling" will be
read as *spatial* sampling — which differs by 5× between routes. Disambiguate to "voyage-to-voyage
variation in departure conditions".

**C9 — 0.08° cell size, three different values.**
§3 line 247 "roughly 5 NM"; §5 line 779 "between 3 and 5 NM"; the underlying grid supplies ~4.8 nm.
Pick one and use it everywhere; ~4.8 nm is the honest figure at these latitudes and is the one the
sampling argument needs.

**C10 — §4's "about 5 NM" subsegment claim vs Route 1's 27.15 nm blocks.**
Line ~412. Not inside the redesigned range, but it is directly falsified by §5.1.3 and must be fixed
in the same edit or §5.1.3 will read as a correction of §4.

---

## 6. What §6 needs and §5 does not currently supply

| # | §6 needs | Currently in §5? | Where it goes |
|---|---|---|---|
| 1 | The nesting corollary, so §6.1 can report magnitude and not sign | **No** — absent from the whole paper | §4 lemma + §5.2.1 instantiation |
| 2 | The same corollary applied to the forecast, so §6.2's overfitting framing is airtight | **No** | §5.2.1, one sentence |
| 3 | Definitions of optimisation span, forecast cost, share captured | **No** | §5.2.4 |
| 4 | Per-voyage failure criteria (worse-than-Luo, worse-than-Naive, union), paired by departure | **No** | §5.2.4 |
| 5 | Block length / SR-legs-per-block per route, so the route contrast is interpretable | **No** | §5.1.3 + Table 3 |
| 6 | An explicit statement that the cross-route comparison is confounded | **No** — and line 846 currently asserts the opposite | §5.1.3 + revised 846 |
| 7 | Per-route forecast-error level (wind RMSE at max lead: 8.40 vs 24.75 km/h) | **No** — §6.3's supporting text has growth *rates* only | Table 3 |
| 8 | That PF and RH sit on one graph (same partition, same voyages, RH reproduces PF) | **No** | §5.2.3 |
| 9 | Aggregation convention (ratio of means) | **No** | §5.2.4 |
| 10 | CI convention (95 % paired bootstrap) | Only in `tab:modec`'s caption | §5.2.4 |
| 11 | Correct oracle information set | **Wrong** (line 855) | §5.2.2 |
| 12 | Correct voyage counts | **Wrong** (868–872) | §5.2.3 |
| 13 | That there is no plan-once arm, so §6's three arms are the whole design | **No** | §5.2.2 + §7 Limitations |
| 14 | Waves as descriptor, not input — pre-empts an obvious referee question | **No** (word absent from draft) | §5.1.3, one clause |

Items 1, 3, 5 and 8 are the load-bearing ones: without 1 §6.1 is misdescribed; without 3 §6.3 is
undefined; without 5 §6's route contrast will be re-read as the retired scaling claim; without 8
§6.3's subtraction is not licensed.

---

## 7. Figures and tables for §5

**Keep:** `fig:routes`, `tab:waypoints` (retitled "Route control points").

**Add exactly one: Table 3 — route and instance summary.** This is the single highest-value addition
in the whole design. It replaces prose in three places and pre-loads §6.

| Quantity | Route 1 (Indian Ocean / Malacca) | Route 2 (North Atlantic) |
|---|---|---|
| Length | 3,393 nm | 1,955 nm |
| ETA | 280 h | 168 h |
| Implied mean SOG ($D/T$) | 12.1 kn | 11.6 kn |
| Control points (Table 2) | 13 | 11 |
| Weather sample spacing | 25.0 nm | 5.0 nm |
| Weather sample points | 131 | 389 |
| Mean decision-block length | 27.15 nm | 5.04 nm |
| 6 h time lines = Luo blocks | 47 | 28 |
| SR legs per 6 h block | 2.0–2.9 | 10.7–15.5 |
| Voyages in the chain | 15 | 26 |
| Wind RMSE at max lead | 8.40 km/h | 24.75 km/h |
| Mean significant wave height | *(to fill — descriptor only)* | *(to fill — descriptor only)* |

Two rows are not yet available and must be filled or dropped before drafting: mean significant wave
height per route, and (optional) mean Beaufort number per route. Everything else is verified.

The "implied mean SOG" row is arithmetic on the two rows above it ($3393/280 = 12.12$,
$1955/168 = 11.64$), included because Naive *is* that speed and because it shows both routes sit
inside the engine envelope.

**Consider (one panel, not a new figure): the nesting, drawn.** §4 already has
`fig:state-neighbours`, a two-panel figure on a schematic 5 nm × 6 h block. A third panel showing
Luo's lattice over the same block — one arc spanning the block at a single slope — beside SR's
H-lines ∪ V-lines would make the containment visible in one glance. **Recommendation: add it as a
panel of the existing §4 figure, not as a new §5 figure.** It belongs with the lemma, and §5 must
stay compact.

**Do not put in §5:** the span-vs-forecast-cost scatter. That is §6's one new figure
(`waypoint_results_2026_09_09.md` §8.5) and it carries a result, not a design.

---

## 8. Voice — flagged, not decided

`.claude/skills/paper-style/SKILL.md` prescribes third person: *"'This study' — never 'we' or 'our'."*
The draft does not comply, and not only in §5:

- §5 line 722: "In this section **we** describe the testbed…"; 727 "**we** describe the input data";
  731 "Two routes were used to benchmark **our** algorithm"; 808 "In **our** experiment **we** tested".
- §4 line 406: "**We** approximate the deterministic speed-control problem…"; 419 "**We** denote…".
- §3 line 242: "In this paper **we** study…".
- Contributions (218–235): "**We** formulate", "**We** embed", "**We** develop", "**We** demonstrate".
- Against this, §3.1/§3.2 (in the commented block) and §7 Discussion use "This study…".

So the draft is **already mixed**, and the mixture does not follow section boundaries.

**Recommendation for this rewrite: match the surrounding draft and keep "we" inside §5**, so the
rewritten subsections do not stand out from §4 and §5.1.1, and **do not perform a silent voice
change**. A global first-person → third-person sweep is a separate, single-purpose edit that should
be run across the whole manuscript at once, after the content is settled. **This is an authors'
decision and is listed in §9 below.**

---

## 9. What this design cannot settle — decisions required from the authors

1. **Voice.** Keep "we" (match the draft) or sweep the whole manuscript to "This study" (match the
   style guide). Recommendation: keep "we" for now, sweep later, once. Must not be decided
   implicitly by this rewrite.
2. **Whether the stride sweep / point-weather probe lands before submission.**
   `waypoint_migration_design.md` §4 argues the sweep is required for any scaling claim. This design
   assumes it **does not** land, and therefore frames §5.1.3 as a stated data limitation with the
   cross-route comparison declared unidentified. If the sweep does land, §5.1.3 gains a paragraph
   describing it as a designed manipulation and §6 gains a dose–response result. **The insertion
   point is the end of §5.1.3.** The rest of this design is unaffected either way.
3. **Whether to add a "plan once from the departure forecast" arm.** It is the maximal-exposure case
   and would sharpen §6.2's overfitting argument considerably — the ordering
   plan-once ≥ RH-SR ≥ oracle would make the regularisation story a gradient rather than a
   two-point contrast. Cost and schedule are unknown to this design. Decide: run it, or state its
   absence in §7 Limitations. **It must not be implied to exist.**
4. **Whether one Naive computation or two are reported.** `waypoint_results_2026_09_09.md` lists a
   separate PF Naive run (`naive_waypoint/`) and a Naive inside the RH run, and quotes Route 1
   Naive 360.476 in the reproduction check. §5 should describe a single Naive policy; the authors
   must confirm that the two computations agree, or say which is reported.
5. **Aggregation convention.** Ratio of means (current `make_pf_tables.py` behaviour, matches the
   published convention) vs mean of percentages; the migration design notes pooled figures differ
   (+1.76 % vs +1.92 %). §5.2.4 must state one. Recommendation: ratio of means, stated explicitly.
6. **Route naming.** The draft says "Indian Ocean route" / "North Atlantic route"; the results
   documents say "Malacca" / "Atlantic". Fix one pair, define it once in §5.1.1, use it everywhere
   including table headers.
7. **The "SR" label.** The method is named after the authors ("Shafir–Raviv", line 881/1177) and is
   introduced as such in §5.2.1 and §6. TRC is not double-blind, so this is permissible, but it is
   unusual and a referee may remark on it. Authors' call; noted because §5.2.1 is where the label is
   defined.
8. **Two table rows.** Mean significant wave height (and optionally mean Beaufort) per route, for
   Table 3. Not available to this design. Fill or drop the rows.
9. **Whether §5.2.4 stays in §5 or opens §6.** Recommendation §5; either is defensible; it must
   exist somewhere.

---

## 10. Editing order

1. Delete 808–810 and the dead comment block 816–822. *(Self-contained; removes the worst defect.)*
2. Rewrite 868–876 to the true protocol and counts (41 = 15 + 26, both regimes, ~170 days).
3. Rewrite 853–856 (oracle information set) and add the no-plan-once clause to 858–862.
4. Compress 776–805 into the new §5.1.2, separating collection cadence from re-plan cadence, and
   fixing "at every waypoint".
5. Write the new §5.1.3 and build Table 3.
6. Add the lemma to §4; add the instantiation and the compatibility sentence to §5.2.1; scope
   line 846.
7. Write §5.2.4.
8. Lockstep fixes outside §5: line 247, line ~412, §7 Limitations item (v) plus the new limitations,
   line 1109, line 723's "stochastic".

Steps 1–3 are pure defect removal and can land before any of the new material is written.

# Meeting agenda — Monday 2026-09-14 (Ami ↔ Tal)

**Research log behind this:** [`meeting_prep_2026_09_14.md`](meeting_prep_2026_09_14.md) ·
**Results:** [`waypoint_results_2026_09_09.md`](waypoint_results_2026_09_09.md) ·
**Designs:** [`waypoint_migration_design.md`](waypoint_migration_design.md),
[`section5_design_2026_09_13.md`](section5_design_2026_09_13.md)

**Paper state:** pushed at `24aef7c`, 32 pages, builds clean. §5 and §6 rewritten on the
41-voyage `waypoint` runs; 55 of 55 numeric claims re-verified against the run data.

---

## Open with this, not with the section walkthrough

A headline claim got weaker this week. Tal should hear it in the first five minutes, framed as a
mechanism rather than found on page 19.

### 1. SR ≥ Luo turned out to be a theorem (5 min)

SR's decision points are H-lines **∪** V-lines, and the V-lines *are* Luo's blocks — 47 and 28,
identical counts. Same speed band, same 1.0 nm distance quantum. So SR's feasible set contains Luo's
and it cannot burn more fuel under equal information.

**The 41/41 was never evidence; it was arithmetic.** What the experiment measures is the magnitude:
−2.43 % and −1.40 %, means of 8.61 mt and 2.82 mt.

→ **Decision: move the dominance claim from Results to Methods.** Already drafted that way
(§4 `Containment of block-locked formulations`, instantiated in §5.2.1).

### 2. The same containment explains the bad news (10 min)

Under real forecasts both planners optimise against the same *forecast*, so SR still fits it at least
as well — and is therefore the more exposed when it is wrong.

| | Malacca | Atlantic |
|---|---|---|
| RH-SR saves vs Naive | **15/15** | 15/26 |
| RH-SR **worse than Luo** | 0/15 | **12/26** |
| RH-SR worse than Naive | 0/15 | 11/26 |
| union of failures | 0/15 | **15/26** |

Published was −1.8 %, 11-of-12 on the Atlantic. Now −0.26 %. Decomposed on the *same 12 voyages*:
`geo` −1.80 % → `waypoint` −0.58 %, so **most of the drop is the partition, not the added voyages**.

Luo's 6 h block is not merely a limitation — it is regularisation.

→ **Decision: promote this to the paper's main empirical result.** Drafted in §6.2.

### 3. The condition that separates the two cases (5 min)

| Route | span (Naive − oracle) | forecast cost (RH-SR − oracle) | captured | cost > span |
|---|---|---|---|---|
| Malacca | 9.66 mt | 4.46 mt | 53.8 % | 0/15 |
| Atlantic | 4.47 mt | 3.90 mt | 12.8 % | **11/26** |

Re-planning pays when the spread a departure makes available exceeds the error in the forecast used
to exploit it. Sharper than "RH saves 1.8 %", and quantitative.

→ **Decision: add the span-vs-cost scatter as §6's one figure?** Data exists; not yet plotted.

---

## Then the deletions — its own slot, while attention is high

**Six scaling claims deleted, not reworded**: abstract, intro, §6, §7 ×2, §8. All asserted the gap
grows with weather variability, larger on the harsher route.

The routes differ in block length by **5.4×** *and* in weather regime, in opposite directions. The
ordering was never identified; `geo` made it look supported. Convexity predicts a penalty in
*within-block spread* = block length × local gradient, and these two routes cannot separate them.

This is the item most likely to draw disagreement. The fallback if Tal wants a scaling claim back is
the **stride sweep** (below), not a rewording.

---

## §5 and §6 walkthrough — after the above

Now it reads as implementation rather than editing.

| What | Why it matters |
|---|---|
| §5.1.3 **new** + `tab:instances` | Route 1 sampled every 25.0 nm, Route 2 every 5.0 nm, against a grid supplying ~4.8 nm on both. This licenses §6's route contrast. |
| §5.2.1 renamed, containment corollary | Reconciles with the independent-implementation claim: *"the two solvers share no code; the containment is a property of their feasible sets."* |
| §5.2.2 oracle corrected | It is time-varying along the whole voyage, not a departure snapshot. |
| §5.2.4 **new** | Defines span, forecast cost, captured share, aggregation conventions. §6.3 is unreadable without it. |
| 150-instance paragraph **deleted** | Described an experiment never run, contradicting the chain protocol three paragraphs later. |

**Two that need Tal's endorsement:**

1. **The `waypoint` decision itself.** He has not been asked to sign off. The case: `geo` builds 163
   blocks from 131 samples on Malacca — it manufactures structure no observation supports.
2. **per-cell → per-sample.** The abstract and contributions claimed "per-cell resolution" (~4.8 nm)
   when the decision interval is the sampling interval — **a fivefold overstatement on Route 1**.
   Corrected; the contribution survives, since no prior formulation reaches data-scale resolution
   tractably either.

---

## Decisions needed from Tal

| # | Decision | Ref |
|---|---|---|
| 1 | Move the dominance claim to Methods — agreed? | §6.1, §4 |
| 2 | Promote the RH reversal to the main empirical result — agreed? | §6.2 |
| 3 | Six scaling claims deleted rather than reworded — agreed? | design §5 |
| 4 | Endorse `waypoint` as the reported partition | migration design |
| 5 | Add the span-vs-cost scatter as §6's figure? | results §8.5 |
| 6 | The three method names (SR / Luo / Naive — Luo needs a neutral name) | prep §1 |
| 7 | Commit the built PDF so pulls are readable without TeX? | — |

---

## Open work — raise as questions, do not pre-commit

| Item | Why it matters | Cost |
|---|---|---|
| **Plan-once RH arm** | **The load-bearing one.** Without it we cannot separate "re-planning hurts" from "forecast-based optimisation hurts" — and §6.2's story rests on that distinction. No such arm exists. | ~40 lines + a 41-voyage run |
| **Stride sweep** | The only clean granularity manipulation. Would restore a magnitude claim honestly. | ~30 lines/engine + ~2 h compute |
| **Point-weather probe** | Explains why SR *degrades* on the Atlantic under `waypoint` despite 3× more decision points. Currently unexplained; §6.1 reports the number without a mechanism. | ~30 min |
| **Python↔C++ parity on `waypoint`** | Not re-established at scale. These are now the paper's only numbers. | cheap |

---

## Settled this week — mention only if asked

- **Wave height** is not an input to any formula, in our code *or* in `yang2020`. Sea state enters
  through BN (Kwon). `yang2020`'s Eqs 11–13 belong to its *optimisation model*, which we replace, so
  nothing needs conceding. It did move published results once, via a NaN gate: ~0.3 % on Route 1,
  0.0 % on Route 2, fixed in `8995489`.
- **Course changes are already decision points** — 13/13 and 11/11 control points are sample points.
  An earlier concern of mine, withdrawn after checking.
- **The C++ golden harness was dead** (retired dataset paths, printing "REGRESSION DETECTED" while
  guarding nothing). Repaired: v4 paths, preflight, 12-config matrix across both partitions.
- **Route 2 is milder than the draft claimed** — measured mean wind 29.7 km/h, not 46.6; median BN 4,
  not 6–8. `tab:instances` uses the measured values.

---

---

## Design direction for the rewrite — Tal, 2026-09-14

**All of this belongs in §3, Problem formulation. §4 (Methods) is complete and is not to be touched.**
Nothing to be written until designed; logged here only.

### Intended flow

1. Explain the problem, the **decision variable**, and the **optimisation function**.
2. Then explain `luo2024`.
3. State that **both formulations obtain fuel from a black box**, and that both black boxes are
   described in the appendix (ours: the resistance decomposition of `yang2020`; theirs: an artificial
   neural network trained on noon reports fused with meteorological reanalysis).
4. Then the difference, and Tal's framing of what the *main* one is:

   > **`luo2024` decides only on a change of time — once every six hours. We decide far more finely,
   > on changes in the sea conditions.**

### Why this framing is better than "granularity"

It names the *trigger* for a speed decision rather than a resolution in the abstract, which is
concrete, is what a reader remembers, and is exactly the axis the experiment varies. It also makes
the black-box point land: if both price fuel the same way, the only thing left to differ on is when
the speed is allowed to change.

### Two things to get right when drafting, so the claim survives review

- **Our decision points are a superset, not a different set.** Speed may change at a sea-conditions
  boundary *and* at each six-hour time line. Luo's six-hour boundaries are therefore among ours. That
  is what makes the containment of §5.3 true, and it is why the perfect-foresight ordering is a
  theorem rather than a finding. Writing "they decide on time, we decide on weather" as a clean
  dichotomy would break that argument. The accurate form is: *they decide only on time; we decide on
  time and on conditions.*
- **"Changes in the sea conditions" means where the conditions were sampled**, not where they truly
  change: every 25.0 NM on Route 1 and 5.0 NM on Route 2 (§5.1.3). The honest phrasing is "wherever
  the conditions are resolved by the data". Claiming resolution finer than the sampling interval is
  the overstatement that was corrected in `24aef7c`.

### Open question that may reshape this — item 5 above

Whether `luo2024` prices a block against block-representative conditions or walks it. Our
implementation walks it at sub-segment resolution, so if the original does not, we have been running
a **stronger** Luo than the published method and the paper must disclose it. Resolve before drafting
§3, since it affects how the difference is stated.

### Scope — settled

§3 carries the whole line of argument: problem, decision variable, objective, then `luo2024`, then
the shared black-box fuel interface, then the difference. **§4 is complete and out of scope.**

This supersedes the structure drafted and reverted earlier today, which had created a separate
section between Methods and the experimental design. That approach is dropped: the comparison belongs
in the problem formulation, where the decision variable is defined, not after the solution method.

Consequence: the containment argument also belongs in §3, stated at the level of the admissible set
(a block-locked plan is a per-leg plan that repeats a value across each block), not as a lemma about
the state space. No new section is created and no section numbers shift.

**Conflict to resolve.** `\subsection{Containment of block-locked formulations}` currently sits in
**§4** (pushed, `24aef7c`, the third subsection of Methods), and six cross-references point at its
label `sec:nesting` from §6, §7 and §8. If the containment argument moves to §3, §4 has to be touched
after all, if only to remove that subsection. Three options:

- **(a)** Leave the §4 lemma exactly where it is and give §3 only the informal statement at the level
  of the admissible set. §4 is then genuinely untouched, at the cost of the point being made twice.
- **(b)** Move the lemma to §3 and delete it from §4. Cleanest result; requires one deletion in §4 and
  no change to any cross-reference, since the label travels with the text.
- **(c)** Leave §4 alone and make no containment claim in §3, letting §3 state only the difference in
  decision triggers. Weakest, because the perfect-foresight ordering then reads as a finding again
  rather than a consequence.

Recommend **(b)**; it is a deletion rather than a rewrite, and the "untouched" instruction is about
not reworking the method, which (b) does not do. Needs Tal's word.


### Restructuring §3 — moving the physics to the appendix

Tal: "move most of §3 to the appendix; it should be structured." The black-box framing is what makes
this possible: once the fuel model is an interface, the physics behind it has no reason to sit in the
problem statement.

**§3 today** is 74 rendered lines (plus a 90-line `comment` block that renders nothing and should be
deleted outright):

| Current content | Disposition |
|---|---|
| Intro paragraph | keep |
| `description` list: Route, $T$, Sea conditions, FCR function | keep, but trim — the *Sea conditions* item currently carries the discretization explanation, which belongs with the partition in §5.1.3 |
| Eq.~`speed-set`, $\mathcal{V}(d)$, and what a solution is | **keep — this is the decision variable** |
| Stochastic-version paragraph | keep, one paragraph |
| §3.1 Speed over ground: Eq.~`sog`, $\Delta V_{\text{wind}}$, the inversion $g^{-1}$ | **move to appendix** — keep only the two facts §3 actually uses: $V_g$ is monotone in $V_s$ so the relation inverts, and required SWS rises as conditions worsen |
| §3.2 Fuel and objective: cubic FCR, Eq.~`legfuel`, Eq.~`obj` | keep the objective; the cubic form and coefficient are **already** in Appendix~`app:fcr` |
| Convexity mechanism (SWS varies, FCR penalises it) | keep — two sentences, it is the paper's mechanism |
| The dead `\begin{comment}` block, lines 322--411 | **delete** |

**§3 after the move** — a problem statement and a comparison, no physics derivations.

**Tal, 2026-09-14: §3 is not to be broken into several subsections. At most one.** So the material
runs as continuous prose, using `\paragraph{}` run-in headings rather than `\subsection{}`. Moving
the physics out is what makes that possible: with the speed-correction chain and the FCR derivation
in the appendix, what remains is short enough to read straight through.

```
3  Problem formulation                 (flat prose, paragraph headings only)
     - inputs: route, T, sea conditions, fuel model
     - the decision variable: V(d), what a plan is
     - the objective: Eq. obj, arrival constraint
     - the convexity mechanism, two sentences
     - the benchmark: luo2024, one speed per forecast cycle
     - the fuel model as a black box, both implementations in the appendix + figure
     - how the two differ: decision triggers; containment at the level of the admissible set

  3.1  (at most one subsection, if anything needs it)
```

The current §3 already has two subsections, `Speed over ground` and `Fuel and objective`. The first
is the one being moved to the appendix; the second collapses into the flowing text. So the subsection
count goes from two to zero or one, without a separate flattening step.

**Appendices after the move:**

```
A  Speed correction model            NEW — receives §3.1's Eq. sog, the wind/current
                                     terms, and the numerical inversion
B  Fuel consumption rate             existing app:fcr, unchanged
C  The benchmark's fuel model        NEW — luo2024's ANN, its inputs and training data
```

#### Cross-references to handle

Counted in the pushed version, so the move is cheap:

| Label | Refs | Action |
|---|---|---|
| `eq:speed-set` | **10** | stays in §3 — it is the decision variable, do not move it |
| `sec:problem` | 5 | stays |
| `app:fcr` | 3 | unchanged |
| `sec:sog` | 2 | both are *from the appendix itself* (lines 1383, 1475); the label travels with the text to Appendix A and both resolve |
| `eq:legfuel` | 1 | stays with the objective |
| `sec:objective`, `eq:sog`, `eq:obj` | 0 | free to move |

So only `sec:sog` moves, and nothing outside the appendix points at it. **No cross-reference breaks.**

#### Sequencing

1. Delete the dead `comment` block (lines 322--411). Independent of everything else, removes 90 lines.
2. Create Appendix A and move §3.1's derivation into it, leaving the two facts §3 needs.
3. Trim the *Sea conditions* description item; its discretization material belongs in §5.1.3.
4. Then draft §3.3--3.5 (the benchmark, the black box, the difference) into the space this frees.

Steps 1--3 are pure relocation and can be verified by diffing the rendered PDF for unchanged claims.
Step 4 is the new writing, and is blocked on item 5 above.

#### What must not move

The decision variable, the objective, the arrival constraint, and the convexity sentence. A reader
must be able to state the optimisation problem from §3 alone without turning to an appendix — that is
the test for whether the split went too far.

### Re-reading `luo2024` — what to cite, and where

Source: `context/literature/pdfs/Luo2024_CompetingArticle.pdf`, *Transportation Research Part C* 167
(2024) 104827, Luo, Yan and Wang. Read 2026-09-14; page/section references below are theirs.

#### Item 5 is RESOLVED, and it is reading (1)

Their §5.1 and §5.2.2 are explicit, twice:

> "Within a given segment, it is assumed that the meteorological conditions, **which are represented by
> the latest meteorological forecast at the beginning of the segment, remain consistent**."

> "As mentioned above, **the meteorological conditions at the beginning of the segment represent those
> along the whole segment.** Therefore, we need to estimate the geographical coordinates of, and the
> arrival time at, node a."

So an edge weight in their graph uses **one** weather sample, taken at the segment's starting node,
extrapolated along the rhumb line, applied across the entire segment.

**Our implementation walks each block at sub-segment and sample-hour resolution**
(`luo_main.cpp:100-131`). **We are therefore running a materially stronger Luo than the published
method.** This must be disclosed, and it cuts in our favour — the reported advantage of the finer
formulation is measured against a benchmark we improved, not one we weakened. It also makes the
existing fidelity sentence ("implemented independently, not as SR subject to an added equality
constraint") incomplete as written: faithful to the *decision structure*, deliberately more generous
on the *cost evaluation*.

**Decision required:** disclose and keep the stronger Luo (recommended — it is the conservative
choice and the comparison stays like-for-like on weather information), or re-run Luo with
segment-start weather to match the original, which would widen our measured advantage.

#### What their method actually is, for §3.3

- Route divided into **segments aligned to the NWP forecast cycle** $T$, with
  $n=\lfloor (T_{\max}-(T-\Delta t))/T \rfloor + 1$; the first and last segments are partial.
- **Speed is constant within a segment.** Their words: "we assume that the sailing speed remains
  unchanged during any one segment of the voyage".
- Speed bounded by $[v_{\min},v_{\max}]=[8.0,18.0]$ knots.
- Multistage graph $G=(V,E)$: stage $i$ holds nodes representing the **remaining distance** to the
  destination, discretised by a distance interval $\zeta$; edges connect adjacent stages only; the
  edge weight is the fuel to cover the segment between two nodes.
- Edge speed follows from the two nodes' remaining distances and the segment's time limit
  (their Eq. 15), so choosing an edge *is* choosing that segment's speed.
- Solved by shortest path; re-run each segment on the latest forecast, committing the first speed —
  a rolling horizon in their own terms.

This maps cleanly onto our framing: **their decision epochs are the forecast cycle, i.e. time only.**

#### What their fuel model is, for §3.4 and the appendix

- $f_{\mathrm{ANN}}(v,w,u)$, a feed-forward ANN: $v$ = sailing speed, $w=(x_2,\dots,x_7)$ = six
  meteorological variables, $u=(x_8,x_9)$ = draught and loading condition (laden or ballast).
- Trained on a **fusion dataset**: ship noon reports for the sailing features, ECMWF ERA5 for the
  meteorological ones, which *replace* the on-board weather entries.
- Meteorological inputs include wind speed, mean wave period, significant height of combined wind
  waves and swell, and forecast surface roughness; absolute wind and mean-wave directions are
  converted to **relative** directions with respect to the ship's true heading.
- Their Table 1 lists the features with min/max/mean; their Fig. 1 shows the three-layer structure.

#### Where to cite what

| Place | Cite for | Notes |
|---|---|---|
| §2 Related work | that it is the state of the art, and the $K^N$ profile-space argument | already there |
| §3.3 The benchmark | segments aligned to the forecast cycle; constant speed per segment; multistage graph over remaining distance; shortest path; re-run per cycle | cite their §5.1--5.2.2 |
| §3.4 Black box | $f_{\mathrm{ANN}}(v,w,u)$ as their fuel model | one sentence, detail to the appendix |
| §3.5 The difference | decision epochs are the forecast cycle, i.e. time only | their own assumption sentence is the cleanest support |
| Appendix C | ANN structure, the fusion dataset, the feature list, relative directions | their §3.1--3.3, Table 1, Fig. 1 |
| Disclosure (§3.3 or §6) | that we evaluate their arcs on finer weather than they do | see item 5 above |

#### Two differences worth stating once, not labouring

- Their fuel model **consumes sea state directly** (significant wave height, mean wave period);
  ours carries sea state only through the Beaufort number.
- Their speed band is $[8,18]$ kn against our $D/T \pm 3$ kn. Ours is the narrower and is tied to the
  schedule; theirs is a vessel envelope. Worth a sentence in §5.2 so the bands are not read as
  arbitrary.

## Decisions made during the session

| Decision | Outcome | Follow-up |
|---|---|---|
| | | |

## Actions assigned

| Action | Owner | Due |
|---|---|---|
| | | |

## Running notes

### Live log — 2026-09-14 session

Requests raised by Tal during the session, in order. **Items 1–4 are already applied to
`paper_full_draft.tex` in the working tree and are NOT committed.** Everything from item 5 onward is
logged only.

| # | Request | Status | Where |
|---|---|---|---|
| 1 | Reference the literature review from the section comparing us to `luo2024` | applied | §5.1 opens "The benchmark introduced in Section~\ref{sec:related}"; §2 already forward-pointed to §5 |
| 2 | ~~A section after §4 describing `luo2024` and how we differ~~ **superseded — it goes in §3** | reverted | was: new §5 "The benchmark formulation and how it differs"** — 5.1 the block-locked lattice, 5.2 where they differ, 5.3 containment (moved out of §4) |
| 3 | In the problem definition, explain how `luo2024` decides its speed and how we decide ours | applied | §3.2 ¶ "What a speed plan is allowed to be" — same objective and constraints, differing only in how many independent speed choices a plan may contain |
| 4 | Say the FCR is a black box detailed in the appendix (their ANN, our `yang2020`), and visualise it: time + space in, FCR out | applied | §3.2 ¶ "The fuel model is an interface" + `fig:fcr-blackbox` (TikZ, p. 9) + **new Appendix B `app:fcr-luo`** |

**Paper state after items 1–4:** 34 pages, builds clean, 0 unresolved references. Section numbering
shifted: Data and experimental design is now §6, Results §7, Discussion §8, Conclusion §9.

**Verified while doing item 4, worth keeping:** `luo2024` does use an artificial neural network for
FCR, trained on ship noon reports fused with meteorological reanalysis (the reanalysis replaces the
on-board weather entries, which they identify as the weak part of noon reports). Inputs include
significant wave height of combined wind waves and swell, wind speed and direction, surface roughness
and air temperature, with directions taken relative to heading.

**Consequence flagged in Appendix B, may need a decision:** their learned model consumes significant
wave height directly; our resistance decomposition carries sea state only through the Beaufort
number. The comparison in this study holds the fuel model fixed across both formulations rather than
giving each its own, because running each on its own fuel model would confound decision granularity
with fuel estimation. If Tal wants the alternative, that is a new experiment, not an edit.

**Toolchain:** `latexdiff` and `pgf`/`tikz` were installed into TinyTeX this week; neither was
present.

---

### Further requests — logged, not applied

_Append below as they come up._

| # | Request | Notes |
|---|---|---|
| 5 | **Luo does not cost against the true sea conditions — needs explaining in the paper** | Raised by Tal. See the note below: our implementation may not match the original on this point, and the two readings have different consequences. **Unresolved — do not write until settled.** |

#### Note on item 5 — what our Luo actually does (checked in code, not assumed)

`luo_main.cpp:100-131` walks the block: it splits each block at sub-segment and sample-hour
boundaries and calls `cell_weather_at(da, cur_sh, cur_fh)` at each piece, i.e. it looks up the
conditions at that position and that time, then prices the piece at the block's fixed SOG. So in
**our** implementation the weather is resolved at sub-segment resolution; only the *speed* is
block-constant. Position within the block is advanced using the block SOG
(`da = sd + (ta - t_sd) * sog`), which is internally consistent with that speed.

So "Luo costs against the true conditions" is true of our implementation under perfect foresight, and
under the rolling horizon it costs against whatever `time_key` supplies (nowcast for the committed
block, forecast beyond).

Three readings of Tal's point, with different consequences — **needs Tal to say which he means:**

1. *The original `luo2024` prices a block against block-representative conditions rather than walking
   it.* If so, our implementation is **more generous to Luo than the original**, and the paper should
   say so — it strengthens our result but must be disclosed.
2. *The original predicts FCR from forecast meteorology via the ANN, so it never sees realised
   conditions at all.* That is an information-regime difference, already handled by evaluating both
   formulations under the same two regimes (§6.2) — but it deserves a sentence.
3. *Costing a block at one SOG misprices it even with perfect weather, because the true optimum
   varies within the block.* That is the Jensen mechanism the paper already argues, not a defect in
   the cost evaluation.

Reading 1 is the one that would change what the paper must disclose. Resolving it means checking the
arc-cost definition in `Luo2024_CompetingArticle.pdf` against `eval_block` in `luo_main.cpp`.



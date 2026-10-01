# Meeting Prep — Thursday 2026-10-01 (Ami ↔ Tal)

Continues from [meeting_prep_2026_09_28.md](meeting_prep_2026_09_28.md). Mid-week session; the
Monday slot keeps [meeting_prep_2026_10_05.md](meeting_prep_2026_10_05.md).

**Purpose:** work through the eight actions assigned on the 28th. Two of them are Tal's to decide and
block work that cannot start until they are answered.

---

## 1. The two decisions needed first — everything else waits on these

### 1.1 The counterpart regime name (action 6) — blocks the rename

"Rolling horizon" becomes "stochastic". The oracle regime's name travels with it and has not been
chosen:

| | Oracle regime | Forecast regime |
|---|---|---|
| (a) | **Deterministic** | Stochastic |
| (b) | Perfect foresight | Stochastic |
| (c) | Perfect foresight (deterministic) | Stochastic (rolling horizon), glossed on first use |

**(a)** matches §3, which already defines a deterministic and a stochastic version of the problem.
**(b)** pairs a §5 word with a §3 word. **(c)** keeps the operational words findable.

The rename is ~85 strings across §1, §3, §5, §6, §7, Table 3 and Appendix D, and it **collides with
the method-naming decision** (SR / Luo / Naive) carried since 09-14, which touches the same tables.
Both should be settled today and done in one pass.

- [ ] **Decide (a), (b) or (c)**
- [ ] **Decide the three method names**, or confirm they stay

### 1.2 More voyages, or bounded effects (action 4)

Seven of eight paired t-tests are decisive on the existing 41 voyages. The two that are not are the
North Atlantic forecast-regime rows, $p = 0.152$ and $0.352$.

| | Cost |
|---|---|
| Power them at 80% | $n \approx 94$ and $218$ → **1.8 and 4.2 years** of weather, against 180 days now |
| Report the bound instead | free — already computed |

The bound says more than "not significant": SR's advantage over Naive lies within
$[-1.33, +0.19]$ mt and over Luo within $[-1.03, +0.36]$ mt. **Recommend the bound.** The null is
§7.3's own finding; chasing significance to overturn it would argue against the paper's thesis.

- [ ] **Decide: collect, or bound**

### 1.3 The shape of the three-way comparison (action 1)

Agreed on the 28th that §6 must compare Naive, `luo2024` and ours. The shape was not chosen, and it is
a partial revert of `cb3f45f`, which removed those columns on the 26th at the author's request.

| | Shape |
|---|---|
| (a) | Revert — the two percentage columns return; nine columns, needs `\small` |
| (b) | **Absolute fuel for all three** — `Naive (mt)`, `Luo (mt)`, `SR (mt)`; seven columns, no percentage printed |
| (c) | Both |

**Recommend (b).** It shows the three methods side by side as asked, and prints no percentage, so it
sidesteps the ratio-of-means question entirely.

- [ ] **Decide (a), (b) or (c)**

---

## 2. What is being applied today

| # | Action | Blocked? | Status |
|---|---|---|---|
| 3 | t-test generator script, not transcribed numbers | no | _in progress_ |
| 2 | Paired t-tests into the paper | placement only | _in progress_ |
| 1 | Three-way comparison in Table 3 | shape — §1.3 | _waiting_ |
| 7 | Weather analysis: forecast error per parameter, per route, by lead | no | _in progress_ |
| 8 | Propagate parameter error into fuel error | follows 7 | _waiting on 7_ |
| 5 | Rename regime → stochastic | **yes, on §1.1** | _blocked_ |
| 4 | More voyages vs bounded effects | **Tal** | _blocked_ |
| 6 | Counterpart regime name | **Tal** | _blocked_ |

---

## 3. Decisions made during the session

| # | Decision | Outcome | Follow-up |
|---|---|---|---|
| | | | |

## 4. Actions assigned

| # | Action | Owner | Due |
|---|---|---|---|
| | | | |

## 5. Live log — 2026-10-01 session

_Append as items come up._

### Item 1 — where does wind speed enter the model, and why does direction matter?

**Raised by Tal.** Checked in the code, not assumed.

**Wind speed enters only through the Beaufort number.** `calculate_speed_over_ground` does not take a
wind speed at all. Its weather arguments are `beaufort_scale`, `wind_direction`, `ocean_current` and
`current_direction`. Wind speed is converted to BN by `wind_speed_to_beaufort` and never used again,
so the model sees a **coarse, integer** version of it:

| wind | 10 | 15 | 20 | 25 | 30 | 35 | 40 | 50 km/h |
|---|---|---|---|---|---|---|---|---|
| BN | 2 | 3 | 4 | 4 | 5 | 5 | 6 | 6 |

This is the same fact §3 states for sea state — "sea state enters through BN" — and it has a
consequence for §6.4 worth noting: **a wind-speed forecast error only costs fuel if it is large enough
to cross a Beaufort boundary.** That is why the measured Beaufort error ratio between the routes
(1.10–1.79) is consistently milder than the wind-speed error ratio (1.34–2.18): the banding absorbs
part of the error.

**Wind direction matters because it multiplies the speed loss.** The direction relative to the ship's
heading selects $C_\beta$, the direction reduction coefficient of Kwon's model, and the range is
enormous:

| relative angle | BN 3 | BN 4 | BN 5 | BN 6 |
|---|---|---|---|---|
| 0–30° head-on | 2.00 | 2.00 | 2.00 | 2.00 |
| 31–60° bow | 1.67 | 1.70 | 1.67 | 1.58 |
| 61–150° beam | 0.36 | 0.66 | 0.84 | 0.90 |
| 151–180° following | 0.10 | 0.10 | 0.13 | 0.28 |

**At BN 3 or 4 the same wind costs 20× more speed loss head-on than following.** Direction is
therefore the larger lever of the two: wind speed moves the loss through a banded integer, direction
scales it by up to twenty.

**This explains the one result in §6.4 that looked anomalous.** The factorial found the Atlantic's
conditions amplify a *wind-direction* error by 1.72, the largest sensitivity of any field, even though
the Atlantic's wind-direction forecasts are the one thing it does *better* at short lead. Both follow
from $C_\beta$: the coefficient is steep in the angle, so an error in direction is expensive wherever
it occurs, and it is steepest around the beam-to-following transition.

- [ ] **Possible follow-up.** The banding means wind-speed error is only partly transmitted. Measuring
      the forecast error **in Beaufort units directly**, which `make_forecast_error.py` already
      reports, may be the more honest input to the factorial than the error in km/h. Cheap to check

### Item 2 — does `luo2024` have route segments, and does the heading change?

**Raised by Tal. Open — to be answered from the `luo2024` paper itself, not from our implementation.**

**The question.** Does their formulation model a route of several waypoints with a course change at
each, or a single course? And if the course does change, where in their method does it enter?

**Why it matters — "segment" means two different things.** In our paper a *segment* is geometric,
waypoint to waypoint, and a *subsegment* is the stretch between two sampling points. In `luo2024`, as
§3 describes it, a segment is a unit of **time**: one per cycle of the weather product, with the speed
held constant across it and the graph built over remaining distance. If their segments are purely
temporal then their route may carry no course structure at all, and the two papers are using one word
for two unrelated objects — which §3 should say explicitly if so.

**What to look for in the paper:** whether the route is a sequence of waypoints or a single rhumb
line; whether a heading appears in their resistance or fuel model at all; and whether the relative
wind angle is computed against a per-leg course or a fixed one.

**Context from our side, for when the answer comes back.** Our implementation takes the heading
**once per block**, at the block's starting position (`luo_main.cpp:81`), and holds it across the
whole block even though it re-resolves the *weather* at every subsegment inside it. SR takes a heading
**per subsegment** (`atomic_edges.cpp:70`). Blocks run about 70–72 NM, and the routes have 11 and 9
interior course changes, so **up to 23% of Indian Ocean blocks and 32% of North Atlantic blocks could
span a course change** and be priced at the heading they started with.

**If that is not what `luo2024` does, it is a second fidelity difference and it runs the opposite way
to the one already disclosed.** §3's footnote discloses that our benchmark is *more* generous than the
published method on cost evaluation. A block-constant heading would make it *less* generous. Both
should be stated, or the disclosure is one-sided.

- [ ] Read `luo2024` on the route model and the heading
- [ ] If their course is per-leg, quantify what the block-constant heading costs our Luo, and extend
      the §3 footnote

### Item 3 — merge Appendix A into Appendix B

**Raised by Tal.** The speed-correction model and the FCR derivation become one appendix.

**Status: logged, not applied.**

- [ ] **Task.** Merge Appendix A (*The speed-correction model*) and Appendix B (*Derivation of the
      fuel-consumption-rate function*) into a single appendix, the two becoming subsections of it
- [ ] **Task.** Retarget all 14 incoming references and re-letter the appendices that follow
- [ ] **Task.** Rebuild and confirm no reference resolves to the wrong appendix

**Why it is the right merge.** Both appendices are **one model** — `yang2020` — split across two
sections. A reads the conditions and returns the still-water speed required to hold a target SOG; B
takes that speed and returns the fuel rate. §3 already describes them as a pair: *"the conditions
determine the still-water speed required to hold the target SOG (Appendix A), and the still-water
speed determines the fuel rate through a cubic law (Appendix B)."* Appendix C is a genuinely separate
object, the benchmark's learned model, and stays as it is.

**Scope — 14 references, across §3, §4 and the appendix itself:**

| Label | Refs | Lines |
|---|---|---|
| `app:sog` | 5 | 259, 280, 354, 1394, 1486 |
| `app:fcr` | 9 | 259, 355, 360, 374, 384, 1356, 1383, 1500, 1516 |

**Shape after the merge.** The merged appendix carries `app:fcr` and gains two subsections, with
`app:sog` demoted to a subsection label so its five references keep resolving. The existing
subsections of B (*The DTU–SDU power chain*, *Reduction to the cubic form*, *Calibration of the
coefficient*, *Assumptions and validity range*) sit under the FCR subsection.

**Re-lettering is the part to watch.** The appendices become A fuel model (was A+B), B benchmark ANN
(was C), C per-voyage (was D), D forecast error (was E). **Nothing in the body hard-codes a letter** —
every reference goes through `\ref`, and `elsarticle` expands those to the full designation — so the
re-lettering is automatic. But §3 and §6.4 name the appendices in prose beside the reference in
several places, and those sentences must be read rather than trusted.

**Two cheap wins while the appendix is open.** The draft spells `subsegment` 17 times and
`sub-segment` 4 times; and §3's figure caption and the fuel-model paragraph both point at two
appendices where they will now point at one.


# Meeting Prep — Monday 2026-09-28 (Ami ↔ Tal)

Continues from [meeting_agenda_2026_09_14.md](meeting_agenda_2026_09_14.md).

**Two-week gap.** No research since 2026-09-14 (vacation; the Sep-21 slot was not held). **No
experiment has run since 09-09 and none needs to.** Everything below is writing and structure.

**One-line status:** three pieces of work to walk through — the **§3 rewrite** Tal directed on the
14th, now reviewed and fixed; **§5 flattened** to three numbered subsections; and **§6 restructured**
so the body carries aggregates and the per-voyage numbers move to a new Appendix D (§1 below). All
committed and pushed. What remains is writing, plus one open experimental decision (§6).

---

## 0. Where the paper stands

| | State |
|---|---|
| Draft | 36 pages, builds clean, **0 errors, 0 undefined references** |
| Last paper commit | `cb3f45f` 2026-09-26 — Table 3's two versus-Naive columns dropped |
| Pushed | Yes — `origin/main` at `3e06d09`, verified against the GitHub API |
| Working tree | Clean. The built PDF stays untracked pending decision #7 |
| §3 Problem formulation | **Rewritten.** Flat prose, 7 run-in paragraphs, 0 subsections |
| §4 Methods | **Untouched** — verified by hunk range, the scope guard held |
| §5 Data and experimental design | **Flattened** to 5.1 / 5.2 / 5.3; was 5.1.1–5.2.4 |
| §6 Results | **Restructured.** 7 tables and 88 rows → 2 tables, 1 figure, 6 rows |
| §7–§9 | Untouched |
| Appendices | A speed correction · B FCR derivation · C Luo's ANN · **D per-voyage results (new)** |
| Experiments | Unchanged since 2026-09-09. **No new runs, and none needed** |

---

## 1. What changed since the 14th — the walkthrough

### 1.1 §3 Problem formulation — rewritten

This implements the direction Tal gave on the 14th: inputs → decision
variable → objective → benchmark → shared fuel interface → the one structural difference, with the
physics pushed to the appendices.

**Order of the new §3** (`paper_full_draft.tex:250-411`):

| # | Block | What it does |
|---|---|---|
| 1 | Opening ¶ | Announces the new flow; says the physics is an input to the formulation, not part of it |
| 2 | Inputs (`description`, 4 items) | Route, T, Sea conditions, FCR function. The 0.08°/5 NM grid explanation was **removed** — it belongs to `sec:sampling`, where it already sits with the correct 4.8 NM figure |
| 3 | Decision variable + `eq:speed-set` | Rewritten tail: a plan may change speed **at a subsegment boundary and at a six-hour block boundary, and nowhere else**. This one sentence is what the containment argument rests on |
| 4 | *Still-water speed and speed over ground* | Cut to the only two properties §3 uses: `g` inverts, and required SWS rises as conditions worsen. The rest → Appendix A |
| 5 | *Objective* | `eq:legfuel`, `eq:obj`, hard arrival constraint, the band, the zero-speed carve-out |
| 6 | *The convexity mechanism* | Fuel tracks SWS, the plan targets SOG; holding one target through changing weather forces SWS to vary and the convex FCR charges for it |
| 7 | *The stochastic version* | The two old stochastic paragraphs merged into one |
| 8 | *The benchmark formulation* | `luo2024` in full: segments on the NWP cycle Δt, speed constant per segment, multistage graph over **remaining distance** on quantum ζ, edge ⇔ speed, shortest path, re-solved each cycle with only the first speed committed. **The disclosure footnote hangs here** |
| 9 | *The fuel model is an interface* | Neither formulation contains a fuel model; both obtain the rate from **the same exogenous function** (`fig:fcr-model`, TikZ). States explicitly that **both run on the same fuel model**, so granularity is not confounded with fuel-estimation error |
| 10 | *How the two formulations differ* | The payload. *They decide on time only; we decide on time **and** on conditions.* Decision points are **nested, not disjoint** → admissible-set containment → cannot do worse. Forward pointer to `sec:nesting` |

**What this closes from the 14th:** Tal's items 1–4 are all delivered — the lit-review reference, the
"how Luo picks its speed vs how we pick ours" explanation in the problem definition, and the FCR
black box with per-formulation appendices.

**Point worth making out loud:** the containment is now visible in §3 as *structure*, before any
algorithm appears. A reader meets "their decision points are a subset of ours" in the formulation
section and only then meets the lemma in §4.

**Wording change worth flagging:** "black box" is gone. Both formulations now obtain the rate from
"the same **exogenous function**", the physical models "supply that function" rather than sitting
behind a box, and the figure caption opens on a full sentence. One framing instead of two metaphors,
and "exogenous" was already the word the paragraph used.

### 1.2 §5 — flattened to three numbered subsections

§5 carried two levels of numbering, 5.1.1 through 5.2.4. It now carries one:

| | |
|---|---|
| **5.1** | Data |
| **5.2** | Experimental design |
| **5.3** | Evaluation protocol and reported quantities (the two former subsubsections, merged) |

Nothing below the numbered level was lost — the six subsubsections became run-in `\paragraph`
headings and the two that were already `\paragraph` became bold run-ins, the third level §5.2 and
§6–§7 already use. All five labels survive; they resolve one level coarser (`sec:sampling` was 5.1.3,
now 5.1), and every one of the eighteen references still reads correctly.

### 1.3 §6 — aggregates in the body, per-voyage numbers in Appendix D

**The biggest change, and the one to walk Tal through.** Designed first
([section6_design_2026_09_26.md](section6_design_2026_09_26.md)), then applied.

| | Before | After |
|---|---|---|
| Tables | 7 | 2 |
| Figures | **0** | 1 |
| Data rows | 88 | **6** |

- **Table 3 (new)** — fuel by route **and information regime**, four rows. Merges the two former
  aggregate tables. The enabling fact is that Naive does not re-plan and is identical in both
  regimes, so the two rows of a route are directly comparable.
- **Figure 4 (new)** — optimisation span against forecast cost, one point per voyage, with the
  break-even diagonal. **Eleven of twenty-six North Atlantic voyages sit above the line and no Indian
  Ocean voyage does**, reproducing the span table's "cost exceeds span" column by an independent
  path. Built from the existing 09-09 run; no new experiment.
- **Appendix D (new)** — the four per-voyage tables, 82 rows, intact.

**Why the figure became necessary.** §6 had no figure at all, and stripping 82 rows removes the
reader's only access to dispersion; a mean and a count cannot show that the two routes fail
*differently*. This is **Sep-14 decision #5**, which was optional then and is load-bearing now — it
was implemented on a default and Tal should be told so.

**What made this cheap:** all eight run-in findings in §6.1–§6.2 state their evidence as derived
aggregates — "ranging from 6.06 to 13.24 mt", "beaten by Luo on 12 of those 26" — and **not one reads
a row out of a per-voyage table**. All eight survived untouched. The per-voyage tables were
corroboration, not support.

**One convention was settled in passing.** §5.3 requires aggregates as a ratio of means; the
perfect-foresight table already obeyed that and the rolling-horizon table did not. Table 3 uses it
throughout, so two figures in §6.2's prose moved to match: $-0.26\%$ → $-0.28\%$ and $+0.10\%$ →
$+0.09\%$. **The quantities are unchanged** — the same voyages, the same fuel — but §6 no longer
prints two conventions at once. Worth a sentence to Tal, since these are numbers he has read.

---

## 2. Three defects found in review — **fixed** (`f5f5242`)

These were found reviewing the rewrite before committing it, and repaired in a separate commit so
the rewrite stays traceable to its design doc. Raise 2.1 with Tal — it is a wording change to a
sentence he has read before, not a silent edit.

### 2.1 §5.2.1 contradicted the new §3 footnote — **the sharp one**

`paper_full_draft.tex:905` still reads:

> This baseline was implemented independently from its published description, with its own lattice and
> arc evaluation, not as SR subject to an added equality constraint, **so the comparison reflects
> Luo's actual method rather than a weakened variant.**

The new §3 footnote discloses the opposite on cost evaluation:

> The implementation of the benchmark used here **is more generous** than that … it walks each segment
> at subsegment and sample-hour resolution … **the benchmark is evaluated on strictly more weather
> information than its published description requires.**

Both are true of different things — §5.2.1 is about the *decision structure*, the footnote is about
the *cost evaluation* — but as written, one says "Luo's actual method" and the other says "more than
Luo's published description." A referee reading both in sequence will call that a contradiction.

- [x] **Fixed.** The sentence now reads *"…rather than a weakened variant: faithful to the decision
      structure and deliberately more generous on the cost evaluation (Section~\ref{sec:problem})."*
      One clause, no new claim. This is the design's open item 3, deferred at the time because §5 was
      out of scope for the rewrite.

### 2.2 §2 points readers to the wrong section for the benchmark

`paper_full_draft.tex:182` — *"(we describe this baseline in detail in Section~\ref{sec:data})"*. After
the rewrite the detailed description is in §3; §5.2.1 keeps only the implementation. Not a LaTeX
error, so the clean build does not catch it.

- [x] **Fixed.** `Section~\ref{sec:data}` → `Section~\ref{sec:problem}` at line 182.

### 2.3 Inherited typo now sitting in the section Tal will read

`paper_full_draft.tex:256` — *"A route is defined by a set by sequence of geographical waypoints"*.
Pre-existing, carried through the rewrite untouched because the Route item was out of scope.

- [x] **Fixed.** "defined by a set by sequence" → "defined by a sequence".

---

## 3. Item 5 — blocked on Tal since the 14th

**His objection:** Luo does not cost against the true sea conditions, and the paper does not say so.

**What our implementation actually does** (checked in code, not assumed — `luo_main.cpp:100-131`): it
splits each block at sub-segment and sample-hour boundaries, calls `cell_weather_at(da, cur_sh,
cur_fh)` at each piece, and prices that piece at the block's fixed SOG. So the weather is resolved at
sub-segment resolution; **only the speed is block-constant.** Position advances using the block SOG,
which is internally consistent.

So our benchmark is *stronger* than the published one, not weaker. Two ways to go:

| Option | Cost | Consequence |
|---|---|---|
| **(a) Keep the stronger benchmark and disclose** ← taken by default | zero, footnote already written | Every advantage we report is measured against a benchmark given more information than its paper requires. Conservative, and it makes the result harder to attack |
| (b) Re-run the benchmark with segment-start weather only | a new 41-voyage run | Matches the published description exactly; our margins would widen. But it is a new experiment, not an edit |

- [ ] **Decision for Tal: confirm (a).** Recommend yes — (a) is the defensible direction to err in, and
      the footnote is already in the draft. If he wants (b), it is a run, not a rewrite, and it should
      be scheduled rather than done in the meeting.
- [x] The §2.1 fix is applied, so §5.2.1 is already consistent with (a). If Tal prefers (b), that fix
      is reworded rather than reverted.

---

## 4. Carried over — seven decisions the 14th never reached

The 14th was spent entirely on the §3 direction. `meeting_agenda_2026_09_14.md:378-388` records
**"Decisions made during the session" and "Actions assigned" as empty tables.** These seven were
tabled and never answered:

| # | Decision | Ref |
|---|---|---|
| 1 | Move the dominance claim to Methods — agreed? | §6.1, §4 |
| 2 | Promote the RH reversal to the main empirical result — agreed? | §6.2 |
| 3 | Six scaling claims deleted rather than reworded — agreed? | design §5 |
| 4 | Endorse `waypoint` as the reported partition | migration design |
| 5 | Add the span-vs-cost scatter as §6's figure? | results §8.5 |
| 6 | **The three method names** (SR / Luo / Naive — Luo needs a neutral name) | prep §1 |
| 7 | Commit the built PDF so pulls are readable without TeX? | — |

**Push #6 hardest, and push it first.** It is the one that gets more expensive every week:

- `SR` appears **41 times**, `Naive` **28 times**, `luo2024` **20 times** in the draft.
- The new §3 avoids the problem by circumlocution — *"the formulation of this paper"*, *"the finer
  formulation"* — which reads acceptably but means a naming decision now requires a pass over the
  fresh §3 prose as well as the six results tables.
- The proposed ladder **FIXED / BLOCK / FREE** (1 → 47 → 5,875 on Route 1; 1 → 28 → 10,864 on Route 2)
  is still **nowhere in the paper**. It is the contribution stated as a number, and §7.2 ("Decision
  granularity, not data, is the limiting factor") has nothing to lean on without it.

---

## 5. Eight design defaults taken without review

`section3_design_2026_09_14.md:778` lists them. Defaults were applied; none has been reviewed. Two are
live and are handled above (#2 → the footnote's placement, #3 → §2.1 here, #4 → §2.2 here). The rest:

| # | Item | Default taken |
|---|---|---|
| 1 | Containment: informal statement in §3 + forward pointer, or reword the §4 lemma? | **(a)** — §4 untouched. `EDIT-OPT-B` written out, marked *do not apply without approval* |
| 5 | Luo's speed band [8,18] kn vs our D/T ± 3 kn | Omitted from §3; carry to the next §5 pass |
| 6 | Luo's segment-count formula | Omitted — their T is the forecast cycle, ours is the ETA; reproducing it collides on T |
| 7 | Appendix C citation granularity | Cites `\citet{luo2024}` with no section numbers. **If Tal wants numbers: their §3 is the data, their §4 is the network** — the agenda's "§3.1–3.3" is wrong, it points at data description, not at the ANN |
| 8 | Re-run benchmark with segment-start weather | Assumed not — see §3 above |

---

## 6. Open work — is this a re-run problem or a writing problem?

**Headline answer: the experiments do not need re-running.** Nothing since 2026-09-09 has touched a
number. The §3 rewrite is formulation prose; the three fixes were a pointer, a typo and a wording
clause. The partition migration that *did* invalidate earlier results happened on 09-08/09-10 and
everything was re-run then. The 41-voyage waypoint runs stand, and §5–§6 were written against them on
the 13th.

What remains splits four ways, and **only one is a real experiment.**

### 6.1 Pure writing — no compute

| Item | Where |
|---|---|
| Item 5 disclosure | Footnote written and committed. Finished if Tal confirms option (a) |
| Luo's speed band [8,18] kn vs our D/T ± 3 kn | One sentence in §5 |
| Appendix C citation granularity | Their §3 is the data, their §4 is the network |
| Method names + the decision-count ladder (1 → 47 → 5,875) | §5.2 table, then a pass over §3 and the six results tables |

This is the bulk of what is outstanding, and none of it needs the cluster.

### 6.2 The one genuine experiment — a choice, not a necessity

**The plan-once RH arm.** The problem is a mismatch between what §7.3 is titled and what its evidence
can carry. The section is *"When re-planning helps, and when it does not"*, and it opens:

> The rolling-horizon benefit over set-and-forget is real, bounded, and on one of the two routes
> frequently absent.

But the evidence is **RH-SR vs Naive**, and that comparison conflates two distinct things: *using
forecasts at all* and *re-planning every cycle*. Naive does not optimise, so nothing in the current
data isolates re-planning. This is why the 14th called this arm load-bearing.

Two honest routes, both legitimate:

| | Cost | What it buys |
|---|---|---|
| **(A) Run the arm** | ~40 lines + one 41-voyage run | Optimise once at departure on the initial forecast, then sail it without re-planning. Plan-once vs RH isolates **re-planning**; plan-once vs Naive isolates **forecast-optimisation**. §7.3 stands as titled |
| **(B) Narrow the claim** | writing only | Retitle and reword §7.3 to what the data shows — forecast-driven optimisation vs set-and-forget, not re-planning specifically |

- [ ] **This is the one decision for Tal on the experimental side.** (A) is the stronger paper. (B) is
      defensible and costs nothing. What is *not* defensible is keeping the present title over the
      present evidence.

### 6.3 Two cheap checks — not new results, do them regardless

| Item | Why | Cost |
|---|---|---|
| **Point-weather probe** | §6.1 reports SR *degrading* on the Atlantic under `waypoint` despite 3× more decision points, and offers no mechanism. This explains a number already in the paper rather than producing one | ~30 min |
| **Python↔C++ parity on `waypoint`** | Never re-established at scale after the migration, and these are now the paper's **only** numbers. Verification, not new work | cheap |

Both are a morning's work and one of them fills a real hole in §6.1.

### 6.4 Stride sweep — recommend dropping

It existed to restore a magnitude claim honestly. But the six scaling claims were **deleted** in
`7971265`, so there is no longer a claim for it to support. Additive now, not required, at ~2 h
compute plus ~30 lines per engine.

### 6.5 The ask, in one line

Land 6.3 this week; bring 6.2 to Tal as a single question — **keep §7.3's claim and run the arm, or
narrow the claim and don't.** Everything else on the list is writing.

---

## 7. Decisions needed

- [ ] Item 5 — confirm the disclosure (§3 above)
- [ ] The three method names, and whether the ladder table goes into §5.2 (§4 #6)
- [ ] The other six carried-over decisions (§4)
- [ ] **§7.3: run the plan-once arm, or narrow the claim?** The only experimental decision (§6.2)
- [ ] Confirm the stride sweep is dropped (§6.4)
- [ ] Commit the built PDF? (§4 #7)

**Arising from the §6 restructure (§1.3):**

- [ ] **Figure 4 approved?** Sep-14 decision #5, implemented on a default because the restructure
      needs it
- [ ] **The ratio-of-means convention**, and the two prose figures that moved with it
- [ ] Should §6 be organised around weather severity? **Not adopted** — it contradicts §6.1 and §6.3,
      which say the governing quantity is span-to-error ratio and that the two routes are confounded.
      Reopening those two is the precondition, not an edit
- [ ] Is Appendix D the right home, or should the per-voyage numbers leave the paper entirely?

## 8. Decisions made during the session

| # | Decision | Outcome | Follow-up |
|---|---|---|---|
| 1 | **§6 must compare all three methods: Naive, `luo2024` and ours** | Agreed | Table 3 to carry the three-way comparison, not only SR against Luo |
| 2 | **Report paired t-tests per comparison per regime** | Agreed | Computed; 7 of 8 decisive, see live log item 2 |
| 3 | **More voyages wanted, for power** | Raised, not settled | Costs 1.8–4.2 years of weather; bounded-effect alternative offered, see item 3 |
| 4 | **"Rolling horizon" → "stochastic setting" paper-wide** | Agreed | ~85 strings; the rolling-horizon *method* keeps its name, only the regime is renamed — see item 4 |

## 9. Actions assigned

| # | Action | Owner | Due |
|---|---|---|---|
| 1 | Restore the three-way comparison in §6's Table 3 | Ami | before 10-05 |
| 2 | Add the paired t-tests (SR vs Naive, SR vs Luo; both regimes) to the paper | Ami | before 10-05 |
| 3 | Commit the t-test as a generator script, not transcribed numbers | Ami | before 10-05 |
| 4 | Decide: collect more weather, or report the two nulls as bounded effects | Tal | 10-05 |
| 5 | Rename the regime "rolling horizon" → "stochastic" paper-wide, keeping the method's name | Ami | before 10-05 |
| 6 | Decide the counterpart name for the oracle regime before that pass starts | Tal | 10-05 |

---

## 9a. Live log — 2026-09-28 session

_Requests as they come up. Append below._

### Item 1 — §6: compare Naive, `luo2024` and ours

**Raised by Tal.** §6 should show the comparison across all three methods, not just SR against Luo.

**Status: logged, not applied.**

**Context this needs, so it is not applied blindly.** Table 3 *did* carry the three-way comparison
until `cb3f45f` on the 26th, when its `SR vs Naive (%)` and `Luo vs Naive (%)` columns were removed
at the author's request. The table currently reads:

| Route | Regime | $n$ | Naive (mt) | SR vs Luo (%) | SR $\le$ Naive | SR $\le$ Luo |

So Naive survives only as a fuel level and as a count; the two columns that actually compared against
it are gone. Restoring the comparison is a revert of `cb3f45f`, in whole or in part.

**Three ways to satisfy it — decide which before editing.**

| | Shape | Cost |
|---|---|---|
| (a) Revert `cb3f45f` | the two percentage columns return; nine columns, needs `\small` again | exact restoration of what was there |
| (b) Absolute fuel for all three | `Naive (mt)`, `Luo (mt)`, `SR (mt)` replace the percentages; the reader computes ratios | seven columns, all three visible as tonnage, no convention question |
| (c) Both | absolutes plus one percentage column | widest |

**(b) is worth considering** over a straight revert: it shows all three methods side by side, which is
what was asked, and it sidesteps the ratio-of-means question entirely since no percentage is printed.
The numbers are already computed — Indian Ocean 355.11 / 354.06 / 345.46 and North Atlantic
203.26 / 201.61 / 198.78 under perfect foresight, 355.11 / 355.45 / 349.92 and 203.26 / 203.02 /
202.68 under the rolling horizon.

**Open:** which of (a), (b) or (c). Ask before editing rather than guess, since the columns were
removed deliberately two days ago.

### Item 2 — paired t-tests: SR vs Naive and SR vs Luo, both regimes

**Raised by Tal.** Report significance tests per comparison per regime.

**Status: computed on the existing 41 voyages, not yet written into the paper.**

- [ ] **Task.** Add the paired t-tests to §6 (or §5.3 as the stated method) — SR vs Naive and SR vs
      Luo, under perfect foresight and under the rolling horizon, per route
- [ ] **Task.** Commit the test as a generator script alongside `make_pf_tables.py` so the numbers
      are reproducible rather than transcribed
- [ ] **Task.** Decide where they live: extra columns in Table 3, a separate table, or Appendix D

**What the tests say** (paired on departure hour, two-sided, 95% CI on the mean difference in mt):

| Route | Regime | Test | Mean diff (mt) | 95% CI | t | p | Cohen's $d_z$ |
|---|---|---|---|---|---|---|---|
| Indian Ocean | Perfect foresight | SR vs Naive | $-9.66$ | $[-10.72, -8.60]$ | $-17.86$ | 5e-11 | $-4.61$ |
| Indian Ocean | Perfect foresight | SR vs Luo | $-8.61$ | $[-9.58, -7.63]$ | $-17.28$ | 8e-11 | $-4.46$ |
| Indian Ocean | Rolling horizon | SR vs Naive | $-5.19$ | $[-6.19, -4.20]$ | $-10.23$ | 7e-08 | $-2.64$ |
| Indian Ocean | Rolling horizon | SR vs Luo | $-5.53$ | $[-6.58, -4.48]$ | $-10.28$ | 7e-08 | $-2.65$ |
| North Atlantic | Perfect foresight | SR vs Naive | $-4.47$ | $[-5.13, -3.82]$ | $-13.38$ | 7e-13 | $-2.62$ |
| North Atlantic | Perfect foresight | SR vs Luo | $-2.82$ | $[-3.38, -2.27]$ | $-9.96$ | 3e-10 | $-1.95$ |
| **North Atlantic** | **Rolling horizon** | **SR vs Naive** | $-0.57$ | $[-1.33, +0.19]$ | $-1.48$ | **0.152** | $-0.29$ |
| **North Atlantic** | **Rolling horizon** | **SR vs Luo** | $-0.34$ | $[-1.03, +0.36]$ | $-0.95$ | **0.352** | $-0.19$ |

**Seven of eight are decisive on the data we already have.** The two that are not are the North
Atlantic rolling-horizon rows — and that null *is* §7.3's finding, not a gap in it: on the harsh route
under a real forecast, SR's advantage disappears. The paper already says so in words; these two rows
are the number behind the words.

### Item 3 — create more voyages

**Raised by Tal**, to give the tests more power.

- [ ] **Task.** Decide whether to collect more weather, or to report the bound instead (below)
- [ ] **Task.** If collecting: scope a new collection run and re-run both regimes on the longer record
- [ ] **Task.** If not: state the two nulls as bounded effects rather than as absences

**What it would cost.** The current record is ~175 days (Indian Ocean) and ~182 days (North Atlantic);
consecutive chaining already extracts every voyage it holds, 15 and 26. To power the two null tests at
80%:

| Test | Observed $d_z$ | $n$ needed | Weather needed | Have |
|---|---|---|---|---|
| NA rolling horizon, SR vs Naive | $-0.29$ | $\approx 94$ | **1.8 years** | 182 days |
| NA rolling horizon, SR vs Luo | $-0.19$ | $\approx 218$ | **4.2 years** | 182 days |

**The trap to avoid.** More voyages can be manufactured from the *same* window by sliding the
departure hour instead of chaining — roughly 650 departures at a 6 h stride. **Those voyages overlap
and are not independent**, so a paired t-test on them would be anti-conservative: the p-values would
fall without any new information arriving. If overlapping departures are used, the dependence has to
be carried through the inference (block bootstrap or a cluster-robust standard error), not ignored.

**The cheaper alternative, worth putting to Tal.** The nulls are already *bounded*, which is a
stronger statement than "not significant": on the North Atlantic under a real forecast, SR's advantage
over Naive lies within $[-1.33, +0.19]$ mt and over Luo within $[-1.03, +0.36]$ mt. That is a precise
claim, it needs no new data, and it says exactly what §7.3 wants to say.

### Item 4 — rename the regime: "rolling horizon" → "stochastic setting", paper-wide

**Raised by Tal.** Change from rolling horizon to stochastic settings throughout.

**Status: logged, not applied.**

- [ ] **Task.** Rename the *information regime* from "rolling horizon" to "stochastic" everywhere it
      names the regime
- [ ] **Task.** Decide the counterpart (below) before starting — the two regime names travel together
- [ ] **Task.** Rename `sec:res-rh`, and `sec:res-oracle` if the counterpart changes; rename the
      `RH-SR` / `RH-Luo` row labels in Table 3 and Appendix D
- [ ] **Task.** Do it in one pass, not incrementally — it touches every results table and §7

**Why this is the right change.** §3 already defines the problem in exactly these words: a
*deterministic* version and a *stochastic* version. §5 and §6 then call the same two things "perfect
foresight" and "rolling horizon". The paper is using two vocabularies for one distinction, and §3's is
the one that belongs.

**The distinction that must survive the rename.** §3 line 319 reads:

> In this study the **stochastic version** is solved in a **rolling-horizon framework** that uses the
> solution method for the deterministic problem as a building block.

So *stochastic* is the problem and the regime; *rolling horizon* is the **solution method** for it.
A blanket find-and-replace would collapse that and leave the paper unable to say how the stochastic
problem is actually solved. **The method keeps its name; only the regime is renamed.**

**The counterpart question, which must be answered first.** If the forecast regime becomes
"stochastic", then for symmetry the oracle regime should become "deterministic", matching §3. Leaving
it as "perfect foresight" pairs a §3 word with a §5 word and reads worse than either pair alone.
Three options:

| | Oracle regime | Forecast regime |
|---|---|---|
| (a) | Deterministic | Stochastic |
| (b) | Perfect foresight | Stochastic |
| (c) | Perfect foresight (deterministic) | Stochastic (rolling horizon) — gloss on first use |

**(a) is the consistent choice**; (c) is the safe one if Tal wants the operational words kept
findable. **Ask before the pass** — the two names travel together and the pass is not worth doing twice.

**Scope, counted on the current draft:**

| String | Count |
|---|---|
| "rolling horizon" / "rolling-horizon" | 35 |
| `RH` standalone | 15 |
| `RH-SR`, `RH-Luo` | 4 each |
| "perfect foresight" | 13 |
| "oracle" | 9 |
| `sec:res-rh` | 1 definition, 4 references |
| `sec:res-oracle` | 1 definition, 2 references |

Roughly 85 strings across §1, §3, §5, §6, §7, Table 3 and Appendix D. Mechanical but wide — and it
collides with the **method-naming decision** (SR / Luo / Naive, carried since the 14th), which touches
the same tables. **Settle both, then do one pass.**

---

## 10. Verification record — what was actually checked, and how

### 10.1 is the §5/§6 work; this first table is the §3 rewrite, run 2026-09-26 against the
then-uncommitted working tree.

| Check | Method | Result |
|---|---|---|
| Build | `paper_full_draft.log` | 35 pages, 0 errors, 0 undefined references |
| PDF current with .tex | mtimes | .tex 21:45:18, .pdf 21:45:25 — yes |
| Page count vs design band 33–35 | — | 35, inside, at the top edge |
| §3 is flat | `grep` for `\subsection` between 250 and 413 | zero; 7 `\paragraph` run-ins |
| §4 Methods untouched | `git diff -U0` hunk ranges vs baseline 413–748 | no hunk in range |
| §5–§9 untouched | same, vs 749–1373 | no hunk in range |
| Appendices A/B/C present and ordered | `grep` for `app:sog`, `app:fcr`, `app:fcr-luo` | 1376, 1411, 1518 |
| Old subsections removed | `grep` for `sec:objective`, "Speed over ground", "Fuel and objective" | absent |
| Disclosure footnote | `grep` | present, on the benchmark paragraph |
| TikZ figure | `grep` for `fig:fcr-blackbox` | defined 386, referenced 351 and 1522 |
| `float` package for `[H]` | `grep` | loaded, line 16 |
| `sec:sampling` target exists | `grep` | line 834 |

**Re-verified after the three fixes and the commits (`88de49c`, `f5f5242`):** rebuild clean, 35 pages,
0 errors, 0 undefined references; the fix diff was exactly three hunks, one per defect; working tree
clean apart from the untracked PDF. A marked-up `latexdiff` of the whole change against the
pre-rewrite baseline `f153e1c` is at `paper_workspace/build/section3_review_diff_2026_09_28.pdf`.

### 10.2 The §5 and §6 work, verified 2026-09-27

| Check | Method | Result |
|---|---|---|
| Build after every change | `paper_full_draft.log` | 36 pages, 0 errors, 0 undefined references |
| §5 has one level of numbering | `grep` for `subsubsection` in 749–967 | zero |
| All five §5 labels survive | `newlabel` in the `.aux` | `sec:data` 5, `sec:sampling` 5.1, `sec:planners` 5.2, `sec:protocol` and `sec:quantities` both 5.3 |
| No sentence cites both `sec:protocol` and `sec:quantities` | `grep` | none — they would now print the same number twice |
| §6 body reduced | counted rows ending `\\` with `&` | 2 tables, 1 figure, 6 data rows (was 7 tables, 88 rows) |
| Appendix D received everything | same, over the appendix | 4 tables, 82 data rows |
| **Every Table 3 cell recomputed from the run output** | `results.csv`, 41 rows | perfect-foresight values reproduce the old aggregate table exactly; rolling-horizon values reproduce §6.2's prose |
| The two cells the design could not source | same | 15/15 and 26/26, as containment predicts |
| Figure 4 against the span table | independent derivation from `oracle_sr`, `naive_mt`, `rh_sr_mt` | 0/15 and 11/26 above the diagonal — matches "cost exceeds span" |
| Appendix D not colliding with the references | `.aux` page numbers | tables on 30–33 consecutively, references after. Fixed by `[H]` plus a `\clearpage`; they had been landing on 30, 33, 34, 35 with the bibliography threaded between |
| 17 doubled `Appendix Appendix B` references | `.aux` shows `\ref{app:fcr}` → `Appendix~B` | all 17 corrected; regular `Section~\ref` unaffected and left alone |
| 9 doubled periods in run-in headings | `elsarticle.cls:1070` appends the stop itself | all 9 corrected; the manual `\textbf` run-ins supply their own and were left |
| Source is pure ASCII | scan for codepoints > 127 | none. The 12 em-dashes and 5 Unicode maths characters were all inside `%` comments and never rendered |
| Rendered prose has no em-dashes | count `---` in rendered text | 2, both "not applicable" cells in the vessel table. The purge happened on 09-13, from 68 |
| Pushed | GitHub API and `ls-remote` | `origin/main` = `3e06d09` |

**Style patterns deliberately left alone.** "precisely" appears 3 times in the 2026-08-25 draft and
"rather than" 14 times, both well before this month's rewrites, so they are the author's own habits
and the newer uses were not edited toward a different voice.

**Not checked:** Gmail returned an auth-scope error and Calendar needs authentication, so anything
Tal may have sent during the two-week gap has not been read, and the Monday slot is unconfirmed.

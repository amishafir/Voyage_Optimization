# Meeting Prep — Monday 2026-09-28 (Ami ↔ Tal)

Continues from [meeting_agenda_2026_09_14.md](meeting_agenda_2026_09_14.md).

**Two-week gap.** No work since 2026-09-14 21:45 (vacation; the Sep-21 slot was not held). Nothing in
this prep is new research — it is the §3 rewrite that was applied at the end of the 14th, verified,
plus everything the 14th left unanswered.

**One-line status:** the §3 rewrite Tal asked for is **written, reviewed, fixed and committed**
(`88de49c`, `f5f5242`). Three defects found in review are repaired (§2 below). **The experiments do
not need re-running** — what is left is writing, plus one open experimental decision (§6).

---

## 0. Where the paper stands

| | State |
|---|---|
| Draft | 35 pages, builds clean, **0 errors, 0 undefined references** |
| Last commit | `f5f5242` 2026-09-26 — the three consistency fixes |
| Working tree | Clean. The built PDF stays untracked pending decision #7 |
| §3 Problem formulation | **Rewritten and committed.** Flat prose, 7 run-in paragraphs, 0 subsections |
| §4 Methods | Untouched, as the scope guard required — verified by hunk range |
| §5–§9 | Untouched |
| Appendices | A speed correction (new) · B FCR derivation · C Luo's ANN (new) |
| Experiments | Unchanged since 2026-09-09. No new runs |

---

## 1. The §3 rewrite — the walkthrough

This is the main thing to show. It implements the direction Tal gave on the 14th: inputs → decision
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
| 9 | *The fuel model is an interface* | Neither formulation contains a fuel model; both reach one through the same interface. TikZ black-box figure (`fig:fcr-blackbox`). States explicitly that **both run on the same fuel model**, so granularity is not confounded with fuel-estimation error |
| 10 | *How the two formulations differ* | The payload. *They decide on time only; we decide on time **and** on conditions.* Decision points are **nested, not disjoint** → admissible-set containment → cannot do worse. Forward pointer to `sec:nesting` |

**What this closes from the 14th:** Tal's items 1–4 are all delivered — the lit-review reference, the
"how Luo picks its speed vs how we pick ours" explanation in the problem definition, and the FCR
black box with per-formulation appendices.

**Point worth making out loud:** the containment is now visible in §3 as *structure*, before any
algorithm appears. A reader meets "their decision points are a subset of ours" in the formulation
section and only then meets the lemma in §4.

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

## 8. Decisions made during the session

| Decision | Outcome | Follow-up |
|---|---|---|
| | | |

## 9. Actions assigned

| Action | Owner | Due |
|---|---|---|
| | | |

---

## 10. Verification record — what was actually checked, and how

Run 2026-09-26 against the uncommitted working tree.

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

**Not checked:** Gmail returned an auth-scope error and Calendar needs authentication, so anything
Tal may have sent during the two-week gap has not been read, and the Monday slot is unconfirmed.

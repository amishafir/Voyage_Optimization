# Meeting Prep — Monday 2026-10-05 (Ami ↔ Tal)

Continues from [meeting_prep_2026_09_28.md](meeting_prep_2026_09_28.md).

**Seeded 2026-09-28; updated 2026-10-01 after the mid-week session**
([meeting_prep_2026_10_01.md](meeting_prep_2026_10_01.md)). Six of the eight actions assigned on the
28th are done and in the paper. What remains is two decisions that are Tal's, and two pieces of work
that were deferred rather than blocked.

---

## 1. What has happened since the 28th

The 28th produced five decisions and eight actions. The 10-01 session worked through them.

| # | Action from the 28th | State |
|---|---|---|
| 1 | Compare all three methods, not SR against Luo | **done** — every comparison is now against Naive, and no SR-against-Luo comparison survives anywhere |
| 2 | Paired $t$-tests in the paper | **done** — merged into the aggregate table, so every saving carries its interval and $p$ |
| 3 | $t$-tests as a generator, not transcribed | **done** — `make_ttests.py` |
| 5 | Rename the regime to stochastic | **done** — 37 rules; the rolling-horizon *method* kept its name in all 14 places it denotes the scheme |
| 6 | The counterpart regime name | **resolved** — deterministic / stochastic, matching §3 |
| 7 | Forecast error per parameter, per route, by lead | **done** — new §6.4, Figure 5, Appendix E |
| 8 | Propagate parameter error into fuel error | **done** — the 2×2 factorial in §6.4 |
| 4 | More voyages, or bounded effects | **still open — Tal** (§2.1) |

Two further decisions were taken on 10-01 and should be confirmed: the aggregate tables report
**average fuel saving** and no voyage counts, and §6's two tables were **merged into one** so a mean
never appears without its interval.

### 1.1 The result that came out of it

§6.4 answers a question the paper could not previously answer: why the stochastic setting pays on one
route and not the other.

| | ratio | 95% CI |
|---|---|---|
| Effect of the **larger error** on the Atlantic | **1.44** | [1.31, 1.56] |
| Effect of the **harsher conditions** | **1.19** | [1.07, 1.29] |
| Both together | 1.61 | [1.46, 1.75] |
| *measured forecast-cost ratio, for comparison* | *1.46* | |

**Both of the obvious explanations are true, and the larger error is the stronger of the two.** Three
of the four consumed fields are forecast worse on the North Atlantic at every lead and degrade faster;
wind direction is the exception and crosses over near three days, better in the short range and worse
beyond.

### 1.2 One claim was removed as a consequence

§7.3 attributed the Atlantic result partly to the finer planner overfitting the forecast, with the
block constraint acting as a regulariser. **The paper's own numbers contradict it** — under forecasts
on that route SR saves 0.57 mt and Luo 0.24, so the block-locked planner does worse, not better — and
the directive that everything is compared to Naive removed the SR-against-Luo comparison the claim
rested on. The Jensen mechanism is kept; the second is replaced by the measured one.

**This is worth raising explicitly:** it is a claim Tal has read, now gone, with a better-evidenced
replacement in its place.

---

## 2. Carried forward — still open after the 28th and the 10-01 session

Two lists. The first has been open since 2026-09-14 and has now survived three meetings' worth of
agenda; the second arrived with the section 6 restructure on the 26th. Items the 10-01 session
resolved are marked in section 1 and are not repeated here.

### 2.1 Open since the 14th

| # | Decision | Where |
|---|---|---|
| 1 | Move the dominance claim to Methods | §6.1, §4 |
| 2 | Promote the RH reversal to the main empirical result | §6.2 |
| 3 | Six scaling claims deleted rather than reworded | design §5 |
| 4 | Endorse `waypoint` as the reported partition | migration design |
| 5 | The span-vs-cost scatter as §6's figure | **implemented as Figure 4** — confirm, or remove |
| 6 | **The three method names** (SR / Luo / Naive) | **deferred on 10-01**, see §3.3 |
| 7 | Commit the built PDF so pulls are readable without TeX | — |
| 8 | **Item 5 — the Luo cost-fidelity disclosure** (option (a), keep the stronger benchmark and disclose) | §3 footnote |
| 9 | **More voyages, or bounded effects** (action 4) | now scoped — see below |

**#6 is the one that compounds.** `SR` appears 41 times, `Naive` 28, `luo2024` 20, and §3's new prose
avoids the problem by circumlocution ("the formulation of this paper", "the finer formulation"), so
every week it waits the rename costs one more pass. The decision-count ladder that states the
contribution as a number is still nowhere in the paper.

### 2.2 Arising from the section 6 restructure

| # | Decision | Default taken |
|---|---|---|
| 9 | Figure 4 approved? | Implemented — the restructure needs it for dispersion |
| 10 | The ratio-of-means convention, and the two figures in §6.2 that moved with it | §5.3's declared convention applied throughout |
| 11 | Organise §6 around weather severity? | **Declined** — contradicts §6.1 and §6.3 |
| 12 | Is Appendix D the right home for the per-voyage numbers? | Kept in the paper |

---

## 3. The work queue

Ordered by what unblocks the most. None of it needs a decision except the first.

### 3.0 Settled on 10-01: overlapping departures will not help

The proposal was to start a voyage every 3.5 days instead of chaining, to power the two null tests.
It yields **+60 voyages, 41 → 101** — and **no additional power**. At an 84 h stride consecutive
voyages share 70% of their hours on the Indian Ocean and 50% on the Atlantic, so the variance inflates
by 3.40 and 2.00 and the effective sample size is **40.2, against the 41 already in hand**. The record
holds 15.7 and 26.2 independent voyages and chaining already extracts 15 and 26. Powering the nulls
needs 74–94 **independent** voyages, which is 1.4–1.8 years of weather.

It is still worth running as a **robustness check** — it removes the departure-phase arbitrariness,
sharpens the proportions and fills in Figure 4 — but not as a route to significance.
Design: [overlapping_departures_design_2026_10_01.md](overlapping_departures_design_2026_10_01.md).

### 3.1 The one experimental question

**The plan-once rolling-horizon arm.** §7.3 is titled *"When re-planning helps, and when it does
not"* while its evidence compares rolling-horizon SR against Naive, which conflates *using a forecast
at all* with *re-planning every cycle*. Either run the arm (~40 lines + a 41-voyage run) and keep the
title, or narrow the claim. Keeping the present title over the present evidence is the option ruled
out.

- [ ] If the 28th said **run it**: implement, run, and it lands in §6 as a third regime row in Table 3
- [ ] If the 28th said **narrow it**: retitle §7.3 and reword its opening; writing only

### 3.2 Dropped on 10-01 at the author's direction

The per-route persistence split and the speed-band utilisation check were both scoped and then
declined. Neither is blocking; both would have been alternative explanations for the Atlantic gap that
§6.4 now explains without them.

### 3.3 Writing, once §5 reopens

- [ ] Luo's speed band [8,18] kn against our $D/T \pm 3$ kn — one sentence, so the bands do not read
      as arbitrary
- [ ] Appendix C citation granularity — their §3 is the data, their §4 is the network; the Sep-14
      agenda's "§3.1–3.3" points at the wrong thing
- [ ] Luo's segment-count formula — omitted on purpose, collides with our $T$
- [ ] The decision-count ladder into §5.2, **counted correctly**: the 1 → 47 → 5,875 figures are the
      rectangle grid (subsegments × blocks), not decisions per voyage, which are nearer 178 on Route 1
      against Luo's 47. Both are defensible; only one is what "decisions per voyage" means
- [ ] **The method names.** Deferred on 10-01. The recommendation was FIXED / BLOCK / FREE, each being
      an adjective the draft already uses for that method — §5.2 calls Naive *"Fixed-speed"*, §4.3 is
      titled *"Containment of **block-locked** formulations"*, §6 opens *"SR denotes the per-leg
      **free-speed** dynamic program"*. `SR` self-names the author, `Luo` puts a surname in every
      results table, and `Naive` is pejorative for what is now the baseline everything is measured
      against. Best done in one pass with the ladder above

### 3.4 Dropped earlier: the stride sweep

- **Stride sweep.** It existed to restore a magnitude claim, and the six scaling claims were deleted
  in `7971265`. Confirm and close.

---

## 4. Paper state entering the week

| | |
|---|---|
| Draft | **40 pages**, builds clean, 0 errors, 0 undefined references |
| Pushed | `origin/main` at `4388032`, verified against the GitHub API |
| §3 | Rewritten; physics in Appendices A and C; "exogenous function", not "black box" |
| §4 | Untouched since 09-13 |
| §5 | Flattened to 5.1 / 5.2 / 5.3; 5.1 gains a forecast-error methods paragraph |
| §6 | 6.1 deterministic, 6.2 stochastic, 6.3 what the forecast costs, **6.4 why it costs more** |
| §6 floats | One aggregate table with intervals, the span table, Figure 4, Table 5, Figure 5, Table 6 |
| §7 | 7.3's second mechanism replaced; otherwise untouched since 09-13 |
| Appendices | A speed correction · B FCR · C benchmark ANN · D per-voyage · **E forecast error** |
| Experiments | Unchanged since 2026-09-09. No new runs, and none needed |
| Generators | `make_ttests`, `make_span_cost_figure`, `make_forecast_error`, `make_error_factorial`, `make_forecast_error_figure`, `make_section64_tables` |

**§7 Discussion still has not been read end to end since 09-13**, which predates the
benchmark-fidelity finding, the §6 restructure and now §6.4. Its second mechanism was replaced on
10-01, but the rest of it has not been checked against the paper it now sits in. **This is the most
likely place a stale claim is sitting, and it is the one piece of the paper nobody has audited.**

---

## 5. Decisions needed

- [ ] **Action 4 — more voyages, or report the bounds?** Now scoped: overlapping departures add
      voyages but no power (§3.0). Recommend the bounds; the null is §7.3's own finding
- [ ] **Confirm the §7.3 replacement** — a mechanism Tal has read is gone (§1.2)
- [ ] **Confirm the 10-01 table decisions** — savings not counts, and one merged table
- [ ] **The method names** — defer again, or do the pass (§3.3)
- [ ] The seven carried-over items from the 14th (§2.1)
- [ ] Commit the built PDF? (§2.1 #7)

## 6. Decisions made during the session

| Decision | Outcome | Follow-up |
|---|---|---|
| | | |

## 7. Actions assigned

| Action | Owner | Due |
|---|---|---|
| | | |

## 8. Running notes

_Append during the session._

# Meeting Prep — Monday 2026-10-05 (Ami ↔ Tal)

Continues from [meeting_prep_2026_09_28.md](meeting_prep_2026_09_28.md).

**Seeded 2026-09-28, before that session ran.** Everything below is carried forward, not concluded.
Section 1 is the slot for what the 28th actually decided; until it is filled, treat every item in
sections 2–4 as still open.

---

## 1. What the 2026-09-28 session settled

_Transcribe from `meeting_prep_2026_09_28.md` §8 and §9 once the session has run. Strike each item in
section 2 below that it resolves._

| Decision | Outcome | Follow-up |
|---|---|---|
| | | |

**Actions assigned on the 28th**

| Action | Owner | Due |
|---|---|---|
| | | |

---

## 2. Carried forward — open until the 28th says otherwise

Two lists. The first has been open since 2026-09-14 and has now survived two meetings' worth of
agenda; the second arrived with the section 6 restructure on the 26th.

### 2.1 Open since the 14th

| # | Decision | Where |
|---|---|---|
| 1 | Move the dominance claim to Methods | §6.1, §4 |
| 2 | Promote the RH reversal to the main empirical result | §6.2 |
| 3 | Six scaling claims deleted rather than reworded | design §5 |
| 4 | Endorse `waypoint` as the reported partition | migration design |
| 5 | The span-vs-cost scatter as §6's figure | **now implemented as Figure 4** — confirm, or remove |
| 6 | **The three method names** (SR / Luo / Naive) | prep §1 |
| 7 | Commit the built PDF so pulls are readable without TeX | — |
| 8 | **Item 5 — the Luo cost-fidelity disclosure** (option (a), keep the stronger benchmark and disclose) | §3 footnote |

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

## 3. The work queue, independent of the 28th

Ordered by what unblocks the most. None of it needs a decision except the first.

### 3.1 The one experimental question

**The plan-once rolling-horizon arm.** §7.3 is titled *"When re-planning helps, and when it does
not"* while its evidence compares rolling-horizon SR against Naive, which conflates *using a forecast
at all* with *re-planning every cycle*. Either run the arm (~40 lines + a 41-voyage run) and keep the
title, or narrow the claim. Keeping the present title over the present evidence is the option ruled
out.

- [ ] If the 28th said **run it**: implement, run, and it lands in §6 as a third regime row in Table 3
- [ ] If the 28th said **narrow it**: retitle §7.3 and reword its opening; writing only

### 3.2 Two cheap checks, not blocked on anything

- [ ] **Point-weather probe** (~30 min) — §6.1 reports SR *degrading* on the Atlantic under `waypoint`
      despite 3× more decision points, and offers no mechanism. Explains a number already in the paper
- [ ] **Python↔C++ parity on `waypoint`** (cheap) — never re-established at scale after the migration,
      and these are now the paper's only numbers

### 3.3 Writing, once §5 reopens

- [ ] Luo's speed band [8,18] kn against our $D/T \pm 3$ kn — one sentence, so the bands do not read
      as arbitrary
- [ ] Appendix C citation granularity — their §3 is the data, their §4 is the network; the Sep-14
      agenda's "§3.1–3.3" points at the wrong thing
- [ ] Luo's segment-count formula — omitted on purpose, collides with our $T$
- [ ] The decision-count ladder into §5.2, **counted correctly**: the 1 → 47 → 5,875 figures are the
      rectangle grid (subsegments × blocks), not decisions per voyage, which are nearer 178 on Route 1
      against Luo's 47. Both are defensible; only one is what "decisions per voyage" means

### 3.4 Dropped

- **Stride sweep.** It existed to restore a magnitude claim, and the six scaling claims were deleted
  in `7971265`. Confirm and close.

---

## 4. Paper state entering the week

| | |
|---|---|
| Draft | 36 pages, builds clean, 0 errors, 0 undefined references |
| §3 | Rewritten, flat prose, physics in Appendices A and C |
| §4 | Untouched since 09-13 |
| §5 | Flattened to 5.1 / 5.2 / 5.3 |
| §6 | 2 tables, 1 figure, 6 rows; per-voyage numbers in Appendix D |
| §7–§9 | Untouched since 09-13 |
| Experiments | Unchanged since 2026-09-09 |

**§7 Discussion has not been read since the 13th**, which is before the benchmark-fidelity finding of
the 14th and before the §6 restructure. It is the most likely place for a stale claim to be sitting.
Worth a pass this week regardless of what else happens.

---

## 5. Decisions needed

- [ ] _(fill once section 1 is transcribed)_

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

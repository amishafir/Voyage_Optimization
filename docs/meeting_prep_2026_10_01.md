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

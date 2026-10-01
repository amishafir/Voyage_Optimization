# Design — overlapping departures: a 3.5-day stride instead of consecutive chaining

**Origin:** action 4 of the 2026-09-28 session — more voyages from the existing data, to power the
two null tests.
**Proposal (author, 2026-10-01):** start a new voyage every 3.5 days (84 h) after the previous one
*starts*, instead of when the previous one *arrives*.
**Status:** design only, nothing run.

---

## 1. The answer up front

The scheme **adds 60 voyages, 41 → 101**, and **adds essentially no statistical power.** The
effective sample size goes from 41 to about 40.

That is not a flaw in the arithmetic of the proposal; it is a property of the record. It is still
worth running, but for different reasons than the one it was proposed for (§5).

---

## 2. The scheme

Departures on the 6 h sample grid, stride $s = 84$ h (84 = 14 × 6, so every departure lands on a
sample). A voyage is admissible while `departure + ETA ≤ 4410`, the last hour of the record.

| Route | ETA | Record | Last departure | Chained | **Stride 84 h** | Added |
|---|---|---|---|---|---|---|
| Indian Ocean | 280 h | 6–4410 | 4130 | 15 | **50** | **+35** |
| North Atlantic | 168 h | 0–4410 | 4242 | 26 | **51** | **+25** |
| | | | | **41** | **101** | **+60** |

The record runs to hour 4410 on both routes, further than the current chain uses (it stops at 3926
and 4200), so a few of the added voyages come from extending the window rather than from overlap.

---

## 3. Why the power does not improve

Consecutive voyages now **share weather**. At an 84 h stride an Indian Ocean voyage overlaps its
successor by 196 of its 280 hours — **70%** — and a North Atlantic voyage by 84 of 168 — **50%**.
Overlapping samples are correlated, and correlated samples carry less information than their count
suggests.

For windows of length $L$ at stride $s$, two voyages $k$ apart share $(L - ks)/L$ of their hours, so
$\rho_k \approx 1 - ks/L$ while $ks < L$. The variance of the mean inflates by
$\mathrm{VIF} = 1 + 2\sum_k \rho_k$, and the effective sample size is $n/\mathrm{VIF}$:

| Route | $n$ | Overlap | $\rho_1,\rho_2,\rho_3$ | VIF | $n_{\text{eff}}$ | Have now |
|---|---|---|---|---|---|---|
| Indian Ocean | 50 | 70% | 0.70, 0.40, 0.10 | 3.40 | **14.7** | 15 |
| North Atlantic | 51 | 50% | 0.50 | 2.00 | **25.5** | 26 |
| | **101** | | | | **40.2** | **41** |

**101 overlapping voyages carry the information of about 40 independent ones — which is what we
already have.**

### The reason, stated once

The information is bounded by **the length of the weather record**, not by how finely it is sliced.
The record holds $4404/280 = 15.7$ and $4410/168 = 26.2$ non-overlapping voyages, and consecutive
chaining already extracts 15 and 26 of them. Slicing the same 180 days more finely produces more
rows, not more weather. A t-test run on the 101 as though they were independent would report
p-values roughly $\sqrt{\mathrm{VIF}}$ too small — about 1.8× too confident on Route 1 — purely as an
artefact of the slicing.

### What it would actually take

Unchanged from the 09-28 estimate: powering the two null tests at 80% needs $n \approx 94$ and $218$
**independent** voyages, which is **1.8 and 4.2 years** of weather against 180 days now. No
re-slicing reaches that; only collection does.

---

## 4. Do it anyway — for these four things

The scheme is worth running. It just should not be sold as a power increase.

1. **It removes the departure-phase arbitrariness.** The current 41 depend on where the chain happens
   to start. A different starting hour gives 41 different voyages and slightly different numbers,
   and nothing in the paper shows that the result is insensitive to that choice. A 3.5-day stride
   samples 3.3× more phases on Route 1 and 2× on Route 2, which turns an unexamined assumption into
   a demonstrated robustness.
2. **It sharpens the proportions, which are headline claims.** §7.3 rests on "SR lost to Naive on 11
   of 26 North Atlantic voyages" and "satisfied on 30 of 41". Those are coarse: one voyage moves
   11/26 by four percentage points. With 51 departures the same proportion is estimated on twice the
   departures, and its confidence interval — computed with the dependence carried through — is the
   honest version of a number the discussion leans on heavily.
3. **It fills in Figure 4.** The span-versus-cost scatter has 41 points and the whole argument is
   where they fall relative to the diagonal. 101 points show the shape of the cloud, particularly
   whether the North Atlantic really straddles the line or merely has a few excursions above it.
4. **It is a sensitivity analysis the referee will ask for.** "Your 41 voyages are one tiling of the
   record; what happens under another?" is an obvious question, and the answer should be in the
   paper rather than improvised.

---

## 5. How the inference must change

**Do not run a paired t-test over the 101 as if independent.** Three honest options, in order of
preference:

| | Approach | Notes |
|---|---|---|
| (a) | **Report the tests on the 41 independent chained voyages; report the 101 as a robustness check** | Simplest and cleanest. The inference stays valid, the overlap does the job it is good at |
| (b) | **Moving-block bootstrap over the 101**, resampling blocks of at least $\lceil L/s \rceil$ consecutive voyages | Carries the dependence properly; gives valid CIs on means *and* on proportions |
| (c) | Report the t-test with $n_{\text{eff}}$ substituted for $n$ | Crude but defensible; must state VIF and how it was obtained |

**(a) is recommended**, with (b) if a confidence interval on the proportions is wanted.

Whichever is used, $\rho_k$ should be **measured from the runs** rather than taken from the
$1 - ks/L$ approximation above, which assumes voyage fuel behaves like a window average. The
empirical autocorrelation of the per-voyage differences is one line once the results exist, and it
either confirms the approximation or improves on it.

---

## 6. Compute

Measured from the existing runs.

| Stage | 41 voyages | 101 voyages |
|---|---|---|
| Deterministic (both planners, C++) | 55 min | **~2.3 h** |
| Stochastic | 1,433 re-plans | **~3,530 re-plans** |

The deterministic side is cheap and can run today. The stochastic side is the long pole: each voyage
is 35 re-plans on average, each a shrinking-horizon solve, and it has never been timed end to end —
**scope it before committing to the full set.** Running Route 2 alone (51 voyages, the route that
carries both null tests) gets the robustness result for roughly half the cost.

---

## 7. What to change in the harness

`run_rh.py` and the perfect-foresight chain driver both derive departures by chaining. Both need the
departure list to become an input:

- [ ] Add a `--departure-stride H` flag; chaining is the special case `stride = ETA`
- [ ] Emit `stride` and `overlap_h` into `results.csv` so a later reader can tell which tiling a row
      came from
- [ ] Keep the 41 chained voyages reproducible — the paper's current numbers must not move
- [ ] Add the empirical $\rho_k$ of the per-voyage differences to the analysis output

---

## 8. Recommendation

**Run it on Route 2 first**, as a robustness and proportion-sharpening exercise, and report the
significance tests on the independent 41. Say in the paper that the result is stable across
departure phase, which is worth having and is currently unevidenced.

**Do not use it to attack the two nulls.** They are not underpowered by an accident of sampling;
they are bounded by the record. The bound already computed — SR within $[-1.33, +0.19]$ mt of Naive
on the North Atlantic under forecasts — says what §7.3 wants to say, costs nothing, and does not
depend on how the record is tiled.

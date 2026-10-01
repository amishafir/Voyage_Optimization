# Design — §6.4 *Why imperfect information costs more on one route*, and the §7.3 replacement

**Origin:** the Atlantic stochastic gap (hypotheses design, same date). H1 and H2 are measured; H3 and
H5 are dropped at the author's direction; H4's mechanism is replaced rather than tested.
**Scope:** a new §6.4, a methods paragraph in §5.1, a new appendix, and one replaced paragraph in §7.3.
**Status:** design only. The exploratory runs exist; nothing in this design has been run in its final
form, because §4 changes how the measurement is made.

---

## 1. What this has to do

Two jobs, and they must not be confused with each other.

1. **Fill a claim the paper already makes.** §6.4 states that "forecast accuracy degraded
   systematically with lead time, which is what the forecast cost of Table~\ref{tab:span} measures".
   Nothing in the paper measures it.
2. **Replace a mechanism the paper's own numbers contradict.** §7.3 attributes the Atlantic result
   partly to the finer planner overfitting the forecast, with the block constraint acting as a
   regulariser. In the stochastic setting on that route SR saves 0.57 mt and Luo 0.24 mt — the
   block-locked planner does *worse*, which is the opposite of what the mechanism predicts.
   Independently, the paper no longer reports any SR-versus-Luo comparison, so the claim has lost its
   evidence base regardless of direction.

---

## 2. The quantity being explained

Stated once, in the frame §6.3 should adopt:

| | Span | Forecast cost | Captured |
|---|---|---|---|
| Indian Ocean | 9.66 mt (2.72%) | 4.46 mt | **53.8%** |
| North Atlantic | 4.47 mt (2.20%) | 3.90 mt | **12.8%** |

**Both terms matter and they pull in different directions depending on normalisation.** In absolute
tonnes the Atlantic's span is 54% smaller while its cost is 13% *smaller* too, so the span dominates
the capture gap. Per nautical mile the Atlantic's cost is 52% *larger* (1.996 against 1.315 kg/NM)
while its span is 20% smaller. §6.4 explains **the per-mile cost term only**, and must say so
explicitly; the span term is a separate question the paper already concedes is confounded (§6.1).

---

## 3. What is measured

### 3.1 Forecast error (H1)

For every forecast row: error $=$ predicted $-$ actual at the same node and the same valid time.

- **`sample_hour` is the issue time and `forecast_hour` is the lead**, so valid time is their sum.
  This was **verified, not assumed**: scoring both readings against the actuals gives MAE 6.87 km/h
  for the lead reading against 9.18 for the absolute reading on route 1 node 0. The check belongs in
  the methods paragraph.
- **Directions are circular.** Every direction error is wrapped to $[-180°, 180°]$ before summary. A
  plain difference reads 359° against 1° as a 358° error.
- **Four fields**, the ones the speed model consumes: wind speed, wind direction, current velocity,
  current direction. Beaufort is reported alongside wind speed but is a deterministic function of it,
  so it is **never counted as a separate contributor**. Wave height is excluded: not an input to any
  formula, settled 2026-09-08 (`afb9056`).
- Only leads that are multiples of 6 h are verifiable, since actuals are recorded every 6 h.

### 3.2 Fuel cost of an error (H2) — **by a 2×2 factorial, not a sensitivity coefficient**

The exploratory run used a fixed perturbation (+1 km/h, +10°) and multiplied by the measured error.
**That is not valid here**, for two reasons found while checking it:

- The response is **non-linear in the step**: mean $|\Delta\mathrm{FCR}|$ per km/h of wind error is
  0.00936 mt/h at a 0.5 km/h step and 0.00777 at 4.0 km/h, a 17% drift across the range.
- The two routes have **different error magnitudes** (wind MAE 3.7 against 5.0 km/h), so a common
  step evaluates them at different points on a curved response and biases the comparison.

**The design instead perturbs each case by a realistic error and crosses the two factors:**

| | perturbed by IO's error | perturbed by NA's error |
|---|---|---|
| **at IO conditions** | $A$ | $B$ |
| **at NA conditions** | $C$ | $D$ |

From which, with no additive or linearity assumption:

- **Effect of error magnitude (H1)** $= B/A$ — same conditions, the other route's error
- **Effect of conditions (H2)** $= C/A$ — same error, the other route's conditions
- **Interaction** $= D/(A \cdot (B/A) \cdot (C/A))$ — whether the two compound
- **Total** $= D/A$, which is the quantity to compare against the measured cost ratio

This is the whole of H1 and H2 in one estimand, and it answers "more error or costlier error" as a
decomposition rather than as a pair of separately-scaled numbers.

Each cell is computed at the route's own sampled weather states, holding the route's mean SOG target
$D/T$, with the heading taken from the route geometry: required SWS by inversion, then FCR, then the
difference against the unperturbed case.

---

## 4. Statistical validity — the threats, and what each requires

This is the part that must not be skipped. **The exploratory numbers quoted in conversation have none
of these controls and must not reach the paper as they stand.**

| # | Threat | Why it bites | Treatment |
|---|---|---|---|
| 1 | **Rows are not independent** | 15.7M forecast rows on route 1 come from ~715 issues over 131 nodes. Adjacent hours, neighbouring nodes and repeated verification against the same actual are all correlated | **Cluster bootstrap on forecast issue** (~715 and ~727 clusters). Resample issues with replacement, recompute the statistic, take percentile intervals |
| 2 | **Row counts masquerade as sample size** | "n = 92k" invites a reader to assume precision that is not there | Report **the number of issues**, never the row count, as $n$ |
| 3 | **Arbitrary perturbation step** | Response is non-linear; a common step evaluates the two routes at different points on the curve | Replaced by the 2×2 factorial of §3.2, each cell perturbed by a measured error |
| 4 | **Arbitrary lead band** | The wind-error ratio is 1.34 at 24–47 h and 2.18 at 120–160 h. Picking one picks the answer | Report **every band**; the headline uses a **reliance-weighted** lead distribution derived from the re-plan logs, stated as such |
| 5 | **Additive decomposition across parameters** | Summing $|\Delta\mathrm{FCR}|$ over four parameters assumes independence and no cancellation; errors are correlated and can offset | The factorial perturbs **all four fields jointly**, so no summing is required |
| 6 | **Multiple comparisons** | 4 fields × 7 bands × 2 routes is 56 contrasts | §6.4 reports **measurement with intervals, not hypothesis tests**. No p-value is attached to a route difference in forecast error |
| 7 | **Post-hoc direction** | "The Atlantic is worse" was read off the data | Presented as **descriptive measurement**, in the past tense, about these two routes and this product. No inferential claim about routes in general |
| 8 | **Sampling error in the factorial** | Each cell is a mean over sampled states | Bootstrap the state sample as well; report an interval per cell |

**Consequence to accept up front:** with ~715 effective clusters the intervals on MAE will be narrow
and the route difference in forecast error will be comfortably resolved. The intervals on the
*factorial ratios* will be wider, and the design should not promise that the interaction term is
resolvable.

---

## 5. What goes where

### §5.1, new paragraph — *Forecast error: how it is measured*
Three or four sentences: the issue/lead convention and that it was verified against the actuals;
circular wrapping for directions; the four consumed fields and why wave is excluded; that only
6-hourly leads are verifiable. **No results.**

### §6.4 — *Why imperfect information costs more on one route* (replaces *Supporting observations*)
The existing §6.4 is two sentences, one of which this section now evidences. It becomes:

1. One paragraph framing the question as the **per-mile cost term** of §6.3, explicitly not the span.
2. **Table — forecast error by lead band and route**, four fields, MAE with cluster-bootstrap
   interval, $n$ = issues. Full per-band detail to the appendix.
3. **Figure — MAE against lead, both routes.** Four small panels, one per field, shared lead axis.
   This is the clearest artefact in the analysis: the Atlantic's steeper decay is visible at a glance
   and invisible in a table. It also carries the one genuine surprise, that Atlantic **wind
   direction** is better forecast at short lead and worse only beyond ~48 h.
4. **Table — the 2×2 factorial**, four cells with intervals, and the three derived ratios.
5. One closing paragraph: what share of the measured per-mile cost ratio the factorial accounts for,
   **stated as consistency, not attribution**.

### Appendix E — *Forecast error in full*
Every field × every lead band × both routes, with bias, MAE, RMSE and interval. Pattern follows
Appendix D: `[H]`-pinned tables, a lead-in paragraph, placed before the references.

### §7.3 — the replaced paragraph
Keep the first mechanism (the Jensen argument; nothing contradicts it). Replace the second:

> The second is a property of the route rather than of the planner. The forecasts available on the
> North Atlantic are less accurate than those on the Indian Ocean at every lead beyond two days and
> degrade faster with lead; and because the conditions there sit higher on a convex fuel curve, a
> given error in the wind converts into more fuel. Section~\ref{sec:res-why} measures both.

This also upgrades §7.3's governing claim: "re-planning pays when the span exceeds the forecast
error" previously had only the span measured. Both terms are now measured.

---

## 6. Build order

1. Rewrite `make_forecast_error.py` to emit cluster-bootstrap intervals and report $n$ as issues
2. Rewrite `make_fuel_sensitivity.py` as the 2×2 factorial with bootstrapped cells
3. Derive the reliance-weighted lead distribution from the re-plan logs
4. Generate the figure
5. Write §5.1's paragraph, §6.4, Appendix E
6. Replace §7.3's second mechanism
7. Rebuild; verify no undefined references and that §6.4's numbers come from the generators

---

## 7. Open items for the author

| # | Item | Default |
|---|---|---|
| 1 | Does §6.4 keep the two sentences currently there about the 6 h cadence? | **Yes**, moved to the end; they are about the design, not the error |
| 2 | Four panels or one combined figure? | **Four panels** — the fields have different units and the wind-direction crossover is the point |
| 3 | Is the factorial reported in §6.4 or only in the appendix? | **§6.4**; it is the answer, not the detail |
| 4 | Should the span term get the same treatment? | **Not now.** §6.1 already concedes the routes are confounded on block length, and no experiment here separates it |

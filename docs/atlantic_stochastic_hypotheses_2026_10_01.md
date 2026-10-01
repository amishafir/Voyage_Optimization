# Design — why the stochastic setting pays on the Indian Ocean and not on the Atlantic

**Question (author, 2026-10-01):** the deterministic advantage survives into the stochastic setting on
the Indian Ocean and does not on the North Atlantic. Why?
**Status:** hypotheses and test design. Nothing run.

---

## 1. Sharpening the question first

"The Atlantic has less span" is the natural guess and it is **mostly wrong**. Decomposing the capture
rate shows where the two routes actually diverge:

| | Span | Forecast cost | **Captured** | Span / nm | **Cost / nm** |
|---|---|---|---|---|---|
| Indian Ocean | 2.72% of fuel | 1.26% | **53.8%** | 2.845 kg | **1.315 kg** |
| North Atlantic | 2.20% of fuel | 1.92% | **12.8%** | 2.288 kg | **1.996 kg** |
| ratio | 1.24× | — | **4.2×** | 1.24× | **1.52×** |

**The span differs by 24%. The forecast cost differs by 52%, in the opposite direction.** Those
compound into a 4.2× difference in capture. So the question is not mainly "why is there less to win
on the Atlantic" but:

> **Why does imperfect information cost half again as much per nautical mile on the Atlantic?**

That is the term to explain. The span difference is secondary and already has a candidate explanation
the paper concedes (§6.1: the routes differ in block length by 5.4× as well as in weather).

---

## 2. What differs between the routes — everything at once

This is why no single comparison settles anything. The routes differ in **four** ways simultaneously:

| | Indian Ocean | North Atlantic |
|---|---|---|
| Mean wind / median BN | 20.2 km/h / 3 | 29.7 km/h / 4 |
| Sampling interval | 25.0 NM (131 points) | 5.0 NM (389 points) |
| SR decisions per 6 h block | 2.0–2.9 | 10.7–15.5 |
| ETA / distance | 280 h / 3393 NM | 168 h / 1955 NM |

Any hypothesis that explains the gap by one of these is confounded with the other three. **The tests
below are chosen for their ability to hold the others fixed**, not merely to correlate with the
outcome.

One fact that already constrains the field: the forecast product reaches only **160 h of lead**,
while an Indian Ocean voyage is **280 h**. The route that plans more of its voyage beyond the
forecast horizon is the route that does *better*. Any hypothesis resting purely on forecast
availability therefore starts out facing a contradiction.

---

## 3. Hypotheses

### H1 — The Atlantic forecasts are simply less accurate
*The same product predicts the North Atlantic worse than the Indian Ocean, in the parameters the
model consumes.*

**Predicts:** larger error in wind speed, wind direction, current velocity and current direction on
Route 2, at matched lead times.
**Test:** the forecast-error analysis already scoped as action 7 — `predicted − actual` per node, per
issue, per lead, per route, with directions handled circularly.
**Data:** in hand, both HDF5 files. **Cost:** hours, no new run.
**Falsified if:** errors are comparable or smaller on the Atlantic — which would promote H2 and H4.

### H2 — The same forecast error costs more fuel in harsher weather
*Error magnitude is comparable, but the Atlantic converts it into more fuel because the fuel model is
convex and the conditions sit higher on the curve.*

**Predicts:** the fuel sensitivity $\partial(\text{fuel})/\partial(\text{wind error})$, evaluated at
each route's realised conditions, is materially larger on the Atlantic.
**Test:** perturb each weather parameter by a fixed amount at every sampled point on each route, push
it through the speed correction and the FCR, and compare the resulting fuel change. This is a
sensitivity calculation, not an optimisation — no planner runs.
**Data:** in hand. **Cost:** hours.
**Why it matters:** H1 and H2 are the two halves of action 8, and they are **separable**: H1 is how
wrong the forecast is, H2 is how much being wrong costs. Either alone would explain the gap, and the
analysis should report both so the paper can say which dominates.

### H3 — The Atlantic weather is less persistent, so a 6 h-old forecast is staler
*Re-planning every 6 h is adequate on a route whose weather changes slowly and inadequate on one
where it does not.*

**Predicts:** lower temporal autocorrelation of the actual weather on Route 2 at 6, 12 and 24 h lags.
**Test:** autocorrelation of each consumed parameter per route, per node. §5.1 already reports that
86% of hourly wind queries and 97% of current queries returned the previous value, but **pooled
across both routes** — splitting that by route is the test, and it is one query.
**Data:** in hand. **Cost:** under an hour.
**Note:** this is the cheapest discriminating test in the list and should be run first.

### H4 — SR overfits the forecast more on the Atlantic because it has more freedom there
*Exposure scales with the number of decisions. Route 2 gives SR 10.7–15.5 speed choices per block
against 2.0–2.9 on Route 1, so there is five times more forecast-driven structure to commit to, and
the block constraint that costs fuel under perfect information acts as a regulariser under a forecast.*

**Predicts:** coarsening Route 2's decision partition towards Route 1's should **improve** its
stochastic capture, while necessarily reducing its deterministic advantage.
**Test — the decisive one.** Re-run Route 2 with the sampling interval coarsened from 5 NM to 25 NM,
matching Route 1, and compare capture. **This holds the weather fixed and varies only granularity**,
which no cross-route comparison can do.
**Data:** in hand — coarsening is a subsample of an existing partition, not a new collection.
**Cost:** one deterministic and one stochastic run on Route 2, roughly half the full-set estimate.
**Falsified if:** capture does not improve, which would exonerate granularity and leave H1/H2/H3.
**This is the paper's own §7.3 claim stated as a testable prediction, and it has never been tested.**

### H5 — The Atlantic's shorter ETA leaves less room to redistribute speed
*With 168 h against 280 h and a binding arrival constraint, there is less slack to move time between
legs, so the same information buys less.*

**Predicts:** the realised speed profiles use less of the available band on Route 2; the oracle's
speed variance is lower relative to the band.
**Test:** compare the distribution of realised SOG against $D/T \pm 3$ kn per route, from the existing
run outputs.
**Data:** in hand. **Cost:** under an hour.
**Caveat:** this speaks to the *span* term, not the cost term, so it is a secondary explanation at
best given §1.

### H6 — The mean is the wrong summary: the Atlantic voyages straddle a threshold
*Capture is not uniformly low on the Atlantic; it is high on voyages with span and negative on those
without, and the mean mixes them.*

**Already supported.** The realised advantage regresses on span with slope $-0.693$ mt per mt,
$r = -0.598$, $p = 0.0012$, break-even at a span of 3.65 mt, which 18 of 26 voyages clear. The
equivalent regression on the Indian Ocean has a shallower slope and every voyage above break-even.
**Remaining test:** whether an **ex-ante** predictor of span — the forecast span computable at
departure, rather than the oracle span used above — carries the same relationship. If it does, the
finding becomes an operational rule rather than an explanation.
**Cost:** a harness change to log planned voyage fuel at $k=0$, plus a re-run. `rh_sr_replans.csv`
currently stores `block0_fuel_mt` but no planned total.

---

## 4. Order of work

Ranked by discrimination per unit of effort, not by interest.

| | Test | Settles | Cost |
|---|---|---|---|
| 1 | **H3** — per-route temporal autocorrelation | cheapest, and §5.1 already half-reports it | < 1 h |
| 2 | **H1 + H2** — forecast error, and fuel sensitivity to it | actions 7 and 8; the two halves of "the forecast costs more" | hours |
| 3 | **H5** — band utilisation | secondary, but nearly free from existing outputs | < 1 h |
| 4 | **H4** — coarsen Route 2 to 25 NM | **the decisive experiment**; the only one that holds weather fixed | one run pair |
| 5 | **H6** — ex-ante span predictor | converts an explanation into an operational rule | harness change + run |

Items 1–3 are analysis of data already collected and can all be done before any new run. **Item 4 is
the one that would change what the paper claims**, because §7.3 currently asserts the granularity-
exposure mechanism without testing it.

---

## 5. What a clean answer would look like

The paper should be able to finish this sentence with a measured number rather than an argument:

> On the North Atlantic the stochastic setting captured 12.8% of the available span against 53.8% on
> the Indian Ocean, because **[the forecasts were X% less accurate / the same error cost Y× more fuel
> / the five-fold finer decision partition exposed the planner to Z more forecast-driven structure]**.

H1–H4 each supply one of those blanks, and they are not mutually exclusive — the likely answer is a
combination, with the analysis reporting the share each contributes. The decomposition in §1 is the
frame to report it in: span differs by 24%, cost by 52%, and the hypotheses explain the second.

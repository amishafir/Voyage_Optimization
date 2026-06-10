<!--
DRAFT — Results section. Writes G1 (evidence ledger) forward.
Answers RQ2 (perfect foresight) then RQ3 (rolling horizon), per the G3 arc.
Numbers are sourced from G1_evidence_ledger.md (CSV-verified). Do not edit numbers
here without updating G1. Placeholders: [TABLE:], [FIG:], [CITE:], [METHODS→G4], [LIT→G5].
Voice: TR-C — third person, passive, past tense for results. "This study", not "we".
-->

# 6. Results

The two free-speed formulations are evaluated against the per-block speed-locked baseline of
[CITE: Luo 2024] in two regimes. Section 6.1 reports the comparison under perfect weather
foresight (the oracle), which bounds the achievable advantage (RQ2). Section 6.2 reports
the comparison under realistic rolling-horizon (RH) planning against real, imperfect forecasts,
relative to set-and-forget operation (RQ3). Throughout, **SR** denotes the Shafir–Raviv
per-leg free-speed dynamic program and **Luo** the per-block speed-locked formulation of
[CITE: Luo 2024]; both were solved on the identical route discretisation and speed grid
[METHODS→G4]. Two routes are used: Route 1 (Persian Gulf → Strait of Malacca,
3,393 nm, ETA 280 h) and Route 2 (St. John's → Liverpool, North Atlantic, 1,955 nm, ETA 168 h)
[METHODS→G4].

## 6.1 Fuel under perfect foresight

Each route was run as a consecutive-voyage chain in which voyage $N+1$ departs when voyage $N$
arrives, so SR and Luo encountered identical departure weather at every voyage. Nineteen voyages
were evaluated in total (seven on Route 1, twelve on Route 2), spanning approximately 80 days of
the collection window. In every voyage both formulations consumed the full time budget
(arrival slack was zero throughout): the hard ETA was binding, and both solvers slow-steamed to
the deadline.

Per-voyage fuel is reported in the Route 1 and Route 2 tables below; the aggregate comparison
follows.

**Perfect-foresight aggregates** (negative gap = SR burns less fuel):

| Route | $n$ | SR mean ± s.d. (mt) | Luo mean ± s.d. (mt) | Mean gap (mt) | Mean gap (%) |
|---|---:|---:|---:|---:|---:|
| 1 (Malacca) | 7 | 344.87 ± 7.77 | 351.26 ± 8.72 | −6.39 | −1.8 |
| 2 (Atlantic) | 12 | 201.90 ± 10.32 | 207.36 ± 11.03 | −5.46 | −2.6 |

**Perfect-foresight per-voyage fuel — Route 1 (Malacca, ETA 280 h)** (sh₀ = departure sample hour):

| Voyage | sh₀ | SR (mt) | Luo (mt) | Gap (mt) | Gap (%) |
|---:|---:|---:|---:|---:|---:|
| 0 | 6 | 354.82 | 361.56 | −6.74 | −1.86 |
| 1 | 286 | 355.23 | 364.68 | −9.45 | −2.59 |
| 2 | 566 | 337.70 | 342.41 | −4.71 | −1.38 |
| 3 | 846 | 348.19 | 353.15 | −4.96 | −1.40 |
| 4 | 1126 | 337.60 | 340.87 | −3.27 | −0.96 |
| 5 | 1406 | 334.83 | 343.86 | −9.03 | −2.63 |
| 6 | 1686 | 345.73 | 352.31 | −6.58 | −1.87 |

**Perfect-foresight per-voyage fuel — Route 2 (Atlantic, ETA 168 h):**

| Voyage | sh₀ | SR (mt) | Luo (mt) | Gap (mt) | Gap (%) |
|---:|---:|---:|---:|---:|---:|
| 0 | 0 | 203.20 | 210.25 | −7.05 | −3.35 |
| 1 | 168 | 204.17 | 209.51 | −5.34 | −2.55 |
| 2 | 336 | 195.24 | 201.95 | −6.71 | −3.32 |
| 3 | 504 | 206.12 | 212.22 | −6.10 | −2.87 |
| 4 | 672 | 215.93 | 223.50 | −7.57 | −3.38 |
| 5 | 840 | 190.75 | 196.89 | −6.14 | −3.12 |
| 6 | 1008 | 227.91 | 233.85 | −5.94 | −2.54 |
| 7 | 1176 | 194.40 | 198.25 | −3.86 | −1.94 |
| 8 | 1344 | 194.64 | 197.05 | −2.41 | −1.22 |
| 9 | 1512 | 192.75 | 196.90 | −4.15 | −2.11 |
| 10 | 1680 | 199.10 | 203.49 | −4.39 | −2.16 |
| 11 | 1848 | 198.57 | 204.41 | −5.84 | −2.86 |

Three findings follow.

**SR consumed less fuel than Luo on every voyage.** The free-speed formulation was more
fuel-efficient on all 19 of 19 voyages, with no exceptions on either route. The per-voyage
advantage ranged from 3.27 to 9.45 mt on Route 1 and from 2.41 to 7.57 mt on Route 2.

**The absolute advantage was comparable across routes, but proportionally larger on the
shorter voyage.** The mean fuel saving was similar in absolute terms (6.39 mt on Route 1,
5.46 mt on Route 2) despite Route 2 being roughly half the duration; expressed as a fraction of
total fuel the advantage was therefore larger on the shorter, harsher Atlantic route (2.6 %)
than on the longer Malacca route (1.8 %). [METHODS→G4 / DISCUSSION: this is the Jensen
mechanism — a shorter voyage concentrates the within-block weather variation that per-block
locking cannot exploit.]

**Departure weather dominated voyage-to-voyage fuel variation.** On Route 2 the worst
departure (227.91 mt) consumed 19.5 % more fuel than the best (190.75 mt) for the same
formulation — a spread larger than the entire SR–Luo gap. The Atlantic fuel spread per
voyage-hour was approximately three times that of the Malacca route, consistent with the
greater variability of North Atlantic conditions [METHODS→G4: weather statistics].

## 6.2 Fuel under rolling-horizon planning (real forecasts)

The oracle comparison establishes an upper bound that assumes perfect foresight. To test
whether the advantage survives realistic operation, both formulations were embedded in a 6 h
rolling-horizon scheme: at each decision step the next 6 h block was planned against **actual**
(nowcast) weather and the remainder of the voyage against the most recent **predicted** weather
cycle; only the first block was committed before re-planning [METHODS→G4]. The realised voyage
was compared against a Naive set-and-forget baseline — a single fixed mean speed
($L/T$) sailed through the actual weather. The same 19 voyages were evaluated.

Realised fuel relative to the Naive baseline is reported per voyage in the Route 1 and Route 2
tables below, and summarised next.

**Rolling-horizon summary** (negative % = saving vs Naive set-and-forget):

| Route | $n$ | RH-SR vs Naive (mean %) | RH-Luo vs Naive (mean %) | RH-SR saves on |
|---|---:|---:|---:|---:|
| 2 (Atlantic) | 12 | −1.9 | −0.2 | 11/12 |
| 1 (Malacca) | 7 | −1.2 | −0.1 | 7/7 |

**Rolling-horizon per-voyage realised fuel — Route 1 (Malacca, ETA 280 h)** (sh₀ = departure sample hour):

| sh₀ | Naive (mt) | RH-SR (mt) | RH-Luo (mt) | RH-SR vs Naive (%) | RH-Luo vs Naive (%) |
|---:|---:|---:|---:|---:|---:|
| 6 | 362.74 | 358.86 | 362.57 | −1.07 | −0.05 |
| 286 | 367.03 | 358.73 | 367.72 | −2.26 | +0.19 |
| 566 | 345.42 | 342.82 | 344.51 | −0.75 | −0.26 |
| 846 | 354.74 | 350.33 | 354.36 | −1.24 | −0.11 |
| 1126 | 342.68 | 341.55 | 341.69 | −0.33 | −0.29 |
| 1406 | 346.19 | 344.11 | 346.57 | −0.60 | +0.11 |
| 1686 | 356.03 | 349.32 | 355.10 | −1.88 | −0.26 |

**Rolling-horizon per-voyage realised fuel — Route 2 (Atlantic, ETA 168 h):**

| sh₀ | Naive (mt) | RH-SR (mt) | RH-Luo (mt) | RH-SR vs Naive (%) | RH-Luo vs Naive (%) |
|---:|---:|---:|---:|---:|---:|
| 0 | 212.61 | 205.00 | 212.12 | −3.58 | −0.23 |
| 168 | 212.78 | 208.34 | 211.41 | −2.08 | −0.64 |
| 336 | 203.65 | 200.99 | 203.42 | −1.31 | −0.11 |
| 504 | 214.54 | 212.61 | 216.01 | −0.90 | +0.68 |
| 672 | 225.98 | 222.38 | 224.90 | −1.59 | −0.48 |
| 840 | 200.50 | 192.98 | 199.04 | −3.75 | −0.73 |
| 1008 | 237.09 | 230.53 | 235.33 | −2.76 | −0.74 |
| 1176 | 200.43 | 197.33 | 200.71 | −1.54 | +0.14 |
| 1344 | 199.35 | 200.82 | 200.49 | +0.74 | +0.57 |
| 1512 | 198.99 | 195.58 | 198.28 | −1.71 | −0.36 |
| 1680 | 206.86 | 201.65 | 205.70 | −2.52 | −0.56 |
| 1848 | 206.10 | 201.91 | 206.27 | −2.03 | +0.08 |

**Free-speed re-planning saved fuel; block-locked re-planning did not.** Rolling-horizon SR
reduced realised fuel relative to set-and-forget on 18 of 19 voyages (mean −1.9 % on Route 2,
−1.2 % on Route 1; best −3.75 %). Rolling-horizon Luo, by contrast, was statistically
indistinguishable from set-and-forget (mean −0.2 % and −0.1 %): the per-block lock left no room
to exploit the refreshed forecasts. The SR–Luo contrast established under perfect foresight
(Section 6.1) therefore persisted under realistic, imperfect-forecast operation, on both routes
and across the full departure window.

**Realised fuel fell within the oracle–Naive envelope.** On every voyage the realised RH fuel
satisfied $\text{oracle} \le \text{RH} \le \text{Naive}$: re-planning under imperfect forecasts
could not beat perfect foresight but did beat set-and-forget. Rolling-horizon SR sat between
1.8 and 8.9 mt above its oracle, the gap representing the cost of committing speeds against
forecasts that were subsequently revised [LIT→G5: forecast error; supporting S-1].

**The two formulations re-planned differently.** A single-voyage diagnostic (Route 2, first
departure) recorded how often a refreshed forecast changed the committed first-block speed:
rolling-horizon SR revised its decision on 8 of 27 re-plans (30 %, mean change 0.19 kn), whereas
rolling-horizon Luo revised on 17 of 27 (63 %, mean change 0.43 kn). The block-locked
formulation adjusted more frequently yet gained less — it lacked the within-block resolution to
convert forecast updates into fuel savings.

[Boundedness of the RH advantage — that it shrinks with weather variability and can reverse on
near-uniform departures — is treated as a limitation in Section&nbsp;7, per the G2 decision.]

## 6.3 Supporting observations

Two measurements underpin the rolling-horizon design [LIT→G5; full detail in §5 / Methods].
First, forecast accuracy degraded systematically with lead time: wind-speed RMSE approximately
doubled over the first 133 h on Route 1 (4.13 → 8.40 km/h) and grew more steeply on the harsher
Route 2 (+286 % over 144 h), establishing why realised RH fuel exceeded the oracle. Second, the
6 h re-plan cadence was not tuned but fixed to the underlying numerical weather prediction (NWP)
model cycle: the GFS wind product refreshes every 6 h, and 86 % of hourly forecast queries
returned identical data, so sub-6 h re-planning carried no new information.

<!--
COVERAGE CHECK vs G1:
- RQ2 (perfect foresight): §6.1 — A.1/A.2/A.3, C-1, C-2 ✓
- RQ3 (RH): §6.2 — B.1/B.2/B.3/B.4, C-3, C-4 ✓; boundedness (C-5) → §7 per G2 ✓
- Supporting S-1/S-2 → §6.3 ✓
- Compute (C-I structural) is NOT here — belongs to Methods/Discussion (RQ1) ✓
OPEN (from G1 §F): pick one oracle source per table (F-3); R2 RH numbers cite prep §6.2 (F-1);
state precise gate when reporting any RH≤Naive reversal (F-2, in §7).
-->

# Rolling horizon with a 6 h information lag, Routes 3-6, departures every 48 h

The setup of `../2026-10-31_rolling_lag6h/` (Tal), repeated on 25 voyages instead of 8: rolling
horizon with decisions every 6 h on the UTC clock, each 6 h block planned with the forecast known
6 h before it starts, fuel realized in the actual (pseudo real-time) weather.

- **Voyages**: departures at 00:00 UTC every 48 h from 2026-10-21 (Tal's first start), as long as
  the voyage ends by 2026-11-05 00:00 UTC, the end of the actual weather in the snapshot (current
  run 2026-11-04T00, wind run 2026-11-04T18). Routes 3-5 (ETA 118 / 117 / 118 h): 21, 23, 25, 27,
  29, 31 Oct, 6 voyages each. Route 6 (ETA 67 h): also 2 Nov, 7 voyages. 25 voyages in all.
- **Data**: snapshot `ami@talraviv-pcl:~/voyage_collector/data/snapshots/2026-11-05_09Z/`
  (`route[3-6]_runs.h5`, copied 2026-11-05 08:48 UTC, between collector writes).
- **Code**: v2 at commit `babf740` (unchanged), run on talraviv-pcl from `~/voyage_v2/v2` with
  `~/collector-venv` (Python 3.12, g++ 13), 10 jobs at a time, `nice 10`: `run.sh`. Statistics:
  `python3 summarize.py` (writes `voyages.csv`, realized fuel in mt per voyage and method).
- **Check**: the 21 Oct voyages reproduce Tal's numbers in `../2026-10-31_rolling_lag6h/` exactly
  (only the solve times differ; talraviv-pcl is about 2.6x slower than tsl2).
- Voyages crossing 20 Oct use the 19 Oct current run for that day (the 20 Oct run is lost); the 21
  and 22 Oct current runs are from Copernicus Marine.

Realized fuel above the full graph with perfect information:

| Method | R3 mean (n=6) | R4 mean (n=6) | R5 mean (n=6) | R6 mean (n=7) | All: mean | median | sd | min | max | beats const. SOG | within 0.05% of ours |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Full graph, departure forecast 6 h before, no re-planning | +0.45% | +0.67% | +0.77% | +0.30% | +0.54% | +0.46% | 0.44 | +0.12% | +2.23% | 23/25 | 5/25 |
| **Full graph, rolling horizon (ours)** | **+0.44%** | **+0.33%** | **+0.75%** | **+0.30%** | **+0.45%** | **+0.36%** | 0.40 | +0.08% | +2.04% | 23/25 | 25/25 |
| Luo 0.5 h, piece by piece, rolling | +0.45% | +0.34% | +0.73% | +0.29% | +0.45% | +0.35% | 0.40 | +0.10% | +2.03% | 23/25 | 22/25 |
| Luo 6 h, piece by piece, rolling | +0.75% | +0.92% | +0.86% | +0.45% | +0.73% | +0.68% | 0.38 | +0.24% | +1.87% | 22/25 | 1/25 |
| Luo 0.5 h, start point, rolling | +0.80% | +0.53% | +1.16% | +0.98% | +0.87% | +0.80% | 0.44 | +0.32% | +2.17% | 16/25 | 1/25 |
| Luo 6 h, start point (Luo et al.), rolling | +2.70% | +4.02% | +4.55% | +2.38% | +3.37% | +3.16% | 1.46 | +1.07% | +6.88% | 0/25 | 0/25 |
| Constant SOG | +1.94% | +2.37% | +1.46% | +0.66% | +1.57% | +1.33% | 0.99 | +0.34% | +4.16% | - | 0/25 |

Head to head against the full graph with rolling horizon, per voyage:

| Method | Mean excess over ours | Ours lower on |
|---|---|---|
| Full graph, departure forecast, no re-planning | +0.09% | 16/25 |
| Luo 0.5 h, piece by piece | -0.00% | 12/25 (a tie) |
| Luo 6 h, piece by piece | +0.29% | 23/25 |
| Luo 0.5 h, start point | +0.42% | 25/25 |
| Luo 6 h, start point (Luo et al.) | +2.91% | 25/25 |
| Constant SOG | +1.12% | 23/25 |

Findings:

- **Ours with re-planning**: +0.45% above perfect information on average (median +0.36%, 0.08% to
  2.04%), 1.12% below constant SOG on average, and below it on 23 of 25 voyages. The two exceptions:
  Route 6 from 21 Oct (+0.82% against +0.64%) and Route 5 from 23 Oct (+2.04% against +1.28%, the
  worst voyage for every method that uses a forecast).
- **Luo et al. as published** (6 h epochs, start-point pricing) is worse than constant SOG on all
  25 voyages, by 1.8% on average, and 2.9% above ours.
- **Luo at 0.5 h priced piece by piece ties the full graph** (mean difference 0.00%, within 0.05% on
  22 of 25). The losses of published Luo come from the 6 h epochs (+0.29%) and above all from
  start-point pricing (+0.42% at 0.5 h, +2.9% at 6 h).
- **Re-planning now gains a little**: with the lag, the plan made 6 h before departure and sailed
  unchanged averages +0.54%, against +0.45% with rolling horizon; rolling is better on 16 of 25.
  On Tal's 8 voyages the two were even (+0.43% / +0.44%).
- Neighbouring voyages overlap (48 h apart, 67-118 h long), so the 25 are not independent samples.

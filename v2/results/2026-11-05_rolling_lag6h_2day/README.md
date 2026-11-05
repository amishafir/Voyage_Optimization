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

Realized fuel above the full graph with perfect information, each route on its own (the routes
differ in length, fuel and weather, so voyages are not pooled across routes). "vs ours" is the
method's realized fuel over the full graph with rolling horizon, per voyage; "ours lower on" counts
the voyages where ours burns less.

### Route 3: 6 voyages (2026-10-21, 2026-10-23, 2026-10-25, 2026-10-27, 2026-10-29, 2026-10-31); perfect information 143.9-171.5 mt

| Method | mean | median | sd | min | max | vs ours (mean) | ours lower on | beats const. SOG |
|---|---|---|---|---|---|---|---|---|
| Full graph, departure forecast 6 h before, no re-planning | +0.45% | +0.45% | 0.26 | +0.12% | +0.85% | +0.01% | 2/6 | 6/6 |
| **Full graph, rolling horizon (ours)** | +0.44% | +0.34% | 0.29 | +0.18% | +0.99% | - | - | 6/6 |
| Luo 0.5 h, piece by piece, rolling | +0.45% | +0.34% | 0.31 | +0.17% | +1.05% | +0.01% | 2/6 | 6/6 |
| Luo 6 h, piece by piece, rolling | +0.75% | +0.76% | 0.22 | +0.49% | +1.08% | +0.30% | 6/6 | 6/6 |
| Luo 0.5 h, start point, rolling | +0.80% | +0.74% | 0.42 | +0.35% | +1.58% | +0.35% | 6/6 | 6/6 |
| Luo 6 h, start point (Luo et al.), rolling | +2.70% | +2.40% | 1.09 | +1.61% | +4.70% | +2.25% | 6/6 | 0/6 |
| Constant SOG | +1.94% | +2.09% | 0.49 | +1.33% | +2.43% | +1.50% | 6/6 | - |

### Route 4: 6 voyages (2026-10-21, 2026-10-23, 2026-10-25, 2026-10-27, 2026-10-29, 2026-10-31); perfect information 144.9-182.9 mt

| Method | mean | median | sd | min | max | vs ours (mean) | ours lower on | beats const. SOG |
|---|---|---|---|---|---|---|---|---|
| Full graph, departure forecast 6 h before, no re-planning | +0.67% | +0.84% | 0.29 | +0.23% | +0.88% | +0.34% | 6/6 | 6/6 |
| **Full graph, rolling horizon (ours)** | +0.33% | +0.31% | 0.17 | +0.09% | +0.59% | - | - | 6/6 |
| Luo 0.5 h, piece by piece, rolling | +0.34% | +0.32% | 0.17 | +0.10% | +0.61% | +0.01% | 5/6 | 6/6 |
| Luo 6 h, piece by piece, rolling | +0.92% | +0.90% | 0.24 | +0.60% | +1.22% | +0.59% | 6/6 | 6/6 |
| Luo 0.5 h, start point, rolling | +0.53% | +0.53% | 0.15 | +0.32% | +0.71% | +0.20% | 6/6 | 6/6 |
| Luo 6 h, start point (Luo et al.), rolling | +4.02% | +3.97% | 0.97 | +2.51% | +5.20% | +3.68% | 6/6 | 0/6 |
| Constant SOG | +2.37% | +2.28% | 0.69 | +1.40% | +3.15% | +2.04% | 6/6 | - |

### Route 5: 6 voyages (2026-10-21, 2026-10-23, 2026-10-25, 2026-10-27, 2026-10-29, 2026-10-31); perfect information 146.7-171.1 mt

| Method | mean | median | sd | min | max | vs ours (mean) | ours lower on | beats const. SOG |
|---|---|---|---|---|---|---|---|---|
| Full graph, departure forecast 6 h before, no re-planning | +0.77% | +0.67% | 0.76 | +0.15% | +2.23% | +0.02% | 4/6 | 5/6 |
| **Full graph, rolling horizon (ours)** | +0.75% | +0.57% | 0.65 | +0.29% | +2.04% | - | - | 5/6 |
| Luo 0.5 h, piece by piece, rolling | +0.73% | +0.54% | 0.65 | +0.27% | +2.03% | -0.02% | 0/6 | 5/6 |
| Luo 6 h, piece by piece, rolling | +0.86% | +0.65% | 0.55 | +0.33% | +1.87% | +0.11% | 5/6 | 5/6 |
| Luo 0.5 h, start point, rolling | +1.16% | +0.93% | 0.60 | +0.68% | +2.17% | +0.41% | 6/6 | 3/6 |
| Luo 6 h, start point (Luo et al.), rolling | +4.55% | +4.10% | 1.43 | +3.05% | +6.88% | +3.77% | 6/6 | 0/6 |
| Constant SOG | +1.46% | +0.98% | 1.34 | +0.63% | +4.16% | +0.71% | 5/6 | - |

### Route 6: 7 voyages (2026-10-21, 2026-10-23, 2026-10-25, 2026-10-27, 2026-10-29, 2026-10-31, 2026-11-02); perfect information 63.1-86.1 mt

| Method | mean | median | sd | min | max | vs ours (mean) | ours lower on | beats const. SOG |
|---|---|---|---|---|---|---|---|---|
| Full graph, departure forecast 6 h before, no re-planning | +0.30% | +0.20% | 0.19 | +0.12% | +0.59% | +0.00% | 4/7 | 6/7 |
| **Full graph, rolling horizon (ours)** | +0.30% | +0.22% | 0.26 | +0.08% | +0.82% | - | - | 6/7 |
| Luo 0.5 h, piece by piece, rolling | +0.29% | +0.22% | 0.25 | +0.10% | +0.83% | -0.00% | 5/7 | 6/7 |
| Luo 6 h, piece by piece, rolling | +0.45% | +0.38% | 0.31 | +0.24% | +1.14% | +0.16% | 6/7 | 5/7 |
| Luo 0.5 h, start point, rolling | +0.98% | +0.88% | 0.27 | +0.59% | +1.43% | +0.68% | 7/7 | 1/7 |
| Luo 6 h, start point (Luo et al.), rolling | +2.38% | +1.75% | 1.29 | +1.07% | +4.68% | +2.07% | 7/7 | 0/7 |
| Constant SOG | +0.66% | +0.64% | 0.19 | +0.34% | +0.88% | +0.36% | 6/7 | - |

Findings, route by route:

- **Ours beats constant SOG on every voyage of Routes 3 and 4** (by 1.50% and 2.04% on average),
  on 5 of 6 on Route 5 (0.71%) and 6 of 7 on Route 6 (0.36%). The exceptions are Route 5 from
  23 Oct (+2.04% against +1.28%, the worst voyage for every method that uses a forecast) and
  Route 6 from 21 Oct (+0.82% against +0.64%).
- **Luo et al. as published** (6 h epochs, start-point pricing) is above constant SOG on every
  voyage of every route, and above ours by 2.25% (Route 3), 3.68% (Route 4), 3.77% (Route 5)
  and 2.07% (Route 6).
- **Luo 0.5 h priced piece by piece ties the full graph on every route** (mean differences
  -0.02% to +0.01%). Most of published Luo's loss is start-point pricing; the 6 h epochs add
  0.11-0.59%.
- **Re-planning pays only on Route 4** (+0.34% for the plan made 6 h before departure and sailed
  unchanged, worse than rolling on 6 of 6). On Routes 3, 5 and 6 the two are within 0.02%.
- Neighbouring voyages of a route overlap (48 h apart, 67-118 h long), so the 6-7 voyages per
  route are not independent samples.

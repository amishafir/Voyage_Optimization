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


## Epoch convergence and computation (`plot_epochs.py`, `count_ops.py`)

Luo re-run on the same 25 voyages (same rolling horizon, 6 h lag) at epochs of 3, 2, 1.5, 1 and
0.25 h (`run_epochs.sh`, outputs in `epochs/`), next to the 6 h and 0.5 h runs above. The
computation is counted by the C++ core (nodes, arcs, SWS evaluations, `Plan.stats`), summed over
every re-plan: `count_ops.py` re-runs each voyage with the v2 code unchanged, only recording the
stats (`run_ops.sh`, outputs in `ops/`; its realized fuel equals the CLI outputs on all 25 voyages
and 15 methods). Arcs measure the work independently of the machine; SWS evaluations understate
Luo's growth, since Luo caches the fuel rate per (subsegment, step, advance) within an epoch, so
its piece-by-piece evaluations stay near 30 M (Route 3) from 6 h to 0.25 h while its arcs grow
about 4x per halving of the epoch. Solve times are from talraviv-pcl with 10 voyages in parallel
(comparable within this run only).

- `epoch_convergence.png/.pdf`: fuel above perfect information against the epoch, per route.
- `epoch_tradeoff.png/.pdf`: the same fuel against arcs (log scale), with the full graph as a point.
- `epochs.csv`: realized fuel per voyage and method; `ops/*.csv`: counts per voyage and method.

Findings, per route:

- **Piece-by-piece pricing converges to the full graph by 1-2 h epochs on every route** and stays
  there to 0.25 h (Route 3: +0.75% at 6 h, +0.44% at 1 h, full graph +0.44%; Route 6: +0.45%,
  +0.30%, +0.30%). At 1 h it needs about 110 M arcs on Routes 3-5 against 6.1-6.4 G for the full
  graph, about 55x less.
- **Start-point pricing does not converge** within the range: still +0.63% / +0.47% / +1.05% /
  +0.75% at 0.25 h against the full graph's +0.44% / +0.33% / +0.75% / +0.30%, with as many arcs
  as piece by piece. Luo et al. (6 h, start point) is above constant SOG on every route.
- So the fuel gap of published Luo comes from its pricing first and its epoch length second; the
  full graph's distance lines add nothing measurable once Luo's arcs are priced piece by piece at
  epochs of 1-2 h or less.

**Route 3** (6 voyages; means per voyage, all re-plans)

| Method | Fuel above perfect information | Arcs | SWS evaluations | Solve time (s) |
|---|---|---|---|---|
| **Full graph** | +0.44% | 6,326.4 M | 4,264.2 M | 389.6 |
| Luo 6 h, piece by piece | +0.75% | 2.7 M | 27.8 M | 7.7 |
| Luo 3 h, piece by piece | +0.53% | 11.6 M | 30.1 M | 11.5 |
| Luo 2 h, piece by piece | +0.47% | 26.7 M | 30.8 M | 13.9 |
| Luo 1.5 h, piece by piece | +0.46% | 48.1 M | 31.3 M | 16.4 |
| Luo 1 h, piece by piece | +0.44% | 109.6 M | 31.7 M | 23.5 |
| Luo 0.5 h, piece by piece | +0.45% | 444.0 M | 32.1 M | 38.6 |
| Luo 0.25 h, piece by piece | +0.45% | 1,787.0 M | 32.2 M | 71.8 |
| Luo 6 h, start point | +2.70% | 2.7 M | 1.0 M | 1.8 |
| Luo 3 h, start point | +1.80% | 11.6 M | 2.3 M | 2.2 |
| Luo 2 h, start point | +1.50% | 26.7 M | 3.6 M | 2.4 |
| Luo 1.5 h, start point | +1.18% | 48.0 M | 4.9 M | 2.6 |
| Luo 1 h, start point | +1.05% | 110.1 M | 7.6 M | 3.6 |
| Luo 0.5 h, start point | +0.80% | 445.8 M | 15.6 M | 7.7 |
| Luo 0.25 h, start point | +0.63% | 1,791.3 M | 31.4 M | 21.0 |

**Route 4** (6 voyages; means per voyage, all re-plans)

| Method | Fuel above perfect information | Arcs | SWS evaluations | Solve time (s) |
|---|---|---|---|---|
| **Full graph** | +0.33% | 6,061.0 M | 4,515.0 M | 413.9 |
| Luo 6 h, piece by piece | +0.92% | 2.6 M | 20.5 M | 6.1 |
| Luo 3 h, piece by piece | +0.58% | 11.1 M | 22.1 M | 8.5 |
| Luo 2 h, piece by piece | +0.49% | 25.7 M | 22.7 M | 11.4 |
| Luo 1.5 h, piece by piece | +0.41% | 46.4 M | 23.1 M | 13.5 |
| Luo 1 h, piece by piece | +0.34% | 105.7 M | 23.4 M | 16.3 |
| Luo 0.5 h, piece by piece | +0.34% | 428.2 M | 23.8 M | 29.0 |
| Luo 0.25 h, piece by piece | +0.31% | 1,724.8 M | 24.0 M | 57.9 |
| Luo 6 h, start point | +4.02% | 2.6 M | 0.8 M | 1.7 |
| Luo 3 h, start point | +2.53% | 11.2 M | 1.7 M | 1.8 |
| Luo 2 h, start point | +1.39% | 25.8 M | 2.7 M | 2.1 |
| Luo 1.5 h, start point | +1.13% | 46.4 M | 3.6 M | 2.4 |
| Luo 1 h, start point | +0.93% | 105.8 M | 5.6 M | 2.8 |
| Luo 0.5 h, start point | +0.53% | 428.4 M | 11.4 M | 6.0 |
| Luo 0.25 h, start point | +0.47% | 1,723.7 M | 23.2 M | 18.6 |

**Route 5** (6 voyages; means per voyage, all re-plans)

| Method | Fuel above perfect information | Arcs | SWS evaluations | Solve time (s) |
|---|---|---|---|---|
| **Full graph** | +0.75% | 6,363.2 M | 4,524.0 M | 417.8 |
| Luo 6 h, piece by piece | +0.86% | 2.7 M | 22.7 M | 6.2 |
| Luo 3 h, piece by piece | +0.75% | 11.8 M | 24.5 M | 8.7 |
| Luo 2 h, piece by piece | +0.72% | 27.3 M | 25.1 M | 11.4 |
| Luo 1.5 h, piece by piece | +0.73% | 49.2 M | 25.5 M | 13.4 |
| Luo 1 h, piece by piece | +0.75% | 112.0 M | 25.8 M | 16.9 |
| Luo 0.5 h, piece by piece | +0.73% | 453.7 M | 26.1 M | 27.0 |
| Luo 0.25 h, piece by piece | +0.75% | 1,823.0 M | 26.3 M | 46.5 |
| Luo 6 h, start point | +4.55% | 2.7 M | 0.8 M | 1.6 |
| Luo 3 h, start point | +2.68% | 11.8 M | 1.9 M | 1.8 |
| Luo 2 h, start point | +2.27% | 27.1 M | 2.9 M | 2.0 |
| Luo 1.5 h, start point | +1.81% | 48.8 M | 4.0 M | 2.3 |
| Luo 1 h, start point | +1.57% | 111.6 M | 6.1 M | 3.0 |
| Luo 0.5 h, start point | +1.16% | 454.3 M | 12.6 M | 5.5 |
| Luo 0.25 h, start point | +1.05% | 1,827.6 M | 25.7 M | 15.0 |

**Route 6** (7 voyages; means per voyage, all re-plans)

| Method | Fuel above perfect information | Arcs | SWS evaluations | Solve time (s) |
|---|---|---|---|---|
| **Full graph** | +0.30% | 1,236.4 M | 882.2 M | 79.1 |
| Luo 6 h, piece by piece | +0.45% | 0.5 M | 4.0 M | 1.4 |
| Luo 3 h, piece by piece | +0.35% | 2.2 M | 4.6 M | 2.0 |
| Luo 2 h, piece by piece | +0.30% | 5.1 M | 4.8 M | 2.5 |
| Luo 1.5 h, piece by piece | +0.30% | 9.3 M | 4.9 M | 2.9 |
| Luo 1 h, piece by piece | +0.30% | 21.4 M | 5.0 M | 3.8 |
| Luo 0.5 h, piece by piece | +0.29% | 87.4 M | 5.2 M | 5.8 |
| Luo 0.25 h, piece by piece | +0.31% | 353.5 M | 5.2 M | 11.1 |
| Luo 6 h, start point | +2.38% | 0.5 M | 0.1 M | 0.7 |
| Luo 3 h, start point | +1.67% | 2.2 M | 0.4 M | 0.7 |
| Luo 2 h, start point | +1.05% | 5.1 M | 0.6 M | 0.7 |
| Luo 1.5 h, start point | +1.16% | 9.3 M | 0.8 M | 0.8 |
| Luo 1 h, start point | +0.87% | 21.3 M | 1.2 M | 0.9 |
| Luo 0.5 h, start point | +0.98% | 87.6 M | 2.4 M | 1.5 |
| Luo 0.25 h, start point | +0.75% | 354.1 M | 5.0 M | 3.3 |

## Against constant SOG (`savings.py`)

Every method measured as fuel **saved over constant SOG** (per voyage, then the route mean);
perfect information gives the attainable saving, and "share" is the method's saving over the
attainable one (ratio of route means). Computation in DP arcs as above. Full tables for every
epoch and pricing: `savings_tables.md` (`savings.csv`). Chart: `savings_tradeoff.png/.pdf`.

| Route | Attainable (perfect info) | Full graph | Luo et al. (6 h, start point) | Luo 6 h, piece by piece | Break-even (piece by piece) | Arcs vs full graph at break-even |
|---|---|---|---|---|---|---|
| 3 | 1.90% | 1.47% (77%) | -0.74% | 1.17% (62%) | 2 h: 1.44% (76%) | 237x fewer |
| 4 | 2.31% | 1.99% (86%) | -1.61% | 1.42% (61%) | 1 h: 1.98% (86%) | 57x fewer |
| 5 | 1.43% | 0.69% (48%) | -3.05% | 0.58% (41%) | 3 h: 0.69% (48%) | 537x fewer |
| 6 | 0.65% | 0.36% (55%) | -1.71% | 0.20% (31%) | 3 h: 0.31% (48%) | 567x fewer |

Break-even = the coarsest Luo epoch, priced piece by piece, whose saving is within 0.05 points of
the full graph's (0.05% of the voyage's fuel, about 0.03-0.09 mt). With 0.02 points it moves to
1.5 / 1 / 3 / 2 h, with 0.1 points to 3 / 1.5 / 3 / 3 h; at 1 h every route is within 0.02 points.

- **The full graph captures 48-86% of the attainable saving**; the rest is the cost of planning
  with forecasts (6 h information lag).
- **Luo et al. as published loses fuel against constant SOG on every route** (-0.7% to -3.1%).
  With start-point pricing Luo needs epochs of 3 h (Route 3), 2 h (Route 4) and 0.5 h (Route 5)
  just to save fuel over constant SOG, and never does on Route 6.
- **Coarser than the break-even, the full graph is worth its cost**: Luo at 6 h, even priced piece
  by piece, gives up 0.1-0.6 points of saving (7-25 points of share).
- **From the break-even on (1-3 h epochs, piece by piece), Luo matches the full graph's saving
  with 57-567x fewer arcs**, and finer epochs add arcs without adding saving. A single setting
  that is at or past the break-even on every route: **1 h epochs** (saving within 0.02 points of
  the full graph on all four routes, 57-58x fewer arcs on every route).

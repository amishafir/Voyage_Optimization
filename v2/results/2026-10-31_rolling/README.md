# Rolling horizon on Routes 3-6, 2026-10-31 snapshot

Re-planning every 6 h with the forecast known at each decision (`voyage_v2/rolling.py`, CLI
`--rolling`), against one plan made with the departure forecast and sailed without re-planning, and
against perfect information. The voyages and data of `../2026-10-31_routes3-6/`: Routes 3-6, starts
2026-10-21 00:00 and 2026-10-26 12:00 UTC, ETAs 118 / 117 / 118 / 67 h, snapshot
`snapshot_2026-10-31_15Z` (MD5s in that README).

- **Decisions** at the start and every 6 h on the UTC clock (00/06/12/18 UTC, when the ECMWF runs are
  issued; a run is known from its start, the zero-delay assumption of the weather products): 20
  decisions on Routes 3-5, 12 on Route 6. Each re-plans from the ship's position to the end of the
  route by the same ETA, with the forecast known then, and is sailed until the next decision. The
  ship holds the planned SOG, so its position at the next decision is the plan's.
- **Fuel** is realized: the sailed SOG profile in the actual (pseudo real-time) weather, every
  subsegment-by-step piece priced. "Departure forecast, no re-planning" is the first plan sailed to
  the end; "perfect information" is the plan made with the actual weather.
- **SOG window** fixed for every plan of a voyage at the departure mean SOG +/- 3 kn.
- **Machine**: tsl2-mac, one core per solve, the four routes in parallel; v2 at commit `e192f20`.

Realized fuel above the full graph with perfect information:

| Method | R3, 21 Oct | R4, 21 Oct | R5, 21 Oct | R6, 21 Oct | R3, 26 Oct | R4, 26 Oct | R5, 26 Oct | R6, 26 Oct |
|---|---|---|---|---|---|---|---|---|
| Full graph, perfect information (mt) | 151.440 | 178.354 | 171.091 | 86.078 | 160.439 | 169.440 | 147.886 | 65.629 |
| Full graph, departure forecast, no re-planning | +0.10% | +0.84% | +0.75% | +0.58% | +0.96% | +0.49% | +0.62% | +0.27% |
| **Full graph, rolling horizon** | **+0.10%** | **+0.16%** | **+0.39%** | **+0.51%** | **+0.13%** | **+0.25%** | **+0.13%** | **+0.05%** |
| Luo 0.5 h, piece by piece, rolling horizon | +0.10% | +0.26% | +0.52% | +0.56% | +0.13% | +0.26% | +0.14% | +0.07% |
| Luo 6 h, piece by piece, rolling horizon | +0.48% | +0.95% | +0.76% | +0.93% | +0.42% | +1.00% | +0.31% | +0.19% |
| Luo 0.5 h, start point, rolling horizon | +0.29% | +0.75% | +1.25% | +1.28% | +0.48% | +0.65% | +1.24% | +0.95% |
| Luo 6 h, start point (Luo et al.), rolling horizon | +2.78% | +3.84% | +5.59% | +2.58% | +1.28% | +2.81% | +3.29% | +2.54% |
| Constant SOG | +2.17% | +2.12% | +4.16% | +0.64% | +2.24% | +2.57% | +1.33% | +0.78% |

Each method's own three numbers (perfect information, departure forecast, rolling horizon, in mt)
are in the output files, `start_<date>T<hour>/r<route>_full_luo6h.txt` (full graph, Luo 6 h) and
`r<route>_luo30min.txt` (Luo 0.5 h).

Re-planning recovers 50% to 90% of what the departure forecast loses on most voyages (Route 3 from
21 Oct lost only 0.10% to begin with; Route 6 from 21 Oct gains little). Luo at 0.5 h priced piece
by piece re-plans almost as well as the full graph (within 0.13%); Luo as published (6 h, start
point) burns more than constant SOG on 7 of the 8 voyages even with re-planning. Solve time per
rolling-horizon voyage: full graph 76-86 s (Routes 3-5), 16 s (Route 6); Luo 0.5 h 8-11 s; Luo 6 h
about 1.5 s.

**Caveat, from the definition of the actual weather.** The actual weather at time t is the newest
run issued by t, at lead 0-5 h, and the decisions fall exactly on the run times, so the 6 h sailed
after each decision are priced with the very run they were planned with (the re-plans' planned and
realized fuel are equal). Rolling horizon here loses fuel only through forecast errors beyond the
next 6 h, which misguide how the remaining time is spread. For the sailed stretches to carry
forecast error too, the realizations need another source, e.g. runs available only some hours after
their start (as real ECMWF delivery), or a later run's analysis as the truth. The conservative variant, each
block planned with the forecast known 6 h before it starts, is in `../2026-10-31_rolling_lag6h/`.

Commands (from `v2/` in the Dropbox folder on tsl2; `P=/opt/miniconda3/envs/voyage/bin/python`,
`D=~/voyage_data/snapshot_2026-10-31_15Z`), for each start, route and ETA (3 118, 4 117, 5 118,
6 67):

```bash
$P -m voyage_v2 $D/route3_runs.h5 --start "2026-10-26 12:00" --eta 118 --solve --luo --luo-pricing both --rolling           # r3_full_luo6h.txt
$P -m voyage_v2 $D/route3_runs.h5 --start "2026-10-26 12:00" --eta 118 --luo --epoch 2 --luo-pricing both --rolling         # r3_luo30min.txt
```

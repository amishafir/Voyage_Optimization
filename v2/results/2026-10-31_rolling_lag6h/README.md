# Rolling horizon with a 6 h information lag, Routes 3-6, 2026-10-31 snapshot

The conservative variant of `../2026-10-31_rolling/`: the plan for each 6 h block between decisions
uses only the information available 6 h before the block starts (`solve_rolling(..., info_lag_h=6)`,
CLI `--rolling --info-lag 6`). Same voyages, data, SOG window and machine as there: Routes 3-6, starts
2026-10-21 00:00 and 2026-10-26 12:00 UTC, ETAs 118 / 117 / 118 / 67 h, snapshot
`snapshot_2026-10-31_15Z`, tsl2-mac.

- **Decisions** as before, at the start and every 6 h on the UTC clock. The block from T to T+6 h is
  planned with the forecast known at T-6 h (the runs issued by then), from the ship's position at T.
  That position is known at T-6 h, because the ship holds the planned SOG, so this is a plan made at
  T-6 h; it is computed at T with the information of T-6 h, which gives the same plan. The first
  block uses the forecast known 6 h before departure (18 UTC on 20 Oct, 06 UTC on 26 Oct).
- **Departure forecast, no re-planning** is now the plan made 6 h before departure, sailed to the
  end.
- **Fuel** is realized in the actual (pseudo real-time) weather, as before. The actual weather of a
  block comes from the runs issued during it (lead 0-5 h), and its plan from the runs issued 6 h
  before it (lead 6-11 h and beyond), so the sailed blocks now carry forecast error. That removes
  the caveat of the zero-lag runs, where each block was planned with the run it was priced with.

Realized fuel above the full graph with perfect information (the zero-lag rows are from
`../2026-10-31_rolling/`):

| Method | R3, 21 Oct | R4, 21 Oct | R5, 21 Oct | R6, 21 Oct | R3, 26 Oct | R4, 26 Oct | R5, 26 Oct | R6, 26 Oct |
|---|---|---|---|---|---|---|---|---|
| Full graph, perfect information (mt) | 151.440 | 178.354 | 171.091 | 86.078 | 160.439 | 169.440 | 147.886 | 65.629 |
| Full graph, departure forecast, no re-planning, no lag | +0.10% | +0.84% | +0.75% | +0.58% | +0.96% | +0.49% | +0.62% | +0.27% |
| Full graph, departure forecast, no re-planning, 6 h lag | +0.12% | +0.87% | +0.70% | +0.42% | +0.25% | +0.48% | +0.21% | +0.36% |
| Full graph, rolling horizon, no lag | +0.10% | +0.16% | +0.39% | +0.51% | +0.13% | +0.25% | +0.13% | +0.05% |
| **Full graph, rolling horizon, 6 h lag** | **+0.18%** | **+0.59%** | **+0.64%** | **+0.82%** | **+0.21%** | **+0.36%** | **+0.56%** | **+0.15%** |
| Luo 0.5 h, piece by piece, rolling horizon, no lag | +0.10% | +0.26% | +0.52% | +0.56% | +0.13% | +0.26% | +0.14% | +0.07% |
| Luo 0.5 h, piece by piece, rolling horizon, 6 h lag | +0.17% | +0.61% | +0.63% | +0.83% | +0.21% | +0.35% | +0.59% | +0.17% |
| Luo 6 h, piece by piece, rolling horizon, no lag | +0.48% | +0.95% | +0.76% | +0.93% | +0.42% | +1.00% | +0.31% | +0.19% |
| Luo 6 h, piece by piece, rolling horizon, 6 h lag | +0.52% | +1.14% | +1.11% | +1.14% | +0.53% | +1.03% | +0.69% | +0.24% |
| Luo 0.5 h, start point, rolling horizon, no lag | +0.29% | +0.75% | +1.25% | +1.28% | +0.48% | +0.65% | +1.24% | +0.95% |
| Luo 0.5 h, start point, rolling horizon, 6 h lag | +0.35% | +0.61% | +1.58% | +1.43% | +0.59% | +0.78% | +1.44% | +0.81% |
| Luo 6 h, start point (Luo et al.), rolling horizon, no lag | +2.78% | +3.84% | +5.59% | +2.58% | +1.28% | +2.81% | +3.29% | +2.54% |
| Luo 6 h, start point (Luo et al.), rolling horizon, 6 h lag | +2.29% | +3.61% | +5.55% | +4.68% | +1.61% | +3.19% | +4.69% | +3.76% |
| Constant SOG | +2.17% | +2.12% | +4.16% | +0.64% | +2.24% | +2.57% | +1.33% | +0.78% |

Findings:

- **The lag doubles what rolling horizon loses.** The full graph's excess over perfect information
  goes from 0.05-0.51% (mean 0.22%) to 0.15-0.82% (mean 0.44%). It still beats constant SOG on 7 of
  the 8 voyages; the exception is Route 6 from 21 Oct (+0.82% against +0.64%).
- **With the lag, re-planning gains little over one plan on average.** The lagged departure plan
  sailed without re-planning averages +0.43%, about the same as lagged rolling horizon (+0.44%).
  Re-planning is better on 5 voyages and worse on 3 (Route 3 and Route 6 from 21 Oct, Route 5 from
  26 Oct). Single runs differ in quality, and 8 voyages are few: the lagged departure plan even beats
  the zero-lag one on 5 voyages (e.g. Route 3 from 26 Oct, +0.25% against +0.96%), because a 6 h
  older run happened to be the better forecast.
- **The method ranking is unchanged.** Luo at 0.5 h priced piece by piece stays within 0.03% of the
  full graph; Luo as published (6 h, start point) burns more than constant SOG on 7 of the 8 voyages.
- **Solve times are as without the lag**: full graph 75-85 s per voyage (Routes 3-5) and 21 s
  (Route 6); Luo 0.5 h 11.5-15.5 s and 2.3-2.4 s; Luo 6 h 1.2-1.6 s and 0.3 s.

Each method's three numbers (perfect information, departure forecast, rolling horizon, in mt) are in
`start_<date>T<hour>/r<route>_full_luo6h.txt` (full graph, Luo 6 h) and `r<route>_luo30min.txt`
(Luo 0.5 h). `run.sh` (bash, from `v2/` on tsl2) runs all 16 in parallel; v2 at the commit that adds
this folder. One command:

```bash
$P -m voyage_v2 $D/route3_runs.h5 --start "2026-10-26 12:00" --eta 118 --solve --luo --luo-pricing both --rolling --info-lag 6
```

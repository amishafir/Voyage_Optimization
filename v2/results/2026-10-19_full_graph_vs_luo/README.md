# Full graph vs Luo et al. vs constant SOG, 2026-10-19 snapshot

Realized fuel of each plan: its SOG profile sailed in the pseudo real-time weather, every
subsegment-by-step piece priced. All plans are made with that same weather (no forecasts,
no re-planning).

- **Voyages**: both routes start at 2026-10-14 12:00 UTC, the earliest start the archives
  cover (first stored wind run 2026-10-14T12; currents from 2026-10-14T00). ETA 280 h
  (Route 1, 3,415.1 NM, mean 12.20 kn) and 168 h (Route 2, 1,954.7 NM, mean 11.63 kn).
- **Data**: `pipeline/data/snapshot_2026-10-19_12Z/route{1,2}_runs.h5` (git-ignored), copied
  from edison at 14:29 UTC on 2026-10-19 while the collector was idle. Newest runs: wind
  2026-10-19T06, currents and waves 2026-10-19T00. MD5: route1 `b4f04828de8ce778cf0ea9396e337502`,
  route2 `52b452c34f722c0de54d607f6fdd3499`. The weather is near-real (leads under 6 h for
  wind, under 24 h for currents) for about the first 120 h of each voyage and forecast after
  that: 43% of Route 1's 280 h, 71% of Route 2's 168 h.
- **Machine**: tsl2-mac (M3 Ultra), one core per solve; v2 code as of commit `8a45528` (unchanged since).

| Method | Route 1 realized | vs full graph | Route 2 realized | vs full graph |
|---|---|---|---|---|
| Full graph (`--solve`) | 355.910 mt | | 215.511 mt | |
| Luo 0.25 h, piece by piece | 355.898 mt | -0.00% | 215.505 mt | -0.00% |
| Luo 1 h, piece by piece | 355.918 mt | +0.00% | 215.530 mt | +0.01% |
| Luo 6 h, piece by piece | 356.142 mt | +0.07% | 215.682 mt | +0.08% |
| Luo 0.25 h, start point (planned 354.939 / 214.766 mt) | 356.176 mt | +0.07% | 215.850 mt | +0.16% |
| Luo 1 h, start point (planned 353.198 / 213.111 mt) | 356.679 mt | +0.22% | 216.671 mt | +0.54% |
| Luo 6 h, start point (planned 345.994 / 208.781 mt) | 360.789 mt | +1.37% | 221.335 mt | +2.70% |
| Constant SOG (12.20 / 11.63 kn) | 356.956 mt | +0.29% | 216.826 mt | +0.61% |

Start-point pricing at 6 h plans 4.3% (Route 1) and 6.0% (Route 2) below what its plan then
burns, and its realized fuel is above constant SOG on both routes (+1.07%, +2.08%). The error
shrinks with the epoch: planned below realized by 1.0% / 1.7% at 1 h and 0.35% / 0.50% at
0.25 h. Piece by piece, 0.25 h epochs come out 0.003% below the full graph on both routes
(the grids are not nested; the full graph's 4 s nodes make its SOG jitter slightly).

Sweep times, piece by piece (start point): full graph 60.3 s / 24.2 s; Luo 6 h 3.1 s / 1.3 s
(under 0.1 s); Luo 1 h 24.4 s / 9.8 s (1.8 s / 0.7 s); Luo 0.25 h 110.6 s / 43.0 s (26.2 s / 9.7 s).

Commands (from `v2/`, with `/opt/miniconda3/envs/voyage/bin/python` on tsl2-mac):

```bash
python3 -m voyage_v2 ../pipeline/data/snapshot_2026-10-19_12Z/route1_runs.h5 --start "2026-10-14 12:00" --eta 280 --solve --luo --luo-pricing both   # r1_full_luo6h.txt
python3 -m voyage_v2 ../pipeline/data/snapshot_2026-10-19_12Z/route1_runs.h5 --start "2026-10-14 12:00" --eta 280 --luo --epoch 4 --luo-pricing both  # r1_luo1h.txt
python3 -m voyage_v2 ../pipeline/data/snapshot_2026-10-19_12Z/route2_runs.h5 --start "2026-10-14 12:00" --eta 168 --solve --luo --luo-pricing both   # r2_full_luo6h.txt
python3 -m voyage_v2 ../pipeline/data/snapshot_2026-10-19_12Z/route2_runs.h5 --start "2026-10-14 12:00" --eta 168 --luo --epoch 4 --luo-pricing both  # r2_luo1h.txt
python3 -m voyage_v2 ../pipeline/data/snapshot_2026-10-19_12Z/route1_runs.h5 --start "2026-10-14 12:00" --eta 280 --luo --epoch 1 --luo-pricing both  # r1_luo15min.txt
python3 -m voyage_v2 ../pipeline/data/snapshot_2026-10-19_12Z/route2_runs.h5 --start "2026-10-14 12:00" --eta 168 --luo --epoch 1 --luo-pricing both  # r2_luo15min.txt
```

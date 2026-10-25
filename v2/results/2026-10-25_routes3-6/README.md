# Full graph vs Luo et al. vs constant SOG on Routes 3-6, 2026-10-25 snapshot

The comparison of `../2026-10-19_full_graph_vs_luo/` on the four volatile routes. Realized fuel
of each plan: its SOG profile sailed in the pseudo real-time weather, every subsegment-by-step
piece priced. All plans are made with that same weather (no forecasts, no re-planning).

- **Voyages**: all four start at 2026-10-21 00:00 UTC, the first day after the lost current run
  of 2026-10-20 (the archives start 2026-10-19: wind from 19T12, currents and waves from 19T00).
  ETAs for a mean SOG of about 12 kn:

  | Route | Length | Subsegments | Wind / current cells | ETA | Mean SOG | Arrival (UTC) |
  |---|---|---|---|---|---|---|
  | 3 Tacoma - Anchorage (from Admiralty Inlet) | 1,414.0 NM | 972 | 409 / 539 | 118 h | 11.98 kn | 25 Oct 22:00 |
  | 4 Rotterdam - Algeciras | 1,400.1 NM | 785 | 351 / 417 | 117 h | 11.97 kn | 25 Oct 21:00 |
  | 5 Kaohsiung - Yokohama | 1,416.1 NM | 797 | 355 / 411 | 118 h | 12.00 kn | 25 Oct 22:00 |
  | 6 Durban - Cape Town | 805.9 NM | 449 | 197 / 233 | 67 h | 12.03 kn | 23 Oct 19:00 |

- **Data**: `pipeline/data/snapshot_2026-10-25_15Z/route{3,4,5,6}_runs.h5` (git-ignored), copied
  from talraviv-pcl at 15:30 UTC on 2026-10-25 while the collector was idle (next action 18:00
  UTC). Newest runs: wind 2026-10-25T06, currents and waves 2026-10-25T00. The current runs of
  2026-10-21 and 2026-10-22 came from Copernicus Marine (Open-Meteo's outage); 2026-10-20 is
  missing and not used. MD5: route3 `46655b7e853386eb991eb4739d1211dd`, route4
  `ca5b19697788f98be19c0bbe0a2ea193`, route5 `70545ebb613a4cc2abe6a6d89dfeb76d`, route6
  `153056e9398f936bb3c7fdb2946ba8e6`. Currents are near-real (leads under 24 h) for the whole
  voyage on every route. Wind is near-real (leads under 6 h) until 25 Oct 12:00 UTC; after that
  the 25T06 run is used at leads of 6 to 16 h: the last 10 h of Routes 3 and 5 and the last 9 h
  of Route 4 (8% of the voyage). Route 6 is near-real throughout.
- **Machine**: shlomo7 (AMD Ryzen 9 5950X, Python 3.8.10), one core per solve, the four routes
  in parallel (tsl2-mac was locked by FileVault after a crash that day); v2 code as of commit
  `8a45528` (unchanged since), copied with `v2/deploy/sync_to_host.sh shlomo7 --code`.

| Method | Route 3 | vs full graph | Route 4 | vs full graph | Route 5 | vs full graph | Route 6 | vs full graph |
|---|---|---|---|---|---|---|---|---|
| Full graph (`--solve`) | 151.436 mt | | 178.314 mt | | 171.315 mt | | 86.078 mt | |
| Luo 0.25 h, piece by piece | 151.419 mt | -0.01% | 178.338 mt | +0.01% | 171.346 mt | +0.02% | 86.094 mt | +0.02% |
| Luo 6 h, piece by piece | 151.961 mt | +0.35% | 179.687 mt | +0.77% | 172.039 mt | +0.42% | 86.395 mt | +0.37% |
| Luo 0.25 h, start point | 151.753 mt | +0.21% | 178.910 mt | +0.33% | 172.105 mt | +0.46% | 86.483 mt | +0.47% |
| Luo 6 h, start point | 154.561 mt | +2.06% | 183.793 mt | +3.07% | 182.990 mt | +6.81% | 89.029 mt | +3.43% |
| Constant SOG | 154.888 mt | +2.28% | 182.103 mt | +2.12% | 178.461 mt | +4.17% | 86.625 mt | +0.64% |

Planned fuel of the start-point plans (what Luo's DP believes it will burn):

| Luo, start point | Route 3 | Route 4 | Route 5 | Route 6 |
|---|---|---|---|---|
| 6 h: planned / realized | 148.497 / 154.561 mt (+4.08%) | 172.929 / 183.793 mt (+6.28%) | 155.471 / 182.990 mt (+17.70%) | 82.281 / 89.029 mt (+8.20%) |
| 0.25 h: planned / realized | 150.482 / 151.753 mt (+0.85%) | 177.613 / 178.910 mt (+0.73%) | 169.859 / 172.105 mt (+1.32%) | 85.059 / 86.483 mt (+1.68%) |

The full graph saves 2.23%, 2.08%, 4.00% and 0.63% against constant SOG, far more than on Routes
1 and 2 (0.29% and 0.61% on the 2026-10-19 snapshot). Start-point Luo at 6 h burns more than
constant SOG on Routes 4-6 (+0.93%, +2.54%, +2.77%) and saves only 0.21% on Route 3; its plans
believe in 4% to 18% less fuel than they burn, worst in the Kuroshio (Route 5), where the current
along a 6 h stage is far from the one at its start. With 0.25 h epochs start-point Luo beats
constant SOG on all four routes but stays 0.21% to 0.47% above the full graph (0.07% and 0.16% on
Routes 1 and 2); on Route 6 it keeps a quarter of the full graph's saving (0.16% of 0.63%). Priced
piece by piece, Luo's epochs cost 0.35% to 0.77% at 6 h and nothing at 0.25 h (within 0.02%; the
grids are not nested, so Route 3 comes out 0.01% below the full graph).

Two settings limit every method alike. The SOG window is the mean +/- 3 kn: the full graph's plan
reaches its 15.00 kn ceiling on Route 5 and 14.96 of 14.97 kn on Route 4, so a wider window would
save a little more there. The SWS bounds are only the hardcoded 2-25 kn: the full-graph plans use
SWS up to 14.06 (Route 3), 16.21 (Route 4), 16.52 (Route 5) and 15.83 kn (Route 6), above the
ship's 11-13 kn service range.

Full graph: 23.9 M nodes (Route 3), 20.0 M, 20.9 M, 6.7 M. Sweep times, piece by piece (start
point): full graph 33.8 / 35.0 / 33.9 / 10.9 s; Luo 6 h 1.7 / 1.3 / 1.4 / 0.4 s (under 0.1 s);
Luo 0.25 h 43.8 / 36.7 / 38.6 / 12.2 s (12.9 / 12.4 / 12.7 / 4.1 s).

Commands (from `v2/` on shlomo7, with the snapshot in `~/Ami/voyage/data/`, which is why the
output files show `../data/...`; in the repository it is `../pipeline/data/...`):

```bash
python3 -m voyage_v2 ../data/snapshot_2026-10-25_15Z/route3_runs.h5 --start "2026-10-21 00:00" --eta 118 --solve --luo --luo-pricing both   # r3_full_luo6h.txt
python3 -m voyage_v2 ../data/snapshot_2026-10-25_15Z/route4_runs.h5 --start "2026-10-21 00:00" --eta 117 --solve --luo --luo-pricing both   # r4_full_luo6h.txt
python3 -m voyage_v2 ../data/snapshot_2026-10-25_15Z/route5_runs.h5 --start "2026-10-21 00:00" --eta 118 --solve --luo --luo-pricing both   # r5_full_luo6h.txt
python3 -m voyage_v2 ../data/snapshot_2026-10-25_15Z/route6_runs.h5 --start "2026-10-21 00:00" --eta 67 --solve --luo --luo-pricing both    # r6_full_luo6h.txt
python3 -m voyage_v2 ../data/snapshot_2026-10-25_15Z/route3_runs.h5 --start "2026-10-21 00:00" --eta 118 --luo --epoch 1 --luo-pricing both  # r3_luo15min.txt
python3 -m voyage_v2 ../data/snapshot_2026-10-25_15Z/route4_runs.h5 --start "2026-10-21 00:00" --eta 117 --luo --epoch 1 --luo-pricing both  # r4_luo15min.txt
python3 -m voyage_v2 ../data/snapshot_2026-10-25_15Z/route5_runs.h5 --start "2026-10-21 00:00" --eta 118 --luo --epoch 1 --luo-pricing both  # r5_luo15min.txt
python3 -m voyage_v2 ../data/snapshot_2026-10-25_15Z/route6_runs.h5 --start "2026-10-21 00:00" --eta 67 --luo --epoch 1 --luo-pricing both   # r6_luo15min.txt
```

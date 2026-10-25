# Full graph vs Luo et al. vs constant SOG on Routes 3-6, 2026-10-25 snapshot

The comparison of `../2026-10-19_full_graph_vs_luo/` on the four volatile routes, with Luo's
epochs of 0.25 h, 1 h and 6 h. Realized fuel of each plan: its SOG profile sailed in the pseudo
real-time weather, every subsegment-by-step piece priced. All plans are made with that same
weather (no forecasts, no re-planning).

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
  `153056e9398f936bb3c7fdb2946ba8e6`. A copy is on talraviv-pcl in the collector account,
  `ami@talraviv-pcl:~/voyage_collector/data/snapshots/2026-10-25_15Z/` (in its nightly NAS backup).
  The live archives next to it hold later runs too, which change the weather of the last hours,
  so rerun on the snapshot to reproduce these numbers. Currents are near-real (leads under 24 h) for the whole voyage on
  every route. Wind is near-real (leads under 6 h) until 25 Oct 12:00 UTC; after that the 25T06
  run is used at leads of 6 to 16 h: the last 10 h of Routes 3 and 5 and the last 9 h of Route 4
  (8% of the voyage). Route 6 is near-real throughout.
- **Machine**: shlomo7 (AMD Ryzen 9 5950X, Python 3.8.10), one core per solve; v2 code as of
  commit `8a45528` (unchanged since), copied with `v2/deploy/sync_to_host.sh shlomo7 --code`
  (tsl2-mac was locked by FileVault after a crash that day). The full graph, 6 h and 0.25 h runs
  ran the four routes in parallel; the 1 h runs come from the later timing benchmark (below),
  one run at a time.

| Method | Route 3 | vs full graph | Route 4 | vs full graph | Route 5 | vs full graph | Route 6 | vs full graph |
|---|---|---|---|---|---|---|---|---|
| Full graph (`--solve`) | 151.436 mt | | 178.314 mt | | 171.315 mt | | 86.078 mt | |
| Luo 0.25 h, piece by piece | 151.419 mt | -0.01% | 178.338 mt | +0.01% | 171.346 mt | +0.02% | 86.094 mt | +0.02% |
| Luo 1 h, piece by piece | 151.452 mt | +0.01% | 178.528 mt | +0.12% | 171.491 mt | +0.10% | 86.167 mt | +0.10% |
| Luo 6 h, piece by piece | 151.961 mt | +0.35% | 179.687 mt | +0.77% | 172.039 mt | +0.42% | 86.395 mt | +0.37% |
| Luo 0.25 h, start point | 151.753 mt | +0.21% | 178.910 mt | +0.33% | 172.105 mt | +0.46% | 86.483 mt | +0.47% |
| Luo 1 h, start point | 152.081 mt | +0.43% | 179.462 mt | +0.64% | 173.583 mt | +1.32% | 86.703 mt | +0.73% |
| Luo 6 h, start point | 154.561 mt | +2.06% | 183.793 mt | +3.07% | 182.990 mt | +6.81% | 89.029 mt | +3.43% |
| Constant SOG | 154.888 mt | +2.28% | 182.103 mt | +2.12% | 178.461 mt | +4.17% | 86.625 mt | +0.64% |

Planned fuel of the start-point plans (what Luo's DP believes it will burn) against what they burn:

| Luo, start point | Route 3 | Route 4 | Route 5 | Route 6 |
|---|---|---|---|---|
| 0.25 h | 150.482 / 151.753 mt (+0.85%) | 177.613 / 178.910 mt (+0.73%) | 169.859 / 172.105 mt (+1.32%) | 85.059 / 86.483 mt (+1.68%) |
| 1 h | 149.522 / 152.081 mt (+1.71%) | 175.982 / 179.462 mt (+1.98%) | 166.983 / 173.583 mt (+3.95%) | 83.369 / 86.703 mt (+4.00%) |
| 6 h | 148.497 / 154.561 mt (+4.08%) | 172.929 / 183.793 mt (+6.28%) | 155.471 / 182.990 mt (+17.70%) | 82.281 / 89.029 mt (+8.20%) |

The full graph saves 2.23%, 2.08%, 4.00% and 0.63% against constant SOG, far more than on Routes
1 and 2 (0.29% and 0.61% on the 2026-10-19 snapshot). Priced piece by piece, Luo's constant SOG
per epoch costs little: within 0.02% of the full graph at 0.25 h (the grids are not nested, so
Route 3 comes out 0.01% below), up to 0.12% at 1 h, 0.35% to 0.77% at 6 h. Start-point pricing
costs much more as the epoch grows: 0.21% to 0.47% at 0.25 h, 0.43% to 1.32% at 1 h, 2.06% to
6.81% at 6 h, tracking how far its plans underestimate their own fuel (up to 1.7%, 4.0% and 18%),
worst in the Kuroshio (Route 5), where the current along a stage is far from the one at its
start. Start-point Luo burns more than constant SOG on Route 6 at 1 h (+0.09%) and on Routes 4-6
at 6 h (+0.93%, +2.54%, +2.77%); at 0.25 h it beats constant SOG on all four routes but keeps only
a quarter of the full graph's saving on Route 6 (0.16% of 0.63%).

Two settings limit every method alike. The SOG window is the mean +/- 3 kn: the full graph's plan
reaches its 15.00 kn ceiling on Route 5 and 14.96 of 14.97 kn on Route 4, so a wider window would
save a little more there. The SWS bounds are only the hardcoded 2-25 kn: the full-graph plans use
SWS up to 14.06 (Route 3), 16.21 (Route 4), 16.52 (Route 5) and 15.83 kn (Route 6), above the
ship's 11-13 kn service range.

Full graph: 23.9 M nodes (Route 3), 20.0 M, 20.9 M, 6.7 M. Sweep times, piece by piece (start
point), Routes 3 / 4 / 5 / 6: full graph 33.8 / 35.0 / 33.9 / 10.9 s; Luo 6 h 1.7 / 1.3 / 1.4 / 0.4 s
(under 0.1 s); Luo 1 h 10.5 / 8.8 / 9.2 / 2.9 s (0.8 / 0.8 / 0.8 / 0.3 s); Luo 0.25 h 43.8 / 36.7 /
38.6 / 12.2 s (12.9 / 12.4 / 12.7 / 4.1 s).

## Why the times differ, and an FCR cache for Luo (prototype, not in v2 yet)

Each method's sweep time is about its number of SWS evaluations times 50-56 ns (the closed-form
inverse: a square root, sometimes a cubic root, then the cubic FCR); relaxing an arc costs a few
ns. Counted by arc type on Route 3 (instrumented copy, same plan):

| Full graph arcs | Arcs | SWS evaluations |
|---|---|---|
| distance line to next distance line (table by duration, per segment and step) | 282.2 M | 4.6 M |
| time line to next time line, unmerged segment (table by grid advance) | 33.7 M | 1.7 M |
| distance line to next time line | 294.5 M | 302.3 M |
| time line to next distance line | 292.2 M | 301.2 M |
| time line to next time line, merged segment | 1.1 M | 1.2 M |

The tables already share each FCR among all the arcs that cross a segment in a step at the same
speed. The other 99% of the evaluations are on arcs whose SOG, (x - D) / (t_next - t) or
(D - x) / (t - t_m), depends on both their start and their end, so no two share a speed and an FCR
cache would never hit. Luo 0.25 h priced piece by piece needs 3.06 evaluations per arc (783 M on
Route 3), since a 0.25 h arc at constant SOG crosses about three subsegments.

The FCR is fixed for a subsegment, a weather step and a speed. In Luo's graph every arc of an epoch
has one of about 61 speeds (its grid advance q, SOG q x dist-step / epoch length), so caching the
FCR per (subsegment, step, q) once per epoch removes almost all evaluations.
`luo_fcr_cache.patch` (against `v2/cpp/src/luo.cpp`, `git apply` from the repository root) does
that; arcs that end at the end of the route keep the uncached pricing. Timed one run at a time on
shlomo7 (its load from other users rose from about 6 to 11 during the runs):

| Luo variant | Sweep, original / cached, Routes 3 / 4 / 5 / 6 | Speed-up | SWS evaluations, Route 3 |
|---|---|---|---|
| 0.25 h, piece by piece | 44.5 / 5.6, 37.8 / 5.0, 39.8 / 5.1, 12.5 / 1.6 s | 7.6-7.9x | 783.3 M / 4.5 M |
| 0.25 h, start point | 13.3 / 1.4, 12.8 / 1.4, 13.0 / 1.5, 4.2 / 0.4 s | 8.7-10.5x | 255.7 M / 4.4 M |
| 1 h, piece by piece | 10.5 / 1.4, 8.8 / 1.2, 9.2 / 1.2, 2.9 / 0.4 s | 7.2-7.7x | 193.4 M / 4.5 M |
| 1 h, start point | 0.8 / 0.1, 0.8 / 0.1, 0.8 / 0.1, 0.3 / under 0.1 s | about 8x | 15.8 M / 1.1 M |
| 6 h, piece by piece | 1.6 / 0.5, 1.3 / 0.4, 1.4 / 0.4, 0.4 / 0.1 s | 3.2-4.0x | 29.6 M / 4.1 M |
| 6 h, start point | under 0.1 s either way | | 0.4 M / 0.1 M |

The cached plans are the same as the original ones (identical SOG profiles in all 12 cases checked
at full precision on Routes 3 and 6); fuel differs in the 15th significant digit, because the
cached version computes the SOG as q x dist-step / epoch length instead of (d1 - d0) / epoch
length. With the cache, 0.25 h Luo priced piece by piece (within 0.02% of the full graph) is 6 to 7
times faster than the full graph on these routes. The remaining time is the loop over each arc's
pieces; cumulative fuel along the route per speed level would make an arc one subtraction.
To adopt it: apply the patch, add a test that the cached Luo reproduces the uncached one, and
rerun the timings.

Commands (from `v2/` on shlomo7, with the snapshot in `~/Ami/voyage/data/`, which is why the
output files show `../data/...`; in the repository it is `../pipeline/data/...`):

```bash
python3 -m voyage_v2 ../data/snapshot_2026-10-25_15Z/route3_runs.h5 --start "2026-10-21 00:00" --eta 118 --solve --luo --luo-pricing both   # r3_full_luo6h.txt
python3 -m voyage_v2 ../data/snapshot_2026-10-25_15Z/route4_runs.h5 --start "2026-10-21 00:00" --eta 117 --solve --luo --luo-pricing both   # r4_full_luo6h.txt
python3 -m voyage_v2 ../data/snapshot_2026-10-25_15Z/route5_runs.h5 --start "2026-10-21 00:00" --eta 118 --solve --luo --luo-pricing both   # r5_full_luo6h.txt
python3 -m voyage_v2 ../data/snapshot_2026-10-25_15Z/route6_runs.h5 --start "2026-10-21 00:00" --eta 67 --solve --luo --luo-pricing both    # r6_full_luo6h.txt
python3 -m voyage_v2 ../data/snapshot_2026-10-25_15Z/route3_runs.h5 --start "2026-10-21 00:00" --eta 118 --luo --epoch 4 --luo-pricing both  # r3_luo1h.txt
python3 -m voyage_v2 ../data/snapshot_2026-10-25_15Z/route4_runs.h5 --start "2026-10-21 00:00" --eta 117 --luo --epoch 4 --luo-pricing both  # r4_luo1h.txt
python3 -m voyage_v2 ../data/snapshot_2026-10-25_15Z/route5_runs.h5 --start "2026-10-21 00:00" --eta 118 --luo --epoch 4 --luo-pricing both  # r5_luo1h.txt
python3 -m voyage_v2 ../data/snapshot_2026-10-25_15Z/route6_runs.h5 --start "2026-10-21 00:00" --eta 67 --luo --epoch 4 --luo-pricing both   # r6_luo1h.txt
python3 -m voyage_v2 ../data/snapshot_2026-10-25_15Z/route3_runs.h5 --start "2026-10-21 00:00" --eta 118 --luo --epoch 1 --luo-pricing both  # r3_luo15min.txt
python3 -m voyage_v2 ../data/snapshot_2026-10-25_15Z/route4_runs.h5 --start "2026-10-21 00:00" --eta 117 --luo --epoch 1 --luo-pricing both  # r4_luo15min.txt
python3 -m voyage_v2 ../data/snapshot_2026-10-25_15Z/route5_runs.h5 --start "2026-10-21 00:00" --eta 118 --luo --epoch 1 --luo-pricing both  # r5_luo15min.txt
python3 -m voyage_v2 ../data/snapshot_2026-10-25_15Z/route6_runs.h5 --start "2026-10-21 00:00" --eta 67 --luo --epoch 1 --luo-pricing both   # r6_luo15min.txt
```

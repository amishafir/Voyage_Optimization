# Full graph vs Luo et al. vs constant SOG on Routes 3-6, 2026-10-31 snapshot

The comparison of `../2026-10-25_routes3-6/` (methods, ETAs and caveats as there) on newer data,
for two starts. Realized fuel of each plan: its SOG profile sailed in the pseudo real-time
weather, every subsegment-by-step piece priced; all plans are made with that same weather.

- **Data**: `route{3,4,5,6}_runs.h5` from talraviv-pcl at 15:41 UTC on 2026-10-31, while the
  collector was idle (next action 18:00 UTC). Newest runs: wind 2026-10-31T06, currents and waves
  2026-10-31T00; only the 2026-10-20 current run is missing. Copies: tsl2-mac
  `~/voyage_data/snapshot_2026-10-31_15Z/` (outside Dropbox; what these runs read, copied straight
  from talraviv-pcl), `pipeline/data/snapshot_2026-10-31_15Z/` (Dropbox, git-ignored) and
  `ami@talraviv-pcl:~/voyage_collector/data/snapshots/2026-10-31_15Z/`. MD5: route3
  `cd2a517a8b2ffa282fb73cb33a605f69`, route4 `d3f42fe8d3a21fd5e1578a2010d472ae`, route5
  `a11cd30a43224b0deb85be11a3bbb95f`, route6 `6f35953eb058f20454f3c77754929c40`.
- **Starts**: 2026-10-21 00:00 UTC (the voyages of the 2026-10-25 comparison, now near-real to
  the end; there the last 9-10 h of wind on Routes 3-5 were forecasts) and 2026-10-26 12:00 UTC (the
  latest round start whose voyages end by 31 Oct 12:00, the end of near-real weather; arrivals
  31 Oct 10:00 for Routes 3 and 5, 09:00 for Route 4, 29 Oct 07:00 for Route 6). ETAs 118 / 117 /
  118 / 67 h as before.
- **Machine**: tsl2-mac (M3 Ultra), `/opt/miniconda3/envs/voyage/bin/python`, one core per solve,
  the four routes in parallel; v2 at commit `bf54980` (Luo's FCR cache on).

Fuel above the full graph (P = piece by piece, S = start point as Luo et al.):

| Start 2026-10-21 00:00 | Route 3 | Route 4 | Route 5 | Route 6 |
|---|---|---|---|---|
| Full graph | 151.440 mt | 178.354 mt | 171.091 mt | 86.078 mt |
| Constant SOG | +2.17% | +2.12% | +4.16% | +0.64% |
| Luo 6 h, P / S | +0.34% / +2.07% | +0.77% / +3.07% | +0.43% / +6.79% | +0.37% / +3.43% |
| Luo 1 h, P / S | +0.01% / +0.43% | +0.12% / +0.64% | +0.10% / +1.33% | +0.10% / +0.73% |
| Luo 0.5 h, P / S | -0.00% / +0.36% | +0.06% / +0.37% | +0.06% / +0.72% | +0.05% / +0.72% |
| Luo 0.25 h, 0.2 kn steps, P / S | -0.01% / +0.21% | +0.03% / +0.33% | +0.04% / +0.62% | +0.02% / +0.46% |
| Luo 0.25 h, 0.1 kn steps, P / S | -0.01% / +0.21% | +0.01% / +0.33% | +0.02% / +0.48% | +0.02% / +0.47% |
| Luo 0.25 h, 0.05 kn steps, P / S | -0.01% / +0.21% | +0.01% / +0.34% | +0.01% / +0.41% | +0.02% / +0.46% |

| Start 2026-10-26 12:00 | Route 3 | Route 4 | Route 5 | Route 6 |
|---|---|---|---|---|
| Full graph | 160.439 mt | 169.440 mt | 147.886 mt | 65.629 mt |
| Constant SOG | +2.24% | +2.57% | +1.33% | +0.78% |
| Luo 6 h, P / S | +0.24% / +1.06% | +0.78% / +3.36% | +0.13% / +3.34% | +0.13% / +1.85% |
| Luo 1 h, P / S | +0.02% / +0.47% | +0.08% / +0.88% | +0.02% / +0.93% | +0.03% / +0.93% |
| Luo 0.5 h, P / S | +0.00% / +0.33% | +0.03% / +0.28% | +0.01% / +0.53% | +0.02% / +0.62% |
| Luo 0.25 h, 0.2 kn steps, P / S | +0.00% / +0.18% | +0.01% / +0.15% | +0.01% / +0.27% | +0.01% / +0.50% |
| Luo 0.25 h, 0.1 kn steps, P / S | -0.00% / +0.16% | +0.01% / +0.15% | +0.00% / +0.27% | +0.01% / +0.47% |
| Luo 0.25 h, 0.05 kn steps, P / S | -0.00% / +0.16% | +0.01% / +0.15% | +0.00% / +0.25% | +0.01% / +0.48% |

Start-point plans burn more than they plan: start 21 Oct, 6 h +4.16% / +6.30% / +17.52% / +8.20%,
0.25 h (0.1 kn) +0.85% / +0.73% / +1.33% / +1.67%; start 26 Oct, 6 h +6.81% / +7.87% / +10.65% /
+5.57%, 0.25 h (0.1 kn) +0.71% / +0.69% / +1.10% / +1.77% (Routes 3 / 4 / 5 / 6).

With the forecast tail replaced by near-real weather, the 21 Oct voyages hardly change (full graph
+0.004, +0.04 and -0.22 mt on Routes 3-5; Route 6 ended before the tail and is identical), nor do
the rankings. The 26 Oct voyages are calmer on Routes 5 and 6 (the full graph saves 1.33% and 0.78%
against constant SOG, against 4.16% and 0.64% from 21 Oct) and confirm the pattern: Luo priced piece
by piece is within 0.03% of the full graph from 0.5 h epochs down; start-point pricing stays 0.15%
to 0.50% above it even at 0.25 h, and at 6 h it burns more than constant SOG on Routes 4, 5 and 6
(and at 1 h on Route 6). The SOG step at 0.25 h changes piece-by-piece fuel by at most 0.03%.

Sweep times (both starts alike), Routes 3 / 4 / 5 / 6: full graph 11.0 / 11.6-12.1 / 11.4-12.0 /
3.6-3.8 s; Luo piece by piece 0.2 / 0.2 / 0.2 / 0.1 s at 6 h, 0.9 / 0.7 / 0.8 / 0.2 s at 1 h,
1.4 / 1.2 / 1.2 / 0.4 s at 0.5 h, 2.7 / 2.3 / 2.4 / 0.8 s at 0.25 h (0.1 kn), 9.7 / 8.3 / 8.6 / 2.7 s
at 0.25 h (0.05 kn); start point under a third of that.

Commands (from `v2/` in the Dropbox folder on tsl2; `P=/opt/miniconda3/envs/voyage/bin/python`,
`D=~/voyage_data/snapshot_2026-10-31_15Z`), for each start, route and ETA (3 118, 4 117, 5 118,
6 67), into `start_<date>T<hour>/`:

```bash
$P -m voyage_v2 $D/route3_runs.h5 --start "2026-10-26 12:00" --eta 118 --solve --luo --luo-pricing both                       # r3_full_luo6h.txt
$P -m voyage_v2 $D/route3_runs.h5 --start "2026-10-26 12:00" --eta 118 --luo --epoch 4 --luo-pricing both                     # r3_luo1h.txt
$P -m voyage_v2 $D/route3_runs.h5 --start "2026-10-26 12:00" --eta 118 --luo --epoch 2 --luo-pricing both                     # r3_luo30min.txt
$P -m voyage_v2 $D/route3_runs.h5 --start "2026-10-26 12:00" --eta 118 --luo --epoch 1 --luo-pricing both                     # r3_luo15min.txt
$P -m voyage_v2 $D/route3_runs.h5 --start "2026-10-26 12:00" --eta 118 --luo --epoch 1 --dist-step 0.05 --luo-pricing both    # r3_luo15min_0.05nm.txt
$P -m voyage_v2 $D/route3_runs.h5 --start "2026-10-26 12:00" --eta 118 --luo --epoch 1 --dist-step 0.0125 --luo-pricing both  # r3_luo15min_0.0125nm.txt
```

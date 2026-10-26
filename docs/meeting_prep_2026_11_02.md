# Meeting Prep — Monday 2026-11-02 (Ami ↔ Tal)

Continues from [meeting_prep_2026_10_07.md](meeting_prep_2026_10_07.md). Covers the two weeks
2026-10-14 → 2026-10-26: 34 commits by Tal (`1a98c1d..bf54980`), his five update emails, and a
read-only check of both collector hosts on 2026-10-19 and 2026-10-26.

**In one paragraph.** Tal's answer to the sampling problem raised on 10-07 was to rebuild the data
side from scratch. Routes are now partitioned at the real wind/current grid cells (option **A** from
10-07). A new collector archives every forecast run on **six routes on two machines**. A new
optimizer, `v2`, solves the full fine-resolution graph and Luo et al. on that data. **The paper has
not caught up:** §5 and §6 still describe and report the old 5/25 NM data, and the 10-07 questions
are still open.

---

## 1. Lead with this: the new results change the paper's story

`v2/results/2026-10-25_routes3-6/README.md`. Departure 2026-10-21 00:00 UTC, mean speed about 12 kn,
realized fuel in pseudo real-time weather, no forecasts and no re-planning.

| Realized fuel vs full graph | R3 Tacoma–Anchorage | R4 Rotterdam–Algeciras | R5 Kaohsiung–Yokohama | R6 Durban–Cape Town |
|---|---|---|---|---|
| Full graph | 151.436 mt | 178.314 mt | 171.315 mt | 86.078 mt |
| Luo 0.25 h, piece by piece | -0.01% | +0.01% | +0.02% | +0.02% |
| Luo 6 h, piece by piece | +0.35% | +0.77% | +0.42% | +0.37% |
| Luo 0.25 h, start point | +0.21% | +0.33% | +0.46% | +0.47% |
| Luo 1 h, start point | +0.43% | +0.64% | +1.32% | +0.73% |
| Luo 6 h, start point (as published) | +2.06% | +3.07% | **+6.81%** | +3.43% |
| Constant SOG | +2.28% | +2.12% | **+4.17%** | +0.64% |

Routes 1–2 (2026-10-19 snapshot, start 10-14): constant SOG costs only +0.29% / +0.61%, and 6 h
start-point Luo +1.37% / +2.70%.

**What it says:**

- **The full graph pays off where the weather moves.** It saves 0.6–4.0% against constant SOG on the
  short volatile routes, against 0.3–0.6% on Routes 1–2. The largest saving is on the Kuroshio (R5).
- **Luo as published loses to constant SOG** on 3 of 4 routes at 6 h stages. Its plan
  underestimates its own fuel by up to 17.7% (R5), because each stage is priced at its start point.
- **The method is not the problem, the pricing is.** Priced piece by piece, Luo is within 0.06% of
  the full graph at 0.5 h and 0.02% at 0.25 h. With the new FCR cache it is also **faster** than the
  full graph.
- Luo 0.25 h piece by piece is *below* the full graph on R3 (-0.01%) and on Routes 1–2 (-0.00%).
  So the full graph's node spacing costs a little. "Full graph = optimum" needs that qualifier.

**Decisions needed:**

- [ ] **Does the paper move to v2 and the new data?** If yes, §5 (data) and §6 (results) are
      rewritten, and the old 5/25 NM results either go or become a robustness appendix.
- [ ] **Which routes go in the paper?** 1–2 only, 3–6 only, or all six. The volatile routes carry the
      effect.
- [ ] **What is the headline claim?** The candidate is "Luo's start-point pricing, not its stage
      length, is what costs fuel; priced exactly, a multistage DP matches the full graph and is
      faster". This is a stronger and more specific finding than §7's current mechanism.
- [ ] Routes 1–2 rerun on a **full voyage of near-real data**. The 10-19 run was 43% / 71% forecast,
      which Tal flagged as a likely underestimate. Route 2 has had full data since about 10-22 and
      Route 1 since about 10-26. *Not in the repo yet.*

---

## 2. What changed in the code (by area)

### 2.1 Routes and partition (`f77f1f5`, `d600582`)
- A subsegment is the longest stretch of a rhumb leg inside **one wind cell and one current cell**
  (`pipeline/shared/subsegments.py`, `rhumb.py`, `weather_grids.py`). This is option A from 10-07,
  so §3's definition is now what the data implements.
- Models are pinned on every request: ECMWF IFS (O1280) for wind and Météo-France SMOC (1/12°) for
  currents. Open-Meteo's default `best_match` switches to regional models in the Atlantic and in the
  Gulf.
- The first and last 2 NM of each route are trimmed. Segments shorter than 0.15 NM are merged in v2,
  which answers Tal's concern about tiny corner-clipping subsegments.
- **Route 1 revised:** Port B was on land in Sumatra and moved 46 NM into the Strait of Malacca. This
  was the cause of the old "Port B NaN". A leg that crossed India and Sri Lanka was moved off land.
  **Route 2:** the North Channel waypoints were fixed.

### 2.2 Live collector (`0566f51` → `daa795e`)
- Every model run is stored once, with its full hourly series, per distinct cell. One HDF5 file per
  route, with a `/runs` status table so the collector resumes after a restart.
- **Wind:** 4 runs a day, +360 h or +144 h. Fixed on 10-15: a run is stored only once it is fully
  published (the archive serves +72 h early). Short runs are refetched automatically within the
  daily budget.
- **Currents:** one run a day, +239 h. Open-Meteo has no archive of them, so a missed run is lost.
- **Waves (new):** MFWAM height, direction and period. They are fetched in the same requests as the
  currents, so they cost no extra calls. The fuel model does not use them yet.

### 2.3 Currents outage and Copernicus backup (`83db105`, `981a16c`, `d1222ef`)
- Open-Meteo's SMOC stalled after the 10-19 run (open-meteo#2246). The cause was a late Copernicus
  sea-level product that blocks Open-Meteo's downloader.
- **Backup:** if run D is not on Open-Meteo by D 18:00 UTC, the collector fetches the same SMOC
  directly from Copernicus Marine. The Copernicus point is half a cell south-west, or the nearest sea
  point within 3 cells near land. Correlation with Open-Meteo is 0.99. Every run records its
  `source`.
- **Outcome:** **10-20 lost on all six routes.** 10-21 and 10-22 came from Copernicus, and Open-Meteo
  is back since 10-23. A rescued Copernicus copy of 10-20 is in `pipeline/data/cmems_rescue/`
  (git-ignored).

### 2.4 Routes 3–7 (`0b5badc`, `dac4625`, `df5c6b6`)
- These are short volatile routes of up to about 5 days. They were traced along the World Bank / IMF
  AIS traffic density as the densest path at most 5% longer than the shortest sea path. The method
  is in `pipeline/tools/routes/README.md`.
- `run_all.py --route` takes a route set: `all` = 1, 2 (edison) and `volatile` = 3–6 (talraviv-pcl,
  about 7,000 calls/day). **Route 7** (Sydney–Auckland) is defined but collected nowhere, because it
  would push the budget too close to the limit.

### 2.5 Exact SOG → SWS inverse (`9e3c4ae`, `443d6d6`, `aab3717`)
- The inverse is closed-form: undo the current, then solve a cubic with one positive root (Cardano's
  formula plus one Newton step). Binary search stays as a fallback. Fuel changes by at most 0.004%,
  and the inverse is 9–14× faster.
- The paper text was updated: the inverse no longer "has no closed form".

### 2.6 v2 optimizer (`8f85836` → `bf54980`)
- A clean restart on the new archives: Python handles input and the command line, and a C++ core
  does the work. The old optimizers cannot read the new archives.
- **Full graph:** distance lines at every subsegment boundary, 4 s nodes, time lines every 0.25 h.
  Route 1 has 116 M nodes and 5 G arcs and solves in about 60 s on one core.
- Tal tested **Dynamic Discretization Discovery** (Oct 16 email) and it is not worth it here. A coarse
  graph followed by a fine corridor would be 3–6× faster, but without an optimality proof.
- **Luo et al.:** the epoch is selectable, with start-point or piece-by-piece pricing. Every plan now
  reports **planned and realized** fuel.
- **FCR cache (`4515546`, now the default):** about 61 distinct SOGs per epoch, so the fuel rate is
  cached per (subsegment, step, speed). Luo becomes 8–9× faster with identical plans across 24
  output pairs. It does not help the full graph.
- **Lab machines:** per-host builds, `v2/deploy/sync_to_host.sh` and `v2/tools/benchmark.py`.
  tsl2-mac is the fastest.

### 2.7 Deployment (`9ecc15c`, `bc68b2d`, `1eb0fa7`)
- Each host has a cron restart check every 10 min (`touch STOP` to stop on purpose) and a daily
  rsync to the lab NAS with weekly copies. Weekly copies are now deleted after 3 months.

---

## 3. Collector status (checked 2026-10-26, read-only)

| | edison | talraviv-pcl |
|---|---|---|
| Routes | 1, 2 | 3, 4, 5, 6 |
| Login | `user` + password | `ssh talraviv` (key, Ami's account) |
| Code | `~/Ami/pipeline_v2`, system Python 3.10 | `~/voyage_collector`, `~/collector-venv` (Python 3.12) |
| tmux | `collector_v2` | `collector_volatile` |
| Running since | 10-21 21:33 UTC (Copernicus deploy) | 10-21 21:40 UTC |
| Deployed code = repo | yes (byte-identical) | yes (byte-identical) |
| Public IP (own quota) | 132.66.196.253 | 132.66.50.222 |
| Peak calls / rolling 24 h | 11,797 (10-17), 0 rate-limit errors | 9,880, 0 rate-limit errors |
| Backups | daily OK, weekly 10-18 and 10-25 | daily OK, 04:30 Israel time |
| Missing runs | currents 10-20 | currents 10-20 |

All stored current runs on Route 3 have no NaN, including Copernicus 10-21. That was checked in
the 10-25 snapshot. The 2 NaN cells logged when 10-21 was stored were filled afterwards.

---

## 4. Questions for Tal

### New
- [ ] **10-20 currents gap.** Tal's email proposes day 2 of the 10-19 run, with the Copernicus
      analysis kept for sensitivity checks. CLAUDE.md says "fallback run D-1". Confirm this is the
      rule for the weather-product builder.
- [ ] **Zero publication delay** for forecasts is an idealization (ECMWF 00 UTC reaches users around
      06 UTC, currents around midday). State it as an assumption, or model the delay?
- [ ] **Fixed speed menu in the full graph** (his open item). Forcing arc speeds to a menu would let
      the full graph reuse the FCR cache. What is the cost in nodes, and what is the gain?
- [ ] **Waves.** They are collected but unused. In scope for the paper, or future work?
- [ ] **Who builds what next:** the 15-minute weather-product builder, rolling-horizon re-planning
      in v2, and the Routes 1–2 full-voyage rerun. Which of these should Ami take?
- [ ] **Route 7:** drop it, or run it on a third machine with its own IP?

### Carried over from 10-07 (no answers recorded)
- [ ] **Convexity in SOG** for §3's Jensen step. Options: (a) assume, (b) verify numerically
      (recommended, 800 of 800 states), or (c) prove. Note: the closed-form inverse may make (c)
      tractable, since $h=g^{-1}$ is now explicit.
- [ ] **Appendix size.** About 25 of 142 lines are needed. "Invertible by binary search" is now
      "closed form", so Appendix A changes anyway.
- [ ] **§7.3 replacement** confirmed? This may be moot if §6/§7 are rebuilt on v2 results (§1 above).
- [ ] **More voyages or report bounds** (Action 4). This is reframed by the new data: how many
      departures per route does the new archive allow?
- [ ] **Method names** (SR / Luo / Naive) and **bearing vs heading**.
- [x] ~~Sampling: option A or B~~. **A, by construction**, in the new collector. The Indian Ocean
      resample happened through Route 1's new partition.
- [ ] Luo: does `luo2024` take one heading per stage? v2's piece-by-piece pricing uses each
      subsegment's own bearing, which makes the question matter only for start-point pricing.

---

## 5. Review notes to pass on (round 1; nothing Critical or High)

| Severity | Finding |
|---|---|
| Medium | `pipeline/deploy/edison/backup_collector.sh`: the weekly `cp -r` is not checked. A partial copy is kept as normal, and an existing `weekly/DATE` gets a nested `latest/`. |
| Medium | The Copernicus fallback runs synchronously, up to 1,800 s per route, retried hourly, and can delay wind fetches while it runs. |
| Medium | No test covers the Copernicus half-cell mapping or the 3-cell sea-point search. They were only checked by the one-off 0.99 comparison. |
| Medium | `backup_collector.sh:2` says "04:30 UTC", but on talraviv-pcl it is 04:30 Israel time. |
| Medium | The 10-19 and 10-25 results READMEs say "v2 code as of `8a45528` (unchanged since)". `luo.cpp` changed in `4515546`. |
| Low | talraviv-pcl's backup (01:30/02:30 UTC) could meet a late 18 UTC wind fetch. The closest observed gap is 26 min (10-22). |
| Low | Runs stored before `83db105` have no `source` attribute. Readers should default to `open-meteo`. |

Housekeeping still open from 10-19:
- `dp_rebuild/geo_grid.py` is 1.2 NM off `rhumb.py`.
- `.claude/rules/data-flow.md` and `pipeline-standards.md` describe the old layout.
- Two Beaufort tables are in use.
- `regression.sh` goldens are stale.

---

## 6. Paper state

| | |
|---|---|
| Draft | 39 pages, unchanged since 10-07 except the closed-form inverse text (`aab3717`, 10-16) |
| §3 | Tal's 10-05 rewrite. It now **matches** the data (cell partition) |
| §5 | **Out of date.** It describes 5/25 NM sampling and 2 routes |
| §6 | **Out of date.** All numbers come from the old data and old optimizers |
| §7 | Not read end to end since 09-13. The mechanism may change with the v2 results |
| Pushed | `origin/main` = `bf54980`. Ami's 4 commits (10-07 prep, sampling notes, partition figure, sampling reference) are rebased on top but **not pushed** |

---

## 7. Decisions made during the session

| # | Decision | Outcome | Follow-up |
|---|---|---|---|
| | | | |

## 8. Actions assigned

| # | Action | Owner | Due |
|---|---|---|---|
| | | | |

## 9. Live log — 2026-11-02 session

_Items as they come up._

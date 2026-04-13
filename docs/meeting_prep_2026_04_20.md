# Meeting Prep — Supervisor Meeting, Apr 20 2026

---

## 1. Action Items from Apr 13 Meeting

| # | Task | Status |
|---|------|--------|
| 1 | *(to be filled after Apr 13 meeting)* | TODO |
| 2 | | |
| 3 | | |

Carried over from Mar 31 (still open):
- Revisit `speed_control_optimizer.py` DP graph structure
- Adjust DP algorithm for forecast resolution awareness

---

## 2. Planned Experiments — DP vs Luo Head-to-Head

The goal is a clean, controlled comparison between our DP and Luo's DP on the same data matrix. Two experiments, both isolating the speed-decision granularity as the only variable.

### 2.1 Experiment 1 — Single plan at t=0 with full hindsight

**Setup**: Assume all actual weather is known for every (location, time) prior to departure. Plan once, execute the schedule.

- **Our DP**: free to choose a different SWS at every leg (1–5 nm waypoint spacing).
- **Luo-style DP**: must commit to one speed for each 6h block; cannot change speed within a 6h window.

Both run on the **same weather matrix** (actual weather, perfect knowledge). The only difference is the granularity of speed decisions.

**What it tests**: how much fuel can be saved by allowing finer-grained speed control when planning is otherwise identical and weather is perfectly known. This isolates the value of fine speed granularity from forecast uncertainty.

### 2.2 Experiment 2 — Rolling horizon, replan every 6h

**Setup**: Same as above but with rolling horizon. Replan every 6h with the latest available information.

- **Our DP**: replans every 6h, free to choose a different SWS at every leg within the next horizon.
- **Luo-style DP**: replans every 6h, but each plan commits one speed per 6h block.

Both follow the same replan cadence and use the same weather data at each replan. The only difference is the speed-decision granularity.

**What it tests**: whether the fine-grained speed advantage from Exp 1 still holds under realistic rolling-horizon planning, where forecast staleness and replanning interact.

### 2.3 Common protocol

- Same route, same departure time, same ETA constraint
- Same speed range [v_min, v_max] (recommend matching Luo's [8, 18] kn for fair comparison)
- Same FCR model on both sides (use our cubic `0.000706 × SWS³` for both — eliminates ANN as a confounder)
- Report: total fuel, voyage time, delay, number of speed changes, fuel-per-nm

---

## 3. Brainstorm — When Should Two Adjacent Nodes Have Different Speeds?

**The question**: If between two adjacent waypoints we are
- not changing course (heading is the same), and
- not crossing into a different weather forecast cell (same polygon / grid square in the GEFS or Open-Meteo grid),

then nothing physical has changed between those two legs. So why should the optimizer be allowed to pick a different speed for each? Conceptually, those legs should be **collapsed into a single decision** — same heading, same weather, same optimal speed.

**Implications to think about**:

1. **Node consolidation**: Adjacent waypoints inside the same weather cell with the same heading could be merged into one "decision unit." This reduces graph size and prevents the optimizer from exploiting numerical noise as if it were real weather variation.

2. **Natural alignment with Luo**: Luo's 6h stages cover ~72–108 nm — large enough that the ship typically crosses multiple weather cells per stage. Our 1–5 nm spacing means we often have many consecutive waypoints inside a single cell. Collapsing them moves us conceptually closer to Luo's "one decision per meaningful change" — but driven by **physical change** (course / weather cell) rather than fixed time blocks.

3. **What defines a "weather cell"?** Open-Meteo grid resolution is ~0.1° (~6 nm). GEFS is 0.5° (~30 nm). Either way, many of our waypoints share a cell. The decision unit should probably be: **(course-segment) × (weather-cell)** — collapsed until either changes.

4. **Open question — does this change results?** If consecutive waypoints in the same cell genuinely have the same optimal speed, collapsing them shouldn't change the fuel total — only the graph size. If results differ, that signals the optimizer was over-fitting to noise, which would be a real finding.

5. **Connection to Luo comparison**: This brainstorm could explain *why* our finer waypoint spacing matters (or doesn't). If most adjacent waypoints share a cell + heading, the effective decision count is much closer to Luo's than the raw waypoint count suggests.

To explore: build a "collapsed" view of the route — group consecutive waypoints by (heading bucket, weather cell ID) — and count how many true decision units exist for each route. Compare to the raw waypoint count and to Luo's stage count.

---

## 4. Progress Since Apr 13

*(to be filled)*

---

## 5. Data Collection Status

| Server | Status | Route B (138 wp) | Route D (391 wp) | Uptime |
|--------|--------|-------------------|-------------------|--------|
| Shlomo1 | | | | |
| Shlomo2 | | | | |
| Edison | | | | |

---

## 6. Results

*(to be filled as Exp 1 / Exp 2 complete)*

---

## 7. Open Items / Discussion Points

- Exp 1 and Exp 2 results (fine-speed vs 6h-locked speed, both on same data)
- Node-collapsing brainstorm — does collapsing (same heading, same weather cell) change results?

---

## 8. Questions for Supervisor

1.
2.
3.

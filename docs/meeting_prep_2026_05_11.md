# Meeting Prep — Supervisor Meeting, May 11 2026

---

## 1. Action Items from May 4 Meeting

| # | Task | Status |
|---|------|--------|
| 1 | **Rebuild the graph** | TODO |
| 2 | | |
| 3 | | |

Carried over from May 4 §3:

- [ ] Rolling-horizon mechanics
- [ ] Behavioural sanity checks (zero-weather, constant-weather, lock-monotonicity)
- [ ] Real heading per sub-leg (currently uses representative source heading)
- [ ] Soft ETA exercise (`BellmanSolver.best_sink(eta_mode="soft", lam=…)`)
- [ ] Combined graph as default `run_demo` (treat free/locked as ablations)
- [ ] Sampling strategy update — switch collector to "2–3 samples per cell-arc + segment endpoints"

---

## 2. Progress This Week — Graph Rebuild

### 2.1 Motivation

The previous edge-build strategy emitted one 6 h arc per (V-src, V-dst, target-SOG) tuple — a single straight line in (t, d) that ignored intermediate cell crossings except for the cell-canonical lookup at the source corner. Two issues:

1. Weather inside a block is not actually constant — the chain crosses several 0.5° cells, each with its own canonical row. A single-arc edge collapses that detail.
2. Free DP and locked DP could not be run on the *same* node + edge set. Locked-DP edges were geometric (`d_src + SOG·6h`), free-DP edges were per-square (1 nm × 0.1 h grid). Apples-to-apples comparison required ad-hoc bridging.

**New strategy.** A locked-block edge is a *chain* of constant-SOG sub-arcs:

- One sub-arc per **H-line crossing** (cell boundary or segment-boundary course change).
- Σ Δt over sub-arcs = exactly 6 h. Last sub-arc may be partial (V-line terminator).
- Speed can change **only** at H-line crossings, never mid-cell.
- Each sub-arc looks up cell-canonical weather + paper heading, inverse-solves SWS to hold target SOG, accumulates `FCR(SWS)·Δt`.

**Free DP** = all chains, mixed-speed allowed at each H-line. **Luo 2024 DP** = the *subset* of chains where all sub-arcs in a block share one speed. Same node set, edge set of Luo ⊂ edge set of ours — a single rebuild produces both.

### 2.1.1 Locked edge-build spec (locked-in)

| Item | Value |
|---|---|
| Speed grid | [9, 13] kn × 0.1 kn step → **41 target SOGs** |
| Speed change point | **Only at H-line crossings** (never mid-cell, never at non-H-line times within a block) |
| H-lines | Rhumb-vs-grid crossings (lon = k·0.5°, lat = k·0.5°) **+ paper-segment boundaries** (course-change H-lines) |
| Sub-arc weather | Cell-canonical mean (linear for scalars, circular for directions) for the 0.5° cell the sub-arc sits in |
| Sub-arc heading | Paper β for the segment the sub-arc sits in |
| Sub-arc fuel | `FCR(SWS_inverse_solved) · Δt`, summed over chain |
| **`sample_hour`** | **Block-start, constant within block** — sub-arcs in block `k` all read `sample_hour = k·6`. **Matches Luo 2024.** |
| `forecast_origin` | One per block (= block-start), updated at each replan in RH mode |
| Block length | 6 h |
| V-line dst-d | **Snapped to 1 nm**; SWS in the final sub-arc inverse-solved so trajectory lands exactly on the snap |
| Edge fan-out per V-src | One edge per (chain of sub-arc speeds) ending at each reachable 1-nm dst V-line node |
| Luo-compatible subset | Chains with one constant speed across all sub-arcs in the block |

### 2.1.2 Worked example (matches Apr 28 sketch, speed range [10, 15] kn)

| Chain | Sub-arc speeds | Trace | dst (t, d) | Type |
|---|---|---|---|---|
| `a → c → F` | 15, 15, 15 | (0,0)→(2,30)→(4,60)→(6,90) | (6, 90) | Luo-compatible (constant 15) |
| `b → e` | 10, 10 | (0,0)→(3,30)→(6,60) | (6, 60) | Luo-compatible (constant 10) |
| `a → d → g` | 15, 10, 15 | (0,0)→(2,30)→(5,60)→(6,75) | (6, 75) | Free DP only; `g` is V-line-terminator (1 h leftover at 15 kn) |

### 2.2 What changed

| File | Purpose |
|---|---|

### 2.3 Updated graph stats

| | Before | After |
|---|---:|---:|
| Squares | | |
| H-lines | | |
| V-bands | | |
| Nodes | | |
| Edges | | |

### 2.4 Updated YAML voyage results

| Mode | Total fuel | End time | End d | Δ vs baseline |
|---|---:|---:|---:|---:|
| **Baseline (steady SOG = 12.120 kn)** | | | | — |
| Free DP (per-square decisions) | | | | |
| Locked DP (SOG-locking, 6 h block) | | | | |
| **Combined (free ⊕ locked)** | | | | |

### 2.5 Sanity checks

*(zero-weather, constant-weather, lock-monotonicity once run)*

---

## 3. Open Items / Next Steps

- **Rolling horizon** — replan every 6 h with fresh forecast.
- **Sampling strategy for new voyages** — switch collector once approved.
- **Soft ETA** — exercise `eta_mode="soft"` once rebuild is stable.
- **Combined-graph as default** — promote in `run_demo` after rebuild lands.

---

## 4. Data Collection Status

| Server | Status | exp_b (138 wp) | exp_d (391 wp) | exp_c (968 wp) | Uptime |
|--------|--------|---|---|---|--------|
| Shlomo1 | | | | | |
| Shlomo2 | | | | | |
| Edison | | | | | |

*(refresh on the morning of May 11)*

---

## 5. Results Tables

### 5.1 Four-mode comparison, YAML voyage (rebuilt graph)

| Metric | **Baseline (steady SOG)** | Free DP | Locked DP (SOG) | **Combined** |
|---|---|---|---|---|
| Total fuel | | | | |
| Δ vs baseline | — | | | |
| Voyage time | | | | |
| Schedule length | | | | |
| Average SOG | | | | |
| target SOG range | | | | |
| mean SWS range | | | | |
| Edges built | | | | |
| Build time | | | | |
| Solve time | | | | |
| NaN edges skipped | | | | |

### 5.2 Comparison vs previous build (May 4 numbers)

| Mode | May 4 | After rebuild | Δ |
|---|---:|---:|---:|
| Baseline | 366.519 mt | | |
| Free DP | 366.769 mt | | |
| Locked DP | 365.161 mt | | |
| Combined | 362.965 mt | | |

---

## 6. Questions for Supervisor

1. *(fill in once results are in)*

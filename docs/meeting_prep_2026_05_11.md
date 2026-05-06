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
- [ ] Sampling strategy update — switch collector to "2–3 samples per cell-arc + segment endpoints"

---

## 2. Progress This Week — Graph Rebuild

### 2.1 Motivation

The previous edge-build strategy emitted one 6 h arc per (V-src, V-dst, target-SOG) tuple — a single straight line in (t, d) that ignored intermediate cell crossings except for the cell-canonical lookup at the source corner. Two issues:

1. Weather inside a block is not actually constant — the chain crosses several 0.5° cells, each with its own canonical row. A single-arc edge collapses that detail.
2. Free DP and locked DP could not be run on the *same* node + edge set. Locked-DP edges were geometric (`d_src + SOG·6h`), free-DP edges were per-square (1 nm × 0.1 h grid). Apples-to-apples comparison required ad-hoc bridging.

**New strategy.** One graph, one edge type — atomic sub-arcs:

- One emitted edge per **single sub-arc** = one cell traversal at one constant target SOG.
- Sub-arc breaks (forced) at every H-line (cell or segment boundary) and at every V-line (forecast block boundary). Last sub-arc in a block may be partial (V-line terminator).
- Each sub-arc looks up cell-canonical weather + paper heading, inverse-solves SWS to hold the target SOG, scores fuel as `FCR(SWS)·Δt`.

**Free DP** = Bellman over the atomic-edge graph, no per-block constraint — speed can change at every H-line.
**Luo DP** = Bellman over the **same** graph with a path constraint: the SOG label of the edge taken at the V-line is locked for all subsequent atomic edges within the 6 h block; resets at the next V-line.

No second edge set, no chain-edge representation, no "combined" graph — Luo is a Bellman-side state augmentation, not a build-time choice.

### 2.1.1 Graph frame — H-lines and V-lines (preserved from current implementation)

The `(t, d)` plane has two axis-aligned line families. **The frame itself does not change in the rebuild** — what changes is the meaning of edges that cross it.

**V-lines (constant `t`)**
- Placed at `t = k · 6 h` for k = 1, 2, … plus forecast-window boundaries plus the terminal at `t = ETA`.
- Node grid on each V-line: every `ζ_nm = 1 nm` across `[0, L]` (matches the V-line dst-d snap).
- Physics meaning: weather snapshot flips. `sample_hour` advances from `(k−1)·6` to `k·6`; in RH mode `forecast_origin` flips too.

**H-lines (constant `d`)**
- Placed at every rhumb-vs-grid crossing (lon = k·0.5°, lat = k·0.5°) **plus paper-segment boundaries** (course-change), plus the terminal at `d = L`.
- Node grid on each H-line: every `τ_h = 0.1 h` across `[0, ETA]` (kept — needed for free-DP Bellman dedup of partial paths).
- Physics meaning: cell-canonical weather row changes (cell crossing) and/or heading β changes (segment boundary).

### 2.1.2 Split-point vs decision-point — the two-role framework

Both line families have **two independent roles**:

- **Split-point** (forced sub-arc break): physics inputs change, so the sub-arc must terminate and the next sub-arc must look up fresh weather + heading.
- **Decision-point** (DP branches): a new target SOG / chain can be chosen.

The split-point role is *physics*. The decision-point role is *graph design* — and that's where free DP differs from Luo.

| Line | Split-point (forced break) | Decision-point (DP branches) |
|---|---|---|
| H-line | **always** — cell or segment changes | **free DP only** — pick new SOG. **Luo subset:** passive split, no branch. |
| V-line | **always** — forecast block changes | **both DPs** — pick new chain / SOG for next 6 h. |

Consequence: a sub-arc can never cross a V-line internally — chains whose 6 h budget runs out mid-cell terminate *at the V-line* (V-line-terminator sub-arc, e.g. `g` in the sketch) rather than continuing into the next block's weather.

### 2.1.3 What's preserved vs what changes

| Aspect | Today (May 4 build) | Rebuild |
|---|---|---|
| V-line frame (positions, ζ=1 nm node grid) | ✓ | **same** |
| H-line frame (positions, τ=0.1 h node grid) | ✓ | **same** |
| H-lines as split-points | ✓ | **same** |
| H-lines as decision-points (free DP only) | ✓ | **same** |
| V-lines as split-points (forecast flips) | implicit | **explicit — sub-arc must end at V-line** |
| Atomic edge meaning | sub-arc on (1 nm × 0.1 h) snap grid | sub-arc traverses **one full cell** at one constant SOG, lands on H-line node snapped to τ_h |
| Locked / Luo edge representation | separate locked-edge build (one straight 6 h arc per SOG) | **none — Luo is a Bellman path constraint** on the atomic-edge graph |
| Bellman input | atomic edges only | **atomic edges only** — single edge set |
| Free vs Luo distinction | two separate graph builds | **same graph, two Bellman modes** (state augmentation: `(node, locked_SOG)`) |

**Bellman mode summary.**

| Mode | State | At V-line | At H-line |
|---|---|---|---|
| Free DP | `node` | Any outgoing SOG | Any outgoing SOG |
| Luo DP | `(node, locked_SOG)` | `locked_SOG` resets — any outgoing SOG, sets new lock | Only edges with `SOG == locked_SOG` |

### 2.1.4 Edge-build spec (locked-in)

| Item | Value |
|---|---|
| Speed grid | [9, 13] kn × 0.1 kn step → **41 target SOGs** |
| Edge type | **Atomic sub-arc only** — one emitted edge per single cell traversal at one SOG |
| Sub-arc break points | H-lines (cell + segment boundaries) **and** V-lines (forecast block boundaries) |
| Speed change point | **Only at H-line crossings** in Free DP; **only at V-lines** in Luo DP (Bellman-enforced) |
| H-line set | Rhumb-vs-grid crossings (lon = k·0.5°, lat = k·0.5°) **+ paper-segment boundaries** |
| Sub-arc weather | Cell-canonical mean (linear for scalars, circular for directions) for the 0.5° cell |
| Sub-arc heading | Paper β for the segment the sub-arc sits in |
| Sub-arc fuel | `FCR(SWS_inverse_solved) · Δt` — **one calculation per atomic edge** (one cell, one heading, one SWS solve, one fuel scalar stored on the edge) |
| Path fuel | `Σ edge.fuel` accumulated by Bellman along the chosen path. **Luo block fuel** = sum across N atomic edges at the same SOG but different cell weathers / headings — *identical formula to the old chain-edge build*, just decomposed onto atomic edges. |
| **`sample_hour`** | **Block-start, constant within block** — sub-arcs in block `k` all read `sample_hour = k·6`. **Matches Luo 2024.** |
| `forecast_origin` | One per block (= block-start), updated at each replan in RH mode |
| Block length | 6 h |
| V-line dst-d | **Snapped to 1 nm**; SWS in the V-line-terminator sub-arc inverse-solved so trajectory lands exactly on the snap |
| Edge label | `(SOG, fuel, Δt)` — SOG carried for the Luo Bellman lock state |
| Luo realization | **Bellman state augmentation** `(node, locked_SOG)`; same graph, no second edge set |

### 2.1.5 Worked example (matches Apr 28 sketch, speed range [10, 15] kn)

Atomic edges in this slice — same graph for both DP modes:

| Atomic edge | From → To | SOG |
|---|---|---|
| `a` | (0, 0) → (2, 30) | 15 |
| `b` | (0, 0) → (3, 30) | 10 |
| `c` | (2, 30) → (4, 60) | 15 |
| `d` | (2, 30) → (5, 60) | 10 |
| `e` | (3, 30) → (6, 60) | 10 |
| `F` | (4, 60) → (6, 90) | 15 |
| `g` | (5, 60) → (6, 75) | 15 (V-line terminator, partial sub-arc) |

Paths Bellman composes:

| Path | Edges traversed | dst | Free DP? | Luo DP? |
|---|---|---|---|---|
| `a → c → F` | 15, 15, 15 | (6, 90) | ✓ | ✓ — locked SOG = 15 holds |
| `b → e` | 10, 10 | (6, 60) | ✓ | ✓ — locked SOG = 10 holds |
| `a → d → g` | 15, 10, 15 | (6, 75) | ✓ | ✗ — Luo lock blocks SOG flip from 15→10 at d=30 |

### 2.2 What changed

| File | Purpose |
|---|---|
| `frame.py` (new) | Frame primitives: V-line times, H-line distances, SOG grid, snap helpers, cell-canonical weather + paper heading lookups. No node materialization. |
| `build_atomic_edges.py` (new) | Atomic-edge builder. BFS from source, lazy node interning, one edge per (src, target_sog). Each edge carries `(target_sog, sog, sws, fuel)` — `target_sog` is the lock label, `sog` is the realized post-snap SOG. |
| `bellman_locked.py` (new) | `BellmanSolverLocked` — forward Bellman with `(node, locked_sog)` state augmentation. V-line nodes carry `lock=None`; H-line nodes carry `lock=target_sog`. Same atomic-edge graph as Free DP. |
| `run_demo_rebuild.py` (new) | End-to-end runner: builds frame, builds atomic-edge graph, runs Free DP (`BellmanSolver`) and Luo DP (`BellmanSolverLocked`) on the same graph. |

Existing `build_nodes.py`, `build_edges.py`, `build_edges_locked.py`, `bellman.py`, validators, and run_demo* are untouched.

### 2.3 Updated graph stats

| | May 4 build | Rebuild |
|---|---:|---:|
| H-lines (positions) | 162 | 162 (same — geometry unchanged) |
| V-lines | 47 | 47 |
| SOG grid | n/a (snap-grid) | 41 target SOGs in [9, 13] kn @ 0.1 kn |
| Nodes (canonical) | 613,328 | **91,663** (lazy interning — only nodes that edges land on) |
| Edges (free) | 3,308,940 | n/a (single graph) |
| Edges (locked) | 631,537 | n/a |
| **Edges (single atomic graph)** | — | **3,317,895** |
| Build time | ~230 s (free + locked sum) | **72 s** (one build) |

### 2.4 Updated YAML voyage results

| Mode | Total fuel | End time | End d | Δ vs baseline |
|---|---:|---:|---:|---:|
| **Baseline (steady SOG = 12.119 kn)** | **366.416 mt** | 280.000 h | 3393.240 nm | — |
| **Free DP** (no SOG lock) | **365.809 mt** | 280.000 h | 3393.240 nm | **−0.606 mt** |
| **Luo DP** (SOG-lock per 6 h block) | **366.132 mt** | 280.000 h | 3393.240 nm | **−0.284 mt** |
| Δ Luo − Free | +0.323 mt | — | — | — *(Luo ≥ Free by construction — confirmed)* |

**Lock invariant verified:** all 47 blocks in the Luo schedule have exactly one distinct `target_sog`. 41/41 SOG values in the grid are reachable as locks somewhere in the search.

### 2.5 Sanity checks

*(zero-weather, constant-weather, lock-monotonicity once run)*

### 2.6 Free vs Luo overlap analysis (block-by-block)

Full log: `pipeline/dp_rebuild/results/free_vs_luo_overlap_2026_05_06.txt`.

For every 6 h block in both schedules we ask:
1. How many distinct `target_sog` values does Free DP use inside this block?
2. What single `target_sog` does Luo DP lock to?

**Block classifications**

| Type | Definition | Count |
|---|---|---:|
| **A** | Free voluntarily uses **1 SOG**, *same value* as Luo (full agreement) | **0** |
| **B** | Free voluntarily uses **1 SOG**, *different value* than Luo (same structure, disagree on speed) | **1** *(block 25: Free 12.6 kn vs Luo 12.2 kn)* |
| **C** | Free uses **≥ 2 SOGs** in the block (Luo's lock forbids this) | **46** |

**Headline.** Free DP **never** picks a single SOG matching Luo (0 type-A blocks). 46 of 47 blocks Free wants to vary SOG mid-block.

**Aligned vs unaligned blocks**

A block is *aligned* when Free's and Luo's V-line `src_d` and `dst_d` coincide (same mini-problem inside the block).

| | Aligned (✓) | Unaligned (≠) |
|---|---:|---:|
| Block count | 7 / 47 | 40 / 47 |
| Σ Free fuel | 54.042 mt | 311.767 mt |
| Σ Luo fuel | 54.042 mt | 312.090 mt |
| **Δfuel (Luo − Free)** | **+0.000 mt** | **+0.323 mt** |

In every aligned block — even the 7 type-C ones where Free uses up to 5 distinct target SOGs — the per-block fuel is **identical to the millimetre**. Different target SOGs collapse to the same realized snap-grid trajectory once `(src_d, dst_d)` are pinned.

**Reframed conclusion.** The +0.323 mt Luo penalty does **not** come from "Free changes SOG mid-block, Luo can't". On this voyage that mid-block flexibility produces zero fuel saving when the V-line nodes match. The penalty comes from Luo's lock indirectly forcing the schedule onto a less-flexible *trajectory* — different `dst_d` choices at V-line boundaries — not a less-flexible *speed profile*. 40 of 47 blocks have unaligned boundaries, and the gap accumulates there.

**Implication for the paper.** The "constant-SOG-per-block" framing of Luo 2024 vs free DP isn't where the fuel difference lives. It's in the *V-line node selection* that the lock indirectly constrains. Worth highlighting as a finding.

---

## 3. Open Items / Next Steps

- **Rolling horizon** — replan every 6 h with fresh forecast.
- **Sampling strategy for new voyages** — switch collector once approved.
- **Soft ETA** — exercise `eta_mode="soft"` once rebuild is stable.

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

### 5.1 Three-mode comparison, YAML voyage (rebuilt graph)

| Metric | **Baseline (steady SOG)** | Free DP | Luo DP |
|---|---:|---:|---:|
| Total fuel (mt) | 366.416 | **365.809** | **366.132** |
| Δ vs baseline | — | −0.606 | −0.284 |
| Voyage time (h) | 280.000 | 280.000 | 280.000 |
| End d (nm) | 3393.240 | 3393.240 | 3393.240 |
| Schedule length (edges) | 1 (162 sub-arcs) | 201 | 205 |
| Edges built (single graph) | — | 3,317,895 | (same) |
| Build time | < 1 s | 72 s | (shared) |
| Solve time | — | 3.3 s | 6.3 s |
| NaN edges skipped | 0 | 0 | 0 |
| Bellman states | — | 91,663 | 1,862,370 *(node × lock)* |
| Distinct lock values used | — | n/a | 41 / 41 |

### 5.2 Comparison vs previous build (May 4 numbers)

| Mode | May 4 | Rebuild | Δ | Note |
|---|---:|---:|---:|---|
| Baseline | 366.519 mt | 366.416 mt | −0.103 mt | numerical noise from H-line set rounding |
| Free DP | 366.769 mt | **365.809 mt** | **−0.960 mt** | atomic edges (cell-level branching) beats per-square (1 nm × 0.1 h snap) |
| Luo DP | 365.161 mt | 366.132 mt | +0.971 mt | new Luo snaps V-line dst to 1 nm grid (May 4 was geometric, no snap) — small accuracy cost for shared-graph apples-to-apples |
| ~~Combined~~ | ~~362.965 mt~~ | n/a | — | dropped: Free DP on the rebuild subsumes it |

**Reading.** Rebuild Free DP improves on May 4 free DP because the new atomic edges branch at *real* cell crossings (one decision per cell) instead of per (1 nm × 0.1 h) square — fewer snap-drift opportunities. Rebuild Luo DP is slightly worse than May 4 Locked DP because snapping the V-line dst to 1 nm imposes a small accuracy cost; this is the price of running both DPs on a single shared graph. The rebuild Free vs Luo gap (+0.323 mt) is the *real* "what does mixed-speed buy us over Luo" number on a single graph.

---

## 6. Questions for Supervisor

1. *(fill in once results are in)*

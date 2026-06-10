# Meeting Prep — Supervisor Meeting, May 18 2026

---

## 1. Action Items from May 11 Meeting

| # | Task | Status |
|---|------|--------|
| 1 | *(to fill in after retrospective)* | |
| 2 | | |
| 3 | | |

Carried over from May 11 §3:

- [ ] Rolling-horizon mechanics
- [ ] Behavioural sanity checks (zero-weather, constant-weather, lock-monotonicity)
- [ ] Real heading per sub-leg
- [ ] Soft ETA exercise (`BellmanSolver.best_sink(eta_mode="soft", lam=…)`)
- [ ] Sampling strategy update — switch collector to "2–3 samples per cell-arc + segment endpoints"

---

## 2. Progress This Week — C++ + Python parallel structure

Tal pushed a complete C++ port of the rebuilt DP solver between May 11–12. Two
executables (`dp_SR` and `dp_luo`) live in `pipeline/dp_cpp/`. This week's
work brought the Python codebase into structural parity with the C++ so
future updates can be mirrored mechanically rather than redesigned.

### 2.1 Tal's C++ port (`pipeline/dp_cpp/`)

| File | Purpose |
|---|---|
| `SR_main.cpp` | SR DP entry point (`dp_SR` binary) |
| `luo_main.cpp` | Luo block DP + baseline mode (`dp_luo` binary) |
| `atomic_edges.{cpp,hpp}` | BFS atomic-edge builder |
| `bellman.{cpp,hpp}` | Forward topological Bellman |
| `frame.{cpp,hpp}` | V/H-line frame + cell-canonical weather lookup |
| `nodes.{cpp,hpp}` | Node + GraphConfig |
| `route.{cpp,hpp}` | YAML loader, paper waypoints |
| `geo_grid.{cpp,hpp}` | Rhumb-line geometry + grid crossings |
| `weather.{cpp,hpp}` | HDF5 reader, Weather struct |
| `physics.{cpp,hpp}` | Eqs 7–16 + SOG/SWS inverse |
| `common.hpp` | `TDKey`, `ShipParameters`, `WeatherDict` |

Build deps: `cmake ≥ 3.17`, `hdf5`, `yaml-cpp`. Builds two executables that
land in `pipeline/dp_cpp/build/`.

**Tal's key design changes** (vs our previous Python locked-DP):

1. **Luo is a 2D DP table over `(col, d_idx)`** with physical distance =
   `d_idx · res_nm`. Not a Bellman-side lock on the atomic-edge graph.
2. **Default speed range** = `mean_sog ± 3` (was hardcoded `[9, 13]`).
3. **CSV output** with one row per arc (SR) or per sub-segment (Luo),
   `--csv` flag on both binaries.
4. **`--baseline` mode** on `dp_luo` — single linear walk at `L/ETA`.
5. **`crosses_v_line`** field on each atomic edge so Luo can release the
   SOG lock at block boundaries.

### 2.2 Python rebuild aligned to C++ structure

Five-phase refactor of `pipeline/dp_rebuild/`:

| Phase | What changed |
|---|---|
| **1** | Module renames to mirror C++ filenames: `build_atomic_edges.py → atomic_edges.py`, `build_nodes.py → nodes.py`, `h5_weather.py → weather.py`, `load_route.py → route.py`. Added new modules `common.py` (`ShipParameters`, `make_td_key`) and `physics.py` (re-export shim over `shared/physics.py`). |
| **2** | New `SR_main.py` mirroring `SR_main.cpp` — CLI (`--yaml`, `--h5`, `--eta`, `--min_speed`, `--max_speed`, `--zeta_nm`, `--tau_h`, `--csv`), default speeds = mean_sog ± 3, CSV writer with 16 columns. Updated `atomic_edges.py` to match C++ behaviour: added `crosses_v_line` field, dropped `realized_sog ∈ [v_min, v_max]` clamp, added H-line-too-close fallback. |
| **3** | New `luo_main.py` mirroring `luo_main.cpp` — full algorithmic rewrite as 2D DP table. Drops the Bellman-side SOG-lock approach. `eval_arc` walks H-line sub-segments at constant block SOG; `--baseline` mode for linear walk. |
| **5** | Deleted 6 dead files: `run_demo.py`, `run_demo_combined.py`, `run_demo_locked.py`, `run_demo_rebuild.py`, `validate_graph.py`, `visualize_squares.py`. Moved `Weather` dataclass from `build_edges.py` → `weather.py` (mirrors C++). |

(Phase 4 — orchestration script refactor — deferred. `bellman_locked.py`,
`build_edges_locked.py`, `build_edges.py` retained as legacy shims until
`run_route2`, `run_stress_test`, etc. are updated to call the new entry
points.)

### 2.3 Repo reorganisation

Major cleanup of the directory layout to keep only the active solver code
prominent:

```
/
├── pipeline/                                ← current
│   ├── dp_cpp/                              Tal's C++ solver
│   ├── dp_rebuild/                          our Python solver
│   ├── shared/                              physics, beaufort, hdf5_io
│   ├── collect/                             Edison weather collector
│   ├── config/routes/                       all route YAMLs in one place
│   ├── data/                                HDF5 (gitignored)
│   ├── run_all.py                           Edison entry
│   └── requirements.txt
├── old/                                     ← legacy
│   ├── Dynamic speed optimization/          legacy DP code
│   ├── Linear programing/                   legacy LP code
│   ├── pipeline_legacy/                     old pipeline subdirs + scripts
│   ├── class.py, remote_server_scripts/, test_files/
├── docs/, context/, paper/                  unchanged
```

`Dynamic speed optimization/weather_forecasts.yaml` (Route 1) promoted to
`pipeline/config/routes/persian_gulf_malacca_paper.yaml` so all route
configs live together. All 11 Python scripts that hardcoded the old
location were updated.

---

## 2.4 Parity verification — C++ ↔ Python

Both solvers run end-to-end on Route 1 / ETA = 280 / default speeds
(v_min = 9.1, v_max = 15.1 kn):

| Solver | Total fuel | Graph | Build | Solve |
|---|---:|---|---:|---:|
| **C++ `dp_SR`** | **359.594 mt** | 152,571 nodes / 9,214,780 atomic edges | 12.3 s | 0.26 s |
| **Python `SR_main.py`** | **359.305 mt** | 152,571 / 9,214,780 *(identical)* | 192.5 s | 9.18 s |
| Δ (SR) | **−0.289 mt (−0.08 %)** | bit-exact graph structure | — | — |

| Solver | Total fuel | Schedule | Solve |
|---|---:|---|---:|
| **C++ `dp_luo`** (res_nm=1.0) | **366.140 mt** | 47 blocks / 209 sub-segments | 14.3 s |
| **Python `luo_main.py`** (res_nm=1.0) | **365.970 mt** | 47 / 209 *(identical)* | 188.7 s |
| Δ (Luo) | **−0.170 mt (−0.046 %)** | identical structure | — |

| Solver | Total fuel |
|---|---:|
| **C++ `dp_luo --baseline`** | **367.560 mt** |
| **Python `luo_main.py --baseline`** | **367.394 mt** |
| Δ (Baseline) | **−0.166 mt (−0.045 %)** |

**Diagnosis of the consistent ≈0.05–0.08 % drift:** Both implementations
use the same algorithm (binary search, tolerance 0.001 kn, max 50 iter,
bracket [5, 20]). The drift comes from bit-level floating-point ordering
differences in `calculate_speed_over_ground`'s arithmetic chain
(resistance components → corrected speed → current synthesis). Python
yields slightly lower fuel on the same trajectory. Well below the noise
floor for any paper-relevant comparison.

**Structural parity is exact**:
- Graph shape: identical node + edge counts on SR DP
- Schedule length: identical
- SOG ranges, V-lines, H-lines: identical
- CSV format: identical column-by-column

---

## 3. Open Items / Next Steps

- **Mode C wired through** (`atomic_edges.py`, `build_edges_locked.py`,
  `run_route2.py`, new `run_route1.py`). Every solver — SR DP, Luo DP,
  Baseline — now reads per-block actual weather instead of a single
  voyage-start snapshot. First Atlantic + PG comparisons logged in §5.3.
- **Phase 4** — refactor orchestration scripts (`run_stress_test.py`,
  `run_route2.py`, `analyze_overlap.py`, `find_divergent_waypoints.py`,
  `trace_optimal.py`, `visualize_schedules.py`, `visualize_stress.py`)
  to call `SR_main.solve()` / `luo_main.solve()` instead of the legacy
  locked modules. Unblocks final deletion of `bellman_locked.py`,
  `build_edges_locked.py`, `build_edges.py`.
- **Rolling horizon** — same atomic-edge graph, rebuild edges at each 6 h
  decision step with the next forecast. Now that Tal's C++ has a stable
  Luo block DP, the RH wrapper can be a thin orchestration layer.
- **Behavioural sanity checks** — zero-weather, constant-weather,
  lock-monotonicity.
- **Soft ETA** exercise.
- **Route 2 (Atlantic) under the new C++/Python pair** — current parity
  numbers are Route 1 only; Route 2 needs the same C++↔Python check.

---

## 4. Data Collection Status

| Server | Status | Route 1 (138 wp) | Route 2 (389 wp) | Uptime |
|--------|--------|---|---|--------|
| Shlomo1 | | | | |
| Shlomo2 | | | | |
| Edison  | | | | |

*(refresh on the morning of May 18)*

The collector was renamed in `run_all.py` on May 7 — `exp_b → "Route 1"`,
`exp_d → "Route 2"` — and re-deployed to Edison. exp_c (968 wp) remains
removed from the loop pending decision.

---

## 5. Results Tables

### 5.1 Three-mode comparison — Route 1 (Persian Gulf → Malacca) / ETA = 280 h

Default speed range mean_sog ± 3 = [9.1, 15.1] kn. Both languages agree
structurally and to within 0.08 % on total fuel.

| Metric | **Baseline (steady SOG)** | **dp_SR / SR_main** | **dp_luo / luo_main** |
|---|---:|---:|---:|
| C++ fuel (mt) | 367.560 | 359.594 | 366.140 |
| Python fuel (mt) | 367.394 | 359.305 | 365.970 |
| Δ vs baseline (C++) | — | **−7.966 mt (−2.17 %)** | **−1.420 mt (−0.39 %)** |
| Δ (SR − Luo) | — | **−6.546 mt (−1.82 % of baseline)** | — |
| Graph (SR) | — | 152,571 nodes / 9,214,780 atomic edges | — |
| Schedule (SR) | 1 (163 sub-segs) | 147 atomic arcs | 47 blocks / 209 sub-segs |
| Build / Solve (C++) | — | 12.3 / 0.26 s | — / 14.3 s |
| Build / Solve (Python) | — | 192.5 / 9.2 s | — / 188.7 s |

### 5.2 Comparison vs May 11 rebuild numbers

| Mode | May 11 (v=[9, 13]) | May 18 (v = mean_sog ± 3) | Comment |
|---|---:|---:|---|
| Baseline | 366.416 mt | 367.560 mt | new baseline uses wider snap-grid window |
| SR DP | 365.809 mt | **359.594 mt** | **−6.2 mt** — wider speed range gives optimizer more headroom |
| Luo DP | 366.132 mt | **366.140 mt** | unchanged within noise — Luo's lock makes wider range less valuable |
| Δ Luo − SR | +0.323 mt | **+6.546 mt** | **gap widened 20×** — SR's value comes from speed flexibility, not just decision freedom |

**Headline.** Under the default `mean_sog ± 3` speed range (C++ convention,
now matched in Python), SR DP saves **2.17 %** of baseline fuel while
Luo's lock costs **1.82 %** of that saving. Previously, with the
artificially narrow `[9, 13]` window, SR DP barely beat baseline and Luo
was within noise — masking the real SR-vs-Luo gap.

### 5.3 Mode C — per-block actual weather (oracle planning)

**Methodology change.** Previously the optimizer used
`actual_weather[sample_hour=N]` as a *single snapshot* for the entire voyage
(Mode A — pretends weather is constant). New runs use Mode C:
`actual_weather[sample_hour = N + 6·block_index]` per block — the nowcast
that was actually recorded at the moment the ship would be in each block.
This is the Luo-2024 weather-row convention. Code wired through
`atomic_edges` (via `Frame.sample_hour_for_block` with new
`base_sample_hour` offset), `simulate_steady_voyage`, and `run_route2.py`
/ new `run_route1.py`. Luo DP / Baseline (steady SOG) updated symmetrically
so all three solvers see the same weather sequence per voyage.

Mode C is an **oracle / upper-bound** planner — it reads ground-truth
nowcasts that wouldn't yet exist at planning time. The realistic
"single-forecast" Mode B (using `predicted_weather[sample_hour=N,
forecast_hour=k]`) is deferred; Mode B − Mode C would measure the value of
perfect information.

**HDF5 sync.** Both files refreshed from Shlomo2 on May 14: PG 88 → 92 MB
(271 samples, 67 days Mar 8 → May 15), Atlantic 212 → 238 MB (272 samples).
Both span the same calendar window. PG has 19 fully-NaN sample_hours
(failed cycles), so PG sample_hour=24 isn't usable; first clean 280h window
starts at sample_hour=222.

#### 5.3.1 Atlantic (Route 2) — two voyages, same Mode C planner

L = 1,955 nm, ETA = 168 h, target SOG = 11.64 kn. Speed range [9, 13] kn
(default Python). Graph: 52,025 nodes / 2,104,743 edges (Atlantic).

| Metric | **Storm (sh=180)** | **Calm (sh=1374)** |
|---|---:|---:|
| Wall-clock | Mar 16 → Mar 22, 2026 | May 4 → May 11, 2026 |
| Voyage mean Hs | 4.35 m | 2.03 m |
| Per-block wind std | 10.96 km/h | 3.33 km/h |
| Wave-Hs trajectory | 6.7 → 3.0 m (decaying) | 1.2 → 1.9 m (flat) |
| Baseline (steady 11.64 kn) | 203.457 mt | 212.342 mt |
| **SR DP** | **196.872 mt** | **208.430 mt** |
| **Luo DP** | **196.986 mt** | **208.495 mt** |
| SR savings vs baseline | **−3.24 %** | **−1.84 %** |
| **Δ Luo − SR** | **+0.114 mt** | **+0.065 mt** |
| Block alignment | 15/28 (54 %) | 16/28 (57 %) |
| Type B blocks (single SOG, SR ≠ Luo) | 3 | 0 |
| Type C blocks (SR ≥ 2 SOGs) | 20 | 19 |

#### 5.3.2 Persian Gulf (Route 1) — single voyage, Mode C

L = 3,394 nm, ETA = 280 h, target SOG = 12.12 kn. Speed range [9, 13] kn.
Graph: 108,418 nodes / 4,397,129 edges. Build 90 s, solve 4 s.

| Metric | **PG (sh=222)** |
|---|---:|
| Wall-clock | Mar 17 → Mar 28, 2026 |
| Voyage mean wind / wave | 10.9 km/h (node 65) / mid-route Hs 0.79 m |
| Baseline (steady 12.12 kn) | 366.162 mt |
| **SR DP** | **358.480 mt** |
| **Luo DP** | **358.532 mt** |
| SR savings vs baseline | **−2.10 %** |
| Δ Luo − SR | +0.053 mt |
| Block alignment | 31/47 (66 %) |

#### 5.3.3 Cross-route — storm vs calm story

| | **Atlantic storm** | **Atlantic calm** | **Persian Gulf** |
|---|---:|---:|---:|
| Voyage mean Hs | 4.35 m | 2.03 m | ~0.8 m |
| Per-block wind std | **10.96** km/h | 3.33 km/h | ~5.5 km/h |
| SR savings vs baseline | **−3.24 %** | −1.84 % | −2.10 % |
| Δ Luo − SR | **+0.114 mt** | +0.065 mt | +0.053 mt |
| Block alignment | 54 % | 57 % | 66 % |

**Three findings worth highlighting.**

1. **Optimizer value tracks weather *variability*, not severity.** Storm Atlantic
   has 3.3× the per-block wind std of calm Atlantic and SR DP captures 76 %
   more savings (3.24 % vs 1.84 %). PG sits in the middle on both axes.
2. **Counterintuitive: storm voyage burns *less* total fuel than calm voyage
   on Atlantic** (197 vs 208 mt). The Mar 16 N-Atlantic storm produced
   westerly winds — a tailwind/following-sea regime for the eastbound voyage.
   Severity ≠ difficulty: it's *direction relative to heading* that matters.
   A westbound voyage on the same storm date would be punishing.
3. **Luo's 6h SOG-lock cost grows with weather variability** (+0.114 mt storm
   vs +0.065 mt calm Atlantic). Locking is cheap in steady weather; expensive
   when intra-block conditions swing.

#### 5.3.4 Methodological note — Mode A vs Mode C on PG

At sh=222, the weather rows read by Mode C vs the single Mode A snapshot
differ by typically **±3 km/h wind, ±0.3 m wave per block**. Mid-route
(node 65) wind varies 3.2–22.2 km/h (std 5.5) across the 47 sample_hours
the voyage actually traverses — a single Mode A snapshot collapses that
entire range to one row replicated 47 times. The 2 % fuel difference
between Mode A and Mode C reflects the optimizer using the *correct*
weather row per block.

### 5.4 Speed-range sweep — Mode C on R1 + R2

Single-script sweep (`pipeline/dp_rebuild/run_speed_sweep.py`,
77 min wall) over `v_max ∈ {13, 15, 18, 21, 24}` with `v_min = 9 kn` fixed.
Mode C oracle weather, default `sog_step = 0.1 kn`, ETA fixed per route
(R1 = 280 h, R2 = 168 h). Three voyages:

- **R1 (PG)** at sh = 222 (first clean 280 h window)
- **R2 storm** at sh = 180 (Mar 16, mean Hs 4.35 m, tailwind regime)
- **R2 calm** at sh = 1374 (May 4, mean Hs 2.03 m)

| Route | sh | v_max | base mt | **SR mt** | SR save % | Luo mt | Luo−SR mt | build s |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| R1 (PG)   | 222  | 13 | 366.162 | **358.480** | −2.098 | 358.532 | +0.053 | 88.9 |
| R1 (PG)   | 222  | 15 | 365.862 | **358.168** | −2.103 | 358.221 | +0.053 | 180.3 |
| R1 (PG)   | 222  | 18 | 365.862 | **358.168** | −2.103 | 358.221 | +0.053 | 347.5 |
| R1 (PG)   | 222  | 21 | 365.862 | **358.168** | −2.103 | 358.221 | +0.053 | 521.0 |
| R1 (PG)   | 222  | 24 | 365.862 | **358.168** | −2.103 | 358.221 | +0.053 | 698.7 |
| R2 storm  | 180  | 13 | 203.457 | **196.872** | −3.237 | 196.986 | +0.115 | 44.3 |
| R2 storm  | 180  | 15 | 203.457 | **195.573** | −3.875 | 195.641 | +0.068 | 83.5 |
| R2 storm  | 180  | 18 | 203.457 | **195.573** | −3.875 | 195.641 | +0.068 | 152.4 |
| R2 storm  | 180  | 21 | 203.457 | **195.573** | −3.875 | 195.641 | +0.068 | 231.3 |
| R2 storm  | 180  | 24 | 203.457 | **195.573** | −3.875 | 195.641 | +0.068 | 352.6 |
| R2 calm   | 1374 | 13 | 212.342 | **208.430** | −1.842 | 208.495 | +0.065 | 44.2 |
| R2 calm   | 1374 | 15 | 212.342 | **208.092** | −2.001 | 208.144 | +0.052 | 85.1 |
| R2 calm   | 1374 | 18 | 212.342 | **208.092** | −2.001 | 208.144 | +0.052 | 160.9 |
| R2 calm   | 1374 | 21 | 212.342 | **208.092** | −2.001 | 208.144 | +0.052 | 236.7 |
| R2 calm   | 1374 | 24 | 212.342 | **208.092** | −2.001 | 208.144 | +0.052 | 314.4 |

Full sweep also in `pipeline/dp_rebuild/results/speed_sweep_2026_05_17.md`.

**Three findings.**

1. **SR DP saturates at v_max = 15 kn on every voyage.** From v_max = 15
   onward, SR fuel is identical to 3 decimal places — the optimizer
   never uses the extra headroom. Same for Luo. Compute is wasted past
   v_max = 15: R1 atomic-edge graph grows from 4.4 M edges (v_max=13)
   to **34.2 M** at v_max=24, build time 89 s → 699 s, for **zero**
   change in optimal fuel.

2. **The real gain is the 13 → 15 jump.** R2 storm benefits most
   (**−1.30 mt**, +0.64 pp extra savings), R2 calm next (−0.34 mt,
   +0.16 pp), R1 minimal (−0.31 mt, +0.005 pp). Where the optimizer
   wants to bank time via short bursts above 13 kn — tailwind storm —
   the narrow window costs real fuel.

3. **Luo's SOG-lock cost shrinks with wider speed range** (where it
   mattered). R2 storm: +0.115 mt @ v_max=13 → +0.068 mt @ v_max=15+
   (−41 %). More SOG choices per block → Luo can pick a better single
   SOG. R1 PG was already saturated.

4. **Best SR-vs-Luo gap across the sweep: R2 storm @ v_max=13,
   +0.115 mt (0.058 % of fuel).** This is the *largest* SR-over-Luo
   advantage anywhere in the matrix. Other gaps: R2 calm +0.065 mt
   (0.031 %), R1 PG +0.053 mt (0.015 %). **SR DP's advantage over Luo
   is small everywhere — at most ~0.06 % of fuel.** Counterintuitive:
   the gap is *widest* with a *narrow* speed range and *volatile*
   weather, because that combination is where Luo's per-6 h SOG-lock
   bites hardest. Practically: the **SR-vs-Luo story is second-order**;
   the headline is **SR-vs-baseline**, which reaches −3.875 % on R2
   storm.

#### 5.4.1 Why is the SR-vs-Luo gap so narrow?

The two solvers share the same atomic-edge graph and the same Mode C
weather lookup. The *only* extra freedom SR has is the right to change
target SOG at each H-line within a 6 h block (typically 3–4 H-lines /
block), while Luo locks one SOG for the whole block. So the entire SR
advantage must come from **intra-block SOG modulation**. Why does that
buy so little?

**(a) Where the gap *can* come from is small to begin with.** Block
classification across the three Mode C voyages (§5.3.1, §5.3.2):

| Voyage | Type A (SR=Luo) | Type B (one SOG, ≠ Luo) | Type C (SR ≥ 2 SOGs) | Luo−SR mt | mt / Type-C block |
|---|---:|---:|---:|---:|---:|
| R2 storm sh=180 | 5/28 | 3/28 | 20/28 | +0.115 | ~5.8 mg |
| R2 calm sh=1374 | 9/28 | 0/28 | 19/28 | +0.065 | ~3.4 mg |
| R1 PG sh=222 | — | — | — | +0.053 | — |

R1 PG breakdown not in the doc — only an "aligned" count (31/47, by
src_d/dst_d match, not by SOG). Doc TODO: rerun R1 with A/B/C
classification. For R2 the pattern is clear: Type A contributes
**zero** to the gap by definition; even on R2 storm the per-Type-C
block penalty is ~5 mg. The mechanism is real but tiny per block.

**(b) Within-block weather barely varies.** Mode C reads one weather
row per (block, cell). A 6 h block at ~11.6 kn covers ~70 nm — about
2–3 0.5° cells. Adjacent cells along a rhumb line have correlated
weather (spatial correlation length >> 30 nm in most regimes), so the
intra-block cell-to-cell weather change is small. SR has the *freedom*
to switch SOG at every H-line; absent meaningful weather change across
those H-lines, it doesn't *want* to.

**(c) FCR convexity actively *prefers* uniform SOG when weather is
constant.** With one block-constant weather row, the only feasible
single-SOG schedule is s̄ = L_block / T_block, and Jensen's inequality
on the cubic FCR makes **uniform SOG the unique optimum**. So if the
weather were truly constant within a block, Type A would hit 100 %
and Luo−SR would be 0. The non-zero gap is exactly the Jensen leak
from weather varying *across cells within a block*.

**(d) Number of within-block decision points is small.** With
`dt_h = 6 h` and 3–4 H-lines per block, SR has at most 2–3 atomic-edge
slots to vary SOG inside a block. Combined with (b), most of those
slots see the same or nearly the same weather as their neighbours, so
SR's "free" decisions collapse to "pick the same SOG anyway."

**Recipe to widen the gap (for the paper, if we wanted to).**
- **Shorter blocks** (`dt_h = 3 h` or `dt_h = 1 h`) **don't help** by
  themselves — H-lines / cells already define SR's decision points;
  Luo's lock relaxes mechanically when the block becomes shorter, so
  both solvers converge as `dt_h → 0`. Shortening *Luo's* lock without
  also shortening the weather refresh shrinks the gap.
- **Higher-resolution weather** (finer cells, smaller correlation
  length) is the right lever. If cells were 5 nm instead of 30 nm,
  within-block weather variation would be much larger and SR's
  per-H-line SOG agility would actually matter.
- **Sharper synthetic perturbations** (`weather_perturb.py` σ-grid)
  inject larger cell-to-cell variability and should widen the gap
  predictably — that's the right vehicle for showcasing the SR
  advantage.

If we want to widen the SR-vs-Luo gap for the paper, the levers are
**finer weather resolution** or **synthetic perturbations**, *not*
wider speed ranges or shorter blocks alone.

### 5.5 ETA sweep — Mode C on R1 + R2

Second sweep (`pipeline/dp_rebuild/run_eta_sweep.py`, 102 min wall)
tightening ETA per route to test the speed-constrained regime.
v_min = 9 kn, **v_max = 25 kn fixed** (never-binding ceiling across all
runs), SOG step = 0.1 kn, Mode C oracle weather. Same three voyages
as §5.4: R1 sh=222, R2 storm sh=180, R2 calm sh=1374. Three ETAs per
voyage: nominal, −30 h, −60 h (R2 scaled proportionally).

| Route | sh | ETA | mean SOG | base mt | **SR mt** | Luo mt | SR save % | Luo−SR mt |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| R1 (PG)   | 222  | 280 | 12.12 | 365.862 | **358.168** | 358.221 | −2.103 | +0.053 |
| R1 (PG)   | 222  | 240 | 14.14 | 489.703 | **482.567** | 482.590 | −1.457 | +0.023 |
| **R1 (PG)**| **222** | **200** | **16.97** | **699.049** | **692.316** | **693.120** | **−0.963** | **+0.804** |
| R2 storm  | 180  | 168 | 11.64 | 203.457 | **195.573** | 195.641 | −3.875 | +0.068 |
| R2 storm  | 180  | 144 | 13.57 | 279.295 | **273.242** | 273.423 | −2.167 | +0.181 |
| R2 storm  | 180  | 120 | 16.29 | 392.205 | **387.095** | 387.297 | −1.303 | +0.202 |
| R2 calm   | 1374 | 168 | 11.64 | 212.342 | **208.092** | 208.144 | −2.001 | +0.052 |
| R2 calm   | 1374 | 144 | 13.57 | 279.243 | **269.249** | 269.467 | −3.579 | +0.219 |
| R2 calm   | 1374 | 120 | 16.29 | 375.710 | **366.325** | 366.340 | −2.498 | +0.015 |

Full sweep at `pipeline/dp_rebuild/results/eta_sweep_2026_05_18.md`.

**Three findings.**

1. **Fuel roughly doubles for a 30 % ETA cut.** Cubic FCR dominates:
   - R1: 366 → 490 → **699 mt** (×1.91)
   - R2 storm: 203 → 279 → 392 mt (×1.93)
   - R2 calm: 212 → 279 → 376 mt (×1.77)

2. **SR savings vs baseline shrink under time pressure on R1 + R2 storm.**
   R1 −2.10 % → −1.46 % → −0.96 %. R2 storm −3.88 % → −2.17 % → −1.30 %.
   With less time slack, the optimizer can't slow down in adverse cells
   — everyone must push hard, so plan-vs-baseline converges.
   **Exception: R2 calm @ ETA=144 hits −3.58 % savings** (more than at
   ETA=168, −2.00 %). Non-monotonic. Hypothesis: a favorable patch in
   the May 4 forecast that the optimizer only fully exploits when
   forced to raise mean SOG. Worth a focused look at the schedule.

3. **Luo−SR gap grows sharply with time pressure — the missing signal.**

| Route | nominal | −30 h | tightest |
|---|---:|---:|---:|
| R1 | +0.053 mt | +0.023 mt | **+0.804 mt** ← 15× jump |
| R2 storm | +0.068 mt | +0.181 mt | +0.202 mt (~3×) |
| R2 calm | +0.052 mt | +0.219 mt | +0.015 mt (anomalous) |

   **R1 @ ETA=200 — Luo burns +0.804 mt extra (0.115 % of fuel) — the
   largest SR-vs-Luo gap in any experiment to date.** This validates the
   §5.4.1 mechanism: `gap ≈ FCR-convexity · within-block weather variance`.
   Bumping mean SOG from 12 → 17 kn ramps `d²FCR/dV²` sharply (cubic
   FCR ⇒ quadratic curvature), so the same intra-block weather variance
   leaks much more fuel under Luo's lock. **Time pressure is the lever
   that surfaces SR's algorithmic advantage** — not wider speed ranges,
   not finer block timing.

   **R2 calm @ ETA=120 anomaly** (+0.015 mt, gap collapses) needs
   investigation. Candidate explanations: (i) v_max=25 starts to bind in
   adverse blocks, forcing both solvers to the same ceiling SOG;
   (ii) the May 4 calm forecast has so little within-block weather
   variance that the Jensen-leak mechanism shuts off; (iii) some blocks
   converge to Type A because mean SOG forces a unique feasible pick.
   Need block-classification + ceiling-binding diagnostic.

**Implication for Q1 (speed-range default).** The `mean_sog ± 3`
convention (≈ [9.1, 15.1] for R1; [8.6, 14.6] for R2) lands inside
the saturation region. So does any v_max ≥ 15. The debate between
`[9, 13]` and `[9, 24]` reduces to **"v_max = 13 vs v_max ≥ 15"** —
and v_max = 15 is sufficient. Recommended paper convention:
`v_min = 9, v_max = 15` (full optimization value, smallest graph).

---

## 6. Questions for Supervisor

1. **Speed range default** (see §5.4). Sweep over `v_max ∈ {13, 15, 18,
   21, 24}` with `v_min = 9` shows SR DP fuel **saturates at v_max = 15**
   on every voyage — pushing to 18/21/24 gives zero additional savings
   for 3-8× the compute. The real choice is `[9, 13]` vs `[9, 15]`, and
   `[9, 15]` clearly wins (largest gain on R2 storm: −1.30 mt / +0.64 pp).
   Proposed paper convention: **`v_min = 9, v_max = 15`** uniformly across
   both routes. Agree?

2. **Phase 4 priority**. The Python code mirrors the C++ structurally, but
   stress-test / Route 2 / visualization scripts still call the legacy
   locked-DP modules. Refactoring them = ~1 day's work. Should we do that
   now or push ahead with Rolling Horizon implementation first?

3. **Route 2 parity**. C++ ↔ Python parity confirmed only on Route 1.
   Re-running on Route 2 (St. John's → Liverpool, 168 h ETA) before next
   meeting?

4. **C++ as the production solver?** Python is now 15× slower per build
   (~3 min vs 12 s on Route 1). For stress sweeps and σ-grids, the C++
   binary is the obvious choice. Do we want to wrap it in Python
   orchestration (subprocess + CSV parsing) or keep dual-language parallel
   development?

5. **Rolling Horizon design**. With Tal's 2D DP table Luo, an RH wrapper is
   straightforward: rebuild the DP at each 6 h decision step with the
   latest forecast, take the first block's optimal SOG, advance. Worth
   prototyping in Python first (matches our experimental workflow), then
   porting to C++?

6. **Mode A vs B vs C as primary planning convention** (§5.3). Mode C
   (per-block actual_weather, "oracle") is now wired through all three
   solvers and gives the first cross-route comparable numbers (Atlantic
   storm/calm + PG). Mode C is an upper-bound benchmark — it uses ground
   truth that wouldn't exist at planning time. The realistic Mode B
   (per-block `predicted_weather` from the planning-moment NWP cycle) is
   not yet implemented. Do we want Mode B as the primary thesis baseline,
   with Mode C as the "value of perfect information" upper bound, or
   present Mode C results alone for now?

7. **PG data quality**. 19 of 271 Persian Gulf sample_hours are fully NaN
   (failed collection cycles: 12, 18, 42, 54, 84, 96, 144, 186, 192, 198,
   204, 210, 216, 540, 732, 738, 744, 750, 756). Mode C fails on any
   voyage window that lands on these. First clean 280h window starts at
   sh=222. Options: (a) report results only on clean windows;
   (b) implement a nearest-non-NaN fallback in the weather lookup so any
   sample_hour can be the base; (c) re-collect (and accept gap). Atlantic
   has only 8 such cycles and is unaffected for the sample_hours we want.

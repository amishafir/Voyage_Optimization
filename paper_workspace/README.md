# Paper Workspace — SR vs Luo Voyage Optimization

Self-contained workspace for writing and reconstructing the journal paper. Everything
needed — scripts, results, input/output data, context, and reference material — was
**copied** here (originals remain in place under `/Users/ami/Desktop/university`).

Created: 2026-06-08.

---

## The paper, in one line

> **Per-leg speed freedom (SR) beats per-block SOG-locking (Luo 2024) by ~6–7 mt
> (1.8–2.6 %) across 19 voyages and two weather regimes — explained by Jensen's
> inequality on the convex FCR — at both the Mode-C oracle ceiling and the RH
> operational floor, at a characterized computational cost (fuel-vs-compute tradeoff).**

### Locked design decisions (2026-06-08)

| Decision | Choice |
|---|---|
| **Spine** | SR vs Luo baseline (per-leg freedom vs per-block SOG-lock) |
| **Comparison points** | **Mode C** (oracle, actual weather) + **RH** (operational). *No Mode B; no other modes.* |
| **Second axis** | Computational complexity: Luo's block graph vs our atomic-edge graph |
| **Evidence scope** | Recent two-route chain sweeps as primary; forecast-error / horizon / replan / NWP-cycle as supporting |
| **Venue** | Transportation Research Part C (~8–10k words) |
| **Hard constraint** | **No new runs.** The paper is built only from results already on disk. |

### Explanatory core
The SR−Luo fuel gap is *explained*, not just measured: per-block SOG-locking pays a
**Jensen's-inequality penalty** on the convex (cubic) FCR whenever weather varies within
a block. This is the intellectual engine of the paper, not a side contribution.

---

## Folder map (and where each part came from)

| Folder | Contents | Copied from |
|---|---|---|
| `00_design/` | Backward-design artifacts (G1–G6 gates). See `00_design/README.md`. | *(new — created here)* |
| `paper/` | Existing draft: `paper_outline.md`, `style_guide.md`, `speed_control_v1.tex` (+ `_supervisor_feedback`), `sections/`, `tables/`, `figures/`, `bibliography/` | `paper/` |
| `results/` | All run outputs (the evidence base) | `runs/` |
| `scripts/dp_rebuild/` | Python solvers: `SR_main.py`, `luo_main.py`, `run_chain_sweep.py`, `analyze_chain_sweep.py` + deps (`frame.py`, `weather.py`, `atomic_edges.py`, `bellman.py`, `physics.py`, …) | `pipeline/dp_rebuild/` (no `__pycache__`, no `runs/`) |
| `scripts/dp_cpp/` | C++ solvers (RH chain): `src/`, `CMakeLists.txt`, port specs, tests | `pipeline/dp_cpp/` (source only — no `build/`, no `__pycache__`) |
| `scripts/shared/` | Physics + I/O that `dp_rebuild` imports (`physics.py` = SOG chain, FCR, `calculate_sws_from_sog`; `beaufort.py`, `hdf5_io.py`, `simulation.py`, `metrics.py`) | `pipeline/shared/` (added 2026-06-08 — `dp_rebuild` depends on it) |
| `data/` | Input HDF5: `experiment_a_7wp.h5`, `experiment_b_138wp.h5` (Route 1), `experiment_d_391wp.h5` (Route 2), `paper_table8.h5` | `pipeline/data/` |
| `config/` | Route YAMLs (`persian_gulf_malacca*`, `st_johns_liverpool`, …), experiment configs, `ship_parameters.yaml` | `pipeline/config/` + `old/Dynamic speed optimization/` |
| `context/docs/` | Meeting preps, `thesis_brainstorm.md`, `experiment_framework.md`, `WBS_next_phases.md`, summaries | `docs/` |
| `context/literature/` | 6 pillar files, `_index.md`, `_template.md`, + PDFs (85M) | `context/literature/` |
| `reference/` | Skill content: `paper-equations`, `paper-results`, `paper-style`, `paper-outline`, `research-paper`, `waypoints`, `dp-optimizer`, `lp-optimizer`, … | `.claude/skills/` |

---

## The evidence base (the two CSVs everything rests on)

| File | What it is | Solver lang | Routes |
|---|---|---|---|
| `results/2026_06_01_chain_sweep/results.csv` | **Mode C** consecutive-voyage chain (19 voyages: R1 ×7, R2 ×12). SR vs Luo on actual weather. | Python | Both |
| `results/2026_06_15_rh_cpp_chain/results.csv` | **RH** consecutive-voyage chain. SR vs Luo under rolling horizon. | C++ | Both |

Per-voyage per-arc schedules live in `route1/` / `route2/` subfolders alongside each `results.csv`.

### Mode-C CSV schema (`run_chain_sweep.CSV_HEADER`)
```
route, label, voyage_idx, sh_base, eta_h,
sr_fuel_mt, luo_fuel_mt, gap_mt, gap_pct,
sr_voyage_time_h, luo_voyage_time_h, sr_slack_h, luo_slack_h,
sr_n_nodes, sr_n_edges, sr_build_s, sr_solve_s,   ← SR: nodes, edges, build, solve
luo_n_blocks, luo_solve_s                          ← Luo: blocks, solve only
```

### ⚠️ Compute-axis caveats (load-bearing for the tradeoff claim)
1. **Instrumentation is asymmetric.** SR logs `n_nodes/n_edges/build_s/solve_s`; Luo logs
   only `n_blocks/solve_s`. The clean measured comparison is **solve time** (both, same
   sweep, same machine). **Graph size** must be reconciled *analytically* (atomic edges vs
   blocks are different units). **Build time** is SR-only — analytical or omit for Luo.
2. **Don't mix languages for timing.** Mode-C chain is Python; RH chain is C++. Fuel parity
   is confirmed (≤0.08 %), so fuel numbers combine fine. **Keep all compute/timing
   comparison inside the Python Mode-C sweep** where SR and Luo ran side by side.

---

## Reconstruction (only if ever needed — default is no new runs)

Solvers are pure Python (`scripts/dp_rebuild/`); deps in
`Linear programing/requirements.txt` / `requirements_marine.txt` at the repo root.
Example (illustrative — not part of the writing workflow):
```
cd scripts/dp_rebuild
python3 run_chain_sweep.py        # regenerates results/<date>_chain_sweep/
```
C++ RH: build via `scripts/dp_cpp/CMakeLists.txt`, run via `run_rh_chain.py`.

## Notes
- ~510 MB total (417 MB is HDF5 input data, 86 MB is literature PDFs). If committing to
  git, add `paper_workspace/data/` and `paper_workspace/context/literature/pdfs/` to
  `.gitignore` to avoid bloating the repo.
- Source-of-truth numbers: cross-check every figure against the CSVs here, not the prose
  in `context/docs/` meeting preps (preps may round or predate a rerun).

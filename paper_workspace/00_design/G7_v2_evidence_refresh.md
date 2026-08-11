# G7 — v2 Evidence Refresh (reopens G1's "no new runs" constraint)

**Gate status:** DRAFT. Not frozen — nothing executed yet (no SSH downloads, no code changes, no
runs). This gate exists outside the G1→G6 backward-design chain: G1–G6 write *this* paper from the
Jun-8 frozen evidence; G7 defines a **new, dated evidence base** that G1 will be re-pointed at once
validated. **The Jun-8 v1 evidence (`results/2026_06_01_chain_sweep/`,
`results/2026_06_15_rh_cpp_chain/`, `data/*.h5`) is left untouched as a fallback** — nothing here
overwrites it.

**Trigger (2026-08-10/11):** results section needs a rewrite — more voyages, a constant-speed
("Naive") comparison point, and CI instead of std-dev for spread. See
[[project_results_rewrite_aug10]] (session memory).

**Supersedes:** the `00_design/README.md` locked input *"Constraint: no new runs — G1 is a closed
audit of `../results/` + `../context/docs/`"* — deliberately, not accidentally. That line stays in
the README as the record of the v1 decision; this gate is the record of why/how it was reopened.

---

## Why the refresh is not optional

Both route chains in `run_chain_sweep.py` are already maxed out on the Jun-1 data — this isn't a
"nice to have more data" ask, it's a hard blocker on adding a single additional voyage:

| Route | Last voyage start (`sh_base`) | + ETA = required data through | Data currently ends |
|---|---:|---:|---:|
| route1 (Malacca) | 1686 | 1966 | ~2052 (no room for `sh_base=1966`, needs data to 2246) |
| route2 (Atlantic) | 1848 | 2016 | ~2052 (no room for `sh_base=2016`, needs data to 2184) |

So: **harvest refresh → more voyages → redesigned comparison**, strictly sequenced, not three
parallel tracks.

---

## A. Weather harvest refresh (route1 + route2 only — no new routes)

1. **Read-only check first** (in progress — see status below): confirm the `collect_all` tmux
   sessions on Shlomo2 (route1 source) and Edison (route2 source) are alive, and read the current
   max `sample_hour`/timestamp in whatever they're writing to. No download at this step.
2. **Pull as dated v2 copies, not overwrites**: `data/experiment_b_138wp_v2_aug.h5`,
   `data/experiment_d_391wp_v2_aug.h5`. Originals (`experiment_b_138wp.h5`,
   `experiment_d_391wp.h5`, both `Jun 8 13:13`) stay in place.
3. **Continuity check before trusting the extension**: confirm the new file's early
   `sample_hours` overlap and agree with the old file's tail (no discontinuity/gap at the seam).
   Candidate tool: `/hdf5-comparison` skill or the `hdf5-comparator` agent.

## B. Chain-sweep expansion (more voyages per route — chosen axis)

1. **Stop hardcoding `sh_bases`.** `run_chain_sweep.py`'s `ROUTES[...]["sh_bases"]` is currently a
   manually written list per route — it goes stale on every refresh (as it just did). Replace with
   a generator: start at `voyage.sample_hours[0]`, step by `eta`, stop once
   `sh_base + eta > max(sample_hours)`. Future refreshes then just re-point the `h5` path.
2. **Turn on the constant-speed ("Naive") baseline.** `luo_main.py::eval_baseline` already
   implements it (fixed mean SOG = `L/ETA`, simulated against real time-varying weather; mirrored
   in the C++ port) and is already named in `G4_methods.md` §4.7 as the "Naive baseline" — it's
   just never wired in (`run_chain_sweep.py::_build_args` hardcodes `baseline=False`). Flip it on,
   add `baseline_fuel_mt` (and derived gap columns) to `CSV_HEADER`.
3. **New output dir**: `results/2026_08_11_chain_sweep_v2/` (v1 dir untouched, stays the fallback).

## C. Comparison redesign — SR / Luo / Naive + confidence intervals

1. **Add the Naive/constant-speed column everywhere the SR-Luo comparison currently appears**:
   `results.csv`, `analyze_chain_sweep.py`'s summary stats, the results tables in
   `drafts/06_results.md`, and the comparison figures (2-series → 3-series).
2. **Std-dev → confidence interval.** SR, Luo, and Naive all run on the *same* voyages/weather —
   paired data, not independent samples. Primary: **paired bootstrap percentile CI** (resample
   voyages with replacement, recompute the mean gap, ~10k iterations, take the 2.5/97.5
   percentiles) — no normality assumption, which matters at n≈12–20 even after the refresh.
   Report a paired t-interval alongside as a cross-check; a large divergence between the two is a
   flag to trust the bootstrap and dig into why.
3. **Figures**: CI whiskers replace std-dev error bars; add the Naive series to the SR-vs-Luo plot.

## D. Promotion criteria (v2 → new frozen evidence)

Before `G1_evidence_ledger.md` is re-pointed at v2 results and re-frozen:
- [ ] Continuity check (A.3) passes on both routes.
- [ ] `analyze_chain_sweep.py` output reviewed for both routes at the new voyage counts.
- [ ] Naive/SR/Luo gap signs and magnitudes checked against the v1 numbers on the *overlapping*
      voyages (same `sh_base` range) — should match closely; a large drift means something in the
      refresh (not just more data) changed the comparison, and that needs explaining before it
      goes in the paper.
- [ ] CI method (bootstrap vs. t-interval) reviewed once real n is known per route.
- [ ] Figures regenerated and checked.
- [ ] `G1_evidence_ledger.md` updated to cite v2 CSV paths; `00_design/README.md` "Locked inputs"
      updated to record the reopened constraint.

## Status

- [x] Design written (this file), 2026-08-11.
- [x] A.1 — server read-only check, 2026-08-11. **Results:**
  - VPN up; Shlomo1/Shlomo2/Edison all reachable.
  - **Shlomo2** (`~/Ami/pipeline/data/`, `run_all.py`, `collect_all` tmux session, alive since
    Mar 18): `experiment_b_138wp.h5` (route1) and `experiment_d_391wp.h5` (route2) both current as
    of 2026-08-11 08:0x, growing on a ~6h cycle aligned to the GFS NWP update (352 min cadence).
    `actual_weather`/`predicted_weather` tables confirmed via direct HDF5 read:
    **max `sample_hour` = 3756 on both files** (route1 min=6, route2 min=0 — matches the v1 files'
    starting points, so continuity looks good pending the formal check in A.3).
  - **Edison** (`~/Ami/pipeline/`, `collect_all` tmux session, alive since May 7): running an
    **independent, redundant collection of the same two routes** (labelled "Route 1"/"Route 2" in
    its log vs Shlomo2's `exp_b`/`exp_d`), offset ~3h in cadence, also current as of 2026-08-11.
    Not currently used by the paper's config (which points at Shlomo2-named files) — flagged as a
    possible cross-validation source, not pulled from.
  - No errors in either `collect_all.log` tail; both collectors healthy.
  - **Voyage-count math (route ETA vs new max sample_hour 3756):**

    | Route | ETA (h) | v1 voyages (sh_base list) | v2 max `sh_base` (`3756 − ETA`) | v2 voyage count | New voyages |
    |---|---:|---:|---:|---:|---:|
    | route1 (Malacca) | 280 | 7 (6…1686) | 3476 → last usable start 3366 | **13** | **+6** |
    | route2 (Atlantic) | 168 | 12 (0…1848) | 3588 → last usable start 3528 | **22** | **+10** |

    Chain total: **19 → 35 voyages** (nearly double, as estimated — now exact).
- [x] A.2 — SCP'd from Shlomo2, 2026-08-11. `data/experiment_b_138wp_v2_aug.h5` (238,347,143
      bytes) and `data/experiment_d_391wp_v2_aug.h5` (561,082,683 bytes) — byte-identical to the
      server copies. v1 files (`experiment_b_138wp.h5`, `experiment_d_391wp.h5`) untouched
      alongside them.
- [x] A.3 — continuity check, 2026-08-11. **PASS on both routes:**
  - Same start (`v1.min(sample_hour) == v2.min`): route1 both `6`, route2 both `0`.
  - v2 extends past v1 as expected: route1 `2052→3756`, route2 `2052→3756`.
  - No gaps: every consecutive `sample_hour` in v2 is exactly 6h from the last, for the entire
    range (625 steps route1, 626 steps route2) — the collector never missed a cycle.
  - Row-for-row spot check at a mid-overlap `sample_hour` (route1 @1032, route2 @1026), joined on
    `node_id`: **max |v1 − v2| = 0.0** across `wind_speed_10m_kmh`, `wind_direction_10m_deg`,
    `wave_height_m`, `ocean_current_velocity_kmh`, `ocean_current_direction_deg`. v2 is a strict,
    exact superset of v1 in the overlapping range — no re-collection drift.
- [x] B — `run_chain_sweep.py` changes, 2026-08-11 (syntax-checked, **not yet run**):
  - `ROUTES["route1"/"route2"]["h5"]` repointed at `experiment_b_138wp_v2_aug.h5` /
    `experiment_d_391wp_v2_aug.h5`; the hardcoded `sh_bases` lists removed.
  - New `_generate_sh_bases(voyage, eta)`: starts at `voyage.sample_hours[0]`, steps by `eta`,
    stops once `sh_base + eta` would exceed the last available `sample_hour` — future refreshes
    only need the `h5` path updated, not a manually maintained list.
  - `_build_args` takes a `baseline: bool` param; `run_chain` now calls `luo_main.solve()` twice
    per voyage — once normal (Luo DP), once with `baseline=True` (routes to
    `luo_main.eval_baseline`, the fixed mean-SOG "Naive" strategy already named in
    `G4_methods.md` §4.7 but never wired in before).
  - `CSV_HEADER` / row dict gained `baseline_fuel_mt`, `gap_sr_baseline_mt`/`_pct`,
    `gap_luo_baseline_mt`/`_pct`; per-voyage `baseline.csv` written alongside `sr.csv`/`luo.csv`
    (via the already-existing `write_baseline_csv`).
  - Default `--out_dir` → `results/2026_08_11_chain_sweep_v2` (v1's `results/2026_06_01_chain_sweep/`
    untouched).
  - **Not run yet** — a 1-voyage smoke test (validate wiring) and then the full 35-voyage sweep are
    separate, explicit go-aheads.
- [x] B.validate — 1-voyage smoke test (route1, `sh_base=6`), 2026-08-11. **Found and fixed a
      pre-existing, unrelated bug**: `ROUTES`' `h5`/`yaml` relative paths were one directory level
      short for the actual `scripts/dp_rebuild/`→`scripts/`→`paper_workspace/` layout (`../data`
      → `../../data`, same for `config`) — `scripts/data` never existed, so the default paths could
      never have resolved; fixed in both routes. Smoke-test result: SR 354.821 mt < Luo 361.561 mt <
      Baseline 362.638 mt (gap SR-Luo −1.86%, matches the paper's known ~1.8–2.6% range); graph size
      `152,571 nodes / 9,214,780 edges` matches `G4_methods.md` §4.6 exactly, confirming the refresh
      changed only weather values, not route/grid structure. Timing: SR build 203s + solve 9s, Luo
      410s, baseline ~0s → ~10.6 min/voyage on route1; **full 35-voyage sweep is a multi-hour run**,
      not launched yet.
- [x] C — `analyze_chain_sweep.py` rewritten, 2026-08-11 (`scipy` added — was missing, installed
      via `pip3 install --break-system-packages scipy`, needed for the t-interval's Student's-t
      critical value; no project `requirements.txt` existed to record this in). Changes:
  - `baseline_fuel_mt` and both baseline gap columns added to every table (per-route summary,
    per-voyage detail, both markdown blocks) — previously entirely absent.
  - `statistics.pstdev` replaced with a **95% paired bootstrap percentile CI** (`_bootstrap_ci`,
    10k resamples, fixed seed `20260811` for run-to-run reproducibility) as the primary interval
    for every reported quantity; the three gap columns (SR-Luo, SR-Baseline, Luo-Baseline, mt and
    %) additionally get a **paired t-interval** printed alongside for cross-check
    (`_gap_line`/`_t_interval`), per the design's "report both, large divergence is a flag" rule.
  - Validated against a synthetic 13-row CSV (not real data — the real sweep hasn't run): bootstrap
    and t-interval track closely on the noisier comparisons and the CI correctly crosses zero for
    the near-zero Luo-Baseline gap rather than overstating certainty — the machinery is sound.
  - `DEFAULT_RESULTS` fixed to match `run_chain_sweep.py`'s new default (`results/2026_08_11_chain_sweep_v2/results.csv`) — it had the same latent `runs/` vs `results/` path bug as A.2 found in B.
- [x] B.robustness — incremental writes, 2026-08-11. `run_chain_sweep.py::main()` previously
      accumulated all rows in memory and wrote `results.csv` once at the very end of the whole
      run; a crash on voyage 30/35 would have lost everything. Restructured so the CSV is opened
      and header-written once up front, and each voyage's row is written + flushed immediately
      after that voyage completes (`run_chain` now takes the open `csv_writer`/file handle and
      returns a count, not a list). Regression-tested: re-ran the 1-voyage route1 smoke test,
      correct single-row CSV produced.
- [x] **E — C++ execution path (new, added 2026-08-11).** The Python sweep's ~4.5–5h estimate for
      35 voyages prompted checking whether `scripts/dp_cpp/` (previously only built for the RH
      chain) could run Mode C too.
  - **Mode C (`--sample_hour`) is already implemented** in the actual C++ source
    (`SR_main.cpp`/`luo_main.cpp`) — ahead of `MODE_C_PORT_SPEC.md`, which describes a plan that
    was already superseded by real commits (`752ae0b Add time-varying weather to dp_luo and
    dp_SR`, and later "Streaming refactor Phase 4"). The spec doc is stale; the source isn't.
  - `paper_workspace/scripts/dp_cpp/src` is a **June-8 snapshot**, missing later `pipeline/dp_cpp`
    changes (`streaming.cpp/hpp`, further `SR_main`/`atomic_edges` edits from the Aug-7 streaming
    refactor). Deliberately **built from the paper_workspace snapshot, not the newer
    `pipeline/dp_cpp/build/` binaries** — keeps this v2 evidence base on the exact solver version
    this workspace already has regression tests and reference numbers for, rather than silently
    picking up unrelated later changes.
  - Built clean (`cmake -B build -DCMAKE_BUILD_TYPE=Release && cmake --build build -j` inside
    `scripts/dp_cpp/`; only compiler warnings, no errors) — deps (cmake, hdf5, yaml-cpp) already
    present.
  - **Parity check** at route1 `sh_base=6` against the already-recorded Python numbers — same
    voyage, same v2 data:

    | | Python | C++ | diff | wall time (Python → C++) |
    |---|---:|---:|---:|---|
    | SR | 354.821 mt | 354.914 mt | 0.093 mt (0.026%) | 212s → 24.5s (8.6×) |
    | Luo | 361.561 mt | 361.671 mt | 0.110 mt (0.030%) | 410s → 33.7s (12.2×) |
    | Baseline | 362.638 mt | 362.743 mt | 0.105 mt (0.029%) | ~0s → 10.7s |

    Node/edge counts identical (152,571 / 9,214,780) — confirms same graph, same route/grid
    logic, differences are FP-ordering-scale only, well within the ±0.05% the port spec's own
    validation section treated as acceptable.
  - **New script**: `scripts/dp_cpp/run_chain_sweep_cpp.py` — C++ counterpart of
    `run_chain_sweep.py`. Same `ROUTES` (v2 h5 files), same dynamic `_generate_sh_bases` rule (via
    direct `h5py` read, no Python solver import needed), **same `CSV_HEADER`/row schema** so
    `analyze_chain_sweep.py` reads either file unchanged (verified — ran it against the C++
    smoke-test output with no errors), and **incremental writes built in from the start**. Drives
    `dp_SR`/`dp_luo`/`dp_luo --baseline` via `subprocess`, parses `stdout` with regexes anchored
    to the binaries' summary-block format.
  - Smoke-tested end-to-end (route1, 1 voyage): matched the manual parity-check numbers exactly,
    **1.2 min total** (vs Python's 10.6 min for the same voyage — 8.8×).
  - **Known gap vs the Python path**: no `--csv` flag passed, so per-voyage per-arc CSVs
    (`sr.csv`/`luo.csv`/`baseline.csv`) are not written by the C++ path — only the aggregate
    `results.csv`. Fine for the headline numbers/CI; would need adding if per-arc figures are
    wanted from the C++ run specifically.
  - **Revised full-sweep estimate**: ~35–45 minutes for all 35 voyages (both routes), down from
    ~4.5–5 hours — route2's smaller graph (4.3M vs 9.2M edges per `G4_methods.md` §4.6) should
    make its per-voyage time lower than route1's, not yet measured directly.
- [~] D — promotion / re-freeze. **Full 35-voyage v2 sweep launched 2026-08-11** via
      `run_chain_sweep_cpp.py --routes route1,route2` (background), writing to
      `results/2026_08_11_chain_sweep_v2_cpp/results.csv` incrementally. Not complete yet —
      remaining once it finishes: sanity-check the real output, re-run
      `analyze_chain_sweep.py` on it, work through the promotion checklist above (§D).

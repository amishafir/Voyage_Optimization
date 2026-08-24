# Meeting Prep — Monday 2026-08-24 (Ami ↔ Tal)

Continues from [meeting_prep_2026_08_17.md](meeting_prep_2026_08_17.md).

Every carryover below was re-checked against `paper_workspace/paper_full_draft.tex` and the
pipeline code as of today — not copied forward blindly. Tal's `5fa8e3b` ("Reintroduce V_min, allow
idling at the route ends, rename L to D") landed the evening of Aug 17 and closed a large block of
the Aug-17 list; Section 0 records what it closed so we don't re-litigate it. Line numbers are
current.

> **Note:** Sections 5 and 6 of the Aug-17 prep were never filled in — no decisions or actions were
> recorded during that session. Worth capturing them live this time.

---

## 0. Closed by Tal's `5fa8e3b` — verified, do not re-open

- **`v_min` reintroduced.** `\mathcal{V}(d)` is now the three-way set at **line 255**: zero joins the
  band at the origin, the floor `V_min > 0` holds in the interior, and zero is the only admissible
  speed at the destination. This closes the entire Aug-17 `v_min` block, including the old
  `$\mathcal{V}=[0,v_{max}]$` sites — line 252 became line 255, and Algorithm 1's input line now
  reads `band $[V_{\min},V_{\max}]$` (**line 679**).
- **Waiting convention settled** — `\phi(t,d;0)=0`, "a wait at `$d=0$` or at `$d=D$` costs time but no
  fuel" (**line 425**), and `\mathcal{V}(D)=\{0\}` (**line 503**). This resolves **2A**'s waiting vote:
  variant (a)'s free pricing, with variant (c)'s endpoint-only restriction, plus the origin-adjacent
  ban we asked for.
- **Figure caption rewritten** (**lines 515–525**) with the real block provenance, both grids anchored
  at the voyage start, the cone spanning the `V_min`/`V_max` rays, and the explicit note that
  "with `$V_{\min}>0$` it has no vertical edge". It also separates figure-only `δ=5` NM, `τ=1` h,
  `[3,16]` kn from the experiments' `δ=1` NM, `τ=0.1` h. This closes three Aug-17 items at once:
  the `[0,15.119]` caption text, the "vertical edge is the `$\bar v=0$` wait leg" line, and the
  7-nodes-per-axis discretization request.
- **The one real code change we flagged is done.** `paper_workspace/figures/plot_state_neighbours_pair.py`
  now has `vmin_kn` (line 104) and `boundary_layer` (line 117), and the feasibility check tests both
  bounds (lines 313, 328, 358–360). Aug-17 called this "the one figure/script that would need an
  actual code change" — Tal made it.
- **Broken route fragment fixed.** Line 342 now reads cleanly ("chosen to contrast weather regimes:
  the Indian Ocean route (Persian Gulf …"), resolved by the Aug-16 route rename `6e825b4`.
- **Candidate-search bounding idea was already implemented.** `neighbour_candidates()` in
  `pipeline/dp_rebuild/atomic_edges.py:117–145` already derives `t_fast`/`t_slow` from `v_max`/`v_min`
  and `d_slow`/`d_fast` likewise, then loops only between those bounds. Closing as pre-existing —
  see 1H for the stale comment it left behind.

---

## 1. New items for this session

### 1A. Unresolved cross-reference in the new §4.1 prose — **line 528**

"…it steams inside a given rectunglar area of the time--distance space demonstrated in **Figure X**."
A literal `Figure X` placeholder in Tal's new paragraph. Should almost certainly be
`Figure~\ref{fig:state-neighbours}`. Confirm the intended target — this is the kind of thing that
survives to submission because LaTeX never complains about it.

### 1B. Typos — **fixed today**, no discussion needed

All nine Aug-17 typos plus a further sweep of the live prose. `paper_full_draft.tex` rebuilds clean
(27 pages, no undefined references). Fixed:

- **Aug-17 list** (lines 751–756): `algoritm`, `This is s shorter`, `volotile`, `depicte`, `tseted`,
  `depature`, `appart`, `teseted`, `corrosponding`, plus "sea conditions **changes** over time".
- **§3.1 intro (line 242)**: `controling`, `minimizing **it** total`, `utlizing`, `determinstic`,
  "the problem **were** the sea conditions" → where, `planed` → planned, "conditions … **is** known"
  → are known, `extened`, `stocastic`, `consuption`, `asspect`, `berifely`.
- **Definitions list (lines 246–252)**: `refred`, `seleceted`, `direciton`, `Beufor` → Beaufort,
  "conditions **changes continuesly**" → change continuously, "are **assume** fixed" → assumed,
  `discterized`, "because it **used** by" → is used by.
- **FCR item (line 248)**: `vessle`, "algorithm **obtain**" → obtains, "**a** increasing" → an,
  and the broken "fixed at of the route segments" → "fixed at that of the route segment".
- **§4.1 prose (line 528)**: "vessel is **streaming**" → steaming, `rectunglar` ×2.
- **§4.2 walkthrough (lines 660–685)**: `aglrithm`, `peformed`, "actual **journeyis** then
  **preformed**" → journey is then performed, `lexicograpgically`.
- **§3.2 (line 307)**: `planed voyage` → planned voyage.

Left alone deliberately: typos inside `\begin{comment}` blocks and `%`-prefixed lines, since those
are Tal's superseded text. Also `xxxx\=\kill` at line 678 — that is legitimate `tabbing` syntax,
not a placeholder.

### 1C. Correction: the `L → D` rename is **complete** — the Aug-17-style worry was mine, and wrong

I previously flagged four surviving `L` sites (317, 343, 344, 801). All four are inside
`\begin{comment}` blocks — L313–403 and L799–804 — which is precisely the "commented-out superseded
blocks keep the old symbol" that `5fa8e3b` describes. The live text uses `D` throughout; a sweep for
bare `L` in live, non-`%` lines returns **zero** hits outside `L_pp`. Nothing to do here.

Comment-environment ranges, for future greps: **313–403, 582–588, 591–601, 603–624, 627–647,
799–804**. Any audit of this file has to exclude them or it will keep producing false positives.

### 1D. Voyage count — **resolved today**, it is a text problem not a data one

The canonical number is **35 = 13 (Indian Ocean) + 22 (North Atlantic)**, verified against the
committed sweep output `paper_workspace/results/2026_08_11_chain_sweep_v2_cpp/results.csv`:
35 rows, route1 = 13, route2 = 22, one ETA per route (280 h / 168 h).

So the other numbers in the draft are stale prose, not disagreement about the data:

- **19 voyages** — lines 67, 1055, 1111, 1139. This is the **v1** chain, superseded by the Aug-11
  refresh. Four sentences to edit.
- **150 problem instances** — line 756. A different quantity entirely (2 routes x 25 departures x
  3 ETA levels), not a voyage count. Needs one sentence saying how the 35-voyage chain relates to
  the 150-instance benchmark, or the two will keep reading as a contradiction.
- Aug-17's **2B** note of "34 (13+21)" was simply a miscount; route2 is 22.

### 1E. `NM` used as a speed unit — **line 756**

"an average sailing speed of 10, 12, and 14 **NM**" → knots (or `NM h^{-1}`). Carried from Aug-17,
still unfixed — left out of today's typo pass on purpose, since it is a units error rather than a
spelling one, though the fix is a single word.

### 1F. The FCR formula in §3.2 is still opaque

Eq.~`\eqref{eq:legfuel}` at **lines 290–291** is unchanged:
`$F_i = \fcr(g^{-1}(V_{g,i};w_i))\,d_i/V_{g,i}$`. The reader must chain `g^{-1}` (§3.1), the cubic
`$\fcr(V_s)=a V_s^3$` (line 286, with `a` deferred to Appendix~`\ref{app:fcr}`, where the calibrated
`0.000706` appears at line 378), and the leg time `$d_i/V_{g,i}$` — with no intermediate form. Still
needs an expanded step or a short walkthrough.

### 1G. Four overfull hboxes

At lines **143–149**, **701–702**, **771–793**, **881–889**. Cosmetic, but cheap to clear before the
TR-C pass.

### 1H. Code comments now stale, since `V_min > 0` landed

- `pipeline/dp_rebuild/atomic_edges.py` (~line 127) — "v_min = 0 (band `[0, v_max]`): the slow side of
  the window is open". The code is correct (it guards `vmin > eps`), but the comment now describes a
  convention the paper has abandoned.
- `pipeline/dp_rebuild/lb_bound.py:32` — "do not assume v_min = 0 — **that band change is pending**".
  No longer pending; Tal landed it.

### 1I. Housekeeping: six label pairs duplicated across live and commented blocks

`sec:sog` (L267 live / L349 commented), `eq:sog` (273/363), `eq:legfuel` (290/386), `eq:obj` (296/396),
`tab:ship` (1205 live / 326 commented), `eq:fcr` (1265 live / 377 commented). Harmless today — exactly
one of each pair is live and LaTeX raises no warning — but re-enabling any superseded block collides
the label. Worth renaming the commented copies while we remember why they exist.

### 1J. "Text Studio" Overleaf/LaTeX add-on — evaluate

Carried from Aug-17, untouched. Partly overtaken by the local build below; the question is now
narrower: does it offer anything the local toolchain doesn't?

### 1K. Tooling: the paper now builds locally

TinyTeX at `~/Library/TinyTeX` plus LaTeX Workshop in Cursor, configured via `.vscode/settings.json`
(gitignored, local only). `latexmk` → `paper_workspace/build/paper_full_draft.pdf`, **27 pages**, no
undefined references or citations, bibliography resolved, both figures embedded. No Overleaf upload
in the loop. Auto-builds on save, `cmd-click` jumps between source and PDF.

### 1L. Code vs paper: Eq. (1)'s three-way `V(d)` is not implemented in either language

Verified by reading and by running the builder. **The results are unaffected** --- with a convex
increasing FCR and a binding ETA, idling is never optimal, which is exactly what line 807 asserts
empirically. But the code cannot express the model as written, which is a defensibility problem if a
referee asks.

- **Waiting arcs are global, not endpoint-only.** `--wait_arcs` defaults to `off`
  (`SR_main.py:105`), so nothing idles anywhere --- including at `d=0`, where the paper now allows a
  postponed departure. Switch it on and `atomic_edges.py:145-149` emits the wait candidate at
  *every* state with a time wall ahead; its own comment says "emitted unconditionally". Demonstrated
  on the real band `[9.12, 15.12]`:

  | Source state | `wait_arcs=off` | `wait_arcs=on` |
  |---|---|---|
  | interior, `d=1500` | no wait leg | wait leg `(102.0, 1500.0)` **(paper forbids)** |
  | origin, `d=0` | no wait leg **(paper allows)** | wait leg `(6.0, 0.0)` |
  | near destination, `d=3390` | no wait leg | wait leg `(276.0, 3390.0)` |

  Default is too restrictive, enabled is too permissive. Eq. (1) wants the opposite pairing.
- **`V(d)` has no `d` dependence at all**: `vmin, vmax = frame.cfg.v_min, frame.cfg.v_max`, one
  global band. `V(D) = {0}` has no counterpart.
- The destination convention *does* work, implicitly: `bellman.py:171-180` takes
  `argmin{cost : t <= ETA}`, so arriving early costs nothing more --- which is `phi(t,D;0)=0` without
  needing an arc.

### 1M. Luo's comparison band is already decided in code --- 2A lists it as open

`luo_main.py:480-481` and `luo_main.cpp:331-332` give Luo the **same** `mean_sog +/- 3` band as SR,
not the 8-18 kn of the original paper. Section 5's comparison claims rest on this. Either ratify it
and say so in the text, or change the code --- but it is not an open question in the implementation.

### 1N. What *is* aligned (so we do not re-litigate it)

| Paper | Python | C++ |
|---|---|---|
| `V_min` floor in the interior | `atomic_edges.py:117-145` | `atomic_edges.cpp:88-127` |
| `V_min = D/T-3`, `V_max = D/T+3` | `SR_main.py:159-161`, `luo_main.py:479-481` | `SR_main.cpp:95-97`, `luo_main.cpp:330-332` |
| Grids anchored at voyage start | `k*tau` / `k*zeta` absolute | same |
| `delta=1` NM, `tau=0.1` h | `frame.py:163-164` | mirrored |

Four-way parity on the band. Also: **the streaming C++ mirror is done** (`streaming.cpp/hpp`,
selected at `SR_main.cpp:104-119` for node-first) --- that Aug-17 carryover can be closed.

### 1O. Rerun environment --- was broken, now works

Nothing here was runnable this morning. Fixed today:

- **C++**: `cmake`, `hdf5`, `yaml-cpp` were all missing. Installed; **builds clean** ---
  `dp_SR`, `dp_luo`, `dp_run_rh`.
- **Python**: no venv existed and no dependencies were installed. `venv/` now on **3.12.14**, all
  13 DP modules import.
- Three repo-level problems worth fixing regardless:
  - `tables` in `pipeline/requirements.txt` is **imported nowhere and cannot build** on 3.9 --- and
    since pip is atomic, it was silently failing the *entire* install. Delete the line.
  - The code **requires Python >= 3.10** (`weather.py:104` uses `Path | str` with no `__future__`
    import) but nothing declares it. Add `python_requires` or a README line.
  - `requirements.txt` is **unpinned**. Today's resolve gave numpy 2.5.2 / pandas 3.0.5 --- almost
    certainly newer than what produced the current tables, and pandas 3.0 has breaking changes. If
    the reruns are meant to be comparable to the existing numbers, pin first. **This decides whether
    "rerun" reproduces or replaces.**

### 1P. Where the draft actually stops --- pick up at Section 4.2, lines 582-660

Tal's `5fa8e3b` touched Section 3.2 (252-300), 4.1 (410-540), 4.2 (664-694), and ended in
Section 5.2.1 (807-832). The **frontier is Section 4.2**:

- **Four commented-out blocks** at 582-588, 591-601, 603-624, 627-647 --- ~66 lines of superseded
  text parked inside "Solving the Bellman equation". That is where the pen was last down.
- **Live text at 650-660 is first-draft rough** ("The first loop, discovers the reachable...",
  "calculate the *value* of every state").
- **`Figure X` at line 528** (see 1A) --- the one hard unfinished marker.
- **Section 4.3 does not exist.** Section 4 has only *State space* (430) and *Solving the Bellman
  equation* (569). So "rewrite Section 4.3 around the two-sided discretization story" is a **write
  from scratch** --- the lower-bound / kappa material has no home in the draft.

His last edit of all (line 832) was cosmetic --- Naive's mean SOG `$L/T$` -> `$D/T$`. The
substantive one just before it (line 807) pinned the band numerically **and** added the sentence
that the zero-speed option "was never exercised: no optimal plan chose to idle". That sentence is
load-bearing --- it is what keeps the endpoint-waiting convention from invalidating the existing
tables --- and per **1L** it is true for a stronger reason than it states. Agree the wording.

---

## 2. Decisions still open

### 2A. Speed-band residue — the waiting half is settled, this half is not

- [ ] **`v_max` may already be settled in the text — ratify or change it.** Line 807 (live) states the
      band explicitly: "the speed at each decision is drawn from a common band spanning the mean voyage
      speed `$D/T \pm 3$` kn, that is `$V_{\min}=D/T-3$` and `$V_{\max}=D/T+3$`". So the paper has
      committed to **mean voyage speed ± 3 kn**, which decides `v_min` as well. Two consequences to
      check: (i) this is what the figure caption defers to as "the band of Section~\ref{sec:data}";
      (ii) it matches the `mean_sog - 3.0` fallback in `SR_main.py` / `luo_main.py` (≈9.1 kn on the
      Indian Ocean route: `3393/280 = 12.12`, so `[9.12, 15.12]`), **not** the `min_speed = 8.0`
      dataclass default. Confirm 8.0 is only an unused default and never produced a results table.
- [ ] Line 807 also asserts the zero-speed option "was never exercised: no optimal plan chose to idle",
      because the arrival constraint bound in every run. Worth confirming that claim holds for the
      rerun set too, since it is the empirical justification for the endpoint-only waiting convention.
- [ ] **Luo's comparison band**: retain its original 8–18 kn, or align it with `[V_min, V_max]`?
- [ ] **Approve the ETA-feasibility arc cut** before the full rerun. The open band produced roughly
      **14× more arcs and 13× runtime** in the quick test.
- [ ] **Confirm which `v_min` the current results tables were actually generated with.** Production
      defaults are still `8.0` (`pipeline/dp_rebuild/common.py:33`, `pipeline/dp_cpp/src/common.hpp:27`),
      and `SR_main.py` / `luo_main.py` fall back to `mean_sog - 3.0` when `--min_speed` is absent
      (≈8.6–9.1 kn). So the code was likely never running the `[0, v_max]` the paper used to describe —
      but the tables need confirming, not assuming.

### 2B. Data — **pulled and verified today.** The question is now 35 vs 38

The download is done, so this is no longer "should we pull?". On this machine, in
`paper_workspace/data/`, as dated v3 copies (no overwrites):

| File | Bytes | sha256 vs Shlomo2 |
|---|---:|---|
| `experiment_b_138wp_v3_aug24.h5` | 260,183,238 | match |
| `experiment_d_391wp_v3_aug24.h5` | 609,807,792 | match |

Continuity check passed cleanly: both routes step in exact 6 h increments with **no gaps**
(`min step = max step = 6`, 679 / 680 distinct sample hours), start hours match v1 and v2
(route1 `6`, route2 `0`), and the **entire v2 range (<= 3756) is present**. v3 is a strict superset
of v2, so this one dataset both reproduces the current tables and extends them.

`max sample_hour` moved **3756 -> 4074** since Aug 11 (the `collect_all` session has been running
since Mar 18 and the files were modified minutes before the pull).

- [ ] **The decision: freeze at 35, or rewrite Section 5 for 38?**

  | Route | ETA | Aug-11 (3756) | Now (4074) | Last usable `sh_base` |
  |---|---:|---:|---:|---:|
  | route1 | 280 | 13 | **14** | 3646 |
  | route2 | 168 | 22 | **24** | 3864 |
  | | | **35** | **38** | |

  Capping the `sh_base` list at the v2 range reproduces the current 35-voyage numbers exactly;
  letting it run gives 38 and moves every Section 5 figure.
- [ ] **Either way, `run_chain_sweep.py` needs repointing.** `ROUTES[...]["h5"]` still names
      `experiment_b_138wp_v2_aug.h5` / `experiment_d_391wp_v2_aug.h5`, which **do not exist on this
      machine** (they were pulled to the Windows box on Aug 11). And `_generate_sh_bases()` derives
      the list from the data, so it will silently produce **38** unless capped. One line either way,
      but it decides whether the numbers move.
- [ ] Regenerate the goldens after whichever choice lands.
- [ ] Optional cross-validation, free: **Edison** runs an independent redundant collection of the
      same two routes, offset ~3 h, healthy. Never pulled from. Useful answer if a referee asks about
      collection reliability. (Key access not yet set up there --- Shlomo2 only.)

### 2C. Bellman / state-space items to verify against Tal's changes

- [ ] Confirm Eq. (6) is the forward/to-arrive formulation matching Algorithm 1.
- [ ] Re-audit the Eq. (5) and state-space definitions Tal rewrote: on-boundary cell maps, the
      now-absolute (voyage-start-anchored) `δ`-grid, argmin notation, "drawn from the grid" wording.
- [ ] **Verify the node set the new equations actually generate.** `Eq.~\eqref{eq:neighbors}` (lines
      487–488) is what `neighbour_candidates()` implements; Tal changed both the anchoring and the
      membership tests (`t' <= t_T(t)`, `d' <= d_D(d)`), so the graph may now build different nodes.
      Check the code output, not just the paper text.
- [ ] Close the remaining Tal-zone notation and prose audit before the next paper-wide pass.

---

## 3. Work to start after the decisions

- [ ] Rewrite the **line 807** band statement (and whatever `sec:data` reports) if `v_max` changes from
      the `$D/T \pm 3$` already written there. Line 801 is the commented predecessor — leave it.
- [ ] Implement the ETA-feasibility arc cut in Python, then mirror it in C++.
- [ ] Finish the streaming-refactor carryovers: C++ mirror and remaining cleanup.
- [ ] Run the full experiment suite under the approved band.
- [ ] Re-measure κ, state/arc counts, runtime, and the Tractability numbers.
- [ ] Rewrite §4.3 around the two-sided discretization story once the lower-bound strategy is final.
- [ ] Update §5–§7 tables, results, and discussion from the approved rerun set.

*(Dropped from the Aug-17 version of this section: the Eq. (5) waiting candidate, the `φ(d,t;0)`
convention statement, and the matching §4.2/caption edits — all landed in `5fa8e3b`.)*

---

## 4. Remaining paper and documentation work

- [ ] Add the remaining figures: forecast error, savings vs departure, fused-voyage placement.
- [ ] Add the one-sentence §5 note that Luo's lattice is also node-first.
- [ ] Update `docs/state_space_evolution.html` with Tal's forward algorithm and flat §4.2.
- [ ] Refresh stale statuses in `docs/audit_explained.html`.
- [ ] Run the internal paper-reviewer / paper-critic pass.
- [ ] Prepare the manuscript for TR-C submission after the internal review closes.

---

## 5. Suggested order --- highest leverage first

1. **35 or 38 voyages** (2B). Data is pulled and verified; this is a one-line config choice that
   either freezes Section 5 or moves every number in it. Everything downstream waits on it.
2. **Ratify `v_max`** (2A). Line 807 already commits the paper to `D/T +/- 3`, so this is
   confirmation, not design --- and it settles `V_min` too.
3. **Luo's band** (1M). Already aligned in code; the text has to match one way or the other.
4. **Pin dependencies or not** (1O). Decides whether a rerun reproduces or replaces.
5. **Section 4.2 / Section 4.3** (1P). Where Tal picks the draft back up, and whether 4.3 gets written.
6. Quick text fixes, no discussion needed: `Figure X` (1A), the 19-voyage sentences (1D), `NM` as a
   speed unit (1E).

---

## 6. Decisions made during the session

| Decision | Owner | Outcome | Follow-up |
|---|---|---|---|
| 35 vs 38 voyages (2B) | | | |
| `v_max = D/T + 3` ratified? (2A) | | | |
| Luo band: align or restore 8-18 kn (1M) | | | |
| Pin `requirements.txt`? (1O) | | | |
| Implement Eq. (1) endpoint waiting in code? (1L) | | | |
| ETA-feasibility arc cut approved? (2A) | | | |
| Write Section 4.3, or fold it elsewhere? (1P) | | | |
| `Figure X` target at line 528 (1A) | | | |
| | | | |

## 7. Actions assigned during the session

| Action | Owner | Due/status |
|---|---|---|
| Justify (or cite) the fixed-average-speed baseline — see note 1 in §8 | | open |
| Strip all `---` em-dashes from the paper — see note 2 in §8 (70 instances) | | open |
| Reconcile the 0.5° cell justification against the actual source resolutions — note 3 in §8 | | open |
| Decide whether route2's 0.08° sampling should survive into the model — note 4 in §8 | | open |
| Resolve the now three-way resolution contradiction after `5f38cba` — note 5 in §8 | | open |
| Add `--grid_deg` CLI flag + route2 sensitivity sweep at 0.25° — note 6 in §8 | | open |
| **Re-collect route1 weather at ~5-10 NM** — note 6, the bigger finding | | open |
| | | |

## 8. Running notes

_Live log --- append as we go._

### Note 1 — why compare against a fixed average speed? (raised in session)

**Question:** what is the reason for comparing against a fixed average speed (`D/T`)? We need a
reference for it, or failing that an explicit explanation in the text.

**Current state of the draft: unsupported.** The baseline is defined at lines 831–833 —

> \textbf{Fixed-speed (Naive).} The operational reference is a set-and-forget policy that sails a
> single fixed mean SOG ($D/T$) through the actual time-varying weather, with no optimisation and no
> re-planning.

— three sentences, **no citation**, and no statement of why that is the right reference policy. It is
then used as a comparator throughout §6: lines 870, 877 (table caption), 883, 905, 938.

**The argument is already in our own paper, just not connected to the baseline.** Line 153 says, with
`\citep{Hvattum2013}`, that convexity of fuel in speed implies **a constant speed is fuel-optimal
under uniform conditions**. That is exactly the justification: the fixed mean SOG is not an arbitrary
straw man, it is *the provable optimum in the absence of weather variation*. So any saving over it is
attributable to weather variation alone — which is precisely the claim §6 wants to make. Lines 52–53
and 96 already make this argument in the abstract and intro; it just never gets restated where the
baseline is defined.

**Cheapest fix:** one or two sentences at line 831 tying the baseline back to `Hvattum2013`, framing
it as the uniform-conditions optimum rather than as naive practice. No new literature needed.

**Candidate citations already in `refs.bib`** if we want external support for it as *practice* rather
than as theory:

| Key | Why it might serve |
|---|---|
| `Hvattum2013` | Constant speed provably optimal under uniform conditions — the theoretical anchor. Already cited at line 153. |
| `Psaraftis2013` | "Speed models for energy-efficient maritime transportation: a taxonomy and survey" — most likely place to source constant speed as *the* canonical baseline formulation in the literature. |
| `Cariou2011` | Slow steaming — fixed reduced speed as documented industry practice. |
| `Jia2017` | Virtual Arrival — directly about the rush-then-wait behaviour a fixed-speed policy avoids. |
| `Taskar2020` | Benefit of speed reduction *in different weather conditions* — bridges fixed speed and weather variation. |

**Note:** the name "Naive" arguably works against us. If the policy is the uniform-conditions
optimum, calling it naive invites a referee to ask why we benchmark against something we have
labelled unsophisticated. "Fixed-speed reference" or "constant-speed optimum" would be more
defensible. Worth deciding alongside the citation.


### Note 2 — remove all `---` em-dashes (raised in session)

**Request:** strip the `---` (em-dash) constructions that an LLM habitually inserts.

**Scope: 70 occurrences across 59 lines** of live text. A further 16 sit inside `\begin{comment}`
blocks and `%` lines and should be left alone. Legitimate en-dashes (`lines~6--7`,
`time--distance`, `$V_{\min}=D/T-3$`) are a different token and must not be touched — this is `---`
only, not `--`.

Distribution is paper-wide, heaviest in the intro and related work: lines 52–234 hold 28 of them,
§5–§6 another 20, the discussion 15, the appendix 2.

**Not a find-and-replace.** Deleting the dashes leaves broken prose, because they appear in two
distinct constructions needing different repairs:

| Pattern | Example | Repair |
|---|---|---|
| Paired (parenthetical) | L86 `rises steeply --- roughly with the cube of speed --- even modest…` | `, roughly with the cube of speed,` or parentheses |
| Single (appositive / clarifier) | L52 `convexity of fuel consumption in speed --- which makes a constant speed optimal…` | comma, colon, or split into a new sentence |
| Triple in one sentence | L737 has **3** | needs restructuring, not substitution |

**Worth knowing before the sweep:** not all 70 are LLM-authored. Lines **807–809** are Tal's own
Aug-17 addition (`5fa8e3b`), and 826–827, 1091 and others sit in his text too. A blanket sweep will
rewrite his sentences as well as ours. Either that is fine and we say so, or we scope the sweep to
the sections we drafted.

**Proposed approach:** one pass, per-instance judgement, no wording changes beyond what the
punctuation repair requires; then rebuild and diff so every touched sentence can be reviewed. Held
pending a go-ahead, since it edits prose paper-wide including a co-author's.


### Note 3 — the `0.08°` resolution, and whether it matches our setting (raised in session)

**Answer: `0.08°` is not our setting, and it is 6.25x finer than ours.** It is the native resolution
of one *source* model, not of our discretization.

**Both sides of this live under the same heading, which is why it slipped through.** The two homes to
reconcile are:

- **§3, line 247** — the definitions item `\item [Sea conditions]`, which states our modelling
  choice: 6 h blocks and `0.5° x 0.5°` cells, with the justification sentence.
- **§5.1.1, line 718** — `\subsubsection{Sea conditions data}`, which describes the actual sources
  and their resolutions.

The first says the grid was chosen to match the services; the second shows the services are finer.
Any fix has to touch both, or the reader hits the same contradiction from the other direction.

Line 732, in the §5.1.1 list, gives one product per environmental driver:

| Driver | Model | Native resolution | Re-initialised |
|---|---|---|---|
| Wind (10 m speed/direction) | NOAA GFS | **0.25°** | every 6 h (00/06/12/18 UTC) |
| Waves (significant height) | Météo-France MFWAM | **0.25°** | twice daily |
| Ocean currents (velocity/direction) | Météo-France SMOC | **0.08°** | once daily |

Our model discretizes space to **0.5° x 0.5°** cells, asserted in three places: line 247 (the
Sea conditions definition), line 114 ("each 0.5° weather-cell crossing"), and line 422 (subsegments
start at each 0.5° latitude/longitude crossing). Whatever we settle on has to hold in all three.

**The problem this exposes.** Line 247 justifies the 0.5° choice with:

> "This discretization level was chosen because it is used by global weather and forecast services."

That claim is contradicted by our own data section two pages later. **None** of the three sources
runs at 0.5°: two are at 0.25° and one at 0.08°. All three are *finer* than our cells, so the
sentence as written is false and a referee reading §5.1.1 will see it immediately.

**What the real justification probably is** — worth deciding which, then saying it plainly:

1. **Aggregation for tractability.** 0.5° keeps the subsegment count (and therefore the state/arc
   count) manageable; the finer native grids would multiply M. This is honest and defensible, and it
   connects to the tractability story in §4.
2. **The coarsest common denominator.** Wind and waves at 0.25° do not divide evenly into a common
   grid with currents at 0.08°; 0.5° is a clean multiple of 0.25° and simple to align.
3. **It matches the API's delivery grid**, as distinct from the models' native grids — Open-Meteo may
   serve on a coarser grid than MFWAM/SMOC compute on. **If this is the reason, it is checkable and
   should be stated as "the resolution at which the data were retrieved", not "used by the services".**

**Follow-on question worth asking:** currents at 0.08° means we are averaging roughly 39 native cells
into each of ours (0.5/0.08 = 6.25 per side). Since ocean currents drive the SOG/SWS gap that the
whole method exploits, it is fair to ask whether that averaging costs us signal — and whether it is
worth a sensitivity check at 0.25°. That is a defensible limitation to state in §7 either way.


### Note 4 — there are three grids, not two, and the tight one is being averaged away

Checked against the downloaded v3 files and the code. There are **three** distinct grids, and the
bridging rule between them is explicit in the code.

**Grid 1 — the NWP source models** (§5.1.1): wind and waves at `0.25°`, ocean currents at `0.08°`.

**Grid 2 — our waypoint sampling**, and the two routes are *not* sampled alike:

| Route | file | distinct `node_id` | length | spacing |
|---|---|---:|---:|---|
| route1 / Indian Ocean | `experiment_b_138wp` | **131** | 3393 NM | **26.1 NM ≈ 0.435°** |
| route2 / North Atlantic | `experiment_d_391wp` | **389** | 1955 NM | **5.04 NM ≈ 0.084°** |

Route2's spacing is essentially exactly the SMOC ocean-current native resolution (`0.08°`). That
looks deliberate, not accidental. Route1's is essentially our own cell size.

**Grid 3 — the model's `0.5° x 0.5°` cells** (`geo_grid.py:129,216`, axis-aligned at integer
multiples of 0.5°), which is what §3 line 247 and §4 line 422 describe.

**How we work between them — the rule already exists.** `build_edges.py:140-147`: weather is resolved
by **per-cell mean aggregation**. The point maps to a `(lat, lon)` on the rhumb-line polyline, the
0.5° bin is taken, and the canonical value is the **mean over every waypoint in that cell**
(NaN-tolerant, circular for directions). This makes weather *cell-canonical* — every `(t,d)` inside
one cell sees the same value — and was chosen specifically to remove the boundary-tie ambiguity of
nearest-waypoint lookup. The node-first path uses the same resolver: `frame.cell_weather_at(src_d,
sample_hour, fh)` at `atomic_edges.py:294`.

**So the tight grid is real, and it is being averaged away — unevenly between routes.** Cell width
depends on latitude, which makes the asymmetry worse:

| Route | lat span | 0.5° longitude | waypoint spacing | waypoints averaged per cell |
|---|---|---:|---:|---:|
| route1 (Persian Gulf–Malacca) | 1.8–26.6° | 29.1 NM | 26.1 NM | **~1** |
| route2 (St John's–Liverpool) | 47.6–55.8° | **18.6 NM** | 5.04 NM | **~4** |

Route1 is effectively 1:1 — one waypoint per cell, no averaging. Route2 collapses about four
waypoints into a single cell value, so roughly 75% of the resolution we paid to collect never reaches
the optimiser. And because currents are the driver the whole method exploits, that is precisely the
signal being smoothed.

**Questions this raises for the paper:**

- [ ] Is the route1/route2 sampling difference intentional and documented? Right now §5.1.1 describes
      the sources but never states our own waypoint spacing, so a reader cannot tell the two routes
      were sampled 5x apart.
- [ ] Does the cross-route comparison in §6 need a caveat? We compare SR-vs-Luo-vs-fixed-speed gaps
      *between* routes while the underlying weather sampling differs by 5x.
- [ ] Is a sensitivity run worth it — route2 at a finer cell (0.25°) — to show the averaging is not
      costing us savings? This is the cheap version of the referee question "why 0.5°?" (see note 3).
- [ ] If 0.5° is kept for tractability, say so, and say what the averaging discards.


### Note 5 — Tal's `5f38cba` pulled and reviewed (19:13, during the session)

"Restructure experimental setup: split physical route subsection, expand forecast data description".
Fast-forward, one file, +58/-52. Builds clean: **27 pages, 0 undefined references**. All 38 of this
morning's typo fixes survived.

**What he did well — the 6 h cadence is now justified by the data** (lines 788-791). GFS wind
refreshes every 6 h, MFWAM waves every 12 h, SMOC currents every 24 h, and the predicted-weather
record confirms it: at a 1 h query cadence 86% of queries return unchanged wind. So "re-planning more
frequently than 6 h acts on no new wind information ... the 6 h cadence is set by the data rather
than tuned." That is a strong, referee-proof answer to a question we would certainly have been asked.

**Section 5.1 is now split** into `\subsubsection{The physical route}` (717) and
`\subsubsection{Sea conditions data}` (764).

**But the resolution problem got worse, not better — it is now three-way.** He added at **line 767**:

> "The system provide the following measurements in spatial granularity of $0.25\degree \times
> 0.25\degree$ and temporal granularity of 6 hours."

So the draft now asserts three different spatial resolutions:

| Where | Claim |
|---|---|
| **line 247** (§3, Sea conditions) | our cells are `0.5°`, "chosen because it is used by global weather and forecast services" |
| **line 767** (§5.1.1, new) | the system provides `0.25° x 0.25°` |
| **line 777** (§5.1.1, list) | ocean currents at `0.08°` |

Line 767 and line 777 now contradict each other **inside the same subsection**, ten lines apart. And
line 247's justification is contradicted by both. This is more visible than before, not less — the
new blanket sentence sits directly above the list that refutes it.

**Cheapest fix:** make line 767 say the granularity we *retrieved and stored* (if that is uniformly
0.25°, then say so and note that SMOC is downsampled to it), and rewrite line 247's justification to
whichever reason is true (see note 3). One sentence each.

**Note 4's gap is untouched.** `tab:waypoints` (737-763) lists **15 rows** — the major route
waypoints from the YAML, not the 131 / 389 weather nodes. So the paper still never states our own
weather-node spacing, and a reader still cannot see that the two routes were sampled 5x apart.

**Also:**
- New typo in the added sentence, line 767: "The system **provide**" -> provides.
- Em-dashes: **70 -> 68** live. Note 2's sweep is still needed, and lines 807-809 are still his.


### Note 6 — the `0.08°` currents question, measured. It is not the real problem.

Full quantitative assessment against the downloaded v3 files and the real physics functions. Two
structural facts reframe the question, and both were verified directly in the source:

**1. The feared failure mode cannot occur.** The resolver does **not** compute a vector mean.
`weather.py:453-457` takes `np.mean(currents)` for magnitude and `_circular_mean_deg(current_dirs)`
for direction. Magnitude is preserved by construction, so opposing currents cannot average toward
zero. The real error is the opposite sign: full current strength retained, pointed in an averaged
direction, which **overstates** net cell drift by **+3.1-3.7%**.

**2. SR never had sub-cell resolution to lose.** SR's H-lines *are* the 0.5° grid crossings —
`h_line_distances_from_geo(..., grid_deg)` (`dp_cpp/src/nodes.cpp:49`) built from
`rhumb_grid_crossings(..., grid_deg=0.5)` (`dp_rebuild/geo_grid.py:126`). All three policies read
weather through the same `cell_weather_at`. So the averaging removes decision opportunities *below*
the cell — a resolution **no** policy possesses — which makes the effect **common-mode** and means it
does **not** bias SR-vs-Luo or SR-vs-baseline.

**Measured information loss** (vector variance decomposed per 6 h slice, E/N components):

| | route1 | route2 |
|---|---|---|
| within-cell / (within+between) | **7.19%** | **9.87%** |
| within-cell RMS spread, median | 0.201 kmh | 0.184 kmh |
| waypoints per cell (mean / max) | 1.16 / 2 | 3.41 / 5 |
| SR H-lines (spatial decisions) | 164 | 121 |

~90% of exploitable current variation is between-cell and survives. Route2 does carry genuinely more
sub-0.5° mesoscale structure (structure function higher at every lag below ~70 NM), but the two
routes' loss figures are close — **not** the 5x asymmetry the sampling difference suggested.

**Cancellation is rare.** `R = |vector mean| / mean(|v|)`: median **0.99** both routes; `R < 0.5` in
**0.89%** (route1) / **0.44%** (route2) of cases once near-zero-current cells are excluded. The low-R
tail sits where the current is too weak to matter.

**Fuel translation** — the recoverable gain, i.e. the upper bound on what a finer grid would buy SR
inside a cell (constrained reallocation at fixed cell transit time, real `calculate_sws_from_sog` /
`calculate_fuel_consumption_rate`):

| | route1 | route2 |
|---|---|---|
| lost to 0.5° averaging | **~0.18-0.19%** | **~0.11-0.14%** |
| SR vs baseline (committed results) | −2.411% | −3.483% |
| SR vs Luo | −1.799% | −2.602% |

**~0.1-0.2 pp against a 2.4-3.5 pp reported advantage — 5-8% of the effect, an order of magnitude
smaller.** Median is ~0; the loss lives in a p90 tail. Accounting bias from evaluating fuel at the
cell mean is −0.2 to −0.3% (Jensen gap), also common-mode.

So our reported SR advantage is **conservative by ~0.1-0.2 pp**, but for a subtler reason than
"averaging removed signal SR was using": SR never had that resolution. A jointly finer grid (weather
*and* H-lines) would raise SR's ceiling while barely moving Luo, whose blocks are already far coarser
than 0.5°.

---

**The bigger finding, which we were not looking for: route1 is under-sampled against its own decision
grid.**

Route1's weather spacing is 26.1 NM but its mean cell traverse is 20.7 NM, so many cells contain **no
waypoint at all** and fall through to nearest-waypoint substitution (`weather.py:502-520`):

| | route1 | route2 |
|---|---|---|
| H-line segments in a **zero-waypoint** cell | **41 of 164 (25.0%)** | 10 of 121 (8.3%) |
| route distance affected | **393 NM = 11.6%** | 74 NM = 3.8% |
| substitution distance mean / max | **9.1 / 18.9 NM** | 1.4 / 2.5 NM |

At 9-10 NM substitution, route1's own structure function implies a current-vector error of
**0.4-0.7 kmh — 2-3x the 0.20 kmh within-cell averaging error** — over 11.6% of the route. It is a
displacement error rather than a signed bias, so it adds noise to route1's absolute fuel more than it
biases the gaps, but it partially undercuts the fine-grained-DP premise on that 11.6%.

**If one data-collection fix is worth doing, it is re-collecting route1 at ~5-10 NM, not refining the
grid.**

---

**Options** (files named; full table in the agent report):

| Option | Verdict |
|---|---|
| (a) document the limitation | **Do this.** Supported by the numbers. |
| (b) finer cells for currents only | Largely pointless — H-lines stay at 0.5°, so SR still cannot act on it; and route1's 26 NM sampling cannot populate sub-0.5° cells. |
| (c) finer cells throughout | Poor return: SR nodes ~152k->~300k, edges 9.2M->20-35M, and **infeasible on route1** without re-collection. |
| (d) path-integrated vector mean per sub-segment | Best accuracy-per-effort. Kills the +3.1-3.7% overstatement, zero runtime cost, graph unchanged. `frame.cpp:30-31`, `weather.py:463`. |
| (e) route2 sensitivity at 0.25° | **Cheapest decisive test.** `grid_deg` already exists as a `Frame` field (`frame.hpp:15`) but is not a CLI flag — ~10 lines each in `SR_main.cpp` / `luo_main.cpp`. |

**Recommendation: (e), then (a); add (d) if there is slack.** Prediction for (e): SR-vs-baseline
improves by <=0.2 pp (−3.48% -> ~−3.6%), Luo-vs-baseline moves <=0.05 pp. If the shift exceeds
~0.5 pp, the within-cell estimate is missing cross-cell time reallocation and (c) deserves another
look.

**Two things to disclose in the paper regardless**, both currently undocumented:
1. The aggregation is a **scalar mean of magnitudes with a circular mean of directions**, not a vector
   mean, and it overstates net cell drift by 3.1-3.7%.
2. Route1's 25% zero-waypoint cells and the 9.1 NM mean nearest-waypoint substitution.



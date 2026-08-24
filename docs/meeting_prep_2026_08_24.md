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

### 1D. The voyage/instance count is now a three-way contradiction

- **150 problem instances** — line 756 (2 routes × 25 departures × 3 ETA levels).
- **35 voyages** — lines 868, 877 (table caption), 967, 1091, 1131.
- **19 voyages** — lines 67 (abstract/intro), 1055, 1111, 1139.

Also: line 868 says "13 on the Indian Ocean route and 22 on the North Atlantic route" = 35, but
Aug-17's **2B** recorded the fresh set as **34** (13 + 21). Decide the canonical number, then state
explicitly how the smaller sets are filtered from the 150.

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

### 2B. Data and golden-set decision

- [ ] Pull the fresh server data and re-freeze, or retain the current set for continuity?
- [ ] Settle the count first (see **1D**) — 35 (13+22), 34 (13+21), and 19 are all in play.
- [ ] If pulling first: schedule the ~740 MB VPN download and regenerate goldens.

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

## 5. Decisions made during the session

| Decision | Owner | Outcome | Follow-up |
|---|---|---|---|
| | | | |

## 6. Actions assigned during the session

| Action | Owner | Due/status |
|---|---|---|
| | | |

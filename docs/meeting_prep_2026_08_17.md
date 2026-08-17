# Meeting Prep — Monday 2026-08-17 (Ami ↔ Tal)

Continues from [meeting_prep_2026_08_10.md](meeting_prep_2026_08_10.md).

This is the running log for the Aug-17 session. Add new items under Section 1 as they arise.
Carryovers below are copied from the previous prep and still need to be confirmed against work
completed since Aug 10.

---

## 1. New items for this session

### 1A. Review Tal's Aug-12 paper changes (`aa43baf`)

- [ ] Review the new two-route benchmark paragraph in §5.
- [ ] Resolve the broken fragment after the route list: “chosen to contrast weather regimes:
  Route~1”.
- [ ] Copy-edit the newly added paragraph (`algoritm`, `This is s shorter`, `volotile`, `depicte`,
  `tseted`, `depature`, `appart`, `teseted`, `corrosponding`).
- [ ] Change the average-speed unit from `NM` to `knots` / `NM h^{-1}`.
- [ ] Reconcile the new **150 problem instances** statement with the unchanged perfect-foresight
  table caption describing **35 voyages**. If 35 is a subset, define the filtering explicitly.
- [ ] Confirm the new stochastic-problem paragraph and rolling-horizon bridge should remain as
  written.
- [ ] Confirm the Algorithm 1 wording “pop the minimal element lexicographically”.
- [ ] Confirm whether the perfect-foresight table should remain `\tiny` or be reformatted.

Reference: [Tal's Aug-12 changes](tal_changes_explained.html).

### 1B. Rework the two-panel state-neighbours figure

Figure: `fig:state-neighbours` — panel (a), a state on a distance line; panel (b), a state on a
time line. Reference image shared before the session.

- [x] **Design prepared:**
  [state_neighbours_figure_redesign.md](state_neighbours_figure_redesign.md).
- [x] Selected a **real, representative interior block**: Route 1, voyage 0 (`sh_base=6`),
  `d∈[1963.886308,1995.718977] NM`, `t∈[120.0,126.0] h`. These are consecutive 0.5° longitude
  crossings (78.5°E–79.0°E) in waypoint segment 8, approximately 58% along the route.
- [x] Defined the source states: panel (a) `(t,d)=(123.0 h,1963.886308 NM)`; panel (b)
  `(t,d)=(120.0 h,1979.718977 NM)`.
- [x] Replaced the illustrative time and distance labels with those **actual values**. Derived all
  candidate-node labels from the selected block and Eq. (5), rather than choosing visually
  convenient example numbers.
- [x] Built both panels from that same selected block: panel (a) places the source state on its
  interior distance line; panel (b) places the source state on its interior time line.
- [x] Made the two panel canvases and plotting regions the **exact same width, height, aspect
  ratio, margins, axis lengths, and clipping bounds**.
- [x] Used one shared design system in both panels: identical background, axis and grid colors,
  successor-family colors, source/candidate marker shapes and sizes, line weights, dash patterns,
  typography, label placement rules, and spacing.
- [x] Kept each mathematical object visually consistent between panels (`v=0`, `v_max`, source
  state, distance-line candidates, time-line candidates, active block boundaries).
- [x] Implemented the shared-renderer architecture and fixed export geometry specified in the
  design.
- [x] Replaced the paper's “values illustrative” caption wording with the selected block's
  provenance.
- [ ] After Tal ratifies `v_max`, regenerate the candidates and final assets with that value. The
  design preview uses the current Route 1 convention `L/T+3 = 15.118714 kn` only provisionally.
- [x] Updated the figure source scripts:
  - `paper_workspace/figures/plot_state_neighbours.py`
  - `paper_workspace/figures/plot_state_neighbours_hline.py`
- [x] Regenerated both individual PDF/PNG outputs and the combined pair output.
- [x] Checked the `v=0` waiting edge, successor families, line labels, units, and candidate labels
  against the current Eq. (5) convention. Recheck after Tal ratifies the open convention.
- [x] Checked legibility and cropping at the two-panel size used in the paper.
- [x] Updated the joint caption for the implemented mathematical interpretation.
- [x] Final acceptance check: overlaid the exported panel bounds and verified they match exactly;
  compared the displayed coordinates against the selected block's source data.

### 1C. Add new topics here

- [ ] Change the discretization used for `fig:state-neighbours` (see
  [state_neighbours_figure_redesign.md](state_neighbours_figure_redesign.md)): every plotted node
  must have an outgoing arc, and the number of nodes along both the vertical (time) and horizontal
  (distance) axes must equal 7 — even if that requires a coarser `τ`/`δ` grid for the figure than
  the production values (`τ=0.1 h`, `δ=1 NM`) currently used. Proposed figure-only grid: `τ = 1 h`
  (hourly), `δ = 5 NM`.

- [ ] Revert the SOG band's lower bound from `0` to `v_min ≈ 8` kn: `v=0` (waiting/station-keeping)
  should only be reachable at the very beginning and very end of a voyage, not mid-route. Relates
  to the still-open waiting-convention decision in **2A** below (variant (a) free-everywhere vs.
  variant (c) priced/destination-only) — this makes the "destination-only" side of that choice the
  default and additionally forbids origin-adjacent-but-not-origin waiting. Places in
  `paper_full_draft.tex` that currently hardcode or describe the `[0, v_max]` band and need
  reconciling once `v_min` is set:
  - Line 252 — the static-problem definition: `$\mathcal{V}=[0, v_{max}]$` (the foundational spot;
    should become `$[v_{\min}, v_{\max}]$`).
  - Line 290 — already written generically as `$\mathcal{V}=[v_{\min},v_{\max}]$`; this is the form
    the rest of the paper should match.
  - Line 484 (figure caption, `fig:state-neighbours`) — "currently generated with
    `$\mathcal{V}=[0,15.119]$ kn`"; entangled with the discretization item above since it's the same
    figure/script.
  - Line 485 (same caption) — "its vertical edge is the `$\bar v=0$` wait leg", shown on an interior
    (non-endpoint) block. Once `v=0` is endpoint-only, either pick a block that legitimately has a
    wait leg (start/end) or drop this from the caption/figure.
  - Line 626–627 (Algorithm walkthrough) — already correctly restricts zero-speed waiting to the
    destination on early arrival ("possibly with some waiting at distance `L` ... at zero speed");
    needs the equivalent statement added for the origin end.
  - Line 638 (Algorithm 1 pseudocode input) — "speed band `$[0,v_{\max}]$`"; should become
    `$[v_{\min},v_{\max}]$` with a note that the endpoints are the exception.

---

## 2. Decisions carried over from Aug 10

### 2A. Waiting and speed-band conventions — Tal to ratify

- [ ] Choose the waiting convention:
  - **Variant (c), recommended:** price mid-ocean waiting at station-keeping cost; waiting is free
    only at the destination.
  - **Variant (a):** free waiting everywhere as an explicit idealization.
- [ ] Define `v_max`: vessel cap, mean speed + 3 kn, or another convention.
- [ ] Decide Luo's comparison band: retain its original 8–18 kn band or align it with
  `[0, v_max]`.
- [ ] Approve the ETA-feasibility arc cut before the full rerun; the open band otherwise produced
  about 14× more arcs and 13× runtime in the quick test.
- [ ] Bless the Eq. (5) waiting candidate and the destination-state convention for `A(L,t)`.

### 2B. Data and golden-set decision

- [ ] Decide whether to pull the fresh server data and re-freeze **34 voyages** (13 Route 1 +
  21 Route 2) before the §5 reruns.
- [ ] Alternative: retain the **19-voyage** set for continuity and pull the fresh data afterward.
- [ ] If pulling first, schedule the approximately 740 MB VPN download and regenerate goldens.

### 2C. Bellman/state-space paper decisions still open

- [ ] Confirm Eq. (6) is the forward/to-arrive formulation that matches Algorithm 1.
- [ ] Fix the remaining Eq. (5) and state-space definitions: on-boundary cell maps, anchored vs
  absolute δ-grid, argmin notation, and the “drawn from the grid” wording.
- [ ] Close the remaining Tal-zone notation and prose audit items before the next paper-wide pass.

---

## 3. Work to start after the decisions

- [ ] Add the waiting candidate and destination clause to Eq. (5).
- [ ] State the selected `φ(d,t;0)` convention and its physical assumption in §4.1.
- [ ] Apply the matching §4.2 extraction, walkthrough, and figure-caption edits.
- [ ] Implement the ETA-feasibility arc cut in Python, then mirror it in C++.
- [ ] Finish the streaming-refactor carryovers: C++ mirror and remaining cleanup.
- [ ] Run the full experiment suite under the approved speed bands.
- [ ] Re-measure κ, state/arc counts, runtime, and Tractability numbers.
- [ ] Rewrite §4.3 around the two-sided discretization story once the lower-bound strategy is
  finalized.
- [ ] Update §5–§7 tables, results, and discussion from the approved rerun set.

---

## 4. Remaining paper and documentation work

- [ ] Add the remaining figures: forecast error, savings vs departure, and fused-voyage placement.
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

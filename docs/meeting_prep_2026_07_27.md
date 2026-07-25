# Meeting Prep — Monday 2026-07-27 (Ami ↔ Tal)

Continues from [meeting_prep_2026_07_13.md](meeting_prep_2026_07_13.md). Everything below is
committed & pushed on `main` (HEAD `72033d9` at time of writing).

---

## 1. Where the paper stands — prose is COMPLETE

Every section is written; no "To be written" stubs remain. Since the last prep:

| Section | State |
|---|---|
| Abstract | ✅ written (node-first numbers: 19/19 oracle, 17/19 RH) |
| §1 Introduction | ✅ written (motivation → granularity gap → 3 questions → approach → results preview) |
| §2 Related work | ✅ citation-accuracy pass (all 26 refs verified; Cariou/Psaraftis re-homed) |
| §3 Problem formulation | ✅ slimmed (option b): SOG + objective in body; vessel table + cubic FCR → Appendix A (also fixed broken appendix refs) |
| §4 Methods | ✅ **jointly reworked — see §2 below** |
| §5 Data & experimental design | ✅ (band 𝒱 wording; node-first on the δ,τ grid) · 1 FIG placeholder |
| §6 Results | ✅ node-first refresh (oracle + RH, both routes) |
| §7 Discussion | ✅ completed (§7.4 written; §7.2 expanded; counts synced 17/19, 2-of-19) |
| §8 Conclusion | ✅ synced |
| Appendix A (FCR) | ✅ (gained eq:fcr + tab:ship) |

**Only remaining paper TODOs: figures** — `FIG: forecast error vs lead time` (§5),
`FIG: savings vs departure` (§7.3), the two `ADD FIGURE` placeholders in §4.1, and deciding
whether the fused voyage concept figure lands in §4.

## 2. §4 state space — the joint Tal+Ami rework (main topic since Jul 23)

Full teaching walk-through (every symbol + plain-words explanations):
- Local: [`docs/state_space_evolution.html`](state_space_evolution.html)
- Artifact: https://claude.ai/code/artifact/e4d27d69-fee3-48c9-857c-8d7794853796

The four acts, in commit order:

1. **`c0dc083` (Tal, Jul 23)** — replaced the abstract "reachable continuum" state set with an
   **explicit grid**: 𝒮 as a union of grid points (δ = 1 NM on time lines, τ = 0.1 h on distance
   lines), index maps 𝒟(d)/𝒯(t), and the neighbour set 𝒜(d,t) — **time case**.
2. **`250ef83` + `a8ae392` (Ami, Jul 24)** — unified notation ζ→δ across §4.2/§5 (two symbols, one
   step); **completed 𝒜(d,t)** with the mirror **distance case** (the task Tal left); typo pass.
3. **`1c6bbb4` (Ami, Jul 25)** — **Bellman equations recast node-first**: C*(d,t) = min over grid
   predecessors (d̃,t̃) with (d,t) ∈ 𝒜(d̃,t̃) and v̄ = Δd/Δt ∈ 𝒱; V* = realised slope of the winning
   leg. The two hand-written cases{} are gone (absorbed into 𝒜); v̄∈𝒱 sits inside the min so Tal's
   Eq. (5) needed no edit. **Forward-only: Tal's Eqs. 4–5 byte-for-byte untouched.**
4. **`72033d9` (Ami, Jul 25)** — **§4.2 reconciled** with the grid: intro no longer claims 𝒮 "has to
   be made finite" (it already is); §4.2.1 reframed from "create the grid" to "use the grid" (snap
   operators = rounding arithmetic; |𝒮| bound read off Eq. 4); §4.2.2 d̄/t̄ ≡ 𝒟/𝒯 shorthand, the
   enumeration explicitly = 𝒜(d,t) filtered by v̄∈𝒱, closure claim corrected (reachable **subset**
   of 𝒮); Algorithm 1's two loops annotated as the two sets of Eq. (5).

**§4 now reads as one continuous story:** §4.1 draws grid + neighbours → Bellman minimises over
neighbours (speed derived) → §4.2 bounds, enumerates (Alg. 1), sweeps (Alg. 2). One notation (δ, τ).
Every superseded passage preserved under `\begin{comment}`.

## 3. Node-first: experiments, code, comparisons (recap of the week before)

- **Both experiments re-run node-first** and §6 rewritten: oracle SR<Luo **19/19** (gaps −1.9% R1 /
  −2.8% R2, wider than speed-first); RH-SR saves vs Naive **17/19** (means −1.3% / −1.8%); Luo &
  Naive baselines reproduce exactly (no drift).
- **C++ port** of node-first (`--node_first`): graph byte-identical to Python on both routes;
  regression harness ALL PASS.
- **Luo is node-first by construction** (per-block end-distance → SOG = Δd/Δt), so the SR–Luo
  comparison isolates granularity, not enumeration. *(Possible one-sentence addition to §5 baseline
  description — see open items.)*
- Comparison artifacts:
  - Node-first vs speed-first results: https://claude.ai/code/artifact/1b54698c-d670-449b-a7f2-67d4d8430861
  - §3–5 method-text change log: [`docs/method_changes_node_first.html`](method_changes_node_first.html) ·
    https://claude.ai/code/artifact/929178ab-ab4d-41ab-b2fc-112d91fb4274

## 4. For Monday — decisions & discussion points

1. **§4.1 review** — Tal to eyeball: (a) the completed two-case 𝒜(d,t) (Eq. 5), (b) the node-first
   Bellman equations (min over 𝒜, v̄ derived), (c) the de-dangled movement sentence. All forward-only
   on his framing, but they're his equations to bless.
2. **Figures plan** (the only remaining paper work):
   - `ADD FIGURE` ×2 in §4.1 (the grid/lines picture + the state/neighbour picture) — the fused
     voyage figure (designs A/B in `paper_workspace/figures/`) could serve as one.
   - `FIG: forecast error vs lead time` (§5) — needs the forecast-error data series.
   - `FIG: savings vs departure` (§7.3) — data already in `runs/…/results.csv`.
3. **Whether to add** the one-sentence §5 note that Luo's lattice is likewise node-first
   (pre-empts the "did you enumerate both the same way?" reviewer question).
3a. **𝒜(d,t) vs the glide-past rule (small formalism gap, Tal's call).** In the τ-unresolvable
   corner (next distance line closer than v_max·τ), Algorithm 1 skips the line and emits time-line
   successors *beyond* d_{𝒟(d)} — successors Eq. (5) does not list. §4.2.2 now scopes its claim
   honestly ("up to this boundary rule"), and the Bellman min inherits the same caveat. Options:
   (i) leave as a stated boundary rule (current), (ii) extend Eq. (5) with the corner case,
   (iii) add a one-line remark after Eq. (5). Also from the same alignment sweep: arc bound now
   |𝒜| = O(κ|𝒮|) with κ = far-wall neighbours (κ≈8), freeing K for "discrete speed levels"
   (K^lines / Luo's K^N); orphan FCR_i(v,t) retired in favour of φ(d,t;v); preamble d_i = d_{i-1}+l_i
   fixed; stale (d̲,t̲) cross-ref in §4.2.2 repaired (commit `12eab79`).
4. **Full Overleaf recompile + read-through** — Overleaf copy must be synced to git HEAD first
   (it lagged twice this week; the repo is the source of truth).
5. Next milestones after figures: internal review pass (paper-reviewer / paper-critic agents),
   then submission logistics (TR-C).

## 5. Reference — key artifacts & files

| What | Where |
|---|---|
| §4 walk-through (4 acts, plain words) | `docs/state_space_evolution.html` · artifact e4d27d69 |
| §3–5 node-first change log | `docs/method_changes_node_first.html` · artifact 929178ab |
| Node-first vs speed-first comparison | artifact 1b54698c |
| Fresh results data | `runs/2026_07_16_nf_oracle_full/` · `runs/2026_07_16_rh_nodefirst/` |
| Table generator | `pipeline/dp_rebuild/make_results_tables.py` |
| Concept figures | `paper_workspace/figures/fused_voyage{,_B}.png` · `plot_fused_voyage{,_B}.py` |

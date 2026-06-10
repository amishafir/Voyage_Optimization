# Backward Design Process (G1 → G6)

We design the paper **from the end backward** — starting from the results we actually
have, and only moving to the previous layer once the current one is *frozen*. The rule:
**do not advance backward until the current part is designed.** Each gate produces one
artifact in this folder; freezing it = signing off before opening the next gate.

Why backward: it makes the abstract physically incapable of over-claiming — every
sentence in it is assembled from a verified link in the chain below it.

## The gates

| Gate | Layer (writing order = reverse) | Artifact (file) | "Frozen" when… |
|---|---|---|---|
| **G1** | **Evidence ledger** | `G1_evidence_ledger.md` | Every result we'd defend is listed with exact numbers, route, mode (Mode C / RH), credibility tag, and source CSV path. No interpretation. |
| **G2** | **Claims / contributions** | `G2_claims.md` | Each claim cites ≥1 G1 row; every strong result maps to a claim; unsupported claims are killed here. Includes the fuel claim **and** the compute-tradeoff claim. |
| **G3** | **Research questions** | `G3_research_questions.md` | RQ → Claim → Evidence map. Each RQ traces forward to a claim and back to a gap. This is the paper's spine made explicit. |
| **G4** | **Methods skeleton** | `G4_methods.md` | Only the apparatus needed to make the RQ→evidence chain legible (routes, SR & Luo formulations, Mode C, RH, bounds, complexity definitions). Nothing methods describes that no result uses. |
| **G5** | **Literature / gap** | `G5_gap_map.md` | Gap table keyed to *our RQs*, drawn from `context/literature/pillar_*`. Every RQ has a positioned gap; no orphan citations. |
| **G6** | **Abstract + title** | `G6_abstract.md` | One paragraph = G3→G2→G1 compressed. Says nothing the body doesn't prove. |

## Locked inputs (from 2026-06-08 session)
- **Spine:** SR vs Luo; per-leg freedom vs per-block SOG-lock; Jensen on cubic FCR is the mechanism.
- **Comparison points:** Mode C (oracle) + RH (operational) only.
- **Second axis:** computational complexity (Luo block graph vs atomic-edge graph).
- **Venue:** Transportation Research Part C.
- **Constraint:** no new runs — G1 is a closed audit of `../results/` + `../context/docs/`.

## Status
- [x] **G1** — evidence ledger ✅ FROZEN (`G1_evidence_ledger.md`). Decisions: compute = structural-only (§D); supporting E-1/E-2/E-4/E-5 in, E-3/E-6 out (§E).
- [x] **G2** — claims ✅ FROZEN (`G2_claims.md`) — 6 claims → **3 contributions**; compute folded into C-I; boundedness = Discussion limitation; LP/DP dropped (single Luo foil); killed list agreed.
- [x] **G3** — research questions ✅ FROZEN (`G3_research_questions.md`) — 3 RQs ↔ 3 contributions, spine + why→how-much→does-it-hold arc.
- [x] **G4** — methods skeleton ✅ FROZEN (`G4_methods.md`). Jensen = **standalone Mechanism section** (between Methods and Results); §4.6 structural-only reaffirmed; Excluded list agreed. **SR = Shafir–Raviv** (confirmed). Paper structure settled.
- [ ] G5 — gap map (last gate blocking the Introduction's motivation/gap)
- [ ] G6 — abstract + title

## Writing-forward (drafts/)
The bottom three frozen gates are being written into actual paper prose under `../drafts/`:
- [~] `drafts/06_results.md` — **Results** (writes G1). RQ2 Mode C + RQ3 RH, CSV-verified numbers. Compute (RQ1) intentionally absent → Methods/Discussion.
- [~] `drafts/01_introduction.md` — **Intro backbone** (writes G3 RQs + G2 contributions). §1.3/1.4 final; §1.1/1.2 motivation+gap are `[LIT→G5]` placeholders (blocked until G5).
- [~] `drafts/04_methodology.md` — **Methods** (writes G4). Common framework, SR, Luo (+fidelity), structural complexity (+structural-only caveat), evaluation protocol. `[METHODS→G4]` placeholders in Results now resolved.
- [~] `drafts/05_mechanism.md` — **Mechanism** standalone section (writes G4 §4.5). Jensen on convex FCR → two empirical predictions (signed gap; scales with variability). **Code verification ✅ PASS** (2026-06-08): both SR (atomic_edges.py:236-247) and Luo (luo_main.py:229-239) cost FCR(SWS) with SWS inverse-solved from the chosen SOG; FCR cubic in SWS (physics.py:325-337). Jensen taken as established from cited reference (math not re-derived).
- [~] `drafts/03_problem_formulation.md` — **Problem Formulation**: ship spec, SOG chain (Eqs 1–7), cubic FCR convexity premise (Eq 8), SOG-targeting objective.
- [~] `drafts/05b_experimental_setup.md` — **Data & design**: Open-Meteo/GFS-MFWAM-SMOC, two-regime contrast, S-1 forecast error, S-2 NWP cycle/6h, 19-voyage chain.
- [~] `drafts/07_discussion.md` — **Discussion**: mechanism predictions confirmed, structural cost, boundedness *limitation* (§7.3), lit comparison `[LIT→G5]`, limitations.
- [~] `drafts/08_conclusion.md` — **Conclusion**: 3 contributions, "granularity is the binding factor", future work.
- [~] `drafts/00_frontmatter.md` — title (working) + authors + **abstract `[G6]`** + keywords placeholders.
- [~] `drafts/02_related_work.md` — Related Work, structure fixed, prose `[LIT→G5]`.
- **Whole unblocked body now drafted.** Still gated on G5: `01_introduction` §1.1/1.2 + Related Work (§2) + Discussion §7.4 + all `[CITE:]`.

## Assembled full draft → `../paper_full_draft.md`
~5,900 words, 9 sections in reading order, dev comments stripped, with a banner inventorying every
open placeholder. **It is a SNAPSHOT — edit the section files in `drafts/`, not this file, then
re-assemble.** Provisional numbering (1,2,3,4,5,5b,6,7,8) preserves internal cross-refs; final
renumber (5b→6, …) happens at LaTeX typesetting.

**Re-assemble command:**
```
cd paper_workspace
cat > paper_full_draft.md <<'B'
<!-- banner: see existing file head -->
B
perl -0777 -pe 's/<!--.*?-->//gs' \
  drafts/00_frontmatter.md drafts/01_introduction.md drafts/02_related_work.md \
  drafts/03_problem_formulation.md drafts/04_methodology.md drafts/05_mechanism.md \
  drafts/05b_experimental_setup.md drafts/06_results.md drafts/07_discussion.md \
  drafts/08_conclusion.md | perl -0777 -pe 's/\n{3,}/\n\n/g' >> paper_full_draft.md
```
(zsh note: pass the file list explicitly — unquoted `$VAR` does not word-split in zsh.)

## Overleaf-ready LaTeX → `../paper_full_draft.tex`
Hand-built from the drafts using the existing `elsarticle` (review) preamble. Compiles with
**pdfLaTeX** as-is (standard packages: amsmath, amssymb, booktabs, siunitx, hyperref, xcolor).
Authors: Ami Shafir, Tal Raviv (TAU). Every open item renders as a **red `\todo{…}`** so the file
compiles while showing exactly what's pending. Section cross-refs use `\ref{}` (auto-numbered), so
LaTeX numbering is correct even though Data/Results/Discussion shift vs the markdown's "5b" scheme.
3 real tables (ship params, Mode-C aggregates, RH summary) are rendered; per-voyage/size/route
tables and both figures are `\todo` placeholders. References pending G5 (no `.bib` yet).
- Placeholders in drafts: `[LIT→G5]`/`[CITE:]` (G5), `[TABLE:]`/`[FIG:]` (build), `[EQ: ...]` (numbered at assembly), `[METHODS: Δt; per-route weather stats]`.

> The existing `../paper/paper_outline.md` and `speed_control_v1.tex` predate this spine
> (they use LP/DP/RH framing + 6 contributions). Treat them as **raw material to mine**,
> not as the structure to follow. The G1–G6 chain defines the new structure.

# Paper Change Log

Running log of changes to make to the paper. **`paper_full_draft.tex` is the source of truth** —
hand-edited directly by the user (as of 2026-06-11 it has diverged from `drafts/`, which is now
stale reference only). Capture notes **during** the meeting in §1 (fast, freeform), triage them into
the action table in §2 afterward, then work the table top-to-bottom and tick items off.

**How to use**
- During the meeting: just dump bullets under a dated heading in **§1 Meeting notes**. Don't worry about structure.
- After: convert each note into a row in **§2 Action items** (section, change, status).
- When applying: edit `paper_full_draft.tex` **directly and surgically** — do **NOT** regenerate it
  from `drafts/` (that would clobber hand edits). Touch only sections **not** listed in **§5 (Locked)**.
  Tick the row and move it to **§3 Done**.

Status key: ☐ open · ◐ in progress · ☑ done

---

## 1. Meeting notes (raw capture)

### Meeting — 2026-06-__
- 
- 
- 

---

## 2. Action items (triaged)

| # | Section / location | Change requested | Priority | Status |
|---|---|---|---|---|
| 2 | §3 Problem formulation | **Restructure with fewer subsections** (input → output). User began this directly in the `.tex` (2026-06-11): added the input→output intro + a Route / T / Weather / FCR definition block. Remaining: collapse the §3.1–3.4 subsections. **§3 is now LOCKED (§5) — coordinate with user before editing.** | medium | ◐ |
| 3 | §3 FCR definition (weather → fuel) | **Describe weather→fuel as a black box** via Yang (2020). Addressed by user in the `.tex` §3 (2026-06-11): FCR defined as a function of weather, vessel characteristics, course, and SOG; method from "(CITE Sustainability)" in "Appendix X". Remaining: resolve the cite to `yang2020` and write Appendix X. | medium | ◐ |
|  |  |  |  | ☐ |

---

## 3. Done

| # | Section | Change | Date |
|---|---|---|---|
| 1 | Bibliography | **BibTeX set up.** Created `refs.bib` (yang2020, luo2024, openmeteo); replaced the manual `thebibliography` with `\bibliographystyle{elsarticle-harv}` + `\bibliography{refs}`; converted all `\todo{cite: …}` markers to `\citet`/`\citep` (Luo×4 → `\citet{luo2024}`, Open-Meteo → `\citep{openmeteo}`; Yang already `\citet/\citep{yang2020}`). NOTE: verify Open-Meteo citation; resolve §3's plain-text "(CITE Sustenability)" to `\citep{yang2020}` (blocked — §3 locked, item #3). Overleaf: upload `refs.bib` alongside the `.tex`. | 2026-06-11 |

---

## 4. Known open items already in the paper (pre-meeting reference)

These are the placeholders/TODOs currently in the draft — useful context, not meeting output:

- **Abstract** — `[To be written.]` (write last)
- **§1 Introduction** — collapsed to `[To be written.]` (motivation, gap, RQs, contributions to be written from G5)
- **§2 Related work** — `[To be written.]` (gated on G5 literature gap map)
- **§7.4 Relation to prior work** — `[To be written.]` (gated on G5)
- **Citations** — only Yang et al. (2020) wired; Luo 2024, Open-Meteo, pillars 1–6 still `\todo{cite: …}`
- **Tables/figures pending** — forecast-error figure, savings-vs-departure figure; per-route weather mean±s.d. in the route table; Δt per route in §4.1
- **Design gates** — G5 (literature) and G6 (abstract) not yet designed; G2/G3/G4 docs still mention the (removed) structural-complexity axis
- **Appendix X + cite** — §3 references the FCR method as "(CITE Sustainability)" in "Appendix X"; resolve the cite to `yang2020` and write Appendix X (the Yang FCR / resistance method)

---

## 5. Locked / hand-edited sections — DO NOT modify or regenerate

`paper_full_draft.tex` is hand-edited and authoritative. Do **not** re-assemble it from `drafts/`
(the `.tex` and `drafts/` have diverged). Apply future changes only to sections **not** listed here;
when the user hand-edits a new section, add it here with a date.

| Section | Locked since | Note |
|---|---|---|
| Frontmatter (title, authors) | 2026-06-10 | Finalised by user. |
| §3 Problem formulation | 2026-06-11 | Hand-edited: new input→output intro + Route / T / Weather / FCR black-box definitions. Coordinate with user before any edit. |

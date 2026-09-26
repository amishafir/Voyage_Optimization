# Design — §6 *Results*: aggregates in the body, per-voyage numbers in the appendix

**Target file:** `paper_workspace/paper_full_draft.tex`
**Baseline:** working tree clean at `054431a`, 35-page PDF, builds clean.
**Brief (author, 2026-09-26):** move every experiment's numbers to the appendix; keep aggregates in
§6; §6 must still convey the **information-regime results for both routes** and the **harsh-weather
result**.
**Status:** design only. Nothing below is applied.

> **Scope guard.** §6 (lines 968–1256) and the appendix are in scope. §1–§5 are not touched. §7
> (Discussion) is **not** modified — it reads §6's conclusions, not its tables, and every fact it
> cites survives this change. One exception is listed in §7 (open items) as an author decision.

---

## 1. What §6 contains today

Seven tables, **88 data rows**, zero figures.

| Table | Kind | Rows | Disposition |
|---|---|---|---|
| `tab:modec` | Perfect-foresight aggregate, both routes | 2 | **merged into T1** |
| `tab:modec-r1` | Per-voyage PF, Indian Ocean | 15 | → appendix |
| `tab:modec-r2` | Per-voyage PF, North Atlantic | 26 | → appendix |
| `tab:rh` | Rolling-horizon aggregate, both routes | 2 | **merged into T1** |
| `tab:rh-r1` | Per-voyage RH, Indian Ocean | 15 | → appendix |
| `tab:rh-r2` | Per-voyage RH, North Atlantic | 26 | → appendix |
| `tab:span` | Span and forecast cost, both routes | 2 | **kept as T2, unchanged** |

**82 of the 88 rows leave the body. Six remain.**

### 1.1 Two findings from the inventory

**The prose already carries the distribution.** The eight `\textbf` run-in findings in §6.1 and §6.2
state their evidence as derived aggregates, not as pointers into a table: per-voyage advantages
"ranging from 6.06 to 13.24 mt", "saved on 15 of 26", "beaten by rolling-horizon Luo on 12 of those
26", "the two failure sets overlap on 8". **None of the eight reads a row out of a per-voyage
table**, so all eight survive the move untouched. The per-voyage tables were corroboration, not
support.

**Three tables are never referenced.** `tab:rh`, `tab:rh-r1` and `tab:rh-r2` have **zero** incoming
`\ref`s; they float unanchored. `tab:modec`, `tab:modec-r1`, `tab:modec-r2` are referenced once
together (line 980) and `tab:span` once (line 1252). So the cross-reference cost of this whole
restructure is **two lines**.

---

## 2. What §6 keeps

### T1 — Fuel by route and information regime (**new**, replaces `tab:modec` + `tab:rh`)

This is the table the brief asks for: the regime comparison, both routes, in one place. It is what
lets a reader see the reversal without turning a page.

**The enabling fact:** Naive does not re-plan and is *identical in both regimes*
(§5.2, *Information regimes*). So "% vs Naive" is the one currency directly comparable across
regimes, and it becomes the spine of the table.

| Route | $n$ | Regime | Naive (mt) | SR vs Naive (%) | Luo vs Naive (%) | SR vs Luo (%) | SR $\le$ Naive |
|---|---|---|---|---|---|---|---|
| Indian Ocean | 15 | Perfect foresight | 355.11 | $-2.72$ | $-0.30$ | $-2.43$ | 15/15 † |
| Indian Ocean | 15 | Rolling horizon | 355.11 | $-1.46$ | $+0.10$ | — | 15/15 |
| North Atlantic | 26 | Perfect foresight | 203.26 | $-2.20$ | $-0.81$ | $-1.40$ | 26/26 † |
| North Atlantic | 26 | Rolling horizon | 203.26 | $-0.26$ | $-0.10$ | — | 15/26 |

All values above are already published in `tab:modec`, `tab:rh` or the §6.2 prose, **except the two
marked †**, which must be computed from `runs/2026_09_08_pf_chain41/waypoint/results.csv`. They are
expected to be 15/15 and 26/26 by containment — Naive's constant $D/T$ lies in SR's band, so SR
cannot do worse under perfect information — but the design does not assert a number it has not read.

**Reading the table.** Under perfect foresight SR beats Naive on both routes by 2–3%. Under a real
forecast the Indian Ocean figure falls to $-1.46\%$ and holds on every voyage, while the North
Atlantic figure collapses to $-0.26\%$ and holds on only 15 of 26. The regime, not the route, is what
changes the verdict — and it changes it on one route only.

**Design decisions:**
- **Confidence intervals are dropped from T1 and kept in the appendix.** `tab:modec` currently
  carries a 95% paired bootstrap CI on all six numeric columns, which is why it is set in `\tiny`.
  A four-row table with CIs on every column is unreadable. Recommendation: carry the CI on the
  headline column (SR vs Naive) only, in the appendix keep them all.
- **Absolute fuel is kept for Naive only**, as the scale anchor. SR and Luo absolutes move to the
  appendix; the body needs the ratio, not the tonnage.
- **`SR vs Luo` is blank for the rolling-horizon rows on purpose.** Under a real forecast the
  containment guarantee does not hold, so this is the one cell where a single mean actively misleads
  — SR is ahead on average and behind on 12 of 26 Atlantic voyages. The dispersion column and F1
  carry that instead.

### T2 — `tab:span`, unchanged

Two rows, already aggregate, already the mechanism. Keep verbatim.

| Route | $n$ | Span (mt) | Forecast cost (mt) | Span captured (%) | Cost exceeds span |
|---|---|---|---|---|---|
| North Atlantic | 26 | 4.47 | 3.90 | 12.8 | 11/26 |
| Indian Ocean | 15 | 9.66 | 4.46 | 53.8 | 0/15 |

### F1 — Span versus forecast cost, per voyage (**new figure**)

**§6 has no figure at all today.** Removing 82 rows of per-voyage numbers removes the reader's only
access to dispersion, and a mean plus a count cannot show that the two routes fail *differently*.
One scatter restores it.

- **x** = optimisation span (Naive $-$ oracle SR), mt
- **y** = forecast cost (RH-SR $-$ oracle SR), mt
- 41 points, one per voyage, marker by route
- the diagonal $y = x$ drawn: **above it, the forecast cost exceeds the whole span and
  rolling-horizon SR finishes behind Naive.** Those are exactly the 11 North Atlantic voyages.

**Buildable today from one existing file, no new run.** `runs/2026_09_09_rh_chain41_waypoint/results.csv`
has 41 rows carrying `oracle_sr`, `naive_mt` and `rh_sr_mt`, so both axes are a subtraction.

This is **decision #5 from the 2026-09-14 agenda** ("Add the span-vs-cost scatter as §6's figure?"),
which was optional then. Moving the per-voyage tables out makes it load-bearing: it is what stops §6
becoming six rows of means with no visible spread.

---

## 3. The harsh-weather requirement, and the trap in it

The brief asks §6 to convey "information about the harsh weather results". It should — but **not as
a claim that harshness caused them**, because the paper already argues the opposite in two places.

**The harsh-route outcome** (North Atlantic: mean wind 29.7 km/h, median BN 4, against 20.2 and BN 3):
rolling-horizon SR averaged $-0.26\%$ against Naive, saved on 15 of 26 voyages, was beaten by
rolling-horizon Luo on 12 of 26 and by the constant-speed baseline on 11 of 26, the two failure sets
overlapping on 8 — so on **15 of 26 voyages the finest-grained planner was beaten by something
simpler**. No such failure on the Indian Ocean route.

**Trap 1 — severity is not the governing variable, and §6.3 says so.** The current text states it
outright: *"The governing quantity is the ratio of span to forecast error, not the severity of the
weather."* The Indian Ocean route has more than twice the span (9.66 vs 4.47 mt) at almost the same
forecast cost (4.46 vs 3.90 mt); that ratio, not the Beaufort number, is what separates 53.8% span
captured from 12.8%.

**Trap 2 — the two routes are confounded, and §6.1 already concedes it.** The North Atlantic is
harsher *and* sampled 5.4× more finely (5.04 NM blocks against 27.15 NM) *and* shorter (168 h against
280 h). The existing finding says *"neither cause can be isolated from this pair of routes, and no
ordering between them is attributed here to either."* A §6 reorganised around "the harsh route"
would quietly retract that concession.

**Resolution adopted by this design.** The harsh-route result is reported as an *outcome* in §6.2,
where it already is, and *explained* in §6.3 by span-versus-cost, where it already is. F1 makes the
explanation visible. **No subsection is named after weather severity, and no causal claim is added.**
The requirement is met by keeping the harsh-route counts in T1's dispersion column and the harsh-route
mechanism in T2 and F1 — not by promoting severity to an organising principle.

- [ ] **Author check.** If the intent was in fact a severity-organised §6, it contradicts §6.1 and
      §6.3 and needs those two to be reopened first. Flagging, not assuming.

---

## 4. What the appendix receives

**New Appendix D — Per-voyage results**, after `app:fcr-luo`, holding the four per-voyage tables
verbatim: PF Indian Ocean (15), PF North Atlantic (26), RH Indian Ocean (15), RH North Atlantic (26).

Ordering within: group by regime (PF then RH), route within regime, matching §6's own order so the
appendix reads as §6's backing sheet.

One lead-in paragraph stating that these are the complete per-voyage numbers behind T1, T2 and F1,
paired by departure hour, and that every aggregate in §6 is derived from them.

**Appendix letters after the change:** A speed correction · B FCR derivation · C benchmark ANN ·
**D per-voyage results**.

---

## 5. Cross-reference impact

Verified by `grep` on the baseline.

| Label | Incoming refs | Action |
|---|---|---|
| `tab:modec` | 1 (line 980) | retarget to T1 |
| `tab:modec-r1` | 1 (line 980) | retarget to Appendix D |
| `tab:modec-r2` | 1 (line 980) | retarget to Appendix D |
| `tab:rh` | **0** | absorbed into T1; label retired |
| `tab:rh-r1` | **0** | moves; label retained for Appendix D |
| `tab:rh-r2` | **0** | moves; label retained for Appendix D |
| `tab:span` | 1 (line 1252) | unchanged |

**Total edit surface for cross-references: two lines, 980 and 1252.** Line 1252 needs no change at
all if `tab:span` keeps its label.

---

## 6. Edits, in application order

| # | Edit | Touches |
|---|---|---|
| E-0 | Baseline check: confirm 88 rows across 7 tables, `tab:rh*` unreferenced | — |
| E-1 | Compute the two † cells from the PF CSV; regenerate T1's numbers from the generators rather than transcribing | `make_pf_tables.py`, `make_rh_tables.py` |
| E-2 | Build F1 from `rh_chain41_waypoint/results.csv`; emit to `paper_workspace/figures/` | new script |
| E-3 | Insert T1 in §6.1, delete `tab:modec` and `tab:rh` | §6.1, §6.2 |
| E-4 | Cut the four per-voyage tables from §6 | §6.1, §6.2 |
| E-5 | Create Appendix D; paste the four tables with labels intact | appendix |
| E-6 | Place F1 in §6.3 beside `tab:span` | §6.3 |
| E-7 | Retarget line 980; add pointers from §6.1 and §6.2 to Appendix D | §6.1, §6.2 |
| E-8 | Verify the eight `\textbf` findings still read correctly with the tables gone | §6.1, §6.2 |

---

## 7. Open items for the author

| # | Item | Default taken |
|---|---|---|
| 1 | **Severity as an organising principle?** Contradicts §6.1 and §6.3 (§3 above) | Not adopted; harsh-route result reported as outcome, explained by span/cost |
| 2 | CIs in T1: all columns, headline only, or none? | **Headline only**; full set in Appendix D |
| 3 | Is F1 approved? It is Sep-14 decision #5, still unanswered | **Assumed yes** — without it §6 has no dispersion and no figure |
| 4 | Absolute SR/Luo tonnage in the body, or appendix only? | **Appendix only**; T1 anchors scale with Naive |
| 5 | Should §6.4 *Supporting observations* (2 sentences) fold into §6.3? | **Left alone** — out of the brief |
| 6 | `tab:rh` is unreferenced today. Retire the label, or keep it for T1? | **Retire**; T1 gets a new label `tab:regimes` |

---

## 8. Facts used, and where each was verified

| Fact | Verified how |
|---|---|
| §6 spans 968–1256; 7 tables, 0 figures | `awk` over the float environments |
| Row counts 15/26/15/26 in the per-voyage tables | counted rows ending `\\` with `&` |
| `tab:rh`, `tab:rh-r1`, `tab:rh-r2` have 0 incoming refs | `grep -o 'ref{...}' \| wc -l` |
| Naive is identical across regimes | §5.2 *Information regimes*: "Naive does not re-plan and is identical in both" |
| Span/cost derivable per voyage without a new run | `results.csv` header carries `oracle_sr`, `naive_mt`, `rh_sr_mt`, 41 rows |
| §6.3 denies severity is the governing quantity | quoted from the run-in at line 1242 |
| §6.1 concedes the routes are confounded | quoted from the run-in at line 1086 |
| The eight run-in findings cite aggregates, not table rows | read all eight at 1080–1102 and 1192–1215 |

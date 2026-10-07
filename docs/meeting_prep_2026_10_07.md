# Meeting Prep — Wednesday 2026-10-07 (Ami ↔ Tal)

Continues from [meeting_prep_2026_10_05.md](meeting_prep_2026_10_05.md). Everything below is pushed;
`origin/main` is at `1a98c1d`.

**The paper is unchanged since Tal's own §3 rewrite**, apart from two repairs it required. Four
questions are waiting on him, and one of them blocks the rest.

---

## 1. Lead with this: a gap in §3's reduction

§3 reduces the problem by Jensen's inequality — *"replacing $v(t)$ by the average speed … does not
increase the fuel consumed"* — and §4's dynamic program is built on that reduction. It needs
$\phi(t,d;\cdot)$ **convex in speed over ground**, which §3 asserts.

**Nothing in the paper establishes it.** The appendix establishes convexity in **still-water speed**,
and gives the link between the two as **monotonicity only**.

**Checked on 10-06: it is true, but not for the easy reason.**

- Convex at **800 of 800** sampled weather states across the band, both routes
- But $g^{-1}$ is **concave** (mean 2nd difference $-1.9\times10^{-4}$), because Kwon's
  $C_U = 2.6 - 13.1 F_n - 15.1 F_n^2$ has negative coefficients at this block coefficient
- So the composition rule **does not apply**. With $h=g^{-1}$,
  $\phi'' = a[6h(h')^2 + 3h^2h'']$ with $h''<0$, so $\phi$ is convex **iff $2(h')^2 > h|h''|$** — the
  cube law's curvature must outweigh the correction's. Here it does, comfortably

**Decision needed — how to discharge it:**

| | Form | Cost |
|---|---|---|
| (a) | State it as an **assumption** of the formulation, as `luo2024` and most of the field do | one sentence |
| (b) | **Verify numerically** — the condition, the 800 states, the margin | a short subsection; already computed |
| (c) | **Prove** it for Kwon's quadratic on $[V_{\min},V_{\max}]$ | real work; likely ends at (b) with algebra |

- [ ] **(a), (b) or (c)?** — recommend **(b)**, with (a) as fallback

---

## 2. How much appendix do we want?

Audit: [appendix_audit_design](appendix_audit_design_2026_10_06.md).

**No appendix equation is referenced from the body.** `eq:app-ct` is referenced by nothing anywhere.
Appendix A has no incoming body reference at all since the §3 rewrite — a consequence of it, since
$\phi$ is now defined on SOG and the body never mentions SWS.

| | Lines | Equations |
|---|---|---|
| Appendices A + B today | 142 | 6 |
| What a reader demonstrably needs | ~25 | 1 |

What survives the test *(needed to reproduce or to judge, and not available from the citation)*: the
calibrated cubic $0.000706\,V_s^3$, the vessel particulars, the verification accuracy, invertibility
by binary search, strict convexity, the validity range — **plus whatever §1 decides**, which is the
one item that is genuinely ours.

What fails it: the DTU–SDU chain, `eq:app-ct`, the reduction to the cubic, the full form of
`eq:sog`. All `yang2020` via `kristensen2012`.

- [ ] Cut to what the paper uses, keep the derivation, or **cut in the paper and keep it in the
      thesis**?
- [ ] Merge A and B regardless? They are two halves of one evaluation of $\phi$, cross-reference each
      other four times, and A is orphaned
- [ ] Move `tab:ship` to §5? Referenced twice, **both from inside the appendix**
- [ ] Appendix C — its own text says it *"is not used to produce any number reported in this paper"*.
      Keep and shorten, or keep as is?

---

## 3. Carried over, needing him

- [ ] **Confirm the §7.3 replacement.** A mechanism he has read is gone: it predicted the block-locked
      planner would be the safer of the two under forecasts on the Atlantic, and it saves 0.24 mt
      against SR's 0.57. Replaced by the measured mechanism in §6.4
- [ ] **Action 4 — more voyages, or report the bounds?** Overlapping departures give +60 voyages and
      no power; effective sample size stays at 40. Recommend the bounds
- [ ] **The method names** — SR / Luo / Naive. Deferred twice
- [ ] Commit the built PDF?
- [ ] **`bearing` or `heading`?** His §3 says bearing (7), the appendices and §4 say heading (15).
      Same thing on a rhumb line, but $\phi$ is *defined* at the bearing and *computed* relative to
      the heading

---

## 4. For his answer: does `luo2024` have route segments, and does the heading change?

Logged 10-01, still open. Their "segments" are units of **time** in our §3's description; ours are
geometric. He renamed theirs to **stages** in the rewrite, which resolves the collision — but the
underlying question stands, because **our Luo implementation takes one heading per block** while SR
takes one per subsegment, and up to 23% / 32% of blocks could span a course change.

If their course is per-leg, that is a **second** fidelity difference, running the *opposite* way to
the one §3's footnote already discloses.

---

## 5. Paper state

| | |
|---|---|
| Draft | 39 pages, builds clean, 0 undefined references |
| Pushed | `origin/main` = `1a98c1d`, verified |
| §3 | **Tal's**, 2026-10-05 — formal statement, $\phi$ on SOG, stages, 0.08° cell subsegments |
| §6 | 6.1 deterministic, 6.2 stochastic, 6.3 forecast cost, 6.4 why it costs more |
| Appendices | A speed correction · B FCR · C benchmark ANN · D per-voyage · E forecast error |

**§7 has still not been read end to end since 09-13.** Its second mechanism was replaced on 10-01;
nothing else in it has been checked against the paper it now sits in.

---

## 6. Decisions made during the session

| # | Decision | Outcome | Follow-up |
|---|---|---|---|
| | | | |

## 7. Actions assigned

| # | Action | Owner | Due |
|---|---|---|---|
| | | | |

## 8. Live log — 2026-10-07 session

_Items as they come up._

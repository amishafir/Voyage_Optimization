# Design — merge Appendices A and B into one, against Tal's §3 of 2026-10-05

**Origin:** logged 2026-10-01 as item 3 of that session.
**Re-designed 2026-10-06** after merging `e809698` and `9f1f8af`, which rewrote §3 and changed what
the appendices are *for*.
**Status:** design only. Nothing applied.

---

## 1. Tal's rewrite turned a tidying job into a structural one

The merge was logged as housekeeping: two appendices that are one model. His §3 makes it necessary
rather than merely neat, for two reasons found while re-reading it.

### 1.1 The body no longer contains still-water speed at all

§3 now defines one function and takes it as given:

> We denote by $\phi(t,d;v)$ the FCR of the vessel when it is at distance $d$ at time $t$ and steams
> at **SOG** $v$, that is, the FCR function evaluated at the bearing at $d$ and at the sea conditions
> prevailing at $(t,d)$.

$\phi$ consumes **speed over ground**. The still-water speed, the speed correction and the inversion
are all *interior* to it. The body states the optimisation entirely in terms of $\phi$ and never
mentions SWS.

So the two appendices are no longer "a speed model and a fuel model". They are **the two halves of one
evaluation of $\phi$**: invert the correction to get the SWS a target SOG requires, then apply the
cubic to get the rate.

### 1.2 Appendix A is orphaned — nothing in the body points to it

Verified by `grep`. Every reference to `app:sog` now sits *inside the appendix*:

| Label | References | From |
|---|---|---|
| `app:sog` | 2 | **both from Appendix B** (lines 1287, 1379). **Zero from the body** |
| `app:fcr` | 6 | 2 from §3 (264, 303), 2 from Appendix A (1249, 1276), 2 from Appendix C (1394, 1410) |

A reader reaches Appendix A only by being sent there from Appendix B. Before the rewrite §3 pointed
at it five times; Tal's version points at it never, because there is no SWS in the body to need it.

**The two appendices also cross-reference each other four times** — A cites B twice, B cites A twice.
Merging removes all four.

---

## 2. The merged appendix

### 2.1 Title and framing

**"The fuel-consumption-rate function $\phi$"**, parallel to Appendix C, *The benchmark's
fuel-consumption model*. Ours and theirs, side by side, named the same way.

It opens on what §3 left open — §3 takes $\phi$ as an exogenous input; this appendix says how it is
evaluated — and states the two steps before either is given:

> Section~3 takes $\phi(t,d;v)$ as an exogenous input: given the bearing and the sea conditions at a
> point, it returns the rate at which fuel is burned to hold a speed over ground $v$. This appendix
> records how that rate is obtained, in two steps. The conditions first determine the still-water
> speed the vessel must make to hold $v$ over the ground; that still-water speed then determines the
> fuel rate through a cubic law. Neither step is a contribution of this paper; both follow
> \citet{yang2020}.

That paragraph is the whole justification for the merge: **one input, one output, two steps.**

### 2.2 Structure — flat, five subsections

Consistent with the §5 flattening: one level of numbering, no subsubsections.

| | Subsection | Label | From |
|---|---|---|---|
| A.1 | From speed over ground to still-water speed | `app:sog` | old Appendix A, body |
| A.2 | The DTU–SDU power chain | `app:fcr-chain` | old B.1 |
| A.3 | Reduction to the cubic form | `app:fcr-cubic` | old B.2 |
| A.4 | Calibration of the coefficient | `app:fcr-calib` | old B.3 |
| A.5 | Assumptions and validity range | `app:fcr-assumptions` | old B.4 |

The two-step grouping lives in the opening paragraph rather than in a second level of headings: A.1 is
the first step, A.2–A.4 the second, A.5 covers both.

### 2.3 Labels — the section carries `app:fcr`

`app:fcr` has **six** incoming references, two of them from §3, and must land on the merged section.
`app:sog` survives as A.1's label so nothing breaks, but **its two references should be deleted rather
than retargeted**: both are now sentences in the same appendix pointing at another part of it.

| Current text | Becomes |
|---|---|
| A: *"Like the fuel-consumption-rate function of \ref{app:fcr}, it is an input to the formulation"* | absorbed into the opening paragraph |
| A: *"through the convex fuel law of \ref{app:fcr}, disproportionately more fuel"* | *"through the convex fuel law of A.3"* — or plain prose, since it is now two subsections down |
| B: *"the separate mapping from SWS to speed over ground … is the speed-correction model of \ref{app:sog}"* | **delete** — the merged opening already said it |
| B: *"it enters by changing the SWS required to hold a given SOG (\ref{app:sog})"* | *"…required to hold a given SOG (A.1)"* |

### 2.4 Re-lettering is automatic, with two places to read

A (merged) · B benchmark ANN · C per-voyage · D forecast error.

Nothing in the body hard-codes a letter — every reference goes through `\ref` and `elsarticle`
expands it to the full designation. **But three sentences name an appendix in prose beside the
reference** and must be read rather than trusted: §3 line 264, §3 line 303, and Appendix C's opening.

---

## 3. Two inconsistencies to fix while the appendix is open

Both are drift between Tal's new §3 and the older appendix text.

### 3.1 Bearing against heading — **the one that matters**

Tal's §3 says **bearing** throughout: *"the bearing depends on $d$ alone"*, *"evaluated at the bearing
at $d$"*, *"it ends either at a waypoint, where the bearing changes"*. The appendix says **heading**:
*"the wind angle relative to the heading"*, *"the angle between the current and the heading"*.

Counted: **7 bearings, 15 headings**, split along exactly that line — §3 says bearing, the appendices
and §4 say heading.

They denote the same thing here, since the vessel follows a rhumb line, so this is terminology and not
a modelling disagreement. **But $\phi$ is defined in §3 as evaluated "at the bearing at $d$" and
computed in the appendix "relative to the heading", so a reader meets two words for the input of one
function.** Pick one. Tal chose bearing in the text he just wrote, which is the argument for bearing.

### 3.2 `subsegment` against `sub-segment`

17 against 4. Mechanical.

---

## 4. Order of work

1. Merge the two sections; the merged one takes `app:fcr`, A.1 keeps `app:sog`
2. Write the opening paragraph; delete the four now-internal cross-references
3. Fix bearing/heading one way throughout, and the subsegment spelling
4. Rebuild; confirm no undefined references and that the three prose mentions still read correctly
5. Check the three other appendices re-lettered as expected

---

## 5. Open items

| # | Item | Default |
|---|---|---|
| 1 | Title: *The fuel-consumption-rate function $\phi$*, or plainer *The fuel model*? | **The former** — it names the object §3 actually defines |
| 2 | Bearing or heading? | **Bearing**, following the §3 Tal just wrote |
| 3 | Keep `app:sog` as a label at all, given both its references are being deleted? | **Keep** — costs nothing, and §4 may want it back |
| 4 | Should A.5 *Assumptions* also cover the speed-correction step, which currently has none stated? | **Flag to the author.** The cubic has an explicit validity range; the correction model does not, and after the merge that asymmetry is visible in one section |

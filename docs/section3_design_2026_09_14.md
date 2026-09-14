# Design — rewrite of §3 *Problem formulation*

**Target file:** `paper_workspace/paper_full_draft.tex`
**Baseline:** working tree clean at `4c73c06` (tex content identical to `24aef7c`), 1486 lines,
32-page PDF, builds clean.
**Author of design:** research agent, 2026-09-14. Everything below is verified against the file and
against `docs/meeting_agenda_2026_09_14.md`.

> **Scope guard.** §4 (Methods, lines 413–748) is **not modified** by any edit in this design.
> §5 onward, the abstract and the introduction are **not touched**. §2 is not touched (one optional
> consistency edit is listed in §6 (open items) as an author decision, not as an edit to apply).
> The appendix **is** in scope — the brief instructs appendix moves.

---

## 1. The resulting §3 — what it says, in order, and how long

§3 becomes **flat prose with run-in `\paragraph{}` headings and ZERO `\subsection{}`** (the constraint
allows at most one; we use none). The two current subsections, `Speed over ground` (`sec:sog`) and
`Fuel and objective` (`sec:objective`), both disappear: the first moves to a new appendix, the second
collapses into the flowing text.

| # | Block | Form | Content |
|---|---|---|---|
| 1 | Opening paragraph | prose | Deterministic problem first, stochastic extension after; what this section will do. Last two sentences rewritten to announce the new flow (inputs → decision variable → objective → benchmark → shared fuel interface → the difference) and to say that the physics lives in the appendices. |
| 2 | Inputs | `description` list, 4 items | **Route** (unchanged), **T** (unchanged), **Sea conditions** (trimmed: the 0.08°/5 NM grid-resolution explanation is removed, it belongs to §5.1.3 `sec:sampling` where it already exists with the correct 4.8 NM figure), **FCR function** (unchanged plus a pointer to the new speed-correction appendix). |
| 3 | Decision variable | prose + `eq:speed-set` | Unchanged text through Eq. (1). Then the plan definition is rewritten: speed may change at a **sub-segment boundary and at a six-hour block boundary**, and a plan is the list of those intervals with the SOG held in each. This sentence is what the containment argument rests on. |
| 4 | `\paragraph{Still-water speed and speed over ground.}` | prose, 3 sentences | Only the two facts §3 uses: $V_g$ monotone in $V_s$ so $g^{-1}$ exists, and required SWS rises as conditions worsen. Everything else → Appendix A. |
| 5 | `\paragraph{Objective.}` | prose + `eq:legfuel` + `eq:obj` | Leg fuel, the programme, the hard arrival constraint, the band, the zero-speed carve-out. |
| 6 | `\paragraph{The convexity mechanism.}` | 2 sentences | Fuel depends on SWS, the plan targets SOG, holding a target SOG through varying weather forces SWS to vary, the convex FCR penalises that variation. |
| 7 | `\paragraph{The stochastic version.}` | 1 paragraph | The two current stochastic paragraphs (lines 273 and 317) are merged into one. |
| 8 | `\paragraph{The benchmark formulation.}` | prose + footnote | `luo2024`: segments aligned to the NWP forecast cycle $\Delta t$; speed constant within a segment; multistage graph over **remaining distance** discretised by $\zeta$; edges between adjacent stages only; edge ↔ speed; shortest path; re-solved every cycle, first speed committed. **The disclosure footnote hangs here.** |
| 9 | `\paragraph{The fuel model is an interface.}` | prose + `fig:fcr-blackbox` | Both formulations obtain FCR through the same interface: position + time select the conditions, the model returns a rate for a chosen speed. Ours = `yang2020` resistance decomposition (Appendix `app:fcr`, speed correction `app:sog`); theirs = $f_{\mathrm{ANN}}(v,w,u)$ (Appendix `app:fcr-luo`). Says explicitly that **both formulations are run on the same fuel model** so that granularity is not confounded with fuel estimation. TikZ figure. |
| 10 | `\paragraph{How the two formulations differ.}` | prose | The main point. *They decide only on time; we decide on time **and** on conditions.* Decision points **nested, not disjoint**. Block-locked plan = one of our plans that repeats a value across each block ⇒ admissible-set containment ⇒ no worse objective under equal conditions. Forward pointer to `sec:nesting`. Explicit honesty clause: a conditions boundary is a point **where a value was sampled**, i.e. "wherever the conditions are resolved by the data", pointing to `sec:sampling`. |

**Length.** §3 today is 74 rendered source lines (≈ 2.0 PDF pages) plus a 90-line `comment` block that
renders nothing. §3 after the rewrite is ≈ 135 source lines ≈ **2.5–3.0 PDF pages**, of which roughly
a third of a page is the TikZ figure. The appendix grows by two sections, ≈ 1.0–1.5 pages. Net
expected PDF: **33–35 pages** (from 32). Cross-check: the agenda records 34 pages for the reverted
draft that contained a comparable black-box paragraph, figure and second fuel appendix.

---

## 2. Decisions this design makes (and why)

### 2.1 The containment problem — **option (a)** is adopted

`\subsection{Containment of block-locked formulations}` / `\label{sec:nesting}` stays exactly where it
is, at lines 729–747 inside §4.

**Verified reference count for `sec:nesting`: 5, not 6** (the agenda says six). The five are at lines
**914** (§5.2.1 `\paragraph{Containment.}`), **974** (§6.1), **1102** (§6.2), **1259** (§7.1),
**1299** (§7.3). Command used:

```bash
grep -n 'ref{sec:nesting}' paper_workspace/paper_full_draft.tex   # → 914, 974, 1102, 1259, 1299
```

**Why (a).** It is the only option that satisfies hard constraint 2 *and* leaves §3 able to state the
optimisation problem and its relation to the benchmark on its own. Option (b) is cleaner on paper but
deletes a subsection from §4, which is exactly what constraint 2 forbids. Option (c) is rejected
because §6.1, §6.2, §7.1 and §7.3 all read the perfect-foresight ordering as a *consequence*, and if
§3 introduces the two formulations without saying their admissible sets are nested, §3 sets up a
comparison it then declines to characterise.

**The cost of (a) — the point is made twice — is contained by construction.** §3's version is
*informal and at the level of the admissible set* (one sentence: a block-locked plan is one of our
plans that repeats a value across each block, so our set contains theirs), and it ends with an
explicit hand-off, "Section~\ref{sec:nesting} states this containment precisely". §4's version is the
formal statement with its three conditions (i)–(iii) and the two consequences. That is a legitimate
informal-then-formal pairing, not a duplication.

> **Option (b) is fully specified in §4 of this document as `EDIT-OPT-B`, and it VIOLATES HARD
> CONSTRAINT 2 (it modifies §4). It is NOT to be applied without the author's explicit approval.**

### 2.2 The disclosure — a footnote in §3, on the benchmark paragraph

The disclosure has to go into §3 or nowhere: §5 (`sec:planners`, where the arc cost is described) and
§6 are out of bounds. A footnote is the right instrument — it keeps a fidelity note out of the line of
argument while putting it on the first page where the benchmark is defined, so no reader can reach the
results without having passed it.

It is written as a **statement of what our benchmark implementation does that the published method
does not require**, and it closes by naming the direction of the bias. It does not contain the words
*error*, *discrepancy*, *unfortunately* or *however*. Exact text in `EDIT-6`.

It is consistent with the untouched §5.2.1, which already says of the baseline: *"The arc cost is
obtained by walking the sub-segments within the block and summing fuel at that fixed block SOG."*

### 2.3 What stays in §3

`eq:speed-set` (**10 incoming references, verified**), `eq:legfuel`, `eq:obj`, the arrival constraint
and the convexity sentence. Test applied throughout: *a reader must be able to state the optimisation
problem from §3 alone*. Satisfied — Eqs. `speed-set`, `legfuel`, `obj` and the definition of a plan are
all in §3; the appendices are needed only to know how the two black boxes are built.

### 2.4 The honesty clause on "changes in the sea conditions"

§3 says **"wherever the conditions are resolved by the data"** and immediately defines a conditions
boundary as *a point at which a value was sampled*, pointing to `sec:sampling`. The per-route sampling
intervals (25.0 NM / 5.0 NM against ~4.8 NM source grids) are **not** repeated in §3 — they are
instance parameters and already stated once, correctly, in §5.1.3. §3 states the *kind* of claim, §5
states the numbers. This is the phrasing corrected in `24aef7c` and it is not reintroduced.

---

## 3. Cross-reference impact table (all counts verified by grep on the baseline file)

Verification command used for each label:

```bash
cd paper_workspace
for L in eq:speed-set sec:problem app:fcr sec:sog eq:legfuel sec:objective eq:sog eq:obj \
         sec:nesting sec:mechanism ; do
  printf '%-16s refs=%s  def=%s\n' "$L" \
    "$(grep -o "ref{$L}" paper_full_draft.tex | wc -l | tr -d ' ')" \
    "$(grep -n "label{$L}" paper_full_draft.tex | cut -d: -f1 | tr '\n' ',')"
done
```

| Label | Defined at | Incoming refs (baseline) | Where those refs are | Disposition | Why nothing breaks |
|---|---|---|---|---|---|
| `eq:speed-set` | 263 (§3) | **10** | 310 (§3, inside the region being rewritten), 421/482/505/507/539/686/700 (§4), 886/890 (§5) | **STAYS in §3**, definition untouched by any edit | The one in-region reference at line 310 is reproduced verbatim in the new objective paragraph (`EDIT-6`). Final count remains 10. §4 and §5 untouched. |
| `sec:problem` | 249 (§3) | 5 | 141 (intro), 416/427 (§4), 1261 (§7), 1379 (appendix) | stays, unchanged | Section header and label untouched. |
| `app:fcr` | 1376 (appendix) | 3 *grep hits*, of which **2 are real**: 257 (§3 description list) and 296 (§3.2, deleted region). The third, line 321, is inside a `%` LaTeX comment and was never a reference. | — | unchanged appendix; §3 keeps line 257's reference and adds four more (`EDIT-4`, `EDIT-6` prose, figure caption, Appendix A, Appendix C) | Definition untouched; reference count only increases. |
| `sec:sog` | 276 (§3.1) — also at 358 inside the dead `comment` block, which LaTeX never sees | **2** | **1383 and 1475, both inside Appendix `app:fcr` itself** — verified: `\appendix` is at line 1373, so both refs are at appendix level. Nothing outside the appendix points at it. | **Label retired.** The text moves to new Appendix A, which takes the new label `app:sog`; the two appendix references are retargeted (`EDIT-9`, `EDIT-10`). | Retargeting is cleaner than carrying `sec:sog` into an appendix: both call sites say the literal word "Section", which would render as "Section A" for an appendix. After `EDIT-9`/`EDIT-10` they read "Appendix~A". **`sec:sog` must appear nowhere in the file afterwards.** |
| `eq:legfuel` | 299 (§3.2) — also 394 inside the dead comment block | **1** | 1476 (Appendix `app:fcr`, assumption 3) | **STAYS in §3**, re-emitted verbatim in `EDIT-6` | Same label, same section, definition survives the region rewrite. |
| `eq:obj` | 305 (§3.2) — also 404 in the dead block | **0** | — | **STAYS in §3**, re-emitted in `EDIT-6`; now gains 1 reference from the new "How the two formulations differ" paragraph | A previously unreferenced equation becomes referenced. No risk. |
| `eq:sog` | 282 (§3.1) — also 371 in the dead block | **0** | — | **MOVES to Appendix A**, label preserved; gains 2 references inside Appendix A | Zero incoming references means the move is free. |
| `sec:objective` | 293 (§3.2) | **0** | — | **DELETED**, not recreated | Zero incoming references. |
| `sec:nesting` | 730 (§4) | **5** (not 6) | 914, 974, 1102, 1259, 1299 | **UNCHANGED — §4 not modified.** Gains 1 new reference from §3 ⇒ 6 after the rewrite | Definition never moves. This is the point of choosing option (a). |
| `sec:mechanism` | **nowhere — undefined** | 2 *grep hits*, both at lines 380 and 391, **both inside the dead `comment` block** | — | Both hits vanish with `EDIT-1` | The block is discarded by the `comment` package before LaTeX sees it, so this is not currently a broken reference; deleting the block removes a latent one. Net cleanup. |
| `tab:ship` | 1391 (appendix) | 2 real (1389, 1455) + 1 inside the dead comment block (line 328) | — | unchanged | The dead duplicate `\label{tab:ship}` at line 331 also disappears with `EDIT-1`. |
| `sec:sampling` | 834 (§5.1.3) | 1 (line 878) | — | unchanged; §3 adds 3 references | §5 not modified; only new incoming references. |
| **`app:sog`** | **NEW**, Appendix A (`EDIT-8`) | — | — | created | 4 incoming after the edits: `EDIT-4` (§3 FCR item), `EDIT-6` (§3 SWS/SOG paragraph and black-box paragraph), `EDIT-9`, `EDIT-10` (appendix). |
| **`app:fcr-luo`** | **NEW**, Appendix C (`EDIT-11`) | — | — | created | 2 incoming: `EDIT-6` black-box paragraph, figure caption. |
| **`fig:fcr-blackbox`** | **NEW**, in §3 (`EDIT-6`) | — | — | created | 1 incoming: `EDIT-6` black-box paragraph. |

**Duplicate-label note.** The baseline file defines `sec:sog`, `eq:sog`, `eq:legfuel`, `eq:obj` and
`tab:ship` **twice** — once live, once inside `\begin{comment}…\end{comment}`. The `comment` package
discards its body at the input level, so LaTeX currently sees only one of each and emits no
"multiply defined" warning. `EDIT-1` removes the shadow copies permanently. After the full edit set,
each label is defined exactly once.

---

## 4. The edits, in application order

**Apply in the order given.** `EDIT-1` is a line-range deletion and must be applied **first**, against
the pristine 1486-line file, because it is the only edit specified by line number. Every edit after it
is anchored on literal text and is therefore order-independent among themselves.

### EDIT-0 — baseline verification (run before anything)

*Rationale: guarantees the line numbers in `EDIT-1` refer to the file this design was written against.*

```bash
cd /Users/ami/Desktop/thesis/Voyage_Optimization/paper_workspace
git status --short paper_full_draft.tex          # must print nothing (clean tree)
wc -l paper_full_draft.tex                       # must print 1486
sed -n '273p' paper_full_draft.tex | cut -c1-60  # must start: In the stochastic version of the problem,
sed -n '322p' paper_full_draft.tex               # must be exactly: \begin{comment}
sed -n '411p' paper_full_draft.tex               # must be exactly: \end{comment}
sed -n '412p' paper_full_draft.tex               # must be the "4. METHODS" banner comment
```

If any check fails, **stop** and re-derive the line numbers.

---

### EDIT-1 — delete the old §3 tail and the dead `comment` block

**File:** `paper_workspace/paper_full_draft.tex`
**Rationale:** removes, in one operation, (i) the first stochastic paragraph, (ii) `\subsection{Speed
over ground}`, (iii) `\subsection{Fuel and objective}`, (iv) the second stochastic paragraph, and
(v) the 90-line dead `comment` block with its explanatory header. All of this is either relocated by
later edits or deliberately dropped. This is the only edit specified by line number.

```bash
cd /Users/ami/Desktop/thesis/Voyage_Optimization/paper_workspace
sed -i '' '273,411d' paper_full_draft.tex     # macOS/BSD sed
wc -l paper_full_draft.tex                    # must now print 1347
sed -n '271,274p' paper_full_draft.tex
#   271 → "so the vessel never idles in mid-ocean, ..."
#   272 → (blank)
#   273 → %% ============================================================ 4. METHODS
#   274 → \section{Methods}
```

*(GNU sed: `sed -i '273,411d' paper_full_draft.tex`.)*

**Deleted line inventory (139 lines):** 273 (stochastic ¶ #1); 274 blank; 275–291 `\subsection{Speed
over ground}` incl. `\label{sec:sog}` and `eq:sog`; 292–317 `\subsection{Fuel and objective}` incl.
`\label{sec:objective}`, `eq:legfuel`, `eq:obj`, the convexity sentences and stochastic ¶ #2; 318
blank; 319–321 the three `%` explanatory comment lines; 322–411 `\begin{comment}…\end{comment}`.

---

### EDIT-2 — preamble: load TikZ

**File:** `paper_workspace/paper_full_draft.tex`
**Rationale:** `fig:fcr-blackbox` needs `tikz`; the arrow tips need `arrows.meta`; `positioning` is
loaded because it is the conventional companion and costs nothing. Neither is currently loaded
(`grep -n 'tikz\|pgf' paper_full_draft.tex` returns nothing on the baseline).

`old_string`
```
\usepackage{comment}
\usepackage[margin=1in]{geometry}
```

`new_string`
```
\usepackage{comment}
\usepackage{tikz}
\usetikzlibrary{arrows.meta,positioning}
\usepackage[margin=1in]{geometry}
```

---

### EDIT-3 — §3 opening paragraph: announce the new flow

**Rationale:** the old closing sentences promise "the method by which the fuel consumption is
calculated" and "the physical aspects of a sea voyage", both of which now live in the appendices.
The replacement announces the section's actual contents.

`old_string`
```
In this section we describe the input of the problem and the method by which the fuel consumption is calculated. This description requires some understanding of the physical aspects of a sea voyage, which we briefly provide here.
```

`new_string`
```
In this section we describe the input of the problem, the decision variable and the objective. We then describe the benchmark formulation of \citet{luo2024}, state the sense in which both formulations obtain the fuel consumption rate from the same kind of black box, and set out the single structural difference between them. The physical models behind that black box are inputs to the formulation rather than part of it, and are given in the appendices.
```

> Note for the implementer: the source line ends with a single trailing space after `here.` The
> anchor above stops at `here.`, so the trailing space is preserved. Do not try to match it.

---

### EDIT-4 — §3 inputs list: trim *Sea conditions*, extend *FCR function*

Two independent replacements inside the `description` list.

**EDIT-4a — trim the grid-resolution explanation out of *Sea conditions*.**
*Rationale: the discretisation belongs with the partition in §5.1.3, where it already appears with the
verified 4.8 NM figure; §3's "roughly 5 NM" is a second, looser statement of the same fact.*

`old_string`
```
(Section~\ref{sec:methods}). The weather and forecast services used in this study deliver their fields on native grids of about $0.08\degree$; recall that a degree of latitude is 60 NM (111 km) everywhere, while a degree of longitude is 60 NM at the equator and shrinks with the cosine of the latitude, so $0.08\degree$ is roughly 5 NM on the routes studied here. That resolution bounds the spatial detail the data can resolve; the sampling interval actually used along each route is an experimental parameter and is reported in Section~\ref{sec:data}.
```

`new_string`
```
(Section~\ref{sec:sampling}). A subsegment boundary is therefore a point at which a value was actually sampled, not a point at which the ocean is known to change: the resolution of the partition is the resolution of the data. The interval at which the conditions were sampled along a route is a property of the data collection rather than of the formulation, and is reported in Section~\ref{sec:sampling}.
```

**EDIT-4b — point the *FCR function* item at the new speed-correction appendix.**
*Rationale: §3 no longer contains the SWS↔SOG correction, so the input description must say where it
went.*

`old_string`
```
We use the method proposed by \citet{yang2020}, which is described in Appendix~\ref{app:fcr}.
```

`new_string`
```
We use the method proposed by \citet{yang2020}, whose fuel-consumption-rate function is derived in Appendix~\ref{app:fcr} and whose accompanying correction from still-water speed to speed over ground is given in Appendix~\ref{app:sog}.
```

---

### EDIT-5 — §3: what a speed plan is

**Rationale:** this is the load-bearing sentence for the containment argument. The old text names only
sub-segments; the decision points are sub-segment boundaries **∪** six-hour block boundaries, and §3
must say so or the nesting claim in `EDIT-6` is unsupported. It also fixes the typo "the course and
and the sea conditions".

`old_string`
```
so the vessel never idles in mid-ocean, and once it has reached $d=D$ it cannot move again.   The voyage can be divided into sub-segments during which the course and and the sea conditions are fixed.  Due to the convexity of the FCR function,  in an optimal solution the SOG is fixed during each such sub-segment.  Therefore, a solution can be described by a list of sub-segments and the SOG in each one of them.
```

`new_string`
```
so the vessel never idles in mid-ocean, and once it has reached $d=D$ it cannot move again. The voyage can be divided into intervals during which the course, the sea conditions and the time block are all fixed; an interval ends where the vessel crosses a subsegment boundary or where a six-hour block turns over, and at no other point. Because the FCR is a convex function of the speed, in an optimal solution the SOG is constant on each such interval. A speed plan is therefore a list of these intervals together with the SOG held in each, and the points at which a plan may change speed are exactly the subsegment boundaries and the six-hour block boundaries.
```

---

### EDIT-6 — §3: the new tail (objective, mechanism, benchmark, black box, difference)

**Rationale:** this is the new writing. It is inserted immediately before the §4 banner, which
`EDIT-1` left as the next thing in the file. The anchor is the two-line §4 header; those two lines are
reproduced **unchanged** at the end of `new_string`, so §4 is not modified — this is a pure insertion
in front of it.

`old_string`
```
%% ============================================================ 4. METHODS
\section{Methods}
```

`new_string`
```
\paragraph{Still-water speed and speed over ground.}
Fuel is burned to produce the vessel's \emph{still-water speed} (SWS) $V_s$, the speed it would make
in calm water at a given power setting, while a plan is expressed in speed over ground. The two are
linked by a speed-correction model, $V_g=g(V_s;w)$, in which the wind reduces the speed made good and
the along-track component of the current adds to or subtracts from it; the model is that of
\citet{yang2020} and is given in Appendix~\ref{app:sog}. Only two of its properties are used here.
For fixed conditions $V_g$ increases monotonically with $V_s$, so the relation inverts and a target
SOG implies a unique required SWS, written $V_s=g^{-1}(V_g;w)$; and that required SWS rises as the
conditions worsen, so holding a target SOG through adverse weather demands more still-water speed.

\paragraph{Objective.}
The fuel burned on an interval $i$ of length $d_i$, sailed at a constant SOG $V_{g,i}$ under
conditions $w_i$, is the fuel-consumption rate times the transit time,
\begin{equation}
\label{eq:legfuel}
F_i \;=\; \fcr\!\big(g^{-1}(V_{g,i};w_i)\big)\,\frac{d_i}{V_{g,i}} .
\end{equation}
Writing $M$ for the number of intervals, the deterministic speed-control problem is to choose the SOG
of each interval so as to minimise total voyage fuel subject to the arrival deadline,
\begin{equation}
\label{eq:obj}
\min_{\{V_{g,i}\in[V_{\min},V_{\max}]\}}\; \sum_{i=1}^{M} \fcr\!\big(g^{-1}(V_{g,i};w_i)\big)\,\frac{d_i}{V_{g,i}}
\qquad\text{s.t.}\qquad \sum_{i=1}^{M}\frac{d_i}{V_{g,i}} \le T .
\end{equation}
The arrival constraint is hard and the SOG of every interval is confined to the band
$[V_{\min},V_{\max}]$; the zero-speed option that Eq.~\eqref{eq:speed-set} admits at the two ends of
the route covers no distance and so contributes no term to the sum, it only consumes part of the time
budget $T$ at the origin or at the destination.

\paragraph{The convexity mechanism.}
Fuel depends on the still-water speed while a plan targets the speed over ground, so holding one
target SOG through changing conditions forces the required SWS to vary along the way. Because the FCR
is strictly convex in SWS, that induced variation costs fuel relative to a plan that resets the target
as the conditions change, and the coarser the interval over which a single target is held, the more of
that penalty a plan incurs; this is the mechanism the rest of the paper exploits
(Section~\ref{sec:methods}).

\paragraph{The stochastic version.}
In the stochastic version of the problem the sea conditions at each location and time along the
planned voyage are unknown, and the only information about them is a published weather forecast, given
on the same discretisation as the conditions themselves and refreshed periodically. Speed decisions
are made from the conditions observed so far and from the most recent forecast, and the planner's goal
is to minimise the fuel consumed over the voyage; no probabilistic information about the relationship
between a forecast and the realisation that follows it is available to the planner. In this study the
stochastic version is solved in a rolling-horizon framework that uses the solution method for the
deterministic problem as a building block.

\paragraph{The benchmark formulation.}
The state of the art for fuel-minimising speed control under dynamic meteorological conditions is the
multistage-graph formulation of \citet{luo2024}, which we adopt as our benchmark. It divides the
voyage into segments aligned to the cycle on which the numerical weather prediction product is
refreshed, one segment per cycle of length $\Delta t$, with the first and the last segment partial,
and it assumes that the sailing speed remains unchanged during any one segment of the voyage. The
voyage is then represented as a multistage graph in which the nodes of stage $i$ are indexed by the
distance still remaining to the destination, discretised on a distance quantum $\zeta$, and in which
edges join nodes of adjacent stages only. The two remaining distances that an edge connects, together
with the fixed duration $\Delta t$ of the segment it spans, determine the speed at which that edge is
traversed, so choosing an edge \emph{is} choosing that segment's speed; the weight of the edge is the
fuel required to cover the segment at that speed.\footnote{\citet{luo2024} price a segment with a
single meteorological sample, taken at the segment's starting node and assumed to represent the whole
segment. The implementation of the benchmark used here is more generous than that: it walks each
segment at subsegment and sample-hour resolution and prices every piece against the conditions
prevailing at that position and that time, holding only the \emph{speed} constant across the segment.
Both formulations compared in this paper are therefore costed against sea-conditions data of the same
resolution, and the benchmark is evaluated on strictly more weather information than its published
description requires. Any advantage reported here for the finer formulation is measured against a
benchmark so strengthened.} The plan is the minimum-weight path through this graph, found by shortest
path, and in operation the graph is rebuilt and re-solved at each forecast cycle on the latest
forecast, with only the first segment's speed committed before the vessel advances, which is a rolling
horizon in their own terms. Their objective and their arrival requirement are those of
Eq.~\eqref{eq:obj}; what differs is the set of plans the formulation admits.

\paragraph{The fuel model is an interface.}
Neither formulation contains a fuel model. Both obtain one through the same interface: a position
along the route and a time select the sea conditions prevailing there, and the model is then asked at
what rate fuel would be burned if the vessel held a chosen speed under those conditions
(Figure~\ref{fig:fcr-blackbox}). What lies inside is exogenous to the optimisation and does not enter
the formulation. In this paper the interface is implemented by the resistance decomposition of
\citet{yang2020}: the conditions determine the still-water speed required to hold the target SOG
(Appendix~\ref{app:sog}), and the still-water speed determines the fuel rate through a cubic law
(Appendix~\ref{app:fcr}). \citet{luo2024} implement the same interface with a learned model, a
feed-forward artificial neural network $f_{\mathrm{ANN}}(v,w,u)$ over the sailing speed $v$, six
meteorological variables $w$, and the draught and loading condition $u$, trained on ship noon reports
fused with ECMWF ERA5 reanalysis; it is described in Appendix~\ref{app:fcr-luo}. Because the question
of this paper is when the speed may change and not how fuel is estimated, both formulations are run on
the same fuel model throughout, the one of Appendix~\ref{app:fcr}; giving each formulation its own
would confound the granularity of the speed decision with the error of the fuel model.

\begin{figure}[H]
\centering
\begin{tikzpicture}[
  >={Stealth[length=2.2mm]},
  inp/.style={draw, rounded corners=2pt, align=center, font=\small, inner sep=4pt},
  bbx/.style={draw, thick, fill=black!8, align=center, font=\small, inner sep=6pt,
              minimum width=42mm, minimum height=16mm},
  out/.style={draw, rounded corners=2pt, align=center, font=\small, inner sep=4pt}
]
\node[inp] (where) at (0,1.15)  {position $d$ and time $t$\\[1pt]\scriptsize select the sea conditions $w$};
\node[inp] (speed) at (0,-1.15) {chosen speed $v$};
\node[bbx] (model) at (5.0,0)   {fuel-consumption-rate model\\[1pt]\scriptsize Appendix~\ref{app:fcr} or Appendix~\ref{app:fcr-luo}};
\node[out] (rate)  at (9.4,0)   {$\fcr$\;\;[mt/h]};
\draw[->] (where) -- (model);
\draw[->] (speed) -- (model);
\draw[->] (model) -- (rate);
\end{tikzpicture}
\caption{The fuel model as a black box. A position along the route and a time select the sea
conditions; given those conditions and a chosen speed, the model returns a fuel-consumption rate.
The formulation of this paper and the benchmark of \citet{luo2024} use the same interface and differ
only in what lies behind it, a resistance decomposition (Appendix~\ref{app:fcr}) in the first case and
a trained neural network (Appendix~\ref{app:fcr-luo}) in the second. All results reported in this
paper use the former for both formulations.}
\label{fig:fcr-blackbox}
\end{figure}

\paragraph{How the two formulations differ.}
The two formulations minimise the same objective, Eq.~\eqref{eq:obj}, subject to the same arrival
deadline and the same speed band, and both price fuel through the interface above. They differ in one
thing only: what triggers a speed decision. In \citet{luo2024} the trigger is the passage of time. A
new segment begins when the forecast cycle turns over and at no other moment, so the speed may change
once every $\Delta t$ hours and is then held through whatever the vessel meets in between. In the
formulation of this paper the speed may change when the time block turns over \emph{and} wherever the
sea conditions along the route are resolved by the data, that is at every point at which the
conditions were sampled, and therefore also at every change of heading, since the sampling points
include the control points of the route (Section~\ref{sec:sampling}). Resolution here means the
resolution of the data and not of the ocean: a conditions boundary is a point at which a value was
observed, and how often that happened is a property of the data collection, reported in
Section~\ref{sec:sampling}.

The decision points of the two formulations are therefore not different sets but nested ones. Every
boundary at which \citet{luo2024} may change speed is a boundary at which we may, and we have others
besides; a plan that is block-locked in their sense is one of our plans that happens to repeat a single
value across each block. The admissible set of the formulation of this paper accordingly contains the
benchmark's, so optimising over the larger set cannot yield a worse objective whenever both are
optimised against the same sea conditions. Section~\ref{sec:nesting} states this containment
precisely, with the conditions under which it holds, and draws the two consequences that
Sections~\ref{sec:res-oracle} and~\ref{sec:res-rh} rely on.

%% ============================================================ 4. METHODS
\section{Methods}
```

---

### EDIT-7 — Appendix A: the speed-correction model (new section)

**Rationale:** receives §3.1's `eq:sog`, the wind and current terms and the numerical inversion.
Inserted immediately after `\appendix` so that it becomes **Appendix A** and the existing FCR appendix
becomes **Appendix B** — the natural order, since `app:fcr` refers back to the speed correction.

`old_string`
```
\appendix

\section{Derivation of the fuel-consumption-rate function}
```

`new_string`
```
\appendix

\section{The speed-correction model}
\label{app:sog}

The problem of Section~\ref{sec:problem} is stated in terms of speed over ground, while fuel is burned
to produce still-water speed. This appendix records the correction that links the two. Like the
fuel-consumption-rate function of Appendix~\ref{app:fcr}, it is an input to the formulation and its
derivation is not a contribution of this paper.

The vessel's \emph{still-water speed} (SWS) $V_s$ is the speed it would make in calm water at a given
power setting; the \emph{speed over ground} (SOG) $V_g$ is $V_s$ modified by the environment, wind
reduces it, while the along-track component of the current adds to or subtracts from it. We follow the
resistance-correction model of \citet{yang2020}. The wind-induced speed loss
$\Delta V_{\text{wind}}$ depends on the Beaufort number, computed from the 10\,m wind speed
(Section~\ref{sec:data}), on the Froude number, and on a set of direction- and form-dependent
coefficients tabulated by \citet{yang2020}; it is piecewise constant in the wind angle relative to the
heading. The current contributes its along-track projection, $V_{c,\parallel}=V_c\cos\theta_c$, where
$\theta_c$ is the angle between the current and the heading. Combining the two terms gives the speed
over ground,
\begin{equation}
\label{eq:sog}
V_g \;=\; V_s - \Delta V_{\text{wind}}(V_s,w) + V_{c,\parallel},
\qquad V_g \ge 0,
\end{equation}
where $w$ denotes the local sea-conditions state and the individual resistance terms and their
coefficients are those of \citet{yang2020}.

Two properties of Eq.~\eqref{eq:sog} are used in the body of the paper. First, for fixed conditions
$V_g$ increases monotonically with $V_s$, so the relation is invertible: a target SOG implies a unique
required SWS, $V_s=g^{-1}(V_g;w)$. The inverse has no closed form, because $\Delta V_{\text{wind}}$
itself depends on $V_s$ through the Froude number, and is evaluated numerically by binary search on
$V_s$. Second, the required SWS rises as the conditions worsen: holding a target SOG through adverse
weather demands more still-water speed and hence, through the convex fuel law of
Appendix~\ref{app:fcr}, disproportionately more fuel. Together these are what make the granularity of
the speed decision matter at all.

\section{Derivation of the fuel-consumption-rate function}
```

---

### EDIT-8 — retarget the first appendix reference to `sec:sog`

**Rationale:** `sec:sog` is retired; the call site must name the new appendix. Also fixes the word
"Section" for a target that is now an appendix.

`old_string`
```
speed over ground under weather is the speed-correction model summarised in Section~\ref{sec:sog}.
```

`new_string`
```
speed over ground under weather is the speed-correction model of Appendix~\ref{app:sog}.
```

---

### EDIT-9 — retarget the second appendix reference to `sec:sog`

**Rationale:** as `EDIT-8`. This is the only other reference to the retired label.

`old_string`
```
given SOG (Section~\ref{sec:sog}). Fuel for a leg is then $\fcr(V_s)\,d_i/V_{g,i}$
```

`new_string`
```
given SOG (Appendix~\ref{app:sog}). Fuel for a leg is then $\fcr(V_s)\,d_i/V_{g,i}$
```

---

### EDIT-10 — Appendix C: the benchmark's fuel model (new section)

**Rationale:** receives the description of `luo2024`'s ANN promised by §3's black-box paragraph.
Inserted after the last subsection of `app:fcr` and before the bibliography, so it becomes
**Appendix C**.

`old_string`
```
%% ============================================================ REFERENCES
\bibliographystyle{elsarticle-harv}
```

`new_string`
```
\section{The benchmark's fuel-consumption model}
\label{app:fcr-luo}

The benchmark formulation of Section~\ref{sec:problem} obtains its fuel-consumption rate from a
learned model rather than from a resistance decomposition. It is recorded here because the black-box
interface of Figure~\ref{fig:fcr-blackbox} is what allows the two formulations to be compared at all;
it is not used to produce any number reported in this paper, since both formulations are run on the
fuel model of Appendix~\ref{app:fcr}.

\citet{luo2024} predict the fuel-consumption rate with a feed-forward artificial neural network,
$f_{\mathrm{ANN}}(v,w,u)$, in which $v$ is the sailing speed, $w$ collects six meteorological
variables, and $u$ is the pair formed by the draught and the loading condition, laden or ballast. The
meteorological inputs include the wind speed, the mean wave period, the significant height of combined
wind waves and swell, and the forecast surface roughness; the absolute wind and mean-wave directions
are converted into directions \emph{relative} to the vessel's true heading before they enter the
network. \citet{luo2024} report the feature list with its ranges and the layer structure of the
network.

The network is trained on a fusion dataset. The sailing features are taken from the vessel's noon
reports, and the meteorological features from the ECMWF ERA5 reanalysis, which replaces the weather
entries recorded on board; the authors identify those on-board entries as the least reliable part of a
noon report, which is the reason for the substitution.

Two differences from the model of Appendix~\ref{app:fcr} are worth recording once. First, the learned
model consumes the sea state directly, through significant wave height and mean wave period, whereas
the resistance decomposition of \citet{yang2020} carries the sea state only through the Beaufort
number. Second, a learned model is calibrated to the vessel and the operating envelope of its training
data, while a resistance decomposition is parameterised by principal particulars. Holding the fuel
model fixed across the two formulations, as this study does, removes both differences from the
comparison: what is compared is when the speed may change, not how the fuel is estimated. Giving each
formulation its own fuel model would be a different experiment.

%% ============================================================ REFERENCES
\bibliographystyle{elsarticle-harv}
```

---

### EDIT-OPT-B — **DO NOT APPLY WITHOUT THE AUTHOR'S APPROVAL**

> **This edit modifies §4 and therefore violates hard constraint 2.** It is specified here only so
> that, if the author prefers option (b) from the agenda, the change is mechanical rather than a
> redesign. Applying it is an author decision, not an implementer decision.

**What it does.** Deletes `\subsection{Containment of block-locked formulations}` from §4 and moves it,
label and all, into §3, immediately after the "How the two formulations differ" paragraph, demoted from
`\subsection` to `\paragraph` so that §3 stays flat.

**Consequence for cross-references:** none. `sec:nesting` travels with the text, so all 5 existing
references (lines 914, 974, 1102, 1259, 1299 of the baseline) resolve to §3 instead of §4. The
`\ref{}` renders a number, not a word, and all five call sites say "Section~\ref{sec:nesting}", which
remains correct for a §3 target.

**Step B1 — delete from §4.** `old_string` (lines 729–747 of the baseline, verbatim):

```
\subsection{Containment of block-locked formulations}
\label{sec:nesting}
A formulation that holds the speed constant over intervals of the voyage is a restriction of the
program above whenever its intervals are aligned with the grid. Concretely, suppose a competing
formulation (i) fixes a single SOG over each of a set of intervals whose endpoints are a subset of
the time lines of $\mathcal{S}$, (ii) draws that SOG from the same band $\mathcal{V}(d)$, and
(iii) resolves distance on the same quantum. Then every plan it admits is reproducible here: hold
its interval speed on every sub-arc inside that interval. The feasible set of the program above
therefore contains the competitor's, and its optimum is no worse, whenever both are optimised
against the same sea conditions.

Two consequences are used later. First, any fuel advantage measured under perfect foresight
(Section~\ref{sec:res-oracle}) is a property of the formulation rather than an empirical tendency;
what the experiment measures is its \emph{magnitude}. Second, the containment is stated with respect
to the conditions each program optimises against, so when both are given a \emph{forecast} rather
than the realised conditions, the guarantee applies to fuel evaluated against that forecast, and not
to fuel realised against the weather that actually occurs. Section~\ref{sec:res-rh} returns to this.
```

`new_string`: *(empty — delete the block and the blank lines around it, leaving one blank line)*

**Step B2 — reinsert in §3.** In `EDIT-6`'s `new_string`, replace the final sentence of the last
paragraph,

```
Section~\ref{sec:nesting} states this containment
precisely, with the conditions under which it holds, and draws the two consequences that
Sections~\ref{sec:res-oracle} and~\ref{sec:res-rh} rely on.
```

with the deleted §4 block, re-headed as

```
\paragraph{Containment of block-locked formulations.}
\label{sec:nesting}
```

followed by the two paragraphs of the §4 block verbatim, with `program above` changed to
`program of Section~\ref{sec:methods}` in both places and `the time lines of $\mathcal{S}$` changed to
`the six-hour time boundaries`, since $\mathcal{S}$ is not defined until §4.

**Cost of (b) beyond the constraint violation:** the lemma's conditions (i)–(iii) refer to the state
space $\mathcal{S}$ and the distance quantum, neither of which exists in §3. That is why this design
recommends **(a)**: option (b) is not a pure move, it requires rewording the lemma to survive being
stated before the state space is defined.

---

## 5. Verification checklist (run after applying EDIT-1 … EDIT-10)

### 5.1 Structural

```bash
cd /Users/ami/Desktop/thesis/Voyage_Optimization/paper_workspace

# 1. §4 was NOT modified. Every diff hunk must lie OUTSIDE baseline lines 413-748.
git diff -U0 paper_full_draft.tex | grep '^@@'
```

Read each hunk header `@@ -<start>,<len> +... @@`. The requirement is that **no hunk has
`start` in the range 413-748**, and that the only hunk whose `start` is below 413 and whose deleted
length reaches past it is `EDIT-1`'s deletion, which ends at line 411. Expected hunk starts:
22 (`EDIT-2`), 251 (`EDIT-3`), 256 (`EDIT-4a`), 257 (`EDIT-4b`), 271 (`EDIT-5`), 273 with length 139
(`EDIT-1`), 412 (`EDIT-6`, an insertion in front of the §4 banner), then three in the appendix
(`EDIT-7`, `EDIT-8`, `EDIT-9`, `EDIT-10`). **Nothing between 413 and 748.**

```bash
# 2. §3 is flat: zero subsections between \section{Problem formulation} and \section{Methods}
awk '/^\\section\{Problem formulation\}/{f=1} /^\\section\{Methods\}/{f=0} f' paper_full_draft.tex \
  | grep -c '\\subsection'           # MUST be 0  (constraint allows ≤ 1)

# 3. Run-in headings are present
awk '/^\\section\{Problem formulation\}/{f=1} /^\\section\{Methods\}/{f=0} f' paper_full_draft.tex \
  | grep -c '\\paragraph{'           # MUST be 7

# 4. The dead comment block is gone; the remaining four are §4's
grep -c 'begin{comment}' paper_full_draft.tex     # MUST be 4 (was 5)

# 5. Three appendix sections, in order A=speed correction, B=FCR, C=benchmark ANN
grep -n '^\\section{' paper_full_draft.tex | tail -3
#   → The speed-correction model / Derivation of the fuel-consumption-rate function /
#     The benchmark's fuel-consumption model

# 6. TikZ is loaded
grep -c 'usepackage{tikz}' paper_full_draft.tex   # MUST be 1
grep -c 'usetikzlibrary' paper_full_draft.tex     # MUST be 1
```

### 5.2 Labels — strings that must be ABSENT

```bash
grep -n 'sec:sog'      paper_full_draft.tex   # MUST return nothing (label retired)
grep -n 'sec:mechanism' paper_full_draft.tex  # MUST return nothing (was undefined, in dead block)
grep -n 'sec:objective' paper_full_draft.tex  # MUST return nothing (0 incoming refs, dropped)
grep -n 'course and and'  paper_full_draft.tex # MUST return nothing (typo fixed by EDIT-5)
grep -n '0.08.degree'  paper_full_draft.tex   # MUST return exactly 2 hits, BOTH in §5 (lines ~812-813)
grep -n 'Speed over ground}' paper_full_draft.tex  # MUST return nothing (no such subsection anywhere)
grep -n 'Fuel and objective' paper_full_draft.tex  # MUST return nothing
```

### 5.3 Labels — strings that must be PRESENT, with exact counts

```bash
for L in eq:speed-set eq:legfuel eq:obj eq:sog app:sog app:fcr app:fcr-luo fig:fcr-blackbox sec:nesting; do
  printf '%-18s def=%s refs=%s\n' "$L" \
    "$(grep -c "label{$L}" paper_full_draft.tex)" \
    "$(grep -o "ref{$L}" paper_full_draft.tex | wc -l | tr -d ' ')"
done
```

Expected:

| Label | `def` must be | `refs` must be | Note |
|---|---|---|---|
| `eq:speed-set` | 1 | **10** | unchanged from baseline; the in-§3 reference is re-emitted by `EDIT-6` |
| `eq:legfuel` | 1 | 1 | the shadow definition in the dead block is gone |
| `eq:obj` | 1 | 2 | was 0 refs; §3's difference paragraph and the benchmark paragraph now cite it |
| `eq:sog` | 1 | **1** | now lives in Appendix A and is cited once inside it (it had 0 references before the move) |
| `app:sog` | 1 | 5 | §3 ×3 (`EDIT-4b`, SWS paragraph, black-box paragraph), Appendix B ×2 (`EDIT-8`, `EDIT-9`) |
| `app:fcr` | 1 | **9** | §3 inputs list ×1, §3 black-box paragraph ×2, figure node ×1, figure caption ×1, Appendix A ×2, Appendix C ×2 — counted mechanically over the `new_string` blocks of this design |
| `app:fcr-luo` | 1 | 3 | §3 black-box paragraph, TikZ node, figure caption |
| `fig:fcr-blackbox` | 1 | 2 | §3 black-box paragraph, Appendix C |
| `sec:nesting` | **1, and it must be inside §4** | **6** | 5 baseline + 1 new from §3. Verify with `grep -n 'label{sec:nesting}'` → the line number must be inside the `\section{Methods}` … `\section{Data and experimental design}` range. |

### 5.4 Content strings that must be PRESENT (the load-bearing claims)

```bash
grep -c 'not different sets but nested ones'                 paper_full_draft.tex  # 1
grep -c 'the trigger is the passage of time'                  paper_full_draft.tex  # 1
grep -c 'resolution of the data and not of the ocean'         paper_full_draft.tex  # 1
grep -c 'strictly more weather information than its published' paper_full_draft.tex # 1  (disclosure)
grep -c 'confound the granularity of the speed decision'      paper_full_draft.tex  # 1
grep -c 'segments aligned to the cycle on which the numerical' paper_full_draft.tex # 1
```

### 5.5 Build

```bash
cd /Users/ami/Desktop/thesis/Voyage_Optimization/paper_workspace
latexmk -C && latexmk -pdf paper_full_draft.tex

grep -c 'Reference.*undefined'  paper_full_draft.log    # MUST be 0
grep -c 'Citation.*undefined'   paper_full_draft.log    # MUST be 0
grep -c 'multiply defined'      paper_full_draft.log    # MUST be 0
grep -c 'There were undefined'  paper_full_draft.log    # MUST be 0
grep -o 'Output written on.*'   paper_full_draft.log | tail -1
#   page count MUST be in 33–35  (baseline 32).  Outside that range, investigate before committing.
```

### 5.6 Visual checks in the built PDF

1. §3 has **no numbered subsection**; the headings inside it are bold run-in paragraph headings.
2. `Figure 1` (the black box) renders: two boxes on the left, one shaded box in the middle, one box on
   the right, three arrows left-to-right. **No `Overfull \hbox` warning on the figure.** If one
   appears, wrap the `tikzpicture` in `\resizebox{\textwidth}{!}{ … }` — no other change is needed.
3. The appendix letters read **A** = The speed-correction model, **B** = Derivation of the
   fuel-consumption-rate function, **C** = The benchmark's fuel-consumption model.
4. The footnote on the benchmark paragraph sets on the same page as the paragraph.
5. `Section~\ref{sec:nesting}` in §3 renders as the §4 subsection number (e.g. "Section 4.3").
6. A reader can state the optimisation problem from §3 alone: Eqs. `speed-set`, `legfuel`, `obj`, the
   band, the arrival constraint and the definition of a plan are all on those pages.

---

## 6. Open items — what the author must decide

| # | Item | Why it cannot be settled here | Default taken by this design |
|---|---|---|---|
| 1 | **Containment: option (a) or (b)?** | (b) modifies §4, which hard constraint 2 forbids. It also requires rewording the lemma, because its conditions (i)–(iii) refer to $\mathcal{S}$ and to the distance quantum, neither defined before §4. | **(a) applied.** §3 gets a one-sentence informal statement plus a forward pointer; §4 untouched. `EDIT-OPT-B` is written out and marked *do not apply without approval*. |
| 2 | **The disclosure is a footnote in §3.** Is that the right weight? | §5 and §6, where a fidelity note would more naturally sit, are out of bounds for this rewrite. | Footnote on the benchmark paragraph. If the author wants it in §6 instead, delete the footnote from `EDIT-6` and the §3 edits stand unchanged. |
| 3 | **§5.2.1's fidelity sentence is now incomplete.** It reads *"implemented independently from its published description … not as SR subject to an added equality constraint"*, which is true of the decision structure but silent on the cost evaluation the new footnote discloses. | §5 is out of bounds. | Not touched. Recommended follow-up once §5 reopens: append *"faithful to the decision structure and deliberately more generous on the cost evaluation (Section~\ref{sec:problem})"*. |
| 4 | **§2 forward pointer.** Line 174 says of the benchmark *"(we describe this baseline in detail in Section~\ref{sec:data})"*. After this rewrite the detailed description is in §3, and §5.2.1 keeps only the implementation. | §2 is outside the brief's scope though not protected. Nothing breaks either way — `sec:data` still contains a description of the baseline. | **Not edited.** If the author wants it, the one-line change is `Section~\ref{sec:data}` → `Section~\ref{sec:problem}` at line 174. |
| 5 | **Luo's speed band $[8,18]$ kn vs our $D/T\pm3$ kn.** The agenda wants a sentence so the bands are not read as arbitrary, and places it in §5.2. | §5 is out of bounds, and §3 states the band abstractly as $[V_{\min},V_{\max}]$, which is the right level for a formulation section. | **Omitted from §3.** Carry to the next §5 pass. |
| 6 | **Luo's segment-count formula** $n=\lfloor (T_{\max}-(T-\Delta t))/T\rfloor+1$. | Their $T$ is the forecast cycle; our $T$ is the ETA. Reproducing it in our notation would collide on $T$ and would need a symbol table for one line of arithmetic. | **Omitted.** §3 says only that the first and last segments are partial, which is the fact that matters for the decision structure. |
| 7 | **Citation granularity for Appendix C.** The agenda's citation map sends Appendix C to "their §3.1–3.3, Table 1, Fig. 1". The PDF bookmark structure shows §3 is *Data description* (3.1 noon report, 3.2 ERA5, 3.3 NOAA forecast) while the network itself is **their §4, *Development of ANN models for predicting ship fuel consumption***. | Neither `pdftotext` nor a Python PDF library is available in this environment, so exact page numbers could not be read. The bookmark titles were extracted and are quoted above. | Appendix C cites `\citet{luo2024}` without section numbers and says "report the feature list with its ranges and the layer structure of the network". **If the author wants explicit section numbers, they are their §3 for the data and their §4 for the network — not §3.1–3.3 alone.** |
| 8 | **Whether to re-run the benchmark with segment-start weather** (the agenda's alternative to disclosure). | An experiment, not an edit. | This design assumes the recommended path: keep the stronger benchmark and disclose. The footnote is written to hold either way except for the last sentence. |

---

## 7. Facts used, and where each was verified

| Fact | Source | Verified how |
|---|---|---|
| §3 spans lines 248–321; dead `comment` block 322–411 | `paper_full_draft.tex` | read directly; `sed -n '322p;411p'` |
| `eq:speed-set` has 10 incoming references | same | `grep -o 'ref{eq:speed-set}' \| wc -l` → 10 |
| `sec:sog` has exactly 2 incoming references, both inside the appendix | same | `grep -n 'ref{sec:sog}'` → 1383, 1475; `\appendix` at 1373 |
| `sec:nesting` has **5** incoming references (agenda says six) | same | `grep -n 'ref{sec:nesting}'` → 914, 974, 1102, 1259, 1299 |
| `sec:objective`, `eq:sog`, `eq:obj` have 0 incoming references | same | `grep -o` → 0 |
| `sec:mechanism` is referenced twice and defined nowhere, both references inside the dead block | same | `grep -n 'ref{sec:mechanism}'` → 380, 391; no `label` |
| TikZ not currently loaded | same | `grep -n 'tikz\|pgf'` → no output |
| Baseline PDF is 32 pages | `paper_full_draft.log` | `Output written on paper_full_draft.pdf (32 pages, 730199 bytes).` |
| Route 1 sampled every 25.0 NM (131 points), Route 2 every 5.0 NM (389 points), source grids ~4.8 NM | §5.1.3 `sec:sampling`, `tab:instances` | read directly |
| 47 time blocks on Route 1, 28 on Route 2 | `tab:instances` | read directly |
| `luo2024` prices a segment with one sample at the segment's start | `docs/meeting_agenda_2026_09_14.md`, quoting their §5.1 and §5.2.2 | treated as verified per the brief |
| Our benchmark walks each block at sub-segment and sample-hour resolution | agenda, `luo_main.cpp:100-131`; and §5.2.1 of the paper says the same | agenda + paper text |
| Their §5.1 *Problem statement*, §5.2.1/§5.2.2 multistage graph, §4 ANN models, §3 data | `Luo2024_CompetingArticle.pdf` | PDF bookmark titles extracted from the file |
| `luo2024`, `yang2020`, `kristensen2012` are keys in `refs.bib` | `paper_workspace/refs.bib` | `grep -n '@.*{luo2024'` etc. |

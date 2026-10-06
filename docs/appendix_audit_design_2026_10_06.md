# Design — what the appendices should contain, and what should be cut

**Question (author, 2026-10-06):** are we over-appendixing? An appendix should carry the formulas we
actually use and reference, not a reproduction of the source paper's derivation.
**Supersedes** the merge design of the same date, which assumed both appendices stay and only merges
them. **They should be merged *and* cut**, and the audit below says by how much.
**Status:** design only.

---

## 1. The test

An item earns a place in an appendix when **both** hold:

1. a reader needs it either **to reproduce our numbers** or **to judge whether to believe them**; and
2. it is **not simply available from the cited source**.

Everything that fails (2) is a reproduction of `yang2020` and belongs behind the citation. Everything
that fails (1) belongs nowhere.

---

## 2. The audit

### 2.1 Sizes

| Appendix | Lines | Equations | Tables | Verdict |
|---|---|---|---|---|
| A — speed-correction model | 35 | 1 | 0 | **cut to a few sentences**, merged |
| B — FCR derivation | 107 | 4 | 1 | **cut hard** — most of it is `yang2020`'s derivation |
| C — benchmark's fuel model | 34 | 0 | 0 | **keep, but it is the one to question** (§4) |
| D — per-voyage results | 159 | 0 | 4 | **keep** — our data, nowhere else |
| E — forecast error | 109 | 0 | 5 | **keep** — our measurement, nowhere else |

### 2.2 The finding that settles it

**Not one appendix equation is referenced from the body.** Checked by `grep` on every `eq:` label:

| Equation | Where | Referenced from |
|---|---|---|
| `eq:app-rt`, `eq:app-pe`, `eq:app-pb`, `eq:app-r` | B | each other, inside B |
| `eq:app-ct` | B | **nothing at all** |
| `eq:app-cubic` | B | inside B |
| `eq:fcr` | B | three times, **all inside the appendix** |
| `eq:sog` | A | once, **inside A** |

The body states the optimisation in terms of $\phi$ and cites `\ref{app:fcr}` twice, as a pointer to
"where the fuel model is written down". **It never uses an appendix equation.** So the five-equation
power chain exists to derive a cubic that the body takes as given.

### 2.3 What a reader actually needs from these two appendices

| Needed | Why | Lines today |
|---|---|---|
| $\fcr(V_s)=0.000706\,V_s^{3}$ | **Ours.** The coefficient is calibrated for this vessel; nobody can reproduce a single number in the paper without it | 1 equation |
| The vessel particulars | Same reason | `tab:ship` |
| Verification accuracy: max 6.5\%, mean 3.75\% | Lets a reader judge the fuel model rather than take it on trust | 2 sentences |
| That the correction inverts, with no closed form, evaluated by binary search | §4's method depends on it; it is a property, not a derivation | 3 sentences |
| That FCR is strictly convex in SWS | The Jensen argument in §3 rests on it | 1 sentence |
| Assumptions and validity range | Tells a reader where the cubic stops being true | ~12 lines |

**That is roughly 25 lines.** The two appendices are 142.

### 2.4 What should go

| Cut | Why |
|---|---|
| The DTU–SDU power chain, `eq:app-rt` through `eq:app-r` | `yang2020`'s derivation via `kristensen2012`. Four equations, none referenced from the body, all available from the citation |
| `eq:app-ct` | Referenced by nothing anywhere |
| *Reduction to the cubic form*, `eq:app-cubic` | The step from the chain to $aV_s^3$. Once the chain goes, this has nothing to reduce; one sentence saying the cubic follows from the chain under constant coefficients replaces it |
| The full form of `eq:sog` | The body never uses it. The two *properties* stay; the equation goes behind the citation |

**Net: five of the six equations go, about 90 lines.**

---

## 3. The resulting appendix

One section, **about 45 lines against 142**, carrying `app:fcr`:

> **A. The fuel-consumption-rate function $\phi$**
>
> *Opening.* §3 takes $\phi$ as exogenous. Given the bearing and the conditions at a point it returns
> the rate at which fuel is burned to hold a speed over ground. It is evaluated in two steps, both
> following \citet{yang2020}: the conditions determine the still-water speed required to hold that
> speed over the ground, and the still-water speed determines the rate.
>
> *A.1 From speed over ground to still-water speed.* What the correction does, and **only the two
> properties the paper uses**: it inverts, with no closed form, by binary search on $V_s$; and the
> required SWS rises as conditions worsen. The resistance terms and coefficients are
> \citet{yang2020}'s and are not reproduced.
>
> *A.2 The fuel-consumption rate.* The calibrated cubic $\fcr(V_s)=0.000706\,V_s^{3}$, where it comes
> from in one sentence, the vessel it is calibrated for, and the verification accuracy. Strict
> convexity noted, since §3 relies on it.
>
> *A.3 Assumptions and validity range.* Kept close to as-is — it is the part that tells a reader when
> to distrust the number.

**`tab:ship` should move to §5.** It is referenced twice, **both from inside the appendix**, and the
vessel being modelled is something a reader wants while reading the experimental setup, not three
sections later in material they are never sent to.

---

## 4. Appendix C is the one to question

34 lines describing the benchmark's learned fuel model, and its own text says:

> it is not used to produce any number reported in this paper, since both formulations are run on the
> fuel model of \ref{app:fcr}.

**An appendix that describes a model we do not use fails test (1) on its face.** The case for keeping
it is that it substantiates a methodological claim — that the comparison holds the fuel model fixed,
so a difference in fuel is a difference in formulation. That claim is load-bearing and Tal's §3 now
makes it explicitly.

**Recommendation: keep, but shorten.** A reader needs to know *what* `luo2024` use and *that* we did
not use it. They do not need the feature list and layer structure, which is `luo2024`'s to document.
Two paragraphs, not four.

---

## 5. What this does not touch

**D and E stay as they are.** Both are our own measurements, exist nowhere else, and are referenced
from the body. They are long because the data is long, which is the right reason for an appendix to
be long.

---

## 6. Open items

| # | Item | Default |
|---|---|---|
| 1 | Cut the power chain entirely, or keep one summarising equation? | **Cut entirely.** A half-derivation is worse than a citation |
| 2 | Move `tab:ship` to §5? | **Yes** — it is experimental setup, and nothing in the body currently points at it |
| 3 | Shorten Appendix C? | **Yes**, to two paragraphs |
| 4 | Does losing the derivation weaken the thesis for examiners, as opposed to the paper? | **Flag to the author.** A thesis may be held to a different standard than a journal submission, and this design optimises for the paper. If the chain must survive for the thesis, the place for it is a thesis-only appendix, not this one |

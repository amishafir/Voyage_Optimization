# Meeting Prep — Monday 2026-09-14 (Ami ↔ Tal)

Continues from [meeting_prep_2026_09_07.md](meeting_prep_2026_09_07.md).

Single topic: **the design of §5.2 (Experimental design)**, so that it slides smoothly into §6 (Results).
Design only — nothing here is implemented. The code work from the 7th–8th is logged in the previous
prep; §4 below lists what is already in place and what §5.2 depends on.

---

## 1. The naming problem, and why it has to be fixed first

Both methods are currently named after people, and one of them after us.

| Current label | Where defined | Problem |
|---|---|---|
| **SR** | Line 881 only: *"SR denotes the Shafir--Raviv per-leg free-speed dynamic program"* | Never expanded on first use (line 60). Self-naming a method before publication reads as presumptuous, and the name conveys nothing about what it does. |
| **Luo** | §5.2, `\citet{luo2024}` | Conflates a *citation* with an *algorithm label*. Every results table then carries an author's surname as a column head. |
| **Naive** | §5.2 | Pejorative rather than descriptive; it is a legitimate operational policy, not a mistake. |

The whole contribution is about **decision granularity**, so name the three methods by their granularity
and attach the citation once. Proposal:

| New label | What it is | Decisions per voyage |
|---|---|---|
| **FIXED** | one speed for the whole voyage, $D/T$, sailed through the actual weather | 1 |
| **BLOCK** | one speed per six-hour block \citep{luo2024} | 47 / 28 |
| **FREE** | one speed per sub-segment × block rectangle (this paper) | 5,875 / 10,864 |

- [ ] **Decide the three names.** Alternatives if FIXED/BLOCK/FREE is not to taste: `CONST/BLOCK/CELL`,
      or keep an abbreviation for our own method but expand it descriptively on first use
      (e.g. "SR — sub-segment resolved") rather than as our surnames.
- [x] The ladder is the contribution **stated as a number**: 1 → 47 → 5,875 on route 1, and
      1 → 28 → 10,864 on route 2. That belongs in §5.2 as a table; it is currently nowhere in the paper.
- [ ] If the names change, they change in: §1 (lines 60, 64, 66, 124), §5.2 (832–851), all six results
      tables (901, 923, 956, 1034, 1054, and the aggregate), §7 (1104–1163), §8 (1177). Mechanical but
      wide — do it in one pass, not incrementally.

---

## 2. §5.2 as proposed, subsection by subsection

The ordering exists to make §6 predictable: **each §5.2 subsection sets up exactly one §6 subsection,
in the same order.**

### 5.2.1 Three levels of speed-decision granularity

The ladder table above, plus one paragraph per method. Key points the current text already makes and
should keep:

- BLOCK was implemented **independently from its published description**, with its own lattice and arc
  evaluation, not as FREE with an added equality constraint. That is what makes the difference
  attributable to granularity rather than to a weakened variant of our own solver — it is the strongest
  methodological sentence in the section and should stay.
- FIXED sails the actual weather with no optimisation and no re-planning.

What to add:

- [ ] **The decision-count table.** It converts "finer granularity" from an adjective into a ratio, and
      it is what §7.2 ("Decision granularity, not data, is the limiting factor") needs to lean on.
- [ ] **What is held equal**: same weather, same physics, same ship, same speed band, same arrival
      constraint. State it once here so §6 need not repeat it per table.

### 5.2.1a What a sub-segment *is* — the science, before any implementation

Settled 2026-09-08. The definition must follow from the physics and the data, not from what the code
produces or what is cheap to compute; the discrepancies are then accounted for separately. (An earlier
draft of this section had it backwards, letting graph size and cross-engine bit-exactness drive the
definition.)

**The definition.** A sub-segment is the stretch over which the **cost coefficient** is constant. It
changes for exactly two reasons: the sea conditions change, and the heading changes. Conditions are
*identically* constant within one source tile — the API performs no interpolation, so this is a property
of the data rather than a modelling assumption. Hence

> sub-segment boundaries = source-tile crossings ∪ course-change points.

**There are two source grids, and they do not align.** This is the part the paper has never stated. The
marine fields arrive on a regular 1/12° lattice; wind arrives on an **octahedral reduced-Gaussian** grid
at ~9 km whose longitude spacing changes row to row. The coefficient therefore changes at the *union* of
two incommensurable lattices, which is finer than either.

| | route 1 | route 2 |
|---|---|---|
| Marine 1/12° crossings (**exact**, pipeline's own analytic routine) | 911 | 715 |
| Wind ~9 km crossings (**estimated** from the probed grid) | ~880 | ~463 |
| Course-change points | 11 | 9 |
| **Union — the true partition** | **~1,802** | **~1,187** |
| **Mean sub-segment** | **1.88 NM** | **1.65 NM** |

The wind figure carries the uncertainty: row spacing 0.0703° and within-row longitude spacing 0.158448°
are measured at 52.4°N, and the latter is scaled as 1/cos φ for an octahedral grid. The marine count is
exact.

**The four discrepancies between that and what the code produces**, which the paper currently collapses
into a single number:

| # | Discrepancy | Effect | Kind |
|---|---|---|---|
| 1 | The model discretizes at **0.5°**, 6× coarser than either source grid in each axis | 1,802 → 164 (r1); 1,187 → 121 (r2) | modelling choice |
| 2 | Only the **marine** grid places boundaries; wind cell crossings place none | drops ~880 / ~463 | modelling choice |
| 3 | Sampling at **25 / 5 NM** holds ~1 reading per 13 / 8 true sub-segments | the partition can be drawn but not populated | **data limitation** |
| 4 | The **τ filter** deletes boundaries as a function of the ETA | 1 / 0 at 0.5°, but **147 / 73** at 0.08° | **defect** |

- [x] This makes Tal's 0.08° edit **right about the science and wrong only as a description of the
      implementation** — a much cleaner thing to fix than a contested definition. §5.1.1 and §4 can keep
      0.08° as the resolution at which conditions are constant; what has to change is the sentence
      claiming the *model* discretizes there.
- [ ] **The narrowed decision: what does the model discretize at, and how is that justified?** No
      candidate reaches ~1.8 NM. Recommendation: the **sampling interval** (125 / 388), on the grounds
      that a boundary carrying no reading carries no information — but stated explicitly as an
      approximation to a known finer truth, not as a definition of a sub-segment.
- [ ] Whichever is chosen, §5.2 states the definition, then the count the model uses, then the reason —
      in that order. Proposed wording:

> The sea conditions are constant within a source tile, so the cost coefficient changes at tile
> crossings and at course changes: on these routes that is a partition of approximately 1,800 and 1,200
> sub-segments, averaging under 2 NM. The model discretizes more coarsely, at *X*, giving *M*
> sub-segments, because […]. Sampling at 25 and 5 NM further limits this to one independent reading per
> *N* sub-segments.

- [ ] Consequence for the §5.2.1 ladder table: it must report the **implemented** M with the true
      partition alongside, or the reader will take the implemented number for the physical one — which
      is the conflation this whole section exists to remove.

### 5.2.2 Two information regimes

Keep the existing perfect-foresight / rolling-horizon split; it is clear. Two corrections:

- [ ] The rolling horizon **re-centres the speed band on the remaining mean** at each re-plan, so RH and
      perfect foresight do not search the same band. Either disclose it or freeze the band to the
      departure value. Currently unstated.
- [ ] Block 0 is planned against **actual** weather (the nowcast), not a forecast. This is already
      admitted as limitation (iii) but is easy to miss in §5.2 itself.

### 5.2.3 Why two routes

Not justified anywhere in the paper at present. The honest justification is a contrast in weather
severity and latitude:

| | route 1 — Indian Ocean | route 2 — North Atlantic |
|---|---|---|
| Length / ETA | 3393.5 NM / 280 h | 1954.0 NM / 168 h |
| Mean $D/T$ | 12.12 kn | 11.63 kn |
| Mean latitude | 12.8°N | 52.4°N |
| Beaufort median / p90 / max | **3 / 5 / 7** | **4 / 6 / 11** |
| Share BN ≥ 6 | **5.7%** | **23.8%** |
| Share BN ≥ 8 | 0.00% | **2.65%** |

**The claim two routes support:** the granularity advantage is not an artefact of one weather regime.
Route 2 has four times the share of BN ≥ 6, reaches BN 11 where route 1 tops out at 7, and sits on the
storm track; route 1 is benign and tropical. If the ordering FREE < BLOCK < FIXED holds on both, it is
not a property of a single ocean.

- [ ] **And what two routes do *not* control, which must be disclosed**: they are sampled 5× differently
      (25 NM vs 5 NM), so they do not resolve the weather equally — route 1's sub-segments span a median
      8 source tiles against route 2's 3. A cross-route difference in the *size* of the advantage is
      therefore confounded with sampling density and cannot be attributed to weather alone. Ordering
      claims survive this; magnitude claims do not.

### 5.2.4 Why the ETA is varied — the strongest new material

This is where §5.2 can stop being descriptive and start making a prediction.

**The structural fact.** The band is $V_{\min},V_{\max} = D/T \pm 3$ kn. So headroom is a *constant*
±3 kn at every ETA: changing the ETA changes the **operating speed level**, not the schedule's
tightness. Relative headroom moves only from ±30% at 10 kn to ±21% at 14 kn.

**Therefore the ETA sweep tests a closed-form prediction.** With $\mathrm{FCR}=c\,V_s^3$, the fuel
penalty of holding speed constant through varying conditions is, to second order, the Jensen term
$\tfrac12 f''(\bar v)\sigma^2 = 3c\,\bar v\,\sigma^2$, while total fuel scales as $\bar v^3$. The
**relative** advantage of fine-grained control should therefore fall as

$$\text{gap}\,\% \;\propto\; \bar v^{-2}.$$

- [x] The May-18 pilot is consistent: FREE-vs-FIXED of −2.10, −1.46, −0.96% at 12.1, 14.1, 17.0 kn —
      ratios 0.69 and 0.66 against the predicted 0.74 and 0.69.
- [ ] So §5.2.4 should state the prediction and §6.3 should report whether it holds, with a
      log–log regression of $|$gap$|$ on $\bar v$ (predicted slope $\approx-2$). That turns the sweep
      from exploratory into **confirmatory**, and it closes the loop with §7.1, which already argues
      "convexity predicted the result" but currently predicts only a *sign*.

**Two band conventions, because one cannot answer both questions.** With the sliding band the ETA sets
the level; to test *tightness* the band must be fixed while $D/T$ moves towards $V_{\max}$. At
$D/T \to V_{\max}$ all three methods collapse to one profile and the gap must go to zero — a free
analytic anchor that validates the harness.

- [ ] Decide whether the fixed-band arm is in scope for this paper or deferred. It doubles the sweep.

**Admissible range.** $\bar v \in [8,14]$ kn. The upper bound is physics, not the solver: at 14 kn the
required SWS exceeds rated power in adverse weather, and the FCR appendix already concedes the cubic
degrades outside the operating band. Below ~8 kn the non-overlapping voyage count collapses and most of
each horizon lies beyond the 168 h forecast reach.

- [ ] Worth knowing: the ship's own `min_speed`/`max_speed` are **never read** by the speed model — the
      only engine constraint anywhere is SWS ≤ 25 kn, which the cubic prices at ~58 MW against a 10 MW
      rated engine. So "the vessel's speed range" as §3 describes it does not exist in the
      implementation. This bounds how fast an ETA level can honestly go.

### 5.2.5 Instances and protocol

Keep the consecutive-voyage chain — stepping by the ETA is what guarantees every planner sees identical
departure weather, and that is the sentence that licenses the whole comparison.

- [ ] **Update the counts.** The fresh data (183 days, 735/736 issues, gap-free) supports **15 + 26 = 41**
      voyages, against 35 published and the stale "nineteen" still in §1 and §5.2.5.
- [ ] For the ETA sweep, use **one common departure grid per route shared by all levels**, stepped by the
      *slowest* level's ETA, so every cross-level comparison is paired on identical departure weather and
      voyages remain non-overlapping at every level. That costs departures (12 + 22) but makes the sweep
      paired.
- [ ] **Supersede, do not realise, the "150 instances" sentence** (lines 795–797). At 72 h spacing, 4–5
      route-1 and 2–3 route-2 voyages are concurrent, so 25 departures carry no more independent
      information than the non-overlapping 12/22. It also uses NM as a speed unit and descends from a
      1–2 departure pilot run with a *fixed* [9,25] band — a different experiment from the production
      sliding band.

### 5.2.6 Metrics

- [ ] Define `gap_pct` **once**, with its denominator named: $100(F_A-F_B)/F_B$, per instance, denominator
      always the reference method. Aggregate as the **mean of per-instance percentages** with a paired
      bootstrap over departures. Note the current aggregate table reports a ratio of means, which is a
      different quantity from the per-voyage column beside it.
- [ ] Never pool routes.
- [ ] For the sweep, report relative gap only — absolute mt is not comparable across ETA levels because
      fuel scales as $\bar v^3$.
- [ ] Add the **granularity decomposition**: (FIXED − FREE) = (FIXED − BLOCK) + (BLOCK − FREE), and report
      (BLOCK − FREE)/(FIXED − FREE) as the share of the achievable saving that requires sub-block
      freedom. On the Aug-11 run that share is ≈74% on both routes — a single number that carries §7.2.

---

## 3. How this lands in §6

§6 currently has two subsections (perfect foresight, rolling horizon) plus "supporting observations".
The design above implies three, in the order §5.2 introduces them:

| §6 subsection | Set up by | Reports |
|---|---|---|
| 6.1 Granularity under perfect foresight | 5.2.1, 5.2.3 | the ladder on 41 voyages, both routes, plus the decomposition |
| 6.2 Granularity under real forecasts | 5.2.2 | the same ordering under rolling horizon, and the regret against the oracle |
| 6.3 How the advantage scales with speed | **5.2.4** | the ETA sweep against the $\bar v^{-2}$ prediction |

- [x] A first full rolling-horizon voyage now runs end-to-end on route 2 with all gates passing
      (FIXED 212.6, FREE 205.0 at −3.58%, BLOCK 212.1 at −0.23%), so 6.2 is reachable.
- [ ] **6.2 has a real finding already visible**: BLOCK under rolling horizon lands within ±0.25% of
      FIXED — essentially on top of the set-and-forget baseline, on either side of zero depending on the
      partition. So block-level re-planning on 6 h forecasts buys almost nothing, and FREE's advantage
      under real forecasts comes from within-block freedom rather than from re-planning. That is a
      sharper claim than §7.3 currently makes.

---

## 4. What §5.2 depends on that is already done

| | Status |
|---|---|
| BLOCK and the rolling horizon run on the same partition as FREE | done, both engines (`35ccf20`) |
| First valid `gap_pct` — same axis, same weather, same partition | done: geo +1.851% (paper reports 1.80%), waypoint +2.048% |
| Full RH voyage, all four gates passing | done, route 2 |
| Fresh data supporting 41 voyages | downloaded, verified gap-free |
| `sh_bases` still hardcoded at the v1 values (19) | **done for the PF drivers** (computed from the h5); `dp_cpp/run_rh_chain.py` still literal |
| Oracle references are geo-only constants | **open** — makes the RH `≥ oracle` gate meaningless on any other partition |
| Paper says 0.08° cells, code uses `grid_deg = 0.5` | **reframed by 5.2.1a** — 0.08° is right as science, wrong as a description of the implementation |

- [x] **No longer a blocker.** §5.2.1a settles the definition on scientific grounds (~1,802 / ~1,187
      sub-segments, under 2 NM). What remains is the narrower question of what the model discretizes at
      and how that approximation is justified — which §5.2 can be written around.

### 4A. 41-voyage perfect-foresight results (2026-09-08) — the partition changes the headline

Both partitions run to completion, 41 voyages each (15 Malacca + 26 Atlantic), departures computed
from the data rather than hardcoded. C++ driver `run_pf_chain.py`, `runs/2026_09_08_pf_chain41/`.

| Partition | Route | n | SR mt | BLOCK mt | gap mt | **gap %** | min | max | sd |
|---|---|---|---|---|---|---|---|---|---|
| geo | Malacca | 15 | 347.069 | 353.330 | 6.262 | **+1.769** | +0.953 | +2.683 | 0.527 |
| geo | Atlantic | 26 | 196.329 | 201.455 | 5.126 | **+2.537** | +1.170 | +4.334 | 0.701 |
| geo | *all* | 41 | | | | **+2.256** | +0.953 | +4.334 | 0.738 |
| waypoint | Malacca | 15 | 345.457 | 354.064 | 8.607 | **+2.428** | +1.770 | +3.613 | 0.514 |
| waypoint | Atlantic | 26 | 198.783 | 201.607 | 2.824 | **+1.376** | +0.365 | +2.685 | 0.644 |
| waypoint | *all* | 41 | | | | **+1.761** | +0.365 | +3.613 | 0.784 |

**The ordering is completely robust.** SR beats BLOCK in **41/41 voyages under both partitions** —
82/82 solves, no exceptions, minimum margin +0.365 %. Whatever else is decided, the ranking claim is
safe and now rests on 41 voyages rather than 19.

**The magnitude is not, and it moves in opposite directions on the two routes:**

| Route | waypoint − geo | consistency |
|---|---|---|
| Malacca | **+0.659 pp** (range +0.004 … +1.248) | waypoint > geo in **15/15** |
| Atlantic | **−1.161 pp** (range −2.909 … −0.186) | waypoint > geo in **0/26** |

The sign flip is unanimous within each route, so it is structure, not noise. It also means the
aggregate figure is partition-dependent (+2.256 % geo vs +1.761 % waypoint) — and neither is
"conservative", because which one is larger depends on the route. **This is the §5.2.1a decision
becoming numerical**: whatever the paper says the model discretizes at determines the headline gap.

Route length is not the explanation — the axes differ by under 0.04 % (Malacca 3393.240 vs 3393.549
nm; Atlantic 1954.699 vs 1954.034 nm), which is two orders of magnitude smaller than the effect.

**Graph size does not move monotonically either**, which is worth knowing before anyone claims the
waypoint partition is simply "finer":

| Partition | Route | mean nodes | mean edges |
|---|---|---|---|
| geo | Malacca | 152,571 | 9,214,780 |
| waypoint | Malacca | 120,844 | 7,284,107 |
| geo | Atlantic | 71,861 | 4,325,288 |
| waypoint | Atlantic | 239,435 | 14,533,161 |

The waypoint partition **shrinks** Malacca by 21 % and **triples** Atlantic (H-lines 121 → 388).
Malacca's 0.5° crossings outnumber its 131 sample points; Atlantic's 391 sample points far outnumber
its 121 crossings. So "finer" is route-specific, not a property of the partition.

**Leading hypothesis for the Atlantic sign flip — not established.** Under `geo`, weather is averaged
over each 0.5° cell crossing; under `waypoint` it is the point value at the sample. In harsh,
variable conditions averaging smooths extremes, which lowers apparent resistance. BLOCK is nearly
unmoved between partitions on Atlantic (201.455 → 201.607) because it already averages over large
blocks, whereas SR — the method that resolves detail — moves 2.45 mt (+1.25 %). That is consistent
with point-vs-average sampling being the mechanism, but it has not been isolated. Worth confirming
before the paper explains the number, because the explanation is the interesting part.

Solver cost: 46.7 min (geo) and 55.4 min (waypoint) across 82 solves each — roughly 10× faster than
the Python driver, which is what made a same-day 41-voyage sweep possible.


---

## 5. Wave height: why Yang's Eqs 11–13 are not in our model

Opened because the wave fields we fetch from the Marine API had no visible consumer. Settled
against the source PDF rather than against our own draft's claims.

### 5A. Wave height is absent from the speed model — in Yang as much as in our code

Yang's speed correction is Kwon's method (Eqs 7–8):

```
ΔV / V_sw · 100% = C_β · C_U · C_Form
V_w = V_sw · (1 − C_β C_U C_Form / 100)
```

with `C_β` = f(weather angle, BN), `C_U` = f(C_B, loading, Fn), `C_Form` = f(ship type, BN, ∇).
Yang then states the closed input list explicitly: *"ship type; ship's main dimensions; ship's
loading conditions; ship payload ∇; ship heading angle α; wind direction angle ϕ; and Beaufort
number BN."* Significant wave height is **not on it**, and wave direction is *assumed equal to*
wind direction.

So there is **no `ΔV_wave` term in the source paper at all** — a single ΔV covers "wind and
irregular waves" jointly through BN. Our implementation was faithful the whole time; the
`ΔV_wave` term and the `H_w` sentence that used to sit in our draft were never Yang's.

### 5B. Where it *is* in Yang: the voluntary speed reduction constraint

| Level | Content |
|---|---|
| Formula | Eqs 11–13: `V_c = exp{0.13·[f(θ) − h]^1.6} + g(θ)`, the **critical STW** |
| Parameter table | Table 5: `V_i_c` — the critical STW in segment i (knots) |
| Model | **Constraint 21**: `V_w^i ≤ V_c^i` |
| Solver | GA fitness penalty `p₂(I_j) = M if ∃ V_w^ij > V_c^i, else 0` (Eq 26) |

`h` = significant wave height (m), `θ` = weather direction angle off the bow.

**Yang did not try this and discard it.** It is specified, tabulated as a parameter, imposed as a
hard constraint, and wired into the solver with a big-M penalty. It is a fully committed
seakeeping safety constraint.

### 5C. But Yang never exercised it

"Significant wave height" appears **exactly once** in the whole paper — the definition line under
Eq 13. No wave-height input data, no `V_c` values, no statement about whether Constraint 21 was
ever active. A constraint fully defined and never demonstrated.

Our measurement explains why nobody noticed: on Yang's own route it cannot bind (§5.5).

### 5D. The `V_c` symbol collision — the likely mechanism for our omission

Yang reuses `V_c` for two different quantities:

| Where | `V_c` means |
|---|---|
| Eq 11, Constraint 21, Table 5 | critical STW (knots) |
| Figure 3, Eqs 14–16, heading algorithm | **ocean current speed** (m/s) |

Their text says it outright: *"In Figure 3, V_c is the current speed, given in m/s"*, and the
heading algorithm notes *"Normally, V_w/V_c > 10"* — a ratio that only makes sense for
ship-speed-over-current.

Our code implements the **current-speed** `V_c` correctly, in the vector synthesis of Eqs 14–16.
The **critical-STW** `V_c` was never implemented. Same symbol, two meanings — a very plausible
route for the constraint to fall through a port. (Mechanism, not proven intent: no rationale for
the omission exists anywhere in the repo — searched every `.md`/`.tex` for "critical STW",
"voluntary speed", "Constraint 21". Zero hits. It was never a recorded decision.)

### 5E. Would it bind? — internal evidence only, not paper material

Kept for our own confidence that the omission is harmless (and to answer the question if Tal asks
it directly). Per §5H this does **not** go in the paper: quantifying Route 2 exposure would concede
an obligation we do not have, and would put wave height back into the text.

Eqs 11–13 evaluated as printed, against the SWS box [11, 13] kn:

| h | V_c | vs. the box |
|---|---|---|
| ≤ 4 m | 44 – 1028 kn | never binds |
| **6.847 m** | 13.0 kn | **starts binding** |
| **7.611 m** | 11.0 kn | **below the SWS floor → infeasible** |
| 8 m | 10.30 kn | infeasible |
| 12 m | 8.00 kn | infeasible |
| > 12.0 m | — | **undefined** (negative base to the 1.6 power) |

Against the observed wave fields in `experiment_{b,d}_v4_sep07.h5`:

| Route | n | binds (V_c<13) | infeasible (V_c<11) | undefined (h>12 m) |
|---|---|---|---|---|
| 1 Malacca | 87,949 | **0.000 %** (0 rows) | 0 rows | 0 rows |
| 2 Atlantic | 282,803 | 2.603 % (7,361) | 1.527 % (4,318) | 0.007 % (19) |

Wave height distribution, for reference:

| Route | mean | p50 | p95 | p99 | max |
|---|---|---|---|---|---|
| 1 Malacca | 1.62 | 1.50 | 3.20 | 4.28 | 5.52 m |
| 2 Atlantic | 2.54 | 2.12 | 5.74 | 8.14 | **12.26 m** |

**Route 1 is Yang's own route** — the one we replicate. Not one sample in 87,949 comes within
1.3 m of the binding threshold. Including Constraint 21 there would change *nothing*, and that is
provable rather than asserted.

**Route 2 is where it would matter**, and there it cannot be implemented as written: in 1.53 % of
conditions Constraint 21 demands `V_w ≤ 11` kn while Constraint 20 demands `V_sw ≥ 11` kn. The two
constraints contradict each other and the model has no feasible solution.

So even if one wanted to adopt it, implementing Constraint 21 would mean choosing the missing sign,
fixing the dead θ units, defining behaviour above 12 m, *and* resolving that contradiction — four
undocumented choices, which makes it a new modelling contribution of our own rather than
replication. That is the practical reason not to, independent of the citation-scope argument in §5H.

### 5F. Two defects in the published equations

1. **The directional dependence does not exist.** Over the full 0–180° range, `f(θ)` spans
   0.00195 and `g(θ)` spans 0.00557 — so `f ≈ 12.0` and `g ≈ 7.0` are constants to four decimals.
   The `(π·θ/180)^2.3` term is numerically dead at the printed coefficients; almost certainly a
   units typo.
2. **The sign is missing.** As printed, `exp{+0.13·[f−h]^1.6}` gives `V_c` = 1027.87 kn in calm
   water. Harmless for an upper bound (it simply never binds), but it means the formula carries
   information only above ~6 m — exactly where it then collides with the speed floor.

Cannot be checked against the primary source: our PDF is **pages 1–13 of a 24-page article**
(running head reads "13 of 24") and contains no reference list, so refs [50,51] — the formula's
origin — are not recoverable from this copy.

### 5G. What was changed (2026-09-08)

**Code** — removed the dead `wave_height` parameter from the speed model in both engines. It had
been in the signature since the initial commit and was **never once an operand** in any commit
(`git log -S` across all history); `physics.cpp` carried it only as `(void)wave_height_m;`.

| File | Change |
|---|---|
| `pipeline/shared/physics.py` | dropped param, docstring line, weather-dict read, pass-through; added a note on why waves are collected but not consumed |
| `pipeline/shared/simulation.py` | dropped the pass-through (kept the local read — feeds the output CSV) |
| `pipeline/dp_rebuild/atomic_edges.py` | dropped the local read and pass-through |
| `pipeline/dp_cpp/src/physics.hpp` / `.cpp` | dropped the parameter, the `(void)` discard, the dict read and the forwarded argument; added the same note |

**Deliberately kept**: HDF5 schema, `Weather`/`WeatherDict` structs, segment averaging, and CSV
logging. Existing datasets depend on the column, the paper legitimately cites wave height as a
route descriptor, and Eq 11 would need it if §5.5 is ever revisited. Only the *speed-model input*
was removed.

**Verification** — no numeric change, as expected of a dead parameter:

- Python: 3,120 SOG + 156 inverse comparisons across SWS × BN 0–12 × wind angle × current ×
  wave height 0–12 m, old vs new code — **0 mismatches, bit-exact**.
- C++: rebuilt in an isolated directory (running binaries untouched); route 1 sh=6 waypoint gives
  `dp_SR` 353.04943315383628 mt and `dp_luo` 360.431 mt — **identical** to the values the
  in-flight run had already logged with the old binary.
- C++ per-arc check (the strong one): old `build/` binary vs new binary, same voyage, `--csv`
  output compared byte-for-byte — **identical**, md5 `e3147edb7078c07731b37855c5e98af9`, 115 arcs.
  That CSV carries per-arc fuel, SWS, SOG, heading and all six weather fields, so any drift in
  path, weather lookup or physics would show.

**Found while verifying, and fixed: the golden-master harness was broken.**
`pipeline/dp_cpp/tests/regression.sh` pointed at `pipeline/data/experiment_{b,d}_*.h5`, which no
longer exist — the datasets moved to `paper_workspace/data/*_v4_sep07.h5`. All six configurations
failed with "HDF5 not found" and the script then printed "REGRESSION DETECTED", a verdict
indistinguishable from a real regression. The C++ safety net had been dead for as long as the data
has been in its current place. Fixed:

- dataset paths repointed to the v4 files, overridable with `DP_CPP_DATA`
- **preflight check**: a missing dataset now exits 4 with a message naming the file, instead of six
  spurious FAILs and a false regression verdict
- `BIN` overridable with `DP_CPP_BIN`, so the harness can verify an out-of-tree build without
  disturbing a running job
- **matrix doubled from 6 to 12**: every configuration now runs under both `geo` and `waypoint`.
  These are separate code paths in `frame.cpp`, so a golden on one said nothing about the other —
  the partition work had no regression cover at all

The goldens were then **captured with the pre-change `build/` binary** (16:05, before `physics.cpp`
was edited at 16:38) and **verified against the post-change build: 12/12 PASS, byte-identical**. So
the removal of the dead wave parameter is now proven across both partitions, all three methods and
both routes — not just the single voyage checked by hand. `build/` has since been rebuilt and also
passes 12/12. The retired goldens remain recoverable from git history (they were tracked).

**Paper** — `paper_full_draft.tex` was already clean (Tal, `8995489`): no wave references, the
MFWAM bullet gone from the data-source list, and the routes characterised qualitatively ("mild and
relatively uniform" / "harsher and more variable"). One precision fix only: "local sea state" →
"local weather state" at the `eq:sog` definition, so `w` cannot be read as including wave height.

The claims survived in the **stale** `paper/sections/*.md` drafts (Aug 19, superseded by the `.tex`,
two identical copies). Corrected there, and the route descriptors swapped from wave height to the
variables the model actually consumes:

| Site | Before | After |
|---|---|---|
| §3 | "three environmental resistance sources — wind, waves, and ocean currents"; inputs `(BN, θ, H_w, V_c, γ)` | "wind-induced resistance — carried through the Beaufort number"; inputs `(BN, θ, V_c, γ)` |
| §5 data sources | MFWAM wave bullet (0.25°) | bullet removed (matches the `.tex`) |
| §5 Route 1 | "mean wave height 0.82 m (std 0.26)" | dropped; wind + current retained |
| §5 Route 2 | "mean significant wave height 5.05 m (std 2.10)"; "2.7× windier and 6.2× wavier" | dropped; "2.7× windier, predominant BN three to four steps higher" |
| §5 Route 2 expected | "Beaufort 8–10, significant wave heights of 4–6 m" | "Beaufort 8–10" |
| §5 sampling | "For waves (MFWAM, 12-h cycle), 94% identical" | clause dropped |
| §4 averaging | "(wind speed, BN, wave height, current velocity)" | "(wind speed, BN, current velocity)" |
| §6 weather tax | "mean wave height 5.05 vs 0.82 m" | "predominant BN 6–8 vs 3–4" |
| §6 forecast error | two Wave RMSE columns + a wave-RMSE sentence | removed (error in an unconsumed field) |
| §8 conclusion | "6.2× higher waves" | "predominant BN three to four steps higher" |

This also **dissolves the stale-statistic problem** rather than fixing it: the 5.05 m figure (v4
measures 2.54 m) and the derived "6.2× wavier" claim are gone instead of needing recomputation.

Wave references now survive only in `01_introduction.md` and `02_literature_review.md`, both
describing *other* authors' work (Yang's resistance decomposition, NWP wave-model refresh cycles,
WaveWatch III, wave-added resistance in the literature). Those stay — removing them would
misrepresent the cited work.

Caveat worth stating once: BN understates sea state at low wind (on Route 2, BN 1 samples had a
median observed wave height of 1.22 m against WMO's implied 0.1 m). A BN-only characterisation is
therefore mildly optimistic about how rough Route 2 is — but it is the model's own view of the
weather, which is what a methods section should report.

### 5H. The position to take: Constraint 21 is not ours to carry

Nothing needs to be conceded here, and nothing about wave height needs to enter the paper. The
argument is about **what this study actually borrows from `yang2020`**, and our own text already
scopes it — §3, on the FCR function:

> "Our algorithm obtains this function as an input. **The calculation or estimation of this
> function is an independent challenge which is not part of the contribution of this paper.** We
> use the method proposed by \citet{yang2020}…"

Every other citation is scoped the same way: "resistance-correction model", "resistance-decomposition
model", "coefficient tables from", "FCR is a cubic function of still-water speed". **Not one
citation adopts Yang's optimization formulation.**

That is the whole case. Constraint 21 belongs to Yang's *optimization model* — Eqs 18–21, solved by
their genetic algorithm — which this study replaces wholesale with DP on the time–distance plane.
We adopt their **speed-correction function** (Eqs 7–9 and 14–16), not their **model**. We are no
more obliged to carry Constraint 21 than their roulette-wheel selection or their big-M penalties.

And the function we did adopt contains no significant wave height at all (§5A). So wave height never
enters this study's model because it never enters the object borrowed from Yang.

**Consequence: no limitation paragraph, no scope-out sentence, no wave-height reference.** There is
no gap to defend. An earlier draft of this section proposed conceding the omission and quantifying
Route 2 exposure; that was the wrong frame — it defends against an obligation that does not exist,
and drags wave height into the paper to do it.

The only sentence worth adding is one that never mentions waves: the SWS interval [11, 13] kn is the
vessel's stated operating envelope (Constraint 20's role), which is what bounds admissible speeds in
this study.

§5E stays in this prep as **evidence that the omission is harmless**, not as material for the paper.

### 5I. Caveats and one loose end

- The 2.60 % / 1.53 % figures are **exposure rates over the whole space–time weather field**, not
  per-voyage binding rates along solved paths. Under §5H this never needs stating publicly, so the
  per-voyage figure was deliberately not computed — it would only be needed if Tal overrules the
  citation-scope position.
- Head seas (θ = 0) assumed; defect (1) in §5F makes direction immaterial anyway.
- ~~Stale route-2 wave statistics~~ — **resolved** by the descriptor swap in §5G. The 5.05 m figure
  (v4 measures 2.54 m) and the derived "6.2× wavier" claim are gone rather than recomputed.
- `.claude/skills/research-paper/SKILL.md` still asserts a step-5 "`delta_V_wave` from wave height,
  ship dimensions" and "implements ALL paper formulas correctly". Both false; that file is the
  origin of the claim that reached our draft, and it is what the next reader or agent will trust.


### 5J. The wave field did move published results — through the NaN gate, and now it is quantified

Found while checking whether the paper's tables could simply be extended from 35 voyages to 41. They
cannot: **the paper's Route 1 perfect-foresight numbers are not reproducible with current code.**

| | SR | Luo | Naive |
|---|---|---|---|
| `tab:modec-r1` voyage 1 (sh 6) | 354.91 | 361.67 | 362.74 |
| `runs/2026_06_15_rh_cpp_chain/results.csv` | 354.914 | 361.671 | 362.743 |
| current code, same voyage, same partition | **353.968** | **360.643** | **361.683** |

So the published Route 1 table came from a **15 June** run. Across the seven voyages that run covers,
SR drift is **−0.946 to +0.369 mt** (mean −0.339) — it varies per voyage and changes sign, which rules
out a simple scaling or a solver change.

It is not the dataset: `experiment_b_138wp_v3_aug24.h5` and `v4_sep07.h5` both give 353.968 for that
voyage. It is not `--node_first` either (that gives 353.101). The axis is identical (L = 3393.24 nm in
both).

**Route 2, by contrast, reproduces exactly**: 203.36 / 210.48 / 212.61 published against
203.357 / 210.480 / 212.609 now, and an independent percentile bootstrap over the same 22-voyage
subset returns SR 196.74 [192.10, 201.77] and SR−Luo −2.61 % [−2.89, −2.32] against the published
196.75 [192.1, 201.8] and −2.60 [−2.89, −2.31]. Both the numbers and the CI method check out.

**The cause is the NaN gate — the wave field's one causal path.** Before `8995489`, `has_nan()`
tested *every* weather field, so `row_has_nan()` dropped any row with a NaN wave height from the
`geo` cell average. Tal's change narrowed the test to consumed fields, so those rows now enter the
average and shift it:

| Route | rows | wave NaN | **wave NaN but all consumed fields valid** |
|---|---|---|---|
| 1 Malacca | 96,285 | 8,336 | **1,426 (1.48 %)** |
| 2 Atlantic | 286,304 | 3,501 | **0 (0.00 %)** |

Route 1 has 1,426 rows that were formerly excluded and are now included. Route 2 has none — which is
exactly why Route 2 reproduces and Route 1 does not. The mechanism is confirmed by that split, not
merely consistent with it.

**So the answer to "does the wave field affect anything" is: it did, at about 0.3 % on Route 1 and
0.0 % on Route 2, entirely through row rejection rather than through any formula.** §5A's claim that
wave height is not an operand stands; what it never was is *inert*. Tal's fix removed the side
channel, and today's parameter removal (§5G) removed the last trace of it.

**Consequence for the paper: the Route 1 PF table must be regenerated, not extended.** The Route 2
table happens to be still correct, but should be regenerated in the same pass so both come from one
run under one partition. That is a correctness fix independent of the 35→41 and partition questions.


## 6. Decisions needed

| Decision | Ref |
|---|---|
| The three method names | 1 |
| What the model discretizes at, and its justification (definition itself is settled) | 5.2.1a |
| Does the ladder table report the true partition alongside the implemented M? | 5.2.1a |
| Is the fixed-band arm in scope, or deferred? | 5.2.4 |
| ETA levels: five, or three? | 5.2.4 |
| Supersede the "150 instances" sentence — agreed? | 5.2.5 |
| Re-run at 41 voyages before or after the partition decision? | 4 |
| ~~Which partition does the paper report?~~ **Decided: `waypoint`.** Migration designed in `docs/waypoint_migration_design.md` | 4A |
| **All experiments now re-run on `waypoint`, 41 voyages** — results and revised conclusions in `docs/waypoint_results_2026_09_09.md` | results |
| **RH-SR loses to RH-Luo on 12/26 Atlantic voyages** — nesting holds in-sample, fails out-of-sample. Promote to the paper's main empirical result? | results §2, §8.3 |
| SR's feasible set provably contains Luo's (V-lines = Luo blocks) — move the 41/41 claim from Results to Methods? | results §1, §8.2 |
| Add the span-vs-forecast-error scatter as the RH section's one figure? | results §8.5 |
| ~~Course changes are not decision points~~ **withdrawn** — verified they already are (13/13, 11/11) | results §6 |
| RH on the Atlantic drops to **−0.26 %, 15/26** (was −1.8 %, 11/12) — §7.2 needs rewriting | results §4 |
| Python↔C++ bit-exactness not re-established on `waypoint` at scale — check before publishing? | results §7 |
| Six scaling claims must be **deleted, not reworded** — no evidence supports any scaling yet | design §5 |
| Run the point-weather probe + stride sweep to recover a magnitude claim? | design §4, §9 |
| §7.2 (RH) is `geo`, 19 voyages, and shares the June-15 reproducibility defect — re-run? | design §6 |
| Why does SR *degrade* on Atlantic with 3x more decision points? Unresolved; blocks §7.1 prose | design §9 |
| Accept the citation-scope position — Constraint 21 is not ours to carry? | 5H |
| **Route 1 PF numbers are from a 15 June run and are not reproducible** — regenerate both tables? | 5J |
| Fix the false `delta_V_wave` row in the `research-paper` skill? | 5I |

## 7. Decisions made during the session

| Decision | Owner | Outcome | Follow-up |
|---|---|---|---|
| Wave height removed as a speed-model input in both engines | Ami | done, 12/12 golden PASS | — |
| Constraint 21 not carried; citation scoped to Yang's speed-correction function | Ami | §5H | Tal to confirm |
| Route descriptors switched from wave height to wind/BN | Ami | §5G | — |
| C++ golden harness repaired: v4 paths, preflight, 12-config partition matrix | Ami | §5G | — |
| | | | |

## 8. Actions assigned during the session

| Action | Owner | Due/status |
|---|---|---|

## 9. Running notes

_Live log — append as we go._

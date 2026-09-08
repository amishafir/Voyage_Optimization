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
| `sh_bases` still hardcoded at the v1 values (19) | **open** — four literal lists, two engines |
| Oracle references are geo-only constants | **open** — makes the RH `≥ oracle` gate meaningless on any other partition |
| Paper says 0.08° cells, code uses `grid_deg = 0.5` | **open, and it blocks §5.2.1** — the sub-segment count in the ladder table depends on which is true |

- [ ] **The last row is the one that gates this section.** §5.2.1's ladder needs a sub-segment count per
      route, and that number is 163/121 under the code and ~775/651 under the paper's current 0.08°
      claim. §5.2 cannot be written until that is decided.

---

## 5. Decisions needed

| Decision | Ref |
|---|---|
| The three method names | 1 |
| Sub-segment count: settle 0.08° vs the implementation first | 4 |
| Is the fixed-band arm in scope, or deferred? | 5.2.4 |
| ETA levels: five, or three? | 5.2.4 |
| Supersede the "150 instances" sentence — agreed? | 5.2.5 |
| Re-run at 41 voyages before or after the partition decision? | 4 |

## 6. Decisions made during the session

| Decision | Owner | Outcome | Follow-up |
|---|---|---|---|
| | | | |

## 7. Actions assigned during the session

| Action | Owner | Due/status |
|---|---|---|

## 8. Running notes

_Live log — append as we go._

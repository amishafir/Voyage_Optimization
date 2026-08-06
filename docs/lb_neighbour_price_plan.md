# Neighbour-price lower bound — prototype log (Tal's idea, Aug-5 meeting)

Implements meeting-prep-08-10 §4 item 3 / meeting-prep-08-05 §0 item 6 (the corrected,
node-first formulation). Code: `pipeline/dp_rebuild/lb_bound.py` (standalone — imports the two
paper-faithful primitives' host module `atomic_edges.py`, modifies nothing; the streaming
refactor runs in parallel in another session). Raw outputs:
`runs/2026_08_07_lb_neighbour_price/` (`*.log` = console, `*.json` = machine-readable).

## 1. Method

The DP's arcs go from a state (d,t) to grid nodes on the two walls ahead (Eq. 5's two
families). The relaxation keeps the **geometry honest** — the vessel still moves to the chosen
node, so there is no positional credit (the leak that made E3's interval LB ~38 % loose) — and
discounts only the **price**: each arc is charged at the speed of the **adjacent, one-step-slower
candidate on the same wall**:

- **family 1** (arrival time t̃ on the distance wall, τ-spaced): the slower neighbour arrives one
  τ later → `v⁻ = (d̃ − d) / (t̃ + τ − t)`;
- **family 2** (arrival distance d̃ on the time wall, ζ-spaced): the slower neighbour advances one
  ζ less → `v⁻ = (d̃ − ζ − d) / (t̃ − t)`.

The discounted speed is used **for pricing only**: SWS inverse at v⁻ (same weather rectangle and
heading the arc already carries — resolved at the source, exactly the DP's convention), FCR at
that SWS, × the arc's **real** duration (t̃ − t). Endpoints and durations are unchanged. One extra
DP run per voyage (here: the same forward pass carries both labels, see §4).

## 2. Validity argument (why LB_DP ≤ F*)

A continuous trajectory crosses each wall somewhere **between** two adjacent grid nodes. Map the
crossing to the adjacent **faster** node — arrival no later (family 1) / advance no shorter
(family 2), so ETA feasibility is preserved. The mapped arc's discounted price is the slower
neighbour's speed, which under-runs the true crossing speed (the crossing lies between the two
neighbours), and FCR is increasing in speed — so every mapped leg is undercharged. The relaxed
DP minimises over all grid paths, including the mapped one, hence

```
LB_DP  ≤  F*(continuous)  ≤  F_polished  ≤  F_DP
```

— a full bracket from the same grid machinery (upper side = the §4.3 node-slide polish).

**Gap control (vs E3):** the discount is exactly one grid step per leg (τ on the leg's arrival
time, or ζ on its advance), so the bound tightens linearly with the grid — E3's looseness was
structural (box-corner teleport), this one is O(step/leg) by construction.

**Formalisation note for Tal:** the leg-by-leg statement needs the induction across legs written
out — after mapping, the next leg starts at the mapped node (which weakly dominates the true
crossing: no later, no less advanced), so the mapped arc's Δt and Δd differ from the true leg's
by at most one step at each end. The prototype takes the meeting-note claim as given; the
one-step-per-leg accounting is what the proof has to deliver.

## 3. Edge-case decisions (as implemented)

| # | Case | Decision | Why it stays a valid LB |
|---|------|----------|------------------------|
| a | Slowest candidate in a window (its slower neighbour falls outside the admissible window) | clip `v⁻` at the **current band's** `v_min` (`frame.cfg.v_min` — NOT 0; the [0, v_max] band change is pending on φ(d,t;0)) | continuous speeds are band-admissible too, so the true crossing speed ≥ v_min; pricing at v_min still undercharges. Frequency: ~17–21 % of arcs (mostly slow-window ends). |
| b | Glide-rule arcs (family-2 candidates extending past an unresolvable distance wall) | same family-2 discount (they live on the time wall); counted separately | the crossing they map is a time-wall crossing; ζ-step discount applies unchanged. ~5 % of arcs. |
| c | v⁻ ≤ 0 | cannot occur while v_min > 0; guarded anyway (floor `max(v⁻, v_min, 1e-6)`) | never fired (see counters). |
| d | Corner nodes (destination on **both** walls — emitted by either family, deduplicated by the candidate set) | priced at **min** of the two family discounts | a crossing of either wall can map to the corner; the smaller speed undercharges both cases. ~1.5 % of arcs. |
| e | SWS inverse infeasible at v⁻ (NaN / > engine bound) | arc priced 0 (undercharge is always LB-safe); counted | never fired — v⁻ < the arc's own realised speed, which passed the same gate. |
| f | Unclassifiable arc (lands on neither wall) | should be impossible in node-first; priced 0 and counted | never fired. |

## 4. Implementation

One streaming-style forward relaxation (pattern of `streaming.py`, copied not imported): lex-min
(t,d) heap on the rounded 9-dp keys, per-source enumeration via the production
`_emit_from_src(node_first=True)` (weather NaN-walkback and heading identical to the solver),
immediate relaxation, no arc storage. The pass carries **two labels per state** — the
normally-priced cost (validates the loop: must reproduce the frozen goldens **exactly**) and the
discounted cost (the LB). Hard-ETA sink selection mirrors `BellmanSolver.best_sink`. A parent
pointer on the normal label gives the diagnostic decomposition below. ~50 s / ~20 s per voyage,
memory O(states) (no 6 GB edge list).

## 5. Results (2026-08-07)

| Voyage | F_DP (mt) | LB (mt) | gap (mt) | gap (% F_DP) | polish recovery (% F_DP) | F_pol (mt) | golden check | LB < F_DP |
|---|---|---|---|---|---|---|---|---|
| route1 (Malacca), sh 6, ETA 280 h | 353.955 | 295.658 | 58.297 | **16.470 %** | 0.204 % | 353.231 | PASS (exact repr, 353.95517201251994) | PASS |
| route2 (Atlantic), sh 0, ETA 168 h | 202.484 | 166.797 | 35.688 | **17.625 %** | 0.239 % | 202.001 | PASS (exact repr, 202.48415966493758) | PASS |

Arc counts (1,179,189 / 468,617) and state counts (133,963 / 61,599) also match the goldens
exactly — the solve loop is the production solve loop.

**Gap decomposition** (new diagnostic: discounted cost of the DP-optimal path itself):

| Voyage | intrinsic discount F_DP − disc(DP path) | path-switch slack disc(DP path) − LB |
|---|---|---|
| route1 | 41.033 mt (11.59 %) | 17.264 mt (4.88 %) |
| route2 | 22.982 mt (11.35 %) | 12.706 mt (6.28 %) |

Sanity of the intrinsic term: the DP plan has ~2 h legs (139 legs / 280 h; 85 / 168 h). A
family-1 leg's speed discount is Δt/(Δt+τ) = 2.0/2.1 ≈ 0.952; with FCR ≈ cubic that is ~13.5 %
fuel, softened to ~11.5 % by the SWS offset and by family-2 legs (ζ/Δd ≈ 1/24 ≈ 4 % speed). The
measured 11.3–11.6 % matches — **the bound's looseness is dominated by the discount itself, not
by a leak**.

## 6. Interpretation — is this a §4.3 companion?

- **It works as designed**: sound, geometry-honest, ~2.2× tighter than E3 (16–18 % vs ~38 %),
  and its error is O(grid step per leg) rather than structural. Both sanity gates pass.
- **But it is not tight enough to sit next to the §4.3 certificate as-is.** The §4.3 polish
  shows the DP is within ~0.2–0.4 % of the continuous optimum *from above*; this LB certifies
  only "within ~16–18 %". The bracket `LB ≤ F* ≤ F_pol ≤ F_DP` is real but its lower side is two
  orders of magnitude wider than its upper side.
- **Why, structurally:** one grid step per leg is *relative to the leg*, not the voyage. With
  τ = 0.1 h and ~2 h legs the per-leg fuel discount is ~11–12 % — that floor is paid even along
  the true optimal path (the intrinsic term). On top, the relaxed DP shops for wall sequences
  with more/shorter legs to harvest one full step per leg (~5–6 % more).
- **Grid refinement helps linearly**: halving τ and ζ should roughly halve both terms
  (~8 %); reaching sub-1 % needs ~×20 refinement — likely impractical as a certificate,
  but the *slope* itself (LB(τ) linear in τ) could be reported as evidence, echoing E1's
  halving/doubling experiment from below.
- Honest paper positioning today: keep §4.3's upper-side certificate as the headline, cite this
  LB as the sound-but-loose lower side (one sentence + future-work), same slot the E3 note
  occupied — now with a mechanism whose gap is grid-controlled rather than structural.

## 7. Open questions for Tal

1. **Fastest window end.** A continuous crossing in the sliver between the *fastest* admissible
   candidate and the band boundary (speed just under v_max) has no faster in-window node to map
   to. Does the enumeration's round()-ended window (the known half-step band-violation wrinkle,
   7/19 schedules) accidentally cover it, or does the relaxed graph need the window extended by
   one node at the fast end for the proof?
2. **Slowest end under the coming [0, v_max] band.** Today's clip at v_min is valid because the
   continuous problem shares the band. With v_min = 0 the clip goes to 0 and the price needs
   φ(d,t;0) (hotel load? free?) — same blocker as the re-runs (prep-08-10 items 2/5). Also: the
   slower neighbour of the shortest family-2 advance becomes the *waiting* arc — is waiting's
   price its own discount floor?
3. **Corner nodes**: is min-of-the-two-discounts (implemented) required, or can the mapping be
   defined per generating wall so the corner charges only the actual family's discount?
4. **Path-switch slack** (~5–6 % of F_DP): the relaxed DP exploits that *every* leg gets a full
   one-step discount, preferring wall sequences with more, shorter legs. Is there a valid
   restriction (e.g., discount per *wall crossed* rather than per arc, since the mapped path
   crosses each wall exactly as the continuous one does) that removes this term?
5. **Induction across legs** (see §2 formalisation note): the mapped leg's Δt/Δd differ from the
   true leg's by up to one step at each end — the write-up must show the discounted price still
   under-runs leg fuel (not just fuel *rate*).
6. **Interaction with the streaming refactor**: once `arc_cost(..., lb=True)` exists on the
   Phase-1 primitive, this prototype reduces to one flag + a second label in the streaming pass
   (this file already demonstrates the two-label single-pass form).

## 8. Reproduce

```bash
cd pipeline/dp_rebuild
python3 lb_bound.py --route route1 --sh_base 6 --out_dir ../../runs/2026_08_07_lb_neighbour_price
python3 lb_bound.py --route route2 --sh_base 0 --out_dir ../../runs/2026_08_07_lb_neighbour_price
```

(~50 s / ~20 s; run sequentially. Golden references: `pipeline/dp_rebuild/goldens/quick.json`;
polish references: `runs/2026_07_28_local_certificate/results.csv`.)

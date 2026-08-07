# Variant (c) — station-keeping-priced waiting: design + test plan (2026-08-08)

Implements meeting-prep-08-10 §2A variant (c) **as an experiment**: code first, behind an opt-in
flag, tested against the current assumptions before any paper direction is committed. Python
first; C++ mirror only after the evaluation says variant (c) is the direction.

## 1. The model being implemented

- Band 𝒱 = [0, v_max] (v_max unresolved — tests keep the current default mean+3; flag stands).
- **Waiting arc** (d,t) → (d, t_𝒯(t)) emitted at every non-sink state (the paper's Eq.-(5)
  amendment, prototype side).
- **Pricing** φ(d,t;0), the "symmetric thrust" prototype convention (to be blessed by Tal):
  - *Head-current / neutral case* (holding needs forward thrust): SWS_hold = g⁻¹(0; w) via the
    existing inversion — the one-home physics path; fuel = FCR(SWS_hold)·Δt.
  - *Following-current case* (the inversion has no non-negative solution): braking. Reverse
    thrust magnitude = the drift SOG (what the current would carry you at with the engine off,
    from the forward physics at SWS = 0), priced through the same cubic: fuel = FCR(drift)·Δt.
    Declared assumption: astern thrust costs like ahead thrust, no loss correction.
- **Waiting at the destination is free** — implemented by NO code (the solver's min-over-sinks
  extraction is exactly equivalent to free waiting at d = L; K4 of the 2A inventory).

## 2. Code layout (Python, `pipeline/dp_rebuild`)

One new axis, three values: `--wait_arcs {off, free, hold}`, default **off** (current behavior,
golden-protected). `free` = variant (a) for comparison; `hold` = variant (c).

| Place | Change |
|---|---|
| `neighbour_candidates` | `wait_arcs` param: when on, add the candidate (t_𝒯(t), src_d). Also guard the family-1 `t_slow = Δd/v_min` division for v_min = 0 (Python raises on float /0). |
| `price_candidate` | `wait_mode` param: Δd = 0 legs short-circuit the normal path — `free`: sog = sws = fcr = fuel = 0; `hold`: the pricing above. **The convention has exactly one home.** Normal legs untouched. |
| `_emit_from_src`, `build_atomic_edges`, `streaming.solve_streaming` | plumb the two params through. |
| `SR_main` | `--wait_arcs` flag; passes through both engines. |
| Band | existing `--min_speed 0` flag; no default change. |

## 3. Gates and the experiment matrix

**Gate E-A (must pass first):** `regression_freeze --check goldens/quick.json` with everything at
defaults — bit-exact (proves the flags at `off` change nothing).

**Experiment E-B (the actual test):** both quick-set voyages × four configs:

| # | band | wait_arcs | question it answers |
|---|---|---|---|
| 1 | current (mean±3) | off | = golden (anchor) |
| 2 | [0, v_max] | off | does the wider slow side alone change anything? |
| 3 | [0, v_max] | free | variant (a): does the DP storm-park? how much fuel does *free* waiting harvest? |
| 4 | [0, v_max] | hold | variant (c): does waiting survive honest pricing? |

Captured per run: fuel, voyage time, arc/state counts, and the waiting diagnostics — number of
wait legs, total waiting hours, where (d, t) they occur, and the hold-price distribution. The
free-vs-hold fuel difference measures **the idealization's bias** — the number that says whether
variant (a)'s free-parking artifact actually matters on real weather.

Interpretation guide: if (3) ≈ (4) ≈ (2), waiting is a non-event on our routes and the choice is
cosmetic; if (3) < (4) markedly, free waiting manufactures savings that honest pricing removes —
variant (c) is the defensible model; if (4) < (2) meaningfully, storm-parking is a real,
honestly-priced phenomenon worth a paragraph in the paper.

## 4. Paper-change inventory IF variant (c) is adopted

**Tal's zones:** Eq. (5) + the unconditional wait candidate; the φ(d,t;0) definition sentence
becomes the station-keeping rule + the symmetric-thrust assumption (one honest sentence); a
d = d_M free-waiting convention sentence (moored; grounds the (L,T) extraction); §4
structural-property 3 needs **no caveat** (continuity restored) — optional footnote on the
V-shaped φ in following currents (zero at the drift speed).

**Ami's zones:** §4.2 extraction paragraph ("waiting at the destination is free (moored), so
C*(L,T) = min over sinks — the terminal state is unique; mid-ocean waiting is priced at the
station-keeping rate"); walkthrough window wording ("the vessel may wait, priced at the
station-keeping rate"); figure captions (the vertical edge = the hold candidate, priced);
Tractability κ + numbers re-measured; §5 band statement + Luo asymmetry policy; §6–§7 re-run
numbers.

**Removed from the 2A inventory under (c):** the constant-SOG caveat (T4) — continuity makes it
unnecessary.

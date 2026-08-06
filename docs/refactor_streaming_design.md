# Streaming-solver refactor — design (approved 2026-08-06)

Implements meeting-prep-08-10 item 4 (decisions 4+5 of the Aug-5 meeting): fuse graph
construction and Bellman solving into one forward pass that stores **only `(C*, pred)` per
state** (no arc set), built on two paper-faithful primitives. Python first, then the C++ mirror.
**Hard gate: results identical to the current code, bit-for-bit, before anything else changes.**
Only after the refactor is green does the `v_min = 0` band change land (separately; blocked on
Tal's φ(d,t;0) decision).

## Why bit-for-bit equality is achievable by construction

Current pipeline: builder BFS → full edge list → solver sorts states lex(t,d) → relaxes each
state's out-edges in list order. The streaming engine keeps the identical arithmetic in the
identical order: pop states from a lex-min heap (same rounded `_KEY_PRECISION` keys as the
dedup), call **the same per-source enumerator** (`atomic_edges.py` already has one: weather
resolved once per source with NaN walkback → node-first candidates → priced), relax each edge the
moment it is produced. Same per-source edge order + same global relax order + same float ops
⇒ identical `cost[]`, `parent[]`, schedule, fuel.

Topological validity: every arc strictly increases `t`, so all predecessors of a state are popped
before it — its label is final at pop time. (Survives `v_min = 0`: waiting arcs still have
`Δt > 0`.) Defensive invariant in code: relaxing an already-popped state raises.

## Approved decisions

1. **Scope**: SR oracle + rolling-horizon stream now (RH inherits automatically — it calls SR's
   solve per re-plan; saving multiplies by #replans). **Luo stays legacy** (its Bellman-side
   state augmentation consumes the edge list; separate later task). Primitives shared by all.
2. **Legacy path kept** behind `--engine {legacy,streaming}` until after the v_min=0 re-runs.
3. **Goldens committed**: `pipeline/dp_rebuild/goldens/*.json`. Quick set (R1·sh6 + R2·sh0
   oracle + 1 RH smoke) at every step; full 19-voyage set at phase exits.

## Phases and gates

| # | Work | Gate |
|---|---|---|
| 0 | `regression_freeze.py`: run CURRENT code (pinned commit), capture per voyage: total fuel (full repr), schedule-CSV sha256, node/edge counts, runtime, peak RSS. Python + C++. | goldens exist |
| 1 | Python primitives inside `atomic_edges.py`: `A(d, t)` (Eq.-5 candidates: two walls, band filter, glide rule) + `arc_cost(...)` (SWS inverse → FCR → ×Δt; takes the once-per-source weather/heading context). Pure extract-method. | quick set bit-exact |
| 2 | `solve_streaming()`: lex-min heap on rounded keys, per-source enumerate, immediate relax, store `(C*, parent_record)` with the same fields `parent_arc` carries today (CSV writer untouched). `--engine` flag, default legacy. | quick + full bit-exact; peak-RSS before/after recorded |
| 3 | Default engine → streaming for SR + RH. | full 19 + RH sweep smoke |
| 4 | C++ mirror: same split in `atomic_edges.cpp`, streaming solve in `bellman.cpp`, `--engine`. | C++ self-exact + Python cross-check (existing ~1e-9 harness) |
| 5 | Cleanup: `ddd_lb.py` `PhiOracle` → `arc_cost` (kills the duplicated physics chain). | certificate numbers unchanged on 1 voyage |
| 6 | **Separate**: `v_min = 0` (config + band + waiting arcs + single-sink (L,T) option). New goldens; expected diffs documented. | new baseline |

Out of scope here: the `lb=True` neighbour-price lower bound (plugs into `arc_cost` after).

## Risk notes

- Heap keys must be the rounded `_key()` values, never raw floats.
- RH's `time_key` / `d_start` arguments flow through the per-source enumerator unchanged.
- Soft-ETA sink selection unchanged (still `best_sink`, both engines).
- Node/edge-count parity: "arcs evaluated" in streaming must equal `len(edges)` in legacy — a
  strong cheap invariant, asserted in the regression script.

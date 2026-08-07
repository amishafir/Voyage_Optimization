"""
Streaming Bellman engine — Phase 2 of the refactor
(docs/refactor_streaming_design.md, approved 2026-08-06).

One forward pass does discovery, discretisation, pricing AND valuation:
states are popped from a lexicographic-(t, d) min-heap; each popped state's
out-edges are produced by the SAME per-source enumerator the legacy builder
uses (`atomic_edges._emit_from_src` = A(d,t) candidates + arc_cost pricing)
and relaxed on the spot. Nothing is stored beyond the two records the answer
needs per state: its cost and its winning parent arc. The arc set is never
materialised.

Bit-exactness vs the legacy build->solve pipeline, by construction:
  - every arc strictly increases t, so heap pops come out in globally
    sorted lex(t, d) order — exactly the topological order the legacy
    solver iterates;
  - per-source edge order is identical (same enumerator);
  - hence the global relaxation sequence, every float operation, the
    parent choices (strict <, first-wins) and the backtracked schedule
    are identical.
  - node-first destinations are generated already rounded to the key
    precision, so rounded keys coincide with raw coordinates.

Scope: node-first only (the speed-first grid stays on the legacy engine).
Luo stays legacy (approved decision).
"""
from __future__ import annotations

import heapq
import sys
from math import inf
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from atomic_edges import AtomicEdge, _emit_from_src
from bellman import BellmanResult
from frame import Frame

_KEY_PRECISION = 9


def _key(t: float, d: float) -> Tuple[float, float]:
    return (round(t, _KEY_PRECISION), round(d, _KEY_PRECISION))


class StreamingStats:
    __slots__ = ("n_nodes", "n_edges_evaluated")

    def __init__(self) -> None:
        self.n_nodes = 0
        self.n_edges_evaluated = 0


def solve_streaming(
    frame: Frame,
    *,
    eta: float,
    eta_mode: str = "hard",
    lam: Optional[float] = None,
    time_key=None,
    d_start: float = 0.0,
    node_first: bool = True,
    forecast_hour: Optional[int] = None,
    override_sample_hour: Optional[int] = None,
    perturber=None,
    wait_mode: str = "off",
) -> Tuple[BellmanResult, StreamingStats]:
    """Solve the DP in a single streaming pass. Returns (result, stats);
    ``stats.n_edges_evaluated`` must equal the legacy ``len(edges)`` — the
    regression harness gates on it."""
    if not node_first:
        raise NotImplementedError(
            "streaming engine supports node-first only; use --engine legacy "
            "for the speed-first grid")

    L = frame.cfg.length_nm
    src_key = _key(0.0, d_start)

    cost: Dict[Tuple[float, float], float] = {src_key: 0.0}
    parent: Dict[Tuple[float, float], Optional[AtomicEdge]] = {src_key: None}
    popped: Set[Tuple[float, float]] = set()
    in_heap: Set[Tuple[float, float]] = {src_key}
    heap: List[Tuple[float, float]] = [src_key]
    stats = StreamingStats()

    while heap:
        k = heapq.heappop(heap)
        in_heap.discard(k)
        if k in popped:
            continue
        popped.add(k)
        t, d = k
        base = cost[k]
        for e in _emit_from_src(t, d, frame,
                                forecast_hour=forecast_hour,
                                override_sample_hour=override_sample_hour,
                                perturber=perturber,
                                time_key=time_key,
                                node_first=True,
                                wait_mode=wait_mode):
            stats.n_edges_evaluated += 1
            dk = _key(e.dst_t, e.dst_d)
            if dk in popped:
                # impossible while every arc strictly increases t — if it
                # ever fires, the pop order was not topological.
                raise AssertionError(
                    f"streaming invariant violated: relax into popped state "
                    f"{dk} from {k}")
            new_cost = base + e.fuel_mt
            prev = cost.get(dk)
            if prev is None or new_cost < prev:
                cost[dk] = new_cost
                parent[dk] = e
            if dk not in in_heap and dk not in popped and prev is None:
                heapq.heappush(heap, dk)
                in_heap.add(dk)

    stats.n_nodes = len(cost)

    # --- sink selection (mirrors BellmanSolver.best_sink) -----------------
    sinks = [k for k in cost if abs(k[1] - L) < 1e-9]
    if not sinks:
        raise ValueError("No sink reachable from the source.")
    if eta_mode == "hard":
        in_time = [k for k in sinks if k[0] <= eta + 1e-6]
        if not in_time:
            raise ValueError(
                f"No sink reachable within ETA {eta} h "
                f"(earliest reachable: {min(k[0] for k in sinks):.3f} h)")
        best = min(in_time, key=lambda k: cost[k])
    elif eta_mode == "soft":
        if lam is None:
            raise ValueError("soft ETA requires `lam`")
        best = min(sinks, key=lambda k: cost[k] + lam * max(0.0, k[0] - eta))
    else:
        raise ValueError(f"Unknown eta_mode {eta_mode!r}; use 'hard' or 'soft'.")

    # --- backtrack (mirrors BellmanSolver.backtrack) ----------------------
    path: List[AtomicEdge] = []
    cur = best
    while parent[cur] is not None:
        e = parent[cur]
        path.append(e)
        cur = _key(e.src_t, e.src_d)
        if cur == src_key:
            break
    path.reverse()

    res = BellmanResult(
        total_fuel_mt=cost[best],
        voyage_time_h=best[0],
        schedule=path,
        sink_node=best,
        eta_mode=eta_mode,
        lam=lam,
        nan_edges_skipped=0,
        nodes_reached=len(cost),
        nodes_unreached=0,
    )
    return res, stats

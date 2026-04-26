"""
Forward Bellman DP solver for the rebuilt graph.

Spec reference: `docs/thesis_brainstorm.md` §14.7 (arc-as-record backtrack),
§14.8 (hard + soft ETA), §15.16 (validator invariants this relies on).

The solver consumes the `(nodes, edges)` produced by `build_nodes.py` +
`build_edges.py`. Each Edge already carries `fuel_mt`; the solver just
relaxes them in topological order.

Topological order is straightforward here: every Edge satisfies both
`dst_t > src_t` and `dst_d > src_d`, so a lexicographic sort on `(t, d)`
gives a valid forward order — Bellman, no priority queue needed.

Backtrack uses the arc-as-record style: each node remembers the optimal
incoming Edge, which already carries `(SWS, SOG, FCR, fuel, weather,
heading)`. Schedule reconstruction is just walking those pointers back to
the source.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import inf, isnan
from typing import Dict, List, Optional, Tuple

from build_edges import Edge
from build_nodes import Node


# ----------------------------------------------------------------------
# Result type
# ----------------------------------------------------------------------

@dataclass
class BellmanResult:
    total_fuel_mt: float
    voyage_time_h: float
    schedule: List[Edge]                # arcs in order from source to sink
    sink_node: Tuple[float, float]      # (t, d)
    eta_mode: str                       # "hard" | "soft"
    lam: Optional[float]                # only set for soft ETA
    nan_edges_skipped: int
    nodes_reached: int
    nodes_unreached: int


# ----------------------------------------------------------------------
# Coordinate key for deduplication
# ----------------------------------------------------------------------

# Round to 9 decimals to absorb float drift from accumulated += zeta_nm /
# tau_h while still being unambiguous for our scales (1 nm and 0.1 h).
_KEY_PRECISION = 9


def _key(t: float, d: float) -> Tuple[float, float]:
    return (round(t, _KEY_PRECISION), round(d, _KEY_PRECISION))


# ----------------------------------------------------------------------
# Solver
# ----------------------------------------------------------------------

class BellmanSolver:
    """Single-shot forward Bellman DP over the rebuilt graph."""

    def __init__(self, nodes: List[Node], edges: List[Edge]):
        # Canonicalise nodes — collapse (V-line, H-line) intersections at
        # d=L and any other coincident pairs into a single graph node.
        seen: Dict[Tuple[float, float], int] = {}
        coords: List[Tuple[float, float]] = []
        is_source: List[bool] = []
        is_sink: List[bool] = []

        for n in nodes:
            k = _key(n.time_h, n.distance_nm)
            idx = seen.get(k)
            if idx is None:
                seen[k] = len(coords)
                coords.append(k)
                is_source.append(n.is_source)
                is_sink.append(n.is_sink)
            else:
                # Merge flags across duplicates so terminal-H sinks "see"
                # the V-line sink at the same (t, L) and vice versa.
                if n.is_source:
                    is_source[idx] = True
                if n.is_sink:
                    is_sink[idx] = True

        self._coords = coords
        self._key_to_id = seen
        self._is_source = is_source
        self._is_sink = is_sink

        n_canonical = len(coords)

        # Outgoing-edge index, keyed by source node id.
        self._outgoing: List[List[Edge]] = [[] for _ in range(n_canonical)]
        self._unknown_edges = 0
        for e in edges:
            src_id = seen.get(_key(e.src_t, e.src_d))
            if src_id is None:
                self._unknown_edges += 1
                continue
            self._outgoing[src_id].append(e)

        # DP state.
        self.cost: List[float] = [inf] * n_canonical
        self.parent_arc: List[Optional[Edge]] = [None] * n_canonical
        self._nan_edges_skipped = 0

        # Source id — must exist exactly at (0, 0).
        zero_id = seen.get(_key(0.0, 0.0))
        explicit_sources = [i for i, s in enumerate(is_source) if s]
        if explicit_sources:
            self._source_id = explicit_sources[0]
        elif zero_id is not None:
            self._source_id = zero_id
        else:
            raise ValueError("No source node found at (0, 0)")
        self.cost[self._source_id] = 0.0

        # Pre-compute topological order — lex sort on (t, d).
        self._topo_order = sorted(range(n_canonical), key=lambda i: coords[i])

    # ------------------------------------------------------------------

    def solve(self) -> None:
        """Forward sweep relaxation. After this, `self.cost[i]` holds the
        minimum cumulative fuel from source to canonical node i."""
        for src_id in self._topo_order:
            if self.cost[src_id] == inf:
                continue
            base = self.cost[src_id]
            for e in self._outgoing[src_id]:
                if isnan(e.fuel_mt):
                    self._nan_edges_skipped += 1
                    continue
                dst_id = self._key_to_id.get(_key(e.dst_t, e.dst_d))
                if dst_id is None:
                    # Edge points to a coordinate no node has — shouldn't
                    # happen if nodes/edges came from the same build pass.
                    continue
                new_cost = base + e.fuel_mt
                if new_cost < self.cost[dst_id]:
                    self.cost[dst_id] = new_cost
                    self.parent_arc[dst_id] = e

    # ------------------------------------------------------------------

    def best_sink(
        self,
        eta_mode: str = "hard",
        eta: Optional[float] = None,
        lam: Optional[float] = None,
    ) -> int:
        """Pick the optimal sink id under the chosen ETA policy.

        - hard ETA: argmin{ cost[s] : sink s with t ≤ ETA }
        - soft ETA: argmin{ cost[s] + lam * max(0, t − ETA) : sink s }
        """
        reachable_sinks = [
            i for i, sink in enumerate(self._is_sink)
            if sink and self.cost[i] < inf
        ]
        if not reachable_sinks:
            raise ValueError("No sink reachable from the source.")

        if eta_mode == "hard":
            if eta is None:
                raise ValueError("hard ETA requires the `eta` argument")
            in_time = [i for i in reachable_sinks if self._coords[i][0] <= eta + 1e-6]
            if not in_time:
                raise ValueError(
                    f"No sink reachable within ETA {eta} h "
                    f"(earliest reachable: {min(self._coords[i][0] for i in reachable_sinks):.3f} h)"
                )
            return min(in_time, key=lambda i: self.cost[i])

        if eta_mode == "soft":
            if eta is None or lam is None:
                raise ValueError("soft ETA requires both `eta` and `lam`")
            return min(
                reachable_sinks,
                key=lambda i: self.cost[i] + lam * max(0.0, self._coords[i][0] - eta),
            )

        raise ValueError(f"Unknown eta_mode {eta_mode!r}; use 'hard' or 'soft'.")

    # ------------------------------------------------------------------

    def backtrack(self, sink_id: int) -> List[Edge]:
        """Walk parent_arc pointers from `sink_id` back to source. Returns
        edges in source→sink order. Each edge already carries its full
        per-arc record (SWS, SOG, fuel, weather, heading)."""
        path: List[Edge] = []
        cur = sink_id
        while self.parent_arc[cur] is not None:
            e = self.parent_arc[cur]
            path.append(e)
            cur = self._key_to_id[_key(e.src_t, e.src_d)]
            if cur == self._source_id:
                break
        path.reverse()
        return path

    # ------------------------------------------------------------------

    def result(
        self,
        eta_mode: str = "hard",
        eta: Optional[float] = None,
        lam: Optional[float] = None,
    ) -> BellmanResult:
        """Convenience: pick the best sink and assemble the result record."""
        sink_id = self.best_sink(eta_mode=eta_mode, eta=eta, lam=lam)
        sink_t, sink_d = self._coords[sink_id]
        schedule = self.backtrack(sink_id)
        reached = sum(1 for c in self.cost if c < inf)
        return BellmanResult(
            total_fuel_mt=float(self.cost[sink_id]),
            voyage_time_h=float(sink_t),
            schedule=schedule,
            sink_node=(float(sink_t), float(sink_d)),
            eta_mode=eta_mode,
            lam=lam,
            nan_edges_skipped=self._nan_edges_skipped,
            nodes_reached=reached,
            nodes_unreached=len(self.cost) - reached,
        )

    # ------------------------------------------------------------------
    # Convenience accessors

    @property
    def num_canonical_nodes(self) -> int:
        return len(self._coords)

    @property
    def num_unknown_edges(self) -> int:
        """Edges whose source coord didn't match any node — should be 0."""
        return self._unknown_edges

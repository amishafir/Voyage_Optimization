"""
Bellman DP solver with per-block SOG-lock state for Luo 2024 mode.

State = (canonical_node_id, locked_target_sog | None):
  * V-line node:     lock = None (forecast block boundary; new SOG can be picked)
  * H-line node mid-block: lock = S (the target_sog chosen at the block-start V-line)

Transitions:
  * Outgoing from (V-line src, None): any atomic edge admissible;
                                       sets new lock = edge.target_sog
                                       (or None again if dst is itself a V-line)
  * Outgoing from (H-line src, S):    only edges with edge.target_sog == S
                                       admissible; lock stays S until next V-line

Free DP and Luo DP run on the SAME atomic-edge graph. Difference is purely
in this Bellman state augmentation.

Spec reference: docs/meeting_prep_2026_05_11.md §2.1.3 (Bellman mode summary).
"""

from __future__ import annotations

from dataclasses import dataclass
from math import inf, isnan
from typing import Dict, List, Optional, Set, Tuple

from atomic_edges import AtomicEdge
from nodes import Node


_KEY_PRECISION = 9
_SOG_TOLERANCE = 1e-6


def _key(t: float, d: float) -> Tuple[float, float]:
    return (round(t, _KEY_PRECISION), round(d, _KEY_PRECISION))


@dataclass
class LuoBellmanResult:
    total_fuel_mt: float
    voyage_time_h: float
    schedule: List[AtomicEdge]
    sink_node: Tuple[float, float]
    nan_edges_skipped: int
    states_reached: int
    distinct_locks_used: int


class BellmanSolverLocked:
    """Forward Bellman over (canonical_node, locked_sog) states."""

    def __init__(
        self,
        nodes: List[Node],
        edges: List[AtomicEdge],
        v_line_times: Set[float],
    ):
        # ---- canonicalise nodes ----
        seen: Dict[Tuple[float, float], int] = {}
        coords: List[Tuple[float, float]] = []
        is_source: List[bool] = []
        is_sink: List[bool] = []
        is_v_line: List[bool] = []

        v_set_rounded = {round(t, _KEY_PRECISION) for t in v_line_times}
        v_set_rounded.add(round(0.0, _KEY_PRECISION))  # source sits on implicit V-line

        for n in nodes:
            k = _key(n.time_h, n.distance_nm)
            if k not in seen:
                seen[k] = len(coords)
                coords.append(k)
                is_source.append(n.is_source)
                is_sink.append(n.is_sink)
                is_v_line.append(k[0] in v_set_rounded)
            else:
                idx = seen[k]
                if n.is_source:
                    is_source[idx] = True
                if n.is_sink:
                    is_sink[idx] = True
                # is_v_line is by coordinate, not flag — already set correctly

        n_canonical = len(coords)
        self._coords = coords
        self._key_to_id = seen
        self._is_source = is_source
        self._is_sink = is_sink
        self._is_v_line = is_v_line

        # ---- index outgoing edges ----
        self._outgoing: List[List[AtomicEdge]] = [[] for _ in range(n_canonical)]
        self._unknown_edges = 0
        for e in edges:
            src_id = seen.get(_key(e.src_t, e.src_d))
            if src_id is None:
                self._unknown_edges += 1
                continue
            self._outgoing[src_id].append(e)

        # ---- source ----
        explicit_sources = [i for i, s in enumerate(is_source) if s]
        if explicit_sources:
            self._source_id = explicit_sources[0]
        else:
            zid = seen.get(_key(0.0, 0.0))
            if zid is None:
                raise ValueError("No source node at (0, 0)")
            self._source_id = zid

        # ---- topological order ----
        self._topo_order = sorted(range(n_canonical), key=lambda i: coords[i])

        # ---- DP state: per-node dict {lock -> (cost, parent_record)} ----
        # parent_record = (edge, prev_canonical_id, prev_lock) or None for source
        self._state: List[Dict[Optional[float], Tuple[float, Optional[Tuple[AtomicEdge, int, Optional[float]]]]]] = [
            {} for _ in range(n_canonical)
        ]
        self._state[self._source_id][None] = (0.0, None)

        self._nan_edges_skipped = 0

    # ------------------------------------------------------------------

    def solve(self) -> None:
        """Forward sweep with SOG-lock state augmentation."""
        is_v_line = self._is_v_line

        for src_id in self._topo_order:
            states = self._state[src_id]
            if not states:
                continue

            # snapshot — we mutate `self._state[dst_id]` below; src state never
            # changes during its own iteration, so a list of (lock, cost) is safe
            src_states = list(states.items())

            for lock_state, (base_cost, _parent) in src_states:
                for e in self._outgoing[src_id]:
                    if isnan(e.fuel_mt):
                        self._nan_edges_skipped += 1
                        continue

                    # ---- lock admissibility ----
                    if lock_state is None:
                        new_lock_in_block = round(e.target_sog, 6)
                    else:
                        if abs(e.target_sog - lock_state) > _SOG_TOLERANCE:
                            continue
                        new_lock_in_block = lock_state

                    # ---- resolve dst ----
                    dst_id = self._key_to_id.get(_key(e.dst_t, e.dst_d))
                    if dst_id is None:
                        continue

                    # Reaching a V-line node releases the lock
                    new_lock = None if is_v_line[dst_id] else new_lock_in_block

                    new_cost = base_cost + e.fuel_mt
                    cur = self._state[dst_id].get(new_lock)
                    if cur is None or new_cost < cur[0]:
                        self._state[dst_id][new_lock] = (
                            new_cost,
                            (e, src_id, lock_state),
                        )

    # ------------------------------------------------------------------

    def best_sink(self, eta_h: float) -> int:
        """Argmin sink reachable with lock=None at t ≤ ETA."""
        best_id = -1
        best_cost = inf
        for i, sink in enumerate(self._is_sink):
            if not sink:
                continue
            if self._coords[i][0] > eta_h + 1e-6:
                continue
            entry = self._state[i].get(None)
            if entry is None:
                continue
            if entry[0] < best_cost:
                best_cost = entry[0]
                best_id = i
        if best_id < 0:
            raise ValueError("No sink reachable within ETA under Luo lock.")
        return best_id

    # ------------------------------------------------------------------

    def backtrack(self, sink_id: int) -> List[AtomicEdge]:
        """Walk parent pointers from (sink_id, None) back to source."""
        path: List[AtomicEdge] = []
        cur_id = sink_id
        cur_lock: Optional[float] = None
        while True:
            entry = self._state[cur_id].get(cur_lock)
            if entry is None or entry[1] is None:
                break
            edge, prev_id, prev_lock = entry[1]
            path.append(edge)
            cur_id = prev_id
            cur_lock = prev_lock
            if cur_id == self._source_id and cur_lock is None:
                break
        path.reverse()
        return path

    # ------------------------------------------------------------------

    def result(self, eta_h: float) -> LuoBellmanResult:
        sink_id = self.best_sink(eta_h)
        sink_t, sink_d = self._coords[sink_id]
        schedule = self.backtrack(sink_id)
        states_reached = sum(len(s) for s in self._state)
        distinct_locks = len({lock for s in self._state for lock in s if lock is not None})
        sink_cost = self._state[sink_id][None][0]
        return LuoBellmanResult(
            total_fuel_mt=float(sink_cost),
            voyage_time_h=float(sink_t),
            schedule=schedule,
            sink_node=(float(sink_t), float(sink_d)),
            nan_edges_skipped=self._nan_edges_skipped,
            states_reached=states_reached,
            distinct_locks_used=distinct_locks,
        )

    @property
    def num_unknown_edges(self) -> int:
        return self._unknown_edges

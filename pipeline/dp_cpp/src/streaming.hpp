#pragma once
// Streaming Bellman engine — C++ mirror of pipeline/dp_rebuild/streaming.py
// (streaming refactor Phase 4; design: docs/refactor_streaming_design.md).
//
// One forward pass does discovery, pricing and valuation: states are popped
// from a lexicographic-(t, d) min-heap; each popped state's out-edges come
// from the SAME per-source enumerator the legacy builder uses
// (emit_from_src = A(d,t) candidates + arc_cost pricing) and are relaxed on
// the spot. Only (cost, winning parent arc) is stored per state; the arc set
// is never materialised.
//
// Bit-exactness vs the legacy build->solve pipeline, by construction:
// every arc strictly increases t, so heap pops come out in globally sorted
// lex(t, d) order — the same topological order BellmanSolver iterates; the
// per-source edge order is identical; hence the relaxation sequence, every
// float operation, the parent choices (strict <, first-wins) and the
// backtracked schedule are identical.
//
// Scope: node-first only. Luo stays on the legacy engine.
#include "atomic_edges.hpp"
#include "frame.hpp"
#include <cstddef>
#include <vector>

struct StreamingResult {
    double total_fuel_mt = 0.0;
    double voyage_time_h = 0.0;
    std::vector<AtomicEdge> path;      // winning arcs, src -> sink order
    std::size_t n_states = 0;          // discovered states (== legacy n_nodes)
    std::size_t n_edges_evaluated = 0; // priced arcs (== legacy n_edges)
};

StreamingResult solve_streaming(const Frame& frame, double eta,
                                const TimeKey& time_key = {},
                                double d_start = 0.0,
                                bool node_first = true);

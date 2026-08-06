#pragma once
#include "frame.hpp"
#include "nodes.hpp"
#include "weather.hpp"
#include <utility>
#include <vector>

struct AtomicEdge {
    double  src_t, src_d;
    double  dst_t, dst_d;
    double  sog;          // realized SOG = Δd/Δt (post-snap)
    double  target_sog;   // decision SOG ∈ {v_min, …, v_max} — Luo lock label
    Weather weather;
    double  heading_deg;
    double  sws;
    double  fcr_mt_per_h;
    double  fuel_mt;
    // True iff this arc crosses a V-line (block boundary) in time.
    // Used by the Luo DP to release the SOG lock.
    // H-line arcs that happen to snap onto a V-line time do NOT set this.
    bool    crosses_v_line = false;
};

// BFS edge builder: discovers (t,d) nodes lazily from source (0, d_start).
// Returns (nodes, edges) ready for BellmanSolver.
//
// override_sample_hour = -1 → use block-start sample_hour per Luo 2024.
// forecast_hour        = -1 → read actual_weather.
// time_key (empty)     → legacy path above. When set, OVERRIDES sample_hour /
//                        forecast_hour per sub-voyage time (rolling horizon).
// d_start              → absolute distance (nm) the (sub-)voyage begins at;
//                        the BFS source is (0, d_start). Distances stay ABSOLUTE
//                        so geo/weather lookups remain geographically correct.
// Per-source enumerator (streaming refactor Phase 4: exposed for the
// streaming engine — previously a static helper of the BFS builder).
// Resolves the source's weather (with NaN walkback) once, then emits the
// node-first A(d,t) candidates priced on the spot (or the legacy SOG grid
// when node_first = false). Returns {} at the sink or when no valid
// weather exists.
std::vector<AtomicEdge> emit_from_src(double src_t, double src_d,
                                      const Frame& frame,
                                      int forecast_hour,
                                      int override_sample_hour,
                                      const TimeKey& time_key,
                                      bool node_first = false);

std::pair<std::vector<Node>, std::vector<AtomicEdge>>
build_atomic_edges(const Frame& frame,
                   int forecast_hour        = -1,
                   int override_sample_hour = -1,
                   bool verbose             = false,
                   const TimeKey& time_key  = {},
                   double d_start           = 0.0,
                   bool node_first          = false);

void summarize_atomic_edges(const std::vector<Node>& nodes,
                              const std::vector<AtomicEdge>& edges);

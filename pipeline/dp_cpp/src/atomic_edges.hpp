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

// BFS edge builder: discovers (t,d) nodes lazily from source (0,0).
// Returns (nodes, edges) ready for BellmanSolver.
//
// override_sample_hour = -1 → use block-start sample_hour per Luo 2024.
// forecast_hour        = -1 → read actual_weather.
std::pair<std::vector<Node>, std::vector<AtomicEdge>>
build_atomic_edges(const Frame& frame,
                   int forecast_hour        = -1,
                   int override_sample_hour = -1,
                   bool verbose             = false);

void summarize_atomic_edges(const std::vector<Node>& nodes,
                              const std::vector<AtomicEdge>& edges);

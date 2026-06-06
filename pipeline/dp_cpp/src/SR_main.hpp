#pragma once
// dp_SR — callable solver API (extracted from main() in Phase 0 of the RH port).
// main() parses args and delegates to sr_solve(); the RH orchestrator
// (run_rh) calls sr_solve() directly, reusing one VoyageWeather across voyages.
#include "atomic_edges.hpp"   // AtomicEdge
#include "nodes.hpp"          // Node
#include "route.hpp"          // Waypoint
#include "weather.hpp"        // VoyageWeather
#include <cstddef>
#include <optional>
#include <string>
#include <vector>

struct SRArgs {
    std::string yaml = "route.yaml";
    std::string h5   = "experiment_b_138wp.h5";
    std::optional<double> eta;
    std::optional<double> min_speed;
    std::optional<double> max_speed;
    std::optional<double> zeta_nm;
    std::optional<double> tau_h;
    int sample_hour = 0;   // departure-time anchor (Phase 1; unused in Phase 0)
};

struct SRResult {
    double total_fuel_mt = 0.0;
    double voyage_time_h = 0.0;
    double eta_h = 0.0;
    std::size_t n_nodes = 0;
    std::size_t n_edges = 0;
    double build_s = 0.0;
    double solve_s = 0.0;
    std::vector<int>        schedule;    // edge indices, src→sink order
    std::vector<AtomicEdge> edges;       // full edge set (CSV + RH block-0 extraction)
    std::vector<Waypoint>   waypoints;
    int    sample_hour = 0;
    double d_start = 0.0;
};

// Build the atomic-edge graph and solve dp_SR. `voyage` is supplied by the
// caller (constructed once, reused across solves so the weather cache stays
// warm). `verbose` controls the frame/build/summarize console output.
// `time_key` / `d_start`: rolling-horizon hooks (see build_atomic_edges).
// time_key empty + d_start 0 → legacy Mode C behaviour.
SRResult sr_solve(const SRArgs& args, const VoyageWeather& voyage,
                  bool verbose = true,
                  const TimeKey& time_key = {}, double d_start = 0.0);

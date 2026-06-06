#pragma once
// dp_luo — callable solver API (extracted from main() in Phase 0 of the RH port).
// Seg / ArcResult live here (not file-local in luo_main.cpp) so LuoResult can
// carry them and the RH orchestrator (run_rh) can read per-block segments.
#include "route.hpp"     // Waypoint
#include "weather.hpp"   // Weather, VoyageWeather
#include <optional>
#include <string>
#include <utility>
#include <vector>

// One weather-zone sub-segment within a block.
struct Seg {
    double src_d, dst_d;   // [nm]
    double src_t;          // [h] absolute time at sub-segment start
    double sog;            // block SOG [kn] — constant within block
    double heading_deg;
    Weather weather;
    double sws, fcr, fuel_mt, dur_h;
};

// Result of evaluating one block arc (d1_idx → d2_idx).
struct ArcResult {
    bool   ok = false;
    double fuel = 0.0;
    std::vector<Seg> segs;
};

struct LuoArgs {
    std::string yaml = "route.yaml";
    std::string h5   = "experiment_b_138wp.h5";
    std::optional<double> eta;
    std::optional<double> min_speed;
    std::optional<double> max_speed;
    double res_nm   = 1.0;
    bool   baseline = false;
    int    sample_hour = 0;   // departure-time anchor (Phase 1; unused in Phase 0)
};

struct LuoResult {
    bool   feasible = true;          // false → no path to destination
    double total_fuel_mt = 0.0;
    double voyage_time_h = 0.0;
    int    n_blocks = 0;             // best_col (DP); 0 for baseline
    double solve_s  = 0.0;
    std::vector<std::pair<ArcResult, int>> path_arcs;   // (arc, block) — DP mode
    std::vector<Seg> baseline_segs;                     // baseline mode
    std::vector<Waypoint> waypoints;
    double eta_h = 0.0;
    int    sample_hour = 0;
    double d_start = 0.0;
};

// Run dp_luo (or the fixed-mean-SOG baseline if args.baseline). `voyage` is
// supplied by the caller (reused across solves so the cache stays warm).
// `time_key` / `d_start`: rolling-horizon hooks. time_key selects mixed
// nowcast/forecast weather per sub-voyage time (empty → time-varying actual);
// d_start seeds the DP at round(d_start/res_nm) and centres the speed band on
// the remaining mean SOG (L - d_start)/eta. Distances stay ABSOLUTE.
LuoResult luo_solve(const LuoArgs& args, const VoyageWeather& voyage,
                    bool verbose = true,
                    const TimeKey& time_key = {}, double d_start = 0.0);

#include "atomic_edges.hpp"
#include "bellman.hpp"
#include "bellman_locked.hpp"
#include "frame.hpp"
#include "nodes.hpp"
#include "physics.hpp"
#include "route.hpp"
#include "weather.hpp"

#include <chrono>
#include <cstdio>
#include <filesystem>
#include <set>
#include <stdexcept>
#include <string>

namespace fs = std::filesystem;

static void print_header(const char* title) {
    printf("\n%s\n%s\n%s\n",
           std::string(78, '=').c_str(), title,
           std::string(78, '=').c_str());
}

int main(int argc, char* argv[]) {
    // Locate data files relative to this binary's parent (pipeline/).
    // Adjust these paths if running from a different working directory.
    std::string yaml_path =
        argc > 1 ? argv[1]
                 : "../../Dynamic speed optimization/weather_forecasts.yaml";
    std::string h5_path =
        argc > 2 ? argv[2]
                 : "../data/voyage_weather.h5";

    if (!fs::exists(yaml_path)) {
        fprintf(stderr, "YAML not found: %s\n", yaml_path.c_str());
        return 1;
    }
    if (!fs::exists(h5_path)) {
        fprintf(stderr, "HDF5 not found: %s\n", h5_path.c_str());
        return 1;
    }

    // ---- Load route & weather ----
    Route route = synthesize_multi_window(load_yaml_route(yaml_path), 6.0);
    VoyageWeather voyage(h5_path);

    // ---- Build frame ----
    print_header("DP REBUILD — frame");
    Frame frame = make_frame(route, voyage, WAYPOINTS);
    summarize_frame(frame);

    // ---- Build atomic-edge graph ----
    print_header("DP REBUILD — build atomic-edge graph");
    auto t0 = std::chrono::steady_clock::now();
    auto [nodes, edges] = build_atomic_edges(frame, /*forecast_hour=*/-1,
                                              /*override_sample_hour=*/0,
                                              /*verbose=*/false);
    double build_t = std::chrono::duration<double>(
        std::chrono::steady_clock::now() - t0).count();
    printf("\nBuild time: %.2f s\n", build_t);
    summarize_atomic_edges(nodes, edges);

    // ---- Free DP ----
    print_header("DP REBUILD — Free DP (no SOG lock)");
    t0 = std::chrono::steady_clock::now();
    BellmanSolver free_solver(nodes, edges);
    free_solver.solve();
    BellmanResult free_res = free_solver.result("hard", frame.cfg.eta_h);
    double free_t = std::chrono::duration<double>(
        std::chrono::steady_clock::now() - t0).count();
    printf("  Total fuel:        %.3f mt\n", free_res.total_fuel_mt);
    printf("  Voyage time:       %.3f h\n",  free_res.voyage_time_h);
    printf("  Sink:              (%.3f h, %.3f nm)\n",
           free_res.sink_node.first, free_res.sink_node.second);
    printf("  Schedule length:   %zu edges\n", free_res.schedule.size());
    printf("  Solve time:        %.3f s\n", free_t);
    printf("  NaN edges skipped: %d\n", free_res.nan_edges_skipped);

    // ---- Luo DP ----
    print_header("DP REBUILD — Luo DP (SOG-lock per 6 h block)");
    std::set<double> v_times_set(frame.v_line_times.begin(), frame.v_line_times.end());
    t0 = std::chrono::steady_clock::now();
    BellmanSolverLocked luo_solver(nodes, edges, v_times_set);
    luo_solver.solve();
    LuoResult luo_res = luo_solver.result(frame.cfg.eta_h);
    double luo_t = std::chrono::duration<double>(
        std::chrono::steady_clock::now() - t0).count();
    printf("  Total fuel:        %.3f mt\n", luo_res.total_fuel_mt);
    printf("  Voyage time:       %.3f h\n",  luo_res.voyage_time_h);
    printf("  Sink:              (%.3f h, %.3f nm)\n",
           luo_res.sink_node.first, luo_res.sink_node.second);
    printf("  Schedule length:   %zu edges\n", luo_res.schedule.size());
    printf("  Solve time:        %.3f s\n", luo_t);
    printf("  States reached:    %d\n",  luo_res.states_reached);
    printf("  Distinct locks:    %d / %zu\n",
           luo_res.distinct_locks_used, frame.sog_grid().size());

    // Check block-lock invariant on the Luo schedule
    std::unordered_map<int, std::set<double>> by_block;
    for (int ei : luo_res.schedule) {
        const auto& e = edges[ei];
        int block = (int)(e.src_t / frame.cfg.dt_h);
        by_block[block].insert(std::round(e.target_sog * 1e4) / 1e4);
    }
    int one_sog_blocks = 0;
    for (auto& [blk, sogs] : by_block)
        if (sogs.size() == 1) ++one_sog_blocks;
    printf("  Lock invariant:    %d/%zu blocks have a single target SOG%s\n",
           one_sog_blocks, by_block.size(),
           one_sog_blocks == (int)by_block.size() ? " ✓" : " ✗ VIOLATED");

    // ---- Summary ----
    print_header("SUMMARY — single graph, two DP modes");
    printf("  Free DP:   %.3f mt  (solve %.2f s)\n", free_res.total_fuel_mt, free_t);
    printf("  Luo DP:    %.3f mt  (solve %.2f s)\n", luo_res.total_fuel_mt,  luo_t);
    printf("  Δ (Luo-Free): %+.3f mt  (Luo ≥ Free by construction)\n",
           luo_res.total_fuel_mt - free_res.total_fuel_mt);
    printf("  Graph: %zu nodes, %zu atomic edges, build %.1f s\n\n",
           nodes.size(), edges.size(), build_t);

    return 0;
}

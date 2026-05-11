#include "atomic_edges.hpp"
#include "bellman.hpp"
#include "bellman_locked.hpp"
#include "frame.hpp"
#include "nodes.hpp"
#include "route.hpp"
#include "weather.hpp"

#include <chrono>
#include <cstdio>
#include <cstdlib>
#include <filesystem>
#include <optional>
#include <set>
#include <string>

namespace fs = std::filesystem;

static void print_header(const char* title) {
    printf("\n%s\n%s\n%s\n",
           std::string(78, '=').c_str(), title,
           std::string(78, '=').c_str());
}

static void usage(const char* prog) {
    fprintf(stderr,
        "Usage: %s [OPTIONS]\n"
        "  --yaml PATH       Route YAML  (default: ../../Dynamic speed optimization/weather_forecasts.yaml)\n"
        "  --h5   PATH       HDF5 file   (default: ../data/voyage_weather.h5)\n"
        "  --eta  HOURS      Override ETA in hours (e.g. 240)\n"
        "  --min_speed KNOTS Override minimum SOG in knots (default: 9)\n"
        "  --max_speed KNOTS Override maximum SOG in knots (default: 13)\n"
        "  --baseline        Fix SOG to route_length / ETA (mean speed); overrides min/max_speed\n",
        prog);
}

int main(int argc, char* argv[]) {
    std::string yaml_path = "../../Dynamic speed optimization/weather_forecasts.yaml";
    std::string h5_path   = "../data/voyage_weather.h5";
    std::optional<double> eta_override;
    std::optional<double> min_speed_override;
    std::optional<double> max_speed_override;
    bool baseline_mode = false;

    for (int i = 1; i < argc; ++i) {
        std::string arg = argv[i];
        auto need_next = [&]() -> const char* {
            if (i + 1 >= argc) {
                fprintf(stderr, "Error: %s requires a value\n", arg.c_str());
                std::exit(1);
            }
            return argv[++i];
        };
        if      (arg == "--yaml")      yaml_path          = need_next();
        else if (arg == "--h5")        h5_path            = need_next();
        else if (arg == "--eta")       eta_override       = std::stod(need_next());
        else if (arg == "--min_speed") min_speed_override = std::stod(need_next());
        else if (arg == "--max_speed") max_speed_override = std::stod(need_next());
        else if (arg == "--baseline")  baseline_mode      = true;
        else if (arg == "--help" || arg == "-h") { usage(argv[0]); return 0; }
        else { fprintf(stderr, "Unknown option: %s\n", arg.c_str()); usage(argv[0]); return 1; }
    }

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
    GraphConfig base_cfg = GraphConfig::from_route(route);
    if (eta_override)       base_cfg.eta_h = *eta_override;
    if (min_speed_override) base_cfg.v_min = *min_speed_override;
    if (max_speed_override) base_cfg.v_max = *max_speed_override;
    // In baseline mode we must NOT narrow the speed range yet: the τ-feasibility
    // filter in h_line_distances_from_geo drops H-line gaps that can't be crossed
    // at any integer multiple of tau_h within [v_min, v_max]. With v_min==v_max the
    // window collapses to a point and almost all H-lines are discarded, leaving no
    // path from source to sink. We therefore build the frame with a wide range, then
    // pin the SOG grid to mean_sog before build_atomic_edges (which reads it lazily).
    if (baseline_mode) {
        double mean_sog = base_cfg.length_nm / base_cfg.eta_h;
        base_cfg.v_min = mean_sog * 0.5;
        base_cfg.v_max = mean_sog * 2.0;
    }
    Frame frame = make_frame(route, voyage, WAYPOINTS, &base_cfg);
    if (baseline_mode) {
        double mean_sog = frame.cfg.length_nm / frame.cfg.eta_h;
        frame.cfg.v_min = mean_sog;
        frame.cfg.v_max = mean_sog;
        printf("Baseline mode: mean SOG = %.4f kn  (%.0f nm / %.1f h)\n",
               mean_sog, frame.cfg.length_nm, frame.cfg.eta_h);
    }
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

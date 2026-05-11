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
#include <fstream>
#include <optional>
#include <set>
#include <string>

namespace fs = std::filesystem;

// Write one CSV row per arc (Free DP / baseline).
// sog_kn = realized dd/dt, consistent with sws/fcr and duration.
static void write_arc_csv(const std::string& path,
                           const std::vector<int>& schedule,
                           const std::vector<AtomicEdge>& edges,
                           const std::vector<Waypoint>& waypoints) {
    std::ofstream f(path);
    f << "time_h,distance_nm,lat_deg,lon_deg,bearing_deg,"
         "sog_kn,sws_kn,fcr_mt_per_h,fuel_mt,duration_h,"
         "wind_speed_kmh,wind_dir_deg,beaufort,wave_height_m,"
         "current_vel_kmh,current_dir_deg\n";
    for (int ei : schedule) {
        const auto& e = edges[ei];
        auto [lat, lon, _seg] = position_at_d(e.src_d, waypoints);
        const auto& w = e.weather;
        f << e.src_t                        << ','
          << e.src_d                        << ','
          << lat                            << ','
          << lon                            << ','
          << e.heading_deg                  << ','
          << e.sog                          << ','
          << e.sws                          << ','
          << e.fcr_mt_per_h                 << ','
          << e.fuel_mt                      << ','
          << (e.dst_t - e.src_t)            << ','
          << w.wind_speed_10m_kmh           << ','
          << w.wind_direction_10m_deg       << ','
          << w.beaufort_number              << ','
          << w.wave_height_m                << ','
          << w.ocean_current_velocity_kmh   << ','
          << w.ocean_current_direction_deg  << '\n';
    }
    printf("  CSV written: %s  (%zu arcs)\n", path.c_str(), schedule.size());
}

// Write one CSV row per arc for Luo DP.
// sog_kn = target_sog (the block-level lock, constant within each 6h block).
// sws_kn, fcr, fuel, and weather vary per arc as the vessel crosses weather
// zones and heading changes — SOG is locked but SWS/FCR respond to conditions.
static void write_block_csv(const std::string& path,
                              const std::vector<int>& schedule,
                              const std::vector<AtomicEdge>& edges,
                              const std::vector<Waypoint>& waypoints,
                              double dt_h) {
    std::ofstream f(path);
    f << "block,time_h,distance_nm,lat_deg,lon_deg,bearing_deg,"
         "sog_kn,sws_kn,fcr_mt_per_h,fuel_mt,duration_h,"
         "wind_speed_kmh,wind_dir_deg,beaufort,wave_height_m,"
         "current_vel_kmh,current_dir_deg\n";

    int n_arcs = 0;
    for (int ei : schedule) {
        const auto& e = edges[ei];
        int blk = (int)(e.src_t / dt_h);
        auto [lat, lon, _seg] = position_at_d(e.src_d, waypoints);
        const auto& w = e.weather;
        f << blk                            << ','
          << e.src_t                        << ','
          << e.src_d                        << ','
          << lat                            << ','
          << lon                            << ','
          << e.heading_deg                  << ','
          << e.target_sog                   << ','  // locked SOG, constant in block
          << e.sws                          << ','  // varies with weather/heading
          << e.fcr_mt_per_h                 << ','  // varies with weather/heading
          << e.fuel_mt                      << ','
          << (e.dst_t - e.src_t)            << ','
          << w.wind_speed_10m_kmh           << ','
          << w.wind_direction_10m_deg       << ','
          << w.beaufort_number              << ','
          << w.wave_height_m                << ','
          << w.ocean_current_velocity_kmh   << ','
          << w.ocean_current_direction_deg  << '\n';
        ++n_arcs;
    }
    printf("  CSV written: %s  (%d arcs)\n", path.c_str(), n_arcs);
}

static void print_header(const char* title) {
    printf("\n%s\n%s\n%s\n",
           std::string(78, '=').c_str(), title,
           std::string(78, '=').c_str());
}

static void usage(const char* prog) {
    fprintf(stderr,
        "Usage: %s [OPTIONS]\n"
        "  --yaml PATH       Route YAML  (default: weather_forecasts.yaml in executable directory)\n"
        "  --h5   PATH       HDF5 file   (default: voyage_weather.h5 in executable directory)\n"
        "  --eta  HOURS      Override ETA in hours (e.g. 240)\n"
        "  --min_speed KNOTS Override minimum SOG in knots (default: 9)\n"
        "  --max_speed KNOTS Override maximum SOG in knots (default: 13)\n"
        "  --baseline        Fix SOG to route_length / ETA (mean speed); overrides min/max_speed\n"
        "  --csv             Write per-arc solution CSVs (free_dp.csv, luo_dp.csv, baseline.csv)\n",
        prog);
}

int main(int argc, char* argv[]) {
    std::string yaml_path = "weather_forecasts.yaml";
    std::string h5_path   = "voyage_weather.h5";
    std::optional<double> eta_override;
    std::optional<double> min_speed_override;
    std::optional<double> max_speed_override;
    bool baseline_mode = false;
    bool write_csv     = false;

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
        else if (arg == "--csv")       write_csv          = true;
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
    // pin the SOG grid before build_atomic_edges (which reads the grid lazily).
    //
    // Baseline: build H-lines with a wide speed range so the τ-feasibility filter
    // keeps all crossings, then pin the SOG grid to mean_sog before build_atomic_edges
    // reads it (lazy). We use soft-ETA (lam=0) when solving so that the hard ETA
    // boundary does not reject the sink — time-snapping in 160+ H-line edges can push
    // the arrival a few tenths of an hour past ETA.
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

    // ---- Free DP (or Baseline) ----
    // In baseline mode there is only one SOG, so we use soft-ETA (lam=0) to
    // retrieve the fixed-SOG cost without being rejected by the hard ETA boundary.
    print_header(baseline_mode ? "BASELINE — fixed mean SOG" : "DP REBUILD — Free DP (no SOG lock)");
    t0 = std::chrono::steady_clock::now();
    BellmanSolver free_solver(nodes, edges);
    free_solver.solve();
    BellmanResult free_res = baseline_mode
        ? free_solver.result("soft", frame.cfg.eta_h, 0.0)
        : free_solver.result("hard", frame.cfg.eta_h);
    double free_t = std::chrono::duration<double>(
        std::chrono::steady_clock::now() - t0).count();
    printf("  Total fuel:        %.3f mt\n", free_res.total_fuel_mt);
    printf("  Voyage time:       %.3f h\n",  free_res.voyage_time_h);
    if (baseline_mode && free_res.voyage_time_h > frame.cfg.eta_h + 1e-6)
        printf("  (arrived %.2f h after ETA — discretization rounding)\n",
               free_res.voyage_time_h - frame.cfg.eta_h);
    printf("  Sink:              (%.3f h, %.3f nm)\n",
           free_res.sink_node.first, free_res.sink_node.second);
    printf("  Schedule length:   %zu edges\n", free_res.schedule.size());
    printf("  Solve time:        %.3f s\n", free_t);
    printf("  NaN edges skipped: %d\n", free_res.nan_edges_skipped);
    if (write_csv && !baseline_mode)
        write_arc_csv("free_dp.csv", free_res.schedule, edges, WAYPOINTS);

    if (baseline_mode) {
        if (write_csv)
            write_arc_csv("baseline.csv", free_res.schedule, edges, WAYPOINTS);
        print_header("SUMMARY — baseline (fixed mean SOG)");
        printf("  Mean SOG:    %.4f kn\n", frame.cfg.v_min);
        printf("  Total fuel:  %.3f mt\n", free_res.total_fuel_mt);
        printf("  Voyage time: %.3f h  (ETA = %.1f h)\n",
               free_res.voyage_time_h, frame.cfg.eta_h);
        printf("  Graph: %zu nodes, %zu atomic edges, build %.1f s\n\n",
               nodes.size(), edges.size(), build_t);
        return 0;
    }

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
    if (write_csv)
        write_block_csv("luo_dp.csv", luo_res.schedule, edges, WAYPOINTS, frame.cfg.dt_h);

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

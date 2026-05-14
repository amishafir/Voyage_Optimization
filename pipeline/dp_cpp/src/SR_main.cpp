#include "atomic_edges.hpp"
#include "bellman.hpp"
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
#include <string>

namespace fs = std::filesystem;

// Write one CSV row per arc.
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

static void print_header(const char* title) {
    printf("\n%s\n%s\n%s\n",
           std::string(78, '=').c_str(), title,
           std::string(78, '=').c_str());
}

static void usage(const char* prog) {
    fprintf(stderr,
        "Usage: %s [OPTIONS]\n"
        "  --yaml PATH       Route YAML  (default: route.yaml)\n"
        "  --h5   PATH       HDF5 file   (default: voyage_weather.h5)\n"
        "  --eta  HOURS      Override ETA in hours (e.g. 240)\n"
        "  --min_speed KNOTS Minimum SOG in knots (default: mean_sog - 3)\n"
        "  --max_speed KNOTS Maximum SOG in knots (default: mean_sog + 3)\n"
        "  --zeta_nm  NM     Distance snap resolution for H-line arcs (default: 1.0)\n"
        "  --tau_h    HOURS  Time snap resolution for V-line arcs (default: 0.1)\n"
        "  --csv             Write per-arc solution CSV (sr_dp.csv)\n",
        prog);
}

int main(int argc, char* argv[]) {
    std::string yaml_path = "route.yaml";
    std::string h5_path   = "voyage_weather.h5";
    std::optional<double> eta_override;
    std::optional<double> min_speed_override;
    std::optional<double> max_speed_override;
    std::optional<double> zeta_nm_override;
    std::optional<double> tau_h_override;
    bool write_csv = false;

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
        else if (arg == "--zeta_nm")   zeta_nm_override   = std::stod(need_next());
        else if (arg == "--tau_h")     tau_h_override     = std::stod(need_next());
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
    print_header("dp_SR — frame");
    GraphConfig base_cfg = GraphConfig::from_route(route);
    if (eta_override)     base_cfg.eta_h   = *eta_override;
    if (zeta_nm_override) base_cfg.zeta_nm = *zeta_nm_override;
    if (tau_h_override)   base_cfg.tau_h   = *tau_h_override;
    double mean_sog = base_cfg.length_nm / base_cfg.eta_h;
    base_cfg.v_min = min_speed_override.value_or(mean_sog - 3.0);
    base_cfg.v_max = max_speed_override.value_or(mean_sog + 3.0);
    Frame frame = make_frame(route, voyage, WAYPOINTS, &base_cfg);
    summarize_frame(frame);

    // ---- Build atomic-edge graph ----
    print_header("dp_SR — build atomic-edge graph");
    auto t0 = std::chrono::steady_clock::now();
    auto [nodes, edges] = build_atomic_edges(frame, /*forecast_hour=*/-1,
                                              /*override_sample_hour=*/0,
                                              /*verbose=*/false);
    double build_t = std::chrono::duration<double>(
        std::chrono::steady_clock::now() - t0).count();
    printf("\nBuild time: %.2f s\n", build_t);
    summarize_atomic_edges(nodes, edges);

    // ---- dp_SR (SR DP, no SOG lock) ----
    t0 = std::chrono::steady_clock::now();
    BellmanSolver solver(nodes, edges);
    solver.solve();
    BellmanResult res = solver.result("hard", frame.cfg.eta_h);
    double solve_t = std::chrono::duration<double>(
        std::chrono::steady_clock::now() - t0).count();
    if (write_csv)
        write_arc_csv("sr_dp.csv", res.schedule, edges, WAYPOINTS);

    // ---- Summary ----
    print_header("dp_SR — SUMMARY");
    printf("  Total fuel:  %.3f mt\n", res.total_fuel_mt);
    printf("  Voyage time: %.3f h  (ETA = %.1f h)\n", res.voyage_time_h, frame.cfg.eta_h);
    printf("  Graph: %zu nodes, %zu atomic edges\n", nodes.size(), edges.size());
    printf("  Build: %.1f s  Solve: %.2f s\n\n", build_t, solve_t);

    return 0;
}

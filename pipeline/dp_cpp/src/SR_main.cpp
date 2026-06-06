#include "SR_main.hpp"
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
        "  --h5   PATH       HDF5 file   (default: experiment_b_138wp.h5)\n"
        "  --eta  HOURS      Override ETA in hours (e.g. 240)\n"
        "  --min_speed KNOTS Minimum SOG in knots (default: mean_sog - 3)\n"
        "  --max_speed KNOTS Maximum SOG in knots (default: mean_sog + 3)\n"
        "  --zeta_nm  NM     Distance snap resolution for H-line arcs (default: 1.0)\n"
        "  --tau_h    HOURS  Time snap resolution for V-line arcs (default: 0.1)\n"
        "  --sample_hour H   Departure-time anchor (sample_hour at t=0; default: file front)\n"
        "  --csv             Write per-arc solution CSV (sr_dp.csv)\n",
        prog);
}

// Build the atomic-edge graph and solve dp_SR. Verbatim extraction of the
// former main() body (Phase 0): load route → frame → build → Bellman solve.
// No behaviour change — CSV writing and the SUMMARY print stay in main() so the
// console order is preserved.
SRResult sr_solve(const SRArgs& args, const VoyageWeather& voyage,
                  bool verbose, const TimeKey& time_key, double d_start) {
    // ---- Load route ----
    // Dispatches on YAML schema:
    //   "forecasts:"  → legacy segments-table (paper Persian Gulf) + hardcoded WAYPOINTS
    //   "waypoints:"  → lat/lon list (e.g. Atlantic), distances + headings computed
    auto [route, wps] = load_route_auto(args.yaml, args.eta);

    // ---- Build frame ----
    if (verbose) print_header("dp_SR — frame");
    GraphConfig base_cfg = GraphConfig::from_route(route);
    if (args.eta)     base_cfg.eta_h   = *args.eta;
    if (args.zeta_nm) base_cfg.zeta_nm = *args.zeta_nm;
    if (args.tau_h)   base_cfg.tau_h   = *args.tau_h;
    double mean_sog = (base_cfg.length_nm - d_start) / base_cfg.eta_h;
    base_cfg.v_min = args.min_speed.value_or(mean_sog - 3.0);
    base_cfg.v_max = args.max_speed.value_or(mean_sog + 3.0);
    Frame frame = make_frame(route, voyage, wps, &base_cfg, args.sample_hour);
    if (verbose) summarize_frame(frame);

    // ---- Build atomic-edge graph ----
    if (verbose) print_header("dp_SR — build atomic-edge graph");
    auto t0 = std::chrono::steady_clock::now();
    // override_sample_hour = -1 → time-varying weather using the file's
    // sample_hour grid (e.g. 6 h cadence in experiment_b_138wp.h5), with
    // NaN walkback to the most recent valid sample.
    auto [nodes, edges] = build_atomic_edges(frame, /*forecast_hour=*/-1,
                                              /*override_sample_hour=*/-1,
                                              /*verbose=*/false,
                                              time_key, d_start);
    double build_t = std::chrono::duration<double>(
        std::chrono::steady_clock::now() - t0).count();
    if (verbose) {
        printf("\nBuild time: %.2f s\n", build_t);
        summarize_atomic_edges(nodes, edges);
    }

    // ---- dp_SR (SR DP, no SOG lock) ----
    t0 = std::chrono::steady_clock::now();
    BellmanSolver solver(nodes, edges);
    solver.solve();
    BellmanResult res = solver.result("hard", frame.cfg.eta_h);
    double solve_t = std::chrono::duration<double>(
        std::chrono::steady_clock::now() - t0).count();

    SRResult out;
    out.total_fuel_mt = res.total_fuel_mt;
    out.voyage_time_h = res.voyage_time_h;
    out.eta_h         = frame.cfg.eta_h;
    out.n_nodes       = nodes.size();
    out.n_edges       = edges.size();
    out.build_s       = build_t;
    out.solve_s       = solve_t;
    out.schedule      = std::move(res.schedule);
    out.edges         = std::move(edges);
    out.waypoints     = std::move(wps);
    out.sample_hour   = args.sample_hour;
    out.d_start       = d_start;
    return out;
}

int main(int argc, char* argv[]) {
    SRArgs args;
    bool write_csv = false;
    bool smoke = false;

    for (int i = 1; i < argc; ++i) {
        std::string arg = argv[i];
        auto need_next = [&]() -> const char* {
            if (i + 1 >= argc) {
                fprintf(stderr, "Error: %s requires a value\n", arg.c_str());
                std::exit(1);
            }
            return argv[++i];
        };
        if      (arg == "--yaml")      args.yaml      = need_next();
        else if (arg == "--h5")        args.h5        = need_next();
        else if (arg == "--eta")       args.eta       = std::stod(need_next());
        else if (arg == "--min_speed") args.min_speed = std::stod(need_next());
        else if (arg == "--max_speed") args.max_speed = std::stod(need_next());
        else if (arg == "--zeta_nm")   args.zeta_nm   = std::stod(need_next());
        else if (arg == "--tau_h")     args.tau_h     = std::stod(need_next());
        else if (arg == "--sample_hour") args.sample_hour = std::stoi(need_next());
        else if (arg == "--smoke")     smoke          = true;
        else if (arg == "--csv")       write_csv      = true;
        else if (arg == "--help" || arg == "-h") { usage(argv[0]); return 0; }
        else { fprintf(stderr, "Unknown option: %s\n", arg.c_str()); usage(argv[0]); return 1; }
    }

    if (!fs::exists(args.yaml)) {
        fprintf(stderr, "YAML not found: %s\n", args.yaml.c_str());
        return 1;
    }
    if (!fs::exists(args.h5)) {
        fprintf(stderr, "HDF5 not found: %s\n", args.h5.c_str());
        return 1;
    }

    VoyageWeather voyage(args.h5);

    // Backward-compat gate: a time_key mirroring Mode C — actual weather at
    // active_sample_hour — must reproduce the plain Mode C result exactly.
    if (smoke) {
        SRResult m = sr_solve(args, voyage, /*verbose=*/false);
        auto tk = [&voyage](double t) {
            return std::make_pair(voyage.active_sample_hour(t, -1), -1);
        };
        SRResult k = sr_solve(args, voyage, /*verbose=*/false, tk, 0.0);
        bool pass = std::fabs(m.total_fuel_mt - k.total_fuel_mt) < 1e-6;
        printf("SMOKE dp_SR: ModeC=%.3f mt  time_key-identity=%.3f mt  %s\n",
               m.total_fuel_mt, k.total_fuel_mt, pass ? "PASS" : "FAIL");
        return pass ? 0 : 1;
    }

    SRResult r = sr_solve(args, voyage, /*verbose=*/true);

    if (write_csv)
        write_arc_csv("sr_dp.csv", r.schedule, r.edges, r.waypoints);

    // ---- Summary ----
    print_header("dp_SR — SUMMARY");
    printf("  Total fuel:  %.3f mt\n", r.total_fuel_mt);
    printf("  Voyage time: %.3f h  (ETA = %.1f h)\n", r.voyage_time_h, r.eta_h);
    printf("  Graph: %zu nodes, %zu atomic edges\n", r.n_nodes, r.n_edges);
    printf("  Build: %.1f s  Solve: %.2f s\n\n", r.build_s, r.solve_s);

    return 0;
}

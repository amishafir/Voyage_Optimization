// luo_main.cpp — Pure integer-nm block Luo DP
//
// Graph: nodes (col, d_nm) where col indexes a time column.
//   Regular columns:  col = 0..T_steps,  t = 0, dt_h, 2·dt_h, … T_steps·dt_h
//   ETA column:       col = T_steps+1,   t = ETA   (added when ETA % dt_h ≠ 0)
//
// Arcs span one column (one block):
//   Regular arc:  duration = dt_h,     SOG = (d2-d1)/dt_h
//   Partial arc:  duration = dt_last,  SOG = (d2-d1)/dt_last  (last column → ETA)
//
// Arc cost is computed by walking through weather-zone / course-change
// boundaries between d1 and d2 and summing sub-segment fuel at the fixed SOG.
//
// Shortest path from (0, 0) to any (col, L_int) with col ≤ last_col.

#include "frame.hpp"
#include "geo_grid.hpp"
#include "nodes.hpp"
#include "physics.hpp"
#include "route.hpp"
#include "weather.hpp"

#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <limits>
#include <optional>
#include <string>
#include <vector>

namespace fs = std::filesystem;

static constexpr double INF_COST = std::numeric_limits<double>::infinity();
static constexpr double SWS_MAX  = 25.0;
static const     ShipParameters SHIP{};

// ── One weather-zone sub-segment within a block ──────────────────────────
struct Seg {
    double src_d, dst_d;   // [nm]
    double src_t;          // [h] absolute time at sub-segment start
    double sog;            // block SOG [kn] — constant within block
    double heading_deg;
    Weather weather;
    double sws, fcr, fuel_mt, dur_h;
};

// ── Arc result ────────────────────────────────────────────────────────────
struct ArcResult {
    bool   ok = false;
    double fuel = 0.0;
    std::vector<Seg> segs;
};

// Evaluate arc (d1_nm → d2_nm) departing at absolute time t_h over block_dur_h hours.
// Weather is read at sample_hour=0 (static-deterministic snapshot, matching dp_rebuild
// which uses override_sample_hour=0). forecast_hour=-1 → actual_weather table.
// Returns ok=false if any sub-segment has NaN weather or infeasible SWS.
static ArcResult eval_arc(int d1_nm, int d2_nm, int t_h, double block_dur_h,
                           const std::vector<double>& bounds,
                           const Frame& fr) {
    ArcResult r;
    double d1  = (double)d1_nm;
    double d2  = (double)d2_nm;
    double sog = (d2 - d1) / block_dur_h;

    // Collect sub-segment breakpoints strictly inside [d1, d2]
    std::vector<double> pts;
    pts.push_back(d1);
    for (double b : bounds)
        if (b > d1 + 1e-9 && b < d2 - 1e-9)
            pts.push_back(b);
    pts.push_back(d2);

    for (size_t i = 0; i + 1 < pts.size(); ++i) {
        double sd = pts[i], ed = pts[i + 1];
        double heading = fr.paper_heading_at(sd);
        Weather wx = fr.cell_weather_at(sd, /*sample_hour=*/0, /*forecast_hour=*/-1);
        if (wx.has_nan()) return r;

        WeatherDict wd = wx.to_dict();
        double sws = calculate_sws_from_sog(sog, wd, heading, SHIP);
        if (std::isnan(sws) || sws > SWS_MAX) return r;

        double fcr  = calculate_fuel_consumption_rate(sws);
        double dur  = (ed - sd) / sog;
        double fuel = fcr * dur;
        if (std::isnan(fuel)) return r;

        double src_t = t_h + (sd - d1) / sog;
        r.segs.push_back({sd, ed, src_t, sog, heading, wx, sws, fcr, fuel, dur});
        r.fuel += fuel;
    }
    r.ok = true;
    return r;
}

// ── CSV writer ────────────────────────────────────────────────────────────
// One row per sub-segment; block index and block SOG included for context.
static void write_csv(const std::string& path,
                      const std::vector<std::pair<ArcResult, int>>& path_arcs,
                      const std::vector<Waypoint>& wps) {
    std::ofstream f(path);
    f << "block,time_h,distance_nm,lat_deg,lon_deg,bearing_deg,"
         "sog_kn,sws_kn,fcr_mt_per_h,fuel_mt,duration_h,"
         "wind_speed_kmh,wind_dir_deg,beaufort,wave_height_m,"
         "current_vel_kmh,current_dir_deg\n";

    int n_segs = 0;
    for (auto& [arc, blk] : path_arcs) {
        for (const auto& s : arc.segs) {
            auto [lat, lon, _seg] = position_at_d(s.src_d, wps);
            const auto& w = s.weather;
            f << blk         << ','
              << s.src_t     << ','
              << s.src_d     << ','
              << lat << ',' << lon << ','
              << s.heading_deg << ','
              << s.sog       << ','
              << s.sws       << ','
              << s.fcr       << ','
              << s.fuel_mt   << ','
              << s.dur_h     << ','
              << w.wind_speed_10m_kmh       << ','
              << w.wind_direction_10m_deg   << ','
              << w.beaufort_number          << ','
              << w.wave_height_m            << ','
              << w.ocean_current_velocity_kmh   << ','
              << w.ocean_current_direction_deg  << '\n';
            ++n_segs;
        }
    }
    printf("  CSV written: %s  (%d sub-segments, %zu blocks)\n",
           path.c_str(), n_segs, path_arcs.size());
}

static void usage(const char* prog) {
    fprintf(stderr,
        "Usage: %s [OPTIONS]\n"
        "  --yaml PATH       Route YAML  (default: weather_forecasts.yaml)\n"
        "  --h5   PATH       HDF5 file   (default: voyage_weather.h5)\n"
        "  --eta  HOURS      Override ETA in hours\n"
        "  --min_speed KNOTS Minimum SOG  (default: 9)\n"
        "  --max_speed KNOTS Maximum SOG  (default: 13)\n"
        "  --csv             Write luo_dp2.csv\n"
        "  -h / --help       Show this message\n",
        prog);
}

int main(int argc, char* argv[]) {
    std::string yaml_path = "weather_forecasts.yaml";
    std::string h5_path   = "voyage_weather.h5";
    std::optional<double> eta_ov, vmin_ov, vmax_ov;
    bool do_csv = false;

    for (int i = 1; i < argc; ++i) {
        std::string a = argv[i];
        auto nxt = [&]() -> const char* {
            if (i + 1 >= argc) {
                fprintf(stderr, "Missing value for %s\n", a.c_str()); exit(1);
            }
            return argv[++i];
        };
        if      (a == "--yaml")      yaml_path = nxt();
        else if (a == "--h5")        h5_path   = nxt();
        else if (a == "--eta")       eta_ov    = std::stod(nxt());
        else if (a == "--min_speed") vmin_ov   = std::stod(nxt());
        else if (a == "--max_speed") vmax_ov   = std::stod(nxt());
        else if (a == "--csv")       do_csv    = true;
        else if (a == "-h" || a == "--help") { usage(argv[0]); return 0; }
        else { fprintf(stderr, "Unknown option: %s\n", a.c_str()); usage(argv[0]); return 1; }
    }

    if (!fs::exists(yaml_path)) { fprintf(stderr,"YAML not found: %s\n",yaml_path.c_str()); return 1; }
    if (!fs::exists(h5_path))   { fprintf(stderr,"HDF5 not found: %s\n",h5_path.c_str());   return 1; }

    Route route = synthesize_multi_window(load_yaml_route(yaml_path), 6.0);
    VoyageWeather voyage(h5_path);

    GraphConfig cfg = GraphConfig::from_route(route);
    if (eta_ov)  cfg.eta_h = *eta_ov;
    if (vmin_ov) cfg.v_min = *vmin_ov;
    if (vmax_ov) cfg.v_max = *vmax_ov;

    Frame frame = make_frame(route, voyage, WAYPOINTS, &cfg);

    // ── Grid parameters ──────────────────────────────────────────────────
    const int    L_int    = (int)std::round(cfg.length_nm);     // destination [nm]
    const int    T_steps  = (int)(cfg.eta_h / cfg.dt_h);        // # regular blocks
    const double T_max_h  = T_steps * cfg.dt_h;                 // last regular t [h]
    const double dt_last  = cfg.eta_h - T_max_h;                // partial block [h]
    const bool   has_eta  = dt_last > 1e-9;                     // extra ETA column?

    // Regular block step range [nm]
    const int step_min = (int)std::ceil (cfg.v_min * cfg.dt_h);
    const int step_max = (int)std::floor(cfg.v_max * cfg.dt_h);

    // Partial block step range [nm] (only used if has_eta)
    const int step_min_eta = has_eta ? (int)std::ceil (cfg.v_min * dt_last) : 0;
    const int step_max_eta = has_eta ? (int)std::floor(cfg.v_max * dt_last) : 0;

    printf("============================================================\n");
    printf("Luo DP (integer-nm block grid)\n");
    printf("============================================================\n");
    printf("Route:      %.2f nm  →  L = %d nm\n", cfg.length_nm, L_int);
    printf("Speed:      [%.1f, %.1f] kn\n", cfg.v_min, cfg.v_max);
    printf("Regular:    %d blocks × %.0f h, step [%d, %d] nm\n",
           T_steps, cfg.dt_h, step_min, step_max);
    if (has_eta)
        printf("ETA block:  1 × %.1f h (t=%.0f→%.0f), step [%d, %d] nm\n",
               dt_last, T_max_h, cfg.eta_h, step_min_eta, step_max_eta);
    else
        printf("ETA = %.0f h is a multiple of %.0f h — no partial block\n",
               cfg.eta_h, cfg.dt_h);
    printf("H-lines:    %zu boundaries\n", frame.h_line_distances.size());

    // ── Sub-segment boundaries (sorted, deduplicated) ─────────────────────
    std::vector<double> bounds = frame.h_line_distances;
    bounds.push_back(0.0);
    bounds.push_back((double)L_int);
    std::sort(bounds.begin(), bounds.end());
    bounds.erase(
        std::unique(bounds.begin(), bounds.end(),
                    [](double a, double b){ return std::abs(a-b) < 1e-9; }),
        bounds.end());

    // ── DP arrays ─────────────────────────────────────────────────────────
    // dp[d]             = min fuel to reach d at current column
    // parent[col][d]    = d at previous column on optimal path  (-1 = unreachable)
    // col_t[col]        = absolute time [h] at column col
    const int last_col = T_steps + (has_eta ? 1 : 0);
    std::vector<double> dp(L_int + 1, INF_COST);
    std::vector<std::vector<int>> parent(last_col + 1,
                                          std::vector<int>(L_int + 1, -1));
    std::vector<double> col_t(last_col + 1);
    for (int k = 0; k <= T_steps; ++k) col_t[k] = k * cfg.dt_h;
    if (has_eta) col_t[last_col] = cfg.eta_h;

    dp[0] = 0.0;

    double best_fuel = INF_COST;
    int    best_col  = -1;

    auto t_start = std::chrono::steady_clock::now();

    // ── Regular blocks ────────────────────────────────────────────────────
    for (int blk = 0; blk < T_steps; ++blk) {
        int    t_h       = (int)col_t[blk];
        std::vector<double> ndp(L_int + 1, INF_COST);

        for (int d1 = 0; d1 < L_int; ++d1) {
            if (dp[d1] >= INF_COST) continue;

            int d2_lo = std::min(d1 + step_min, L_int);
            int d2_hi = std::min(d1 + step_max, L_int);

            for (int d2 = d2_lo; d2 <= d2_hi; ++d2) {
                auto arc = eval_arc(d1, d2, t_h, cfg.dt_h, bounds, frame);
                if (!arc.ok) continue;

                double nc = dp[d1] + arc.fuel;
                if (nc < ndp[d2]) {
                    ndp[d2]               = nc;
                    parent[blk + 1][d2] = d1;
                }
            }
        }
        dp = ndp;

        if (dp[L_int] < best_fuel) {
            best_fuel = dp[L_int];
            best_col  = blk + 1;
        }
    }

    // ── Partial ETA block ─────────────────────────────────────────────────
    if (has_eta) {
        int    t_h = (int)T_max_h;
        std::vector<double> ndp(L_int + 1, INF_COST);

        for (int d1 = 0; d1 < L_int; ++d1) {
            if (dp[d1] >= INF_COST) continue;

            int d2_lo = std::min(d1 + step_min_eta, L_int);
            int d2_hi = std::min(d1 + step_max_eta, L_int);

            for (int d2 = d2_lo; d2 <= d2_hi; ++d2) {
                auto arc = eval_arc(d1, d2, t_h, dt_last, bounds, frame);
                if (!arc.ok) continue;

                double nc = dp[d1] + arc.fuel;
                if (nc < ndp[d2]) {
                    ndp[d2]               = nc;
                    parent[last_col][d2] = d1;
                }
            }
        }
        dp = ndp;

        if (dp[L_int] < best_fuel) {
            best_fuel = dp[L_int];
            best_col  = last_col;
        }
    }

    double solve_s = std::chrono::duration<double>(
        std::chrono::steady_clock::now() - t_start).count();

    if (best_col < 0) {
        fprintf(stderr, "No feasible path to destination found.\n"); return 1;
    }

    printf("============================================================\n");
    printf("Total fuel:  %.3f mt\n",         best_fuel);
    printf("Voyage time: %.1f h  (%d blocks)\n", col_t[best_col], best_col);
    printf("Solve time:  %.2f s\n",           solve_s);
    printf("============================================================\n");

    // ── Backtrack optimal path ────────────────────────────────────────────
    // path_d[k] = distance [nm] at column k, for k = 0..best_col
    std::vector<int> path_d(best_col + 1);
    path_d[best_col] = L_int;
    for (int k = best_col; k > 0; --k)
        path_d[k - 1] = parent[k][path_d[k]];

    // Print block schedule
    printf("  Block SOG schedule:\n");
    double fuel_check = 0.0;
    for (int k = 0; k < best_col; ++k) {
        double dur = col_t[k + 1] - col_t[k];
        double sog = (double)(path_d[k + 1] - path_d[k]) / dur;
        auto arc = eval_arc(path_d[k], path_d[k + 1], (int)col_t[k], dur, bounds, frame);
        fuel_check += arc.fuel;
        printf("    block %2d: t=%.0f→%.0f h,  d=%4d→%4d nm,  SOG=%.3f kn,  fuel=%.3f mt\n",
               k, col_t[k], col_t[k+1], path_d[k], path_d[k+1], sog, arc.fuel);
    }
    printf("  Total fuel (recomputed): %.3f mt\n", fuel_check);

    // ── CSV ───────────────────────────────────────────────────────────────
    if (do_csv) {
        std::vector<std::pair<ArcResult, int>> path_arcs;
        for (int k = 0; k < best_col; ++k) {
            double dur = col_t[k + 1] - col_t[k];
            auto arc = eval_arc(path_d[k], path_d[k+1], (int)col_t[k], dur, bounds, frame);
            path_arcs.push_back({std::move(arc), k});
        }
        write_csv("luo_dp2.csv", path_arcs, WAYPOINTS);
    }

    return 0;
}

// luo_main.cpp — Pure block Luo DP with configurable distance resolution
//
// Graph: nodes (col, d_idx) where col indexes a time column and d_idx is a
//   distance index; physical distance = d_idx * res_nm.
//   Regular columns:  col = 0..T_steps,  t = 0, dt_h, 2·dt_h, … T_steps·dt_h
//   ETA column:       col = T_steps+1,   t = ETA   (added when ETA % dt_h ≠ 0)
//
// Arcs span one column (one block):
//   Regular arc:  duration = dt_h,     SOG = (d2-d1)*res_nm / dt_h
//   Partial arc:  duration = dt_last,  SOG = (d2-d1)*res_nm / dt_last
//
// Arc cost: walk sub-segments between weather-zone / course-change boundaries
// from d1*res_nm to d2*res_nm, summing fuel at the fixed block SOG. Each
// spatial sub-segment is further split at every sample_hour change so the
// fuel of each piece is computed from the weather active at that absolute
// time. The trip is assumed to start at the earliest sample_hour stored in
// the HDF5 file; absolute voyage time t [h] maps to the largest sample_hour
// in the file that is ≤ (earliest + ⌊t⌋), so any cadence (1 h, 6 h, …) and
// non-uniform sample_hour grids are handled correctly.
//
// Shortest path from (0, 0) to any (col, L_scaled) with col ≤ last_col.

#include "luo_main.hpp"
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

// Seg and ArcResult are declared in luo_main.hpp (so LuoResult can carry them).

// Evaluate arc from grid index d1_idx to d2_idx, departing at t_h [h] over
// block_dur_h hours. Physical distances are d_idx * res_nm.
// Trip start is mapped to the earliest sample_hour in the HDF5 file; within
// each spatial sub-segment the arc is split at every sample_hour transition
// (= sh_list[k] - sh_base) so the fuel of each piece is evaluated against the
// weather active at that absolute time. forecast_hour=-1 → actual_weather.
// Returns ok=false on NaN weather or infeasible SWS.
static ArcResult eval_arc(int d1_idx, int d2_idx, double t_h, double block_dur_h,
                           const std::vector<double>& bounds,
                           const Frame& fr, double res_nm) {
    ArcResult r;
    double d1  = d1_idx * res_nm;
    double d2  = d2_idx * res_nm;
    double sog = (d2 - d1) / block_dur_h;

    const auto& sh_list = fr.voyage->sample_hours();
    if (sh_list.empty()) return r;
    const int sh_base = sh_list.front();

    // Collect spatial sub-segment breakpoints strictly inside [d1, d2]
    std::vector<double> pts;
    pts.push_back(d1);
    for (double b : bounds)
        if (b > d1 + 1e-9 && b < d2 - 1e-9)
            pts.push_back(b);
    pts.push_back(d2);

    for (size_t i = 0; i + 1 < pts.size(); ++i) {
        double sd = pts[i], ed = pts[i + 1];
        double heading = fr.paper_heading_at(sd);

        // Absolute (voyage-relative) time at the spatial sub-segment endpoints
        double t_sd = t_h + (sd - d1) / sog;
        double t_ed = t_h + (ed - d1) / sog;

        // Temporal breakpoints: every sample_hour transition (other than sh_base)
        // strictly inside the time interval, mapped to voyage time t = sh - sh_base
        std::vector<double> t_pts;
        t_pts.push_back(t_sd);
        for (int sh_v : sh_list) {
            if (sh_v == sh_base) continue;
            double t_b = (double)(sh_v - sh_base);
            if (t_b > t_sd + 1e-9 && t_b < t_ed - 1e-9)
                t_pts.push_back(t_b);
            if (t_b >= t_ed) break;
        }
        t_pts.push_back(t_ed);

        for (size_t k = 0; k + 1 < t_pts.size(); ++k) {
            double ta = t_pts[k], tb = t_pts[k + 1];
            double dur = tb - ta;
            if (dur <= 1e-12) continue;

            int sample_hour = fr.voyage->active_sample_hour(ta);

            double da = sd + (ta - t_sd) * sog;
            double db = sd + (tb - t_sd) * sog;

            Weather wx = fr.cell_weather_at(da, sample_hour, /*forecast_hour=*/-1);
            if (wx.has_nan()) {
                // Walk back through sh_list to find the most recent valid sample
                auto it = std::lower_bound(sh_list.begin(), sh_list.end(), sample_hour);
                while (it != sh_list.begin() && wx.has_nan()) {
                    --it;
                    wx = fr.cell_weather_at(da, *it, -1);
                    if (!wx.has_nan()) { sample_hour = *it; break; }
                }
                if (wx.has_nan()) return r;
            }

            WeatherDict wd = wx.to_dict();
            double sws = calculate_sws_from_sog(sog, wd, heading, SHIP);
            if (std::isnan(sws) || sws > SWS_MAX) return r;

            double fcr  = calculate_fuel_consumption_rate(sws);
            double fuel = fcr * dur;
            if (std::isnan(fuel)) return r;

            r.segs.push_back({da, db, ta, sog, heading, wx, sws, fcr, fuel, dur});
            r.fuel += fuel;
        }
    }
    r.ok = true;
    return r;
}

// ── Baseline: fixed mean SOG, no graph ───────────────────────────────────
// Trip starts at the earliest sample_hour in the HDF5 file. Each spatial
// sub-segment is split at every sample_hour transition so each piece is
// evaluated against the weather active at that absolute time.
static std::vector<Seg> eval_baseline(const Frame& fr,
                                       const std::vector<double>& bounds) {
    double sog = fr.cfg.length_nm / fr.cfg.eta_h;
    std::vector<Seg> segs;

    const auto& sh_list = fr.voyage->sample_hours();
    if (sh_list.empty()) return segs;
    const int sh_base = sh_list.front();

    for (size_t i = 0; i + 1 < bounds.size(); ++i) {
        double sd = bounds[i], ed = bounds[i + 1];
        if (ed > fr.cfg.length_nm + 1e-9) ed = fr.cfg.length_nm;
        if (ed <= sd + 1e-9) continue;

        double heading = fr.paper_heading_at(sd);

        // Absolute time at endpoints (trip starts at t=0)
        double t_sd = sd / sog;
        double t_ed = ed / sog;

        // Temporal breakpoints: every sample_hour transition (other than sh_base)
        // strictly inside the time interval, mapped to voyage time t = sh - sh_base
        std::vector<double> t_pts;
        t_pts.push_back(t_sd);
        for (int sh_v : sh_list) {
            if (sh_v == sh_base) continue;
            double t_b = (double)(sh_v - sh_base);
            if (t_b > t_sd + 1e-9 && t_b < t_ed - 1e-9)
                t_pts.push_back(t_b);
            if (t_b >= t_ed) break;
        }
        t_pts.push_back(t_ed);

        for (size_t k = 0; k + 1 < t_pts.size(); ++k) {
            double ta = t_pts[k], tb = t_pts[k + 1];
            double dur = tb - ta;
            if (dur <= 1e-12) continue;

            int sample_hour = fr.voyage->active_sample_hour(ta);

            double da = sd + (ta - t_sd) * sog;
            double db = sd + (tb - t_sd) * sog;

            Weather wx = fr.cell_weather_at(da, sample_hour, /*forecast_hour=*/-1);
            if (wx.has_nan()) {
                // Walk back through sh_list to find the most recent valid sample
                auto it = std::lower_bound(sh_list.begin(), sh_list.end(), sample_hour);
                while (it != sh_list.begin() && wx.has_nan()) {
                    --it;
                    wx = fr.cell_weather_at(da, *it, -1);
                    if (!wx.has_nan()) { sample_hour = *it; break; }
                }
                if (wx.has_nan()) {
                    fprintf(stderr, "  NaN weather at d=%.1f nm, sh=%d — piece skipped\n",
                            da, sample_hour);
                    continue;
                }
            }
            WeatherDict wd = wx.to_dict();
            double sws  = calculate_sws_from_sog(sog, wd, heading, SHIP);
            double fcr  = calculate_fuel_consumption_rate(sws);
            double fuel = fcr * dur;

            segs.push_back({da, db, ta, sog, heading, wx, sws, fcr, fuel, dur});
        }
    }
    return segs;
}

// Write baseline.csv — one row per sub-segment, no block column.
static void write_baseline_csv(const std::string& path,
                                const std::vector<Seg>& segs,
                                const std::vector<Waypoint>& wps) {
    std::ofstream f(path);
    f << "time_h,distance_nm,lat_deg,lon_deg,bearing_deg,"
         "sog_kn,sws_kn,fcr_mt_per_h,fuel_mt,duration_h,"
         "wind_speed_kmh,wind_dir_deg,beaufort,wave_height_m,"
         "current_vel_kmh,current_dir_deg\n";

    for (const auto& s : segs) {
        auto [lat, lon, _seg] = position_at_d(s.src_d, wps);
        const auto& w = s.weather;
        f << s.src_t     << ','
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
    }
    printf("  CSV written: %s  (%zu sub-segments)\n", path.c_str(), segs.size());
}

// ── CSV writer (Luo DP path) ──────────────────────────────────────────────
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
        "  --yaml PATH       Route YAML  (default: route.yaml)\n"
        "  --h5   PATH       HDF5 file   (default: experiment_b_138wp.h5)\n"
        "  --eta  HOURS      Override ETA in hours\n"
        "  --min_speed KNOTS Minimum SOG in knots (default: mean_sog - 3)\n"
        "  --max_speed KNOTS Maximum SOG in knots (default: mean_sog + 3)\n"
        "  --res_nm  NM      Distance grid resolution in NM (default: 1.0, range [0.1, 10])\n"
        "  --baseline        Compute fixed mean-SOG baseline (no graph)\n"
        "  --csv             Write output CSV(s)\n"
        "                    Luo DP  → luo_dp.csv\n"
        "                    Baseline → baseline.csv\n"
        "  -h / --help       Show this message\n",
        prog);
}

// Run dp_luo (or the fixed-mean-SOG baseline). Verbatim extraction of the former
// main() body (Phase 0): load route → frame → grid → DP → backtrack. CSV writing
// stays in main() so console order is preserved; path_arcs is now built
// unconditionally (the RH orchestrator always needs it). No behaviour change.
LuoResult luo_solve(const LuoArgs& args, const VoyageWeather& voyage,
                    bool verbose) {
    const double res_nm = args.res_nm;

    auto [route, wps] = load_route_auto(args.yaml, args.eta);

    GraphConfig cfg = GraphConfig::from_route(route);
    if (args.eta) cfg.eta_h = *args.eta;
    double mean_sog = cfg.length_nm / cfg.eta_h;
    cfg.v_min = args.min_speed.value_or(mean_sog - 3.0);
    cfg.v_max = args.max_speed.value_or(mean_sog + 3.0);

    Frame frame = make_frame(route, voyage, wps, &cfg);

    LuoResult out;
    out.waypoints   = wps;
    out.eta_h       = cfg.eta_h;
    out.sample_hour = args.sample_hour;
    out.d_start     = 0.0;

    // ── Grid parameters ──────────────────────────────────────────────────
    const int    L_scaled = (int)std::round(cfg.length_nm / res_nm); // destination index
    const double L_snapped = L_scaled * res_nm;                       // snapped length [nm]
    const int    T_steps  = (int)(cfg.eta_h / cfg.dt_h);             // # regular blocks
    const double T_max_h  = T_steps * cfg.dt_h;
    const double dt_last  = cfg.eta_h - T_max_h;
    const bool   has_eta  = dt_last > 1e-9;

    // Step range in grid-index units for regular and partial blocks
    const int step_min     = (int)std::ceil (cfg.v_min * cfg.dt_h / res_nm);
    const int step_max     = (int)std::floor(cfg.v_max * cfg.dt_h / res_nm);
    const int step_min_eta = has_eta ? (int)std::ceil (cfg.v_min * dt_last / res_nm) : 0;
    const int step_max_eta = has_eta ? (int)std::floor(cfg.v_max * dt_last / res_nm) : 0;

    if (verbose) {
        printf("============================================================\n");
        printf("Luo DP  (%.2f nm grid resolution)\n", res_nm);
        printf("============================================================\n");
        printf("Route:      %.2f nm  →  L_scaled = %d  (%.2f nm)\n",
               cfg.length_nm, L_scaled, L_snapped);
        printf("Speed:      [%.1f, %.1f] kn\n", cfg.v_min, cfg.v_max);
        printf("Regular:    %d blocks × %.0f h, step [%d, %d] idx  ([%.2f, %.2f] nm)\n",
               T_steps, cfg.dt_h, step_min, step_max,
               step_min * res_nm, step_max * res_nm);
        if (has_eta)
            printf("ETA block:  1 × %.1f h (t=%.0f→%.0f), step [%d, %d] idx\n",
                   dt_last, T_max_h, cfg.eta_h, step_min_eta, step_max_eta);
        else
            printf("ETA = %.0f h is a multiple of %.0f h — no partial block\n",
                   cfg.eta_h, cfg.dt_h);
        printf("H-lines:    %zu boundaries\n", frame.h_line_distances.size());
    }

    // ── Sub-segment boundaries (sorted, deduplicated, physical NM) ────────
    std::vector<double> bounds = frame.h_line_distances;
    bounds.push_back(0.0);
    bounds.push_back(cfg.length_nm);
    std::sort(bounds.begin(), bounds.end());
    bounds.erase(
        std::unique(bounds.begin(), bounds.end(),
                    [](double a, double b){ return std::abs(a-b) < 1e-9; }),
        bounds.end());

    // ── Baseline mode (fixed mean SOG, no graph) ──────────────────────────
    if (args.baseline) {
        if (verbose) {
            printf("============================================================\n");
            printf("Baseline (fixed mean SOG)\n");
            printf("============================================================\n");
            printf("Route:      %.2f nm  ETA: %.1f h\n", cfg.length_nm, cfg.eta_h);
            printf("Mean SOG:   %.4f kn\n", mean_sog);
            printf("Boundaries: %zu sub-segments\n", bounds.size() - 1);
        }

        auto segs = eval_baseline(frame, bounds);
        double total_fuel = 0.0;
        for (const auto& s : segs) total_fuel += s.fuel_mt;

        if (verbose) printf("Total fuel: %.3f mt\n", total_fuel);
        out.baseline_segs = std::move(segs);
        out.total_fuel_mt = total_fuel;
        out.voyage_time_h = cfg.eta_h;
        out.n_blocks      = 0;
        return out;
    }

    // For the Luo DP the terminal boundary must be L_snapped (the grid-snapped
    // destination). Replace the exact cfg.length_nm endpoint with L_snapped.
    bounds.erase(std::remove_if(bounds.begin(), bounds.end(),
                     [&](double b){ return std::abs(b - cfg.length_nm) < 1e-9
                                        && std::abs(b - L_snapped) > 1e-9; }),
                 bounds.end());
    if (bounds.empty() || std::abs(bounds.back() - L_snapped) > 1e-9)
        bounds.push_back(L_snapped);
    std::sort(bounds.begin(), bounds.end());

    // ── DP arrays ─────────────────────────────────────────────────────────
    const int last_col = T_steps + (has_eta ? 1 : 0);
    std::vector<double> dp(L_scaled + 1, INF_COST);
    std::vector<std::vector<int>> parent(last_col + 1,
                                          std::vector<int>(L_scaled + 1, -1));
    std::vector<double> col_t(last_col + 1);
    for (int k = 0; k <= T_steps; ++k) col_t[k] = k * cfg.dt_h;
    if (has_eta) col_t[last_col] = cfg.eta_h;

    dp[0] = 0.0;

    double best_fuel = INF_COST;
    int    best_col  = -1;

    auto t_start = std::chrono::steady_clock::now();

    // ── Regular blocks ────────────────────────────────────────────────────
    for (int blk = 0; blk < T_steps; ++blk) {
        double t_h = col_t[blk];
        std::vector<double> ndp(L_scaled + 1, INF_COST);

        for (int d1 = 0; d1 < L_scaled; ++d1) {
            if (dp[d1] >= INF_COST) continue;

            int d2_lo = std::min(d1 + step_min, L_scaled);
            int d2_hi = std::min(d1 + step_max, L_scaled);

            for (int d2 = d2_lo; d2 <= d2_hi; ++d2) {
                auto arc = eval_arc(d1, d2, t_h, cfg.dt_h, bounds, frame, res_nm);
                if (!arc.ok) continue;

                double nc = dp[d1] + arc.fuel;
                if (nc < ndp[d2]) {
                    ndp[d2]             = nc;
                    parent[blk + 1][d2] = d1;
                }
            }
        }
        dp = ndp;

        if (dp[L_scaled] < best_fuel) {
            best_fuel = dp[L_scaled];
            best_col  = blk + 1;
        }
    }

    // ── Partial ETA block ─────────────────────────────────────────────────
    if (has_eta) {
        double t_h = T_max_h;
        std::vector<double> ndp(L_scaled + 1, INF_COST);

        for (int d1 = 0; d1 < L_scaled; ++d1) {
            if (dp[d1] >= INF_COST) continue;

            int d2_lo = std::min(d1 + step_min_eta, L_scaled);
            int d2_hi = std::min(d1 + step_max_eta, L_scaled);

            for (int d2 = d2_lo; d2 <= d2_hi; ++d2) {
                auto arc = eval_arc(d1, d2, t_h, dt_last, bounds, frame, res_nm);
                if (!arc.ok) continue;

                double nc = dp[d1] + arc.fuel;
                if (nc < ndp[d2]) {
                    ndp[d2]              = nc;
                    parent[last_col][d2] = d1;
                }
            }
        }
        dp = ndp;

        if (dp[L_scaled] < best_fuel) {
            best_fuel = dp[L_scaled];
            best_col  = last_col;
        }
    }

    double solve_s = std::chrono::duration<double>(
        std::chrono::steady_clock::now() - t_start).count();

    if (best_col < 0) {
        fprintf(stderr, "No feasible path to destination found.\n");
        out.feasible = false;
        return out;
    }

    if (verbose) {
        printf("============================================================\n");
        printf("Total fuel:  %.3f mt\n",         best_fuel);
        printf("Voyage time: %.1f h  (%d blocks)\n", col_t[best_col], best_col);
        printf("Solve time:  %.2f s\n",           solve_s);
        printf("============================================================\n");
    }

    // ── Backtrack optimal path ────────────────────────────────────────────
    std::vector<int> path_d(best_col + 1);
    path_d[best_col] = L_scaled;
    for (int k = best_col; k > 0; --k)
        path_d[k - 1] = parent[k][path_d[k]];

    // Reconstruct per-block arcs (always — the RH orchestrator needs them; CSV
    // writing in main() reuses these).
    std::vector<std::pair<ArcResult, int>> path_arcs;
    for (int k = 0; k < best_col; ++k) {
        double dur = col_t[k + 1] - col_t[k];
        auto arc = eval_arc(path_d[k], path_d[k+1], col_t[k], dur, bounds, frame, res_nm);
        path_arcs.push_back({std::move(arc), k});
    }

    out.path_arcs     = std::move(path_arcs);
    out.total_fuel_mt = best_fuel;
    out.voyage_time_h = col_t[best_col];
    out.n_blocks      = best_col;
    out.solve_s       = solve_s;
    return out;
}

int main(int argc, char* argv[]) {
    LuoArgs args;
    bool do_csv = false;

    for (int i = 1; i < argc; ++i) {
        std::string a = argv[i];
        auto nxt = [&]() -> const char* {
            if (i + 1 >= argc) {
                fprintf(stderr, "Missing value for %s\n", a.c_str()); exit(1);
            }
            return argv[++i];
        };
        if      (a == "--yaml")      args.yaml      = nxt();
        else if (a == "--h5")        args.h5        = nxt();
        else if (a == "--eta")       args.eta       = std::stod(nxt());
        else if (a == "--min_speed") args.min_speed = std::stod(nxt());
        else if (a == "--max_speed") args.max_speed = std::stod(nxt());
        else if (a == "--res_nm")    args.res_nm    = std::stod(nxt());
        else if (a == "--baseline")  args.baseline  = true;
        else if (a == "--csv")       do_csv         = true;
        else if (a == "-h" || a == "--help") { usage(argv[0]); return 0; }
        else { fprintf(stderr, "Unknown option: %s\n", a.c_str()); usage(argv[0]); return 1; }
    }

    if (args.res_nm < 0.1 || args.res_nm > 10.0) {
        fprintf(stderr, "Error: --res_nm must be in [0.1, 10.0], got %.3f\n", args.res_nm);
        return 1;
    }

    if (!fs::exists(args.yaml)) { fprintf(stderr,"YAML not found: %s\n",args.yaml.c_str()); return 1; }
    if (!fs::exists(args.h5))   { fprintf(stderr,"HDF5 not found: %s\n",args.h5.c_str());   return 1; }

    VoyageWeather voyage(args.h5);
    LuoResult r = luo_solve(args, voyage, /*verbose=*/true);
    if (!r.feasible) return 1;

    if (do_csv) {
        if (args.baseline)
            write_baseline_csv("baseline.csv", r.baseline_segs, r.waypoints);
        else
            write_csv("luo_dp.csv", r.path_arcs, r.waypoints);
    }

    return 0;
}

#include "nodes.hpp"
#include "geo_grid.hpp"
#include <algorithm>
#include <cmath>
#include <set>

GraphConfig GraphConfig::from_route(const Route& route,
                                     double dt_h, double zeta_nm,
                                     double tau_h, double weather_cell_nm,
                                     double v_min, double v_max) {
    return {route.length_nm(), route.eta_h(),
            dt_h, zeta_nm, tau_h, weather_cell_nm, v_min, v_max};
}

static double round9(double x) {
    return std::round(x * 1e9) / 1e9;
}

std::vector<double> v_line_times_from_route(const GraphConfig& cfg, const Route& route) {
    std::set<double> times;
    int k = 1;
    while (k * cfg.dt_h < cfg.eta_h - 1e-9)
        times.insert(round9(k++ * cfg.dt_h));
    times.insert(round9(cfg.eta_h));
    for (auto& w : route.windows)
        if (w.end > 1e-9)
            times.insert(round9(w.end));
    return std::vector<double>(times.begin(), times.end());
}

std::vector<double> h_line_distances_from_route(const GraphConfig& cfg, const Route& route) {
    std::set<double> distances;
    double cum = 0.0;
    for (auto& seg : route.windows[0].segments) {
        double seg_end = cum + seg.distance;
        double d_sub = cum + cfg.weather_cell_nm;
        while (d_sub < seg_end - 1e-9) {
            distances.insert(round9(d_sub));
            d_sub += cfg.weather_cell_nm;
        }
        if (1e-9 < seg_end && seg_end < cfg.length_nm - 1e-9)
            distances.insert(round9(seg_end));
        cum = seg_end;
    }
    distances.insert(round9(cfg.length_nm));
    return std::vector<double>(distances.begin(), distances.end());
}

std::vector<double> h_line_distances_from_geo(const GraphConfig& cfg,
                                               const std::vector<Waypoint>& waypoints,
                                               double grid_deg) {
    std::set<double> h_set;
    double cum = 0.0;
    int n_seg = (int)waypoints.size() - 1;
    double L_rounded = round9(cfg.length_nm);

    for (int seg_idx = 0; seg_idx < n_seg; ++seg_idx) {
        const auto& wp1 = waypoints[seg_idx];
        const auto& wp2 = waypoints[seg_idx + 1];
        double seg_dist = rhumb_distance_nm(wp1.lat_deg, wp1.lon_deg,
                                            wp2.lat_deg, wp2.lon_deg);
        auto crossings = rhumb_grid_crossings(wp1.lat_deg, wp1.lon_deg,
                                              wp2.lat_deg, wp2.lon_deg, grid_deg);
        for (auto& c : crossings) {
            double d_voy = cum + c.distance_nm;
            if (d_voy > 1e-6 && d_voy < cfg.length_nm - 1e-6)
                h_set.insert(round9(d_voy));
        }
        cum += seg_dist;
        if (seg_idx < n_seg - 1 && cum > 1e-6 && cum < cfg.length_nm - 1e-6)
            h_set.insert(round9(cum));
    }
    h_set.insert(L_rounded);

    // Enforce τ-grid feasibility: gap G is feasible if ∃ k ≥ 1 s.t.
    //   k·τ·v_min ≤ G ≤ k·τ·v_max
    auto feasible = [&](double G) -> bool {
        if (G <= 1e-9) return false;
        int k_min = std::max(1, (int)std::ceil(G / (cfg.v_max * cfg.tau_h) - 1e-9));
        int k_max = (int)std::floor(G / (cfg.v_min * cfg.tau_h) + 1e-9);
        return k_min <= k_max;
    };

    std::vector<double> sorted_h(h_set.begin(), h_set.end());
    std::vector<double> kept;
    int dropped = 0;
    double prev = 0.0;
    for (double d : sorted_h) {
        if (feasible(d - prev)) { kept.push_back(d); prev = d; }
        else                     ++dropped;
    }
    // Ensure terminal is reachable
    while (kept.size() >= 1 && kept.back() != L_rounded
           && !feasible(L_rounded - (kept.size() >= 2 ? kept[kept.size()-2] : 0.0))) {
        ++dropped;
        kept.pop_back();
    }
    if (kept.empty() || kept.back() != L_rounded)
        kept.push_back(L_rounded);

    if (dropped)
        printf("[h_line_distances_from_geo] dropped %d τ-infeasible H-lines\n", dropped);
    return kept;
}

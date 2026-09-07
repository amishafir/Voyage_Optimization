#pragma once
#include "route.hpp"
#include <vector>

enum class LineType { V, H };

struct Node {
    double   time_h;
    double   distance_nm;
    LineType line_type;
    bool     is_source = false;
    bool     is_sink   = false;
};

struct GraphConfig {
    double length_nm;
    double eta_h;
    double dt_h            = 6.0;
    double zeta_nm         = 1.0;
    double tau_h           = 0.1;
    double weather_cell_nm = 30.0;
    double v_min           = 9.0;
    double v_max           = 13.0;

    static GraphConfig from_route(const Route& route,
                                   double dt_h = 6.0, double zeta_nm = 1.0,
                                   double tau_h = 0.1, double weather_cell_nm = 30.0,
                                   double v_min = 9.0, double v_max = 13.0);
};

// V-line times: dt_h cadence ∪ forecast-window boundaries ∪ {ETA}
std::vector<double> v_line_times_from_route(const GraphConfig& cfg, const Route& route);

// H-line distances: segment boundaries ∪ cell crossings ∪ {L}
// Uses analytic rhumb-line / NWP-grid crossing geometry (Qg1-Qg4).
// Enforces τ-grid traversability (drops infeasible sub-nm gaps).
// Cumulative rhumb distance through a waypoint polyline: [d_1 .. d_{n-1}].
// Under the waypoint partition these ARE the H-line distances. d_0 = 0 is the
// implicit voyage start (matching h_line_distances_from_geo).
template <typename WP>
std::vector<double> cumulative_rhumb_nm(const std::vector<WP>& wps) {
    std::vector<double> out;
    double d = 0.0;
    for (size_t i = 0; i + 1 < wps.size(); ++i) {
        d += rhumb_distance_nm(wps[i].lat_deg, wps[i].lon_deg,
                               wps[i + 1].lat_deg, wps[i + 1].lon_deg);
        out.push_back(std::round(d * 1e9) / 1e9);
    }
    return out;
}

// tau-grid traversability as an invariant rather than a filter. Under uniform
// spacing every segment is traversable, so this never fires; a failure means a
// problem upstream. It must not silently delete H-lines - that is what made
// the spatial grid a function of the speed band and hence of the ETA.
void assert_tau_feasible(const GraphConfig& cfg,
                          const std::vector<double>& h_dists);

std::vector<double> h_line_distances_from_geo(const GraphConfig& cfg,
                                               const std::vector<Waypoint>& waypoints,
                                               double grid_deg = 0.5);

// Legacy: H-line from YAML (segment boundaries + uniform weather_cell_nm sub-lines)
std::vector<double> h_line_distances_from_route(const GraphConfig& cfg, const Route& route);

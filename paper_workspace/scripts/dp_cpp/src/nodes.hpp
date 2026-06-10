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
std::vector<double> h_line_distances_from_geo(const GraphConfig& cfg,
                                               const std::vector<Waypoint>& waypoints,
                                               double grid_deg = 0.5);

// Legacy: H-line from YAML (segment boundaries + uniform weather_cell_nm sub-lines)
std::vector<double> h_line_distances_from_route(const GraphConfig& cfg, const Route& route);

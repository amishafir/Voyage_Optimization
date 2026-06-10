#pragma once
#include "geo_grid.hpp"
#include <optional>
#include <string>
#include <vector>

struct Segment {
    int    id;
    double distance;      // nm
    double ship_heading;  // deg
};

struct ForecastWindow {
    double start;  // hours
    double end;    // hours
    std::vector<Segment> segments;
};

struct Route {
    std::vector<ForecastWindow> windows;

    double length_nm() const;
    double eta_h() const;

    std::vector<double> cumulative_segment_endpoints() const;
    const Segment& segment_for_distance(double d, int window_idx = 0) const;
    const ForecastWindow& window_for_time(double t) const;
    const Segment& weather_at(double t, double d) const;
};

Route load_yaml_route(const std::string& path);
Route synthesize_multi_window(const Route& route, double window_h = 6.0);

// ---- Paper waypoints (route_waypoints.py) ----
struct Waypoint {
    int    idx;
    double lat_deg;
    double lon_deg;
    std::optional<std::string> name;
    std::optional<int>    segment_to_next;
    std::optional<double> heading_deg;
    std::optional<double> distance_nm;
    std::optional<double> sws_kn;
    std::optional<double> fuel_paper_mt;
    std::optional<double> wind_dir_deg;
    std::optional<int>    beaufort;
    std::optional<double> wave_height_m;
    std::optional<double> current_dir_deg;
    std::optional<double> current_speed_kn;
};

extern const std::vector<Waypoint> WAYPOINTS;

// Build a Route from a waypoint-only YAML (no paper β metadata)
std::pair<Route, std::vector<Waypoint>>
build_route_from_waypoints_yaml(const std::string& yaml_path,
                                 std::optional<double> eta_h = std::nullopt,
                                 double cruise_sog_kn = 12.0);

// Dispatcher: picks the right loader based on YAML schema.
//   yaml has "forecasts:"  → load_yaml_route (legacy segments-table)  +  hardcoded WAYPOINTS
//   yaml has "waypoints:"  → build_route_from_waypoints_yaml (computed from lat/lon)
std::pair<Route, std::vector<Waypoint>>
load_route_auto(const std::string& yaml_path,
                std::optional<double> eta_h_opt = std::nullopt,
                double cruise_sog_kn = 12.0);

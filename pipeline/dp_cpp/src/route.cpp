#include "route.hpp"
#include <algorithm>
#include <cmath>
#include <stdexcept>
#include <yaml-cpp/yaml.h>

// ---- Route methods ----

double Route::length_nm() const {
    if (windows.empty()) return 0.0;
    double s = 0.0;
    for (auto& seg : windows[0].segments) s += seg.distance;
    return s;
}

double Route::eta_h() const {
    return windows.empty() ? 0.0 : windows.back().end;
}

std::vector<double> Route::cumulative_segment_endpoints() const {
    if (windows.empty()) return {};
    std::vector<double> out;
    double cum = 0.0;
    const auto& segs = windows[0].segments;
    for (int i = 0; i + 1 < (int)segs.size(); ++i) {
        cum += segs[i].distance;
        out.push_back(cum);
    }
    return out;
}

const Segment& Route::segment_for_distance(double d, int window_idx) const {
    double cum = 0.0;
    const auto& segs = windows[window_idx].segments;
    for (auto& s : segs) {
        cum += s.distance;
        if (d <= cum + 1e-9) return s;
    }
    return segs.back();
}

const ForecastWindow& Route::window_for_time(double t) const {
    for (auto& w : windows)
        if (w.start - 1e-9 <= t && t < w.end - 1e-9) return w;
    return windows.back();
}

const Segment& Route::weather_at(double t, double d) const {
    const auto& w = window_for_time(t);
    double cum = 0.0;
    for (auto& s : w.segments) {
        cum += s.distance;
        if (d <= cum + 1e-9) return s;
    }
    return w.segments.back();
}

// ---- YAML loader ----

Route load_yaml_route(const std::string& path) {
    YAML::Node data = YAML::LoadFile(path);
    Route route;
    for (auto wnode : data["forecasts"]) {
        ForecastWindow fw;
        auto fwmap = wnode["forecast_window"];
        fw.start = fwmap["start"].as<double>();
        fw.end   = fwmap["end"].as<double>();
        for (auto snode : wnode["segments_table"]) {
            Segment seg;
            seg.id           = snode["id"].as<int>();
            seg.distance     = snode["distance"].as<double>();
            seg.ship_heading = snode["ship_heading"].as<double>();
            seg.wind_dir     = snode["wind_dir"].as<double>();
            seg.beaufort     = snode["beaufort"].as<int>();
            seg.wave_height  = snode["wave_height"].as<double>();
            seg.current_dir  = snode["current_dir"].as<double>();
            seg.current_speed= snode["current_speed"].as<double>();
            fw.segments.push_back(seg);
        }
        route.windows.push_back(fw);
    }
    return route;
}

Route synthesize_multi_window(const Route& route, double window_h) {
    if (route.windows.empty()) return route;
    const auto& base_segs = route.windows[0].segments;
    double eta = route.eta_h();
    Route out;
    double t = 0.0;
    while (t < eta - 1e-9) {
        double t_end = std::min(t + window_h, eta);
        ForecastWindow fw;
        fw.start    = t;
        fw.end      = t_end;
        fw.segments = base_segs;
        out.windows.push_back(fw);
        t = t_end;
    }
    return out;
}

// ---- Waypoint YAML loader ----

std::pair<Route, std::vector<Waypoint>>
build_route_from_waypoints_yaml(const std::string& yaml_path,
                                 std::optional<double> eta_h_opt,
                                 double cruise_sog_kn) {
    YAML::Node data = YAML::LoadFile(yaml_path);
    auto raw = data["waypoints"];
    if (!raw || raw.size() < 2)
        throw std::runtime_error("Route YAML must have >= 2 waypoints");

    std::vector<Waypoint> wps;
    int idx = 1;
    for (auto node : raw) {
        Waypoint wp;
        wp.idx     = idx++;
        wp.lat_deg = node["lat"].as<double>();
        wp.lon_deg = node["lon"].as<double>();
        if (node["name"]) wp.name = node["name"].as<std::string>();
        wps.push_back(wp);
    }

    std::vector<Segment> segs;
    double total_d = 0.0;
    for (int i = 0; i + 1 < (int)wps.size(); ++i) {
        Segment s;
        s.id           = i + 1;
        s.distance     = rhumb_distance_nm(wps[i].lat_deg, wps[i].lon_deg,
                                            wps[i+1].lat_deg, wps[i+1].lon_deg);
        s.ship_heading = rhumb_bearing_deg(wps[i].lat_deg, wps[i].lon_deg,
                                            wps[i+1].lat_deg, wps[i+1].lon_deg);
        s.wind_dir = s.beaufort = 0;
        s.wave_height = s.current_dir = s.current_speed = 0.0;
        total_d += s.distance;
        segs.push_back(s);
    }
    double eta = eta_h_opt.value_or(total_d / cruise_sog_kn);
    ForecastWindow fw{0.0, eta, segs};
    Route route;
    route.windows.push_back(fw);
    return {route, wps};
}

// ---- Hard-coded paper waypoints (route_waypoints.py) ----

const std::vector<Waypoint> WAYPOINTS = {
    {1, 24.75, 52.83, "Port A (Persian Gulf)", 1,  61.25, 223.86, 12.7, 25.54, 139.0, 3, 1.0, 245.0, 0.30},
    {2, 26.55, 56.45, "Gulf of Oman",          2, 121.53, 282.54, 12.6, 31.93, 207.0, 3, 1.0, 248.0, 0.72},
    {3, 24.08, 60.88, std::nullopt,             3, 117.61, 303.18, 12.7, 32.33,   9.0, 4, 1.5, 158.0, 0.73},
    {4, 21.73, 65.73, std::nullopt,             4, 139.03, 298.44, 12.5, 32.18, 201.0, 4, 1.5, 178.0, 0.21},
    {5, 17.96, 69.19, std::nullopt,             5, 143.63, 280.51, 12.3, 31.66,  88.0, 5, 2.5, 135.0, 0.49},
    {6, 14.18, 72.07, std::nullopt,             6, 140.84, 287.34, 12.2, 32.60,  86.0, 4, 1.5, 113.0, 0.22},
    {7, 10.45, 75.16, std::nullopt,             7, 136.42, 284.40, 12.2, 32.00, 353.0, 3, 1.0, 338.0, 0.54},
    {8,  7.00, 78.46, std::nullopt,             8, 110.37, 233.25, 12.2, 30.74,  35.0, 5, 2.5, 290.0, 1.25},
    {9,  5.64, 82.12, std::nullopt,             9, 102.57, 301.80, 12.8, 33.72, 269.0, 4, 1.5, 270.0, 0.28},
    {10, 4.54, 87.04, std::nullopt,            10,  82.83, 315.70, 12.6, 32.32, 174.0, 3, 1.0,  93.0, 0.72},
    {11, 5.20, 92.27, std::nullopt,            11,  84.87, 293.80, 12.7, 34.41,  60.0, 1, 0.1, 185.0, 0.62},
    {12, 5.64, 97.16, std::nullopt,            12, 142.39, 288.42, 12.3, 31.57, 315.0, 3, 1.0,  90.0, 0.30},
    {13, 1.81,100.10, "Port B (Strait of Malacca)", std::nullopt, std::nullopt, std::nullopt,
                       std::nullopt, std::nullopt, std::nullopt, std::nullopt, std::nullopt,
                       std::nullopt, std::nullopt},
};

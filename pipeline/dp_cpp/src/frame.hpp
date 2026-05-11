#pragma once
#include "nodes.hpp"
#include "weather.hpp"
#include <optional>
#include <vector>

class Frame {
public:
    GraphConfig            cfg;
    Route                  route;
    const VoyageWeather*   voyage;          // non-owning
    std::vector<Waypoint>  waypoints;       // paper waypoints
    std::vector<double>    v_line_times;
    std::vector<double>    h_line_distances;
    double                 grid_deg  = 0.5;
    double                 sog_step  = 0.1; // kn

    // SOG decision grid [v_min, v_max] at sog_step
    const std::vector<double>& sog_grid() const;

    std::optional<double> next_v_time(double t, double eps = 1e-9) const;
    std::optional<double> next_h_distance(double d, double eps = 1e-9) const;

    int    block_index(double t) const { return (int)(t / cfg.dt_h); }
    double block_start_time(double t) const { return cfg.dt_h * block_index(t); }
    int    sample_hour_for_block(double t) const {
        return static_cast<int>(std::round(block_start_time(t))); }

    double snap_v_dst_d(double d) const {
        return std::round(d / cfg.zeta_nm) * cfg.zeta_nm; }
    double snap_h_dst_t(double t) const {
        return std::round(t / cfg.tau_h) * cfg.tau_h; }

    Weather cell_weather_at(double d, int sample_hour, int forecast_hour = -1) const;
    double  paper_heading_at(double d) const;

private:
    mutable std::vector<double> sog_grid_cache_;
};

Frame make_frame(const Route& route, const VoyageWeather& voyage,
                  const std::vector<Waypoint>& waypoints,
                  const GraphConfig* cfg_override = nullptr,
                  double grid_deg = 0.5, double sog_step = 0.1);

void summarize_frame(const Frame& frame);

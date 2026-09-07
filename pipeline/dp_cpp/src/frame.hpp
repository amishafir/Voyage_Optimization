#pragma once
#include "nodes.hpp"
#include "weather.hpp"
#include <optional>
#include <string>
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
    // "geo"      - H-lines at 0.5 deg crossings, weather from the cell mean (legacy)
    // "waypoint" - H-lines at the sample points, weather from the source waypoint
    std::string            partition = "geo";
    std::vector<double>    segment_heading;   // one rhumb bearing per segment
    std::vector<int>       segment_src_node;  // node_id sourcing each segment
    double                 sog_step  = 0.1; // kn
    int                    base_sample_hour = 0;  // departure-time anchor (0 = file front)

    // SOG decision grid [v_min, v_max] at sog_step
    const std::vector<double>& sog_grid() const;

    std::optional<double> next_v_time(double t, double eps = 1e-9) const;
    std::optional<double> next_h_distance(double d, double eps = 1e-9) const;

    int    block_index(double t) const { return (int)(t / cfg.dt_h); }
    double block_start_time(double t) const { return cfg.dt_h * block_index(t); }
    int    sample_hour_for_block(double t) const {
        return base_sample_hour + static_cast<int>(std::round(block_start_time(t))); }

    double snap_v_dst_d(double d) const {
        return std::round(d / cfg.zeta_nm) * cfg.zeta_nm; }
    double snap_h_dst_t(double t) const {
        return std::round(t / cfg.tau_h) * cfg.tau_h; }

    // Index of the segment a source at distance d departs into. Exact by
    // construction: h_line_distances holds the very numbers that define the
    // boundaries, so a source on a line resolves to the segment it is about to
    // traverse - no derived coordinate to round, hence none of the
    // floor(lat/0.5) ambiguity the cell path has.
    int segment_index(double d) const;

    // Whether a reading is too incomplete to price an arc. Under the waypoint
    // partition only the consumed fields can invalidate an arc.
    bool weather_unusable(const Weather& w) const {
        return partition == "waypoint" ? w.has_nan_consumed() : w.has_nan();
    }

    Weather cell_weather_at(double d, int sample_hour, int forecast_hour = -1) const;
    double  paper_heading_at(double d) const;

private:
    mutable std::vector<double> sog_grid_cache_;
};

Frame make_frame(const Route& route, const VoyageWeather& voyage,
                  const std::vector<Waypoint>& waypoints,
                  const GraphConfig* cfg_override = nullptr,
                  int base_sample_hour = 0,
                  double grid_deg = 0.5, double sog_step = 0.1,
                  const std::string& partition = "geo");

void summarize_frame(const Frame& frame);

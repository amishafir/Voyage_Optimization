#include "frame.hpp"
#include "geo_grid.hpp"
#include <algorithm>
#include <cmath>
#include <cstdio>

const std::vector<double>& Frame::sog_grid() const {
    if (sog_grid_cache_.empty()) {
        int n = (int)std::round((cfg.v_max - cfg.v_min) / sog_step) + 1;
        sog_grid_cache_.reserve(n);
        for (int i = 0; i < n; ++i)
            sog_grid_cache_.push_back(
                std::round((cfg.v_min + i * sog_step) * 1e6) / 1e6);
    }
    return sog_grid_cache_;
}

std::optional<double> Frame::next_v_time(double t, double eps) const {
    auto it = std::upper_bound(v_line_times.begin(), v_line_times.end(), t + eps);
    if (it == v_line_times.end()) return std::nullopt;
    return *it;
}

std::optional<double> Frame::next_h_distance(double d, double eps) const {
    auto it = std::upper_bound(h_line_distances.begin(), h_line_distances.end(), d + eps);
    if (it == h_line_distances.end()) return std::nullopt;
    return *it;
}

Weather Frame::cell_weather_at(double d, int sample_hour, int forecast_hour) const {
    auto dict = voyage->cell_weather_at_d(d, waypoints, sample_hour, forecast_hour, grid_deg);
    return Weather::from_dict(dict);
}

double Frame::paper_heading_at(double d) const {
    auto [_lat, _lon, seg_idx] = position_at_d(d, waypoints);
    const auto& segs = route.windows[0].segments;
    int clamped = std::max(0, std::min(seg_idx, (int)segs.size() - 1));
    return segs[clamped].ship_heading;
}

Frame make_frame(const Route& route, const VoyageWeather& voyage,
                  const std::vector<Waypoint>& waypoints,
                  const GraphConfig* cfg_override,
                  int base_sample_hour,
                  double grid_deg, double sog_step) {
    Frame f;
    f.route    = route;
    f.voyage   = &voyage;
    f.waypoints= waypoints;
    f.grid_deg = grid_deg;
    f.sog_step = sog_step;
    f.base_sample_hour = base_sample_hour;

    if (cfg_override)
        f.cfg = *cfg_override;
    else
        f.cfg = GraphConfig::from_route(route, 6.0, 1.0, 0.1, 30.0, 9.0, 13.0);

    f.v_line_times    = v_line_times_from_route(f.cfg, route);
    f.h_line_distances = h_line_distances_from_geo(f.cfg, waypoints, grid_deg);
    return f;
}

void summarize_frame(const Frame& f) {
    const auto& sg = f.sog_grid();
    int n_blocks = static_cast<int>(f.cfg.eta_h / f.cfg.dt_h);
    printf("============================================================\n");
    printf("DP rebuild — Frame summary\n");
    printf("============================================================\n");
    printf("Route:         L = %.3f nm, ETA = %.1f h\n", f.cfg.length_nm, f.cfg.eta_h);
    printf("V-lines:       %zu times, first = %.2f h, last = %.2f h\n",
           f.v_line_times.size(), f.v_line_times.front(), f.v_line_times.back());
    printf("               dt_h = %.1f h, zeta_nm = %.1f nm\n", f.cfg.dt_h, f.cfg.zeta_nm);
    printf("H-lines:       %zu distances\n", f.h_line_distances.size());
    printf("               tau_h = %.2f h\n", f.cfg.tau_h);
    printf("SOG grid:      %zu target SOGs in [%.1f, %.1f] kn at %.2f kn step\n",
           sg.size(), sg.front(), sg.back(), f.sog_step);
    printf("Blocks:        %d blocks of %.1f h\n", n_blocks, f.cfg.dt_h);
    printf("============================================================\n");
}

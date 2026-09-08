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

int Frame::segment_index(double d) const {
    auto it = std::upper_bound(h_line_distances.begin(), h_line_distances.end(), d);
    int k = (int)(it - h_line_distances.begin());
    if (k < 0) k = 0;
    if (k > (int)h_line_distances.size() - 1) k = (int)h_line_distances.size() - 1;
    return k;
}

Weather Frame::cell_weather_at(double d, int sample_hour, int forecast_hour) const {
    if (partition == "waypoint") {
        int k = segment_index(d);
        return Weather::from_dict(
            voyage->weather_at_waypoint(segment_src_node[k], sample_hour, forecast_hour));
    }
    auto dict = voyage->cell_weather_at_d(d, waypoints, sample_hour, forecast_hour, grid_deg);
    return Weather::from_dict(dict);
}

double Frame::paper_heading_at(double d) const {
    // partition="waypoint": the segment's own rhumb bearing. This also fixes
    // the boundary case - position_at_d resolves a distance lying exactly on a
    // segment boundary to the segment that *ends* there, so the legacy path
    // prices the outgoing leg with the incoming heading.
    if (partition == "waypoint")
        return segment_heading[segment_index(d)];
    auto [_lat, _lon, seg_idx] = position_at_d(d, waypoints);
    const auto& segs = route.windows[0].segments;
    int clamped = std::max(0, std::min(seg_idx, (int)segs.size() - 1));
    return segs[clamped].ship_heading;
}

Frame make_frame(const Route& route, const VoyageWeather& voyage,
                  const std::vector<Waypoint>& waypoints,
                  const GraphConfig* cfg_override,
                  int base_sample_hour,
                  double grid_deg, double sog_step,
                  const std::string& partition) {
    Frame f;
    f.partition = partition;
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

    if (partition == "waypoint") {
        // The sample points define the partition. `waypoints` stays the paper
        // polyline so the output path (position_at_d) is untouched and both
        // engines agree; the partition needs only the three arrays below.
        const auto& samples = voyage.waypoints();
        std::vector<double> cum;
        cum.push_back(0.0);
        for (double v : cumulative_rhumb_nm(samples)) cum.push_back(v);
        const double L = cum.back();
        f.cfg.length_nm = L;

        // Only sample points that actually carry a reading may place an H-line.
        auto usable = voyage.usable_node_ids();
        std::vector<size_t> idx;
        for (size_t i = 0; i < samples.size(); ++i)
            if (usable.count(samples[i].node_id)) idx.push_back(i);
        if (idx.empty() || idx.front() != 0) {
            fprintf(stderr, "[make_frame] partition=waypoint needs a usable reading "
                            "at the first sample point\n");
            std::abort();
        }
        size_t dropped = samples.size() - idx.size();
        if (dropped) {
            printf("[frame] partition=waypoint: %zu of %zu sample points carry no "
                   "valid reading and place no H-line\n", dropped, samples.size());
        }

        // Segment k spans [cum[idx[k]], bounds[k]), sourced at idx[k]. A
        // trailing run of unusable points extends the final segment to L.
        std::vector<double> bounds;
        for (size_t j = 1; j < idx.size(); ++j) bounds.push_back(cum[idx[j]]);
        if (bounds.empty() || bounds.back() < L - 1e-9)
            bounds.push_back(std::round(L * 1e9) / 1e9);
        f.h_line_distances = bounds;

        std::vector<size_t> ends(idx.begin() + 1, idx.end());
        if (idx.back() != samples.size() - 1) ends.push_back(samples.size() - 1);
        for (size_t k = 0; k < f.h_line_distances.size(); ++k) {
            size_t i0 = idx[k], i1 = ends[k];
            f.segment_src_node.push_back(samples[i0].node_id);
            f.segment_heading.push_back(rhumb_bearing_deg(
                samples[i0].lat_deg, samples[i0].lon_deg,
                samples[i1].lat_deg, samples[i1].lon_deg));
        }
        assert_tau_feasible(f.cfg, f.h_line_distances);
    } else if (partition == "geo") {
        f.h_line_distances = h_line_distances_from_geo(f.cfg, waypoints, grid_deg);
    } else {
        // Previously an unrecognised string fell through to geo and ran
        // silently, so a typo produced a plausible published-path result.
        fprintf(stderr, "[make_frame] unknown partition '%s'; "
                        "expected \"geo\" or \"waypoint\"\n", partition.c_str());
        std::abort();
    }
    f.v_line_times = v_line_times_from_route(f.cfg, route);
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

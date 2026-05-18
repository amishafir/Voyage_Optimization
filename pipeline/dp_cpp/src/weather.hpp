#pragma once
#include "common.hpp"
#include "geo_grid.hpp"
#include <cmath>
#include <memory>
#include <optional>
#include <string>
#include <unordered_map>
#include <vector>

static const char* WEATHER_FIELDS[] = {
    "wind_speed_10m_kmh", "wind_direction_10m_deg", "beaufort_number",
    "wave_height_m", "ocean_current_velocity_kmh", "ocean_current_direction_deg"
};

struct Weather {
    double wind_speed_10m_kmh      = 0.0;
    double wind_direction_10m_deg  = 0.0;
    int    beaufort_number         = 0;
    double wave_height_m           = 0.0;
    double ocean_current_velocity_kmh = 0.0;
    double ocean_current_direction_deg = 0.0;

    bool has_nan() const {
        return std::isnan(wind_speed_10m_kmh) || std::isnan(wind_direction_10m_deg)
            || std::isnan(wave_height_m)       || std::isnan(ocean_current_velocity_kmh)
            || std::isnan(ocean_current_direction_deg);
    }

    WeatherDict to_dict() const {
        return {{"wind_speed_10m_kmh",       wind_speed_10m_kmh},
                {"wind_direction_10m_deg",    wind_direction_10m_deg},
                {"beaufort_number",           static_cast<double>(beaufort_number)},
                {"wave_height_m",             wave_height_m},
                {"ocean_current_velocity_kmh",    ocean_current_velocity_kmh},
                {"ocean_current_direction_deg",   ocean_current_direction_deg}};
    }

    static Weather from_dict(const WeatherDict& d) {
        auto g = [&](const std::string& k) -> double {
            auto it = d.find(k); return it != d.end() ? it->second : 0.0;
        };
        return {g("wind_speed_10m_kmh"), g("wind_direction_10m_deg"),
                static_cast<int>(std::round(g("beaufort_number"))),
                g("wave_height_m"), g("ocean_current_velocity_kmh"),
                g("ocean_current_direction_deg")};
    }
};

// HDF5 waypoint record (interpolated waypoints from metadata table)
struct H5Waypoint : GeoPoint {
    int    node_id;
    double distance_nm;
    int    segment;
};

// Forward declaration
struct CellKey { int lat_idx; int lon_idx;
    bool operator==(const CellKey& o) const { return lat_idx == o.lat_idx && lon_idx == o.lon_idx; } };
namespace std { template<> struct hash<CellKey> {
    size_t operator()(const CellKey& k) const {
        return hash<int>()(k.lat_idx) ^ (hash<int>()(k.lon_idx) * 2654435761U); } }; }

// Tuple key for weather cache: (grid_deg scaled, lat_idx, lon_idx, sample_hour, forecast_hour)
struct WeatherCacheKey {
    int lat_idx, lon_idx, sample_hour, forecast_hour;  // forecast_hour = -1 → actual
    bool operator==(const WeatherCacheKey& o) const {
        return lat_idx==o.lat_idx && lon_idx==o.lon_idx
            && sample_hour==o.sample_hour && forecast_hour==o.forecast_hour; }
};
namespace std { template<> struct hash<WeatherCacheKey> {
    size_t operator()(const WeatherCacheKey& k) const {
        size_t h = hash<int>()(k.lat_idx);
        h ^= hash<int>()(k.lon_idx)      * 2654435761U + 0x9e3779b9;
        h ^= hash<int>()(k.sample_hour)  * 1234567891U;
        h ^= hash<int>()(k.forecast_hour)* 987654321U;
        return h; } }; }

class VoyageWeather {
public:
    explicit VoyageWeather(const std::string& h5_path);

    double length_nm() const { return waypoints_.back().distance_nm; }
    int    num_waypoints() const { return (int)waypoints_.size(); }
    const std::vector<H5Waypoint>& waypoints() const { return waypoints_; }
    const std::vector<int>& sample_hours()   const { return sample_hours_; }
    const std::vector<int>& forecast_hours() const { return forecast_hours_; }
    std::string route_name() const { return route_name_; }

    // Map voyage time t [h since trip start] → largest sample_hour in the file
    // that is ≤ (earliest_sample_hour + ⌊t⌋), clamped to the latest available.
    // Handles non-uniform sample_hour cadence (e.g. 6 h) and missing zero anchor.
    int active_sample_hour(double t_voyage_h) const;

    // Segment-aware weather lookup (nearest valid waypoint in segment)
    WeatherDict weather_at(double d, int sample_hour, int forecast_hour = -1) const;

    // Cell-canonical weather (Qg5(b): aggregate all waypoints in the 0.5° cell)
    WeatherDict cell_weather(const CellKey& cell, int sample_hour,
                              int forecast_hour = -1, double grid_deg = 0.5) const;

    // Convenience: map distance d → (lat,lon) → cell → cell_weather
    template <typename WP>
    WeatherDict cell_weather_at_d(double d, const std::vector<WP>& paper_wps,
                                   int sample_hour, int forecast_hour = -1,
                                   double grid_deg = 0.5) const;

    std::vector<double> segment_boundaries_nm() const;
    std::vector<double> weather_cell_boundaries_nm(double grid_deg = 0.5) const;

private:
    struct WeatherRow {
        double wind_speed_10m_kmh      = std::numeric_limits<double>::quiet_NaN();
        double wind_direction_10m_deg  = std::numeric_limits<double>::quiet_NaN();
        int    beaufort_number         = 0;
        double wave_height_m           = std::numeric_limits<double>::quiet_NaN();
        double ocean_current_velocity_kmh  = std::numeric_limits<double>::quiet_NaN();
        double ocean_current_direction_deg = std::numeric_limits<double>::quiet_NaN();
        bool has_nan() const { return std::isnan(wind_speed_10m_kmh) || std::isnan(wind_direction_10m_deg)
            || std::isnan(wave_height_m) || std::isnan(ocean_current_velocity_kmh)
            || std::isnan(ocean_current_direction_deg); }
    };

    using ActualKey    = std::pair<int,int>;          // (node_id, sample_hour)
    using PredictedKey = std::tuple<int,int,int>;     // (node_id, forecast_hour, sample_hour)
    struct PairHash { size_t operator()(const ActualKey& k) const {
        return std::hash<int>()(k.first) ^ (std::hash<int>()(k.second) << 16); } };
    struct TupleHash { size_t operator()(const PredictedKey& k) const {
        size_t h = std::hash<int>()(std::get<0>(k));
        h ^= std::hash<int>()(std::get<1>(k)) * 2654435761U;
        h ^= std::hash<int>()(std::get<2>(k)) * 1234567891U;
        return h; } };

    std::vector<H5Waypoint> waypoints_;
    std::vector<double>     distances_;          // for bisect
    std::unordered_map<int, std::vector<H5Waypoint>> wps_by_seg_;
    std::vector<int>        segments_in_order_;

    std::unordered_map<ActualKey,    WeatherRow, PairHash>  actual_;
    std::unordered_map<PredictedKey, WeatherRow, TupleHash> predicted_;
    std::vector<int> sample_hours_;
    std::vector<int> forecast_hours_;
    std::string route_name_;

    // Cell index cache: grid_deg (as int*1000) -> cell -> [waypoint indices]
    mutable std::unordered_map<int, std::unordered_map<CellKey, std::vector<int>>> cell_index_;
    mutable std::unordered_map<WeatherCacheKey, WeatherDict> cell_cache_;

    void build_cell_index(double grid_deg) const;
    const WeatherRow* row_for(int node_id, int sample_hour, int forecast_hour) const;
    bool row_has_nan(const WeatherRow* row) const { return row == nullptr || row->has_nan(); }
    const H5Waypoint& nearest_waypoint(double d) const;
    const H5Waypoint& nearest_valid_in_segment(double d, int seg,
                                                int sample_hour, int forecast_hour) const;
    int segment_for_distance(double d) const;
    WeatherDict row_to_dict(const WeatherRow& r) const;
};

// ---- Template implementation ----
template <typename WP>
WeatherDict VoyageWeather::cell_weather_at_d(double d, const std::vector<WP>& paper_wps,
                                              int sample_hour, int forecast_hour,
                                              double grid_deg) const {
    auto [lat_at, lon_at, _seg] = position_at_d(d, paper_wps);
    CellKey cell{(int)std::floor(lat_at / grid_deg),
                 (int)std::floor(lon_at / grid_deg)};
    auto wx = cell_weather(cell, sample_hour, forecast_hour, grid_deg);
    // Fall back to segment-aware nearest-valid lookup if cell has no valid data
    bool any_nan = std::isnan(wx.at("wind_speed_10m_kmh"))
                || std::isnan(wx.at("wave_height_m"))
                || std::isnan(wx.at("ocean_current_velocity_kmh"));
    if (any_nan)
        return weather_at(d, sample_hour, forecast_hour);
    return wx;
}

#pragma once
#include <cmath>
#include <string>
#include <tuple>
#include <vector>

static constexpr double R_EARTH_NM    = 60.0 * 180.0 / M_PI;  // ≈ 3437.747 nm
static constexpr double LAT_LIMIT_DEG = 89.5;

// Minimal waypoint view needed by geo_grid (paper or HDF5)
struct GeoPoint {
    double lat_deg;
    double lon_deg;
};

struct Crossing {
    double fraction;      // 0..1 along the segment
    double distance_nm;   // cumulative nm from segment start
    double lat_deg;
    double lon_deg;
    std::string axis;     // "lat" or "lon"
    double grid_value;    // the lat or lon grid line crossed
};

double clamp_lat(double lat_deg);
double normalize_dlon(double dlon_deg);
double mercator_y(double lat_deg);
double inverse_mercator_lat(double my);

double rhumb_distance_nm(double lat1, double lon1, double lat2, double lon2);
double rhumb_bearing_deg(double lat1, double lon1, double lat2, double lon2);

std::vector<Crossing> rhumb_grid_crossings(double lat1, double lon1,
                                            double lat2, double lon2,
                                            double grid_deg = 0.5);

// Cell index (lat_idx, lon_idx) for a geographic point
std::pair<int, int> cell_index(double lat_deg, double lon_deg, double grid_deg = 0.5);

// Position (lat, lon, segment_0_indexed) at cumulative voyage distance d
template <typename WP>
std::tuple<double, double, int> position_at_d(double d_voy,
                                               const std::vector<WP>& waypoints);

// Total rhumb distance for a polyline
template <typename WP>
double rhumb_total_nm(const std::vector<WP>& waypoints);

// ---- Template implementations ----
#include <cmath>
#include <algorithm>

template <typename WP>
std::tuple<double, double, int> position_at_d(double d_voy,
                                               const std::vector<WP>& waypoints) {
    if (waypoints.size() < 2)
        return {waypoints.empty() ? 0.0 : (double)waypoints[0].lat_deg,
                waypoints.empty() ? 0.0 : (double)waypoints[0].lon_deg, 0};
    double cum = 0.0;
    int n_seg = (int)waypoints.size() - 1;
    for (int seg = 0; seg < n_seg; ++seg) {
        double seg_dist = rhumb_distance_nm(waypoints[seg].lat_deg, waypoints[seg].lon_deg,
                                            waypoints[seg+1].lat_deg, waypoints[seg+1].lon_deg);
        if (d_voy <= cum + seg_dist + 1e-9) {
            double f = seg_dist <= 1e-12 ? 0.0 : (d_voy - cum) / seg_dist;
            f = std::max(0.0, std::min(1.0, f));
            double dlon = normalize_dlon(waypoints[seg+1].lon_deg - waypoints[seg].lon_deg);
            double lon_raw = waypoints[seg].lon_deg + f * dlon;
            double lon_at = std::fmod(lon_raw + 180.0, 360.0) - 180.0;
            double my1 = mercator_y(waypoints[seg].lat_deg);
            double my2 = mercator_y(waypoints[seg+1].lat_deg);
            double lat_at = inverse_mercator_lat(my1 + f * (my2 - my1));
            return {lat_at, lon_at, seg};
        }
        cum += seg_dist;
    }
    return {(double)waypoints.back().lat_deg, (double)waypoints.back().lon_deg, n_seg - 1};
}

template <typename WP>
double rhumb_total_nm(const std::vector<WP>& waypoints) {
    double total = 0.0;
    for (int i = 0; i + 1 < (int)waypoints.size(); ++i)
        total += rhumb_distance_nm(waypoints[i].lat_deg, waypoints[i].lon_deg,
                                   waypoints[i+1].lat_deg, waypoints[i+1].lon_deg);
    return total;
}

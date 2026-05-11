#include "geo_grid.hpp"
#include <algorithm>
#include <cmath>

double clamp_lat(double lat) {
    return std::max(-LAT_LIMIT_DEG, std::min(LAT_LIMIT_DEG, lat));
}

double normalize_dlon(double dlon) {
    double d = std::fmod(dlon + 180.0, 360.0) - 180.0;
    return d == -180.0 ? 180.0 : d;
}

double mercator_y(double lat_deg) {
    double lat_rad = std::abs(clamp_lat(lat_deg)) * M_PI / 180.0;
    // Restore sign after clamp
    double sign = (lat_deg < 0) ? -1.0 : 1.0;
    double clamped = clamp_lat(lat_deg) * M_PI / 180.0;
    return std::log(std::tan(M_PI / 4.0 + clamped / 2.0));
}

double inverse_mercator_lat(double my) {
    return (2.0 * std::atan(std::exp(my)) - M_PI / 2.0) * 180.0 / M_PI;
}

double rhumb_distance_nm(double lat1, double lon1, double lat2, double lon2) {
    lat1 = clamp_lat(lat1);  lat2 = clamp_lat(lat2);
    double phi1 = lat1 * M_PI / 180.0;
    double phi2 = lat2 * M_PI / 180.0;
    double dphi = phi2 - phi1;
    double dlon = normalize_dlon(lon2 - lon1) * M_PI / 180.0;
    double dpsi = mercator_y(lat2) - mercator_y(lat1);
    double q = std::abs(dpsi) > 1e-12 ? dphi / dpsi : std::cos(phi1);
    return std::sqrt(dphi * dphi + (q * dlon) * (q * dlon)) * R_EARTH_NM;
}

double rhumb_bearing_deg(double lat1, double lon1, double lat2, double lon2) {
    lat1 = clamp_lat(lat1);  lat2 = clamp_lat(lat2);
    double dpsi = mercator_y(lat2) - mercator_y(lat1);
    double dlon_deg = normalize_dlon(lon2 - lon1);
    double dlam = dlon_deg * M_PI / 180.0;
    if (std::abs(dpsi) < 1e-12)
        return dlam > 0 ? 90.0 : 270.0;
    double bearing = std::atan2(dlam, dpsi) * 180.0 / M_PI;
    return std::fmod(bearing + 360.0, 360.0);
}

std::vector<Crossing> rhumb_grid_crossings(double lat1, double lon1,
                                            double lat2, double lon2,
                                            double grid_deg) {
    lat1 = clamp_lat(lat1);  lat2 = clamp_lat(lat2);
    double dlon = normalize_dlon(lon2 - lon1);
    double lon2_eff = lon1 + dlon;
    double D_total = rhumb_distance_nm(lat1, lon1, lat2, lon2);

    auto wrap_lon = [](double lon) { return std::fmod(lon + 180.0, 360.0) - 180.0; };

    std::vector<Crossing> crossings;

    // Longitude crossings
    if (std::abs(dlon) > 1e-12) {
        double lo = std::min(lon1, lon2_eff);
        double hi = std::max(lon1, lon2_eff);
        int k_first = (int)std::ceil(lo / grid_deg);
        int k_last  = (int)std::floor(hi / grid_deg);
        double my1 = mercator_y(lat1), my2 = mercator_y(lat2);
        for (int k = k_first; k <= k_last; ++k) {
            double g = std::round(k * grid_deg * 1e9) / 1e9;
            if (std::abs(g - lon1) < 1e-12 || std::abs(g - lon2_eff) < 1e-12) continue;
            double f = (g - lon1) / dlon;
            if (f <= 0.0 || f >= 1.0) continue;
            double my = my1 + f * (my2 - my1);
            crossings.push_back({f, f * D_total,
                                  inverse_mercator_lat(my), wrap_lon(g),
                                  "lon", wrap_lon(g)});
        }
    }

    // Latitude crossings
    if (std::abs(lat2 - lat1) > 1e-12) {
        double lat_lo = std::min(lat1, lat2);
        double lat_hi = std::max(lat1, lat2);
        int k_first = (int)std::ceil(lat_lo / grid_deg);
        int k_last  = (int)std::floor(lat_hi / grid_deg);
        double my1 = mercator_y(lat1), my2 = mercator_y(lat2);
        for (int k = k_first; k <= k_last; ++k) {
            double g = std::round(k * grid_deg * 1e9) / 1e9;
            if (std::abs(g - lat1) < 1e-12 || std::abs(g - lat2) < 1e-12) continue;
            double myg = mercator_y(g);
            double f = (myg - my1) / (my2 - my1);
            if (f <= 0.0 || f >= 1.0) continue;
            double lon_uw = lon1 + f * dlon;
            crossings.push_back({f, f * D_total,
                                  g, wrap_lon(lon_uw), "lat", g});
        }
    }

    // Sort by fraction, deduplicate near-coincident crossings
    std::sort(crossings.begin(), crossings.end(),
              [](const Crossing& a, const Crossing& b) { return a.fraction < b.fraction; });
    std::vector<Crossing> deduped;
    for (auto& c : crossings) {
        if (deduped.empty() || std::abs(c.fraction - deduped.back().fraction) > 1e-6)
            deduped.push_back(c);
    }
    return deduped;
}

std::pair<int, int> cell_index(double lat_deg, double lon_deg, double grid_deg) {
    return {(int)std::floor(lat_deg / grid_deg),
            (int)std::floor(lon_deg / grid_deg)};
}

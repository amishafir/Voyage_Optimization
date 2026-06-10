#include "physics.hpp"
#include <algorithm>
#include <cmath>

static inline double to_rad(double deg) { return deg * M_PI / 180.0; }
static inline double to_deg(double rad) { return rad * 180.0 / M_PI; }

double calculate_weather_direction_angle(double wind_dir_rad, double ship_heading_rad) {
    double theta = wind_dir_rad - ship_heading_rad;
    if (theta > M_PI)  theta -= 2 * M_PI;
    if (theta < -M_PI) theta += 2 * M_PI;
    return std::abs(theta);
}

double calculate_froude_number(double ship_speed_ms, double ship_length) {
    return ship_speed_ms / std::sqrt(GRAVITY * ship_length);
}

double calculate_direction_reduction_coefficient(double theta_deg, int bn) {
    double c;
    if (theta_deg <= 30.0)
        c = 2.0;
    else if (theta_deg <= 60.0)
        c = 1.7 - 0.03 * (bn - 4) * (bn - 4);
    else if (theta_deg <= 150.0)
        c = 0.9 - 0.06 * (bn - 6) * (bn - 6);
    else
        c = 0.4 - 0.03 * (bn - 8) * (bn - 8);
    return std::max(c, 0.1);
}

double calculate_speed_reduction_coefficient(double froude, double cb, bool ballast) {
    double c;
    if (cb <= 0.55)
        c = 1.7 - 1.4 * froude - 7.4 * froude * froude;
    else if (cb <= 0.60)
        c = 2.2 - 2.5 * froude - 9.7 * froude * froude;
    else if (cb <= 0.65)
        c = 2.6 - 3.7 * froude - 11.6 * froude * froude;
    else if (cb <= 0.70)
        c = 3.1 - 5.3 * froude - 12.4 * froude * froude;
    else if (cb <= 0.75) {
        c = ballast ? (2.6 - 12.5 * froude - 13.5 * froude * froude)
                    : (2.4 - 10.6 * froude -  9.5 * froude * froude);
    } else if (cb <= 0.80) {
        c = ballast ? (3.0 - 16.3 * froude - 21.6 * froude * froude)
                    : (2.6 - 13.1 * froude - 15.1 * froude * froude);
    } else {
        c = ballast ? (3.4 - 20.9 * froude + 31.8 * froude * froude)
                    : (3.1 - 18.7 * froude + 28.0 * froude * froude);
    }
    return std::max(c, 0.1);
}

double calculate_ship_form_coefficient(int bn, double displacement_vol, bool ballast) {
    double disp_term = std::pow(displacement_vol, 2.0 / 3.0);
    double bn_d = static_cast<double>(bn);
    if (ballast)
        return 0.7 * bn_d + std::pow(bn_d, 6.5) / (22.0 * disp_term);
    return 0.5 * bn_d + std::pow(bn_d, 6.5) / (22.0 * disp_term);
}

double calculate_speed_loss_percentage(double c_beta, double c_u, double c_form) {
    return std::min(std::max(c_beta * c_u * c_form, 0.0), 50.0);
}

double calculate_weather_corrected_speed(double sws, double speed_loss_pct) {
    return std::max(sws * (1.0 - speed_loss_pct / 100.0), 1.0);
}

double calculate_sog_vector_synthesis(double vw, double heading_rad,
                                       double current_kn, double current_dir_rad) {
    double vg_x = vw * std::sin(heading_rad) + current_kn * std::sin(current_dir_rad);
    double vg_y = vw * std::cos(heading_rad) + current_kn * std::cos(current_dir_rad);
    return std::sqrt(vg_x * vg_x + vg_y * vg_y);
}

double calculate_speed_over_ground(double sws, double current_kn,
                                    double current_dir_rad, double heading_rad,
                                    double wind_dir_rad, int bn,
                                    double wave_height_m,
                                    const ShipParameters& params) {
    (void)wave_height_m;
    double sws_ms = sws * KNOTS_TO_MS;
    double weather_angle_rad = calculate_weather_direction_angle(wind_dir_rad, heading_rad);
    double weather_angle_deg = to_deg(weather_angle_rad);
    double froude = calculate_froude_number(sws_ms, params.length);
    double c_beta = calculate_direction_reduction_coefficient(weather_angle_deg, bn);
    double c_u    = calculate_speed_reduction_coefficient(froude, params.block_coefficient);
    double disp_vol = params.displacement * 1000.0 / WATER_DENSITY;
    double c_form = calculate_ship_form_coefficient(bn, disp_vol);
    double loss   = calculate_speed_loss_percentage(c_beta, c_u, c_form);
    double vw     = calculate_weather_corrected_speed(sws, loss);
    double sog    = calculate_sog_vector_synthesis(vw, heading_rad, current_kn, current_dir_rad);
    if (bn >= 5) sog *= 0.965;
    return sog;
}

double calculate_speed_over_ground(double sws, const WeatherDict& weather,
                                    double heading_deg, const ShipParameters& params) {
    auto get = [&](const std::string& k, double def = 0.0) -> double {
        auto it = weather.find(k);
        return it != weather.end() ? it->second : def;
    };
    double wind_dir_rad  = to_rad(get("wind_direction_10m_deg"));
    int    bn            = static_cast<int>(std::round(get("beaufort_number", 3)));
    double wave          = get("wave_height_m", 1.0);
    double current_kn    = get("ocean_current_velocity_kmh", 0.0) / 1.852;
    double current_dir   = to_rad(get("ocean_current_direction_deg"));
    double heading_rad   = to_rad(heading_deg);
    return calculate_speed_over_ground(sws, current_kn, current_dir, heading_rad,
                                        wind_dir_rad, bn, wave, params);
}

double calculate_fuel_consumption_rate(double sws) {
    return std::max(0.000706 * sws * sws * sws, 0.1);
}

double calculate_sws_from_sog(double target_sog, const WeatherDict& weather,
                               double heading_deg, const ShipParameters& params,
                               double tolerance, int max_iter) {
    auto sog_at = [&](double s) {
        return calculate_speed_over_ground(s, weather, heading_deg, params);
    };
    double lo = 5.0, hi = 20.0;
    if (target_sog < sog_at(lo)) { hi = lo; lo = 1.0; }
    else if (target_sog > sog_at(hi)) { lo = hi; hi = 30.0; }

    double best_sws = lo;
    double best_err = std::numeric_limits<double>::infinity();
    for (int i = 0; i < max_iter; ++i) {
        double mid = (lo + hi) / 2.0;
        double got = sog_at(mid);
        double err = std::abs(got - target_sog);
        if (err < best_err) { best_err = err; best_sws = mid; }
        if (err < tolerance) break;
        if (got < target_sog) lo = mid;
        else                   hi = mid;
        if (std::abs(hi - lo) < 1e-4) break;
    }
    return (best_err < 0.1) ? best_sws : target_sog;
}

int wind_speed_to_beaufort(double wind_kmh) {
    // Beaufort thresholds in km/h (upper bound of each BN)
    static const double thresholds[] = {
        1.0, 5.0, 11.0, 19.0, 28.0, 38.0, 49.0, 61.0, 74.0, 88.0, 102.0, 117.0
    };
    for (int bn = 0; bn <= 11; ++bn)
        if (wind_kmh < thresholds[bn]) return bn;
    return 12;
}

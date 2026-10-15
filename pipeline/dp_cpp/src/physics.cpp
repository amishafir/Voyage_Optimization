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

// Sea state enters only through the Beaufort number (Kwon's method, as used by
// Yang 2020 Eqs 7-9). Significant wave height appears in Yang only in Eqs 11-13
// (critical STW / voluntary speed reduction, Constraint 21), which this study does
// not model. It is still read and logged as a route descriptor; do not re-add it
// here as a speed-model input.
double calculate_speed_over_ground(double sws, double current_kn,
                                    double current_dir_rad, double heading_rad,
                                    double wind_dir_rad, int bn,
                                    const ShipParameters& params) {
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
    double current_kn    = get("ocean_current_velocity_kmh", 0.0) / 1.852;
    double current_dir   = to_rad(get("ocean_current_direction_deg"));
    double heading_rad   = to_rad(heading_deg);
    return calculate_speed_over_ground(sws, current_kn, current_dir, heading_rad,
                                        wind_dir_rad, bn, params);
}

double calculate_fuel_consumption_rate(double sws) {
    return std::max(0.000706 * sws * sws * sws, 0.1);
}

// ---------------------------------------------------------------------------
// Inverse: SWS from SOG. Mirrors pipeline/shared/physics.py, where the
// derivation is written out. In short, for fixed weather and heading:
//   K = Cβ·CForm (no SWS dependence), CU = max(a − b·V − c·V², 0.1),
//   loss = min(K·CU, 50) %, Vw = max(V·(1 − loss/100), 1),
//   SOG = |Vw·heading + current| · (0.965 if BN ≥ 5).
// Undo the BN factor, solve the current triangle for Vw, then V from Vw:
// V = Vw/(1 − 0.001·K) above V1 (CU floor), V = 2·Vw where the loss is capped,
// otherwise the unique positive root of
//   (K·c/100)·V³ + (K·b/100)·V² + (1 − K·a/100)·V − Vw = 0   (Cardano).
// ---------------------------------------------------------------------------

namespace {

// Largest real root of p3·x³ + p2·x² + p1·x + p0 (p3 ≠ 0), by Cardano's formula.
double largest_real_cubic_root(double p3, double p2, double p1, double p0) {
    const double b = p2 / p3, c = p1 / p3, d = p0 / p3;
    const double p = c - b * b / 3.0;
    const double q = 2.0 * b * b * b / 27.0 - b * c / 3.0 + d;
    const double disc = (q / 2.0) * (q / 2.0) + (p / 3.0) * (p / 3.0) * (p / 3.0);
    double t;
    if (disc > 0) {                       // one real root
        const double r = std::sqrt(disc);
        t = std::cbrt(-q / 2.0 + r) + std::cbrt(-q / 2.0 - r);
    } else {                              // three real roots; the k = 0 branch is the largest
        const double m = std::sqrt(-p / 3.0);
        t = m > 0 ? 2.0 * m * std::cos(std::acos(std::clamp(-q / (2.0 * m * m * m), -1.0, 1.0)) / 3.0)
                  : 0.0;
    }
    double x = t - b / 3.0;
    // One Newton step removes Cardano's rounding error
    const double dfx = (3.0 * p3 * x + 2.0 * p2) * x + p1;
    if (dfx != 0) x -= (((p3 * x + p2) * x + p1) * x + p0) / dfx;
    return x;
}

// Table 3 as CU(V) = a − b·V − c·V² with V = SWS in knots, plus V1 where CU
// reaches its 0.1 floor. Read off calculate_speed_reduction_coefficient at three
// Froude numbers so it cannot drift from the forward model; ok = false when CU is
// not strictly decreasing (Cb > 0.80).
struct CuQuadratic { double a, b, c, v1; bool ok; };

CuQuadratic cu_quadratic(double length, double cb) {
    const double h = 0.05;
    const double cu0 = calculate_speed_reduction_coefficient(0.0, cb);
    const double cu1 = calculate_speed_reduction_coefficient(h, cb);
    const double cu2 = calculate_speed_reduction_coefficient(2.0 * h, cb);
    const double c_fn = -(cu2 - 2.0 * cu1 + cu0) / (2.0 * h * h);
    const double b_fn = (cu0 - cu1) / h - c_fn * h;
    if (c_fn <= 0 || b_fn < 0) return {0, 0, 0, 0, false};
    const double fn_per_knot = KNOTS_TO_MS / std::sqrt(GRAVITY * length);
    const double a = cu0, b = b_fn * fn_per_knot, c = c_fn * fn_per_knot * fn_per_knot;
    return {a, b, c, (-b + std::sqrt(b * b + 4.0 * c * (a - 0.1))) / (2.0 * c), true};
}

}  // namespace

std::optional<double> calculate_sws_from_sog_closed_form(double target_sog,
                                                         const WeatherDict& weather,
                                                         double heading_deg,
                                                         const ShipParameters& params) {
    if (!(target_sog > 0)) return std::nullopt;
    const CuQuadratic cu = cu_quadratic(params.length, params.block_coefficient);
    if (!cu.ok) return std::nullopt;

    auto get = [&](const std::string& k, double def = 0.0) -> double {
        auto it = weather.find(k);
        return it != weather.end() ? it->second : def;
    };
    const int    bn          = static_cast<int>(std::round(get("beaufort_number", 3)));
    const double heading_rad = to_rad(heading_deg);

    // 1. BN ≥ 5 reduction
    const double s = bn >= 5 ? target_sog / 0.965 : target_sog;

    // 2. Current (Eqs 14-16)
    const double current_kn = get("ocean_current_velocity_kmh", 0.0) / 1.852;
    const double delta = heading_rad - to_rad(get("ocean_current_direction_deg"));
    const double cross = current_kn * std::sin(delta);
    if (s * s < cross * cross) return std::nullopt;
    const double vw = -current_kn * std::cos(delta) + std::sqrt(s * s - cross * cross);
    if (!(vw > 1.0)) return std::nullopt;

    // 3. Speed loss (Eqs 7-8, Tables 2-4)
    const double weather_angle_deg =
        to_deg(calculate_weather_direction_angle(to_rad(get("wind_direction_10m_deg")), heading_rad));
    const double c_beta = calculate_direction_reduction_coefficient(weather_angle_deg, bn);
    const double k = c_beta * calculate_ship_form_coefficient(bn, params.displacement * 1000.0 / WATER_DENSITY);

    double sws;
    if (k == 0) {                               // BN 0: no speed loss
        sws = vw;
    } else if (k >= 500) {                      // loss capped at 50 % at every speed
        sws = 2.0 * vw;
    } else {
        const double floor_loss = 0.1 * k / 100.0;   // loss once CU sits at its 0.1 floor (< 0.5)
        if (vw >= cu.v1 * (1.0 - floor_loss)) {
            sws = vw / (1.0 - floor_loss);
        } else {
            const double cap = 50.0 / k;             // CU at which the loss reaches 50 %
            const double v2 = cap < cu.a
                ? (-cu.b + std::sqrt(cu.b * cu.b + 4.0 * cu.c * (cu.a - cap))) / (2.0 * cu.c)
                : 0.0;
            sws = vw <= 0.5 * v2
                ? 2.0 * vw
                : largest_real_cubic_root(k * cu.c / 100.0, k * cu.b / 100.0, 1.0 - k * cu.a / 100.0, -vw);
        }
    }
    if (!(std::isfinite(sws) && sws > 0)) return std::nullopt;
    return sws;
}

double calculate_sws_from_sog(double target_sog, const WeatherDict& weather,
                               double heading_deg, const ShipParameters& params,
                               double tolerance, int max_iter) {
    if (auto sws = calculate_sws_from_sog_closed_form(target_sog, weather, heading_deg, params))
        return *sws;
    return calculate_sws_from_sog_bisection(target_sog, weather, heading_deg, params,
                                            tolerance, max_iter);
}

double calculate_sws_from_sog_bisection(double target_sog, const WeatherDict& weather,
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

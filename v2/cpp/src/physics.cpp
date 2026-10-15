#include "voyage_v2/physics.hpp"

#include <algorithm>
#include <cmath>
#include <limits>
#include <stdexcept>

namespace v2 {
namespace {

constexpr double kPi = 3.14159265358979323846;
constexpr double kDeg = kPi / 180.0;
constexpr double kGravity = 9.81;           // m/s^2
constexpr double kMsPerKnot = 0.5144;
constexpr double kKmhPerKnot = 1.852;
constexpr double kSeawater = 1025.0;        // kg/m^3
constexpr double kInf = std::numeric_limits<double>::infinity();

// Table 3, normal loading: CU = a - b*Fn - c*Fn^2, by upper bound on Cb.
struct CuRow { double cb_max, a, b, c; };
constexpr CuRow kCuTable[] = {
    {0.55, 1.7, 1.4, 7.4}, {0.60, 2.2, 2.5, 9.7}, {0.65, 2.6, 3.7, 11.6},
    {0.70, 3.1, 5.3, 12.4}, {0.75, 2.4, 10.6, 9.5}, {0.80, 2.6, 13.1, 15.1},
};

// Beaufort upper bounds in m/s: BN = number of bounds the speed reaches.
constexpr double kBeaufortMs[] = {0.5, 1.6, 3.4, 5.5, 8.0, 10.8, 13.9, 17.2, 20.8, 24.5, 28.5, 32.7};

// Table 2: direction reduction coefficient, theta in degrees [0, 180].
double c_beta(double theta_deg, int bn) {
    double c;
    if (theta_deg <= 30.0)       c = 2.0;
    else if (theta_deg <= 60.0)  c = 1.7 - 0.03 * (bn - 4) * (bn - 4);
    else if (theta_deg <= 150.0) c = 0.9 - 0.06 * (bn - 6) * (bn - 6);
    else                         c = 0.4 - 0.03 * (bn - 8) * (bn - 8);
    return std::max(c, 0.1);
}

// Angle [0, 180] between the wind's "from" direction and the course; 0 = head wind.
double weather_angle_deg(double wind_from_deg, double bearing_deg) {
    double d = std::fmod(wind_from_deg - bearing_deg, 360.0);
    if (d < 0) d += 360.0;
    return d > 180.0 ? 360.0 - d : d;
}

// Largest real root of p3*x^3 + p2*x^2 + p1*x + p0 (p3 != 0), by Cardano's formula,
// polished by one Newton step.
double largest_real_cubic_root(double p3, double p2, double p1, double p0) {
    const double b = p2 / p3, c = p1 / p3, d = p0 / p3;
    const double p = c - b * b / 3.0;
    const double q = 2.0 * b * b * b / 27.0 - b * c / 3.0 + d;
    const double disc = (q / 2.0) * (q / 2.0) + (p / 3.0) * (p / 3.0) * (p / 3.0);
    double t;
    if (disc > 0) {                          // one real root
        const double r = std::sqrt(disc);
        t = std::cbrt(-q / 2.0 + r) + std::cbrt(-q / 2.0 - r);
    } else {                                 // three real roots; k = 0 is the largest
        const double m = std::sqrt(-p / 3.0);
        t = m > 0 ? 2.0 * m * std::cos(std::acos(std::clamp(-q / (2.0 * m * m * m), -1.0, 1.0)) / 3.0)
                  : 0.0;
    }
    double x = t - b / 3.0;
    const double dfx = (3.0 * p3 * x + 2.0 * p2) * x + p1;
    if (dfx != 0) x -= (((p3 * x + p2) * x + p1) * x + p0) / dfx;
    return x;
}

}  // namespace

int beaufort_number(double wind_speed_kmh) {
    if (std::isnan(wind_speed_kmh)) return -1;
    const double ms = wind_speed_kmh / 3.6;
    int bn = 0;
    while (bn < 12 && ms >= kBeaufortMs[bn]) ++bn;
    return bn;
}

SpeedModel::SpeedModel(const Ship& ship) : ship_(ship) {
    const CuRow* row = nullptr;
    for (const auto& r : kCuTable)
        if (ship.block_coefficient <= r.cb_max) { row = &r; break; }
    if (!row)
        throw std::invalid_argument("block coefficient above 0.80: CU (Table 3) is not monotone there "
                                    "and the closed-form SOG -> SWS inverse does not apply");
    if (!(ship.length_m > 0 && ship.displacement_t > 0 && ship.fcr_coefficient > 0))
        throw std::invalid_argument("ship length, displacement and FCR coefficient must be positive");

    const double fn_per_knot = kMsPerKnot / std::sqrt(kGravity * ship.length_m);
    a_ = row->a;
    b_ = row->b * fn_per_knot;
    c_ = row->c * fn_per_knot * fn_per_knot;
    v1_ = (-b_ + std::sqrt(b_ * b_ + 4.0 * c_ * (a_ - 0.1))) / (2.0 * c_);

    const double disp_term = std::pow(ship.displacement_t * 1000.0 / kSeawater, 2.0 / 3.0);
    for (int bn = 0; bn <= 12; ++bn)
        cform_[bn] = 0.5 * bn + std::pow(static_cast<double>(bn), 6.5) / (22.0 * disp_term);
}

double SpeedModel::cu(double sws_kn) const {
    return std::max(a_ - b_ * sws_kn - c_ * sws_kn * sws_kn, 0.1);
}

SpeedModel::Loss SpeedModel::loss_factor(double bearing_deg, const Conditions& c) const {
    const int bn = beaufort_number(c.wind_speed_kmh);
    return {c_beta(weather_angle_deg(c.wind_from_deg, bearing_deg), bn) * cform_[bn], bn};
}

double SpeedModel::sog(double sws_kn, double bearing_deg, const Conditions& c) const {
    if (std::isnan(c.wind_speed_kmh) || std::isnan(c.wind_from_deg) ||
        std::isnan(c.current_speed_kmh) || std::isnan(c.current_to_deg))
        return std::numeric_limits<double>::quiet_NaN();
    const Loss loss = loss_factor(bearing_deg, c);
    const double pct = std::clamp(loss.k * cu(sws_kn), 0.0, 50.0);          // Eq 7
    const double vw = std::max(sws_kn * (1.0 - pct / 100.0), 1.0);           // Eq 8
    const double vc = c.current_speed_kmh / kKmhPerKnot;                     // Eqs 14-16
    const double x = vw * std::sin(bearing_deg * kDeg) + vc * std::sin(c.current_to_deg * kDeg);
    const double y = vw * std::cos(bearing_deg * kDeg) + vc * std::cos(c.current_to_deg * kDeg);
    return std::hypot(x, y) * (loss.bn >= 5 ? 0.965 : 1.0);
}

// Undoes sog() step by step:
//   1. the BN >= 5 reduction;
//   2. the current: Vw = -Vc*cos(d) + sqrt(s^2 - Vc^2*sin^2(d)), d = bearing - current direction;
//   3. the speed loss, piecewise in V = SWS:
//        V >= V1 (CU at its 0.1 floor):  V = Vw / (1 - 0.001*K)
//        loss capped at 50 %:           V = 2*Vw
//        otherwise the cubic (K*c/100)*V^3 + (K*b/100)*V^2 + (1 - K*a/100)*V - Vw = 0,
//        whose only positive root (Descartes) comes from Cardano's formula.
double SpeedModel::sws(double sog_kn, double bearing_deg, const Conditions& c) const {
    if (std::isnan(sog_kn) || std::isnan(c.wind_speed_kmh) || std::isnan(c.wind_from_deg) ||
        std::isnan(c.current_speed_kmh) || std::isnan(c.current_to_deg))
        return std::numeric_limits<double>::quiet_NaN();
    if (!(sog_kn > 0)) return kInf;

    const Loss loss = loss_factor(bearing_deg, c);
    const double s = loss.bn >= 5 ? sog_kn / 0.965 : sog_kn;

    const double vc = c.current_speed_kmh / kKmhPerKnot;
    const double d = (bearing_deg - c.current_to_deg) * kDeg;
    const double cross = vc * std::sin(d);
    if (s * s < cross * cross) return kInf;              // cross current stronger than the target
    const double vw = -vc * std::cos(d) + std::sqrt(s * s - cross * cross);
    if (!(vw > 1.0)) return kInf;                         // below the Vw >= 1 kn floor

    const double k = loss.k;
    if (k == 0) return vw;                                // BN 0: no speed loss
    if (k >= 500.0) return 2.0 * vw;                      // loss capped at 50 % at every speed
    const double floor_loss = 0.1 * k / 100.0;            // loss once CU sits at 0.1 (< 0.5)
    if (vw >= v1_ * (1.0 - floor_loss)) return vw / (1.0 - floor_loss);
    const double cap = 50.0 / k;                          // CU at which the loss reaches 50 %
    const double v2 = cap < a_ ? (-b_ + std::sqrt(b_ * b_ + 4.0 * c_ * (a_ - cap))) / (2.0 * c_) : 0.0;
    if (vw <= 0.5 * v2) return 2.0 * vw;
    return largest_real_cubic_root(k * c_ / 100.0, k * b_ / 100.0, 1.0 - k * a_ / 100.0, -vw);
}

}  // namespace v2

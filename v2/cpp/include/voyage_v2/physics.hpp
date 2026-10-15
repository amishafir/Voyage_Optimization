#pragma once
// Speed and fuel model of the paper (Yang et al. 2020, Kwon's speed-loss method):
// the forward map SWS -> SOG for given conditions and bearing, its exact
// closed-form inverse SOG -> SWS, and the fuel consumption rate.

namespace v2 {

// Ship particulars the model uses.
struct Ship {
    double length_m;            // for the Froude number
    double displacement_t;      // tonnes
    double block_coefficient;   // Cb; the closed-form inverse needs Cb <= 0.80
    double fcr_coefficient;     // FCR = fcr_coefficient * SWS^3  [mt/h], SWS in knots
};

// Conditions at one place and time, in the weather archive's units and conventions.
struct Conditions {
    double wind_speed_kmh;      // 10 m wind speed
    double wind_from_deg;       // direction the wind blows FROM, clockwise from north
    double current_speed_kmh;   // surface current speed
    double current_to_deg;      // direction the current flows TO, clockwise from north
};

// Beaufort number (0-12) from wind speed, WMO thresholds in m/s. -1 for NaN.
int beaufort_number(double wind_speed_kmh);

class SpeedModel {
public:
    explicit SpeedModel(const Ship& ship);   // throws std::invalid_argument for Cb > 0.80

    const Ship& ship() const { return ship_; }

    // SOG [kn] reached at still-water speed sws_kn on a course of bearing_deg.
    double sog(double sws_kn, double bearing_deg, const Conditions& c) const;

    // Still-water speed [kn] needed to make good sog_kn: the exact inverse of sog().
    // +inf when no SWS reaches sog_kn, NaN when a condition is NaN.
    double sws(double sog_kn, double bearing_deg, const Conditions& c) const;

    // FCR [mt/h] at a still-water speed.
    double fcr_from_sws(double sws_kn) const {
        return ship_.fcr_coefficient * sws_kn * sws_kn * sws_kn;
    }

    // FCR [mt/h] needed to make good sog_kn on bearing_deg in conditions c.
    double fcr(double sog_kn, double bearing_deg, const Conditions& c) const {
        return fcr_from_sws(sws(sog_kn, bearing_deg, c));
    }

private:
    struct Loss { double k; int bn; };       // speed loss [%] = k * CU(SWS), clamped to [0, 50]
    Loss loss_factor(double bearing_deg, const Conditions& c) const;
    double cu(double sws_kn) const;           // Table 3, with its 0.1 floor

    Ship ship_;
    double a_, b_, c_;      // CU(V) = a - b*V - c*V^2, V = SWS in knots (before the floor)
    double v1_;             // SWS at which CU reaches its 0.1 floor
    double cform_[13];      // Table 4 CForm, by Beaufort number
};

}  // namespace v2

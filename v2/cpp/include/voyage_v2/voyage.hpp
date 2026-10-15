#pragma once
// A voyage: the route's subsegments, the ETA, the weather archive and the speed
// model, with the cost of one arc (one subsegment sailed at one SOG).

#include <vector>

#include "voyage_v2/physics.hpp"
#include "voyage_v2/weather.hpp"

namespace v2 {

// The vessel's still-water speed range (hardcoded for now) and the cost of an arc
// whose SOG needs a speed outside it.
constexpr double kSwsMinKn = 2.0;
constexpr double kSwsMaxKn = 25.0;
constexpr double kInfeasibleFuelMt = 9999.0;

// One subsegment of the route: a rhumb line inside one wind cell and one current cell.
struct Subsegment {
    double length_nm;
    double bearing_deg;
    int wind_cell;
    int current_cell;
};

// Everything arc_cost computes on the way to the fuel.
struct ArcDetail {
    Conditions conditions;
    int beaufort;
    double sws_kn;              // +inf when no SWS reaches the SOG
    bool feasible;              // sws_kn within [kSwsMinKn, kSwsMaxKn]
    double hours;
    double fcr_mt_h;            // at sws_kn, also when infeasible
    double fuel_mt;             // kInfeasibleFuelMt when infeasible
    Sample wind, current;       // where the weather came from
};

class Voyage {
public:
    Voyage(const Ship& ship, std::vector<Subsegment> subsegments, int eta_steps,
           WeatherArchive weather);

    // Fuel [mt] to sail subsegment `sub` at `sog_kn`, in the conditions at step t
    // as forecast at step tau (0 <= tau <= t <= ETA). kInfeasibleFuelMt when the
    // SOG needs an SWS outside [kSwsMinKn, kSwsMaxKn] (or no SWS reaches it), NaN
    // when the archive has no value there.
    double arc_cost(int sub, double sog_kn, int t, int tau) const;

    // Pseudo real-time: the conditions at step t as known at step t.
    double arc_cost(int sub, double sog_kn, int t) const { return arc_cost(sub, sog_kn, t, t); }

    ArcDetail arc_detail(int sub, double sog_kn, int t, int tau) const;

    int n_subsegments() const { return static_cast<int>(subsegments_.size()); }
    int eta_steps() const { return eta_steps_; }
    const Subsegment& subsegment(int sub) const { return subsegments_[sub]; }
    const SpeedModel& model() const { return model_; }
    const WeatherArchive& weather() const { return weather_; }

private:
    void check(int sub, double sog_kn, int t, int tau) const;

    SpeedModel model_;
    std::vector<Subsegment> subsegments_;
    int eta_steps_;
    WeatherArchive weather_;
};

}  // namespace v2

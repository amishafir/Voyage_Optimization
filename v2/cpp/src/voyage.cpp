#include "voyage_v2/voyage.hpp"

#include <cmath>
#include <stdexcept>
#include <string>
#include <utility>

namespace v2 {

Voyage::Voyage(const Ship& ship, std::vector<Subsegment> subsegments, int eta_steps,
               WeatherArchive weather)
    : model_(ship), subsegments_(std::move(subsegments)), eta_steps_(eta_steps),
      weather_(std::move(weather)) {
    if (eta_steps_ < 1) throw std::invalid_argument("ETA must be at least one step");
    for (const auto& s : subsegments_)
        if (s.wind_cell < 0 || s.wind_cell >= weather_.n_cells(kWind) ||
            s.current_cell < 0 || s.current_cell >= weather_.n_cells(kCurrent))
            throw std::invalid_argument("subsegment refers to a cell outside the archive");
}

void Voyage::check(int sub, double sog_kn, int t, int tau) const {
    if (sub < 0 || sub >= n_subsegments())
        throw std::out_of_range("subsegment " + std::to_string(sub) + " out of range");
    if (!(sog_kn > 0)) throw std::invalid_argument("SOG must be positive");
    if (t < 0 || t > eta_steps_)
        throw std::out_of_range("step " + std::to_string(t) + " outside the voyage (0.." +
                                std::to_string(eta_steps_) + ")");
    if (tau < 0 || tau > t)
        throw std::out_of_range("information step " + std::to_string(tau) + " must lie in 0.." +
                                std::to_string(t));
}

double Voyage::arc_cost(int sub, double sog_kn, int t, int tau) const {
    check(sub, sog_kn, t, tau);
    const Subsegment& s = subsegments_[sub];
    const Conditions c = weather_.conditions(s.wind_cell, s.current_cell, t, tau);
    const double sws = model_.sws(sog_kn, s.bearing_deg, c);
    if (std::isnan(sws)) return sws;
    if (!(sws >= kSwsMinKn && sws <= kSwsMaxKn)) return kInfeasibleFuelMt;
    return model_.fcr_from_sws(sws) * s.length_nm / sog_kn;
}

ArcDetail Voyage::arc_detail(int sub, double sog_kn, int t, int tau) const {
    check(sub, sog_kn, t, tau);
    const Subsegment& s = subsegments_[sub];
    ArcDetail d{};
    d.conditions = weather_.conditions(s.wind_cell, s.current_cell, t, tau, &d.wind, &d.current);
    d.beaufort = beaufort_number(d.conditions.wind_speed_kmh);
    d.sws_kn = model_.sws(sog_kn, s.bearing_deg, d.conditions);
    d.feasible = d.sws_kn >= kSwsMinKn && d.sws_kn <= kSwsMaxKn;
    d.hours = s.length_nm / sog_kn;
    d.fcr_mt_h = model_.fcr_from_sws(d.sws_kn);
    d.fuel_mt = std::isnan(d.sws_kn) ? d.sws_kn : d.feasible ? d.fcr_mt_h * d.hours : kInfeasibleFuelMt;
    return d;
}

}  // namespace v2

#include "voyage_v2/capi.h"

#include <exception>
#include <limits>
#include <string>
#include <vector>

#include "voyage_v2/voyage.hpp"

struct v2_archive { v2::WeatherArchive archive; };
struct v2_voyage { v2::Voyage voyage; };

namespace {

thread_local std::string last_error;
constexpr double kNaN = std::numeric_limits<double>::quiet_NaN();

v2::Ship ship_of(const v2_ship* s) {
    return {s->length_m, s->displacement_t, s->block_coefficient, s->fcr_coefficient};
}

v2::Conditions conditions_of(const v2_conditions* c) {
    return {c->wind_speed_kmh, c->wind_from_deg, c->current_speed_kmh, c->current_to_deg};
}

// Runs f, turning an exception into `failed` and a message for v2_last_error().
template <typename F, typename R>
R guarded(F&& f, R failed) {
    try {
        last_error.clear();
        return f();
    } catch (const std::exception& e) {
        last_error = e.what();
    } catch (...) {
        last_error = "unknown error";
    }
    return failed;
}

}  // namespace

extern "C" {

const char* v2_last_error(void) { return last_error.c_str(); }

v2_archive* v2_archive_new(int n_wind_cells, int n_current_cells) {
    return guarded([&] { return new v2_archive{v2::WeatherArchive(n_wind_cells, n_current_cells)}; },
                   static_cast<v2_archive*>(nullptr));
}

int v2_archive_add_run(v2_archive* archive, int grid, int init_step, int first_step, int n_hours,
                       const float* speed_kmh, const float* direction_deg) {
    return guarded([&] {
        archive->archive.add_run(static_cast<v2::Grid>(grid), init_step, first_step, n_hours,
                                 speed_kmh, direction_deg);
        return 0;
    }, 1);
}

void v2_archive_free(v2_archive* archive) { delete archive; }

v2_voyage* v2_voyage_new(const v2_ship* ship, int n_subsegments, const double* length_nm,
                         const double* bearing_deg, const int* wind_cell, const int* current_cell,
                         int eta_steps, const v2_archive* archive) {
    return guarded([&] {
        std::vector<v2::Subsegment> subs(n_subsegments);
        for (int i = 0; i < n_subsegments; ++i)
            subs[i] = {length_nm[i], bearing_deg[i], wind_cell[i], current_cell[i]};
        return new v2_voyage{v2::Voyage(ship_of(ship), std::move(subs), eta_steps, archive->archive)};
    }, static_cast<v2_voyage*>(nullptr));
}

void v2_voyage_free(v2_voyage* voyage) { delete voyage; }

double v2_arc_cost(const v2_voyage* voyage, int sub, double sog_kn, int t, int tau) {
    return guarded([&] { return voyage->voyage.arc_cost(sub, sog_kn, t, tau < 0 ? t : tau); }, kNaN);
}

int v2_arc_costs(const v2_voyage* voyage, long n, const int* sub, const double* sog_kn,
                 const int* t, const int* tau, double* out) {
    long i = 0;
    const int status = guarded([&] {
        for (; i < n; ++i)
            out[i] = voyage->voyage.arc_cost(sub[i], sog_kn[i], t[i], tau[i] < 0 ? t[i] : tau[i]);
        return 0;
    }, 1);
    if (status != 0) last_error = "arc " + std::to_string(i) + ": " + last_error;
    return status;
}

int v2_arc_detail(const v2_voyage* voyage, int sub, double sog_kn, int t, int tau,
                  v2_arc_info* out) {
    return guarded([&] {
        const v2::ArcDetail d = voyage->voyage.arc_detail(sub, sog_kn, t, tau < 0 ? t : tau);
        out->conditions = {d.conditions.wind_speed_kmh, d.conditions.wind_from_deg,
                           d.conditions.current_speed_kmh, d.conditions.current_to_deg};
        out->beaufort = d.beaufort;
        out->sws_kn = d.sws_kn;
        out->hours = d.hours;
        out->fcr_mt_h = d.fcr_mt_h;
        out->fuel_mt = d.fuel_mt;
        out->feasible = d.feasible;
        out->wind_run = d.wind.run;
        out->current_run = d.current.run;
        out->wind_held = d.wind.held;
        out->current_held = d.current.held;
        return 0;
    }, 1);
}

int v2_beaufort_number(double wind_speed_kmh) { return v2::beaufort_number(wind_speed_kmh); }

double v2_sog_from_sws(const v2_ship* ship, double sws_kn, double bearing_deg, const v2_conditions* c) {
    return guarded([&] { return v2::SpeedModel(ship_of(ship)).sog(sws_kn, bearing_deg, conditions_of(c)); },
                   kNaN);
}

double v2_sws_from_sog(const v2_ship* ship, double sog_kn, double bearing_deg, const v2_conditions* c) {
    return guarded([&] { return v2::SpeedModel(ship_of(ship)).sws(sog_kn, bearing_deg, conditions_of(c)); },
                   kNaN);
}

double v2_fcr_from_sog(const v2_ship* ship, double sog_kn, double bearing_deg, const v2_conditions* c) {
    return guarded([&] { return v2::SpeedModel(ship_of(ship)).fcr(sog_kn, bearing_deg, conditions_of(c)); },
                   kNaN);
}

}  // extern "C"

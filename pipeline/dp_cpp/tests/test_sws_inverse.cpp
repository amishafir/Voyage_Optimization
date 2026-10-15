// Tests for the closed-form SOG -> SWS inverse (src/physics.cpp), against the
// forward model, the binary search it replaces, and the Python implementation.
//
//   cmake --build build --target test_sws_inverse && ./build/test_sws_inverse
//
// Exit code 0 on success; prints timings per call.

#include "physics.hpp"

#include <chrono>
#include <cstdio>
#include <random>
#include <vector>

namespace {

int failures = 0;

void check(bool ok, const char* what, double sog, double got, double expected) {
    if (!ok) {
        ++failures;
        if (failures <= 10)
            std::printf("FAIL %s: sog=%.4f got=%.12f expected=%.12f\n", what, sog, got, expected);
    }
}

struct Case { double sog; WeatherDict w; double heading; };

WeatherDict weather(int bn, double wind_dir, double current_kn, double current_dir) {
    return {{"wind_direction_10m_deg", wind_dir}, {"beaufort_number", static_cast<double>(bn)},
            {"ocean_current_velocity_kmh", current_kn * 1.852}, {"ocean_current_direction_deg", current_dir}};
}

std::vector<Case> cases(int n, int bn_max, double sog_lo, double sog_hi, double current_max, unsigned seed) {
    std::mt19937 rng(seed);
    std::uniform_real_distribution<double> u(0.0, 1.0);
    std::uniform_int_distribution<int> bn(0, bn_max);
    std::vector<Case> out;
    for (int i = 0; i < n; ++i)
        out.push_back({sog_lo + (sog_hi - sog_lo) * u(rng),
                       weather(bn(rng), 360 * u(rng), current_max * u(rng), 360 * u(rng)),
                       360 * u(rng)});
    return out;
}

}  // namespace

int main() {
    const ShipParameters ship;   // defaults = experiment.yaml ship (200 m, Cb 0.75, 50,000 t)
    const auto realistic = cases(20000, 8, 9.0, 15.0, 2.5, 1);
    const auto wide      = cases(20000, 12, 3.0, 20.0, 4.0, 2);

    // 1. Exact inverse of the forward model; applies to every realistic case.
    int solved = 0;
    for (const auto* set : {&realistic, &wide})
        for (const auto& c : *set) {
            auto sws = calculate_sws_from_sog_closed_form(c.sog, c.w, c.heading, ship);
            if (set == &realistic) check(sws.has_value(), "closed form applies (realistic)", c.sog, 0, 0);
            if (!sws) continue;
            ++solved;
            double sog = calculate_speed_over_ground(*sws, c.w, c.heading, ship);
            check(std::abs(sog - c.sog) < 1e-9, "reproduces target SOG", c.sog, sog, c.sog);
        }
    check(solved > 0.95 * (realistic.size() + wide.size()), "solved fraction", 0, solved, 0);

    // 2. Agrees with the binary search to within its 0.001 kn SOG tolerance.
    for (const auto& c : realistic) {
        double exact = *calculate_sws_from_sog_closed_form(c.sog, c.w, c.heading, ship);
        double bis = calculate_sws_from_sog_bisection(c.sog, c.w, c.heading, ship);
        check(std::abs(exact - bis) < 2e-3, "agrees with binary search", c.sog, exact, bis);
    }

    // 3. nullopt only when the target is unreachable; the public function falls back.
    for (const auto& c : wide) {
        auto exact = calculate_sws_from_sog_closed_form(c.sog, c.w, c.heading, ship);
        double expected = exact ? *exact : calculate_sws_from_sog_bisection(c.sog, c.w, c.heading, ship);
        double got = calculate_sws_from_sog(c.sog, c.w, c.heading, ship);
        check(got == expected, "public function = closed form or fallback", c.sog, got, expected);
        if (!exact) {
            double min_sog = 1e9;
            for (int i = 1; i <= 800; ++i)
                min_sog = std::min(min_sog, calculate_speed_over_ground(0.05 * i, c.w, c.heading, ship));
            check(c.sog < min_sog, "nullopt only when unreachable", c.sog, min_sog, c.sog);
        }
    }

    // 4. Cb > 0.80: CU not monotone, closed form declines.
    ShipParameters full = ship;
    full.block_coefficient = 0.85;
    auto w = weather(5, 30.0, 1.0, 90.0);
    check(!calculate_sws_from_sog_closed_form(12.0, w, 45.0, full), "Cb 0.85 declines", 12.0, 0, 0);

    // 5. Same values as pipeline/shared/physics.py (every branch of the closed form).
    struct Fixed { double sog; int bn; double wind_dir, current_kn, current_dir, heading, sws; };
    const Fixed fixed[] = {
        {12.0, 0, 0.0, 0.0, 0.0, 0.0, 12.000000000000},
        {12.0, 3, 45.0, 0.8, 120.0, 75.0, 11.658510765679},
        {12.0, 5, 10.0, 1.0, 200.0, 0.0, 13.831756349611},
        {11.5, 7, 170.0, 1.5, 300.0, 250.0, 11.952725597296},
        {13.0, 8, 350.0, 2.0, 180.0, 10.0, 16.395599142925},
        {17.0, 4, 90.0, 0.0, 0.0, 0.0, 17.025607928091},     // CU at its 0.1 floor
        {6.0, 9, 0.0, 0.0, 0.0, 0.0, 12.435233160622},       // loss capped at 50 %
        {12.0, 12, 0.0, 0.0, 0.0, 0.0, 24.870466321244},     // loss 50 % at every speed
    };
    for (const auto& f : fixed) {
        auto got = calculate_sws_from_sog_closed_form(
            f.sog, weather(f.bn, f.wind_dir, f.current_kn, f.current_dir), f.heading, ship);
        check(got && std::abs(*got - f.sws) < 1e-9, "matches Python", f.sog, got.value_or(-1), f.sws);
    }

    // Timing
    auto time_us = [&](auto fn) {
        volatile double sink = 0;
        auto t0 = std::chrono::steady_clock::now();
        for (const auto& c : realistic) sink = sink + fn(c);
        auto dt = std::chrono::duration<double, std::micro>(std::chrono::steady_clock::now() - t0).count();
        return dt / realistic.size();
    };
    double t_bis = time_us([&](const Case& c) { return calculate_sws_from_sog_bisection(c.sog, c.w, c.heading, ship); });
    double t_cf  = time_us([&](const Case& c) { return calculate_sws_from_sog(c.sog, c.w, c.heading, ship); });
    double t_fwd = time_us([&](const Case& c) { return calculate_speed_over_ground(c.sog, c.w, c.heading, ship); });
    std::printf("per call: binary search %.3f us, closed form %.3f us, one forward call %.3f us\n",
                t_bis, t_cf, t_fwd);

    if (failures) {
        std::printf("%d check(s) FAILED\n", failures);
        return 1;
    }
    std::printf("all checks passed\n");
    return 0;
}

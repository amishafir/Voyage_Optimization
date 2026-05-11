#pragma once
#include <cmath>
#include <cstdint>
#include <limits>
#include <string>
#include <unordered_map>

using WeatherDict = std::unordered_map<std::string, double>;

struct ShipParameters {
    double length          = 200.0;
    double beam            = 32.0;
    double draft           = 12.0;
    double displacement    = 50000.0;   // tonnes
    double block_coefficient = 0.75;
    double wetted_surface  = 8000.0;
    double rated_power     = 10000.0;
    double max_speed       = 14.0;
    double min_speed       = 8.0;
};

// ---- (time, distance) key rounded to 9 decimal places ----
// Quantise to int64 * 1e9 to allow exact equality comparisons.
// Safe range: t < 1000 h → t*1e9 < 1e12 ≪ INT64_MAX.
struct TDKey {
    int64_t t9;
    int64_t d9;
    bool operator==(const TDKey& o) const noexcept {
        return t9 == o.t9 && d9 == o.d9;
    }
};

namespace std {
template <>
struct hash<TDKey> {
    size_t operator()(const TDKey& k) const noexcept {
        size_t h1 = hash<int64_t>()(k.t9);
        size_t h2 = hash<int64_t>()(k.d9);
        // Mix: shift h2 so it doesn't just XOR with h1 for equal values.
        return h1 ^ (h2 * 2654435761ULL + 0x9e3779b9ULL + (h1 << 6) + (h1 >> 2));
    }
};
}  // namespace std

inline TDKey make_td_key(double t, double d) {
    return {static_cast<int64_t>(std::llround(t * 1e9)),
            static_cast<int64_t>(std::llround(d * 1e9))};
}

#include "voyage_v2/weather.hpp"

#include <algorithm>
#include <climits>
#include <cmath>
#include <stdexcept>
#include <string>

namespace v2 {
namespace {

constexpr double kDeg = 3.14159265358979323846 / 180.0;

double direction_deg(double east, double north) {
    double d = std::atan2(east, north) / kDeg;
    return d < 0 ? d + 360.0 : d;
}

}  // namespace

WeatherArchive::WeatherArchive(int n_wind_cells, int n_current_cells)
    : n_cells_{n_wind_cells, n_current_cells} {}

void WeatherArchive::add_run(Grid grid, int init_step, int first_step, int n_hours,
                             const float* speed_kmh, const float* direction_deg) {
    if (grid != kWind && grid != kCurrent) throw std::invalid_argument("unknown grid");
    if (n_hours < 1) throw std::invalid_argument("a run needs at least one hour");
    if (first_step < init_step || (first_step - init_step) % 4 != 0)
        throw std::invalid_argument("a run's hours must fall on whole hours from its start");

    Run run{init_step, first_step, n_hours, {}, {}};
    const std::size_t n = static_cast<std::size_t>(n_cells_[grid]) * n_hours;
    run.east.resize(n);
    run.north.resize(n);
    const double sign = grid == kWind ? -1.0 : 1.0;      // wind: "from" -> the vector it blows to
    for (std::size_t i = 0; i < n; ++i) {
        const double s = speed_kmh[i], d = direction_deg[i] * kDeg;
        run.east[i] = static_cast<float>(sign * s * std::sin(d));
        run.north[i] = static_cast<float>(sign * s * std::cos(d));
    }

    auto& runs = runs_[grid];
    auto pos = std::upper_bound(runs.begin(), runs.end(), init_step,
                                [](int s, const Run& r) { return s < r.init_step; });
    if (pos != runs.begin() && std::prev(pos)->init_step == init_step)
        throw std::invalid_argument("run added twice");
    runs.insert(pos, std::move(run));
}

Sample WeatherArchive::sample(Grid grid, int cell, int t, int tau) const {
    const auto& runs = runs_[grid];
    if (cell < 0 || cell >= n_cells_[grid]) throw std::out_of_range("cell out of range");

    // Newest run issued at or before tau
    auto it = std::upper_bound(runs.begin(), runs.end(), tau,
                               [](int s, const Run& r) { return s < r.init_step; });
    if (it == runs.begin())
        throw std::out_of_range("no " + std::string(grid == kWind ? "wind" : "current") +
                                " run issued by step " + std::to_string(tau));

    int hold = -1, hold_last = INT_MIN;
    for (int i = static_cast<int>(it - runs.begin()) - 1; i >= 0; --i) {
        const Run& r = runs[i];
        if (t >= r.first_step && t <= r.last_step()) {
            const int off = t - r.first_step;
            const std::size_t idx = static_cast<std::size_t>(cell) * r.n_hours + off / 4;
            const double w = (off % 4) / 4.0;
            double east = r.east[idx], north = r.north[idx];
            if (w > 0) {
                east += w * (r.east[idx + 1] - east);
                north += w * (r.north[idx + 1] - north);
            }
            return {east, north, i, false};
        }
        if (r.last_step() < t && r.last_step() > hold_last) {   // newest wins ties
            hold = i;
            hold_last = r.last_step();
        }
    }
    if (hold < 0) throw std::out_of_range("no run holds data before step " + std::to_string(t));
    const Run& r = runs[hold];
    const std::size_t idx = static_cast<std::size_t>(cell) * r.n_hours + (r.n_hours - 1);
    return {r.east[idx], r.north[idx], hold, true};
}

Conditions WeatherArchive::conditions(int wind_cell, int current_cell, int t, int tau,
                                      Sample* wind, Sample* current) const {
    const Sample w = sample(kWind, wind_cell, t, tau);
    const Sample c = sample(kCurrent, current_cell, t, tau);
    if (wind) *wind = w;
    if (current) *current = c;
    return {std::hypot(w.east, w.north), direction_deg(-w.east, -w.north),
            std::hypot(c.east, c.north), direction_deg(c.east, c.north)};
}

}  // namespace v2

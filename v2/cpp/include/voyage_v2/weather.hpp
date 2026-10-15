#pragma once
// Archived model runs and the weather they give at a 15-minute step.
//
// Time is an integer count of 15-minute steps from the voyage start (step 0).
// A run issued at step i is known from step i on (zero publication delay). The
// weather at step t, as known at step tau (the information time), comes from the
// newest run issued at or before tau that covers t; when that run has ended before
// t, from the next older run that covers t. Between a run's hourly values the
// east/north components are interpolated linearly. When no run issued by tau
// reaches t, the latest value before t is held.

#include <vector>

#include "voyage_v2/physics.hpp"

namespace v2 {

enum Grid : int { kWind = 0, kCurrent = 1 };

// One model run, holding the hours the voyage can use.
struct Run {
    int init_step;              // run start (may be before the voyage start)
    int first_step;             // valid time of the first stored hour
    int n_hours;
    std::vector<float> east;    // [cell * n_hours + hour], km/h; wind as the vector it blows TO
    std::vector<float> north;
    int last_step() const { return first_step + 4 * (n_hours - 1); }
};

// A grid's vector at one cell and step, and where it came from.
struct Sample {
    double east, north;         // km/h
    int run;                    // index into WeatherArchive::runs(grid)
    bool held;                  // true when the latest value before t was held
};

class WeatherArchive {
public:
    WeatherArchive(int n_wind_cells, int n_current_cells);

    // Adds a run, given as speed [km/h] and direction [deg] per [cell][hour]. Wind
    // direction is the "from" direction, current direction the "to" direction.
    void add_run(Grid grid, int init_step, int first_step, int n_hours,
                 const float* speed_kmh, const float* direction_deg);

    Sample sample(Grid grid, int cell, int t, int tau) const;

    Conditions conditions(int wind_cell, int current_cell, int t, int tau,
                          Sample* wind = nullptr, Sample* current = nullptr) const;

    int n_cells(Grid grid) const { return n_cells_[grid]; }
    const std::vector<Run>& runs(Grid grid) const { return runs_[grid]; }

private:
    int n_cells_[2];
    std::vector<Run> runs_[2];      // by init_step
};

}  // namespace v2

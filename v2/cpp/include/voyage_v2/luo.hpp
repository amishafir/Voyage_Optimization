#pragma once
// Luo et al. (2024) multistage-graph DP on v2's data (single core).
//
// The voyage is divided into decision epochs of epoch_steps weather steps
// (0.25 h each; 24 = 6 h as in Luo et al.); the last epoch ends at the ETA and
// may be shorter. The SOG is constant within an epoch. Nodes lie only on the
// epoch boundaries, every dist_step_nm from the start (default: 0.1 kn x the
// epoch length, i.e. 0.6 NM for 6 h epochs), inside the window reachable with an
// SOG in mean SOG +/- sog_band_kn that can still arrive by the ETA.
//
// An arc joins a node to a node of the next boundary, or arrives at the end of
// the route exactly at the next boundary (no later than the ETA), at the constant
// SOG inside the band that this requires. Its fuel is integrated along the path:
// cut at every subsegment boundary and every 15-minute weather step, each piece
// is priced with its own bearing, cells and weather (pseudo real-time, or the
// forecast known at the start). An arc with any piece whose SWS falls outside
// [kSwsMinKn, kSwsMaxKn] is left out. No subsegments are merged and the route
// length is not snapped to the grid. Within an epoch an arc between grid nodes has
// one of a few SOGs (its grid advance q x dist_step / epoch length), so the FCR of each
// (subsegment, step, q) is computed once per epoch and shared by all arcs that cross
// that subsegment in that step at that SOG.
//
// With start_point_pricing, arcs are priced as in Luo et al.: the whole epoch at
// the conditions where and when it starts (that subsegment's bearing and cells, that
// weather step), feasibility checked there only. The plan is then evaluated as above
// (DPResult::fuel_mt), so the cost of the cruder pricing shows.

#include "voyage_v2/dp.hpp"

namespace v2 {

struct LuoOptions {
    double sog_band_kn = 3.0;   // SOG window: mean SOG (route length / ETA) +/- this
    int epoch_steps = 24;       // decision epoch in 0.25 h weather steps (24 = 6 h)
    double dist_step_nm = 0.0;  // node spacing on the epoch lines; 0 = 0.1 kn x epoch length
    bool forecast = false;      // false: pseudo real-time (tau = t); true: forecast known at the start
    bool start_point_pricing = false;   // price each arc at its start point only (Luo et al.)
};

// The plan has one arc per epoch (segment = the subsegment it starts in, step =
// its first weather step, sws_kn = time-weighted mean); segments lists the
// route's subsegments. Node counts are all on time lines.
DPResult solve_luo(const Voyage& voyage, const LuoOptions& options = LuoOptions());

}  // namespace v2

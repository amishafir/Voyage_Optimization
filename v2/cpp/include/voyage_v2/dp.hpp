#pragma once
// Minimum-fuel speed plan on the full time-distance graph (single core).
//
// Lines. Distance lines sit at every segment boundary: the route's subsegments,
// after each one shorter than merge_nm has joined its shorter neighbour. Merging
// only removes the line between them; every piece of a merged segment is still
// priced with its own bearing and weather cells. Time
// lines sit at every 15-minute weather step. Nodes lie every tick_s seconds on a
// distance line and every zeta_m metres on a time line, both counted from the
// start, and only inside the window the ship can reach with an SOG in
// [v_min, v_max] = mean SOG +/- sog_band_kn while still arriving by the ETA.
//
// Arcs. From a node, constant SOG in [v_min, v_max] to the first line ahead: to
// every node of the next distance line reached before the next time line, and to
// every node of the next time line short of the next distance line. Each arc thus
// lies inside one segment and one weather step; its fuel is FCR(SWS) x duration in
// the weather of that step (pseudo real-time, or the forecast known at the start),
// and over a merged segment the sum, piece by piece, of each piece's FCR for the
// time spent on it.
// Arcs whose SWS falls outside [kSwsMinKn, kSwsMaxKn] are left out.
//
// The sweep visits the nodes in time order, generating each node's arcs as it
// goes; only every node's fuel and predecessor are stored.

#include <cstdint>
#include <vector>

#include "voyage_v2/voyage.hpp"

namespace v2 {

struct DPOptions {
    double sog_band_kn = 3.0;   // SOG window: mean SOG (route length / ETA) +/- this
    int tick_s = 4;             // node spacing on distance lines [s]; must divide 900
    double zeta_m = 25.0;       // node spacing on time lines [m]
    double merge_nm = 0.15;     // subsegments shorter than this join their shorter neighbour
    bool forecast = false;      // false: pseudo real-time (tau = t); true: forecast known at the start
};

// The stretch of route between two consecutive distance lines.
struct Segment {
    double start_nm, length_nm, bearing_deg;
    int wind_cell, current_cell;
    int first_sub, n_subs;      // the subsegments it is made of
    int dominant_sub;           // the longest of them (its bearing and cells are reported; pricing is per piece)
};

// One arc of the plan.
struct PlanArc {
    double t0_h, d0_nm, t1_h, d1_nm;
    double sog_kn;
    double sws_kn, fuel_mt;             // realized: actual (pseudo real-time) weather, every piece priced;
                                        // sws_kn is the time-weighted mean over the pieces
    double planned_fuel_mt;             // as priced when planning
    int segment, step;
};

struct DPStats {
    long long nodes, distance_line_nodes, time_line_nodes, reached_nodes;
    long long arcs, infeasible_arcs;    // arcs generated; of them, SWS outside the vessel's range
    long long sws_evaluations;          // SWS inversions (tables shared by many arcs count once)
    long long realized_sws_violations;  // plan pieces whose SWS leaves the vessel's range in actual weather
    double setup_s, sweep_s;
    double memory_mb;                   // node arrays
};

// fuel_mt is the plan's realized fuel: its SOG profile sailed in the actual (pseudo
// real-time) weather, every subsegment-by-step piece priced. planned_fuel_mt is the
// DP's objective. They coincide when planning used integrated prices in actual weather.
struct DPResult {
    bool feasible;
    double fuel_mt, planned_fuel_mt, arrival_h;
    double constant_sog_fuel_mt;        // every piece at the mean SOG, actual weather
    double v_min_kn, v_max_kn;
    std::vector<Segment> segments;
    std::vector<PlanArc> path;
    DPStats stats;
};

std::vector<Segment> merge_subsegments(const Voyage& voyage, double min_nm);

DPResult solve_dp(const Voyage& voyage, const DPOptions& options = DPOptions());

}  // namespace v2

#pragma once
#include "atomic_edges.hpp"
#include "nodes.hpp"
#include <set>
#include <unordered_map>
#include <utility>
#include <vector>

struct LuoResult {
    double total_fuel_mt;
    double voyage_time_h;
    std::vector<int> schedule;      // edge indices, src→sink order
    std::pair<double,double> sink_node;
    int nan_edges_skipped;
    int states_reached;
    int distinct_locks_used;
};

// Forward Bellman DP over (canonical_node_id, locked_target_sog | UNLOCKED) states.
//
// State = (node_id, lock):
//   lock = UNLOCKED (-1.0) on V-line nodes → any edge may be taken, picks new lock
//   lock = S ≥ 0 on H-line mid-block nodes → only edges with target_sog ≈ S allowed
class BellmanSolverLocked {
public:
    static constexpr double UNLOCKED = -1.0;

    BellmanSolverLocked(const std::vector<Node>& nodes,
                         const std::vector<AtomicEdge>& edges,
                         const std::set<double>& v_line_times);

    void solve();
    LuoResult result(double eta_h);

private:
    // Parent record stored per (node, lock) state.
    // edge_idx == -1 signals "no parent" (source state).
    struct LockEntry {
        double cost      = std::numeric_limits<double>::infinity();
        int    edge_idx  = -1;  // -1 → no parent (source)
        int    prev_node = -1;
        double prev_lock = UNLOCKED;
        bool has_parent() const { return edge_idx >= 0; }
    };
    using LockMap = std::unordered_map<double, LockEntry>;

    const std::vector<AtomicEdge>& edges_;

    std::vector<std::pair<double,double>> coords_;
    std::unordered_map<TDKey, int>        key_to_id_;
    std::vector<bool>                     is_source_;
    std::vector<bool>                     is_sink_;
    std::vector<bool>                     is_v_line_;

    std::vector<std::vector<int>> outgoing_;
    int source_id_         = 0;
    int nan_edges_skipped_ = 0;
    int unknown_edges_     = 0;

    std::vector<int> topo_order_;
    std::vector<LockMap> state_;

    int best_sink(double eta_h);
    std::vector<int> backtrack(int sink_id);
};

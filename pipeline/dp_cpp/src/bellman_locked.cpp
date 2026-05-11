#include "bellman_locked.hpp"
#include <algorithm>
#include <cmath>
#include <limits>
#include <numeric>
#include <set>
#include <stdexcept>
#include <unordered_set>

static constexpr double SOG_TOL           = 1e-6;
static constexpr double LOCK_KEY_PRECISION = 1e6;

static double round_lock(double sog) {
    return std::round(sog * LOCK_KEY_PRECISION) / LOCK_KEY_PRECISION;
}

BellmanSolverLocked::BellmanSolverLocked(const std::vector<Node>& nodes,
                                           const std::vector<AtomicEdge>& edges,
                                           const std::set<double>& v_line_times)
    : edges_(edges) {
    std::unordered_set<int64_t> v_t_set;
    v_t_set.insert(0LL);
    for (double t : v_line_times)
        v_t_set.insert(static_cast<int64_t>(std::llround(t * 1e9)));

    for (auto& n : nodes) {
        TDKey k = make_td_key(n.time_h, n.distance_nm);
        auto it = key_to_id_.find(k);
        if (it == key_to_id_.end()) {
            int id = (int)coords_.size();
            key_to_id_[k] = id;
            coords_.push_back({n.time_h, n.distance_nm});
            is_source_.push_back(n.is_source);
            is_sink_.push_back(n.is_sink);
            is_v_line_.push_back(v_t_set.count(k.t9) > 0);
        } else {
            int id = it->second;
            if (n.is_source) is_source_[id] = true;
            if (n.is_sink)   is_sink_[id]   = true;
        }
    }

    int N = (int)coords_.size();
    outgoing_.resize(N);
    for (int ei = 0; ei < (int)edges_.size(); ++ei) {
        auto it = key_to_id_.find(make_td_key(edges_[ei].src_t, edges_[ei].src_d));
        if (it == key_to_id_.end()) { ++unknown_edges_; continue; }
        outgoing_[it->second].push_back(ei);
    }

    state_.resize(N);
    source_id_ = -1;
    for (int i = 0; i < N; ++i)
        if (is_source_[i]) { source_id_ = i; break; }
    if (source_id_ < 0) {
        auto it = key_to_id_.find(make_td_key(0.0, 0.0));
        if (it == key_to_id_.end()) throw std::runtime_error("No source node at (0,0)");
        source_id_ = it->second;
    }
    // Source starts with lock = UNLOCKED, cost = 0, no parent
    LockEntry src_entry;
    src_entry.cost = 0.0;
    state_[source_id_][UNLOCKED] = src_entry;

    topo_order_.resize(N);
    std::iota(topo_order_.begin(), topo_order_.end(), 0);
    std::sort(topo_order_.begin(), topo_order_.end(),
              [&](int a, int b) { return coords_[a] < coords_[b]; });
}

void BellmanSolverLocked::solve() {
    for (int src_id : topo_order_) {
        if (state_[src_id].empty()) continue;

        // Snapshot so dst writes don't invalidate iteration
        LockMap snapshot = state_[src_id];

        for (auto& [lock_state, src_entry] : snapshot) {
            double base_cost = src_entry.cost;

            for (int ei : outgoing_[src_id]) {
                const auto& e = edges_[ei];
                if (std::isnan(e.fuel_mt)) { ++nan_edges_skipped_; continue; }

                // Lock admissibility
                double new_lock_in_block;
                if (lock_state == UNLOCKED) {
                    new_lock_in_block = round_lock(e.target_sog);
                } else {
                    if (std::abs(e.target_sog - lock_state) > SOG_TOL) continue;
                    new_lock_in_block = lock_state;
                }

                auto dit = key_to_id_.find(make_td_key(e.dst_t, e.dst_d));
                if (dit == key_to_id_.end()) continue;
                int dst_id = dit->second;

                double new_lock = is_v_line_[dst_id] ? UNLOCKED : new_lock_in_block;
                double new_cost = base_cost + e.fuel_mt;

                auto& dst_map = state_[dst_id];
                auto mit = dst_map.find(new_lock);
                if (mit == dst_map.end() || new_cost < mit->second.cost) {
                    LockEntry entry;
                    entry.cost      = new_cost;
                    entry.edge_idx  = ei;
                    entry.prev_node = src_id;
                    entry.prev_lock = lock_state;
                    dst_map[new_lock] = entry;
                }
            }
        }
    }
}

int BellmanSolverLocked::best_sink(double eta_h) {
    int best_id   = -1;
    double best_c = std::numeric_limits<double>::infinity();
    for (int i = 0; i < (int)coords_.size(); ++i) {
        if (!is_sink_[i]) continue;
        if (coords_[i].first > eta_h + 1e-6) continue;
        auto it = state_[i].find(UNLOCKED);
        if (it == state_[i].end()) continue;
        if (it->second.cost < best_c) {
            best_c  = it->second.cost;
            best_id = i;
        }
    }
    if (best_id < 0) throw std::runtime_error("No sink reachable within ETA under Luo lock.");
    return best_id;
}

std::vector<int> BellmanSolverLocked::backtrack(int sink_id) {
    std::vector<int> path;
    int    cur_id   = sink_id;
    double cur_lock = UNLOCKED;
    for (;;) {
        auto mit = state_[cur_id].find(cur_lock);
        if (mit == state_[cur_id].end() || !mit->second.has_parent()) break;
        const auto& e = mit->second;
        path.push_back(e.edge_idx);
        cur_id   = e.prev_node;
        cur_lock = e.prev_lock;
        if (cur_id == source_id_ && cur_lock == UNLOCKED) break;
    }
    std::reverse(path.begin(), path.end());
    return path;
}

LuoResult BellmanSolverLocked::result(double eta_h) {
    int sink_id      = best_sink(eta_h);
    auto schedule    = backtrack(sink_id);
    double sink_cost = state_[sink_id].at(UNLOCKED).cost;

    int states_reached = 0;
    std::set<double> distinct_locks;
    for (auto& lmap : state_) {
        states_reached += (int)lmap.size();
        for (auto& [lock, _v] : lmap)
            if (lock != UNLOCKED) distinct_locks.insert(lock);
    }

    return {sink_cost, coords_[sink_id].first,
            schedule, coords_[sink_id],
            nan_edges_skipped_, states_reached,
            (int)distinct_locks.size()};
}

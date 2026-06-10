#include "bellman.hpp"
#include <algorithm>
#include <cmath>
#include <numeric>
#include <stdexcept>

BellmanSolver::BellmanSolver(const std::vector<Node>& nodes,
                               const std::vector<AtomicEdge>& edges)
    : edges_(edges) {
    // Canonicalise nodes: collapse coincident (t,d) pairs
    for (auto& n : nodes) {
        TDKey k = make_td_key(n.time_h, n.distance_nm);
        auto it = key_to_id_.find(k);
        if (it == key_to_id_.end()) {
            int id = (int)coords_.size();
            key_to_id_[k] = id;
            coords_.push_back({n.time_h, n.distance_nm});
            is_source_.push_back(n.is_source);
            is_sink_.push_back(n.is_sink);
        } else {
            int id = it->second;
            if (n.is_source) is_source_[id] = true;
            if (n.is_sink)   is_sink_[id]   = true;
        }
    }

    int N = (int)coords_.size();
    outgoing_.resize(N);
    for (int ei = 0; ei < (int)edges_.size(); ++ei) {
        TDKey sk = make_td_key(edges_[ei].src_t, edges_[ei].src_d);
        auto it = key_to_id_.find(sk);
        if (it == key_to_id_.end()) { ++unknown_edges_; continue; }
        outgoing_[it->second].push_back(ei);
    }

    cost_.assign(N, std::numeric_limits<double>::infinity());
    parent_arc_.assign(N, -1);

    // Source: first explicit source or (0,0)
    source_id_ = -1;
    for (int i = 0; i < N; ++i)
        if (is_source_[i]) { source_id_ = i; break; }
    if (source_id_ < 0) {
        auto it = key_to_id_.find(make_td_key(0.0, 0.0));
        if (it == key_to_id_.end()) throw std::runtime_error("No source node at (0,0)");
        source_id_ = it->second;
    }
    cost_[source_id_] = 0.0;

    // Topological order: lex sort on (t, d)
    topo_order_.resize(N);
    std::iota(topo_order_.begin(), topo_order_.end(), 0);
    std::sort(topo_order_.begin(), topo_order_.end(),
              [&](int a, int b) { return coords_[a] < coords_[b]; });
}

void BellmanSolver::solve() {
    for (int src_id : topo_order_) {
        double base = cost_[src_id];
        if (!std::isfinite(base)) continue;
        for (int ei : outgoing_[src_id]) {
            const auto& e = edges_[ei];
            if (std::isnan(e.fuel_mt)) { ++nan_edges_skipped_; continue; }
            TDKey dk = make_td_key(e.dst_t, e.dst_d);
            auto dit = key_to_id_.find(dk);
            if (dit == key_to_id_.end()) continue;
            int dst_id   = dit->second;
            double new_c = base + e.fuel_mt;
            if (new_c < cost_[dst_id]) {
                cost_[dst_id]      = new_c;
                parent_arc_[dst_id] = ei;
            }
        }
    }
}

int BellmanSolver::best_sink(const std::string& eta_mode, double eta, double lam) {
    std::vector<int> reachable;
    for (int i = 0; i < (int)coords_.size(); ++i)
        if (is_sink_[i] && std::isfinite(cost_[i])) reachable.push_back(i);
    if (reachable.empty()) throw std::runtime_error("No sink reachable from source.");

    if (eta_mode == "hard") {
        if (eta < 0) throw std::invalid_argument("hard ETA requires eta argument");
        std::vector<int> in_time;
        for (int i : reachable)
            if (coords_[i].first <= eta + 1e-6) in_time.push_back(i);
        if (in_time.empty()) throw std::runtime_error("No sink reachable within ETA");
        return *std::min_element(in_time.begin(), in_time.end(),
                                  [&](int a, int b) { return cost_[a] < cost_[b]; });
    }
    if (eta_mode == "soft") {
        if (eta < 0 || lam < 0) throw std::invalid_argument("soft ETA needs eta and lam");
        return *std::min_element(reachable.begin(), reachable.end(), [&](int a, int b) {
            auto pen = [&](int i) {
                return cost_[i] + lam * std::max(0.0, coords_[i].first - eta); };
            return pen(a) < pen(b);
        });
    }
    throw std::invalid_argument("Unknown eta_mode: " + eta_mode);
}

std::vector<int> BellmanSolver::backtrack(int sink_id) {
    std::vector<int> path;
    int cur = sink_id;
    while (parent_arc_[cur] >= 0) {
        int ei = parent_arc_[cur];
        path.push_back(ei);
        TDKey sk = make_td_key(edges_[ei].src_t, edges_[ei].src_d);
        cur = key_to_id_.at(sk);
        if (cur == source_id_) break;
    }
    std::reverse(path.begin(), path.end());
    return path;
}

BellmanResult BellmanSolver::result(const std::string& eta_mode, double eta, double lam) {
    int sink_id  = best_sink(eta_mode, eta, lam);
    auto& coord  = coords_[sink_id];
    auto schedule = backtrack(sink_id);
    int reached  = (int)std::count_if(cost_.begin(), cost_.end(),
                                       [](double c) { return std::isfinite(c); });
    BellmanResult r;
    r.total_fuel_mt   = cost_[sink_id];
    r.voyage_time_h   = coord.first;
    r.schedule        = schedule;
    r.sink_node       = coord;
    r.eta_mode        = eta_mode;
    if (lam >= 0) r.lam = lam;
    r.nan_edges_skipped = nan_edges_skipped_;
    r.nodes_reached   = reached;
    r.nodes_unreached = (int)coords_.size() - reached;
    return r;
}

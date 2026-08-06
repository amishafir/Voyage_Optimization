#include "streaming.hpp"
#include "common.hpp"

#include <algorithm>
#include <cmath>
#include <queue>
#include <stdexcept>
#include <unordered_map>
#include <unordered_set>
#include <utility>

namespace {

// Min-heap ordering on the quantised (t, d) key — exact lexicographic order
// on integers, no float-tie hazards.
struct KeyGreater {
    bool operator()(const TDKey& a, const TDKey& b) const noexcept {
        if (a.t9 != b.t9) return a.t9 > b.t9;
        return a.d9 > b.d9;
    }
};

}  // namespace

StreamingResult solve_streaming(const Frame& frame, double eta,
                                const TimeKey& time_key,
                                double d_start,
                                bool node_first) {
    if (!node_first)
        throw std::runtime_error(
            "streaming engine supports node-first only; use the legacy "
            "engine for the speed-first grid");

    const double L = frame.cfg.length_nm;
    const TDKey src = make_td_key(0.0, d_start);

    std::unordered_map<TDKey, double> cost;
    std::unordered_map<TDKey, AtomicEdge> parent;  // winning incoming arc
    // exact coordinates as first discovered (node-first destinations are
    // generated already 9-rounded, so these coincide with the key values;
    // kept anyway so the enumerator receives the same doubles the legacy
    // builder interned).
    std::unordered_map<TDKey, std::pair<double, double>> coord;
    std::unordered_set<TDKey> popped;

    std::priority_queue<TDKey, std::vector<TDKey>, KeyGreater> heap;
    cost.emplace(src, 0.0);
    coord.emplace(src, std::make_pair(0.0, d_start));
    heap.push(src);

    StreamingResult out;

    while (!heap.empty()) {
        TDKey k = heap.top();
        heap.pop();
        if (!popped.insert(k).second) continue;

        const auto [t, d] = coord.at(k);
        const double base = cost.at(k);

        // Same call the legacy builder makes (forecast_hour = -1,
        // override_sample_hour = -1 → time-varying actual weather with
        // NaN walkback), node-first enumeration.
        auto edges = emit_from_src(t, d, frame, /*forecast_hour=*/-1,
                                   /*override_sample_hour=*/-1, time_key,
                                   /*node_first=*/true);
        for (auto& e : edges) {
            ++out.n_edges_evaluated;
            if (std::isnan(e.fuel_mt)) continue;  // legacy-solver parity
            TDKey dk = make_td_key(e.dst_t, e.dst_d);
            if (popped.count(dk))
                throw std::runtime_error(
                    "streaming invariant violated: relax into a popped state "
                    "(pop order not topological)");
            const double new_cost = base + e.fuel_mt;
            auto it = cost.find(dk);
            const bool fresh = (it == cost.end());
            if (fresh || new_cost < it->second) {
                if (fresh) {
                    cost.emplace(dk, new_cost);
                    coord.emplace(dk, std::make_pair(e.dst_t, e.dst_d));
                } else {
                    it->second = new_cost;
                }
                parent.insert_or_assign(dk, e);
            }
            if (fresh) heap.push(dk);
        }
    }

    out.n_states = cost.size();

    // ---- sink selection (mirrors BellmanSolver::best_sink, hard ETA) ----
    bool found = false;
    TDKey best{};
    double best_cost = 0.0;
    for (const auto& [k, c] : cost) {
        const auto& [t, d] = coord.at(k);
        if (std::abs(d - L) >= 1e-9) continue;
        if (t > eta + 1e-6) continue;
        if (!found || c < best_cost) {
            found = true;
            best = k;
            best_cost = c;
        }
    }
    if (!found) {
        // distinguish the two legacy error messages
        bool any_sink = std::any_of(cost.begin(), cost.end(), [&](const auto& kv) {
            return std::abs(coord.at(kv.first).second - L) < 1e-9;
        });
        throw std::runtime_error(any_sink ? "No sink reachable within ETA"
                                          : "No sink reachable from source.");
    }

    // ---- backtrack (mirrors BellmanSolver::backtrack) ----
    std::vector<AtomicEdge> path;
    TDKey cur = best;
    while (true) {
        auto it = parent.find(cur);
        if (it == parent.end()) break;
        const AtomicEdge& e = it->second;
        path.push_back(e);
        cur = make_td_key(e.src_t, e.src_d);
        if (cur == src) break;
    }
    std::reverse(path.begin(), path.end());

    out.total_fuel_mt = best_cost;
    out.voyage_time_h = coord.at(best).first;
    out.path = std::move(path);
    return out;
}

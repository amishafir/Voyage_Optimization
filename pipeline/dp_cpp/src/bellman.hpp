#pragma once
#include "atomic_edges.hpp"
#include "nodes.hpp"
#include <optional>
#include <string>
#include <utility>
#include <vector>

struct BellmanResult {
    double total_fuel_mt;
    double voyage_time_h;
    std::vector<int> schedule;        // indices into the edges vector, src→sink order
    std::pair<double,double> sink_node;
    std::string eta_mode;
    std::optional<double> lam;
    int nan_edges_skipped;
    int nodes_reached;
    int nodes_unreached;
};

class BellmanSolver {
public:
    BellmanSolver(const std::vector<Node>& nodes,
                   const std::vector<AtomicEdge>& edges);

    void solve();

    BellmanResult result(const std::string& eta_mode = "hard",
                          double eta = -1.0,
                          double lam = -1.0);

    int num_canonical_nodes() const { return (int)coords_.size(); }

private:
    const std::vector<AtomicEdge>& edges_;

    std::vector<std::pair<double,double>> coords_;   // (t, d) per canonical node
    std::unordered_map<TDKey, int>        key_to_id_;
    std::vector<bool>                     is_source_;
    std::vector<bool>                     is_sink_;

    std::vector<std::vector<int>> outgoing_;   // edge indices per source node id
    int    source_id_          = 0;
    int    unknown_edges_      = 0;
    int    nan_edges_skipped_  = 0;

    std::vector<double> cost_;
    std::vector<int>    parent_arc_;  // edge index, -1 = none
    std::vector<int>    topo_order_;

    int best_sink(const std::string& eta_mode, double eta, double lam);
    std::vector<int> backtrack(int sink_id);
};

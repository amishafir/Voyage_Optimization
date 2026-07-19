#include "atomic_edges.hpp"
#include "physics.hpp"
#include <algorithm>
#include <cmath>
#include <cstdio>
#include <deque>
#include <set>
#include <unordered_map>
#include <unordered_set>

static constexpr double SWS_MAX_FEASIBLE = 25.0;
static const ShipParameters DEFAULT_SHIP_PARAMS{};

static LineType line_type_at(double t, double d, const Frame& frame) {
    double eps = 1e-6;
    if (std::abs(t) < eps) return LineType::V;
    for (double vt : frame.v_line_times)
        if (std::abs(t - vt) < eps) return LineType::V;
    return LineType::H;
}

// Emit all atomic edges from one source (t, d).
// sample_hour is chosen per arc from the file's actual sample_hour grid:
//   override_sample_hour >= 0 → use that value (legacy static-deterministic mode)
//   override_sample_hour <  0 → time-varying: active_sample_hour(src_t),
//     with walkback to the most recent valid sample if the cell is NaN at the
//     requested sample_hour. This handles 6 h cadence and failed collection
//     cycles (e.g. sh=12 with 100 % NaN rows).
static std::vector<AtomicEdge> emit_from_src(double src_t, double src_d,
                                               const Frame& frame,
                                               int forecast_hour,
                                               int override_sample_hour,
                                               const TimeKey& time_key,
                                               bool node_first = false) {
    if (std::abs(src_d - frame.cfg.length_nm) < 1e-9) return {};

    const auto& sh_list = frame.voyage->sample_hours();
    int sample_hour;
    int fh_eff = forecast_hour;
    if (time_key) {
        // Rolling-horizon: (sample_hour, forecast_hour) keyed on sub-voyage time.
        auto [sh, fh] = time_key(src_t);
        sample_hour = sh;
        fh_eff      = fh;
    } else if (override_sample_hour >= 0) {
        sample_hour = override_sample_hour;
    } else if (sh_list.empty()) {
        return {};
    } else {
        sample_hour = frame.voyage->active_sample_hour(
            src_t, frame.base_sample_hour ? frame.base_sample_hour : -1);
    }

    Weather wx = frame.cell_weather_at(src_d, sample_hour, fh_eff);
    if (wx.has_nan() && override_sample_hour < 0) {
        // Walk back through sh_list to the most recent valid sample at this cell,
        // holding the effective forecast_hour fixed (works for Mode C and RH).
        auto it = std::lower_bound(sh_list.begin(), sh_list.end(), sample_hour);
        while (it != sh_list.begin() && wx.has_nan()) {
            --it;
            wx = frame.cell_weather_at(src_d, *it, fh_eff);
            if (!wx.has_nan()) { sample_hour = *it; break; }
        }
    }
    if (wx.has_nan()) return {};

    WeatherDict wx_dict = wx.to_dict();
    double heading = frame.paper_heading_at(src_d);

    auto next_v = frame.next_v_time(src_t);
    auto next_h = frame.next_h_distance(src_d);
    if (!next_v && !next_h) return {};

    double L = frame.cfg.length_nm;
    static constexpr double eps = 1e-9;

    std::vector<AtomicEdge> edges;

    if (node_first) {
        // Node-first (Tal, T20): emit the DISTINCT reachable far-wall grid nodes
        // between v_min and v_max, SOG = dd/dt per node — no SOG grid, no
        // target-vs-realised gap. Corner handling: if the next distance line is
        // too close to resolve on the tau grid, skip it and glide to the time
        // line (mirrors the speed-first h_too_close fallback). Mirror of the
        // Python node_first branch in atomic_edges.py.
        const double vmin = frame.cfg.v_min, vmax = frame.cfg.v_max;
        const double zeta = frame.cfg.zeta_nm, tau = frame.cfg.tau_h;
        const double T = frame.cfg.eta_h;
        // round to 9 decimals (dedupe grid) and Python-style round-half-to-even
        // for the integer loop bounds, so the reachable-node set matches Python.
        auto r9 = [](double x) { return std::round(x * 1e9) / 1e9; };
        auto pyround = [](double x) -> long {
            double f = std::floor(x), diff = x - f;
            if (diff < 0.5) return (long)f;
            if (diff > 0.5) return (long)f + 1;
            long fl = (long)f;
            return (fl % 2 == 0) ? fl : fl + 1;   // tie -> even
        };
        std::set<std::pair<double, double>> cand;  // (dst_t, dst_d)

        bool resolvable_d = false;
        double dd_h = 0.0;
        if (next_h) {
            dd_h = *next_h - src_d;
            if (dd_h > eps && frame.snap_h_dst_t(src_t + dd_h / vmax) > src_t + eps)
                resolvable_d = true;
        }
        if (resolvable_d) {                       // distance line binds → enum arrival TIMES
            double t_fast = src_t + dd_h / vmax;
            double t_slow = src_t + dd_h / vmin;
            double t_hi = std::min(t_slow, std::min(next_v ? *next_v : T, T));
            for (long k = pyround(t_fast / tau); k <= pyround(t_hi / tau); ++k) {
                double dst_t = r9(k * tau);
                if (dst_t > src_t + eps && dst_t <= T + eps)
                    cand.insert({dst_t, r9(*next_h)});
            }
        }
        if (next_v) {                             // time line binds → enum arrival DISTANCES
            double dt = *next_v - src_t;
            if (dt > eps) {
                double d_slow = src_d + vmin * dt;
                double d_fast = src_d + vmax * dt;
                double d_cap = resolvable_d ? *next_h : L;   // glide past a too-close line
                double d_hi = std::min(d_fast, std::min(d_cap, L));
                for (long k = pyround(d_slow / zeta); k <= pyround(d_hi / zeta); ++k) {
                    double dst_d = r9(k * zeta);
                    if (dst_d > src_d + eps && dst_d <= L + eps)
                        cand.insert({r9(*next_v), dst_d});
                }
            }
        }
        for (const auto& [dst_t, dst_d] : cand) {
            double ddt = dst_t - src_t, ddd = dst_d - src_d;
            if (ddt <= eps || ddd <= eps) continue;
            double realized_sog = ddd / ddt;
            double sws = calculate_sws_from_sog(realized_sog, wx_dict, heading,
                                                 DEFAULT_SHIP_PARAMS);
            if (std::isnan(sws) || sws > SWS_MAX_FEASIBLE) continue;
            double fcr = calculate_fuel_consumption_rate(sws);
            double fuel = fcr * ddt;
            if (std::isnan(fuel)) continue;
            bool crosses_v = (next_v && std::abs(dst_t - *next_v) < eps);
            edges.push_back({src_t, src_d, dst_t, dst_d,
                             realized_sog, realized_sog, wx, heading,
                             sws, fcr, fuel, crosses_v});
        }
        return edges;
    }

    edges.reserve(frame.sog_grid().size());

    for (double target_sog : frame.sog_grid()) {
        double dt_to_h = next_h ? ((*next_h - src_d) / target_sog) : 1e18;
        double dt_to_v = next_v ? (*next_v - src_t) : 1e18;

        double dst_t, dst_d;

        // Prefer whichever boundary comes first, but if the H-line is so close
        // that snapping collapses the time step (dst_t rounds back to src_t),
        // fall back to the V-line boundary instead.
        bool use_h = (dt_to_h <= dt_to_v + eps) && next_h;
        bool h_too_close = false;
        if (use_h && next_v) {
            double snapped = frame.snap_h_dst_t(src_t + dt_to_h);
            if (snapped <= src_t + eps) { use_h = false; h_too_close = true; }
        }

        // crosses_v_line: true iff this arc reaches a V-line as its terminal boundary.
        // - V-line arcs always cross (dst_t = *next_v, set in the else branch).
        // - H-line arcs whose snapped time overshoots the V-line are clipped to it
        //   (the `if (next_v && dst_t > *next_v - eps)` clip below) — those also cross.
        // - H-line arcs that merely happen to snap onto a V-line time do NOT cross;
        //   treating them as block-boundary unlocks would let the Luo DP change SOG
        //   mid-block whenever an H-line coincides with a V-line discretization point.
        bool crosses_v_line = !use_h;  // V-line arc: always true; H-line arc: may be set below
        if (use_h) {
            dst_d = *next_h;
            double dst_t_raw = src_t + dt_to_h;
            dst_t = frame.snap_h_dst_t(dst_t_raw);
            if (next_v && dst_t > *next_v - eps) {
                dst_t = *next_v;
                crosses_v_line = true;  // H-line clipped to V-line: genuine block boundary
            }
        } else {
            if (!next_v) continue;
            dst_t = *next_v;
            double dst_d_raw = src_d + target_sog * dt_to_v;
            dst_d = frame.snap_v_dst_d(dst_d_raw);
            if (dst_d > L) dst_d = L;
            // Only clip to next_h when it was legitimately chosen as the first
            // boundary. If we fell back to V-line because next_h was too close
            // to snap, clipping here would create a near-zero-distance edge that
            // wastes the entire 6h block.
            if (!h_too_close && next_h && dst_d > *next_h - eps) dst_d = *next_h;
        }

        double dt = dst_t - src_t;
        double dd = dst_d - src_d;
        if (dt <= eps || dd <= eps) continue;

        // Compute SWS/FCR from the realized SOG (dd/dt) so that every arc is
        // self-consistent: speed × duration = distance, and physics matches speed.
        // Time-snapping shifts dst_t, making realized_sog slightly different from
        // target_sog; target_sog is retained only as the Luo-lock label.
        double realized_sog = dd / dt;
        double sws = calculate_sws_from_sog(realized_sog, wx_dict, heading,
                                             DEFAULT_SHIP_PARAMS);
        if (std::isnan(sws) || sws > SWS_MAX_FEASIBLE) continue;

        double fcr  = calculate_fuel_consumption_rate(sws);
        double fuel = fcr * dt;
        if (std::isnan(fuel)) continue;

        edges.push_back({src_t, src_d, dst_t, dst_d,
                         dd / dt, target_sog, wx, heading,
                         sws, fcr, fuel, crosses_v_line});
    }
    return edges;
}

std::pair<std::vector<Node>, std::vector<AtomicEdge>>
build_atomic_edges(const Frame& frame, int forecast_hour,
                   int override_sample_hour, bool verbose,
                   const TimeKey& time_key, double d_start,
                   bool node_first) {
    double L = frame.cfg.length_nm;
    const TDKey src_key = make_td_key(0.0, d_start);

    std::unordered_map<TDKey, Node> node_index;
    auto intern = [&](double t, double d) -> Node& {
        TDKey k = make_td_key(t, d);
        auto it = node_index.find(k);
        if (it != node_index.end()) return it->second;
        bool is_src  = (k == src_key);
        bool is_sink = std::abs(d - L) < 1e-9;
        Node n{t, d, line_type_at(t, d, frame), is_src, is_sink};
        return node_index.emplace(k, n).first->second;
    };

    intern(0.0, d_start);   // register the source node (0, d_start)

    std::deque<TDKey> queue;
    std::unordered_set<TDKey> visited;
    queue.push_back(src_key);

    std::vector<AtomicEdge> edges;

    while (!queue.empty()) {
        TDKey nk = queue.front(); queue.pop_front();
        if (!visited.insert(nk).second) continue;

        auto it = node_index.find(nk);
        if (it == node_index.end()) continue;
        const Node& n = it->second;
        if (n.is_sink) continue;

        auto out = emit_from_src(n.time_h, n.distance_nm, frame,
                                  forecast_hour, override_sample_hour, time_key,
                                  node_first);
        for (auto& e : out) {
            edges.push_back(e);
            intern(e.dst_t, e.dst_d);   // ensure dst is in node_index
            TDKey dk = make_td_key(e.dst_t, e.dst_d);
            if (!visited.count(dk)) queue.push_back(dk);
        }

        if (verbose && visited.size() % 5000 == 0)
            printf("  …%zu nodes visited, %zu edges so far\n",
                   visited.size(), edges.size());
    }

    std::vector<Node> nodes;
    nodes.reserve(node_index.size());
    for (auto& [k, n] : node_index) nodes.push_back(n);
    return {nodes, edges};
}

void summarize_atomic_edges(const std::vector<Node>& nodes,
                              const std::vector<AtomicEdge>& edges) {
    int n_v = 0, n_h = 0, n_src = 0, n_sink = 0;
    for (auto& n : nodes) {
        if (n.line_type == LineType::V) ++n_v; else ++n_h;
        if (n.is_source) ++n_src;
        if (n.is_sink)   ++n_sink;
    }
    printf("========================================================\n");
    printf("DP rebuild — atomic-edge graph summary\n");
    printf("========================================================\n");
    printf("Nodes:       %zu  (V=%d, H=%d, source=%d, sink=%d)\n",
           nodes.size(), n_v, n_h, n_src, n_sink);
    printf("Edges:       %zu\n", edges.size());
    if (edges.empty()) { printf("========================================================\n"); return; }

    double min_fuel = edges[0].fuel_mt, max_fuel = edges[0].fuel_mt, sum_fuel = 0;
    double min_sog  = edges[0].sog,     max_sog  = edges[0].sog;
    double min_sws  = edges[0].sws,     max_sws  = edges[0].sws,  sum_sws = 0;
    for (auto& e : edges) {
        min_fuel = std::min(min_fuel, e.fuel_mt);
        max_fuel = std::max(max_fuel, e.fuel_mt);
        sum_fuel += e.fuel_mt;
        min_sog  = std::min(min_sog, e.sog);
        max_sog  = std::max(max_sog, e.sog);
        min_sws  = std::min(min_sws, e.sws);
        max_sws  = std::max(max_sws, e.sws);
        sum_sws  += e.sws;
    }
    double n_non_sink = std::max(1.0, (double)(nodes.size() - n_sink));
    printf("Avg fan-out: %.2f edges per non-sink node\n", edges.size() / n_non_sink);
    printf("SOG range:   [%.4f, %.4f] kn\n", min_sog, max_sog);
    printf("SWS range:   [%.3f, %.3f] kn  (mean %.3f)\n",
           min_sws, max_sws, sum_sws / edges.size());
    printf("Fuel/edge:   [%.5f, %.4f] mt  (mean %.4f)\n",
           min_fuel, max_fuel, sum_fuel / edges.size());
    printf("========================================================\n");
}

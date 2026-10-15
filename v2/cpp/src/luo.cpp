#include "voyage_v2/luo.hpp"

#include <algorithm>
#include <chrono>
#include <cmath>
#include <limits>
#include <stdexcept>
#include <string>

namespace v2 {
namespace {

constexpr double kInf = std::numeric_limits<double>::infinity();
constexpr std::uint32_t kNone = std::numeric_limits<std::uint32_t>::max();
constexpr double kStepH = 0.25;     // weather step [h]
constexpr double kEps = 1e-9;       // tolerance in grid units

long long ceil_idx(double x) { return static_cast<long long>(std::ceil(x - kEps)); }
long long floor_idx(double x) { return static_cast<long long>(std::floor(x + kEps)); }

class LuoSweep {
public:
    LuoSweep(const Voyage& voyage, const LuoOptions& options);
    DPResult run();

private:
    // An epoch boundary: its weather step, and grid indices lo..hi of its nodes (global id of lo).
    struct Boundary {
        int step;
        long long lo, hi;
        std::uint64_t offset;
        long long size() const { return hi >= lo ? hi - lo + 1 : 0; }
    };

    const SpeedContext& context(int sub, int step);
    SpeedContext fresh_context(int sub, int step) const;
    int subsegment_of(double d) const;
    template <typename Ctx>
    double path_fuel(double d0, double d1, double v, int step0, int n_steps, Ctx&& ctx,
                     double* mean_sws = nullptr) const;
    void relax(std::uint64_t id, double value, std::uint64_t src) {
        if (value < cost_[id]) {
            cost_[id] = value;
            pred_[id] = static_cast<std::uint32_t>(src);
        }
    }
    double node_dist(int e, long long i) const { return e == 0 ? 0.0 : i * delta_; }
    int boundary_of(std::uint64_t id) const;
    PlanArc plan_arc(int e, double d0, double d1) const;
    double constant_sog_fuel() const;

    const Voyage& voyage_;
    const SpeedModel& model_;
    LuoOptions o_;
    std::vector<double> S_;                     // subsegment boundaries S_[0] = 0 .. S_[n] = L
    int n_, M_, K_;
    double eta_h_, L_, vmin_, vmax_, delta_;
    std::vector<Boundary> b_;                   // b_[0]: the start; b_.back(): the ETA (no nodes)
    std::vector<double> cost_;
    std::vector<std::uint32_t> pred_;
    std::vector<double> arrive_cost_;           // arriving at the end of the route at boundary e
    std::vector<std::uint32_t> arrive_pred_;

    std::vector<SpeedContext> ctx_;             // [sub * K_ + step - epoch_step0_], current epoch
    std::vector<int> ctx_stamp_;
    int epoch_ = -1, epoch_step0_ = 0;
    long long arcs_ = 0, infeasible_ = 0;
    mutable long long evaluations_ = 0;
};

LuoSweep::LuoSweep(const Voyage& voyage, const LuoOptions& o)
    : voyage_(voyage), model_(voyage.model()), o_(o) {
    if (o.epoch_steps < 1) throw std::invalid_argument("epoch_steps must be at least 1");
    if (!(o.sog_band_kn > 0)) throw std::invalid_argument("sog_band_kn must be positive");
    if (!(o.dist_step_nm >= 0)) throw std::invalid_argument("dist_step_nm must not be negative");

    n_ = voyage.n_subsegments();
    S_.assign(n_ + 1, 0.0);
    for (int q = 0; q < n_; ++q) S_[q + 1] = S_[q] + voyage.subsegment(q).length_nm;
    L_ = S_[n_];
    M_ = voyage.eta_steps();
    K_ = o.epoch_steps;
    eta_h_ = M_ * kStepH;
    vmin_ = L_ / eta_h_ - o.sog_band_kn;
    vmax_ = L_ / eta_h_ + o.sog_band_kn;
    if (!(vmin_ > 0))
        throw std::invalid_argument("the SOG band reaches zero: mean SOG " + std::to_string(L_ / eta_h_) +
                                    " kn, band " + std::to_string(o.sog_band_kn) + " kn");
    delta_ = o.dist_step_nm > 0 ? o.dist_step_nm : 0.1 * K_ * kStepH;

    // Boundaries every K steps, and the ETA; nodes strictly before the end of the route,
    // reachable from the start within the band and able to arrive by the ETA.
    std::vector<int> steps;
    for (int s = 0; s < M_; s += K_) steps.push_back(s);
    steps.push_back(M_);
    std::uint64_t offset = 0;
    b_.push_back({0, 0, 0, offset++});
    for (std::size_t e = 1; e < steps.size(); ++e) {
        Boundary bd{steps[e], 1, 0, offset};
        if (steps[e] < M_) {
            const double t = steps[e] * kStepH;
            bd.lo = ceil_idx(std::max(vmin_ * t, L_ - vmax_ * (eta_h_ - t)) / delta_);
            bd.hi = std::min(floor_idx(std::min(vmax_ * t, L_) / delta_), ceil_idx(L_ / delta_) - 1);
        }
        offset += bd.size();
        b_.push_back(bd);
    }
    if (offset >= kNone) throw std::length_error("graph has more nodes than 32-bit ids allow");
    cost_.assign(offset, kInf);
    pred_.assign(offset, kNone);
    cost_[0] = 0.0;
    arrive_cost_.assign(b_.size(), kInf);
    arrive_pred_.assign(b_.size(), kNone);
    ctx_.resize(static_cast<std::size_t>(n_) * K_);
    ctx_stamp_.assign(static_cast<std::size_t>(n_) * K_, -1);
}

SpeedContext LuoSweep::fresh_context(int sub, int step) const {
    const Subsegment& g = voyage_.subsegment(sub);
    const Conditions c = voyage_.weather().conditions(g.wind_cell, g.current_cell, step, o_.forecast ? 0 : step);
    return model_.context(g.bearing_deg, c);
}

const SpeedContext& LuoSweep::context(int sub, int step) {
    const std::size_t k = static_cast<std::size_t>(sub) * K_ + (step - epoch_step0_);
    if (ctx_stamp_[k] != epoch_) {
        ctx_[k] = fresh_context(sub, step);
        ctx_stamp_[k] = epoch_;
    }
    return ctx_[k];
}

int LuoSweep::subsegment_of(double d) const {
    const auto it = std::upper_bound(S_.begin(), S_.end(), d);
    return std::max(0, std::min(static_cast<int>(it - S_.begin()) - 1, n_ - 1));
}

// Fuel of sailing [d0, d1] at constant SOG v from the start of weather step step0,
// through n_steps steps: cut at every subsegment boundary and every step boundary,
// each piece at its own subsegment's and step's fuel rate. +inf when v leaves the
// band or a piece's SWS the vessel's range. Optionally the time-weighted mean SWS.
template <typename Ctx>
double LuoSweep::path_fuel(double d0, double d1, double v, int step0, int n_steps, Ctx&& ctx,
                           double* mean_sws) const {
    if (v < vmin_ - kEps || v > vmax_ + kEps) return kInf;
    double fuel = 0.0, sws_time = 0.0, x = d0;
    int sub = subsegment_of(d0), k = 0;
    double step_end = d0 + v * kStepH;                  // where the ship leaves step step0 + k
    while (x < d1) {
        const double x_end = std::min({d1, S_[sub + 1], step_end});
        if (x_end > x) {
            ++evaluations_;
            const double sws = model_.sws(ctx(sub, step0 + std::min(k, n_steps - 1)), v);
            if (!(sws >= kSwsMinKn && sws <= kSwsMaxKn)) return kInf;
            const double dt = (x_end - x) / v;
            fuel += model_.fcr_from_sws(sws) * dt;
            sws_time += sws * dt;
        }
        x = x_end;
        if (x >= d1) break;
        if (x == S_[sub + 1] && sub + 1 < n_) ++sub;
        if (x == step_end) {
            ++k;
            step_end = d0 + v * kStepH * (k + 1);
        }
    }
    if (mean_sws) *mean_sws = sws_time / ((d1 - d0) / v);
    return fuel;
}

int LuoSweep::boundary_of(std::uint64_t id) const {
    return static_cast<int>(std::upper_bound(b_.begin(), b_.end(), id,
                                             [](std::uint64_t v, const Boundary& b) { return v < b.offset; }) -
                            b_.begin()) - 1;
}

PlanArc LuoSweep::plan_arc(int e, double d0, double d1) const {
    const int s0 = b_[e].step, s1 = b_[e + 1].step;
    const double dt = (s1 - s0) * kStepH;
    PlanArc p{};
    p.t0_h = s0 * kStepH;
    p.t1_h = s1 * kStepH;
    p.d0_nm = d0;
    p.d1_nm = d1;
    p.sog_kn = (d1 - d0) / dt;
    p.fuel_mt = path_fuel(d0, d1, p.sog_kn, s0, s1 - s0, [&](int sub, int step) { return fresh_context(sub, step); },
                          &p.sws_kn);
    p.segment = subsegment_of(d0);
    p.step = s0;
    return p;
}

// Every subsegment at the mean SOG, split at the weather steps, in its own weather.
double LuoSweep::constant_sog_fuel() const {
    const double v = L_ / eta_h_;
    double total = 0.0;
    for (int q = 0; q < n_; ++q) {
        double t = S_[q] / v;
        const double t_end = S_[q + 1] / v;
        while (t < t_end - 1e-12) {
            const int m = std::min(static_cast<int>(std::floor(t / kStepH + kEps)), M_ - 1);
            const double t_next = std::min(t_end, (m + 1) * kStepH);
            const double sws = model_.sws(fresh_context(q, m), v);
            if (!(sws >= kSwsMinKn && sws <= kSwsMaxKn)) return kInf;
            total += model_.fcr_from_sws(sws) * (t_next - t);
            t = t_next;
        }
    }
    return total;
}

DPResult LuoSweep::run() {
    const auto start = std::chrono::steady_clock::now();
    for (int e = 0; e + 1 < static_cast<int>(b_.size()); ++e) {
        const Boundary& from = b_[e];
        const Boundary& to = b_[e + 1];
        const int n_steps = to.step - from.step;
        const double dt = n_steps * kStepH;
        epoch_ = e;
        epoch_step0_ = from.step;
        auto ctx = [&](int sub, int step) -> const SpeedContext& { return context(sub, step); };
        const long long q_lo = ceil_idx(vmin_ * dt / delta_), q_hi = floor_idx(vmax_ * dt / delta_);
        for (long long i = from.lo; i <= from.hi; ++i) {
            const std::uint64_t id = from.offset + static_cast<std::uint64_t>(i - from.lo);
            const double c = cost_[id];
            if (c == kInf) continue;
            const double d0 = node_dist(e, i);
            // to the nodes of the next boundary
            const long long lo = std::max(i + q_lo, to.lo), hi = std::min(i + q_hi, to.hi);
            for (long long ip = lo; ip <= hi; ++ip) {
                const double d1 = ip * delta_;
                const double f = path_fuel(d0, d1, (d1 - d0) / dt, from.step, n_steps, ctx);
                ++arcs_;
                if (f == kInf) {
                    ++infeasible_;
                    continue;
                }
                relax(to.offset + static_cast<std::uint64_t>(ip - to.lo), c + f, id);
            }
            // arriving at the end of the route at the next boundary
            const double v = (L_ - d0) / dt;
            if (v >= vmin_ - kEps && v <= vmax_ + kEps) {
                const double f = path_fuel(d0, L_, v, from.step, n_steps, ctx);
                ++arcs_;
                if (f == kInf) ++infeasible_;
                else if (c + f < arrive_cost_[e + 1]) {
                    arrive_cost_[e + 1] = c + f;
                    arrive_pred_[e + 1] = static_cast<std::uint32_t>(id);
                }
            }
        }
    }
    const double sweep_s = std::chrono::duration<double>(std::chrono::steady_clock::now() - start).count();

    DPResult r{};
    r.v_min_kn = vmin_;
    r.v_max_kn = vmax_;
    for (int q = 0; q < n_; ++q) {
        const Subsegment& g = voyage_.subsegment(q);
        r.segments.push_back({S_[q], g.length_nm, g.bearing_deg, g.wind_cell, g.current_cell, q, 1, q});
    }
    int best = -1;
    for (int e = 1; e < static_cast<int>(b_.size()); ++e)
        if (arrive_cost_[e] < kInf && (best < 0 || arrive_cost_[e] < arrive_cost_[best])) best = e;
    r.feasible = best > 0;
    r.fuel_mt = r.feasible ? arrive_cost_[best] : kInf;
    if (r.feasible) {
        r.arrival_h = b_[best].step * kStepH;
        std::vector<std::pair<int, double>> pts{{best, L_}};    // (boundary, distance), end first
        for (std::uint64_t id = arrive_pred_[best]; id != kNone; id = pred_[id]) {
            const int e = boundary_of(id);
            pts.push_back({e, node_dist(e, b_[e].lo + static_cast<long long>(id - b_[e].offset))});
        }
        std::reverse(pts.begin(), pts.end());
        for (std::size_t q = 1; q < pts.size(); ++q) r.path.push_back(plan_arc(pts[q - 1].first, pts[q - 1].second,
                                                                                pts[q].second));
    }
    r.constant_sog_fuel_mt = constant_sog_fuel();

    DPStats& st = r.stats;
    st.nodes = static_cast<long long>(cost_.size());
    st.time_line_nodes = st.nodes;
    st.reached_nodes = std::count_if(cost_.begin(), cost_.end(), [](double c) { return c < kInf; });
    st.arcs = arcs_;
    st.infeasible_arcs = infeasible_;
    st.sws_evaluations = evaluations_;
    st.sweep_s = sweep_s;
    st.memory_mb = cost_.size() * (sizeof(double) + sizeof(std::uint32_t)) / 1e6;
    return r;
}

}  // namespace

DPResult solve_luo(const Voyage& voyage, const LuoOptions& options) {
    const auto start = std::chrono::steady_clock::now();
    LuoSweep sweep(voyage, options);
    const double setup_s = std::chrono::duration<double>(std::chrono::steady_clock::now() - start).count();
    DPResult r = sweep.run();
    r.stats.setup_s = setup_s;
    return r;
}

}  // namespace v2

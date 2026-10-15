#include "voyage_v2/dp.hpp"

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
constexpr double kStepH = 0.25;     // weather step and time-line spacing [h]
constexpr double kEps = 1e-9;       // tolerance in grid units

long long ceil_idx(double x) { return static_cast<long long>(std::ceil(x - kEps)); }
long long floor_idx(double x) { return static_cast<long long>(std::floor(x + kEps)); }

// Grid indices lo..hi on one line, and the global id of index lo.
struct Line {
    long long lo, hi;
    std::uint64_t offset;
    long long size() const { return hi >= lo ? hi - lo + 1 : 0; }
};

class Sweep {
public:
    Sweep(const Voyage& voyage, const DPOptions& options);
    DPResult run();

private:
    // A node: on distance line `line` at tick `idx`, or on time line `line` at grid position `idx`.
    struct Node { bool on_time_line; int line; long long idx; };

    bool merged(int s) const { return seg_[s].n_subs > 1; }
    const SpeedContext& context(int sub, int m);          // cached, for subsegment sub in step m
    SpeedContext fresh_context(int sub, int m, bool actual = false) const;
    double arc_fuel(const SpeedContext& x, double sog, double dt_h);
    template <typename Ctx>
    double piecewise_fuel(int s, double x0, double x1, double sog, double dt_h, Ctx&& ctx,
                          double* mean_sws = nullptr, long long* violations = nullptr) const;
    void build_hh(int k, int m);
    const std::vector<double>& vv(int s, int m);
    // One arc of fuel f from a node of cost c to grid index idx of a line.
    void relax(const Line& line, long long idx, double c, double f, std::uint64_t src) {
        ++arcs_;
        if (f == kInf) {
            ++infeasible_;
            return;
        }
        const double value = c + f;
        const std::uint64_t id = line.offset + static_cast<std::uint64_t>(idx - line.lo);
        if (value < cost_[id]) {
            cost_[id] = value;
            pred_[id] = static_cast<std::uint32_t>(src);
        }
    }
    void from_distance_node(int k, long long j, std::uint64_t id, double c, int m);
    void from_time_node(int m, long long i, std::uint64_t id, double c, int& s);
    int segment_of(double d) const;
    long long below(double d) const;            // largest grid position strictly before d
    Node node(std::uint64_t id) const;
    double time_h(const Node& n) const;
    double dist_nm(const Node& n) const;
    PlanArc plan_arc(const Node& a, const Node& b, long long* violations) const;
    double constant_sog_fuel() const;

    const Voyage& voyage_;
    const SpeedModel& model_;
    DPOptions o_;
    std::vector<Segment> seg_;
    std::vector<double> D_;                     // distance lines D_[0] = 0 .. D_[n] = L
    std::vector<int> piece_begin_;              // pieces of segment s: piece_begin_[s] .. piece_begin_[s+1]-1
    std::vector<int> piece_sub_;                // a piece's subsegment
    std::vector<double> piece_lo_, piece_hi_;   // a piece's extent along the route
    int n_, M_, P_;                             // segments, steps to the ETA, ticks per step
    double tick_h_, zeta_, eta_h_, L_, vmin_, vmax_;
    std::vector<Line> dl_, tl_;                 // distance lines 0..n; time lines 1..M-1 (tl_[0] empty)
    std::vector<double> cost_;
    std::vector<std::uint32_t> pred_;

    std::vector<SpeedContext> ctx_;             // per subsegment, for step ctx_step_[sub]
    std::vector<int> ctx_step_;
    std::vector<double> hh_;                    // distance-to-distance fuel by duration in ticks
    long long hh_min_ = 0, hh_max_ = -1;
    std::vector<std::vector<double>> vv_;       // time-to-time fuel by grid advance, per unmerged segment
    std::vector<int> vv_step_;
    long long vv_min_, vv_max_;
    long long arcs_ = 0, infeasible_ = 0;
    mutable long long evaluations_ = 0;
};

Sweep::Sweep(const Voyage& voyage, const DPOptions& o)
    : voyage_(voyage), model_(voyage.model()), o_(o) {
    if (o.tick_s < 1 || 900 % o.tick_s != 0)
        throw std::invalid_argument("tick_s must divide 900 s, got " + std::to_string(o.tick_s));
    if (!(o.zeta_m > 0)) throw std::invalid_argument("zeta_m must be positive");
    if (!(o.sog_band_kn > 0)) throw std::invalid_argument("sog_band_kn must be positive");
    if (!(o.merge_nm >= 0)) throw std::invalid_argument("merge_nm must not be negative");

    seg_ = merge_subsegments(voyage, o.merge_nm);
    n_ = static_cast<int>(seg_.size());
    D_.assign(n_ + 1, 0.0);
    for (int s = 0; s < n_; ++s) D_[s + 1] = D_[s] + seg_[s].length_nm;
    L_ = D_[n_];
    piece_begin_.assign(n_ + 1, 0);
    for (int s = 0; s < n_; ++s) {
        piece_begin_[s] = static_cast<int>(piece_sub_.size());
        double lo = D_[s];
        for (int q = 0; q < seg_[s].n_subs; ++q) {
            const int sub = seg_[s].first_sub + q;
            const double hi = q + 1 == seg_[s].n_subs ? D_[s + 1] : lo + voyage.subsegment(sub).length_nm;
            piece_sub_.push_back(sub);
            piece_lo_.push_back(lo);
            piece_hi_.push_back(hi);
            lo = hi;
        }
    }
    piece_begin_[n_] = static_cast<int>(piece_sub_.size());
    M_ = voyage.eta_steps();
    P_ = 900 / o.tick_s;
    tick_h_ = o.tick_s / 3600.0;
    zeta_ = o.zeta_m / 1852.0;
    eta_h_ = M_ * kStepH;
    vmin_ = L_ / eta_h_ - o.sog_band_kn;
    vmax_ = L_ / eta_h_ + o.sog_band_kn;
    if (!(vmin_ > 0))
        throw std::invalid_argument("the SOG band reaches zero: mean SOG " + std::to_string(L_ / eta_h_) +
                                    " kn, band " + std::to_string(o.sog_band_kn) + " kn");

    // Every segment must leave at least one tick of arrival times inside the band, or
    // its nodes are dead ends.
    const double min_nm = tick_h_ / (1.0 / vmin_ - 1.0 / vmax_);
    for (const Segment& g : seg_)
        if (g.length_nm < min_nm)
            throw std::invalid_argument("a " + std::to_string(g.length_nm) + " NM segment allows no arrival time on a " +
                                        std::to_string(o.tick_s) + " s grid within the SOG band; merge subsegments "
                                        "shorter than " + std::to_string(min_nm) + " NM (merge_nm)");

    // Node windows: reachable from the start within the band, and able to arrive by the ETA.
    std::uint64_t offset = 0;
    dl_.resize(n_ + 1);
    dl_[0] = {0, 0, offset++};
    for (int k = 1; k <= n_; ++k) {
        const double t_lo = D_[k] / vmax_;
        const double t_hi = std::min(D_[k] / vmin_, eta_h_ - (L_ - D_[k]) / vmax_);
        Line& l = dl_[k];
        l.lo = ceil_idx(t_lo / tick_h_);
        l.hi = floor_idx(t_hi / tick_h_);
        l.offset = offset;
        offset += l.size();
    }
    tl_.resize(M_);
    tl_[0] = {1, 0, offset};
    for (int m = 1; m < M_; ++m) {
        const double t = m * kStepH;
        const double d_lo = std::max(vmin_ * t, L_ - vmax_ * (eta_h_ - t));
        const double d_hi = std::min(vmax_ * t, L_);
        Line& l = tl_[m];
        l.lo = ceil_idx(d_lo / zeta_);
        l.hi = std::min(floor_idx(d_hi / zeta_), below(L_));
        l.offset = offset;
        offset += l.size();
    }
    if (offset >= kNone) throw std::length_error("graph has more nodes than 32-bit ids allow");
    cost_.assign(offset, kInf);
    pred_.assign(offset, kNone);
    cost_[0] = 0.0;

    ctx_.resize(voyage.n_subsegments());
    ctx_step_.assign(voyage.n_subsegments(), -1);
    vv_min_ = std::max(1LL, ceil_idx(vmin_ * kStepH / zeta_));
    vv_max_ = floor_idx(vmax_ * kStepH / zeta_);
    vv_.assign(n_, {});
    vv_step_.assign(n_, -1);
}

long long Sweep::below(double d) const { return ceil_idx(d / zeta_) - 1; }

int Sweep::segment_of(double d) const {
    const auto it = std::upper_bound(D_.begin(), D_.end(), d);
    return std::min(static_cast<int>(it - D_.begin()) - 1, n_ - 1);
}

// The conditions the sweep prices with, or with `actual` the pseudo real-time ones.
SpeedContext Sweep::fresh_context(int sub, int m, bool actual) const {
    const Subsegment& g = voyage_.subsegment(sub);
    const Conditions c = voyage_.weather().conditions(g.wind_cell, g.current_cell, m,
                                                      o_.forecast && !actual ? 0 : m);
    return model_.context(g.bearing_deg, c);
}

const SpeedContext& Sweep::context(int sub, int m) {
    if (ctx_step_[sub] != m) {
        ctx_[sub] = fresh_context(sub, m);
        ctx_step_[sub] = m;
    }
    return ctx_[sub];
}

// Fuel of one arc, or +inf when its SOG leaves the band or its SWS the vessel's range.
double Sweep::arc_fuel(const SpeedContext& x, double sog, double dt_h) {
    if (sog < vmin_ - kEps || sog > vmax_ + kEps) return kInf;
    ++evaluations_;
    const double sws = model_.sws(x, sog);
    if (!(sws >= kSwsMinKn && sws <= kSwsMaxKn)) return kInf;
    return model_.fcr_from_sws(sws) * dt_h;
}

// Fuel at SOG `sog` for dt_h hours over [x0, x1] of segment s: each piece of the
// segment at its own fuel rate for its share of the time (its share of the
// distance, the SOG being constant). Optionally the time-weighted mean SWS. +inf
// when the SOG leaves the band or a covered piece's SWS the vessel's range; given
// `violations`, such pieces are counted and priced anyway (evaluating a plan). On an
// unmerged segment this is arc_fuel with the segment's context, to the bit.
template <typename Ctx>
double Sweep::piecewise_fuel(int s, double x0, double x1, double sog, double dt_h, Ctx&& ctx,
                             double* mean_sws, long long* violations) const {
    if (sog < vmin_ - kEps || sog > vmax_ + kEps) return kInf;
    const double span = x1 - x0;
    double rate = 0.0, sws_sum = 0.0;
    for (int q = piece_begin_[s]; q < piece_begin_[s + 1]; ++q) {
        const double share = (std::min(x1, piece_hi_[q]) - std::max(x0, piece_lo_[q])) / span;
        if (share <= 1e-12) continue;
        ++evaluations_;
        const double sws = model_.sws(ctx(piece_sub_[q]), sog);
        if (!(sws >= kSwsMinKn && sws <= kSwsMaxKn)) {
            if (!violations) return kInf;
            ++*violations;
        }
        rate += model_.fcr_from_sws(sws) * share;
        sws_sum += sws * share;
    }
    if (mean_sws) *mean_sws = sws_sum;
    return rate * dt_h;
}

// Distance-to-distance fuel on segment k in step m, by duration in ticks: the
// same for every node of line k in the step.
void Sweep::build_hh(int k, int m) {
    const double ell = seg_[k].length_nm;
    hh_min_ = std::max(1LL, ceil_idx(ell / vmax_ / tick_h_));
    hh_max_ = floor_idx(ell / vmin_ / tick_h_);
    hh_.assign(static_cast<std::size_t>(std::max(0LL, hh_max_ - hh_min_ + 1)), kInf);
    if (merged(k)) {
        auto ctx = [&](int sub) -> const SpeedContext& { return context(sub, m); };
        for (long long q = hh_min_; q <= hh_max_; ++q) {
            const double dt = q * tick_h_;
            hh_[q - hh_min_] = piecewise_fuel(k, D_[k], D_[k + 1], ell / dt, dt, ctx);
        }
        return;
    }
    const SpeedContext& x = context(seg_[k].first_sub, m);
    for (long long q = hh_min_; q <= hh_max_; ++q) {
        const double dt = q * tick_h_;
        hh_[q - hh_min_] = arc_fuel(x, ell / dt, dt);
    }
}

// Time-to-time fuel on unmerged segment s in step m, by grid advance: the same for
// every node of time line m inside the segment.
const std::vector<double>& Sweep::vv(int s, int m) {
    if (vv_step_[s] != m) {
        std::vector<double>& t = vv_[s];
        t.assign(static_cast<std::size_t>(std::max(0LL, vv_max_ - vv_min_ + 1)), kInf);
        const SpeedContext& x = context(seg_[s].first_sub, m);
        for (long long q = vv_min_; q <= vv_max_; ++q) {
            t[q - vv_min_] = arc_fuel(x, q * zeta_ / kStepH, kStepH);
        }
        vv_step_[s] = m;
    }
    return vv_[s];
}

void Sweep::from_distance_node(int k, long long j, std::uint64_t id, double c, int m) {
    const long long t1 = static_cast<long long>(m + 1) * P_;

    // to the next distance line, before the next time line
    const Line& dst = dl_[k + 1];
    const long long lo = std::max(j + hh_min_, dst.lo);
    const long long hi = std::min({j + hh_max_, t1, dst.hi});
    for (long long jp = lo; jp <= hi; ++jp) relax(dst, jp, c, hh_[jp - j - hh_min_], id);

    // to the next time line, short of the next distance line
    if (m + 1 < M_) {
        const Line& nt = tl_[m + 1];
        const double dt = (t1 - j) * tick_h_;
        const long long ilo = std::max(ceil_idx((D_[k] + vmin_ * dt) / zeta_), nt.lo);
        const long long ihi = std::min({floor_idx((D_[k] + vmax_ * dt) / zeta_), below(D_[k + 1]), nt.hi});
        if (ilo <= ihi && merged(k)) {
            auto ctx = [&](int sub) -> const SpeedContext& { return context(sub, m); };
            for (long long i = ilo; i <= ihi; ++i)
                relax(nt, i, c, piecewise_fuel(k, D_[k], i * zeta_, (i * zeta_ - D_[k]) / dt, dt, ctx), id);
        } else if (ilo <= ihi) {
            const SpeedContext& x = context(seg_[k].first_sub, m);
            for (long long i = ilo; i <= ihi; ++i)
                relax(nt, i, c, arc_fuel(x, (i * zeta_ - D_[k]) / dt, dt), id);
        }
    }
}

void Sweep::from_time_node(int m, long long i, std::uint64_t id, double c, int& s) {
    const double d = i * zeta_;
    while (s + 1 < n_ && D_[s + 1] <= d) ++s;
    const double r = D_[s + 1] - d;
    const long long t0 = static_cast<long long>(m) * P_, t1 = t0 + P_;
    const Line& dst = dl_[s + 1];
    const long long lo = std::max({ceil_idx(t0 + r / vmax_ / tick_h_), t0 + 1, dst.lo});
    const long long hi = std::min({floor_idx(t0 + r / vmin_ / tick_h_), t1, dst.hi});
    long long ilo = 1, ihi = 0;
    if (m + 1 < M_) {
        ilo = std::max(i + vv_min_, tl_[m + 1].lo);
        ihi = std::min({i + vv_max_, below(D_[s + 1]), tl_[m + 1].hi});
    }

    if (merged(s)) {
        auto ctx = [&](int sub) -> const SpeedContext& { return context(sub, m); };
        for (long long j = lo; j <= hi; ++j) {              // to the next distance line
            const double dt = (j - t0) * tick_h_;
            relax(dst, j, c, piecewise_fuel(s, d, D_[s + 1], r / dt, dt, ctx), id);
        }
        for (long long ip = ilo; ip <= ihi; ++ip)            // to the next time line
            relax(tl_[m + 1], ip, c,
                  piecewise_fuel(s, d, ip * zeta_, (ip - i) * zeta_ / kStepH, kStepH, ctx), id);
        return;
    }

    // to the next distance line, before the next time line
    const SpeedContext& x = context(seg_[s].first_sub, m);
    for (long long j = lo; j <= hi; ++j) {
        const double dt = (j - t0) * tick_h_;
        relax(dst, j, c, arc_fuel(x, r / dt, dt), id);
    }

    // to the next time line, short of the next distance line
    if (ilo <= ihi) {
        const std::vector<double>& t = vv(s, m);
        for (long long ip = ilo; ip <= ihi; ++ip) relax(tl_[m + 1], ip, c, t[ip - i - vv_min_], id);
    }
}

Sweep::Node Sweep::node(std::uint64_t id) const {
    if (id < tl_[0].offset) {
        const int k = static_cast<int>(
            std::upper_bound(dl_.begin(), dl_.end(), id,
                             [](std::uint64_t v, const Line& l) { return v < l.offset; }) - dl_.begin()) - 1;
        return {false, k, dl_[k].lo + static_cast<long long>(id - dl_[k].offset)};
    }
    const int m = static_cast<int>(
        std::upper_bound(tl_.begin() + 1, tl_.end(), id,
                         [](std::uint64_t v, const Line& l) { return v < l.offset; }) - tl_.begin()) - 1;
    return {true, m, tl_[m].lo + static_cast<long long>(id - tl_[m].offset)};
}

double Sweep::time_h(const Node& n) const { return n.on_time_line ? n.line * kStepH : n.idx * tick_h_; }
double Sweep::dist_nm(const Node& n) const { return n.on_time_line ? n.idx * zeta_ : D_[n.line]; }

// One arc of the plan, priced with the same expressions as the sweep (planned) and in
// the actual weather (realized; the same when the sweep used the actual weather).
PlanArc Sweep::plan_arc(const Node& a, const Node& b, long long* violations) const {
    PlanArc p{};
    p.t0_h = time_h(a);
    p.d0_nm = dist_nm(a);
    p.t1_h = time_h(b);
    p.d1_nm = dist_nm(b);
    double sog, dt, x0, x1;
    if (!a.on_time_line) {
        p.segment = a.line;
        p.step = static_cast<int>(a.idx / P_);
        x0 = D_[a.line];
        if (!b.on_time_line) {
            dt = (b.idx - a.idx) * tick_h_;
            sog = seg_[a.line].length_nm / dt;
            x1 = D_[a.line + 1];
        } else {
            dt = (static_cast<long long>(p.step + 1) * P_ - a.idx) * tick_h_;
            sog = (b.idx * zeta_ - D_[a.line]) / dt;
            x1 = b.idx * zeta_;
        }
    } else {
        p.segment = segment_of(p.d0_nm);
        p.step = a.line;
        x0 = a.idx * zeta_;
        if (!b.on_time_line) {
            dt = (b.idx - static_cast<long long>(a.line) * P_) * tick_h_;
            sog = (D_[p.segment + 1] - a.idx * zeta_) / dt;
            x1 = D_[p.segment + 1];
        } else {
            dt = kStepH;
            sog = (b.idx - a.idx) * zeta_ / kStepH;
            x1 = b.idx * zeta_;
        }
    }
    p.sog_kn = sog;
    const int m = p.step;
    for (bool actual : {false, true}) {
        if (actual && !o_.forecast) break;              // planned in the actual weather already
        double sws, fuel;
        if (merged(p.segment)) {
            long long* v = actual ? violations : nullptr;
            fuel = piecewise_fuel(p.segment, x0, x1, sog, dt,
                                  [&](int sub) { return fresh_context(sub, m, actual); }, &sws, v);
        } else {
            sws = model_.sws(fresh_context(seg_[p.segment].first_sub, m, actual), sog);
            fuel = model_.fcr_from_sws(sws) * dt;
            if (actual && !(sws >= kSwsMinKn && sws <= kSwsMaxKn)) ++*violations;
        }
        if (!actual) p.planned_fuel_mt = fuel;
        p.sws_kn = sws;
        p.fuel_mt = fuel;
    }
    return p;
}

// Every piece at the mean SOG, split at the time lines, in its own weather.
double Sweep::constant_sog_fuel() const {
    const double v = L_ / eta_h_;
    double total = 0.0;
    for (std::size_t q = 0; q < piece_sub_.size(); ++q) {
        double t = piece_lo_[q] / v;
        const double t_end = piece_hi_[q] / v;
        while (t < t_end - 1e-12) {
            const int m = std::min(static_cast<int>(std::floor(t / kStepH + kEps)), M_ - 1);
            const double t_next = std::min(t_end, (m + 1) * kStepH);
            const double sws = model_.sws(fresh_context(piece_sub_[q], m, true), v);
            if (!(sws >= kSwsMinKn && sws <= kSwsMaxKn)) return kInf;
            total += model_.fcr_from_sws(sws) * (t_next - t);
            t = t_next;
        }
    }
    return total;
}

DPResult Sweep::run() {
    const auto start = std::chrono::steady_clock::now();
    for (int m = 0; m < M_; ++m) {
        if (m >= 1) {                                       // time line m (time m * 0.25 h)
            const Line& tl = tl_[m];
            int s = -1;
            for (long long i = tl.lo; i <= tl.hi; ++i) {
                const std::uint64_t id = tl.offset + static_cast<std::uint64_t>(i - tl.lo);
                const double c = cost_[id];
                if (c == kInf) continue;
                if (s < 0) s = segment_of(i * zeta_);
                from_time_node(m, i, id, c, s);
            }
        }
        const long long t0 = static_cast<long long>(m) * P_, t1 = t0 + P_;
        for (int k = 0; k < n_; ++k) {                      // distance lines, nodes inside step m
            const Line& ln = dl_[k];
            const long long lo = std::max(ln.lo, t0), hi = std::min(ln.hi, t1 - 1);
            bool table = false;
            for (long long j = lo; j <= hi; ++j) {
                const std::uint64_t id = ln.offset + static_cast<std::uint64_t>(j - ln.lo);
                const double c = cost_[id];
                if (c == kInf) continue;
                if (!table) {
                    build_hh(k, m);
                    table = true;
                }
                from_distance_node(k, j, id, c, m);
            }
        }
    }
    const double sweep_s = std::chrono::duration<double>(std::chrono::steady_clock::now() - start).count();

    DPResult r{};
    r.v_min_kn = vmin_;
    r.v_max_kn = vmax_;
    r.segments = seg_;
    const Line& sink = dl_[n_];
    std::uint64_t best = kNone;
    double best_cost = kInf;
    for (long long j = sink.lo; j <= sink.hi; ++j) {
        const std::uint64_t id = sink.offset + static_cast<std::uint64_t>(j - sink.lo);
        if (cost_[id] < best_cost) {
            best_cost = cost_[id];
            best = id;
        }
    }
    r.feasible = best != kNone;
    r.planned_fuel_mt = r.fuel_mt = best_cost;
    long long violations = 0;
    if (r.feasible) {
        std::vector<std::uint64_t> chain;
        for (std::uint64_t id = best; id != kNone; id = pred_[id]) chain.push_back(id);
        std::reverse(chain.begin(), chain.end());
        r.arrival_h = time_h(node(best));
        for (std::size_t q = 1; q < chain.size(); ++q)
            r.path.push_back(plan_arc(node(chain[q - 1]), node(chain[q]), &violations));
        if (o_.forecast) {
            r.fuel_mt = 0.0;
            for (const PlanArc& a : r.path) r.fuel_mt += a.fuel_mt;
        }
    }
    r.constant_sog_fuel_mt = constant_sog_fuel();

    DPStats& st = r.stats;
    for (const Line& l : dl_) st.distance_line_nodes += l.size();
    for (int m = 1; m < M_; ++m) st.time_line_nodes += tl_[m].size();
    st.nodes = static_cast<long long>(cost_.size());
    st.reached_nodes = std::count_if(cost_.begin(), cost_.end(), [](double c) { return c < kInf; });
    st.arcs = arcs_;
    st.infeasible_arcs = infeasible_;
    st.sws_evaluations = evaluations_;
    st.realized_sws_violations = violations;
    st.sweep_s = sweep_s;
    st.memory_mb = cost_.size() * (sizeof(double) + sizeof(std::uint32_t)) / 1e6;
    return r;
}

}  // namespace

std::vector<Segment> merge_subsegments(const Voyage& voyage, double min_nm) {
    struct Piece { double length; int first, count, dominant; };
    std::vector<Piece> p;
    for (int i = 0; i < voyage.n_subsegments(); ++i) p.push_back({voyage.subsegment(i).length_nm, i, 1, i});
    auto longest = [&](const Piece& a, const Piece& b) {
        return voyage.subsegment(a.dominant).length_nm >= voyage.subsegment(b.dominant).length_nm
                   ? a.dominant : b.dominant;
    };
    while (p.size() > 1) {
        const std::size_t i = static_cast<std::size_t>(
            std::min_element(p.begin(), p.end(), [](const Piece& a, const Piece& b) { return a.length < b.length; }) -
            p.begin());
        if (p[i].length >= min_nm) break;
        std::size_t j;                                       // the shorter neighbour, the earlier on ties
        if (i == 0) j = 1;
        else if (i == p.size() - 1) j = i - 1;
        else j = p[i - 1].length <= p[i + 1].length ? i - 1 : i + 1;
        const std::size_t lo = std::min(i, j);
        p[lo] = {p[lo].length + p[lo + 1].length, p[lo].first, p[lo].count + p[lo + 1].count,
                 longest(p[lo], p[lo + 1])};
        p.erase(p.begin() + static_cast<long>(lo) + 1);
    }
    std::vector<Segment> out;
    double start = 0.0;
    for (const Piece& q : p) {
        const Subsegment& d = voyage.subsegment(q.dominant);
        out.push_back({start, q.length, d.bearing_deg, d.wind_cell, d.current_cell, q.first, q.count, q.dominant});
        start += q.length;
    }
    return out;
}

DPResult solve_dp(const Voyage& voyage, const DPOptions& options) {
    const auto start = std::chrono::steady_clock::now();
    Sweep sweep(voyage, options);
    const double setup_s = std::chrono::duration<double>(std::chrono::steady_clock::now() - start).count();
    DPResult r = sweep.run();
    r.stats.setup_s = setup_s;
    return r;
}

}  // namespace v2

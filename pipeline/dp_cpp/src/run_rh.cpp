// run_rh.cpp — Rolling-horizon orchestrator (C++ mirror of pipeline/dp_rebuild/run_rh.py).
//
// Re-plans every 6 h. At each decision step k the look-ahead uses MIXED weather:
//   - first 6 h block (τ < 6): ACTUAL weather at the decision wall-clock (nowcast);
//   - rest (τ ≥ 6):           FORECAST from the most-recent issue ≤ T_wall, at
//                              lead (T_wall - sh_fc) + 6·⌊τ/6⌋, capped at the
//                              issue's max lead.
// SR and Luo each solve the sub-problem from their current position (d_start,
// absolute distances) and EXECUTE block 0 only; realised fuel = Σ executed
// block-0 fuels (block 0 used actual weather, so realised == planned block 0).
// Headline = realised RH fuel vs a Naive fixed-mean-SOG baseline on actual weather.
//
// Usage (run from build/):
//   ./dp_run_rh [--yaml P --h5 P --eta H --sh_base H --max_replans N --out_dir D --label L]
// Defaults: Route 2 (St John's → Liverpool), ETA 168 h, sh_base 0.

#include "SR_main.hpp"
#include "luo_main.hpp"
#include "weather.hpp"

#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstdio>
#include <filesystem>
#include <fstream>
#include <string>
#include <tuple>
#include <unordered_map>
#include <utility>
#include <vector>

namespace fs = std::filesystem;

static constexpr double DT_H = 6.0;
// C++ Mode C oracle reference (golden capture 2026-06-06, Route 2 sh_base=0).
// Override per route via --oracle_sr / --oracle_luo (Route 1: 354.914 / 361.671).
static constexpr double DEFAULT_ORACLE_SR  = 203.357;
static constexpr double DEFAULT_ORACLE_LUO = 210.480;

// ── time_key: most-recent forecast cycle with staleness-adjusted lead ───────
static TimeKey make_time_key(int t_wall, const std::vector<int>& issues,
                             const std::unordered_map<int,int>& max_lead,
                             int& sh_fc_out, int& staleness_out) {
    auto it = std::upper_bound(issues.begin(), issues.end(), t_wall);
    int sh_fc = (it == issues.begin()) ? issues.front() : *(it - 1);
    int staleness = t_wall - sh_fc;
    int cap = 0;
    auto m = max_lead.find(sh_fc);
    if (m != max_lead.end()) cap = m->second;
    sh_fc_out = sh_fc;
    staleness_out = staleness;
    return [t_wall, sh_fc, staleness, cap](double tau) -> std::pair<int,int> {
        if (tau < DT_H) return {t_wall, -1};                 // actual nowcast
        int lead = staleness + (int)(DT_H * std::floor(tau / DT_H));
        if (lead > cap) lead = cap;
        return {sh_fc, lead};
    };
}

// ── block-0 (and block-1) extraction ───────────────────────────────────────
struct BlockM { double fuel; double end_d; double sog; bool found; };

static BlockM sr_block_metrics(const std::vector<AtomicEdge>& edges,
                               const std::vector<int>& schedule,
                               double d_start, double lo, double hi) {
    const double eps = 1e-6;
    double fuel = 0.0, end_d = d_start, start_d = -1.0;
    for (int ei : schedule) {
        const AtomicEdge& e = edges[ei];
        if (e.src_t >= lo - eps && e.src_t < hi - eps) {
            if (start_d < 0) start_d = e.src_d;
            fuel += e.fuel_mt;
            end_d = e.dst_d;
        }
    }
    if (start_d < 0) return {0.0, d_start, 0.0, false};
    double dur = hi - lo;
    double sog = dur > 0 ? (end_d - start_d) / dur : 0.0;
    return {fuel, end_d, sog, true};
}

static BlockM luo_block_metrics(const std::vector<std::pair<ArcResult,int>>& path_arcs,
                                int blk_idx) {
    for (const auto& pr : path_arcs) {
        if (pr.second == blk_idx) {
            const ArcResult& arc = pr.first;
            if (arc.segs.empty()) return {arc.fuel, 0.0, 0.0, true};
            return {arc.fuel, arc.segs.back().dst_d, arc.segs.front().sog, true};
        }
    }
    return {0.0, 0.0, 0.0, false};
}

int main(int argc, char* argv[]) {
    std::string yaml = "../../config/routes/st_johns_liverpool.yaml";
    std::string h5   = "../../data/experiment_d_391wp.h5";
    double eta = 168.0;
    int sh_base = 0;
    int max_replans = 0;
    std::string out_dir = "../../../runs/2026_06_15_rh_cpp/route2/voyage_00";
    std::string label = "route2";
    double oracle_sr = DEFAULT_ORACLE_SR, oracle_luo = DEFAULT_ORACLE_LUO;

    for (int i = 1; i < argc; ++i) {
        std::string a = argv[i];
        auto nxt = [&]() -> const char* {
            if (i + 1 >= argc) { fprintf(stderr, "Missing value for %s\n", a.c_str()); exit(1); }
            return argv[++i];
        };
        if      (a == "--yaml")        yaml = nxt();
        else if (a == "--h5")          h5 = nxt();
        else if (a == "--eta")         eta = std::stod(nxt());
        else if (a == "--sh_base")     sh_base = std::stoi(nxt());
        else if (a == "--max_replans") max_replans = std::stoi(nxt());
        else if (a == "--out_dir")     out_dir = nxt();
        else if (a == "--label")       label = nxt();
        else if (a == "--oracle_sr")   oracle_sr = std::stod(nxt());
        else if (a == "--oracle_luo")  oracle_luo = std::stod(nxt());
        else { fprintf(stderr, "Unknown option: %s\n", a.c_str()); return 1; }
    }

    if (!fs::exists(yaml)) { fprintf(stderr, "YAML not found: %s\n", yaml.c_str()); return 1; }
    if (!fs::exists(h5))   { fprintf(stderr, "HDF5 not found: %s\n", h5.c_str());   return 1; }
    fs::create_directories(out_dir);

    VoyageWeather voyage(h5);
    auto [issues, max_lead] = voyage.forecast_cycle_index();
    double L = voyage.length_nm();
    printf("Route: L=%.1f nm, ETA=%.0f h, sh_base=%d, %zu forecast cycles\n",
           L, eta, sh_base, issues.size());

    auto t_start = std::chrono::steady_clock::now();

    // ── Naive baseline (fixed mean SOG vs actual weather) ──────────────────
    LuoArgs nargs; nargs.yaml = yaml; nargs.h5 = h5; nargs.eta = eta;
    nargs.res_nm = 1.0; nargs.baseline = true; nargs.sample_hour = sh_base;
    double naive_mt = luo_solve(nargs, voyage, /*verbose=*/false).total_fuel_mt;
    printf("Naive baseline: %.3f mt\n", naive_mt);

    // ── RH loop ────────────────────────────────────────────────────────────
    int n_blocks = (int)std::ceil(eta / DT_H - 1e-9);
    if (max_replans > 0) n_blocks = std::min(n_blocks, max_replans);

    double d_sr = 0.0, fuel_sr = 0.0, prev_b1_sr = -999.0;
    double d_luo = 0.0, fuel_luo = 0.0, prev_b1_luo = -999.0;
    double executed_h = 0.0;

    std::ofstream sr_rep(out_dir + "/rh_sr_replans.csv");
    std::ofstream luo_rep(out_dir + "/rh_luo_replans.csv");
    std::ofstream sr_real(out_dir + "/rh_sr_realized.csv");
    std::ofstream luo_real(out_dir + "/rh_luo_realized.csv");
    const char* REP_HDR = "k,t_wall,sub_eta,forecast_cycle,staleness_h,d_start,"
                          "planned_b0_sog,prev_plan_b0_sog,divergence_kn,block0_fuel_mt,sub_solve_s\n";
    sr_rep << REP_HDR; luo_rep << REP_HDR;
    sr_real  << "k,t_h,d_start,d_end,sog_kn,fuel_mt\n";
    luo_real << "k,t_h,d_start,d_end,sog_kn,fuel_mt\n";

    for (int k = 0; k < n_blocks; ++k) {
        double eta_sub = eta - DT_H * k;
        double blk_dur = std::min(DT_H, eta_sub);
        double b1_hi   = std::min(2.0 * DT_H, eta_sub);
        int t_wall = sh_base + (int)(DT_H * k);
        int sh_fc, staleness;
        TimeKey tk = make_time_key(t_wall, issues, max_lead, sh_fc, staleness);

        printf("[k=%02d] T_wall=%4d eta_sub=%5.0f blk=%.0fh cycle=%d(stale %dh) "
               "d_sr=%.1f d_luo=%.1f\n",
               k, t_wall, eta_sub, blk_dur, sh_fc, staleness, d_sr, d_luo);

        // ---- SR ----
        SRArgs sa; sa.yaml = yaml; sa.h5 = h5; sa.eta = eta_sub; sa.sample_hour = sh_base;
        SRResult sr = sr_solve(sa, voyage, /*verbose=*/false, tk, d_sr);
        BlockM s0 = sr_block_metrics(sr.edges, sr.schedule, d_sr, 0.0, blk_dur);
        BlockM s1 = sr_block_metrics(sr.edges, sr.schedule, d_sr, DT_H, b1_hi);
        double div_sr = (prev_b1_sr > -900.0) ? (s0.sog - prev_b1_sr) : NAN;
        sr_rep << k << ',' << t_wall << ',' << eta_sub << ',' << sh_fc << ','
               << staleness << ',' << d_sr << ',' << s0.sog << ',';
        if (prev_b1_sr > -900.0) sr_rep << prev_b1_sr; sr_rep << ',';
        if (!std::isnan(div_sr)) sr_rep << div_sr; sr_rep << ','
               << s0.fuel << ',' << sr.solve_s << '\n';
        sr_real << k << ',' << DT_H * k << ',' << d_sr << ',' << s0.end_d << ','
                << s0.sog << ',' << s0.fuel << '\n';
        fuel_sr += s0.fuel; d_sr = s0.end_d; prev_b1_sr = s1.found ? s1.sog : -999.0;
        printf("        SR : b0_sog=%.3f fuel=%.3f -> d=%.1f (%.1fs)\n",
               s0.sog, s0.fuel, d_sr, sr.solve_s);

        // ---- Luo ----
        LuoArgs la; la.yaml = yaml; la.h5 = h5; la.eta = eta_sub; la.res_nm = 1.0;
        la.sample_hour = sh_base;
        LuoResult luo = luo_solve(la, voyage, /*verbose=*/false, tk, d_luo);
        BlockM l0 = luo_block_metrics(luo.path_arcs, 0);
        BlockM l1 = luo_block_metrics(luo.path_arcs, 1);
        double div_luo = (prev_b1_luo > -900.0) ? (l0.sog - prev_b1_luo) : NAN;
        luo_rep << k << ',' << t_wall << ',' << eta_sub << ',' << sh_fc << ','
                << staleness << ',' << d_luo << ',' << l0.sog << ',';
        if (prev_b1_luo > -900.0) luo_rep << prev_b1_luo; luo_rep << ',';
        if (!std::isnan(div_luo)) luo_rep << div_luo; luo_rep << ','
                << l0.fuel << ',' << luo.solve_s << '\n';
        luo_real << k << ',' << DT_H * k << ',' << d_luo << ',' << l0.end_d << ','
                 << l0.sog << ',' << l0.fuel << '\n';
        fuel_luo += l0.fuel; d_luo = l0.end_d; prev_b1_luo = l1.found ? l1.sog : -999.0;
        printf("        Luo: b0_sog=%.3f fuel=%.3f -> d=%.1f (%.1fs)\n",
               l0.sog, l0.fuel, d_luo, luo.solve_s);

        executed_h += blk_dur;
    }
    sr_rep.close(); luo_rep.close(); sr_real.close(); luo_real.close();

    double runtime_min = std::chrono::duration<double>(
        std::chrono::steady_clock::now() - t_start).count() / 60.0;

    // ── Gates + summary ────────────────────────────────────────────────────
    auto gates = [&](double fuel, double final_d, double oracle) {
        bool reached = std::fabs(final_d - L) < 1.0;
        bool slack0  = std::fabs(executed_h - eta) < 1e-6 && reached;
        bool le_naive = fuel <= naive_mt + 1e-9;
        bool ge_oracle = fuel >= oracle - 1e-9;
        return std::make_tuple(reached, slack0, le_naive, ge_oracle);
    };
    auto [sr_re, sr_sl, sr_ln, sr_go] = gates(fuel_sr, d_sr, oracle_sr);
    auto [lu_re, lu_sl, lu_ln, lu_go] = gates(fuel_luo, d_luo, oracle_luo);
    double sr_vs_naive  = naive_mt ? (fuel_sr - naive_mt) / naive_mt * 100.0 : NAN;
    double luo_vs_naive = naive_mt ? (fuel_luo - naive_mt) / naive_mt * 100.0 : NAN;

    std::ofstream js(out_dir + "/summary.json");
    js << "{\n"
       << "  \"route\": \"" << label << "\",\n"
       << "  \"sh_base\": " << sh_base << ",\n"
       << "  \"eta_h\": " << eta << ",\n"
       << "  \"n_replans\": " << n_blocks << ",\n"
       << "  \"L_nm\": " << L << ",\n"
       << "  \"naive_mt\": " << naive_mt << ",\n"
       << "  \"arrival_h\": " << executed_h << ",\n"
       << "  \"runtime_min\": " << runtime_min << ",\n"
       << "  \"oracle_ref\": {\"sr\": " << oracle_sr << ", \"luo\": " << oracle_luo << "},\n"
       << "  \"results\": {\n"
       << "    \"sr\":  {\"realised_mt\": " << fuel_sr << ", \"final_d_nm\": " << d_sr
       << ", \"vs_naive_pct\": " << sr_vs_naive << ", \"vs_oracle_mt\": " << (fuel_sr - oracle_sr) << "},\n"
       << "    \"luo\": {\"realised_mt\": " << fuel_luo << ", \"final_d_nm\": " << d_luo
       << ", \"vs_naive_pct\": " << luo_vs_naive << ", \"vs_oracle_mt\": " << (fuel_luo - oracle_luo) << "}\n"
       << "  },\n"
       << "  \"gates\": {\n"
       << "    \"sr\":  {\"reached\": " << sr_re << ", \"slack0\": " << sr_sl
       << ", \"rh_le_naive\": " << sr_ln << ", \"rh_ge_oracle\": " << sr_go << "},\n"
       << "    \"luo\": {\"reached\": " << lu_re << ", \"slack0\": " << lu_sl
       << ", \"rh_le_naive\": " << lu_ln << ", \"rh_ge_oracle\": " << lu_go << "}\n"
       << "  }\n}\n";
    js.close();

    printf("\n================================================================\n");
    printf("ROLLING-HORIZON SUMMARY — %s, sh_base=%d\n", label.c_str(), sh_base);
    printf("================================================================\n");
    printf("Naive (fixed mean SOG, actual wx): %8.3f mt\n", naive_mt);
    printf("\nRH-SR : %8.3f mt  vs Naive %+6.2f %%  vs oracle %+6.3f (oracle %.3f)\n",
           fuel_sr, sr_vs_naive, fuel_sr - oracle_sr, oracle_sr);
    printf("        final d %.1f/%.1f nm  arrival %.0f h  GATES reached=%d slack0=%d RH<=Naive=%d RH>=oracle=%d\n",
           d_sr, L, executed_h, sr_re, sr_sl, sr_ln, sr_go);
    printf("RH-Luo: %8.3f mt  vs Naive %+6.2f %%  vs oracle %+6.3f (oracle %.3f)\n",
           fuel_luo, luo_vs_naive, fuel_luo - oracle_luo, oracle_luo);
    printf("        final d %.1f/%.1f nm  arrival %.0f h  GATES reached=%d slack0=%d RH<=Naive=%d RH>=oracle=%d\n",
           d_luo, L, executed_h, lu_re, lu_sl, lu_ln, lu_go);
    printf("\nRuntime: %.1f min   Outputs: %s\n", runtime_min, out_dir.c_str());
    return 0;
}

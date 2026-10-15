# Closed-form SOG->SWS inverse: baseline vs new (2026-10-15)

Baseline = pipeline/shared and dp_cpp/src at HEAD 358b655 (binary search). New = working tree (closed form + fallback). Route D data: edison:~/Ami/pipeline/data/experiment_d_391wp.h5 (old collector, last modified 2026-10-14). Route 1 C++ data: pipeline/dp_cpp/build/experiment_b_138wp.h5. The new code was committed as 9e3c4ae (2026-10-15).

## Python, legacy back-compat cases (Route D)

| Case | Metric | Stored reference | Baseline (old inverse) | New (closed form) | Change |
|---|---|---|---|---|---|
| naive_a | sim_fuel_mt | 216.57 | 203.0001 | 203.0006 | +0.0005 |
| naive_a | sim_time_h | 163.0 | 163.0 | 163.0 | +0.0000 |
| lp_a | plan_fuel_mt | 208.91 | 198.6929 | 198.6929 | +0.0000 |
| lp_a | plan_time_h | 162.99 | 162.9973 | 162.9973 | +0.0000 |
| lp_a | sim_fuel_mt | 215.6 | 202.8144 | 202.8113 | -0.0031 |
| lp_a | sim_time_h | 163.43 | 163.0535 | 163.0535 | +0.0000 |
| lp_a | sws_adj | 64 | 8 | 8 | +0 |
| dp_a | plan_fuel_mt | 222.6 | 221.583 | 221.583 | +0.0000 |
| dp_a | plan_time_h | 162.51 | 162.5316 | 162.5316 | +0.0000 |
| dp_a | sim_fuel_mt | 214.24 | 207.8335 | 207.8334 | -0.0001 |
| dp_a | sim_time_h | 164.53 | 161.6262 | 161.6262 | +0.0000 |
| dp_a | sws_adj | 161 | 106 | 106 | +0 |
| dp_c | plan_fuel_mt | 218.79 | 218.9941 | 218.9941 | +0.0000 |
| dp_c | sim_fuel_mt | 217.28 | 220.6842 | 220.6867 | +0.0025 |
| dp_c | sim_time_h | 163.03 | 163.2618 | 163.2618 | +0.0000 |
| dp_c | sws_adj | 15 | 16 | 16 | +0 |
| lp_c | plan_fuel_mt | 210.84 | 214.3565 | 214.3565 | +0.0000 |
| lp_c | sim_fuel_mt | 215.56 | 218.8288 | 218.8292 | +0.0004 |
| lp_c | sim_time_h | 163.43 | 163.6786 | 163.6786 | +0.0000 |
| lp_c | sws_adj | 51 | 53 | 53 | +0 |
| lp_a_lambda2 | plan_fuel_mt | 191.72 | 172.9023 | 172.9023 | +0.0000 |
| lp_a_lambda2 | plan_delay_h | 7.83 | 11.6357 | 11.6357 | +0.0000 |
| lp_a_lambda2 | plan_cost_mt | 207.38 | 196.1736 | 196.1736 | +0.0000 |
| lp_a_lambda0 | plan_fuel_mt | 172.17 | 167.0333 | 167.0333 | +0.0000 |
| lp_a_lambda0 | plan_delay_h | 21.0 | 15.0 | 15.0 | +0.0000 |
| lp_a_lambda0 | sws_all_min | True | True | True | same |

Python seconds: baseline 2245, new 2271
  naive_a: 1.3 s -> 0.9 s
  lp_a: 0.2 s -> 0.2 s
  dp_a: 35.6 s -> 37.7 s
  dp_c: 1305.6 s -> 1271.7 s
  lp_c: 902.2 s -> 960.7 s
  lp_a_lambda2: 0.1 s -> 0.1 s
  lp_a_lambda0: 0.0 s -> 0.0 s

## C++ solver matrix (dp_cpp, 6 runs per route; build = dp_SR graph build)

| Run | Golden | Baseline fuel (mt) | New fuel (mt) | Change (mt) | Change % | Build s (base -> new) | Wall s (base -> new) |
|---|---|---|---|---|---|---|---|
| sr_route1_geo | 353.968 | 353.9676 | 353.9684 | +0.0009 | +0.0002% | 15.9 -> 3.2 | 20.51 -> 9.7 |
| sr_route1_waypoint | 353.049 | 353.0494 | 353.0546 | +0.0052 | +0.0015% | 16.4 -> 1.8 | 20.57 -> 6.82 |
| luo_route1_geo | 360.643 | 360.6430 | 360.6430 | +0.0000 | +0.0000% |  | 29.04 -> 25.69 |
| luo_route1_waypoint | 360.431 | 360.4310 | 360.4370 | +0.0060 | +0.0017% |  | 19.49 -> 14.05 |
| naive_route1_geo | 361.683 | 361.6830 | 361.6910 | +0.0080 | +0.0022% |  | 3.69 -> 4.6 |
| naive_route1_waypoint | 360.476 | 360.4760 | 360.4690 | -0.0070 | -0.0019% |  | 4.69 -> 5.22 |
| sr_route2_geo | 203.357 | 201.7520 | 201.7599 | +0.0078 | +0.0039% | 7.6 -> 2.2 | 52.52 -> 70.76 |
| sr_route2_waypoint | 205.254 | 204.4828 | 204.4850 | +0.0023 | +0.0011% | 29.2 -> 6.5 | 86.3 -> 70.31 |
| luo_route2_geo | 210.48 | 205.8770 | 205.8810 | +0.0040 | +0.0019% |  | 51.44 -> 65.77 |
| luo_route2_waypoint | 210.058 | 206.1140 | 206.1120 | -0.0020 | -0.0010% |  | 81.49 -> 80.43 |
| naive_route2_geo | 212.609 | 207.4380 | 207.4360 | -0.0020 | -0.0010% |  | 43.99 -> 72.88 |
| naive_route2_waypoint | 211.7 | 206.7530 | 206.7530 | +0.0000 | +0.0000% |  | 66.08 -> 60.58 |

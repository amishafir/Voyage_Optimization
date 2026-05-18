"""
ETA sweep for Route 1 & Route 2 under Mode C (per-block actual weather).

For every (route, sample_hour, ETA) combination in the matrix below, builds
the atomic-edge graph with v_min=9, v_max=25 (never-binding ceiling),
solves SR DP + Luo DP + baseline (steady SOG = L/ETA), and appends a row
to a markdown summary table.

Matrix:
  Route 1 (PG -> Malacca):  sh = 222,  ETA in {280, 240, 200} h
  Route 2 (Atlantic):       sh = 180,  ETA in {168, 144, 120} h
                            sh = 1374, ETA in {168, 144, 120} h
  v_min:                    9   kn   (fixed)
  v_max:                    25  kn   (fixed, never binds anywhere)
  Mode:                     C   (per-block actual_weather, oracle planner)
  SOG step:                 0.1 kn

Reducing ETA pushes the mean SOG above the §5.4 saturation point
(v_max=15), testing the speed-constrained regime where the v_max ceiling
*might* actually bite.

Output: results/eta_sweep_2026_05_18.md
"""

from __future__ import annotations

import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import List

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from atomic_edges import build_atomic_edges
from bellman import BellmanSolver
from bellman_locked import BellmanSolverLocked
from build_edges_locked import simulate_steady_voyage
from frame import from_route as frame_from_route
from nodes import GraphConfig
from route import build_route_from_waypoints_yaml, synthesize_multi_window
from weather import VoyageWeather


# ---- Experiment matrix ------------------------------------------------------

@dataclass
class Run:
    route_name: str
    yaml: Path
    h5: Path
    sample_hour: int
    eta_h: float


YAML_R1 = _HERE.parent / "config" / "routes" / "persian_gulf_malacca.yaml"
H5_R1 = _HERE.parent / "data" / "experiment_b_138wp.h5"
YAML_R2 = _HERE.parent / "config" / "routes" / "st_johns_liverpool.yaml"
H5_R2 = _HERE.parent / "data" / "experiment_d_391wp.h5"

RUNS: List[Run] = []
# R1 (PG) at sh=222, ETA sweep
for eta in (280.0, 240.0, 200.0):
    RUNS.append(Run("Route 1 (PG)", YAML_R1, H5_R1, 222, eta))
# R2 (Atlantic) at sh=180 (storm) and sh=1374 (calm), ETA sweep
for sh in (180, 1374):
    for eta in (168.0, 144.0, 120.0):
        RUNS.append(Run("Route 2 (Atlantic)", YAML_R2, H5_R2, sh, eta))

V_MIN_FIXED = 9.0
V_MAX_FIXED = 25.0

OUTPUT_PATH = _HERE / "results" / "eta_sweep_2026_05_18.md"


# ---- One run ---------------------------------------------------------------

@dataclass
class RunResult:
    route: str
    sample_hour: int
    eta_h: float
    mean_sog: float
    v_min: float
    v_max: float
    n_nodes: int
    n_edges: int
    build_s: float
    base_mt: float
    sr_mt: float
    sr_solve_s: float
    luo_mt: float
    luo_solve_s: float

    @property
    def sr_save_pct(self) -> float:
        return (self.sr_mt - self.base_mt) / self.base_mt * 100.0

    @property
    def luo_minus_sr_mt(self) -> float:
        return self.luo_mt - self.sr_mt


def run_one(spec: Run) -> RunResult:
    tag = (f"{spec.route_name}  sh={spec.sample_hour}  "
           f"ETA={spec.eta_h:.0f} h")
    print("\n" + "-" * 78)
    print(f"RUN: {tag}")
    print("-" * 78)

    route, waypoints = build_route_from_waypoints_yaml(spec.yaml, eta_h=spec.eta_h)
    route = synthesize_multi_window(route, window_h=6.0)
    voyage = VoyageWeather(spec.h5)

    cfg = GraphConfig.from_route(
        route,
        dt_h=6.0,
        zeta_nm=1.0,
        tau_h=0.1,
        weather_cell_nm=30.0,
        v_min=V_MIN_FIXED,
        v_max=V_MAX_FIXED,
    )
    mean_sog = cfg.length_nm / cfg.eta_h
    frame = frame_from_route(
        route, voyage, waypoints,
        cfg=cfg,
        base_sample_hour=spec.sample_hour,
    )
    print(f"  Frame: L={cfg.length_nm:.1f} nm, ETA={cfg.eta_h:.0f} h, "
          f"mean SOG={mean_sog:.2f} kn, "
          f"|sog_grid|={len(frame.sog_grid())}, "
          f"|V|={len(frame.v_line_times)}, |H|={len(frame.h_line_distances)}")

    t0 = time.time()
    nodes, edges = build_atomic_edges(frame, override_sample_hour=None)
    build_s = time.time() - t0
    print(f"  Built {len(nodes):,} nodes / {len(edges):,} edges  "
          f"({build_s:.1f} s)")

    t0 = time.time()
    sr = BellmanSolver(nodes, edges)
    sr.solve()
    sr_res = sr.result(eta_mode="hard", eta=cfg.eta_h)
    sr_solve_s = time.time() - t0
    print(f"  SR DP:  {sr_res.total_fuel_mt:.3f} mt  ({sr_solve_s:.2f} s)")

    t0 = time.time()
    luo = BellmanSolverLocked(nodes, edges, set(frame.v_line_times))
    luo.solve()
    luo_res = luo.result(eta_h=cfg.eta_h)
    luo_solve_s = time.time() - t0
    print(f"  Luo DP: {luo_res.total_fuel_mt:.3f} mt  ({luo_solve_s:.2f} s)")

    target_sog = cfg.length_nm / cfg.eta_h
    base = simulate_steady_voyage(
        L=cfg.length_nm, eta_h=cfg.eta_h,
        route=route, voyage=voyage,
        h_line_distances=frame.h_line_distances,
        waypoints=waypoints, target_sog=target_sog,
        base_sample_hour=spec.sample_hour,
    )
    base_mt = base[2] if base else float("nan")
    print(f"  Baseline (steady {target_sog:.3f} kn): {base_mt:.3f} mt")

    return RunResult(
        route=spec.route_name,
        sample_hour=spec.sample_hour,
        eta_h=cfg.eta_h,
        mean_sog=mean_sog,
        v_min=V_MIN_FIXED,
        v_max=V_MAX_FIXED,
        n_nodes=len(nodes),
        n_edges=len(edges),
        build_s=build_s,
        base_mt=base_mt,
        sr_mt=sr_res.total_fuel_mt,
        sr_solve_s=sr_solve_s,
        luo_mt=luo_res.total_fuel_mt,
        luo_solve_s=luo_solve_s,
    )


# ---- Markdown writer -------------------------------------------------------

def write_summary(results: List[RunResult], path: Path) -> None:
    lines: List[str] = []
    lines.append("# ETA Sweep — Mode C (per-block actual weather)")
    lines.append("")
    lines.append("Sweep run on `pipeline/dp_rebuild/run_eta_sweep.py`. "
                 f"v_min = {V_MIN_FIXED:.0f} kn, v_max = {V_MAX_FIXED:.0f} kn fixed "
                 "(never-binding ceiling). SOG step 0.1 kn. "
                 "Baseline = steady SOG = L/ETA.")
    lines.append("")
    lines.append("## Results")
    lines.append("")
    header = ("| Route | sh | ETA h | mean SOG | "
              "base mt | SR mt | Luo mt | SR save % | Luo−SR mt | "
              "nodes | edges | build s |")
    sep = "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"
    lines.append(header)
    lines.append(sep)
    for r in results:
        lines.append(
            f"| {r.route} | {r.sample_hour} | {r.eta_h:.0f} | "
            f"{r.mean_sog:.2f} | {r.base_mt:.3f} | {r.sr_mt:.3f} | "
            f"{r.luo_mt:.3f} | {r.sr_save_pct:+.3f} | "
            f"{r.luo_minus_sr_mt:+.3f} | "
            f"{r.n_nodes:,} | {r.n_edges:,} | {r.build_s:.1f} |"
        )
    lines.append("")
    lines.append("## Notes")
    lines.append("")
    lines.append("- **Mode C**: each 6 h block reads "
                 "`actual_weather[sample_hour = base_sample_hour + 6·block]`.")
    lines.append("- **SR save %** is `(SR − baseline)/baseline · 100`. "
                 "Negative is savings.")
    lines.append("- **Luo − SR mt** is the SOG-lock cost.")
    lines.append(f"- v_max = {V_MAX_FIXED:.0f} kn fixed across all runs — "
                 "high enough never to bind at any ETA in this matrix.")
    path.write_text("\n".join(lines))
    print(f"\nSummary written to {path}")


# ---- Driver ----------------------------------------------------------------

def main() -> None:
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    results: List[RunResult] = []
    overall_t0 = time.time()

    print("=" * 78)
    print(f"ETA sweep — {len(RUNS)} runs total")
    print(f"v_min = {V_MIN_FIXED}, v_max = {V_MAX_FIXED} (fixed)")
    print("=" * 78)

    for i, spec in enumerate(RUNS, 1):
        print(f"\n[{i}/{len(RUNS)}] "
              f"elapsed {(time.time()-overall_t0)/60:.1f} min")
        try:
            res = run_one(spec)
            results.append(res)
            write_summary(results, OUTPUT_PATH)
        except Exception as exc:
            print(f"  !! RUN FAILED: {exc!r}")
            raise

    total_min = (time.time() - overall_t0) / 60.0
    print(f"\nAll {len(RUNS)} runs complete in {total_min:.1f} min")


if __name__ == "__main__":
    main()

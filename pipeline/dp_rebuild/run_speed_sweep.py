"""
Speed-range sweep for Route 1 & Route 2 under Mode C (per-block actual weather).

For every (route, sample_hour, v_max) combination in the matrix below, builds
the atomic-edge graph with v_min = 9 kn fixed, solves SR DP + Luo DP +
baseline (steady SOG = L/ETA), and appends a row to a markdown summary table.

Matrix:
  Route 1 (PG -> Malacca,  ETA = 280 h):  sh = {222}
  Route 2 (Atlantic,       ETA = 168 h):  sh = {180, 1374}
  v_max sweep:             {13, 15, 18, 21, 24}  kn
  v_min:                   9  kn   (fixed)
  Mode:                    C   (per-block actual_weather, oracle planner)
  SOG step:                0.1 kn  (default)

Output: results/speed_sweep_2026_05_17.md

Run::

    python3 run_speed_sweep.py

This is a long-running job — expect 45-60 min wall time. Progress is printed
to stdout per run.
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
class RouteSpec:
    name: str
    yaml: Path
    h5: Path
    eta_h: float
    sample_hours: List[int]


ROUTES = [
    RouteSpec(
        name="Route 1 (PG)",
        yaml=_HERE.parent / "config" / "routes" / "persian_gulf_malacca.yaml",
        h5=_HERE.parent / "data" / "experiment_b_138wp.h5",
        eta_h=280.0,
        sample_hours=[222],
    ),
    RouteSpec(
        name="Route 2 (Atlantic)",
        yaml=_HERE.parent / "config" / "routes" / "st_johns_liverpool.yaml",
        h5=_HERE.parent / "data" / "experiment_d_391wp.h5",
        eta_h=168.0,
        sample_hours=[180, 1374],
    ),
]

V_MIN_FIXED = 9.0
V_MAX_SWEEP = [13.0, 15.0, 18.0, 21.0, 24.0]

OUTPUT_PATH = _HERE / "results" / "speed_sweep_2026_05_17.md"


# ---- One run ---------------------------------------------------------------

@dataclass
class RunResult:
    route: str
    eta_h: float
    sample_hour: int
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


def run_one(route_spec: RouteSpec, sample_hour: int,
            v_min: float, v_max: float) -> RunResult:
    """Single (route, sh, v_min, v_max) solve."""
    tag = (f"{route_spec.name}  sh={sample_hour}  "
           f"v=[{v_min:.1f}, {v_max:.1f}]")
    print("\n" + "-" * 78)
    print(f"RUN: {tag}")
    print("-" * 78)

    # ---- Route + weather ----
    route, waypoints = build_route_from_waypoints_yaml(
        route_spec.yaml, eta_h=route_spec.eta_h
    )
    route = synthesize_multi_window(route, window_h=6.0)
    voyage = VoyageWeather(route_spec.h5)

    # ---- Custom GraphConfig with the swept speed range ----
    cfg = GraphConfig.from_route(
        route,
        dt_h=6.0,
        zeta_nm=1.0,
        tau_h=0.1,
        weather_cell_nm=30.0,
        v_min=v_min,
        v_max=v_max,
    )
    frame = frame_from_route(
        route, voyage, waypoints,
        cfg=cfg,
        base_sample_hour=sample_hour,
    )
    print(f"  Frame: L={cfg.length_nm:.1f} nm, ETA={cfg.eta_h:.0f} h, "
          f"|sog_grid|={len(frame.sog_grid())}, "
          f"|V|={len(frame.v_line_times)}, |H|={len(frame.h_line_distances)}")

    # ---- Atomic graph (Mode C: override_sample_hour=None) ----
    t0 = time.time()
    nodes, edges = build_atomic_edges(frame, override_sample_hour=None)
    build_s = time.time() - t0
    print(f"  Built {len(nodes):,} nodes / {len(edges):,} edges  "
          f"({build_s:.1f} s)")

    # ---- SR DP ----
    t0 = time.time()
    sr = BellmanSolver(nodes, edges)
    sr.solve()
    sr_res = sr.result(eta_mode="hard", eta=cfg.eta_h)
    sr_solve_s = time.time() - t0
    print(f"  SR DP:  {sr_res.total_fuel_mt:.3f} mt  ({sr_solve_s:.2f} s)")

    # ---- Luo DP ----
    t0 = time.time()
    luo = BellmanSolverLocked(nodes, edges, set(frame.v_line_times))
    luo.solve()
    luo_res = luo.result(eta_h=cfg.eta_h)
    luo_solve_s = time.time() - t0
    print(f"  Luo DP: {luo_res.total_fuel_mt:.3f} mt  ({luo_solve_s:.2f} s)")

    # ---- Baseline (steady L/ETA) ----
    target_sog = cfg.length_nm / cfg.eta_h
    base = simulate_steady_voyage(
        L=cfg.length_nm, eta_h=cfg.eta_h,
        route=route, voyage=voyage,
        h_line_distances=frame.h_line_distances,
        waypoints=waypoints, target_sog=target_sog,
        base_sample_hour=sample_hour,
    )
    base_mt = base[2] if base else float("nan")
    print(f"  Baseline (steady {target_sog:.3f} kn): {base_mt:.3f} mt")

    return RunResult(
        route=route_spec.name,
        eta_h=cfg.eta_h,
        sample_hour=sample_hour,
        v_min=v_min,
        v_max=v_max,
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
    lines.append("# Speed-Range Sweep — Mode C (per-block actual weather)")
    lines.append("")
    lines.append("Sweep run on `pipeline/dp_rebuild/run_speed_sweep.py`. "
                 "v_min = 9 kn fixed, SOG step 0.1 kn. ETA fixed per route "
                 "(R1 = 280 h, R2 = 168 h). Baseline = steady SOG = L/ETA.")
    lines.append("")
    lines.append("## Results")
    lines.append("")
    header = ("| Route | sh | v_max | nodes | edges | build s | "
              "base mt | SR mt | SR save % | Luo mt | Luo−SR mt | "
              "SR solve s | Luo solve s |")
    sep = ("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    lines.append(header)
    lines.append(sep)
    for r in results:
        lines.append(
            f"| {r.route} | {r.sample_hour} | {r.v_max:.0f} | "
            f"{r.n_nodes:,} | {r.n_edges:,} | {r.build_s:.1f} | "
            f"{r.base_mt:.3f} | {r.sr_mt:.3f} | {r.sr_save_pct:+.3f} | "
            f"{r.luo_mt:.3f} | {r.luo_minus_sr_mt:+.3f} | "
            f"{r.sr_solve_s:.2f} | {r.luo_solve_s:.2f} |"
        )
    lines.append("")
    lines.append("## Notes")
    lines.append("")
    lines.append("- **Mode C**: each 6 h block reads "
                 "`actual_weather[sample_hour = base_sample_hour + 6·block]` "
                 "(Luo-2024 weather convention). Oracle / upper-bound planner.")
    lines.append("- **SR save %** is `(SR − baseline)/baseline · 100`. "
                 "Negative is savings.")
    lines.append("- **Luo − SR mt** is the SOG-lock cost. Positive means "
                 "the SR DP saves more.")
    lines.append("- Default sog_step = 0.1 kn. Number of target SOGs = "
                 "(v_max − v_min)/0.1 + 1.")
    path.write_text("\n".join(lines))
    print(f"\nSummary written to {path}")


# ---- Driver ----------------------------------------------------------------

def main() -> None:
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    results: List[RunResult] = []
    overall_t0 = time.time()
    total_runs = sum(len(r.sample_hours) for r in ROUTES) * len(V_MAX_SWEEP)
    run_idx = 0

    print("=" * 78)
    print(f"Speed-range sweep — {total_runs} runs total")
    print(f"v_min fixed = {V_MIN_FIXED}, v_max sweep = {V_MAX_SWEEP}")
    print("=" * 78)

    for rs in ROUTES:
        for sh in rs.sample_hours:
            for v_max in V_MAX_SWEEP:
                run_idx += 1
                print(f"\n[{run_idx}/{total_runs}] "
                      f"elapsed {(time.time()-overall_t0)/60:.1f} min")
                try:
                    res = run_one(rs, sh, V_MIN_FIXED, v_max)
                    results.append(res)
                    # Write partial summary after each run so failures
                    # mid-sweep don't lose prior results.
                    write_summary(results, OUTPUT_PATH)
                except Exception as exc:
                    print(f"  !! RUN FAILED: {exc!r}")
                    raise

    total_min = (time.time() - overall_t0) / 60.0
    print(f"\nAll {total_runs} runs complete in {total_min:.1f} min")


if __name__ == "__main__":
    main()

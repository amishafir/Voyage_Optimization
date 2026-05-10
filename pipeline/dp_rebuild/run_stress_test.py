"""
Stress test the rebuilt DP graph by injecting controlled within-block
weather variability via WeatherPerturber.

For each (σ_wind, σ_wave) magnitude pair in the sweep:
  1. Build atomic-edge graph for Route 2 (St. John's → Liverpool) with the
     perturber active.
  2. Solve Free DP and Luo DP on that graph.
  3. Simulate the perturbed steady-SOG baseline (same perturbation, no
     speed adjustment) for fair comparison.
  4. Record (fuel_baseline, fuel_free, fuel_luo, ΔLuo-Free, ΔFree-baseline).

All three solvers see IDENTICAL perturbation realizations (same seed) so
the comparison is fair: differences are purely from the optimizer's
ability or inability to react to the temporal variation.

Hypothesis (H1): as σ grows, Free DP's advantage over Luo grows
monotonically. Free can change SOG at every H-line crossing in response
to the perturbation; Luo is locked to one SOG per 6 h block.

Output:
  results/stress_test_sweep.txt — per-σ summary table
  results/stress_test_sweep.png — Δ vs σ curve

Usage:
  python3 run_stress_test.py
  python3 run_stress_test.py --route 1   # run on Route 1 instead
"""

from __future__ import annotations

import argparse
import sys
import time
from bisect import bisect_right
from pathlib import Path
from typing import List, Tuple

import matplotlib.pyplot as plt

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

_PIPELINE_ROOT = _HERE.parent
if str(_PIPELINE_ROOT) not in sys.path:
    sys.path.insert(0, str(_PIPELINE_ROOT))

from shared.physics import (  # noqa: E402
    calculate_fuel_consumption_rate,
    calculate_sws_from_sog,
)

from bellman import BellmanSolver  # noqa: E402
from bellman_locked import BellmanSolverLocked  # noqa: E402
from build_atomic_edges import build_atomic_edges  # noqa: E402
from frame import from_route as frame_from_route  # noqa: E402
from h5_weather import VoyageWeather  # noqa: E402
from load_route import build_route_from_waypoints_yaml, synthesize_multi_window  # noqa: E402
from weather_perturb import WeatherPerturber  # noqa: E402


# ----------------------------------------------------------------------
# Sweep configuration
# ----------------------------------------------------------------------

# σ_wind in km/h. σ_wave is proportional (σ_wave = σ_wind / 15 m, so 15 km/h
# wind → 1 m wave perturbation — typical scaling for fully-developed seas).
SWEEP_SIGMAS_WIND = [0.0, 5.0, 10.0, 15.0, 20.0, 30.0]
WAVE_PER_WIND = 1.0 / 15.0
TAU_H = 4.0
SEED = 42
SAMPLE_HOUR = 0


# ----------------------------------------------------------------------
# Perturbed steady-SOG baseline (mirrors simulate_steady_voyage but with
# the same perturber as Free + Luo see)
# ----------------------------------------------------------------------

def perturbed_steady_baseline(
    frame,
    waypoints,
    sample_hour: int = 0,
    perturber=None,
    sws_max_feasible: float = 25.0,
) -> float:
    """Simulate a constant-target-SOG = L/ETA voyage under the same perturbation."""
    L = frame.cfg.length_nm
    eta = frame.cfg.eta_h
    target_sog = L / eta

    h_distances = list(frame.h_line_distances)
    h_with_start = [0.0] + h_distances

    total_fuel = 0.0
    t = 0.0
    d = 0.0
    for d_next in h_with_start:
        if d_next <= d + 1e-9:
            continue
        gap = d_next - d
        # Sub-arc from d to d_next at constant target SOG
        from geo_grid import position_at_d
        _lat, _lon, seg_idx = position_at_d(d, waypoints)
        segs = frame.route.windows[0].segments
        heading = segs[max(0, min(seg_idx, len(segs) - 1))].ship_heading
        weather = frame.cell_weather_at(d, sample_hour)
        if weather.has_nan():
            return float("nan")
        if perturber is not None:
            weather = perturber.perturb(weather, t_h=t, d_nm=d, waypoints=waypoints)
        weather_dict = {
            "wind_speed_10m_kmh": weather.wind_speed_10m_kmh,
            "wind_direction_10m_deg": weather.wind_direction_10m_deg,
            "beaufort_number": weather.beaufort_number,
            "wave_height_m": weather.wave_height_m,
            "ocean_current_velocity_kmh": weather.ocean_current_velocity_kmh,
            "ocean_current_direction_deg": weather.ocean_current_direction_deg,
        }
        sws = calculate_sws_from_sog(
            target_sog=target_sog, weather=weather_dict,
            ship_heading_deg=heading, ship_parameters=None,
        )
        if sws != sws or sws > sws_max_feasible:
            return float("nan")
        dt = gap / target_sog
        fcr = calculate_fuel_consumption_rate(sws)
        total_fuel += fcr * dt
        t += dt
        d = d_next
        if abs(d - L) < 1e-9:
            break
    return total_fuel


# ----------------------------------------------------------------------
# One run at one σ
# ----------------------------------------------------------------------

def run_one_sigma(
    frame, waypoints,
    sigma_wind: float, sigma_wave: float,
    tau_h: float = TAU_H, seed: int = SEED,
    sample_hour: int = SAMPLE_HOUR,
) -> dict:
    perturber = WeatherPerturber(
        mode=("random_walk_ou" if sigma_wind > 0.0 or sigma_wave > 0.0
              else "none"),
        sigma_wind=sigma_wind, sigma_wave=sigma_wave,
        tau_h=tau_h, seed=seed,
    )
    t0 = time.time()
    nodes, edges = build_atomic_edges(
        frame, override_sample_hour=sample_hour, perturber=perturber,
    )
    build_t = time.time() - t0

    free = BellmanSolver(nodes, edges)
    free.solve()
    free_res = free.result(eta_mode="hard", eta=frame.cfg.eta_h)

    luo = BellmanSolverLocked(nodes, edges, set(frame.v_line_times))
    luo.solve()
    luo_res = luo.result(eta_h=frame.cfg.eta_h)

    base_fuel = perturbed_steady_baseline(
        frame, waypoints, sample_hour=sample_hour, perturber=perturber,
    )

    return {
        "sigma_wind": sigma_wind,
        "sigma_wave": sigma_wave,
        "n_nodes": len(nodes),
        "n_edges": len(edges),
        "build_t": build_t,
        "fuel_baseline": base_fuel,
        "fuel_free": free_res.total_fuel_mt,
        "fuel_luo": luo_res.total_fuel_mt,
        "delta_luo_free": luo_res.total_fuel_mt - free_res.total_fuel_mt,
        "delta_free_base": free_res.total_fuel_mt - base_fuel,
        "delta_luo_base": luo_res.total_fuel_mt - base_fuel,
        "free_pct": (free_res.total_fuel_mt - base_fuel) / base_fuel * 100.0
                    if base_fuel == base_fuel else float("nan"),
        "luo_pct":  (luo_res.total_fuel_mt - base_fuel) / base_fuel * 100.0
                    if base_fuel == base_fuel else float("nan"),
        "luo_free_pct": (luo_res.total_fuel_mt - free_res.total_fuel_mt) / base_fuel * 100.0
                        if base_fuel == base_fuel else float("nan"),
    }


def _load_frame(route_id: int):
    if route_id == 2:
        yaml_path = _PIPELINE_ROOT / "config" / "routes" / "st_johns_liverpool.yaml"
        h5_path = _PIPELINE_ROOT / "data" / "experiment_d_391wp.h5"
        eta_h = 168.0
        route, waypoints = build_route_from_waypoints_yaml(yaml_path, eta_h=eta_h)
    elif route_id == 1:
        yaml_path = _PIPELINE_ROOT.parent / "Dynamic speed optimization" / "weather_forecasts.yaml"
        h5_path = _PIPELINE_ROOT / "data" / "voyage_weather.h5"
        from load_route import load_yaml_route
        from route_waypoints import WAYPOINTS
        route = load_yaml_route(yaml_path)
        waypoints = WAYPOINTS
    else:
        raise ValueError(f"unknown route id {route_id}")
    route = synthesize_multi_window(route, window_h=6.0)
    voyage = VoyageWeather(h5_path)
    frame = frame_from_route(route, voyage, waypoints)
    return frame, waypoints


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--route", type=int, default=2, choices=[1, 2])
    ap.add_argument("--sample-hour", type=int, default=SAMPLE_HOUR)
    ap.add_argument("--seed", type=int, default=SEED)
    args = ap.parse_args()

    frame, waypoints = _load_frame(args.route)
    print("=" * 92)
    print(f"Stress sweep — Route {args.route}, sample_hour={args.sample_hour}, seed={args.seed}")
    print(f"  L = {frame.cfg.length_nm:.2f} nm, ETA = {frame.cfg.eta_h:.0f} h, "
          f"{len(frame.v_line_times)} V-lines, {len(frame.h_line_distances)} H-lines")
    print("=" * 92)

    rows = []
    for sigma_wind in SWEEP_SIGMAS_WIND:
        sigma_wave = sigma_wind * WAVE_PER_WIND
        print(f"\n--- σ_wind = {sigma_wind:.1f} km/h, σ_wave = {sigma_wave:.2f} m ---")
        r = run_one_sigma(frame, waypoints, sigma_wind, sigma_wave,
                          sample_hour=args.sample_hour, seed=args.seed)
        rows.append(r)
        print(f"  baseline = {r['fuel_baseline']:.3f} mt   "
              f"free = {r['fuel_free']:.3f} mt ({r['free_pct']:+.3f}%)   "
              f"luo = {r['fuel_luo']:.3f} mt ({r['luo_pct']:+.3f}%)")
        print(f"  Δ(Luo - Free) = {r['delta_luo_free']:+.3f} mt "
              f"({r['luo_free_pct']:+.4f}% of baseline)")

    # ---- Table ----
    print("\n" + "=" * 102)
    print("STRESS-SWEEP RESULTS")
    print("=" * 102)
    print(f"  {'σ_wind':>8} {'σ_wave':>7} {'baseline':>9} {'free':>9} {'luo':>9} "
          f"{'Δ Free-base':>13} {'Δ Luo-base':>12} {'Δ Luo-Free':>12} {'Δ%':>7}")
    print("-" * 102)
    for r in rows:
        print(f"  {r['sigma_wind']:>8.1f} {r['sigma_wave']:>7.2f} "
              f"{r['fuel_baseline']:>9.3f} {r['fuel_free']:>9.3f} {r['fuel_luo']:>9.3f} "
              f"{r['delta_free_base']:>+13.3f} {r['delta_luo_base']:>+12.3f} "
              f"{r['delta_luo_free']:>+12.3f} {r['luo_free_pct']:>+7.4f}")
    print("=" * 102)

    # ---- Save table to file ----
    out_dir = _HERE / "results"
    out_dir.mkdir(exist_ok=True)
    out_txt = out_dir / f"stress_test_sweep_route{args.route}.txt"
    with open(out_txt, "w") as f:
        f.write(f"Route {args.route} stress sweep (sample_hour={args.sample_hour}, seed={args.seed})\n")
        f.write(f"L = {frame.cfg.length_nm:.2f} nm, ETA = {frame.cfg.eta_h:.0f} h\n\n")
        f.write(f"{'σ_wind':>8} {'σ_wave':>7} {'baseline':>9} {'free':>9} {'luo':>9} "
                f"{'Δ Free-base':>13} {'Δ Luo-base':>12} {'Δ Luo-Free':>12} {'Δ% baseline':>13}\n")
        for r in rows:
            f.write(f"{r['sigma_wind']:>8.1f} {r['sigma_wave']:>7.2f} "
                    f"{r['fuel_baseline']:>9.3f} {r['fuel_free']:>9.3f} {r['fuel_luo']:>9.3f} "
                    f"{r['delta_free_base']:>+13.3f} {r['delta_luo_base']:>+12.3f} "
                    f"{r['delta_luo_free']:>+12.3f} {r['luo_free_pct']:>+12.4f}\n")
    print(f"\nTable saved: {out_txt}")

    # ---- Plot ----
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    sigmas = [r["sigma_wind"] for r in rows]
    free_pcts = [r["free_pct"] for r in rows]
    luo_pcts = [r["luo_pct"] for r in rows]
    gap_pcts = [r["luo_free_pct"] for r in rows]

    ax = axes[0]
    ax.plot(sigmas, free_pcts, "o-", color="#1a73e8", label="Free DP vs baseline")
    ax.plot(sigmas, luo_pcts, "s--", color="#d62728", label="Luo DP vs baseline")
    ax.axhline(0.0, color="black", linewidth=0.6, alpha=0.5)
    ax.set_xlabel("σ_wind (km/h)")
    ax.set_ylabel("Δfuel vs baseline (% of baseline)")
    ax.set_title(f"Route {args.route} — DP fuel vs steady-SOG baseline")
    ax.legend()
    ax.grid(alpha=0.3)

    ax = axes[1]
    ax.plot(sigmas, gap_pcts, "o-", color="#5e35b1", label="Δ(Luo - Free) / baseline")
    ax.axhline(0.0, color="black", linewidth=0.6, alpha=0.5)
    ax.set_xlabel("σ_wind (km/h)")
    ax.set_ylabel("Δ(Luo - Free) (% of baseline)")
    ax.set_title("Free's advantage over Luo grows with stress")
    ax.legend()
    ax.grid(alpha=0.3)

    plt.tight_layout()
    out_png = out_dir / f"stress_test_sweep_route{args.route}.png"
    plt.savefig(out_png, dpi=150)
    print(f"Plot saved:  {out_png}")


if __name__ == "__main__":
    main()

"""
dp_SR — Shafir-Raviv SR DP.

Python mirror of ``pipeline/dp_cpp/src/SR_main.cpp``. Builds a (t, d) graph
of atomic edges (one arc per discrete target SOG per source) and runs a
single-pass topological Bellman to find the minimum-fuel path from
``(0, 0)`` to any sink ``(·, L)`` arriving at or before ``ETA``.

Default speed range is centered on ``mean_sog = L / ETA`` (± 3 kn).
Override with ``--min_speed`` / ``--max_speed``.

Usage::

    python3 SR_main.py [OPTIONS]
        --yaml PATH       Route YAML  (default: route.yaml)
        --h5   PATH       HDF5 file   (default: voyage_weather.h5)
        --eta  HOURS      Override ETA in hours
        --min_speed KNOTS Minimum SOG in knots  (default: mean_sog - 3)
        --max_speed KNOTS Maximum SOG in knots  (default: mean_sog + 3)
        --zeta_nm  NM     Distance snap for H-line arc destinations
        --tau_h    HOURS  Time snap for V-line arc destinations
        --csv             Write per-arc schedule to sr_dp.csv
"""

from __future__ import annotations

import argparse
import csv
import sys
import time
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from atomic_edges import build_atomic_edges, summarize as summarize_atomic_edges
from bellman import BellmanSolver
from frame import from_route as make_frame
from geo_grid import position_at_d
from nodes import GraphConfig
from route import load_route_auto, synthesize_multi_window
from weather import VoyageWeather


# CSV column order — must match ``write_arc_csv`` in SR_main.cpp.
CSV_COLUMNS = [
    "time_h", "distance_nm", "lat_deg", "lon_deg", "bearing_deg",
    "sog_kn", "sws_kn", "fcr_mt_per_h", "fuel_mt", "duration_h",
    "wind_speed_kmh", "wind_dir_deg", "beaufort", "wave_height_m",
    "current_vel_kmh", "current_dir_deg",
]


def write_arc_csv(path: Path, schedule, waypoints) -> None:
    """One row per atomic edge in the optimal schedule — mirrors SR_main.cpp."""
    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(CSV_COLUMNS)
        for e in schedule:
            lat, lon, _seg = position_at_d(e.src_d, waypoints)
            w = e.weather
            writer.writerow([
                e.src_t, e.src_d, lat, lon, e.heading_deg,
                e.sog, e.sws, e.fcr_mt_per_h, e.fuel_mt, e.dst_t - e.src_t,
                w.wind_speed_10m_kmh, w.wind_direction_10m_deg, w.beaufort_number,
                w.wave_height_m,
                w.ocean_current_velocity_kmh, w.ocean_current_direction_deg,
            ])
    print(f"  CSV written: {path}  ({len(schedule)} arcs)")


def _print_header(title: str) -> None:
    bar = "=" * 78
    print(f"\n{bar}\n{title}\n{bar}")


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(
        prog="SR_main",
        description="Shafir-Raviv SR DP — Python port of dp_SR",
    )
    ap.add_argument("--yaml", default="route.yaml", help="Route YAML (default: route.yaml)")
    ap.add_argument("--h5", default="voyage_weather.h5",
                    help="HDF5 file (default: voyage_weather.h5)")
    ap.add_argument("--eta", type=float, default=None, help="Override ETA in hours")
    ap.add_argument("--min_speed", type=float, default=None,
                    help="Minimum SOG in knots (default: mean_sog - 3)")
    ap.add_argument("--max_speed", type=float, default=None,
                    help="Maximum SOG in knots (default: mean_sog + 3)")
    ap.add_argument("--zeta_nm", type=float, default=None,
                    help="Distance snap for H-line arc destinations (default: 1.0)")
    ap.add_argument("--tau_h", type=float, default=None,
                    help="Time snap for V-line arc destinations (default: 0.1)")
    ap.add_argument("--csv", action="store_true",
                    help="Write per-arc solution CSV (sr_dp.csv)")
    return ap.parse_args()


def main() -> int:
    args = parse_args()

    yaml_path = Path(args.yaml)
    h5_path = Path(args.h5)
    if not yaml_path.exists():
        print(f"YAML not found: {yaml_path}", file=sys.stderr)
        return 1
    if not h5_path.exists():
        print(f"HDF5 not found: {h5_path}", file=sys.stderr)
        return 1

    # ---- Load route & weather ----
    # load_route_auto dispatches on schema: "forecasts:" → segments-table +
    # hardcoded paper WAYPOINTS; "waypoints:" → computed from lat/lon.
    route, waypoints = load_route_auto(yaml_path, eta_h=args.eta)
    route = synthesize_multi_window(route, window_h=6.0)
    voyage = VoyageWeather(h5_path)

    # ---- Build frame ----
    _print_header("dp_SR — frame")
    cfg = GraphConfig.from_route(route)
    if args.eta is not None:
        cfg.eta_h = args.eta
        # Patch the last forecast-window end so route.eta_h agrees with cfg.
        if route.windows:
            route.windows[-1].end = float(args.eta)
            route = synthesize_multi_window(route, window_h=6.0)
    if args.zeta_nm is not None:
        cfg.zeta_nm = args.zeta_nm
    if args.tau_h is not None:
        cfg.tau_h = args.tau_h

    mean_sog = cfg.length_nm / cfg.eta_h
    cfg.v_min = args.min_speed if args.min_speed is not None else (mean_sog - 3.0)
    cfg.v_max = args.max_speed if args.max_speed is not None else (mean_sog + 3.0)

    frame = make_frame(route, voyage, waypoints, cfg=cfg)
    n_blocks = int(cfg.eta_h / cfg.dt_h)
    print("=" * 60)
    print("DP rebuild — Frame summary")
    print("=" * 60)
    print(f"Route:         L = {cfg.length_nm:.3f} nm, ETA = {cfg.eta_h:.1f} h")
    print(f"V-lines:       {len(frame.v_line_times)} times, "
          f"first = {frame.v_line_times[0]:.2f} h, last = {frame.v_line_times[-1]:.2f} h")
    print(f"               dt_h = {cfg.dt_h} h, zeta_nm = {cfg.zeta_nm} nm")
    print(f"H-lines:       {len(frame.h_line_distances)} distances")
    print(f"               tau_h = {cfg.tau_h:.2f} h")
    sog_grid = frame.sog_grid()
    print(f"SOG grid:      {len(sog_grid)} target SOGs in "
          f"[{sog_grid[0]:.1f}, {sog_grid[-1]:.1f}] kn at {frame.sog_step} kn step")
    print(f"Blocks:        {n_blocks} blocks of {cfg.dt_h:.1f} h")
    print("=" * 60)

    # ---- Build atomic-edge graph ----
    _print_header("dp_SR — build atomic-edge graph")
    t0 = time.time()
    # override_sample_hour=None → time-varying: per-arc active_sample_hour(src_t)
    # with NaN walkback (mirror of dp_SR with override_sample_hour=-1 in C++,
    # commit 752ae0b). Pass an int here to force static-mode legacy behaviour.
    nodes, edges = build_atomic_edges(frame,
                                      forecast_hour=None,
                                      override_sample_hour=None,
                                      verbose=False)
    build_t = time.time() - t0
    print(f"\nBuild time: {build_t:.2f} s\n")
    summarize_atomic_edges(nodes, edges)

    # ---- dp_SR (SR DP, no SOG lock) ----
    t0 = time.time()
    solver = BellmanSolver(nodes, edges)
    solver.solve()
    res = solver.result(eta_mode="hard", eta=cfg.eta_h)
    solve_t = time.time() - t0

    if args.csv:
        write_arc_csv(Path("sr_dp.csv"), res.schedule, waypoints)

    # ---- Summary ----
    _print_header("dp_SR — SUMMARY")
    print(f"  Total fuel:  {res.total_fuel_mt:.3f} mt")
    print(f"  Voyage time: {res.voyage_time_h:.3f} h  (ETA = {cfg.eta_h:.1f} h)")
    print(f"  Graph: {len(nodes)} nodes, {len(edges)} atomic edges")
    print(f"  Build: {build_t:.1f} s  Solve: {solve_t:.2f} s\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())

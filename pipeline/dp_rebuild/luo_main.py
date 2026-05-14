"""
dp_luo — Luo block DP + baseline mode.

Python mirror of ``pipeline/dp_cpp/src/luo_main.cpp``.

Graph: nodes ``(col, d_idx)`` where ``col`` indexes a time column and
``d_idx`` is a distance index; physical distance = ``d_idx * res_nm``.

    Regular columns:  col = 0..T_steps,  t = 0, dt_h, 2·dt_h, … T_steps·dt_h
    ETA column:       col = T_steps + 1, t = ETA   (added when ETA % dt_h ≠ 0)

Arcs span one column (one block):

    Regular arc:  duration = dt_h,     SOG = (d2-d1)*res_nm / dt_h
    Partial arc:  duration = dt_last,  SOG = (d2-d1)*res_nm / dt_last

Arc cost: walk sub-segments between weather-zone / course-change boundaries
from ``d1*res_nm`` to ``d2*res_nm``, summing fuel at the fixed block SOG.

Shortest path from ``(0, 0)`` to any ``(col, L_scaled)`` with ``col ≤ last_col``.

The ``--baseline`` mode skips the graph entirely and does a single linear walk
at the fixed mean SOG ``L / ETA``, splitting at the same sub-segment
boundaries.

Usage::

    python3 luo_main.py [OPTIONS]
        --yaml PATH       Route YAML  (default: route.yaml)
        --h5   PATH       HDF5 file   (default: voyage_weather.h5)
        --eta  HOURS      Override ETA in hours
        --min_speed KNOTS Minimum SOG in knots  (default: mean_sog - 3)
        --max_speed KNOTS Maximum SOG in knots  (default: mean_sog + 3)
        --res_nm  NM      Distance grid resolution (default: 1.0, range [0.1, 10])
        --baseline        Compute fixed mean-SOG baseline (no graph)
        --csv             Write schedule CSV(s)
                            Luo DP  → luo_dp.csv
                            Baseline → baseline.csv
"""

from __future__ import annotations

import argparse
import csv
import math
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from common import ShipParameters
from frame import from_route as make_frame, Frame
from geo_grid import position_at_d
from nodes import GraphConfig
from physics import (
    calculate_fuel_consumption_rate,
    calculate_sws_from_sog,
)
from route import load_yaml_route, synthesize_multi_window
from route_waypoints import WAYPOINTS
from weather import VoyageWeather
from weather import Weather   # AtomicEdge's weather struct — Luo uses the same


SWS_MAX = 25.0
SHIP = ShipParameters()  # default vessel params, matches C++ luo_main.cpp


# ----------------------------------------------------------------------
# Per-sub-segment record (mirrors the C++ Seg struct)
# ----------------------------------------------------------------------

@dataclass
class Seg:
    """One weather-zone sub-segment within a block."""
    src_d: float           # nm
    dst_d: float           # nm
    src_t: float           # h — absolute time at sub-segment start
    sog: float             # block SOG [kn] — constant within block
    heading_deg: float
    weather: Weather
    sws: float
    fcr: float
    fuel_mt: float
    dur_h: float


@dataclass
class ArcResult:
    """Result of evaluating one block arc (d1_idx → d2_idx)."""
    ok: bool = False
    fuel: float = 0.0
    segs: List[Seg] = None

    def __post_init__(self):
        if self.segs is None:
            self.segs = []


def _weather_to_dict(w: Weather) -> dict:
    return {
        "wind_speed_10m_kmh": w.wind_speed_10m_kmh,
        "wind_direction_10m_deg": w.wind_direction_10m_deg,
        "beaufort_number": w.beaufort_number,
        "wave_height_m": w.wave_height_m,
        "ocean_current_velocity_kmh": w.ocean_current_velocity_kmh,
        "ocean_current_direction_deg": w.ocean_current_direction_deg,
    }


# ----------------------------------------------------------------------
# eval_arc — block arc evaluation
# ----------------------------------------------------------------------

def eval_arc(
    d1_idx: int,
    d2_idx: int,
    t_h: float,
    block_dur_h: float,
    bounds: List[float],
    frame: Frame,
    res_nm: float,
    sample_hour: int = 0,
    forecast_hour: Optional[int] = None,
) -> ArcResult:
    """Evaluate one block arc (d1_idx → d2_idx) departing at t_h.

    SOG is constant within the block at ``(d2-d1)*res_nm / block_dur_h``.
    Walks every sub-segment break point (H-line boundary) strictly between
    ``d1*res_nm`` and ``d2*res_nm``, summing fuel at the block SOG.

    Returns ``ArcResult(ok=False)`` on NaN weather or infeasible SWS
    (``> SWS_MAX = 25 kn``). Mirrors C++ luo_main.cpp `eval_arc` line-for-line.
    """
    r = ArcResult()
    d1 = d1_idx * res_nm
    d2 = d2_idx * res_nm
    sog = (d2 - d1) / block_dur_h

    # Collect sub-segment breakpoints strictly inside (d1, d2).
    pts: List[float] = [d1]
    for b in bounds:
        if b > d1 + 1e-9 and b < d2 - 1e-9:
            pts.append(b)
    pts.append(d2)

    for i in range(len(pts) - 1):
        sd = pts[i]
        ed = pts[i + 1]
        heading = frame.paper_heading_at(sd)
        wx = frame.cell_weather_at(sd, sample_hour=sample_hour,
                                   forecast_hour=forecast_hour)
        if wx.has_nan():
            return r  # ok=False

        wd = _weather_to_dict(wx)
        sws = calculate_sws_from_sog(
            target_sog=sog,
            weather=wd,
            ship_heading_deg=heading,
            ship_parameters=None,
        )
        if math.isnan(sws) or sws > SWS_MAX:
            return r

        fcr = calculate_fuel_consumption_rate(sws)
        dur = (ed - sd) / sog
        fuel = fcr * dur
        if math.isnan(fuel):
            return r

        src_t = t_h + (sd - d1) / sog
        r.segs.append(Seg(
            src_d=sd, dst_d=ed, src_t=src_t, sog=sog,
            heading_deg=heading, weather=wx,
            sws=sws, fcr=fcr, fuel_mt=fuel, dur_h=dur,
        ))
        r.fuel += fuel
    r.ok = True
    return r


# ----------------------------------------------------------------------
# eval_baseline — fixed mean SOG, no graph
# ----------------------------------------------------------------------

def eval_baseline(
    frame: Frame,
    bounds: List[float],
    sample_hour: int = 0,
    forecast_hour: Optional[int] = None,
) -> List[Seg]:
    """Fixed mean-SOG baseline.

    SOG = L / ETA constant for the entire voyage. Walks every sub-segment
    boundary in ``bounds``, splitting the route at H-line crossings and
    computing SWS / FCR / fuel for each. NaN-weather sub-segments are
    skipped (warned to stderr).
    """
    sog = frame.cfg.length_nm / frame.cfg.eta_h
    segs: List[Seg] = []
    L = frame.cfg.length_nm

    for i in range(len(bounds) - 1):
        sd = bounds[i]
        ed = bounds[i + 1]
        if ed > L + 1e-9:
            ed = L
        if ed <= sd + 1e-9:
            continue

        heading = frame.paper_heading_at(sd)
        wx = frame.cell_weather_at(sd, sample_hour=sample_hour,
                                   forecast_hour=forecast_hour)
        if wx.has_nan():
            print(f"  NaN weather at d={sd:.1f} nm — sub-segment skipped",
                  file=sys.stderr)
            continue
        wd = _weather_to_dict(wx)
        sws = calculate_sws_from_sog(
            target_sog=sog,
            weather=wd,
            ship_heading_deg=heading,
            ship_parameters=None,
        )
        fcr = calculate_fuel_consumption_rate(sws)
        dur = (ed - sd) / sog
        fuel = fcr * dur
        src_t = sd / sog
        segs.append(Seg(
            src_d=sd, dst_d=ed, src_t=src_t, sog=sog,
            heading_deg=heading, weather=wx,
            sws=sws, fcr=fcr, fuel_mt=fuel, dur_h=dur,
        ))
    return segs


# ----------------------------------------------------------------------
# CSV writers (mirror C++)
# ----------------------------------------------------------------------

_LUO_COLUMNS = [
    "block", "time_h", "distance_nm", "lat_deg", "lon_deg", "bearing_deg",
    "sog_kn", "sws_kn", "fcr_mt_per_h", "fuel_mt", "duration_h",
    "wind_speed_kmh", "wind_dir_deg", "beaufort", "wave_height_m",
    "current_vel_kmh", "current_dir_deg",
]
_BASELINE_COLUMNS = _LUO_COLUMNS[1:]  # same minus "block"


def _row_for_seg(s: Seg, block: Optional[int] = None) -> list:
    lat, lon, _seg = position_at_d(s.src_d, WAYPOINTS)
    w = s.weather
    base = [
        s.src_t, s.src_d, lat, lon, s.heading_deg,
        s.sog, s.sws, s.fcr, s.fuel_mt, s.dur_h,
        w.wind_speed_10m_kmh, w.wind_direction_10m_deg, w.beaufort_number,
        w.wave_height_m,
        w.ocean_current_velocity_kmh, w.ocean_current_direction_deg,
    ]
    if block is None:
        return base
    return [block, *base]


def write_luo_csv(path: Path, path_arcs: List[Tuple[ArcResult, int]]) -> None:
    n_segs = 0
    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(_LUO_COLUMNS)
        for arc, blk in path_arcs:
            for s in arc.segs:
                writer.writerow(_row_for_seg(s, block=blk))
                n_segs += 1
    print(f"  CSV written: {path}  ({n_segs} sub-segments, {len(path_arcs)} blocks)")


def write_baseline_csv(path: Path, segs: List[Seg]) -> None:
    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(_BASELINE_COLUMNS)
        for s in segs:
            writer.writerow(_row_for_seg(s, block=None))
    print(f"  CSV written: {path}  ({len(segs)} sub-segments)")


# ----------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(
        prog="luo_main",
        description="Luo block DP + baseline — Python port of dp_luo",
    )
    ap.add_argument("--yaml", default="route.yaml")
    ap.add_argument("--h5", default="voyage_weather.h5")
    ap.add_argument("--eta", type=float, default=None)
    ap.add_argument("--min_speed", type=float, default=None)
    ap.add_argument("--max_speed", type=float, default=None)
    ap.add_argument("--res_nm", type=float, default=1.0,
                    help="Distance grid resolution in NM (default 1.0, range [0.1, 10])")
    ap.add_argument("--baseline", action="store_true",
                    help="Compute fixed mean-SOG baseline (no graph)")
    ap.add_argument("--csv", action="store_true",
                    help="Write output CSV(s) — luo_dp.csv or baseline.csv")
    return ap.parse_args()


def main() -> int:
    args = parse_args()

    if args.res_nm < 0.1 or args.res_nm > 10.0:
        print(f"Error: --res_nm must be in [0.1, 10.0], got {args.res_nm}",
              file=sys.stderr)
        return 1

    yaml_path = Path(args.yaml)
    h5_path = Path(args.h5)
    if not yaml_path.exists():
        print(f"YAML not found: {yaml_path}", file=sys.stderr)
        return 1
    if not h5_path.exists():
        print(f"HDF5 not found: {h5_path}", file=sys.stderr)
        return 1

    route = synthesize_multi_window(load_yaml_route(yaml_path), window_h=6.0)
    voyage = VoyageWeather(h5_path)

    cfg = GraphConfig.from_route(route)
    if args.eta is not None:
        cfg.eta_h = args.eta
        if route.windows:
            route.windows[-1].end = float(args.eta)
            route = synthesize_multi_window(route, window_h=6.0)
    mean_sog = cfg.length_nm / cfg.eta_h
    cfg.v_min = args.min_speed if args.min_speed is not None else (mean_sog - 3.0)
    cfg.v_max = args.max_speed if args.max_speed is not None else (mean_sog + 3.0)

    frame = make_frame(route, voyage, WAYPOINTS, cfg=cfg)
    res_nm = args.res_nm

    # ---- Grid parameters --------------------------------------------------
    L_scaled = int(round(cfg.length_nm / res_nm))
    L_snapped = L_scaled * res_nm
    T_steps = int(cfg.eta_h / cfg.dt_h)
    T_max_h = T_steps * cfg.dt_h
    dt_last = cfg.eta_h - T_max_h
    has_eta = dt_last > 1e-9

    step_min = int(math.ceil(cfg.v_min * cfg.dt_h / res_nm))
    step_max = int(math.floor(cfg.v_max * cfg.dt_h / res_nm))
    step_min_eta = int(math.ceil(cfg.v_min * dt_last / res_nm)) if has_eta else 0
    step_max_eta = int(math.floor(cfg.v_max * dt_last / res_nm)) if has_eta else 0

    print("=" * 60)
    print(f"Luo DP  ({res_nm:.2f} nm grid resolution)")
    print("=" * 60)
    print(f"Route:      {cfg.length_nm:.2f} nm  →  L_scaled = {L_scaled}  "
          f"({L_snapped:.2f} nm)")
    print(f"Speed:      [{cfg.v_min:.1f}, {cfg.v_max:.1f}] kn")
    print(f"Regular:    {T_steps} blocks × {cfg.dt_h:.0f} h, "
          f"step [{step_min}, {step_max}] idx  "
          f"([{step_min * res_nm:.2f}, {step_max * res_nm:.2f}] nm)")
    if has_eta:
        print(f"ETA block:  1 × {dt_last:.1f} h (t={T_max_h:.0f}→{cfg.eta_h:.0f}), "
              f"step [{step_min_eta}, {step_max_eta}] idx")
    else:
        print(f"ETA = {cfg.eta_h:.0f} h is a multiple of {cfg.dt_h:.0f} h — no partial block")
    print(f"H-lines:    {len(frame.h_line_distances)} boundaries")

    # ---- Sub-segment boundaries (sorted, deduplicated, physical NM) ------
    bounds = list(frame.h_line_distances)
    bounds.append(0.0)
    bounds.append(cfg.length_nm)
    bounds.sort()
    # Dedupe to within 1e-9
    deduped: List[float] = []
    for b in bounds:
        if not deduped or abs(b - deduped[-1]) >= 1e-9:
            deduped.append(b)
    bounds = deduped

    # ---- Baseline mode ----------------------------------------------------
    if args.baseline:
        print("=" * 60)
        print("Baseline (fixed mean SOG)")
        print("=" * 60)
        print(f"Route:      {cfg.length_nm:.2f} nm  ETA: {cfg.eta_h:.1f} h")
        print(f"Mean SOG:   {mean_sog:.4f} kn")
        print(f"Boundaries: {len(bounds) - 1} sub-segments")

        segs = eval_baseline(frame, bounds)
        total_fuel = sum(s.fuel_mt for s in segs)
        print(f"Total fuel: {total_fuel:.3f} mt")

        if args.csv:
            write_baseline_csv(Path("baseline.csv"), segs)
        return 0

    # ---- For Luo DP, replace the L endpoint with L_snapped if they differ -
    bounds = [b for b in bounds
              if not (abs(b - cfg.length_nm) < 1e-9
                      and abs(b - L_snapped) > 1e-9)]
    if not bounds or abs(bounds[-1] - L_snapped) > 1e-9:
        bounds.append(L_snapped)
    bounds.sort()

    # ---- DP arrays --------------------------------------------------------
    last_col = T_steps + (1 if has_eta else 0)
    INF = float("inf")
    dp = [INF] * (L_scaled + 1)
    parent = [[-1] * (L_scaled + 1) for _ in range(last_col + 1)]

    col_t = [k * cfg.dt_h for k in range(T_steps + 1)]
    if has_eta:
        col_t.append(cfg.eta_h)

    dp[0] = 0.0
    best_fuel = INF
    best_col = -1

    t_start = time.time()

    # ---- Regular blocks ---------------------------------------------------
    for blk in range(T_steps):
        t_h = col_t[blk]
        ndp = [INF] * (L_scaled + 1)
        for d1 in range(L_scaled):
            if dp[d1] == INF:
                continue
            d2_lo = min(d1 + step_min, L_scaled)
            d2_hi = min(d1 + step_max, L_scaled)
            for d2 in range(d2_lo, d2_hi + 1):
                arc = eval_arc(d1, d2, t_h, cfg.dt_h, bounds, frame, res_nm)
                if not arc.ok:
                    continue
                nc = dp[d1] + arc.fuel
                if nc < ndp[d2]:
                    ndp[d2] = nc
                    parent[blk + 1][d2] = d1
        dp = ndp
        if dp[L_scaled] < best_fuel:
            best_fuel = dp[L_scaled]
            best_col = blk + 1

    # ---- Partial ETA block ------------------------------------------------
    if has_eta:
        t_h = T_max_h
        ndp = [INF] * (L_scaled + 1)
        for d1 in range(L_scaled):
            if dp[d1] == INF:
                continue
            d2_lo = min(d1 + step_min_eta, L_scaled)
            d2_hi = min(d1 + step_max_eta, L_scaled)
            for d2 in range(d2_lo, d2_hi + 1):
                arc = eval_arc(d1, d2, t_h, dt_last, bounds, frame, res_nm)
                if not arc.ok:
                    continue
                nc = dp[d1] + arc.fuel
                if nc < ndp[d2]:
                    ndp[d2] = nc
                    parent[last_col][d2] = d1
        dp = ndp
        if dp[L_scaled] < best_fuel:
            best_fuel = dp[L_scaled]
            best_col = last_col

    solve_s = time.time() - t_start

    if best_col < 0:
        print("No feasible path to destination found.", file=sys.stderr)
        return 1

    print("=" * 60)
    print(f"Total fuel:  {best_fuel:.3f} mt")
    print(f"Voyage time: {col_t[best_col]:.1f} h  ({best_col} blocks)")
    print(f"Solve time:  {solve_s:.2f} s")
    print("=" * 60)

    # ---- Backtrack optimal path ------------------------------------------
    path_d = [0] * (best_col + 1)
    path_d[best_col] = L_scaled
    for k in range(best_col, 0, -1):
        path_d[k - 1] = parent[k][path_d[k]]

    # ---- CSV --------------------------------------------------------------
    if args.csv:
        path_arcs: List[Tuple[ArcResult, int]] = []
        for k in range(best_col):
            dur = col_t[k + 1] - col_t[k]
            arc = eval_arc(path_d[k], path_d[k + 1], col_t[k], dur,
                           bounds, frame, res_nm)
            path_arcs.append((arc, k))
        write_luo_csv(Path("luo_dp.csv"), path_arcs)

    return 0


if __name__ == "__main__":
    sys.exit(main())

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
from bisect import bisect_right
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
from route import load_route_auto, synthesize_multi_window
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
    sample_hour: Optional[int] = None,
    forecast_hour: Optional[int] = None,
    time_key=None,
) -> ArcResult:
    """Evaluate one block arc (d1_idx → d2_idx) departing at t_h.

    SOG is constant within the block at ``(d2-d1)*res_nm / block_dur_h``.
    Each spatial sub-segment (delimited by H-line bounds) is further split at
    every ``sample_hour`` transition so each temporal piece is priced against
    the weather active at that absolute voyage time. Trip start is anchored to
    ``sh_base = voyage.sample_hours[0]``; absolute voyage time t maps to the
    largest ``sample_hour ≤ (sh_base + ⌊t⌋)`` via ``active_sample_hour``.

    ``sample_hour=None`` (default) → time-varying. Pass an ``int`` to force
    legacy static-deterministic mode (all pieces read the same sample_hour).
    On a NaN read in time-varying mode, walks back through ``sh_list`` to the
    most recent valid sample at the same cell; drops the arc if walkback fails.

    ``time_key``: optional ``Callable[[float], tuple[int, int | None]]`` used by
    the rolling-horizon orchestrator. When supplied it OVERRIDES sample_hour /
    forecast_hour resolution per temporal piece: piece-start voyage time maps to
    ``(sample_hour, forecast_hour)`` (None forecast_hour → actual, int →
    predicted at that lead). Takes precedence over ``sample_hour``; default
    ``None`` preserves the time-varying-actual behaviour above.

    Mirrors C++ luo_main.cpp eval_arc (commit 752ae0b).
    """
    r = ArcResult()
    d1 = d1_idx * res_nm
    d2 = d2_idx * res_nm
    sog = (d2 - d1) / block_dur_h

    sh_list = frame.voyage.sample_hours
    if not sh_list:
        return r
    # Voyage-start anchor: frame.base_sample_hour overrides sh_list[0] for the
    # departure-time sweep. 0 (default) → sh_list[0], preserving legacy behaviour.
    sh_base = frame.base_sample_hour if frame.base_sample_hour else sh_list[0]

    # Spatial sub-segment breakpoints (H-line bounds strictly inside (d1, d2)).
    pts: List[float] = [d1]
    for b in bounds:
        if b > d1 + 1e-9 and b < d2 - 1e-9:
            pts.append(b)
    pts.append(d2)

    for i in range(len(pts) - 1):
        sd = pts[i]
        ed = pts[i + 1]
        heading = frame.paper_heading_at(sd)

        # Voyage time at the spatial sub-segment endpoints
        t_sd = t_h + (sd - d1) / sog
        t_ed = t_h + (ed - d1) / sog

        # Temporal breakpoints: each sample_hour transition (other than sh_base)
        # strictly inside (t_sd, t_ed), mapped to voyage time t = sh_v - sh_base
        t_pts: List[float] = [t_sd]
        for sh_v in sh_list:
            if sh_v == sh_base:
                continue
            t_b = float(sh_v - sh_base)
            if t_b > t_sd + 1e-9 and t_b < t_ed - 1e-9:
                t_pts.append(t_b)
            if t_b >= t_ed:
                break
        t_pts.append(t_ed)

        for k in range(len(t_pts) - 1):
            ta = t_pts[k]
            tb = t_pts[k + 1]
            dur = tb - ta
            if dur <= 1e-12:
                continue

            cur_fh = forecast_hour
            if time_key is not None:
                cur_sh, cur_fh = time_key(ta)
            elif sample_hour is None:
                cur_sh = frame.voyage.active_sample_hour(ta, sh_base=sh_base)
            else:
                cur_sh = sample_hour

            da = sd + (ta - t_sd) * sog
            db = sd + (tb - t_sd) * sog

            wx = frame.cell_weather_at(da, sample_hour=cur_sh,
                                       forecast_hour=cur_fh)
            if wx.has_nan() and (sample_hour is None or time_key is not None):
                idx = bisect_right(sh_list, cur_sh) - 1
                while idx > 0 and wx.has_nan():
                    idx -= 1
                    wx = frame.cell_weather_at(da, sample_hour=sh_list[idx],
                                               forecast_hour=cur_fh)
                    if not wx.has_nan():
                        cur_sh = sh_list[idx]
                        break
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
            fuel = fcr * dur
            if math.isnan(fuel):
                return r

            r.segs.append(Seg(
                src_d=da, dst_d=db, src_t=ta, sog=sog,
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
    sample_hour: Optional[int] = None,
    forecast_hour: Optional[int] = None,
    time_key=None,
) -> List[Seg]:
    """Fixed mean-SOG baseline with time-varying weather.

    SOG = L / ETA constant for the entire voyage. Trip starts at t=0 anchored
    to ``sh_base = voyage.sample_hours[0]``; each spatial sub-segment is split
    at every ``sample_hour`` transition so each temporal piece is evaluated
    against the weather active at that absolute time. NaN-weather pieces are
    skipped after walkback fails (warned to stderr).

    ``sample_hour=None`` (default) → time-varying. Pass an ``int`` for legacy
    static-deterministic mode. Mirrors C++ luo_main.cpp eval_baseline (752ae0b).
    """
    sog = frame.cfg.length_nm / frame.cfg.eta_h
    segs: List[Seg] = []
    L = frame.cfg.length_nm

    sh_list = frame.voyage.sample_hours
    if not sh_list:
        return segs
    sh_base = frame.base_sample_hour if frame.base_sample_hour else sh_list[0]

    for i in range(len(bounds) - 1):
        sd = bounds[i]
        ed = bounds[i + 1]
        if ed > L + 1e-9:
            ed = L
        if ed <= sd + 1e-9:
            continue

        heading = frame.paper_heading_at(sd)

        # Voyage time at endpoints (trip starts at t=0)
        t_sd = sd / sog
        t_ed = ed / sog

        # Temporal breakpoints
        t_pts: List[float] = [t_sd]
        for sh_v in sh_list:
            if sh_v == sh_base:
                continue
            t_b = float(sh_v - sh_base)
            if t_b > t_sd + 1e-9 and t_b < t_ed - 1e-9:
                t_pts.append(t_b)
            if t_b >= t_ed:
                break
        t_pts.append(t_ed)

        for k in range(len(t_pts) - 1):
            ta = t_pts[k]
            tb = t_pts[k + 1]
            dur = tb - ta
            if dur <= 1e-12:
                continue

            cur_fh = forecast_hour
            if time_key is not None:
                cur_sh, cur_fh = time_key(ta)
            elif sample_hour is None:
                cur_sh = frame.voyage.active_sample_hour(ta, sh_base=sh_base)
            else:
                cur_sh = sample_hour

            da = sd + (ta - t_sd) * sog
            db = sd + (tb - t_sd) * sog

            wx = frame.cell_weather_at(da, sample_hour=cur_sh,
                                       forecast_hour=cur_fh)
            if wx.has_nan() and (sample_hour is None or time_key is not None):
                idx = bisect_right(sh_list, cur_sh) - 1
                while idx > 0 and wx.has_nan():
                    idx -= 1
                    wx = frame.cell_weather_at(da, sample_hour=sh_list[idx],
                                               forecast_hour=cur_fh)
                    if not wx.has_nan():
                        cur_sh = sh_list[idx]
                        break
            if wx.has_nan():
                print(f"  NaN weather at d={da:.1f} nm, sh={cur_sh} — piece skipped",
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
            fuel = fcr * dur
            segs.append(Seg(
                src_d=da, dst_d=db, src_t=ta, sog=sog,
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


def _row_for_seg(s: Seg, waypoints, block: Optional[int] = None) -> list:
    lat, lon, _seg = position_at_d(s.src_d, waypoints)
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


def write_luo_csv(path: Path, path_arcs: List[Tuple[ArcResult, int]],
                  waypoints) -> None:
    n_segs = 0
    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(_LUO_COLUMNS)
        for arc, blk in path_arcs:
            for s in arc.segs:
                writer.writerow(_row_for_seg(s, waypoints, block=blk))
                n_segs += 1
    print(f"  CSV written: {path}  ({n_segs} sub-segments, {len(path_arcs)} blocks)")


def write_baseline_csv(path: Path, segs: List[Seg], waypoints) -> None:
    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(_BASELINE_COLUMNS)
        for s in segs:
            writer.writerow(_row_for_seg(s, waypoints, block=None))
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
    ap.add_argument("--sample_hour", type=int, default=0,
                    help="Voyage-start sample_hour anchor for the departure-time "
                         "sweep. 0 (default) = use sh_list[0] (legacy). >0 = anchor "
                         "the time-varying weather lookup at this sample_hour.")
    ap.add_argument("--baseline", action="store_true",
                    help="Compute fixed mean-SOG baseline (no graph)")
    ap.add_argument("--csv", action="store_true",
                    help="Write output CSV(s) — luo_dp.csv or baseline.csv")
    return ap.parse_args()


def solve(args: argparse.Namespace, voyage: Optional[VoyageWeather] = None,
          verbose: bool = True, time_key=None, d_start: float = 0.0) -> dict:
    """Run dp_luo with the given args and return a result dict.

    The ``voyage`` arg lets callers (e.g. the chain-sweep orchestrator) load
    ``VoyageWeather`` once and reuse it across many solve() calls on the same
    HDF5 file. Pass ``None`` to load on demand.

    ``time_key`` / ``d_start``: rolling-horizon hooks. ``time_key`` selects
    mixed nowcast/forecast weather keyed on sub-voyage time (see ``eval_arc``);
    ``d_start`` is the absolute distance (nm) the sub-voyage begins at — the DP
    is seeded at ``round(d_start / res_nm)`` instead of 0 and the speed band is
    centred on the REMAINING mean SOG ``(L - d_start) / eta``. Distances stay
    ABSOLUTE so weather/geo lookups remain geographically correct.

    Returns:
        dict with keys total_fuel_mt, voyage_time_h, n_blocks, solve_s,
        path_arcs, waypoints, eta_h, sample_hour, d_start, baseline_segs (None
        unless args.baseline=True).
    """
    if args.res_nm < 0.1 or args.res_nm > 10.0:
        raise ValueError(f"--res_nm must be in [0.1, 10.0], got {args.res_nm}")

    yaml_path = Path(args.yaml)
    h5_path = Path(args.h5)
    if not yaml_path.exists():
        raise FileNotFoundError(f"YAML not found: {yaml_path}")
    if not h5_path.exists():
        raise FileNotFoundError(f"HDF5 not found: {h5_path}")

    route, waypoints = load_route_auto(yaml_path, eta_h=args.eta)
    route = synthesize_multi_window(route, window_h=6.0)
    if voyage is None:
        voyage = VoyageWeather(h5_path)

    cfg = GraphConfig.from_route(route)
    if args.eta is not None:
        cfg.eta_h = args.eta
        if route.windows:
            route.windows[-1].end = float(args.eta)
            route = synthesize_multi_window(route, window_h=6.0)
    mean_sog = (cfg.length_nm - d_start) / cfg.eta_h
    cfg.v_min = args.min_speed if args.min_speed is not None else (mean_sog - 3.0)
    cfg.v_max = args.max_speed if args.max_speed is not None else (mean_sog + 3.0)

    sample_hour = int(getattr(args, "sample_hour", 0) or 0)
    frame = make_frame(route, voyage, waypoints, cfg=cfg,
                       base_sample_hour=sample_hour)
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

    if verbose:
        print("=" * 60)
        print(f"Luo DP  ({res_nm:.2f} nm grid resolution)")
        print("=" * 60)
        print(f"Route:      {cfg.length_nm:.2f} nm  →  L_scaled = {L_scaled}  "
              f"({L_snapped:.2f} nm)")
        print(f"Speed:      [{cfg.v_min:.3f}, {cfg.v_max:.3f}] kn")
        print(f"Regular:    {T_steps} blocks × {cfg.dt_h:.0f} h")
        if has_eta:
            print(f"ETA block:  1 × {dt_last:.1f} h")
        print(f"sh_base:    {sample_hour}  "
              f"(0 = sh_list[0]={voyage.sample_hours[0] if voyage.sample_hours else 'n/a'})")

    # ---- Sub-segment boundaries (sorted, deduplicated, physical NM) ------
    bounds = list(frame.h_line_distances)
    bounds.append(0.0)
    bounds.append(cfg.length_nm)
    bounds.sort()
    deduped: List[float] = []
    for b in bounds:
        if not deduped or abs(b - deduped[-1]) >= 1e-9:
            deduped.append(b)
    bounds = deduped

    # ---- Baseline mode ----------------------------------------------------
    if args.baseline:
        if verbose:
            print("=" * 60)
            print(f"Baseline (fixed mean SOG = {mean_sog:.4f} kn)")
        segs = eval_baseline(frame, bounds)
        total_fuel = sum(s.fuel_mt for s in segs)
        if verbose:
            print(f"Total fuel: {total_fuel:.3f} mt")
        return {
            "total_fuel_mt": total_fuel,
            "voyage_time_h": cfg.eta_h,
            "n_blocks": None,
            "solve_s": 0.0,
            "path_arcs": [],
            "baseline_segs": segs,
            "waypoints": waypoints,
            "eta_h": cfg.eta_h,
            "sample_hour": sample_hour,
            "d_start": d_start,
        }

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

    # Seed the DP at the (sub-)voyage start. d_start=0 → route origin (legacy).
    d_start_idx = int(round(d_start / res_nm))
    dp[d_start_idx] = 0.0
    best_fuel = INF
    best_col = -1

    t_start = time.time()

    for blk in range(T_steps):
        t_h = col_t[blk]
        ndp = [INF] * (L_scaled + 1)
        for d1 in range(L_scaled):
            if dp[d1] == INF:
                continue
            d2_lo = min(d1 + step_min, L_scaled)
            d2_hi = min(d1 + step_max, L_scaled)
            for d2 in range(d2_lo, d2_hi + 1):
                arc = eval_arc(d1, d2, t_h, cfg.dt_h, bounds, frame, res_nm,
                               time_key=time_key)
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

    if has_eta:
        t_h = T_max_h
        ndp = [INF] * (L_scaled + 1)
        for d1 in range(L_scaled):
            if dp[d1] == INF:
                continue
            d2_lo = min(d1 + step_min_eta, L_scaled)
            d2_hi = min(d1 + step_max_eta, L_scaled)
            for d2 in range(d2_lo, d2_hi + 1):
                arc = eval_arc(d1, d2, t_h, dt_last, bounds, frame, res_nm,
                               time_key=time_key)
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

    solve_s_dur = time.time() - t_start

    if best_col < 0:
        raise RuntimeError("Luo DP: no feasible path to destination found.")

    if verbose:
        print("=" * 60)
        print(f"Total fuel:  {best_fuel:.3f} mt")
        print(f"Voyage time: {col_t[best_col]:.1f} h  ({best_col} blocks)")
        print(f"Solve time:  {solve_s_dur:.2f} s")
        print("=" * 60)

    # Backtrack optimal path + reconstruct per-block arcs for CSV
    path_d = [0] * (best_col + 1)
    path_d[best_col] = L_scaled
    for k in range(best_col, 0, -1):
        path_d[k - 1] = parent[k][path_d[k]]

    path_arcs: List[Tuple[ArcResult, int]] = []
    for k in range(best_col):
        dur = col_t[k + 1] - col_t[k]
        arc = eval_arc(path_d[k], path_d[k + 1], col_t[k], dur,
                       bounds, frame, res_nm, time_key=time_key)
        path_arcs.append((arc, k))

    return {
        "total_fuel_mt": best_fuel,
        "voyage_time_h": col_t[best_col],
        "n_blocks": best_col,
        "solve_s": solve_s_dur,
        "path_arcs": path_arcs,
        "baseline_segs": None,
        "waypoints": waypoints,
        "eta_h": cfg.eta_h,
        "sample_hour": sample_hour,
        "d_start": d_start,
    }


def main() -> int:
    args = parse_args()
    try:
        result = solve(args)
    except (ValueError, FileNotFoundError, RuntimeError) as e:
        print(str(e), file=sys.stderr)
        return 1
    if args.csv:
        if result["baseline_segs"] is not None:
            write_baseline_csv(Path("baseline.csv"), result["baseline_segs"],
                               result["waypoints"])
        else:
            write_luo_csv(Path("luo_dp.csv"), result["path_arcs"],
                          result["waypoints"])
    return 0


if __name__ == "__main__":
    sys.exit(main())

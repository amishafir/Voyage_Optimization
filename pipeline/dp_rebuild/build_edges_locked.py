"""
Locked-mode edge builder — Luo-2024-style **SOG-targeting** policy.

The captain picks a *target SOG* (ground speed) at every V-line boundary
and holds it constant for the next 6h block. As the ship crosses cell or
segment boundaries inside the block, the engine SWS adjusts (per sub-leg
inverse physics) so the actual SOG keeps matching the target. Block fuel
is the integral of FCR(SWS_i) × Δt_i over the sub-legs.

Compared to the earlier SWS-locking version, this is operationally more
realistic and structurally simpler:

  * decision = target SOG (held constant)
  * destination = d_src + target_SOG × 6h  (geometric — no inverse search)
  * SWS varies per sub-leg, fuel is the sum FCR(SWS_i) × Δt_i

Reuses the free-DP node set unchanged. Same-node invariant (every edge
endpoint coincides with a free-DP node) is enforced by a closing
assertion. `LockedEdge` field names match `build_edges.Edge` so that
`BellmanSolver` works on locked edges without modification.
"""

from __future__ import annotations

import sys
from bisect import bisect_right
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

# Make `pipeline/shared/physics.py` importable regardless of CWD.
_PIPELINE_ROOT = Path(__file__).resolve().parent.parent
if str(_PIPELINE_ROOT) not in sys.path:
    sys.path.insert(0, str(_PIPELINE_ROOT))
from shared.physics import (  # noqa: E402
    calculate_fuel_consumption_rate,
    calculate_sws_from_sog,
)

from build_edges import Weather, index_nodes
from build_nodes import GraphConfig, Node, v_line_times_from_route
from h5_weather import VoyageWeather
from load_route import Route


# ----------------------------------------------------------------------
# LockedEdge — Bellman-compatible (same field names as Edge)
# ----------------------------------------------------------------------

@dataclass(frozen=True)
class LockedEdge:
    src_t: float
    src_d: float
    dst_t: float
    dst_d: float
    sog: float            # CONSTANT target SOG over the block (the decision)
    weather: Weather      # source-block weather (representative; varies sub-leg)
    heading_deg: float    # source-block heading (representative; can change sub-leg)
    sws: float            # time-weighted MEAN SWS over the block (varies per sub-leg)
    fcr_mt_per_h: float   # mean FCR = fuel_mt / Δt
    fuel_mt: float        # total fuel for the block (Σ FCR_i × Δt_i)
    sub_legs: int         # how many H-line crossings inside the block


# ----------------------------------------------------------------------
# Block simulation — constant target SOG, walk through H-line crossings
# ----------------------------------------------------------------------

def simulate_block_sog(
    t0: float,
    d0: float,
    target_sog: float,
    target_dst_d: float,
    route: Route,
    voyage: VoyageWeather,
    h_line_distances: List[float],
    L: float,
    waypoints,
    sample_hour: int = 0,
    forecast_hour: Optional[int] = None,
    grid_deg: float = 0.5,
    sws_max_feasible: float = 25.0,
) -> Optional[Tuple[float, float, float, int, float, float, float]]:
    """Walk a constant-SOG trajectory from (t0, d0) to (?, target_dst_d).

    SOG is held at `target_sog`. SWS varies per sub-leg (between H-lines)
    via the inverse physics: at each sub-leg's cell-canonical weather +
    paper-segment heading, find the SWS that produces `target_sog`, then
    accumulate FCR(SWS) × Δt as the fuel for that sub-leg. Δt of each
    sub-leg is geometric: Δt_i = gap_i / target_sog.

    Returns
        (final_t, final_d, total_fuel_mt, sub_legs, sws_mean, sws_max, sws_min)
    or `None` if any sub-leg's required SWS is NaN or exceeds
    `sws_max_feasible` (engine can't push hard enough to maintain SOG).
    """
    from geo_grid import position_at_d

    yaml_segments = route.windows[0].segments
    n_yaml = len(yaml_segments)
    n_h = len(h_line_distances)

    t = t0
    d = d0
    total_fuel = 0.0
    sub_legs = 0
    sws_sum_dt = 0.0
    sws_max = -1.0
    sws_min = float("inf")
    h_idx = bisect_right(h_line_distances, d)

    target_dst_d = min(target_dst_d, L)

    while d < target_dst_d - 1e-9:
        # Next H-line ahead, capped at target_dst_d (and L).
        next_h = h_line_distances[h_idx] if h_idx < n_h else L
        next_h = min(next_h, target_dst_d, L)

        gap = next_h - d
        if gap <= 1e-9:
            h_idx += 1
            continue

        # Sub-leg weather + heading at the entering position.
        _lat, _lon, seg_idx = position_at_d(d, waypoints)
        seg_clamped = max(0, min(seg_idx, n_yaml - 1))
        heading_deg = yaml_segments[seg_clamped].ship_heading
        wx = voyage.cell_weather_at_d(
            d, waypoints=waypoints,
            sample_hour=sample_hour, forecast_hour=forecast_hour,
            grid_deg=grid_deg,
        )

        # Inverse SWS that produces target_sog under (wx, heading).
        sws_i = calculate_sws_from_sog(
            target_sog=target_sog,
            weather=wx,
            ship_heading_deg=heading_deg,
            ship_parameters=None,
        )
        if sws_i != sws_i:                  # NaN
            return None
        if sws_i > sws_max_feasible:
            return None

        time_step = gap / target_sog
        fcr_i = calculate_fuel_consumption_rate(sws_i)
        fuel_i = fcr_i * time_step

        total_fuel += fuel_i
        sws_sum_dt += sws_i * time_step
        if sws_i > sws_max:
            sws_max = sws_i
        if sws_i < sws_min:
            sws_min = sws_i

        d += target_sog * time_step
        t += time_step
        sub_legs += 1

        if abs(d - next_h) < 1e-9:
            h_idx += 1

    total_dt = t - t0
    sws_mean = sws_sum_dt / total_dt if total_dt > 1e-9 else float("nan")
    return (t, d, total_fuel, sub_legs, sws_mean, sws_max, sws_min)


# ----------------------------------------------------------------------
# Locked-edge builder
# ----------------------------------------------------------------------

def build_locked_edges(
    cfg: GraphConfig,
    route: Route,
    voyage: VoyageWeather,
    h_line_distances: List[float],
    waypoints,
    nodes: List[Node],
    sample_hour: int = 0,
    forecast_hour: Optional[int] = None,
    tau_h_locked: float = 0.1,
    grid_deg: float = 0.5,
    sws_max_feasible: float = 25.0,
    early_terminal_sog_step: float = 0.1,
) -> List[LockedEdge]:
    """SOG-locking locked-mode edge builder.

    Decision variable: target SOG (held constant for one V-band, default 6h).
    SWS varies per sub-leg via inverse physics. Fuel is the integral of
    FCR(SWS_i) × Δt_i over sub-legs.

    For each V-line source `(t_k, d_src)`:

      Case A — regular V-line dst at `t_next`:
        For every V-line node `(t_next, dst_d)` in
            [d_src + v_min·dt, min(L, d_src + v_max·dt)]
        the target SOG is geometric: `(dst_d - d_src) / dt`. Simulate
        the trajectory at constant SOG; emit one edge.

      Case B — early-terminal dst at d = L:
        If `d_src + v_max·dt >= L`, some target SOGs land at `L` before
        `t_next`. Enumerate target SOGs on a `early_terminal_sog_step`
        grid in `(max(v_min, (L-d_src)/dt), v_max]`. For each, snap the
        landing time to the nearest H-line@L node time (already on the
        τ-h grid in the free-DP node set) and emit one edge.

    Same-node invariant: every produced edge endpoint coincides with a
    free-DP node. Enforced by a closing assertion.

    Edges where some sub-leg's required SWS exceeds `sws_max_feasible`
    (or is NaN) are silently dropped — the SOG is infeasible across that
    block, and Bellman simply doesn't see the option.
    """
    v_times_strict = v_line_times_from_route(cfg, route)
    v_times = [0.0] + list(v_times_strict)

    L = cfg.length_nm
    eta = cfg.eta_h
    n_yaml = len(route.windows[0].segments)

    nodes_by_v, nodes_by_h = index_nodes(nodes)
    v_dist_by_time: Dict[float, List[float]] = {
        t: [n.distance_nm for n in lst]
        for t, lst in nodes_by_v.items()
    }
    h_at_L_times: List[float] = sorted(
        n.time_h for n in nodes_by_h.get(L, []) if not n.is_source
    )
    node_key_set = {(round(n.time_h, 6), round(n.distance_nm, 6)) for n in nodes}

    reachable_at_t: Dict[float, Set[float]] = {0.0: {0.0}}
    edges: List[LockedEdge] = []

    from geo_grid import position_at_d as _pos_at_d

    for k in range(len(v_times) - 1):
        t_k = v_times[k]
        t_next = v_times[k + 1]
        dt = t_next - t_k
        if t_k not in reachable_at_t:
            continue

        sources = sorted(reachable_at_t[t_k])
        next_reachable: Set[float] = set()

        for d_src in sources:
            if abs(d_src - L) < 1e-9:
                continue  # already at sink

            # Source representative weather + heading.
            _lat_s, _lon_s, seg_src = _pos_at_d(d_src, waypoints)
            seg_src_clamped = max(0, min(seg_src, n_yaml - 1))
            heading_src = route.windows[0].segments[seg_src_clamped].ship_heading
            wx_src = Weather.from_dict(voyage.cell_weather_at_d(
                d_src, waypoints=waypoints,
                sample_hour=sample_hour, forecast_hour=forecast_hour,
                grid_deg=grid_deg,
            ))

            # ---- Case A: regular V-line dst, dt = full V-band ----
            dst_lo = d_src + cfg.v_min * dt
            dst_hi = min(L - 1e-9, d_src + cfg.v_max * dt)
            v_line_dists = v_dist_by_time.get(t_next, [])
            for dst_d in v_line_dists:
                if dst_d < dst_lo - 1e-9 or dst_d > dst_hi + 1e-9:
                    continue
                target_sog = (dst_d - d_src) / dt
                if not (cfg.v_min - 1e-9 <= target_sog <= cfg.v_max + 1e-9):
                    continue
                res = simulate_block_sog(
                    t0=t_k, d0=d_src, target_sog=target_sog,
                    target_dst_d=dst_d,
                    route=route, voyage=voyage,
                    h_line_distances=h_line_distances, L=L,
                    waypoints=waypoints,
                    sample_hour=sample_hour, forecast_hour=forecast_hour,
                    grid_deg=grid_deg,
                    sws_max_feasible=sws_max_feasible,
                )
                if res is None:
                    continue
                _final_t, _final_d, fuel, sub_legs, sws_mean, _sws_max, _sws_min = res
                fcr_eff = fuel / dt
                edges.append(LockedEdge(
                    src_t=t_k, src_d=d_src,
                    dst_t=t_next, dst_d=dst_d,
                    sog=target_sog,
                    weather=wx_src, heading_deg=heading_src,
                    sws=sws_mean, fcr_mt_per_h=fcr_eff, fuel_mt=fuel,
                    sub_legs=sub_legs,
                ))
                next_reachable.add(dst_d)

            # ---- Case B: early-terminal edges to d = L ----
            if d_src + cfg.v_max * dt >= L - 1e-9:
                sog_to_L_at_tnext = (L - d_src) / dt   # SOG landing exactly at L at t_next
                # Overshooting SOGs reach L before t_next.
                sog_lo = max(cfg.v_min, sog_to_L_at_tnext + 1e-6)
                if sog_lo <= cfg.v_max + 1e-9:
                    sog = sog_lo
                    seen_dst_t: Set[float] = set()
                    while sog <= cfg.v_max + 1e-9:
                        res = simulate_block_sog(
                            t0=t_k, d0=d_src, target_sog=sog,
                            target_dst_d=L,
                            route=route, voyage=voyage,
                            h_line_distances=h_line_distances, L=L,
                            waypoints=waypoints,
                            sample_hour=sample_hour, forecast_hour=forecast_hour,
                            grid_deg=grid_deg,
                            sws_max_feasible=sws_max_feasible,
                        )
                        if res is not None:
                            final_t, _final_d, fuel, sub_legs, sws_mean, _, _ = res
                            dst_t_raw = min(final_t, eta)
                            if h_at_L_times:
                                dst_t = min(h_at_L_times, key=lambda t: abs(t - dst_t_raw))
                            else:
                                dst_t = round(dst_t_raw / tau_h_locked) * tau_h_locked
                            elapsed = dst_t - t_k
                            if elapsed > 1e-9 and dst_t not in seen_dst_t:
                                seen_dst_t.add(dst_t)
                                fcr_eff = fuel / elapsed
                                edges.append(LockedEdge(
                                    src_t=t_k, src_d=d_src,
                                    dst_t=dst_t, dst_d=L,
                                    sog=sog,
                                    weather=wx_src, heading_deg=heading_src,
                                    sws=sws_mean, fcr_mt_per_h=fcr_eff, fuel_mt=fuel,
                                    sub_legs=sub_legs,
                                ))
                        sog += early_terminal_sog_step

        reachable_at_t.setdefault(t_next, set()).update(next_reachable)

    # Same-node invariant.
    for e in edges:
        src_key = (round(e.src_t, 6), round(e.src_d, 6))
        dst_key = (round(e.dst_t, 6), round(e.dst_d, 6))
        if src_key not in node_key_set:
            raise AssertionError(f"locked edge src {src_key} not in node set")
        if dst_key not in node_key_set:
            raise AssertionError(f"locked edge dst {dst_key} not in node set")

    return edges


# ----------------------------------------------------------------------
# Continuous-resim sanity check
# ----------------------------------------------------------------------

def verify_locked_schedule(
    schedule: List[LockedEdge],
    route: Route,
    voyage: VoyageWeather,
    h_line_distances: List[float],
    L: float,
    eta_h: float,
    waypoints,
    sample_hour: int = 0,
    forecast_hour: Optional[int] = None,
    grid_deg: float = 0.5,
) -> Dict[str, float]:
    """Resimulate the locked schedule **continuously**, starting each block
    from the previous block's continuous (t, d) end (not its snapped src).

    With SOG-locking, the trajectory is a straight line in (t, d) at
    constant `target_sog`, so continuous Δd_snap should be ~0 nm per
    block (only floating-point drift). Bellman fuel and continuous fuel
    should agree exactly.
    """
    print("=" * 78)
    print("Locked schedule sanity check — continuous resimulation (SOG-locking)")
    print("=" * 78)
    print(f"  {'k':>2} {'src(t,d) snap':>22} {'src(t,d) cont':>22}  "
          f"{'tSOG':>5} {'dt':>5}  {'dst_cont':>10}  {'Δd_snap':>9}")

    t = 0.0
    d = 0.0
    total_fuel = 0.0
    bellman_total = sum(e.fuel_mt for e in schedule)

    for k, e in enumerate(schedule):
        target_sog = e.sog
        dt = e.dst_t - e.src_t
        # Where would constant-SOG land us starting from the continuous (t, d)?
        d_geom = d + target_sog * dt
        if d_geom > L:
            d_geom = L
        res = simulate_block_sog(
            t0=t, d0=d, target_sog=target_sog,
            target_dst_d=d_geom,
            route=route, voyage=voyage,
            h_line_distances=h_line_distances, L=L,
            waypoints=waypoints,
            sample_hour=sample_hour, forecast_hour=forecast_hour,
            grid_deg=grid_deg,
        )
        if res is None:
            print(f"  Block {k}: infeasible at continuous src ({t:.3f}, {d:.4f})")
            return {}
        final_t, final_d, fuel, _, _, _, _ = res
        delta_snap = final_d - e.dst_d

        if k < 3 or k > len(schedule) - 4 or k % 10 == 0:
            print(f"  {k:>2} ({e.src_t:>5.1f},{e.src_d:>9.3f})  "
                  f"({t:>5.2f},{d:>10.5f})  "
                  f"{target_sog:>5.2f} {dt:>5.2f}  ({final_d:>9.5f})  "
                  f"{delta_snap:>+9.5f}")

        t = final_t
        d = final_d
        total_fuel += fuel

    print("-" * 78)
    print(f"  Bellman claimed ending: t = {eta_h:.3f} h,  d = {L:.3f} nm")
    print(f"  Continuous resim ending: t = {t:.3f} h,  d = {d:.5f} nm")
    print(f"  Δt = {t - eta_h:+.4f} h,  Δd = {d - L:+.5f} nm")
    print(f"  Bellman fuel:            {bellman_total:>10.5f} mt")
    print(f"  Continuous fuel:         {total_fuel:>10.5f} mt")
    print(f"  Δfuel:                   {total_fuel - bellman_total:>+10.5f} mt")
    print("=" * 78)

    return {
        "continuous_t": t,
        "continuous_d": d,
        "continuous_fuel": total_fuel,
        "bellman_fuel": bellman_total,
        "delta_d": d - L,
        "delta_t": t - eta_h,
        "delta_fuel": total_fuel - bellman_total,
    }


# ----------------------------------------------------------------------
# Quick-look summary
# ----------------------------------------------------------------------

def summarize_locked(edges: List[LockedEdge]) -> None:
    if not edges:
        print("No locked edges built.")
        return
    fuels = [e.fuel_mt for e in edges]
    sogs = [e.sog for e in edges]
    swss = [e.sws for e in edges if e.sws == e.sws]
    sub_legs = [e.sub_legs for e in edges]
    print("=" * 70)
    print(f"LockedEdge summary  ({len(edges):,} edges, SOG-locking)")
    print("=" * 70)
    print(f"  target SOG range: [{min(sogs):.3f}, {max(sogs):.3f}] kn")
    if swss:
        print(f"  mean SWS range:   [{min(swss):.3f}, {max(swss):.3f}] kn")
    print(f"  fuel/edge:        [{min(fuels):.3f}, {max(fuels):.3f}] mt  "
          f"(mean {sum(fuels)/len(fuels):.3f})")
    print(f"  sub_legs/edge:    min {min(sub_legs)}, max {max(sub_legs)}, "
          f"mean {sum(sub_legs)/len(sub_legs):.2f}")
    src_ts = sorted({e.src_t for e in edges})
    print(f"  V-bands used:     {len(src_ts)}  (first src_t={src_ts[0]}, "
          f"last src_t={src_ts[-1]})")
    print("=" * 70)

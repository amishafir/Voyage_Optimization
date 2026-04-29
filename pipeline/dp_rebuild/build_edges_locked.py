"""
Locked-mode edge builder — one constant SWS per 6h V-band block.

This is the Luo-2024-style decision policy applied to the rebuild graph:
the speed (SWS) decision happens *only* at V-line boundaries; within a
6h block, the engine setting is held constant and the ship's position
evolves through whatever weather/heading changes apply along the way.

Each `LockedEdge` corresponds to one source V-line node + one fixed SWS
choice, with the trajectory simulated forward through every H-line
crossing in the block. Field names match `build_edges.Edge` so that
`BellmanSolver` works on locked edges without modification.

Reuses the same node set as the free-DP graph — only the edge set
differs. That makes the comparison clean: any fuel difference is
attributable to the per-square vs per-block speed-decision policy.
"""

from __future__ import annotations

import math
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
    calculate_speed_over_ground,
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
    sog: float            # AVG SOG over the block = (dst_d - src_d) / (dst_t - src_t)
    weather: Weather      # source-block weather (representative; varies sub-leg)
    heading_deg: float    # source-block heading (representative; can change sub-leg)
    sws: float            # constant for the entire block
    fcr_mt_per_h: float   # 0.000706 × SWS³ (constant)
    fuel_mt: float        # total fuel for the block
    sub_legs: int         # how many H-line crossings inside the block


# ----------------------------------------------------------------------
# Forward-physics SOG helper
# ----------------------------------------------------------------------

def _forward_sog(
    sws: float,
    wx: Dict[str, float],
    heading_deg: float,
    ship_params: Optional[Dict] = None,
) -> float:
    return calculate_speed_over_ground(
        ship_speed=sws,
        ocean_current=wx["ocean_current_velocity_kmh"] / 1.852,
        current_direction=math.radians(wx["ocean_current_direction_deg"]),
        ship_heading=math.radians(heading_deg),
        wind_direction=math.radians(wx["wind_direction_10m_deg"]),
        beaufort_scale=int(wx["beaufort_number"]),
        wave_height=wx["wave_height_m"],
        ship_parameters=ship_params,
    )


# ----------------------------------------------------------------------
# Block simulation — constant SWS, walk through H-line crossings
# ----------------------------------------------------------------------

def simulate_block(
    t0: float,
    d0: float,
    sws: float,
    duration_h: float,
    route: Route,
    voyage: VoyageWeather,
    h_line_distances: List[float],
    L: float,
    waypoints,
    sample_hour: int = 0,
    forecast_hour: Optional[int] = None,
    grid_deg: float = 0.5,
) -> Optional[Tuple[float, float, float, int]]:
    """Forward-simulate `duration_h` of constant-SWS sailing from (t0, d0).

    Walks through each H-line crossing inside the block, looking up
    weather + heading at every sub-leg using the paper-waypoint geometry
    (`position_at_d` for segment + cell index, `cell_weather_at_d` for the
    per-cell mean Qg5(b) weather). Returns
        (final_t, final_d, total_fuel_mt, sub_legs_count)
    or None if the simulation hits a degenerate state (SOG ≤ 0 or NaN).

    If the ship reaches d=L before duration_h elapses, the simulation
    terminates early and final_t < t0 + duration_h.
    """
    from geo_grid import position_at_d

    fcr = calculate_fuel_consumption_rate(sws)
    yaml_segments = route.windows[0].segments
    n_yaml = len(yaml_segments)
    n_h = len(h_line_distances)

    t = t0
    d = d0
    remaining = duration_h
    total_fuel = 0.0
    sub_legs = 0
    h_idx = bisect_right(h_line_distances, d)

    while remaining > 1e-9 and d < L - 1e-9:
        # Next H-line ahead, clamped to the route end.
        next_h = h_line_distances[h_idx] if h_idx < n_h else L
        if next_h > L:
            next_h = L

        # Weather + heading at the ship's current position (paper-waypoint
        # segment, per-cell mean weather — same policy as the free-DP edge
        # builder via lookup_source_state).
        _lat, _lon, seg_idx = position_at_d(d, waypoints)
        seg_clamped = max(0, min(seg_idx, n_yaml - 1))
        heading_deg = yaml_segments[seg_clamped].ship_heading
        wx = voyage.cell_weather_at_d(
            d, waypoints=waypoints,
            sample_hour=sample_hour, forecast_hour=forecast_hour,
            grid_deg=grid_deg,
        )

        sog = _forward_sog(sws, wx, heading_deg)
        if not (sog > 1e-6) or sog != sog:  # also catches NaN
            return None

        gap = next_h - d
        if gap <= 1e-9:
            # We sit exactly on an H-line; advance the H-line index.
            h_idx += 1
            continue

        time_to_h = gap / sog
        time_step = min(time_to_h, remaining)
        d_new = d + sog * time_step
        if d_new > L + 1e-6:
            d_new = L
            time_step = (d_new - d) / sog

        total_fuel += fcr * time_step
        t += time_step
        d = d_new
        remaining -= time_step
        sub_legs += 1

        if abs(d - next_h) < 1e-9:
            h_idx += 1

    return (t, d, total_fuel, sub_legs)


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
    sws_search_min: float = 4.0,
    sws_search_max: float = 22.0,
    cache_sws_step: float = 0.5,
    tolerance_nm: float = 0.01,
    max_refine_iter: int = 30,
    grid_deg: float = 0.5,
) -> List[LockedEdge]:
    """Inverse-integration locked-mode edge builder.

    For every (V-line source, V-line destination at `t_next`) pair,
    **binary-search the SWS** so that `simulate_block(SWS)` ends exactly
    at the destination (within `tolerance_nm`). This eliminates the
    snap-drift bias that the earlier forward-enumeration version had:
    every edge's continuous trajectory now matches its declared
    destination.

    Same-node invariant
    -------------------
    Destinations are taken **directly from the free-DP V-line node set**:
    `nodes_by_v[t_next]` filtered to the reachable distance window
    `[d_src + v_min·dt, d_src + v_max·dt]`. When the ship reaches `d = L`
    before `t_next`, the destination is the H-line@L node whose time is
    `final_t` rounded to the `tau_h_locked` grid (also already in the
    free-DP node set since H-line@L has nodes at every τ-grid cell).
    A final assertion confirms every produced edge's `(src_t, src_d)`
    and `(dst_t, dst_d)` exist as nodes in `nodes`.

    Per source we first build a coarse `(SWS, final_d)` cache at
    `cache_sws_step` step, then bracket each candidate dst_d in the
    cache and refine with binary search.

    Same-logic filter as free-DP: edge accepted iff
    `avg_SOG = Δd/Δt ∈ [v_min, v_max]`. SWS itself is unbounded (matches
    `calculate_sws_from_sog` in free mode).
    """
    v_times_strict = v_line_times_from_route(cfg, route)
    v_times = [0.0] + list(v_times_strict)

    L = cfg.length_nm
    eta = cfg.eta_h
    n_yaml = len(route.windows[0].segments)

    # --- Same-node enumeration: pull dst candidates from free-DP node set ----
    nodes_by_v, nodes_by_h = index_nodes(nodes)
    # Pre-extract sorted distance arrays per V-time for fast range lookup.
    v_dist_by_time: Dict[float, List[float]] = {
        t: [n.distance_nm for n in lst]  # already sorted by index_nodes
        for t, lst in nodes_by_v.items()
    }
    # H-line@L node times (for early-terminal dst snapping).
    h_at_L_times: List[float] = sorted(
        n.time_h for n in nodes_by_h.get(L, []) if not n.is_source
    )
    # Whole-graph node-key set for the closing invariant assertion.
    node_key_set = {(round(n.time_h, 6), round(n.distance_nm, 6)) for n in nodes}

    reachable_at_t: Dict[float, Set[float]] = {0.0: {0.0}}
    edges: List[LockedEdge] = []

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

            # Representative source weather + heading (for the LockedEdge record).
            # Paper-waypoint geometry + cell-canonical weather (Qg5(b)).
            from geo_grid import position_at_d as _pos_at_d
            _lat_s, _lon_s, seg_src = _pos_at_d(d_src, waypoints)
            seg_src_clamped = max(0, min(seg_src, n_yaml - 1))
            heading_src = route.windows[0].segments[seg_src_clamped].ship_heading
            wx_src_dict = voyage.cell_weather_at_d(
                d_src, waypoints=waypoints,
                sample_hour=sample_hour, forecast_hour=forecast_hour,
                grid_deg=grid_deg,
            )
            wx_src = Weather.from_dict(wx_src_dict)

            # ---- 1) Build coarse (SWS, final_d) cache for this source ----
            cache: List[Tuple[float, float]] = []
            sws = sws_search_min
            while sws <= sws_search_max + 1e-9:
                result = simulate_block(
                    t0=t_k, d0=d_src, sws=sws, duration_h=dt,
                    route=route, voyage=voyage,
                    h_line_distances=h_line_distances, L=L,
                    waypoints=waypoints,
                    sample_hour=sample_hour, forecast_hour=forecast_hour,
                    grid_deg=grid_deg,
                )
                if result is not None:
                    cache.append((round(sws, 6), result[1]))
                sws += cache_sws_step
            if len(cache) < 2:
                continue
            cache.sort()
            min_reach = cache[0][1]
            max_reach = cache[-1][1]

            # ---- 2) Enumerate dst targets directly from free-DP V-line nodes ----
            # Same-node invariant: every dst is a real node in the free-DP graph.
            dst_min_geom = d_src + cfg.v_min * dt
            dst_max_geom = min(L, d_src + cfg.v_max * dt)
            dst_lo_eff = max(dst_min_geom, min_reach)
            dst_hi_eff = min(dst_max_geom, max_reach)

            v_line_dists = v_dist_by_time.get(t_next, [])
            # Linear scan is fine — the list is short (~3393 entries) and we
            # need every match anyway. bisect would be a marginal win.
            dst_targets: List[float] = [
                d for d in v_line_dists
                if dst_lo_eff - 1e-9 <= d <= dst_hi_eff + 1e-9
            ]

            # ---- 3) Per dst target, inverse-solve SWS via bracket+binary search ----
            for dst_d in dst_targets:
                # Find bracket in cache: cache[i].final_d <= dst_d <= cache[i+1].final_d
                lo_sws = hi_sws = None
                lo_d = hi_d = None
                for i in range(len(cache) - 1):
                    if cache[i][1] <= dst_d <= cache[i + 1][1]:
                        lo_sws, lo_d = cache[i]
                        hi_sws, hi_d = cache[i + 1]
                        break
                if lo_sws is None:
                    continue

                # Binary search refinement
                sws_solved = None
                final_d_solved = None
                sub_legs_solved = 0
                final_t_solved = t_next
                for _ in range(max_refine_iter):
                    mid_sws = 0.5 * (lo_sws + hi_sws)
                    result = simulate_block(
                        t0=t_k, d0=d_src, sws=mid_sws, duration_h=dt,
                        route=route, voyage=voyage,
                        h_line_distances=h_line_distances, L=L,
                        waypoints=waypoints,
                        sample_hour=sample_hour, forecast_hour=forecast_hour,
                        grid_deg=grid_deg,
                    )
                    if result is None:
                        break
                    final_t_mid, final_d_mid, _, sub_legs_mid = result
                    if abs(final_d_mid - dst_d) < tolerance_nm:
                        sws_solved = mid_sws
                        final_d_solved = final_d_mid
                        sub_legs_solved = sub_legs_mid
                        final_t_solved = final_t_mid
                        break
                    if final_d_mid < dst_d:
                        lo_sws, lo_d = mid_sws, final_d_mid
                    else:
                        hi_sws, hi_d = mid_sws, final_d_mid
                    if abs(hi_sws - lo_sws) < 1e-6:
                        sws_solved = mid_sws
                        final_d_solved = final_d_mid
                        sub_legs_solved = sub_legs_mid
                        final_t_solved = final_t_mid
                        break

                if sws_solved is None:
                    continue
                # Reject edges where the inverse didn't actually hit the target.
                if abs(final_d_solved - dst_d) > tolerance_nm * 10:
                    continue

                # Determine dst_t. If ship reached L early, simulator returns
                # final_t < dt; otherwise the block ran the full duration.
                hit_terminal = abs(final_d_solved - L) < 1e-6 and final_t_solved < t_next - 1e-6
                if hit_terminal:
                    # Snap to a real H-line@L node time (the τ-grid cells
                    # already in the free-DP node set), so dst is on a node.
                    dst_t_raw = min(final_t_solved, eta)
                    if h_at_L_times:
                        dst_t = min(h_at_L_times, key=lambda t: abs(t - dst_t_raw))
                    else:
                        dst_t = round(dst_t_raw / tau_h_locked) * tau_h_locked
                    elapsed = dst_t - t_k                 # block duration actually used (snapped)
                    fuel = 0.000706 * sws_solved ** 3 * elapsed
                else:
                    dst_t = t_next
                    fuel = 0.000706 * sws_solved ** 3 * dt

                if dst_t <= t_k + 1e-9:
                    continue

                avg_sog = (dst_d - d_src) / (dst_t - t_k)
                if not (cfg.v_min - 1e-6 <= avg_sog <= cfg.v_max + 1e-6):
                    continue

                fcr = 0.000706 * sws_solved ** 3

                edges.append(LockedEdge(
                    src_t=t_k, src_d=d_src,
                    dst_t=dst_t, dst_d=dst_d,
                    sog=avg_sog,
                    weather=wx_src, heading_deg=heading_src,
                    sws=sws_solved, fcr_mt_per_h=fcr, fuel_mt=fuel,
                    sub_legs=sub_legs_solved,
                ))

                if abs(dst_t - t_next) < 1e-6 and abs(dst_d - L) > 1e-9:
                    next_reachable.add(dst_d)

        reachable_at_t.setdefault(t_next, set()).update(next_reachable)

    # Same-node invariant: every produced edge endpoint must coincide with
    # an existing free-DP node. This is what lets Bellman run on the union
    # of free-DP and locked edges with a single canonical-node table.
    for e in edges:
        src_key = (round(e.src_t, 6), round(e.src_d, 6))
        dst_key = (round(e.dst_t, 6), round(e.dst_d, 6))
        if src_key not in node_key_set:
            raise AssertionError(f"locked edge src {src_key} not in node set")
        if dst_key not in node_key_set:
            raise AssertionError(f"locked edge dst {dst_key} not in node set")

    return edges


# ----------------------------------------------------------------------
# Quick-look summary
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
    """Resimulate the locked schedule **continuously** (no inter-block snap).

    Each block's simulation starts from the *continuous* end of the previous
    block, NOT from its snapped destination. Reports actual final (t, d) and
    actual cumulative fuel against what Bellman claimed. If the snap policy is
    biased, the continuous trajectory will end short of (or past) L=3393.24
    even though Bellman claimed it landed exactly on the sink.
    """
    print("=" * 78)
    print("Locked schedule sanity check — continuous resimulation")
    print("=" * 78)
    print(f"  {'k':>2} {'src(t,d) snap':>22} {'src(t,d) cont':>22}  "
          f"{'SWS':>6} {'dt':>5}  {'dst_cont':>10}  {'Δd_snap':>9}")

    t = 0.0
    d = 0.0
    total_fuel = 0.0
    bellman_total = sum(e.fuel_mt for e in schedule)

    for k, e in enumerate(schedule):
        # We deliberately ignore e.src_d / e.src_t for the simulation start,
        # using the continuous (t, d) we actually arrived at.
        dt = e.dst_t - e.src_t
        sws = e.sws
        result = simulate_block(
            t0=t, d0=d, sws=sws, duration_h=dt,
            route=route, voyage=voyage,
            h_line_distances=h_line_distances, L=L,
            waypoints=waypoints,
            sample_hour=sample_hour, forecast_hour=forecast_hour,
            grid_deg=grid_deg,
        )
        if result is None:
            print(f"  Block {k}: infeasible at continuous src ({t:.3f}, {d:.4f})")
            return {}
        final_t, final_d, fuel, _ = result
        delta_snap = final_d - e.dst_d

        if k < 3 or k > len(schedule) - 4 or k % 10 == 0:
            print(f"  {k:>2} ({e.src_t:>5.1f},{e.src_d:>9.3f})  "
                  f"({t:>5.2f},{d:>10.5f})  "
                  f"{sws:>6.3f} {dt:>5.2f}  ({final_d:>9.5f})  {delta_snap:>+9.5f}")

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


def summarize_locked(edges: List[LockedEdge]) -> None:
    if not edges:
        print("No locked edges built.")
        return
    fuels = [e.fuel_mt for e in edges]
    swss = [e.sws for e in edges]
    sub_legs = [e.sub_legs for e in edges]
    print("=" * 70)
    print(f"LockedEdge summary  ({len(edges):,} edges)")
    print("=" * 70)
    print(f"  SWS range:     [{min(swss):.3f}, {max(swss):.3f}] kn")
    print(f"  fuel/edge:     [{min(fuels):.3f}, {max(fuels):.3f}] mt  "
          f"(mean {sum(fuels)/len(fuels):.3f})")
    print(f"  sub_legs/edge: min {min(sub_legs)}, max {max(sub_legs)}, "
          f"mean {sum(sub_legs)/len(sub_legs):.2f}")
    src_ts = sorted({e.src_t for e in edges})
    print(f"  V-bands used:  {len(src_ts)}  (first src_t={src_ts[0]}, "
          f"last src_t={src_ts[-1]})")
    print("=" * 70)

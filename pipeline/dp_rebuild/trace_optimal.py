"""
Step-by-step trace of edge creation and fuel calculation for the optimal route.

Walks through:
  1. The edge-creation algorithm (one concrete edge, all 9 sub-steps).
  2. Every atomic edge of the Free DP optimal schedule, showing target SOG,
     realized SOG, weather, heading, SWS, FCR, Δt, fuel, and cumulative fuel.
  3. A reconciliation against the Bellman total.
"""

from __future__ import annotations

import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_PIPELINE_ROOT = _HERE.parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))
if str(_PIPELINE_ROOT) not in sys.path:
    sys.path.insert(0, str(_PIPELINE_ROOT))

from shared.physics import (  # type: ignore  # noqa: E402
    calculate_fuel_consumption_rate,
    calculate_sws_from_sog,
)

from bellman import BellmanSolver
from build_atomic_edges import build_atomic_edges
from frame import from_route as frame_from_route
from h5_weather import VoyageWeather
from load_route import load_yaml_route, synthesize_multi_window
from route_waypoints import WAYPOINTS


def trace_one_edge_creation(frame, src_t, src_d, target_sog):
    """Print the 9-step derivation of ONE atomic edge."""
    print("=" * 78)
    print(f"Edge creation walkthrough — src=({src_t:.3f} h, {src_d:.3f} nm), "
          f"target_sog={target_sog:.2f} kn")
    print("=" * 78)

    # Step 1: find next V-line and next H-line
    next_v = frame.next_v_time(src_t)
    next_h = frame.next_h_distance(src_d)
    print(f"  1. next V-line time:        {next_v:.3f} h")
    print(f"     next H-line distance:    {next_h:.6f} nm")

    # Step 2: time to reach each
    dt_to_h = (next_h - src_d) / target_sog
    dt_to_v = next_v - src_t
    print(f"  2. Δt to next H-line:       (H − src_d) / target = "
          f"({next_h:.4f} − {src_d:.4f}) / {target_sog:.2f} = {dt_to_h:.6f} h")
    print(f"     Δt to next V-line:       {dt_to_v:.3f} h")

    # Step 3: which boundary comes first
    if dt_to_h <= dt_to_v + 1e-9:
        print(f"  3. H-line crossing comes first (Δt_h ≤ Δt_v) → H-line target")
        # Step 4: snap arrival t to 0.1 h grid
        dst_d = next_h
        dst_t_raw = src_t + dt_to_h
        dst_t = frame.snap_h_dst_t(dst_t_raw)
        print(f"  4. Raw dst_t  = src_t + Δt_h = {src_t:.3f} + {dt_to_h:.6f} = "
              f"{dst_t_raw:.6f} h")
        print(f"     Snapped dst_t (0.1 h grid) = {dst_t:.3f} h")
    else:
        print(f"  3. V-line boundary comes first (Δt_v < Δt_h) → V-line target")
        dst_t = next_v
        dst_d_raw = src_d + target_sog * dt_to_v
        dst_d = frame.snap_v_dst_d(dst_d_raw)
        print(f"  4. Raw dst_d = src_d + sog · Δt_v = {src_d:.3f} + "
              f"{target_sog:.2f} · {dt_to_v:.3f} = {dst_d_raw:.4f} nm")
        print(f"     Snapped dst_d (1 nm grid) = {dst_d:.0f} nm")

    # Step 5: realized SOG
    dt = dst_t - src_t
    dd = dst_d - src_d
    realized_sog = dd / dt
    print(f"  5. Δt = dst_t − src_t       = {dt:.3f} h")
    print(f"     Δd = dst_d − src_d       = {dd:.4f} nm")
    print(f"     realized SOG = Δd / Δt   = {realized_sog:.6f} kn  "
          f"(target {target_sog:.2f} → realized {realized_sog:.4f}, "
          f"snap drift {realized_sog - target_sog:+.4f})")

    # Step 6: cell-canonical weather + heading
    sample_hour = 0  # using the demo's override
    weather = frame.cell_weather_at(src_d, sample_hour=sample_hour)
    heading = frame.paper_heading_at(src_d)
    print(f"  6. weather  @ src_d (sample_hour={sample_hour}, cell-canonical):")
    print(f"        wind   = {weather.wind_speed_10m_kmh:.2f} km/h, "
          f"dir = {weather.wind_direction_10m_deg:.1f}°")
    print(f"        wave   = {weather.wave_height_m:.2f} m,  BN = {weather.beaufort_number}")
    print(f"        current= {weather.ocean_current_velocity_kmh:.2f} km/h, "
          f"dir = {weather.ocean_current_direction_deg:.1f}°")
    print(f"     paper β @ src_d           = {heading:.2f}°")

    # Step 7: inverse-solve SWS
    weather_dict = {
        "wind_speed_10m_kmh": weather.wind_speed_10m_kmh,
        "wind_direction_10m_deg": weather.wind_direction_10m_deg,
        "beaufort_number": weather.beaufort_number,
        "wave_height_m": weather.wave_height_m,
        "ocean_current_velocity_kmh": weather.ocean_current_velocity_kmh,
        "ocean_current_direction_deg": weather.ocean_current_direction_deg,
    }
    sws = calculate_sws_from_sog(
        target_sog=realized_sog,
        weather=weather_dict,
        ship_heading_deg=heading,
        ship_parameters=None,
    )
    print(f"  7. SWS = inverse_solve(realized_sog, weather, β)")
    print(f"        = {sws:.6f} kn   (engine speed needed to make realized SOG good)")

    # Step 8: FCR
    fcr = calculate_fuel_consumption_rate(sws)
    print(f"  8. FCR = 0.000706 · SWS³ = 0.000706 · {sws:.4f}³ = {fcr:.6f} mt/h")

    # Step 9: fuel
    fuel = fcr * dt
    print(f"  9. fuel = FCR · Δt = {fcr:.6f} · {dt:.3f} = {fuel:.6f} mt")
    print(f"     → emit AtomicEdge(src={src_t:.2f},{src_d:.2f} → "
          f"dst={dst_t:.2f},{dst_d:.2f}; target={target_sog:.2f}; fuel={fuel:.4f} mt)")
    print()


def trace_block(schedule, frame, block_idx):
    """Walk through every atomic edge in one 6 h block of the optimal schedule.

    Each edge gets the 9-step derivation. The first edge in a block starts
    from a V-line node; the rest start from H-line nodes. Block fuel is the
    sum of per-edge fuels.
    """
    dt_h = frame.cfg.dt_h
    block_edges = [e for e in schedule if int(e.src_t // dt_h) == block_idx]
    if not block_edges:
        print(f"No edges in block {block_idx}.")
        return

    t_lo = block_idx * dt_h
    t_hi = min((block_idx + 1) * dt_h, frame.cfg.eta_h)
    print()
    print("#" * 78)
    print(f"# Block {block_idx} trace — t ∈ [{t_lo:.1f}, {t_hi:.1f}] h, "
          f"{len(block_edges)} atomic edges")
    print(f"# block-start sample_hour = {frame.sample_hour_for_block(t_lo)} "
          f"(used for all edges in this block)")
    print("#" * 78)

    block_fuel = 0.0
    for i, e in enumerate(block_edges):
        src_kind = "V-line" if i == 0 else "H-line"
        print()
        print(f"---- edge {i + 1} of block {block_idx} (src on {src_kind}) ----")
        trace_one_edge_creation(frame, e.src_t, e.src_d, e.target_sog)
        block_fuel += e.fuel_mt
        print(f"     running block fuel: {block_fuel:.6f} mt")

    print()
    print("=" * 78)
    print(f"Block {block_idx} totals")
    print("=" * 78)
    print(f"  src_d at block start  = {block_edges[0].src_d:.4f} nm "
          f"(V-line t = {t_lo:.1f})")
    print(f"  dst_d at block end    = {block_edges[-1].dst_d:.4f} nm "
          f"(V-line t = {t_hi:.1f})")
    print(f"  Δd over the block     = "
          f"{block_edges[-1].dst_d - block_edges[0].src_d:.4f} nm")
    print(f"  avg SOG over block    = "
          f"{(block_edges[-1].dst_d - block_edges[0].src_d) / (t_hi - t_lo):.4f} kn")
    print(f"  target SOGs used      = "
          f"{sorted({round(e.target_sog, 4) for e in block_edges})}")
    print(f"  block fuel            = Σ FCR·Δt = "
          f"{' + '.join(f'{e.fuel_mt:.4f}' for e in block_edges)} = "
          f"{block_fuel:.6f} mt")
    print()


def trace_optimal_schedule(schedule, frame, total_bellman):
    """Print every atomic edge in the optimal schedule with its derivation."""
    print("=" * 122)
    print(f"Optimal Free DP schedule — {len(schedule)} atomic edges, "
          f"Bellman total {total_bellman:.4f} mt")
    print("=" * 122)
    print(f"{'#':>3}  {'src(t,d)':>20}  {'dst(t,d)':>20}  {'tSOG':>5}  "
          f"{'rSOG':>6}  {'BN':>3}  {'β':>6}  {'SWS':>7}  "
          f"{'FCR':>8}  {'Δt':>6}  {'fuel_i':>8}  {'cum_fuel':>9}")
    print("-" * 122)

    cum = 0.0
    cell_changes = 0
    block_changes = 0
    last_sog = None
    last_block = -1
    for i, e in enumerate(schedule):
        cum += e.fuel_mt
        block = int(e.src_t // frame.cfg.dt_h)
        marker = ""
        if last_block != -1 and block != last_block:
            marker = "  ← block boundary (V-line)"
            block_changes += 1
        elif last_sog is not None and abs(e.target_sog - last_sog) > 1e-6:
            marker = "  ← speed change (H-line)"
            cell_changes += 1
        print(f"{i+1:>3}  ({e.src_t:>6.2f},{e.src_d:>9.2f})  "
              f"({e.dst_t:>6.2f},{e.dst_d:>9.2f})  {e.target_sog:>5.2f}  "
              f"{e.sog:>6.3f}  {e.weather.beaufort_number:>3}  "
              f"{e.heading_deg:>6.2f}  {e.sws:>7.3f}  "
              f"{e.fcr_mt_per_h:>8.5f}  {e.dst_t - e.src_t:>6.3f}  "
              f"{e.fuel_mt:>8.4f}  {cum:>9.4f}{marker}")
        last_sog = e.target_sog
        last_block = block

    print("-" * 122)
    print(f"  Σ fuel over all atomic edges = {cum:.6f} mt")
    print(f"  Bellman.cost[sink]           = {total_bellman:.6f} mt")
    print(f"  Δ                            = {cum - total_bellman:+.2e} mt  (floating-point only)")
    print()
    print(f"  Block boundaries (V-line) crossed: {block_changes}")
    print(f"  Mid-block speed changes  (H-line): {cell_changes}")


def main():
    yaml_path = _HERE.parent.parent / "Dynamic speed optimization" / "weather_forecasts.yaml"
    h5_path = _HERE.parent / "data" / "voyage_weather.h5"
    route = load_yaml_route(yaml_path)
    route = synthesize_multi_window(route, window_h=6.0)
    voyage = VoyageWeather(h5_path)
    frame = frame_from_route(route, voyage, WAYPOINTS)

    print("Building atomic-edge graph …")
    nodes, edges = build_atomic_edges(frame, override_sample_hour=0)
    print(f"  {len(nodes):,} nodes, {len(edges):,} edges")

    print("\nSolving Free DP …")
    solver = BellmanSolver(nodes, edges)
    solver.solve()
    res = solver.result(eta_mode="hard", eta=frame.cfg.eta_h)
    print(f"  optimal fuel = {res.total_fuel_mt:.4f} mt, "
          f"voyage time = {res.voyage_time_h:.3f} h, "
          f"schedule = {len(res.schedule)} edges")

    # ---- Walk through the FIRST edge in the optimal schedule -----------
    first = res.schedule[0]
    print()
    trace_one_edge_creation(frame, first.src_t, first.src_d, first.target_sog)

    # ---- Walk through one whole block, all edges (most start at H-lines)
    block_to_trace = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    trace_block(res.schedule, frame, block_to_trace)

    # ---- Walk through the FULL schedule with cumulative fuel ----------
    trace_optimal_schedule(res.schedule, frame, res.total_fuel_mt)


if __name__ == "__main__":
    main()

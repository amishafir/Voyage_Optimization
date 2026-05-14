"""
Compare SR DP and Luo DP schedules on the rebuilt graph, block by block.

For each 6 h block:
  * SR DP may take 1+ atomic edges, possibly with different target_sogs.
  * Luo DP must take a *single* target_sog across all edges in the block
    (the SOG-lock invariant).

Block classifications:
  A. **identical decision** — SR uses 1 distinct target_sog AND it matches
     Luo's chosen SOG. The two policies converge in this block.
  B. **same structure, different SOG** — SR uses 1 distinct target_sog
     but a *different* one than Luo. Both ran a constant-SOG block, but
     they disagreed on which SOG was best.
  C. **SR deviated** — SR used ≥ 2 distinct target_sogs in the block.
     SR exploited mid-block speed flexibility that Luo's lock forbids;
     this is where the +0.323 mt gap (Luo - SR) is generated.

Outputs a per-block table + an aggregate summary.
"""

from __future__ import annotations

import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Tuple

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from bellman import BellmanSolver
from bellman_locked import BellmanSolverLocked
from atomic_edges import AtomicEdge, build_atomic_edges
from frame import from_route as frame_from_route
from weather import VoyageWeather
from route import load_yaml_route, synthesize_multi_window
from route_waypoints import WAYPOINTS


def _block_index(t: float, dt_h: float = 6.0) -> int:
    return int(t // dt_h)


def group_schedule_by_block(
    schedule: List[AtomicEdge],
    dt_h: float = 6.0,
) -> Dict[int, List[AtomicEdge]]:
    by_block: Dict[int, List[AtomicEdge]] = defaultdict(list)
    for e in schedule:
        by_block[_block_index(e.src_t, dt_h)].append(e)
    return dict(sorted(by_block.items()))


def main() -> None:
    yaml_path = _HERE.parent / "config" / "routes" / "persian_gulf_malacca_paper.yaml"
    h5_path = _HERE.parent / "data" / "voyage_weather.h5"

    route = load_yaml_route(yaml_path)
    route = synthesize_multi_window(route, window_h=6.0)
    voyage = VoyageWeather(h5_path)
    frame = frame_from_route(route, voyage, WAYPOINTS)

    print("Building atomic-edge graph …")
    t0 = time.time()
    nodes, edges = build_atomic_edges(frame, override_sample_hour=0)
    print(f"  {len(nodes):,} nodes, {len(edges):,} edges in {time.time()-t0:.1f} s\n")

    print("Solving SR DP …")
    sr = BellmanSolver(nodes, edges)
    sr.solve()
    sr_res = sr.result(eta_mode="hard", eta=frame.cfg.eta_h)
    print(f"  fuel = {sr_res.total_fuel_mt:.3f} mt, edges = {len(sr_res.schedule)}\n")

    print("Solving Luo DP …")
    luo = BellmanSolverLocked(nodes, edges, set(frame.v_line_times))
    luo.solve()
    luo_res = luo.result(eta_h=frame.cfg.eta_h)
    print(f"  fuel = {luo_res.total_fuel_mt:.3f} mt, edges = {len(luo_res.schedule)}\n")

    sr_by_block = group_schedule_by_block(sr_res.schedule, frame.cfg.dt_h)
    luo_by_block = group_schedule_by_block(luo_res.schedule, frame.cfg.dt_h)

    # ------------------------------------------------------------------
    # Per-block comparison
    # ------------------------------------------------------------------

    print("=" * 130)
    print("Per-block comparison: SR DP vs Luo DP")
    print("  ✓ = block (src_d, dst_d) coincide between SR and Luo (apples-to-apples)")
    print("  ≠ = block boundaries diverge in space (different mini-problems per block)")
    print("=" * 130)
    print(f"{'blk':>3} {'t_range':>11}  "
          f"{'sr src→dst (nm)':>22} {'luo src→dst (nm)':>22} {'aligned':>7}  "
          f"{'sr_SOGs':>22} {'luo_SOG':>7}  {'Δfuel':>8}  type")
    print("-" * 130)

    counts = {"A": 0, "B": 0, "C": 0}
    fuel_by_type = {"A": (0.0, 0.0), "B": (0.0, 0.0), "C": (0.0, 0.0)}
    aligned_count = 0

    all_blocks = sorted(set(sr_by_block) | set(luo_by_block))
    for blk in all_blocks:
        sr_edges = sr_by_block.get(blk, [])
        luo_edges = luo_by_block.get(blk, [])
        if not sr_edges or not luo_edges:
            continue

        sr_sogs = sorted({round(e.target_sog, 4) for e in sr_edges})
        luo_sog = round(luo_edges[0].target_sog, 4)
        # Sanity: Luo block must have exactly one target_sog
        assert len({round(e.target_sog, 4) for e in luo_edges}) == 1

        sr_fuel = sum(e.fuel_mt for e in sr_edges)
        luo_fuel = sum(e.fuel_mt for e in luo_edges)

        if len(sr_sogs) == 1 and abs(sr_sogs[0] - luo_sog) < 1e-6:
            block_type = "A"
        elif len(sr_sogs) == 1:
            block_type = "B"
        else:
            block_type = "C"

        counts[block_type] += 1
        f_acc, l_acc = fuel_by_type[block_type]
        fuel_by_type[block_type] = (f_acc + sr_fuel, l_acc + luo_fuel)

        sr_src = sr_edges[0].src_d
        sr_dst = sr_edges[-1].dst_d
        luo_src = luo_edges[0].src_d
        luo_dst = luo_edges[-1].dst_d
        aligned = abs(sr_src - luo_src) < 1e-3 and abs(sr_dst - luo_dst) < 1e-3
        if aligned:
            aligned_count += 1
        align_mark = "✓" if aligned else "≠"

        t_lo = blk * frame.cfg.dt_h
        t_hi = min((blk + 1) * frame.cfg.dt_h, frame.cfg.eta_h)
        sr_sogs_str = ",".join(f"{s:g}" for s in sr_sogs)
        if len(sr_sogs_str) > 22:
            sr_sogs_str = sr_sogs_str[:19] + "..."

        print(f"{blk:>3} {t_lo:>5.1f}–{t_hi:<5.1f}  "
              f"{sr_src:>9.2f}→{sr_dst:<10.2f} "
              f"{luo_src:>9.2f}→{luo_dst:<10.2f} {align_mark:>7}  "
              f"{sr_sogs_str:>22} {luo_sog:>7.2f}  "
              f"{luo_fuel - sr_fuel:>+8.3f}  {block_type}")

    # ------------------------------------------------------------------
    # Aggregate summary
    # ------------------------------------------------------------------

    total_blocks = sum(counts.values())
    print("=" * 130)
    print("Aggregate summary")
    print("=" * 130)
    print(f"{'type':<55} {'count':>5} {'sr_fuel':>11} {'luo_fuel':>11} {'Δ (luo-free)':>14}")
    print("-" * 130)
    labels = {
        "A": "A. identical decision (SR 1 SOG, matches Luo)",
        "B": "B. same structure, different SOG (SR 1 SOG ≠ Luo)",
        "C": "C. SR deviated (≥ 2 SOGs in block, Luo can't)",
    }
    for t in ("A", "B", "C"):
        f_fuel, l_fuel = fuel_by_type[t]
        print(f"{labels[t]:<55} {counts[t]:>5} "
              f"{f_fuel:>11.3f} {l_fuel:>11.3f} {l_fuel - f_fuel:>+14.3f}")
    print("-" * 130)
    total_free = sum(f for f, _ in fuel_by_type.values())
    total_luo = sum(l for _, l in fuel_by_type.values())
    print(f"{'TOTAL':<55} {total_blocks:>5} "
          f"{total_free:>11.3f} {total_luo:>11.3f} {total_luo - total_free:>+14.3f}")
    print()
    print(f"SR DP total fuel:  {sr_res.total_fuel_mt:.3f} mt")
    print(f"Luo DP total fuel:   {luo_res.total_fuel_mt:.3f} mt")
    print(f"Δ (Luo - SR):      {luo_res.total_fuel_mt - sr_res.total_fuel_mt:+.3f} mt")
    print(f"Aligned blocks (✓):  {aligned_count}/{total_blocks}  "
          f"(both schedules agree on the V-line node positions for that block)")

    # ------------------------------------------------------------------
    # Apples-to-apples per-block view (only aligned blocks)
    # ------------------------------------------------------------------

    print()
    print("Apples-to-apples per-block view (only blocks where SR's and Luo's")
    print("V-line dst d coincide — same mini-problem, fuel comparison is meaningful):")
    print("-" * 130)

    aligned_sr = aligned_luo = 0.0
    aligned_C_sr = aligned_C_luo = 0.0
    aligned_C = 0
    for blk in all_blocks:
        sr_edges = sr_by_block.get(blk, [])
        luo_edges = luo_by_block.get(blk, [])
        if not sr_edges or not luo_edges:
            continue
        sr_src, sr_dst = sr_edges[0].src_d, sr_edges[-1].dst_d
        luo_src, luo_dst = luo_edges[0].src_d, luo_edges[-1].dst_d
        if abs(sr_src - luo_src) >= 1e-3 or abs(sr_dst - luo_dst) >= 1e-3:
            continue
        sr_fuel = sum(e.fuel_mt for e in sr_edges)
        luo_fuel = sum(e.fuel_mt for e in luo_edges)
        aligned_sr += sr_fuel
        aligned_luo += luo_fuel
        sr_sogs = {round(e.target_sog, 4) for e in sr_edges}
        if len(sr_sogs) >= 2:
            aligned_C += 1
            aligned_C_sr += sr_fuel
            aligned_C_luo += luo_fuel

    print(f"  Aligned-block totals:  SR = {aligned_sr:.3f} mt,  "
          f"Luo = {aligned_luo:.3f} mt,  Δ = {aligned_luo - aligned_sr:+.3f} mt")
    print(f"  Aligned type-C blocks: {aligned_C}  →  SR saves "
          f"{aligned_C_luo - aligned_C_sr:+.3f} mt by using mid-block SOG flexibility")


if __name__ == "__main__":
    main()

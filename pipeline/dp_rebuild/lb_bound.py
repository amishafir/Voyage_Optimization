"""
lb_bound — neighbour-price LOWER BOUND for the SR DP (Tal's idea, Aug-5 meeting).

Node-first formulation, no snapping involved. The relaxation: every arc
(d,t) -> (d~,t~) still MOVES the vessel to the chosen grid node (geometry
honest — no positional credit, which is what fixed E3's ~38% leak), but the
arc's fuel is charged at the speed of the ADJACENT, ONE-STEP-SLOWER candidate
on the same wall:

  family 1 (arrival time t~ on the distance wall, tau-spaced):
      slower neighbour arrives one tau later
          v_minus = (d~ - d) / (t~ + tau - t)
  family 2 (arrival distance d~ on the time wall, zeta-spaced):
      slower neighbour advances one zeta less
          v_minus = (d~ - zeta - d) / (t~ - t)

Validity (LB of the continuous optimum): a continuous trajectory crosses each
wall BETWEEN two adjacent grid nodes; map the crossing to the adjacent FASTER
node (arrival no later / advance no shorter => ETA feasibility preserved).
The mapped arc's discounted price — the slower neighbour's speed — under-runs
the true crossing speed (which lies between the two neighbours), and FCR is
increasing in speed, so every leg is undercharged. Hence

    LB_DP  <=  F*(continuous)  <=  F_polished  <=  F_DP

which, together with the §4.3 node-slide polish (upper side), brackets the
continuous optimum from the same grid machinery.

Edge cases (documented in docs/lb_neighbour_price_plan.md):
  (a) slowest candidate in a window — its slower neighbour falls outside the
      admissible window: clip v_minus at the CURRENT band's v_min
      (frame.cfg.v_min; do not assume v_min = 0 — that band change is pending);
  (b) glide-rule arcs (family-2 candidates extending past a skipped distance
      wall) — same family-2 discount (they live on the time wall); counted;
  (c) v_minus <= 0 cannot occur while v_min > 0, but guarded (floor 1e-6 kn);
  (d) corner nodes (destination on BOTH walls) — priced at the SMALLER of the
      two family discounts (conservative: undercharges either wall-crossing
      mapping);
  (e) the discounted speed is used for PRICING ONLY (SWS inverse -> FCR at
      v_minus, times the arc's REAL duration t~ - t); arc geometry unchanged.

Implementation: one streaming-style forward relaxation (lex-min (t,d) heap,
same rounded keys / same per-source enumerator `_emit_from_src` as the
production solvers) carrying TWO labels per state — the normally-priced cost
(must reproduce the frozen goldens EXACTLY, validating the solve loop) and the
discounted cost (the LB). No arc set is stored. This file is standalone: it
imports from atomic_edges/frame/nodes/route/weather/shared.physics but
modifies nothing (streaming refactor is running concurrently in another
session — its pattern is copied here, not imported).

Usage (from pipeline/dp_rebuild/):
    python3 lb_bound.py --route route1 --sh_base 6
    python3 lb_bound.py --route route2 --sh_base 0
    # optional: --out_dir PATH  (also writes <route>_sh<sh>.json there)
"""
from __future__ import annotations

import argparse
import heapq
import json
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))
_PIPELINE_ROOT = _HERE.parent
if str(_PIPELINE_ROOT) not in sys.path:
    sys.path.insert(0, str(_PIPELINE_ROOT))

from atomic_edges import _SWS_MAX_FEASIBLE, _emit_from_src  # noqa: E402
from frame import from_route as make_frame  # noqa: E402
from nodes import GraphConfig  # noqa: E402
from route import load_route_auto, synthesize_multi_window  # noqa: E402
from weather import VoyageWeather  # noqa: E402
from shared.physics import (  # noqa: E402
    calculate_fuel_consumption_rate,
    calculate_sws_from_sog,
)

EPS = 1e-9
_KEY_PRECISION = 9

# Route configs — mirror of run_chain_sweep.ROUTES (duplicated here so this
# script does not import run_chain_sweep -> SR_main/luo_main, which are being
# refactored concurrently).
ROUTES = {
    "route1": {
        "label": "Malacca",
        "yaml": "../config/routes/persian_gulf_malacca_paper.yaml",
        "h5":   "../data/experiment_b_138wp.h5",
        "eta":  280.0,
    },
    "route2": {
        "label": "Atlantic",
        "yaml": "../config/routes/st_johns_liverpool.yaml",
        "h5":   "../data/experiment_d_391wp.h5",
        "eta":  168.0,
    },
}

# Frozen references (goldens/quick.json, commit 6f35f31, node-first legacy).
GOLDEN_F_DP = {
    ("route1", 6): "353.95517201251994",
    ("route2", 0): "202.48415966493758",
}

# §4.3 polish recovery for the bracket comparison (upper side).
CERTIFICATE_CSV = (
    _HERE.parent.parent / "runs" / "2026_07_28_local_certificate" / "results.csv"
)


def _key(t: float, d: float) -> Tuple[float, float]:
    return (round(t, _KEY_PRECISION), round(d, _KEY_PRECISION))


def build_frame(route_key: str, sh_base: int,
                tau_h: float = None, zeta_nm: float = None):
    """Frame construction identical to SR_main.solve / ddd_lb.build_frame
    (route yaml + eta override + windows re-synth + mean-SOG +/- 3 band)."""
    rc = ROUTES[route_key]
    yaml_path = (_HERE / rc["yaml"]).resolve()
    h5_path = (_HERE / rc["h5"]).resolve()
    eta = float(rc["eta"])
    route, wps = load_route_auto(yaml_path, eta_h=eta)
    route = synthesize_multi_window(route, window_h=6.0)
    cfg = GraphConfig.from_route(route)
    cfg.eta_h = eta
    if route.windows:
        route.windows[-1].end = eta
        route = synthesize_multi_window(route, window_h=6.0)
    mean_sog = cfg.length_nm / cfg.eta_h
    cfg.v_min, cfg.v_max = mean_sog - 3.0, mean_sog + 3.0
    if tau_h is not None:
        cfg.tau_h = tau_h          # refinement study: finer pricing grid
    if zeta_nm is not None:
        cfg.zeta_nm = zeta_nm
    voyage = VoyageWeather(h5_path)
    frame = make_frame(route, voyage, wps, cfg=cfg, base_sample_hour=sh_base)
    return frame


def _lb_edge_cost(e, next_v: Optional[float], next_h: Optional[float],
                  tau: float, zeta: float, vmin: float,
                  wd: dict, heading: float, stats: Dict[str, int]) -> float:
    """Discounted (neighbour) price of one arc. Geometry untouched — only the
    pricing speed changes: v_minus per the family rules, clipped at the band's
    v_min, then SWS inverse -> FCR -> x real duration."""
    dt = e.dst_t - e.src_t
    on_h = next_h is not None and abs(e.dst_d - next_h) < EPS
    on_v = next_v is not None and abs(e.dst_t - next_v) < EPS
    vms: List[float] = []
    if on_h:                                   # family 1: distance wall
        vms.append((e.dst_d - e.src_d) / (dt + tau))
        stats["n_family1"] += 1
    if on_v:                                   # family 2: time wall
        vms.append((e.dst_d - zeta - e.src_d) / dt)
        stats["n_family2"] += 1
    if on_h and on_v:
        stats["n_corner"] += 1                 # priced at min(v1-, v2-)
    if on_v and not on_h and next_h is not None and e.dst_d > next_h + EPS:
        stats["n_glide"] += 1                  # glide-rule arc (family 2)
    if not vms:
        # Should be impossible: every node-first candidate lands on a wall.
        # Conservative fallback = free arc (undercharging is always LB-safe).
        stats["n_unclassified"] += 1
        return 0.0
    v_raw = min(vms)
    v_minus = max(v_raw, vmin, 1e-6)           # edge cases (a) + (c)
    if v_raw < vmin - EPS:
        stats["n_clipped_vmin"] += 1
    sws = calculate_sws_from_sog(target_sog=v_minus, weather=wd,
                                 ship_heading_deg=heading, ship_parameters=None)
    if sws != sws or sws > _SWS_MAX_FEASIBLE:
        # v_minus < realised arc speed which passed the same gate, so this
        # should never fire; undercharge (free) keeps the bound valid.
        stats["n_phys_fallback"] += 1
        return 0.0
    return calculate_fuel_consumption_rate(sws) * dt


def solve_dual(frame, eta: float) -> dict:
    """One forward pass, two labels per state: cost_dp (normal pricing — must
    match the golden F_DP bit-for-bit) and cost_lb (neighbour pricing — the
    lower bound). Streaming pattern: lex-min heap over rounded (t, d) keys,
    per-source enumeration via _emit_from_src(node_first=True), immediate
    relaxation, nothing stored per arc."""
    L = frame.cfg.length_nm
    tau, zeta = frame.cfg.tau_h, frame.cfg.zeta_nm
    vmin = frame.cfg.v_min

    src = _key(0.0, 0.0)
    cost_dp: Dict[Tuple[float, float], float] = {src: 0.0}
    cost_lb: Dict[Tuple[float, float], float] = {src: 0.0}
    # Diagnostic (gap decomposition): parent of the NORMAL-priced label and
    # the discounted price of that same parent arc. Lets us split
    # F_DP - LB = [F_DP - disc(DP path)] (intrinsic one-step discount along
    # the true plan) + [disc(DP path) - LB] (adversarial path-switch slack).
    parent_dp: Dict[Tuple[float, float], Optional[Tuple[float, float]]] = {src: None}
    parent_dt: Dict[Tuple[float, float], float] = {}
    parent_lbc: Dict[Tuple[float, float], float] = {}
    popped: Set[Tuple[float, float]] = set()
    in_heap: Set[Tuple[float, float]] = {src}
    heap: List[Tuple[float, float]] = [src]

    stats = {k: 0 for k in (
        "n_edges", "n_family1", "n_family2", "n_corner", "n_glide",
        "n_clipped_vmin", "n_unclassified", "n_phys_fallback")}

    t0 = time.time()
    while heap:
        k = heapq.heappop(heap)
        in_heap.discard(k)
        if k in popped:
            continue
        popped.add(k)
        t, d = k
        base_dp = cost_dp[k]
        base_lb = cost_lb[k]

        edges = _emit_from_src(t, d, frame, node_first=True)
        if not edges:
            continue
        # Weather and heading are resolved once per source inside
        # _emit_from_src; every edge of this source carries the same pair.
        w = edges[0].weather
        wd = {
            "wind_speed_10m_kmh": w.wind_speed_10m_kmh,
            "wind_direction_10m_deg": w.wind_direction_10m_deg,
            "beaufort_number": w.beaufort_number,
            "wave_height_m": w.wave_height_m,
            "ocean_current_velocity_kmh": w.ocean_current_velocity_kmh,
            "ocean_current_direction_deg": w.ocean_current_direction_deg,
        }
        heading = edges[0].heading_deg
        next_v = frame.next_v_time(t)
        next_h = frame.next_h_distance(d)

        for e in edges:
            stats["n_edges"] += 1
            dk = _key(e.dst_t, e.dst_d)
            if dk in popped:
                raise AssertionError(
                    f"lb_bound invariant violated: relax into popped state "
                    f"{dk} from {k}")
            # --- neighbour (discounted) pricing ---
            lbc = _lb_edge_cost(e, next_v, next_h, tau, zeta, vmin,
                                wd, heading, stats)
            # --- normal pricing (golden validation path) ---
            new_dp = base_dp + e.fuel_mt
            prev_dp = cost_dp.get(dk)
            if prev_dp is None or new_dp < prev_dp:
                cost_dp[dk] = new_dp
                parent_dp[dk] = k
                parent_dt[dk] = e.dst_t - e.src_t
                parent_lbc[dk] = lbc
            new_lb = base_lb + lbc
            prev_lb = cost_lb.get(dk)
            if prev_lb is None or new_lb < prev_lb:
                cost_lb[dk] = new_lb
            if prev_dp is None and dk not in in_heap and dk not in popped:
                heapq.heappush(heap, dk)
                in_heap.add(dk)

    wall = time.time() - t0

    # --- hard-ETA sink selection (mirrors BellmanSolver.best_sink) ---------
    sinks = [k for k in cost_dp if abs(k[1] - L) < 1e-9 and k[0] <= eta + 1e-6]
    if not sinks:
        raise ValueError(f"No sink reachable within ETA {eta} h")
    best_dp = min(sinks, key=lambda k: cost_dp[k])
    best_lb = min(sinks, key=lambda k: cost_lb[k])

    # --- gap decomposition: discounted cost of the DP-optimal path ---------
    disc_dp_path = 0.0
    leg_dts: List[float] = []
    cur = best_dp
    while parent_dp.get(cur) is not None:
        disc_dp_path += parent_lbc[cur]
        leg_dts.append(parent_dt[cur])
        cur = parent_dp[cur]

    return {
        "F_DP": cost_dp[best_dp],
        "F_DP_time_h": best_dp[0],
        "LB": cost_lb[best_lb],
        "LB_time_h": best_lb[0],
        "disc_dp_path": disc_dp_path,
        "dp_n_legs": len(leg_dts),
        "dp_mean_leg_h": sum(leg_dts) / len(leg_dts) if leg_dts else 0.0,
        "n_nodes": len(cost_dp),
        "wall_s": wall,
        "stats": stats,
    }


def _polish_reference(route_key: str, sh_base: int) -> Optional[dict]:
    """F_polished / recovered_pct from the §4.3 certificate CSV, if present."""
    if not CERTIFICATE_CSV.exists():
        return None
    import csv as _csv
    with open(CERTIFICATE_CSV) as f:
        for row in _csv.DictReader(f):
            if row["route"] == route_key and int(row["sh"]) == sh_base:
                return {
                    "F_polished": float(row["F_polished"]),
                    "recovered_pct": float(row["recovered_pct"]),
                }
    return None


def main() -> int:
    ap = argparse.ArgumentParser(prog="lb_bound")
    ap.add_argument("--route", required=True, choices=list(ROUTES))
    ap.add_argument("--sh_base", type=int, required=True)
    ap.add_argument("--out_dir", default=None,
                    help="also write <route>_sh<sh>.json to this directory")
    ap.add_argument("--tau_h", type=float, default=None,
                    help="override the time grid step (refinement study)")
    ap.add_argument("--zeta_nm", type=float, default=None,
                    help="override the distance grid step (refinement study)")
    ap.add_argument("--tag", default="",
                    help="suffix for the output JSON filename")
    a = ap.parse_args()

    rc = ROUTES[a.route]
    print(f"lb_bound — neighbour-price LB   {a.route} ({rc['label']})  "
          f"sh_base={a.sh_base}  eta={rc['eta']:.0f} h", flush=True)

    frame = build_frame(a.route, a.sh_base, tau_h=a.tau_h, zeta_nm=a.zeta_nm)
    print(f"frame: L={frame.cfg.length_nm:.3f} nm  "
          f"band=[{frame.cfg.v_min:.3f}, {frame.cfg.v_max:.3f}] kn  "
          f"tau={frame.cfg.tau_h} h  zeta={frame.cfg.zeta_nm} nm  "
          f"V-lines={len(frame.v_line_times)}  "
          f"H-lines={len(frame.h_line_distances)}", flush=True)

    res = solve_dual(frame, eta=frame.cfg.eta_h)

    F, LB = res["F_DP"], res["LB"]
    gap_mt = F - LB
    gap_pct = gap_mt / F * 100.0
    s = res["stats"]

    print(f"\nsolve: {res['n_nodes']:,} states, {s['n_edges']:,} arcs "
          f"evaluated, {res['wall_s']:.1f} s")
    print(f"arc mix: family1={s['n_family1']:,}  family2={s['n_family2']:,}  "
          f"corner={s['n_corner']:,}  glide={s['n_glide']:,}")
    print(f"edge cases: clipped_at_vmin={s['n_clipped_vmin']:,}  "
          f"unclassified={s['n_unclassified']:,}  "
          f"phys_fallback={s['n_phys_fallback']:,}")

    print(f"\nF_DP (normal pricing)    : {F!r} mt   "
          f"(arrival {res['F_DP_time_h']:.1f} h)")
    golden = GOLDEN_F_DP.get((a.route, a.sh_base))
    sanity = None
    if golden is not None:
        sanity = (repr(F) == golden)
        print(f"golden check             : "
              f"{'PASS (exact repr match)' if sanity else 'FAIL'}  "
              f"[golden {golden}]")
    print(f"LB   (neighbour pricing) : {LB!r} mt   "
          f"(arrival {res['LB_time_h']:.1f} h)")
    print(f"LB < F_DP strictly       : {'PASS' if LB < F else 'FAIL'}")
    print(f"gap  (F_DP - LB)         : {gap_mt:.3f} mt  =  {gap_pct:.3f} % of F_DP")

    disc = res["disc_dp_path"]
    print(f"\ngap decomposition (DP path: {res['dp_n_legs']} legs, "
          f"mean leg {res['dp_mean_leg_h']:.2f} h):")
    print(f"  intrinsic discount  F_DP - disc(DP path)  : "
          f"{F - disc:.3f} mt  ({(F - disc) / F * 100:.3f} %)")
    print(f"  path-switch slack   disc(DP path) - LB    : "
          f"{disc - LB:.3f} mt  ({(disc - LB) / F * 100:.3f} %)")

    pol = _polish_reference(a.route, a.sh_base)
    if pol is not None:
        print(f"\nbracket   LB <= F* <= F_pol <= F_DP")
        print(f"  upper-side recovery (F_DP - F_pol)/F_DP : "
              f"{pol['recovered_pct']:.3f} %   (F_pol = {pol['F_polished']:.3f} mt)")
        print(f"  lower-side gap      (F_DP - LB)/F_DP    : {gap_pct:.3f} %")
        print(f"  certified bracket width (F_pol - LB)    : "
              f"{pol['F_polished'] - LB:.3f} mt")

    if a.out_dir:
        out_dir = Path(a.out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        payload = {
            "route": a.route, "sh_base": a.sh_base, "eta_h": rc["eta"],
            "F_DP": repr(F), "LB": repr(LB),
            "gap_mt": gap_mt, "gap_pct": gap_pct,
            "golden_check": sanity, "lb_strictly_below": LB < F,
            "F_DP_time_h": res["F_DP_time_h"], "LB_time_h": res["LB_time_h"],
            "disc_dp_path": res["disc_dp_path"],
            "dp_n_legs": res["dp_n_legs"],
            "dp_mean_leg_h": round(res["dp_mean_leg_h"], 3),
            "n_nodes": res["n_nodes"], "wall_s": round(res["wall_s"], 1),
            "stats": s, "polish_reference": pol,
        }
        out_path = out_dir / f"{a.route}_sh{a.sh_base}{a.tag}.json"
        out_path.write_text(json.dumps(payload, indent=2) + "\n")
        print(f"\nwrote {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

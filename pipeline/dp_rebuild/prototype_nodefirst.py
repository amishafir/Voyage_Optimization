"""
PROTOTYPE — Tal's node-first speed decision (2026-07-16).

Instead of looping the discrete SOG grid (speed-first, `atomic_edges.py`), this
enumerates, from each source node, the reachable DISTINCT grid nodes on the far
walls of the current rectangle (next distance line d-bar and next time line
t-bar) between v_min and v_max, rounded to the (zeta, tau) node grid. Each such
node's SOG = dd/dt is computed directly — no target speed, no target-vs-realised
gap (T18). This is the node-first dual of the speed-first build (T6/T20).

Runs an A/B against the speed-first builder on the same frame and reports
nodes / arcs / fan-out / fuel / build+solve time for both.

Usage:
    python3 prototype_nodefirst.py --yaml ../config/routes/persian_gulf_malacca_paper.yaml \
        --h5 ../data/experiment_d_391wp.h5 [--zeta 1.0 --tau 0.1 --sample_hour 0]
"""
from __future__ import annotations

import argparse
import sys
import time
from math import ceil, floor, isnan
from collections import deque
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent
for _p in (str(_HERE), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from shared.physics import calculate_fuel_consumption_rate, calculate_sws_from_sog  # noqa: E402
from atomic_edges import AtomicEdge, build_atomic_edges, summarize as summ  # noqa: E402
from bellman import BellmanSolver  # noqa: E402
from frame import from_route as make_frame  # noqa: E402
from nodes import GraphConfig, Node  # noqa: E402
from route import load_route_auto, synthesize_multi_window  # noqa: E402
from weather import VoyageWeather  # noqa: E402

_SWS_MAX = 25.0
_EPS = 1e-9


def _weather_at(frame, src_d, sample_hour):
    """Single-snapshot weather (override_sample_hour path), with NaN skip."""
    w = frame.cell_weather_at(src_d, sample_hour, None)
    if w.has_nan():
        return None, None
    wd = {
        "wind_speed_10m_kmh": w.wind_speed_10m_kmh,
        "wind_direction_10m_deg": w.wind_direction_10m_deg,
        "beaufort_number": w.beaufort_number,
        "wave_height_m": w.wave_height_m,
        "ocean_current_velocity_kmh": w.ocean_current_velocity_kmh,
        "ocean_current_direction_deg": w.ocean_current_direction_deg,
    }
    return w, wd


def emit_nodefirst(src_t, src_d, frame, sample_hour) -> List[AtomicEdge]:
    """Node-first arc emission: enumerate reachable far-wall grid nodes."""
    L = frame.cfg.length_nm
    T = frame.cfg.eta_h
    if abs(src_d - L) < _EPS or src_t >= T - _EPS:
        return []

    w, wd = _weather_at(frame, src_d, sample_hour)
    if w is None:
        return []
    heading = frame.paper_heading_at(src_d)

    next_t = frame.next_v_time(src_t)     # t-bar  (next time line)
    next_d = frame.next_h_distance(src_d)  # d-bar  (next distance line)
    if next_t is None and next_d is None:
        return []

    vmin, vmax = frame.cfg.v_min, frame.cfg.v_max
    zeta, tau = frame.cfg.zeta_nm, frame.cfg.tau_h
    cand: Set[Tuple[float, float]] = set()

    # A distance line is "resolvable" only if even the fastest speed lands a
    # non-degenerate snapped time on it. If it is too close (a cell-corner
    # cluster), we SKIP it and glide to the time line — mirroring speed-first's
    # h_too_close fallback. Without this, node-first is forced to stop at the
    # tiny leg and misses the far time-line successors speed-first reaches (the
    # ~1.5% fuel gap; see diagnostic_nodefirst_diff.py).
    dd = (next_d - src_d) if next_d is not None else None
    resolvable_d = (next_d is not None and dd > _EPS
                    and frame.snap_h_dst_t(src_t + dd / vmax) > src_t + _EPS)

    # --- distance line binds (fast speeds): enumerate arrival TIMES ---
    if resolvable_d:
        t_fast = src_t + dd / vmax            # v=vmax -> earliest
        t_slow = src_t + dd / vmin            # v=vmin -> latest
        t_hi = min(t_slow, next_t if next_t is not None else T, T)  # cap at corner / ETA
        k0, k1 = round(t_fast / tau), round(t_hi / tau)
        for k in range(k0, k1 + 1):
            dst_t = round(k * tau, 9)
            if dst_t > src_t + _EPS and dst_t <= T + _EPS:
                cand.add((dst_t, round(next_d, 9)))

    # --- time line binds (slow speeds): enumerate arrival DISTANCES ---
    # Cap at next_d only if that line is a resolvable stop; otherwise glide past
    # it (cap at L) so the far time-line nodes are reached in one leg.
    if next_t is not None:
        dt = next_t - src_t
        if dt > _EPS:
            d_slow = src_d + vmin * dt             # v=vmin -> nearest
            d_fast = src_d + vmax * dt             # v=vmax -> farthest
            d_cap = next_d if resolvable_d else L
            d_hi = min(d_fast, d_cap, L)
            k0, k1 = round(d_slow / zeta), round(d_hi / zeta)
            for k in range(k0, k1 + 1):
                dst_d = round(k * zeta, 9)
                if dst_d > src_d + _EPS and dst_d <= L + _EPS:
                    cand.add((round(next_t, 9), dst_d))

    edges: List[AtomicEdge] = []
    for dst_t, dst_d in cand:
        ddt, ddd = dst_t - src_t, dst_d - src_d
        if ddt <= _EPS or ddd <= _EPS:
            continue
        sog = ddd / ddt
        sws = calculate_sws_from_sog(sog, wd, heading, None)
        if sws != sws or sws > _SWS_MAX:
            continue
        fcr = calculate_fuel_consumption_rate(sws)
        fuel = fcr * ddt
        if isnan(fuel):
            continue
        crosses_v = abs(dst_t - (next_t if next_t is not None else -1)) < _EPS
        edges.append(AtomicEdge(src_t, src_d, dst_t, dst_d, sog, sog, w,
                                heading, sws, fcr, fuel, crosses_v))
    return edges


def build_nodefirst(frame, sample_hour) -> Tuple[List[Node], List[AtomicEdge]]:
    """BFS from the source, node-first emission, lazy interning (mirrors build_atomic_edges)."""
    L = frame.cfg.length_nm
    kp = 9
    idx: Dict[Tuple[float, float], Node] = {}

    def intern(t, d):
        k = (round(t, kp), round(d, kp))
        if k in idx:
            return idx[k]
        n = Node(time_h=t, distance_nm=d,
                 line_type=("V" if k == (0.0, 0.0) else "H"),
                 is_source=(k == (0.0, 0.0)), is_sink=abs(d - L) < 1e-9)
        idx[k] = n
        return n

    src = intern(0.0, 0.0)
    q = deque([src])
    visited: Set[Tuple[float, float]] = set()
    edges: List[AtomicEdge] = []
    while q:
        n = q.popleft()
        nk = (round(n.time_h, kp), round(n.distance_nm, kp))
        if nk in visited:
            continue
        visited.add(nk)
        if n.is_sink:
            continue
        for e in emit_nodefirst(n.time_h, n.distance_nm, frame, sample_hour):
            edges.append(e)
            d = intern(e.dst_t, e.dst_d)
            if (round(d.time_h, kp), round(d.distance_nm, kp)) not in visited:
                q.append(d)
    return list(idx.values()), edges


def _run(nodes, edges, eta):
    t0 = time.time()
    solver = BellmanSolver(nodes, edges)
    solver.solve()
    res = solver.result(eta_mode="hard", eta=eta)
    return res, time.time() - t0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--yaml", default="../config/routes/persian_gulf_malacca_paper.yaml")
    ap.add_argument("--h5", default="../data/experiment_d_391wp.h5")
    ap.add_argument("--eta", type=float, default=None)
    ap.add_argument("--zeta", type=float, default=None)
    ap.add_argument("--tau", type=float, default=None)
    ap.add_argument("--sample_hour", type=int, default=0)
    a = ap.parse_args()

    route, wps = load_route_auto(Path(a.yaml), eta_h=a.eta)
    route = synthesize_multi_window(route, window_h=6.0)
    voyage = VoyageWeather(Path(a.h5))
    cfg = GraphConfig.from_route(route)
    if a.eta:
        cfg.eta_h = a.eta
    if a.zeta:
        cfg.zeta_nm = a.zeta
    if a.tau:
        cfg.tau_h = a.tau
    mean = cfg.length_nm / cfg.eta_h
    cfg.v_min, cfg.v_max = mean - 3.0, mean + 3.0
    frame = make_frame(route, voyage, wps, cfg=cfg)
    K = len(frame.sog_grid())
    print(f"Route L={cfg.length_nm:.0f} nm, ETA={cfg.eta_h:.0f} h, zeta={cfg.zeta_nm} nm, "
          f"tau={cfg.tau_h} h, speed grid |V|={K} in [{cfg.v_min:.2f},{cfg.v_max:.2f}]")

    # ---- speed-first (current) ----
    print("\n[speed-first] building..."); t0 = time.time()
    n1, e1 = build_atomic_edges(frame, override_sample_hour=a.sample_hour, verbose=False)
    b1 = time.time() - t0
    r1, s1 = _run(n1, e1, cfg.eta_h)

    # ---- node-first (Tal) ----
    print("[node-first]  building..."); t0 = time.time()
    n2, e2 = build_nodefirst(frame, a.sample_hour)
    b2 = time.time() - t0
    r2, s2 = _run(n2, e2, cfg.eta_h)

    print("\n" + "=" * 68)
    print(f"{'':16}{'speed-first':>16}{'node-first':>16}")
    print("-" * 68)
    print(f"{'nodes':16}{len(n1):>16,}{len(n2):>16,}")
    print(f"{'arcs':16}{len(e1):>16,}{len(e2):>16,}")
    fan1 = len(e1) / max(1, sum(1 for n in n1 if not n.is_sink))
    fan2 = len(e2) / max(1, sum(1 for n in n2 if not n.is_sink))
    print(f"{'fan-out/node':16}{fan1:>16.1f}{fan2:>16.1f}")
    print(f"{'fuel (mt)':16}{r1.total_fuel_mt:>16.3f}{r2.total_fuel_mt:>16.3f}")
    print(f"{'voyage time (h)':16}{r1.voyage_time_h:>16.2f}{r2.voyage_time_h:>16.2f}")
    print(f"{'build (s)':16}{b1:>16.1f}{b2:>16.1f}")
    print(f"{'solve (s)':16}{s1:>16.2f}{s2:>16.2f}")
    print("-" * 68)
    dfuel = r2.total_fuel_mt - r1.total_fuel_mt
    print(f"node-first fuel - speed-first fuel = {dfuel:+.4f} mt "
          f"({100*dfuel/r1.total_fuel_mt:+.3f}%)  [expect <= 0, second-order]")
    print("=" * 68)
    return 0


if __name__ == "__main__":
    sys.exit(main())

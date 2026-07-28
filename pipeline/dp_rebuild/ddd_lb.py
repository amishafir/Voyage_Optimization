"""
ddd_lb — certificates for the discretisation gap of the SR DP.

Two independent certificates (docs/ddd_experiment_plan.md, E2/E3):

1. LOCAL (node-slide) certificate  [--mode local]
   Take the DP's optimal schedule. Each interior decision point q_k lies on a
   mandatory line; slide it CONTINUOUSLY along its line (between its grid
   neighbours' constraints, speeds kept in 𝒱, weather conventions identical to
   the DP) while keeping the adjacent points fixed, and re-optimise the two
   incident legs. The summed positive gains of one full sweep bound how much a
   coordinate-descent move to off-grid points could save. Directly answers
   "is there a better speed choice between two nodes?" for the realised plan.

2. GLOBAL interval lower bound with DDD refinement  [--mode lb]
   Interval relaxation a la Marshall-Boland-Savelsbergh-Hewitt: partition each
   mandatory line into intervals (mandatory crossings are always boundaries, so
   an interval never straddles a weather rectangle); an arc between intervals
   is costed by the MINIMUM fuel over its whole transition family
       c(I->J) = min { phi(rect; v) * dt : p in I, q in J, v = dd/dt in V }.
   Any continuous trajectory maps leg-by-leg into arcs of cost <= its own, so
   the shortest path is a rigorous LOWER bound on the continuous optimum F*.
   Coarse partitions are loose (the family min harvests the free coordinate's
   interval width per hop); DDD refinement bisects the intervals used by the
   current LB path and re-solves, LB_k monotonically nondecreasing.

Usage (from pipeline/dp_rebuild):
    python3 ddd_lb.py --route route2 --sh 0   --mode local
    python3 ddd_lb.py --route route2 --sh 0   --mode lb --rounds 8
"""
from __future__ import annotations

import argparse
import math
import sys
import time
from bisect import bisect_right
from pathlib import Path
from typing import Dict, List, Optional, Tuple

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

import SR_main  # noqa: E402
from atomic_edges import _SWS_MAX_FEASIBLE  # noqa: E402
from frame import from_route as make_frame  # noqa: E402
from nodes import GraphConfig  # noqa: E402
from route import load_route_auto, synthesize_multi_window  # noqa: E402
from run_chain_sweep import ROUTES, _resolve, _build_args  # noqa: E402
from shared.physics import (  # noqa: E402
    calculate_fuel_consumption_rate,
    calculate_sws_from_sog,
)
from weather import VoyageWeather  # noqa: E402

EPS = 1e-9
DT_FLOOR = 1e-6      # relaxed legs must take some time
V_SAMPLES = 96       # v-grid per arc-cost minimisation (+ golden polish)


# ----------------------------------------------------------------------
# phi: fuel rate at speed v from a given source point, EXACTLY the DP's
# convention (cell from src_d, block from src_t, NaN walkback over sample
# hours, SWS feasibility gate).
# ----------------------------------------------------------------------

class PhiOracle:
    def __init__(self, frame):
        self.frame = frame
        self.cache: Dict[Tuple[float, int], object] = {}

    def weather_at(self, src_d: float, src_t: float):
        sh_list = self.frame.voyage.sample_hours
        sh_base = self.frame.base_sample_hour if self.frame.base_sample_hour else None
        sh = self.frame.voyage.active_sample_hour(src_t, sh_base=sh_base)
        key = (round(src_d, 6), sh)
        if key in self.cache:
            return self.cache[key]
        wx = self.frame.cell_weather_at(src_d, sh, None)
        if wx.has_nan():
            idx = bisect_right(sh_list, sh) - 1
            while idx > 0 and wx.has_nan():
                idx -= 1
                wx = self.frame.cell_weather_at(src_d, sh_list[idx], None)
        self.cache[key] = None if wx.has_nan() else wx
        return self.cache[key]

    def phi(self, src_d: float, src_t: float, v: float) -> float:
        """Fuel rate (mt/h) at speed v from source (src_d, src_t); inf if infeasible."""
        wx = self.weather_at(src_d, src_t)
        if wx is None or v <= 0:
            return math.inf
        wd = {
            "wind_speed_10m_kmh": wx.wind_speed_10m_kmh,
            "wind_direction_10m_deg": wx.wind_direction_10m_deg,
            "beaufort_number": wx.beaufort_number,
            "wave_height_m": wx.wave_height_m,
            "ocean_current_velocity_kmh": wx.ocean_current_velocity_kmh,
            "ocean_current_direction_deg": wx.ocean_current_direction_deg,
        }
        heading = self.frame.paper_heading_at(src_d)
        sws = calculate_sws_from_sog(target_sog=v, weather=wd,
                                     ship_heading_deg=heading, ship_parameters=None)
        if sws != sws or sws > _SWS_MAX_FEASIBLE:
            return math.inf
        return calculate_fuel_consumption_rate(sws)


def build_frame(route_key: str, sh_base: int):
    cfg_r = ROUTES[route_key]
    args = _build_args(cfg_r, sh_base, node_first=True)
    route, wps = load_route_auto(Path(args.yaml), eta_h=args.eta)
    route = synthesize_multi_window(route, window_h=6.0)
    cfg = GraphConfig.from_route(route)
    cfg.eta_h = float(args.eta)
    if route.windows:
        route.windows[-1].end = float(args.eta)
        route = synthesize_multi_window(route, window_h=6.0)
    mean_sog = cfg.length_nm / cfg.eta_h
    cfg.v_min, cfg.v_max = mean_sog - 3.0, mean_sog + 3.0
    voyage = VoyageWeather(Path(args.h5))
    frame = make_frame(route, voyage, wps, cfg=cfg, base_sample_hour=sh_base)
    return frame, args, voyage


# ======================================================================
# MODE 1 — local node-slide certificate
# ======================================================================

def golden_min(f, lo: float, hi: float, iters: int = 60) -> Tuple[float, float]:
    """Golden-section min of f on [lo,hi] with a coarse presample guard."""
    n = 33
    xs = [lo + (hi - lo) * k / (n - 1) for k in range(n)]
    vals = [f(x) for x in xs]
    k0 = min(range(n), key=lambda k: vals[k])
    a = xs[max(0, k0 - 1)]
    b = xs[min(n - 1, k0 + 1)]
    g = (math.sqrt(5) - 1) / 2
    c, d = b - g * (b - a), a + g * (b - a)
    fc, fd = f(c), f(d)
    for _ in range(iters):
        if fc < fd:
            b, d, fd = d, c, fc
            c = b - g * (b - a)
            fc = f(c)
        else:
            a, c, fc = c, d, fd
            d = a + g * (b - a)
            fd = f(d)
    x = (a + b) / 2
    return x, min(f(x), vals[k0])


def local_certificate(route_key: str, sh_base: int) -> None:
    frame, args, voyage = build_frame(route_key, sh_base)
    res = SR_main.solve(args, voyage=voyage, verbose=False)
    sched = res["schedule"]
    F = res["total_fuel_mt"]
    oracle = PhiOracle(frame)
    vmin, vmax = frame.cfg.v_min, frame.cfg.v_max
    T = frame.cfg.eta_h

    def leg_fuel(p, q):
        dd, dt = q[0] - p[0], q[1] - p[1]
        if dd <= EPS or dt <= DT_FLOOR:
            return math.inf
        v = dd / dt
        if v < vmin - 1e-9 or v > vmax + 1e-9:
            return math.inf
        ph = oracle.phi(p[0], p[1], v)
        return ph * dt

    pts = [(sched[0].src_d, sched[0].src_t)] + [(e.dst_d, e.dst_t) for e in sched]
    gains, details = [], []
    for k in range(1, len(pts) - 1):
        p, q, r = pts[k - 1], pts[k], pts[k + 1]
        on_h = any(abs(q[0] - d) < 1e-6 for d in frame.h_line_distances)  # distance line?
        base = leg_fuel(p, q) + leg_fuel(q, r)
        if not math.isfinite(base):
            continue
        if on_h and abs(q[0] - r[0]) > EPS and abs(q[0] - p[0]) > EPS:
            # slide arrival TIME along the distance line, within (p.t, r.t)
            lo, hi = p[1] + DT_FLOOR, min(r[1] - DT_FLOOR, T)
            if hi - lo < 1e-6:
                continue
            fn = lambda tt: leg_fuel(p, (q[0], tt)) + leg_fuel((q[0], tt), r)
            _, best = golden_min(fn, lo, hi)
        elif not on_h and abs(q[1] - r[1]) > EPS and abs(q[1] - p[1]) > EPS:
            # slide DISTANCE along the time line, within (p.d, r.d)
            lo, hi = p[0] + EPS, r[0] - EPS
            if hi - lo < 1e-6:
                continue
            fn = lambda dd: leg_fuel(p, (dd, q[1])) + leg_fuel((dd, q[1]), r)
            _, best = golden_min(fn, lo, hi)
        else:
            continue
        gain = max(0.0, base - best)
        gains.append(gain)
        if gain > 1e-6:
            details.append((k, q, gain))

    total = sum(gains)
    print(f"\nLOCAL node-slide certificate — {route_key} sh={sh_base}")
    print(f"  F_DP                    : {F:.3f} mt   ({len(pts)} points, {len(gains)} slid)")
    print(f"  max single-node gain    : {max(gains) if gains else 0.0:.5f} mt")
    print(f"  one-sweep total gain    : {total:.5f} mt  = {total / F * 100:.4f}% of F_DP")
    print(f"  (bound on what continuous coordinate-descent recovers in one sweep;")
    print(f"   each leg counted in two node moves -> pairwise-independent bound ~ half)")
    for k, q, g in sorted(details, key=lambda x: -x[2])[:8]:
        print(f"    node {k:4d} at (d={q[0]:9.3f}, t={q[1]:8.3f}): gain {g:.5f} mt")


# ======================================================================
# MODE 2 — global interval lower bound + DDD refinement
# ======================================================================

class Iv:
    """Interval state on a mandatory line.

    kind 'D': on distance line d = H[i]; free coord = time,   box = [lo, hi].
    kind 'T': on time line   t = V[j]; free coord = distance, box = [lo, hi].
    """
    __slots__ = ("kind", "i", "j", "lo", "hi", "cost", "parent")

    def __init__(self, kind, i, j, lo, hi):
        self.kind, self.i, self.j, self.lo, self.hi = kind, i, j, lo, hi
        self.cost = math.inf
        self.parent = None

    def rep(self, H, V) -> Tuple[float, float]:
        """A representative interior source point (d, t) — fixes phi's rectangle.

        Index semantics: kind 'D' -> (.i = distance-line idx, .j = block idx);
        kind 'T' -> (.i = time-line idx, .j = cell idx), as constructed.
        """
        if self.kind == "D":
            return H[self.i], min(self.lo + 1e-6, (self.lo + self.hi) / 2)
        return min(self.lo + 1e-6, (self.lo + self.hi) / 2), V[self.i]

    def box(self, H, V) -> Tuple[float, float, float, float]:
        """(d_lo, d_hi, t_lo, t_hi) closed box."""
        if self.kind == "D":
            return H[self.i], H[self.i], self.lo, self.hi
        return self.lo, self.hi, V[self.i], V[self.i]

def arc_cost(src_box, dst_box, phi_of_v, vmin, vmax, lam: float = 0.0) -> float:
    """min over p in src, q in dst, v = dd/dt in [vmin,vmax] of (phi(v)+lam)*dt.

    lam >= 0 is a Lagrangian price on charged time: for any lam, the resulting
    shortest path value minus lam*T is a valid lower bound on F* (the true
    trajectory pays fuel + lam*arrival - lam*T <= fuel)."""
    sd0, sd1, st0, st1 = src_box
    dd0, dd1, dt0, dt1 = dst_box
    d_lo = max(0.0, dd0 - sd1)
    d_hi = dd1 - sd0
    t_lo = max(DT_FLOOR, dt0 - st1)
    t_hi = dt1 - st0
    if d_hi < d_lo - EPS or t_hi < t_lo - EPS:
        return math.inf
    best = math.inf
    for k in range(V_SAMPLES + 1):
        v = vmin + (vmax - vmin) * k / V_SAMPLES
        # dt feasible range at this v:  dd = v*dt in [d_lo, d_hi]
        lo = max(t_lo, d_lo / v if v > 0 else math.inf)
        hi = min(t_hi, d_hi / v if v > 0 else 0.0)
        if lo > hi + EPS:
            continue
        ph = phi_of_v(v)
        if math.isfinite(ph):
            best = min(best, (ph + lam) * lo)
    return best


def global_lb(route_key: str, sh_base: int, rounds: int, f_dp: Optional[float]) -> None:
    frame, args, voyage = build_frame(route_key, sh_base)
    oracle = PhiOracle(frame)
    H = list(frame.h_line_distances)          # d_0 .. d_M = L
    V = list(frame.v_line_times)              # t_0 .. t_Theta = T
    if abs(H[0]) > EPS:
        H = [0.0] + H
    if abs(V[0]) > EPS:
        V = [0.0] + V
    L, T = frame.cfg.length_nm, frame.cfg.eta_h
    vmin, vmax = frame.cfg.v_min, frame.cfg.v_max
    M, TH = len(H) - 1, len(V) - 1
    print(f"GLOBAL interval LB — {route_key} sh={sh_base}: M={M} distance lines, "
          f"Theta={TH} blocks, band=[{vmin:.2f},{vmax:.2f}]")

    # ---- interval store: per (kind, line-index, block/cell-index) a sorted list of Iv
    store: Dict[Tuple[str, int, int], List[Iv]] = {}
    for i in range(1, M + 1):                       # distance lines d_1..d_M
        for j in range(TH):                          # block j: t in [V[j], V[j+1]]
            store[("D", i, j)] = [Iv("D", i, j, V[j], V[j + 1])]
    for j in range(1, TH):                           # time lines t_1..t_{Th-1}
        for i in range(M):                           # cell i: d in [H[i], H[i+1]]
            store[("T", j, i)] = [Iv("T", j, i, H[i], H[i + 1])]

    phi_grid_cache: Dict[Tuple[float, float], List[float]] = {}

    def phi_of_v_fn(rep):
        key = (round(rep[0], 6), round(rep[1], 4))
        if key not in phi_grid_cache:
            grid = [oracle.phi(rep[0], rep[1], vmin + (vmax - vmin) * k / V_SAMPLES)
                    for k in range(V_SAMPLES + 1)]
            phi_grid_cache[key] = grid
        grid = phi_grid_cache[key]
        return lambda v: grid[int(round((v - vmin) / (vmax - vmin) * V_SAMPLES))]

    def successors(iv: Iv):
        """Destination interval GROUPS (lists in store) reachable from iv."""
        out = []
        if iv.kind == "D":
            i, j = iv.i, iv.j
            if i + 1 <= M:
                out.append(("D", i + 1, j))
                if j + 1 <= TH - 1:
                    out.append(("D", i + 1, j + 1))          # corner
            if j + 1 <= TH - 1 and i <= M - 1:
                out.append(("T", j + 1, i))
        else:
            j, i = iv.i, iv.j   # T: .i = time-line idx, .j = cell idx
            if i + 1 <= M:
                out.append(("D", i + 1, j))
                if j + 1 <= TH - 1:
                    out.append(("D", i + 1, j + 1))
            if j + 1 <= TH - 1:
                out.append(("T", j + 1, i))
        return [k for k in out if k in store]

    def solve(lam: float = 0.0) -> Tuple[float, List[Iv]]:
        ivs: List[Iv] = [iv for lst in store.values() for iv in lst]
        for iv in ivs:
            iv.cost, iv.parent = math.inf, None
        # topological order: stage = i + j — every arc advances a line index
        # (D(i,j)->D(i+1,*)/T(j+1,i); T(j,i)->D(i+1,*)/T(j+1,i)), so sorting by
        # stage is a valid DAG order even after intervals are bisected.
        def order(iv: Iv):
            return (iv.i + iv.j, iv.kind, iv.lo)
        ivs.sort(key=order)
        # source arcs from origin (0,0)
        origin_box = (0.0, 0.0, 0.0, 0.0)
        origin = Iv("D", 0, -1, 0.0, 0.0)   # synthetic
        origin.cost = 0.0
        rep0 = (0.0, 0.0)
        for key in [("D", 1, 0), ("D", 1, 1), ("T", 1, 0)]:
            if key not in store:
                continue
            for dst in store[key]:
                c = arc_cost(origin_box, dst.box(H, V), phi_of_v_fn(rep0), vmin, vmax, lam)
                if c < dst.cost:
                    dst.cost, dst.parent = c, origin
        # sweep
        for iv in ivs:
            if not math.isfinite(iv.cost) or (iv.kind == "D" and iv.i == M):
                continue
            fv = phi_of_v_fn(iv.rep(H, V))
            sb = iv.box(H, V)
            for key in successors(iv):
                for dst in store.get(key, []):
                    c = arc_cost(sb, dst.box(H, V), fv, vmin, vmax, lam)
                    if iv.cost + c < dst.cost - 1e-12:
                        dst.cost, dst.parent = iv.cost + c, iv
        # sinks: distance line M, any block (t_lo <= T by construction)
        best, best_iv = math.inf, None
        for j in range(TH):
            for iv in store.get(("D", M, j), []):
                if iv.cost < best:
                    best, best_iv = iv.cost, iv
        path = []
        cur = best_iv
        while cur is not None and cur.j != -1:
            path.append(cur)
            cur = cur.parent
        return best, list(reversed(path))

    def lagrangian_lb() -> Tuple[float, float, List[Iv]]:
        """max over lam >= 0 of [solve(lam) - lam*T] (golden search)."""
        def val(lam):
            v, pth = solve(lam)
            return v - lam * T, pth
        best_lam, best_v, best_p = 0.0, -math.inf, None
        # bracket: lam in [0, 3] mt/h (marginal fuel value of an hour)
        lams = [0.0, 0.25, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0]
        vals = []
        for lm in lams:
            v, pth = val(lm)
            vals.append(v)
            if v > best_v:
                best_lam, best_v, best_p = lm, v, pth
        k = vals.index(max(vals))
        a = lams[max(0, k - 1)]; b = lams[min(len(lams) - 1, k + 1)]
        g = (math.sqrt(5) - 1) / 2
        c, d = b - g * (b - a), a + g * (b - a)
        (fc, pc), (fd, pd) = val(c), val(d)
        for _ in range(12):
            if fc > fd:
                b, d, fd, pd = d, c, fc, pc
                c = b - g * (b - a); fc, pc = val(c)
            else:
                a, c, fc, pc = c, d, fd, pd
                d = a + g * (b - a); fd, pd = val(d)
        for lm, v, pth in [(c, fc, pc), (d, fd, pd)]:
            if v > best_v:
                best_lam, best_v, best_p = lm, v, pth
        return best_lam, best_v, best_p

    t0 = time.time()
    lam, lb, path = lagrangian_lb()
    hist = [lb]
    print(f"  LB_0 = {lb:9.3f} mt  (lam*={lam:.2f})  "
          f"({(lb / f_dp * 100 if f_dp else 0):.1f}% of F_DP)   [{time.time()-t0:.0f}s]")
    for r in range(1, rounds + 1):
        # refine: bisect every interval on the LB path (if wide enough)
        n_split = 0
        for iv in path:
            key = (iv.kind, iv.i, iv.j)   # matches store keys for both kinds
            lst = store.get(key)
            if lst is None or iv not in lst:
                continue
            width = iv.hi - iv.lo
            min_w = 1e-3 if iv.kind == "D" else 1e-2      # 0.001 h / 0.01 nm floors
            if width < min_w:
                continue
            mid = (iv.lo + iv.hi) / 2
            lst.remove(iv)
            a = Iv(iv.kind, iv.i, iv.j, iv.lo, mid)
            b = Iv(iv.kind, iv.i, iv.j, mid, iv.hi)
            lst.extend([a, b])
            n_split += 1
        t1 = time.time()
        lam, lb, path = lagrangian_lb()
        hist.append(lb)
        print(f"  LB_{r} = {lb:9.3f} mt  (lam*={lam:.2f})  "
              f"({(lb / f_dp * 100 if f_dp else 0):.1f}% of F_DP)   "
              f"[split {n_split}, {time.time()-t1:.0f}s]")
        if n_split == 0:
            break
    if f_dp:
        print(f"\n  F_DP = {f_dp:.3f} mt   certified gap <= {f_dp - hist[-1]:.3f} mt "
              f"({(f_dp - hist[-1]) / f_dp * 100:.2f}%)")


# ----------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser(prog="ddd_lb")
    ap.add_argument("--route", default="route2", choices=list(ROUTES))
    ap.add_argument("--sh", type=int, default=0)
    ap.add_argument("--mode", default="local", choices=["local", "lb"])
    ap.add_argument("--rounds", type=int, default=6)
    ap.add_argument("--f_dp", type=float, default=None,
                    help="known F_DP for gap reporting (else solved fresh in local mode)")
    a = ap.parse_args()
    if a.mode == "local":
        local_certificate(a.route, a.sh)
    else:
        f_dp = a.f_dp
        if f_dp is None:
            f_dp = {("route2", 0): 202.484, ("route1", 6): 353.955}.get((a.route, a.sh))
        global_lb(a.route, a.sh, a.rounds, f_dp)
    return 0


if __name__ == "__main__":
    sys.exit(main())

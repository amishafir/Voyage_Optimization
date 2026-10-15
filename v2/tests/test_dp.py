"""
The C++ DP (cpp/src/dp.cpp) against a plain-Python DP that builds every node and
arc of the same graph explicitly, on a small archive written with the collector's
own writer. Set V2_ARCHIVE (and V2_START, V2_ETA) to also check a full solve on a
real route archive.

Run from v2/:  python3 tests/test_dp.py
"""

from __future__ import annotations

import math
import os
import sys
import tempfile
from pathlib import Path

import numpy as np

V2 = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(V2), str(V2.parent / "pipeline"), str(Path(__file__).resolve().parent)]

from voyage_v2 import Conditions, CoreError, Ship, Voyage, load_voyage_data, sws_from_sog  # noqa: E402

SHIP = Ship.from_yaml()
from synthetic_route import BEARINGS, ETA_H, LENGTHS, START, write_archive  # noqa: E402


# ---------------------------------------------------------------------------
# The graph, stated plainly
# ---------------------------------------------------------------------------

def merge(lengths, min_nm):
    """[(length, first, count, dominant)]: the shortest piece below min_nm joins its
    shorter neighbour (the earlier on ties) until none is left."""
    p = [(l, i, 1, i) for i, l in enumerate(lengths)]
    while len(p) > 1:
        i = min(range(len(p)), key=lambda q: p[q][0])
        if p[i][0] >= min_nm:
            break
        j = 1 if i == 0 else i - 1 if i == len(p) - 1 else (i - 1 if p[i - 1][0] <= p[i + 1][0] else i + 1)
        lo = min(i, j)
        a, b = p[lo], p[lo + 1]
        dom = a[3] if lengths[a[3]] >= lengths[b[3]] else b[3]
        p[lo:lo + 2] = [(a[0] + b[0], a[1], a[2] + b[2], dom)]
    return p


def reference_dp(voyage, band=3.0, tick_s=4, zeta_m=25.0, merge_nm=0.15, forecast=False):
    data = voyage.data
    lengths = [float(x) for x in data.subsegments["length_nm"]]
    pieces = merge(lengths, merge_nm)
    D = [0.0]
    for p in pieces:
        D.append(D[-1] + p[0])
    n, L, M = len(pieces), D[-1], data.eta_steps
    P, tick_h, zeta, eta_h = 900 // tick_s, tick_s / 3600, zeta_m / 1852, M * 0.25
    vmin, vmax = L / eta_h - band, L / eta_h + band
    in_band = lambda v: vmin - 1e-9 <= v <= vmax + 1e-9

    BEAR = [float(x) for x in data.subsegments["bearing_deg"]]
    # the subsegments of each merged segment, with their extent along the route
    parts = []
    for s, (length, first, count, dom) in enumerate(pieces):
        lo, ps = D[s], []
        for q in range(count):
            hi = D[s + 1] if q == count - 1 else lo + lengths[first + q]
            ps.append((first + q, lo, hi))
            lo = hi
        parts.append(ps)
    conds = {}

    def piece_fcr(sub, m, sog):
        """FCR of subsegment sub at SOG sog in step m; inf outside the vessel's SWS range."""
        if (sub, m) not in conds:
            d = voyage.arc_detail(sub, 12.0, m, 0 if forecast else m)
            conds[sub, m] = Conditions(d["wind_speed_kmh"], d["wind_from_deg"], d["current_speed_kmh"],
                                       d["current_to_deg"])
        sws = sws_from_sog(SHIP, sog, BEAR[sub], conds[sub, m])
        return SHIP.fcr_coefficient * sws ** 3 if 2 <= sws <= 25 else math.inf

    def fuel(s, m, x0, x1, sog, dt):
        """Each piece of segment s at its own fuel rate for its share of [x0, x1]."""
        if not in_band(sog):
            return math.inf
        rate = 0.0
        for sub, lo, hi in parts[s]:
            share = (min(x1, hi) - max(x0, lo)) / (x1 - x0)
            if share > 1e-12:
                rate += piece_fcr(sub, m, sog) * share
        return rate * dt
    # windows: reachable within the band, still able to arrive by the ETA
    dwin = {0: (0, 0)}
    for k in range(1, n + 1):
        t_hi = min(D[k] / vmin, eta_h - (L - D[k]) / vmax)
        dwin[k] = (math.ceil(D[k] / vmax / tick_h - 1e-9), math.floor(t_hi / tick_h + 1e-9))
    twin = {}
    for m in range(1, M):
        t = m * 0.25
        lo = math.ceil(max(vmin * t, L - vmax * (eta_h - t)) / zeta - 1e-9)
        hi = math.floor(min(vmax * t, L) / zeta + 1e-9)
        while hi * zeta >= L:
            hi -= 1
        twin[m] = (lo, hi)

    nodes = [("D", k, j) for k in dwin for j in range(dwin[k][0], dwin[k][1] + 1)]
    nodes += [("T", m, i) for m in twin for i in range(twin[m][0], twin[m][1] + 1)]
    time_of = lambda nd: nd[2] * tick_h if nd[0] == "D" else nd[1] * 0.25
    nodes.sort(key=time_of)
    cost = {nd: math.inf for nd in nodes}
    cost[("D", 0, 0)] = 0.0
    arcs = {}

    def relax(a, b, f):
        arcs[a, b] = f
        if cost[a] + f < cost[b]:
            cost[b] = cost[a] + f

    for nd in nodes:
        if nd[0] == "D" and nd[1] == n or cost[nd] == math.inf:
            continue
        if nd[0] == "D":
            k, j = nd[1], nd[2]
            s, m, d0 = k, j // P, D[k]
            t_next = (m + 1) * P
            for jp in range(max(dwin[k + 1][0], j + 1), min(dwin[k + 1][1], t_next) + 1):
                dt = (jp - j) * tick_h
                relax(nd, ("D", k + 1, jp), fuel(s, m, D[k], D[k + 1], pieces[s][0] / dt, dt))
            if m + 1 < M:
                dt = (t_next - j) * tick_h
                for ip in range(twin[m + 1][0], twin[m + 1][1] + 1):
                    if d0 < ip * zeta < D[k + 1]:
                        relax(nd, ("T", m + 1, ip), fuel(s, m, d0, ip * zeta, (ip * zeta - d0) / dt, dt))
        else:
            m, i = nd[1], nd[2]
            d0 = i * zeta
            s = max(q for q in range(n) if D[q] <= d0)
            r = D[s + 1] - d0
            for jp in range(max(dwin[s + 1][0], m * P + 1), min(dwin[s + 1][1], (m + 1) * P) + 1):
                dt = (jp - m * P) * tick_h
                relax(nd, ("D", s + 1, jp), fuel(s, m, d0, D[s + 1], r / dt, dt))
            if m + 1 < M:
                for ip in range(twin[m + 1][0], twin[m + 1][1] + 1):
                    if d0 < ip * zeta < D[s + 1]:
                        relax(nd, ("T", m + 1, ip), fuel(s, m, d0, ip * zeta, (ip - i) * zeta / 0.25, 0.25))
    best = min((cost[("D", n, j)] for j in range(dwin[n][0], dwin[n][1] + 1)), default=math.inf)
    # every piece at the mean SOG, split at the time lines, in its own weather
    vbar, const = L / eta_h, 0.0
    for s in range(n):
        for sub, lo, hi in parts[s]:
            t, t_end = lo / vbar, hi / vbar
            while t < t_end - 1e-12:
                m = min(math.floor(t / 0.25 + 1e-9), M - 1)
                t_next = min(t_end, (m + 1) * 0.25)
                const += piece_fcr(sub, m, vbar) * (t_next - t)
                t = t_next
    return dict(fuel=best, pieces=pieces, D=D, nodes=len(nodes), arcs=arcs, tick_h=tick_h, zeta=zeta, P=P,
                reached=sum(c < math.inf for c in cost.values()), constant=const)


def _node_of(ref, t_h, d_nm):
    """The reference node at a plan point: on a distance line if d is a boundary, else on a time line."""
    D = ref["D"]
    k = min(range(len(D)), key=lambda q: abs(D[q] - d_nm))
    if abs(D[k] - d_nm) < 1e-9:
        return ("D", k, round(t_h / ref["tick_h"]))
    return ("T", round(t_h / 0.25), round(d_nm / ref["zeta"]))


def _check_against_reference(plan, ref, actual=None):
    """plan's planned fuel and arcs against ref; its realized fuel against `actual`, the reference
    of the same graph in the actual weather (ref itself when planning used the actual weather)."""
    actual = actual or ref
    assert plan.feasible and math.isfinite(ref["fuel"])
    assert math.isclose(plan.planned_fuel_mt, ref["fuel"], rel_tol=1e-10), (plan.planned_fuel_mt, ref["fuel"])
    P = plan.path
    for q in range(len(P["fuel_mt"])):             # every plan arc is an arc of the reference graph, same fuel
        a = _node_of(ref, P["t0_h"][q], P["d0_nm"][q])
        b = _node_of(ref, P["t1_h"][q], P["d1_nm"][q])
        assert (a, b) in ref["arcs"], (q, a, b)
        assert math.isclose(P["planned_fuel_mt"][q], ref["arcs"][a, b], rel_tol=1e-12)
        assert math.isclose(P["fuel_mt"][q], actual["arcs"][a, b], rel_tol=1e-12)
    assert math.isclose(P["planned_fuel_mt"].sum(), plan.planned_fuel_mt, rel_tol=1e-12)
    assert math.isclose(P["fuel_mt"].sum(), plan.fuel_mt, rel_tol=1e-12)
    assert math.isclose(plan.constant_sog_fuel_mt, actual["constant"], rel_tol=1e-10)
    if actual is ref:
        assert plan.fuel_mt == plan.planned_fuel_mt


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

_TMP = tempfile.TemporaryDirectory()
ARCHIVE = os.path.join(_TMP.name, "test_runs.h5")
write_archive(ARCHIVE)
VOYAGE = Voyage(load_voyage_data(ARCHIVE, START, ETA_H), SHIP)


def test_merge_matches_reference():
    plan = VOYAGE.solve()
    ref = merge(LENGTHS, 0.15)
    assert [(p[1], p[2], p[3]) for p in ref] == list(zip(plan.segments["first_sub"], plan.segments["n_subs"],
                                                          plan.segments["dominant_sub"]))
    assert np.allclose(plan.segments["length_nm"], [p[0] for p in ref], rtol=0, atol=1e-12)
    assert plan.segments["length_nm"].min() >= 0.15


def test_merged_segments_are_priced_piece_by_piece():
    # the merged pieces of the test route have their own bearings and cells, so pricing a
    # merged segment with its longest piece alone would change the optimum
    ref = reference_dp(VOYAGE)
    assert any(p[2] > 1 for p in ref["pieces"])
    plan = VOYAGE.solve()
    on_merged = np.isin(plan.path["segment"], [s for s, p in enumerate(ref["pieces"]) if p[2] > 1])
    assert on_merged.any()


def test_optimal_pseudo_real_time():
    _check_against_reference(VOYAGE.solve(), reference_dp(VOYAGE))


def test_optimal_forecast_from_the_start():
    # planned in the forecast known at the start, realized in the actual weather
    _check_against_reference(VOYAGE.solve(forecast=True), reference_dp(VOYAGE, forecast=True), reference_dp(VOYAGE))


def test_optimal_on_a_coarse_grid():
    kw = dict(tick_s=60, zeta_m=200.0, merge_nm=1.0, band=2.0)
    plan = VOYAGE.solve(sog_band_kn=kw["band"], tick_s=kw["tick_s"], zeta_m=kw["zeta_m"], merge_nm=kw["merge_nm"])
    _check_against_reference(plan, reference_dp(VOYAGE, **kw))


def test_node_count_matches_reference():
    plan, ref = VOYAGE.solve(), reference_dp(VOYAGE)
    assert plan.stats["nodes"] == ref["nodes"] and plan.stats["reached_nodes"] == ref["reached"]


def test_plan_is_a_valid_voyage():
    plan = VOYAGE.solve()
    P = plan.path
    assert P["t0_h"][0] == 0 and P["d0_nm"][0] == 0
    assert np.all(P["t0_h"][1:] == P["t1_h"][:-1]) and np.all(P["d0_nm"][1:] == P["d1_nm"][:-1])
    assert math.isclose(P["d1_nm"][-1], sum(LENGTHS), rel_tol=1e-12) and P["t1_h"][-1] <= ETA_H + 1e-12
    assert np.all((P["sog_kn"] >= plan.v_min_kn - 1e-9) & (P["sog_kn"] <= plan.v_max_kn + 1e-9))
    assert np.all((P["sws_kn"] >= 2) & (P["sws_kn"] <= 25))
    assert np.all(np.floor(P["t0_h"] * 4 + 1e-9) == P["step"])          # every arc inside one weather step
    assert np.all(P["t1_h"] <= (P["step"] + 1) * 0.25 + 1e-12)


def test_too_short_segment_is_refused():
    # 300 s ticks need segments of about 0.49 NM at this route's 3.7-9.7 kn band; one is 0.31 NM
    try:
        VOYAGE.solve(tick_s=300, zeta_m=200.0)
        raise AssertionError("expected a refusal")
    except CoreError as e:
        assert "merge" in str(e)


def test_real_archive():
    path = os.environ.get("V2_ARCHIVE")
    if not path:
        print("    (skipped: set V2_ARCHIVE to a route archive)")
        return
    data = load_voyage_data(path, os.environ.get("V2_START", "2026-10-14 13:20"), float(os.environ.get("V2_ETA", "280")))
    plan = Voyage(data, SHIP).solve()
    P = plan.path
    L = float(data.subsegments["length_nm"].sum())
    assert plan.feasible and P["t0_h"][0] == 0 and P["d0_nm"][0] == 0
    assert np.all(P["t0_h"][1:] == P["t1_h"][:-1]) and np.all(P["d0_nm"][1:] == P["d1_nm"][:-1])
    assert math.isclose(P["d1_nm"][-1], L, rel_tol=1e-9) and P["t1_h"][-1] <= data.eta_steps / 4 + 1e-12
    assert np.all((P["sog_kn"] >= plan.v_min_kn - 1e-9) & (P["sog_kn"] <= plan.v_max_kn + 1e-9))
    assert np.all((P["sws_kn"] >= 2) & (P["sws_kn"] <= 25))
    assert math.isclose(P["fuel_mt"].sum(), plan.fuel_mt, rel_tol=1e-12)
    assert plan.fuel_mt <= plan.constant_sog_fuel_mt
    print(f"    {Path(path).name}: {plan.fuel_mt:.3f} mt (constant SOG {plan.constant_sog_fuel_mt:.3f}), "
          f"{plan.stats['nodes'] / 1e6:.1f} M nodes, {plan.stats['arcs'] / 1e9:.2f} G arcs, "
          f"sweep {plan.stats['sweep_s']:.0f} s")


if __name__ == "__main__":
    tests = [(n, f) for n, f in sorted(globals().items()) if n.startswith("test_")]
    for name, fn in tests:
        fn()
        print(f"ok  {name}")
    print(f"{len(tests)} passed")

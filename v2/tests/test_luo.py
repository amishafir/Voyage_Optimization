"""
The C++ Luo et al. multistage DP (cpp/src/luo.cpp) against a plain-Python DP over
the same graph, on the small synthetic archive. The reference integrates each arc
its own way: it sorts every cut point (subsegment boundaries and the positions
where the ship crosses a weather step) and prices each piece by its midpoint. Set
V2_ARCHIVE (and V2_START, V2_ETA) to also check a solve on a real route archive.

Run from v2/:  python3 tests/test_luo.py
"""

from __future__ import annotations

import bisect
import math
import os
import sys
import tempfile
from pathlib import Path

import numpy as np

V2 = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(V2), str(V2.parent / "pipeline"), str(Path(__file__).resolve().parent)]

from synthetic_route import ETA_H, LENGTHS, SHIP, START, write_archive  # noqa: E402
from voyage_v2 import Conditions, CoreError, Voyage, load_voyage_data, sws_from_sog  # noqa: E402


def reference_luo(voyage, epoch_steps=24, dist_step_nm=None, band=3.0, forecast=False):
    data = voyage.data
    lengths = [float(x) for x in data.subsegments["length_nm"]]
    bearing = [float(x) for x in data.subsegments["bearing_deg"]]
    S = [0.0]
    for l in lengths:
        S.append(S[-1] + l)
    L, M = S[-1], data.eta_steps
    eta_h = M * 0.25
    vmin, vmax = L / eta_h - band, L / eta_h + band
    delta = dist_step_nm or 0.1 * epoch_steps * 0.25
    steps = list(range(0, M, epoch_steps)) + [M]
    conds = {}

    def fcr(sub, step, v):
        if (sub, step) not in conds:
            d = voyage.arc_detail(sub, 12.0, step, 0 if forecast else step)
            conds[sub, step] = Conditions(d["wind_speed_kmh"], d["wind_from_deg"], d["current_speed_kmh"],
                                          d["current_to_deg"])
        sws = sws_from_sog(SHIP, v, bearing[sub], conds[sub, step])
        return SHIP.fcr_coefficient * sws ** 3 if 2 <= sws <= 25 else math.inf

    def path_fuel(d0, d1, v, step0, n_steps):
        if not vmin - 1e-9 <= v <= vmax + 1e-9:
            return math.inf
        cuts = {d0, d1} | {x for x in S if d0 < x < d1}
        cuts |= {d0 + v * 0.25 * k for k in range(1, n_steps) if d0 < d0 + v * 0.25 * k < d1}
        cuts = sorted(cuts)
        fuel = 0.0
        for a, b in zip(cuts, cuts[1:]):
            mid = (a + b) / 2
            sub = min(bisect.bisect_right(S, mid) - 1, len(lengths) - 1)
            step = step0 + min(int((mid - d0) / v / 0.25), n_steps - 1)
            fuel += fcr(sub, step, v) * (b - a) / v
        return fuel

    def window(step):
        t = step * 0.25
        lo = math.ceil(max(vmin * t, L - vmax * (eta_h - t)) / delta - 1e-9)
        hi = min(math.floor(min(vmax * t, L) / delta + 1e-9), math.ceil(L / delta - 1e-9) - 1)
        return range(lo, hi + 1)

    cost = {(0, 0): 0.0}
    arrive = {}
    nodes = 1
    for e in range(len(steps) - 1):
        n_steps = steps[e + 1] - steps[e]
        dt = n_steps * 0.25
        nxt = window(steps[e + 1]) if steps[e + 1] < M else range(0)
        nodes += len(nxt)
        for (ee, i), c in sorted(cost.items()):
            if ee != e:
                continue
            d0 = 0.0 if e == 0 else i * delta
            for ip in nxt:
                f = path_fuel(d0, ip * delta, (ip * delta - d0) / dt, steps[e], n_steps)
                if c + f < cost.get((e + 1, ip), math.inf):
                    cost[e + 1, ip] = c + f
            f = path_fuel(d0, L, (L - d0) / dt, steps[e], n_steps)
            arrive[e + 1] = min(arrive.get(e + 1, math.inf), c + f)
    best = min(arrive.values())
    return dict(fuel=best, nodes=nodes, path_fuel=path_fuel, steps=steps, delta=delta)


def _check(plan, ref):
    assert plan.feasible and math.isfinite(ref["fuel"])
    assert math.isclose(plan.fuel_mt, ref["fuel"], rel_tol=1e-10), (plan.fuel_mt, ref["fuel"])
    assert plan.stats["nodes"] == ref["nodes"]
    P = plan.path
    for q in range(len(P["fuel_mt"])):             # every plan arc, priced by the reference integration
        e = ref["steps"].index(int(round(P["t0_h"][q] * 4)))
        n_steps = ref["steps"][e + 1] - ref["steps"][e]
        f = ref["path_fuel"](P["d0_nm"][q], P["d1_nm"][q], P["sog_kn"][q], ref["steps"][e], n_steps)
        assert math.isclose(P["fuel_mt"][q], f, rel_tol=1e-10), (q, P["fuel_mt"][q], f)
    assert math.isclose(P["fuel_mt"].sum(), plan.fuel_mt, rel_tol=1e-12)
    assert np.all(P["t0_h"][1:] == P["t1_h"][:-1]) and np.all(P["d0_nm"][1:] == P["d1_nm"][:-1])
    assert P["t0_h"][0] == 0 and P["d0_nm"][0] == 0
    assert math.isclose(P["d1_nm"][-1], sum(LENGTHS), rel_tol=1e-12)


_TMP = tempfile.TemporaryDirectory()
ARCHIVE = os.path.join(_TMP.name, "test_runs.h5")
write_archive(ARCHIVE)
VOYAGE = Voyage(load_voyage_data(ARCHIVE, START, ETA_H), SHIP)      # ETA 1.5 h = 6 steps


def test_epochs_dividing_the_eta():
    _check(VOYAGE.solve_luo(epoch_steps=2), reference_luo(VOYAGE, epoch_steps=2))


def test_partial_last_epoch():
    _check(VOYAGE.solve_luo(epoch_steps=4), reference_luo(VOYAGE, epoch_steps=4))     # 1 h + 0.5 h


def test_quarter_hour_epochs():
    _check(VOYAGE.solve_luo(epoch_steps=1), reference_luo(VOYAGE, epoch_steps=1))


def test_given_distance_step():
    _check(VOYAGE.solve_luo(epoch_steps=2, dist_step_nm=0.13), reference_luo(VOYAGE, epoch_steps=2, dist_step_nm=0.13))


def test_forecast_from_the_start():
    _check(VOYAGE.solve_luo(epoch_steps=2, forecast=True), reference_luo(VOYAGE, epoch_steps=2, forecast=True))


def test_one_epoch_is_constant_speed():
    plan = VOYAGE.solve_luo(epoch_steps=6)                 # one 1.5 h epoch: the only plan is the mean SOG
    assert len(plan.path["fuel_mt"]) == 1 and plan.arrival_h == ETA_H
    assert math.isclose(plan.fuel_mt, plan.constant_sog_fuel_mt, rel_tol=1e-9)


def test_default_distance_step_is_a_tenth_of_a_knot():
    plan = VOYAGE.solve_luo(epoch_steps=2)                 # 0.5 h epochs: 0.05 NM
    sog = plan.path["sog_kn"][:-1]                         # the arrival arc's SOG is whatever reaches L
    assert np.allclose(sog * 10, np.round(sog * 10), atol=1e-9)


def test_bad_arguments_raise():
    for kw in (dict(epoch_steps=0), dict(dist_step_nm=-1.0), dict(sog_band_kn=0.0)):
        try:
            VOYAGE.solve_luo(**kw)
            raise AssertionError(kw)
        except CoreError:
            pass


def test_real_archive():
    path = os.environ.get("V2_ARCHIVE")
    if not path:
        print("    (skipped: set V2_ARCHIVE to a route archive)")
        return
    data = load_voyage_data(path, os.environ.get("V2_START", "2026-10-14 13:20"), float(os.environ.get("V2_ETA", "280")))
    plan = Voyage(data, SHIP).solve_luo()
    P = plan.path
    L = float(data.subsegments["length_nm"].sum())
    assert plan.feasible and P["t0_h"][0] == 0 and P["d0_nm"][0] == 0
    assert np.all(P["t0_h"][1:] == P["t1_h"][:-1]) and np.all(P["d0_nm"][1:] == P["d1_nm"][:-1])
    assert math.isclose(P["d1_nm"][-1], L, rel_tol=1e-12) and P["t1_h"][-1] <= data.eta_steps / 4
    assert np.all((P["sog_kn"] >= plan.v_min_kn - 1e-9) & (P["sog_kn"] <= plan.v_max_kn + 1e-9))
    assert math.isclose(P["fuel_mt"].sum(), plan.fuel_mt, rel_tol=1e-12)
    print(f"    {Path(path).name}: {plan.fuel_mt:.3f} mt (constant SOG {plan.constant_sog_fuel_mt:.3f}), "
          f"{len(P['fuel_mt'])} epochs, {plan.stats['nodes']:,} nodes, {plan.stats['arcs']:,} arcs, "
          f"sweep {plan.stats['sweep_s']:.1f} s")


if __name__ == "__main__":
    tests = [(n, f) for n, f in sorted(globals().items()) if n.startswith("test_")]
    for name, fn in tests:
        fn()
        print(f"ok  {name}")
    print(f"{len(tests)} passed")

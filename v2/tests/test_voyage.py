"""
Loading a voyage and arc_cost, on a small archive written with the collector's own
writer (pipeline/shared/run_archive.py), against a plain-Python statement of the
weather rules. Set V2_ARCHIVE to a real route archive to compare on it as well.

Run from v2/:  python3 tests/test_voyage.py
"""

from __future__ import annotations

import math
import os
import random
import sys
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

V2 = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(V2), str(V2.parent / "pipeline")]

from shared import run_archive  # noqa: E402
from voyage_v2 import (INFEASIBLE_FUEL_MT, Conditions, CoreError, ReferenceTimeError, Ship, Voyage,  # noqa: E402
                       load_voyage_data, sws_from_sog)
from voyage_v2.loader import eta_to_steps, parse_start, round_to_step  # noqa: E402

SHIP = Ship.from_yaml()
H = 3600
D0 = 1792022400 - 86400            # 2026-10-14 00:00 UTC
N_WIND, N_CURRENT, N_SUB = 3, 2, 6

# (init, hours stored) per grid. With the voyage below (start D0 07:15, ETA 60 h):
#   wind: D-1 00Z reaches past the end, D-1 12Z is overtaken by newer runs, D3 is after the end;
#   current: the D1 run is missed, so D0's last value is held until D2 is issued.
WIND_RUNS = [(D0 - 24 * H, 200), (D0 - 12 * H, 30), (D0, 40), (D0 + 6 * H, 24), (D0 + 12 * H, 72),
             (D0 + 18 * H, 24), (D0 + 24 * H, 72), (D0 + 72 * H, 72)]
CURRENT_RUNS = [(D0 - 24 * H, 48), (D0, 40), (D0 + 48 * H, 48)]
START, ETA_H = "2026-10-14 07:20", 60.0


def _write_archive(path):
    sub = pd.DataFrame({
        "index": range(N_SUB), "leg": 0, "start_nm": np.arange(N_SUB) * 2.0, "length_nm": 2.0,
        "bearing_deg": [10.0, 80.0, 170.0, 200.0, 260.0, 350.0],
        "start_lat": 0.0, "start_lon": 0.0, "mid_lat": 0.0, "mid_lon": 0.0, "end_lat": 0.0, "end_lon": 0.0,
        "wind_cell": [0, 0, 1, 1, 2, 2], "current_cell": [0, 0, 0, 1, 1, 1]})
    cells = {g: pd.DataFrame({"index": range(n), "row": 0, "col": range(n), "grid_lat": 0.0, "grid_lon": 0.0,
                              "query_lat": 0.0, "query_lon": 0.0, "length_nm": 1.0,
                              "first_subsegment": 0, "n_subsegments": 1})
             for g, n in (("wind", N_WIND), ("current", N_CURRENT))}
    run_archive.create_archive(path, sub, cells, {"route_label": "Test", "route_name": "synthetic"})
    rng = np.random.default_rng(7)
    for grid, runs, n, cols, top in (("wind", WIND_RUNS, N_WIND, ("wind_speed_10m_kmh", "wind_direction_10m_deg"), 70),
                                     ("current", CURRENT_RUNS, N_CURRENT,
                                      ("ocean_current_velocity_kmh", "ocean_current_direction_deg"), 5)):
        for init, hours in runs:
            run_archive.write_run(path, grid, init, init + H * np.arange(hours),
                                  {cols[0]: rng.uniform(0, top, (n, hours)), cols[1]: rng.uniform(0, 360, (n, hours))},
                                  np.zeros(n), np.zeros(n))


# ---------------------------------------------------------------------------
# The weather rules, stated plainly
# ---------------------------------------------------------------------------

def _vector(grid, speed, direction):
    sign = -1.0 if grid == "wind" else 1.0
    d = float(direction) * (math.pi / 180)
    return float(np.float32(sign * float(speed) * math.sin(d))), float(np.float32(sign * float(speed) * math.cos(d)))


def reference_sample(data, grid, cell, t, tau):
    """Newest run issued by tau that covers t (interpolated); else the latest value before t."""
    hold = None
    for r in sorted((r for r in data.runs[grid] if r.init_step <= tau), key=lambda r: -r.init_step):
        if r.first_step <= t <= r.last_step:
            h, w = divmod(t - r.first_step, 4)
            e0, n0 = _vector(grid, r.speed[cell, h], r.direction[cell, h])
            if w:
                e1, n1 = _vector(grid, r.speed[cell, h + 1], r.direction[cell, h + 1])
                e0, n0 = e0 + w / 4 * (e1 - e0), n0 + w / 4 * (n1 - n0)
            return e0, n0, r.name, False
        if r.last_step < t and (hold is None or r.last_step > hold.last_step):
            hold = r
    e, n = _vector(grid, hold.speed[cell, -1], hold.direction[cell, -1])
    return e, n, hold.name, True


def reference_arc(data, sub, sog, t, tau):
    s = data.subsegments[sub]
    tau = t if tau is None else tau
    we, wn, wrun, wheld = reference_sample(data, "wind", int(s["wind_cell"]), t, tau)
    ce, cn, crun, cheld = reference_sample(data, "current", int(s["current_cell"]), t, tau)
    c = Conditions(math.hypot(we, wn), math.degrees(math.atan2(-we, -wn)) % 360,
                   math.hypot(ce, cn), math.degrees(math.atan2(ce, cn)) % 360)
    sws = sws_from_sog(SHIP, sog, float(s["bearing_deg"]), c)
    fuel = SHIP.fcr_coefficient * sws ** 3 * float(s["length_nm"]) / sog if 2 <= sws <= 25 else INFEASIBLE_FUEL_MT
    return fuel, c, (wrun, wheld, crun, cheld)


def _compare(voyage, n, seed):
    rng = random.Random(seed)
    data = voyage.data
    held = 0
    for _ in range(n):
        sub = rng.randrange(len(data.subsegments))
        t = rng.randint(0, data.eta_steps)
        tau = None if rng.random() < 0.3 else rng.randint(0, t)
        sog = rng.uniform(8, 16)
        fuel, c, src = reference_arc(data, sub, sog, t, tau)
        d = voyage.arc_detail(sub, sog, t, tau)
        assert (d["wind_run"], d["wind_held"], d["current_run"], d["current_held"]) == src, (sub, t, tau)
        assert math.isclose(d["wind_speed_kmh"], c.wind_speed_kmh, rel_tol=1e-12, abs_tol=1e-9)
        assert math.isclose(d["current_speed_kmh"], c.current_speed_kmh, rel_tol=1e-12, abs_tol=1e-9)
        assert math.isclose(voyage.arc_cost(sub, sog, t, tau), fuel, rel_tol=1e-12), (sub, sog, t, tau)
        held += src[1] or src[3]
    return held


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

_TMP = tempfile.TemporaryDirectory()
ARCHIVE = os.path.join(_TMP.name, "test_runs.h5")
_write_archive(ARCHIVE)
DATA = load_voyage_data(ARCHIVE, START, ETA_H)
VOYAGE = Voyage(DATA, SHIP)


def _name(unix):
    return run_archive.run_name(unix)


def test_start_and_eta():
    assert round_to_step(parse_start("2026-10-14 07:20")) == D0 + 7 * H + 900
    assert round_to_step(parse_start("2026-10-14T07:07:29")) == D0 + 7 * H
    assert round_to_step(parse_start("2026-10-14 07:07:30")) == D0 + 7 * H + 900     # halves round up
    assert round_to_step(parse_start("2026-10-14 7.3")) == D0 + 7 * H + 900          # 07:18
    assert eta_to_steps(280) == 1120 and eta_to_steps(0.25) == 1
    for bad in (0.3, 0, -1):
        try:
            eta_to_steps(bad)
            raise AssertionError(bad)
        except ValueError:
            pass


def test_loads_only_the_runs_the_voyage_can_use():
    assert [r.name for r in DATA.runs["wind"]] == [_name(i) for i, _ in WIND_RUNS if i not in (D0 - 12 * H, D0 + 72 * H)]
    assert [r.name for r in DATA.runs["current"]] == [_name(D0), _name(D0 + 48 * H)]
    end = DATA.end_unix
    for runs in DATA.runs.values():
        for r in runs:
            assert r.first_step == max(r.init_step, -1)                  # the hour before the start: 07:00
            assert DATA.start_unix + 900 * r.last_step <= -(-end // H) * H


def test_start_not_in_the_archive_is_an_error():
    for start in ("2026-10-12 20:00", "2026-10-25 00:00"):
        try:
            load_voyage_data(ARCHIVE, start, 10)
            raise AssertionError(start)
        except ReferenceTimeError as e:
            assert "not covered" in str(e)


def test_arc_cost_matches_the_rules():
    assert _compare(VOYAGE, 4000, seed=1) > 100          # the hold rule is exercised


def test_pseudo_real_time_is_tau_equal_t():
    for sub, t in ((0, 0), (3, 37), (5, DATA.eta_steps)):
        assert VOYAGE.arc_cost(sub, 12.0, t) == VOYAGE.arc_cost(sub, 12.0, t, t)


def test_vectorized_matches_scalar():
    rng = np.random.default_rng(3)
    t = rng.integers(0, DATA.eta_steps + 1, 500)
    tau = np.where(rng.random(500) < 0.5, -1, (t * rng.random(500)).astype(int))
    sub, sog = rng.integers(0, N_SUB, 500), rng.uniform(8, 16, 500)
    out = VOYAGE.arc_costs(sub, sog, t, tau)
    assert all(out[i] == VOYAGE.arc_cost(sub[i], sog[i], t[i], None if tau[i] < 0 else tau[i]) for i in range(500))


def test_sws_outside_2_to_25_knots_costs_9999():
    assert VOYAGE.arc_cost(0, 30.0, 10) == INFEASIBLE_FUEL_MT
    d = VOYAGE.arc_detail(0, 30.0, 10)
    assert not d["feasible"] and d["sws_kn"] > 25
    d = VOYAGE.arc_detail(0, 0.5, 10)
    assert not d["feasible"] and d["fuel_mt"] == INFEASIBLE_FUEL_MT


def test_bad_arguments_raise():
    for args in ((N_SUB, 12.0, 0, None), (0, 12.0, -1, None), (0, 12.0, DATA.eta_steps + 1, None),
                 (0, 12.0, 10, 11), (0, 0.0, 10, None)):
        try:
            VOYAGE.arc_cost(*args)
            raise AssertionError(args)
        except CoreError:
            pass


def test_real_archive():
    path = os.environ.get("V2_ARCHIVE")
    if not path:
        print("    (skipped: set V2_ARCHIVE to a route archive)")
        return
    data = load_voyage_data(path, os.environ.get("V2_START", "2026-10-14 13:20"), float(os.environ.get("V2_ETA", "280")))
    _compare(Voyage(data, SHIP), 3000, seed=2)


if __name__ == "__main__":
    tests = [(n, f) for n, f in sorted(globals().items()) if n.startswith("test_")]
    for name, fn in tests:
        fn()
        print(f"ok  {name}")
    print(f"{len(tests)} passed")

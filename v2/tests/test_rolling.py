"""
Rolling-horizon re-planning (voyage_v2/rolling.py) on the small synthetic archive,
plus a wind run issued during the voyage so that the forecast changes.

Run from v2/:  python3 tests/test_rolling.py
"""

from __future__ import annotations

import math
import sys
import tempfile
from pathlib import Path

import numpy as np

V2 = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(V2), str(V2.parent / "pipeline"), str(Path(__file__).resolve().parent)]

from synthetic_route import D0, ETA_H, H, LENGTHS, N_WIND, SHIP, START, write_archive  # noqa: E402
from shared import run_archive  # noqa: E402
from voyage_v2 import Voyage, load_voyage_data  # noqa: E402
from voyage_v2.rolling import remaining_route, solve_rolling  # noqa: E402

_DIR = tempfile.mkdtemp()
PATH = str(Path(_DIR) / "route.h5")
write_archive(PATH)
# A wind run issued at 08:00, mid-voyage (07:15-08:45), with other winds: the forecast
# known at the start is wrong after 08:00, and the 08:00 decision sees the new run.
run_archive.write_run(PATH, "wind", D0 + 8 * H, D0 + 8 * H + H * np.arange(12),
                      {"wind_speed_10m_kmh": np.random.default_rng(5).uniform(40, 90, (N_WIND, 12)),
                       "wind_direction_10m_deg": np.random.default_rng(6).uniform(0, 360, (N_WIND, 12))},
                      np.zeros(N_WIND), np.zeros(N_WIND))
DATA = load_voyage_data(PATH, START, ETA_H)
VOYAGE = Voyage(DATA, SHIP)
L = sum(LENGTHS)
RANGE = (L / ETA_H - 3.0, L / ETA_H + 3.0)


def check_path(r):
    P = r.path
    assert np.all(P["t0_h"][1:] == P["t1_h"][:-1]) and np.allclose(P["d0_nm"][1:], P["d1_nm"][:-1], atol=1e-12)
    assert P["t0_h"][0] == 0 and P["d0_nm"][0] == 0
    assert math.isclose(P["d1_nm"][-1], L, rel_tol=1e-12) and P["t1_h"][-1] <= ETA_H + 1e-12
    assert np.all((P["sog_kn"] >= RANGE[0] - 1e-9) & (P["sog_kn"] <= RANGE[1] + 1e-9))
    assert math.isclose(P["fuel_mt"].sum(), r.fuel_mt, rel_tol=1e-12)


def test_remaining_route_cuts_the_first_subsegment():
    rest = remaining_route(DATA, 1.5)                   # 0.2 NM into the second subsegment
    assert len(rest) == len(LENGTHS) - 1
    assert math.isclose(rest["length_nm"][0], 0.7) and math.isclose(rest["length_nm"].sum(), L - 1.5)
    assert len(remaining_route(DATA, 1.3)) == len(LENGTHS) - 1     # exactly on a boundary


def test_oracle_replanning_equals_one_perfect_information_plan():
    # Without merging, every re-plan's graph is the original one from the ship's node on, so
    # re-planning with the actual weather sails exactly the perfect-information plan.
    for method, opts, ref in (("full", {"merge_nm": 0.0}, VOYAGE.solve(sog_range_kn=RANGE, merge_nm=0.0)),
                              ("luo", {"epoch_steps": 1}, VOYAGE.solve_luo(epoch_steps=1, sog_range_kn=RANGE))):
        for every in (0.25, 0.5):
            r = solve_rolling(PATH, START, ETA_H, method, every_h=every, forecast=False, ship=SHIP, **opts)
            check_path(r)
            assert math.isclose(r.fuel_mt, ref.fuel_mt, rel_tol=1e-12), (method, every, r.fuel_mt, ref.fuel_mt)
    # With merging (0.15 NM), a re-plan made less than 0.15 NM before a segment boundary merges the
    # cut piece with the next segment and loses that boundary's nodes: here 3.90 NM, 0.08 NM short
    # of 3.98 NM, at the 0.5 h decision of the 0.25 h clock.
    ref = VOYAGE.solve(sog_range_kn=RANGE)
    r = solve_rolling(PATH, START, ETA_H, "full", every_h=0.25, forecast=False, ship=SHIP)
    check_path(r)
    assert ref.fuel_mt <= r.fuel_mt <= ref.fuel_mt * (1 + 1e-4)


def test_forecast_replanning():
    perfect = VOYAGE.solve(sog_range_kn=RANGE)
    once = VOYAGE.solve(forecast=True, sog_range_kn=RANGE)
    assert once.fuel_mt > perfect.fuel_mt * (1 + 1e-6)          # the 08:00 run makes the start forecast wrong
    r = solve_rolling(PATH, START, ETA_H, "full", every_h=0.25, ship=SHIP)
    check_path(r)
    assert [round(x.t_h, 9) for x in r.decisions] == [0, 0.25, 0.5, 0.75, 1.0, 1.25]
    # Until the 08:00 run is issued (0.75 h in) every decision knows what the first did, so it sails the
    # first plan; from 0.75 h on the forecast is the actual weather, so the plan is optimal from there.
    first = once.path
    n = int(np.searchsorted(first["t1_h"], 0.75 + 1e-9, side="right"))
    assert np.allclose(r.path["sog_kn"][:n], first["sog_kn"][:n]) and np.allclose(r.path["fuel_mt"][:n], first["fuel_mt"][:n])
    late = r.decisions[3]
    assert math.isclose(late.remaining_planned_mt, late.remaining_realized_mt, rel_tol=1e-12)
    assert perfect.fuel_mt * (1 - 1e-9) <= r.fuel_mt <= once.fuel_mt * (1 + 1e-9)
    assert math.isclose(sum(x.sailed_realized_mt for x in r.decisions), r.fuel_mt, rel_tol=1e-12)


def test_luo_epochs_must_divide_the_decision_interval():
    try:
        solve_rolling(PATH, START, ETA_H, "luo", every_h=0.25, ship=SHIP, epoch_steps=2)
    except ValueError as e:
        assert "epochs that divide" in str(e)
    else:
        raise AssertionError("expected a ValueError")


if __name__ == "__main__":
    tests = [(n, f) for n, f in sorted(globals().items()) if n.startswith("test_")]
    for name, fn in tests:
        fn()
        print(f"ok  {name}")
    print(f"{len(tests)} passed")

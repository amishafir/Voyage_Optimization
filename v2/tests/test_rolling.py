"""
Rolling-horizon re-planning (voyage_v2/rolling.py) on the small synthetic archive,
plus a wind run issued during the voyage so that the forecast changes.

Run from v2/:  python3 tests/test_rolling.py
"""

from __future__ import annotations

import math
import shutil
import sys
import tempfile
from pathlib import Path

import h5py
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


# --- information lag (the conservative variant): each block planned with the forecast known
# info_lag_h before it starts. The voyage starts at 07:15; wind runs at 00:00, 06:00 and 08:00.

def test_lagged_data_hold_the_runs_known_before_the_start():
    assert [r.name for r in DATA.runs["wind"]] == ["2026-10-14T06", "2026-10-14T08"]
    lagged = load_voyage_data(PATH, START, ETA_H, info_lag_h=1.5)          # known at 05:45: the 00:00 run
    assert [r.name for r in lagged.runs["wind"]] == ["2026-10-14T00", "2026-10-14T06", "2026-10-14T08"]
    try:
        VOYAGE.solve(forecast=True, sog_range_kn=RANGE, forecast_lag_h=1.5)
    except ValueError as e:
        assert "info_lag_h >= 1.5" in str(e)
    else:
        raise AssertionError("expected a ValueError: the data lack the runs known 1.5 h before the start")


def test_lagged_forecast_equals_the_forecast_from_the_runs_known_then():
    # The forecast known at 05:45 is the 00:00 wind run alone: the same plan as the forecast known
    # at the start of an archive without the later wind runs, and the same realized fuel.
    only00 = str(Path(_DIR) / "only00.h5")
    shutil.copy(PATH, only00)
    with h5py.File(only00, "r+") as f:
        for name in ("2026-10-14T06", "2026-10-14T08"):
            del f["wind"][name]
    early = Voyage(load_voyage_data(only00, START, ETA_H), SHIP)
    lagged = Voyage(load_voyage_data(PATH, START, ETA_H, info_lag_h=1.5), SHIP)
    for solve, opts in (("solve", {}), ("solve_luo", {"epoch_steps": 1})):
        ref = getattr(early, solve)(forecast=True, sog_range_kn=RANGE, **opts)
        p = getattr(lagged, solve)(forecast=True, sog_range_kn=RANGE, forecast_lag_h=1.5, **opts)
        assert math.isclose(p.planned_fuel_mt, ref.planned_fuel_mt, rel_tol=1e-12), solve
        assert np.array_equal(p.path["sog_kn"], ref.path["sog_kn"]), solve
        now = getattr(VOYAGE, solve)(forecast=True, sog_range_kn=RANGE, **opts)
        assert not math.isclose(p.planned_fuel_mt, now.planned_fuel_mt, rel_tol=1e-9), solve   # 06:00 run unknown
    # Lag 0 is the forecast known at the start.
    zero = VOYAGE.solve(forecast=True, sog_range_kn=RANGE, forecast_lag_h=0)
    assert zero.planned_fuel_mt == VOYAGE.solve(forecast=True, sog_range_kn=RANGE).planned_fuel_mt


def test_lagged_rolling_horizon():
    # Decisions every 0.25 h with a 0.25 h lag: the 08:00 run is first used for the block from
    # 08:15 (1.0 h in), one block later than without the lag. Until then every block is planned
    # with the 00:00 and 06:00 runs, as the first plan is (known at 07:00 or at 07:15 alike).
    perfect = VOYAGE.solve(sog_range_kn=RANGE)
    once = VOYAGE.solve(forecast=True, sog_range_kn=RANGE)
    now = solve_rolling(PATH, START, ETA_H, "full", every_h=0.25, ship=SHIP)
    r = solve_rolling(PATH, START, ETA_H, "full", every_h=0.25, ship=SHIP, info_lag_h=0.25)
    check_path(r)
    assert r.info_lag_h == 0.25 and [round(x.t_h, 9) for x in r.decisions] == [0, 0.25, 0.5, 0.75, 1.0, 1.25]
    n = int(np.searchsorted(once.path["t1_h"], 1.0 + 1e-9, side="right"))
    assert np.allclose(r.path["sog_kn"][:n], once.path["sog_kn"][:n])
    assert not np.allclose(now.path["sog_kn"][:n], once.path["sog_kn"][:n])     # no lag: re-planned at 0.75 h
    block = r.decisions[3]                                                       # the 08:00 block, from 07:45
    assert not math.isclose(block.sailed_planned_mt, block.sailed_realized_mt, rel_tol=1e-9)
    late = r.decisions[4]
    assert math.isclose(late.remaining_planned_mt, late.remaining_realized_mt, rel_tol=1e-12)
    assert perfect.fuel_mt * (1 - 1e-9) <= r.fuel_mt
    # Luo too; and lag 0 is the unlagged result.
    rl = solve_rolling(PATH, START, ETA_H, "luo", every_h=0.25, ship=SHIP, info_lag_h=0.25, epoch_steps=1)
    check_path(rl)
    assert rl.fuel_mt >= VOYAGE.solve_luo(epoch_steps=1, sog_range_kn=RANGE).fuel_mt * (1 - 1e-9)
    assert solve_rolling(PATH, START, ETA_H, "full", every_h=0.25, ship=SHIP, info_lag_h=0).fuel_mt == now.fuel_mt
    # The oracle ignores the lag.
    oracle = solve_rolling(PATH, START, ETA_H, "full", every_h=0.5, forecast=False, ship=SHIP, info_lag_h=6,
                           merge_nm=0.0)
    assert math.isclose(oracle.fuel_mt, VOYAGE.solve(sog_range_kn=RANGE, merge_nm=0.0).fuel_mt, rel_tol=1e-12)


if __name__ == "__main__":
    tests = [(n, f) for n, f in sorted(globals().items()) if n.startswith("test_")]
    for name, fn in tests:
        fn()
        print(f"ok  {name}")
    print(f"{len(tests)} passed")

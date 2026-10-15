"""
Tests for the closed-form SOG -> SWS inverse in shared/physics.py, against the
forward model and the binary search it replaces.

Run from pipeline/:  python3 -m pytest tests/test_sws_inverse.py
             or:     python3 tests/test_sws_inverse.py
"""

from __future__ import annotations

import math
import random
import sys
from pathlib import Path

PIPELINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PIPELINE))

from shared.physics import (  # noqa: E402
    DEFAULT_SHIP_PARAMETERS, GRAVITY, KNOTS_TO_MS, _cu_quadratic,
    calculate_speed_over_ground, calculate_speed_reduction_coefficient,
    calculate_sws_from_sog, calculate_sws_from_sog_bisection, calculate_sws_from_sog_closed_form,
)

SHIP = DEFAULT_SHIP_PARAMETERS


def _forward(sws, w, heading_deg, ship=SHIP):
    return calculate_speed_over_ground(
        ship_speed=sws,
        ocean_current=w["ocean_current_velocity_kmh"] / 1.852,
        current_direction=math.radians(w["ocean_current_direction_deg"]),
        ship_heading=math.radians(heading_deg),
        wind_direction=math.radians(w["wind_direction_10m_deg"]),
        beaufort_scale=int(w["beaufort_number"]),
        ship_parameters=ship,
    )


def _weather(bn, wind_dir=0.0, current_kn=0.0, current_dir=0.0):
    return {"wind_direction_10m_deg": wind_dir, "beaufort_number": bn,
            "ocean_current_velocity_kmh": current_kn * 1.852, "ocean_current_direction_deg": current_dir}


def _cases(n, bn_max, sog_range, current_max_kn, seed):
    rng = random.Random(seed)
    return [(rng.uniform(*sog_range),
             _weather(rng.randint(0, bn_max), rng.uniform(0, 360), rng.uniform(0, current_max_kn), rng.uniform(0, 360)),
             rng.uniform(0, 360))
            for _ in range(n)]


REALISTIC = _cases(5000, bn_max=8, sog_range=(9, 15), current_max_kn=2.5, seed=1)
WIDE = _cases(5000, bn_max=12, sog_range=(3, 20), current_max_kn=4.0, seed=2)


def test_closed_form_reproduces_target_sog():
    solved = 0
    for sog, w, hd in REALISTIC + WIDE:
        sws = calculate_sws_from_sog_closed_form(sog, w, hd, SHIP)
        if sws is not None:
            solved += 1
            assert abs(_forward(sws, w, hd) - sog) < 1e-9, (sog, w, hd, sws)
    assert solved > 0.95 * len(REALISTIC + WIDE)


def test_closed_form_applies_to_every_realistic_case():
    assert all(calculate_sws_from_sog_closed_form(s, w, h, SHIP) is not None for s, w, h in REALISTIC)


def test_agrees_with_binary_search_in_realistic_conditions():
    # The binary search stops within 0.001 kn of the target SOG, so the two SWS
    # values differ by about 0.001 kn divided by dSOG/dSWS (near 1 here).
    for sog, w, hd in REALISTIC:
        exact = calculate_sws_from_sog_closed_form(sog, w, hd, SHIP)
        assert abs(exact - calculate_sws_from_sog_bisection(sog, w, hd, SHIP)) < 2e-3


def test_none_only_when_target_is_unreachable():
    grid = [0.05 * i for i in range(1, 801)]                 # SWS 0.05 .. 40 kn
    for sog, w, hd in WIDE:
        if calculate_sws_from_sog_closed_form(sog, w, hd, SHIP) is None:
            assert sog < min(_forward(v, w, hd) for v in grid), (sog, w, hd)


def test_public_function_falls_back_to_binary_search():
    for sog, w, hd in WIDE:
        exact = calculate_sws_from_sog_closed_form(sog, w, hd, SHIP)
        expected = exact if exact is not None else calculate_sws_from_sog_bisection(sog, w, hd, SHIP)
        assert calculate_sws_from_sog(sog, w, hd, SHIP) == expected


def test_every_branch():
    a, b, c, v1 = _cu_quadratic(SHIP["length"], SHIP["block_coefficient"])
    cases = {
        "BN 0, no speed loss":            (12.0, _weather(0)),
        "cubic, moderate head wind":      (12.0, _weather(5, wind_dir=10.0, current_kn=1.0, current_dir=200.0)),
        "CU at its 0.1 floor (fast)":     (17.0, _weather(4, wind_dir=90.0)),
        "loss capped at 50 % (slow)":     (6.0, _weather(9, wind_dir=0.0)),
        "loss 50 % at every speed":       (12.0, _weather(12, wind_dir=0.0)),
    }
    for label, (sog, w) in cases.items():
        sws = calculate_sws_from_sog_closed_form(sog, w, 0.0, SHIP)
        assert sws is not None, label
        assert abs(_forward(sws, w, 0.0) - sog) < 1e-9, label
    assert calculate_sws_from_sog_closed_form(17.0, _weather(4, wind_dir=90.0), 0.0, SHIP) > v1


def test_cu_quadratic_matches_table_3():
    for cb in (0.50, 0.58, 0.63, 0.68, 0.75, 0.78):
        a, b, c, v1 = _cu_quadratic(200.0, cb)
        fn_per_knot = KNOTS_TO_MS / math.sqrt(GRAVITY * 200.0)
        for v in (2.0, 8.0, 12.0, 0.9 * v1):
            assert math.isclose(a - b * v - c * v * v,
                                calculate_speed_reduction_coefficient(v * fn_per_knot, cb, "normal"),
                                rel_tol=1e-12)
        assert math.isclose(calculate_speed_reduction_coefficient(v1 * fn_per_knot, cb, "normal"), 0.1, rel_tol=1e-9)


def test_block_coefficient_above_080_uses_binary_search():
    ship = dict(SHIP, block_coefficient=0.85)
    w = _weather(5, wind_dir=30.0, current_kn=1.0, current_dir=90.0)
    assert calculate_sws_from_sog_closed_form(12.0, w, 45.0, ship) is None
    assert calculate_sws_from_sog(12.0, w, 45.0, ship) == calculate_sws_from_sog_bisection(12.0, w, 45.0, ship)


if __name__ == "__main__":
    tests = [(n, f) for n, f in sorted(globals().items()) if n.startswith("test_")]
    for name, fn in tests:
        fn()
        print(f"ok  {name}")
    print(f"{len(tests)} passed")

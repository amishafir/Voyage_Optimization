"""
The C++ speed and fuel model against the reference implementation in
pipeline/shared/physics.py.

Run from v2/:  python3 tests/test_physics.py
"""

from __future__ import annotations

import math
import random
import sys
from pathlib import Path

V2 = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(V2), str(V2.parent / "pipeline")]

from shared.beaufort import wind_speed_to_beaufort  # noqa: E402
from shared.physics import calculate_speed_over_ground  # noqa: E402
from voyage_v2 import Conditions, Ship, beaufort_number, fcr_from_sog, sog_from_sws, sws_from_sog  # noqa: E402

SHIP = Ship.from_yaml()
PIPELINE_SHIP = {"length": SHIP.length_m, "displacement": SHIP.displacement_t,
                 "block_coefficient": SHIP.block_coefficient}


def _cases(n, seed, wind_max=120.0, current_max_kmh=6.0):
    rng = random.Random(seed)
    return [(Conditions(rng.uniform(0, wind_max), rng.uniform(0, 360), rng.uniform(0, current_max_kmh),
                        rng.uniform(0, 360)), rng.uniform(0, 360)) for _ in range(n)]


def _reference_sog(sws, c, bearing):
    return calculate_speed_over_ground(
        ship_speed=sws, ocean_current=c.current_speed_kmh / 1.852,
        current_direction=math.radians(c.current_to_deg), ship_heading=math.radians(bearing),
        wind_direction=math.radians(c.wind_from_deg),
        beaufort_scale=wind_speed_to_beaufort(c.wind_speed_kmh), ship_parameters=PIPELINE_SHIP)


def test_beaufort_matches_reference():
    for i in range(0, 1500):
        kmh = i * 0.1
        assert beaufort_number(kmh) == wind_speed_to_beaufort(kmh), kmh


def test_forward_matches_reference():
    rng = random.Random(1)
    for c, bearing in _cases(5000, 1):
        sws = rng.uniform(2, 25)
        assert math.isclose(sog_from_sws(SHIP, sws, bearing, c), _reference_sog(sws, c, bearing),
                            rel_tol=1e-12, abs_tol=1e-12)


def test_inverse_is_exact():
    rng = random.Random(2)
    unreachable = 0
    for c, bearing in _cases(5000, 2):
        sog = rng.uniform(3, 20)
        sws = sws_from_sog(SHIP, sog, bearing, c)
        if math.isinf(sws):
            unreachable += 1
            assert sog < min(_reference_sog(0.05 * k, c, bearing) for k in range(1, 801))
            continue
        assert abs(_reference_sog(sws, c, bearing) - sog) < 1e-9, (sog, c, bearing, sws)
    assert unreachable < 250


def test_fcr_is_cubic_in_sws():
    for c, bearing in _cases(200, 3, wind_max=60):
        sws = sws_from_sog(SHIP, 12.0, bearing, c)
        assert math.isclose(fcr_from_sog(SHIP, 12.0, bearing, c), SHIP.fcr_coefficient * sws ** 3, rel_tol=1e-14)


if __name__ == "__main__":
    tests = [(n, f) for n, f in sorted(globals().items()) if n.startswith("test_")]
    for name, fn in tests:
        fn()
        print(f"ok  {name}")
    print(f"{len(tests)} passed")

"""
Tests for shared/rhumb.py, shared/weather_grids.py and shared/subsegments.py.

Run from pipeline/:  python3 -m pytest tests/test_subsegments.py
             or:     python3 tests/test_subsegments.py
"""

from __future__ import annotations

import math
import random
import sys
from pathlib import Path

import yaml

PIPELINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PIPELINE))

from shared.rhumb import RhumbLeg  # noqa: E402
from shared.subsegments import partition_route  # noqa: E402
from shared.weather_grids import (  # noqa: E402
    CURRENT_GRID, DEFAULT_GRIDS, WIND_GRID, OctahedralGaussianGrid, boundaries_by_search,
)

ROUTES = ["persian_gulf_malacca", "st_johns_liverpool", "yokohama_long_beach"]


def _waypoints(route):
    with open(PIPELINE / "config" / "routes" / f"{route}.yaml") as f:
        return yaml.safe_load(f)["waypoints"]


def _legs(route):
    wps = _waypoints(route)
    return [RhumbLeg(a["lat"], a["lon"], b["lat"], b["lon"]) for a, b in zip(wps, wps[1:])]


# --- rhumb.py -----------------------------------------------------------------

def test_meridian_and_parallel_lengths():
    assert math.isclose(RhumbLeg(10, 20, 13, 20).length_nm, 180.0, rel_tol=1e-12)
    assert math.isclose(RhumbLeg(60, 0, 60, 2).length_nm, 60.0, rel_tol=1e-12)
    assert RhumbLeg(10, 20, 13, 20).bearing_deg == 0.0
    assert RhumbLeg(60, 2, 60, 0).bearing_deg == 270.0


def test_distance_is_linear_in_fraction():
    # The sub-leg from the start to point_at(f) is f of the leg, on the same bearing.
    for route in ROUTES:
        for leg in _legs(route):
            for f in (0.1, 0.37, 0.5, 0.93):
                lat, lon = leg.point_at(f)
                sub = RhumbLeg(leg.lat1, leg.lon1, lat, lon)
                assert math.isclose(sub.length_nm, f * leg.length_nm, rel_tol=1e-9)
                assert math.isclose(sub.bearing_deg, leg.bearing_deg, abs_tol=1e-7)


def test_fraction_inverses():
    for leg in _legs("st_johns_liverpool") + _legs("yokohama_long_beach"):
        for f in (0.05, 0.5, 0.95):
            lat, _ = leg.point_at(f)
            assert math.isclose(leg.fraction_at_lat(lat), f, abs_tol=1e-12)
            assert math.isclose(leg.fraction_at_lon(leg.lon_unwrapped_at(f)), f, abs_tol=1e-11)


def test_antimeridian_leg_goes_the_short_way():
    leg = RhumbLeg(46.85, 175.45, 47.65, -173.94)
    assert 0 < leg.bearing_deg < 180
    assert leg.length_nm < 500
    assert leg.point_at(0.5)[1] < -170 or leg.point_at(0.5)[1] > 170


def test_agrees_with_dp_rebuild_geo_grid():
    sys.path.insert(0, str(PIPELINE / "dp_rebuild"))
    from geo_grid import rhumb_bearing_deg, rhumb_distance_nm
    for route in ROUTES:
        for leg in _legs(route):
            d = rhumb_distance_nm(leg.lat1, leg.lon1, leg.lat2, leg.lon2)
            b = rhumb_bearing_deg(leg.lat1, leg.lon1, leg.lat2, leg.lon2)
            assert math.isclose(leg.length_nm, d, rel_tol=1e-9)
            assert math.isclose(leg.bearing_deg, b, abs_tol=1e-9)


# --- weather_grids.py ---------------------------------------------------------

# Grid points the live APIs returned on 2026-10-14 for requests at open-sea
# positions, with models and cell_selection=sea pinned as in api_params.
API_WIND = [((25.9646, 57.4999), (25.97539, 57.54098)),
            ((6.1337, 80.7914), (6.15114, 80.82707)),
            ((5.4803, 95.3849), (5.44815, 95.36868)),
            ((4.7323, 97.8568), (4.74517, 97.83894)),
            ((54.9630, -4.8682), (54.93849, -4.83102)),
            ((35.9761, 140.6990), (36.02812, 140.71243))]
API_CURRENT = [((8.9423, 76.6021), (8.95834, 76.62502)),
               ((6.4057, 80.0594), (6.37500, 80.04167)),
               ((54.8630, -4.7282), (54.87501, -4.70833)),
               ((34.4069, -119.4295), (34.37500, -119.45833)),
               ((33.7500, -118.2200), (33.79166, -118.20833))]


def test_cells_match_points_served_by_api():
    for grid, cases in ((WIND_GRID, API_WIND), (CURRENT_GRID, API_CURRENT)):
        for (lat, lon), served in cases:
            got = grid.center_of(grid.cell_of(lat, lon))
            assert abs(got[0] - served[0]) < 1e-4 and abs(got[1] - served[1]) < 1e-4, \
                (grid.name, (lat, lon), got, served)


def test_o1280_layout():
    g = WIND_GRID
    assert sum(g.nx_of(y) for y in range(2 * g.n)) == 6599680  # O1280 point count
    assert g.nx_of(0) == 20 and g.nx_of(1279) == g.nx_of(1280) == 5136
    for lat, lon in ((12.8, 60.0), (52.4, -30.0), (-33.0, 151.0), (47.0, 179.99)):
        assert g.cell_of(*g.center_of(g.cell_of(lat, lon))) == g.cell_of(lat, lon)


def test_current_cell_edges_on_twelfths():
    g = CURRENT_GRID
    for k in (-600, 7, 611):
        edge = k / 12.0
        assert g.cell_of(edge - 1e-7, 30.0) != g.cell_of(edge + 1e-7, 30.0)
        assert g.cell_of(30.0, edge - 1e-7) != g.cell_of(30.0, edge + 1e-7)
        assert g.cell_of(edge + 0.01, 30.0) == g.cell_of(edge + 1 / 12 - 0.01, 30.0)


def test_regular_grid_closed_form_matches_search():
    for route in ROUTES:
        for leg in _legs(route):
            exact = CURRENT_GRID.boundary_fractions(leg)
            found = boundaries_by_search(CURRENT_GRID.cell_of, leg, step_nm=0.25)
            assert len(found) == len(exact), (route, leg)
            assert max(abs(a - b) for a, b in zip(exact, found)) * leg.length_nm < 1e-8


def test_gaussian_boundaries_do_not_depend_on_search_step():
    fine = OctahedralGaussianGrid("fine", 1280, WIND_GRID.api_url, WIND_GRID.api_params,
                                  search_step_nm=0.02)
    for route in ROUTES:
        for leg in _legs(route)[:4]:
            a, b = WIND_GRID.boundary_fractions(leg), fine.boundary_fractions(leg)
            assert len(a) == len(b), (route, leg)
            assert max(abs(x - y) for x, y in zip(a, b)) * leg.length_nm < 1e-8


# --- subsegments.py -----------------------------------------------------------

def _check_partition(waypoints):
    subs = partition_route(waypoints)
    legs = [RhumbLeg(a["lat"], a["lon"], b["lat"], b["lon"])
            for a, b in zip(waypoints, waypoints[1:])]
    total = sum(leg.length_nm for leg in legs)

    assert math.isclose(sum(s.length_nm for s in subs), total, rel_tol=1e-12)
    assert subs[0].start_nm == 0.0 and math.isclose(subs[-1].end_nm, total, rel_tol=1e-12)
    for a, b in zip(subs, subs[1:]):
        assert math.isclose(a.end_nm, b.start_nm, abs_tol=1e-6)
        assert b.leg in (a.leg, a.leg + 1)
        if b.leg == a.leg:
            assert a.cells != b.cells, "a boundary with no change of cell"
        else:
            # A new leg starts exactly at its waypoint.
            wp = waypoints[b.leg]
            assert abs(b.start_lat - wp["lat"]) < 1e-9 and abs(b.start_lon - wp["lon"]) < 1e-9

    # Every subsegment lies inside the cells it reports, up to 1e-6 NM from its ends.
    rng = random.Random(0)
    leg_start = [sum(leg.length_nm for leg in legs[:i]) for i in range(len(legs))]
    for s in subs:
        leg = legs[s.leg]
        assert math.isclose(s.bearing_deg, leg.bearing_deg)
        f0 = (s.start_nm - leg_start[s.leg]) / leg.length_nm
        f1 = f0 + s.length_nm / leg.length_nm
        lat, lon = leg.point_at(f0)
        assert abs(lat - s.start_lat) < 1e-9 and abs(lon - s.start_lon) < 1e-9
        eps = 1e-6 / leg.length_nm
        for f in [f0 + eps, f1 - eps] + [rng.uniform(f0, f1) for _ in range(3)]:
            p = leg.point_at(f)
            for name, grid in DEFAULT_GRIDS.items():
                assert grid.cell_of(*p) == s.cells[name], (s, name, f)
    return subs


def test_partition_routes():
    for route in ROUTES:
        _check_partition(_waypoints(route))


def test_partition_accepts_tuples_and_skips_repeated_waypoints():
    a = partition_route([(50.0, -30.0), (50.0, -30.0), (51.0, -29.0)])
    b = partition_route([(50.0, -30.0), (51.0, -29.0)])
    assert [s.length_nm for s in a] == [s.length_nm for s in b]
    assert all(s.leg == 1 for s in a)


def test_east_west_and_north_south_legs():
    _check_partition([{"lat": 40.0, "lon": -20.0}, {"lat": 40.0, "lon": -18.0},
                      {"lat": 41.0, "lon": -18.0}])


if __name__ == "__main__":
    tests = [(n, f) for n, f in sorted(globals().items()) if n.startswith("test_")]
    for name, fn in tests:
        fn()
        print(f"ok  {name}")
    print(f"{len(tests)} passed")

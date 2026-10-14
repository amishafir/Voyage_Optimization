"""
Offline tests for the subsegment collector (collect/collector.py, run_all.py)
and the HDF5 extensions it uses (shared/hdf5_io.py). No network: the APIs are
replaced by fake `get` functions that answer like Open-Meteo.

Run from anywhere:  python3 pipeline/tests/test_collector.py
"""

from __future__ import annotations

import io
import json
import logging
import math
import os
import sys
import tempfile
import urllib.error
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

PIPELINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PIPELINE))

from collect import collector as C  # noqa: E402
from shared.beaufort import wind_speed_to_beaufort  # noqa: E402
from shared.hdf5_io import (  # noqa: E402
    ACTUAL_DTYPE, METADATA_DTYPE, PREDICTED_DTYPE, append_actual, append_predicted,
    create_hdf5, get_attrs, get_completed_runs, read_actual, read_metadata, read_predicted,
    read_samples,
)
from shared.weather_grids import CURRENT_GRID, WIND_GRID, RegularLatLonGrid  # noqa: E402

ROUTES = ["persian_gulf_malacca", "st_johns_liverpool"]
T0 = int(datetime(2026, 10, 15, 8, tzinfo=timezone.utc).timestamp())   # a scheduled slot
DAY0 = T0 - 8 * 3600                                                     # 00:00 UTC that day
# A short open-ocean route in the mid-Atlantic: a few cells of each grid.
SHORT_ROUTE = [(52.0, -34.0), (52.06, -33.75), (52.12, -33.62)]


def _waypoints(route):
    with open(PIPELINE / "config" / "routes" / f"{route}.yaml") as f:
        return yaml.safe_load(f)["waypoints"]


class _Records(logging.Handler):
    def __init__(self):
        super().__init__(logging.DEBUG)
        self.records = []

    def emit(self, record):
        self.records.append(record)

    def messages(self, level=logging.WARNING):
        return [r.getMessage() for r in self.records if r.levelno >= level]


def _capture():
    h = _Records()
    log = logging.getLogger(C.__name__)
    h.saved_level = log.level
    log.setLevel(logging.DEBUG)
    log.addHandler(h)
    return h


def _release(h):
    log = logging.getLogger(C.__name__)
    log.removeHandler(h)
    log.setLevel(h.saved_level)


class _NoSleep:
    """Pacer clock and sleep that never wait, but record what they were asked."""

    def __init__(self):
        self.t, self.sleeps = 0.0, []

    def sleep(self, s):
        self.sleeps.append(s)
        self.t += s

    def clock(self):
        return self.t


def _pacer():
    ns = _NoSleep()
    return C.Pacer(C.SECONDS_PER_CHUNK, sleep=ns.sleep, clock=ns.clock), ns


# --- A fake Open-Meteo ---------------------------------------------------------

def _units(variables):
    return {"time": "unixtime", **{v: C.EXPECTED_UNITS[v] for v in variables}}


def _body(grid, lat, lon, variables, now, hours, nan=False, served_shift=0.0):
    """What the API answers for one location: the cell's grid point, float32 like the API."""
    glat, glon = grid.center_of(grid.cell_of(lat, lon))
    glat += served_shift
    seed = (glat * 7.0 + glon * 3.0) % 20.0

    def value(i, h):
        return None if nan else round(seed + i + 0.01 * h, 3)

    times = [DAY0 + 3600 * h for h in range(hours)]
    return {
        "latitude": float(np.float32(glat)), "longitude": float(np.float32(glon)),
        "generationtime_ms": 0.1, "utc_offset_seconds": 0, "timezone": "GMT",
        "current_units": {**_units(variables), "interval": "seconds"},
        "current": {"time": now, "interval": 900,
                    **{v: value(i, 0) for i, v in enumerate(variables)}},
        "hourly_units": _units(variables),
        "hourly": {"time": times, **{v: [value(i, h) for h in range(hours)]
                                     for i, v in enumerate(variables)}},
    }


class FakeApi:
    """Answers forecast, marine and model-metadata URLs; records every URL."""

    def __init__(self, now=T0, hours=24 * C.FORECAST_DAYS, current_hours=None,
                 nan_cells=(), shifted_cells=(), errors=(), meta_fails=False):
        self.now, self.hours = now, hours
        self.current_hours = hours if current_hours is None else current_hours
        self.nan_cells, self.shifted_cells = set(nan_cells), set(shifted_cells)
        self.errors = list(errors)          # raised by the next weather requests
        self.meta_fails = meta_fails
        self.urls = []

    def __call__(self, url):
        self.urls.append(url)
        parts = urllib.parse.urlsplit(url)
        if parts.path.endswith("/static/meta.json"):
            if self.meta_fails:
                raise TimeoutError("timed out")
            return {"last_run_initialisation_time": self.now - 8 * 3600,
                    "last_run_availability_time": self.now - 2 * 3600}
        if self.errors:
            raise self.errors.pop(0)
        q = urllib.parse.parse_qs(parts.query)
        is_wind = url.startswith(WIND_GRID.api_url)
        grid = WIND_GRID if is_wind else CURRENT_GRID
        variables = q["hourly"][0].split(",")
        lats = [float(x) for x in q["latitude"][0].split(",")]
        lons = [float(x) for x in q["longitude"][0].split(",")]
        bodies = []
        for lat, lon in zip(lats, lons):
            cell = (grid.name, grid.cell_of(lat, lon))
            bodies.append(_body(grid, lat, lon, variables, self.now,
                                self.hours if is_wind else self.current_hours,
                                nan=cell in self.nan_cells,
                                served_shift=1 / 12 if cell in self.shifted_cells else 0.0))
        return bodies if len(bodies) > 1 else bodies[0]


def _http_error(code, reason):
    body = io.BytesIO(json.dumps({"error": True, "reason": reason}).encode())
    return urllib.error.HTTPError("https://example.test", code, "error", {}, body)


# --- Sampling plan --------------------------------------------------------------

def _check_plan(plan):
    subs = plan.subsegments
    for g, grid in plan.grids.items():
        queries = plan.queries[g]
        assert len(queries) == len({s.cells[g] for s in subs})
        assert len({q.cell for q in queries}) == len(queries)
        seen = set()
        for k, q in enumerate(queries):
            # Every subsegment of the query, and no other, lies in its cell.
            assert all(subs[i].cells[g] == q.cell for i in q.subsegments)
            assert all(plan.cell_index[g][i] == k for i in q.subsegments)
            seen.update(q.subsegments)
            # The query point is in the cell, at the (rounded) midpoint of one of its subsegments.
            assert grid.cell_of(q.query_lat, q.query_lon) == q.cell, (g, q)
            assert any(abs(plan.midpoints[i][0] - q.query_lat) < 1e-6 and
                       abs(plan.midpoints[i][1] - q.query_lon) < 1e-6 for i in q.subsegments)
            assert (q.grid_lat, q.grid_lon) == grid.center_of(q.cell)
            assert math.isclose(q.length_nm, sum(subs[i].length_nm for i in q.subsegments))
        assert seen == set(range(len(subs)))
        # Queries are in order of first appearance along the route.
        firsts = [q.subsegments[0] for q in queries]
        assert firsts == sorted(firsts)
        assert math.isclose(sum(q.length_nm for q in queries), sum(s.length_nm for s in subs))
    for s in subs:
        for g in plan.grids:
            assert plan.queries[g][plan.cell_index[g][s.index]].cell == s.cells[g]


def test_plan_groups_subsegments_by_cell():
    for route in ROUTES:
        plan = C.build_sampling_plan(_waypoints(route), route_key=route)
        _check_plan(plan)
        # Most cells hold a single subsegment run, but cells are shared between subsegments:
        # every subsegment boundary inside a leg changes exactly one grid's cell.
        assert len(plan.subsegments) > max(len(q) for q in plan.queries.values())


def _coarse_grids():
    params = {"models": "test_model", "cell_selection": "sea"}
    return {
        C.WIND: RegularLatLonGrid("coarse_wind", 0.5, 0.5, 1.0, 1.0, 180, 360,
                                  WIND_GRID.api_url, params),
        C.CURRENT: RegularLatLonGrid("coarse_current", 0.25, 0.25, 0.5, 0.5, 360, 720,
                                     CURRENT_GRID.api_url, params),
    }


def test_plan_queries_a_revisited_cell_once():
    # A U-turn: east along 10.2 N, north, west along 10.8 N. The wind cell
    # (10, 20) is entered at the start and again at the end.
    grids = _coarse_grids()
    route = [(10.2, 20.2), (10.2, 21.8), (10.8, 21.8), (10.8, 20.2)]
    plan = C.build_sampling_plan(route, grids=grids, port_trim_nm=0.0)
    _check_plan(plan)
    wind_cells = [s.cells[C.WIND] for s in plan.subsegments]
    assert wind_cells[0] == wind_cells[-1] == (10, 20)
    q = plan.queries[C.WIND][plan.cell_index[C.WIND][0]]
    assert plan.cell_index[C.WIND][len(plan.subsegments) - 1] == plan.cell_index[C.WIND][0]
    assert q.subsegments[0] == 0 and q.subsegments[-1] == len(plan.subsegments) - 1
    assert len(plan.queries[C.WIND]) == 2
    # The query point is the midpoint of the longest subsegment in the cell.
    longest = max(q.subsegments, key=lambda i: plan.subsegments[i].length_nm)
    assert (q.query_lat, q.query_lon) == tuple(round(x, C.COORD_DECIMALS)
                                               for x in plan.midpoints[longest])


def test_plan_fingerprint_tracks_the_route():
    a = C.build_sampling_plan(SHORT_ROUTE)
    b = C.build_sampling_plan(list(SHORT_ROUTE))
    c = C.build_sampling_plan(SHORT_ROUTE[:-1] + [(52.13, -33.62)])
    d = C.build_sampling_plan(SHORT_ROUTE, port_trim_nm=1.0)
    assert a.fingerprint == b.fingerprint
    assert len({a.fingerprint, c.fingerprint, d.fingerprint}) == 3


def test_plan_metadata_columns():
    plan = C.build_sampling_plan(SHORT_ROUTE)
    md = C.plan_metadata(plan)
    assert list(md["node_id"]) == [s.index for s in plan.subsegments]
    assert list(md["segment"]) == [s.leg for s in plan.subsegments]
    assert np.allclose(md["distance_from_start_nm"], [s.start_nm for s in plan.subsegments])
    assert np.allclose(md["length_nm"], [s.length_nm for s in plan.subsegments])
    for s, row in zip(plan.subsegments, md.itertuples()):
        assert (row.wind_cell_row, row.wind_cell_col) == s.cells[C.WIND]
        assert (row.current_cell_row, row.current_cell_col) == s.cells[C.CURRENT]
        assert (row.wind_grid_lat, row.wind_grid_lon) == WIND_GRID.center_of(s.cells[C.WIND])
        assert WIND_GRID.cell_of(row.lat, row.lon) == s.cells[C.WIND]       # midpoint
        assert CURRENT_GRID.cell_of(row.lat, row.lon) == s.cells[C.CURRENT]
    assert md["is_original"].tolist()[:1] == [True]
    assert md["is_original"].sum() == len({s.leg for s in plan.subsegments})


# --- Requests -------------------------------------------------------------------

def test_request_params_pin_the_grids():
    plan = C.build_sampling_plan(SHORT_ROUTE)
    for g, grid in ((C.WIND, WIND_GRID), (C.CURRENT, CURRENT_GRID)):
        p = C.request_params(g, grid, plan.queries[g])
        for k, v in grid.api_params.items():
            assert p[k] == v
        assert p["current"] == p["hourly"] == ",".join(C.API_FIELDS[g])
        assert p["timeformat"] == "unixtime" and p["timezone"] == "GMT"
        assert p["forecast_days"] == C.FORECAST_DAYS
        lats = p["latitude"].split(",")
        assert len(lats) == len(plan.queries[g])
        assert all(len(x.split(".")[1]) == C.COORD_DECIMALS for x in lats)
        assert [float(x) for x in lats] == [q.query_lat for q in plan.queries[g]]
    # The grid's own parameters cannot be overridden, and must pin both settings.
    clash = RegularLatLonGrid("clash", 0.5, 0.5, 1, 1, 180, 360, WIND_GRID.api_url,
                              {"models": "m", "cell_selection": "sea", "wind_speed_unit": "ms"})
    assert C.request_params(C.WIND, clash, plan.queries[C.WIND])["wind_speed_unit"] == "ms"
    loose = RegularLatLonGrid("loose", 0.5, 0.5, 1, 1, 180, 360, WIND_GRID.api_url,
                              {"models": "m"})
    try:
        C.request_params(C.WIND, loose, plan.queries[C.WIND])
        raise AssertionError("expected ValueError")
    except ValueError:
        pass


def test_fetch_cells_chunks_and_pins_every_request():
    plan = C.build_sampling_plan(_waypoints("st_johns_liverpool"))
    api = FakeApi()
    pacer, ns = _pacer()
    for g, grid in plan.grids.items():
        bodies = C.fetch_cells(g, grid, plan.queries[g], pacer, api, chunk_size=100)
        assert len(bodies) == len(plan.queries[g])
        for q, b in zip(plan.queries[g], bodies):
            assert abs(b["latitude"] - q.grid_lat) < 1e-4   # answers stay in order
    n_requests = sum(-(-len(plan.queries[g]) // 100) for g in plan.grids)
    assert len(api.urls) == n_requests
    for url in api.urls:
        grid = WIND_GRID if url.startswith(WIND_GRID.api_url + "?") else CURRENT_GRID
        assert url.startswith(grid.api_url + "?")
        q = urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)
        for k, v in grid.api_params.items():
            assert q[k] == [v], (url[:80], k)
        assert len(q["latitude"][0].split(",")) <= 100
    # Request starts are spaced SECONDS_PER_CHUNK apart: <= 400 calls per minute.
    assert len(ns.sleeps) == n_requests - 1
    assert all(math.isclose(s, C.SECONDS_PER_CHUNK) for s in ns.sleeps)


def test_retries_and_rate_limits():
    plan = C.build_sampling_plan(SHORT_ROUTE)
    queries = plan.queries[C.WIND]

    # Minutely limit and a server error: retried after waiting.
    api = FakeApi(errors=[_http_error(429, "Minutely API request limit exceeded. Please try "
                                           "again in one minute."), _http_error(503, "busy")])
    pacer, ns = _pacer()
    h = _capture()
    try:
        bodies = C.fetch_cells(C.WIND, WIND_GRID, queries, pacer, api)
    finally:
        _release(h)
    assert len(bodies) == len(queries) and len(api.urls) == 3
    assert ns.sleeps == [60, 60]        # 60 s for the minutely limit, 30 s * attempt 2 for the 503
    assert len(h.messages()) == 2

    # Daily limit: no retry.
    api = FakeApi(errors=[_http_error(429, "Daily API request limit exceeded. Please try "
                                           "again tomorrow.")])
    try:
        C.fetch_cells(C.WIND, WIND_GRID, queries, _pacer()[0], api)
        raise AssertionError("expected DailyLimitExceeded")
    except C.DailyLimitExceeded:
        assert len(api.urls) == 1

    # A bad request is not retried.
    api = FakeApi(errors=[_http_error(400, "Cannot initialize WeatherVariable")])
    try:
        C.fetch_cells(C.WIND, WIND_GRID, queries, _pacer()[0], api)
        raise AssertionError("expected ApiError")
    except C.ApiError as e:
        assert "400" in str(e) and len(api.urls) == 1

    # Persistent network failure: gives up after MAX_ATTEMPTS.
    api = FakeApi(errors=[TimeoutError("timed out")] * C.MAX_ATTEMPTS)
    h = _capture()
    try:
        C.fetch_cells(C.WIND, WIND_GRID, queries, _pacer()[0], api)
        raise AssertionError("expected ApiError")
    except C.ApiError:
        assert len(api.urls) == C.MAX_ATTEMPTS
    finally:
        _release(h)

    # A response for the wrong number of locations is rejected.
    def short(url):
        body = FakeApi()(url)
        return body[:-1] if isinstance(body, list) else []
    try:
        C.fetch_cells(C.WIND, WIND_GRID, queries, _pacer()[0], short)
        raise AssertionError("expected ApiError")
    except C.ApiError:
        pass


def test_pacer_spaces_request_starts():
    ns = _NoSleep()
    pacer = C.Pacer(15.0, sleep=ns.sleep, clock=ns.clock)
    pacer.wait()
    ns.t += 4.0          # the request took 4 s
    pacer.wait()
    ns.t += 20.0         # this one took longer than the interval
    pacer.wait()
    assert ns.sleeps == [11.0]


def test_model_run_metadata():
    api = FakeApi()
    init, avail = C.model_run(WIND_GRID, api)
    assert (init, avail) == (T0 - 8 * 3600, T0 - 2 * 3600)
    assert api.urls == ["https://api.open-meteo.com/data/ecmwf_ifs/static/meta.json"]
    C.model_run(CURRENT_GRID, api)
    assert api.urls[-1] == "https://marine-api.open-meteo.com/data/meteofrance_currents/static/meta.json"
    h = _capture()
    try:
        assert C.model_run(WIND_GRID, FakeApi(meta_fails=True)) == (-1, -1)
    finally:
        _release(h)


# --- Responses ------------------------------------------------------------------

def _grid_weather(plan, g, api=None):
    api = api or FakeApi()
    return C.parse_responses(g, C.fetch_cells(g, plan.grids[g], plan.queries[g], _pacer()[0], api))


def test_parse_and_nan_detection():
    plan = C.build_sampling_plan(SHORT_ROUTE)
    bad = plan.queries[C.CURRENT][1]
    api = FakeApi(nan_cells={(CURRENT_GRID.name, bad.cell)})
    gw = _grid_weather(plan, C.CURRENT, api)
    n = len(plan.queries[C.CURRENT])
    assert gw.hourly["ocean_current_velocity_kmh"].shape == (n, 24 * C.FORECAST_DAYS)
    nan = C.find_nan_cells(gw)
    assert list(nan) == [1]
    cols, n_bad, n_all = nan[1]
    assert cols == ["ocean_current_velocity_kmh", "ocean_current_direction_deg"]
    assert n_bad == n_all == 2 * 24 * C.FORECAST_DAYS
    assert C.find_nan_cells(_grid_weather(plan, C.WIND)) == {}

    # One NaN hourly value is enough.
    bodies = C.fetch_cells(C.WIND, WIND_GRID, plan.queries[C.WIND], _pacer()[0], FakeApi())
    bodies[0]["hourly"]["wind_direction_10m"][5] = None
    nan = C.find_nan_cells(C.parse_responses(C.WIND, bodies))
    assert nan == {0: ([], 1, 2 * 24 * C.FORECAST_DAYS)}

    # Wrong units, inconsistent time axes and malformed bodies are errors.
    for spoil in (lambda b: b["hourly_units"].update(wind_speed_10m="m/s"),
                  lambda b: b["hourly"]["time"].pop(),
                  lambda b: b.pop("current")):
        bodies = C.fetch_cells(C.WIND, WIND_GRID, plan.queries[C.WIND], _pacer()[0], FakeApi())
        spoil(bodies[-1])
        try:
            C.parse_responses(C.WIND, bodies)
            raise AssertionError("expected ApiError")
        except C.ApiError:
            pass


def test_substitution_detection():
    plan = C.build_sampling_plan(SHORT_ROUTE)
    q = plan.queries[C.WIND][-1]
    gw = _grid_weather(plan, C.WIND, FakeApi(shifted_cells={(WIND_GRID.name, q.cell)}))
    assert C.find_substitutions(plan.queries[C.WIND], gw) == [len(plan.queries[C.WIND]) - 1]
    assert C.find_substitutions(plan.queries[C.CURRENT], _grid_weather(plan, C.CURRENT)) == []
    # Longitudes compare modulo 360, and NaN coordinates never match.
    cq = C.CellQuery(C.WIND, (0, 0), 0.0, 180.0, 10.0, -180.0, (0,), 1.0)
    one = C.GridWeather(np.array([10.0]), np.array([180.0]), {}, np.array([]), {})
    assert C.find_substitutions([cq], one) == []
    one.served_lat[0] = np.nan
    assert C.find_substitutions([cq], one) == [0]


def test_beaufort_of_missing_wind_is_not_a_gale():
    assert wind_speed_to_beaufort(float("nan")) == 12          # why the guard exists
    assert C._beaufort(float("nan")) == C.BEAUFORT_MISSING == -1
    for v in (0.0, 1.7, 20.0, 61.0, 200.0):
        assert C._beaufort(v) == wind_speed_to_beaufort(v)


# --- Rows -----------------------------------------------------------------------

def test_rows_give_each_subsegment_its_cells_weather():
    plan = C.build_sampling_plan(_waypoints("st_johns_liverpool"))
    weather = {g: _grid_weather(plan, g) for g in plan.grids}
    actual, predicted = C.build_rows(plan, weather, sample_hour=42, reference_unix=T0)
    n, nt = len(plan.subsegments), 24 * C.FORECAST_DAYS
    assert len(actual) == n and len(predicted) == n * nt
    w, c = plan.cell_index[C.WIND], plan.cell_index[C.CURRENT]
    W, K = weather[C.WIND], weather[C.CURRENT]
    for s in plan.subsegments[::97]:
        i = s.index
        a = actual.iloc[i]
        assert a.node_id == i and a.sample_hour == 42
        assert a.wind_speed_10m_kmh == W.current["wind_speed_10m_kmh"][w[i]]
        assert a.ocean_current_direction_deg == K.current["ocean_current_direction_deg"][c[i]]
        assert a.beaufort_number == wind_speed_to_beaufort(a.wind_speed_10m_kmh)
        assert (a.wind_served_lat, a.current_served_lon) == (W.served_lat[w[i]], K.served_lon[c[i]])
        assert math.isnan(a.wave_height_m)
        rows = predicted[predicted.node_id == i]
        assert list(rows.forecast_hour) == list(range(-8, nt - 8))   # hours from 08:00 UTC
        assert np.array_equal(rows.wind_direction_10m_deg.values,
                              W.hourly["wind_direction_10m_deg"][w[i]])
        assert np.array_equal(rows.ocean_current_velocity_kmh.values,
                              K.hourly["ocean_current_velocity_kmh"][c[i]])
        assert rows.wave_height_m.isna().all()
    assert predicted.forecast_hour.dtype == np.int32 and actual.sample_hour.dtype == np.int32


def test_rows_keep_only_hours_both_forecasts_cover():
    plan = C.build_sampling_plan(SHORT_ROUTE)
    api = FakeApi(current_hours=100)
    weather = {g: _grid_weather(plan, g, api) for g in plan.grids}
    h = _capture()
    try:
        _, predicted = C.build_rows(plan, weather, 0, T0)
        try:
            C.build_rows(plan, weather, 0, T0 + 1800)
            raise AssertionError("expected ValueError: leads must be whole hours")
        except ValueError:
            pass
    finally:
        _release(h)
    assert sorted(set(predicted.forecast_hour)) == list(range(-8, 92))
    assert not predicted.ocean_current_velocity_kmh.isna().any()
    assert any("differ in time span" in m for m in h.messages())


# --- Scheduling and budget --------------------------------------------------------

def test_previous_slot():
    def at(day, hour, minute=0, second=0):
        return datetime(2026, 10, day, hour, minute, second, tzinfo=timezone.utc).timestamp()
    slot = lambda t: C.previous_slot(t, 6, 8)   # noqa: E731
    assert slot(at(15, 8)) == at(15, 8)
    assert slot(at(15, 7, 59, 59)) == at(15, 2)
    assert slot(at(15, 13, 30)) == at(15, 8)
    assert slot(at(15, 20, 0, 1)) == at(15, 20)
    assert slot(at(15, 1)) == at(14, 20)
    assert {datetime.fromtimestamp(slot(at(15, h)), timezone.utc).hour
            for h in range(24)} == {2, 8, 14, 20}


def test_query_weight_and_calls_per_sample():
    assert C.query_weight(4, 7) == 1.0         # what the collector requests
    assert C.query_weight(10, 7) == 1.0
    assert math.isclose(C.query_weight(12, 7), 1.2)
    assert math.isclose(C.query_weight(5, 7, n_models=2), 1.0)
    assert math.isclose(C.query_weight(10, 28), 2.0)
    plan = C.build_sampling_plan(SHORT_ROUTE)
    assert C.calls_per_sample(plan) == {g: float(len(q)) for g, q in plan.queries.items()}


# --- HDF5 -----------------------------------------------------------------------

def test_collect_writes_a_readable_sample_and_resumes():
    plan = C.build_sampling_plan(SHORT_ROUTE, route_key="short", route_name="Short test route")
    nan_cell = plan.queries[C.CURRENT][-1]
    shifted = plan.queries[C.WIND][0]
    api = FakeApi(nan_cells={(CURRENT_GRID.name, nan_cell.cell)},
                  shifted_cells={(WIND_GRID.name, shifted.cell)})
    n, nt = len(plan.subsegments), 24 * C.FORECAST_DAYS
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "out", "short.h5")
        rc = C.RouteCollector("Short", plan, path, 6, 8, {C.WIND: 11.0}, get=api)
        assert not rc.has_sample(T0)
        h = _capture()
        try:
            assert rc.collect(T0, _pacer()[0])
            api.now = T0 + 6 * 3600
            assert rc.collect(T0 + 6 * 3600, _pacer()[0])
        finally:
            _release(h)
        assert get_completed_runs(path) == [0, 6]
        assert rc.has_sample(T0) and rc.has_sample(T0 + 6 * 3600)
        assert not rc.has_sample(T0 + 12 * 3600)

        # NaN and substitution are both visible in the log.
        warnings = h.messages(logging.WARNING)
        assert any("NaN in model inputs at 1 of" in m for m in warnings)
        assert any(f"cell {nan_cell.cell}" in m for m in warnings)
        infos = h.messages(logging.INFO)
        assert any("1 of %d cells served by another grid point" % len(plan.queries[C.WIND]) in m
                   for m in infos)
        assert any("same as last sample" in m for m in infos)

        attrs = get_attrs(path)
        assert attrs["sampling"] == "subsegments" and attrs["epoch_unix"] == T0
        assert attrs["plan_fingerprint"] == plan.fingerprint
        assert json.loads(attrs["wind_api_params_json"]) == WIND_GRID.api_params
        assert json.loads(attrs["current_api_params_json"]) == CURRENT_GRID.api_params
        assert "not collected" in attrs["wave_height_m"]

        md = read_metadata(path)
        assert list(md.node_id) == list(range(n))
        assert md.waypoint_name.iloc[0].startswith("leg00_")
        assert list(md.columns[:len(METADATA_DTYPE.names)]) == list(METADATA_DTYPE.names)

        act = read_actual(path, sample_hour=6)
        assert len(act) == n and act.sample_hour.dtype == np.int32
        k = plan.cell_index[C.WIND][0]
        assert abs(act.wind_served_lat.iloc[0] - (plan.queries[C.WIND][k].grid_lat + 1 / 12)) < 1e-4
        bad = list(nan_cell.subsegments)
        assert act.ocean_current_velocity_kmh.iloc[bad].isna().all()
        assert not act.drop(index=bad).ocean_current_velocity_kmh.isna().any()
        assert act.wave_height_m.isna().all()

        pred = read_predicted(path, sample_hour=0)
        assert len(pred) == n * nt and pred.forecast_hour.dtype == np.int32
        assert set(pred.forecast_hour) == set(range(-8, nt - 8))
        pred6 = read_predicted(path, sample_hour=6, forecast_hour=0)
        assert len(pred6) == n                                  # 14:00 UTC, lead 0

        samples = read_samples(path)
        assert list(samples.sample_hour) == [0, 6]
        s0 = samples.iloc[0]
        assert s0.reference_time_unix == T0 and s0.wind_run_init_unix == T0 - 8 * 3600
        assert s0.current_nan_cells == 1 and s0.wind_nan_cells == 0
        assert s0.wind_substituted_cells == 1 and s0.current_substituted_cells == 0

        # Restart: the epoch comes from the file, the next sample is hour 12.
        rc2 = C.RouteCollector("Short", plan, path, 6, 8, get=FakeApi(now=T0 + 12 * 3600))
        assert rc2.epoch_unix == T0 and rc2.sample_hour(T0 + 12 * 3600) == 12
        assert rc2.collect(T0 + 12 * 3600, _pacer()[0])
        assert get_completed_runs(path) == [0, 6, 12]

        # A changed route or schedule must not be appended to the old file.
        other = C.build_sampling_plan(SHORT_ROUTE[:-1] + [(52.13, -33.62)])
        for args in ((other, 6, 8), (plan, 6, 7), (plan, 3, 8)):
            try:
                C.RouteCollector("Short", args[0], path, args[1], args[2], get=api)
                raise AssertionError(f"expected PlanMismatch for {args[1:]}")
            except C.PlanMismatch:
                pass


def test_failed_sample_writes_nothing():
    plan = C.build_sampling_plan(SHORT_ROUTE)
    api = FakeApi(errors=[_http_error(429, "Daily API request limit exceeded.")], meta_fails=True)
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "x.h5")
        rc = C.RouteCollector("X", plan, path, 6, 8, get=api)
        h = _capture()
        try:
            assert not rc.collect(T0, _pacer()[0])
        finally:
            _release(h)
        assert get_completed_runs(path) == [] and len(read_predicted(path)) == 0
        assert len(read_samples(path)) == 0
        assert any("not collected" in m for m in h.messages(logging.ERROR))
        assert sum("Could not read model metadata" in m for m in h.messages()) == 2


def test_legacy_schema_still_works():
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "legacy.h5")
        md = pd.DataFrame({"node_id": [0, 1], "lon": [1.0, 2.0], "lat": [3.0, 4.0],
                           "waypoint_name": ["A", "B"], "is_original": [True, False],
                           "distance_from_start_nm": [0.0, 5.0], "segment": [0, 0]})
        create_hdf5(path, md, {"route_name": "legacy"})
        weather = {"wind_speed_10m_kmh": 10.0, "wind_direction_10m_deg": 90.0,
                   "beaufort_number": 2, "wave_height_m": 1.0,
                   "ocean_current_velocity_kmh": 1.0, "ocean_current_direction_deg": 45.0}
        append_actual(path, pd.DataFrame([{"node_id": 0, "sample_hour": 0, **weather}]))
        append_predicted(path, pd.DataFrame([{"node_id": 1, "forecast_hour": 3,
                                              "sample_hour": 0, **weather}]))
        assert list(read_metadata(path).columns) == list(METADATA_DTYPE.names)
        assert read_metadata(path).waypoint_name.tolist() == ["A", "B"]
        assert list(read_actual(path).columns) == list(ACTUAL_DTYPE.names)
        assert list(read_predicted(path).columns) == list(PREDICTED_DTYPE.names)
        assert get_completed_runs(path) == [0] and len(read_samples(path)) == 0
        try:
            create_hdf5(path, md.drop(columns="segment"))
            raise AssertionError("expected ValueError for a missing metadata column")
        except ValueError:
            pass


# --- run_all.py -----------------------------------------------------------------

def _run_all_main(args):
    """run_all.main(args) with its log output captured; returns (exit code, output)."""
    import contextlib
    import run_all
    root = logging.getLogger()
    before, level = list(root.handlers), root.level
    out = io.StringIO()
    try:
        with contextlib.redirect_stderr(out):
            code = run_all.main(args)
    finally:
        for hnd in root.handlers[:]:
            if hnd not in before:
                root.removeHandler(hnd)
        root.setLevel(level)
    return code, out.getvalue()


def test_run_all_dry_run_and_budget():
    import run_all
    with tempfile.TemporaryDirectory() as tmp:
        for route in ("1", "2"):
            code, out = _run_all_main(["--route", route, "--dry-run", "--data-dir", tmp])
            assert code == 0 and f"Route {route}" in out and "ERROR" not in out
        code, out = _run_all_main(["--route", "all", "--dry-run", "--data-dir", tmp])
        assert code == 1 and "run one route per machine" in out     # over the daily limit
        assert os.listdir(tmp) == []                                 # a dry run writes nothing
    plans = run_all.build_plans(["1", "2"])
    lines, per_day = run_all.budget_report(plans)
    per_sample = {k: sum(C.calls_per_sample(p).values()) for k, p in plans.items()}
    assert all(v * 4 < C.API_LIMITS["day"] for v in per_sample.values())
    assert per_day == 4 * sum(per_sample.values()) > C.API_LIMITS["day"]
    assert sum(per_sample.values()) < C.API_LIMITS["hour"]


def test_legacy_collect_is_removed():
    try:
        C.collect({"collection": {"route": "st_johns_liverpool", "interval_nm": 5}})
        raise AssertionError("expected RuntimeError")
    except RuntimeError as e:
        assert "run_all.py" in str(e)


if __name__ == "__main__":
    tests = [(n, f) for n, f in sorted(globals().items()) if n.startswith("test_")]
    for name, fn in tests:
        fn()
        print(f"ok  {name}")
    print(f"{len(tests)} passed")

"""
Offline tests for the model-run collector (collect/collector.py, run_all.py)
and its archive (shared/run_archive.py). No network: Open-Meteo is replaced by
a fake that publishes runs on a fake clock.

Run from anywhere:  python3 pipeline/tests/test_collector.py
"""

from __future__ import annotations

import contextlib
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
import yaml

PIPELINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PIPELINE))

from collect import collector as C  # noqa: E402
from shared import run_archive as A  # noqa: E402
from shared.weather_grids import CURRENT_GRID, WAVE_GRID, WIND_GRID, RegularLatLonGrid  # noqa: E402

H = 3600
D0 = int(datetime(2026, 10, 14, tzinfo=timezone.utc).timestamp())   # day D, 00:00 UTC
ROUTES = ["persian_gulf_malacca", "st_johns_liverpool"]
# A short open-ocean route in the mid-Atlantic: a few cells of each grid.
SHORT_ROUTE = [(52.0, -34.0), (52.06, -33.75), (52.12, -33.62)]


def _waypoints(route):
    with open(PIPELINE / "config" / "routes" / f"{route}.yaml") as f:
        return yaml.safe_load(f)["waypoints"]


def _hm(h, m=0, day=0):
    """Unix time of day D + `day`, h:m UTC."""
    return D0 + day * 24 * H + h * H + m * 60


# --- Log capture ---------------------------------------------------------------

class _Records(logging.Handler):
    def __init__(self):
        super().__init__(logging.DEBUG)
        self.records = []

    def emit(self, record):
        self.records.append(record)

    def messages(self, level=logging.WARNING):
        return [r.getMessage() for r in self.records if r.levelno >= level]


@contextlib.contextmanager
def captured():
    h, log = _Records(), logging.getLogger(C.__name__)
    level = log.level
    log.setLevel(logging.DEBUG)
    log.addHandler(h)
    try:
        yield h
    finally:
        log.removeHandler(h)
        log.setLevel(level)


# --- A fake Open-Meteo on a fake clock --------------------------------------------

def _seed(glat, glon):
    return round((glat * 7.0 + glon * 3.0) % 20.0, 3)


def wind_value(glat, glon, init, lead):
    """(speed, direction) the fake serves for a wind run."""
    return round(_seed(glat, glon) + 0.01 * lead, 3), float((init // H) % 360)


def current_value(glat, glon, run_day, t):
    """(velocity, direction) the fake serves; the direction names the run that served it."""
    return round(_seed(glat, glon) / 10 + 0.001 * ((t - run_day) // H), 4), float((run_day // 86400) % 360)


def wave_value(glat, glon, run, t):
    """(height, direction, period) the fake serves for a waves run; the direction names
    the run. Like MFWAM, the period runs 3 h past the height and direction."""
    lead = (t - run) // H
    if lead > C.WAVE_LAST_LEAD_H + 3:
        return None, None, None
    period = round(5 + _seed(glat, glon) / 4 + 0.01 * lead, 3)
    if lead > C.WAVE_LAST_LEAD_H:
        return None, None, period
    return round(_seed(glat, glon) / 5 + 0.001 * lead, 4), float((run // H) % 360), period


MARINE_MODELS = {"meteofrance_currents": (CURRENT_GRID, C.API_FIELDS[C.CURRENT]),
                 "meteofrance_wave": (WAVE_GRID, C.API_FIELDS[C.WAVE])}


def _http_error(code, reason):
    body = io.BytesIO(json.dumps({"error": True, "reason": reason}).encode())
    return urllib.error.HTTPError("https://example.test", code, "error", {}, body)


class World:
    """Fake clock and Open-Meteo. Runs become available at their publication time."""

    def __init__(self, t):
        self.t = float(t)
        self.wind_published = {_hm(18, day=-1): _hm(0, 30), _hm(0): _hm(7, 30),
                               _hm(6): _hm(12, 24), _hm(12): _hm(20, 1), _hm(18): _hm(0, 24, 1),
                               _hm(0, day=1): _hm(7, 30, 1), _hm(6, day=1): _hm(12, 24, 1)}
        self.current_published = {_hm(0, day=-1): _hm(12, 5, -1), _hm(0): _hm(12, 5),
                                  _hm(0, day=1): _hm(12, 5, 1)}
        self.wave_published = {_hm(0, day=-1): _hm(12, 4, -1), _hm(12, day=-1): _hm(0, 4),
                               _hm(0): _hm(12, 4), _hm(12): _hm(0, 4, 1),
                               _hm(0, day=1): _hm(12, 4, 1), _hm(12, day=1): _hm(0, 4, 2)}
        self.partial_after_s = 6 * H    # the archive serves a partial run from C + 6 h
        self.archive_lag_s = 0          # the full run reaches the archive this long after publication
        self.nan_cells, self.shifted_cells = set(), set()
        self.failures = []      # [predicate(url), exception factory, remaining count]
        self.hooks = []         # called with each data URL before answering
        self.urls = []

    # clock
    def clock(self):
        return self.t

    def sleep(self, s):
        self.t += s

    def client(self):
        return C.ApiClient(get=self, pacer=C.Pacer(C.SECONDS_PER_CHUNK, sleep=self.sleep,
                                                   clock=self.clock), clock=self.clock)

    def fail(self, predicate, factory, times=10**9):
        self.failures.append([predicate, factory, times])

    def _latest(self, published):
        done = [(init, at) for init, at in published.items() if at <= self.t]
        return max(done) if done else (-1, -1)

    def data_urls(self, part=""):
        return [u for u in self.urls if "/static/" not in u and part in u]

    # the API
    def __call__(self, url):
        self.urls.append(url)
        parts = urllib.parse.urlsplit(url)
        if parts.path.endswith("/static/meta.json"):
            init, at = self._latest({"ecmwf_ifs": self.wind_published,
                                     "meteofrance_currents": self.current_published,
                                     "meteofrance_wave": self.wave_published}[parts.path.split("/")[2]])
            return {"last_run_initialisation_time": init, "last_run_availability_time": at}
        for hook in self.hooks:
            hook(url)
        for rule in self.failures:
            if rule[2] > 0 and rule[0](url):
                rule[2] -= 1
                raise rule[1]()
        q = {k: v[0] for k, v in urllib.parse.parse_qs(parts.query).items()}
        lats = [float(x) for x in q["latitude"].split(",")]
        lons = [float(x) for x in q["longitude"].split(",")]
        if parts.netloc == "single-runs-api.open-meteo.com":
            init = int(datetime.strptime(q["run"], "%Y-%m-%dT%H:%M")
                       .replace(tzinfo=timezone.utc).timestamp())
            # Like the real archive: a run answers from C + 6 h with its first 72 h
            # while it streams in, and in full only once it is published.
            published = self.wind_published.get(init, math.inf)
            if self.t < min(published, init + self.partial_after_s):
                raise _http_error(400, f"The requested model run is not available. Model: "
                                       f"ecmwf_ifs, run: {q['run']}Z")
            times = [init + h * H for h in range(24 * int(q["forecast_days"]))]
            last = C.WIND_LAST_LEAD_H[datetime.fromtimestamp(init, timezone.utc).hour]
            if self.t < published + self.archive_lag_s:
                last = min(last, 72)
            bodies = [self._body(WIND_GRID, lat, lon, times, q["hourly"].split(","),
                                 lambda g, t: wind_value(*g, init, (t - init) // H)
                                 if (t - init) // H <= last else (None, None))
                      for lat, lon in zip(lats, lons)]
        elif parts.path == "/v1/marine":
            start, end = (int(datetime.strptime(q[k], "%Y-%m-%dT%H:%M")
                              .replace(tzinfo=timezone.utc).timestamp())
                          for k in ("start_hour", "end_hour"))
            times = list(range(start, end + H, H))
            bodies = [self._marine_body(lat, lon, times, q["models"].split(","),
                                        q["hourly"].split(",")) for lat, lon in zip(lats, lons)]
        else:
            raise _http_error(404, "unknown endpoint")
        return bodies if len(bodies) > 1 else bodies[0]

    def _marine_body(self, lat, lon, times, models, variables):
        """Like the Marine API: with several models every variable comes once per model,
        suffixed _<model> (null where the model lacks it), and the reported grid point
        is the first model's."""
        hourly, units, first = {"time": times}, {"time": "unixtime"}, None
        for m in models:
            grid, fields = MARINE_MODELS[m]
            if m == "meteofrance_currents":
                run, _ = self._latest(self.current_published)
                value = (lambda r: lambda g, t: current_value(*g, r, t))(run)
            else:
                run, _ = self._latest(self.wave_published)
                value = (lambda r: lambda g, t: wave_value(*g, r, t))(run)
            body = self._body(grid, lat, lon, times, [v for v in variables if v in fields], value)
            first = first or body
            sfx = f"_{m}" if len(models) > 1 else ""
            for v in variables:
                hourly[v + sfx] = body["hourly"][v] if v in fields else [None] * len(times)
                units[v + sfx] = body["hourly_units"][v] if v in fields else "undefined"
        return {**first, "hourly": hourly, "hourly_units": units}

    def _body(self, grid, lat, lon, times, variables, value):
        cell = grid.cell_of(lat, lon)
        glat, glon = grid.center_of(cell)
        if (grid.name, cell) in self.shifted_cells:
            glat += 1 / 12
        nan = (grid.name, cell) in self.nan_cells
        rows = [(None,) * len(variables) if nan else value((glat, glon), t) for t in times]
        return {
            "latitude": float(np.float32(glat)), "longitude": float(np.float32(glon)),
            "generationtime_ms": 0.1, "utc_offset_seconds": 0, "timezone": "GMT",
            "hourly_units": {"time": "unixtime", **{v: C.EXPECTED_UNITS[v] for v in variables}},
            "hourly": {"time": times, **{v: [r[i] for r in rows] for i, v in enumerate(variables)}},
        }


def make_collector(world, path, plan=None, label="Short"):
    plan = plan or C.build_sampling_plan(SHORT_ROUTE, route_key="short")
    route = C.RouteRuns(label, plan, path, clock=world.clock)
    return C.RunCollector([route], world.client(), clock=world.clock), route


def run_until(world, coll, t_end, max_steps=2000):
    for _ in range(max_steps):
        wake = coll.step()
        if wake > t_end:
            world.t = max(world.t, t_end)
            return
        world.t = max(world.t, wake)
    raise AssertionError("too many steps")


@contextlib.contextmanager
def chunk_size(n):
    old, C.CHUNK_SIZE = C.CHUNK_SIZE, n
    try:
        yield
    finally:
        C.CHUNK_SIZE = old


def _status(path, grid, init):
    runs = A.read_runs(path)
    row = runs[(runs.grid == grid) & (runs.run_init_unix == init)]
    assert len(row) == 1, (grid, A.run_name(init), runs)
    return row.iloc[0]


# --- Sampling plan --------------------------------------------------------------

def _on_subsegment(plan, i, lat, lon, tol_nm=1e-4):
    """The point lies on subsegment i: its distances to both ends add up to its length."""
    from shared.rhumb import RhumbLeg
    s, (elat, elon) = plan.subsegments[i], plan.endpoints[i]
    d = RhumbLeg(s.start_lat, s.start_lon, lat, lon).length_nm + RhumbLeg(lat, lon, elat, elon).length_nm
    return abs(d - s.length_nm) < tol_nm


def _check_plan(plan):
    subs = plan.subsegments
    for g, grid in plan.grids.items():
        queries = plan.queries[g]
        assert len(queries) == len({s.cells[g] for s in subs})
        seen = set()
        for k, q in enumerate(queries):
            assert all(subs[i].cells[g] == q.cell for i in q.subsegments)
            assert all(plan.cell_index[g][i] == k for i in q.subsegments)
            seen.update(q.subsegments)
            assert grid.cell_of(q.query_lat, q.query_lon) == q.cell, (g, q)
            assert any(_on_subsegment(plan, i, q.query_lat, q.query_lon) for i in q.subsegments)
            assert (q.grid_lat, q.grid_lon) == grid.center_of(q.cell)
        assert seen == set(range(len(subs)))
        firsts = [q.subsegments[0] for q in queries]
        assert firsts == sorted(firsts)


def test_plan_groups_subsegments_by_cell():
    for route in ROUTES:
        _check_plan(C.build_sampling_plan(_waypoints(route), route_key=route))


def test_query_points_keep_away_from_cell_edges():
    # The midpoint of the longest subsegment is used unless it lies within
    # MIN_EDGE_MARGIN_NM of the cell's edge; a replacement is never closer to it.
    for route in ROUTES:
        plan = C.build_sampling_plan(_waypoints(route))
        moved = 0
        for g, grid in plan.grids.items():
            for q in plan.queries[g]:
                longest = max(q.subsegments, key=lambda i: plan.subsegments[i].length_nm)
                mid = tuple(round(x, C.COORD_DECIMALS) for x in plan.midpoints[longest])
                m_mid = C._edge_margin(grid, q.cell, *mid) if grid.cell_of(*mid) == q.cell else -1
                m_q = C._edge_margin(grid, q.cell, q.query_lat, q.query_lon)
                if (q.query_lat, q.query_lon) == mid:
                    assert m_mid >= C.MIN_EDGE_MARGIN_NM or m_q >= m_mid
                else:
                    moved += 1
                    assert m_mid < C.MIN_EDGE_MARGIN_NM and m_q > m_mid, (route, g, q.cell)
        assert moved > 0


def test_plan_queries_a_revisited_cell_once():
    params = {"models": "test_model", "cell_selection": "sea"}
    grids = {C.WIND: RegularLatLonGrid("coarse_wind", 0.5, 0.5, 1.0, 1.0, 180, 360,
                                       WIND_GRID.api_url, params),
             C.CURRENT: RegularLatLonGrid("coarse_current", 0.25, 0.25, 0.5, 0.5, 360, 720,
                                          CURRENT_GRID.api_url, params)}
    route = [(10.2, 20.2), (10.2, 21.8), (10.8, 21.8), (10.8, 20.2)]   # a U-turn
    plan = C.build_sampling_plan(route, grids=grids, port_trim_nm=0.0)
    _check_plan(plan)
    last = len(plan.subsegments) - 1
    assert plan.subsegments[0].cells[C.WIND] == plan.subsegments[last].cells[C.WIND]
    assert plan.cell_index[C.WIND][0] == plan.cell_index[C.WIND][last]
    assert len(plan.queries[C.WIND]) == 2


def test_plan_fingerprint_tracks_the_route():
    a = C.build_sampling_plan(SHORT_ROUTE)
    assert a.fingerprint == C.build_sampling_plan(list(SHORT_ROUTE)).fingerprint
    c = C.build_sampling_plan(SHORT_ROUTE[:-1] + [(52.13, -33.62)])
    d = C.build_sampling_plan(SHORT_ROUTE, port_trim_nm=1.0)
    assert len({a.fingerprint, c.fingerprint, d.fingerprint}) == 3


def test_plan_tables():
    plan = C.build_sampling_plan(_waypoints("st_johns_liverpool"))
    subs, cells = C.plan_tables(plan)
    assert list(subs["index"]) == list(range(len(plan.subsegments)))
    for g in (C.WIND, C.CURRENT):
        assert len(cells[g]) == len(plan.queries[g])
        rows = cells[g].iloc[subs[f"{g}_cell"].values]
        assert [tuple(x) for x in rows[["row", "col"]].values] == \
            [s.cells[g] for s in plan.subsegments]
        assert cells[g]["n_subsegments"].sum() == len(plan.subsegments)


# --- Requests and budget ---------------------------------------------------------

def test_run_params_pin_the_grids_and_the_window():
    plan = C.build_sampling_plan(SHORT_ROUTE)
    p = C.run_params(C.WIND, WIND_GRID, plan.queries[C.WIND], _hm(12))
    assert p["run"] == "2026-10-14T12:00" and p["forecast_days"] == 16
    assert p["hourly"] == "wind_speed_10m,wind_direction_10m" and "current" not in p
    assert p["wind_speed_unit"] == "kmh" and p["timeformat"] == "unixtime"
    p = C.run_params(C.CURRENT, CURRENT_GRID, plan.queries[C.CURRENT], _hm(0))
    assert (p["start_hour"], p["end_hour"]) == ("2026-10-14T00:00", "2026-10-23T23:00")
    assert "run" not in p and "forecast_days" not in p and "current" not in p
    for g, grid in ((C.WIND, WIND_GRID), (C.CURRENT, CURRENT_GRID)):
        p = C.run_params(g, grid, plan.queries[g], _hm(0))
        for k, v in grid.api_params.items():
            assert p[k] == v
        assert [float(x) for x in p["latitude"].split(",")] == [q.query_lat for q in plan.queries[g]]
    assert C.run_url(C.WIND, WIND_GRID, plan.queries[C.WIND], _hm(0)).startswith(
        "https://single-runs-api.open-meteo.com/v1/forecast?")
    assert C.run_url(C.CURRENT, CURRENT_GRID, plan.queries[C.CURRENT], _hm(0)).startswith(
        CURRENT_GRID.api_url + "?")
    p = C.run_params(C.CURRENT, CURRENT_GRID, plan.queries[C.CURRENT], _hm(0), [(C.WAVE, WAVE_GRID)])
    assert p["models"] == "meteofrance_currents,meteofrance_wave"
    assert p["hourly"] == ("ocean_current_velocity,ocean_current_direction,"
                           "wave_height,wave_direction,wave_period")
    assert p["start_hour"] == "2026-10-14T00:00" and p["cell_selection"] == "sea"
    try:
        C.run_params(C.WIND, WIND_GRID, plan.queries[C.WIND], _hm(0), [(C.WAVE, WAVE_GRID)])
        raise AssertionError("expected ValueError")
    except ValueError:
        pass
    loose = RegularLatLonGrid("loose", 0.5, 0.5, 1, 1, 180, 360, WIND_GRID.api_url, {"models": "m"})
    try:
        C.run_params(C.WIND, loose, plan.queries[C.WIND], _hm(0))
        raise AssertionError("expected ValueError")
    except ValueError:
        pass


def test_query_weight_and_daily_budget():
    assert C.query_weight(2, 16) == 1.0 and C.query_weight(2, 10) == 1.0
    assert math.isclose(C.query_weight(12, 7), 1.2) and math.isclose(C.query_weight(10, 28), 2.0)
    assert C.WEIGHT == {C.WIND: 1.0, C.CURRENT: 1.0, C.WAVE: 1.0}
    # Currents and waves in one request: 5 variables x 2 models = 10, still one call.
    assert C.WEIGHT_CURRENT_WITH_WAVE == 1.0 and C.query_weight(5, 10, n_models=2) == 1.0
    assert math.isclose(C.query_weight(6, 10, n_models=2), 1.2)
    total = 0.0
    for route in ROUTES:
        plan = C.build_sampling_plan(_waypoints(route))
        c = C.daily_calls(plan)
        assert c["wind"] == 4 * len(plan.queries[C.WIND])
        assert c["current"] == len(plan.queries[C.CURRENT])
        assert c["wave"] == 0 and c["wave_alone"] == len(plan.queries[C.CURRENT])
        total += c["wind"] + c["current"] + c["wave"] + c["probes_max"]
    assert total < C.API_LIMITS["day"]          # both routes fit on one machine


def test_api_client_retries_and_counts():
    w = World(_hm(12))
    url = "https://single-runs-api.open-meteo.com/v1/forecast?x"
    calls = []

    def get(u):
        calls.append(w.t)
        if len(calls) == 1:
            raise _http_error(429, "Minutely API request limit exceeded. Please try again in one minute.")
        return {"ok": True}
    client = C.ApiClient(get=get, pacer=C.Pacer(15, sleep=w.sleep, clock=w.clock), clock=w.clock)
    with captured():
        assert client.get_json(url, 3.0) == {"ok": True}
    assert calls[1] - calls[0] == 60 and client.calls == 6.0 and client.requests == 2
    assert client.calls_last_24h() == 6.0
    w.t += 25 * H
    assert client.calls_last_24h() == 0.0

    for err, exc in ((_http_error(400, "The requested model run is not available. Model: "
                                       "ecmwf_ifs, run: 2026-10-14T18:00Z"), C.RunNotAvailable),
                     (_http_error(429, "Daily API request limit exceeded."), C.DailyLimitExceeded),
                     (_http_error(400, "Cannot initialize WeatherVariable"), C.ApiError)):
        client = C.ApiClient(get=lambda u, e=err: (_ for _ in ()).throw(e),
                             pacer=C.Pacer(15, sleep=w.sleep, clock=w.clock), clock=w.clock)
        try:
            client.get_json(url, 1.0)
            raise AssertionError(f"expected {exc.__name__}")
        except exc:
            assert client.requests == 1          # not retried
    client = C.ApiClient(get=lambda u: (_ for _ in ()).throw(TimeoutError()),
                         pacer=C.Pacer(15, sleep=w.sleep, clock=w.clock), clock=w.clock)
    with captured():
        try:
            client.get_json(url, 1.0)
            raise AssertionError("expected ApiError")
        except C.ApiError:
            assert client.requests == C.ATTEMPTS


def test_cut_to_span_and_parse_errors():
    run = C.GridRun(np.zeros(2), np.zeros(2), np.arange(6) * H,
                    {"a": np.array([[np.nan, 1, 2, np.nan, np.nan, np.nan],
                                    [np.nan, np.nan, 3, 4, np.nan, np.nan]])})
    cut = C.cut_to_span(run)
    assert list(cut.time) == [H, 2 * H, 3 * H] and cut.values["a"].shape == (2, 3)
    assert C.find_nan_cells(cut) == {0: (1, 3), 1: (1, 3)}
    # Several variables: the span is where every one of them has a value somewhere.
    run = C.GridRun(np.zeros(1), np.zeros(1), np.arange(5) * H,
                    {"a": np.array([[1, 2, 3, np.nan, np.nan]]),
                     "b": np.array([[1, 2, 3, 4, np.nan]])})
    assert list(C.cut_to_span(run).time) == [0, H, 2 * H]
    w = World(_hm(13))
    plan = C.build_sampling_plan(SHORT_ROUTE)
    url = C.run_url(C.WIND, WIND_GRID, plan.queries[C.WIND], _hm(6))
    for spoil in (lambda b: b["hourly_units"].update(wind_speed_10m="m/s"),
                  lambda b: b["hourly"]["time"].pop(),
                  lambda b: b.pop("hourly")):
        bodies = w(url)
        spoil(bodies[-1])
        try:
            C.parse_run(C.WIND, bodies)
            raise AssertionError("expected ApiError")
        except C.ApiError:
            pass


# --- Wind ------------------------------------------------------------------------

def test_wind_probes_until_published_then_fetches_and_cuts():
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "a.h5")
        w = World(_hm(12))
        coll, route = make_collector(w, path)
        with captured() as log:
            run_until(w, coll, _hm(13))
        row = _status(path, "wind", _hm(6))
        assert row.status == "complete"
        # The archive serves the run's first 72 h from 12:00, but the collector waits
        # for the metadata (published 12:24) plus 10 minutes: metadata reads at 12:00,
        # 12:10, 12:20, 12:30 and 12:34, then one archive probe.
        assert row.probe_attempts == 6
        assert _hm(12, 34) <= row.first_probe_success_unix < _hm(12, 35)
        assert row.availability_unix == _hm(12, 24)          # from the metadata
        n_wind = len(route.plan.queries[C.WIND])
        assert row.fetch_requests == 1 and row.api_calls == 1 + n_wind
        assert sum("wind run" in m and "not published yet" in m
                   for m in log.messages(logging.INFO)) == 3

        run = A.read_run(path, "wind", _hm(6))
        assert run["time_unix"][0] == _hm(6) and len(run["time_unix"]) == 145   # cut at +144 h
        assert run["wind_speed_10m_kmh"].shape == (n_wind, 145)
        assert run["wind_speed_10m_kmh"].dtype == np.float32
        for k, q in enumerate(route.plan.queries[C.WIND]):
            assert abs(run["served_lat"][k] - q.grid_lat) < 1e-4
            speed, direction = wind_value(q.grid_lat, q.grid_lon, _hm(6), 144)
            assert math.isclose(run["wind_speed_10m_kmh"][k, -1], speed, rel_tol=1e-5)
            assert run["wind_direction_10m_deg"][k, 0] == direction
        at = run["attrs"]
        assert at["run_init_unix"] == _hm(6) and at["availability_unix"] == _hm(12, 24)
        assert at["last_lead_hours"] == 144 and at["nan_cells"] == 0 and not at["backfilled"]
        assert json.loads(at["api_params_json"])["models"] == "ecmwf_ifs"

        # The 12 UTC run, published 20:01, reaches +360 h.
        run_until(w, coll, _hm(20, 30))
        run = A.read_run(path, "wind", _hm(12))
        assert len(run["time_unix"]) == 361 and run["attrs"]["last_lead_hours"] == 360
        assert _status(path, "wind", _hm(12)).probe_attempts == 16   # reads 18:00 .. 20:11, probe


def test_wind_retries_only_failed_chunks():
    with tempfile.TemporaryDirectory() as tmp, chunk_size(2):
        w = World(_hm(12, 35))
        coll, route = make_collector(w, os.path.join(tmp, "a.h5"))
        q = route.plan.queries[C.WIND]
        assert len(q) >= 3
        second = f"latitude={q[2].query_lat:.6f}"
        w.fail(lambda u: "single-runs" in u and second in u, lambda: _http_error(503, "busy"), 2)
        with captured() as log:
            coll.step()
        assert _status(coll.routes[0].path, "wind", _hm(6)).status == "pending"
        assert any("chunk 2/" in m for m in log.messages())
        first_round = len(w.data_urls("single-runs"))
        run_until(w, coll, _hm(13))
        row = _status(coll.routes[0].path, "wind", _hm(6))
        assert row.status == "complete"
        retried = w.data_urls("single-runs")[first_round:]
        assert len(retried) == 1 and second in retried[0]          # only the failed chunk
        assert row.fetch_requests == first_round - 1 + 1           # probe excluded


def test_wind_missed_at_deadline_then_backfilled():
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "a.h5")
        w = World(_hm(12))
        del w.wind_published[_hm(6)]                  # the 06 UTC run never shows up
        coll, route = make_collector(w, path)
        with captured() as log:
            run_until(w, coll, _hm(20, 0))
            assert _status(path, "wind", _hm(6)).status == "pending"
            run_until(w, coll, _hm(20, 15))           # 12 UTC published at 20:01
        row = _status(path, "wind", _hm(6))
        assert row.status == "missed" and "archive" in row.note
        assert row.probe_attempts == 50                # metadata reads 12:00 .. 20:10
        assert any("wind run 2026-10-14T06 missed" in m for m in log.messages())
        assert not A.has_run(path, "wind", _hm(6))

        n_wind = len(route.plan.queries[C.WIND])
        assert coll.backfill_wind(dry_run=True) == n_wind
        assert _status(path, "wind", _hm(6)).status == "missed"
        w.wind_published[_hm(6)] = _hm(12, 24)        # it is in the archive after all
        with captured():
            assert coll.backfill_wind() == n_wind
        assert _status(path, "wind", _hm(6)).status == "complete"
        run = A.read_run(path, "wind", _hm(6))
        assert run["attrs"]["backfilled"] and run["attrs"]["first_probe_success_unix"] == -1
        assert coll.backfill_wind(dry_run=True) == 0


# --- Currents --------------------------------------------------------------------

def test_current_waits_for_availability_then_fetches_the_full_span():
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "a.h5")
        w = World(_hm(11))
        coll, route = make_collector(w, path)
        with captured():
            run_until(w, coll, _hm(12, 10))
            assert _status(path, "current", _hm(0)).status == "pending"
            assert not w.data_urls("/v1/marine")          # metadata only so far
            run_until(w, coll, _hm(12, 20))
        row = _status(path, "current", _hm(0))
        assert row.status == "complete"
        assert row.availability_unix == _hm(12, 5) and row.first_probe_success_unix == _hm(12, 10)
        urls = w.data_urls("/v1/marine")
        assert len(urls) == 1 and "start_hour=2026-10-14T00%3A00" in urls[0]
        assert urllib.parse.parse_qs(urllib.parse.urlsplit(urls[0]).query)["end_hour"] == \
            ["2026-10-23T23:00"]
        run = A.read_run(path, "current", _hm(0))
        assert run["time_unix"][0] == _hm(0) and len(run["time_unix"]) == 240
        assert run["attrs"]["fetch_start_unix"] >= _hm(12, 15)        # availability + 10 min
        assert (run["ocean_current_direction_deg"] == float((_hm(0) // 86400) % 360)).all()


def test_current_late_retry_after_midnight_keeps_the_first_day():
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "a.h5")
        w = World(_hm(12))
        w.fail(lambda u: "/v1/marine" in u and w.t < _hm(0, 30, day=1),
               lambda: _http_error(502, "bad gateway"))
        coll, _ = make_collector(w, path)
        with captured():
            run_until(w, coll, _hm(1, 0, day=1))
        assert _status(path, "current", _hm(0)).status == "complete"
        run = A.read_run(path, "current", _hm(0))
        assert run["time_unix"][0] == _hm(0) and len(run["time_unix"]) == 240
        assert run["attrs"]["fetch_end_unix"] >= _hm(0, 30, day=1)


def test_current_missed_at_the_hard_deadline():
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "a.h5")
        w = World(_hm(12))
        w.fail(lambda u: "/v1/marine" in u, lambda: _http_error(503, "busy"))
        coll, _ = make_collector(w, path)
        with captured() as log:
            run_until(w, coll, _hm(12, 0, day=1))
            assert _status(path, "current", _hm(0)).status == "pending"
            run_until(w, coll, _hm(12, 30, day=1))   # run D + 1 published at 12:05
        row = _status(path, "current", _hm(0))
        assert row.status == "missed" and "no archive" in row.note
        assert not A.has_run(path, "current", _hm(0))
        assert any("current run 2026-10-14T00 missed" in m for m in log.messages(logging.ERROR))


def test_current_discarded_if_the_run_changes_during_the_fetch():
    with tempfile.TemporaryDirectory() as tmp, chunk_size(2):
        path = os.path.join(tmp, "a.h5")
        w = World(_hm(12, 15))
        coll, route = make_collector(w, path)
        assert len(route.plan.queries[C.CURRENT]) > 2

        def publish_next_day(url):
            if "/v1/marine" in url and len(w.data_urls("/v1/marine")) == 2:
                w.current_published[_hm(0, day=1)] = w.t   # run D + 1 appears mid-fetch
        w.hooks.append(publish_next_day)
        with captured() as log:
            coll.step()
        row = _status(path, "current", _hm(0))
        assert row.status == "discarded" and "could mix runs" in row.note
        assert not A.has_run(path, "current", _hm(0))
        assert any("discarded" in m for m in log.messages(logging.ERROR))


def test_current_refetched_if_republished_during_the_fetch():
    with tempfile.TemporaryDirectory() as tmp, chunk_size(2):
        path = os.path.join(tmp, "a.h5")
        w = World(_hm(12, 15))
        coll, route = make_collector(w, path)
        n_chunks = -(-len(route.plan.queries[C.CURRENT]) // 2)

        def republish(url):
            if "/v1/marine" in url and len(w.data_urls("/v1/marine")) == 2:
                w.current_published[_hm(0)] = _hm(12, 14)   # same run, new availability time
        w.hooks.append(republish)
        with captured() as log:
            run_until(w, coll, _hm(13))
        assert _status(path, "current", _hm(0)).status == "complete"
        assert len(w.data_urls("/v1/marine")) == 2 * n_chunks
        assert A.read_run(path, "current", _hm(0))["attrs"]["availability_unix"] == _hm(12, 14)
        assert any("republished" in m for m in log.messages())


# --- Checks, restarts, limits ------------------------------------------------------

def test_nan_and_substitutions_are_logged_and_counted():
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "a.h5")
        w = World(_hm(12, 30))
        plan = C.build_sampling_plan(SHORT_ROUTE)
        nan_q, shifted_q = plan.queries[C.CURRENT][1], plan.queries[C.WIND][0]
        w.nan_cells.add((CURRENT_GRID.name, nan_q.cell))
        w.shifted_cells.add((WIND_GRID.name, shifted_q.cell))
        coll, _ = make_collector(w, path, plan)
        with captured() as log:
            run_until(w, coll, _hm(13))
        cur = A.read_run(path, "current", _hm(0))
        assert cur["attrs"]["nan_cells"] == 1 and cur["attrs"]["substituted_cells"] == 0
        assert np.isnan(cur["ocean_current_velocity_kmh"][1]).all()
        assert len(cur["time_unix"]) == 240            # a NaN cell does not shorten the run
        wind = A.read_run(path, "wind", _hm(6))
        assert wind["attrs"]["substituted_cells"] == 1 and wind["attrs"]["nan_cells"] == 0
        assert abs(wind["served_lat"][0] - (shifted_q.grid_lat + 1 / 12)) < 1e-4
        assert any("NaN values at 1 of" in m for m in log.messages(logging.WARNING))
        wave = A.read_run(path, "wave", _hm(0))
        assert wave["attrs"]["nan_cells"] == 0 and wave["attrs"]["substituted_cells"] == -1
        assert any(f"cell {nan_q.cell}" in m for m in log.messages(logging.WARNING))
        assert any("1 of %d cells served by another grid point" % len(plan.queries[C.WIND]) in m
                   for m in log.messages(logging.INFO))


def test_restart_resumes_from_the_runs_table():
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "a.h5")
        w = World(_hm(12))
        coll, route = make_collector(w, path)
        with captured():
            run_until(w, coll, _hm(13))
        assert _status(path, "wind", _hm(6)).status == "complete"
        assert _status(path, "current", _hm(0)).status == "complete"

        # Stopped for a day: the next restart happens on day D + 1 at 12:20.
        w.t = _hm(12, 20, day=1)
        n_before = len(w.data_urls())
        coll, route = make_collector(w, path)
        assert route.attrs["first_wind_run_unix"] == _hm(6)          # from the file
        with captured() as log:
            run_until(w, coll, _hm(13, 0, day=1))
        status = {(r.grid, A.run_name(r.run_init_unix)): r.status
                  for r in A.read_runs(path).itertuples()}
        assert status == {("wind", "2026-10-14T06"): "complete",
                          ("wind", "2026-10-14T12"): "complete",   # missed, a day old: backfilled
                          ("wind", "2026-10-14T18"): "missed",     # not yet a day old
                          ("wind", "2026-10-15T00"): "complete",   # 06 UTC not out until 12:24
                          ("wind", "2026-10-15T06"): "complete",
                          ("current", "2026-10-14T00"): "complete",
                          ("current", "2026-10-15T00"): "complete",
                          ("wave", "2026-10-14T00"): "complete",
                          ("wave", "2026-10-15T00"): "complete"}
        assert A.read_run(path, "wind", _hm(12))["attrs"]["backfilled"]
        new = w.data_urls()[n_before:]
        assert not any("run=2026-10-14T06" in u for u in new)        # nothing fetched twice
        assert sum("missed" in m for m in log.messages()) == 2
        assert len(coll.missed_wind_runs()) == 1

        # A crash after a run was stored but before /runs was updated.
        w.t = _hm(0, 30, day=2)
        coll.routes[0].add_due_runs(w.t)
        coll.routes[0].flush()
        stored = A.read_run(path, "wind", _hm(6, day=1))
        A.write_run(path, "wind", _hm(12, day=1), stored["time_unix"],
                    {k: stored[k] for k in ("wind_speed_10m_kmh", "wind_direction_10m_deg")},
                    stored["served_lat"], stored["served_lon"], {"last_lead_hours": 360})
        assert _status(path, "wind", _hm(12, day=1)).status == "pending"
        _, route = make_collector(w, path)
        assert route.rows[("wind", _hm(12, day=1))]["status"] == "complete"


def test_changed_route_is_refused():
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "a.h5")
        w = World(_hm(12))
        coll, _ = make_collector(w, path)
        coll.routes[0].create(w.t)
        other = C.build_sampling_plan(SHORT_ROUTE[:-1] + [(52.13, -33.62)])
        try:
            C.RouteRuns("Short", other, path)
            raise AssertionError("expected PlanMismatch")
        except C.PlanMismatch:
            pass


def test_daily_limit_stops_the_step():
    with tempfile.TemporaryDirectory() as tmp:
        w = World(_hm(12, 30))
        w.fail(lambda u: True, lambda: _http_error(429, "Daily API request limit exceeded. "
                                                        "Please try again tomorrow."))
        coll, _ = make_collector(w, os.path.join(tmp, "a.h5"))
        with captured() as log:
            wake = coll.step()
        assert len(w.data_urls()) == 1                       # nothing after the refusal
        assert wake >= _hm(12, 40)
        assert any("daily limit" in m for m in log.messages(logging.ERROR))


def test_archive_round_trip():
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "a.h5")
        w = World(_hm(12))
        coll, route = make_collector(w, path)
        with captured():
            run_until(w, coll, _hm(20, 30))
        attrs = A.read_attrs(path)
        assert attrs["layout"] == A.LAYOUT and attrs["plan_fingerprint"] == route.plan.fingerprint
        assert json.loads(attrs["wind_api_params_json"]) == WIND_GRID.api_params
        assert json.loads(attrs["current_api_params_json"]) == CURRENT_GRID.api_params
        assert attrs["wind_api_url"].startswith("https://single-runs-api")
        assert "wave_height" not in attrs and "MFWAM" in attrs["wave_note"]
        assert attrs["wave_cell_table"] == "current_cells"
        assert attrs["first_wave_run_unix"] == attrs["first_current_run_unix"]
        plan = A.read_plan(path)
        assert len(plan["subsegments"]) == len(route.plan.subsegments)
        assert list(plan["wind_cells"]["row"]) == [q.cell[0] for q in route.plan.queries[C.WIND]]
        assert A.run_inits(path, "wind") == [_hm(6), _hm(12)]
        assert A.run_inits(path, "current") == [_hm(0)]
        assert A.run_inits(path, "wave") == [_hm(0)]
        runs = A.read_runs(path)
        assert set(runs.status) == {"complete"} and runs.run_init_unix.dtype == np.int64
        # The product builder's lookup: subsegment -> cell row of a run.
        assert plan["subsegments"]["current_cell"].dtype == np.int32
        k = int(plan["subsegments"]["current_cell"].iloc[-1])
        cur = A.read_run(path, "current", _hm(0))
        q = route.plan.queries[C.CURRENT][k]
        assert math.isclose(cur["ocean_current_velocity_kmh"][k, 5],
                            current_value(q.grid_lat, q.grid_lon, _hm(0), _hm(5))[0], rel_tol=1e-5)


# --- run_all.py -----------------------------------------------------------------

def _run_all(args):
    import run_all
    root = logging.getLogger()
    before, level = list(root.handlers), root.level
    out = io.StringIO()
    try:
        with contextlib.redirect_stderr(out):
            code = run_all.main(args)
    finally:
        for h in root.handlers[:]:
            if h not in before:
                root.removeHandler(h)
        root.setLevel(level)
    return code, out.getvalue()


def test_run_all_dry_run_and_backfill_report():
    import run_all
    with tempfile.TemporaryDirectory() as tmp:
        code, out = _run_all(["--route", "all", "--dry-run", "--data-dir", tmp])
        assert code == 0 and "Total:" in out and "ERROR" not in out
        assert os.listdir(tmp) == []                                  # nothing written
        code, out = _run_all(["--route", "2", "--backfill-wind", "--dry-run", "--data-dir", tmp])
        assert code == 3 and "No archive" in out

        # An archive for Route 2 with one missed wind run.
        plan = run_all.build_plans(["2"])["2"]
        route = C.RouteRuns("Route 2", plan, os.path.join(tmp, run_all.ROUTES["2"]["hdf5"]),
                            clock=lambda: _hm(13))
        route.create(_hm(13))
        route.add_due_runs(_hm(13))
        route.finish("wind", _hm(6), "missed", "test")
        code, out = _run_all(["--route", "2", "--backfill-wind", "--dry-run", "--data-dir", tmp])
        assert code == 0
        assert (f"Backfill: 1 missed or incomplete wind runs, {len(plan.queries[C.WIND])} "
                "API calls") in out


def test_route_selection_and_each_set_fits_one_machine():
    import argparse
    import run_all
    assert run_all.route_keys("all") == ["1", "2"]          # edison's watchdog starts "--route all"
    assert run_all.route_keys("volatile") == ["3", "4", "5", "6"]
    assert run_all.route_keys("4") == ["4"] and run_all.route_keys("5,3") == ["5", "3"]
    for bad in ("8", "1,x", ""):
        try:
            run_all.route_keys(bad)
            raise AssertionError(f"expected an error for {bad!r}")
        except argparse.ArgumentTypeError:
            pass
    for name, keys in run_all.ROUTE_SETS.items():
        _, worst = run_all.budget_report(run_all.build_plans(keys))
        assert worst < C.API_LIMITS["day"], (name, worst)
    with tempfile.TemporaryDirectory() as tmp:
        code, out = _run_all(["--route", "volatile", "--dry-run", "--data-dir", tmp])
        assert code == 0 and "Route 5 (kaohsiung_yokohama)" in out and "ERROR" not in out


def test_wind_waits_while_the_archive_still_holds_a_partial_run():
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "a.h5")
        w = World(_hm(12, 30))
        w.archive_lag_s = 20 * 60          # published 12:24, complete in the archive at 12:44
        coll, route = make_collector(w, path)
        with captured() as log:
            run_until(w, coll, _hm(13, 30))
        row = _status(path, "wind", _hm(6))
        assert row.status == "complete"
        assert _hm(12, 44) <= row.first_probe_success_unix < _hm(12, 45)
        n_chunks = -(-len(route.plan.queries[C.WIND]) // C.CHUNK_SIZE)
        assert row.fetch_requests == n_chunks                 # the full run fetched once
        assert any("holds +0..+72 h of +144 h" in m for m in log.messages(logging.INFO))
        assert len(A.read_run(path, "wind", _hm(6))["time_unix"]) == 145


def _truncate(path, grid, init, hours):
    run = A.read_run(path, grid, init)
    attrs = dict(run["attrs"], last_lead_hours=hours - 1)
    attrs.pop("complete", None)
    cols = [k for k in run if k not in ("time_unix", "served_lat", "served_lon", "attrs")]
    A.write_run(path, grid, init, run["time_unix"][:hours], {k: run[k][:, :hours] for k in cols},
                run["served_lat"], run["served_lon"], attrs)


def test_short_stored_run_is_marked_incomplete_and_backfilled():
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "a.h5")
        w = World(_hm(12, 40))
        coll, route = make_collector(w, path)
        with captured():
            run_until(w, coll, _hm(13))
        _truncate(path, "wind", _hm(6), 73)             # as the old collector stored it
        assert _status(path, "wind", _hm(6)).status == "complete"

        w.t = _hm(7, 0, day=1)                          # restart a day later
        with captured() as log:
            coll, route = make_collector(w, path)
            assert route.rows[("wind", _hm(6))]["status"] == "incomplete"
            assert any("marked incomplete" in m for m in log.messages())
            run_until(w, coll, _hm(9, 0, day=1))
        row = _status(path, "wind", _hm(6))
        assert row.status == "complete" and row.note == "backfilled"
        run = A.read_run(path, "wind", _hm(6))
        assert len(run["time_unix"]) == 145 and run["attrs"]["backfilled"]


def test_auto_backfill_respects_the_budget_and_waits_for_currents():
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "a.h5")
        w = World(_hm(12, 40))
        coll, route = make_collector(w, path)
        with captured():
            run_until(w, coll, _hm(13))
        _truncate(path, "wind", _hm(6), 73)

        # Over the budget: the run waits, and is looked at again an hour later.
        old, C.AUTO_BACKFILL_LIMIT = C.AUTO_BACKFILL_LIMIT, 1
        try:
            w.t = _hm(7, 0, day=1)
            with captured() as log:
                coll, route = make_collector(w, path)
                wake = coll.step()
            assert _status(path, "wind", _hm(6)).status == "incomplete"
            assert any("waits for backfill" in m for m in log.messages(logging.INFO))
            assert wake <= w.t + C.BACKFILL_RETRY_S
        finally:
            C.AUTO_BACKFILL_LIMIT = old

        # A current run pending (day D+1, due at 11:00, published 12:05) comes first.
        w.t = _hm(11, 30, day=1)
        with captured():
            coll, route = make_collector(w, path)
            coll.step()
        assert _status(path, "current", _hm(0, day=1)).status == "pending"
        assert _status(path, "wind", _hm(6)).status == "incomplete"   # no backfill yet
        with captured():
            run_until(w, coll, _hm(13, 0, day=1))
        assert _status(path, "current", _hm(0, day=1)).status == "complete"
        assert _status(path, "wind", _hm(6)).status == "complete"


# --- Waves -------------------------------------------------------------------------

def _models(url):
    return urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)["models"][0]


def test_waves_come_in_the_currents_requests():
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "a.h5")
        w = World(_hm(11))
        coll, route = make_collector(w, path)
        with captured():
            run_until(w, coll, _hm(12, 30))
        urls = w.data_urls("/v1/marine")
        assert len(urls) == 1 and _models(urls[0]) == "meteofrance_currents,meteofrance_wave"
        n = len(route.plan.queries[C.CURRENT])
        cur, wav = _status(path, "current", _hm(0)), _status(path, "wave", _hm(0))
        assert cur.status == wav.status == "complete"
        assert cur.api_calls == n and wav.api_calls == 0         # the waves cost nothing extra
        assert wav.availability_unix == _hm(12, 4) and "requests of current run" in wav.note
        run = A.read_run(path, "wave", _hm(0))
        hours = C.WAVE_LAST_LEAD_H + 1                           # period's extra hours cut
        assert run["time_unix"][0] == _hm(0) and len(run["time_unix"]) == hours
        assert run["wave_height_m"].shape == (n, hours)
        for k, q in enumerate(route.plan.queries[C.CURRENT]):
            height, direction, period = wave_value(q.grid_lat, q.grid_lon, _hm(0), _hm(5))
            assert math.isclose(run["wave_height_m"][k, 5], height, rel_tol=1e-5)
            assert math.isclose(run["wave_period_s"][k, 5], period, rel_tol=1e-5)
            assert run["wave_direction_deg"][k, 0] == direction
        at = run["attrs"]
        assert np.isnan(run["served_lat"]).all() and not at["served_points_reported"]
        assert at["substituted_cells"] == -1 and at["nan_cells"] == 0
        assert at["request_grids"] == "current,wave" and at["cell_table"] == "current_cells"
        assert at["fetch_start_unix"] == A.read_run_attrs(path, "current", _hm(0))["fetch_start_unix"]
        assert json.loads(at["api_params_json"])["models"] == "meteofrance_currents,meteofrance_wave"
        cur_run = A.read_run(path, "current", _hm(0))
        assert len(cur_run["time_unix"]) == 240 and not np.isnan(cur_run["served_lat"]).any()


def test_currents_wait_for_waves_published_a_little_later():
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "a.h5")
        w = World(_hm(12))
        w.wave_published[_hm(0)] = _hm(13, 30)
        coll, _ = make_collector(w, path)
        with captured() as log:
            run_until(w, coll, _hm(14))
        urls = w.data_urls("/v1/marine")
        assert len(urls) == 1 and "meteofrance_wave" in _models(urls[0])
        assert A.read_run_attrs(path, "current", _hm(0))["fetch_start_unix"] >= _hm(13, 40)
        assert _status(path, "wave", _hm(0)).status == "complete"
        assert any("waits for wave run" in m for m in log.messages(logging.INFO))


def test_late_waves_are_fetched_alone_within_the_budget():
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "a.h5")
        w = World(_hm(12))
        w.wave_published[_hm(0)] = _hm(15)          # after the 2 h grace (currents: 12:05)
        coll, route = make_collector(w, path)
        old, C.WAVE_ALONE_LIMIT = C.WAVE_ALONE_LIMIT, 1
        try:
            with captured() as log:
                run_until(w, coll, _hm(15, 30))
            assert _status(path, "current", _hm(0)).status == "complete"
            assert _status(path, "wave", _hm(0)).status == "pending"
            assert any("would exceed" in m for m in log.messages())
        finally:
            C.WAVE_ALONE_LIMIT = old
        with captured():
            run_until(w, coll, _hm(17))
        urls = w.data_urls("/v1/marine")
        assert [_models(u) for u in urls] == ["meteofrance_currents", "meteofrance_wave"]
        cur = A.read_run_attrs(path, "current", _hm(0))
        assert _hm(14, 5) <= cur["fetch_start_unix"] < _hm(14, 20)
        row = _status(path, "wave", _hm(0))
        assert row.status == "complete" and row.api_calls == len(route.plan.queries[C.CURRENT])
        run = A.read_run(path, "wave", _hm(0))
        assert run["attrs"]["served_points_reported"] and run["attrs"]["substituted_cells"] == 0
        assert not np.isnan(run["served_lat"]).any()


def test_waves_missed_when_their_next_run_comes_first():
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "a.h5")
        w = World(_hm(11))
        del w.wave_published[_hm(0)]                 # never published; 12 UTC at 00:04
        coll, _ = make_collector(w, path)
        with captured() as log:
            run_until(w, coll, _hm(1, 0, day=1))
        assert _status(path, "current", _hm(0)).status == "complete"
        row = _status(path, "wave", _hm(0))
        assert row.status == "missed" and "no archive" in row.note
        assert not A.has_run(path, "wave", _hm(0))
        assert any("wave run 2026-10-14T00 missed" in m for m in log.messages(logging.ERROR))
        assert all(_models(u) == "meteofrance_currents" for u in w.data_urls("/v1/marine"))


def test_archive_without_waves_gains_them_from_the_next_day():
    import h5py
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "a.h5")
        w = World(_hm(12, 30))
        coll, _ = make_collector(w, path)
        with captured():
            run_until(w, coll, _hm(13))
        # Make it look like an archive of the collector before waves.
        with h5py.File(path, "a") as f:
            del f["wave"]
            for k in [k for k in f.attrs if k.startswith(("wave_", "first_wave_"))]:
                del f.attrs[k]
            f.attrs["wave_height"] = "not collected."
        runs = A.read_runs(path)
        A.write_runs(path, runs[runs.grid != "wave"].reset_index(drop=True))

        w.t = _hm(13, 10)
        with captured() as log:
            coll, route = make_collector(w, path)
        attrs = A.read_attrs(path)
        assert attrs["first_wave_run_unix"] == _hm(0, day=1)   # today's currents came without
        assert "wave_height" not in attrs and attrs["wave_cell_table"] == "current_cells"
        assert any("waves collected from now on" in m for m in log.messages(logging.INFO))
        with captured():
            run_until(w, coll, _hm(13, 0, day=1))
        assert _status(path, "wave", _hm(0, day=1)).status == "complete"
        assert A.run_inits(path, "wave") == [_hm(0, day=1)]
        assert set(A.read_runs(path).status) == {"complete"}


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

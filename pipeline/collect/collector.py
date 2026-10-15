"""
Live weather collection: archive every model run once, cell by cell.

Open-Meteo's real-time ("current") value is the latest published run's hourly
series interpolated to the current 15-minute slot, so sampling it adds
nothing. The raw data needed later (for 15-minute pseudo real-time and
forecast series) is every run's full hourly forecast, and that is what is
stored, in shared/run_archive.py's layout.

Where to ask. The route is split into subsegments (shared/subsegments.py):
maximal stretches of one leg inside one wind cell and one current cell. Each
API is asked once per distinct cell, at the midpoint of the longest subsegment
inside it (a point the route actually sails through), with the grid's pinned
api_params from shared/weather_grids.py:

    wind     ECMWF IFS (models=ecmwf_ifs), from the Single Runs API, which serves
             any run by its start time and keeps them (archived since March 2024)
    current  Meteo-France SMOC (models=meteofrance_currents), from the Marine API,
             which has no archive: a run can only be read while it is the latest
    wave     Meteo-France MFWAM (models=meteofrance_wave), from the Marine API, no
             archive either. Same grid as the currents, so asked at the current
             cells' points and stored on the current cells

When to ask.
  Wind, run C (00/06/12/18 UTC): from C + 6 h, probe the Single Runs API for
  run C at one location every 10 minutes. Once it answers, fetch all cells
  (forecast_days=16) and cut the series at the run's last non-null hour
  (+360 h for 00/12 UTC, +144 h for 06/18 UTC). Failed chunks are retried
  every 10 minutes until done, or until run C + 6 h is published; run C is
  then logged as missed, and --backfill-wind can fetch it from the archive.
  Current, run D (00 UTC): from D 11:00 UTC, read Open-Meteo's metadata every
  10 minutes. When it shows run D, wait until its availability time + 10
  minutes, then fetch all cells for D 00:00 .. D + 239 h (start_hour/end_hour,
  so a retry after midnight still gets the first day). Re-read the metadata
  after the fetch and discard the data if the run changed meanwhile, since it
  could mix runs. Failed chunks are retried every 10 minutes until done or
  until run D + 1 is published: a hard deadline, there is no archive.
  Waves, run D (00 UTC): MFWAM also runs at 12 UTC, but only the 00 UTC run is
  kept, and it comes in the same requests as currents run D (both models, five
  variables: still one call per location, so the waves cost no extra calls).
  Both are normally published within minutes of each other (about 12:05 UTC);
  the currents wait for the waves up to WAVE_GRACE_S after their own
  publication. If the waves miss that (or are not in by D 18:00 while the
  currents are still pending), they are fetched on their own, at one more call
  per cell, if the calls of the last 24 h allow it, until run D 12 UTC is
  published. Data is kept only if the metadata did not change during the fetch.

Every response reports the grid point that served it; it is compared with the
grid point predicted by shared/weather_grids.py, and a mismatch (near land the
API substitutes a nearby sea point for a land-masked one) is logged and the
served points are stored. NaN in a model input (wind speed, which sets the
Beaufort number, wind direction, current velocity and direction) is logged as
a warning and counted in the run's attributes.

Waves (height, direction, period) are archived for later use: the present
speed and fuel model does not read wave height (see
docs/weather_resolution_audit_2026_09_06.html).

The command line and the main loop are in run_all.py.
"""

from __future__ import annotations

import collections
import hashlib
import http.client
import json
import logging
import math
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable, Dict, List, Mapping, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

from shared import run_archive
from shared.rhumb import RhumbLeg
from shared.subsegments import MERGE_TOL_NM, PORT_TRIM_NM, Subsegment, partition_route, trim_route
from shared.weather_grids import CURRENT_GRID, WAVE_GRID, WIND_GRID

logger = logging.getLogger(__name__)

WIND, CURRENT, WAVE = "wind", "current", "wave"
GRIDS = {WIND: WIND_GRID, CURRENT: CURRENT_GRID}        # the grids that split the route
COLLECTED = {WIND: WIND_GRID, CURRENT: CURRENT_GRID, WAVE: WAVE_GRID}
CELLS_OF = {WIND: WIND, CURRENT: CURRENT, WAVE: CURRENT}   # whose cells a grid is asked at

# Open-Meteo hourly variable -> stored column. Wind and wave directions are the
# direction they come from, current direction the direction it flows to.
API_FIELDS = {
    WIND: {"wind_speed_10m": "wind_speed_10m_kmh",
           "wind_direction_10m": "wind_direction_10m_deg"},
    CURRENT: {"ocean_current_velocity": "ocean_current_velocity_kmh",
              "ocean_current_direction": "ocean_current_direction_deg"},
    WAVE: {"wave_height": "wave_height_m", "wave_direction": "wave_direction_deg",
           "wave_period": "wave_period_s"},
}
EXPECTED_UNITS = {"wind_speed_10m": "km/h", "wind_direction_10m": "°",
                  "ocean_current_velocity": "km/h", "ocean_current_direction": "°",
                  "wave_height": "m", "wave_direction": "°", "wave_period": "s"}

# Where runs are read. The Single Runs API serves the same grid points as the
# live Forecast API (WIND_GRID.api_url), with identical values.
RUN_API_URLS = {WIND: "https://single-runs-api.open-meteo.com/v1/forecast",
                CURRENT: CURRENT_GRID.api_url, WAVE: WAVE_GRID.api_url}
EXTRA_PARAMS = {WIND: {"wind_speed_unit": "kmh"}, CURRENT: {}, WAVE: {}}
NOT_AVAILABLE = "model run is not available"   # reason of HTTP 400 for an unpublished run

HOUR = 3600
WIND_CYCLE_S = 6 * HOUR             # ECMWF runs at 00/06/12/18 UTC
WIND_DUE_AFTER_S = 6 * HOUR         # first metadata read for run C at C + 6 h
WIND_FORECAST_DAYS = 16             # request window; the run is cut at its last value
WIND_LAST_LEAD_H = {0: 360, 6: 144, 12: 360, 18: 144}   # by cycle hour: a complete run
CURRENT_CYCLE_S = 24 * HOUR         # SMOC runs once a day, at 00 UTC
CURRENT_DUE_AFTER_S = 11 * HOUR     # first metadata read for run D at D 11:00 UTC
CURRENT_SPAN_H = 240                # D 00:00 .. D + 239 h; also the waves' request window
WAVE_CYCLE_S = 24 * HOUR            # MFWAM runs at 00 and 12 UTC; the 00 UTC run is kept
WAVE_DUE_AFTER_S = 11 * HOUR        # as the currents, whose requests it shares
WAVE_LAST_LEAD_H = 227              # MFWAM as served hourly: height and direction to +227 h
                                    # (period to +230 h), seen on the 2026-10-14 12 UTC run
WAVE_GRACE_S = 2 * HOUR             # currents wait this long after their publication for the waves
WAVE_ALONE_AFTER_S = 18 * HOUR      # waves stop waiting for pending currents at D 18:00 UTC
WAVE_ALONE_LIMIT = 9700             # a waves-only fetch only if the last 24 h stay below this
SCHEDULE = {WIND: (WIND_CYCLE_S, WIND_DUE_AFTER_S), CURRENT: (CURRENT_CYCLE_S, CURRENT_DUE_AFTER_S),
            WAVE: (WAVE_CYCLE_S, WAVE_DUE_AFTER_S)}      # grid -> (cycle, first check after start)
SETTLE_S = 600                      # Open-Meteo: wait 10 min after the availability time
RETRY_S = 600                       # probes, metadata reads and failed chunks
# The Single Runs archive serves a run as soon as its first hours arrive (on
# 2026-10-15 the 00 UTC run answered at 06:00 with +0..+72 h, hours before
# Open-Meteo published it), so "available" is not "complete". A wind run is
# fetched only once the metadata shows it published and a probe shows its full
# span, and a short run is never stored as complete.
# Missed and incomplete wind runs are refetched from the archive automatically,
# one per step, once they are a day old (complete in the archive), while no
# current run is pending, and only if the calls of the last 24 h plus the
# refetch stay within AUTO_BACKFILL_LIMIT.
BACKFILL_MIN_AGE_S = 24 * HOUR
AUTO_BACKFILL_LIMIT = 9000
BACKFILL_RETRY_S = HOUR

COORD_DECIMALS = 6     # query coordinates as sent (about 0.1 m)
MATCH_TOL_DEG = 1e-4   # served vs predicted grid point; the API reports float32

# A request for n locations counts as n calls (query_weight); the free tier
# allows 600 calls per minute, 5,000 per hour and 10,000 per day per IP.
CHUNK_SIZE = 100            # locations per request; longer URLs risk HTTP 414
SECONDS_PER_CHUNK = 15.0    # request starts at least this far apart: <= 400 calls/min
ATTEMPTS = 2                # per request within one round; failed chunks wait RETRY_S
API_LIMITS = {"minute": 600, "hour": 5000, "day": 10000}
# Probes per wind run: about 3 for 06/18 UTC runs and 13 for 00/12 UTC runs
# (published 6.4 h and 8.0 h after the cycle on 2026-10-14); a run probed
# until the next one is published (about 7 h of probing) costs 42.
PROBES_PER_DAY_TYPICAL = 32
PROBES_PER_RUN_MAX = 42

WAVE_NOTE = ("Meteo-France MFWAM (models=meteofrance_wave), the 00 UTC run of each day, "
             "fetched in the same requests as that day's currents run. Same 1/12 deg grid as "
             "the currents: rows follow /plan/current_cells. Native 3-hourly from the run "
             "start; the hours between are Open-Meteo's interpolation. wave_direction_deg is "
             "the direction the waves come from. Not read by the present speed and fuel model.")


class ApiError(RuntimeError):
    """A request that failed (after its quick retries, or not worth retrying)."""


class RunNotAvailable(ApiError):
    """The Single Runs API does not (yet) have the requested run."""


class DailyLimitExceeded(ApiError):
    """Open-Meteo refused the request because this IP used up its daily calls."""


class PlanMismatch(RuntimeError):
    """An existing archive was built from a different route partition."""


def utc(unix: float) -> str:
    return datetime.fromtimestamp(unix, timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def _iso_minute(unix: int) -> str:
    return datetime.fromtimestamp(unix, timezone.utc).strftime("%Y-%m-%dT%H:%M")


# ---------------------------------------------------------------------------
# Sampling plan: subsegments, the cells they lie in, and where to query
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class CellQuery:
    """A cell of one weather grid that the route passes through."""
    grid: str                       # WIND or CURRENT
    cell: Tuple[int, int]           # (row, col) in that grid
    query_lat: float                # a point of the route inside the cell, as sent
    query_lon: float
    grid_lat: float                 # grid point predicted to serve the cell
    grid_lon: float
    subsegments: Tuple[int, ...]    # indices of the subsegments inside the cell
    length_nm: float                # route length inside the cell


@dataclass
class SamplingPlan:
    """What to ask the APIs for one route, and how to map the answers back."""
    route_key: str
    route_name: str
    waypoints: List[Tuple[float, float]]
    port_trim_nm: float
    grids: Dict[str, object]
    subsegments: List[Subsegment]
    midpoints: List[Tuple[float, float]]
    endpoints: List[Tuple[float, float]]
    queries: Dict[str, List[CellQuery]]     # per grid, in order of first appearance
    cell_index: Dict[str, np.ndarray]       # per grid: subsegment index -> position in queries
    fingerprint: str                        # changes whenever the partition or the queries do


def _as_lat_lon(waypoint) -> Tuple[float, float]:
    if isinstance(waypoint, Mapping):
        return float(waypoint["lat"]), float(waypoint["lon"])
    lat, lon = waypoint
    return float(lat), float(lon)


# A query point closer than this to its cell's edge may be resolved into the
# neighboring cell by the server, which works with float32 coordinates (a test
# point lying exactly on a 1/12 deg edge was served the cell across it).
MIN_EDGE_MARGIN_NM = 0.05
_MARGIN_STEPS_NM = (0.001, 0.002, 0.005, 0.01, 0.02, 0.05)


def _edge_margin(grid, cell, lat: float, lon: float) -> float:
    """How far (NM, one of _MARGIN_STEPS_NM, or 0) the point can move in any of
    eight directions and stay in `cell`."""
    margin = 0.0
    for r in _MARGIN_STEPS_NM:
        dlat, dlon = r / 60.0, r / (60.0 * math.cos(math.radians(lat)))
        if any(grid.cell_of(lat + a * dlat, lon + b * dlon) != cell
               for a in (-1, 0, 1) for b in (-1, 0, 1) if a or b):
            break
        margin = r
    return margin


def _query_point(grid, cell, ids: Sequence[int], point) -> Tuple[float, float]:
    """A point of the route inside `cell`, as sent: the midpoint of the longest
    subsegment, or, if that lies within MIN_EDGE_MARGIN_NM of the cell's edge,
    the point along the cell's subsegments farthest from it."""
    def sent(i, frac):
        return tuple(round(x, COORD_DECIMALS) for x in point(i, frac))

    first = sent(ids[0], 0.5)          # ids are sorted by length, longest first
    if grid.cell_of(*first) == cell and _edge_margin(grid, cell, *first) >= MIN_EDGE_MARGIN_NM:
        return first
    best, best_margin = None, -1.0
    for i in ids:
        for frac in [0.5] + [k / 20 for k in range(1, 20) if k != 10]:
            p = sent(i, frac)
            if grid.cell_of(*p) == cell:
                m = _edge_margin(grid, cell, *p)
                if m > best_margin:
                    best, best_margin = p, m
    if best is None:
        logger.warning("No point of the route rounds into %s cell %s; querying (%.6f, %.6f)",
                       grid.name, cell, *first)
        return first
    return best


def build_sampling_plan(waypoints: Sequence, route_key: str = "", route_name: str = "",
                        grids: Optional[Mapping] = None,
                        port_trim_nm: float = PORT_TRIM_NM) -> SamplingPlan:
    """Partition the route and choose one query point per distinct cell of each grid.

    Args:
        waypoints: Route waypoints in sailing order, as (lat, lon) pairs or as
            dicts with 'lat' and 'lon' (the format of config/routes/*.yaml).
        route_key, route_name: Labels stored with the data.
        grids: {WIND: grid, CURRENT: grid}; defaults to the pinned Open-Meteo grids.
        port_trim_nm: Distance cut off at each end of the route.
    """
    grids = dict(GRIDS if grids is None else grids)
    subs = partition_route(waypoints, grids=grids, port_trim_nm=port_trim_nm)
    points = trim_route(waypoints, port_trim_nm, port_trim_nm)
    legs = [RhumbLeg(*a, *b) for a, b in zip(points, points[1:])]
    # Distance of each leg start along the trimmed route, accumulated as
    # partition_route does (it skips legs shorter than MERGE_TOL_NM).
    leg_start, total = [], 0.0
    for leg in legs:
        leg_start.append(total)
        if leg.length_nm >= MERGE_TOL_NM:
            total += leg.length_nm

    def point(s: Subsegment, frac: float) -> Tuple[float, float]:
        leg = legs[s.leg]
        return leg.point_at((s.start_nm + frac * s.length_nm - leg_start[s.leg]) / leg.length_nm)

    for s in subs:
        lat, lon = point(s, 0.0)
        if abs(lat - s.start_lat) > 1e-6 or abs((lon - s.start_lon + 180.0) % 360.0 - 180.0) > 1e-6:
            raise RuntimeError(f"subsegment {s.index} does not start where its leg puts it; "
                               "has shared/subsegments.py changed its conventions?")
    midpoints = [point(s, 0.5) for s in subs]
    endpoints = [point(s, 1.0) for s in subs]

    queries: Dict[str, List[CellQuery]] = {}
    cell_index: Dict[str, np.ndarray] = {}
    for name, grid in grids.items():
        members: Dict[Tuple[int, int], List[int]] = {}   # insertion order = first appearance
        for s in subs:
            members.setdefault(s.cells[name], []).append(s.index)
        index = np.empty(len(subs), dtype=np.int64)
        cells = []
        for k, (cell, ids) in enumerate(members.items()):
            by_length = sorted(ids, key=lambda i: -subs[i].length_nm)
            qlat, qlon = _query_point(grid, cell, by_length, lambda i, f: point(subs[i], f))
            glat, glon = grid.center_of(cell)
            cells.append(CellQuery(name, tuple(cell), qlat, qlon, glat, glon, tuple(ids),
                                   sum(subs[i].length_nm for i in ids)))
            index[ids] = k
        queries[name], cell_index[name] = cells, index

    blob = json.dumps({
        "grids": {n: [g.name, g.api_url, g.api_params] for n, g in sorted(grids.items())},
        "port_trim_nm": port_trim_nm,
        "subsegments": [[s.leg, round(s.start_nm, 6), round(s.length_nm, 6),
                         [list(s.cells[n]) for n in sorted(grids)]] for s in subs],
        "queries": {n: [[q.query_lat, q.query_lon] for q in qs] for n, qs in sorted(queries.items())},
    }, sort_keys=True, separators=(",", ":"))

    return SamplingPlan(
        route_key=route_key, route_name=route_name,
        waypoints=[_as_lat_lon(w) for w in waypoints], port_trim_nm=port_trim_nm,
        grids=grids, subsegments=subs, midpoints=midpoints, endpoints=endpoints,
        queries=queries, cell_index=cell_index,
        fingerprint=hashlib.sha256(blob.encode()).hexdigest()[:16],
    )


def plan_tables(plan: SamplingPlan) -> Tuple[pd.DataFrame, Dict[str, pd.DataFrame]]:
    """/plan/subsegments and the per-grid cell tables of shared/run_archive.py."""
    subs = pd.DataFrame([{
        "index": s.index, "leg": s.leg, "start_nm": s.start_nm, "length_nm": s.length_nm,
        "bearing_deg": s.bearing_deg, "start_lat": s.start_lat, "start_lon": s.start_lon,
        "mid_lat": plan.midpoints[s.index][0], "mid_lon": plan.midpoints[s.index][1],
        "end_lat": plan.endpoints[s.index][0], "end_lon": plan.endpoints[s.index][1],
        "wind_cell": int(plan.cell_index[WIND][s.index]),
        "current_cell": int(plan.cell_index[CURRENT][s.index]),
    } for s in plan.subsegments])
    cells = {g: pd.DataFrame([{
        "index": k, "row": q.cell[0], "col": q.cell[1], "grid_lat": q.grid_lat,
        "grid_lon": q.grid_lon, "query_lat": q.query_lat, "query_lon": q.query_lon,
        "length_nm": q.length_nm, "first_subsegment": q.subsegments[0],
        "n_subsegments": len(q.subsegments),
    } for k, q in enumerate(plan.queries[g])]) for g in (WIND, CURRENT)}
    return subs, cells


# ---------------------------------------------------------------------------
# API budget
# ---------------------------------------------------------------------------

def query_weight(n_variables: int, days: float, n_models: int = 1) -> float:
    """API calls that Open-Meteo counts for one location of a request.

    Mirrors calculateQueryWeight() of the Open-Meteo server
    (open-meteo/open-meteo, Sources/App/Helper/Writer/ForecastApiResult.swift):
    with V = requested variables (current + hourly + ...) times models and
    `days` the length of the requested time range, a location costs
    max(1, V / 10, V / 10 * days / 14) calls.
    """
    v = n_variables * n_models / 10.0
    return max(1.0, v, v * days / 14.0)


def request_weight(grids: Sequence[str]) -> float:
    """Calls per location of a request for these grids' runs (one model each)."""
    days = WIND_FORECAST_DAYS if grids[0] == WIND else CURRENT_SPAN_H / 24
    return query_weight(sum(len(API_FIELDS[g]) for g in grids), days, n_models=len(grids))


WEIGHT = {g: request_weight((g,)) for g in (WIND, CURRENT, WAVE)}
# Currents and waves in one request: 5 variables x 2 models, still one call.
WEIGHT_CURRENT_WITH_WAVE = request_weight((CURRENT, WAVE))


def daily_calls(plan: SamplingPlan) -> Dict[str, float]:
    """Planned calls per day for one route, without retries. 'wave' is what the
    waves add to the currents' requests; 'wave_alone' what a waves-only fetch costs."""
    wind = len(plan.queries[WIND]) * WEIGHT[WIND] * (24 * HOUR // WIND_CYCLE_S)
    current = len(plan.queries[CURRENT]) * WEIGHT[CURRENT] * (24 * HOUR // CURRENT_CYCLE_S)
    with_wave = (len(plan.queries[CURRENT]) * WEIGHT_CURRENT_WITH_WAVE
                 * (24 * HOUR // CURRENT_CYCLE_S))
    runs = 24 * HOUR // WIND_CYCLE_S
    return {"wind": wind, "current": current, "wave": with_wave - current,
            "wave_alone": len(plan.queries[CELLS_OF[WAVE]]) * WEIGHT[WAVE],
            "probes_typical": PROBES_PER_DAY_TYPICAL * WEIGHT[WIND],
            "probes_max": PROBES_PER_RUN_MAX * runs * WEIGHT[WIND]}


# ---------------------------------------------------------------------------
# Requests
# ---------------------------------------------------------------------------

def http_get_json(url: str, timeout: float = 60.0):
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return json.load(r)


class Pacer:
    """Keeps request starts at least `interval` seconds apart."""

    def __init__(self, interval: float = SECONDS_PER_CHUNK,
                 sleep: Callable[[float], None] = time.sleep,
                 clock: Callable[[], float] = time.monotonic):
        self.interval, self.sleep, self.clock = interval, sleep, clock
        self._last: Optional[float] = None

    def wait(self) -> None:
        if self._last is not None:
            delay = self._last + self.interval - self.clock()
            if delay > 0:
                self.sleep(delay)
        self._last = self.clock()


def _error_reason(e: urllib.error.HTTPError) -> str:
    try:
        return str(json.loads(e.read().decode("utf-8", "replace")).get("reason", e))
    except Exception:
        return str(e)


class ApiClient:
    """Paced JSON requests to Open-Meteo, counting every attempt as API calls."""

    def __init__(self, get: Callable = http_get_json, pacer: Optional[Pacer] = None,
                 clock: Callable[[], float] = time.time, attempts: int = ATTEMPTS):
        self.get, self.pacer, self.clock, self.attempts = get, pacer or Pacer(), clock, attempts
        self.calls = 0.0                  # Open-Meteo's count, all attempts
        self.requests = 0
        self._recent = collections.deque()   # (time, calls) of the last 24 h

    def calls_last_24h(self) -> float:
        cutoff = self.clock() - 24 * HOUR
        while self._recent and self._recent[0][0] < cutoff:
            self._recent.popleft()
        return sum(c for _, c in self._recent)

    def get_json(self, url: str, weight: float):
        """GET `url`; a failure is retried once after a short wait within the round."""
        for attempt in range(1, self.attempts + 1):
            self.pacer.wait()
            self.requests += 1
            self.calls += weight
            self._recent.append((self.clock(), weight))
            try:
                return self.get(url)
            except urllib.error.HTTPError as e:
                reason = _error_reason(e)
                if e.code == 400 and NOT_AVAILABLE in reason:
                    raise RunNotAvailable(reason) from None
                if e.code == 429:
                    if "daily" in reason.lower():
                        raise DailyLimitExceeded(reason) from None
                    if "hourly" in reason.lower():
                        raise ApiError(f"HTTP 429: {reason}") from None
                    wait = 60
                elif e.code >= 500:
                    wait = 30
                else:
                    raise ApiError(f"HTTP {e.code}: {reason}") from None
                problem = f"HTTP {e.code}: {reason}"
            except (OSError, ValueError, http.client.HTTPException) as e:   # network, timeouts, bad JSON
                wait, problem = 30, repr(e)
            if attempt == self.attempts:
                raise ApiError(problem)
            logger.warning("Request to %s failed (%s); retrying in %d s",
                           urllib.parse.urlsplit(url).netloc, problem, wait)
            self.pacer.sleep(wait)

    def model_run(self, grid) -> Tuple[int, int]:
        """(initialization, availability) Unix times of the newest published run of
        the grid's model, from the static metadata file behind
        open-meteo.com/en/docs/model-updates (not the forecast API); (-1, -1) if
        it cannot be read."""
        parts = urllib.parse.urlsplit(grid.api_url)
        url = f"{parts.scheme}://{parts.netloc}/data/{grid.api_params['models']}/static/meta.json"
        try:
            meta = self.get(url)
            return int(meta["last_run_initialisation_time"]), int(meta["last_run_availability_time"])
        except Exception as e:
            logger.warning("Could not read model metadata %s: %r", url, e)
            return -1, -1


def run_params(grid_key: str, grid, chunk: Sequence[CellQuery], run_init: int,
               riders: Sequence[Tuple[str, object]] = ()) -> dict:
    """Query parameters for one chunk of one run; the grid's model and cell selection win.
    `riders` are (grid key, grid) of runs asked in the same request: same API, window
    and cell selection, their own model and variables (the answer then names each
    variable with a _<model> suffix)."""
    for g in [grid] + [g for _, g in riders]:
        if not {"models", "cell_selection"} <= set(g.api_params):
            raise ValueError(f"{g.name}.api_params must pin models and cell_selection")
    for key, g in riders:
        if (RUN_API_URLS[key] != RUN_API_URLS[grid_key] or key == WIND
                or g.api_params["cell_selection"] != grid.api_params["cell_selection"]):
            raise ValueError(f"{key} runs cannot be asked in the same request as {grid_key} runs")
    if grid_key == WIND:
        window = {"run": _iso_minute(run_init), "forecast_days": WIND_FORECAST_DAYS}
    else:
        window = {"start_hour": _iso_minute(run_init),
                  "end_hour": _iso_minute(run_init + (CURRENT_SPAN_H - 1) * HOUR)}
    return {
        "latitude": ",".join(f"{q.query_lat:.{COORD_DECIMALS}f}" for q in chunk),
        "longitude": ",".join(f"{q.query_lon:.{COORD_DECIMALS}f}" for q in chunk),
        "hourly": ",".join([v for k in [grid_key] + [k for k, _ in riders] for v in API_FIELDS[k]]),
        **window,
        "timezone": "GMT",
        "timeformat": "unixtime",
        **EXTRA_PARAMS[grid_key],
        **grid.api_params,
        "models": ",".join([grid.api_params["models"]] + [g.api_params["models"] for _, g in riders]),
    }


def run_url(grid_key: str, grid, chunk: Sequence[CellQuery], run_init: int,
            riders: Sequence[Tuple[str, object]] = ()) -> str:
    params = run_params(grid_key, grid, chunk, run_init, riders)
    return f"{RUN_API_URLS[grid_key]}?{urllib.parse.urlencode(params)}"


# ---------------------------------------------------------------------------
# Responses
# ---------------------------------------------------------------------------

@dataclass
class GridRun:
    """One run of one grid for all cells of a route."""
    served_lat: np.ndarray            # (n_cells,) grid point the API used
    served_lon: np.ndarray
    time: np.ndarray                  # (n_hours,) Unix seconds
    values: Dict[str, np.ndarray]     # column -> (n_cells, n_hours), NaN for null


def parse_run(grid_key: str, bodies: Sequence[dict], suffix: str = "") -> GridRun:
    """Collect the JSON bodies (one per cell, in cell order) into arrays. `suffix`
    ('_<model>') when the request asked for several models."""
    try:
        fields = API_FIELDS[grid_key]
        if not bodies:
            raise ApiError(f"no {grid_key} responses")
        time_axis = np.asarray(bodies[0]["hourly"]["time"], dtype=np.int64)
        values = {col: np.full((len(bodies), len(time_axis)), np.nan) for col in fields.values()}
        for i, b in enumerate(bodies):
            units = b.get("hourly_units", {})
            for var in fields:
                if units.get(var + suffix) != EXPECTED_UNITS[var]:
                    raise ApiError(f"{var + suffix} in {units.get(var + suffix)!r}, "
                                   f"expected {EXPECTED_UNITS[var]!r}")
            if not np.array_equal(np.asarray(b["hourly"]["time"], dtype=np.int64), time_axis):
                raise ApiError(f"{grid_key}: hourly time axes differ between locations")
            for var, col in fields.items():
                values[col][i] = np.array(b["hourly"][var + suffix], dtype=float)   # None -> NaN
        return GridRun(np.array([float(b["latitude"]) for b in bodies]),
                       np.array([float(b["longitude"]) for b in bodies]), time_axis, values)
    except (KeyError, TypeError, ValueError) as e:
        raise ApiError(f"malformed {grid_key} response: {e!r}") from None


def expected_last_lead(grid: str, init: int) -> int:
    """Last lead (h) of a complete run of the grid started at init."""
    if grid == WIND:
        return WIND_LAST_LEAD_H[datetime.fromtimestamp(init, timezone.utc).hour]
    if grid == WAVE:
        return WAVE_LAST_LEAD_H
    return CURRENT_SPAN_H - 1


def last_lead_in(body, init: int) -> int:
    """Last lead (h) with a value in one location's response; -1 if none."""
    body = body[0] if isinstance(body, list) else body
    hourly = body["hourly"]
    times = hourly["time"]
    last = -1
    for i, t in enumerate(times):
        if any(hourly[v][i] is not None for v in hourly if v != "time"):
            last = (int(t) - init) // HOUR
    return last


def cut_to_span(run: GridRun) -> GridRun:
    """Keep the hours from the first to the last at which every variable has a value
    (at some cell). MFWAM's wave period runs a few hours past its wave height."""
    has = np.ones(len(run.time), dtype=bool)
    for arr in run.values.values():
        has &= ~np.isnan(arr).all(axis=0)
    idx = np.flatnonzero(has)
    if len(idx) == 0:
        raise ApiError("the run returned no values")
    a, b = idx[0], idx[-1] + 1
    return GridRun(run.served_lat, run.served_lon, run.time[a:b],
                   {c: v[:, a:b] for c, v in run.values.items()})


def find_substitutions(queries: Sequence[CellQuery], run: GridRun,
                       tol_deg: float = MATCH_TOL_DEG) -> List[int]:
    """Cells served by a different grid point than predicted."""
    out = []
    for k, q in enumerate(queries):
        dlat = abs(run.served_lat[k] - q.grid_lat)
        dlon = abs((run.served_lon[k] - q.grid_lon + 180.0) % 360.0 - 180.0)
        if not (dlat <= tol_deg and dlon <= tol_deg):   # NaN coordinates count as a mismatch
            out.append(k)
    return out


def find_nan_cells(run: GridRun) -> Dict[int, Tuple[int, int]]:
    """Cells with NaN in a variable within the run's span: k -> (NaN values, values)."""
    nan = np.stack([np.isnan(v) for v in run.values.values()], axis=1)   # (n, fields, t)
    n_all = nan.shape[1] * nan.shape[2]
    return {int(k): (int(nan[k].sum()), n_all) for k in np.flatnonzero(nan.any(axis=(1, 2)))}


def _nm_apart(lat1, lon1, lat2, lon2) -> float:
    dlon = (lon2 - lon1 + 180.0) % 360.0 - 180.0
    return 60.0 * math.hypot(lat2 - lat1, dlon * math.cos(math.radians(0.5 * (lat1 + lat2))))


# ---------------------------------------------------------------------------
# One route: its plan, its archive and the status of its runs
# ---------------------------------------------------------------------------

def _floor(t: float, period: int) -> int:
    return int(t // period * period)


@dataclass
class _Work:
    """Progress of one run of one route within this process (lost on restart)."""
    next_try: int
    first_probe_success: int = -1
    availability: int = -1
    fetch_meta: Optional[Tuple[int, int]] = None   # currents, waves: metadata when the fetch began
    chunks: Dict[int, list] = field(default_factory=dict)
    fetch_start: int = -1
    request: Tuple[str, ...] = ()       # grids asked in the chunks' requests; () = this grid alone
    riders_done: bool = False           # the other grids of `request` have been dealt with


class RouteRuns:
    """The archive file of one route and the status of every expected run.

    Expected runs start with the newest run that was due when the file was
    created (attributes first_wind_run_unix, first_current_run_unix,
    first_wave_run_unix) and continue with every later cycle, so a restart
    finds the runs that came due meanwhile. An archive created before waves
    were collected gains them on opening, from the first day whose currents
    are not yet fetched.
    """

    def __init__(self, label: str, plan: SamplingPlan, path: str,
                 clock: Callable[[], float] = time.time):
        self.label, self.plan, self.path, self.clock = label, plan, path, clock
        self.rows: Dict[Tuple[str, int], dict] = {}
        self.work: Dict[Tuple[str, int], _Work] = {}
        self.attrs: Optional[dict] = None
        self._last_substitutions: Dict[str, Optional[dict]] = {g: None for g in COLLECTED}
        geometry = ("lat_first", "lon_first", "dlat", "dlon", "n_lat", "n_lon")
        if any(getattr(plan.grids[CURRENT], k, None) != getattr(WAVE_GRID, k) for k in geometry):
            raise ValueError("wave runs are stored on the current cells, so the plan's current "
                             "grid must have the geometry of WAVE_GRID")
        if os.path.exists(path):
            self.attrs = run_archive.read_attrs(path)
            if self.attrs.get("layout") != run_archive.LAYOUT:
                raise PlanMismatch(f"{path} is not a model-run archive; choose another file")
            if self.attrs.get("plan_fingerprint") != plan.fingerprint:
                raise PlanMismatch(
                    f"{path} was built from a different partition of {plan.route_key} "
                    f"(fingerprint {self.attrs.get('plan_fingerprint')}, now {plan.fingerprint}): "
                    "the route waypoints or the grids changed. Start a new file (move this one "
                    "away or use another --data-dir); appending would mismatch cell indices.")
            for row in run_archive.read_runs(path).to_dict("records"):
                self.rows[(row["grid"], int(row["run_init_unix"]))] = row
            for (g, init), row in self.rows.items():
                if row["status"] == "pending" and run_archive.has_run(path, g, init):
                    self._set(row, "complete", "found stored at restart")
            for (g, init), row in self.rows.items():
                if g == WIND and row["status"] == "complete" and run_archive.has_run(path, g, init):
                    last = int(run_archive.read_run_attrs(path, g, init).get("last_lead_hours", -1))
                    if last < expected_last_lead(g, init):
                        self._set(row, "incomplete",
                                  f"stored +0..+{last} h of +{expected_last_lead(g, init)} h; "
                                  "refetched from the archive automatically")
                        logger.warning("[%s] wind run %s holds only +0..+%d h; marked incomplete",
                                       label, run_archive.run_name(init), last)
            if "first_wave_run_unix" not in self.attrs:
                self._add_waves(self.clock())

    def _wave_attrs(self, first_wave: int) -> dict:
        return {"first_wave_run_unix": first_wave, "first_wave_run_utc": utc(first_wave),
                "wave_cycle_hours": WAVE_CYCLE_S // HOUR, "wave_grid": WAVE_GRID.name,
                "wave_api_url": RUN_API_URLS[WAVE],
                "wave_api_params_json": json.dumps(WAVE_GRID.api_params),
                "wave_variables_json": json.dumps(API_FIELDS[WAVE]),
                "wave_cell_table": run_archive.CELL_TABLES[WAVE], "wave_note": WAVE_NOTE}

    def _add_waves(self, now: float) -> None:
        first = _floor(now - WAVE_DUE_AFTER_S, WAVE_CYCLE_S)
        if self.status(CURRENT, first) not in (None, "pending"):
            first += WAVE_CYCLE_S       # that day's currents came without waves
        run_archive.add_grid(self.path, WAVE, self._wave_attrs(first), drop_attrs=("wave_height",))
        self.attrs = run_archive.read_attrs(self.path)
        logger.info("[%s] %s: waves collected from now on; first wave run %s", self.label,
                    self.path, utc(first))

    def create(self, now: float) -> None:
        """Create the archive; the first expected runs are the newest already due."""
        p = self.plan
        first_wind = _floor(now - WIND_DUE_AFTER_S, WIND_CYCLE_S)
        first_current = _floor(now - CURRENT_DUE_AFTER_S, CURRENT_CYCLE_S)
        attrs = {
            "source": "live_collection",
            "route_label": self.label,
            "route_key": p.route_key,
            "route_name": p.route_name,
            "route_waypoints_json": json.dumps(p.waypoints),
            "port_trim_nm": p.port_trim_nm,
            "plan_fingerprint": p.fingerprint,
            "n_subsegments": len(p.subsegments),
            "first_wind_run_unix": first_wind,
            "first_wind_run_utc": utc(first_wind),
            "first_current_run_unix": first_current,
            "first_current_run_utc": utc(first_current),
            "wind_cycle_hours": WIND_CYCLE_S // HOUR,
            "current_cycle_hours": CURRENT_CYCLE_S // HOUR,
            "time_definition": "time_unix: forecast valid times, UTC Unix seconds; a run's "
                               "lead is time_unix - run_init_unix",
        }
        for g, grid in p.grids.items():
            attrs[f"{g}_grid"] = grid.name
            attrs[f"{g}_api_url"] = RUN_API_URLS[g]
            attrs[f"{g}_api_params_json"] = json.dumps(grid.api_params)
            attrs[f"{g}_variables_json"] = json.dumps(API_FIELDS[g])
            attrs[f"n_{g}_cells"] = len(p.queries[g])
        attrs.update(self._wave_attrs(first_current))
        subs, cells = plan_tables(p)
        run_archive.create_archive(self.path, subs, cells, attrs)
        self.attrs = run_archive.read_attrs(self.path)
        logger.info("[%s] Created %s: %d subsegments, %d wind and %d current cells; first runs: "
                    "wind %s, current %s", self.label, self.path, len(p.subsegments),
                    len(p.queries[WIND]), len(p.queries[CURRENT]), utc(first_wind),
                    utc(first_current))

    # --- runs table -------------------------------------------------------

    def _schedules(self) -> List[Tuple[str, int, int, int]]:
        """(grid, first run, cycle, due after) of every collected grid."""
        return [(g, int(self.attrs[f"first_{g}_run_unix"]), *SCHEDULE[g]) for g in COLLECTED
                if f"first_{g}_run_unix" in self.attrs]

    def add_due_runs(self, now: float) -> None:
        for g, first, cycle, due in self._schedules():
            init = int(first)
            while init + due <= now:
                if (g, init) not in self.rows:
                    self.rows[(g, init)] = {
                        "grid": g, "run_init_unix": init, "status": "pending",
                        "probe_attempts": 0, "fetch_requests": 0, "api_calls": 0.0,
                        "first_probe_success_unix": -1, "availability_unix": -1,
                        "fetch_start_unix": -1, "fetch_end_unix": -1,
                        "updated_unix": int(now), "note": ""}
                init += cycle

    def next_due(self, now: float) -> int:
        """When the next run that is not yet due becomes due."""
        out = []
        for _, first, cycle, due in self._schedules():
            k = max(0, math.floor((now - due - first) / cycle) + 1)
            out.append(int(first + k * cycle + due))
        return min(out)

    def pending(self, grid: str) -> List[int]:
        return sorted(init for (g, init), row in self.rows.items()
                      if g == grid and row["status"] == "pending")

    def status(self, grid: str, init: int) -> Optional[str]:
        row = self.rows.get((grid, init))
        return None if row is None else row["status"]

    def work_for(self, grid: str, init: int) -> _Work:
        key = (grid, init)
        if key not in self.work:
            due = SCHEDULE[grid][1]
            row = self.rows[key]
            self.work[key] = _Work(next_try=init + due,
                                   first_probe_success=int(row["first_probe_success_unix"]),
                                   availability=int(row["availability_unix"]))
        return self.work[key]

    def _set(self, row: dict, status: str, note: str = "") -> None:
        row["status"] = status
        if note:
            row["note"] = note[:200]
        row["updated_unix"] = int(self.clock())

    def finish(self, grid: str, init: int, status: str, note: str) -> None:
        self._set(self.rows[(grid, init)], status, note)
        self.work.pop((grid, init), None)
        self.flush()

    def flush(self) -> None:
        if self.attrs is None:
            return
        rows = [self.rows[k] for k in sorted(self.rows)]
        cols = list(run_archive.RUNS_DTYPE.names)
        run_archive.write_runs(self.path, pd.DataFrame(rows, columns=cols))


# ---------------------------------------------------------------------------
# The collector
# ---------------------------------------------------------------------------

class RunCollector:
    """Fetches and archives the runs of every route; drive it with step()."""

    def __init__(self, routes: Sequence[RouteRuns], client: ApiClient,
                 clock: Callable[[], float] = time.time):
        self.routes, self.client, self.clock = list(routes), client, clock
        self._backfill_next_try = 0     # after a failed automatic backfill, wait an hour

    # --- scheduling -------------------------------------------------------

    def step(self) -> int:
        """Do everything due now; return the time of the next thing to do."""
        now = self.clock()
        for r in self.routes:
            if r.attrs is None:
                r.create(now)
            r.add_due_runs(now)
        wakes: List[int] = []
        try:
            # Currents and waves first: they have a hard deadline and no archive.
            for grid, handler in ((CURRENT, self._current), (WAVE, self._wave), (WIND, self._wind)):
                for r in self.routes:
                    for init in r.pending(grid):
                        wake = handler(r, init)
                        if wake is not None:
                            wakes.append(wake)
            wake = self._auto_backfill()
            if wake is not None:
                wakes.append(wake)
        except DailyLimitExceeded as e:
            later = int(self.clock()) + RETRY_S
            logger.error("Open-Meteo's daily limit is used up (%s); trying again at %s",
                         e, utc(later))
            for r in self.routes:
                for w in r.work.values():
                    w.next_try = max(w.next_try, later)
            wakes.append(later)
        finally:
            for r in self.routes:
                r.flush()
        now = self.clock()
        wakes += [r.next_due(now) for r in self.routes]
        # The handlers' wakes cover every pending run; a past next_try here is a run
        # that waits for another (waves for their currents), not one due now.
        wakes += [w.next_try for r in self.routes for k, w in r.work.items()
                  if r.rows[k]["status"] == "pending" and w.next_try > now]
        return max(int(now), min(wakes))

    def _wind(self, r: RouteRuns, init: int) -> Optional[int]:
        w, row, name = r.work_for(WIND, init), r.rows[(WIND, init)], run_archive.run_name(init)
        now = int(self.clock())
        if now < w.next_try:
            return w.next_try
        row["probe_attempts"] += 1
        meta_init, meta_avail = self.client.model_run(WIND_GRID)
        if meta_init >= init + WIND_CYCLE_S:
            note = (f"run {run_archive.run_name(init + WIND_CYCLE_S)} was published before this "
                    "run was fetched; it is refetched from the archive automatically")
            logger.warning("[%s] wind run %s missed: %s", r.label, name, note)
            r.finish(WIND, init, "missed", note)
            return None
        if meta_init < init:
            w.next_try = now + RETRY_S
            logger.info("[%s] wind run %s not published yet (newest %s); next check at %s",
                        r.label, name, run_archive.run_name(meta_init) if meta_init > 0 else
                        "unknown", utc(w.next_try))
            return w.next_try
        w.availability = row["availability_unix"] = meta_avail
        if now < meta_avail + SETTLE_S:
            w.next_try = meta_avail + SETTLE_S
            logger.info("[%s] wind run %s published at %s; fetching from %s", r.label, name,
                        utc(meta_avail), utc(w.next_try))
            return w.next_try
        if w.first_probe_success < 0:
            q, expected = r.plan.queries[WIND][0], expected_last_lead(WIND, init)
            try:
                body = self._request(r, row, "probe", run_url(WIND, WIND_GRID, [q], init),
                                     WEIGHT[WIND])
                last = last_lead_in(body, init)
            except RunNotAvailable:
                last = -1
            except DailyLimitExceeded:
                raise
            except (ApiError, KeyError, TypeError, ValueError) as e:
                w.next_try = now + RETRY_S
                logger.warning("[%s] wind run %s: probe failed: %s", r.label, name, e)
                return w.next_try
            if last < expected:
                w.next_try = now + RETRY_S
                logger.info("[%s] wind run %s published, but the archive holds +0..+%d h of "
                            "+%d h so far; next probe at %s", r.label, name, last, expected,
                            utc(w.next_try))
                return w.next_try
            w.first_probe_success = row["first_probe_success_unix"] = int(self.clock())
            logger.info("[%s] wind run %s complete in the archive (probe at %s)", r.label, name,
                        utc(w.first_probe_success))
        if self._fetch(r, WIND, init, w) and self._store(r, WIND, init, w):
            return None
        w.next_try = int(self.clock()) + RETRY_S
        return w.next_try

    def _current(self, r: RouteRuns, init: int) -> Optional[int]:
        return self._marine(r, CURRENT, init)

    def _wave(self, r: RouteRuns, init: int) -> Optional[int]:
        """A waves run normally comes in the requests of the same day's currents run
        (_wave_rider); it is fetched on its own only once that is out of the question."""
        cw = r.work.get((CURRENT, init))
        if cw is not None and WAVE in cw.request and not cw.riders_done:
            return None                             # being fetched with the currents
        if r.status(CURRENT, init) == "pending" and self.clock() < init + WAVE_ALONE_AFTER_S:
            return init + WAVE_ALONE_AFTER_S        # the currents' handler takes it along
        return self._marine(r, WAVE, init)

    def _wave_rider(self, r: RouteRuns, init: int, current_avail: int) -> Tuple[Optional[int], bool]:
        """Whether waves run `init` comes along in the requests of currents run `init`,
        published at current_avail: (None, True) fetch both now, (None, False) fetch the
        currents alone, (t, False) wait for the waves until t."""
        if r.status(WAVE, init) != "pending":
            return None, False
        ww, row, name = r.work_for(WAVE, init), r.rows[(WAVE, init)], run_archive.run_name(init)
        if ww.chunks:                               # being fetched on its own
            return None, False
        now = int(self.clock())
        row["probe_attempts"] += 1
        meta_init, meta_avail = self.client.model_run(WAVE_GRID)
        if meta_init > init:
            self._marine_missed(r, WAVE, init, meta_init)
            return None, False
        if meta_init == init:
            if ww.first_probe_success < 0:
                ww.first_probe_success = row["first_probe_success_unix"] = now
            ww.availability = row["availability_unix"] = meta_avail
            if now >= meta_avail + SETTLE_S:
                ww.fetch_meta = (meta_init, meta_avail)
                return None, True
            wake = meta_avail + SETTLE_S
        else:
            wake = now + RETRY_S
        deadline = current_avail + WAVE_GRACE_S
        if now >= deadline:
            logger.warning("[%s] wave run %s not ready %d h after current run %s was published; "
                           "fetching the currents alone", r.label, name, WAVE_GRACE_S // HOUR, name)
            return None, False
        wake = min(wake, deadline)
        logger.info("[%s] current run %s waits for wave run %s (%s) to fetch both in one "
                    "request; next check at %s", r.label, name, name,
                    f"published at {utc(meta_avail)}" if meta_init == init else "not published yet",
                    utc(wake))
        return wake, False

    def _marine_missed(self, r: RouteRuns, grid: str, init: int, newer: int) -> None:
        note = (f"run {run_archive.run_name(newer)} was published before this run was fetched, "
                "and the Marine API has no archive")
        logger.error("[%s] %s run %s missed: %s", r.label, grid, run_archive.run_name(init), note)
        r.finish(grid, init, "missed", note)

    def _marine(self, r: RouteRuns, grid: str, init: int) -> Optional[int]:
        """A currents or waves run: readable only while it is the newest of its model."""
        w, row, name = r.work_for(grid, init), r.rows[(grid, init)], run_archive.run_name(init)
        now = int(self.clock())
        if now < w.next_try:
            return w.next_try
        row["probe_attempts"] += 1
        meta_init, meta_avail = self.client.model_run(COLLECTED[grid])
        if meta_init < 0:
            w.next_try = now + RETRY_S
            return w.next_try
        if meta_init > init:
            self._marine_missed(r, grid, init, meta_init)
            return None
        if meta_init < init:
            w.next_try = now + RETRY_S
            logger.info("[%s] %s run %s not published yet (newest %s); next check at %s",
                        r.label, grid, name, run_archive.run_name(meta_init), utc(w.next_try))
            return w.next_try
        if w.first_probe_success < 0:
            w.first_probe_success = row["first_probe_success_unix"] = now
        w.availability = row["availability_unix"] = meta_avail
        if now < meta_avail + SETTLE_S:
            w.next_try = meta_avail + SETTLE_S
            logger.info("[%s] %s run %s published at %s; fetching from %s", r.label, grid, name,
                        utc(meta_avail), utc(w.next_try))
            return w.next_try
        if w.fetch_meta is not None and w.fetch_meta != (meta_init, meta_avail):
            logger.warning("[%s] %s run %s was republished (%s); fetching it again",
                           r.label, grid, name, utc(meta_avail))
            w.chunks.clear()
        if not w.chunks:
            w.request, w.riders_done = (grid,), False
            if grid == CURRENT:
                wake, join = self._wave_rider(r, init, meta_avail)
                if wake is not None:
                    w.next_try = wake
                    return wake
                if join:
                    w.request = (CURRENT, WAVE)
            else:
                cost = len(r.plan.queries[CELLS_OF[grid]]) * WEIGHT[grid]
                used = self.calls_last_24h()
                if used + cost > WAVE_ALONE_LIMIT:
                    w.next_try = now + BACKFILL_RETRY_S
                    logger.warning("[%s] %s run %s waits: %.0f calls in the last 24 h + %.0f "
                                   "would exceed %d; next try at %s", r.label, grid, name, used,
                                   cost, WAVE_ALONE_LIMIT, utc(w.next_try))
                    return w.next_try
            w.fetch_meta = (meta_init, meta_avail)
        if self._fetch(r, grid, init, w):
            after = self.client.model_run(COLLECTED[grid])
            if after[0] < 0:
                w.next_try = int(self.clock()) + RETRY_S
                return w.next_try
            if not w.riders_done:
                if not all(self._store_rider(r, g, init, w) for g in w.request[1:]):
                    w.next_try = int(self.clock()) + RETRY_S
                    return w.next_try
                w.riders_done = True
            if after[0] > init:
                note = (f"run {run_archive.run_name(after[0])} was published during the fetch; "
                        "data discarded since it could mix runs")
                logger.error("[%s] %s run %s discarded: %s", r.label, grid, name, note)
                r.finish(grid, init, "discarded", note)
                return None
            if after == w.fetch_meta and self._store(r, grid, init, w):
                return None
            if after[0] == init and after != w.fetch_meta:
                logger.warning("[%s] %s run %s was republished during the fetch; fetching "
                               "it again", r.label, grid, name)
                w.chunks.clear()
                w.fetch_meta = None
        w.next_try = int(self.clock()) + RETRY_S
        return w.next_try

    def _store_rider(self, r: RouteRuns, grid: str, init: int, source: _Work) -> bool:
        """Store a run that came in the requests of another grid's run (`source`), if its
        metadata did not change during the fetch. False if the metadata cannot be read
        now (try again later); True when dealt with."""
        if r.status(grid, init) != "pending":
            return True
        w, name = r.work_for(grid, init), run_archive.run_name(init)
        after = self.client.model_run(COLLECTED[grid])
        if after[0] < 0:
            return False
        if after != w.fetch_meta:
            if after[0] > init:
                note = (f"run {run_archive.run_name(after[0])} was published during the fetch; "
                        "data discarded since it could mix runs")
                logger.error("[%s] %s run %s discarded: %s", r.label, grid, name, note)
                r.finish(grid, init, "discarded", note)
            else:
                logger.warning("[%s] %s run %s was republished during the fetch; it is fetched "
                               "again on its own", r.label, grid, name)
                w.fetch_meta = None
            return True
        w.fetch_start = r.rows[(grid, init)]["fetch_start_unix"] = source.fetch_start
        self._store(r, grid, init, w, source=source)
        return True

    # --- fetching and storing -----------------------------------------------

    def _request(self, r: RouteRuns, row: dict, kind: str, url: str, weight: float):
        calls, requests = self.client.calls, self.client.requests
        try:
            return self.client.get_json(url, weight)
        finally:
            row["api_calls"] += self.client.calls - calls
            row["probe_attempts" if kind == "probe" else "fetch_requests"] += \
                self.client.requests - requests

    @staticmethod
    def _grid(r: RouteRuns, grid: str):
        return r.plan.grids.get(grid, COLLECTED[grid])

    def _fetch(self, r: RouteRuns, grid: str, init: int, w: _Work) -> bool:
        """Fetch the chunks still missing, for the grids of w.request (default: `grid`
        alone; the first is `grid`, whose cells are asked); True when all are in."""
        row, queries = r.rows[(grid, init)], r.plan.queries[CELLS_OF[grid]]
        request = w.request or (grid,)
        riders = [(g, self._grid(r, g)) for g in request[1:]]
        weight = request_weight(request)
        n_chunks = -(-len(queries) // CHUNK_SIZE)
        if w.fetch_start < 0:
            w.fetch_start = row["fetch_start_unix"] = int(self.clock())
        for ci in range(n_chunks):
            if ci in w.chunks:
                continue
            chunk = queries[ci * CHUNK_SIZE:(ci + 1) * CHUNK_SIZE]
            try:
                url = run_url(grid, self._grid(r, grid), chunk, init, riders)
                body = self._request(r, row, "fetch", url, weight * len(chunk))
                body = body if isinstance(body, list) else [body]
                if len(body) != len(chunk):
                    raise ApiError(f"{len(body)} results for {len(chunk)} locations")
                w.chunks[ci] = body
            except DailyLimitExceeded:
                raise
            except ApiError as e:
                logger.warning("[%s] %s run %s: chunk %d/%d failed (%s); retrying in %d min",
                               r.label, grid, run_archive.run_name(init), ci + 1, n_chunks, e,
                               RETRY_S // 60)
        return len(w.chunks) == n_chunks

    def _check(self, r: RouteRuns, grid: str, name: str, run: GridRun,
               served_known: bool = True) -> Tuple[int, int]:
        """Log substituted and NaN cells; return their counts (-1 substitutions if the
        response did not report this grid's points)."""
        queries = r.plan.queries[CELLS_OF[grid]]
        nan = find_nan_cells(run)
        if nan:
            logger.warning("[%s] %s run %s: NaN values at %d of %d cells (stored as NaN)",
                           r.label, grid, name, len(nan), len(queries))
            for k, (n_bad, n_all) in nan.items():
                q = queries[k]
                logger.warning("[%s] %s:   cell %s at %.1f NM (query %.4f, %.4f): %d of %d "
                               "values NaN", r.label, grid, q.cell,
                               r.plan.subsegments[q.subsegments[0]].start_nm, q.query_lat,
                               q.query_lon, n_bad, n_all)
        if not served_known:
            return len(nan), -1
        subst = find_substitutions(queries, run)
        served = {k: (float(run.served_lat[k]), float(run.served_lon[k])) for k in subst}
        if subst:
            changed = served != r._last_substitutions[grid]
            logger.info("[%s] %s run %s: %d of %d cells served by another grid point than "
                        "predicted (near land the API substitutes a sea point)%s", r.label, grid,
                        name, len(subst), len(queries), "" if changed else ", as before")
            if changed:
                for k in subst:
                    q, (lat, lon) = queries[k], served[k]
                    logger.info("[%s] %s:   cell %s at %.1f NM (query %.4f, %.4f): predicted "
                                "(%.5f, %.5f), served (%.5f, %.5f), %.1f NM apart", r.label, grid,
                                q.cell, r.plan.subsegments[q.subsegments[0]].start_nm,
                                q.query_lat, q.query_lon, q.grid_lat, q.grid_lon, lat, lon,
                                _nm_apart(q.grid_lat, q.grid_lon, lat, lon))
        r._last_substitutions[grid] = served
        return len(nan), len(subst)

    def _store(self, r: RouteRuns, grid: str, init: int, w: _Work, backfilled: bool = False,
               accept_short: bool = False, source: Optional[_Work] = None) -> bool:
        """Parse, check and store a fully fetched run; False (chunks dropped) if malformed,
        or if it is a wind run shorter than a complete one and accept_short is False.
        A short current or wave run is stored anyway, with a warning: no archive.
        `source` holds the chunks when they came in another grid's requests."""
        row, name = r.rows[(grid, init)], run_archive.run_name(init)
        src = source or w
        request = src.request or (grid,)
        suffix = f"_{COLLECTED[grid].api_params['models']}" if len(request) > 1 else ""
        bodies = [b for ci in sorted(src.chunks) for b in src.chunks[ci]]
        try:
            run = cut_to_span(parse_run(grid, bodies, suffix))
        except ApiError as e:
            logger.error("[%s] %s run %s: %s; fetching it again", r.label, grid, name, e)
            src.chunks.clear()
            return False
        first_lead = int(run.time[0] - init) // HOUR
        last_lead = int(run.time[-1] - init) // HOUR
        expected = expected_last_lead(grid, init)
        if first_lead != 0 or last_lead < expected:
            if grid == WIND and not accept_short:
                logger.warning("[%s] wind run %s spans +%d..+%d h, expected +0..+%d h: not "
                               "stored; fetching it again in %d min", r.label, name, first_lead,
                               last_lead, expected, RETRY_S // 60)
                w.chunks.clear()
                w.first_probe_success = -1
                return False
            logger.warning("[%s] %s run %s spans +%d..+%d h, expected +0..+%d h; stored as it is",
                           r.label, grid, name, first_lead, last_lead, expected)
        elif last_lead > expected:
            logger.warning("[%s] %s run %s spans +%d..+%d h, longer than the expected +%d h",
                           r.label, grid, name, first_lead, last_lead, expected)
        # A request for several models reports one grid point per location, the first
        # model's; the others use their own nearest sea point, unreported.
        served_known = request[0] == grid
        n_nan, n_subst = self._check(r, grid, name, run, served_known)
        if not served_known:
            run.served_lat = np.full(len(bodies), np.nan)
            run.served_lon = np.full(len(bodies), np.nan)
        end = int(self.clock())
        params = run_params(request[0], self._grid(r, request[0]), [], init,
                            [(g, self._grid(r, g)) for g in request[1:]])
        for k in ("latitude", "longitude"):
            params.pop(k)
        run_archive.write_run(r.path, grid, init, run.time, run.values, run.served_lat,
                              run.served_lon, {
                                  "run_init_utc": utc(init),
                                  "availability_unix": w.availability,
                                  "first_probe_success_unix": w.first_probe_success,
                                  "fetch_start_unix": w.fetch_start,
                                  "fetch_end_unix": end,
                                  "first_lead_hours": first_lead,
                                  "last_lead_hours": last_lead,
                                  "nan_cells": n_nan,
                                  "substituted_cells": n_subst,
                                  "api_url": RUN_API_URLS[grid],
                                  "api_params_json": json.dumps(params),
                                  "request_grids": ",".join(request),
                                  "cell_table": run_archive.CELL_TABLES[grid],
                                  "served_points_reported": served_known,
                                  "backfilled": backfilled,
                              })
        row["fetch_end_unix"] = end
        with_other = "" if served_known else f"fetched in the requests of {request[0]} run {name}"
        r.finish(grid, init, "complete", "backfilled" if backfilled else with_other)
        level = logging.WARNING if n_nan else logging.INFO
        logger.log(level, "[%s] %s run %s stored: %d cells x %d h (+%d..+%d h), NaN cells %d, "
                   "substituted %s; %s; calls in the last 24 h: %.0f", r.label, grid, name,
                   len(bodies), len(run.time), first_lead, last_lead, n_nan,
                   n_subst if served_known else "not reported",
                   with_other or f"{row['fetch_requests']} requests, {row['api_calls']:.0f} calls, "
                                 f"{(end - w.fetch_start) / 60.0:.1f} min",
                   self.calls_last_24h())
        return True

    # --- backfill -----------------------------------------------------------

    def missed_wind_runs(self) -> List[Tuple[RouteRuns, int]]:
        """Wind runs to refetch from the archive: missed, or stored incomplete."""
        return [(r, init) for r in self.routes for (g, init), row in sorted(r.rows.items())
                if g == WIND and row["status"] in ("missed", "incomplete")]

    def _backfill_one(self, r: RouteRuns, init: int) -> bool:
        """Refetch one wind run from the archive; True if it was stored."""
        name = run_archive.run_name(init)
        w = _Work(next_try=0)
        old = self.clock() - init >= BACKFILL_MIN_AGE_S
        if self._fetch(r, WIND, init, w) and self._store(r, WIND, init, w, backfilled=True,
                                                         accept_short=old):
            return True
        row = r.rows[(WIND, init)]
        row["note"] = f"backfill at {utc(self.clock())} failed; will try again"[:200]
        logger.error("[%s] wind run %s: backfill failed", r.label, name)
        return False

    def calls_last_24h(self) -> float:
        """API calls of the last 24 h: this process's count, or the /runs tables' (which
        survive restarts), whichever is larger."""
        cutoff = self.clock() - 24 * HOUR
        table = sum(float(row["api_calls"]) for r in self.routes for row in r.rows.values()
                    if int(row["updated_unix"]) >= cutoff)
        return max(table, self.client.calls_last_24h())

    def _auto_backfill(self) -> Optional[int]:
        """Refetch the oldest missed or incomplete wind run that is a day old, if the
        daily budget allows and no current run is pending. Returns when to look again."""
        now = int(self.clock())
        if now < self._backfill_next_try:
            return self._backfill_next_try
        todo = [(r, init) for r, init in self.missed_wind_runs()
                if now - init >= BACKFILL_MIN_AGE_S]
        if not todo:
            pending = [init for r, init in self.missed_wind_runs()]
            return min(pending) + BACKFILL_MIN_AGE_S if pending else None
        if any(r.pending(CURRENT) or r.pending(WAVE) for r in self.routes):
            return now + BACKFILL_RETRY_S
        r, init = todo[0]
        cost = len(r.plan.queries[WIND]) * WEIGHT[WIND]
        used = self.calls_last_24h()
        if used + cost > AUTO_BACKFILL_LIMIT:
            logger.info("[%s] wind run %s waits for backfill: %.0f calls in the last 24 h + %.0f "
                        "would exceed %d", r.label, run_archive.run_name(init), used, cost,
                        AUTO_BACKFILL_LIMIT)
            return now + BACKFILL_RETRY_S
        logger.info("[%s] backfilling wind run %s from the archive (%.0f calls)", r.label,
                    run_archive.run_name(init), cost)
        if not self._backfill_one(r, init):
            self._backfill_next_try = int(self.clock()) + BACKFILL_RETRY_S
            return self._backfill_next_try
        return int(self.clock())

    def backfill_wind(self, dry_run: bool = False) -> float:
        """Refetch missed and incomplete wind runs from the Single Runs archive now,
        regardless of the budget. Returns their cost in API calls (planned with dry_run,
        else spent)."""
        todo = self.missed_wind_runs()
        cost = sum(len(r.plan.queries[WIND]) * WEIGHT[WIND] for r, _ in todo)
        logger.info("Backfill: %d missed or incomplete wind runs, %.0f API calls%s", len(todo),
                    cost, "".join(f"\n  [{r.label}] {run_archive.run_name(i)}" for r, i in todo))
        if dry_run or not todo:
            return cost
        spent = self.client.calls
        try:
            for r, init in todo:
                self._backfill_one(r, init)
        except DailyLimitExceeded as e:
            logger.error("Backfill stopped, Open-Meteo's daily limit is used up: %s", e)
        finally:
            for r in self.routes:
                r.flush()
        return self.client.calls - spent


# ---------------------------------------------------------------------------
# Removed: fixed-spacing collection
# ---------------------------------------------------------------------------

def collect(config, hdf5_path=None):
    """Removed on 2026-10-14.

    The fixed-spacing collector (generate_waypoints every interval_nm, with
    Open-Meteo's default best_match models and cell selection) produced
    experiments A-D. New collections archive model runs per subsegment cell
    with pinned grids: see run_all.py.
    """
    raise RuntimeError("collect.collector.collect() was removed: it sampled at fixed spacing "
                       "with Open-Meteo's best_match models. Use run_all.py, which archives "
                       "every model run per subsegment cell with pinned grids.")

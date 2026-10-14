"""
Live weather collection by subsegment.

The route is split into subsegments (shared/subsegments.py): maximal stretches
of one leg that lie inside one wind cell and one current cell. Open-Meteo
answers every position inside a cell with the value of that cell's grid point,
so the weather of a subsegment is the weather of its two cells, and each API
is asked once per distinct cell rather than once per subsegment:

    wind     Forecast API with WIND_GRID.api_params    (ECMWF IFS, cell_selection=sea)
    current  Marine API with CURRENT_GRID.api_params   (Meteo-France SMOC, cell_selection=sea)

A cell is queried at the midpoint of the longest subsegment inside it, a point
the route actually sails through. Every response reports the grid point that
served it. It is compared with the grid point predicted by
shared/weather_grids.py; a mismatch (near land the API substitutes a nearby sea
point for a land-masked one) is logged, and the served points are stored with
each sample.

NaN in a model input (wind speed, which sets the Beaufort number, wind
direction, current velocity and current direction) is logged as a warning
with the cells and route distances concerned, and counted in /samples.

Wave height is not collected. The speed and fuel model never reads it (see
docs/weather_resolution_audit_2026_09_06.html), and the currents model
(meteofrance_currents) has no wave field. Getting it would mean adding a
second model (meteofrance_wave) to every Marine request for a value nothing
uses. wave_height_m is therefore NaN by design; the HDF5 attributes say so,
and the NaN checks above exclude it.

One sample of one route goes into one HDF5 file (shared/hdf5_io.py), with one
node per subsegment. The scheduling loop and the command line are in
run_all.py.
"""

from __future__ import annotations

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
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, Dict, List, Mapping, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

from shared.beaufort import wind_speed_to_beaufort
from shared.hdf5_io import (
    SAMPLES_DTYPE,
    SUBSEGMENT_ACTUAL_DTYPE,
    SUBSEGMENT_METADATA_DTYPE,
    append_sample,
    create_hdf5,
    get_attrs,
    get_completed_runs,
)
from shared.rhumb import RhumbLeg
from shared.subsegments import MERGE_TOL_NM, PORT_TRIM_NM, Subsegment, partition_route, trim_route
from shared.weather_grids import CURRENT_GRID, WIND_GRID

logger = logging.getLogger(__name__)

WIND, CURRENT = "wind", "current"
GRIDS = {WIND: WIND_GRID, CURRENT: CURRENT_GRID}

# Open-Meteo variable -> HDF5 column. Each variable is requested twice, as
# current conditions (-> /actual_weather) and as an hourly forecast
# (-> /predicted_weather).
API_FIELDS = {
    WIND: {"wind_speed_10m": "wind_speed_10m_kmh",
           "wind_direction_10m": "wind_direction_10m_deg"},
    CURRENT: {"ocean_current_velocity": "ocean_current_velocity_kmh",
              "ocean_current_direction": "ocean_current_direction_deg"},
}
EXPECTED_UNITS = {"wind_speed_10m": "km/h", "wind_direction_10m": "°",
                  "ocean_current_velocity": "km/h", "ocean_current_direction": "°"}

# Request parameters besides locations, variables and the pinned grid.
EXTRA_PARAMS = {WIND: {"wind_speed_unit": "kmh"}, CURRENT: {}}

# Hourly series run from 00:00 UTC of the sample day for this many days, as in
# the earlier collections. Up to 14 days cost no extra API calls (query_weight).
FORECAST_DAYS = 7

COORD_DECIMALS = 6     # query coordinates as sent (about 0.1 m)
MATCH_TOL_DEG = 1e-4   # served vs predicted grid point; the API reports float32

# Pacing. A request for n locations counts as n calls, and the free tier allows
# 600 calls per minute, 5,000 per hour and 10,000 per day per IP.
CHUNK_SIZE = 100            # locations per request; longer URLs risk HTTP 414
SECONDS_PER_CHUNK = 15.0    # request starts at least this far apart: <= 400 calls/min
MAX_ATTEMPTS = 5            # per request
API_LIMITS = {"minute": 600, "hour": 5000, "day": 10000}

# beaufort_number is int8 and cannot hold NaN; a missing wind speed is stored
# as -1 (and always logged), never as a real Beaufort number.
BEAUFORT_MISSING = -1

WAVE_HEIGHT_NOTE = ("not collected: wave_height_m is NaN by design. The speed and fuel model "
                    "does not use wave height (docs/weather_resolution_audit_2026_09_06.html) "
                    "and the currents model has no wave field.")


class ApiError(RuntimeError):
    """A request that failed for good (after retries, or not worth retrying)."""


class DailyLimitExceeded(ApiError):
    """Open-Meteo refused the request because this IP used up its daily calls."""


class PlanMismatch(RuntimeError):
    """An existing HDF5 file was built from a different route partition."""


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


def _query_point(grid, cell, candidates: Sequence[int], midpoints) -> Tuple[float, float]:
    """Midpoint of the longest candidate subsegment that, as sent, is still in `cell`."""
    for i in candidates:
        lat, lon = (round(x, COORD_DECIMALS) for x in midpoints[i])
        if grid.cell_of(lat, lon) == cell:
            return lat, lon
    lat, lon = (round(x, COORD_DECIMALS) for x in midpoints[candidates[0]])
    logger.warning("Every candidate query point for %s cell %s leaves the cell when rounded "
                   "to %d decimals; using (%.6f, %.6f)", grid.name, cell, COORD_DECIMALS, lat, lon)
    return lat, lon


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
            qlat, qlon = _query_point(grid, cell, by_length, midpoints)
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


def plan_metadata(plan: SamplingPlan) -> pd.DataFrame:
    """The /metadata table: one node per subsegment (SUBSEGMENT_METADATA_DTYPE)."""
    rows = []
    for s in plan.subsegments:
        w = plan.queries[WIND][plan.cell_index[WIND][s.index]]
        c = plan.queries[CURRENT][plan.cell_index[CURRENT][s.index]]
        (mid_lat, mid_lon), (end_lat, end_lon) = plan.midpoints[s.index], plan.endpoints[s.index]
        rows.append({
            "node_id": s.index,
            "lon": mid_lon,
            "lat": mid_lat,
            "waypoint_name": f"leg{s.leg:02d}_sub{s.index:05d}",
            "is_original": s.index == 0 or plan.subsegments[s.index - 1].leg != s.leg,
            "distance_from_start_nm": s.start_nm,
            "segment": s.leg,
            "length_nm": s.length_nm,
            "bearing_deg": s.bearing_deg,
            "start_lat": s.start_lat,
            "start_lon": s.start_lon,
            "end_lat": end_lat,
            "end_lon": end_lon,
            "wind_cell_row": w.cell[0],
            "wind_cell_col": w.cell[1],
            "wind_grid_lat": w.grid_lat,
            "wind_grid_lon": w.grid_lon,
            "wind_query_lat": w.query_lat,
            "wind_query_lon": w.query_lon,
            "current_cell_row": c.cell[0],
            "current_cell_col": c.cell[1],
            "current_grid_lat": c.grid_lat,
            "current_grid_lon": c.grid_lon,
            "current_query_lat": c.query_lat,
            "current_query_lon": c.query_lon,
        })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# API budget
# ---------------------------------------------------------------------------

def query_weight(n_variables: int, forecast_days: float, n_models: int = 1) -> float:
    """API calls that Open-Meteo counts for one location of a request.

    Mirrors calculateQueryWeight() of the Open-Meteo server
    (open-meteo/open-meteo, Sources/App/Helper/Writer/ForecastApiResult.swift):
    with V = requested variables (current + hourly + ...) times models,
    a location costs max(1, V / 10, V / 10 * days / 14) calls.
    """
    v = n_variables * n_models / 10.0
    return max(1.0, v, v * forecast_days / 14.0)


def calls_per_sample(plan: SamplingPlan, forecast_days: int = FORECAST_DAYS) -> Dict[str, float]:
    """API calls one sample of the route costs, per grid."""
    return {g: len(plan.queries[g]) * query_weight(2 * len(API_FIELDS[g]), forecast_days)
            for g in plan.queries}


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


def request_params(grid_key: str, grid, chunk: Sequence[CellQuery],
                   forecast_days: int = FORECAST_DAYS) -> dict:
    """Query parameters for one request; the grid's model and cell selection always win."""
    if not {"models", "cell_selection"} <= set(grid.api_params):
        raise ValueError(f"{grid.name}.api_params must pin models and cell_selection")
    variables = ",".join(API_FIELDS[grid_key])
    return {
        "latitude": ",".join(f"{q.query_lat:.{COORD_DECIMALS}f}" for q in chunk),
        "longitude": ",".join(f"{q.query_lon:.{COORD_DECIMALS}f}" for q in chunk),
        "current": variables,
        "hourly": variables,
        "timezone": "GMT",
        "timeformat": "unixtime",
        "forecast_days": forecast_days,
        **EXTRA_PARAMS[grid_key],
        **grid.api_params,
    }


def _error_reason(e: urllib.error.HTTPError) -> str:
    try:
        return str(json.loads(e.read().decode("utf-8", "replace")).get("reason", e))
    except Exception:
        return str(e)


def request_with_retry(url: str, pacer: Pacer, get: Callable = http_get_json,
                       max_attempts: int = MAX_ATTEMPTS):
    """GET `url` as JSON, waiting out rate limits and transient failures."""
    for attempt in range(1, max_attempts + 1):
        pacer.wait()
        try:
            return get(url)
        except urllib.error.HTTPError as e:
            reason = _error_reason(e)
            if e.code == 429:
                if "daily" in reason.lower():
                    raise DailyLimitExceeded(reason) from None
                wait = 900 if "hourly" in reason.lower() else 60
            elif e.code >= 500:
                wait = 30 * attempt
            else:
                raise ApiError(f"HTTP {e.code}: {reason}") from None
            problem = f"HTTP {e.code}: {reason}"
        except (OSError, ValueError, http.client.HTTPException) as e:   # network, timeouts, bad JSON
            wait, problem = 30 * attempt, repr(e)
        if attempt == max_attempts:
            raise ApiError(f"giving up after {max_attempts} attempts: {problem}")
        logger.warning("Request to %s failed (attempt %d/%d): %s; retrying in %d s",
                       urllib.parse.urlsplit(url).netloc, attempt, max_attempts, problem, wait)
        pacer.sleep(wait)


def fetch_cells(grid_key: str, grid, queries: Sequence[CellQuery], pacer: Pacer,
                get: Callable = http_get_json, chunk_size: int = CHUNK_SIZE,
                forecast_days: int = FORECAST_DAYS) -> List[dict]:
    """One JSON response per query, in order, requested `chunk_size` locations at a time."""
    bodies: List[dict] = []
    for start in range(0, len(queries), chunk_size):
        chunk = queries[start:start + chunk_size]
        url = f"{grid.api_url}?{urllib.parse.urlencode(request_params(grid_key, grid, chunk, forecast_days))}"
        body = request_with_retry(url, pacer, get)
        body = body if isinstance(body, list) else [body]
        if len(body) != len(chunk):
            raise ApiError(f"{grid.api_url} returned {len(body)} results for {len(chunk)} locations")
        bodies.extend(body)
    return bodies


def model_run(grid, get: Callable = http_get_json) -> Tuple[int, int]:
    """(initialization, availability) Unix times of the newest run of the grid's
    model on Open-Meteo, or (-1, -1) if unavailable. Reads the static metadata file
    behind open-meteo.com/en/docs/model-updates, not the forecast API."""
    parts = urllib.parse.urlsplit(grid.api_url)
    url = f"{parts.scheme}://{parts.netloc}/data/{grid.api_params['models']}/static/meta.json"
    try:
        meta = get(url)
        return int(meta["last_run_initialisation_time"]), int(meta["last_run_availability_time"])
    except Exception as e:
        logger.warning("Could not read model metadata %s: %r", url, e)
        return -1, -1


# ---------------------------------------------------------------------------
# Responses
# ---------------------------------------------------------------------------

@dataclass
class GridWeather:
    """All responses for one grid in one sample, one row per cell query."""
    served_lat: np.ndarray            # (n_cells,) grid point the API used
    served_lon: np.ndarray
    current: Dict[str, np.ndarray]    # HDF5 column -> (n_cells,)
    hourly_time: np.ndarray           # (n_times,) Unix seconds, shared by all cells
    hourly: Dict[str, np.ndarray]     # HDF5 column -> (n_cells, n_times)


def parse_responses(grid_key: str, bodies: Sequence[dict]) -> GridWeather:
    """Collect the JSON bodies of one grid into arrays; null values become NaN."""
    try:
        return _parse_responses(grid_key, bodies)
    except (KeyError, TypeError, ValueError) as e:
        raise ApiError(f"malformed {grid_key} response: {e!r}") from None


def _parse_responses(grid_key: str, bodies: Sequence[dict]) -> GridWeather:
    fields = API_FIELDS[grid_key]
    n = len(bodies)
    if n == 0:
        raise ApiError(f"no {grid_key} responses")
    served_lat = np.array([float(b["latitude"]) for b in bodies])
    served_lon = np.array([float(b["longitude"]) for b in bodies])
    hourly_time = np.asarray(bodies[0]["hourly"]["time"], dtype=np.int64)
    current = {col: np.full(n, np.nan) for col in fields.values()}
    hourly = {col: np.full((n, len(hourly_time)), np.nan) for col in fields.values()}
    for i, b in enumerate(bodies):
        for section in ("current", "hourly"):
            units = b.get(f"{section}_units", {})
            for var in fields:
                if units.get(var) != EXPECTED_UNITS[var]:
                    raise ApiError(f"{section} {var} in {units.get(var)!r}, expected "
                                   f"{EXPECTED_UNITS[var]!r}")
        if not np.array_equal(np.asarray(b["hourly"]["time"], dtype=np.int64), hourly_time):
            raise ApiError(f"{grid_key}: hourly time axes differ between locations")
        for var, col in fields.items():
            value = b["current"][var]
            current[col][i] = np.nan if value is None else float(value)
            hourly[col][i] = np.array(b["hourly"][var], dtype=float)   # None -> NaN
    return GridWeather(served_lat, served_lon, current, hourly_time, hourly)


def find_substitutions(queries: Sequence[CellQuery], gw: GridWeather,
                       tol_deg: float = MATCH_TOL_DEG) -> List[int]:
    """Cells served by a different grid point than predicted."""
    out = []
    for k, q in enumerate(queries):
        dlat = abs(gw.served_lat[k] - q.grid_lat)
        dlon = abs((gw.served_lon[k] - q.grid_lon + 180.0) % 360.0 - 180.0)
        if not (dlat <= tol_deg and dlon <= tol_deg):   # NaN coordinates count as a mismatch
            out.append(k)
    return out


def find_nan_cells(gw: GridWeather) -> Dict[int, Tuple[List[str], int, int]]:
    """Cells with NaN in a model input: k -> (columns NaN in the current
    conditions, NaN hourly values, hourly values)."""
    cols = list(gw.current)
    cur_nan = np.stack([np.isnan(gw.current[c]) for c in cols], axis=1)        # (n, fields)
    hourly_nan = np.stack([np.isnan(gw.hourly[c]) for c in cols], axis=1)      # (n, fields, t)
    n_hourly = hourly_nan.shape[1] * hourly_nan.shape[2]
    out = {}
    for k in np.flatnonzero(cur_nan.any(axis=1) | hourly_nan.any(axis=(1, 2))):
        out[int(k)] = ([c for c, bad in zip(cols, cur_nan[k]) if bad],
                       int(hourly_nan[k].sum()), n_hourly)
    return out


def _where(plan: SamplingPlan, q: CellQuery) -> str:
    a = plan.subsegments[q.subsegments[0]].start_nm
    b = plan.subsegments[q.subsegments[-1]].end_nm
    return (f"cell {q.cell} at {a:.1f}-{b:.1f} NM "
            f"(query {q.query_lat:.4f}, {q.query_lon:.4f})")


def _nm_apart(lat1, lon1, lat2, lon2) -> float:
    dlon = (lon2 - lon1 + 180.0) % 360.0 - 180.0
    return 60.0 * math.hypot(lat2 - lat1, dlon * math.cos(math.radians(0.5 * (lat1 + lat2))))


# ---------------------------------------------------------------------------
# Rows
# ---------------------------------------------------------------------------

def _beaufort(wind_speed_kmh: float) -> int:
    return wind_speed_to_beaufort(wind_speed_kmh) if math.isfinite(wind_speed_kmh) \
        else BEAUFORT_MISSING


_beaufort_array = np.vectorize(_beaufort, otypes=[np.int8])


def build_rows(plan: SamplingPlan, weather: Mapping[str, GridWeather], sample_hour: int,
               reference_unix: int) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """/actual_weather and /predicted_weather rows: every subsegment gets the
    weather of its wind cell and of its current cell.

    forecast_hour counts hours from reference_unix (the time sample_hour stands
    for) to the forecast's valid time. Only times both APIs returned are kept.
    """
    wind, cur = weather[WIND], weather[CURRENT]
    w_idx, c_idx = plan.cell_index[WIND], plan.cell_index[CURRENT]
    n = len(plan.subsegments)
    node_id = np.arange(n, dtype=np.int32)

    ws_now = wind.current["wind_speed_10m_kmh"]
    actual = pd.DataFrame({
        "node_id": node_id,
        "sample_hour": np.full(n, sample_hour, dtype=np.int32),
        "wind_speed_10m_kmh": ws_now[w_idx],
        "wind_direction_10m_deg": wind.current["wind_direction_10m_deg"][w_idx],
        "beaufort_number": _beaufort_array(ws_now)[w_idx],
        "wave_height_m": np.full(n, np.nan),
        "ocean_current_velocity_kmh": cur.current["ocean_current_velocity_kmh"][c_idx],
        "ocean_current_direction_deg": cur.current["ocean_current_direction_deg"][c_idx],
        "wind_served_lat": wind.served_lat[w_idx],
        "wind_served_lon": wind.served_lon[w_idx],
        "current_served_lat": cur.served_lat[c_idx],
        "current_served_lon": cur.served_lon[c_idx],
    })

    times = np.intersect1d(wind.hourly_time, cur.hourly_time)
    if len(times) == 0:
        raise ApiError("the wind and current forecasts share no hourly time")
    if len(times) < max(len(wind.hourly_time), len(cur.hourly_time)):
        logger.warning("Hourly forecasts differ in time span: wind %d h, current %d h; "
                       "keeping the %d h both cover", len(wind.hourly_time),
                       len(cur.hourly_time), len(times))
    lead_s = times - int(reference_unix)
    if np.any(lead_s % 3600):
        raise ValueError("forecast times are not whole hours after the reference time")
    lead = (lead_s // 3600).astype(np.int32)
    wi = np.searchsorted(wind.hourly_time, times)
    ci = np.searchsorted(cur.hourly_time, times)
    nt = len(times)

    ws = wind.hourly["wind_speed_10m_kmh"][:, wi]
    predicted = pd.DataFrame({
        "node_id": np.repeat(node_id, nt),
        "forecast_hour": np.tile(lead, n),
        "sample_hour": np.full(n * nt, sample_hour, dtype=np.int32),
        "wind_speed_10m_kmh": ws[w_idx].ravel(),
        "wind_direction_10m_deg": wind.hourly["wind_direction_10m_deg"][:, wi][w_idx].ravel(),
        "beaufort_number": _beaufort_array(ws)[w_idx].ravel(),
        "wave_height_m": np.full(n * nt, np.nan),
        "ocean_current_velocity_kmh": cur.hourly["ocean_current_velocity_kmh"][:, ci][c_idx].ravel(),
        "ocean_current_direction_deg": cur.hourly["ocean_current_direction_deg"][:, ci][c_idx].ravel(),
    })
    return actual, predicted


# ---------------------------------------------------------------------------
# One route, one HDF5 file
# ---------------------------------------------------------------------------

def utc(unix: float) -> str:
    return datetime.fromtimestamp(unix, timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def previous_slot(now_unix: float, interval_hours: int, offset_hours: int) -> int:
    """Latest scheduled sample time at or before `now_unix`.

    Samples are due at offset_hours + k * interval_hours UTC (interval_hours
    must divide 24), e.g. 02, 08, 14, 20 UTC for interval 6 and offset 8.
    """
    period = interval_hours * 3600
    phase = (offset_hours % interval_hours) * 3600
    return int((now_unix - phase) // period * period + phase)


class RouteCollector:
    """Collects samples of one route into its HDF5 file.

    sample_hour counts hours from the file's first scheduled sample (attribute
    epoch_unix) to the sample's scheduled time, so a missed cycle leaves a gap
    instead of shifting later samples.
    """

    def __init__(self, label: str, plan: SamplingPlan, path: str,
                 sample_interval_hours: int, nwp_offset_hours: int,
                 max_run_age_hours: Optional[Mapping[str, float]] = None,
                 get: Callable = http_get_json):
        self.label, self.plan, self.path = label, plan, path
        self.sample_interval_hours = sample_interval_hours
        self.nwp_offset_hours = nwp_offset_hours
        self.max_run_age_hours = dict(max_run_age_hours or {})
        self.get = get
        self.epoch_unix: Optional[int] = None
        self._last_substitutions: Dict[str, Optional[dict]] = {g: None for g in plan.queries}
        if os.path.exists(path):
            self.epoch_unix = self._check_file()

    # --- file -------------------------------------------------------------

    def _check_file(self) -> int:
        attrs = get_attrs(self.path)
        if attrs.get("sampling") != "subsegments":
            raise PlanMismatch(f"{self.path} is not a subsegment collection; "
                               "choose another output file")
        if attrs.get("plan_fingerprint") != self.plan.fingerprint:
            raise PlanMismatch(
                f"{self.path} was built from a different partition of {self.plan.route_key} "
                f"(fingerprint {attrs.get('plan_fingerprint')}, now {self.plan.fingerprint}): "
                "the route waypoints or the grids changed. Start a new file (move this one "
                "away or use another --data-dir); appending would mismatch node ids.")
        for key, now in (("sample_interval_hours", self.sample_interval_hours),
                         ("nwp_offset_hours", self.nwp_offset_hours)):
            if int(attrs[key]) != now:
                raise PlanMismatch(f"{self.path} was collected with {key}={attrs[key]}, now "
                                   f"{now}: its samples would leave the 6-hourly grid. Start a "
                                   "new file.")
        return int(attrs["epoch_unix"])

    def _create_file(self, epoch_unix: int) -> None:
        p = self.plan
        attrs = {
            "source": "live_collection",
            "sampling": "subsegments",
            "route_label": self.label,
            "route_key": p.route_key,
            "route_name": p.route_name,
            "route_waypoints_json": json.dumps(p.waypoints),
            "port_trim_nm": p.port_trim_nm,
            "plan_fingerprint": p.fingerprint,
            "n_subsegments": len(p.subsegments),
            "epoch_unix": int(epoch_unix),
            "epoch_utc": utc(epoch_unix),
            "sample_interval_hours": self.sample_interval_hours,
            "nwp_offset_hours": self.nwp_offset_hours,
            "forecast_days": FORECAST_DAYS,
            "sample_hour_definition": "hours from epoch_utc to the scheduled time of the sample",
            "forecast_hour_definition": "hours from the scheduled time of the sample "
                                        "(epoch_unix + 3600 * sample_hour) to the forecast valid time",
            "actual_weather_definition": "Open-Meteo current conditions at query time "
                                         "(see /samples query_start_unix)",
            "node_definition": "one node per subsegment (shared/subsegments.py); lat/lon is its "
                               "midpoint, distance_from_start_nm its start on the trimmed route, "
                               "segment its leg, is_original marks the first subsegment of a leg",
            "wave_height_m": WAVE_HEIGHT_NOTE,
            "beaufort_missing_value": BEAUFORT_MISSING,
        }
        for g, grid in p.grids.items():
            attrs[f"{g}_grid"] = grid.name
            attrs[f"{g}_api_url"] = grid.api_url
            attrs[f"{g}_api_params_json"] = json.dumps(grid.api_params)
            attrs[f"{g}_variables_json"] = json.dumps(list(API_FIELDS[g]))
            attrs[f"n_{g}_cells"] = len(p.queries[g])
        create_hdf5(self.path, plan_metadata(p), attrs,
                    metadata_dtype=SUBSEGMENT_METADATA_DTYPE,
                    actual_dtype=SUBSEGMENT_ACTUAL_DTYPE,
                    samples_dtype=SAMPLES_DTYPE)
        self.epoch_unix = int(epoch_unix)
        logger.info("[%s] Created %s: %d subsegments, epoch %s", self.label, self.path,
                    len(p.subsegments), utc(epoch_unix))

    def sample_hour(self, reference_unix: int) -> int:
        epoch = reference_unix if self.epoch_unix is None else self.epoch_unix
        return int(reference_unix - epoch) // 3600

    def has_sample(self, reference_unix: int) -> bool:
        if self.epoch_unix is None:
            return False
        return self.sample_hour(reference_unix) in set(get_completed_runs(self.path))

    # --- checks and logging ----------------------------------------------

    def _log_runs(self, reference_unix: int) -> Dict[str, int]:
        runs = {}
        for g, grid in self.plan.grids.items():
            init, avail = model_run(grid, self.get)
            runs[g] = init
            if init < 0:
                continue
            age = (reference_unix - init) / 3600.0
            limit = self.max_run_age_hours.get(g)
            msg = ("[%s] %s: newest %s run %s, available %s (%.1f h old at the scheduled time)"
                   % (self.label, g, grid.api_params["models"], utc(init), utc(avail), age))
            if limit is not None and age > limit:
                logger.warning("%s; older than the expected %.0f h, is NWP_OFFSET_HOURS too small?",
                               msg, limit)
            else:
                logger.info(msg)
        return runs

    def _check(self, g: str, gw: GridWeather) -> Tuple[int, int]:
        """Log substituted and NaN cells of grid g; return their counts."""
        queries = self.plan.queries[g]
        subst = find_substitutions(queries, gw)
        served = {k: (float(gw.served_lat[k]), float(gw.served_lon[k])) for k in subst}
        if subst:
            changed = served != self._last_substitutions[g]
            logger.info("[%s] %s: %d of %d cells served by another grid point than predicted "
                        "(near land the API substitutes a sea point)%s", self.label, g,
                        len(subst), len(queries), "" if changed else ", same as last sample")
            if changed:
                for k in subst:
                    q, (lat, lon) = queries[k], served[k]
                    logger.info("[%s] %s:   %s: predicted (%.5f, %.5f), served (%.5f, %.5f), "
                                "%.1f NM apart", self.label, g, _where(self.plan, q), q.grid_lat,
                                q.grid_lon, lat, lon, _nm_apart(q.grid_lat, q.grid_lon, lat, lon))
        else:
            logger.info("[%s] %s: all %d cells served by the predicted grid point",
                        self.label, g, len(queries))
        self._last_substitutions[g] = served

        nan = find_nan_cells(gw)
        if nan:
            logger.warning("[%s] %s: NaN in model inputs at %d of %d cells (written as NaN)",
                           self.label, g, len(nan), len(queries))
            for k, (cols, n_bad, n_all) in nan.items():
                logger.warning("[%s] %s:   %s: current conditions NaN in %s; %d of %d hourly "
                               "values NaN", self.label, g, _where(self.plan, queries[k]),
                               cols or "none", n_bad, n_all)
        return len(nan), len(subst)

    # --- one sample -------------------------------------------------------

    def collect(self, reference_unix: int, pacer: Pacer) -> bool:
        """Collect and append the sample scheduled at reference_unix. Returns
        True if it was written; API failures are logged and nothing is written."""
        if self.epoch_unix is None:
            self._create_file(reference_unix)
        sample_hour = self.sample_hour(reference_unix)
        if sample_hour < 0:
            logger.error("[%s] %s is before the file's epoch; skipped", self.label, utc(reference_unix))
            return False
        p = self.plan
        calls = calls_per_sample(p)
        logger.info("[%s] sample_hour %d (%s): %d subsegments, %s", self.label, sample_hour,
                    utc(reference_unix), len(p.subsegments),
                    ", ".join(f"{len(p.queries[g])} {g} cells" for g in p.queries))
        t0 = time.time()
        runs = self._log_runs(reference_unix)
        weather, nan_cells, substituted = {}, {}, {}
        try:
            for g, grid in p.grids.items():
                bodies = fetch_cells(g, grid, p.queries[g], pacer, self.get)
                weather[g] = parse_responses(g, bodies)
                nan_cells[g], substituted[g] = self._check(g, weather[g])
            actual, predicted = build_rows(p, weather, sample_hour, reference_unix)
        except ApiError as e:
            logger.error("[%s] sample_hour %d not collected: %s", self.label, sample_hour, e)
            return False
        t1 = time.time()
        samples = pd.DataFrame([{
            "sample_hour": sample_hour,
            "reference_time_unix": int(reference_unix),
            "query_start_unix": int(t0),
            "query_end_unix": int(t1),
            "wind_run_init_unix": runs.get(WIND, -1),
            "current_run_init_unix": runs.get(CURRENT, -1),
            "wind_nan_cells": nan_cells[WIND],
            "current_nan_cells": nan_cells[CURRENT],
            "wind_substituted_cells": substituted[WIND],
            "current_substituted_cells": substituted[CURRENT],
        }])
        append_sample(self.path, actual, predicted, samples)
        level = logging.WARNING if any(nan_cells.values()) else logging.INFO
        logger.log(level, "[%s] sample_hour %d written: %d actual + %d predicted rows, "
                   "%.0f API calls, %.1f min, NaN cells: wind %d, current %d; file %.1f MB",
                   self.label, sample_hour, len(actual), len(predicted), sum(calls.values()),
                   (t1 - t0) / 60.0, nan_cells[WIND], nan_cells[CURRENT],
                   os.path.getsize(self.path) / 2**20)
        return True


# ---------------------------------------------------------------------------
# Removed: fixed-spacing collection
# ---------------------------------------------------------------------------

def collect(config, hdf5_path=None):
    """Removed on 2026-10-14.

    The fixed-spacing collector (generate_waypoints every interval_nm, with
    Open-Meteo's default best_match models and cell selection) produced
    experiments A-D. New collections sample by subsegment with pinned grids:
    see run_all.py.
    """
    raise RuntimeError("collect.collector.collect() was removed: it sampled at fixed spacing "
                       "with Open-Meteo's best_match models. Use run_all.py, which samples "
                       "by subsegment with pinned grids.")

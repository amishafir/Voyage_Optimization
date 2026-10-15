"""
Read a route's weather archive (the live collector's HDF5 layout, "model-runs-v1",
see pipeline/shared/run_archive.py): the route's subsegments and, from every model
run, only the runs and hours a voyage from `start` to `start + ETA` can use, at
their native hourly granularity on the native grid cells.

Time is counted in 15-minute steps from the voyage start, which is rounded to
the nearest quarter hour. A run issued at step i is known from step i on.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List

import h5py
import numpy as np

LAYOUT = "model-runs-v1"
STEP_SECONDS = 900
GRIDS = ("wind", "current")
COLUMNS = {   # (speed [km/h], direction [deg]); wind direction is "from", current direction "to"
    "wind": ("wind_speed_10m_kmh", "wind_direction_10m_deg"),
    "current": ("ocean_current_velocity_kmh", "ocean_current_direction_deg"),
}


class ReferenceTimeError(ValueError):
    """The voyage start is not covered by the archive."""


@dataclass
class RunSlice:
    grid: str
    name: str                   # group name, e.g. "2026-10-14T12"
    init_unix: int
    init_step: int
    first_step: int             # step of the first kept hour
    speed: np.ndarray           # (n_cells, n_hours) float32, km/h
    direction: np.ndarray       # (n_cells, n_hours) float32, deg
    run_end_unix: int           # last valid time of the stored run

    @property
    def n_hours(self) -> int:
        return self.speed.shape[1]

    @property
    def last_step(self) -> int:
        return self.first_step + 4 * (self.n_hours - 1)


@dataclass
class VoyageData:
    archive: str
    attrs: Dict
    requested_start_unix: float
    start_unix: int
    eta_steps: int
    subsegments: np.ndarray                 # /plan/subsegments rows
    n_cells: Dict[str, int]
    runs: Dict[str, List[RunSlice]] = field(default_factory=dict)

    @property
    def end_unix(self) -> int:
        return self.start_unix + self.eta_steps * STEP_SECONDS

    def utc(self, step: int) -> datetime:
        return datetime.fromtimestamp(self.start_unix + step * STEP_SECONDS, timezone.utc)


# ---------------------------------------------------------------------------
# Start time and ETA
# ---------------------------------------------------------------------------

def parse_start(text: str) -> float:
    """UTC Unix time of 'YYYY-MM-DD HH:MM[:SS]', 'YYYY-MM-DDTHH:MM' or 'YYYY-MM-DD 13.3'
    (decimal hours)."""
    m = re.fullmatch(r"\s*(\d{4}-\d{2}-\d{2})[ T](\d{1,2})(?::(\d{2})(?::(\d{2}(?:\.\d*)?))?|(\.\d*))?\s*(?:Z|UTC)?\s*",
                     text)
    if not m:
        raise ValueError(f"cannot read start time {text!r}; use 'YYYY-MM-DD HH:MM' (UTC)")
    date, hour, minute, second, frac = m.groups()
    day = datetime.strptime(date, "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp()
    hours = int(hour) + (float(frac) if frac else 0.0)
    seconds = hours * 3600 + int(minute or 0) * 60 + float(second or 0)
    if not 0 <= seconds < 86400:
        raise ValueError(f"time of day out of range in {text!r}")
    return day + seconds


def round_to_step(unix: float) -> int:
    """Nearest quarter hour (halves round up)."""
    return int(math.floor((unix + STEP_SECONDS / 2) / STEP_SECONDS)) * STEP_SECONDS


def eta_to_steps(eta_hours: float) -> int:
    steps = round(eta_hours * 4)
    if steps < 1 or abs(eta_hours * 4 - steps) > 1e-9:
        raise ValueError(f"ETA must be a positive multiple of 0.25 h, got {eta_hours}")
    return steps


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------

def _step(unix: int, start_unix: int) -> int:
    d = int(unix) - start_unix
    if d % STEP_SECONDS:
        raise ValueError(f"time {unix} is not on a quarter hour")
    return d // STEP_SECONDS


def _select_runs(f: h5py.File, grid: str, start_unix: int, end_unix: int, path: str) -> List[RunSlice]:
    """The runs a voyage can draw on: every run issued after the start and by the end,
    and, among the runs issued by the start, the newest and each older one that
    reaches further in time, until one reaches the end."""
    hour_lo = start_unix // 3600 * 3600                 # hours that bracket the voyage
    hour_hi = -(-end_unix // 3600) * 3600
    runs = []
    for name, g in f[grid].items():
        if g.attrs.get("complete", False):
            t = g["time_unix"][()]
            runs.append((int(g.attrs["run_init_unix"]), name, int(t[0]), int(t[-1])))
    runs.sort()

    keep, reach = [], None
    for init, name, first, last in reversed([r for r in runs if r[0] <= start_unix]):
        if reach is None or last > reach:
            keep.append((init, name))
            reach = last
        if reach >= hour_hi:
            break
    covered = any(first <= hour_lo and last >= -(-start_unix // 3600) * 3600
                  for init, name, first, last in runs if init <= start_unix)
    if not covered:
        spans = ", ".join(f"{n} {_iso(a)}..{_iso(b)}" for _, n, a, b in runs) or "none"
        raise ReferenceTimeError(
            f"the start time {_iso(start_unix)} is not covered by the {grid} data in {path} "
            f"(stored {grid} runs: {spans})")
    keep += [(init, name) for init, name, _, _ in runs if start_unix < init <= end_unix]

    out = []
    for init, name in sorted(keep):
        g = f[grid][name]
        t = g["time_unix"][()].astype(np.int64)
        h = np.flatnonzero((t >= hour_lo) & (t <= hour_hi))
        if not len(h):
            continue
        h0, h1 = int(h[0]), int(h[-1]) + 1
        speed_col, dir_col = COLUMNS[grid]
        out.append(RunSlice(grid=grid, name=name, init_unix=init, init_step=_step(init, start_unix),
                            first_step=_step(t[h0], start_unix),
                            speed=np.ascontiguousarray(g[speed_col][:, h0:h1], dtype=np.float32),
                            direction=np.ascontiguousarray(g[dir_col][:, h0:h1], dtype=np.float32),
                            run_end_unix=int(t[-1])))
    return out


def _iso(unix: int) -> str:
    return datetime.fromtimestamp(int(unix), timezone.utc).strftime("%Y-%m-%d %H:%M")


def load_voyage_data(path: str, start: str, eta_hours: float) -> VoyageData:
    """Route and weather for a voyage from `start` (UTC, rounded to the nearest
    quarter hour) with an ETA of `eta_hours` (a multiple of 0.25 h) after it."""
    requested = parse_start(start)
    start_unix = round_to_step(requested)
    eta_steps = eta_to_steps(eta_hours)
    with h5py.File(path, "r") as f:
        attrs = {k: (v.decode() if isinstance(v, bytes) else v) for k, v in f.attrs.items()}
        if attrs.get("layout") != LAYOUT:
            raise ValueError(f"{path} is not a {LAYOUT} archive (layout={attrs.get('layout')!r})")
        data = VoyageData(archive=str(path), attrs=attrs, requested_start_unix=requested,
                          start_unix=start_unix, eta_steps=eta_steps,
                          subsegments=f["plan/subsegments"][()],
                          n_cells={"wind": len(f["plan/wind_cells"]),
                                   "current": len(f["plan/current_cells"])})
        for grid in GRIDS:
            data.runs[grid] = _select_runs(f, grid, start_unix, data.end_unix, str(path))
    return data

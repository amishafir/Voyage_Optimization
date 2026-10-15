"""
HDF5 archive of model runs for one route, as written by the live collector
(collect/collector.py, run_all.py).

Each model run is stored once, as published: its full hourly series for every
weather-grid cell the route passes through. Products that need weather at a
given time (e.g. the 15-minute pseudo real-time and forecast series) are built
from these runs later.

Layout:
    attrs                    route, plan fingerprint, grids, API parameters, ...
    /plan/subsegments        one row per subsegment (SUBSEGMENT_DTYPE); wind_cell and
                             current_cell index the rows of the two cell tables
    /plan/wind_cells         one row per distinct wind cell (CELL_DTYPE)
    /plan/current_cells      one row per distinct current cell (CELL_DTYPE)
    /wind/<YYYY-MM-DDTHH>    one ECMWF IFS run, named by its start time (UTC)
    /current/<YYYY-MM-DDTHH> one SMOC currents run
    /runs                    every expected run with its status (RUNS_DTYPE)

A run group holds:
    time_unix                (n_hours,) int64, valid times (UTC, Unix seconds)
    <column>                 (n_cells, n_hours) float32 per variable, rows in the
                             order of the grid's cell table; NaN where the API
                             returned null
    served_lat, served_lon   (n_cells,) float32, the grid point the API reported
                             serving each cell
    attrs                    run_init_unix, availability_unix, fetch times, NaN and
                             substitution counts, API parameters; complete=True
                             is written last

Usage:
    from shared.run_archive import read_plan, read_runs, read_run, run_inits
    wind = read_run(path, "wind", run_inits(path, "wind")[-1])
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Dict, List, Mapping, Optional

import h5py
import numpy as np
import pandas as pd

LAYOUT = "model-runs-v1"
GRIDS = ("wind", "current")

SUBSEGMENT_DTYPE = np.dtype([
    ("index", "i4"),
    ("leg", "i4"),                  # leg of the trimmed route (shared/subsegments.py)
    ("start_nm", "f8"),             # distance along the trimmed route
    ("length_nm", "f8"),
    ("bearing_deg", "f8"),
    ("start_lat", "f8"), ("start_lon", "f8"),
    ("mid_lat", "f8"), ("mid_lon", "f8"),
    ("end_lat", "f8"), ("end_lon", "f8"),
    ("wind_cell", "i4"),            # row of /plan/wind_cells
    ("current_cell", "i4"),         # row of /plan/current_cells
])

CELL_DTYPE = np.dtype([
    ("index", "i4"),
    ("row", "i4"), ("col", "i4"),           # cell of the grid (shared/weather_grids.py)
    ("grid_lat", "f8"), ("grid_lon", "f8"), # grid point predicted to serve the cell
    ("query_lat", "f8"), ("query_lon", "f8"),  # route point the API is asked for
    ("length_nm", "f8"),                    # route length inside the cell
    ("first_subsegment", "i4"),
    ("n_subsegments", "i4"),
])

STATUSES = ("pending", "complete", "missed", "incomplete", "discarded")

RUNS_DTYPE = np.dtype([
    ("grid", "S8"),
    ("run_init_unix", "i8"),
    ("status", "S10"),
    ("probe_attempts", "i4"),            # metadata reads, plus Single Runs probes for wind
    ("fetch_requests", "i4"),            # chunk requests, retries included
    ("api_calls", "f8"),                 # Open-Meteo's count for probes and fetches
    ("first_probe_success_unix", "i8"),  # -1 = never
    ("availability_unix", "i8"),         # from Open-Meteo's metadata; -1 = unknown
    ("fetch_start_unix", "i8"),
    ("fetch_end_unix", "i8"),
    ("updated_unix", "i8"),
    ("note", "S200"),
])


def run_name(run_init_unix: int) -> str:
    """Group name of a run: its start time, e.g. '2026-10-14T12'."""
    return datetime.fromtimestamp(int(run_init_unix), timezone.utc).strftime("%Y-%m-%dT%H")


def _structured(df: pd.DataFrame, dtype: np.dtype) -> np.ndarray:
    missing = [n for n in dtype.names if n not in df.columns]
    if missing:
        raise ValueError(f"missing columns {missing}")
    arr = np.empty(len(df), dtype=dtype)
    for name in dtype.names:
        values = df[name].values
        arr[name] = (df[name].astype(str).values.astype(dtype[name])
                     if dtype[name].kind == "S" else values)
    return arr


def _frame(arr: np.ndarray) -> pd.DataFrame:
    df = pd.DataFrame(arr) if len(arr) else pd.DataFrame(columns=list(arr.dtype.names))
    for name in arr.dtype.names:
        if arr.dtype[name].kind == "S":
            df[name] = [b.decode("utf-8") if isinstance(b, bytes) else str(b) for b in df[name]]
    return df


# ---------------------------------------------------------------------------
# Create and read
# ---------------------------------------------------------------------------

def create_archive(path: str, subsegments: pd.DataFrame, cells: Mapping[str, pd.DataFrame],
                   attrs: Optional[Mapping] = None) -> None:
    """Create a new archive with its plan tables and an empty /runs table."""
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with h5py.File(path, "w-") as f:
        f.attrs["layout"] = LAYOUT
        f.attrs["created_at"] = datetime.now(timezone.utc).isoformat()
        for k, v in (attrs or {}).items():
            f.attrs[k] = v
        plan = f.create_group("plan")
        plan.create_dataset("subsegments", data=_structured(subsegments, SUBSEGMENT_DTYPE))
        for g in GRIDS:
            plan.create_dataset(f"{g}_cells", data=_structured(cells[g], CELL_DTYPE))
            f.create_group(g)
        f.create_dataset("runs", shape=(0,), maxshape=(None,), dtype=RUNS_DTYPE, chunks=(256,))


def read_attrs(path: str) -> Dict:
    with h5py.File(path, "r") as f:
        return {k: (v.decode("utf-8") if isinstance(v, bytes) else v) for k, v in f.attrs.items()}


def read_plan(path: str) -> Dict[str, pd.DataFrame]:
    """{'subsegments': ..., 'wind_cells': ..., 'current_cells': ...}"""
    with h5py.File(path, "r") as f:
        return {name: _frame(f["plan"][name][:]) for name in f["plan"]}


def read_runs(path: str) -> pd.DataFrame:
    """The /runs table, one row per expected run."""
    with h5py.File(path, "r") as f:
        return _frame(f["runs"][:])


def write_runs(path: str, runs: pd.DataFrame) -> None:
    """Replace the /runs table."""
    arr = _structured(runs, RUNS_DTYPE)
    with h5py.File(path, "a") as f:
        ds = f["runs"]
        ds.resize(len(arr), axis=0)
        ds[:] = arr


# ---------------------------------------------------------------------------
# Runs
# ---------------------------------------------------------------------------

def write_run(path: str, grid: str, run_init_unix: int, time_unix: np.ndarray,
              values: Mapping[str, np.ndarray], served_lat: np.ndarray, served_lon: np.ndarray,
              attrs: Optional[Mapping] = None) -> None:
    """Store one run as /<grid>/<run name>, replacing an earlier copy."""
    name = f"{grid}/{run_name(run_init_unix)}"
    with h5py.File(path, "a") as f:
        if name in f:
            del f[name]
        g = f.create_group(name)
        g.create_dataset("time_unix", data=np.asarray(time_unix, dtype=np.int64))
        for col, arr in values.items():
            g.create_dataset(col, data=np.asarray(arr, dtype=np.float32),
                             compression="gzip", shuffle=True)
        g.create_dataset("served_lat", data=np.asarray(served_lat, dtype=np.float32))
        g.create_dataset("served_lon", data=np.asarray(served_lon, dtype=np.float32))
        g.attrs["grid"] = grid
        g.attrs["run_init_unix"] = int(run_init_unix)
        for k, v in (attrs or {}).items():
            g.attrs[k] = v
        g.attrs["complete"] = True


def has_run(path: str, grid: str, run_init_unix: int) -> bool:
    """True if a complete copy of the run is stored."""
    name = f"{grid}/{run_name(run_init_unix)}"
    with h5py.File(path, "r") as f:
        return name in f and bool(f[name].attrs.get("complete", False))


def run_inits(path: str, grid: str) -> List[int]:
    """Start times of the stored complete runs of a grid, in order."""
    with h5py.File(path, "r") as f:
        return sorted(int(g.attrs["run_init_unix"]) for g in f[grid].values()
                      if g.attrs.get("complete", False))


def read_run_attrs(path: str, grid: str, run_init_unix: int) -> Dict:
    """The attributes of one stored run (run timing, leads, counts, API parameters)."""
    with h5py.File(path, "r") as f:
        g = f[f"{grid}/{run_name(run_init_unix)}"]
        return {k: (v.decode("utf-8") if isinstance(v, bytes) else v) for k, v in g.attrs.items()}


def read_run(path: str, grid: str, run_init_unix: int) -> Dict:
    """One run: {'time_unix', <columns>, 'served_lat', 'served_lon', 'attrs'}."""
    with h5py.File(path, "r") as f:
        g = f[f"{grid}/{run_name(run_init_unix)}"]
        out = {k: g[k][()] for k in g}
        out["attrs"] = {k: (v.decode("utf-8") if isinstance(v, bytes) else v)
                        for k, v in g.attrs.items()}
    return out

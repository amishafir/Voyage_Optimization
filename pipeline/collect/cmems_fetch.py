#!/usr/bin/env python3
"""
Fetch one Meteo-France SMOC currents run from Copernicus Marine, for given current cells.

The backup source for the collector's currents (collect/collector.py): Open-Meteo's
meteofrance_currents is SMOC, which Copernicus Marine publishes as
cmems_mod_glo_phy_anfc_merged-uv_PT1H-i (hourly merged surface currents: circulation,
tides and Stokes drift; utotal/vtotal). Copernicus keeps only its newest forecast run, so
a run can be fetched only until the next one replaces it.

Runs in its own Python environment (copernicusmarine, xarray, numpy) so that the
collector does not import the Copernicus client; the collector calls it as a subprocess:

    PYTHON cmems_fetch.py CELLS.npy RUN_INIT_UNIX HOURS OUT.npz

CELLS.npy holds (n, 2) int rows and columns of the collector's current grid
(shared/weather_grids.py CURRENT_GRID: points at -80 + 1/24 + row/12, -180 + 1/24 + col/12).
Copernicus's grid points sit at -80 + i/12, -180 + j/12, half a cell off: the value used
is the one at POINT (see below), or the nearest of the four surrounding points with data.

Exit status: 0 stored; 3 Copernicus's newest run is not RUN_INIT (nothing written);
1 any other failure. Needs a Copernicus Marine login on the machine
(`copernicusmarine login`, once, by the account's owner).

OUT.npz: time_unix (h,), velocity_kmh and direction_deg (n, h; direction the current flows
to, as Open-Meteo's ocean_current_direction), point_lat/point_lon (n,) of the points used,
substituted (n,) bool, meta (JSON).
"""

from __future__ import annotations

import json
import sys
import time

import numpy as np

DATASET = "cmems_mod_glo_phy_anfc_merged-uv_PT1H-i"
OTHER_RUN = 3          # exit status; 2 is what Python itself uses for a script it cannot run
VARIABLES = ("utotal", "vtotal")
# Which of the four Copernicus points around a collector cell Open-Meteo serves, as
# (d_row, d_col) offsets from (row, col); set from the comparison of 2026-10-21.
POINT = (0, 0)
NEIGHBOURS = ((0, 0), (0, 1), (1, 0), (1, 1))
N_LON = 4320


def main(argv) -> int:
    cells_path, init, hours, out = argv[1], int(argv[2]), int(argv[3]), argv[4]
    import copernicusmarine as cm
    import xarray as xr

    cells = np.load(cells_path).astype(np.int64)
    t0, t1 = init, init + (hours - 1) * 3600
    iso = lambda t: time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(t))
    ds = cm.open_dataset(DATASET, variables=list(VARIABLES), start_datetime=iso(t0),
                         end_datetime=iso(t1), service="arco-time-series")
    full = cm.open_dataset(DATASET, variables=[VARIABLES[0]], service="arco-time-series")
    last = int(full["time"].values[-1].astype("datetime64[s]").astype(np.int64))
    if last != t1:
        # The run on offer ends at its start + hours - 1 (a 00 UTC run reaches D+9 23:00).
        print(f"Copernicus's newest run ends {iso(last)}, not {iso(t1)}: it is not the "
              f"requested run", file=sys.stderr)
        return OTHER_RUN
    lat, lon = ds["latitude"].values, ds["longitude"].values
    if not (abs(lat[0] + 80) < 1e-6 and abs(lon[0] + 180) < 1e-6 and len(lon) == N_LON):
        print(f"unexpected Copernicus grid: lat {lat[:2]}, lon {lon[:2]}, {len(lon)} longitudes",
              file=sys.stderr)
        return 1
    order = [POINT] + [nb for nb in NEIGHBOURS if nb != POINT]
    I = np.stack([cells[:, 0] + dr for dr, _ in order], 1)           # (n, 4)
    J = np.stack([(cells[:, 1] + dc) % N_LON for _, dc in order], 1)
    sel = ds.isel(latitude=xr.DataArray(I.ravel(), dims="p"),
                  longitude=xr.DataArray(J.ravel(), dims="p"))
    if "depth" in sel.dims:
        sel = sel.isel(depth=0)
    sel = sel.load()
    times = sel["time"].values.astype("datetime64[s]").astype(np.int64)
    if len(times) != hours or times[0] != t0:
        print(f"Copernicus returned {len(times)} hours from {iso(int(times[0]))}", file=sys.stderr)
        return 1
    u = sel[VARIABLES[0]].transpose("p", "time").values.reshape(len(cells), 4, hours)
    v = sel[VARIABLES[1]].transpose("p", "time").values.reshape(len(cells), 4, hours)
    has = np.isfinite(u).all(axis=2) & np.isfinite(v).all(axis=2)     # (n, 4)
    pick = np.where(has[:, 0], 0, np.argmax(has, axis=1))             # first point with data
    rows = np.arange(len(cells))
    uu, vv = u[rows, pick], v[rows, pick]
    uu[~has[rows, pick]] = np.nan
    vv[~has[rows, pick]] = np.nan
    np.savez_compressed(
        out, time_unix=times,
        velocity_kmh=(np.hypot(uu, vv) * 3.6).astype(np.float32),
        direction_deg=((np.degrees(np.arctan2(uu, vv)) + 360.0) % 360.0).astype(np.float32),
        point_lat=lat[I[rows, pick]].astype(np.float32),
        point_lon=lon[J[rows, pick]].astype(np.float32),
        substituted=(pick != 0),
        meta=json.dumps({"dataset_id": DATASET, "variables": VARIABLES, "point": POINT,
                         "run_end_utc": iso(last), "fetched_utc": iso(int(time.time()))}))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv))
    except Exception as e:        # reported to the collector through the exit status and stderr
        print(f"{type(e).__name__}: {e}", file=sys.stderr)
        sys.exit(1)

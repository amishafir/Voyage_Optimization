"""
A small synthetic route archive, written with the collector's own writer
(pipeline/shared/run_archive.py), shared by the DP tests.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

V2 = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(V2), str(V2.parent / "pipeline")]

from shared import run_archive  # noqa: E402
from voyage_v2 import Ship  # noqa: E402

SHIP = Ship.from_yaml()
H = 3600
D0 = 1792022400 - 86400                      # 2026-10-14 00:00 UTC
LENGTHS = [1.3, 0.9, 0.08, 1.7, 0.6, 2.4, 1.1, 0.12, 1.5, 0.31]   # two below 0.15 NM
BEARINGS = [20.0, 35.0, 80.0, 95.0, 140.0, 170.0, 200.0, 250.0, 300.0, 330.0]
N_WIND, N_CURRENT = 4, 3
START, ETA_H = "2026-10-14 07:20", 1.5


def write_archive(path):
    n = len(LENGTHS)
    sub = pd.DataFrame({
        "index": range(n), "leg": 0, "start_nm": np.concatenate([[0], np.cumsum(LENGTHS)[:-1]]),
        "length_nm": LENGTHS, "bearing_deg": BEARINGS,
        "start_lat": 0.0, "start_lon": 0.0, "mid_lat": 0.0, "mid_lon": 0.0, "end_lat": 0.0, "end_lon": 0.0,
        "wind_cell": [i % N_WIND for i in range(n)], "current_cell": [(i // 2) % N_CURRENT for i in range(n)]})
    cells = {g: pd.DataFrame({"index": range(c), "row": 0, "col": range(c), "grid_lat": 0.0, "grid_lon": 0.0,
                              "query_lat": 0.0, "query_lon": 0.0, "length_nm": 1.0,
                              "first_subsegment": 0, "n_subsegments": 1})
             for g, c in (("wind", N_WIND), ("current", N_CURRENT))}
    run_archive.create_archive(path, sub, cells, {"route_label": "Test", "route_name": "synthetic"})
    rng = np.random.default_rng(11)
    for init, hours in ((D0, 72), (D0 + 6 * H, 24)):
        run_archive.write_run(path, "wind", init, init + H * np.arange(hours),
                              {"wind_speed_10m_kmh": rng.uniform(5, 75, (N_WIND, hours)),
                               "wind_direction_10m_deg": rng.uniform(0, 360, (N_WIND, hours))},
                              np.zeros(N_WIND), np.zeros(N_WIND))
    run_archive.write_run(path, "current", D0, D0 + H * np.arange(72),
                          {"ocean_current_velocity_kmh": rng.uniform(0, 5, (N_CURRENT, 72)),
                           "ocean_current_direction_deg": rng.uniform(0, 360, (N_CURRENT, 72))},
                          np.zeros(N_CURRENT), np.zeros(N_CURRENT))

"""
Time the full graph and the Luo variants on both routes, for comparing machines.

    python3 v2/tools/benchmark.py DATA_DIR [--start "2026-10-14 13:20"]

DATA_DIR holds route1_runs.h5 and route2_runs.h5 (ETA 280 h and 168 h). Single core.
"""

import argparse
import os
import platform
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from voyage_v2 import Voyage, load_voyage_data  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("data_dir")
ap.add_argument("--start", default="2026-10-14 13:20")
a = ap.parse_args()
print(f"host {platform.node()}, {platform.machine()}, python {platform.python_version()}, data {a.data_dir}", flush=True)
for name, eta in (("route1_runs.h5", 280), ("route2_runs.h5", 168)):
    v = Voyage(load_voyage_data(os.path.join(a.data_dir, name), a.start, eta))
    t0 = time.perf_counter()
    full = v.solve()
    print(f"== {name}: full graph {full.fuel_mt:.4f} mt in {time.perf_counter() - t0:.1f} s, "
          f"constant SOG {full.constant_sog_fuel_mt:.4f} mt", flush=True)
    for k, pricing in ((24, "integrated"), (24, "start"), (4, "integrated"), (4, "start"), (1, "integrated")):
        t0 = time.perf_counter()
        p = v.solve_luo(epoch_steps=k, pricing=pricing)
        print(f"   Luo {k / 4:g} h {pricing:10s}: planned {p.planned_fuel_mt:9.4f}, realized {p.fuel_mt:9.4f} mt "
              f"({100 * (p.fuel_mt / full.fuel_mt - 1):+.3f}% vs full graph), {time.perf_counter() - t0:.1f} s",
              flush=True)

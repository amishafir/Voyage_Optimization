"""
Phase-0 golden freeze for the streaming-solver refactor.

Runs the SR solver (node-first, Mode C oracle) on a fixed voyage set and
records everything the refactor must reproduce BIT-FOR-BIT:

  - total_fuel_mt / voyage_time_h as full-precision reprs
  - a sha256 over the full schedule (every arc, every float, full repr)
  - n_nodes / n_edges (streaming engine must EVALUATE exactly n_edges arcs)
  - build_s / solve_s and peak RSS (informational, not gated)

Design doc: docs/refactor_streaming_design.md (approved 2026-08-06).
Luo is out of scope (stays on the legacy engine).

Usage (from pipeline/dp_rebuild/):
  python3 regression_freeze.py --set quick            # R1 sh6 + R2 sh0  -> goldens/quick.json
  python3 regression_freeze.py --set full             # all 19 voyages   -> goldens/full.json
  python3 regression_freeze.py --check goldens/quick.json [--engine streaming]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import resource
import subprocess
import sys
import time
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

import run_chain_sweep as rcs
import SR_main
from weather import VoyageWeather

QUICK = {"route1": [6], "route2": [0]}
FULL = {k: v["sh_bases"] for k, v in rcs.ROUTES.items()} if hasattr(rcs, "ROUTES") else None

EDGE_FIELDS = ("src_t", "src_d", "dst_t", "dst_d", "sog", "sws",
               "fcr_mt_per_h", "fuel_mt", "heading_deg")
WEATHER_FIELDS = ("wind_speed_10m_kmh", "wind_direction_10m_deg", "beaufort_number",
                  "wave_height_m", "ocean_current_velocity_kmh",
                  "ocean_current_direction_deg")


def _routes_table():
    """run_chain_sweep keeps its route configs in a module-level dict; find it."""
    for name in ("ROUTES", "ROUTE_CFGS", "CONFIGS"):
        if hasattr(rcs, name):
            return getattr(rcs, name)
    raise AttributeError("route config dict not found in run_chain_sweep")


def schedule_sha256(schedule) -> str:
    h = hashlib.sha256()
    for leg in schedule:
        for f in EDGE_FIELDS:
            v = getattr(leg, f, None)
            h.update(f"{f}={v!r};".encode())
        w = getattr(leg, "weather", None)
        if w is not None:
            for f in WEATHER_FIELDS:
                h.update(f"w.{f}={getattr(w, f, None)!r};".encode())
        h.update(b"|")
    return h.hexdigest()


def run_voyage(route_key: str, sh_base: int, engine: str = "legacy",
               voyage_cache: dict | None = None) -> dict:
    routes = _routes_table()
    cfg = routes[route_key]
    args = rcs._build_args(cfg, sh_base, node_first=True)
    if engine != "legacy":
        setattr(args, "engine", engine)
    voyage = None
    if voyage_cache is not None:
        key = cfg["h5"]
        if key not in voyage_cache:
            voyage_cache[key] = VoyageWeather(Path(rcs._resolve(cfg["h5"])))
        voyage = voyage_cache[key]
    t0 = time.time()
    res = SR_main.solve(args, voyage=voyage, verbose=False)
    wall = time.time() - t0
    return {
        "route": route_key,
        "sh_base": sh_base,
        "engine": engine,
        "total_fuel_mt": repr(res["total_fuel_mt"]),
        "voyage_time_h": repr(res["voyage_time_h"]),
        "n_nodes": res["n_nodes"],
        "n_edges": res["n_edges"],
        "schedule_sha256": schedule_sha256(res["schedule"]),
        "n_legs": len(res["schedule"]),
        "build_s": round(res.get("build_s", -1), 2),
        "solve_s": round(res.get("solve_s", -1), 3),
        "wall_s": round(wall, 2),
    }


def freeze(set_name: str, out: Path) -> None:
    plan = QUICK if set_name == "quick" else {k: v["sh_bases"] for k, v in _routes_table().items()}
    commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                            capture_output=True, text=True).stdout.strip()
    cache: dict = {}
    rows = []
    for route_key, sh_bases in plan.items():
        for sh in sh_bases:
            print(f"[freeze] {route_key} sh_base={sh} ...", flush=True)
            row = run_voyage(route_key, sh, voyage_cache=cache)
            print(f"         fuel={row['total_fuel_mt']}  edges={row['n_edges']}  "
                  f"wall={row['wall_s']}s", flush=True)
            rows.append(row)
    golden = {
        "set": set_name,
        "commit": commit,
        "engine": "legacy",
        "peak_rss_mb": round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / (1024 ** 2), 1),
        "voyages": rows,
    }
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(golden, indent=2) + "\n")
    print(f"[freeze] wrote {out}  ({len(rows)} voyages, peak RSS "
          f"{golden['peak_rss_mb']} MB)")


def check(golden_path: Path, engine: str) -> int:
    golden = json.loads(golden_path.read_text())
    cache: dict = {}
    failures = 0
    for ref in golden["voyages"]:
        row = run_voyage(ref["route"], ref["sh_base"], engine=engine, voyage_cache=cache)
        ok = True
        for k in ("total_fuel_mt", "voyage_time_h", "schedule_sha256", "n_legs"):
            if row[k] != ref[k]:
                ok = False
                print(f"[FAIL] {ref['route']} sh={ref['sh_base']} {k}:\n"
                      f"       golden {ref[k]}\n       got    {row[k]}")
        # streaming must evaluate exactly the legacy arc count
        if row["n_edges"] != ref["n_edges"]:
            ok = False
            print(f"[FAIL] {ref['route']} sh={ref['sh_base']} n_edges: "
                  f"golden {ref['n_edges']} got {row['n_edges']}")
        if ok:
            print(f"[ OK ] {ref['route']} sh={ref['sh_base']}  fuel={row['total_fuel_mt']}  "
                  f"wall={row['wall_s']}s")
        else:
            failures += 1
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / (1024 ** 2)
    print(f"[check] engine={engine}  failures={failures}  peak RSS {rss:.1f} MB "
          f"(golden run: {golden['peak_rss_mb']} MB)")
    return failures


def main() -> None:
    ap = argparse.ArgumentParser(prog="regression_freeze")
    ap.add_argument("--set", choices=["quick", "full"], help="freeze this voyage set")
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--check", type=Path, help="re-run and compare against this golden file")
    ap.add_argument("--engine", default="legacy",
                    help="engine to use for --check (legacy | streaming)")
    a = ap.parse_args()
    if a.set:
        freeze(a.set, a.out or _HERE / "goldens" / f"{a.set}.json")
    elif a.check:
        sys.exit(1 if check(a.check, a.engine) else 0)
    else:
        ap.error("need --set or --check")


if __name__ == "__main__":
    main()

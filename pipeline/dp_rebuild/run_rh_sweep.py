"""
Rolling-horizon consecutive-voyage chain sweep (both routes).

Wraps ``run_rh`` (single-voyage RH loop) into the same consecutive-voyage
chain protocol as ``run_chain_sweep`` (§5.1): for each route, voyage N+1
departs at the sample hour where voyage N arrives (step = ETA). At each
departure it runs the Naive baseline and the 6 h rolling-horizon loop for
SR (and Luo unless ``--skip_luo``).

Route configs (yaml / h5 / eta / sh_bases) are taken from
``run_chain_sweep.ROUTES`` so the RH and oracle sweeps stay on identical
route/data pairings and departure grids.

Output
------
<out_dir>/results.csv                          one row per (route, voyage)
<out_dir>/route1/voyage_00/rh_*.csv            per-voyage per-replan detail
...

Usage (from pipeline/dp_rebuild/)::

    python3 run_rh_sweep.py [--routes route1,route2] [--out_dir PATH]
        [--node_first] [--skip_luo] [--max_voyages N] [--max_replans N]

``--skip_luo`` reuses the paper's unchanged RH-Luo/Naive columns and runs
RH-SR only (fast). ``--node_first`` uses the adopted SR arc enumeration.
"""
from __future__ import annotations

import argparse
import csv
import sys
import time
from pathlib import Path
from typing import List

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from run_chain_sweep import ROUTES, _resolve  # noqa: E402
from run_rh import (  # noqa: E402
    load_forecast_index, run_naive, run_rh, write_replan_csv,
)
from weather import VoyageWeather  # noqa: E402


CSV_HEADER = [
    "route", "label", "voyage_idx", "sh_base", "eta_h", "sr_mode",
    "naive_mt", "rh_sr_mt", "rh_luo_mt",
    "rh_sr_vs_naive_pct", "rh_luo_vs_naive_pct",
    "rh_sr_final_d", "rh_luo_final_d", "arrival_h", "n_replans",
]


def _print_hdr(s: str) -> None:
    bar = "=" * 80
    print(f"\n{bar}\n{s}\n{bar}", flush=True)


def run_route(route_key: str, route_cfg: dict, out_dir: Path,
              node_first: bool, skip_luo: bool, skip_csv: bool,
              max_voyages: int, max_replans: int) -> List[dict]:
    sh_bases = route_cfg["sh_bases"]
    if max_voyages and max_voyages > 0:
        sh_bases = sh_bases[:max_voyages]
    yaml = _resolve(route_cfg["yaml"])
    h5 = _resolve(route_cfg["h5"])
    eta = float(route_cfg["eta"])

    _print_hdr(f"RH CHAIN — {route_key} ({route_cfg['label']})  "
               f"ETA={eta:.0f}  voyages={len(sh_bases)}  "
               f"SR={'node-first' if node_first else 'speed-first'}  "
               f"Luo={'skipped' if skip_luo else 'run'}")

    voyage = VoyageWeather(Path(h5))
    issues, max_lead = load_forecast_index(h5)
    print(f"Loaded {Path(h5).name}: L={voyage.length_nm:.1f} nm, "
          f"{len(issues)} forecast cycles", flush=True)

    rows: List[dict] = []
    for voyage_idx, sh_base in enumerate(sh_bases):
        _print_hdr(f"{route_key}  voyage {voyage_idx:02d}  sh_base={sh_base}")
        t0 = time.time()

        naive = run_naive(voyage, eta, sh_base, yaml=yaml, h5=h5)
        naive_mt = naive["total_fuel_mt"]
        print(f"  Naive: {naive_mt:.3f} mt", flush=True)

        rh = run_rh(voyage, issues, max_lead, eta, sh_base,
                    max_replans=max_replans, node_first=node_first,
                    yaml=yaml, h5=h5, skip_luo=skip_luo)

        sr_mt = rh["sr"]["realised_fuel_mt"]
        luo_mt = rh["luo"]["realised_fuel_mt"]
        sr_pct = (sr_mt - naive_mt) / naive_mt * 100.0 if naive_mt else float("nan")
        luo_pct = ((luo_mt - naive_mt) / naive_mt * 100.0
                   if (naive_mt and luo_mt == luo_mt) else float("nan"))
        print(f"  RH-SR : {sr_mt:.3f} mt ({sr_pct:+.2f}% vs Naive)  "
              f"final_d={rh['sr']['final_d']:.1f}/{voyage.length_nm:.1f}  "
              f"({time.time() - t0:.0f}s)", flush=True)
        if not skip_luo:
            print(f"  RH-Luo: {luo_mt:.3f} mt ({luo_pct:+.2f}% vs Naive)",
                  flush=True)

        if not skip_csv:
            vdir = out_dir / route_key / f"voyage_{voyage_idx:02d}"
            vdir.mkdir(parents=True, exist_ok=True)
            write_replan_csv(vdir / "rh_sr_replans.csv", rh["rows"]["sr"])
            write_replan_csv(vdir / "rh_sr_realized.csv", rh["realized"]["sr"])
            if not skip_luo:
                write_replan_csv(vdir / "rh_luo_replans.csv", rh["rows"]["luo"])
                write_replan_csv(vdir / "rh_luo_realized.csv", rh["realized"]["luo"])

        rows.append({
            "route": route_key, "label": route_cfg["label"],
            "voyage_idx": voyage_idx, "sh_base": sh_base, "eta_h": eta,
            "sr_mode": "node-first" if node_first else "speed-first",
            "naive_mt": naive_mt,
            "rh_sr_mt": sr_mt, "rh_luo_mt": luo_mt,
            "rh_sr_vs_naive_pct": sr_pct, "rh_luo_vs_naive_pct": luo_pct,
            "rh_sr_final_d": rh["sr"]["final_d"],
            "rh_luo_final_d": rh["luo"]["final_d"],
            "arrival_h": rh["sr"]["arrival_h"], "n_replans": rh["n_replans"],
        })

    return rows


def main() -> int:
    ap = argparse.ArgumentParser(prog="run_rh_sweep")
    ap.add_argument("--routes", default="route1,route2")
    ap.add_argument("--out_dir", default="runs/2026_07_16_rh_sweep")
    ap.add_argument("--node_first", action="store_true")
    ap.add_argument("--skip_luo", action="store_true",
                    help="Reuse the unchanged RH-Luo/Naive; run RH-SR only.")
    ap.add_argument("--skip_csv", action="store_true")
    ap.add_argument("--max_voyages", type=int, default=0)
    ap.add_argument("--max_replans", type=int, default=0)
    args = ap.parse_args()

    chosen = [r.strip() for r in args.routes.split(",") if r.strip()]
    unknown = [r for r in chosen if r not in ROUTES]
    if unknown:
        print(f"Unknown routes: {unknown}. Available: {list(ROUTES)}",
              file=sys.stderr)
        return 1

    project_root = _HERE.parent.parent
    out_dir = Path(args.out_dir)
    if not out_dir.is_absolute():
        out_dir = project_root / out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"Output dir: {out_dir}", flush=True)

    all_rows: List[dict] = []
    t_start = time.time()
    for route_key in chosen:
        all_rows.extend(run_route(
            route_key, ROUTES[route_key], out_dir,
            node_first=args.node_first, skip_luo=args.skip_luo,
            skip_csv=args.skip_csv, max_voyages=args.max_voyages,
            max_replans=args.max_replans))

    results_csv = out_dir / "results.csv"
    with open(results_csv, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=CSV_HEADER)
        w.writeheader()
        for row in all_rows:
            w.writerow(row)
    print(f"\nWrote {len(all_rows)} rows to {results_csv}")
    print(f"Total wall time: {(time.time() - t_start)/60.0:.1f} min")
    return 0


if __name__ == "__main__":
    sys.exit(main())

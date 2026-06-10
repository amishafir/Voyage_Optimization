"""
Mode-C departure-time chain sweep.

For each configured route, runs a consecutive-voyage chain stepping the
voyage-start sample_hour by the route's ETA: voyage N+1 starts when voyage N
arrives (using the fixed ETA, not each solver's realised arrival, so SR and
Luo see identical departure weather). Each voyage is solved with both
``SR_main.solve`` and ``luo_main.solve`` (Mode C — per-block active actual
weather anchored at the voyage-start sample_hour).

Output
------
runs/2026_06_01_chain_sweep/
    results.csv                                  — one row per (route, voyage)
    route1/voyage_00/sr.csv, luo.csv             — per-arc schedule CSVs
    route1/voyage_01/sr.csv, luo.csv
    ...
    route2/...

Usage::

    python3 run_chain_sweep.py
        [--routes route1,route2]   subset of routes to run
        [--out_dir PATH]           override output dir
        [--skip_csv]               skip per-voyage per-arc CSV writes (faster)

Backward compat: doesn't touch SR_main / luo_main main()s. Uses solve() API
added 2026-06-01.
"""
from __future__ import annotations

import argparse
import csv
import sys
import time
from argparse import Namespace
from pathlib import Path
from typing import List

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

import SR_main  # noqa: E402
import luo_main  # noqa: E402
from luo_main import write_luo_csv  # noqa: E402
from SR_main import write_arc_csv  # noqa: E402
from weather import VoyageWeather  # noqa: E402


# Route configurations. ETA is set to match Task 1 §5.1 (Atlantic ETA 168) and
# the May 25 parity number (Malacca ETA 280).
ROUTES = {
    "route1": {
        "label": "Malacca",
        "yaml": "../config/routes/persian_gulf_malacca_paper.yaml",
        "h5":   "../data/experiment_b_138wp.h5",
        "eta":  280,
        # sh_list[0]=6 on Shlomo2 exp_b. Step by ETA=280. Last sh used ≤ 2052.
        "sh_bases": [6, 286, 566, 846, 1126, 1406, 1686],
    },
    "route2": {
        "label": "Atlantic",
        "yaml": "../config/routes/st_johns_liverpool.yaml",
        "h5":   "../data/experiment_d_391wp.h5",
        "eta":  168,
        # sh_list[0]=0 on exp_d. Step by ETA=168. Last sh used = 1848+168=2016 ≤ 2052.
        "sh_bases": [0, 168, 336, 504, 672, 840, 1008, 1176, 1344, 1512, 1680, 1848],
    },
}


CSV_HEADER = [
    "route", "label", "voyage_idx", "sh_base", "eta_h",
    "sr_fuel_mt", "luo_fuel_mt", "gap_mt", "gap_pct",
    "sr_voyage_time_h", "luo_voyage_time_h",
    "sr_slack_h", "luo_slack_h",
    "sr_n_nodes", "sr_n_edges", "sr_build_s", "sr_solve_s",
    "luo_n_blocks", "luo_solve_s",
]


def _resolve(p: str) -> str:
    """Resolve a route-config path relative to this script's dir."""
    pp = Path(p)
    if pp.is_absolute():
        return str(pp)
    return str((_HERE / pp).resolve())


def _build_args(route_cfg: dict, sh_base: int) -> Namespace:
    """Construct the Namespace expected by SR_main.solve / luo_main.solve."""
    return Namespace(
        yaml=_resolve(route_cfg["yaml"]),
        h5=_resolve(route_cfg["h5"]),
        eta=float(route_cfg["eta"]),
        min_speed=None,
        max_speed=None,
        zeta_nm=None,
        tau_h=None,
        res_nm=1.0,
        sample_hour=sh_base,
        baseline=False,
        csv=False,
    )


def _print_hdr(s: str) -> None:
    bar = "=" * 80
    print(f"\n{bar}\n{s}\n{bar}", flush=True)


def run_chain(route_key: str, route_cfg: dict, out_dir: Path,
              skip_csv: bool, max_voyages: int = 0) -> List[dict]:
    """Run the consecutive-voyage chain for one route."""
    sh_bases = route_cfg["sh_bases"]
    if max_voyages and max_voyages > 0:
        sh_bases = sh_bases[:max_voyages]
    _print_hdr(f"CHAIN — {route_key} ({route_cfg['label']})  "
               f"ETA={route_cfg['eta']}  voyages={len(sh_bases)}"
               + (f" (truncated from {len(route_cfg['sh_bases'])})"
                  if max_voyages and max_voyages > 0 else ""))

    h5_path = Path(_resolve(route_cfg["h5"]))
    voyage = VoyageWeather(h5_path)
    print(f"Loaded {h5_path.name}: sh range "
          f"[{voyage.sample_hours[0]}..{voyage.sample_hours[-1]}], "
          f"{len(voyage.sample_hours)} unique sample_hours", flush=True)

    rows: List[dict] = []
    for voyage_idx, sh_base in enumerate(sh_bases):
        _print_hdr(f"{route_key}  voyage {voyage_idx:02d}/{len(route_cfg['sh_bases'])-1}  "
                   f"sh_base={sh_base}")
        args = _build_args(route_cfg, sh_base)

        t0 = time.time()
        sr_res = SR_main.solve(args, voyage=voyage, verbose=False)
        sr_total = time.time() - t0
        print(f"  SR   : fuel={sr_res['total_fuel_mt']:8.3f} mt  "
              f"t={sr_res['voyage_time_h']:7.3f} h  "
              f"({sr_total:5.1f}s wall)", flush=True)

        t0 = time.time()
        luo_res = luo_main.solve(args, voyage=voyage, verbose=False)
        luo_total = time.time() - t0
        print(f"  Luo  : fuel={luo_res['total_fuel_mt']:8.3f} mt  "
              f"t={luo_res['voyage_time_h']:7.3f} h  "
              f"({luo_total:5.1f}s wall)", flush=True)

        gap = sr_res["total_fuel_mt"] - luo_res["total_fuel_mt"]
        gap_pct = (gap / luo_res["total_fuel_mt"] * 100.0
                   if luo_res["total_fuel_mt"] else float("nan"))
        print(f"  gap  : {gap:+.3f} mt ({gap_pct:+.2f} %)", flush=True)

        # Per-voyage arc CSVs
        if not skip_csv:
            voyage_dir = out_dir / route_key / f"voyage_{voyage_idx:02d}"
            voyage_dir.mkdir(parents=True, exist_ok=True)
            write_arc_csv(voyage_dir / "sr.csv", sr_res["schedule"],
                          sr_res["waypoints"])
            write_luo_csv(voyage_dir / "luo.csv", luo_res["path_arcs"],
                          luo_res["waypoints"])

        rows.append({
            "route": route_key,
            "label": route_cfg["label"],
            "voyage_idx": voyage_idx,
            "sh_base": sh_base,
            "eta_h": route_cfg["eta"],
            "sr_fuel_mt": sr_res["total_fuel_mt"],
            "luo_fuel_mt": luo_res["total_fuel_mt"],
            "gap_mt": gap,
            "gap_pct": gap_pct,
            "sr_voyage_time_h": sr_res["voyage_time_h"],
            "luo_voyage_time_h": luo_res["voyage_time_h"],
            "sr_slack_h": route_cfg["eta"] - sr_res["voyage_time_h"],
            "luo_slack_h": route_cfg["eta"] - luo_res["voyage_time_h"],
            "sr_n_nodes": sr_res["n_nodes"],
            "sr_n_edges": sr_res["n_edges"],
            "sr_build_s": sr_res["build_s"],
            "sr_solve_s": sr_res["solve_s"],
            "luo_n_blocks": luo_res["n_blocks"],
            "luo_solve_s": luo_res["solve_s"],
        })

    return rows


def parse_args() -> Namespace:
    ap = argparse.ArgumentParser(prog="run_chain_sweep")
    ap.add_argument("--routes", default="route1,route2",
                    help="Comma-separated subset of routes to run "
                         "(choices: route1, route2). Default: both.")
    ap.add_argument("--out_dir", default="runs/2026_06_01_chain_sweep",
                    help="Output directory (default: runs/2026_06_01_chain_sweep)")
    ap.add_argument("--skip_csv", action="store_true",
                    help="Skip per-voyage per-arc CSV writes (only write results.csv)")
    ap.add_argument("--max_voyages", type=int, default=0,
                    help="Truncate each route's chain to first N voyages (0 = all). "
                         "Useful for validation runs.")
    return ap.parse_args()


def main() -> int:
    args = parse_args()
    chosen = [r.strip() for r in args.routes.split(",") if r.strip()]
    unknown = [r for r in chosen if r not in ROUTES]
    if unknown:
        print(f"Unknown routes: {unknown}. Available: {list(ROUTES)}",
              file=sys.stderr)
        return 1

    project_root = _HERE.parent.parent  # …/university
    out_dir = Path(args.out_dir)
    if not out_dir.is_absolute():
        out_dir = project_root / out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"Output dir: {out_dir}", flush=True)

    all_rows: List[dict] = []
    t_start = time.time()
    for route_key in chosen:
        rows = run_chain(route_key, ROUTES[route_key], out_dir, args.skip_csv,
                         max_voyages=args.max_voyages)
        all_rows.extend(rows)

    # Write summary CSV
    results_csv = out_dir / "results.csv"
    with open(results_csv, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_HEADER)
        writer.writeheader()
        for row in all_rows:
            writer.writerow(row)
    print(f"\nWrote {len(all_rows)} rows to {results_csv}")
    print(f"Total wall time: {(time.time() - t_start)/60.0:.1f} min")
    return 0


if __name__ == "__main__":
    sys.exit(main())

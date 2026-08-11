#!/usr/bin/env python3
"""
Mode-C departure-time chain sweep — C++ orchestrator.

C++ counterpart of ../dp_rebuild/run_chain_sweep.py: same voyage-chain logic
(voyage N+1 starts when voyage N's fixed ETA would have it arrive) and the
same results.csv schema (analyze_chain_sweep.py reads either file
unchanged), but drives the compiled dp_SR / dp_luo binaries via subprocess
instead of calling into the Python solve() functions. Parity-checked against
the Python path at sh_base=6 on route1 (2026-08-11, see
../../00_design/G7_v2_evidence_refresh.md): fuel within ~0.03%, ~9-12x
faster wall-clock per voyage.

For each voyage, shells out to:
  dp_SR   --sample_hour SH             -> SR fuel
  dp_luo  --sample_hour SH             -> Luo fuel
  dp_luo  --sample_hour SH --baseline  -> Baseline (Naive constant-speed) fuel

sh_bases (voyage start hours) are generated dynamically from the HDF5's
sample_hour range (read directly via h5py -- no Python solver stack import
needed here), mirroring dp_rebuild's ``_generate_sh_bases``.

Output is written incrementally (one flush per voyage, not batched to the
end) -- see run_chain_sweep.py's docstring for why that matters on a
multi-hour-scale sweep. Note: unlike the Python path, this script does NOT
write per-voyage per-arc CSVs (no --csv flag passed to the binaries) --
only the aggregate results.csv. Add --csv per call later if per-arc detail
is needed for figures.

Usage::

    python3 run_chain_sweep_cpp.py
        [--routes route1,route2]
        [--out_dir PATH]              default: results/2026_08_11_chain_sweep_v2_cpp
        [--max_voyages N]             truncate each route's chain (0 = all)
"""
from __future__ import annotations

import argparse
import csv
import re
import subprocess
import sys
import time
from pathlib import Path

import h5py

_HERE = Path(__file__).resolve().parent  # paper_workspace/scripts/dp_cpp
BIN = _HERE / "build"
PAPER_WORKSPACE = _HERE.parent.parent
ROUTES_DIR = PAPER_WORKSPACE / "config" / "routes"
DATA = PAPER_WORKSPACE / "data"

ROUTES = {
    "route1": {
        "label": "Malacca",
        "yaml": ROUTES_DIR / "persian_gulf_malacca_paper.yaml",
        "h5":   DATA / "experiment_b_138wp_v2_aug.h5",
        "eta":  280,
    },
    "route2": {
        "label": "Atlantic",
        "yaml": ROUTES_DIR / "st_johns_liverpool.yaml",
        "h5":   DATA / "experiment_d_391wp_v2_aug.h5",
        "eta":  168,
    },
}

# Same header as dp_rebuild/run_chain_sweep.py -- keep in sync.
CSV_HEADER = [
    "route", "label", "voyage_idx", "sh_base", "eta_h",
    "sr_fuel_mt", "luo_fuel_mt", "baseline_fuel_mt",
    "gap_mt", "gap_pct",
    "gap_sr_baseline_mt", "gap_sr_baseline_pct",
    "gap_luo_baseline_mt", "gap_luo_baseline_pct",
    "sr_voyage_time_h", "luo_voyage_time_h",
    "sr_slack_h", "luo_slack_h",
    "sr_n_nodes", "sr_n_edges", "sr_build_s", "sr_solve_s",
    "luo_n_blocks", "luo_solve_s",
]

_FUEL_RE = re.compile(r"Total fuel:\s*([0-9.]+)\s*mt")
_TIME_RE = re.compile(r"Voyage time:\s*([0-9.]+)\s*h")
_NODES_RE = re.compile(r"Graph:\s*(\d+)\s*nodes,\s*(\d+)\s*atomic edges")
_BUILD_RE = re.compile(r"Build:\s*([0-9.]+)\s*s\s*Solve:\s*([0-9.]+)\s*s")
_BLOCKS_RE = re.compile(r"Voyage time:\s*[0-9.]+\s*h\s*\((\d+)\s*blocks\)")
_LUO_SOLVE_RE = re.compile(r"Solve time:\s*([0-9.]+)\s*s")


def _generate_sh_bases(h5_path: Path, eta: float) -> list[int]:
    """Same rule as dp_rebuild's _generate_sh_bases: sh_list[0], +eta, +eta,
    ..., stopping once a voyage's arrival would run past the last available
    sample_hour."""
    with h5py.File(h5_path, "r") as h:
        sh_col = h["actual_weather"]["sample_hour"][:]
    sh_list = sorted(set(int(x) for x in sh_col))
    if not sh_list:
        return []
    max_sh = sh_list[-1]
    bases = []
    sh = sh_list[0]
    while sh + eta <= max_sh:
        bases.append(sh)
        sh += eta
    return bases


def _run(binary: str, route: dict, sh_base: int, extra: list[str] = ()) -> tuple[str, float]:
    """Run a dp_cpp binary, return (stdout, wall_seconds). Raises on non-zero exit."""
    cmd = [str(BIN / binary),
           "--yaml", str(route["yaml"]), "--h5", str(route["h5"]),
           "--eta", str(route["eta"]), "--sample_hour", str(sh_base)] + list(extra)
    t0 = time.time()
    out = subprocess.run(cmd, capture_output=True, text=True)
    wall = time.time() - t0
    if out.returncode != 0:
        raise RuntimeError(f"{binary} sh={sh_base} failed (exit {out.returncode}):\n"
                           f"stdout: {out.stdout[-1000:]}\nstderr: {out.stderr[-1000:]}")
    return out.stdout, wall


def _parse_sr(stdout: str) -> dict:
    fuel, vtime = _FUEL_RE.search(stdout), _TIME_RE.search(stdout)
    nodes, build = _NODES_RE.search(stdout), _BUILD_RE.search(stdout)
    if not (fuel and vtime and nodes and build):
        raise RuntimeError(f"could not parse dp_SR output:\n{stdout[-1000:]}")
    return {
        "total_fuel_mt": float(fuel.group(1)),
        "voyage_time_h": float(vtime.group(1)),
        "n_nodes": int(nodes.group(1)),
        "n_edges": int(nodes.group(2)),
        "build_s": float(build.group(1)),
        "solve_s": float(build.group(2)),
    }


def _parse_luo(stdout: str) -> dict:
    fuel, vtime = _FUEL_RE.search(stdout), _TIME_RE.search(stdout)
    blocks, solve = _BLOCKS_RE.search(stdout), _LUO_SOLVE_RE.search(stdout)
    if not (fuel and vtime and solve):
        raise RuntimeError(f"could not parse dp_luo output:\n{stdout[-1000:]}")
    return {
        "total_fuel_mt": float(fuel.group(1)),
        "voyage_time_h": float(vtime.group(1)),
        "n_blocks": int(blocks.group(1)) if blocks else None,
        "solve_s": float(solve.group(1)),
    }


def _parse_baseline(stdout: str) -> dict:
    fuel = _FUEL_RE.search(stdout)
    if not fuel:
        raise RuntimeError(f"could not parse dp_luo --baseline output:\n{stdout[-1000:]}")
    return {"total_fuel_mt": float(fuel.group(1))}


def run_chain(route_key: str, route: dict, csv_writer: csv.DictWriter, csv_file,
              max_voyages: int = 0) -> int:
    """Run the consecutive-voyage chain for one route via the C++ binaries.

    Writes and flushes each voyage's row immediately -- see module docstring.
    Returns the number of voyages run.
    """
    sh_bases_full = _generate_sh_bases(route["h5"], route["eta"])
    sh_bases = sh_bases_full[:max_voyages] if max_voyages and max_voyages > 0 else sh_bases_full
    bar = "=" * 80
    print(f"\n{bar}\nCHAIN (C++) — {route_key} ({route['label']})  "
          f"ETA={route['eta']}  voyages={len(sh_bases)}"
          + (f" (truncated from {len(sh_bases_full)})"
             if max_voyages and max_voyages > 0 else "")
          + f"\n{bar}", flush=True)

    n_written = 0
    for voyage_idx, sh_base in enumerate(sh_bases):
        print(f"\n{route_key}  voyage {voyage_idx:02d}/{len(sh_bases)-1}  sh_base={sh_base}",
              flush=True)

        out, wall = _run("dp_SR", route, sh_base)
        sr = _parse_sr(out)
        print(f"  SR       : fuel={sr['total_fuel_mt']:8.3f} mt  "
              f"t={sr['voyage_time_h']:7.3f} h  ({wall:5.1f}s wall)", flush=True)

        out, wall = _run("dp_luo", route, sh_base)
        luo = _parse_luo(out)
        print(f"  Luo      : fuel={luo['total_fuel_mt']:8.3f} mt  "
              f"t={luo['voyage_time_h']:7.3f} h  ({wall:5.1f}s wall)", flush=True)

        out, wall = _run("dp_luo", route, sh_base, extra=["--baseline"])
        base = _parse_baseline(out)
        print(f"  Baseline : fuel={base['total_fuel_mt']:8.3f} mt  ({wall:5.1f}s wall)",
              flush=True)

        gap = sr["total_fuel_mt"] - luo["total_fuel_mt"]
        gap_pct = gap / luo["total_fuel_mt"] * 100.0 if luo["total_fuel_mt"] else float("nan")
        gap_sr_base = sr["total_fuel_mt"] - base["total_fuel_mt"]
        gap_sr_base_pct = (gap_sr_base / base["total_fuel_mt"] * 100.0
                           if base["total_fuel_mt"] else float("nan"))
        gap_luo_base = luo["total_fuel_mt"] - base["total_fuel_mt"]
        gap_luo_base_pct = (gap_luo_base / base["total_fuel_mt"] * 100.0
                            if base["total_fuel_mt"] else float("nan"))
        print(f"  gap SR-Luo: {gap:+.3f} mt ({gap_pct:+.2f} %)   "
              f"SR-Base: {gap_sr_base:+.3f} mt ({gap_sr_base_pct:+.2f} %)   "
              f"Luo-Base: {gap_luo_base:+.3f} mt ({gap_luo_base_pct:+.2f} %)", flush=True)

        row = {
            "route": route_key, "label": route["label"], "voyage_idx": voyage_idx,
            "sh_base": sh_base, "eta_h": route["eta"],
            "sr_fuel_mt": sr["total_fuel_mt"], "luo_fuel_mt": luo["total_fuel_mt"],
            "baseline_fuel_mt": base["total_fuel_mt"],
            "gap_mt": gap, "gap_pct": gap_pct,
            "gap_sr_baseline_mt": gap_sr_base, "gap_sr_baseline_pct": gap_sr_base_pct,
            "gap_luo_baseline_mt": gap_luo_base, "gap_luo_baseline_pct": gap_luo_base_pct,
            "sr_voyage_time_h": sr["voyage_time_h"], "luo_voyage_time_h": luo["voyage_time_h"],
            "sr_slack_h": route["eta"] - sr["voyage_time_h"],
            "luo_slack_h": route["eta"] - luo["voyage_time_h"],
            "sr_n_nodes": sr["n_nodes"], "sr_n_edges": sr["n_edges"],
            "sr_build_s": sr["build_s"], "sr_solve_s": sr["solve_s"],
            "luo_n_blocks": luo["n_blocks"], "luo_solve_s": luo["solve_s"],
        }
        csv_writer.writerow(row)
        csv_file.flush()
        n_written += 1

    return n_written


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(prog="run_chain_sweep_cpp")
    ap.add_argument("--routes", default="route1,route2",
                    help="Comma-separated subset of routes to run "
                         "(choices: route1, route2). Default: both.")
    ap.add_argument("--out_dir", default="results/2026_08_11_chain_sweep_v2_cpp",
                    help="Output directory (default: results/2026_08_11_chain_sweep_v2_cpp)")
    ap.add_argument("--max_voyages", type=int, default=0,
                    help="Truncate each route's chain to first N voyages (0 = all).")
    return ap.parse_args()


def main() -> int:
    args = parse_args()
    chosen = [r.strip() for r in args.routes.split(",") if r.strip()]
    unknown = [r for r in chosen if r not in ROUTES]
    if unknown:
        print(f"Unknown routes: {unknown}. Available: {list(ROUTES)}", file=sys.stderr)
        return 1

    for b in ("dp_SR", "dp_luo"):
        if not (BIN / b).exists():
            print(f"missing {BIN / b} -- build first:\n"
                  f"  cd {_HERE} && cmake -B build -DCMAKE_BUILD_TYPE=Release "
                  f"&& cmake --build build -j", file=sys.stderr)
            return 1

    out_dir = Path(args.out_dir)
    if not out_dir.is_absolute():
        out_dir = PAPER_WORKSPACE / out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"Output dir: {out_dir}", flush=True)

    results_csv = out_dir / "results.csv"
    total_written = 0
    t_start = time.time()
    with open(results_csv, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_HEADER)
        writer.writeheader()
        f.flush()
        for route_key in chosen:
            total_written += run_chain(route_key, ROUTES[route_key], writer, f,
                                       max_voyages=args.max_voyages)

    print(f"\nWrote {total_written} rows to {results_csv}")
    print(f"Total wall time: {(time.time() - t_start)/60.0:.1f} min")
    return 0


if __name__ == "__main__":
    sys.exit(main())

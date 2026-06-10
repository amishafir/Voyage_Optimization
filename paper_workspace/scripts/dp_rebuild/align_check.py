#!/usr/bin/env python3
"""
Python <-> C++ alignment check (Mode C, no RH).

For each config, runs SR / Luo / Naive Mode C in BOTH implementations and
tabulates the per-solver delta:
  - Python: pipeline/dp_rebuild  (imports solve(), reuses one VoyageWeather)
  - C++:    pipeline/dp_cpp/build (dp_SR / dp_luo binaries)

Same route YAMLs + HDF5 files feed both, so any delta is a true cross-language
discrepancy (known ~0.1% drift as of 2026-06; this quantifies it across configs).

Run from pipeline/dp_rebuild/:  python3 align_check.py
"""
from __future__ import annotations

import re
import subprocess
import sys
from argparse import Namespace
from pathlib import Path

HERE = Path(__file__).resolve().parent          # dp_rebuild
PIPE = HERE.parent
CPP_BIN = PIPE / "dp_cpp" / "build"
ROUTES = PIPE / "config" / "routes"
DATA = PIPE / "data"

sys.path.insert(0, str(HERE))
import SR_main          # noqa: E402
import luo_main         # noqa: E402
from weather import VoyageWeather  # noqa: E402

# (label, yaml, h5, eta, [sh_bases])  — kept small for a fast pass.
CONFIGS = [
    ("route2", ROUTES / "st_johns_liverpool.yaml", DATA / "experiment_d_391wp.h5",
     168, [0, 1008]),
    ("route1", ROUTES / "persian_gulf_malacca_paper.yaml", DATA / "experiment_b_138wp.h5",
     280, [6]),
]
_FUEL = re.compile(r"Total fuel:\s*([0-9.]+)")


def cpp_fuel(binary: str, yaml: Path, h5: Path, eta: int, sh: int, extra: list[str]) -> float:
    cmd = [str(CPP_BIN / binary), "--yaml", str(yaml), "--h5", str(h5),
           "--eta", str(eta), "--sample_hour", str(sh)] + extra
    out = subprocess.run(cmd, capture_output=True, text=True)
    vals = _FUEL.findall(out.stdout)
    if not vals:
        raise RuntimeError(f"{binary} sh={sh}: no fuel parsed\n{out.stdout[-400:]}\n{out.stderr[-400:]}")
    return float(vals[-1])


def py_args(yaml: Path, h5: Path, eta: int, sh: int, baseline: bool = False) -> Namespace:
    return Namespace(yaml=str(yaml), h5=str(h5), eta=float(eta), min_speed=None,
                     max_speed=None, zeta_nm=None, tau_h=None, res_nm=1.0,
                     sample_hour=sh, baseline=baseline, csv=False)


def main() -> int:
    rows = []
    for label, yaml, h5, eta, shs in CONFIGS:
        voyage = VoyageWeather(h5)   # one load per route; warms the Python cell cache
        for sh in shs:
            print(f"\n--- {label} sh={sh} (eta={eta}) ---", flush=True)
            py_sr = SR_main.solve(py_args(yaml, h5, eta, sh), voyage=voyage,
                                  verbose=False)["total_fuel_mt"]
            py_luo = luo_main.solve(py_args(yaml, h5, eta, sh), voyage=voyage,
                                    verbose=False)["total_fuel_mt"]
            py_naive = luo_main.solve(py_args(yaml, h5, eta, sh, baseline=True), voyage=voyage,
                                      verbose=False)["total_fuel_mt"]
            cpp_sr = cpp_fuel("dp_SR", yaml, h5, eta, sh, [])
            cpp_luo = cpp_fuel("dp_luo", yaml, h5, eta, sh, ["--res_nm", "1.0"])
            cpp_naive = cpp_fuel("dp_luo", yaml, h5, eta, sh, ["--res_nm", "1.0", "--baseline"])
            for solver, py, cpp in [("SR", py_sr, cpp_sr), ("Luo", py_luo, cpp_luo),
                                    ("Naive", py_naive, cpp_naive)]:
                d = cpp - py
                dpct = d / py * 100.0 if py else float("nan")
                rows.append((label, sh, solver, py, cpp, d, dpct))
                print(f"  {solver:5}: py={py:9.3f}  cpp={cpp:9.3f}  "
                      f"Δ={d:+7.3f}  ({dpct:+.3f}%)", flush=True)

    print("\n" + "=" * 72)
    print(f"{'route':7} {'sh':>5} {'solver':6} {'Python':>10} {'C++':>10} "
          f"{'Δ (mt)':>9} {'Δ %':>8}")
    print("-" * 72)
    worst = 0.0
    for label, sh, solver, py, cpp, d, dpct in rows:
        print(f"{label:7} {sh:>5} {solver:6} {py:>10.3f} {cpp:>10.3f} {d:>+9.3f} {dpct:>+8.3f}")
        worst = max(worst, abs(dpct))
    print("-" * 72)
    print(f"max |Δ%| = {worst:.3f}%   ({len(rows)} comparisons)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

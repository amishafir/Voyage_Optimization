#!/usr/bin/env python3
"""
Rolling-horizon chain sweep (C++ orchestrator driver).

Runs the RH experiment across the standard departure sample_hours for both
routes (same sh_bases as run_chain_sweep.py / dp_rebuild). Per voyage it:
  1. computes the Mode C oracle (dp_SR / dp_luo, no RH) at that sh_base;
  2. runs dp_run_rh (Naive + RH-SR + RH-Luo) with that oracle for the gates;
  3. records oracle / naive / RH / gaps / gates into results.csv.

This is the §4.8 chain table the supervisor meeting wants: per voyage
oracle ≤ RH ≤ Naive, and RH-vs-Naive %.

Usage (from pipeline/dp_cpp/):
    python3 run_rh_chain.py [--routes route1,route2] [--max_voyages N]
                            [--skip_oracle] [--out_dir DIR]
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
BIN = HERE / "build"
ROOT = HERE.parent.parent                       # repo root
ROUTES_DIR = HERE.parent / "config" / "routes"
DATA = HERE.parent / "data"

ROUTES = {
    "route2": {
        "yaml": ROUTES_DIR / "st_johns_liverpool.yaml",
        "h5":   DATA / "experiment_d_391wp.h5",
        "eta":  168,
        "sh_bases": [0, 168, 336, 504, 672, 840, 1008, 1176, 1344, 1512, 1680, 1848],
    },
    "route1": {
        "yaml": ROUTES_DIR / "persian_gulf_malacca_paper.yaml",
        "h5":   DATA / "experiment_b_138wp.h5",
        "eta":  280,
        "sh_bases": [6, 286, 566, 846, 1126, 1406, 1686],
    },
}

_FUEL_RE = re.compile(r"Total fuel:\s*([0-9.]+)")


def mode_c_fuel(binary: str, route: dict, sh_base: int, extra: list[str]) -> float:
    """Run a Mode C solve (no RH) and parse 'Total fuel: X mt' from stdout."""
    cmd = [str(BIN / binary), "--yaml", str(route["yaml"]), "--h5", str(route["h5"]),
           "--eta", str(route["eta"]), "--sample_hour", str(sh_base)] + extra
    out = subprocess.run(cmd, capture_output=True, text=True)
    m = None
    for line in out.stdout.splitlines():
        mm = _FUEL_RE.search(line)
        if mm:
            m = float(mm.group(1))   # last match = final total
    if m is None:
        raise RuntimeError(f"no fuel parsed from {binary} sh={sh_base}:\n{out.stdout[-500:]}\n{out.stderr[-500:]}")
    return m


def _row(route_key: str, voyage_idx: int, sh_base: int, route: dict,
         s: dict, rh_min: float) -> dict:
    res, g = s["results"], s["gates"]
    orc = s.get("oracle_ref", {})
    return {
        "route": route_key, "voyage_idx": voyage_idx, "sh_base": sh_base,
        "eta_h": route["eta"], "L_nm": round(s["L_nm"], 2),
        "oracle_sr": round(orc.get("sr", float("nan")), 3),
        "oracle_luo": round(orc.get("luo", float("nan")), 3),
        "naive_mt": s["naive_mt"],
        "rh_sr_mt": res["sr"]["realised_mt"], "rh_luo_mt": res["luo"]["realised_mt"],
        "rh_sr_vs_naive_pct": res["sr"]["vs_naive_pct"],
        "rh_luo_vs_naive_pct": res["luo"]["vs_naive_pct"],
        "rh_sr_vs_oracle_mt": res["sr"]["vs_oracle_mt"],
        "rh_luo_vs_oracle_mt": res["luo"]["vs_oracle_mt"],
        "sr_gates_ok": all(g["sr"].values()), "luo_gates_ok": all(g["luo"].values()),
        "arrival_h": s["arrival_h"], "rh_runtime_min": round(rh_min, 1),
    }


def run_voyage(route_key: str, route: dict, voyage_idx: int, sh_base: int,
               out_dir: Path, skip_oracle: bool) -> dict:
    print(f"\n=== {route_key} voyage {voyage_idx:02d}  sh_base={sh_base} ===", flush=True)
    v_dir = out_dir / route_key / f"voyage_{voyage_idx:02d}"
    summ = v_dir / "summary.json"

    # Resume: skip voyages already completed (cheap re-runs after a crash).
    if summ.exists():
        s = json.loads(summ.read_text())
        row = _row(route_key, voyage_idx, sh_base, route, s, float("nan"))
        print(f"  (resume) Naive {row['naive_mt']:.3f} | RH-SR {row['rh_sr_mt']:.3f} "
              f"({row['rh_sr_vs_naive_pct']:+.2f}%) | RH-Luo {row['rh_luo_mt']:.3f} "
              f"({row['rh_luo_vs_naive_pct']:+.2f}%)", flush=True)
        return row

    oracle_sr = oracle_luo = float("nan")
    if not skip_oracle:
        t0 = time.time()
        oracle_sr = mode_c_fuel("dp_SR", route, sh_base, [])
        oracle_luo = mode_c_fuel("dp_luo", route, sh_base, ["--res_nm", "1.0"])
        print(f"  oracle: SR={oracle_sr:.3f}  Luo={oracle_luo:.3f}  ({time.time()-t0:.0f}s)", flush=True)

    cmd = [str(BIN / "dp_run_rh"),
           "--yaml", str(route["yaml"]), "--h5", str(route["h5"]),
           "--eta", str(route["eta"]), "--sh_base", str(sh_base),
           "--label", route_key, "--out_dir", str(v_dir)]
    if not skip_oracle:
        cmd += ["--oracle_sr", str(oracle_sr), "--oracle_luo", str(oracle_luo)]
    t0 = time.time()
    subprocess.run(cmd, check=True)
    rh_min = (time.time() - t0) / 60.0

    s = json.loads((v_dir / "summary.json").read_text())
    res, g = s["results"], s["gates"]
    row = {
        "route": route_key, "voyage_idx": voyage_idx, "sh_base": sh_base,
        "eta_h": route["eta"], "L_nm": round(s["L_nm"], 2),
        "oracle_sr": round(oracle_sr, 3), "oracle_luo": round(oracle_luo, 3),
        "naive_mt": s["naive_mt"],
        "rh_sr_mt": res["sr"]["realised_mt"], "rh_luo_mt": res["luo"]["realised_mt"],
        "rh_sr_vs_naive_pct": res["sr"]["vs_naive_pct"],
        "rh_luo_vs_naive_pct": res["luo"]["vs_naive_pct"],
        "rh_sr_vs_oracle_mt": res["sr"]["vs_oracle_mt"],
        "rh_luo_vs_oracle_mt": res["luo"]["vs_oracle_mt"],
        "sr_gates_ok": all(g["sr"].values()), "luo_gates_ok": all(g["luo"].values()),
        "arrival_h": s["arrival_h"], "rh_runtime_min": round(rh_min, 1),
    }
    print(f"  Naive {row['naive_mt']:.3f} | RH-SR {row['rh_sr_mt']:.3f} "
          f"({row['rh_sr_vs_naive_pct']:+.2f}%) | RH-Luo {row['rh_luo_mt']:.3f} "
          f"({row['rh_luo_vs_naive_pct']:+.2f}%) | gates SR={row['sr_gates_ok']} "
          f"Luo={row['luo_gates_ok']} | {rh_min:.1f}min", flush=True)
    return row


def main() -> int:
    ap = argparse.ArgumentParser(prog="run_rh_chain")
    ap.add_argument("--routes", default="route2,route1")
    ap.add_argument("--max_voyages", type=int, default=0, help="first N voyages per route (0=all)")
    ap.add_argument("--skip_oracle", action="store_true")
    ap.add_argument("--out_dir", default=str(ROOT / "runs" / "2026_06_15_rh_cpp_chain"))
    args = ap.parse_args()

    chosen = [r.strip() for r in args.routes.split(",") if r.strip()]
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"Output: {out_dir}", flush=True)

    rows: list[dict] = []
    t_start = time.time()
    for route_key in chosen:
        route = ROUTES[route_key]
        shbs = route["sh_bases"]
        if args.max_voyages > 0:
            shbs = shbs[:args.max_voyages]
        for vi, sh in enumerate(shbs):
            try:
                rows.append(run_voyage(route_key, route, vi, sh, out_dir, args.skip_oracle))
            except Exception as e:
                print(f"  !! {route_key} voyage {vi:02d} sh={sh} FAILED: {e}", flush=True)
                rows.append({
                    "route": route_key, "voyage_idx": vi, "sh_base": sh,
                    "eta_h": route["eta"], "L_nm": float("nan"),
                    "oracle_sr": float("nan"), "oracle_luo": float("nan"),
                    "naive_mt": float("nan"), "rh_sr_mt": float("nan"),
                    "rh_luo_mt": float("nan"), "rh_sr_vs_naive_pct": float("nan"),
                    "rh_luo_vs_naive_pct": float("nan"), "rh_sr_vs_oracle_mt": float("nan"),
                    "rh_luo_vs_oracle_mt": float("nan"), "sr_gates_ok": False,
                    "luo_gates_ok": False, "arrival_h": float("nan"),
                    "rh_runtime_min": float("nan")})

    results_csv = out_dir / "results.csv"
    with open(results_csv, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    print(f"\n{'='*64}\nCHAIN SWEEP DONE — {len(rows)} voyages, "
          f"{(time.time()-t_start)/60:.1f} min total\n{'='*64}")
    print(f"{'route':7} {'sh':>5} {'naive':>9} {'RH-SR':>9} {'RH-Luo':>9} "
          f"{'SR%':>7} {'Luo%':>7} {'gates':>6}")
    for r in rows:
        print(f"{r['route']:7} {r['sh_base']:>5} {r['naive_mt']:>9.3f} "
              f"{r['rh_sr_mt']:>9.3f} {r['rh_luo_mt']:>9.3f} "
              f"{r['rh_sr_vs_naive_pct']:>+7.2f} {r['rh_luo_vs_naive_pct']:>+7.2f} "
              f"{'OK' if r['sr_gates_ok'] and r['luo_gates_ok'] else 'FAIL':>6}")
    print(f"\nWrote {results_csv}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""
Perfect-foresight chain sweep (C++ driver).

The Mode C oracle half of `run_rh_chain.py`, without the rolling horizon: per
voyage it runs `dp_SR` and `dp_luo` at one departure sample_hour and records
fuel, voyage time and the gap. Mirrors `dp_rebuild/run_chain_sweep.py` but ~10x
faster, which is the difference between an overnight job and an hour.

Departures are COMPUTED from the h5's own extent rather than hardcoded: step by
the ETA, admit a departure while sh + eta <= max stored sample_hour. The
hardcoded lists elsewhere in the tree were sized for a snapshot ending at
sample_hour 2052 and give 19 voyages, which is where the paper's stale
"nineteen voyages" comes from.

Usage (from pipeline/dp_cpp/):
    python3 run_pf_chain.py --partition waypoint --out_dir ../../runs/pf_wp
"""
from __future__ import annotations

import argparse
import csv
import re
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
ROUTES_DIR = HERE.parent / "config" / "routes"
DATA = ROOT / "paper_workspace" / "data"

ROUTES = {
    "route1": {
        "label": "Malacca",
        "yaml": ROUTES_DIR / "persian_gulf_malacca_paper.yaml",
        "h5":   DATA / "experiment_b_138wp_v4_sep07.h5",
        "eta":  280,
        "sh_first": 6,
    },
    "route2": {
        "label": "Atlantic",
        "yaml": ROUTES_DIR / "st_johns_liverpool.yaml",
        "h5":   DATA / "experiment_d_391wp_v4_sep07.h5",
        "eta":  168,
        "sh_first": 0,
    },
}

CSV_HEADER = [
    "route", "label", "voyage_idx", "sh_base", "eta_h", "partition",
    "sr_fuel_mt", "luo_fuel_mt", "naive_fuel_mt", "gap_mt", "gap_pct",
    "sr_voyage_time_h", "luo_voyage_time_h",
    "sr_n_nodes", "sr_n_edges", "sr_wall_s", "luo_wall_s", "naive_wall_s",
]

# dp_SR prints both a rounded and a full-precision total; prefer the latter.
_SR_FULL = re.compile(r"Total fuel \(full\):\s*([0-9.]+)")
_FUEL = re.compile(r"Total fuel:\s*([0-9.]+)")
_TIME = re.compile(r"Voyage time:\s*([0-9.]+)")
_GRAPH = re.compile(r"Graph:\s*([0-9]+) nodes,\s*([0-9]+)")


def chain_sh_bases(h5: Path, eta: float, sh_first: int) -> list[int]:
    import h5py
    import numpy as np
    with h5py.File(h5, "r") as f:
        last = int(np.max(f["actual_weather"]["sample_hour"]))
    out, k = [], 0
    while sh_first + eta * k + eta <= last:
        out.append(int(sh_first + eta * k))
        k += 1
    return out


def run_one(binary: Path, route: dict, sh: int, partition: str,
            extra: list[str]) -> dict:
    cmd = [str(binary), "--yaml", str(route["yaml"]), "--h5", str(route["h5"]),
           "--eta", str(route["eta"]), "--sample_hour", str(sh),
           "--partition", partition] + extra
    t0 = time.time()
    p = subprocess.run(cmd, capture_output=True, text=True)
    wall = time.time() - t0
    if p.returncode != 0:
        raise RuntimeError(f"{binary.name} exited {p.returncode}\n"
                           f"{p.stderr[-800:]}")
    out = p.stdout
    full = _SR_FULL.search(out)
    fuel = float(full.group(1)) if full else None
    if fuel is None:
        m = _FUEL.search(out)
        if not m:
            raise RuntimeError(f"no fuel line from {binary.name}\n{out[-800:]}")
        fuel = float(m.group(1))
    t = _TIME.search(out)
    g = _GRAPH.search(out)
    return {"fuel": fuel,
            "time_h": float(t.group(1)) if t else float("nan"),
            "n_nodes": int(g.group(1)) if g else "",
            "n_edges": int(g.group(2)) if g else "",
            "wall_s": round(wall, 2)}


def main() -> int:
    ap = argparse.ArgumentParser(prog="run_pf_chain")
    ap.add_argument("--routes", default="route1,route2")
    ap.add_argument("--partition", choices=["geo", "waypoint"], default="geo")
    ap.add_argument("--max_voyages", type=int, default=0)
    ap.add_argument("--bin", default=str(HERE / "build"),
                    help="Directory holding dp_SR and dp_luo")
    ap.add_argument("--out_dir", default=str(ROOT / "runs" / "pf_chain"))
    ap.add_argument("--node_first", action="store_true")
    ap.add_argument("--naive_only", action="store_true",
                    help="Run only the Naive baseline (dp_luo --baseline). Reuses the "
                         "same computed departures, so rows line up with a prior sweep.")
    ap.add_argument("--with_naive", action="store_true",
                    help="Also run the Naive baseline alongside SR and Luo.")
    args = ap.parse_args()

    binroot = Path(args.bin)
    for b in ("dp_SR", "dp_luo"):
        if not (binroot / b).exists():
            print(f"missing binary: {binroot / b}", file=sys.stderr)
            return 1

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    rows: list[dict] = []
    t_start = time.time()

    for rk in [r.strip() for r in args.routes.split(",") if r.strip()]:
        route = ROUTES[rk]
        shs = chain_sh_bases(route["h5"], float(route["eta"]),
                             int(route["sh_first"]))
        if args.max_voyages:
            shs = shs[:args.max_voyages]
        print(f"\n=== {rk} ({route['label']})  ETA={route['eta']}  "
              f"partition={args.partition}  voyages={len(shs)} ===", flush=True)

        extra_sr = ["--node_first"] if args.node_first else []
        want_naive = args.naive_only or args.with_naive
        blank = {"fuel": "", "time_h": "", "n_nodes": "", "n_edges": "", "wall_s": ""}
        for i, sh in enumerate(shs):
            if args.naive_only:
                sr = luo = blank
            else:
                sr = run_one(binroot / "dp_SR", route, sh, args.partition, extra_sr)
                luo = run_one(binroot / "dp_luo", route, sh, args.partition, [])
            naive = (run_one(binroot / "dp_luo", route, sh, args.partition, ["--baseline"])
                     if want_naive else blank)

            if args.naive_only:
                gap_mt = gap_pct = ""
                print(f"  [{i:02d}] sh={sh:5d}  Naive {naive['fuel']:9.3f}  "
                      f"[{naive['wall_s']:.0f}s]", flush=True)
            else:
                gap_mt = luo["fuel"] - sr["fuel"]
                gap_pct = 100.0 * gap_mt / luo["fuel"] if luo["fuel"] else float("nan")
                nv = f"  Naive {naive['fuel']:9.3f}" if want_naive else ""
                print(f"  [{i:02d}] sh={sh:5d}  SR {sr['fuel']:9.3f}  "
                      f"Luo {luo['fuel']:9.3f}{nv}  gap {gap_mt:+7.3f} mt "
                      f"({gap_pct:+6.3f} %)  [{sr['wall_s']:.0f}+{luo['wall_s']:.0f}s]",
                      flush=True)
                gap_mt = round(gap_mt, 6); gap_pct = round(gap_pct, 6)
            rows.append({
                "route": rk, "label": route["label"], "voyage_idx": i,
                "sh_base": sh, "eta_h": route["eta"], "partition": args.partition,
                "sr_fuel_mt": sr["fuel"], "luo_fuel_mt": luo["fuel"],
                "naive_fuel_mt": naive["fuel"],
                "gap_mt": gap_mt, "gap_pct": gap_pct,
                "sr_voyage_time_h": sr["time_h"], "luo_voyage_time_h": luo["time_h"],
                "sr_n_nodes": sr["n_nodes"], "sr_n_edges": sr["n_edges"],
                "sr_wall_s": sr["wall_s"], "luo_wall_s": luo["wall_s"],
                "naive_wall_s": naive["wall_s"],
            })

    csv_path = out_dir / "results.csv"
    with open(csv_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=CSV_HEADER)
        w.writeheader()
        w.writerows(rows)
    print(f"\nWrote {len(rows)} rows to {csv_path}")
    print(f"Total wall time: {(time.time() - t_start) / 60:.1f} min")

    for rk in sorted({r["route"] for r in rows}):
        g = [r["gap_pct"] for r in rows if r["route"] == rk and r["gap_pct"] != ""]
        if g:
            print(f"  {rk}: mean gap {sum(g) / len(g):+.3f} %  n={len(g)}")
        n = [r["naive_fuel_mt"] for r in rows if r["route"] == rk and r["naive_fuel_mt"] != ""]
        if n:
            print(f"  {rk}: mean Naive {sum(n) / len(n):.3f} mt  n={len(n)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

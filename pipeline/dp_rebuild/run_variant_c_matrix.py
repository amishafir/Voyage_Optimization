"""
E-B experiment matrix for the waiting-arc prototype (docs/variant_c_design.md).

Four configs x two quick-set voyages:
  1. band current (mean+-3), wait off   -> must equal the golden (anchor)
  2. band [0, v_max],        wait off   -> wider slow side alone
  3. band [0, v_max],        wait free  -> variant (a)
  4. band [0, v_max],        wait hold  -> variant (c)

Captures fuel / time / counts + waiting diagnostics (wait legs, hours,
locations, hold prices). Output: runs/2026_08_08_variant_c_test/.

Run from pipeline/dp_rebuild/:  python3 run_variant_c_matrix.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

import run_chain_sweep as rcs
import SR_main
from weather import VoyageWeather

OUT = _HERE / "../../runs/2026_08_08_variant_c_test"
GOLDEN = {"route1": "353.95517201251994", "route2": "202.48415966493758"}
VOYAGES = [("route1", 6), ("route2", 0)]
CONFIGS = [
    ("band_cur_off",  None, "off"),
    ("band0_off",     0.0,  "off"),
    ("band0_free",    0.0,  "free"),
    ("band0_hold",    0.0,  "hold"),
]


def wait_stats(schedule):
    legs = [e for e in schedule if e.sog == 0.0]
    return {
        "wait_legs": len(legs),
        "wait_hours": round(sum(e.dst_t - e.src_t for e in legs), 3),
        "wait_fuel_mt": round(sum(e.fuel_mt for e in legs), 6),
        "wait_where": [
            {"d_nm": round(e.src_d, 1), "t_h": round(e.src_t, 1),
             "hours": round(e.dst_t - e.src_t, 2),
             "hold_sws_kn": round(e.sws, 3),
             "fuel_mt": round(e.fuel_mt, 5)}
            for e in legs
        ],
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    cache: dict = {}
    rows = []
    for route_key, sh in VOYAGES:
        cfg = rcs.ROUTES[route_key]
        h5 = rcs._resolve(cfg["h5"])
        if h5 not in cache:
            cache[h5] = VoyageWeather(Path(h5))
        for name, vmin, wait in CONFIGS:
            args = rcs._build_args(cfg, sh, node_first=True)
            if vmin is not None:
                args.min_speed = vmin
            setattr(args, "wait_arcs", wait)
            print(f"[matrix] {route_key} sh={sh} {name} ...", flush=True)
            res = SR_main.solve(args, voyage=cache[h5], verbose=False)
            row = {
                "route": route_key, "sh_base": sh, "config": name,
                "v_min": vmin, "wait_arcs": wait,
                "fuel_mt": repr(res["total_fuel_mt"]),
                "voyage_time_h": res["voyage_time_h"],
                "n_nodes": res["n_nodes"], "n_edges": res["n_edges"],
                "solve_s": round(res["solve_s"], 1),
                **wait_stats(res["schedule"]),
            }
            if name == "band_cur_off":
                row["golden_match"] = (row["fuel_mt"] == GOLDEN[route_key])
            rows.append(row)
            print(f"         fuel={row['fuel_mt']}  edges={row['n_edges']}  "
                  f"waits={row['wait_legs']} ({row['wait_hours']}h, "
                  f"{row['wait_fuel_mt']} mt)  solve={row['solve_s']}s", flush=True)

    (OUT / "matrix.json").write_text(json.dumps(rows, indent=2) + "\n")

    # summary table
    print("\n===== E-B SUMMARY =====")
    print(f"{'route':8} {'config':14} {'fuel_mt':>22} {'Δ vs band0_off':>15} "
          f"{'waits':>6} {'wait_h':>7}")
    for route_key, _ in VOYAGES:
        base = next(float(r["fuel_mt"]) for r in rows
                    if r["route"] == route_key and r["config"] == "band0_off")
        for r in rows:
            if r["route"] != route_key:
                continue
            f = float(r["fuel_mt"])
            print(f"{route_key:8} {r['config']:14} {f:>22.10f} "
                  f"{f - base:>+15.6f} {r['wait_legs']:>6} {r['wait_hours']:>7}")
    print(f"\nwritten: {OUT}/matrix.json")


if __name__ == "__main__":
    main()

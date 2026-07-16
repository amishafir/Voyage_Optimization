"""
Rolling-horizon orchestrator (meeting_prep_2026_06_15.md §4).

Simulates a captain who re-plans every 6 h. At each decision step k:

  * Look-ahead = remainder of the voyage from the current position (d_k) and a
    fresh sub-voyage clock (tau = 0 at the decision point).
  * Weather for the re-plan is MIXED:
      - first 6 h block (tau < 6)  -> ACTUAL weather at the decision wall-clock
        (nowcast — the captain can observe current conditions);
      - rest of the look-ahead     -> FORECAST from the most-recent forecast
        cycle (sh_fc <= T_wall), at lead = (T_wall - sh_fc) + 6*floor(tau/6),
        capped at that cycle's max available lead.
  * Solve SR and Luo independently on this sub-problem (absolute distances, so
    geo/weather lookups stay correct; only the time axis is re-anchored).
  * EXECUTE block 0 only — the planned block-0 SOG/fuel/distance. Because block
    0 used actual weather, realised fuel == planned block-0 fuel.
  * Advance d, repeat. SR and Luo each evolve their own d_executed.

Headline comparison: realised RH fuel vs a Naive fixed-mean-SOG baseline run
against actual weather. Reference upper bound (cost of imperfect forecast) is
the Mode C oracle from the June 1 chain sweep (Route 2 sh_base=0): SR 203.198 /
Luo 210.250 mt.

Usage (from pipeline/dp_rebuild/):
    python3 run_rh.py [--max_replans N] [--out_dir PATH] [--sh_base H] [--eta H]

--max_replans N truncates the re-plan loop (validation smoke before the full
28-step run). Default 0 = run the full voyage.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import sys
import time
from argparse import Namespace
from bisect import bisect_right
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

import h5py

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

import SR_main
import luo_main
from weather import VoyageWeather

# Route 2 config (mirrors run_chain_sweep.ROUTES["route2"]).
YAML = str((_HERE / "../config/routes/st_johns_liverpool.yaml").resolve())
H5 = str((_HERE / "../data/experiment_d_391wp.h5").resolve())
ETA_DEFAULT = 168.0
SH_BASE_DEFAULT = 0
DT_H = 6.0

# Mode C oracle reference (June 1 chain sweep, Route 2 voyage 0).
REF_ORACLE = {"sr": 203.198, "luo": 210.250}


# ----------------------------------------------------------------------
# Forecast-cycle index (from predicted_weather): issue times + max lead.
# ----------------------------------------------------------------------

def load_forecast_index(h5_path: str) -> Tuple[List[int], Dict[int, int]]:
    """Return (sorted predicted sample_hours, {sample_hour: max positive lead})."""
    with h5py.File(h5_path, "r") as f:
        d = f["predicted_weather"][()]
    sh = d["sample_hour"]
    fh = d["forecast_hour"]
    issues = sorted(set(int(x) for x in sh.tolist()))
    max_lead: Dict[int, int] = {}
    for s in issues:
        leads = fh[sh == s]
        pos = leads[leads >= 0]
        max_lead[s] = int(pos.max()) if pos.size else 0
    return issues, max_lead


def make_time_key(
    t_wall: int,
    issues: List[int],
    max_lead: Dict[int, int],
    dt_h: float = DT_H,
    actual_hours: Optional[List[int]] = None,
) -> Callable[[float], Tuple[int, Optional[int]]]:
    """Build the rolling-horizon weather selector for a decision at wall-clock
    time ``t_wall`` (= sh_base + 6k).

    tau < dt_h          -> (t_now, None)             actual nowcast
    tau >= dt_h         -> (sh_fc, lead)             most-recent forecast cycle
        t_now = latest actual sample_hour <= t_wall   (off-grid t_wall like 286
                snaps to the most recent stored sample, e.g. 282 at 6h cadence
                --- mirrors VoyageWeather.active_sample_hour, so RH block-0
                nowcast matches the Mode C oracle's actual-weather resolution)
        sh_fc = latest forecast issue <= t_wall
        lead  = (t_wall - sh_fc) + 6*floor(tau/dt_h), capped at max_lead[sh_fc]
    """
    # Most-recent forecast issue at or before the decision time.
    idx = bisect_right(issues, t_wall) - 1
    sh_fc = issues[max(0, idx)]
    staleness = t_wall - sh_fc
    cap = max_lead.get(sh_fc, 0)

    # Snap the nowcast wall-clock to the nearest available actual sample_hour
    # <= t_wall (actual_weather is stored on a 6h grid; off-grid decision times
    # would otherwise raise KeyError in weather_at).
    if actual_hours:
        j = bisect_right(actual_hours, t_wall) - 1
        t_now = actual_hours[max(0, j)]
    else:
        t_now = t_wall

    def time_key(tau: float) -> Tuple[int, Optional[int]]:
        if tau < dt_h:
            return (t_now, None)
        lead = staleness + int(dt_h * (tau // dt_h))
        if lead > cap:
            lead = cap
        return (sh_fc, lead)

    return time_key, sh_fc, staleness


# ----------------------------------------------------------------------
# Block-0 extraction from each solver's plan
# ----------------------------------------------------------------------

def sr_block_metrics(schedule, d_start: float, blk_lo: float, blk_hi: float
                     ) -> Tuple[float, float, float]:
    """(fuel, end_distance_nm, mean_sog_kn) for SR edges in [blk_lo, blk_hi)."""
    eps = 1e-6
    fuel = 0.0
    end_d = d_start
    start_d = None
    for e in schedule:
        if e.src_t >= blk_lo - eps and e.src_t < blk_hi - eps:
            if start_d is None:
                start_d = e.src_d
            fuel += e.fuel_mt
            end_d = e.dst_d
    if start_d is None:
        return 0.0, d_start, 0.0
    dur = blk_hi - blk_lo
    sog = (end_d - start_d) / dur if dur > 0 else 0.0
    return fuel, end_d, sog


def luo_block_metrics(path_arcs, blk_idx: int) -> Optional[Tuple[float, float, float]]:
    """(fuel, end_distance_nm, sog_kn) for Luo block `blk_idx`, or None if absent."""
    for arc, blk in path_arcs:
        if blk == blk_idx:
            if not arc.segs:
                return arc.fuel, 0.0, 0.0
            end_d = arc.segs[-1].dst_d
            sog = arc.segs[0].sog
            return arc.fuel, end_d, sog
    return None


# ----------------------------------------------------------------------
# Orchestration
# ----------------------------------------------------------------------

def base_args(eta: float, sh_base: int, node_first: bool = False,
              yaml: str = YAML, h5: str = H5) -> Namespace:
    return Namespace(
        yaml=yaml, h5=h5, eta=eta,
        min_speed=None, max_speed=None, zeta_nm=None, tau_h=None,
        res_nm=1.0, sample_hour=sh_base, baseline=False, csv=False,
        node_first=node_first,   # SR only; Luo/Naive ignore it
    )


def run_naive(voyage: VoyageWeather, eta: float, sh_base: int,
              yaml: str = YAML, h5: str = H5) -> dict:
    """Naive fixed-mean-SOG baseline against ACTUAL weather (Mode C)."""
    args = base_args(eta, sh_base, yaml=yaml, h5=h5)
    args.baseline = True
    res = luo_main.solve(args, voyage=voyage, verbose=False)
    return {"total_fuel_mt": res["total_fuel_mt"],
            "voyage_time_h": res["voyage_time_h"]}


def run_rh(voyage: VoyageWeather, issues, max_lead, eta: float, sh_base: int,
           max_replans: int = 0, node_first: bool = False,
           yaml: str = YAML, h5: str = H5, skip_luo: bool = False) -> dict:
    """Run the RH loop for SR and Luo. Returns totals + per-replan rows.

    ETA need not be a multiple of DT_H: the loop runs ceil(eta/DT_H) re-plans
    and the final block is the remainder (min(DT_H, eta_sub)). Decision cadence
    is a fixed DT_H, so both solvers execute the same per-block durations
    (distance covered differs) and share one arrival time = sum of durations.
    """
    n_blocks = math.ceil(eta / DT_H - 1e-9)
    if max_replans and max_replans > 0:
        n_blocks = min(n_blocks, max_replans)

    state = {
        "sr": {"d": 0.0, "fuel": 0.0, "prev_b1_sog": None},
        "luo": {"d": 0.0, "fuel": 0.0, "prev_b1_sog": None},
    }
    rows = {"sr": [], "luo": []}
    realized = {"sr": [], "luo": []}

    executed_h = 0.0
    for k in range(n_blocks):
        eta_sub = eta - DT_H * k
        # Executed block duration: full DT_H except a short final remainder.
        blk_dur = min(DT_H, eta_sub)
        b1_hi = min(2 * DT_H, eta_sub)  # block-1 upper bound (diagnostic)
        t_wall = sh_base + int(DT_H * k)
        tk, sh_fc, staleness = make_time_key(t_wall, issues, max_lead,
                                             actual_hours=voyage.sample_hours)
        args_k = base_args(eta_sub, sh_base, node_first=node_first,
                           yaml=yaml, h5=h5)

        print(f"\n[k={k:02d}] T_wall={t_wall:4d}  eta_sub={eta_sub:5.0f}h  "
              f"blk_dur={blk_dur:.0f}h  "
              f"forecast_cycle={sh_fc} (stale {staleness}h)  "
              f"d_sr={state['sr']['d']:.1f}  d_luo={state['luo']['d']:.1f}",
              flush=True)

        # ---- SR ----
        t0 = time.time()
        sr = SR_main.solve(args_k, voyage=voyage, verbose=False,
                           time_key=tk, d_start=state["sr"]["d"])
        sr_wall = time.time() - t0
        f0, end_d, sog0 = sr_block_metrics(sr["schedule"], state["sr"]["d"],
                                           0.0, blk_dur)
        _, _, b1_sog = sr_block_metrics(sr["schedule"], state["sr"]["d"],
                                        DT_H, b1_hi)
        div = (sog0 - state["sr"]["prev_b1_sog"]
               if state["sr"]["prev_b1_sog"] is not None else float("nan"))
        rows["sr"].append({
            "k": k, "t_wall": t_wall, "sub_eta": eta_sub,
            "forecast_cycle": sh_fc, "staleness_h": staleness,
            "d_start": round(state["sr"]["d"], 3),
            "planned_b0_sog": round(sog0, 4),
            "realised_b0_sog": round(sog0, 4),
            "prev_plan_b0_sog": (round(state["sr"]["prev_b1_sog"], 4)
                                 if state["sr"]["prev_b1_sog"] is not None else ""),
            "divergence_kn": (round(div, 4) if div == div else ""),
            "block0_fuel_mt": round(f0, 4),
            "sub_solve_s": round(sr["solve_s"], 2),
            "sub_wall_s": round(sr_wall, 1),
        })
        realized["sr"].append({
            "k": k, "t_h": DT_H * k, "d_start": round(state["sr"]["d"], 3),
            "d_end": round(end_d, 3), "sog_kn": round(sog0, 4),
            "fuel_mt": round(f0, 4),
        })
        state["sr"]["fuel"] += f0
        state["sr"]["d"] = end_d
        state["sr"]["prev_b1_sog"] = b1_sog
        print(f"        SR : b0_sog={sog0:6.3f}kn  b0_fuel={f0:6.3f}mt  "
              f"-> d={end_d:.1f}  ({sr_wall:.0f}s)", flush=True)

        # ---- Luo ----
        if skip_luo:
            # Luo/Naive unchanged by the node-first SR refresh — skip the
            # (slow) Luo re-plan and reuse prior RH-Luo numbers. Fill NaN so
            # downstream code stays shape-compatible.
            luo = {"path_arcs": [], "solve_s": 0.0}
            luo_wall = 0.0
            f0L, end_dL, sog0L = float("nan"), state["luo"]["d"], float("nan")
            b1_sogL = None
        else:
            t0 = time.time()
            luo = luo_main.solve(args_k, voyage=voyage, verbose=False,
                                 time_key=tk, d_start=state["luo"]["d"])
            luo_wall = time.time() - t0
            b0 = luo_block_metrics(luo["path_arcs"], 0)
            b1 = luo_block_metrics(luo["path_arcs"], 1)
            f0L, end_dL, sog0L = b0 if b0 else (0.0, state["luo"]["d"], 0.0)
            b1_sogL = b1[2] if b1 else None
        divL = (sog0L - state["luo"]["prev_b1_sog"]
                if state["luo"]["prev_b1_sog"] is not None else float("nan"))
        rows["luo"].append({
            "k": k, "t_wall": t_wall, "sub_eta": eta_sub,
            "forecast_cycle": sh_fc, "staleness_h": staleness,
            "d_start": round(state["luo"]["d"], 3),
            "planned_b0_sog": round(sog0L, 4),
            "realised_b0_sog": round(sog0L, 4),
            "prev_plan_b0_sog": (round(state["luo"]["prev_b1_sog"], 4)
                                 if state["luo"]["prev_b1_sog"] is not None else ""),
            "divergence_kn": (round(divL, 4) if divL == divL else ""),
            "block0_fuel_mt": round(f0L, 4),
            "sub_solve_s": round(luo["solve_s"], 2),
            "sub_wall_s": round(luo_wall, 1),
        })
        realized["luo"].append({
            "k": k, "t_h": DT_H * k, "d_start": round(state["luo"]["d"], 3),
            "d_end": round(end_dL, 3), "sog_kn": round(sog0L, 4),
            "fuel_mt": round(f0L, 4),
        })
        state["luo"]["fuel"] += f0L
        state["luo"]["d"] = end_dL
        state["luo"]["prev_b1_sog"] = b1_sogL
        print(f"        Luo: b0_sog={sog0L:6.3f}kn  b0_fuel={f0L:6.3f}mt  "
              f"-> d={end_dL:.1f}  ({luo_wall:.0f}s)", flush=True)

        executed_h += blk_dur

    L = voyage.length_nm
    return {
        "sr": {"realised_fuel_mt": state["sr"]["fuel"],
               "final_d": state["sr"]["d"], "L": L,
               "arrival_h": executed_h},
        "luo": {"realised_fuel_mt": state["luo"]["fuel"],
                "final_d": state["luo"]["d"], "L": L,
                "arrival_h": executed_h},
        "rows": rows, "realized": realized, "n_replans": n_blocks,
    }


def write_replan_csv(path: Path, rows: List[dict]) -> None:
    if not rows:
        return
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


def main() -> int:
    ap = argparse.ArgumentParser(prog="run_rh")
    ap.add_argument("--max_replans", type=int, default=0,
                    help="Truncate re-plan loop to first N steps (0 = full voyage)")
    ap.add_argument("--out_dir", default="runs/2026_06_15_rh/route2/voyage_00")
    ap.add_argument("--sh_base", type=int, default=SH_BASE_DEFAULT)
    ap.add_argument("--eta", type=float, default=ETA_DEFAULT)
    ap.add_argument("--node_first", action="store_true",
                    help="Use node-first SR arc enumeration (T20). Luo/Naive unaffected.")
    args = ap.parse_args()

    out_dir = Path(args.out_dir)
    if not out_dir.is_absolute():
        out_dir = (_HERE.parent.parent / out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"Output dir: {out_dir}", flush=True)
    voyage = VoyageWeather(Path(H5))
    issues, max_lead = load_forecast_index(H5)
    print(f"Route 2: L={voyage.length_nm:.1f} nm, ETA={args.eta:.0f} h, "
          f"sh_base={args.sh_base}, {len(issues)} forecast cycles", flush=True)

    t_start = time.time()

    print("\n=== Naive baseline (fixed mean SOG vs actual weather) ===", flush=True)
    naive = run_naive(voyage, args.eta, args.sh_base)
    print(f"Naive: {naive['total_fuel_mt']:.3f} mt", flush=True)

    print("\n=== Rolling-horizon loop ===", flush=True)
    rh = run_rh(voyage, issues, max_lead, args.eta, args.sh_base,
                max_replans=args.max_replans, node_first=args.node_first)

    # Write per-replan + realised CSVs
    write_replan_csv(out_dir / "rh_sr_replans.csv", rh["rows"]["sr"])
    write_replan_csv(out_dir / "rh_luo_replans.csv", rh["rows"]["luo"])
    write_replan_csv(out_dir / "rh_sr_realized.csv", rh["realized"]["sr"])
    write_replan_csv(out_dir / "rh_luo_realized.csv", rh["realized"]["luo"])

    # Gates
    naive_mt = naive["total_fuel_mt"]
    summary = {
        "route": "route2", "sh_base": args.sh_base, "eta_h": args.eta,
        "n_replans": rh["n_replans"], "L_nm": voyage.length_nm,
        "naive_mt": round(naive_mt, 3),
        "runtime_min": round((time.time() - t_start) / 60.0, 1),
        "oracle_ref": REF_ORACLE,
        "results": {}, "gates": {},
    }
    for key, label in [("sr", "RH-SR"), ("luo", "RH-Luo")]:
        rfuel = rh[key]["realised_fuel_mt"]
        final_d = rh[key]["final_d"]
        arr = rh[key]["arrival_h"]
        reached = abs(final_d - voyage.length_nm) < 1.0
        vs_naive = (rfuel - naive_mt) / naive_mt * 100.0 if naive_mt else float("nan")
        oracle = REF_ORACLE[key]
        gates = {
            "reached_destination": bool(reached),
            "slack_zero": bool(abs(arr - args.eta) < 1e-6) and reached,
            "rh_le_naive": bool(rfuel <= naive_mt + 1e-9),
            "rh_ge_oracle": bool(rfuel >= oracle - 1e-9),
        }
        summary["results"][key] = {
            "realised_mt": round(rfuel, 3),
            "final_d_nm": round(final_d, 2),
            "arrival_h": arr,
            "vs_naive_pct": round(vs_naive, 2),
            "vs_oracle_mt": round(rfuel - oracle, 3),
        }
        summary["gates"][key] = gates

    with open(out_dir / "summary.json", "w") as f:
        json.dump(summary, f, indent=2)

    # Console report
    print("\n" + "=" * 64)
    print("ROLLING-HORIZON SUMMARY — Route 2, sh_base=0")
    print("=" * 64)
    print(f"Naive (fixed mean SOG, actual wx): {naive_mt:8.3f} mt")
    for key, label in [("sr", "RH-SR"), ("luo", "RH-Luo")]:
        r = summary["results"][key]
        g = summary["gates"][key]
        print(f"\n{label}:")
        print(f"  realised fuel : {r['realised_mt']:8.3f} mt")
        print(f"  vs Naive      : {r['vs_naive_pct']:+6.2f} %")
        print(f"  vs oracle     : {r['vs_oracle_mt']:+6.3f} mt  "
              f"(oracle {REF_ORACLE[key]:.3f})")
        print(f"  final d       : {r['final_d_nm']:.1f} / {voyage.length_nm:.1f} nm  "
              f"arrival {r['arrival_h']:.0f} h")
        print(f"  GATES: reached={g['reached_destination']}  "
              f"slack0={g['slack_zero']}  "
              f"RH<=Naive={g['rh_le_naive']}  RH>=oracle={g['rh_ge_oracle']}")
    print(f"\nRuntime: {summary['runtime_min']:.1f} min")
    print(f"Outputs: {out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

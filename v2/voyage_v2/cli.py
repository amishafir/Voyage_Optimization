"""
Load a voyage from a route's weather archive and print what was loaded;
optionally evaluate arcs and solve for the minimum-fuel plan.

    python3 -m voyage_v2 ARCHIVE --start "YYYY-MM-DD HH:MM" --eta HOURS [--arc SUB SOG T [TAU]] ...
    python3 -m voyage_v2 ARCHIVE --start ... --eta ... --solve [--plan-csv FILE]
    python3 -m voyage_v2 ARCHIVE --start ... --eta ... --luo [--epoch 24] [--dist-step NM] [--luo-csv FILE]

ARCHIVE is a route archive written by the live collector (e.g. route1_runs.h5).
--start is UTC and is rounded to the nearest quarter hour; --eta is in hours
after the start, a multiple of 0.25. Steps (T, TAU) count quarter hours from
the start; without TAU an arc uses pseudo real-time weather.
"""

from __future__ import annotations

import argparse
import csv
import sys
from typing import Optional

from .core import DEFAULT_SHIP, CoreError, Plan, Ship, Voyage
from .loader import STEP_SECONDS, ReferenceTimeError, VoyageData, load_voyage_data


def _summary(data: VoyageData) -> str:
    a, sub = data.attrs, data.subsegments
    total_nm = float(sub["length_nm"].sum())
    lines = [
        f"Route    {a.get('route_label', '?')}: {a.get('route_name', '?')}  ({data.archive})",
        f"Start    {data.utc(0):%Y-%m-%d %H:%M} UTC"
        + ("" if data.requested_start_unix == data.start_unix else
           f"  (asked {_utc(data, data.requested_start_unix):%Y-%m-%d %H:%M:%S}, rounded to the nearest 0.25 h)"),
        f"ETA      {data.eta_steps / 4:.2f} h = {data.eta_steps} steps, arrival by {data.utc(data.eta_steps):%Y-%m-%d %H:%M} UTC",
        f"Plan     {len(sub):,} subsegments, {total_nm:,.1f} NM, {data.n_cells['wind']} wind cells, "
        f"{data.n_cells['current']} current cells (mean SOG for the ETA {total_nm / (data.eta_steps / 4):.2f} kn)",
    ]
    for grid, runs in data.runs.items():
        label = f"{grid.capitalize():<9}"
        for i, r in enumerate(runs):
            lines.append(f"{label if i == 0 else ' ' * 9}run {r.name}  steps {r.first_step:+d}..{r.last_step:+d} "
                         f"({r.n_hours} h x {r.speed.shape[0]} cells)")
        last = max(r.last_step for r in runs)
        if last < data.eta_steps:
            lines.append(f"{' ' * 9}data ends at step {last} ({data.utc(last):%Y-%m-%d %H:%M} UTC); "
                         f"steps {last + 1}..{data.eta_steps} hold the last value")
    return "\n".join(lines)


def _utc(data: VoyageData, unix: float):
    return data.utc(0) + (data.utc(1) - data.utc(0)) * ((unix - data.start_unix) / STEP_SECONDS)


def _arc_table(voyage: Voyage, arcs) -> str:
    head = (f"{'sub':>5} {'SOG':>6} {'t':>5} {'tau':>5} | {'bearing':>7} {'NM':>6} | {'wind':>6} {'from':>5} {'BN':>3} | "
            f"{'curr':>5} {'to':>5} | {'SWS':>6} {'fuel mt':>9} | sources")
    rows = [head, "-" * len(head)]
    for sub, sog, t, tau in arcs:
        d = voyage.arc_detail(sub, sog, t, tau)
        src = f"wind {d['wind_run']}{' held' if d['wind_held'] else ''}, current {d['current_run']}" \
              f"{' held' if d['current_held'] else ''}"
        rows.append(f"{sub:>5} {sog:>6.2f} {t:>5} {('-' if tau is None else tau):>5} | {d['bearing_deg']:>7.1f} "
                    f"{d['length_nm']:>6.3f} | {d['wind_speed_kmh']:>6.1f} {d['wind_from_deg']:>5.0f} {d['beaufort']:>3} | "
                    f"{d['current_speed_kmh']:>5.2f} {d['current_to_deg']:>5.0f} | {d['sws_kn']:>6.2f} "
                    f"{d['fuel_mt']:>9.5f} | {src}")
    return "\n".join(rows)


def _plan_summary(data: VoyageData, plan: Plan, args) -> str:
    s, p = plan.stats, plan.path
    lines = [
        f"Graph    {s['n_segments']:,} segments (subsegments under {args.merge} NM merged), "
        f"{args.tick} s on distance lines, {args.zeta:g} m on 0.25 h time lines, "
        f"SOG {plan.v_min_kn:.2f}-{plan.v_max_kn:.2f} kn, {'forecast from the start' if args.forecast else 'pseudo real-time'}",
        f"         nodes {s['nodes'] / 1e6:.1f} M ({s['distance_line_nodes'] / 1e6:.1f} M on distance lines, "
        f"{s['time_line_nodes'] / 1e6:.1f} M on time lines), reached {s['reached_nodes'] / 1e6:.1f} M; "
        f"arcs {s['arcs'] / 1e9:.2f} G ({s['infeasible_arcs']:,} outside the SWS range); "
        f"node memory {s['memory_mb']:.0f} MB; sweep {s['sweep_s']:.1f} s",
    ]
    if not plan.feasible:
        return "\n".join(lines + ["Plan     infeasible: no path reaches the end of the route by the ETA"])
    gain = 100 * (1 - plan.fuel_mt / plan.constant_sog_fuel_mt)
    lines += [
        f"Plan     fuel {plan.fuel_mt:.3f} mt, arrival {plan.arrival_h:.2f} h ({data.utc(round(plan.arrival_h * 4)):%Y-%m-%d %H:%M} UTC), "
        f"{len(p['fuel_mt']):,} arcs",
        f"         constant SOG {data.subsegments['length_nm'].sum() / (data.eta_steps / 4):.2f} kn: "
        f"{plan.constant_sog_fuel_mt:.3f} mt; the plan saves {gain:.2f}%",
        f"         SOG {p['sog_kn'].min():.2f}-{p['sog_kn'].max():.2f} kn, SWS {p['sws_kn'].min():.2f}-{p['sws_kn'].max():.2f} kn",
    ]
    return "\n".join(lines)


def _luo_summary(data: VoyageData, plan: Plan, args, sr: Optional[Plan], pricing: str) -> str:
    s, p = plan.stats, plan.path
    hours = args.epoch * 0.25
    step = args.dist_step or 0.1 * hours
    how = "arcs priced at their start point (Luo et al.)" if pricing == "start" else "arcs priced piece by piece"
    lines = [
        f"Luo      epochs of {hours:g} h ({args.epoch} steps), nodes every {step:g} NM on the epoch lines "
        f"(SOG steps {step / hours:.3f} kn), SOG {plan.v_min_kn:.2f}-{plan.v_max_kn:.2f} kn, "
        f"{'forecast from the start' if args.forecast else 'pseudo real-time'}; {how}",
        f"         nodes {s['nodes']:,}, reached {s['reached_nodes']:,}; arcs {s['arcs']:,} "
        f"({s['infeasible_arcs']:,} outside the SWS range); {s['sws_evaluations'] / 1e6:.1f} M SWS evaluations; "
        f"sweep {s['sweep_s']:.1f} s",
    ]
    if not plan.feasible:
        return "\n".join(lines + ["         infeasible: no path reaches the end of the route by the ETA"])
    gain = 100 * (1 - plan.fuel_mt / plan.constant_sog_fuel_mt)
    if abs(plan.planned_fuel_mt - plan.fuel_mt) > 1e-9 * plan.fuel_mt:
        lines.append(f"         planned {plan.planned_fuel_mt:.3f} mt; realized in the actual weather, every piece priced: "
                     f"{plan.fuel_mt:.3f} mt ({100 * (plan.fuel_mt / plan.planned_fuel_mt - 1):+.3f}%)"
                     + (f"; {s['realized_sws_violations']} pieces need an SWS outside 2-25 kn"
                        if s["realized_sws_violations"] else ""))
    lines.append(f"         fuel {plan.fuel_mt:.3f} mt, arrival {plan.arrival_h:.2f} h, {len(p['fuel_mt'])} epochs, "
                 f"SOG {p['sog_kn'].min():.2f}-{p['sog_kn'].max():.2f} kn; "
                 + (f"saves {gain:.2f}%" if gain >= 0 else f"uses {-gain:.2f}% more") + " against constant SOG")
    if sr is not None and sr.feasible:
        diff = 100 * (plan.fuel_mt / sr.fuel_mt - 1)
        lines.append(f"         {abs(diff):.3f}% {'more' if diff >= 0 else 'less'} fuel than the full graph "
                     f"(--solve, {sr.fuel_mt:.3f} mt)")
    return "\n".join(lines)


def _write_plan(path: str, data: VoyageData, plan: Plan) -> None:
    p, seg = plan.path, plan.segments
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["t0_h", "t0_utc", "d0_nm", "t1_h", "d1_nm", "sog_kn", "sws_kn", "fuel_mt", "planned_fuel_mt",
                    "segment", "subsegment", "bearing_deg", "step"])
        for q in range(len(p["fuel_mt"])):
            g = int(p["segment"][q])
            w.writerow([f"{p['t0_h'][q]:.6f}", f"{data.utc(0) + (data.utc(4) - data.utc(0)) * p['t0_h'][q]:%Y-%m-%d %H:%M:%S}",
                        f"{p['d0_nm'][q]:.6f}", f"{p['t1_h'][q]:.6f}", f"{p['d1_nm'][q]:.6f}",
                        f"{p['sog_kn'][q]:.6f}", f"{p['sws_kn'][q]:.6f}", f"{p['fuel_mt'][q]:.9f}",
                        f"{p['planned_fuel_mt'][q]:.9f}", g,
                        int(seg['dominant_sub'][g]), f"{seg['bearing_deg'][g]:.4f}", int(p["step"][q])])


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="python3 -m voyage_v2", description=__doc__.split("\n\n")[0].strip())
    p.add_argument("archive", help="route weather archive (HDF5, collector layout model-runs-v1)")
    p.add_argument("--start", required=True, help='voyage start, UTC: "YYYY-MM-DD HH:MM"')
    p.add_argument("--eta", required=True, type=float, help="ETA in hours after the start (multiple of 0.25)")
    p.add_argument("--ship", default=str(DEFAULT_SHIP), help="ship particulars (YAML)")
    p.add_argument("--arc", nargs="+", action="append", metavar="SUB SOG T [TAU]", default=[],
                   help="evaluate an arc: subsegment, SOG [kn], step, information step (optional)")
    g = p.add_argument_group("minimum-fuel plan (single core)")
    g.add_argument("--solve", action="store_true", help="solve the DP on the full time-distance graph")
    g.add_argument("--sog-band", type=float, default=3.0, help="SOG window: mean SOG +/- this [kn] (default 3)")
    g.add_argument("--tick", type=int, default=4, help="node spacing on distance lines [s], divides 900 (default 4)")
    g.add_argument("--zeta", type=float, default=25.0, help="node spacing on time lines [m] (default 25)")
    g.add_argument("--merge", type=float, default=0.15, help="merge subsegments shorter than this [NM] (default 0.15)")
    g.add_argument("--forecast", action="store_true", help="price arcs with the forecast known at the start")
    g.add_argument("--plan-csv", metavar="FILE", help="write the plan, one row per arc")
    g = p.add_argument_group("Luo et al. multistage DP (single core)")
    g.add_argument("--luo", action="store_true", help="solve with constant SOG within decision epochs")
    g.add_argument("--epoch", type=int, default=24, help="decision epoch in 0.25 h steps (default 24 = 6 h)")
    g.add_argument("--dist-step", type=float, default=None,
                   help="node spacing on the epoch lines [NM] (default 0.1 kn x epoch length, 0.6 NM for 6 h)")
    g.add_argument("--luo-pricing", choices=("integrated", "start", "both"), default="integrated",
                   help="price arcs piece by piece along their path (default), at their start point only as "
                        "Luo et al. do, or both")
    g.add_argument("--luo-csv", metavar="FILE", help="write the Luo plan, one row per epoch")
    args = p.parse_args(argv)

    arcs = []
    for a in args.arc:
        if len(a) not in (3, 4):
            p.error(f"--arc takes SUB SOG T [TAU], got {' '.join(a)}")
        arcs.append((int(a[0]), float(a[1]), int(a[2]), int(a[3]) if len(a) == 4 else None))

    try:
        data = load_voyage_data(args.archive, args.start, args.eta)
    except (ReferenceTimeError, ValueError, OSError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    print(_summary(data))
    voyage = Voyage(data, Ship.from_yaml(args.ship))
    if arcs:
        print()
        print(_arc_table(voyage, arcs))
    plan = None
    if args.solve or args.plan_csv:
        try:
            plan = voyage.solve(args.sog_band, args.tick, args.zeta, args.merge, args.forecast)
        except CoreError as e:
            print(f"error: {e}", file=sys.stderr)
            return 1
        print()
        print(_plan_summary(data, plan, args))
        if args.plan_csv and plan.feasible:
            _write_plan(args.plan_csv, data, plan)
            print(f"         plan written to {args.plan_csv}")
    if args.luo or args.luo_csv:
        for pricing in (("integrated", "start") if args.luo_pricing == "both" else (args.luo_pricing,)):
            try:
                luo = voyage.solve_luo(args.epoch, args.dist_step, args.sog_band, args.forecast, pricing)
            except CoreError as e:
                print(f"error: {e}", file=sys.stderr)
                return 1
            print()
            print(_luo_summary(data, luo, args, plan, pricing))
            if args.luo_csv and luo.feasible:
                path = args.luo_csv if args.luo_pricing != "both" else args.luo_csv.replace(".csv", f"_{pricing}.csv")
                _write_plan(path, data, luo)
                print(f"         plan written to {path}")
    return 0

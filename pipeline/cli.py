#!/usr/bin/env python3
"""
CLI entry point for the maritime speed optimization pipeline.

Usage:
    python3 pipeline/cli.py collect
    python3 pipeline/cli.py run static_det
    python3 pipeline/cli.py run all
    python3 pipeline/cli.py compare
    python3 pipeline/cli.py convert-pickle <pickle_path> <hdf5_path>
"""

import argparse
import logging
import os
import sys

import yaml


def load_config(config_path):
    """Load and return the experiment config."""
    with open(config_path) as f:
        return yaml.safe_load(f)


def cmd_collect(args, config):
    if args.route:
        config["collection"]["route"] = args.route
    if args.hours:
        config["collection"]["hours"] = args.hours
    if args.interval_nm:
        config["collection"]["interval_nm"] = args.interval_nm
    from collect.collector import collect
    collect(config)


def _find_hdf5(config):
    """Locate the HDF5 data file."""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_dir, "data", "voyage_weather.h5")


def _run_static_det(config):
    """Run static deterministic pipeline: transform -> optimize -> simulate -> metrics."""
    from static_det.transform import transform
    from static_det.optimize import optimize
    from shared.simulation import simulate_voyage
    from shared.metrics import compute_result_metrics, build_result_json, save_result

    hdf5_path = _find_hdf5(config)
    base_dir = os.path.dirname(os.path.abspath(__file__))
    output_dir = os.path.join(base_dir, "output")
    os.makedirs(output_dir, exist_ok=True)

    # 1. Transform
    print("--- Transform ---")
    t_out = transform(hdf5_path, config)

    # 2. Optimize
    print("--- Optimize ---")
    planned = optimize(t_out, config)
    if planned.get("status") != "Optimal":
        print(f"LP solver status: {planned.get('status')} -- aborting.")
        return

    # 3. Simulate
    print("--- Simulate ---")
    simulated = simulate_voyage(
        planned["speed_schedule"], hdf5_path, config,
        sample_hour=config["static_det"]["weather_snapshot"],
    )

    # 4. Metrics
    total_dist = sum(t_out["distances"])
    metrics = compute_result_metrics(planned, simulated, total_dist)

    # 5. Save time series CSV
    ts_path = os.path.join(output_dir, "timeseries_static_det.csv")
    simulated["time_series"].to_csv(ts_path, index=False)
    print(f"Time series saved: {ts_path}")

    # 6. Build and save result JSON
    result = build_result_json(
        approach="static_det",
        config=config,
        planned=planned,
        simulated=simulated,
        metrics=metrics,
        time_series_file=ts_path,
    )
    json_path = os.path.join(output_dir, "result_static_det.json")
    save_result(result, json_path)

    # 7. Print summary
    print()
    print("=" * 60)
    print("STATIC DETERMINISTIC — RESULTS")
    print("=" * 60)
    print(f"  Planned fuel:    {planned['planned_fuel_kg']:>10.2f} kg")
    print(f"  Planned time:    {planned['planned_time_h']:>10.2f} h")
    print(f"  Simulated fuel:  {simulated['total_fuel_kg']:>10.2f} kg")
    print(f"  Simulated time:  {simulated['total_time_h']:>10.2f} h")
    print(f"  Fuel gap:        {metrics['fuel_gap_percent']:>10.2f} %")
    print(f"  Fuel/nm:         {metrics['fuel_per_nm']:>10.4f} kg/nm")
    print(f"  Avg SOG:         {metrics['avg_sog_knots']:>10.2f} knots")
    print(f"  CO2 emissions:   {simulated['co2_emissions_kg']:>10.2f} kg")
    print(f"  Solve time:      {planned['computation_time_s']:>10.3f} s")
    print(f"  Result JSON:     {json_path}")
    print("=" * 60)

    # Print speed schedule
    print()
    print(f"{'Seg':>3}  {'Dist':>8}  {'SWS':>6}  {'SOG':>8}  {'Time':>7}  {'Fuel':>8}")
    print(f"{'#':>3}  {'(nm)':>8}  {'(kn)':>6}  {'(kn)':>8}  {'(h)':>7}  {'(kg)':>8}")
    print("-" * 50)
    for s in planned["speed_schedule"]:
        print(f"{s['segment']+1:>3}  {s['distance_nm']:>8.1f}  "
              f"{s['sws_knots']:>6.1f}  {s['sog_knots']:>8.3f}  "
              f"{s['time_h']:>7.2f}  {s['fuel_kg']:>8.2f}")
    print()


def _run_dynamic_det(config):
    """Run dynamic deterministic pipeline: transform -> optimize -> simulate -> metrics."""
    from dynamic_det.transform import transform
    from dynamic_det.optimize import optimize
    from shared.simulation import simulate_voyage
    from shared.metrics import compute_result_metrics, build_result_json, save_result

    hdf5_path = _find_hdf5(config)
    base_dir = os.path.dirname(os.path.abspath(__file__))
    output_dir = os.path.join(base_dir, "output")
    os.makedirs(output_dir, exist_ok=True)

    # 1. Transform
    print("--- Transform ---")
    t_out = transform(hdf5_path, config)

    # 2. Optimize
    print("--- Optimize ---")
    planned = optimize(t_out, config)
    if planned.get("status") not in ("Optimal", "Feasible"):
        print(f"DP solver status: {planned.get('status')} -- aborting.")
        return

    # 3. Simulate
    print("--- Simulate ---")
    simulated = simulate_voyage(
        planned["speed_schedule"], hdf5_path, config,
        sample_hour=config["dynamic_det"]["forecast_origin"],
    )

    # 4. Metrics
    total_dist = sum(t_out["distances"])
    metrics = compute_result_metrics(planned, simulated, total_dist)

    # 5. Save time series CSV
    ts_path = os.path.join(output_dir, "timeseries_dynamic_det.csv")
    simulated["time_series"].to_csv(ts_path, index=False)
    print(f"Time series saved: {ts_path}")

    # 6. Build and save result JSON
    result = build_result_json(
        approach="dynamic_det",
        config=config,
        planned=planned,
        simulated=simulated,
        metrics=metrics,
        time_series_file=ts_path,
    )
    json_path = os.path.join(output_dir, "result_dynamic_det.json")
    save_result(result, json_path)

    # 7. Print summary
    print()
    print("=" * 60)
    print("DYNAMIC DETERMINISTIC — RESULTS")
    print("=" * 60)
    print(f"  Planned fuel:    {planned['planned_fuel_kg']:>10.2f} kg")
    print(f"  Planned time:    {planned['planned_time_h']:>10.2f} h")
    print(f"  Simulated fuel:  {simulated['total_fuel_kg']:>10.2f} kg")
    print(f"  Simulated time:  {simulated['total_time_h']:>10.2f} h")
    print(f"  Fuel gap:        {metrics['fuel_gap_percent']:>10.2f} %")
    print(f"  Fuel/nm:         {metrics['fuel_per_nm']:>10.4f} kg/nm")
    print(f"  Avg SOG:         {metrics['avg_sog_knots']:>10.2f} knots")
    print(f"  CO2 emissions:   {simulated['co2_emissions_kg']:>10.2f} kg")
    print(f"  Solve time:      {planned['computation_time_s']:>10.3f} s")
    print(f"  Result JSON:     {json_path}")
    print("=" * 60)

    # Print first/last 5 legs of schedule (278 legs is too many to show all)
    sched = planned["speed_schedule"]
    print()
    print(f"{'Leg':>4}  {'Node':>5}  {'Seg':>3}  {'Dist':>8}  {'SWS':>6}  {'SOG':>8}  {'Time':>7}  {'Fuel':>8}")
    print(f"{'#':>4}  {'ID':>5}  {'#':>3}  {'(nm)':>8}  {'(kn)':>6}  {'(kn)':>8}  {'(h)':>7}  {'(kg)':>8}")
    print("-" * 60)
    show = sched[:5] + [None] + sched[-5:] if len(sched) > 12 else sched
    for s in show:
        if s is None:
            print(f"{'...':>4}  {'...':>5}  {'...':>3}  {'...':>8}  {'...':>6}  {'...':>8}  {'...':>7}  {'...':>8}")
            continue
        print(f"{s['leg']:>4}  {s['node_id']:>5}  {s['segment']:>3}  {s['distance_nm']:>8.1f}  "
              f"{s['sws_knots']:>6.1f}  {s['sog_knots']:>8.3f}  "
              f"{s['time_h']:>7.4f}  {s['fuel_kg']:>8.4f}")
    print()


def _run_dynamic_rh(config):
    """Run rolling horizon pipeline: transform -> optimize -> simulate -> metrics."""
    from dynamic_rh.transform import transform
    from dynamic_rh.optimize import optimize
    from shared.simulation import simulate_voyage
    from shared.metrics import compute_result_metrics, build_result_json, save_result

    hdf5_path = _find_hdf5(config)
    base_dir = os.path.dirname(os.path.abspath(__file__))
    output_dir = os.path.join(base_dir, "output")
    os.makedirs(output_dir, exist_ok=True)

    # 1. Transform (loads all sample hours)
    print("--- Transform ---")
    t_out = transform(hdf5_path, config)

    # 2. Optimize (rolling horizon loop)
    print("--- Optimize (Rolling Horizon) ---")
    planned = optimize(t_out, config)
    if planned.get("status") not in ("Optimal", "Feasible"):
        print(f"RH solver status: {planned.get('status')} -- aborting.")
        return

    # 3. Simulate
    print("--- Simulate ---")
    simulated = simulate_voyage(
        planned["speed_schedule"], hdf5_path, config,
        sample_hour=0,
    )

    # 4. Metrics
    total_dist = sum(t_out["distances"])
    metrics = compute_result_metrics(planned, simulated, total_dist)

    # 5. Save time series CSV
    ts_path = os.path.join(output_dir, "timeseries_dynamic_rh.csv")
    simulated["time_series"].to_csv(ts_path, index=False)
    print(f"Time series saved: {ts_path}")

    # 6. Build and save result JSON (include decision_points)
    result = build_result_json(
        approach="dynamic_rh",
        config=config,
        planned=planned,
        simulated=simulated,
        metrics=metrics,
        time_series_file=ts_path,
    )
    result["decision_points"] = planned.get("decision_points", [])
    json_path = os.path.join(output_dir, "result_dynamic_rh.json")
    save_result(result, json_path)

    # 7. Print summary
    print()
    print("=" * 60)
    print("DYNAMIC ROLLING HORIZON — RESULTS")
    print("=" * 60)
    print(f"  Planned fuel:    {planned['planned_fuel_kg']:>10.2f} kg")
    print(f"  Planned time:    {planned['planned_time_h']:>10.2f} h")
    print(f"  Simulated fuel:  {simulated['total_fuel_kg']:>10.2f} kg")
    print(f"  Simulated time:  {simulated['total_time_h']:>10.2f} h")
    print(f"  Fuel gap:        {metrics['fuel_gap_percent']:>10.2f} %")
    print(f"  Fuel/nm:         {metrics['fuel_per_nm']:>10.4f} kg/nm")
    print(f"  Avg SOG:         {metrics['avg_sog_knots']:>10.2f} knots")
    print(f"  CO2 emissions:   {simulated['co2_emissions_kg']:>10.2f} kg")
    print(f"  Solve time:      {planned['computation_time_s']:>10.3f} s")
    print(f"  Decision points: {len(planned.get('decision_points', [])):>10d}")
    print(f"  Result JSON:     {json_path}")
    print("=" * 60)

    # Print decision points summary
    dps = planned.get("decision_points", [])
    if dps:
        print()
        print(f"{'DP':>3}  {'Hour':>6}  {'SH':>3}  {'Node':>5}  {'Legs':>5}  "
              f"{'Fuel':>8}  {'Time':>7}  {'Status':>8}")
        print("-" * 58)
        for i, dp in enumerate(dps):
            print(f"{i:>3}  {dp['decision_hour']:>6}  {dp['sample_hour']:>3}  "
                  f"{dp['node_idx']:>5}  {dp['legs_committed']:>5}  "
                  f"{dp['elapsed_fuel_kg']:>8.2f}  {dp['elapsed_time_h']:>7.2f}  "
                  f"{dp['dp_status']:>8}")
    print()


def cmd_run(args, config):
    approach = args.approach
    if approach == "static_det":
        _run_static_det(config)
    elif approach == "all":
        if config.get("static_det", {}).get("enabled", True):
            _run_static_det(config)
        if config.get("dynamic_det", {}).get("enabled", True):
            _run_dynamic_det(config)
        if config.get("dynamic_rh", {}).get("enabled", True):
            _run_dynamic_rh(config)
    elif approach == "dynamic_det":
        _run_dynamic_det(config)
    elif approach == "dynamic_rh":
        _run_dynamic_rh(config)


def cmd_compare(args, config):
    print("compare: Not implemented yet")


def cmd_convert_pickle(args, config):
    from collect.waypoints import load_route_config
    from shared.hdf5_io import import_from_pickle
    route_config = load_route_config(config)
    import_from_pickle(args.pickle_path, args.hdf5_path, route_config)


def main():
    # Resolve config path relative to this file
    base_dir = os.path.dirname(os.path.abspath(__file__))
    default_config = os.path.join(base_dir, "config", "experiment.yaml")

    # Ensure pipeline dir is on sys.path for `from shared...` / `from collect...`
    if base_dir not in sys.path:
        sys.path.insert(0, base_dir)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    parser = argparse.ArgumentParser(
        prog="pipeline",
        description="Maritime speed optimization research pipeline",
    )
    parser.add_argument(
        "--config",
        default=default_config,
        help="Path to experiment.yaml (default: pipeline/config/experiment.yaml)",
    )

    subparsers = parser.add_subparsers(dest="command")

    # collect
    sp_collect = subparsers.add_parser("collect", help="Collect weather data into HDF5")
    sp_collect.add_argument("--route", help="Route name override")
    sp_collect.add_argument("--hours", type=int, help="Collection duration override")
    sp_collect.add_argument("--interval-nm", type=float, help="Waypoint spacing override")

    # run
    sp_run = subparsers.add_parser("run", help="Run an optimization approach")
    sp_run.add_argument(
        "approach",
        choices=["static_det", "dynamic_det", "dynamic_rh", "all"],
        help="Which approach to run",
    )

    # compare
    subparsers.add_parser("compare", help="Compare results across approaches")

    # convert-pickle
    sp_convert = subparsers.add_parser("convert-pickle", help="Convert legacy pickle to HDF5")
    sp_convert.add_argument("pickle_path", help="Path to input pickle file")
    sp_convert.add_argument("hdf5_path", help="Path to output HDF5 file")

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(0)

    # Validate config exists
    if not os.path.isfile(args.config):
        print(f"Error: config file not found: {args.config}", file=sys.stderr)
        sys.exit(1)

    config = load_config(args.config)

    dispatch = {
        "collect": cmd_collect,
        "run": cmd_run,
        "compare": cmd_compare,
        "convert-pickle": cmd_convert_pickle,
    }
    dispatch[args.command](args, config)


if __name__ == "__main__":
    main()

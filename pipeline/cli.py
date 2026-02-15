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
import os
import sys

import yaml


def load_config(config_path):
    """Load and return the experiment config."""
    with open(config_path) as f:
        return yaml.safe_load(f)


def cmd_collect(args, config):
    print("collect: Not implemented yet")


def cmd_run(args, config):
    print(f"run {args.approach}: Not implemented yet")


def cmd_compare(args, config):
    print("compare: Not implemented yet")


def cmd_convert_pickle(args, config):
    print(f"convert-pickle {args.pickle_path} -> {args.hdf5_path}: Not implemented yet")


def main():
    # Resolve config path relative to this file
    base_dir = os.path.dirname(os.path.abspath(__file__))
    default_config = os.path.join(base_dir, "config", "experiment.yaml")

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
        choices=["static_det", "dynamic_det", "dynamic_stoch", "all"],
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

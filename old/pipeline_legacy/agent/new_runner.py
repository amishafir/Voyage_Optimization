"""Runner for the 3-agent cycle experiment.

Runs Naive, Deterministic, and Stochastic agents on the same route/weather
data and prints a comparison table.

Usage:
    cd pipeline
    python3 -m agent.new_runner --config config/experiment_exp_d.yaml \
                                --hdf5 data/experiment_d_391wp.h5
    python3 -m agent.new_runner --config config/experiment_exp_d.yaml \
                                --hdf5 data/experiment_d_391wp.h5 \
                                --agents naive deterministic
"""

import argparse
import logging
import sys
import os
import yaml

from agent.cycle_executor import execute_cycle_voyage

logger = logging.getLogger(__name__)

AGENT_3_CONFIGS = [
    {"name": "Naive",         "type": "naive"},
    {"name": "Deterministic", "type": "deterministic"},
    {"name": "Stochastic",    "type": "stochastic"},
]


def run_3agent(config: dict, hdf5_path: str,
               agents: list = None,
               departure_sample_hour: int = 0) -> list:
    """Run all (or selected) agents and return results.

    Args:
        config: Full experiment config dict.
        hdf5_path: Path to HDF5 weather data.
        agents: List of agent type strings to run (default: all three).
        departure_sample_hour: Which sample_hour the voyage departs at.

    Returns:
        List of result dicts, one per agent.
    """
    if agents is None:
        agent_list = AGENT_3_CONFIGS
    else:
        agent_set = {a.lower() for a in agents}
        agent_list = [c for c in AGENT_3_CONFIGS if c["type"] in agent_set]

    results = []
    for agent_cfg in agent_list:
        logger.info("=" * 60)
        logger.info("Running agent: %s", agent_cfg["name"])
        logger.info("=" * 60)

        result = execute_cycle_voyage(
            agent_type=agent_cfg["type"],
            hdf5_path=hdf5_path,
            config=config,
            departure_sample_hour=departure_sample_hour,
        )
        results.append(result)

        logger.info("%s: %.2f mt fuel, %.1f h, deviation=%.2f h, "
                     "Flow2=%d, re-plans=%d",
                     result["agent"], result["total_fuel_mt"],
                     result["total_time_h"], result["arrival_deviation_h"],
                     result["flow2_count"], result["replan_count"])

    return results


def print_summary(results: list, config: dict):
    """Print a formatted comparison table."""
    eta = config["ship"]["eta_hours"]
    route = config.get("collection", {}).get("route", "unknown")

    print()
    print(f"  3-Agent Comparison — Route: {route}, ETA: {eta}h")
    print("  " + "=" * 75)
    print(f"  {'Agent':<15} {'Fuel (mt)':>10} {'Time (h)':>10} "
          f"{'Delay (h)':>10} {'Flow2':>7} {'Flow3':>7} {'Re-plans':>9}")
    print("  " + "-" * 75)

    for r in results:
        delay = r["arrival_deviation_h"]
        delay_str = f"{delay:+.2f}"
        print(f"  {r['agent']:<15} {r['total_fuel_mt']:>10.2f} "
              f"{r['total_time_h']:>10.1f} {delay_str:>10} "
              f"{r['flow2_count']:>7} {r['flow3_count']:>7} "
              f"{r['replan_count']:>9}")

    print("  " + "=" * 75)

    # Fuel comparison
    if len(results) >= 2:
        fuels = {r["agent"]: r["total_fuel_mt"] for r in results}
        best = min(fuels, key=fuels.get)
        worst = max(fuels, key=fuels.get)
        savings = fuels[worst] - fuels[best]
        pct = 100.0 * savings / fuels[worst] if fuels[worst] > 0 else 0
        print(f"\n  Best: {best} ({fuels[best]:.2f} mt)")
        print(f"  Worst: {worst} ({fuels[worst]:.2f} mt)")
        print(f"  Savings: {savings:.2f} mt ({pct:.1f}%)")
    print()


def main():
    parser = argparse.ArgumentParser(description="3-Agent Cycle Experiment")
    parser.add_argument("--config", required=True, help="Path to experiment YAML")
    parser.add_argument("--hdf5", required=True, help="Path to HDF5 weather file")
    parser.add_argument("--agents", nargs="*", default=None,
                        help="Agent types to run (default: all)")
    parser.add_argument("--departure", type=int, default=0,
                        help="Departure sample_hour (default: 0)")
    parser.add_argument("--verbose", action="store_true",
                        help="Enable debug logging")
    args = parser.parse_args()

    level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%H:%M:%S",
    )

    with open(args.config) as f:
        config = yaml.safe_load(f)

    results = run_3agent(config, args.hdf5,
                         agents=args.agents,
                         departure_sample_hour=args.departure)

    print_summary(results, config)

    # Save time series CSVs
    output_dir = os.path.join(os.path.dirname(args.hdf5), "..", "output")
    os.makedirs(output_dir, exist_ok=True)
    for r in results:
        ts = r.get("time_series")
        if ts is not None and len(ts) > 0:
            fname = f"cycle_{r['agent'].lower()}_dep{args.departure}.csv"
            path = os.path.join(output_dir, fname)
            ts.to_csv(path, index=False)
            logger.info("Saved time series: %s", path)


if __name__ == "__main__":
    main()

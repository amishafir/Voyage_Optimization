#!/usr/bin/env python3
"""Experiment runner — execute all agent configurations and produce comparison table.

Usage:
    cd pipeline
    python3 -m agent.runner --config config/experiment_exp_d.yaml --hdf5 data/experiment_d_391wp.h5
    python3 -m agent.runner --config config/experiment_exp_b.yaml --hdf5 data/experiment_b_138wp.h5
"""

import argparse
import logging
import os
import sys
import time

import yaml

pipeline_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if pipeline_dir not in sys.path:
    sys.path.insert(0, pipeline_dir)

from agent import assemble
from agent.executor import execute_voyage

logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Agent definitions
# ---------------------------------------------------------------------------

AGENT_CONFIGS = [
    {"name": "Naive-A", "plan": "naive", "environment": "basic"},
    {"name": "LP-A",    "plan": "lp",    "environment": "basic"},
    {"name": "LP-B",    "plan": "lp",    "environment": "mid",   "policy": "reactive"},
    {"name": "LP-C",    "plan": "lp",    "environment": "connected", "policy": "proactive"},
    {"name": "DP-A",    "plan": "dp",    "environment": "basic"},
    {"name": "DP-B",    "plan": "dp",    "environment": "mid",   "policy": "reactive"},
    {"name": "DP-C",    "plan": "dp",    "environment": "connected", "policy": "proactive"},
]


def _get_transforms(hdf5_path, config):
    """Pre-compute transform outputs (shared across agents)."""
    from static_det.transform import transform as lp_transform
    from dynamic_det.transform import transform as dp_transform

    transforms = {
        "lp": lp_transform(hdf5_path, config),
        "dp": dp_transform(hdf5_path, config),
    }

    # RH transform for Connected agents (loads all sample hours)
    try:
        from dynamic_rh.transform import transform as rh_transform
        transforms["rh"] = rh_transform(hdf5_path, config)
    except Exception as e:
        logger.warning("RH transform failed (Connected agents will be skipped): %s", e)
        transforms["rh"] = None

    return transforms


def _setup_environment(agent, transforms, config):
    """Configure environment with appropriate weather data."""
    from agent.environments import MidEnvironment, ConnectedEnvironment

    if isinstance(agent.environment, MidEnvironment):
        plan_key = "dp" if agent.plan.name == "dp" else "lp"
        agent.environment.cache_initial_transform(transforms[plan_key])

    elif isinstance(agent.environment, ConnectedEnvironment):
        rh = transforms.get("rh")
        if rh is not None:
            agent.environment.load_all_forecasts(rh)


def _get_transform_for_plan(agent, transforms):
    """Get the right transform output for this agent's plan type."""
    if agent.plan.name == "dp":
        return transforms["dp"]
    elif agent.plan.name == "lp":
        return transforms["lp"]
    elif agent.plan.name == "naive":
        return transforms["lp"]  # Naive uses LP transform for distances
    return None


def _is_time_varying(agent):
    """Connected agents use time-varying actual weather for execution."""
    return agent.environment.can_communicate


def run_single(agent_cfg, config, hdf5_path, transforms, lambda_val=None):
    """Run a single agent configuration.

    Returns result dict or None on failure.
    """
    # Override λ if specified
    run_config = dict(config)
    run_config["ship"] = dict(config["ship"])
    if lambda_val is not None:
        run_config["ship"]["eta_penalty_mt_per_hour"] = lambda_val
    else:
        run_config["ship"]["eta_penalty_mt_per_hour"] = config["ship"].get(
            "eta_penalty_mt_per_hour"
        )

    agent = assemble(
        run_config,
        plan=agent_cfg["plan"],
        policy=agent_cfg.get("policy"),
        environment=agent_cfg["environment"],
        name=agent_cfg["name"],
    )

    _setup_environment(agent, transforms, run_config)
    t_out = _get_transform_for_plan(agent, transforms)

    if t_out is None:
        return None

    # Plan
    plan = agent.plan.optimize(t_out, run_config)
    if plan.get("status") not in ("Optimal", "Feasible", "ETA_relaxed"):
        return {"agent": agent.name, "status": plan.get("status", "Failed"), "lambda": lambda_val}

    # For LP re-planning, we need the DP transform (has node_metadata, per-node distances)
    replan_t = transforms["dp"] if agent.plan.name == "lp" else None

    # Execute
    result = execute_voyage(
        agent, hdf5_path, run_config,
        initial_plan=plan,
        transform_output=t_out,
        replan_transform=replan_t,
        time_varying=_is_time_varying(agent),
        sample_hour=0,
    )
    result["lambda"] = lambda_val
    return result


def run_matrix(config, hdf5_path, agents=None, lambdas=None):
    """Run the full experiment matrix.

    Args:
        config: Experiment YAML config.
        hdf5_path: Path to HDF5 weather file.
        agents: List of agent config dicts (default: all 7).
        lambdas: List of λ values to test (default: [None] = use config value).

    Returns:
        List of result dicts.
    """
    if agents is None:
        agents = AGENT_CONFIGS
    if lambdas is None:
        lambdas = [None]

    print("Pre-computing transforms...")
    transforms = _get_transforms(hdf5_path, config)

    results = []
    total = len(agents) * len(lambdas)
    done = 0

    for lam in lambdas:
        lam_str = f"λ={lam}" if lam is not None else "λ=config"
        for agent_cfg in agents:
            done += 1
            name = agent_cfg["name"]
            print(f"  [{done}/{total}] {name} ({lam_str})...", end="", flush=True)
            t0 = time.time()

            try:
                result = run_single(agent_cfg, config, hdf5_path, transforms, lam)
                if result and result.get("status") not in (None, "Failed", "Infeasible"):
                    elapsed = time.time() - t0
                    print(f" {result['total_fuel_mt']:.1f} mt, "
                          f"{result['total_time_h']:.1f}h, "
                          f"F2={result.get('flow2_count', 0)}, "
                          f"re={result.get('replan_count', 0)} "
                          f"({elapsed:.1f}s)")
                    results.append(result)
                else:
                    status = result.get("status", "?") if result else "None"
                    print(f" SKIP ({status})")
            except Exception as e:
                print(f" ERROR: {e}")
                logger.exception("Failed: %s %s", name, lam_str)

    return results


def print_summary(results, config):
    """Print a formatted comparison table."""
    if not results:
        print("\nNo results to display.")
        return

    eta = config["ship"]["eta_hours"]
    lambda_val = config["ship"].get("eta_penalty_mt_per_hour")
    lam_str = f"λ={lambda_val}" if lambda_val is not None else "λ=∞ (hard ETA)"

    # Group by λ
    lambdas_seen = sorted(set(r.get("lambda") for r in results), key=lambda x: (x is None, x or 0))

    for lam in lambdas_seen:
        lam_results = [r for r in results if r.get("lambda") == lam]
        lam_label = f"λ={lam}" if lam is not None else lam_str

        print(f"\n{'=' * 85}")
        print(f"  RESULTS  ({lam_label})  ETA={eta}h")
        print(f"{'=' * 85}")
        print(f"  {'Agent':<10} {'Plan Fuel':>10} {'Exec Fuel':>10} {'Time':>8} "
              f"{'Delay':>8} {'Flow2':>6} {'Flow3':>6} {'Replan':>7} {'Wall(s)':>8}")
        print(f"  {'-' * 80}")

        for r in sorted(lam_results, key=lambda x: x.get("total_fuel_mt", 999)):
            name = r.get("agent", "?")
            plan_fuel = r.get("planned_fuel_mt", 0)
            exec_fuel = r.get("total_fuel_mt", 0)
            exec_time = r.get("total_time_h", 0)
            delay = exec_time - eta
            flow2 = r.get("flow2_count", 0)
            flow3 = r.get("flow3_count", 0)
            replans = r.get("replan_count", 0)
            wall = r.get("computation_time_s", 0)

            print(f"  {name:<10} {plan_fuel:>10.2f} {exec_fuel:>10.2f} {exec_time:>8.2f} "
                  f"{delay:>+8.2f} {flow2:>6} {flow3:>6} {replans:>7} {wall:>8.1f}")

        print(f"  {'-' * 80}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Run agent experiment matrix")
    parser.add_argument("--config", required=True, help="Path to experiment YAML")
    parser.add_argument("--hdf5", required=True, help="Path to HDF5 weather file")
    parser.add_argument("--agents", nargs="+", default=None,
                        help="Agent names to run (default: all)")
    parser.add_argument("--lambda", dest="lambdas", nargs="+", type=str, default=None,
                        help="Lambda values (use 'null' for hard ETA, 'inf' for infinity)")
    args = parser.parse_args()

    with open(args.config) as f:
        config = yaml.safe_load(f)

    # Filter agents if specified
    agents = AGENT_CONFIGS
    if args.agents:
        agents = [a for a in AGENT_CONFIGS if a["name"] in args.agents]

    # Parse lambda values
    lambdas = [None]
    if args.lambdas:
        lambdas = []
        for v in args.lambdas:
            if v in ("null", "None", "none"):
                lambdas.append(None)
            elif v == "inf":
                lambdas.append(None)  # None = hard ETA = λ=∞
            else:
                lambdas.append(float(v))

    route_name = config.get("collection", {}).get("route", "unknown")
    print(f"\n{'=' * 85}")
    print(f"  AGENT EXPERIMENT — {route_name}")
    print(f"  {len(agents)} agents × {len(lambdas)} λ values = {len(agents) * len(lambdas)} runs")
    print(f"{'=' * 85}\n")

    results = run_matrix(config, args.hdf5, agents=agents, lambdas=lambdas)
    print_summary(results, config)


if __name__ == "__main__":
    main()

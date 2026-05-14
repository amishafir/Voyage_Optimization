#!/usr/bin/env python3
"""Backward compatibility tests for the agent framework.

These tests ensure that the new agent executor produces identical results
to the existing pipeline when configured equivalently. They must pass
before any agent framework code is merged.

Usage:
    cd pipeline
    python3 -m pytest tests/test_agent_backward_compat.py -v
    # or without pytest:
    python3 tests/test_agent_backward_compat.py
"""

import os
import sys

pipeline_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if pipeline_dir not in sys.path:
    sys.path.insert(0, pipeline_dir)

import yaml

# ---------------------------------------------------------------------------
# Reference values — known-good results from current pipeline
# These MUST NOT change. If they do, the new code has a bug.
# ---------------------------------------------------------------------------

REFERENCE = {
    "route_d": {
        "hdf5": "data/experiment_d_391wp.h5",
        "config": "config/experiment_exp_d.yaml",
        "naive_a": {
            "sim_fuel_mt": 216.57,
            "sim_time_h": 163.00,
            "sws_adj": 73,
        },
        "lp_a": {
            "plan_fuel_mt": 208.91,
            "plan_time_h": 162.99,
            "sim_fuel_mt": 215.60,
            "sim_time_h": 163.43,
            "sws_adj": 64,
        },
        "dp_a": {
            "plan_fuel_mt": 222.60,
            "plan_time_h": 162.51,
            "sim_fuel_mt": 214.24,
            "sim_time_h": 164.53,
            "sws_adj": 161,
        },
        "dp_c": {
            "plan_fuel_mt": 218.79,
            "plan_time_h": 163.00,
            "sim_fuel_mt": 217.28,
            "sim_time_h": 163.03,
            "sws_adj": 15,
        },
        "lp_c": {
            "plan_fuel_mt": 210.84,
            "plan_time_h": 163.00,
            "sim_fuel_mt": 215.56,
            "sim_time_h": 163.43,
            "sws_adj": 51,
        },
        "lp_a_lambda2": {
            "plan_fuel_mt": 191.72,
            "plan_delay_h": 7.83,
            "plan_cost_mt": 207.38,
        },
        "dp_a_lambda2": {
            "plan_fuel_mt": 222.60,
            "plan_delay_h": 0.00,
        },
        "lp_a_lambda0": {
            "plan_fuel_mt": 172.17,
            "plan_delay_h": 21.00,  # approximate (20-22h)
            "sws_all_min": True,    # all segments use SWS=11.0
        },
    },
    "route_b": {
        "hdf5": "data/experiment_b_138wp.h5",
        "config": "config/experiment_exp_b.yaml",
        "lp_a": {
            "plan_fuel_mt": 175.96,
            "plan_time_h": 140.00,
            "sim_fuel_mt": 180.63,
            "sws_adj": 4,
        },
        "dp_a": {
            "plan_fuel_mt": 177.63,
            "plan_time_h": 139.40,
            "sim_fuel_mt": 182.22,
            "sws_adj": 17,
        },
        "dp_c": {
            "plan_fuel_mt": 173.37,
            "plan_time_h": 140.74,
            "sim_fuel_mt": 174.37,
            "sws_adj": 0,
        },
    },
}

# Tolerances
FUEL_TOL = 0.05   # mt
TIME_TOL = 0.05   # hours
COUNT_TOL = 0     # exact match for integer counts


def _load_config(config_rel_path):
    config_path = os.path.join(pipeline_dir, config_rel_path)
    with open(config_path) as f:
        return yaml.safe_load(f)


def _hdf5_path(rel_path):
    return os.path.join(pipeline_dir, rel_path)


def _assert_close(actual, expected, tol, label):
    diff = abs(actual - expected)
    assert diff <= tol, (
        f"{label}: expected {expected}, got {actual}, diff={diff} > tol={tol}"
    )


# ---------------------------------------------------------------------------
# Current pipeline tests (run these FIRST to confirm reference values)
# ---------------------------------------------------------------------------

def test_route_d_lp_a():
    """LP-A on Route D: static LP + simulation with hard ETA."""
    ref = REFERENCE["route_d"]
    config = _load_config(ref["config"])
    hdf5 = _hdf5_path(ref["hdf5"])
    if not os.path.exists(hdf5):
        print(f"  SKIP: {hdf5} not found")
        return False

    from static_det.transform import transform
    from static_det.optimize import optimize
    from shared.simulation import simulate_voyage

    t_out = transform(hdf5, config)
    planned = optimize(t_out, config)
    exp = ref["lp_a"]

    _assert_close(planned["planned_fuel_mt"], exp["plan_fuel_mt"], FUEL_TOL, "LP-A plan fuel")
    _assert_close(planned["planned_time_h"], exp["plan_time_h"], TIME_TOL, "LP-A plan time")
    assert planned.get("planned_delay_h", 0) == 0, "LP-A should have zero delay with hard ETA"

    simulated = simulate_voyage(
        planned["speed_schedule"], hdf5, config,
        sample_hour=config["static_det"]["weather_snapshot"],
    )
    _assert_close(simulated["total_fuel_mt"], exp["sim_fuel_mt"], FUEL_TOL, "LP-A sim fuel")
    assert simulated["sws_adjustments"] == exp["sws_adj"], (
        f"LP-A SWS adj: expected {exp['sws_adj']}, got {simulated['sws_adjustments']}"
    )
    print("  PASS: test_route_d_lp_a")
    return True


def test_route_d_dp_a():
    """DP-A on Route D: static DP + simulation with hard ETA."""
    ref = REFERENCE["route_d"]
    config = _load_config(ref["config"])
    hdf5 = _hdf5_path(ref["hdf5"])
    if not os.path.exists(hdf5):
        print(f"  SKIP: {hdf5} not found")
        return False

    from dynamic_det.transform import transform
    from dynamic_det.optimize import optimize
    from shared.simulation import simulate_voyage

    t_out = transform(hdf5, config)
    planned = optimize(t_out, config)
    exp = ref["dp_a"]

    _assert_close(planned["planned_fuel_mt"], exp["plan_fuel_mt"], FUEL_TOL, "DP-A plan fuel")
    _assert_close(planned["planned_time_h"], exp["plan_time_h"], TIME_TOL, "DP-A plan time")

    simulated = simulate_voyage(
        planned["speed_schedule"], hdf5, config,
        sample_hour=config["dynamic_det"]["forecast_origin"],
    )
    _assert_close(simulated["total_fuel_mt"], exp["sim_fuel_mt"], FUEL_TOL, "DP-A sim fuel")
    assert simulated["sws_adjustments"] == exp["sws_adj"], (
        f"DP-A SWS adj: expected {exp['sws_adj']}, got {simulated['sws_adjustments']}"
    )
    print("  PASS: test_route_d_dp_a")
    return True


def test_route_d_naive_a():
    """Naive-A on Route D: constant speed baseline."""
    ref = REFERENCE["route_d"]
    config = _load_config(ref["config"])
    hdf5 = _hdf5_path(ref["hdf5"])
    if not os.path.exists(hdf5):
        print(f"  SKIP: {hdf5} not found")
        return False

    from compare.sensitivity import run_constant_speed_bound

    result = run_constant_speed_bound(config, hdf5, os.path.join(pipeline_dir, "output"))
    sim = result.get("simulated", result)
    exp = ref["naive_a"]

    _assert_close(sim["total_fuel_mt"], exp["sim_fuel_mt"], FUEL_TOL, "Naive-A sim fuel")
    sim_time = sim.get("total_time_h", sim.get("voyage_time_h", 0))
    _assert_close(sim_time, exp["sim_time_h"], TIME_TOL, "Naive-A sim time")
    print("  PASS: test_route_d_naive_a")
    return True


def test_route_d_dp_c():
    """DP-C on Route D: RH-DP with hard ETA."""
    ref = REFERENCE["route_d"]
    config = _load_config(ref["config"])
    hdf5 = _hdf5_path(ref["hdf5"])
    if not os.path.exists(hdf5):
        print(f"  SKIP: {hdf5} not found")
        return False

    from dynamic_rh.transform import transform
    from dynamic_rh.optimize import optimize
    from shared.simulation import simulate_voyage

    t_out = transform(hdf5, config)
    planned = optimize(t_out, config)
    exp = ref["dp_c"]

    _assert_close(planned["planned_fuel_mt"], exp["plan_fuel_mt"], FUEL_TOL, "DP-C plan fuel")

    simulated = simulate_voyage(
        planned["speed_schedule"], hdf5, config,
        sample_hour=0, time_varying=True,
    )
    _assert_close(simulated["total_fuel_mt"], exp["sim_fuel_mt"], FUEL_TOL, "DP-C sim fuel")
    assert simulated["sws_adjustments"] == exp["sws_adj"], (
        f"DP-C SWS adj: expected {exp['sws_adj']}, got {simulated['sws_adjustments']}"
    )
    print("  PASS: test_route_d_dp_c")
    return True


def test_route_d_lp_c():
    """LP-C on Route D: RH-LP with hard ETA."""
    ref = REFERENCE["route_d"]
    config = _load_config(ref["config"])
    hdf5 = _hdf5_path(ref["hdf5"])
    if not os.path.exists(hdf5):
        print(f"  SKIP: {hdf5} not found")
        return False

    from dynamic_rh.transform import transform
    from dynamic_rh.optimize_lp import optimize
    from shared.simulation import simulate_voyage

    t_out = transform(hdf5, config)
    planned = optimize(t_out, config)
    exp = ref["lp_c"]

    _assert_close(planned["planned_fuel_mt"], exp["plan_fuel_mt"], FUEL_TOL, "LP-C plan fuel")

    simulated = simulate_voyage(
        planned["speed_schedule"], hdf5, config,
        sample_hour=0, time_varying=True,
    )
    _assert_close(simulated["total_fuel_mt"], exp["sim_fuel_mt"], FUEL_TOL, "LP-C sim fuel")
    assert simulated["sws_adjustments"] == exp["sws_adj"], (
        f"LP-C SWS adj: expected {exp['sws_adj']}, got {simulated['sws_adjustments']}"
    )
    print("  PASS: test_route_d_lp_c")
    return True


def test_route_d_lp_lambda2():
    """LP-A with λ=2.0 on Route D: soft ETA."""
    ref = REFERENCE["route_d"]
    config = _load_config(ref["config"])
    config["ship"]["eta_penalty_mt_per_hour"] = 2.0
    hdf5 = _hdf5_path(ref["hdf5"])
    if not os.path.exists(hdf5):
        print(f"  SKIP: {hdf5} not found")
        return False

    from static_det.transform import transform
    from static_det.optimize import optimize

    t_out = transform(hdf5, config)
    planned = optimize(t_out, config)
    exp = ref["lp_a_lambda2"]

    _assert_close(planned["planned_fuel_mt"], exp["plan_fuel_mt"], FUEL_TOL, "LP λ=2 fuel")
    _assert_close(planned["planned_delay_h"], exp["plan_delay_h"], TIME_TOL, "LP λ=2 delay")
    _assert_close(planned["planned_total_cost_mt"], exp["plan_cost_mt"], FUEL_TOL, "LP λ=2 cost")
    assert planned["status"] == "Optimal", f"LP λ=2 should be Optimal, got {planned['status']}"
    print("  PASS: test_route_d_lp_lambda2")
    return True


def test_route_d_lp_lambda0():
    """LP-A with λ=0 on Route D: pure fuel minimization."""
    ref = REFERENCE["route_d"]
    config = _load_config(ref["config"])
    config["ship"]["eta_penalty_mt_per_hour"] = 0.0
    hdf5 = _hdf5_path(ref["hdf5"])
    if not os.path.exists(hdf5):
        print(f"  SKIP: {hdf5} not found")
        return False

    from static_det.transform import transform
    from static_det.optimize import optimize

    t_out = transform(hdf5, config)
    planned = optimize(t_out, config)
    exp = ref["lp_a_lambda0"]

    _assert_close(planned["planned_fuel_mt"], exp["plan_fuel_mt"], FUEL_TOL, "LP λ=0 fuel")
    # All segments should use minimum SWS (11.0)
    sws_values = [s["sws_knots"] for s in planned["speed_schedule"]]
    assert all(s == 11.0 for s in sws_values), (
        f"LP λ=0 should use SWS=11.0 everywhere, got {set(sws_values)}"
    )
    print("  PASS: test_route_d_lp_lambda0")
    return True


# ---------------------------------------------------------------------------
# Placeholder: Agent executor tests (to be filled in Phase 8.2)
# ---------------------------------------------------------------------------

def test_agent_lp_a_matches_current():
    """Agent executor LP-A must match current static LP + simulate_voyage."""
    # TODO: Phase 8.2 — instantiate Agent(plan=LPPlan, policy=Passive, env=Basic)
    #       run execute_voyage(), compare against test_route_d_lp_a reference values
    print("  SKIP: test_agent_lp_a_matches_current (Phase 8.2)")
    return True


def test_agent_dp_a_matches_current():
    """Agent executor DP-A must match current static DP + simulate_voyage."""
    print("  SKIP: test_agent_dp_a_matches_current (Phase 8.2)")
    return True


def test_agent_dp_c_matches_current():
    """Agent executor DP-C must match current RH-DP."""
    print("  SKIP: test_agent_dp_c_matches_current (Phase 8.2)")
    return True


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def run_all():
    tests = [
        test_route_d_naive_a,
        test_route_d_lp_a,
        test_route_d_dp_a,
        test_route_d_dp_c,
        test_route_d_lp_c,
        test_route_d_lp_lambda2,
        test_route_d_lp_lambda0,
        # Agent executor tests (Phase 8.2)
        test_agent_lp_a_matches_current,
        test_agent_dp_a_matches_current,
        test_agent_dp_c_matches_current,
    ]

    print(f"\nRunning {len(tests)} backward compatibility tests...\n")
    passed = 0
    failed = 0
    skipped = 0

    for test in tests:
        try:
            result = test()
            if result:
                passed += 1
            else:
                skipped += 1
        except AssertionError as e:
            print(f"  FAIL: {test.__name__}: {e}")
            failed += 1
        except Exception as e:
            print(f"  ERROR: {test.__name__}: {e}")
            failed += 1

    print(f"\n{'=' * 50}")
    print(f"  Results: {passed} passed, {failed} failed, {skipped} skipped")
    print(f"{'=' * 50}")
    return failed == 0


if __name__ == "__main__":
    success = run_all()
    sys.exit(0 if success else 1)

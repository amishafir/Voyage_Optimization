"""
Static Deterministic optimizer: LP formulation via PuLP (CBC) or Gurobi.

Ported from: Linear programing/ship_speed_optimization_pulp.py
Takes in-memory dict (from transform) instead of parsing .dat file.
"""

import logging
import time

logger = logging.getLogger(__name__)


def _solve_pulp(distances, fcr, sog, sog_lower, sog_upper,
                num_segments, num_speeds, speeds, ETA, lambda_val=None):
    """Solve with PuLP CBC.

    If lambda_val is a finite number, ETA becomes a soft constraint:
      minimize fuel + lambda_val * max(0, voyage_time - ETA)
    If lambda_val is None or inf, ETA is a hard constraint (original behavior).
    """
    import pulp

    soft_eta = lambda_val is not None and lambda_val != float("inf")

    prob = pulp.LpProblem("StaticDet_SpeedOptimization", pulp.LpMinimize)

    x = {}
    for i in range(num_segments):
        for k in range(num_speeds):
            x[i, k] = pulp.LpVariable(f"x_{i}_{k}", cat="Binary")

    fuel_expr = pulp.lpSum(
        distances[i] * fcr[k] / sog[i][k] * x[i, k]
        for i in range(num_segments)
        for k in range(num_speeds)
        if sog[i][k] > 0
    )

    time_expr = pulp.lpSum(
        distances[i] / sog[i][k] * x[i, k]
        for i in range(num_segments)
        for k in range(num_speeds)
        if sog[i][k] > 0
    )

    if soft_eta:
        delta = pulp.LpVariable("delay", lowBound=0)
        prob += delta >= time_expr - ETA, "delay_definition"
        prob += fuel_expr + lambda_val * delta
    else:
        prob += fuel_expr
        prob += (time_expr <= ETA, "ETA_constraint")

    for i in range(num_segments):
        prob += (
            pulp.lpSum(x[i, k] for k in range(num_speeds)) == 1,
            f"one_speed_{i}",
        )

    for i in range(num_segments):
        sog_expr = pulp.lpSum(sog[i][k] * x[i, k] for k in range(num_speeds))
        prob += sog_expr >= sog_lower[i], f"sog_lb_{i}"
        prob += sog_expr <= sog_upper[i], f"sog_ub_{i}"

    start = time.time()
    solver = pulp.PULP_CBC_CMD(msg=False)
    prob.solve(solver)
    elapsed = time.time() - start

    status = pulp.LpStatus[prob.status]
    optimal = prob.status == pulp.constants.LpStatusOptimal

    # Extract selected speed per segment
    selected = {}
    delay_hours = 0.0
    if optimal:
        for i in range(num_segments):
            for k in range(num_speeds):
                if pulp.value(x[i, k]) is not None and pulp.value(x[i, k]) > 0.5:
                    selected[i] = k
                    break
        if soft_eta:
            delay_hours = max(0.0, pulp.value(delta) or 0.0)

    return status, optimal, elapsed, selected, delay_hours


def _solve_gurobi(distances, fcr, sog, sog_lower, sog_upper,
                   num_segments, num_speeds, speeds, ETA, lambda_val=None):
    """Solve with Gurobi.

    If lambda_val is a finite number, ETA becomes a soft constraint:
      minimize fuel + lambda_val * max(0, voyage_time - ETA)
    If lambda_val is None or inf, ETA is a hard constraint (original behavior).
    """
    import gurobipy as gp
    from gurobipy import GRB

    soft_eta = lambda_val is not None and lambda_val != float("inf")

    m = gp.Model("StaticDet_SpeedOptimization")
    m.Params.OutputFlag = 0  # suppress output

    # Binary decision variables
    x = m.addVars(num_segments, num_speeds, vtype=GRB.BINARY, name="x")

    fuel_expr = gp.quicksum(
        distances[i] * fcr[k] / sog[i][k] * x[i, k]
        for i in range(num_segments)
        for k in range(num_speeds)
        if sog[i][k] > 0
    )

    time_expr = gp.quicksum(
        distances[i] / sog[i][k] * x[i, k]
        for i in range(num_segments)
        for k in range(num_speeds)
        if sog[i][k] > 0
    )

    if soft_eta:
        delta = m.addVar(name="delay", lb=0.0)
        m.addConstr(delta >= time_expr - ETA, "delay_definition")
        m.setObjective(fuel_expr + lambda_val * delta, GRB.MINIMIZE)
    else:
        m.setObjective(fuel_expr, GRB.MINIMIZE)
        m.addConstr(time_expr <= ETA, "ETA")

    # One speed per segment
    for i in range(num_segments):
        m.addConstr(
            gp.quicksum(x[i, k] for k in range(num_speeds)) == 1,
            f"one_speed_{i}",
        )

    # SOG bounds
    for i in range(num_segments):
        sog_expr = gp.quicksum(sog[i][k] * x[i, k] for k in range(num_speeds))
        m.addConstr(sog_expr >= sog_lower[i], f"sog_lb_{i}")
        m.addConstr(sog_expr <= sog_upper[i], f"sog_ub_{i}")

    start = time.time()
    m.optimize()
    elapsed = time.time() - start

    status_map = {
        GRB.OPTIMAL: "Optimal",
        GRB.INFEASIBLE: "Infeasible",
        GRB.UNBOUNDED: "Unbounded",
    }
    status = status_map.get(m.status, f"GurobiStatus_{m.status}")
    optimal = m.status == GRB.OPTIMAL

    selected = {}
    delay_hours = 0.0
    if optimal:
        for i in range(num_segments):
            for k in range(num_speeds):
                if x[i, k].X > 0.5:
                    selected[i] = k
                    break
        if soft_eta:
            delay_hours = max(0.0, delta.X)

    return status, optimal, elapsed, selected, delay_hours


def optimize(transform_output: dict, config: dict) -> dict:
    """Solve the ship speed optimization LP.

    Args:
        transform_output: Dict from transform.transform().
        config: Full experiment config.

    Returns:
        Dict with: status, planned_fuel_mt, planned_time_h,
        speed_schedule (list of 12 dicts), computation_time_s.
    """
    ETA = transform_output["ETA"]
    num_segments = transform_output["num_segments"]
    num_speeds = transform_output["num_speeds"]
    distances = transform_output["distances"]
    speeds = transform_output["speeds"]
    fcr = transform_output["fcr"]
    sog = transform_output["sog_matrix"]
    sog_lower = transform_output["sog_lower"]
    sog_upper = transform_output["sog_upper"]

    solver_name = config.get("static_det", {}).get("optimizer", "pulp")
    lambda_val = config.get("ship", {}).get("eta_penalty_mt_per_hour", None)

    logger.info("LP: %d segments x %d speeds = %d vars, ETA=%.0f h, solver=%s, λ=%s",
                num_segments, num_speeds, num_segments * num_speeds, ETA, solver_name,
                lambda_val)

    solve_args = (distances, fcr, sog, sog_lower, sog_upper,
                  num_segments, num_speeds, speeds, ETA, lambda_val)

    if solver_name == "gurobi":
        status, optimal, elapsed, selected, delay_hours = _solve_gurobi(*solve_args)
    else:
        status, optimal, elapsed, selected, delay_hours = _solve_pulp(*solve_args)

    logger.info("LP status: %s  (%.4f s, solver=%s)", status, elapsed, solver_name)

    if not optimal:
        if lambda_val is not None and lambda_val != float("inf"):
            # Soft constraint should always be feasible — something is wrong
            logger.error("LP %s with soft ETA (λ=%s) — unexpected infeasibility",
                         status, lambda_val)
            return {
                "status": status,
                "computation_time_s": elapsed,
                "solver": solver_name,
            }
        # Hard ETA fallback: use minimum SWS (index 0) for all segments
        logger.warning("LP %s — falling back to min-SWS plan (soft-ETA)", status)
        selected = {i: 0 for i in range(num_segments)}
        delay_hours = 0.0
        status = "ETA_relaxed"

    # ------------------------------------------------------------------
    # Extract solution
    # ------------------------------------------------------------------
    total_fuel = 0.0
    total_time = 0.0
    schedule = []

    for i in range(num_segments):
        k = selected[i]
        seg_sog = sog[i][k]
        seg_time = distances[i] / seg_sog
        seg_fuel = distances[i] * fcr[k] / seg_sog
        total_fuel += seg_fuel
        total_time += seg_time
        schedule.append({
            "segment": i,
            "sws_knots": speeds[k],
            "sog_knots": seg_sog,
            "distance_nm": distances[i],
            "time_h": seg_time,
            "fuel_mt": seg_fuel,
            "fcr_mt_h": fcr[k],
        })

    result = {
        "status": status,
        "planned_fuel_mt": total_fuel,
        "planned_time_h": total_time,
        "planned_delay_h": delay_hours,
        "speed_schedule": schedule,
        "computation_time_s": elapsed,
        "solver": solver_name,
    }

    # Total cost = fuel + λ * delay (for soft ETA)
    if lambda_val is not None and lambda_val != float("inf"):
        result["planned_total_cost_mt"] = total_fuel + lambda_val * delay_hours
    else:
        result["planned_total_cost_mt"] = total_fuel

    return result

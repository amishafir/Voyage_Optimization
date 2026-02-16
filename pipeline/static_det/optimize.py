"""
Static Deterministic optimizer: LP formulation via PuLP.

Ported from: Linear programing/ship_speed_optimization_pulp.py
Takes in-memory dict (from transform) instead of parsing .dat file.
"""

import logging
import time

import pulp

logger = logging.getLogger(__name__)


def optimize(transform_output: dict, config: dict) -> dict:
    """Solve the ship speed optimization LP.

    Args:
        transform_output: Dict from transform.transform().
        config: Full experiment config.

    Returns:
        Dict with: status, planned_fuel_kg, planned_time_h,
        speed_schedule (list of 12 dicts), computation_time_s.
    """
    ETA = transform_output["ETA"]
    num_segments = transform_output["num_segments"]
    num_speeds = transform_output["num_speeds"]
    distances = transform_output["distances"]
    speeds = transform_output["speeds"]
    fcr = transform_output["fcr"]
    sog = transform_output["sog_matrix"]  # [seg][spd]
    sog_lower = transform_output["sog_lower"]
    sog_upper = transform_output["sog_upper"]

    # ------------------------------------------------------------------
    # Create LP problem
    # ------------------------------------------------------------------
    prob = pulp.LpProblem("StaticDet_SpeedOptimization", pulp.LpMinimize)

    # Binary decision variables: x[i,k] = 1 if segment i uses speed k
    x = {}
    for i in range(num_segments):
        for k in range(num_speeds):
            x[i, k] = pulp.LpVariable(f"x_{i}_{k}", cat="Binary")

    # ------------------------------------------------------------------
    # Objective: minimize total fuel  =  sum  l[i] * FCR[k] / SOG[i][k] * x[i,k]
    # ------------------------------------------------------------------
    prob += pulp.lpSum(
        distances[i] * fcr[k] / sog[i][k] * x[i, k]
        for i in range(num_segments)
        for k in range(num_speeds)
        if sog[i][k] > 0
    )

    # ------------------------------------------------------------------
    # Constraint 1: ETA — total travel time <= ETA
    # ------------------------------------------------------------------
    prob += (
        pulp.lpSum(
            distances[i] / sog[i][k] * x[i, k]
            for i in range(num_segments)
            for k in range(num_speeds)
            if sog[i][k] > 0
        )
        <= ETA,
        "ETA_constraint",
    )

    # ------------------------------------------------------------------
    # Constraint 2: exactly one speed per segment
    # ------------------------------------------------------------------
    for i in range(num_segments):
        prob += (
            pulp.lpSum(x[i, k] for k in range(num_speeds)) == 1,
            f"one_speed_{i}",
        )

    # ------------------------------------------------------------------
    # Constraint 3: SOG bounds per segment
    # ------------------------------------------------------------------
    for i in range(num_segments):
        sog_expr = pulp.lpSum(sog[i][k] * x[i, k] for k in range(num_speeds))
        prob += sog_expr >= sog_lower[i], f"sog_lb_{i}"
        prob += sog_expr <= sog_upper[i], f"sog_ub_{i}"

    # ------------------------------------------------------------------
    # Solve
    # ------------------------------------------------------------------
    logger.info("LP: %d segments x %d speeds = %d vars, ETA=%.0f h",
                num_segments, num_speeds, num_segments * num_speeds, ETA)

    start = time.time()
    solver = pulp.PULP_CBC_CMD(msg=False)
    prob.solve(solver)
    elapsed = time.time() - start

    status = pulp.LpStatus[prob.status]
    logger.info("LP status: %s  (%.2f s)", status, elapsed)

    if prob.status != pulp.constants.LpStatusOptimal:
        return {"status": status, "computation_time_s": elapsed}

    # ------------------------------------------------------------------
    # Extract solution
    # ------------------------------------------------------------------
    total_fuel = 0.0
    total_time = 0.0
    schedule = []

    for i in range(num_segments):
        for k in range(num_speeds):
            if pulp.value(x[i, k]) is not None and pulp.value(x[i, k]) > 0.5:
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
                    "fuel_kg": seg_fuel,
                    "fcr_kg_h": fcr[k],
                })
                break

    return {
        "status": status,
        "planned_fuel_kg": total_fuel,
        "planned_time_h": total_time,
        "speed_schedule": schedule,
        "computation_time_s": elapsed,
    }

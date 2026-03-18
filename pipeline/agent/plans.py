"""Optimization plans — each produces a speed schedule from a static problem.

All plans share the same interface:
    plan.optimize(route_data, weather_data, eta, lambda_val, config) -> dict

Plans are STATELESS — they solve a one-shot problem when called.
They know nothing about voyage execution or re-planning.
"""

import logging
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


class Plan(ABC):
    """Base class for optimization plans."""

    @abstractmethod
    def optimize(self, transform_output: dict, config: dict) -> dict:
        """Solve the optimization problem.

        Args:
            transform_output: Route + weather data (from transform step).
            config: Full experiment config.

        Returns:
            Dict with at minimum: status, planned_fuel_mt, planned_time_h,
            planned_delay_h, speed_schedule.
        """

    @property
    @abstractmethod
    def name(self) -> str:
        """Short name for logging/display."""


class NaivePlan(Plan):
    """Constant SOG = total_distance / ETA at every leg."""

    @property
    def name(self) -> str:
        return "naive"

    def optimize(self, transform_output: dict, config: dict) -> dict:
        eta = transform_output["ETA"]

        # Works for both segment-level (LP transform) and node-level (DP transform)
        distances = transform_output["distances"]
        total_dist = sum(distances)
        constant_sog = total_dist / eta

        # Use middle speed as SWS reference (actual SWS determined at execution)
        speeds = transform_output.get("speeds", [12.0])
        mid_sws = speeds[len(speeds) // 2]

        schedule = []
        for i, dist in enumerate(distances):
            leg_time = dist / constant_sog
            schedule.append({
                "leg": i,
                "sws_knots": mid_sws,
                "sog_knots": constant_sog,
                "distance_nm": dist,
                "time_h": leg_time,
            })

        return {
            "status": "Optimal",
            "planned_fuel_mt": 0.0,  # naive doesn't compute fuel at plan time
            "planned_time_h": eta,
            "planned_delay_h": 0.0,
            "planned_total_cost_mt": 0.0,
            "speed_schedule": schedule,
            "computation_time_s": 0.0,
            "solver": "naive_constant_sog",
        }


class LPPlan(Plan):
    """LP optimizer (PuLP/Gurobi) over segments."""

    @property
    def name(self) -> str:
        return "lp"

    def optimize(self, transform_output: dict, config: dict) -> dict:
        from static_det.optimize import optimize
        return optimize(transform_output, config)


class DPPlan(Plan):
    """Forward Bellman DP over per-node graph."""

    @property
    def name(self) -> str:
        return "dp"

    def optimize(self, transform_output: dict, config: dict) -> dict:
        from dynamic_det.optimize import optimize
        return optimize(transform_output, config)

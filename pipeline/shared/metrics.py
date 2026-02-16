"""
Result metrics, JSON builder, and persistence.

Implements the output contract from docs/WBS_next_phases.md Section 7.
"""

import json
import logging
import os
from datetime import datetime

logger = logging.getLogger(__name__)


def compute_result_metrics(
    planned: dict, simulated: dict, total_distance_nm: float
) -> dict:
    """Compute comparison metrics between planned and simulated results.

    Args:
        planned:           Dict with planned_fuel_kg, planned_time_h.
        simulated:         Dict with total_fuel_kg, total_time_h.
        total_distance_nm: Total route distance.

    Returns:
        Dict with fuel_gap_percent, fuel_per_nm, avg_sog_knots.
    """
    planned_fuel = planned["planned_fuel_kg"]
    sim_fuel = simulated["total_fuel_kg"]

    fuel_gap_pct = 0.0
    if planned_fuel > 0:
        fuel_gap_pct = (sim_fuel - planned_fuel) / planned_fuel * 100

    fuel_per_nm = sim_fuel / total_distance_nm if total_distance_nm > 0 else 0.0

    sim_time = simulated["total_time_h"]
    avg_sog = total_distance_nm / sim_time if sim_time > 0 else 0.0

    return {
        "fuel_gap_percent": round(fuel_gap_pct, 4),
        "fuel_per_nm": round(fuel_per_nm, 6),
        "avg_sog_knots": round(avg_sog, 4),
    }


def build_result_json(
    approach: str,
    config: dict,
    planned: dict,
    simulated: dict,
    metrics: dict,
    time_series_file: str = "",
) -> dict:
    """Build the full result JSON matching the output contract.

    Args:
        approach:         String identifier (e.g. "static_det").
        config:           Full experiment config.
        planned:          Dict from optimize().
        simulated:        Dict from simulate_voyage().
        metrics:          Dict from compute_result_metrics().
        time_series_file: Path to per-waypoint CSV.

    Returns:
        Complete result dict ready for JSON serialization.
    """
    return {
        "approach": approach,
        "created_at": datetime.now().isoformat(),
        "config_snapshot": {
            "ship": config.get("ship", {}),
            approach: config.get(approach, {}),
        },
        "planned": {
            "total_fuel_kg": round(planned["planned_fuel_kg"], 4),
            "voyage_time_h": round(planned["planned_time_h"], 4),
            "speed_schedule": planned.get("speed_schedule", []),
            "computation_time_s": round(planned.get("computation_time_s", 0), 4),
            "solver_status": planned.get("status", "unknown"),
        },
        "simulated": {
            "total_fuel_kg": round(simulated["total_fuel_kg"], 4),
            "voyage_time_h": round(simulated["total_time_h"], 4),
            "arrival_deviation_h": round(simulated["arrival_deviation_h"], 4),
            "speed_changes": simulated.get("speed_changes", 0),
            "co2_emissions_kg": round(simulated["co2_emissions_kg"], 4),
        },
        "metrics": metrics,
        "time_series_file": time_series_file,
    }


def save_result(result: dict, path: str) -> None:
    """Write result dict to JSON file.

    Creates parent directories if needed.
    """
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w") as f:
        json.dump(result, f, indent=2, default=str)
    logger.info("Saved result JSON: %s", path)

"""Weather assembly for the 3-agent cycle executor.

Each function builds a weather_grid dict in DP format:
    weather_grid[node_id][forecast_hour] -> {6 weather fields}

The three agents differ only in what weather they provide to the optimizer:
    - Naive: None (no weather)
    - Deterministic: actual observations at all waypoints, treated as constant
    - Stochastic: actuals for current 6h window, forecast beyond
"""

import logging
import math

logger = logging.getLogger(__name__)

WEATHER_FIELDS = [
    "wind_speed_10m_kmh", "wind_direction_10m_deg", "beaufort_number",
    "wave_height_m", "ocean_current_velocity_kmh", "ocean_current_direction_deg",
]


def assemble_naive():
    """Naive agent uses no weather. Returns None."""
    return None, 0


def assemble_deterministic(actual_weather, sample_hour, node_ids,
                           max_forecast_hour_needed):
    """Build weather grid from actual observations, treated as constant.

    At re-plan hour H, the deterministic agent sees actual weather at ALL
    waypoints and assumes these values hold for the entire remaining voyage.

    Args:
        actual_weather: Pre-loaded dict {sample_hour: {node_id: weather_dict}}
        sample_hour: Which actual snapshot to use (NWP-aligned)
        node_ids: List of node IDs that need weather
        max_forecast_hour_needed: How many forecast hours the DP needs
            (ceil of remaining_eta)

    Returns:
        (weather_grid, max_forecast_hour) tuple
    """
    actual_grid = actual_weather.get(sample_hour, {})
    if not actual_grid:
        # Fallback: pick closest available
        available = sorted(actual_weather.keys())
        if available:
            closest = min(available, key=lambda s: abs(s - sample_hour))
            actual_grid = actual_weather[closest]
            logger.warning("Det: no actual at SH=%d, using SH=%d", sample_hour, closest)
        else:
            logger.error("Det: no actual weather available at all")
            return {}, 0

    max_fh = int(math.ceil(max_forecast_hour_needed))
    weather_grid = {}

    for nid in node_ids:
        wx = actual_grid.get(nid)
        if wx is None:
            continue
        # Same actual weather at every forecast hour (constant assumption)
        weather_grid[nid] = {fh: wx for fh in range(max_fh + 1)}

    logger.info("Det weather: SH=%d, %d nodes, fh=0..%d (constant)",
                sample_hour, len(weather_grid), max_fh)
    return weather_grid, max_fh


def assemble_stochastic(actual_weather, predicted_grids, max_forecast_hours,
                        sample_hour, node_ids, elapsed_time, replan_freq):
    """Build weather grid: actuals for current 6h, forecast beyond.

    For forecast hours within [elapsed_time, elapsed_time + replan_freq]:
        Use per-waypoint actual observations (same as deterministic).
    For forecast hours beyond elapsed_time + replan_freq:
        Use predicted weather from freshest forecast at sample_hour.

    Args:
        actual_weather: Pre-loaded dict {sample_hour: {node_id: weather_dict}}
        predicted_grids: Pre-loaded dict {sample_hour: {node_id: {fh: weather_dict}}}
        max_forecast_hours: Dict {sample_hour: max_fh} for predicted data
        sample_hour: Which forecast/actual snapshot to use (NWP-aligned)
        node_ids: List of node IDs that need weather
        elapsed_time: Hours elapsed since departure
        replan_freq: Re-plan frequency in hours (6)

    Returns:
        (weather_grid, max_forecast_hour) tuple
    """
    # Get the predicted grid for this sample hour
    pred_grid = predicted_grids.get(sample_hour, {})
    if not pred_grid:
        available = sorted(predicted_grids.keys())
        if available:
            closest = min(available, key=lambda s: abs(s - sample_hour))
            pred_grid = predicted_grids[closest]
            sample_hour = closest
            logger.warning("Stoch: no predicted at SH=%d, using SH=%d",
                           sample_hour, closest)

    max_fh = max_forecast_hours.get(sample_hour, 0)

    # Start with forecast data (deep copy to avoid mutation)
    weather_grid = {}
    for nid in node_ids:
        if nid in pred_grid:
            weather_grid[nid] = dict(pred_grid[nid])
        else:
            weather_grid[nid] = {}

    # Inject actual weather for the committed window [elapsed, elapsed+replan_freq]
    actual_grid = actual_weather.get(sample_hour, {})
    if not actual_grid:
        available_actual = sorted(actual_weather.keys())
        if available_actual:
            closest = min(available_actual, key=lambda s: abs(s - sample_hour))
            actual_grid = actual_weather[closest]

    fh_start = int(round(elapsed_time))
    fh_end = int(round(elapsed_time + replan_freq))
    injected = 0

    for fh in range(fh_start, min(fh_end, max_fh) + 1):
        for nid in node_ids:
            if nid in actual_grid:
                weather_grid.setdefault(nid, {})[fh] = actual_grid[nid]
                injected += 1

    logger.info("Stoch weather: SH=%d, %d nodes, max_fh=%d, "
                "actual injected for fh=[%d,%d] (%d entries)",
                sample_hour, len(weather_grid), max_fh,
                fh_start, min(fh_end, max_fh), injected)
    return weather_grid, max_fh

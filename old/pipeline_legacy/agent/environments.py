"""Environments — define agent capabilities during a voyage.

Each environment answers: can the agent compute? Can it communicate?
And provides weather data access appropriate to its tier.
"""

import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class BasicEnvironment:
    """No compute, no communication. Agent follows original plan only.

    Weather access: initial forecast loaded at departure (used for planning only).
    During execution, the agent cannot re-plan.
    """

    can_compute = False
    can_communicate = False

    def get_forecast(self, time_h: float, hdf5_path: str, config: dict) -> Optional[Dict]:
        """Basic environment cannot fetch forecasts during voyage."""
        return None


class MidEnvironment:
    """Compute available, no communication. Agent can re-plan with stale forecast.

    Weather access: the forecast loaded at departure (sample_hour=0).
    On re-plan, the optimizer uses this stale forecast for remaining legs.
    """

    can_compute = True
    can_communicate = False

    def __init__(self):
        self._cached_transform = None

    def cache_initial_transform(self, transform_output: dict):
        """Cache the departure-time transform data for re-use during re-planning."""
        self._cached_transform = transform_output

    def get_forecast(self, time_h: float, hdf5_path: str, config: dict) -> Optional[Dict]:
        """Return the stale (departure) forecast data."""
        return self._cached_transform


class ConnectedEnvironment:
    """Compute + communication. Agent can re-plan with fresh forecast.

    Weather access: downloads fresh forecast at the sample_hour closest to
    the current voyage time. Uses the HDF5 multi-sample-hour data.
    """

    can_compute = True
    can_communicate = True

    def __init__(self):
        self._weather_grids = None
        self._max_forecast_hours = None
        self._available_sample_hours = None
        self._actual_weather = None
        self._available_actual_hours = None

    def load_all_forecasts(self, transform_output: dict):
        """Load all available forecasts from the RH transform output.

        This pre-loads all sample hours so get_forecast() can pick
        the freshest one at any point during the voyage.
        """
        self._weather_grids = transform_output.get("weather_grids", {})
        self._max_forecast_hours = transform_output.get("max_forecast_hours", {})
        self._available_sample_hours = transform_output.get("available_sample_hours", [0])
        self._actual_weather = transform_output.get("actual_weather", {})
        self._available_actual_hours = transform_output.get("available_actual_hours", [])

    def get_forecast(self, time_h: float, hdf5_path: str, config: dict) -> Optional[Dict]:
        """Return the freshest available forecast for the given voyage time.

        Picks the largest sample_hour <= time_h from available forecasts.
        """
        if not self._available_sample_hours:
            return None

        elapsed_int = int(time_h)
        candidates = [s for s in self._available_sample_hours if s <= elapsed_int]
        sample_hour = max(candidates) if candidates else self._available_sample_hours[0]

        return {
            "weather_grid": self._weather_grids.get(sample_hour, {}),
            "max_forecast_hour": self._max_forecast_hours.get(sample_hour, 0),
            "sample_hour": sample_hour,
            "actual_weather": self._actual_weather,
            "available_actual_hours": self._available_actual_hours,
        }

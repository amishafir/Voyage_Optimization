"""Measurement system — wraps shared/physics.py with forward/inverse interface."""

import math
from typing import Dict, Tuple

from shared.physics import (
    calculate_speed_over_ground,
    calculate_fuel_consumption_rate,
    calculate_sws_from_sog,
    load_ship_parameters,
)
from agent.spec import ShipSpec


class Measurement:
    """Translates between control input (SWS) and outcomes (SOG, fuel).

    Fixed for this thesis: Holtrop-Mennen resistance + Isherwood wind coefficients.
    """

    def __init__(self, spec: ShipSpec, config: dict):
        self._spec = spec
        self._ship_params = load_ship_parameters(config)

    def forward(
        self,
        sws: float,
        weather: Dict,
        heading_rad: float,
    ) -> Tuple[float, float]:
        """SWS → (SOG, FCR).

        Args:
            sws: Still Water Speed in knots.
            weather: Dict with 6 weather fields.
            heading_rad: Ship heading in radians.

        Returns:
            (sog_knots, fcr_mt_per_hour)
        """
        wind_dir_rad = math.radians(weather.get("wind_direction_10m_deg", 0.0))
        current_knots = weather.get("ocean_current_velocity_kmh", 0.0) / 1.852
        current_dir_rad = math.radians(weather.get("ocean_current_direction_deg", 0.0))
        beaufort = int(round(weather.get("beaufort_number", 0)))
        wave_height = weather.get("wave_height_m", 0.0)

        # Handle NaN
        if math.isnan(current_knots):
            current_knots = 0.0
        if math.isnan(wave_height):
            wave_height = 0.0
        if math.isnan(beaufort) or beaufort < 0:
            beaufort = 0

        sog = calculate_speed_over_ground(
            ship_speed=sws,
            ocean_current=current_knots,
            current_direction=current_dir_rad,
            ship_heading=heading_rad,
            wind_direction=wind_dir_rad,
            beaufort_scale=beaufort,
            wave_height=wave_height,
            ship_parameters=self._ship_params,
        )
        sog = max(sog, 0.1)
        fcr = calculate_fuel_consumption_rate(sws)
        return sog, fcr

    def inverse(
        self,
        target_sog: float,
        weather: Dict,
        heading_deg: float,
    ) -> float:
        """SOG → required SWS.

        Args:
            target_sog: Desired Speed Over Ground in knots.
            weather: Dict with 6 weather fields.
            heading_deg: Ship heading in degrees.

        Returns:
            Required SWS in knots (may be outside speed_range).
        """
        return calculate_sws_from_sog(
            target_sog=target_sog,
            weather=weather,
            ship_heading_deg=heading_deg,
            ship_parameters=self._ship_params,
        )

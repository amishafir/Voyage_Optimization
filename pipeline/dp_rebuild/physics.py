"""
Physics surface — mirrors ``pipeline/dp_cpp/src/physics.{cpp,hpp}``.

Thin re-export shim over ``pipeline/shared/physics.py`` so this module owns
its public API in the same way the C++ side does. The actual implementations
of the paper's Eqs 7–16 live in the shared module and are unchanged.

Public surface (matches ``physics.hpp``):

* ``calculate_speed_over_ground``
* ``calculate_sws_from_sog``
* ``calculate_fuel_consumption_rate``
* ``calculate_weather_direction_angle``
* ``calculate_froude_number``
* ``calculate_direction_reduction_coefficient`` (Cβ)
* ``calculate_speed_reduction_coefficient`` (CU)
* ``calculate_ship_form_coefficient`` (CForm)
* ``calculate_speed_loss_percentage``
* ``calculate_weather_corrected_speed``
* ``calculate_sog_vector_synthesis``
* Physical constants (``GRAVITY``, ``WATER_DENSITY``, …) — when needed

The Beaufort lookup lives in ``shared.beaufort.wind_speed_to_beaufort``; we
re-export it here too so callers don't need both imports.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Make ``pipeline/shared/`` importable regardless of CWD.
_PIPELINE_ROOT = Path(__file__).resolve().parent.parent
if str(_PIPELINE_ROOT) not in sys.path:
    sys.path.insert(0, str(_PIPELINE_ROOT))

from shared.beaufort import wind_speed_to_beaufort  # noqa: F401, E402
from shared.physics import (  # noqa: F401, E402
    # Top-level model
    calculate_speed_over_ground,
    calculate_sws_from_sog,
    calculate_fuel_consumption_rate,
    # Paper Eqs 7–16 building blocks
    calculate_weather_direction_angle,
    calculate_froude_number,
    calculate_direction_reduction_coefficient,
    calculate_speed_reduction_coefficient,
    calculate_ship_form_coefficient,
    calculate_speed_loss_percentage,
    calculate_weather_corrected_speed,
    calculate_sog_vector_synthesis,
    # Utility
    calculate_travel_time,
    calculate_ship_heading,
    load_ship_parameters,
)

# Physical constants — mirror the values in physics.hpp.
GRAVITY: float            = 9.81
WATER_DENSITY: float      = 1025.0
AIR_DENSITY: float        = 1.225
KINEMATIC_VISCOSITY: float = 1.19e-6
CO2_FACTOR: float         = 3.17
KNOTS_TO_MS: float        = 0.5144
MS_TO_KNOTS: float        = 1.944

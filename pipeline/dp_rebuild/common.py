"""
Common types — mirrors ``pipeline/dp_cpp/src/common.hpp``.

* ``TDKey`` — `(time, distance)` rounded to 9 decimals for exact hash-equality.
  Same precision as the C++ side; safe range t < 1000 h.
* ``ShipParameters`` — frozen dataclass of vessel constants
  (200 m length, 32 m beam, 12 m draft, 10 000 kW, Cb 0.75) matching the
  ``ShipParameters`` struct in ``common.hpp``.
* ``WeatherDict`` — alias for ``Dict[str, float]`` (the C++ side uses
  ``std::unordered_map<std::string, double>``).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict


WeatherDict = Dict[str, float]


@dataclass(frozen=True)
class ShipParameters:
    """Vessel constants. Defaults match ``ShipParameters`` in ``common.hpp``."""
    length: float           = 200.0
    beam: float             = 32.0
    draft: float            = 12.0
    displacement: float     = 50000.0     # tonnes
    block_coefficient: float = 0.75
    wetted_surface: float   = 8000.0
    rated_power: float      = 10000.0     # kW
    max_speed: float        = 14.0
    min_speed: float        = 8.0


# ----------------------------------------------------------------------
# Time-distance keys for graph node deduplication
# ----------------------------------------------------------------------

_KEY_PRECISION = 9


def make_td_key(t: float, d: float) -> tuple[float, float]:
    """Round (t, d) to 9 decimal places for hashing.

    Mirrors the C++ ``TDKey`` whose two int64 members are
    ``llround(t * 1e9)`` / ``llround(d * 1e9)``. Python tuples of rounded
    floats serve the same purpose.
    """
    return (round(t, _KEY_PRECISION), round(d, _KEY_PRECISION))

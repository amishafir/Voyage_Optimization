"""
Rhumb-line (loxodrome) geometry for one leg of the route.

Between two consecutive waypoints the vessel holds a constant compass
bearing, so each leg is a rhumb line. Earth is a sphere on which one degree
of latitude is exactly 60 NM, the convention used throughout the project.

A position on a leg is addressed by the fraction f in [0, 1] of the leg's
length, so the distance from the leg start is exactly f * length_nm. Along a
rhumb line the latitude is linear in distance, and the longitude is linear
in the Mercator ordinate psi(lat) = ln(tan(pi/4 + lat/2)):

    lat(f) = lat1 + f * dlat
    lon(f) = lon1 + dlon * (psi(lat(f)) - psi(lat1)) / dpsi

On an east-west leg (dlat = 0) the longitude is linear in f instead.
"""

from __future__ import annotations

import math
from typing import Tuple

NM_PER_DEG_LAT = 60.0
R_EARTH_NM = NM_PER_DEG_LAT * 180.0 / math.pi

# Mercator psi is singular at the poles; legs must stay inside this band.
MAX_ABS_LAT_DEG = 89.5

# A leg whose latitude changes by less than this (about 0.1 m) is treated as
# east-west, which keeps fraction_at_lon well conditioned.
_EW_TOL_DEG = 1e-6


def normalize_dlon(dlon_deg: float) -> float:
    """Longitude difference mapped to (-180, 180], the short way round."""
    dlon = (dlon_deg + 180.0) % 360.0 - 180.0
    return 180.0 if dlon == -180.0 else dlon


def wrap_lon(lon_deg: float) -> float:
    """Longitude mapped to [-180, 180)."""
    return (lon_deg + 180.0) % 360.0 - 180.0


def mercator_psi(lat_deg: float) -> float:
    """Mercator ordinate psi(lat) in radians."""
    return math.log(math.tan(math.pi / 4.0 + math.radians(lat_deg) / 2.0))


def inverse_mercator_psi(psi: float) -> float:
    """Latitude (deg) whose Mercator ordinate is psi."""
    return math.degrees(2.0 * math.atan(math.exp(psi)) - math.pi / 2.0)


class RhumbLeg:
    """The rhumb line from (lat1, lon1) to (lat2, lon2), taken the short way
    round in longitude (so legs across the antimeridian work)."""

    def __init__(self, lat1: float, lon1: float, lat2: float, lon2: float):
        for lat in (lat1, lat2):
            if abs(lat) > MAX_ABS_LAT_DEG:
                raise ValueError(f"latitude {lat} outside +-{MAX_ABS_LAT_DEG} deg")
        self.lat1, self.lon1 = float(lat1), float(lon1)
        self.lat2, self.lon2 = float(lat2), float(lon2)
        self.dlat = self.lat2 - self.lat1
        self.dlon = normalize_dlon(self.lon2 - self.lon1)
        # End longitude unwrapped so that lon runs monotonically lon1 -> lon1_end.
        self.lon2_unwrapped = self.lon1 + self.dlon
        self.is_east_west = abs(self.dlat) < _EW_TOL_DEG
        self._psi1 = mercator_psi(self.lat1)
        self._dpsi = mercator_psi(self.lat2) - self._psi1

        if self.is_east_west:
            self.length_nm = (abs(self.dlon) * NM_PER_DEG_LAT
                              * math.cos(math.radians(self.lat1)))
        else:
            # ds = R * dphi / cos(bearing), with tan(bearing) = dlambda / dpsi.
            q = math.radians(self.dlat) / self._dpsi
            self.length_nm = R_EARTH_NM * math.hypot(
                math.radians(self.dlat), q * math.radians(self.dlon))

        if self.is_east_west:
            self.bearing_deg = 90.0 if self.dlon > 0 else 270.0
        else:
            self.bearing_deg = math.degrees(
                math.atan2(math.radians(self.dlon), self._dpsi)) % 360.0

    def lon_unwrapped_at(self, f: float) -> float:
        """Longitude at fraction f, continuous along the leg (not wrapped)."""
        if self.is_east_west:
            return self.lon1 + f * self.dlon
        psi = mercator_psi(self.lat1 + f * self.dlat)
        return self.lon1 + self.dlon * (psi - self._psi1) / self._dpsi

    def point_at(self, f: float) -> Tuple[float, float]:
        """(lat, lon) at fraction f of the leg length; lon in [-180, 180)."""
        return self.lat1 + f * self.dlat, wrap_lon(self.lon_unwrapped_at(f))

    def fraction_at_lat(self, lat: float) -> float:
        """Fraction at which the leg reaches latitude `lat` (not east-west legs)."""
        return (lat - self.lat1) / self.dlat

    def fraction_at_lon(self, lon_unwrapped: float) -> float:
        """Fraction at which the leg reaches the unwrapped longitude `lon_unwrapped`."""
        g = (lon_unwrapped - self.lon1) / self.dlon
        if self.is_east_west:
            return g
        lat = inverse_mercator_psi(self._psi1 + g * self._dpsi)
        return (lat - self.lat1) / self.dlat

    def __repr__(self) -> str:
        return (f"RhumbLeg(({self.lat1:.4f}, {self.lon1:.4f}) -> "
                f"({self.lat2:.4f}, {self.lon2:.4f}), {self.length_nm:.2f} NM, "
                f"bearing {self.bearing_deg:.2f})")

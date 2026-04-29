"""
Geographic primitives for placing H-lines on the rebuilt DP graph.

Per Qg2 (rhumb line) and Qg4 (rhumb-line distance):
- Each segment of the voyage is a loxodrome (constant compass bearing).
- Distance along the segment is the rhumb-line (loxodromic) distance.
- Per Qg3 (0.5° marine grid axis-aligned at integer multiples of 0.5°),
  we compute every point along the rhumb line where it crosses a
  `lat = 0.5 * k` or `lon = 0.5 * k` line.

Every crossing becomes an H-line in the DP graph at the cumulative route
distance (from voyage start) where it happens.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import List, Tuple

# Earth radius — matches typical maritime convention. 1 nm ≈ 1.852 km.
# 60 nm per degree of latitude → R_earth = 60 × 360 / (2π) = 3437.747 nm.
R_EARTH_NM = 60.0 * 180.0 / math.pi

# Mercator y(φ) → ∞ at φ = ±90°. Clamp the input slightly inside that to
# keep the math finite for high-latitude / polar-region voyages.
_LAT_LIMIT_DEG = 89.5


def _clamp_lat(lat_deg: float) -> float:
    """Clamp latitude to [−89.5°, 89.5°] to dodge the Mercator singularity."""
    if lat_deg > _LAT_LIMIT_DEG:
        return _LAT_LIMIT_DEG
    if lat_deg < -_LAT_LIMIT_DEG:
        return -_LAT_LIMIT_DEG
    return lat_deg


def _normalize_dlon(dlon_deg: float) -> float:
    """Normalize a longitude difference into (−180°, 180°].

    Handles antimeridian-crossing routes: Tokyo (139°E) → Honolulu (−158°E)
    has naïve Δlon = −297°; this returns +63° (the short way east through
    the antimeridian).
    """
    dlon = (dlon_deg + 180.0) % 360.0 - 180.0
    # Edge case: -180° and +180° are the same line; prefer +180°.
    if dlon == -180.0:
        dlon = 180.0
    return dlon


def _mercator_y(lat_deg: float) -> float:
    """Mercator y-coordinate (radians) for a given latitude in degrees.

    M(φ) = ln(tan(π/4 + φ/2)). Singular at the poles; we clamp φ to
    ±89.5° via `_clamp_lat` so this is always finite even for arctic routes.
    """
    lat_rad = math.radians(_clamp_lat(lat_deg))
    return math.log(math.tan(math.pi / 4 + lat_rad / 2))


def _inverse_mercator_lat_deg(my: float) -> float:
    """Inverse of `_mercator_y` — convert Mercator y back to latitude (deg)."""
    return math.degrees(2.0 * math.atan(math.exp(my)) - math.pi / 2)


def rhumb_distance_nm(
    lat1_deg: float, lon1_deg: float, lat2_deg: float, lon2_deg: float,
) -> float:
    """Loxodromic (rhumb-line) distance between two points, in nautical miles.

    Lat is clamped to ±89.5° before use; Δlon is normalised to (−180°, 180°]
    so antimeridian-crossing routes take the short way around.
    """
    lat1_deg = _clamp_lat(lat1_deg)
    lat2_deg = _clamp_lat(lat2_deg)
    phi1 = math.radians(lat1_deg)
    phi2 = math.radians(lat2_deg)
    dphi = phi2 - phi1
    dlon_deg = _normalize_dlon(lon2_deg - lon1_deg)
    dlam = math.radians(dlon_deg)

    dpsi = _mercator_y(lat2_deg) - _mercator_y(lat1_deg)
    if abs(dpsi) > 1e-12:
        q = dphi / dpsi
    else:
        q = math.cos(phi1)

    distance_rad = math.sqrt(dphi * dphi + (q * dlam) ** 2)
    return distance_rad * R_EARTH_NM


def rhumb_bearing_deg(
    lat1_deg: float, lon1_deg: float, lat2_deg: float, lon2_deg: float,
) -> float:
    """Constant compass bearing along the rhumb line from p1 → p2 (degrees).

    Returned in [0, 360). 0 = north, 90 = east, etc. Δlon is normalised so
    the bearing reflects the short way around (e.g. Tokyo → Honolulu →
    east, not west).
    """
    lat1_deg = _clamp_lat(lat1_deg)
    lat2_deg = _clamp_lat(lat2_deg)
    dpsi = _mercator_y(lat2_deg) - _mercator_y(lat1_deg)
    dlon_deg = _normalize_dlon(lon2_deg - lon1_deg)
    dlam = math.radians(dlon_deg)
    if abs(dpsi) < 1e-12:
        # Pure east-west leg. Bearing is +90 (east) or 270 (west).
        return 90.0 if dlam > 0 else 270.0
    bearing_rad = math.atan2(dlam, dpsi)
    return (math.degrees(bearing_rad) + 360.0) % 360.0


@dataclass(frozen=True)
class Crossing:
    """One point where a rhumb-line segment intersects a NWP grid line."""
    fraction: float       # 0..1 along the segment
    distance_nm: float    # cumulative nm from the segment start
    lat_deg: float        # geographic position of the crossing
    lon_deg: float
    axis: str             # "lat" or "lon" — which grid line was crossed
    grid_value: float     # the lat or lon value of the grid line (deg)


def rhumb_grid_crossings(
    lat1_deg: float, lon1_deg: float,
    lat2_deg: float, lon2_deg: float,
    grid_deg: float = 0.5,
) -> List[Crossing]:
    """Return every grid-line crossing along the rhumb line p1 → p2.

    Crossings are deduplicated (same fraction within 1e-6) and returned
    sorted by fraction.

    Mathematics:
      - In Mercator coordinates, both lon and ψ = ln(tan(π/4 + φ/2)) vary
        linearly along a rhumb line. So:
            lat(f) = inv_M(M(lat1) + f·(M(lat2) − M(lat1)))
            lon(f) = lon1 + f·(lon2 − lon1)
            d(f)   = f · D_total       (rhumb-line distance scales linearly)
      - For each lon target g: f = (g − lon1)/(lon2 − lon1).
      - For each lat target g: f = (M(g) − M(lat1))/(M(lat2) − M(lat1)).
    """
    lat1_deg = _clamp_lat(lat1_deg)
    lat2_deg = _clamp_lat(lat2_deg)
    # Normalise Δlon so antimeridian-crossing routes go the short way.
    # `lon2_eff` is the unwrapped lon2: lon1 + (signed normalised Δlon).
    dlon = _normalize_dlon(lon2_deg - lon1_deg)
    lon2_eff = lon1_deg + dlon

    D_total = rhumb_distance_nm(lat1_deg, lon1_deg, lat2_deg, lon2_deg)

    def _wrap_lon(lon: float) -> float:
        """Wrap a longitude back to [-180°, 180°] for storage."""
        return ((lon + 180.0) % 360.0) - 180.0

    crossings: List[Crossing] = []

    # --- longitude-line crossings ---------------------------------------
    # Iterate in the *unwrapped* coordinate system [lon1, lon2_eff] so we
    # never miss crossings on antimeridian routes; wrap the stored lon
    # value back to [-180°, 180°].
    if abs(dlon) > 1e-12:
        lon_lo, lon_hi = sorted([lon1_deg, lon2_eff])
        k_first = math.ceil(lon_lo / grid_deg)
        k_last = math.floor(lon_hi / grid_deg)
        for k in range(k_first, k_last + 1):
            g_unwrapped = round(k * grid_deg, 9)
            if abs(g_unwrapped - lon1_deg) < 1e-12 or abs(g_unwrapped - lon2_eff) < 1e-12:
                continue
            f = (g_unwrapped - lon1_deg) / dlon
            if not (0.0 < f < 1.0):
                continue
            my = _mercator_y(lat1_deg) + f * (_mercator_y(lat2_deg) - _mercator_y(lat1_deg))
            lat_at = _inverse_mercator_lat_deg(my)
            g_stored = _wrap_lon(g_unwrapped)
            crossings.append(Crossing(
                fraction=f, distance_nm=f * D_total,
                lat_deg=lat_at, lon_deg=g_stored,
                axis="lon", grid_value=g_stored,
            ))

    # --- latitude-line crossings ----------------------------------------
    if abs(lat2_deg - lat1_deg) > 1e-12:
        lat_lo, lat_hi = sorted([lat1_deg, lat2_deg])
        my1 = _mercator_y(lat1_deg)
        my2 = _mercator_y(lat2_deg)
        k_first = math.ceil(lat_lo / grid_deg)
        k_last = math.floor(lat_hi / grid_deg)
        for k in range(k_first, k_last + 1):
            g = round(k * grid_deg, 9)
            if abs(g - lat1_deg) < 1e-12 or abs(g - lat2_deg) < 1e-12:
                continue
            myg = _mercator_y(g)
            f = (myg - my1) / (my2 - my1)
            if not (0.0 < f < 1.0):
                continue
            lon_unwrapped = lon1_deg + f * dlon
            crossings.append(Crossing(
                fraction=f, distance_nm=f * D_total,
                lat_deg=g, lon_deg=_wrap_lon(lon_unwrapped),
                axis="lat", grid_value=g,
            ))

    # Sort by fraction, dedupe near-coincident crossings.
    crossings.sort(key=lambda c: c.fraction)
    deduped: List[Crossing] = []
    for c in crossings:
        if deduped and abs(c.fraction - deduped[-1].fraction) < 1e-6:
            continue
        deduped.append(c)
    return deduped


def cell_index(lat_deg: float, lon_deg: float, grid_deg: float = 0.5) -> Tuple[int, int]:
    """NWP cell (lat_idx, lon_idx) containing the given point."""
    return (int(math.floor(lat_deg / grid_deg)),
            int(math.floor(lon_deg / grid_deg)))


def rhumb_total_nm(waypoints) -> float:
    """Total rhumb-line distance for a polyline through `waypoints`.

    `waypoints` is iterable of objects with `.lat_deg` / `.lon_deg` (or
    tuples (lat, lon)). Returns the sum of consecutive rhumb distances.
    """
    pts = []
    for w in waypoints:
        if hasattr(w, "lat_deg"):
            pts.append((w.lat_deg, w.lon_deg))
        else:
            pts.append((w[0], w[1]))
    total = 0.0
    for i in range(len(pts) - 1):
        total += rhumb_distance_nm(pts[i][0], pts[i][1], pts[i + 1][0], pts[i + 1][1])
    return total

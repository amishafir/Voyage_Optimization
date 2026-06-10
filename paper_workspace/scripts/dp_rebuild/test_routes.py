"""
Hypothetical routes for validating the geo layer at higher latitudes
and edge-case geometries (antimeridian crossings, polar approaches).

These are NOT used by the production pipeline. They exist so we can
visualise / regression-test `geo_grid.py` against routes the YAML paper
voyage doesn't exercise.

Reuses `route_waypoints.Waypoint`; only the (idx, lat, lon, name) fields
are populated — segment-attached fields (heading, distance, weather) are
left as None and computed on the fly when needed.
"""

from __future__ import annotations

from typing import Dict, List

from route_waypoints import Waypoint


# -----------------------------------------------------------------------------
# (a) Iceland → Tromsø — 4 waypoints, Norwegian Sea crossing.
# Lat 64°–69°N, lon −22° → 19°E. Mid-high latitude, no antimeridian, no
# polar projection switch (max lat 69° < 70° threshold). Validates that
# the lat-clamp + Δlon-normalisation refactor doesn't break tame routes.
# -----------------------------------------------------------------------------
ICELAND_TROMSO: List[Waypoint] = [
    Waypoint(idx=1, lat_deg=64.13, lon_deg=-21.95, name="Reykjavík (Iceland)"),
    Waypoint(idx=2, lat_deg=65.50, lon_deg=-10.00, name="Norwegian Sea (mid-Atlantic)"),
    Waypoint(idx=3, lat_deg=67.00, lon_deg=4.00,   name="Norwegian shelf"),
    Waypoint(idx=4, lat_deg=69.65, lon_deg=18.96,  name="Tromsø (Norway)"),
]


# Registry — add future fixtures here.
TEST_ROUTES: Dict[str, List[Waypoint]] = {
    "iceland_tromso": ICELAND_TROMSO,
}

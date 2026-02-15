"""
Waypoint generation for the maritime route.

Ported from: test_files/generate_intermediate_waypoints.py
Key change: returns DataFrame (for HDF5 /metadata), not Node objects.
"""

import math
import os

import pandas as pd
import yaml

# Constants
NAUTICAL_MILE_KM = 1.852
EARTH_RADIUS_KM = 6371.0


# ---------------------------------------------------------------------------
# Geodesic math
# ---------------------------------------------------------------------------

def haversine_distance(lat1, lon1, lat2, lon2):
    """Great circle distance between two points in km."""
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)

    a = (math.sin(delta_lat / 2) ** 2
         + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return EARTH_RADIUS_KM * c


def interpolate_geodesic(lat1, lon1, lat2, lon2, fraction):
    """Interpolate a point along the great circle path.

    Args:
        fraction: 0 = start point, 1 = end point.

    Returns:
        (lat, lon) in degrees.
    """
    lat1_rad = math.radians(lat1)
    lon1_rad = math.radians(lon1)
    lat2_rad = math.radians(lat2)
    lon2_rad = math.radians(lon2)

    d = haversine_distance(lat1, lon1, lat2, lon2) / EARTH_RADIUS_KM

    if d == 0:
        return lat1, lon1

    a = math.sin((1 - fraction) * d) / math.sin(d)
    b = math.sin(fraction * d) / math.sin(d)

    x = a * math.cos(lat1_rad) * math.cos(lon1_rad) + b * math.cos(lat2_rad) * math.cos(lon2_rad)
    y = a * math.cos(lat1_rad) * math.sin(lon1_rad) + b * math.cos(lat2_rad) * math.sin(lon2_rad)
    z = a * math.sin(lat1_rad) + b * math.sin(lat2_rad)

    lat_i = math.atan2(z, math.sqrt(x ** 2 + y ** 2))
    lon_i = math.atan2(y, x)

    return math.degrees(lat_i), math.degrees(lon_i)


# ---------------------------------------------------------------------------
# Config loader
# ---------------------------------------------------------------------------

def load_route_config(config):
    """Resolve route name to YAML path and load.

    Args:
        config: Full experiment config dict.

    Returns:
        Route config dict with 'name' and 'waypoints' keys.
    """
    route_name = config["collection"]["route"]

    # Look for route YAML relative to config dir
    config_dir = os.path.join(os.path.dirname(__file__), "..", "config")
    route_path = os.path.join(config_dir, "routes", f"{route_name}.yaml")
    route_path = os.path.normpath(route_path)

    with open(route_path) as f:
        return yaml.safe_load(f)


# ---------------------------------------------------------------------------
# Waypoint generation
# ---------------------------------------------------------------------------

def generate_waypoints(route_config, interval_nm=1.0):
    """Generate waypoints at specified nautical mile intervals.

    Args:
        route_config: Dict with 'waypoints' key (list of {lat, lon, name}).
        interval_nm: Spacing between intermediate waypoints in nautical miles.

    Returns:
        DataFrame with columns: node_id, lon, lat, waypoint_name,
        is_original, distance_from_start_nm, segment.
    """
    originals = route_config["waypoints"]
    all_waypoints = []
    node_id = 0

    for i, wp in enumerate(originals):
        # Add original waypoint
        segment = i if i < len(originals) - 1 else i - 1
        all_waypoints.append({
            "node_id": node_id,
            "lon": wp["lon"],
            "lat": wp["lat"],
            "waypoint_name": wp["name"],
            "is_original": True,
            "segment": segment,
        })
        node_id += 1

        # Add intermediate points to next original
        if i < len(originals) - 1:
            wp_next = originals[i + 1]
            dist_km = haversine_distance(wp["lat"], wp["lon"], wp_next["lat"], wp_next["lon"])
            dist_nm = dist_km / NAUTICAL_MILE_KM
            num_intermediate = int(dist_nm / interval_nm) - 1

            if num_intermediate > 0:
                for j in range(1, num_intermediate + 1):
                    fraction = (j * interval_nm) / dist_nm
                    lat_i, lon_i = interpolate_geodesic(
                        wp["lat"], wp["lon"],
                        wp_next["lat"], wp_next["lon"],
                        fraction,
                    )
                    all_waypoints.append({
                        "node_id": node_id,
                        "lon": lon_i,
                        "lat": lat_i,
                        "waypoint_name": f"WP{i+1}-{i+2}_{j}nm",
                        "is_original": False,
                        "segment": i,
                    })
                    node_id += 1

    # Calculate cumulative distance from start
    all_waypoints[0]["distance_from_start_nm"] = 0.0
    total_dist = 0.0
    for k in range(1, len(all_waypoints)):
        prev = all_waypoints[k - 1]
        curr = all_waypoints[k]
        d = haversine_distance(prev["lat"], prev["lon"], curr["lat"], curr["lon"])
        total_dist += d / NAUTICAL_MILE_KM
        curr["distance_from_start_nm"] = total_dist

    df = pd.DataFrame(all_waypoints)
    return df

#!/usr/bin/env python3
"""
Generate Intermediate Waypoints at 1 Nautical Mile Intervals

Takes the 13 original waypoints and interpolates additional points
along the geodesic (great circle) path between consecutive waypoints.

Output:
- List of all waypoints (original + intermediate) with Node class structure
- Saved as pickle file
"""

import pickle
import math
from dataclasses import dataclass
from typing import List, Tuple

# Try to use geopy, fall back to manual calculation if not available
try:
    from geopy.distance import geodesic
    from geopy.point import Point
    HAS_GEOPY = True
except ImportError:
    HAS_GEOPY = False
    print("Note: geopy not installed, using manual geodesic calculation")

# ============================================================================
# NODE CLASS (same as class.py)
# ============================================================================

class Node:
    def __init__(self):
        self.node_index = None  # Tuple of (longitude, latitude)
        self.Actual_weather_conditions = None  # Dict: {time_from_start: weather_dict}
        self.Predicted_weather_conditions = None  # Dict: {forecast_time: {sample_time: weather_dict}}

    def __repr__(self):
        return f"Node(index={self.node_index})"


# ============================================================================
# ORIGINAL WAYPOINTS (from Table 8 of research paper)
# ============================================================================

ORIGINAL_WAYPOINTS = [
    {"id": 1, "name": "Port A", "lat": 24.75, "lon": 52.83},
    {"id": 2, "name": "Waypoint 2", "lat": 26.55, "lon": 56.45},
    {"id": 3, "name": "Waypoint 3", "lat": 24.08, "lon": 60.88},
    {"id": 4, "name": "Waypoint 4", "lat": 21.73, "lon": 65.73},
    {"id": 5, "name": "Waypoint 5", "lat": 17.96, "lon": 69.19},
    {"id": 6, "name": "Waypoint 6", "lat": 14.18, "lon": 72.07},
    {"id": 7, "name": "Waypoint 7", "lat": 10.45, "lon": 75.16},
    {"id": 8, "name": "Waypoint 8", "lat": 7.00, "lon": 78.46},
    {"id": 9, "name": "Waypoint 9", "lat": 5.64, "lon": 82.12},
    {"id": 10, "name": "Waypoint 10", "lat": 4.54, "lon": 87.04},
    {"id": 11, "name": "Waypoint 11", "lat": 5.20, "lon": 92.27},
    {"id": 12, "name": "Waypoint 12", "lat": 5.64, "lon": 97.16},
    {"id": 13, "name": "Port B", "lat": 1.81, "lon": 100.10},
]

# Constants
NAUTICAL_MILE_KM = 1.852  # 1 nautical mile in kilometers
EARTH_RADIUS_KM = 6371.0  # Earth's radius in kilometers


# ============================================================================
# GEODESIC CALCULATIONS (manual fallback if geopy not available)
# ============================================================================

def haversine_distance(lat1, lon1, lat2, lon2):
    """Calculate the great circle distance between two points in km."""
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)

    a = math.sin(delta_lat / 2) ** 2 + \
        math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return EARTH_RADIUS_KM * c


def interpolate_geodesic_manual(lat1, lon1, lat2, lon2, fraction):
    """
    Interpolate a point along the great circle path.
    fraction: 0 = start point, 1 = end point
    """
    lat1_rad = math.radians(lat1)
    lon1_rad = math.radians(lon1)
    lat2_rad = math.radians(lat2)
    lon2_rad = math.radians(lon2)

    # Calculate angular distance
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


# ============================================================================
# WAYPOINT GENERATION
# ============================================================================

def get_distance_nm(lat1, lon1, lat2, lon2):
    """Get distance between two points in nautical miles."""
    if HAS_GEOPY:
        dist_km = geodesic((lat1, lon1), (lat2, lon2)).kilometers
    else:
        dist_km = haversine_distance(lat1, lon1, lat2, lon2)
    return dist_km / NAUTICAL_MILE_KM


def interpolate_point(lat1, lon1, lat2, lon2, fraction):
    """Interpolate a point along geodesic path."""
    if HAS_GEOPY:
        start = Point(lat1, lon1)
        end = Point(lat2, lon2)
        total_dist = geodesic(start, end).kilometers
        target_dist = total_dist * fraction

        # Use geodesic interpolation
        dest = geodesic(kilometers=target_dist).destination(start,
            bearing=calculate_bearing(lat1, lon1, lat2, lon2))
        return dest.latitude, dest.longitude
    else:
        return interpolate_geodesic_manual(lat1, lon1, lat2, lon2, fraction)


def calculate_bearing(lat1, lon1, lat2, lon2):
    """Calculate initial bearing from point 1 to point 2."""
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lon = math.radians(lon2 - lon1)

    x = math.sin(delta_lon) * math.cos(lat2_rad)
    y = math.cos(lat1_rad) * math.sin(lat2_rad) - \
        math.sin(lat1_rad) * math.cos(lat2_rad) * math.cos(delta_lon)

    bearing = math.atan2(x, y)
    return (math.degrees(bearing) + 360) % 360


def generate_intermediate_waypoints(interval_nm=1.0):
    """
    Generate waypoints at specified nautical mile intervals.

    Returns:
        List of dicts with waypoint info including original waypoints
    """
    all_waypoints = []
    waypoint_id = 0

    for i in range(len(ORIGINAL_WAYPOINTS)):
        wp = ORIGINAL_WAYPOINTS[i]

        # Add original waypoint
        waypoint_id += 1
        all_waypoints.append({
            "id": waypoint_id,
            "name": wp["name"],
            "lat": wp["lat"],
            "lon": wp["lon"],
            "original_wp_id": wp["id"],
            "is_original": True,
            "segment": i if i < len(ORIGINAL_WAYPOINTS) - 1 else i - 1,
            "distance_from_start_nm": 0 if i == 0 else None  # Will calculate later
        })

        # If not the last waypoint, add intermediate points
        if i < len(ORIGINAL_WAYPOINTS) - 1:
            wp_next = ORIGINAL_WAYPOINTS[i + 1]

            # Calculate distance between waypoints
            dist_nm = get_distance_nm(wp["lat"], wp["lon"], wp_next["lat"], wp_next["lon"])

            # Number of intermediate points (excluding start and end)
            num_intermediate = int(dist_nm / interval_nm) - 1

            if num_intermediate > 0:
                for j in range(1, num_intermediate + 1):
                    fraction = (j * interval_nm) / dist_nm
                    lat_i, lon_i = interpolate_point(
                        wp["lat"], wp["lon"],
                        wp_next["lat"], wp_next["lon"],
                        fraction
                    )

                    waypoint_id += 1
                    all_waypoints.append({
                        "id": waypoint_id,
                        "name": f"WP{wp['id']}-{wp_next['id']}_{j}nm",
                        "lat": lat_i,
                        "lon": lon_i,
                        "original_wp_id": None,
                        "is_original": False,
                        "segment": i,
                        "distance_from_prev_nm": interval_nm
                    })

    # Calculate cumulative distance from start
    total_dist = 0
    all_waypoints[0]["distance_from_start_nm"] = 0

    for i in range(1, len(all_waypoints)):
        prev = all_waypoints[i - 1]
        curr = all_waypoints[i]
        dist = get_distance_nm(prev["lat"], prev["lon"], curr["lat"], curr["lon"])
        total_dist += dist
        curr["distance_from_start_nm"] = total_dist

    return all_waypoints


def create_nodes_from_waypoints(waypoints):
    """Create Node objects from waypoint list."""
    nodes = []
    for wp in waypoints:
        node = Node()
        node.node_index = (wp["lon"], wp["lat"])
        node.Actual_weather_conditions = {}
        node.Predicted_weather_conditions = {}
        # Store additional metadata
        node.waypoint_info = {
            "id": wp["id"],
            "name": wp["name"],
            "is_original": wp["is_original"],
            "segment": wp["segment"],
            "distance_from_start_nm": wp["distance_from_start_nm"]
        }
        nodes.append(node)
    return nodes


# ============================================================================
# MAIN
# ============================================================================

def main():
    print("=" * 80)
    print("Generating Intermediate Waypoints at 1 Nautical Mile Intervals")
    print("=" * 80)
    print()

    # Generate waypoints
    print("Calculating distances between original waypoints...")
    print()

    total_distance = 0
    for i in range(len(ORIGINAL_WAYPOINTS) - 1):
        wp1 = ORIGINAL_WAYPOINTS[i]
        wp2 = ORIGINAL_WAYPOINTS[i + 1]
        dist = get_distance_nm(wp1["lat"], wp1["lon"], wp2["lat"], wp2["lon"])
        total_distance += dist
        print(f"  Segment {i+1}: {wp1['name']:15} -> {wp2['name']:15} = {dist:7.1f} nm")

    print()
    print(f"  Total voyage distance: {total_distance:.1f} nm")
    print()

    # Generate intermediate waypoints
    print("Generating intermediate waypoints at 1 nm intervals...")
    waypoints = generate_intermediate_waypoints(interval_nm=1.0)

    print(f"  Original waypoints: {len(ORIGINAL_WAYPOINTS)}")
    print(f"  Total waypoints (with intermediate): {len(waypoints)}")
    print()

    # Create Node objects
    print("Creating Node objects...")
    nodes = create_nodes_from_waypoints(waypoints)

    # Save to pickle
    output_file = "voyage_nodes_interpolated.pickle"
    with open(output_file, 'wb') as f:
        pickle.dump(nodes, f)
    print(f"  Saved to: {output_file}")
    print()

    # Also save waypoint list as readable format
    output_txt = "waypoints_interpolated.txt"
    with open(output_txt, 'w') as f:
        f.write(f"{'ID':>5} | {'Name':^20} | {'Lat':>10} | {'Lon':>10} | {'Dist(nm)':>10} | {'Original':>8}\n")
        f.write("-" * 80 + "\n")
        for wp in waypoints:
            f.write(f"{wp['id']:>5} | {wp['name']:^20} | {wp['lat']:>10.4f} | {wp['lon']:>10.4f} | "
                   f"{wp['distance_from_start_nm']:>10.1f} | {'Yes' if wp['is_original'] else 'No':>8}\n")
    print(f"  Waypoint list saved to: {output_txt}")
    print()

    # Print sample of waypoints
    print("=" * 80)
    print("Sample Waypoints (first 20)")
    print("=" * 80)
    print(f"{'ID':>5} | {'Name':^20} | {'Lat':>10} | {'Lon':>10} | {'Dist(nm)':>10} | {'Original':>8}")
    print("-" * 80)
    for wp in waypoints[:20]:
        orig = "Yes" if wp["is_original"] else "No"
        print(f"{wp['id']:>5} | {wp['name']:^20} | {wp['lat']:>10.4f} | {wp['lon']:>10.4f} | "
              f"{wp['distance_from_start_nm']:>10.1f} | {orig:>8}")
    print("  ...")
    print()

    # Print summary by segment
    print("=" * 80)
    print("Summary by Segment")
    print("=" * 80)
    for i in range(len(ORIGINAL_WAYPOINTS) - 1):
        segment_wps = [wp for wp in waypoints if wp["segment"] == i]
        wp1 = ORIGINAL_WAYPOINTS[i]
        wp2 = ORIGINAL_WAYPOINTS[i + 1]
        print(f"  Segment {i+1} ({wp1['name']} -> {wp2['name']}): {len(segment_wps)} waypoints")

    print()
    print("=" * 80)
    print("Done!")
    print("=" * 80)


if __name__ == "__main__":
    main()

# Intermediate Waypoint Generation

## Overview

The `generate_intermediate_waypoints.py` script creates additional waypoints at 1 nautical mile intervals along the geodesic (great circle) path between the original 13 waypoints.

## Run Command

```bash
cd test_files
python3 generate_intermediate_waypoints.py
```

## Output Files

- `voyage_nodes_interpolated.pickle` - 3,388 Node objects (original + intermediate)
- `waypoints_interpolated.txt` - Human-readable waypoint list
- `voyage_route_map.html` - Interactive map visualization

## Statistics

- Original waypoints: 13
- Total waypoints: 3,388 (at 1 nm intervals)
- Total voyage distance: 3,393.5 nm

## Interpolated Node Structure

```python
node.node_index = (lon, lat)
node.Actual_weather_conditions = {}
node.Predicted_weather_conditions = {}
node.waypoint_info = {
    "id": 5,
    "name": "WP1-2_5nm",
    "is_original": False,
    "segment": 0,
    "distance_from_start_nm": 5.0
}
```

## Segment Distances

| Segment | From | To | Distance (nm) |
|---------|------|-----|---------------|
| 1 | Port A | WP 2 | 223.8 |
| 2 | WP 2 | WP 3 | 282.5 |
| 3 | WP 3 | WP 4 | 303.2 |
| 4 | WP 4 | WP 5 | 298.4 |
| 5 | WP 5 | WP 6 | 280.5 |
| 6 | WP 6 | WP 7 | 287.3 |
| 7 | WP 7 | WP 8 | 284.4 |
| 8 | WP 8 | WP 9 | 233.3 |
| 9 | WP 9 | WP 10 | 301.8 |
| 10 | WP 10 | WP 11 | 315.7 |
| 11 | WP 11 | WP 12 | 293.8 |
| 12 | WP 12 | Port B | 288.8 |

#!/usr/bin/env python3
"""
Tree-based visualization of voyage weather data structure from pickle file.
"""

import pickle

# Node class for unpickling
class Node:
    def __init__(self):
        self.node_index = None
        self.Actual_weather_conditions = None
        self.Predicted_weather_conditions = None

import __main__
__main__.Node = Node

# Load data
with open('voyage_nodes.pickle', 'rb') as f:
    nodes = pickle.load(f)

# Waypoint names
WAYPOINT_NAMES = [
    "Port A", "Waypoint 2", "Waypoint 3", "Waypoint 4", "Waypoint 5",
    "Waypoint 6", "Waypoint 7", "Waypoint 8", "Waypoint 9", "Waypoint 10",
    "Waypoint 11", "Waypoint 12", "Port B"
]

def format_weather(weather, indent=""):
    """Format weather dict as tree."""
    lines = []
    for key, val in weather.items():
        if isinstance(val, float):
            lines.append(f"{indent}{key}: {val:.2f}")
        else:
            lines.append(f"{indent}{key}: {val}")
    return lines

def print_tree():
    print("=" * 80)
    print("VOYAGE NODES PICKLE DATA STRUCTURE")
    print("=" * 80)
    print()
    print(f"voyage_nodes.pickle")
    print(f"└── List[Node] ({len(nodes)} nodes)")

    for i, node in enumerate(nodes):
        is_last_node = (i == len(nodes) - 1)
        prefix = "    └── " if is_last_node else "    ├── "
        child_prefix = "        " if is_last_node else "    │   "

        print(f"{prefix}Node[{i}]: {WAYPOINT_NAMES[i]}")
        print(f"{child_prefix}├── node_index: {node.node_index}")
        print(f"{child_prefix}│   └── (longitude={node.node_index[0]}, latitude={node.node_index[1]})")

        # Actual weather conditions
        actual = node.Actual_weather_conditions or {}
        print(f"{child_prefix}├── Actual_weather_conditions: dict ({len(actual)} samples)")

        actual_times = sorted(actual.keys())
        for j, time_h in enumerate(actual_times[:3]):  # Show first 3
            is_last_actual = (j == min(2, len(actual_times) - 1))
            actual_prefix = "│   └── " if is_last_actual else "│   ├── "
            weather = actual[time_h]
            print(f"{child_prefix}{actual_prefix}t={time_h:.4f}h:")

            weather_prefix = "│       " if not is_last_actual else "        "
            for k, (key, val) in enumerate(weather.items()):
                is_last_item = (k == len(weather) - 1)
                item_prefix = "└── " if is_last_item else "├── "
                if isinstance(val, float):
                    print(f"{child_prefix}{weather_prefix}    {item_prefix}{key}: {val:.2f}")
                else:
                    print(f"{child_prefix}{weather_prefix}    {item_prefix}{key}: {val}")

        if len(actual_times) > 3:
            print(f"{child_prefix}│   └── ... ({len(actual_times) - 3} more samples)")

        # Predicted weather conditions
        predicted = node.Predicted_weather_conditions or {}
        print(f"{child_prefix}└── Predicted_weather_conditions: dict ({len(predicted)} forecast times)")

        forecast_times = sorted(predicted.keys())
        sample_forecasts = forecast_times[::24][:3]  # Show every 24h, first 3

        for j, ft in enumerate(sample_forecasts):
            is_last_forecast = (j == len(sample_forecasts) - 1) and len(forecast_times) <= 72
            forecast_prefix = "    └── " if is_last_forecast else "    ├── "
            predictions = predicted[ft]
            print(f"{child_prefix}{forecast_prefix}forecast_time={ft:.1f}h: dict ({len(predictions)} predictions)")

            sample_times = sorted(predictions.keys())[:2]  # Show first 2 sample times
            for k, st in enumerate(sample_times):
                is_last_sample = (k == len(sample_times) - 1)
                sample_prefix = "        └── " if is_last_sample else "        ├── "
                weather = predictions[st]
                print(f"{child_prefix}{sample_prefix}sample_time={st:.4f}h: {{...}}")

        if len(forecast_times) > 72:
            print(f"{child_prefix}    └── ... ({len(forecast_times) - 72} more forecast times)")

        print()  # Blank line between nodes

        # Only show first 2 nodes in detail, then summary
        if i == 1:
            print(f"    │")
            print(f"    ├── ... (Nodes 2-11 follow same structure)")
            print(f"    │")
            # Skip to last node
            break

    # Show last node summary
    last_node = nodes[-1]
    last_actual = last_node.Actual_weather_conditions or {}
    last_predicted = last_node.Predicted_weather_conditions or {}
    print(f"    └── Node[12]: Port B")
    print(f"        ├── node_index: {last_node.node_index}")
    print(f"        ├── Actual_weather_conditions: dict ({len(last_actual)} samples)")
    print(f"        │   └── Note: Marine data is NaN (outside API coverage)")
    print(f"        └── Predicted_weather_conditions: dict ({len(last_predicted)} forecast times)")

    print()
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Total nodes: {len(nodes)}")
    print(f"Actual samples per node: {len(nodes[0].Actual_weather_conditions)}")
    print(f"Forecast times per node: {len(nodes[0].Predicted_weather_conditions)}")
    print(f"Predictions per forecast time: {len(list(nodes[0].Predicted_weather_conditions.values())[0])}")
    print()
    print("Weather data fields:")
    sample_weather = list(nodes[0].Actual_weather_conditions.values())[0]
    for key in sample_weather.keys():
        print(f"  - {key}")

if __name__ == "__main__":
    print_tree()

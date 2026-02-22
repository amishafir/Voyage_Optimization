"""Validate downloaded HDF5 experiment files.

Checks:
  - Sample hour completeness (0-143)
  - Node counts (7 for exp_a, ~138 for exp_b)
  - NaN gaps in actual weather
  - Summary statistics of weather fields
"""

import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from shared.hdf5_io import read_metadata, read_actual, read_predicted, get_attrs, get_completed_runs

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")

WEATHER_FIELDS = [
    "wind_speed_10m_kmh", "wind_direction_10m_deg", "beaufort_number",
    "wave_height_m", "ocean_current_velocity_kmh", "ocean_current_direction_deg",
]


def validate_hdf5(path, expected_nodes=None, expected_samples=144):
    """Validate a single HDF5 file."""
    name = os.path.basename(path)
    print(f"\n{'='*60}")
    print(f"VALIDATING: {name}")
    print(f"{'='*60}")

    if not os.path.isfile(path):
        print(f"  ERROR: File not found!")
        return False

    size_mb = os.path.getsize(path) / 1024 / 1024
    print(f"  File size: {size_mb:.1f} MB")

    # Attributes
    attrs = get_attrs(path)
    print(f"  Attributes: {attrs}")

    # Metadata
    metadata = read_metadata(path)
    num_nodes = len(metadata)
    num_original = metadata["is_original"].sum()
    total_dist = metadata.iloc[-1]["distance_from_start_nm"]
    num_segments = metadata["segment"].nunique()
    print(f"  Nodes: {num_nodes} ({num_original} original)")
    print(f"  Segments: {num_segments}")
    print(f"  Total distance: {total_dist:.1f} nm")

    if expected_nodes is not None and num_nodes != expected_nodes:
        print(f"  WARNING: Expected {expected_nodes} nodes, got {num_nodes}")

    # Completed runs
    runs = get_completed_runs(path)
    print(f"  Completed sample hours: {len(runs)}")
    if runs:
        print(f"    Range: {min(runs)} - {max(runs)}")
        expected_range = set(range(expected_samples))
        missing = expected_range - set(runs)
        if missing:
            print(f"    MISSING hours: {sorted(missing)}")
        else:
            print(f"    All {expected_samples} hours present!")

    # Actual weather stats
    actual = read_actual(path)
    print(f"\n  Actual weather: {len(actual)} rows")
    if not actual.empty:
        for field in WEATHER_FIELDS:
            vals = actual[field]
            nan_count = vals.isna().sum()
            print(f"    {field}: mean={vals.mean():.3f}, "
                  f"std={vals.std():.3f}, "
                  f"range=[{vals.min():.3f}, {vals.max():.3f}], "
                  f"NaN={nan_count} ({nan_count/len(vals)*100:.1f}%)")

    # Predicted weather stats
    predicted = read_predicted(path)
    print(f"\n  Predicted weather: {len(predicted)} rows")
    if not predicted.empty:
        n_forecast_hours = predicted["forecast_hour"].nunique()
        n_sample_hours = predicted["sample_hour"].nunique()
        print(f"    Forecast hours: {n_forecast_hours} unique "
              f"(range {predicted['forecast_hour'].min()}-{predicted['forecast_hour'].max()})")
        print(f"    Sample hours: {n_sample_hours} unique")

    # Check for NaN gaps in actual weather per-node
    if not actual.empty:
        print(f"\n  NaN gap analysis (actual weather):")
        for field in ["wind_speed_10m_kmh", "wave_height_m", "ocean_current_velocity_kmh"]:
            nan_by_node = actual.groupby("node_id")[field].apply(lambda x: x.isna().sum())
            nodes_with_nan = (nan_by_node > 0).sum()
            if nodes_with_nan > 0:
                print(f"    {field}: {nodes_with_nan} nodes with NaN values")
                worst = nan_by_node.nlargest(3)
                for nid, count in worst.items():
                    print(f"      node {nid}: {count} NaN values")
            else:
                print(f"    {field}: No NaN values!")

    passed = len(runs) >= expected_samples and num_nodes > 0
    status = "PASS" if passed else "FAIL"
    print(f"\n  Status: {status}")
    return passed


if __name__ == "__main__":
    print("=" * 60)
    print("HDF5 EXPERIMENT VALIDATION")
    print("=" * 60)

    results = {}

    exp_a_path = os.path.join(DATA_DIR, "experiment_a_7wp.h5")
    results["exp_a"] = validate_hdf5(exp_a_path, expected_nodes=7)

    exp_b_path = os.path.join(DATA_DIR, "experiment_b_138wp.h5")
    results["exp_b"] = validate_hdf5(exp_b_path)

    print("\n" + "=" * 60)
    print("OVERALL RESULTS")
    print("=" * 60)
    for name, passed in results.items():
        print(f"  {name}: {'PASS' if passed else 'FAIL'}")
    print("=" * 60)

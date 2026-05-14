#!/usr/bin/env python3
"""
Experiment C — Collection Status Checker
=========================================
Lightweight script (no optimizer imports) that reads the HDF5 and reports
collection progress, data quality, and estimated time to full coverage.

Run locally on a downloaded copy:
    python3 pipeline/check_exp_c_status.py

Run remotely via SSH one-liner:
    ssh user@Shlomo1-pcl.eng.tau.ac.il "cd ~/Ami && python3 check_exp_c_status.py"
"""

import os
import sys
from datetime import datetime

pipeline_dir = os.path.dirname(os.path.abspath(__file__))
if pipeline_dir not in sys.path:
    sys.path.insert(0, pipeline_dir)

import h5py
import numpy as np

HDF5_PATH = os.path.join(pipeline_dir, "data", "experiment_c_968wp.h5")

VOYAGE_HOURS = 400        # ~4,782 nm / 12 kn
EXPECTED_NODES = 968      # ~4,782 nm / 5 nm spacing


def check_status(hdf5_path):
    if not os.path.exists(hdf5_path):
        print(f"HDF5 file not found: {hdf5_path}")
        return

    file_size_mb = os.path.getsize(hdf5_path) / (1024 * 1024)

    with h5py.File(hdf5_path, "r") as f:
        # Metadata
        meta = f["metadata"][:]
        n_nodes = len(meta)

        # Attributes
        created_at = f.attrs.get("created_at", "unknown")
        route_name = f.attrs.get("route_name", "unknown")
        if isinstance(route_name, bytes):
            route_name = route_name.decode("utf-8")
        if isinstance(created_at, bytes):
            created_at = created_at.decode("utf-8")

        # Actual weather
        actual_ds = f["actual_weather"]
        n_actual = actual_ds.shape[0]
        if n_actual > 0:
            actual_hours = sorted(set(int(h) for h in actual_ds["sample_hour"][:]))
            n_completed = len(actual_hours)
            min_hour = min(actual_hours)
            max_hour = max(actual_hours)

            # NaN counts per field
            nan_counts = {}
            for field in ["wind_speed_10m_kmh", "wind_direction_10m_deg",
                          "wave_height_m", "ocean_current_velocity_kmh",
                          "ocean_current_direction_deg"]:
                vals = actual_ds[field][:]
                nan_counts[field] = int(np.isnan(vals).sum())
        else:
            actual_hours = []
            n_completed = 0
            min_hour = max_hour = None
            nan_counts = {}

        # Predicted weather
        predicted_ds = f["predicted_weather"]
        n_predicted = predicted_ds.shape[0]

    # Print report
    print("=" * 65)
    print("  EXPERIMENT C — Collection Status")
    print("=" * 65)
    print(f"  Route:       {route_name}")
    print(f"  HDF5 file:   {hdf5_path}")
    print(f"  File size:   {file_size_mb:.1f} MB")
    print(f"  Created:     {created_at}")
    print()

    # Node coverage
    print(f"  Nodes:       {n_nodes} (expected ~{EXPECTED_NODES})")
    print()

    # Sample hours
    print(f"  Sample hours collected: {n_completed}")
    if n_completed > 0:
        print(f"  Hour range:  {min_hour} → {max_hour}")
        gaps = set(range(min_hour, max_hour + 1)) - set(actual_hours)
        if gaps:
            print(f"  Gaps:        {sorted(gaps)[:10]}{'...' if len(gaps) > 10 else ''} ({len(gaps)} total)")
        else:
            print(f"  Gaps:        none (contiguous)")
    print()

    # Data rows
    print(f"  Actual rows:    {n_actual:,}")
    print(f"  Predicted rows: {n_predicted:,}")
    print()

    # NaN quality
    if nan_counts:
        print("  NaN counts (actual weather):")
        for field, count in nan_counts.items():
            pct = 100 * count / n_actual if n_actual > 0 else 0
            status = "OK" if count == 0 else f"{count:,} ({pct:.1f}%)"
            print(f"    {field}: {status}")
        print()

    # Voyage readiness
    if n_completed > 0:
        print("  Voyage readiness:")
        if max_hour >= VOYAGE_HOURS:
            print(f"    READY for full voyage ({VOYAGE_HOURS}h)")
        else:
            remaining = VOYAGE_HOURS - max_hour
            print(f"    {max_hour}/{VOYAGE_HOURS}h collected ({100*max_hour/VOYAGE_HOURS:.0f}%)")
            print(f"    ~{remaining}h remaining (~{remaining/24:.1f} days)")

        # Reachable distance at 12 kn
        reachable_nm = max_hour * 12
        total_nm = float(meta["distance_from_start_nm"][-1]) if n_nodes > 0 else 0
        print(f"    Reachable distance: {reachable_nm:.0f} / {total_nm:.0f} nm")
    print("=" * 65)


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else HDF5_PATH
    check_status(path)

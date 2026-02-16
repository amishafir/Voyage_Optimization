#!/usr/bin/env python3
"""
Run the new pipeline against the research paper's Table 8 weather data.
Validates that the new pipeline reproduces the legacy 372 kg result.
"""

import math
import os
import sys

import numpy as np
import pandas as pd

# Ensure pipeline modules are importable
base_dir = os.path.dirname(os.path.abspath(__file__))
if base_dir not in sys.path:
    sys.path.insert(0, base_dir)

from shared.hdf5_io import create_hdf5, append_actual

# -----------------------------------------------------------------------
# Paper Table 8 data (from voyage_data.py)
# -----------------------------------------------------------------------

SEGMENT_DATA = [
    # wind_dir(deg), beaufort, wave_height(m), current_dir(deg), current_speed(kn)
    [139, 3, 1.0, 245, 0.30],
    [207, 3, 1.0, 248, 0.72],
    [  9, 4, 1.5, 158, 0.73],
    [201, 4, 1.5, 178, 0.21],
    [ 88, 5, 2.5, 135, 0.49],
    [ 86, 4, 1.5, 113, 0.22],
    [353, 3, 1.0, 338, 0.54],
    [ 35, 5, 2.5, 290, 1.25],
    [269, 4, 1.5, 270, 0.28],
    [174, 3, 1.0,  93, 0.72],
    [ 60, 1, 0.1, 185, 0.62],
    [315, 3, 1.0,  90, 0.30],
]

SEGMENT_HEADINGS_DEG = [
    61.25, 121.53, 117.61, 139.03, 143.63,
    140.84, 136.42, 110.37, 102.57, 82.83,
    84.87, 142.39,
]

SEGMENT_DISTANCES = [
    223.86, 282.54, 303.18, 298.44, 280.51,
    287.34, 284.40, 233.25, 301.80, 315.70,
    293.80, 288.42,
]

WAYPOINTS = [
    {"lat": 24.75, "lon": 52.83, "name": "Port A (Persian Gulf)"},
    {"lat": 26.55, "lon": 56.45, "name": "Gulf of Oman"},
    {"lat": 24.08, "lon": 60.88, "name": "Arabian Sea 1"},
    {"lat": 21.73, "lon": 65.73, "name": "Arabian Sea 2"},
    {"lat": 17.96, "lon": 69.19, "name": "Arabian Sea 3"},
    {"lat": 14.18, "lon": 72.07, "name": "Arabian Sea 4"},
    {"lat": 10.45, "lon": 75.16, "name": "Indian Ocean 1"},
    {"lat":  7.00, "lon": 78.46, "name": "Indian Ocean 2"},
    {"lat":  5.64, "lon": 82.12, "name": "Bay of Bengal"},
    {"lat":  4.54, "lon": 87.04, "name": "Indian Ocean 3"},
    {"lat":  5.20, "lon": 92.27, "name": "Andaman Sea 1"},
    {"lat":  5.64, "lon": 97.16, "name": "Andaman Sea 2"},
    {"lat":  1.81, "lon": 100.10, "name": "Port B (Strait of Malacca)"},
]


# Beaufort -> representative wind speed (km/h) for HDF5 field
BEAUFORT_WIND_KMH = {
    0: 0, 1: 3, 2: 9, 3: 16, 4: 25, 5: 35,
    6: 45, 7: 56, 8: 68, 9: 82, 10: 96, 11: 110, 12: 120,
}


def create_paper_hdf5(path):
    """Build an HDF5 with 13 original waypoints and paper weather."""
    # Cumulative distances
    cum_dist = [0.0]
    for d in SEGMENT_DISTANCES:
        cum_dist.append(cum_dist[-1] + d)

    # Metadata: 13 nodes, all original
    meta_rows = []
    for i, wp in enumerate(WAYPOINTS):
        seg = min(i, 11)  # last node belongs to segment 11
        meta_rows.append({
            "node_id": i,
            "lon": wp["lon"],
            "lat": wp["lat"],
            "waypoint_name": wp["name"],
            "is_original": True,
            "distance_from_start_nm": cum_dist[i],
            "segment": seg,
        })
    metadata_df = pd.DataFrame(meta_rows)

    create_hdf5(path, metadata_df, attrs={
        "source": "paper_table8",
        "num_nodes": 13,
    })

    # Actual weather at sample_hour=0
    # Node i (i=0..11) gets segment i weather; node 12 (Port B) gets NaN
    wx_rows = []
    for i in range(13):
        if i < 12:
            seg = SEGMENT_DATA[i]
            bn = seg[1]
            wx_rows.append({
                "node_id": i,
                "sample_hour": 0,
                "wind_speed_10m_kmh": float(BEAUFORT_WIND_KMH[bn]),
                "wind_direction_10m_deg": float(seg[0]),
                "beaufort_number": bn,
                "wave_height_m": float(seg[2]),
                "ocean_current_velocity_kmh": float(seg[4] * 1.852),  # knots -> km/h
                "ocean_current_direction_deg": float(seg[3]),
            })
        else:
            # Port B — NaN marine data
            wx_rows.append({
                "node_id": i,
                "sample_hour": 0,
                "wind_speed_10m_kmh": float("nan"),
                "wind_direction_10m_deg": float("nan"),
                "beaufort_number": 0,
                "wave_height_m": float("nan"),
                "ocean_current_velocity_kmh": float("nan"),
                "ocean_current_direction_deg": float("nan"),
            })
    append_actual(path, pd.DataFrame(wx_rows))
    print(f"Created paper HDF5: {path}")


def main():
    import logging
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    # 1. Create paper HDF5
    hdf5_path = os.path.join(base_dir, "data", "paper_table8.h5")
    create_paper_hdf5(hdf5_path)

    # 2. Config matching the old LP: 78 speeds from 8.0 to 15.7
    config = {
        "ship": {
            "length_m": 200.0,
            "beam_m": 32.0,
            "draft_m": 12.0,
            "displacement_tonnes": 50000.0,
            "block_coefficient": 0.75,
            "rated_power_kw": 10000.0,
            "speed_range_knots": [8.0, 15.7],
            "eta_hours": 280,
        },
        "static_det": {
            "enabled": True,
            "segments": 12,
            "weather_snapshot": 0,
            "optimizer": "gurobi",
            "speed_choices": 78,
        },
    }

    # 3. Transform
    from static_det.transform import transform
    t_out = transform(hdf5_path, config)

    # Show headings comparison
    print("\nHeading comparison (paper vs GPS-computed):")
    print(f"{'Seg':>3}  {'Paper':>8}  {'GPS':>8}  {'Delta':>7}")
    for i in range(12):
        paper_h = SEGMENT_HEADINGS_DEG[i]
        gps_h = t_out["segment_headings_deg"][i]
        delta = gps_h - paper_h
        print(f"{i+1:>3}  {paper_h:>8.2f}  {gps_h:>8.2f}  {delta:>+7.2f}")

    # 4. Optimize
    from static_det.optimize import optimize
    planned = optimize(t_out, config)
    if planned.get("status") != "Optimal":
        print(f"LP failed: {planned.get('status')}")
        return

    # 5. Simulate (with only 13 nodes, simulation ≈ planned)
    from shared.simulation import simulate_voyage
    simulated = simulate_voyage(
        planned["speed_schedule"], hdf5_path, config, sample_hour=0,
    )

    # 6. Metrics
    from shared.metrics import compute_result_metrics
    total_dist = sum(t_out["distances"])
    metrics = compute_result_metrics(planned, simulated, total_dist)

    # 7. Print results
    print()
    print("=" * 60)
    print("NEW PIPELINE — PAPER TABLE 8 DATA")
    print("=" * 60)
    print(f"  Planned fuel:    {planned['planned_fuel_kg']:>10.2f} kg")
    print(f"  Planned time:    {planned['planned_time_h']:>10.2f} h")
    print(f"  Simulated fuel:  {simulated['total_fuel_kg']:>10.2f} kg")
    print(f"  Simulated time:  {simulated['total_time_h']:>10.2f} h")
    print(f"  Fuel gap:        {metrics['fuel_gap_percent']:>10.2f} %")
    print(f"  Solve time:      {planned['computation_time_s']:>10.3f} s")
    print("=" * 60)

    print()
    print(f"{'Seg':>3}  {'Dist':>8}  {'SWS':>6}  {'SOG':>8}  {'Time':>7}  {'Fuel':>8}")
    print(f"{'#':>3}  {'(nm)':>8}  {'(kn)':>6}  {'(kn)':>8}  {'(h)':>7}  {'(kg)':>8}")
    print("-" * 50)
    for s in planned["speed_schedule"]:
        print(f"{s['segment']+1:>3}  {s['distance_nm']:>8.1f}  "
              f"{s['sws_knots']:>6.1f}  {s['sog_knots']:>8.3f}  "
              f"{s['time_h']:>7.2f}  {s['fuel_kg']:>8.2f}")
    print(f"{'TOT':>3}  {total_dist:>8.1f}  {'--':>6}  {'--':>8}  "
          f"{planned['planned_time_h']:>7.2f}  {planned['planned_fuel_kg']:>8.2f}")

    # Compare with legacy
    print()
    print("Legacy LP result: 372.37 kg")
    delta = planned["planned_fuel_kg"] - 372.37
    print(f"Delta:            {delta:+.2f} kg ({delta/372.37*100:+.2f}%)")


if __name__ == "__main__":
    main()

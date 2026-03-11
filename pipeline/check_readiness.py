#!/usr/bin/env python3
"""Check how close each experiment is to having enough data for analysis."""
import h5py
import os

EXPERIMENTS = [
    ("data/experiment_b_138wp.h5", "exp_b", 3394),   # Persian Gulf-Malacca
    ("data/experiment_d_391wp.h5", "exp_d", 1955),    # St John's-Liverpool
    ("data/experiment_c_968wp.h5", "exp_c", 4782),    # Yokohama-Long Beach
]

for fname, name, route_nm in EXPERIMENTS:
    if not os.path.exists(fname):
        print(f"\n=== {name}: FILE NOT FOUND ===")
        continue
    h = h5py.File(fname, "r")
    print(f"\n=== {name} ({fname}) ===")
    print(f"Route: {route_nm} nm")

    # Actual weather
    aw = h["actual_weather"]
    a_hours = sorted(set(int(x) for x in aw["sample_hour"]))
    print(f"Actual samples: {len(a_hours)}, range {a_hours[0]}-{a_hours[-1]}")

    # Predicted weather
    pw = h["predicted_weather"]
    p_hours = sorted(set(int(x) for x in pw["sample_hour"]))
    print(f"Predicted samples: {len(p_hours)}, range {p_hours[0]}-{p_hours[-1]}")

    # Voyage duration at 12 kn
    voyage_h = route_nm / 12.0
    needed_samples = int(voyage_h / 6) + 1
    print(f"Voyage duration at 12kn: {voyage_h:.0f}h ({voyage_h/24:.1f} days)")
    print(f"Samples needed (every 6h): {needed_samples}")

    # How many more predicted samples needed
    remaining = max(0, needed_samples - len(p_hours))
    hours_left = remaining * 6
    print(f"Predicted: have {len(p_hours)}/{needed_samples} -> {remaining} more needed ({hours_left}h = {hours_left/24:.1f} days)")

    # Gaps in predicted
    expected = set(range(0, max(a_hours[-1], p_hours[-1]) + 1, 6))
    missing = sorted(expected - set(p_hours))
    if missing:
        print(f"Missing predicted at hours: {missing[:15]}{'...' if len(missing)>15 else ''}")

    h.close()

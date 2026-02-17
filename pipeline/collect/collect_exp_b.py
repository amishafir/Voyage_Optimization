#!/usr/bin/env python3
"""
Experiment B — Spatial + Temporal Collection
=============================================
138 interpolated waypoints at 12nm spacing (WP 1→7), 144 sample hours, every 1 hour.
LP averages weather across segments; DP uses per-node weather.
Shows both spatial granularity and temporal advantages.

Output: data/experiment_b_138wp.h5
Run:    cd pipeline && python3 collect/collect_exp_b.py
"""

import os
import sys

# Allow running from pipeline/ directory
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from collect.collector import collect

CONFIG = {
    "collection": {
        "route": "persian_gulf_io1",
        "interval_nm": 12,         # 12nm spacing → ~138 nodes
        "hours": 144,              # 6 days — covers full voyage duration
        "api_delay_seconds": 0.1,
    },
}

OUTPUT_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data", "experiment_b_138wp.h5",
)

if __name__ == "__main__":
    print("=" * 70)
    print("EXPERIMENT B — Spatial + Temporal")
    print("  ~138 waypoints at 12nm spacing, 144 sample hours")
    print("  Route: Port A → Indian Ocean 1 (1,678 nm)")
    print(f"  Output: {OUTPUT_PATH}")
    print("  API calls per sample: ~138 nodes × 2 endpoints = ~276")
    print("  Total API calls: ~276 × 144 = ~39,744")
    print("=" * 70)
    collect(CONFIG, hdf5_path=OUTPUT_PATH)

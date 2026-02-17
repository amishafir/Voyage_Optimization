#!/usr/bin/env python3
"""
Experiment A — Temporal Isolation Collection
=============================================
7 original waypoints (WP 1→7), 144 sample hours, every 1 hour.
No interpolation — LP and DP see the same 6 segments.
Isolates the temporal advantage: time-varying weather (DP) vs frozen snapshot (LP).

Output: data/experiment_a_7wp.h5
Run:    cd pipeline && python3 collect/collect_exp_a.py
"""

import os
import sys

# Allow running from pipeline/ directory
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from collect.collector import collect

CONFIG = {
    "collection": {
        "route": "persian_gulf_io1",
        "interval_nm": 9999,       # Large interval = only original waypoints (7 nodes)
        "hours": 144,              # 6 days — covers full voyage duration
        "api_delay_seconds": 0.1,
    },
}

OUTPUT_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data", "experiment_a_7wp.h5",
)

if __name__ == "__main__":
    print("=" * 70)
    print("EXPERIMENT A — Temporal Isolation")
    print("  7 original waypoints, 144 sample hours")
    print("  Route: Port A → Indian Ocean 1 (1,678 nm)")
    print(f"  Output: {OUTPUT_PATH}")
    print("  API calls per sample: 7 nodes × 2 endpoints = 14")
    print("  Total API calls: 14 × 144 = 2,016")
    print("=" * 70)
    collect(CONFIG, hdf5_path=OUTPUT_PATH)

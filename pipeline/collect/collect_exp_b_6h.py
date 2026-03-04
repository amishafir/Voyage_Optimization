#!/usr/bin/env python3
"""
Experiment B — 6-hourly collection (reduced API load).

Same as collect_exp_b.py but samples every 6 hours instead of every 1 hour,
aligned with NWP model update cycles (GFS updates every 6h).

This reduces API calls from ~40,000 to ~6,600, avoiding quota conflicts
with exp_c and exp_d running on the same server.

Output: data/experiment_b_138wp.h5
Run:    cd pipeline && python3 collect/collect_exp_b_6h.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from collect.collector import collect

CONFIG = {
    "collection": {
        "route": "persian_gulf_io1",
        "interval_nm": 12,              # 12nm spacing → ~138 nodes
        "hours": 144,                   # 6 days — covers full voyage duration
        "api_delay_seconds": 0.1,
        "sample_interval_hours": 6,     # every 6h instead of every 1h
    },
}

OUTPUT_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data", "experiment_b_138wp.h5",
)

if __name__ == "__main__":
    print("=" * 70)
    print("EXPERIMENT B — 6-hourly collection")
    print("  ~138 waypoints at 12nm spacing, 144h voyage, sample every 6h")
    print("  Route: Port A → Indian Ocean 1 (1,678 nm)")
    print(f"  Output: {OUTPUT_PATH}")
    print("  API calls per sample: ~138 nodes × 2 endpoints = ~276")
    print("  Total samples: 24 (every 6h × 144h)")
    print("  Total API calls: ~276 × 24 = ~6,624")
    print("=" * 70)
    collect(CONFIG, hdf5_path=OUTPUT_PATH)

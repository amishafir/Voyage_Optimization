#!/usr/bin/env python3
"""
Experiment C — North Pacific Great Circle (Indefinite Collection)
=================================================================
~968 interpolated waypoints at 5nm spacing (Yokohama → Long Beach),
indefinite hourly samples until stopped.

Harsh route: Aleutian storm track, 4,782 nm, ~17 days at 12 kn.
API calls per sample: ~968 nodes × 2 endpoints = ~1,936
Time per sample: ~3.2 min at 0.1s delay

Output: data/experiment_c_968wp.h5

Deployment (TAU server):
    scp pipeline/collect/collect_exp_c.py user@Shlomo1-pcl.eng.tau.ac.il:~/Ami/
    ssh user@Shlomo1-pcl.eng.tau.ac.il
    tmux new -s exp_c
    cd ~/Ami && python3 collect_exp_c.py

Download partial data:
    scp user@Shlomo1-pcl.eng.tau.ac.il:~/Ami/experiment_c_968wp.h5 pipeline/data/

Run:    cd pipeline && python3 collect/collect_exp_c.py
Stop:   Ctrl+C (finishes current sample, then exits cleanly)
Resume: Re-run the same command (picks up from last completed sample_hour)
"""

import os
import sys

# Allow running from pipeline/ directory
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from collect.collector import collect

CONFIG = {
    "collection": {
        "route": "yokohama_long_beach",
        "interval_nm": 5,          # 5nm spacing → ~968 nodes
        "hours": 0,                # 0 = indefinite (run until stopped)
        "api_delay_seconds": 0.1,
    },
}

OUTPUT_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data", "experiment_c_968wp.h5",
)

if __name__ == "__main__":
    print("=" * 70)
    print("EXPERIMENT C — North Pacific Great Circle (Indefinite)")
    print("  ~968 waypoints at 5nm spacing, indefinite hourly collection")
    print("  Route: Yokohama → Long Beach (4,782 nm)")
    print(f"  Output: {OUTPUT_PATH}")
    print("  API calls per sample: ~968 nodes × 2 endpoints = ~1,936")
    print("  Ctrl+C to stop gracefully after current sample")
    print("=" * 70)
    collect(CONFIG, hdf5_path=OUTPUT_PATH)

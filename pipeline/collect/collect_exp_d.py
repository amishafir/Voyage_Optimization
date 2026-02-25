#!/usr/bin/env python3
"""
Experiment D — North Atlantic Storm Track (Indefinite Collection)
==================================================================
~391 interpolated waypoints at 5nm spacing (St. John's → Liverpool),
indefinite hourly samples until stopped.

North Atlantic storm track: 1,955 nm, ~6.8 days at 12 kn.
Entire voyage fits within the 7-day (168h) forecast horizon.
Isolates the forecast freshness effect for RH advantage.

API calls per sample: ~391 nodes × 2 endpoints = ~782
Time per sample: ~1.3 min at 0.1s delay

Output: data/experiment_d_391wp.h5

Deployment (TAU server):
    scp pipeline/collect/collect_exp_d.py user@Shlomo1-pcl.eng.tau.ac.il:~/Ami/pipeline/collect/
    ssh user@Shlomo1-pcl.eng.tau.ac.il
    tmux new -s exp_d
    cd ~/Ami/pipeline && python3 -u collect/collect_exp_d.py 2>&1 | tee collect_exp_d.log

Download partial data:
    scp user@Shlomo1-pcl.eng.tau.ac.il:~/Ami/pipeline/data/experiment_d_391wp.h5 pipeline/data/

Run:    cd pipeline && python3 collect/collect_exp_d.py
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
        "route": "st_johns_liverpool",
        "interval_nm": 5,          # 5nm spacing → ~391 nodes
        "hours": 0,                # 0 = indefinite (run until stopped)
        "api_delay_seconds": 0.1,
    },
}

OUTPUT_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data", "experiment_d_391wp.h5",
)

if __name__ == "__main__":
    print("=" * 70)
    print("EXPERIMENT D — North Atlantic Storm Track (Indefinite)")
    print("  ~391 waypoints at 5nm spacing, indefinite hourly collection")
    print("  Route: St. John's → Liverpool (1,955 nm)")
    print(f"  Output: {OUTPUT_PATH}")
    print("  API calls per sample: ~391 nodes × 2 endpoints = ~782")
    print("  Ctrl+C to stop gracefully after current sample")
    print("=" * 70)
    collect(CONFIG, hdf5_path=OUTPUT_PATH)

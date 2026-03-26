#!/usr/bin/env python3
"""Unified collector — runs exp_b, exp_c, exp_d sequentially per NWP cycle.

Avoids API rate limits by ensuring only one experiment hits the API at a time.
Shares a single API client and respects a configurable delay between chunks.
"""
import os
import sys
import signal
import time
import logging
from datetime import datetime, timezone, timedelta

import pandas as pd

sys.path.insert(0, os.path.expanduser("~/Ami/pipeline"))

from collect.collector import (
    setup_api_client,
    fetch_wind_bulk,
    fetch_marine_bulk,
    _parse_bulk_responses,
    _nan_actual_row,
    _next_nwp_time,
    BULK_CHUNK_SIZE,
)
from collect.waypoints import generate_waypoints, load_route_config
from shared.hdf5_io import create_hdf5, append_actual, append_predicted, get_completed_runs

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Experiment definitions
# ---------------------------------------------------------------------------

EXPERIMENTS = [
    {
        "name": "exp_b",
        "route": "persian_gulf_malacca",
        "interval_nm": 25,
        "hdf5": "data/experiment_b_138wp.h5",
    },
{
        "name": "exp_d",
        "route": "st_johns_liverpool",
        "interval_nm": 5,
        "hdf5": "data/experiment_d_391wp.h5",
    },
]

# Shared settings
API_DELAY = 5.0          # seconds between API chunks
SAMPLE_INTERVAL = 6      # hours between samples
NWP_OFFSET_UTC = 5       # GFS data arrives ~5h after cycle start
INTER_EXPERIMENT_DELAY = 300  # 5 min pause between experiments (avoid API throttling)
WIND_MARINE_DELAY = 60   # seconds pause between wind and marine bulk calls

# ---------------------------------------------------------------------------
# Single-sample collection for one experiment
# ---------------------------------------------------------------------------

def collect_one_sample(client, exp, sample_hour, base_dir):
    """Collect one sample_hour for one experiment. Returns True on success."""
    hdf5_path = os.path.join(base_dir, exp["hdf5"])
    route_config = load_route_config({"collection": {"route": exp["route"]}})
    waypoints_df = generate_waypoints(route_config, interval_nm=exp["interval_nm"])

    # Create HDF5 if first run
    if not os.path.exists(hdf5_path):
        attrs = {
            "route_name": route_config.get("name", "unknown"),
            "interval_nm": exp["interval_nm"],
            "planned_hours": 0,
            "sample_interval_hours": SAMPLE_INTERVAL,
            "source": "live_collection",
        }
        create_hdf5(hdf5_path, waypoints_df, attrs)
        logger.info("[%s] Created HDF5: %s", exp["name"], hdf5_path)

    # Skip if already collected
    completed = get_completed_runs(hdf5_path)
    if sample_hour in completed:
        logger.info("[%s] sample_hour %d already collected, skipping", exp["name"], sample_hour)
        return True

    n_wp = len(waypoints_df)
    n_chunks = (n_wp + BULK_CHUNK_SIZE - 1) // BULK_CHUNK_SIZE
    logger.info("[%s] Collecting sample_hour %d — %d waypoints (%d chunks)",
                exp["name"], sample_hour, n_wp, n_chunks)

    lats = waypoints_df["lat"].tolist()
    lons = waypoints_df["lon"].tolist()
    node_ids = waypoints_df["node_id"].tolist()
    voyage_start_time = datetime.now()

    max_retries = 5
    for attempt in range(max_retries):
        try:
            wind_responses = fetch_wind_bulk(client, lats, lons, API_DELAY)
            time.sleep(WIND_MARINE_DELAY)
            marine_responses = fetch_marine_bulk(client, lats, lons, API_DELAY)

            actual_rows, predicted_rows, failed = _parse_bulk_responses(
                wind_responses, marine_responses, node_ids,
                sample_hour, voyage_start_time,
            )
            successful = n_wp - failed
            break
        except Exception as e:
            err_str = str(e).lower()
            is_retryable = ("rate" in err_str or "limit" in err_str
                            or "timeout" in err_str or "timed out" in err_str
                            or "504" in err_str or "503" in err_str)
            if is_retryable and attempt < max_retries - 1:
                wait = 120 * (attempt + 1)  # 2min, 4min, 6min, 8min backoff
                logger.warning("[%s] API error (attempt %d/%d), retrying in %ds: %s",
                               exp["name"], attempt + 1, max_retries, wait, e)
                time.sleep(wait)
                continue
            logger.error("[%s] API call failed (attempt %d/%d): %s",
                         exp["name"], attempt + 1, max_retries, e)
            actual_rows = [_nan_actual_row(nid, sample_hour) for nid in node_ids]
            predicted_rows = []
            failed = n_wp
            successful = 0
            break

    append_actual(hdf5_path, pd.DataFrame(actual_rows))
    if predicted_rows:
        append_predicted(hdf5_path, pd.DataFrame(predicted_rows))

    h5_mb = os.path.getsize(hdf5_path) / (1024 * 1024)
    total = len(completed) + 1
    logger.info("[%s] Done: %d/%d OK, %d failed | predicted: %d rows | total samples: %d | %.1f MB",
                exp["name"], successful, n_wp, failed, len(predicted_rows), total, h5_mb)
    return failed < n_wp  # success if at least some waypoints succeeded


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

def main():
    base_dir = os.path.expanduser("~/Ami/pipeline")

    # Graceful shutdown
    shutdown = [False]
    def _handler(signum, frame):
        logger.info("Shutdown requested — finishing current experiment...")
        shutdown[0] = True
    signal.signal(signal.SIGINT, _handler)
    signal.signal(signal.SIGTERM, _handler)

    client = setup_api_client()

    # Determine next sample_hour from existing data (use exp_b as reference)
    ref_path = os.path.join(base_dir, EXPERIMENTS[0]["hdf5"])
    if os.path.exists(ref_path):
        completed = get_completed_runs(ref_path)
        next_hour = (max(completed) + SAMPLE_INTERVAL) if completed else 0
    else:
        next_hour = 0

    logger.info("Starting unified collector — next sample_hour: %d", next_hour)
    logger.info("Experiments: %s", ", ".join(e["name"] for e in EXPERIMENTS))
    logger.info("API delay: %.1fs, sample interval: %dh, NWP offset: %d UTC",
                API_DELAY, SAMPLE_INTERVAL, NWP_OFFSET_UTC)

    sample_hour = next_hour
    while not shutdown[0]:
        cycle_start = time.time()
        logger.info("=== Cycle: sample_hour %d ===", sample_hour)

        for i, exp in enumerate(EXPERIMENTS):
            if shutdown[0]:
                break
            collect_one_sample(client, exp, sample_hour, base_dir)
            # Pause between experiments to stay well under rate limits
            if i < len(EXPERIMENTS) - 1:
                time.sleep(INTER_EXPERIMENT_DELAY)

        if shutdown[0]:
            break

        cycle_elapsed = time.time() - cycle_start
        logger.info("Cycle done in %.0fs", cycle_elapsed)

        # Sleep until next NWP cycle
        target = _next_nwp_time(NWP_OFFSET_UTC, SAMPLE_INTERVAL)
        now = datetime.now(timezone.utc)
        wait = max(0, (target - now).total_seconds())
        logger.info("Next NWP update: %s UTC (waiting %.0f min)",
                     target.strftime("%H:%M"), wait / 60)

        if wait > 0:
            try:
                time.sleep(wait)
            except (KeyboardInterrupt, SystemExit):
                break
            if shutdown[0]:
                break

        sample_hour += SAMPLE_INTERVAL

    logger.info("Collector stopped.")


if __name__ == "__main__":
    main()

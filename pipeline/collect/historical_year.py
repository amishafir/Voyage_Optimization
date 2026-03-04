#!/usr/bin/env python3
"""
Year-long historical weather collection for experiments B, C, D.

Downloads 1 year of actual weather data using Open-Meteo Archive + Marine APIs
with monthly chunking to manage response sizes. Generates waypoints from route
config (no need for an existing HDF5).

Actual weather only — predicted weather requires real-time collection to capture
full 168h forecast horizons at 6h intervals (GFS cycle).

Usage:
    cd pipeline && python3 collect/historical_year.py --experiment d   # ~389 nodes, ~4 min
    cd pipeline && python3 collect/historical_year.py --experiment c   # ~947 nodes, ~10 min
    cd pipeline && python3 collect/historical_year.py --experiment b   # ~138 nodes, ~2 min
"""

import argparse
import math
import os
import sys
import time
from datetime import datetime, timedelta

import pandas as pd
import requests

pipeline_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, pipeline_dir)

from collect.waypoints import generate_waypoints, load_route_config
from shared.beaufort import wind_speed_to_beaufort
from shared.hdf5_io import create_hdf5, append_actual

# ──────────────────────────────────────────────────────────────────────
# Experiment definitions
# ──────────────────────────────────────────────────────────────────────

EXPERIMENTS = {
    "b": {
        "route": "persian_gulf_io1",
        "interval_nm": 12,
        "output": "experiment_b_138wp_year.h5",
    },
    "c": {
        "route": "yokohama_long_beach",
        "interval_nm": 5,
        "output": "experiment_c_947wp_year.h5",
    },
    "d": {
        "route": "st_johns_liverpool",
        "interval_nm": 5,
        "output": "experiment_d_389wp_year.h5",
    },
}

# Date range: past year (365 days = 8,760 hours)
DATE_START = "2025-03-04"
DATE_END = "2026-03-03"

# API endpoints
WIND_ARCHIVE_API = "https://archive-api.open-meteo.com/v1/archive"
MARINE_API = "https://marine-api.open-meteo.com/v1/marine"

MARINE_VARS = ["wave_height", "ocean_current_velocity", "ocean_current_direction"]

API_DELAY_SECONDS = 2


# ──────────────────────────────────────────────────────────────────────
# API functions
# ──────────────────────────────────────────────────────────────────────

def fetch_bulk(api_url, lats, lons, hourly_vars, start_date, end_date):
    """Fetch hourly data for multiple locations in one API call.

    Returns list of dicts, one per location, each with
    {timestamp_str: {var1: val, var2: val, ...}}.
    """
    params = {
        "latitude": ",".join(f"{lat:.4f}" for lat in lats),
        "longitude": ",".join(f"{lon:.4f}" for lon in lons),
        "start_date": start_date,
        "end_date": end_date,
        "hourly": ",".join(hourly_vars),
        "timezone": "GMT",
        "timeformat": "iso8601",
    }

    print(f"  GET {api_url}")
    print(f"    {len(lats)} locations, {start_date} to {end_date}")

    r = requests.get(api_url, params=params, timeout=600)
    r.raise_for_status()
    data = r.json()

    # Multi-location returns a list; single location returns a dict
    if isinstance(data, dict):
        data = [data]

    result = []
    for loc_data in data:
        hourly = loc_data["hourly"]
        times = hourly["time"]
        loc_dict = {}
        for i, t in enumerate(times):
            row = {}
            for var in hourly_vars:
                val = hourly[var][i]
                row[var] = float(val) if val is not None else float("nan")
            loc_dict[t] = row
        result.append(loc_dict)

    n_hours = len(result[0]) if result else 0
    print(f"    -> {len(result)} locations x {n_hours} hours")
    return result


def generate_monthly_ranges(start_date, end_date):
    """Generate list of (start, end) date strings for monthly chunks."""
    ranges = []
    current = datetime.strptime(start_date, "%Y-%m-%d")
    final = datetime.strptime(end_date, "%Y-%m-%d")

    while current <= final:
        if current.month == 12:
            month_end = current.replace(year=current.year + 1, month=1, day=1) - timedelta(days=1)
        else:
            month_end = current.replace(month=current.month + 1, day=1) - timedelta(days=1)

        chunk_end = min(month_end, final)
        ranges.append((current.strftime("%Y-%m-%d"), chunk_end.strftime("%Y-%m-%d")))
        current = chunk_end + timedelta(days=1)

    return ranges


# ──────────────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Year-long historical weather collection")
    parser.add_argument("--experiment", "-e", required=True, choices=["b", "c", "d"],
                        help="Experiment to collect data for")
    args = parser.parse_args()

    exp = EXPERIMENTS[args.experiment]
    output_path = os.path.join(pipeline_dir, "data", exp["output"])

    print("=" * 70)
    print(f"YEAR-LONG HISTORICAL COLLECTION -- Experiment {args.experiment.upper()}")
    print(f"  Route: {exp['route']}")
    print(f"  Spacing: {exp['interval_nm']}nm")
    print(f"  Date range: {DATE_START} to {DATE_END} (365 days)")
    print(f"  Output: {output_path}")
    print("=" * 70)
    t0 = time.time()

    # ── Step 1: Generate waypoints ────────────────────────────────────
    print(f"\n[1/4] Generating waypoints...")

    config = {"collection": {"route": exp["route"]}}
    route_config = load_route_config(config)
    meta = generate_waypoints(route_config, interval_nm=exp["interval_nm"])

    num_nodes = len(meta)
    lats = meta["lat"].tolist()
    lons = meta["lon"].tolist()
    node_ids = meta["node_id"].tolist()
    total_dist = meta["distance_from_start_nm"].iloc[-1]

    print(f"  {num_nodes} nodes at {exp['interval_nm']}nm spacing")
    print(f"  Total distance: {total_dist:.1f} nm")

    # ── Step 2: Create HDF5 with metadata ─────────────────────────────
    print(f"\n[2/4] Creating HDF5 file...")

    if os.path.exists(output_path):
        os.remove(output_path)

    attrs = {
        "route_name": route_config["name"],
        "interval_nm": exp["interval_nm"],
        "source": "historical_year",
        "date_start": DATE_START,
        "date_end": DATE_END,
    }
    create_hdf5(output_path, meta, attrs)

    # ── Step 3: Download + store month by month ───────────────────────
    print(f"\n[3/4] Downloading weather and building actual_weather (monthly)...")

    monthly_ranges = generate_monthly_ranges(DATE_START, DATE_END)
    print(f"  {len(monthly_ranges)} monthly chunks x 2 endpoints"
          f" = {len(monthly_ranges) * 2} API calls")

    total_rows = 0
    hour_offset = 0

    for chunk_idx, (chunk_start, chunk_end) in enumerate(monthly_ranges):
        chunk_t0 = time.time()
        print(f"\n  --- Chunk {chunk_idx + 1}/{len(monthly_ranges)}:"
              f" {chunk_start} to {chunk_end} ---")

        # Wind (Archive API)
        wind_chunk = fetch_bulk(
            WIND_ARCHIVE_API, lats, lons,
            ["wind_speed_10m", "wind_direction_10m"],
            chunk_start, chunk_end,
        )
        time.sleep(API_DELAY_SECONDS)

        # Marine
        marine_chunk = fetch_bulk(
            MARINE_API, lats, lons, MARINE_VARS,
            chunk_start, chunk_end,
        )

        timestamps = sorted(wind_chunk[0].keys())
        n_ts = len(timestamps)

        actual_rows = []
        for ts_idx, ts_str in enumerate(timestamps):
            sample_hour = hour_offset + ts_idx
            for loc_idx in range(num_nodes):
                wind = wind_chunk[loc_idx].get(ts_str, {})
                marine = marine_chunk[loc_idx].get(ts_str, {})
                ws = wind.get("wind_speed_10m", float("nan"))
                actual_rows.append({
                    "node_id": node_ids[loc_idx],
                    "sample_hour": sample_hour,
                    "wind_speed_10m_kmh": ws,
                    "wind_direction_10m_deg": wind.get("wind_direction_10m", float("nan")),
                    "beaufort_number": wind_speed_to_beaufort(ws) if not math.isnan(ws) else 0,
                    "wave_height_m": marine.get("wave_height", float("nan")),
                    "ocean_current_velocity_kmh": marine.get("ocean_current_velocity", float("nan")),
                    "ocean_current_direction_deg": marine.get("ocean_current_direction", float("nan")),
                })

        actual_df = pd.DataFrame(actual_rows)
        append_actual(output_path, actual_df)

        total_rows += len(actual_df)
        hour_offset += n_ts

        print(f"    {n_ts}h x {num_nodes} nodes = {len(actual_df):,} rows"
              f" (total: {total_rows:,}) [{time.time() - chunk_t0:.1f}s]")

        if chunk_idx < len(monthly_ranges) - 1:
            time.sleep(API_DELAY_SECONDS)

    total_api_calls = len(monthly_ranges) * 2
    print(f"\n  Download+build: {time.time() - t0:.1f}s ({total_api_calls} API calls)")

    # ── Step 4: Verify ────────────────────────────────────────────────
    print(f"\n[4/4] Verifying output...")

    import h5py
    with h5py.File(output_path, "r") as f:
        n_meta = len(f["metadata"])
        n_actual = len(f["actual_weather"])
        n_pred = len(f["predicted_weather"])

    file_size = os.path.getsize(output_path) / (1024 * 1024)
    total_time = time.time() - t0

    expected_rows = num_nodes * hour_offset
    print(f"  Metadata:  {n_meta} nodes")
    print(f"  Actual:    {n_actual:,} rows (expected: {expected_rows:,})")
    print(f"  Predicted: {n_pred:,} rows (none -- actual only)")
    print(f"  Hours:     {hour_offset} (0 to {hour_offset - 1})")
    print(f"  File size: {file_size:.1f} MB")

    if n_actual != expected_rows:
        print(f"  WARNING: Row count mismatch: got {n_actual:,}, expected {expected_rows:,}")

    print(f"\nDone in {total_time:.1f}s")
    print(f"  Output: {output_path}")
    print(f"  API calls: {total_api_calls}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Historical bulk download for experiment_b.

Recreates the exp_b HDF5 file using Open-Meteo Historical/Forecast API
with multi-location bulk requests instead of real-time hourly collection.

Original: ~40,000 API calls over 6 days of real-time collection
Historical: ~4 API calls in ~1 minute

Usage:
    cd pipeline && python3 collect/historical_exp_b.py
"""

import math
import os
import sys
import time
from datetime import datetime

import pandas as pd
import requests

pipeline_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, pipeline_dir)

from shared.beaufort import wind_speed_to_beaufort
from shared.hdf5_io import (
    create_hdf5,
    append_actual,
    append_predicted,
    read_metadata,
)

# ──────────────────────────────────────────────────────────────────────
# Configuration
# ──────────────────────────────────────────────────────────────────────

EXISTING_HDF5 = os.path.join(pipeline_dir, "data", "experiment_b_138wp.h5")
OUTPUT_HDF5 = os.path.join(pipeline_dir, "data", "experiment_b_138wp_historical.h5")

# Original collection: created 2026-02-17T11:24:14, 134 sample hours
VOYAGE_START_STR = "2026-02-17T11:00"
NUM_SAMPLE_HOURS = 134

# Date range covering actual (hours 0-133) + predicted (max fh=276)
# Actual: hours 0-133 → Feb 17 11:00 to Feb 23 00:00
# Predicted: max forecast_hour=276 → Feb 17 11:00 + 276h ≈ Mar 1 07:00
# With -11h hindcast → Feb 17 00:00
DATA_START = "2026-02-17"
DATA_END = "2026-03-02"

# API endpoints — use forecast API with past_days for recent data
WIND_API = "https://api.open-meteo.com/v1/forecast"
MARINE_API = "https://marine-api.open-meteo.com/v1/marine"

# Maximum locations per request (API limit: 1000)
BATCH_SIZE = 138  # all exp_b waypoints fit in one call


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
    print(f"    variables: {hourly_vars}")

    r = requests.get(api_url, params=params, timeout=300)
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
    print(f"    → {len(result)} locations × {n_hours} hours")
    return result


# ──────────────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────────────

def main():
    print("=" * 70)
    print("HISTORICAL BULK DOWNLOAD — Experiment B")
    print("  Original: ~40,000 API calls over 6 days")
    print("  Historical: ~2 API calls in seconds")
    print("=" * 70)
    t0 = time.time()

    # Read metadata from existing file
    meta = read_metadata(EXISTING_HDF5)
    meta = meta.sort_values("node_id").reset_index(drop=True)
    num_nodes = len(meta)
    lats = meta["lat"].tolist()
    lons = meta["lon"].tolist()
    print(f"\nWaypoints: {num_nodes}")
    print(f"Date range: {DATA_START} to {DATA_END}")
    print(f"Sample hours: 0 to {NUM_SAMPLE_HOURS - 1}")

    # ── Step 1: Bulk download ──────────────────────────────────────
    print(f"\n[1/4] Downloading bulk weather data...")

    wind_data = fetch_bulk(
        WIND_API, lats, lons,
        ["wind_speed_10m", "wind_direction_10m"],
        DATA_START, DATA_END,
    )

    # Small delay between API calls to be polite
    time.sleep(1)

    marine_data = fetch_bulk(
        MARINE_API, lats, lons,
        ["wave_height", "ocean_current_velocity", "ocean_current_direction"],
        DATA_START, DATA_END,
    )

    dl_time = time.time() - t0
    print(f"\n  Download time: {dl_time:.1f}s (2 API calls)")

    # ── Step 2: Build timestamp mapping ────────────────────────────
    print(f"\n[2/4] Building timestamp mapping...")

    voyage_start = datetime.fromisoformat(VOYAGE_START_STR)

    # Get sorted timestamps from wind data (same for all locations)
    all_timestamps = sorted(wind_data[0].keys())

    # Map: timestamp string → relative hour from voyage start
    ts_to_hour = {}
    for ts_str in all_timestamps:
        ts = datetime.fromisoformat(ts_str)
        rel_hours = (ts - voyage_start).total_seconds() / 3600
        ts_to_hour[ts_str] = round(rel_hours)

    # Reverse: hour → timestamp
    hour_to_ts = {}
    for ts_str, h in ts_to_hour.items():
        hour_to_ts[h] = ts_str  # last one wins if duplicates

    available_hours = sorted(hour_to_ts.keys())
    print(f"  Hours relative to voyage start: {available_hours[0]} to {available_hours[-1]}")
    print(f"  Total timestamps: {len(all_timestamps)}")

    # ── Step 3: Create HDF5 and populate ───────────────────────────
    print(f"\n[3/4] Creating HDF5 file...")

    if os.path.exists(OUTPUT_HDF5):
        os.remove(OUTPUT_HDF5)

    attrs = {
        "route_name": "Persian Gulf to Indian Ocean 1",
        "interval_nm": 12,
        "planned_hours": 144,
        "source": "historical_bulk",
        "original_created_at": "2026-02-17T11:24:14",
        "data_start": DATA_START,
        "data_end": DATA_END,
    }
    create_hdf5(OUTPUT_HDF5, meta, attrs)

    # ── 3a: Actual weather ─────────────────────────────────────────
    print("\n  [3a] Building actual_weather table...")

    def _get_weather(loc_idx, ts_str):
        """Combine wind + marine for a location at a timestamp."""
        wind = wind_data[loc_idx].get(ts_str, {})
        marine = marine_data[loc_idx].get(ts_str, {})
        ws = wind.get("wind_speed_10m", float("nan"))
        return {
            "wind_speed_10m_kmh": ws,
            "wind_direction_10m_deg": wind.get("wind_direction_10m", float("nan")),
            "beaufort_number": wind_speed_to_beaufort(ws) if not math.isnan(ws) else 0,
            "wave_height_m": marine.get("wave_height", float("nan")),
            "ocean_current_velocity_kmh": marine.get("ocean_current_velocity", float("nan")),
            "ocean_current_direction_deg": marine.get("ocean_current_direction", float("nan")),
        }

    def _closest_ts(target_hour):
        """Find the timestamp string closest to target_hour."""
        if target_hour in hour_to_ts:
            return hour_to_ts[target_hour]
        closest_h = min(available_hours, key=lambda h: abs(h - target_hour))
        return hour_to_ts[closest_h]

    actual_rows = []
    for sample_hour in range(NUM_SAMPLE_HOURS):
        ts = _closest_ts(sample_hour)
        for loc_idx in range(num_nodes):
            node_id = int(meta.iloc[loc_idx]["node_id"])
            wx = _get_weather(loc_idx, ts)
            actual_rows.append({
                "node_id": node_id,
                "sample_hour": sample_hour,
                **wx,
            })

    actual_df = pd.DataFrame(actual_rows)
    append_actual(OUTPUT_HDF5, actual_df)
    print(f"    {len(actual_df)} rows ({num_nodes} nodes x {NUM_SAMPLE_HOURS} hours)")

    # ── 3b: Predicted weather (actual = perfect forecast) ──────────
    print("\n  [3b] Building predicted_weather table...")
    print("    NOTE: Using actual weather as 'perfect forecast' (zero forecast error)")

    # Process in batches to manage memory
    BATCH = 10  # sample hours per batch
    total_pred = 0

    for sh_start in range(0, NUM_SAMPLE_HOURS, BATCH):
        sh_end = min(sh_start + BATCH, NUM_SAMPLE_HOURS)
        pred_rows = []

        for sample_hour in range(sh_start, sh_end):
            # Match original: 168 forecast hours starting at sample_hour - 11
            fh_start = sample_hour - 11
            fh_end = fh_start + 168

            for fh in range(fh_start, fh_end):
                ts = _closest_ts(fh)
                for loc_idx in range(num_nodes):
                    node_id = int(meta.iloc[loc_idx]["node_id"])
                    wx = _get_weather(loc_idx, ts)
                    pred_rows.append({
                        "node_id": node_id,
                        "forecast_hour": fh,
                        "sample_hour": sample_hour,
                        **wx,
                    })

        pred_df = pd.DataFrame(pred_rows)
        append_predicted(OUTPUT_HDF5, pred_df)
        total_pred += len(pred_df)
        print(f"    Batch sh={sh_start}-{sh_end-1}: {len(pred_df):,} rows (total: {total_pred:,})")

    print(f"    Predicted total: {total_pred:,} rows")

    # ── Step 4: Verify ─────────────────────────────────────────────
    print(f"\n[4/4] Verifying output...")

    import h5py
    with h5py.File(OUTPUT_HDF5, "r") as f:
        n_meta = len(f["metadata"])
        n_actual = len(f["actual_weather"])
        n_pred = len(f["predicted_weather"])

    file_size = os.path.getsize(OUTPUT_HDF5) / (1024 * 1024)
    total_time = time.time() - t0

    print(f"  Metadata:  {n_meta} nodes")
    print(f"  Actual:    {n_actual:,} rows (original: 18,492)")
    print(f"  Predicted: {n_pred:,} rows (original: 3,106,656)")
    print(f"  File size: {file_size:.1f} MB")

    print(f"\nDone in {total_time:.1f}s")
    print(f"  Output: {OUTPUT_HDF5}")
    print(f"  API calls: 2 (vs ~40,000 for real-time collection)")


if __name__ == "__main__":
    main()

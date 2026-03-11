"""
Weather data collector for the maritime route.

Ported from: test_files/multi_location_forecast_170wp.py
Key changes:
  - Config-driven (experiment.yaml), no hardcoded constants
  - Output to HDF5 via shared.hdf5_io, not pickle
  - Uses shared.beaufort.wind_speed_to_beaufort
  - Resume-aware via get_completed_runs()
  - Single waypoint failure logs warning + NaN row, doesn't abort
"""

import logging
import os
import signal
import time
from datetime import datetime, timezone, timedelta

import pandas as pd
import openmeteo_requests
import requests_cache
from retry_requests import retry

from shared.beaufort import wind_speed_to_beaufort
from shared.hdf5_io import (
    create_hdf5,
    append_actual,
    append_predicted,
    get_completed_runs,
)
from collect.waypoints import generate_waypoints, load_route_config

logger = logging.getLogger(__name__)

# API endpoints
WIND_API_URL = "https://api.open-meteo.com/v1/forecast"
MARINE_API_URL = "https://marine-api.open-meteo.com/v1/marine"

# Max locations per bulk request (avoids 414 URI Too Large)
BULK_CHUNK_SIZE = 100

WIND_HOURLY_VARIABLES = ["wind_speed_10m", "wind_direction_10m"]
WIND_CURRENT_VARIABLES = ["wind_speed_10m", "wind_direction_10m"]
MARINE_HOURLY_VARIABLES = ["ocean_current_velocity", "ocean_current_direction", "wave_height"]
MARINE_CURRENT_VARIABLES = ["wave_height", "ocean_current_velocity", "ocean_current_direction"]


# ---------------------------------------------------------------------------
# API setup
# ---------------------------------------------------------------------------

def setup_api_client():
    """Setup Open-Meteo API client with niquests session and 30s timeout.

    No cache, no retry middleware — retries are handled explicitly in
    the collection loop (run_all.py) to avoid blocking on rate limits.
    """
    import niquests
    session = niquests.Session(timeout=30)
    return openmeteo_requests.Client(session=session)


# ---------------------------------------------------------------------------
# Data fetching
# ---------------------------------------------------------------------------

def _chunked_bulk(client, url, lats, lons, hourly_vars, current_vars, api_delay):
    """Fetch data for all locations, chunking to avoid 414 URI Too Large.

    Splits locations into batches of BULK_CHUNK_SIZE and concatenates results.

    Returns:
        List[WeatherApiResponse], one per location in order.
    """
    all_responses = []
    n = len(lats)
    for start in range(0, n, BULK_CHUNK_SIZE):
        end = min(start + BULK_CHUNK_SIZE, n)
        params = {
            "latitude": ",".join(f"{lat:.4f}" for lat in lats[start:end]),
            "longitude": ",".join(f"{lon:.4f}" for lon in lons[start:end]),
            "hourly": ",".join(hourly_vars),
            "current": ",".join(current_vars),
            "timezone": "GMT",
        }
        responses = client.weather_api(url, params=params)
        all_responses.extend(responses)
        if end < n:
            time.sleep(api_delay)
    return all_responses


def fetch_wind_bulk(client, lats, lons, api_delay=0.1):
    """Fetch wind data for all locations in chunked bulk calls."""
    return _chunked_bulk(client, WIND_API_URL, lats, lons,
                         WIND_HOURLY_VARIABLES, WIND_CURRENT_VARIABLES, api_delay)


def fetch_marine_bulk(client, lats, lons, api_delay=0.1):
    """Fetch marine data for all locations in chunked bulk calls."""
    return _chunked_bulk(client, MARINE_API_URL, lats, lons,
                         MARINE_HOURLY_VARIABLES, MARINE_CURRENT_VARIABLES, api_delay)


def _parse_bulk_responses(wind_responses, marine_responses, node_ids, sample_hour, voyage_start_time):
    """Parse bulk API responses into actual_rows + predicted_rows lists.

    Args:
        wind_responses: List of wind WeatherApiResponse (one per location).
        marine_responses: List of marine WeatherApiResponse (one per location).
        node_ids: List of node IDs matching response order.
        sample_hour: Integer sample hour index.
        voyage_start_time: datetime of voyage start.

    Returns:
        (actual_rows, predicted_rows, failed_count)
    """
    actual_rows = []
    predicted_rows = []
    failed = 0

    for i, node_id in enumerate(node_ids):
        try:
            wind_resp = wind_responses[i]
            marine_resp = marine_responses[i]

            # --- Current (actual) conditions ---
            wind_cur = wind_resp.Current()
            marine_cur = marine_resp.Current()
            ws_curr = wind_cur.Variables(0).Value()

            actual = {
                "node_id": node_id,
                "sample_hour": sample_hour,
                "wind_speed_10m_kmh": ws_curr,
                "wind_direction_10m_deg": wind_cur.Variables(1).Value(),
                "beaufort_number": wind_speed_to_beaufort(ws_curr),
                "wave_height_m": marine_cur.Variables(0).Value(),
                "ocean_current_velocity_kmh": marine_cur.Variables(1).Value(),
                "ocean_current_direction_deg": marine_cur.Variables(2).Value(),
            }
            actual_rows.append(actual)

            # --- Hourly (predicted) conditions ---
            wind_hourly = wind_resp.Hourly()
            wind_time = pd.date_range(
                start=pd.to_datetime(wind_hourly.Time(), unit="s", utc=True),
                end=pd.to_datetime(wind_hourly.TimeEnd(), unit="s", utc=True),
                freq=pd.Timedelta(seconds=wind_hourly.Interval()),
                inclusive="left",
            )
            wind_speed_vals = wind_hourly.Variables(0).ValuesAsNumpy()
            wind_dir_vals = wind_hourly.Variables(1).ValuesAsNumpy()

            marine_hourly = marine_resp.Hourly()
            marine_time = pd.date_range(
                start=pd.to_datetime(marine_hourly.Time(), unit="s", utc=True),
                end=pd.to_datetime(marine_hourly.TimeEnd(), unit="s", utc=True),
                freq=pd.Timedelta(seconds=marine_hourly.Interval()),
                inclusive="left",
            )
            marine_vel_vals = marine_hourly.Variables(0).ValuesAsNumpy()
            marine_dir_vals = marine_hourly.Variables(1).ValuesAsNumpy()
            marine_wave_vals = marine_hourly.Variables(2).ValuesAsNumpy()

            # Index marine by timestamp for merging
            marine_by_time = {}
            for j, t in enumerate(marine_time):
                marine_by_time[t] = (
                    float(marine_vel_vals[j]),
                    float(marine_dir_vals[j]),
                    float(marine_wave_vals[j]),
                )

            for j, forecast_time in enumerate(wind_time):
                forecast_hours = (forecast_time.replace(tzinfo=None) - voyage_start_time).total_seconds() / 3600
                forecast_hour = round(forecast_hours)
                ws = float(wind_speed_vals[j])

                row = {
                    "node_id": node_id,
                    "forecast_hour": forecast_hour,
                    "sample_hour": sample_hour,
                    "wind_speed_10m_kmh": ws,
                    "wind_direction_10m_deg": float(wind_dir_vals[j]),
                    "beaufort_number": wind_speed_to_beaufort(ws),
                }

                if forecast_time in marine_by_time:
                    vel, d, wh = marine_by_time[forecast_time]
                    row["wave_height_m"] = wh
                    row["ocean_current_velocity_kmh"] = vel
                    row["ocean_current_direction_deg"] = d
                else:
                    row["wave_height_m"] = float("nan")
                    row["ocean_current_velocity_kmh"] = float("nan")
                    row["ocean_current_direction_deg"] = float("nan")

                predicted_rows.append(row)

        except Exception as e:
            failed += 1
            if failed <= 5:
                logger.warning("Node %d parse error: %s", node_id, e)
            actual_rows.append(_nan_actual_row(node_id, sample_hour))

    return actual_rows, predicted_rows, failed


def _nan_actual_row(node_id, sample_hour):
    """Create a NaN actual row for a failed waypoint."""
    return {
        "node_id": node_id,
        "sample_hour": sample_hour,
        "wind_speed_10m_kmh": float("nan"),
        "wind_direction_10m_deg": float("nan"),
        "beaufort_number": 0,
        "wave_height_m": float("nan"),
        "ocean_current_velocity_kmh": float("nan"),
        "ocean_current_direction_deg": float("nan"),
    }


# ---------------------------------------------------------------------------
# NWP cycle alignment
# ---------------------------------------------------------------------------

def _next_nwp_time(nwp_offset_utc, interval_hours):
    """Compute the next UTC datetime when an NWP update is expected.

    GFS runs at 00/06/12/18 UTC with ~5h propagation delay to Open-Meteo.
    So fresh data arrives at approximately 05/11/17/23 UTC (offset=5).

    Args:
        nwp_offset_utc: Hours after each cycle start when data arrives (e.g. 5).
        interval_hours: NWP cycle interval (e.g. 6).

    Returns:
        datetime (UTC, aware) of the next expected update.
    """
    now = datetime.now(timezone.utc)
    # Target hours within the day: offset, offset+interval, offset+2*interval, ...
    targets = [(nwp_offset_utc + i * interval_hours) % 24
               for i in range(24 // interval_hours)]
    targets.sort()

    # Find the next target hour today or tomorrow
    for t in targets:
        candidate = now.replace(hour=t, minute=0, second=0, microsecond=0)
        if candidate > now:
            return candidate
    # All today's targets have passed — use first target tomorrow
    tomorrow = now + timedelta(days=1)
    return tomorrow.replace(hour=targets[0], minute=0, second=0, microsecond=0)


# ---------------------------------------------------------------------------
# Main collection loop
# ---------------------------------------------------------------------------

def collect(config, hdf5_path=None):
    """Run the weather collection loop.

    Args:
        config: Full experiment config dict.
        hdf5_path: Override output path (default: pipeline/data/voyage_weather.h5).

    Supports indefinite collection when hours=0: runs until interrupted.
    Handles SIGINT/SIGTERM gracefully — finishes the current sample, then exits.
    Resumes from the last completed sample_hour on restart.

    NWP-aligned collection (optional):
        sample_interval_hours: 6    — collect every 6h instead of every 1h
        nwp_offset_utc: 5           — align to GFS cycle (data arrives ~05/11/17/23 UTC)
    When both are set, the collector sleeps until the next NWP update time
    instead of using a fixed wait. Sample hours increment by sample_interval_hours.
    """
    # Load route config and generate waypoints
    route_config = load_route_config(config)
    interval_nm = config["collection"].get("interval_nm", 1.0)
    hours = config["collection"].get("hours", 72)
    api_delay = config["collection"].get("api_delay_seconds", 0.1)
    sample_interval = config["collection"].get("sample_interval_hours", 1)
    nwp_offset = config["collection"].get("nwp_offset_utc", None)
    indefinite = hours == 0

    if hdf5_path is None:
        pipeline_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        hdf5_path = os.path.join(pipeline_dir, "data", "voyage_weather.h5")

    waypoints_df = generate_waypoints(route_config, interval_nm=interval_nm)
    print(f"Generated {len(waypoints_df)} waypoints at {interval_nm} nm intervals")

    if sample_interval > 1 or nwp_offset is not None:
        nwp_info = f", NWP offset={nwp_offset} UTC" if nwp_offset is not None else ""
        print(f"Sample interval: every {sample_interval}h{nwp_info}")

    # Create HDF5 if it doesn't exist
    if not os.path.exists(hdf5_path):
        attrs = {
            "route_name": route_config.get("name", "unknown"),
            "interval_nm": interval_nm,
            "planned_hours": hours,
            "sample_interval_hours": sample_interval,
            "source": "live_collection",
        }
        create_hdf5(hdf5_path, waypoints_df, attrs)
        print(f"Created HDF5 file: {hdf5_path}")

    # Check what's already collected
    completed = get_completed_runs(hdf5_path)
    print(f"Already completed: {len(completed)} runs ({sorted(completed)[-5:] if completed else []})")

    # Determine starting sample_hour for resume
    next_hour = (max(completed) + sample_interval) if completed else 0

    # Graceful shutdown via SIGINT/SIGTERM
    shutdown_requested = [False]

    def _signal_handler(signum, frame):
        sig_name = signal.Signals(signum).name
        print(f"\n  [{sig_name}] Shutdown requested — finishing current sample...")
        shutdown_requested[0] = True

    prev_sigint = signal.signal(signal.SIGINT, _signal_handler)
    prev_sigterm = signal.signal(signal.SIGTERM, _signal_handler)

    # Setup API client
    client = setup_api_client()
    voyage_start_time = datetime.now()
    collection_start = time.time()

    try:
        sample_hour = next_hour
        while True:
            # Check bounds for finite mode
            if not indefinite and sample_hour >= hours:
                break

            if sample_hour in completed:
                sample_hour += 1
                continue

            if indefinite:
                print(f"\n--- Sample hour {sample_hour} (indefinite mode) ---")
            else:
                print(f"\n--- Sample hour {sample_hour}/{hours - 1} ---")
            start_time = time.time()

            lats = waypoints_df["lat"].tolist()
            lons = waypoints_df["lon"].tolist()
            node_ids = waypoints_df["node_id"].tolist()

            max_retries = 5
            for attempt in range(max_retries):
                try:
                    wind_responses = fetch_wind_bulk(client, lats, lons, api_delay)
                    time.sleep(api_delay)
                    marine_responses = fetch_marine_bulk(client, lats, lons, api_delay)

                    actual_rows, predicted_rows, failed = _parse_bulk_responses(
                        wind_responses, marine_responses, node_ids,
                        sample_hour, voyage_start_time,
                    )
                    successful = len(node_ids) - failed
                    break  # success
                except Exception as e:
                    is_rate_limit = "rate" in str(e).lower() or "limit" in str(e).lower()
                    if is_rate_limit and attempt < max_retries - 1:
                        wait_secs = 60 * (attempt + 1)  # 60, 120, 180, 240s
                        logger.warning("Rate limited (attempt %d/%d), waiting %ds: %s",
                                       attempt + 1, max_retries, wait_secs, e)
                        time.sleep(wait_secs)
                        continue
                    logger.error("Bulk API call failed (attempt %d/%d): %s",
                                 attempt + 1, max_retries, e)
                    actual_rows = [_nan_actual_row(nid, sample_hour) for nid in node_ids]
                    predicted_rows = []
                    failed = len(node_ids)
                    successful = 0
                    break

            # Batch append to HDF5
            append_actual(hdf5_path, pd.DataFrame(actual_rows))
            if predicted_rows:
                append_predicted(hdf5_path, pd.DataFrame(predicted_rows))

            elapsed = time.time() - start_time
            wall_hours = (time.time() - collection_start) / 3600
            h5_size_mb = os.path.getsize(hdf5_path) / (1024 * 1024)
            total_collected = len(completed) + (sample_hour - next_hour + 1)
            print(f"  {successful}/{len(waypoints_df)} OK, {failed} failed, {elapsed:.1f}s")
            print(f"  Actual: {len(actual_rows)} rows, Predicted: {len(predicted_rows)} rows")
            print(f"  Total hours collected: {total_collected}, HDF5: {h5_size_mb:.1f} MB, wall: {wall_hours:.1f}h")

            # Check for shutdown request
            if shutdown_requested[0]:
                print(f"\nGraceful shutdown after sample hour {sample_hour}. Output: {hdf5_path}")
                return

            # Wait before next sample
            is_last = not indefinite and sample_hour + sample_interval >= hours
            if not is_last:
                if nwp_offset is not None:
                    # Align to NWP cycle: sleep until next update time
                    target = _next_nwp_time(nwp_offset, sample_interval)
                    now_utc = datetime.now(timezone.utc)
                    wait = max(0, (target - now_utc).total_seconds())
                    print(f"  Next NWP update: {target.strftime('%H:%M UTC')} (waiting {wait/60:.0f} min)")
                else:
                    wait = max(0, sample_interval * 3600 - elapsed)
                    if wait > 0:
                        print(f"  Waiting {wait/60:.0f} min until next sample...")
                if wait > 0:
                    try:
                        time.sleep(wait)
                    except (KeyboardInterrupt, SystemExit):
                        print(f"\nShutdown during wait after sample hour {sample_hour}. Output: {hdf5_path}")
                        return
                    if shutdown_requested[0]:
                        print(f"\nGraceful shutdown after sample hour {sample_hour}. Output: {hdf5_path}")
                        return

            sample_hour += sample_interval
    finally:
        # Restore original signal handlers
        signal.signal(signal.SIGINT, prev_sigint)
        signal.signal(signal.SIGTERM, prev_sigterm)

    print(f"\nCollection complete. Output: {hdf5_path}")

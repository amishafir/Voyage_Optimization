"""
HDF5 I/O for voyage weather data.

Schema:
    /metadata           — fixed table: node_id, lon, lat, waypoint_name, is_original, distance_from_start_nm, segment
    /actual_weather     — appendable: node_id, sample_hour, + 6 weather fields
    /predicted_weather  — appendable: node_id, forecast_hour, sample_hour, + 6 weather fields
    attrs               — voyage_start_time, route_name, created_at, source, etc.
"""

import logging
import os
import pickle
from datetime import datetime

import h5py
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Structured NumPy dtypes
# ---------------------------------------------------------------------------

METADATA_DTYPE = np.dtype([
    ("node_id", "i4"),
    ("lon", "f8"),
    ("lat", "f8"),
    ("waypoint_name", "S50"),
    ("is_original", "?"),
    ("distance_from_start_nm", "f8"),
    ("segment", "i4"),
])

WEATHER_FIELDS = [
    ("wind_speed_10m_kmh", "f4"),
    ("wind_direction_10m_deg", "f4"),
    ("beaufort_number", "i1"),
    ("wave_height_m", "f4"),
    ("ocean_current_velocity_kmh", "f4"),
    ("ocean_current_direction_deg", "f4"),
]

ACTUAL_DTYPE = np.dtype([
    ("node_id", "i4"),
    ("sample_hour", "i4"),
] + WEATHER_FIELDS)

PREDICTED_DTYPE = np.dtype([
    ("node_id", "i4"),
    ("forecast_hour", "i4"),
    ("sample_hour", "i4"),
] + WEATHER_FIELDS)


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------

def create_hdf5(path, metadata_df, attrs=None):
    """Create a new HDF5 file with metadata table and global attributes.

    Args:
        path: Output file path.
        metadata_df: DataFrame with columns matching METADATA_DTYPE.
        attrs: Optional dict of global attributes.
    """
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)

    meta_arr = np.empty(len(metadata_df), dtype=METADATA_DTYPE)
    meta_arr["node_id"] = metadata_df["node_id"].values
    meta_arr["lon"] = metadata_df["lon"].values
    meta_arr["lat"] = metadata_df["lat"].values
    meta_arr["waypoint_name"] = metadata_df["waypoint_name"].astype(str).values.astype("S50")
    meta_arr["is_original"] = metadata_df["is_original"].values
    meta_arr["distance_from_start_nm"] = metadata_df["distance_from_start_nm"].values
    meta_arr["segment"] = metadata_df["segment"].values

    with h5py.File(path, "w") as f:
        # Global attributes
        f.attrs["created_at"] = datetime.now().isoformat()
        if attrs:
            for k, v in attrs.items():
                f.attrs[k] = v

        # Fixed metadata dataset
        f.create_dataset("metadata", data=meta_arr)

        # Appendable weather datasets (start empty)
        f.create_dataset(
            "actual_weather",
            shape=(0,),
            maxshape=(None,),
            dtype=ACTUAL_DTYPE,
            chunks=(10000,),
            compression="gzip",
        )
        f.create_dataset(
            "predicted_weather",
            shape=(0,),
            maxshape=(None,),
            dtype=PREDICTED_DTYPE,
            chunks=(10000,),
            compression="gzip",
        )

    logger.info("Created HDF5 file %s with %d nodes", path, len(metadata_df))


# ---------------------------------------------------------------------------
# Append
# ---------------------------------------------------------------------------

def _df_to_structured(df, dtype):
    """Convert a DataFrame to a structured NumPy array."""
    arr = np.empty(len(df), dtype=dtype)
    for name in dtype.names:
        if name in df.columns:
            arr[name] = df[name].values
        else:
            arr[name] = 0
    return arr


def append_actual(path, dataframe):
    """Append rows to /actual_weather table.

    Args:
        path: HDF5 file path.
        dataframe: DataFrame with columns: node_id, sample_hour, + 6 weather fields.
    """
    arr = _df_to_structured(dataframe, ACTUAL_DTYPE)
    with h5py.File(path, "a") as f:
        ds = f["actual_weather"]
        old_len = ds.shape[0]
        ds.resize(old_len + len(arr), axis=0)
        ds[old_len:] = arr
    logger.debug("Appended %d actual rows (total %d)", len(arr), old_len + len(arr))


def append_predicted(path, dataframe):
    """Append rows to /predicted_weather table.

    Args:
        path: HDF5 file path.
        dataframe: DataFrame with columns: node_id, forecast_hour, sample_hour, + 6 weather fields.
    """
    arr = _df_to_structured(dataframe, PREDICTED_DTYPE)
    with h5py.File(path, "a") as f:
        ds = f["predicted_weather"]
        old_len = ds.shape[0]
        ds.resize(old_len + len(arr), axis=0)
        ds[old_len:] = arr
    logger.debug("Appended %d predicted rows (total %d)", len(arr), old_len + len(arr))


# ---------------------------------------------------------------------------
# Read
# ---------------------------------------------------------------------------

def read_metadata(path):
    """Read /metadata table as DataFrame.

    Returns:
        DataFrame with decoded string columns.
    """
    with h5py.File(path, "r") as f:
        arr = f["metadata"][:]
    df = pd.DataFrame(arr)
    # Decode bytes to str
    df["waypoint_name"] = df["waypoint_name"].apply(
        lambda b: b.decode("utf-8") if isinstance(b, bytes) else str(b)
    )
    return df


def read_actual(path, sample_hour=None, node_id=None):
    """Read /actual_weather with optional filters.

    Args:
        path: HDF5 file path.
        sample_hour: Filter by sample_hour (int).
        node_id: Filter by node_id (int).

    Returns:
        DataFrame.
    """
    with h5py.File(path, "r") as f:
        arr = f["actual_weather"][:]
    if len(arr) == 0:
        return pd.DataFrame(columns=[n for n in ACTUAL_DTYPE.names])
    df = pd.DataFrame(arr)
    if sample_hour is not None:
        df = df[df["sample_hour"] == int(sample_hour)]
    if node_id is not None:
        df = df[df["node_id"] == int(node_id)]
    return df.reset_index(drop=True)


def read_predicted(path, sample_hour=None, forecast_hour=None, node_id=None):
    """Read /predicted_weather with optional filters.

    Args:
        path: HDF5 file path.
        sample_hour: Filter by sample_hour (int).
        forecast_hour: Filter by forecast_hour (int).
        node_id: Filter by node_id (int).

    Returns:
        DataFrame.
    """
    with h5py.File(path, "r") as f:
        arr = f["predicted_weather"][:]
    if len(arr) == 0:
        return pd.DataFrame(columns=[n for n in PREDICTED_DTYPE.names])
    df = pd.DataFrame(arr)
    if sample_hour is not None:
        df = df[df["sample_hour"] == int(sample_hour)]
    if forecast_hour is not None:
        df = df[df["forecast_hour"] == int(forecast_hour)]
    if node_id is not None:
        df = df[df["node_id"] == int(node_id)]
    return df.reset_index(drop=True)


# ---------------------------------------------------------------------------
# Attributes & helpers
# ---------------------------------------------------------------------------

def get_attrs(path):
    """Read global attributes dict."""
    with h5py.File(path, "r") as f:
        attrs = {}
        for k, v in f.attrs.items():
            if isinstance(v, bytes):
                v = v.decode("utf-8")
            attrs[k] = v
        return attrs


def get_completed_runs(path):
    """Return sorted list of distinct sample_hour values in /actual_weather."""
    with h5py.File(path, "r") as f:
        ds = f["actual_weather"]
        if ds.shape[0] == 0:
            return []
        hours = ds["sample_hour"][:]
    return sorted(set(int(h) for h in hours))


# ---------------------------------------------------------------------------
# Pickle import
# ---------------------------------------------------------------------------

class _PlaceholderNode:
    """Accepts any attributes set by pickle deserialization."""
    pass


class _SafeUnpickler(pickle.Unpickler):
    """Map any Node class to our placeholder."""
    def find_class(self, module, name):
        if name == "Node":
            return _PlaceholderNode
        return super().find_class(module, name)


def _infer_segments(nodes):
    """Infer segment index from is_original flags.

    Original waypoints mark segment boundaries:
    - Original[0] starts segment 0
    - Original[k] (k < N-1) starts segment k
    - Port B (last original) belongs to the last segment
    """
    original_indices = [
        i for i, n in enumerate(nodes)
        if getattr(n, "waypoint_info", None) and n.waypoint_info.get("is_original")
    ]

    if not original_indices:
        return [0] * len(nodes)

    num_segments = max(len(original_indices) - 1, 1)
    segments = [0] * len(nodes)

    for seg_idx in range(num_segments):
        start = original_indices[seg_idx]
        if seg_idx < num_segments - 1:
            end = original_indices[seg_idx + 1]
        else:
            end = len(nodes)
        for i in range(start, end):
            segments[i] = seg_idx

    return segments


def import_from_pickle(pickle_path, hdf5_path, route_config=None):
    """Convert a legacy pickle file to HDF5 format.

    Args:
        pickle_path: Path to input pickle file.
        hdf5_path: Path to output HDF5 file.
        route_config: Route config dict (optional, used for attrs).
    """
    logger.info("Loading pickle: %s", pickle_path)

    with open(pickle_path, "rb") as f:
        data = _SafeUnpickler(f).load()

    # Detect wrapper format
    if isinstance(data, dict):
        nodes = data["nodes"]
        voyage_start_time = data.get("voyage_start_time")
        wrapper_format = "dict_wrapper"
    elif isinstance(data, list):
        nodes = data
        voyage_start_time = None
        wrapper_format = "raw_list"
    else:
        raise ValueError(f"Unknown pickle format: {type(data)}")

    logger.info("Loaded %d nodes (%s format)", len(nodes), wrapper_format)

    # Infer segments from is_original flags
    segments = _infer_segments(nodes)

    # Build metadata DataFrame
    meta_rows = []
    for i, node in enumerate(nodes):
        lon, lat = node.node_index
        info = getattr(node, "waypoint_info", None) or {}
        meta_rows.append({
            "node_id": i,
            "lon": lon,
            "lat": lat,
            "waypoint_name": info.get("name", f"node_{i}"),
            "is_original": info.get("is_original", False),
            "distance_from_start_nm": info.get("distance_from_start_nm", 0.0),
            "segment": segments[i],
        })
    metadata_df = pd.DataFrame(meta_rows)

    # Prepare attributes
    attrs = {
        "source": "pickle_import",
        "source_file": os.path.basename(pickle_path),
        "wrapper_format": wrapper_format,
        "num_nodes": len(nodes),
    }
    if voyage_start_time is not None:
        attrs["voyage_start_time"] = str(voyage_start_time)
    if route_config:
        attrs["route_name"] = route_config.get("name", "unknown")

    # Create HDF5 with metadata
    create_hdf5(hdf5_path, metadata_df, attrs)

    # Process nodes in batches for weather data
    BATCH_SIZE = 100
    for batch_start in range(0, len(nodes), BATCH_SIZE):
        batch_end = min(batch_start + BATCH_SIZE, len(nodes))
        batch_nodes = nodes[batch_start:batch_end]

        actual_rows = []
        predicted_rows = []

        for node_offset, node in enumerate(batch_nodes):
            node_id = batch_start + node_offset

            # Actual weather
            actual = getattr(node, "Actual_weather_conditions", None) or {}
            for key, weather in actual.items():
                sample_hour = int(round(key))
                row = {"node_id": node_id, "sample_hour": sample_hour}
                for field_name, _ in WEATHER_FIELDS:
                    val = weather.get(field_name, float("nan"))
                    if val is None:
                        val = float("nan")
                    row[field_name] = val
                actual_rows.append(row)

            # Predicted weather
            predicted = getattr(node, "Predicted_weather_conditions", None) or {}
            for forecast_key, sub_dict in predicted.items():
                forecast_hour = int(round(forecast_key))
                for sample_key, weather in sub_dict.items():
                    sample_hour = int(round(sample_key))
                    row = {
                        "node_id": node_id,
                        "forecast_hour": forecast_hour,
                        "sample_hour": sample_hour,
                    }
                    for field_name, _ in WEATHER_FIELDS:
                        val = weather.get(field_name, float("nan"))
                        if val is None:
                            val = float("nan")
                        row[field_name] = val
                    predicted_rows.append(row)

        if actual_rows:
            append_actual(hdf5_path, pd.DataFrame(actual_rows))
        if predicted_rows:
            append_predicted(hdf5_path, pd.DataFrame(predicted_rows))

        logger.info(
            "Batch %d-%d: %d actual, %d predicted rows",
            batch_start, batch_end - 1, len(actual_rows), len(predicted_rows),
        )

    # Final summary
    runs = get_completed_runs(hdf5_path)
    logger.info(
        "Conversion complete: %d nodes, %d sample hours, output: %s",
        len(nodes), len(runs), hdf5_path,
    )
    print(f"Converted {len(nodes)} nodes, {len(runs)} sample hours -> {hdf5_path}")

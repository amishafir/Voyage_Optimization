"""
HDF5 I/O for voyage weather data.

Stub — implementation in Phase 1.
"""


def create_hdf5(path, metadata, attrs=None):
    """Create a new HDF5 file with metadata table and global attributes."""
    raise NotImplementedError("Phase 1")


def append_actual(path, dataframe):
    """Append rows to /actual_weather table."""
    raise NotImplementedError("Phase 1")


def append_predicted(path, dataframe):
    """Append rows to /predicted_weather table."""
    raise NotImplementedError("Phase 1")


def read_metadata(path):
    """Read /metadata table as DataFrame."""
    raise NotImplementedError("Phase 1")


def read_actual(path, sample_hour=None, node_id=None):
    """Read /actual_weather with optional filters."""
    raise NotImplementedError("Phase 1")


def read_predicted(path, sample_hour=None, forecast_hour=None, node_id=None):
    """Read /predicted_weather with optional filters."""
    raise NotImplementedError("Phase 1")


def get_attrs(path):
    """Read global attributes dict."""
    raise NotImplementedError("Phase 1")


def get_completed_runs(path):
    """Return sorted list of distinct sample_hour values in /actual_weather."""
    raise NotImplementedError("Phase 1")


def import_from_pickle(pickle_path, hdf5_path, route_config):
    """Convert a legacy pickle file to HDF5 format."""
    raise NotImplementedError("Phase 1")

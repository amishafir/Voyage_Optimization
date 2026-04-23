"""
HDF5 weather loader for the Persian Gulf -> Malacca route.

Backed by `pipeline/data/voyage_weather.h5`. Loads 279 interpolated waypoints
(lat/lon/distance/segment) plus time-varying weather — actual (12 h of samples)
and predicted (168 forecast-hours x 12 sample-hours per node).

Exposes the interface the rebuild graph needs:
  - waypoint list with distance / lat / lon / segment
  - segment boundaries (cumulative distances)
  - weather-cell boundaries (where the route crosses a 0.5° marine grid cell)
  - weather_at(d, sample_hour=0, forecast_hour=None) -> dict
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

import h5py
import numpy as np


WEATHER_FIELDS = (
    "wind_speed_10m_kmh",
    "wind_direction_10m_deg",
    "beaufort_number",
    "wave_height_m",
    "ocean_current_velocity_kmh",
    "ocean_current_direction_deg",
)


@dataclass
class Waypoint:
    node_id: int
    distance_nm: float
    lat: float
    lon: float
    segment: int


class VoyageWeather:
    """Read-only view over voyage_weather.h5."""

    def __init__(self, h5_path: Path | str):
        self.path = Path(h5_path)
        with h5py.File(self.path, "r") as f:
            md = f["metadata"][()]
            self._waypoints: List[Waypoint] = [
                Waypoint(
                    node_id=int(row["node_id"]),
                    distance_nm=float(row["distance_from_start_nm"]),
                    lat=float(row["lat"]),
                    lon=float(row["lon"]),
                    segment=int(row["segment"]),
                )
                for row in md
            ]
            # Sort by distance just to be safe — metadata should already be ordered.
            self._waypoints.sort(key=lambda w: w.distance_nm)
            self._distances = np.array([w.distance_nm for w in self._waypoints])

            # Actual weather indexed as (node_id, sample_hour) -> row
            aw = f["actual_weather"][()]
            self._actual: Dict[tuple[int, int], np.void] = {
                (int(r["node_id"]), int(r["sample_hour"])): r for r in aw
            }
            self._sample_hours = sorted({int(r["sample_hour"]) for r in aw})

            # Predicted weather indexed as (node_id, forecast_hour, sample_hour) -> row
            # This can be large; keep as a dict keyed by the triple.
            pw = f["predicted_weather"][()]
            self._predicted: Dict[tuple[int, int, int], np.void] = {
                (int(r["node_id"]), int(r["forecast_hour"]), int(r["sample_hour"])): r
                for r in pw
            }
            self._forecast_hours = sorted({int(r["forecast_hour"]) for r in pw})

            self._attrs = dict(f.attrs)

    # ------------------------------------------------------------------
    # Route geometry
    # ------------------------------------------------------------------

    @property
    def length_nm(self) -> float:
        return float(self._waypoints[-1].distance_nm)

    @property
    def waypoints(self) -> List[Waypoint]:
        return self._waypoints

    @property
    def num_waypoints(self) -> int:
        return len(self._waypoints)

    @property
    def sample_hours(self) -> List[int]:
        return self._sample_hours

    @property
    def forecast_hours(self) -> List[int]:
        return self._forecast_hours

    @property
    def route_name(self) -> str:
        return str(self._attrs.get("route_name", "unknown"))

    def nearest_waypoint(self, d: float) -> Waypoint:
        """Waypoint with distance closest to d (clamped to route)."""
        d_clamped = max(0.0, min(d, self.length_nm))
        i = int(np.searchsorted(self._distances, d_clamped))
        if i == 0:
            return self._waypoints[0]
        if i >= len(self._waypoints):
            return self._waypoints[-1]
        left = self._waypoints[i - 1]
        right = self._waypoints[i]
        return left if abs(left.distance_nm - d_clamped) <= abs(right.distance_nm - d_clamped) else right

    # ------------------------------------------------------------------
    # H-line boundary generators
    # ------------------------------------------------------------------

    def segment_boundaries_nm(self) -> List[float]:
        """Cumulative distances at the *end* of each segment (interior only).

        Boundary is taken as the midpoint between the last waypoint of segment k
        and the first waypoint of segment k+1 (waypoints span but don't coincide
        at segment joins in the HDF5 — e.g. seg 0 ends at 204 nm, seg 1 starts
        at 223.74 nm).
        """
        out: List[float] = []
        prev_seg = self._waypoints[0].segment
        prev_d = self._waypoints[0].distance_nm
        for w in self._waypoints[1:]:
            if w.segment != prev_seg:
                out.append((prev_d + w.distance_nm) / 2.0)
            prev_seg = w.segment
            prev_d = w.distance_nm
        return out

    def weather_cell_boundaries_nm(self, grid_deg: float = 0.5) -> List[float]:
        """Distances where the route crosses a `grid_deg` NWP cell boundary.

        The route is sampled at waypoints (12 nm intervals here). We detect a
        cell change between consecutive waypoints and mark the boundary at the
        midpoint. Result can be used as H lines for weather-cell-driven decisions.
        """
        out: List[float] = []
        if not self._waypoints:
            return out
        prev = self._waypoints[0]
        prev_cell = (int(np.floor(prev.lat / grid_deg)), int(np.floor(prev.lon / grid_deg)))
        for w in self._waypoints[1:]:
            cell = (int(np.floor(w.lat / grid_deg)), int(np.floor(w.lon / grid_deg)))
            if cell != prev_cell:
                out.append((prev.distance_nm + w.distance_nm) / 2.0)
            prev = w
            prev_cell = cell
        return out

    # ------------------------------------------------------------------
    # Weather lookup
    # ------------------------------------------------------------------

    def weather_at(
        self,
        d: float,
        sample_hour: int = 0,
        forecast_hour: Optional[int] = None,
    ) -> Dict[str, float]:
        """Weather at distance d.

        `sample_hour`: when the observation (or forecast) was taken (0..11).
        `forecast_hour`: if not None, read predicted_weather at this forecast lead;
                        if None, read actual_weather.
        """
        wp = self.nearest_waypoint(d)
        if forecast_hour is None:
            key = (wp.node_id, int(sample_hour))
            row = self._actual.get(key)
            if row is None:
                raise KeyError(f"actual_weather missing for {key}")
        else:
            key3 = (wp.node_id, int(forecast_hour), int(sample_hour))
            row = self._predicted.get(key3)
            if row is None:
                raise KeyError(f"predicted_weather missing for {key3}")
        return {f: float(row[f]) for f in WEATHER_FIELDS}


def summarize(vw: VoyageWeather) -> None:
    print("=" * 70)
    print("VoyageWeather summary")
    print("=" * 70)
    print(f"Path:             {vw.path}")
    print(f"Route:            {vw.route_name}")
    print(f"Length:           {vw.length_nm:.2f} nm")
    print(f"Waypoints:        {vw.num_waypoints}")
    print(f"Sample hours:     {vw.sample_hours[0]}..{vw.sample_hours[-1]} ({len(vw.sample_hours)})")
    print(f"Forecast hours:   {vw.forecast_hours[0]}..{vw.forecast_hours[-1]} ({len(vw.forecast_hours)})")
    print(f"Lat range:        [{min(w.lat for w in vw.waypoints):.2f}, {max(w.lat for w in vw.waypoints):.2f}]")
    print(f"Lon range:        [{min(w.lon for w in vw.waypoints):.2f}, {max(w.lon for w in vw.waypoints):.2f}]")
    print("-" * 70)
    seg_b = vw.segment_boundaries_nm()
    print(f"Segment boundaries (interior): {len(seg_b)}")
    for i, d in enumerate(seg_b):
        print(f"  #{i+1:2d}: {d:8.2f} nm")
    print("-" * 70)
    for grid in (0.5, 0.25, 0.1):
        wc = vw.weather_cell_boundaries_nm(grid_deg=grid)
        print(f"Weather-cell boundaries at {grid}° grid: {len(wc)}")
    print("-" * 70)
    print("Example weather lookups:")
    for d in (0.0, 500.0, 1700.0, 3000.0):
        wx = vw.weather_at(d, sample_hour=0)
        print(f"  d={d:6.0f} nm @ sample_hour=0: "
              f"wind {wx['wind_speed_10m_kmh']:5.1f} kmh / {wx['wind_direction_10m_deg']:5.1f}°, "
              f"BN{int(wx['beaufort_number'])}, wave {wx['wave_height_m']:.2f} m, "
              f"current {wx['ocean_current_velocity_kmh']:.2f} kmh")
    print("=" * 70)


if __name__ == "__main__":
    h5_path = Path(__file__).resolve().parent.parent / "data" / "voyage_weather.h5"
    vw = VoyageWeather(h5_path)
    summarize(vw)

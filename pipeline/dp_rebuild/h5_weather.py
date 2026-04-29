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

from bisect import bisect_right
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

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


def _circular_mean_deg(angles_deg: List[float]) -> float:
    """Circular mean of angles in degrees, NaN-tolerant. Returns NaN if all NaN.

    Uses atan2 of mean(sin), mean(cos) to avoid wrap-around bias near 0°/360°.
    """
    valid = [a for a in angles_deg if not (a != a)]  # drop NaN
    if not valid:
        return float("nan")
    rads = np.deg2rad(np.asarray(valid, dtype=float))
    sin_mean = float(np.mean(np.sin(rads)))
    cos_mean = float(np.mean(np.cos(rads)))
    return float(np.rad2deg(np.arctan2(sin_mean, cos_mean)) % 360.0)


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

            # Pre-group waypoints by segment for segment-aware nearest lookups.
            self._wps_by_seg: Dict[int, List[Waypoint]] = defaultdict(list)
            for w in self._waypoints:
                self._wps_by_seg[w.segment].append(w)
            self._segments_in_order = sorted(self._wps_by_seg.keys())

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

        # Per-cell aggregation cache + index. Lazy by grid_deg.
        # _cell_index[grid_deg][(lat_idx, lon_idx)] -> [Waypoint]
        # _cell_cache[(grid_deg, cell, sample_hour, forecast_hour)] -> dict
        self._cell_index: Dict[float, Dict[Tuple[int, int], List[Waypoint]]] = {}
        self._cell_cache: Dict[Tuple[float, Tuple[int, int], int, Optional[int]], Dict[str, float]] = {}

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
        """Cumulative distances at segment transitions.

        Uses the distance of the **first waypoint of each new segment** — this
        matches the YAML cumulative-segment-length semantic. E.g. the seg 0/1
        boundary lands at wp18's d = 223.74 nm (≈ YAML's 223.86 within
        interpolation rounding), not at the midpoint of the no-waypoint gap.
        """
        out: List[float] = []
        prev_seg = self._waypoints[0].segment
        for w in self._waypoints[1:]:
            if w.segment != prev_seg:
                out.append(w.distance_nm)
            prev_seg = w.segment
        return out

    def weather_cell_boundaries_nm(self, grid_deg: float = 0.5) -> List[float]:
        """Distances where the route crosses a `grid_deg` NWP cell boundary.

        Placed at the **midpoint** between the two waypoints that straddle the
        cell change. This matches the behaviour of `nearest_waypoint_in_segment`
        (which flips the returned waypoint at the waypoint-pair midpoint), so
        boundary placement and cell lookup stay internally consistent.

        Note: segment boundaries (see `segment_boundaries_nm`) use a different
        convention (first waypoint of the new segment) because segments have a
        no-waypoint gap at the transition — there's no adjacent-waypoint pair
        whose midpoint to use.
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
    # Segment-aware lookup
    # ------------------------------------------------------------------

    def segment_for_distance(self, d: float) -> int:
        """Which segment the route is in at distance d (by cumulative boundary).

        Uses `segment_boundaries_nm()` + bisect so the answer agrees with
        H-line placement: d < boundary → prev segment; d >= boundary → new
        segment. Handles the gap between segments consistently (gap zone is
        attributed to the previous segment, matching YAML).
        """
        boundaries = self.segment_boundaries_nm()
        first_seg = self._waypoints[0].segment if self._waypoints else 0
        return first_seg + bisect_right(boundaries, d)

    def nearest_waypoint_in_segment(self, d: float, seg: int) -> Waypoint:
        """Nearest waypoint within segment `seg`. Falls back to route nearest
        if the segment has no waypoints (shouldn't happen for real data)."""
        lst = self._wps_by_seg.get(seg)
        if not lst:
            return self.nearest_waypoint(d)
        return min(lst, key=lambda w: abs(w.distance_nm - d))

    def _row_has_nan(self, row) -> bool:
        """True if any of the marine fields on this weather row is NaN."""
        if row is None:
            return True
        for f in ("wind_speed_10m_kmh", "wind_direction_10m_deg",
                  "wave_height_m",
                  "ocean_current_velocity_kmh", "ocean_current_direction_deg"):
            v = row[f]
            if v != v:  # NaN check (NaN != NaN)
                return True
        return False

    def nearest_valid_waypoint_in_segment(
        self,
        d: float,
        seg: int,
        sample_hour: int,
        forecast_hour: Optional[int] = None,
    ) -> Waypoint:
        """Nearest waypoint within `seg` whose weather row at the given
        (sample_hour, forecast_hour) has no NaN fields.

        Fallback chain:
          1. nearest valid wp in `seg`
          2. nearest valid wp anywhere on the route
          3. plain nearest wp (NaN may propagate)

        Used by `weather_at` to keep the optimizer from dead-ending at the
        ~15 waypoints in segments 7/10/11 that the marine API leaves blank
        (Port B coastal & a few mid-voyage spots).
        """
        candidates = self._wps_by_seg.get(seg, [])
        valid_in_seg = []
        for w in candidates:
            row = self._row_for(w.node_id, sample_hour, forecast_hour)
            if not self._row_has_nan(row):
                valid_in_seg.append(w)
        if valid_in_seg:
            return min(valid_in_seg, key=lambda w: abs(w.distance_nm - d))

        valid_anywhere = []
        for w in self._waypoints:
            row = self._row_for(w.node_id, sample_hour, forecast_hour)
            if not self._row_has_nan(row):
                valid_anywhere.append(w)
        if valid_anywhere:
            return min(valid_anywhere, key=lambda w: abs(w.distance_nm - d))

        return self.nearest_waypoint(d)

    def _row_for(
        self,
        node_id: int,
        sample_hour: int,
        forecast_hour: Optional[int],
    ):
        if forecast_hour is None:
            return self._actual.get((node_id, int(sample_hour)))
        return self._predicted.get((node_id, int(forecast_hour), int(sample_hour)))

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

        Looks up the segment containing d, then returns the weather of the
        **nearest valid waypoint within that segment** (fallback chain in
        `nearest_valid_waypoint_in_segment`). This both:
        (a) handles the no-waypoint gap at segment joins by pulling weather
            from the correct side of the boundary, and
        (b) skips the ~15 NaN waypoints (marine API gaps near Port B and a
            few mid-voyage spots) that would otherwise dead-end the DP.

        `sample_hour`: when the observation (or forecast) was taken (0..11).
        `forecast_hour`: if not None, read predicted_weather at this forecast lead;
                        if None, read actual_weather.
        """
        seg = self.segment_for_distance(d)
        wp = self.nearest_valid_waypoint_in_segment(d, seg, sample_hour, forecast_hour)
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

    # ------------------------------------------------------------------
    # Per-cell mean weather aggregation (Qg5(b))
    # ------------------------------------------------------------------

    def _build_cell_index(self, grid_deg: float) -> None:
        """Lazy-build the cell -> [Waypoint] index for `grid_deg`."""
        if grid_deg in self._cell_index:
            return
        idx: Dict[Tuple[int, int], List[Waypoint]] = defaultdict(list)
        for w in self._waypoints:
            cell = (
                int(np.floor(w.lat / grid_deg)),
                int(np.floor(w.lon / grid_deg)),
            )
            idx[cell].append(w)
        self._cell_index[grid_deg] = idx

    def cell_weather(
        self,
        cell: Tuple[int, int],
        sample_hour: int = 0,
        forecast_hour: Optional[int] = None,
        grid_deg: float = 0.5,
    ) -> Dict[str, float]:
        """Cell-canonical weather (Qg5(b)).

        Returns the mean weather over every voyage waypoint that falls in
        `cell` = (lat_idx, lon_idx) at the given (sample_hour, forecast_hour):
          - linear mean for `wind_speed_10m_kmh`, `wave_height_m`,
            `ocean_current_velocity_kmh`
          - circular mean for `wind_direction_10m_deg`, `ocean_current_direction_deg`
          - int-rounded mean for `beaufort_number`
        Rows with any NaN field are dropped before averaging.

        If no valid waypoint sits in this cell, falls back to the nearest
        valid waypoint anywhere on the route. If the entire route's data
        is unavailable for this (sample_hour, forecast_hour), returns
        all-NaN.
        """
        sample_hour = int(sample_hour)
        fh = None if forecast_hour is None else int(forecast_hour)
        cache_key = (grid_deg, cell, sample_hour, fh)
        cached = self._cell_cache.get(cache_key)
        if cached is not None:
            return cached

        self._build_cell_index(grid_deg)
        wps = self._cell_index[grid_deg].get(cell, [])

        rows = []
        for w in wps:
            row = self._row_for(w.node_id, sample_hour, fh)
            if row is None or self._row_has_nan(row):
                continue
            rows.append(row)

        if not rows:
            # No geographic anchor here — return NaN. Callers with a distance
            # context (e.g. `cell_weather_at_d`) should fall back via
            # `weather_at(d)` so the substitute is *spatially* near, not just
            # the first valid row anywhere on the route.
            result = {f: float("nan") for f in WEATHER_FIELDS}
        else:
            wind_speeds = [float(r["wind_speed_10m_kmh"]) for r in rows]
            wave_heights = [float(r["wave_height_m"]) for r in rows]
            currents = [float(r["ocean_current_velocity_kmh"]) for r in rows]
            wind_dirs = [float(r["wind_direction_10m_deg"]) for r in rows]
            current_dirs = [float(r["ocean_current_direction_deg"]) for r in rows]
            bns = [float(r["beaufort_number"]) for r in rows]
            result = {
                "wind_speed_10m_kmh": float(np.mean(wind_speeds)),
                "wind_direction_10m_deg": _circular_mean_deg(wind_dirs),
                "beaufort_number": int(round(float(np.mean(bns)))),
                "wave_height_m": float(np.mean(wave_heights)),
                "ocean_current_velocity_kmh": float(np.mean(currents)),
                "ocean_current_direction_deg": _circular_mean_deg(current_dirs),
            }

        self._cell_cache[cache_key] = result
        return result

    def cell_weather_at_d(
        self,
        d: float,
        waypoints,
        sample_hour: int = 0,
        forecast_hour: Optional[int] = None,
        grid_deg: float = 0.5,
    ) -> Dict[str, float]:
        """Cell-canonical weather at voyage distance `d`.

        Computes (lat, lon) at d via rhumb-line interpolation along the
        paper-waypoint polyline (`geo_grid.position_at_d`), derives the
        cell, and returns `cell_weather` for that cell.
        """
        # Local import keeps h5_weather.py free of a hard dependency on
        # geo_grid for code paths that don't use cell aggregation.
        from geo_grid import position_at_d

        lat_at, lon_at, _seg = position_at_d(d, waypoints)
        cell = (
            int(np.floor(lat_at / grid_deg)),
            int(np.floor(lon_at / grid_deg)),
        )
        wx = self.cell_weather(
            cell,
            sample_hour=sample_hour,
            forecast_hour=forecast_hour,
            grid_deg=grid_deg,
        )
        # Empty cell (no valid waypoints in this lat/lon bin at this hour) —
        # fall back to the segment-aware nearest-valid lookup at this d so
        # the substitute is geographically near the probe point, not the
        # first valid waypoint on the route.
        if any(v != v for v in (
            wx["wind_speed_10m_kmh"],
            wx["wave_height_m"],
            wx["ocean_current_velocity_kmh"],
        )):
            fb = self.weather_at(
                d, sample_hour=sample_hour, forecast_hour=forecast_hour,
            )
            # weather_at returns BN as float; mirror cell_weather's int contract.
            fb["beaufort_number"] = int(round(float(fb["beaufort_number"])))
            return fb
        return wx


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

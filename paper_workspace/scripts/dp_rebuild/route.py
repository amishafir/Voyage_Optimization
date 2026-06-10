"""
DP graph rebuild — route loader.

Parses the legacy `weather_forecasts.yaml` format into a `Route` object.
Dropped fields: `current_angle` (Q_yaml_2: derived duplicate of `current_dir`).
Parser behavior for segment 6 duplicate `distance` (Q_yaml_3): YAML spec says
the last key wins → 287.34.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, List, Optional

import yaml


@dataclass
class Segment:
    id: int
    distance: float         # nm
    ship_heading: float     # deg
    wind_dir: float         # deg
    beaufort: int
    wave_height: float      # m
    current_dir: float      # deg
    current_speed: float    # knots


@dataclass
class ForecastWindow:
    start: float            # hours
    end: float              # hours
    segments: List[Segment]


@dataclass
class Route:
    windows: List[ForecastWindow]

    @property
    def length_nm(self) -> float:
        if not self.windows:
            return 0.0
        return sum(s.distance for s in self.windows[0].segments)

    @property
    def eta_h(self) -> float:
        if not self.windows:
            return 0.0
        return self.windows[-1].end

    def cumulative_segment_endpoints(self) -> List[float]:
        """Cumulative distance at each segment boundary (excluding the route endpoint).

        For 12 segments this returns 11 interior boundary distances; the terminal
        endpoint at L is added separately by the H-line builder.
        """
        if not self.windows:
            return []
        out: List[float] = []
        cum = 0.0
        segs = self.windows[0].segments
        for s in segs[:-1]:
            cum += s.distance
            out.append(cum)
        return out

    def segment_for_distance(self, d: float, window_idx: int = 0) -> Segment:
        """Return the segment containing distance d along the route."""
        cum = 0.0
        segs = self.windows[window_idx].segments
        for s in segs:
            cum += s.distance
            if d <= cum + 1e-9:
                return s
        return segs[-1]

    def window_for_time(self, t: float) -> ForecastWindow:
        """Return forecast window whose [start, end) contains t. Clamps to last."""
        for w in self.windows:
            if w.start - 1e-9 <= t < w.end - 1e-9:
                return w
        return self.windows[-1]

    def weather_at(self, t: float, d: float) -> Segment:
        """Weather = segment-at-d within the forecast-window-at-t."""
        w = self.window_for_time(t)
        cum = 0.0
        for s in w.segments:
            cum += s.distance
            if d <= cum + 1e-9:
                return s
        return w.segments[-1]


def load_yaml_route(path: Path | str) -> Route:
    """Load a weather_forecasts.yaml file into a Route."""
    with open(path) as f:
        data = yaml.safe_load(f)
    windows: List[ForecastWindow] = []
    for w in data.get("forecasts", []) or []:
        fw = w.get("forecast_window", {}) or {}
        start = float(fw["start"])
        end = float(fw["end"])
        segments: List[Segment] = []
        for s in w.get("segments_table", []) or []:
            segments.append(Segment(
                id=int(s["id"]),
                distance=float(s["distance"]),
                ship_heading=float(s["ship_heading"]),
                wind_dir=float(s["wind_dir"]),
                beaufort=int(s["beaufort"]),
                wave_height=float(s["wave_height"]),
                current_dir=float(s["current_dir"]),
                current_speed=float(s["current_speed"]),
                # current_angle intentionally dropped (Q_yaml_2)
            ))
        windows.append(ForecastWindow(start=start, end=end, segments=segments))
    return Route(windows=windows)


def build_route_from_waypoints_yaml(
    yaml_path: "Path | str",
    eta_h: Optional[float] = None,
    cruise_sog_kn: float = 12.0,
):
    """Build (Route, List[Waypoint]) from a waypoint-only YAML.

    For routes that DON'T ship with paper β / segment metadata (Route 2 onwards).
    Bearings are computed via rhumb_bearing_deg between consecutive waypoints;
    distances via rhumb_distance_nm. Weather fields on each Segment are
    placeholder zeros — the rebuild reads weather from the HDF5 cell-canonical
    lookup, not from the segment.

    YAML schema (`pipeline/config/routes/<name>.yaml`):
        name: <human label>
        description: …
        waypoints:
          - {lat: …, lon: …, name: <optional>}
          - …

    `eta_h`: voyage ETA in hours. If None, defaults to total rhumb / cruise_sog_kn.

    Returns `(route, waypoints)` — `route` is a single-window Route ready for
    `synthesize_multi_window`; `waypoints` is the canonical Waypoint list used
    by `frame.from_route`, `geo_grid.position_at_d`, etc.
    """
    # Local imports keep load_route importable without geo_grid / route_waypoints.
    from geo_grid import rhumb_bearing_deg, rhumb_distance_nm
    from route_waypoints import Waypoint

    with open(yaml_path) as f:
        data = yaml.safe_load(f)

    raw_wps = data.get("waypoints", []) or []
    if len(raw_wps) < 2:
        raise ValueError(f"Route YAML {yaml_path} must list ≥ 2 waypoints, got {len(raw_wps)}")

    waypoints: List[Waypoint] = [
        Waypoint(idx=i + 1,
                 lat_deg=float(wp["lat"]), lon_deg=float(wp["lon"]),
                 name=wp.get("name"))
        for i, wp in enumerate(raw_wps)
    ]

    segments: List[Segment] = []
    total_d = 0.0
    for i in range(len(waypoints) - 1):
        w1, w2 = waypoints[i], waypoints[i + 1]
        d = rhumb_distance_nm(w1.lat_deg, w1.lon_deg, w2.lat_deg, w2.lon_deg)
        b = rhumb_bearing_deg(w1.lat_deg, w1.lon_deg, w2.lat_deg, w2.lon_deg)
        segments.append(Segment(
            id=i + 1,
            distance=d,
            ship_heading=b,
            # Placeholder weather fields — ignored by the rebuild (HDF5 wins).
            wind_dir=0.0, beaufort=0, wave_height=0.0,
            current_dir=0.0, current_speed=0.0,
        ))
        total_d += d

    if eta_h is None:
        eta_h = total_d / cruise_sog_kn

    window = ForecastWindow(start=0.0, end=float(eta_h), segments=segments)
    return Route(windows=[window]), waypoints


def load_route_auto(
    yaml_path: "Path | str",
    eta_h: Optional[float] = None,
    cruise_sog_kn: float = 12.0,
):
    """Dispatcher: pick the right loader from the YAML schema.

    `forecasts:`  → legacy segments-table (paper Persian Gulf) + hardcoded WAYPOINTS.
    `waypoints:`  → lat/lon list (e.g. Atlantic); distances + headings computed.

    Returns `(route, waypoints)` always — for the legacy path the hardcoded
    paper waypoints are returned so callers can stop depending on a global.
    """
    with open(yaml_path) as f:
        data = yaml.safe_load(f)
    if data.get("forecasts"):
        from route_waypoints import WAYPOINTS
        return load_yaml_route(yaml_path), list(WAYPOINTS)
    if data.get("waypoints"):
        return build_route_from_waypoints_yaml(yaml_path, eta_h=eta_h,
                                                cruise_sog_kn=cruise_sog_kn)
    raise ValueError(
        f"Route YAML {yaml_path} must have either 'forecasts:' or 'waypoints:' "
        "top-level key")


def synthesize_multi_window(
    route: Route,
    window_h: float = 6.0,
    noise_fn: Optional[Callable[[Segment, int], Segment]] = None,
) -> Route:
    """Replicate a single-window route into multiple equal windows of `window_h`.

    Q_yaml_4: exercise time-varying-weather infrastructure even though the YAML
    ships with one long window. Default behavior: copy same segments into each
    window (static weather). Supply `noise_fn(segment, window_idx) -> Segment`
    to inject per-window variation.

    Last window is trimmed so its end equals route.eta_h exactly.
    """
    if not route.windows:
        return route
    base_segments = route.windows[0].segments
    eta = route.eta_h

    new_windows: List[ForecastWindow] = []
    t = 0.0
    idx = 0
    while t < eta - 1e-9:
        t_end = min(t + window_h, eta)
        if noise_fn is None:
            segs = list(base_segments)
        else:
            segs = [noise_fn(s, idx) for s in base_segments]
        new_windows.append(ForecastWindow(start=t, end=t_end, segments=segs))
        t = t_end
        idx += 1
    return Route(windows=new_windows)


def summarize_route(route: Route) -> None:
    print("=" * 60)
    print("Route summary")
    print("=" * 60)
    print(f"Length:        {route.length_nm:.2f} nm")
    print(f"ETA:           {route.eta_h:.1f} h")
    print(f"Windows:       {len(route.windows)}")
    print(f"Segments/window: {len(route.windows[0].segments) if route.windows else 0}")
    if route.windows:
        print("\nSegment boundaries (cumulative, nm):")
        cum = 0.0
        for s in route.windows[0].segments:
            cum += s.distance
            print(f"  id {s.id:2d}: +{s.distance:7.2f} -> {cum:7.2f} nm  "
                  f"heading {s.ship_heading:6.2f}°  BN{s.beaufort}")
    print("=" * 60)


if __name__ == "__main__":
    yaml_path = Path(__file__).resolve().parent.parent / \
        "config" / "routes" / "persian_gulf_malacca_paper.yaml"
    route = load_yaml_route(yaml_path)
    summarize_route(route)

    print()
    multi = synthesize_multi_window(route, window_h=6.0)
    print(f"After synthesize_multi_window(6 h): {len(multi.windows)} windows, "
          f"first = [{multi.windows[0].start}, {multi.windows[0].end}), "
          f"last = [{multi.windows[-1].start}, {multi.windows[-1].end})")

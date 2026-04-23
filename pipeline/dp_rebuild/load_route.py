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
    yaml_path = Path(__file__).resolve().parent.parent.parent / \
        "Dynamic speed optimization" / "weather_forecasts.yaml"
    route = load_yaml_route(yaml_path)
    summarize_route(route)

    print()
    multi = synthesize_multi_window(route, window_h=6.0)
    print(f"After synthesize_multi_window(6 h): {len(multi.windows)} windows, "
          f"first = [{multi.windows[0].start}, {multi.windows[0].end}), "
          f"last = [{multi.windows[-1].start}, {multi.windows[-1].end})")

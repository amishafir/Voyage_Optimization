"""
DP graph rebuild — Stage 1: node construction from a Route.

Spec reference: docs/thesis_brainstorm.md §14.14, §14.15, §14.17.

Geometric convention:
  x = time       (0 .. ETA)      hours
  y = distance   (0 .. L)        nautical miles

Line types:
  V line (constant t):  time-decision boundary, every dt_h hours.
                        Also at every forecast-window boundary.
  H line (constant d):  segment boundaries (heading/weather change)
                        + sub-H-lines every weather_cell_nm inside each segment
                          (Q_yaml_5: more decision points, same segment weather)
                        + terminal sink column at d = L.

Node density on each line:
  V line: nodes every zeta_nm across [0, L].
  H line: nodes every tau_h across [0, ETA].
"""

from dataclasses import dataclass
from typing import List, Literal, Optional

from load_route import Route


LineType = Literal["V", "H"]


@dataclass(frozen=True)
class Node:
    time_h: float
    distance_nm: float
    line_type: LineType
    is_source: bool = False
    is_sink: bool = False


@dataclass
class GraphConfig:
    length_nm: float          # L — total voyage distance
    eta_h: float              # T — ETA in hours
    dt_h: float = 6.0         # spacing between V (constant-time) lines
    zeta_nm: float = 1.0      # node spacing on a V line (across distance)
    tau_h: float = 0.1        # node spacing on an H line (across time)
    weather_cell_nm: float = 30.0  # Q_yaml_5: sub-H-line spacing inside segments
    v_min: float = 9.0        # speed range (knots)
    v_max: float = 13.0

    @classmethod
    def from_route(cls, route: Route, **overrides) -> "GraphConfig":
        return cls(length_nm=route.length_nm, eta_h=route.eta_h, **overrides)


# ---------------------------------------------------------------------------
# V lines (constant time)
# ---------------------------------------------------------------------------

def v_line_times_from_route(cfg: GraphConfig, route: Route) -> List[float]:
    """Union of dt_h-spaced times and forecast-window boundaries.

    V lines come from two sources:
      1. dt_h cadence (default 6 h) — the baseline decision rhythm.
      2. Forecast-window boundaries — every time the forecast refreshes.
    Usually these coincide (both 6 h), but the union is the safe general case.
    The synthetic terminal line at t = ETA is included unconditionally.
    """
    times = set()

    # 1. dt_h cadence, plus terminal
    k = 1
    while k * cfg.dt_h < cfg.eta_h - 1e-9:
        times.add(round(k * cfg.dt_h, 9))
        k += 1
    times.add(round(cfg.eta_h, 9))

    # 2. Forecast-window boundaries (strictly > 0 and <= ETA)
    for w in route.windows:
        if w.end > 1e-9:
            times.add(round(w.end, 9))

    return sorted(times)


def build_v_line_nodes(cfg: GraphConfig, t: float) -> List[Node]:
    """Dense column of nodes at time t across [0, L] every zeta_nm."""
    nodes: List[Node] = []
    d = 0.0
    while d <= cfg.length_nm + 1e-9:
        is_sink = abs(d - cfg.length_nm) < 1e-9
        nodes.append(Node(time_h=t, distance_nm=d, line_type="V", is_sink=is_sink))
        d += cfg.zeta_nm
    if nodes and abs(nodes[-1].distance_nm - cfg.length_nm) > 1e-9:
        nodes.append(Node(time_h=t, distance_nm=cfg.length_nm, line_type="V", is_sink=True))
    return nodes


# ---------------------------------------------------------------------------
# H lines (constant distance)
# ---------------------------------------------------------------------------

def h_line_distances_from_route(cfg: GraphConfig, route: Route) -> List[float]:
    """Union of segment boundaries + weather-cell sub-lines + terminal.

    Per Q3: H lines at segment endpoints (heading + weather change).
    Per Q_yaml_5: additionally, H lines every weather_cell_nm inside each segment
    (using the same segment weather — purely more DP decision points).
    Terminal sink column at d = L is always included.
    """
    distances = set()

    cum = 0.0
    for s in route.windows[0].segments:
        seg_start = cum
        seg_end = cum + s.distance

        # Weather-cell sub-lines strictly inside this segment
        d_sub = seg_start + cfg.weather_cell_nm
        while d_sub < seg_end - 1e-9:
            distances.add(round(d_sub, 9))
            d_sub += cfg.weather_cell_nm

        # Segment boundary (but not the terminal, and not d = 0)
        if 1e-9 < seg_end < cfg.length_nm - 1e-9:
            distances.add(round(seg_end, 9))

        cum = seg_end

    # Terminal sink column
    distances.add(round(cfg.length_nm, 9))

    return sorted(distances)


def h_line_distances_from_h5(cfg: GraphConfig, voyage, grid_deg: float = 0.5) -> List[float]:
    """H-line distances from real HDF5 geometry.

    Takes a `VoyageWeather` (imported from h5_weather). Placement rule:
        segment boundaries  ∪  weather-cell crossings  ∪  {terminal at L}

    `grid_deg` = NWP grid resolution (0.5° for Open-Meteo marine / GFS,
                 0.1° for Open-Meteo atmosphere). Cell crossings are detected
    between consecutive waypoints and placed at their midpoint distance.
    """
    distances = set()
    for d in voyage.segment_boundaries_nm():
        distances.add(round(d, 9))
    for d in voyage.weather_cell_boundaries_nm(grid_deg=grid_deg):
        distances.add(round(d, 9))
    distances.add(round(cfg.length_nm, 9))
    return sorted(distances)


def build_h_line_nodes(cfg: GraphConfig, d: float) -> List[Node]:
    """Dense row of nodes at distance d across [0, ETA] every tau_h."""
    nodes: List[Node] = []
    is_sink_line = abs(d - cfg.length_nm) < 1e-9
    t = 0.0
    while t <= cfg.eta_h + 1e-9:
        nodes.append(Node(time_h=t, distance_nm=d, line_type="H", is_sink=is_sink_line))
        t += cfg.tau_h
    if nodes and abs(nodes[-1].time_h - cfg.eta_h) > 1e-9:
        nodes.append(Node(time_h=cfg.eta_h, distance_nm=d, line_type="H", is_sink=is_sink_line))
    return nodes


# ---------------------------------------------------------------------------
# Assembly
# ---------------------------------------------------------------------------

def build_nodes(
    cfg: GraphConfig,
    route: Route,
    h_line_distances: Optional[List[float]] = None,
) -> List[Node]:
    """Source + V-line nodes + H-line nodes.

    By default H-line distances come from the YAML `route` (segments +
    uniform weather-cell sub-lines). Pass `h_line_distances` explicitly to
    override with a list produced from another source (e.g. HDF5 geometry via
    `h_line_distances_from_h5`).
    """
    nodes: List[Node] = [Node(time_h=0.0, distance_nm=0.0, line_type="V", is_source=True)]

    for t in v_line_times_from_route(cfg, route):
        nodes.extend(build_v_line_nodes(cfg, t))

    if h_line_distances is None:
        h_line_distances = h_line_distances_from_route(cfg, route)
    for d in h_line_distances:
        nodes.extend(build_h_line_nodes(cfg, d))

    return nodes


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

def summarize(nodes: List[Node], cfg: GraphConfig, route: Route) -> None:
    v_times = sorted({n.time_h for n in nodes if n.line_type == "V" and not n.is_source})
    h_distances = sorted({n.distance_nm for n in nodes if n.line_type == "H"})
    seg_endpoints = route.cumulative_segment_endpoints()
    v_sinks = sum(1 for n in nodes if n.is_sink and n.line_type == "V")
    h_sinks = sum(1 for n in nodes if n.is_sink and n.line_type == "H")

    print("=" * 70)
    print("DP rebuild — node summary (from Route)")
    print("=" * 70)
    print(f"Route:           L = {cfg.length_nm:.2f} nm, ETA = {cfg.eta_h:.1f} h")
    print(f"V lines:         dt_h = {cfg.dt_h} h, nodes every zeta = {cfg.zeta_nm} nm")
    print(f"H lines:         nodes every tau = {cfg.tau_h} h")
    print(f"Weather cell:    {cfg.weather_cell_nm} nm (sub-H inside each segment)")
    print(f"Speed range:     [{cfg.v_min}, {cfg.v_max}] kn")
    print(f"Forecast windows: {len(route.windows)}")
    print("-" * 70)
    print(f"V lines (time):     {len(v_times)}")
    print(f"  first = {v_times[0]:.2f} h,  last = {v_times[-1]:.2f} h")
    print(f"H lines (distance): {len(h_distances)}")
    print(f"  segment-boundary H lines: {len(seg_endpoints)}")
    print(f"  weather-cell sub-H lines: {len(h_distances) - len(seg_endpoints) - 1}")
    print(f"  terminal sink line:       1")
    print(f"Total nodes:     {len(nodes):,}")
    print(f"  source:                   1")
    print(f"  on V lines:  {sum(1 for n in nodes if n.line_type == 'V' and not n.is_source):,}")
    print(f"  on H lines:  {sum(1 for n in nodes if n.line_type == 'H'):,}")
    print(f"Sinks @ d=L:     {v_sinks + h_sinks:,} "
          f"({v_sinks} on V lines + {h_sinks} on H lines; "
          f"{v_sinks} duplicates at (t, L) intersections)")
    print("=" * 70)


if __name__ == "__main__":
    from pathlib import Path
    from load_route import load_yaml_route, synthesize_multi_window
    from h5_weather import VoyageWeather

    yaml_path = Path(__file__).resolve().parent.parent.parent / \
        "Dynamic speed optimization" / "weather_forecasts.yaml"
    h5_path = Path(__file__).resolve().parent.parent / "data" / "voyage_weather.h5"

    route = load_yaml_route(yaml_path)
    route = synthesize_multi_window(route, window_h=6.0)  # Q_yaml_4

    cfg = GraphConfig.from_route(
        route,
        dt_h=6.0,
        zeta_nm=1.0,
        tau_h=0.1,
        weather_cell_nm=30.0,
        v_min=9.0,
        v_max=13.0,
    )

    # Path A — H lines from YAML (segment boundaries + uniform 30-nm sub-lines)
    print("\n### Path A: H lines from YAML (12 segments + uniform 30-nm) ###\n")
    nodes_a = build_nodes(cfg, route)
    summarize(nodes_a, cfg, route)

    # Path B — H lines from HDF5 (segment boundaries + real 0.5° marine cell crossings)
    print("\n### Path B: H lines from HDF5 (real weather-cell geometry, 0.5°) ###\n")
    voyage = VoyageWeather(h5_path)
    h_lines_h5 = h_line_distances_from_h5(cfg, voyage, grid_deg=0.5)
    nodes_b = build_nodes(cfg, route, h_line_distances=h_lines_h5)
    summarize(nodes_b, cfg, route)

    print(f"\nSummary: YAML-driven = {len(nodes_a):,} nodes / "
          f"HDF5-driven = {len(nodes_b):,} nodes "
          f"(H lines: {len(h_line_distances_from_route(cfg, route))} vs "
          f"{len(h_lines_h5)})")

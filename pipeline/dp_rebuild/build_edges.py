"""
DP graph rebuild — Stage 2: edge construction with source-node weather.

Spec reference: docs/thesis_brainstorm.md §14.14 Q1, Q6, Q7, Q8.

Geometric convention:
  V line = constant time  (time-decision boundary, every dt_h hours)
  H line = constant distance (course / weather / sink boundary)

For every source node, emit an edge to every destination node on the
**next V line** or the **next H line** such that
    SOG = (d_b - d_a) / (t_b - t_a)  lies in  [v_min, v_max].

Q1 ("first boundary crossed") is enforced by destination clamping:
  - V-line targets: only if d_b <= d_H_next
  - H-line targets: only if t_b <= t_V_next

Each edge carries the **source-node weather** (Q8 — weather constant between
nodes; verified because H lines exist at every weather-cell boundary, so no
edge crosses one). SWS inverse + FCR + fuel are the *next* stage.
"""

from bisect import bisect_right
from dataclasses import dataclass
from math import isnan
from typing import Dict, List, Optional, Tuple

from build_nodes import GraphConfig, Node, build_nodes
from h5_weather import WEATHER_FIELDS, VoyageWeather


@dataclass(frozen=True)
class Weather:
    wind_speed_10m_kmh: float
    wind_direction_10m_deg: float
    beaufort_number: int
    wave_height_m: float
    ocean_current_velocity_kmh: float
    ocean_current_direction_deg: float

    @classmethod
    def from_dict(cls, d: Dict[str, float]) -> "Weather":
        return cls(
            wind_speed_10m_kmh=float(d["wind_speed_10m_kmh"]),
            wind_direction_10m_deg=float(d["wind_direction_10m_deg"]),
            beaufort_number=int(d["beaufort_number"]),
            wave_height_m=float(d["wave_height_m"]),
            ocean_current_velocity_kmh=float(d["ocean_current_velocity_kmh"]),
            ocean_current_direction_deg=float(d["ocean_current_direction_deg"]),
        )

    def has_nan(self) -> bool:
        for f in (
            self.wind_speed_10m_kmh,
            self.wind_direction_10m_deg,
            self.wave_height_m,
            self.ocean_current_velocity_kmh,
            self.ocean_current_direction_deg,
        ):
            if isinstance(f, float) and isnan(f):
                return True
        return False


@dataclass(frozen=True)
class Edge:
    src_t: float
    src_d: float
    dst_t: float
    dst_d: float
    sog: float  # knots — Δd/Δt
    weather: Weather


# ---------------------------------------------------------------------------
# Indexing
# ---------------------------------------------------------------------------

def index_nodes(nodes: List[Node]) -> Tuple[Dict[float, List[Node]], Dict[float, List[Node]]]:
    """Group nodes by line coordinate for fast destination lookup.

    Returns (nodes_by_v_time, nodes_by_h_distance).
      nodes_by_v_time[t]     -> nodes on the V line at time t, sorted by distance
      nodes_by_h_distance[d] -> nodes on the H line at distance d, sorted by time
    """
    by_v: Dict[float, List[Node]] = {}
    by_h: Dict[float, List[Node]] = {}
    for n in nodes:
        if n.line_type == "V":
            by_v.setdefault(n.time_h, []).append(n)
        else:
            by_h.setdefault(n.distance_nm, []).append(n)
    for lst in by_v.values():
        lst.sort(key=lambda n: n.distance_nm)
    for lst in by_h.values():
        lst.sort(key=lambda n: n.time_h)
    return by_v, by_h


def next_coord(sorted_coords: List[float], c: float) -> Optional[float]:
    i = bisect_right(sorted_coords, c)
    if i == len(sorted_coords):
        return None
    return sorted_coords[i]


# ---------------------------------------------------------------------------
# Weather lookup policy
# ---------------------------------------------------------------------------

def lookup_source_weather(
    src: Node,
    voyage: VoyageWeather,
    next_v_time: Optional[float] = None,
    next_h_distance: Optional[float] = None,
    sample_hour: int = 0,
    forecast_hour: Optional[int] = None,
) -> Weather:
    """Weather at the **center of the enter-square** (upper-right of src).

    Probing the source's exact coordinates is unsafe: a source that sits on
    a boundary line can hit a `nearest_waypoint` tie and resolve to the
    waypoint on the *wrong* side of the boundary. Probing the enter-square's
    center ((src.t + next_v)/2, (src.d + next_h)/2) guarantees we read the
    weather of the square every edge from this source actually traverses.

    Caller passes `next_v_time` / `next_h_distance`; if either is None, the
    source coord itself is used along that axis.
    """
    t_probe = src.time_h
    if next_v_time is not None:
        t_probe = (src.time_h + next_v_time) / 2.0
    d_probe = src.distance_nm
    if next_h_distance is not None:
        d_probe = (src.distance_nm + next_h_distance) / 2.0
    wx_dict = voyage.weather_at(
        d_probe,
        sample_hour=sample_hour,
        forecast_hour=forecast_hour,
    )
    return Weather.from_dict(wx_dict)


# ---------------------------------------------------------------------------
# Edge enumeration
# ---------------------------------------------------------------------------

def edges_from_source(
    src: Node,
    cfg: GraphConfig,
    v_line_times: List[float],
    h_line_distances: List[float],
    nodes_by_v: Dict[float, List[Node]],
    nodes_by_h: Dict[float, List[Node]],
    wx: Weather,
) -> List[Edge]:
    """Enumerate all feasible edges out of a single source node.

    `wx` is the already-resolved source weather so we don't re-query the HDF5
    per destination.
    """
    edges: List[Edge] = []
    t_a, d_a = src.time_h, src.distance_nm

    t_v_next = next_coord(v_line_times, t_a)
    d_h_next = next_coord(h_line_distances, d_a)

    # Targets on the next V line (constant time) — vary distance
    if t_v_next is not None:
        dt = t_v_next - t_a
        d_min = d_a + cfg.v_min * dt
        d_max = d_a + cfg.v_max * dt
        if d_h_next is not None:
            d_max = min(d_max, d_h_next)  # Q1: don't overshoot the H corner
        for n in nodes_by_v.get(t_v_next, []):
            if n.distance_nm < d_min - 1e-9:
                continue
            if n.distance_nm > d_max + 1e-9:
                break
            sog = (n.distance_nm - d_a) / dt
            if cfg.v_min - 1e-9 <= sog <= cfg.v_max + 1e-9:
                edges.append(Edge(t_a, d_a, n.time_h, n.distance_nm, sog, wx))

    # Targets on the next H line (constant distance) — vary time
    if d_h_next is not None:
        dd = d_h_next - d_a
        t_min_arr = t_a + dd / cfg.v_max
        t_max_arr = t_a + dd / cfg.v_min
        if t_v_next is not None:
            t_max_arr = min(t_max_arr, t_v_next)  # Q1
        for n in nodes_by_h.get(d_h_next, []):
            if n.time_h < t_min_arr - 1e-9:
                continue
            if n.time_h > t_max_arr + 1e-9:
                break
            dt = n.time_h - t_a
            if dt <= 0:
                continue
            sog = dd / dt
            if cfg.v_min - 1e-9 <= sog <= cfg.v_max + 1e-9:
                edges.append(Edge(t_a, d_a, n.time_h, n.distance_nm, sog, wx))

    return edges


def build_edges(
    cfg: GraphConfig,
    nodes: List[Node],
    voyage: VoyageWeather,
    sample_hour: int = 0,
    forecast_hour: Optional[int] = None,
) -> List[Edge]:
    by_v, by_h = index_nodes(nodes)
    v_times = sorted(by_v.keys())
    h_distances = sorted(by_h.keys())

    edges: List[Edge] = []
    for n in nodes:
        if n.is_sink:
            continue
        next_v = next_coord(v_times, n.time_h)
        next_h = next_coord(h_distances, n.distance_nm)
        wx = lookup_source_weather(
            n, voyage,
            next_v_time=next_v,
            next_h_distance=next_h,
            sample_hour=sample_hour,
            forecast_hour=forecast_hour,
        )
        edges.extend(edges_from_source(n, cfg, v_times, h_distances, by_v, by_h, wx))
    return edges


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

def summarize_edges(edges: List[Edge], nodes: List[Node], cfg: GraphConfig) -> None:
    if not edges:
        print("No edges built.")
        return

    v_times = {n.time_h for n in nodes if n.line_type == "V"}
    h_distances = {n.distance_nm for n in nodes if n.line_type == "H"}
    to_v = sum(1 for e in edges if e.dst_t in v_times)
    to_h = sum(1 for e in edges if e.dst_d in h_distances)

    sogs = [e.sog for e in edges]
    wind_speeds = [e.weather.wind_speed_10m_kmh for e in edges]
    wave_heights = [e.weather.wave_height_m for e in edges]
    nan_edges = sum(1 for e in edges if e.weather.has_nan())

    print("=" * 70)
    print("DP rebuild — edge summary (with source-node weather)")
    print("=" * 70)
    print(f"Total edges:     {len(edges):,}")
    print(f"  to V line:     {to_v:,}   (constant-time targets)")
    print(f"  to H line:     {to_h:,}   (constant-distance targets)")
    print(f"SOG range:       [{min(sogs):.4f}, {max(sogs):.4f}] kn  "
          f"(mean {sum(sogs) / len(sogs):.3f})")
    print(f"Avg fan-out:     {len(edges) / max(1, sum(1 for n in nodes if not n.is_sink)):.2f}")
    print("-" * 70)
    print("Weather on edges (source-node, actual_weather sample_hour=0):")
    valid_wind = [w for w in wind_speeds if not isnan(w)]
    valid_wave = [w for w in wave_heights if not isnan(w)]
    print(f"  wind speed (kmh):  min {min(valid_wind):.2f}, "
          f"max {max(valid_wind):.2f}, "
          f"mean {sum(valid_wind) / len(valid_wind):.2f}")
    print(f"  wave height  (m):  min {min(valid_wave):.2f}, "
          f"max {max(valid_wave):.2f}, "
          f"mean {sum(valid_wave) / len(valid_wave):.2f}")
    beauforts = [e.weather.beaufort_number for e in edges]
    print(f"  Beaufort number:   {min(beauforts)}..{max(beauforts)}")
    print(f"  NaN-weather edges: {nan_edges:,}  "
          f"({100 * nan_edges / len(edges):.2f}% — expected near Port B)")
    print("-" * 70)
    print("First 3 edges:")
    for e in edges[:3]:
        print(f"  ({e.src_t:6.2f}, {e.src_d:7.2f}) -> "
              f"({e.dst_t:6.2f}, {e.dst_d:7.2f})  SOG {e.sog:.3f} kn  "
              f"| wind {e.weather.wind_speed_10m_kmh:5.1f} kmh BN{e.weather.beaufort_number} "
              f"wave {e.weather.wave_height_m:.2f} m")
    print("=" * 70)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    from pathlib import Path
    from load_route import load_yaml_route, synthesize_multi_window
    from build_nodes import h_line_distances_from_h5

    yaml_path = Path(__file__).resolve().parent.parent.parent / \
        "Dynamic speed optimization" / "weather_forecasts.yaml"
    h5_path = Path(__file__).resolve().parent.parent / "data" / "voyage_weather.h5"

    route = load_yaml_route(yaml_path)
    route = synthesize_multi_window(route, window_h=6.0)
    voyage = VoyageWeather(h5_path)

    cfg = GraphConfig.from_route(
        route,
        dt_h=6.0,
        zeta_nm=1.0,
        tau_h=0.1,
        weather_cell_nm=30.0,
        v_min=9.0,
        v_max=13.0,
    )

    # H lines from HDF5 real geometry (segment boundaries + 0.5° marine cells + terminal)
    h_lines = h_line_distances_from_h5(cfg, voyage, grid_deg=0.5)
    nodes = build_nodes(cfg, route, h_line_distances=h_lines)
    print(f"Nodes: {len(nodes):,}   H lines: {len(h_lines)}")

    edges = build_edges(cfg, nodes, voyage, sample_hour=0)
    summarize_edges(edges, nodes, cfg)

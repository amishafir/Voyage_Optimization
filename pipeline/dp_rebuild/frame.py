"""
DP graph rebuild — frame primitives.

Encapsulates the (t, d) frame geometry used by the atomic-edge builder:
  - V-line times (every dt_h + forecast boundaries + ETA)
  - H-line distances (cell crossings + segment boundaries + terminal at L)
  - SOG decision grid (41 speeds in [9, 13] kn at 0.1 kn step)
  - 1 nm V-line dst snap, 0.1 h H-line dst snap
  - Cell-canonical weather + paper heading lookups
  - Block-start sample_hour (Luo 2024 compatible — one weather row per block)

Pure geometry + lookups, no node materialization. Nodes are interned
lazily by the atomic-edge builder as edges land on (t, d) coordinates.

Spec reference: docs/meeting_prep_2026_05_11.md §2.1.1 – §2.1.4.
"""

from __future__ import annotations

import sys
from bisect import bisect_right
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

_PIPELINE_ROOT = Path(__file__).resolve().parent.parent
if str(_PIPELINE_ROOT) not in sys.path:
    sys.path.insert(0, str(_PIPELINE_ROOT))

from build_edges import Weather  # noqa: E402
from build_nodes import (  # noqa: E402
    GraphConfig,
    h_line_distances_from_geo,
    v_line_times_from_route,
)
from geo_grid import position_at_d  # noqa: E402
from h5_weather import VoyageWeather  # noqa: E402
from load_route import Route  # noqa: E402


SOG_STEP_DEFAULT = 0.1  # kn — discrete SOG grid step (41 SOGs in [9, 13])


@dataclass
class Frame:
    """The (t, d) line frame + lookups, no nodes materialized."""

    cfg: GraphConfig
    route: Route
    voyage: VoyageWeather
    waypoints: list
    v_line_times: List[float]
    h_line_distances: List[float]
    grid_deg: float = 0.5
    sog_step: float = SOG_STEP_DEFAULT
    _sog_grid_cache: List[float] = field(default_factory=list, repr=False)

    # ---------------------------------------------------------------- SOG grid

    def sog_grid(self) -> List[float]:
        """Discrete target-SOG grid: [v_min, v_max] at sog_step (default 41 values)."""
        if not self._sog_grid_cache:
            n = int(round((self.cfg.v_max - self.cfg.v_min) / self.sog_step)) + 1
            self._sog_grid_cache = [
                round(self.cfg.v_min + i * self.sog_step, 6) for i in range(n)
            ]
        return self._sog_grid_cache

    # ---------------------------------------------------------------- next-line lookup

    def next_v_time(self, t: float, eps: float = 1e-9) -> Optional[float]:
        i = bisect_right(self.v_line_times, t + eps)
        if i == len(self.v_line_times):
            return None
        return self.v_line_times[i]

    def next_h_distance(self, d: float, eps: float = 1e-9) -> Optional[float]:
        i = bisect_right(self.h_line_distances, d + eps)
        if i == len(self.h_line_distances):
            return None
        return self.h_line_distances[i]

    # ---------------------------------------------------------------- block math

    def block_index(self, t: float) -> int:
        """Which 6 h block does t belong to? block 0 = [0, 6), block 1 = [6, 12), …"""
        return int(t // self.cfg.dt_h)

    def block_start_time(self, t: float) -> float:
        return self.cfg.dt_h * self.block_index(t)

    def sample_hour_for_block(self, t: float) -> int:
        """Block-start sample_hour — same row for the whole 6 h block (Luo 2024)."""
        return int(round(self.block_start_time(t)))

    # ---------------------------------------------------------------- snap helpers

    def snap_v_dst_d(self, d: float) -> float:
        """Snap distance to the 1 nm V-line dst grid."""
        return round(d / self.cfg.zeta_nm) * self.cfg.zeta_nm

    def snap_h_dst_t(self, t: float) -> float:
        """Snap time to the 0.1 h H-line dst grid."""
        return round(t / self.cfg.tau_h) * self.cfg.tau_h

    # ---------------------------------------------------------------- physics inputs

    def cell_weather_at(
        self,
        d: float,
        sample_hour: int,
        forecast_hour: Optional[int] = None,
    ) -> Weather:
        """Cell-canonical weather row for the 0.5° cell containing position d."""
        return Weather.from_dict(
            self.voyage.cell_weather_at_d(
                d,
                waypoints=self.waypoints,
                sample_hour=sample_hour,
                forecast_hour=forecast_hour,
                grid_deg=self.grid_deg,
            )
        )

    def paper_heading_at(self, d: float) -> float:
        """Paper-segment β (deg) at distance d (rhumb-line polyline lookup)."""
        _lat, _lon, seg_idx = position_at_d(d, self.waypoints)
        segs = self.route.windows[0].segments
        seg = segs[max(0, min(seg_idx, len(segs) - 1))]
        return seg.ship_heading


# ----------------------------------------------------------------------
# Construction
# ----------------------------------------------------------------------

def from_route(
    route: Route,
    voyage: VoyageWeather,
    waypoints,
    cfg: Optional[GraphConfig] = None,
    grid_deg: float = 0.5,
    sog_step: float = SOG_STEP_DEFAULT,
) -> Frame:
    """Construct a Frame from a route + waypoints + HDF5 weather.

    Default cfg: [9, 13] kn × 0.1 kn step, dt_h=6 h, zeta_nm=1 nm, tau_h=0.1 h.
    """
    if cfg is None:
        cfg = GraphConfig.from_route(
            route,
            dt_h=6.0,
            zeta_nm=1.0,
            tau_h=0.1,
            weather_cell_nm=30.0,  # legacy; ignored by from-geo H-line generator
            v_min=9.0,
            v_max=13.0,
        )
    v_times = v_line_times_from_route(cfg, route)
    h_dists = h_line_distances_from_geo(cfg, waypoints, grid_deg=grid_deg)
    return Frame(
        cfg=cfg,
        route=route,
        voyage=voyage,
        waypoints=waypoints,
        v_line_times=v_times,
        h_line_distances=h_dists,
        grid_deg=grid_deg,
        sog_step=sog_step,
    )


# ----------------------------------------------------------------------
# Summary (for __main__)
# ----------------------------------------------------------------------

def summarize(frame: Frame) -> None:
    print("=" * 72)
    print("DP rebuild — Frame summary")
    print("=" * 72)
    print(f"Route:         L = {frame.cfg.length_nm:.3f} nm, ETA = {frame.cfg.eta_h:.1f} h")
    print(f"V-lines:       {len(frame.v_line_times)} times, "
          f"first = {frame.v_line_times[0]:.2f} h, last = {frame.v_line_times[-1]:.2f} h")
    print(f"               dt_h = {frame.cfg.dt_h} h, zeta_nm = {frame.cfg.zeta_nm} nm "
          f"(V-line dst snap)")
    print(f"H-lines:       {len(frame.h_line_distances)} distances "
          f"(cell crossings + segment boundaries + terminal)")
    print(f"               tau_h = {frame.cfg.tau_h} h (H-line dst snap)")
    sog_grid = frame.sog_grid()
    print(f"SOG grid:      {len(sog_grid)} target SOGs in "
          f"[{sog_grid[0]:.1f}, {sog_grid[-1]:.1f}] kn at {frame.sog_step} kn step")
    n_blocks = int(frame.cfg.eta_h / frame.cfg.dt_h)
    print(f"Blocks:        {n_blocks} blocks of {frame.cfg.dt_h} h "
          f"(sample_hour @ block-start: 0, {frame.cfg.dt_h:.0f}, "
          f"{2*frame.cfg.dt_h:.0f}, …, {(n_blocks-1)*frame.cfg.dt_h:.0f})")
    print("=" * 72)


# ----------------------------------------------------------------------
# Smoke test
# ----------------------------------------------------------------------

if __name__ == "__main__":
    from load_route import load_yaml_route, synthesize_multi_window
    from route_waypoints import WAYPOINTS

    yaml_path = Path(__file__).resolve().parent.parent.parent / \
        "Dynamic speed optimization" / "weather_forecasts.yaml"
    h5_path = Path(__file__).resolve().parent.parent / "data" / "voyage_weather.h5"

    route = load_yaml_route(yaml_path)
    route = synthesize_multi_window(route, window_h=6.0)
    voyage = VoyageWeather(h5_path)

    frame = from_route(route, voyage, WAYPOINTS)
    summarize(frame)

    # Spot-check a few lookups.
    print("\nSpot checks:")
    print(f"  next_v_time(5.5)         = {frame.next_v_time(5.5)}")
    print(f"  next_v_time(6.0)         = {frame.next_v_time(6.0)}")
    print(f"  next_h_distance(0.0)     = {frame.next_h_distance(0.0)}")
    print(f"  next_h_distance(100.0)   = {frame.next_h_distance(100.0)}")
    print(f"  block_index(5.9)         = {frame.block_index(5.9)}")
    print(f"  block_index(6.0)         = {frame.block_index(6.0)}")
    print(f"  sample_hour_for_block(5.9) = {frame.sample_hour_for_block(5.9)}")
    print(f"  sample_hour_for_block(6.0) = {frame.sample_hour_for_block(6.0)}")
    print(f"  snap_v_dst_d(75.4)       = {frame.snap_v_dst_d(75.4)}")
    print(f"  snap_h_dst_t(2.673)      = {frame.snap_h_dst_t(2.673)}")
    print(f"  paper_heading_at(0.0)    = {frame.paper_heading_at(0.0):.2f}°")
    print(f"  paper_heading_at(100.0)  = {frame.paper_heading_at(100.0):.2f}°")

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
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import List, Optional

_PIPELINE_ROOT = Path(__file__).resolve().parent.parent
if str(_PIPELINE_ROOT) not in sys.path:
    sys.path.insert(0, str(_PIPELINE_ROOT))

from weather import Weather  # noqa: E402
from nodes import (  # noqa: E402
    GraphConfig,
    assert_tau_feasible,
    cumulative_rhumb_nm,
    h_line_distances_from_geo,
    v_line_times_from_route,
)
from geo_grid import position_at_d, rhumb_bearing_deg  # noqa: E402
from weather import VoyageWeather  # noqa: E402
from route import Route  # noqa: E402


SOG_STEP_DEFAULT = 0.1  # kn — discrete SOG grid step (41 SOGs in [9, 13])

# Recognised H-line placements. "geo" is the published path.
PARTITIONS = ("geo", "waypoint")


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
    base_sample_hour: int = 0
    # "geo"      — H-lines at 0.5 deg crossings, weather from the cell mean (legacy)
    # "waypoint" — H-lines at the sample points, weather from the source waypoint
    partition: str = "geo"
    # One rhumb bearing per segment; populated only for partition="waypoint".
    segment_heading: List[float] = field(default_factory=list, repr=False)
    # node_id sourcing each segment's reading; partition="waypoint" only.
    segment_src_node: List[int] = field(default_factory=list, repr=False)
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
        """Block-start sample_hour (with base offset) — same row for the whole 6 h block.

        Mode C support: voyage starting at base_sample_hour=B uses
        actual_weather[sample_hour = B + 6·block_index(t)] for each block.
        Mode A callers pass override_sample_hour and ignore this method.
        """
        return self.base_sample_hour + int(round(self.block_start_time(t)))

    # ---------------------------------------------------------------- snap helpers

    def snap_v_dst_d(self, d: float) -> float:
        """Snap distance to the 1 nm V-line dst grid."""
        return round(d / self.cfg.zeta_nm) * self.cfg.zeta_nm

    def snap_h_dst_t(self, t: float) -> float:
        """Snap time to the 0.1 h H-line dst grid."""
        return round(t / self.cfg.tau_h) * self.cfg.tau_h

    # ---------------------------------------------------------------- physics inputs

    def segment_index(self, d: float) -> int:
        """Index of the segment a source at distance d departs into.

        Exact by construction: `h_line_distances` holds the very numbers that
        define the segment boundaries, so a source sitting on a line resolves
        to the segment it is about to traverse. There is no derived coordinate
        to round and hence none of the `floor(lat/0.5)` boundary ambiguity that
        the cell path has. `h_line_distances` excludes d_0 = 0, so no -1.
        """
        k = bisect_right(self.h_line_distances, d)
        return min(max(k, 0), len(self.h_line_distances) - 1)

    def weather_unusable(self, w: Weather) -> bool:
        """Whether a reading is too incomplete to price an arc.

        Under the waypoint partition only the fields the cost function actually
        consumes can invalidate an arc; wind speed and wave height are not
        consumed. The legacy geo path keeps the original all-fields test so it
        stays bit-identical.
        """
        return w.has_nan_consumed() if self.partition == "waypoint" else w.has_nan()

    def cell_weather_at(
        self,
        d: float,
        sample_hour: int,
        forecast_hour: Optional[int] = None,
    ) -> Weather:
        """Weather governing the segment departing position d.

        partition="waypoint": the source waypoint's stored reading.
        partition="geo":      the 0.5 deg cell mean (legacy).
        """
        if self.partition == "waypoint":
            k = self.segment_index(d)
            return Weather.from_dict(
                self.voyage.weather_at_waypoint(
                    self.segment_src_node[k],
                    sample_hour=sample_hour,
                    forecast_hour=forecast_hour,
                )
            )
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
        """Ship heading (deg) governing the segment departing position d.

        partition="waypoint": the segment's own rhumb bearing. This also fixes
        the boundary case — `position_at_d` resolves a distance lying exactly
        on a segment boundary to the segment that *ends* there, so the legacy
        path prices the outgoing leg with the incoming heading.
        """
        if self.partition == "waypoint":
            return self.segment_heading[self.segment_index(d)]
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
    base_sample_hour: int = 0,
    partition: str = "geo",
) -> Frame:
    """Construct a Frame from a route + waypoints + HDF5 weather.

    Default cfg: [9, 13] kn × 0.1 kn step, dt_h=6 h, zeta_nm=1 nm, tau_h=0.1 h.

    `base_sample_hour`: offset for Mode C (per-block actual_weather lookup).
    Block k will read actual_weather[sample_hour = base_sample_hour + 6k].
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
    seg_headings: List[float] = []
    seg_src_node: List[int] = []
    if partition not in PARTITIONS:
        # Previously an unrecognised string fell through to the geo branch and
        # ran silently, so a typo produced a plausible-looking published-path
        # result. Fail instead.
        raise ValueError(
            f"unknown partition {partition!r}; expected one of {PARTITIONS}")

    if partition == "waypoint":
        # The sample points become the graph's polyline. This is what makes the
        # distance axis identical to the path the weather was sampled along,
        # collapsing the paper-table / rhumb / haversine axes into one.
        # The sample points define the partition. `waypoints` stays the paper
        # polyline so the output/plotting path (position_at_d) is untouched and
        # both engines agree; the partition needs only the three arrays below.
        samples = list(voyage.waypoints)
        cum = [0.0] + cumulative_rhumb_nm(samples)   # cum[i] = distance of sample i
        L = cum[-1]
        cfg = replace(cfg, length_nm=L)

        # Only waypoints that actually carry a reading may place an H-line.
        usable = voyage.usable_node_ids()
        idx = [i for i, w in enumerate(samples) if w.node_id in usable]
        if not idx or idx[0] != 0:
            raise ValueError(
                "partition='waypoint' needs a usable reading at the first "
                f"waypoint; usable indices start at {idx[0] if idx else None}")
        dropped = len(samples) - len(idx)
        if dropped:
            print(f"[frame] partition=waypoint: {dropped} of {len(samples)} "
                  f"sample points carry no valid reading and place no H-line "
                  f"(node_ids {[samples[i].node_id for i in range(len(samples)) if i not in set(idx)]})")

        # Segment k spans [cum[idx[k]], cum[idx[k+1]]), sourced at idx[k].
        # A trailing run of unusable waypoints extends the final segment to L.
        bounds = [cum[i] for i in idx[1:]]
        if not bounds or bounds[-1] < L - 1e-9:
            bounds.append(round(L, 9))
        h_dists = [round(b, 9) for b in bounds]

        ends = idx[1:] + ([len(samples) - 1] if idx[-1] != len(samples) - 1 else [])
        for k, i0 in enumerate(idx[:len(h_dists)]):
            i1 = ends[k]
            seg_src_node.append(samples[i0].node_id)
            seg_headings.append(rhumb_bearing_deg(
                samples[i0].lat_deg, samples[i0].lon_deg,
                samples[i1].lat_deg, samples[i1].lon_deg))

        assert_tau_feasible(cfg, h_dists)
    else:
        h_dists = h_line_distances_from_geo(cfg, waypoints, grid_deg=grid_deg)

    v_times = v_line_times_from_route(cfg, route)
    return Frame(
        cfg=cfg,
        route=route,
        voyage=voyage,
        waypoints=waypoints,
        v_line_times=v_times,
        h_line_distances=h_dists,
        grid_deg=grid_deg,
        sog_step=sog_step,
        base_sample_hour=base_sample_hour,
        partition=partition,
        segment_heading=seg_headings,
        segment_src_node=seg_src_node,
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
    from route import load_yaml_route, synthesize_multi_window
    from route_waypoints import WAYPOINTS

    yaml_path = Path(__file__).resolve().parent.parent / \
        "config" / "routes" / "persian_gulf_malacca_paper.yaml"
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

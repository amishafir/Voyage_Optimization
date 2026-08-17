"""Generate the matched two-panel state-neighbours figure.

The panels use one real interior block from the Indian Ocean route (Persian Gulf
to the Strait of Malacca), voyage 0.  Geometry is reconstructed from the canonical
route waypoints; candidates are generated from Eq. (5), not hand-authored.

Outputs (in this directory by default):
  state_neighbours.pdf / .png
  state_neighbours_hline.pdf / .png
  state_neighbours_pair.pdf / .png

Run:
  python plot_state_neighbours_pair.py
  python plot_state_neighbours_pair.py --vmax 15.118714
"""

from __future__ import annotations

import argparse
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon, Rectangle


# ---------------------------------------------------------------------------
# Real route/block data
# ---------------------------------------------------------------------------

ROUTE_WAYPOINTS = (
    (24.75, 52.83),
    (26.55, 56.45),
    (24.08, 60.88),
    (21.73, 65.73),
    (17.96, 69.19),
    (14.18, 72.07),
    (10.45, 75.16),
    (7.00, 78.46),
    (5.64, 82.12),
    (4.54, 87.04),
    (5.20, 92.27),
    (5.64, 97.16),
    (1.81, 100.10),
)

# Segment lengths are the production Indian-Ocean-route values from
# pipeline/config/routes/persian_gulf_malacca_paper.yaml.
ROUTE_SEGMENT_LENGTHS_NM = (
    223.86,
    282.54,
    303.18,
    298.44,
    280.51,
    287.34,
    284.40,
    233.25,
    301.80,
    315.70,
    293.80,
    288.42,
)

ROUTE_LENGTH_NM = sum(ROUTE_SEGMENT_LENGTHS_NM)
ETA_H = 280.0
PROVISIONAL_VMAX_KN = ROUTE_LENGTH_NM / ETA_H + 3.0
# V_min of the paper's band L/T +- 3 kn.  The block drawn here is interior, so
# Eq. (2) forbids the zero-speed wait leg in it.
PROVISIONAL_VMIN_KN = ROUTE_LENGTH_NM / ETA_H - 3.0

# Illustrative settings for the figure.  The experiments use delta = 1 NM,
# tau = 0.1 h and the band of Section 5.2; at those values this 31.8 NM x 6 h
# block yields 13 and 7 candidates, too dense to label.  Coarsening the grid to
# delta = 5 / tau = 1 alone empties the panels (2 and 0 candidates), because the
# admissible windows are then narrower than one grid step, so the band is
# widened to [3, 16] kn purely for the drawing.  Both families stay populated
# and V_min > 0 still makes the cone's lower edge a ray rather than a vertical.
FIGURE_DELTA_NM = 5.0
FIGURE_TAU_H = 1.0
FIGURE_VMIN_KN = 3.0
FIGURE_VMAX_KN = 16.0

FROZEN_D_LEFT_NM = 1963.886308
FROZEN_D_RIGHT_NM = 1995.718977


@dataclass(frozen=True)
class BlockSpec:
    route: str = "Indian Ocean route: Persian Gulf--Strait of Malacca"
    voyage: str = "voyage 0 (sh_base=6)"
    d_left: float = FROZEN_D_LEFT_NM
    d_right: float = FROZEN_D_RIGHT_NM
    t_top: float = 120.0
    t_bottom: float = 126.0
    tau_h: float = FIGURE_TAU_H
    delta_nm: float = FIGURE_DELTA_NM
    vmax_kn: float = FIGURE_VMAX_KN
    vmin_kn: float = FIGURE_VMIN_KN
    xlim: tuple[float, float] = (1958.0, 2002.0)
    ylim: tuple[float, float] = (119.2, 126.8)


@dataclass(frozen=True)
class PanelSpec:
    key: str
    source_t: float
    source_d: float
    source_line: str
    subtitle: str
    # True only at d = 0 or d = D, where Eq. (2) admits the zero-speed wait leg.
    boundary_layer: bool = False


@dataclass(frozen=True)
class CandidateFamilies:
    distance_wall: tuple[tuple[float, float], ...]
    time_wall: tuple[tuple[float, float], ...]
    unique: frozenset[tuple[float, float]]


BLOCK_DEFAULT = BlockSpec()
PANELS = {
    "a": PanelSpec(
        key="a",
        # On the absolute tau-grid of Eq. (5).
        source_t=121.0,
        source_d=FROZEN_D_LEFT_NM,
        source_line="distance",
        subtitle=r"(a) an initial state on a $\mathit{distance}$ line",
    ),
    "b": PanelSpec(
        key="b",
        source_t=120.0,
        # Must sit on the absolute delta-grid of Eq. (5); the old value
        # (d_right - 16) was anchored to the wall and is no longer a state.
        source_d=1970.0,
        source_line="time",
        subtitle=r"(b) an initial state on a $\mathit{time}$ line",
    ),
}


# ---------------------------------------------------------------------------
# Shared style and exact export geometry
# ---------------------------------------------------------------------------

FIGSIZE = (6.0, 4.6)
PAIR_FIGSIZE = (12.0, 4.6)
PLOT_BOX = (0.17, 0.15, 0.67, 0.66)
COMPASS_BOX = (0.06, 0.87, 0.34, 0.11)
SUBTITLE_Y = 0.035
PNG_DPI = 300

COLORS = {
    "block": "#F4F7FA",
    "distance": "#0D3B66",
    "time": "#6B7C8F",
    "cone": "#FFF3E0",
    "speed": "#E64A19",
    "source": "#C62828",
    "family1": "#1565C0",
    "family2": "#2E7D32",
    "fan1": "#8EA8C3",
    "fan2": "#9DBF9E",
    "inactive": "#CFD8DC",
    "compass": "#33475B",
    "white": "#FFFFFF",
    "text": "#263746",
}

FONT = {
    "boundary": 8.5,
    "source": 8.2,
    "candidate": 7.1,
    "speed": 9.0,
    "compass": 9.0,
    "subtitle": 10.0,
}

SOURCE_SIZE = 92
CANDIDATE_SIZE = 31
MARKER_EDGE_WIDTH = 0.65
# One style per line family, applied identically in both panels.
DISTANCE_LINE_WIDTH = 1.9
TIME_LINE_WIDTH = 1.9
SPEED_EDGE_WIDTH = 1.8
FAN_WIDTH = 0.72


def _num(value: float, decimals: int = 1) -> str:
    """Format a label number, dropping an all-zero fraction (120.0 -> '120').

    The decimal point survives the strip only when a non-zero digit precedes it,
    so 1963.9 keeps its tenth while 1990.0 and 16.000 come out whole.
    """
    text = f"{value:.{decimals}f}"
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text


def _subrect(canvas: tuple[float, float, float, float],
             local: tuple[float, float, float, float]) -> list[float]:
    """Map a panel-local rectangle into a figure canvas rectangle."""
    cx, cy, cw, ch = canvas
    lx, ly, lw, lh = local
    return [cx + lx * cw, cy + ly * ch, lw * cw, lh * ch]


# ---------------------------------------------------------------------------
# Provenance verification: analytic rhumb-line crossing positions
# ---------------------------------------------------------------------------

R_EARTH_NM = 60.0 * 180.0 / math.pi


def _mercator_y(lat_deg: float) -> float:
    lat_rad = math.radians(max(-89.5, min(89.5, lat_deg)))
    return math.log(math.tan(math.pi / 4.0 + lat_rad / 2.0))


def _normalise_dlon(dlon_deg: float) -> float:
    dlon = (dlon_deg + 180.0) % 360.0 - 180.0
    return 180.0 if dlon == -180.0 else dlon


def _rhumb_distance_nm(p1: tuple[float, float],
                       p2: tuple[float, float]) -> float:
    lat1, lon1 = p1
    lat2, lon2 = p2
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = phi2 - phi1
    dlam = math.radians(_normalise_dlon(lon2 - lon1))
    dpsi = _mercator_y(lat2) - _mercator_y(lat1)
    q = dphi / dpsi if abs(dpsi) > 1e-12 else math.cos(phi1)
    return math.hypot(dphi, q * dlam) * R_EARTH_NM


def _longitude_crossing_distance_nm(target_lon: float) -> tuple[float, int]:
    cumulative = 0.0
    for index, (p1, p2) in enumerate(zip(ROUTE_WAYPOINTS, ROUTE_WAYPOINTS[1:]), start=1):
        lat1, lon1 = p1
        _lat2, lon2 = p2
        dlon = _normalise_dlon(lon2 - lon1)
        lon2_effective = lon1 + dlon
        segment_distance = _rhumb_distance_nm(p1, p2)
        lo, hi = sorted((lon1, lon2_effective))
        if lo < target_lon < hi:
            fraction = (target_lon - lon1) / dlon
            return cumulative + fraction * segment_distance, index
        cumulative += segment_distance
    raise ValueError(f"Route does not cross longitude {target_lon}")


def verify_provenance(block: BlockSpec) -> None:
    left, left_segment = _longitude_crossing_distance_nm(78.5)
    right, right_segment = _longitude_crossing_distance_nm(79.0)
    assert left_segment == right_segment == 8
    assert abs(left - block.d_left) <= 1e-6, (left, block.d_left)
    assert abs(right - block.d_right) <= 1e-6, (right, block.d_right)
    assert block.t_top > 0.0 and block.d_left > 0.0
    assert block.t_bottom - block.t_top == 6.0
    assert block.d_left < block.d_right < ROUTE_LENGTH_NM


# ---------------------------------------------------------------------------
# Eq. (5) candidate generation
# ---------------------------------------------------------------------------

def _node(t: float, d: float) -> tuple[float, float]:
    return round(t, 9), round(d, 9)


def grid_times(block: BlockSpec) -> list[float]:
    """tau-grid of Eq. (5), anchored at the voyage start, clipped to the block."""
    lo = math.ceil(block.t_top / block.tau_h - 1e-9)
    hi = math.floor(block.t_bottom / block.tau_h + 1e-9)
    return [round(n * block.tau_h, 9) for n in range(lo, hi + 1)]


def grid_distances(block: BlockSpec) -> list[float]:
    """delta-grid of Eq. (5), anchored at the voyage start, clipped to the block."""
    lo = math.ceil(block.d_left / block.delta_nm - 1e-9)
    hi = math.floor(block.d_right / block.delta_nm + 1e-9)
    return [round(n * block.delta_nm, 9) for n in range(lo, hi + 1)]


def candidate_families(block: BlockSpec, panel: PanelSpec) -> CandidateFamilies:
    """Successors under Eq. (6).

    Both grids are anchored at the voyage start, not stepped backward from the
    block walls, so a candidate is admissible only where the absolute grid falls.
    Family 1 lands on the next distance line at a tau-grid time; family 2 lands
    on the next time line at a delta-grid distance.  The zero-speed wait leg is
    admissible only where Eq. (2) allows it, i.e. at d = 0 and d = D.
    """
    eps = 1e-9
    f1: list[tuple[float, float]] = []
    f2: list[tuple[float, float]] = []
    wait_ok = block.vmin_kn <= eps or panel.boundary_layer

    # Family 1: the next distance wall, at tau-grid times up to the next time line.
    for dst_t in grid_times(block):
        if dst_t <= panel.source_t + eps:
            continue
        speed = (block.d_right - panel.source_d) / (dst_t - panel.source_t)
        if block.vmin_kn - eps <= speed <= block.vmax_kn + eps:
            f1.append(_node(dst_t, block.d_right))

    # The block corner is a state via the distance-line term of Eq. (5): the next
    # distance line carries the whole tau-grid, so t_bottom sits on it too.
    # grid_times already includes t_bottom whenever tau divides it.

    # Family 2: the next time wall, at delta-grid distances up to the next distance line.
    for dst_d in grid_distances(block):
        if dst_d < panel.source_d - eps:
            continue
        speed = (dst_d - panel.source_d) / (block.t_bottom - panel.source_t)
        if speed <= eps:
            if wait_ok:
                f2.append(_node(block.t_bottom, dst_d))
        elif block.vmin_kn - eps <= speed <= block.vmax_kn + eps:
            f2.append(_node(block.t_bottom, dst_d))

    f1_unique = tuple(sorted(set(f1)))
    f2_unique = tuple(sorted(set(f2), key=lambda p: (p[1], p[0])))
    unique = frozenset(f1_unique).union(f2_unique)
    return CandidateFamilies(f1_unique, f2_unique, frozenset(unique))


def verify_candidates(block: BlockSpec, panel: PanelSpec,
                      families: CandidateFamilies) -> None:
    eps = 1e-7
    assert block.t_top - eps <= panel.source_t < block.t_bottom - eps
    assert block.d_left - eps <= panel.source_d < block.d_right - eps
    # The source must itself be a state of Eq. (5): a distance-line source sits
    # on a tau-grid time, a time-line source on a delta-grid distance.
    if panel.source_line == "distance":
        assert abs(panel.source_d - block.d_left) <= eps
        ratio = panel.source_t / block.tau_h
    else:
        assert abs(panel.source_t - block.t_top) <= eps
        ratio = panel.source_d / block.delta_nm
    assert abs(ratio - round(ratio)) <= 1e-6, (panel.key, ratio)

    for dst_t, dst_d in families.unique:
        assert dst_t > panel.source_t + eps
        assert dst_d >= panel.source_d - eps
        assert abs(dst_d - block.d_right) <= eps or abs(dst_t - block.t_bottom) <= eps
        speed = (dst_d - panel.source_d) / (dst_t - panel.source_t)
        if speed > eps:
            assert block.vmin_kn - eps <= speed <= block.vmax_kn + eps
        else:
            assert block.vmin_kn <= eps or panel.boundary_layer


# ---------------------------------------------------------------------------
# Drawing helpers
# ---------------------------------------------------------------------------

def _sample_indices(size: int, maximum: int) -> list[int]:
    if size <= maximum:
        return list(range(size))
    indexes = {0, size - 1}
    for i in range(1, maximum - 1):
        indexes.add(round(i * (size - 1) / (maximum - 1)))
    return sorted(indexes)


def _time_label_indices(points: Sequence[tuple[float, float]]) -> list[int]:
    if not points:
        return []
    indexes = {0, len(points) - 1}
    for i, (t, _d) in enumerate(points):
        if abs(t - round(t)) <= 1e-8:
            indexes.add(i)
    if len(indexes) < 3 and len(points) > 2:
        indexes.add(len(points) // 2)
    return sorted(indexes)


def _draw_compass(fig, canvas: tuple[float, float, float, float]) -> None:
    ax_c = fig.add_axes(_subrect(canvas, COMPASS_BOX))
    ax_c.set_xlim(0, 1)
    ax_c.set_ylim(0, 1)
    ax_c.axis("off")
    ax_c.annotate(
        "", xy=(0.30, 0.80), xytext=(0.02, 0.80),
        arrowprops=dict(arrowstyle="-|>", color=COLORS["compass"], lw=1.25,
                        mutation_scale=12),
    )
    ax_c.annotate(
        "", xy=(0.02, 0.10), xytext=(0.02, 0.80),
        arrowprops=dict(arrowstyle="-|>", color=COLORS["compass"], lw=1.25,
                        mutation_scale=12),
    )
    ax_c.text(0.35, 0.80, "distance $d$ [NM]", fontsize=FONT["compass"],
              color=COLORS["compass"], va="center", ha="left")
    ax_c.text(0.07, 0.10, "time $t$ [h]", fontsize=FONT["compass"],
              color=COLORS["compass"], va="center", ha="left")


def _draw_panel(fig, canvas: tuple[float, float, float, float],
                block: BlockSpec, panel: PanelSpec) -> dict:
    families = candidate_families(block, panel)
    verify_candidates(block, panel, families)

    ax = fig.add_axes(_subrect(canvas, PLOT_BOX))
    ax.set_xlim(*block.xlim)
    ax.set_ylim(block.ylim[1], block.ylim[0])  # elapsed time increases downward
    ax.set_xticks([])
    ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_visible(False)

    # Real selected block.
    ax.add_patch(Rectangle(
        (block.d_left, block.t_top),
        block.d_right - block.d_left,
        block.t_bottom - block.t_top,
        facecolor=COLORS["block"], edgecolor="none", zorder=0,
    ))

    # The four block boundaries are drawn identically in both panels: every
    # distance line in one style, every time line in another.  The source is
    # identified by its marker and label, not by emphasising the line it sits on.
    for d_line in (block.d_left, block.d_right):
        ax.plot([d_line, d_line], [block.t_top, block.t_bottom],
                color=COLORS["distance"], lw=DISTANCE_LINE_WIDTH, zorder=1.4)
    for t_line in (block.t_top, block.t_bottom):
        ax.plot([block.d_left, block.d_right], [t_line, t_line],
                color=COLORS["time"], lw=TIME_LINE_WIDTH, zorder=1.4)

    # Every state of Eq. (5) on all four boundaries of the block, at full marker
    # size in grey: circles on the two distance lines, which carry the tau-grid,
    # and squares on the two time lines, which carry the delta-grid.  Candidate
    # markers are overplotted below, so what stays grey is what is unreachable
    # from this source.
    all_times = grid_times(block)
    all_distances = grid_distances(block)
    for d_line in (block.d_left, block.d_right):
        ax.scatter([d_line] * len(all_times), all_times, s=CANDIDATE_SIZE,
                   color=COLORS["inactive"], marker="o",
                   edgecolor=COLORS["white"], linewidth=MARKER_EDGE_WIDTH, zorder=2)
    for t_line in (block.t_top, block.t_bottom):
        ax.scatter(all_distances, [t_line] * len(all_distances), s=CANDIDATE_SIZE,
                   color=COLORS["inactive"], marker="s",
                   edgecolor=COLORS["white"], linewidth=MARKER_EDGE_WIDTH, zorder=2)

    # Speed cone: upper edge is the v_max ray, lower edge is the v_min ray
    # (vertical when vmin = 0), both clipped at the block's two far walls.
    t_fast = panel.source_t + (block.d_right - panel.source_d) / block.vmax_kn
    if block.vmin_kn > 1e-9:
        # Slow edge either reaches the distance wall or is cut by the time wall.
        t_slow = panel.source_t + (block.d_right - panel.source_d) / block.vmin_kn
        if t_slow <= block.t_bottom:
            slow_end = (block.d_right, t_slow)
            cone_tail = [(block.d_right, t_slow)]
        else:
            d_slow = panel.source_d + block.vmin_kn * (block.t_bottom - panel.source_t)
            slow_end = (d_slow, block.t_bottom)
            cone_tail = [(block.d_right, block.t_bottom), (d_slow, block.t_bottom)]
    else:
        slow_end = (panel.source_d, block.t_bottom)
        cone_tail = [(block.d_right, block.t_bottom), (panel.source_d, block.t_bottom)]

    cone = [(panel.source_d, panel.source_t), (block.d_right, t_fast)] + cone_tail
    ax.add_patch(Polygon(cone, closed=True, facecolor=COLORS["cone"],
                         edgecolor="none", alpha=0.85, zorder=1.1))
    ax.plot([panel.source_d, block.d_right], [panel.source_t, t_fast],
            color=COLORS["speed"], lw=SPEED_EDGE_WIDTH, zorder=3.2)
    ax.plot([panel.source_d, slow_end[0]], [panel.source_t, slow_end[1]],
            color=COLORS["speed"], lw=SPEED_EDGE_WIDTH, zorder=3.2)

    # Candidate fan lines are thinned, while every candidate marker remains.
    f1 = list(families.distance_wall)
    f2 = list(families.time_wall)
    for i in _sample_indices(len(f1), 8):
        dst_t, dst_d = f1[i]
        ax.plot([panel.source_d, dst_d], [panel.source_t, dst_t],
                color=COLORS["fan1"], lw=FAN_WIDTH, alpha=0.82, zorder=2.7)
    # The shared corner is rendered as family 1 only.
    f2_render = [p for p in f2 if p not in set(f1)]
    for i in _sample_indices(len(f2_render), 8):
        dst_t, dst_d = f2_render[i]
        ax.plot([panel.source_d, dst_d], [panel.source_t, dst_t],
                color=COLORS["fan2"], lw=FAN_WIDTH, alpha=0.86, zorder=2.7)

    if f1:
        ax.scatter([d for _t, d in f1], [t for t, _d in f1],
                   s=CANDIDATE_SIZE, color=COLORS["family1"], marker="o",
                   edgecolor=COLORS["white"], linewidth=MARKER_EDGE_WIDTH, zorder=4)
    if f2_render:
        ax.scatter([d for _t, d in f2_render], [t for t, _d in f2_render],
                   s=CANDIDATE_SIZE, color=COLORS["family2"], marker="s",
                   edgecolor=COLORS["white"], linewidth=MARKER_EDGE_WIDTH, zorder=4)

    # Source state and exact numeric label, tuple order matching the paper.
    ax.scatter([panel.source_d], [panel.source_t], s=SOURCE_SIZE,
               color=COLORS["source"], edgecolor=COLORS["white"],
               linewidth=0.9, zorder=5)
    source_label = (rf"$s_{panel.key}=(t,d)$" + "\n" +
                    rf"$=({_num(panel.source_t)}\,\mathrm{{h}},\ {_num(panel.source_d)}\,\mathrm{{NM}})$")
    source_offset = (-10, -10) if panel.key == "a" else (-9, -12)
    source_va = "top"
    ax.annotate(source_label, (panel.source_d, panel.source_t), xytext=source_offset,
                textcoords="offset points", fontsize=FONT["source"],
                color=COLORS["source"], ha="right", va=source_va, zorder=6,
                bbox=dict(boxstyle="round,pad=0.18", facecolor=COLORS["white"],
                          edgecolor="none", alpha=0.85))

    # Four real block boundary labels.
    ax.annotate(rf"$d_i={_num(block.d_left)}\,\mathrm{{NM}}$",
                (block.d_left, block.t_top), xytext=(0, 9), textcoords="offset points",
                fontsize=FONT["boundary"], color=COLORS["distance"],
                ha="left", va="bottom")
    ax.annotate(rf"$d_{{i+1}}={_num(block.d_right)}\,\mathrm{{NM}}$",
                (block.d_right, block.t_top), xytext=(0, 9), textcoords="offset points",
                fontsize=FONT["boundary"], color=COLORS["distance"],
                ha="right", va="bottom")
    ax.annotate(rf"$t_j={_num(block.t_top)}\,\mathrm{{h}}$",
                (block.d_left, block.t_top), xytext=(-7, 0), textcoords="offset points",
                fontsize=FONT["boundary"], color=COLORS["time"],
                ha="right", va="center")
    ax.annotate(rf"$t_{{j+1}}={_num(block.t_bottom)}\,\mathrm{{h}}$",
                (block.d_left, block.t_bottom), xytext=(-7, 0), textcoords="offset points",
                fontsize=FONT["boundary"], color=COLORS["time"],
                ha="right", va="center")

    # Candidate labels: actual absolute values, deterministically thinned.
    for i in _time_label_indices(f1):
        dst_t, dst_d = f1[i]
        ax.annotate(_num(dst_t), (dst_d, dst_t), xytext=(6, 0),
                    textcoords="offset points", fontsize=FONT["candidate"],
                    color=COLORS["family1"], ha="left", va="center")
    for i in _sample_indices(len(f2_render), 5):
        dst_t, dst_d = f2_render[i]
        ax.annotate(_num(dst_d), (dst_d, dst_t), xytext=(0, -6),
                    textcoords="offset points", fontsize=FONT["candidate"],
                    color=COLORS["family2"], ha="right", va="top", rotation=35)

    # Cone labels and candidate count.
    fraction = 0.70
    fast_x = panel.source_d + fraction * (block.d_right - panel.source_d)
    fast_y = panel.source_t + fraction * (t_fast - panel.source_t)
    ax.annotate(rf"$V_{{\max}}={_num(block.vmax_kn, 3)}\,\mathrm{{kn}}$",
                (fast_x, fast_y), xytext=(0, 8), textcoords="offset points",
                fontsize=FONT["speed"], color=COLORS["speed"],
                ha="center", va="bottom")
    if block.vmin_kn > 1e-9:
        # Slow edge is the V_min ray: label it along the ray, not vertically.
        slow_x = panel.source_d + fraction * (slow_end[0] - panel.source_d)
        slow_y = panel.source_t + fraction * (slow_end[1] - panel.source_t)
        ax.annotate(rf"$V_{{\min}}={_num(block.vmin_kn, 3)}\,\mathrm{{kn}}$",
                    (slow_x, slow_y), xytext=(-8, -7), textcoords="offset points",
                    fontsize=FONT["speed"], color=COLORS["speed"],
                    ha="right", va="top")
    else:
        ax.annotate(r"$\bar v=0$", (panel.source_d, (panel.source_t + block.t_bottom) / 2),
                    xytext=(-6, 0), textcoords="offset points", fontsize=FONT["speed"],
                    color=COLORS["speed"], rotation=90, ha="right", va="center")
    _draw_compass(fig, canvas)
    cx, cy, cw, _ch = canvas
    fig.text(cx + cw / 2.0, cy + SUBTITLE_Y, panel.subtitle,
             ha="center", va="bottom", fontsize=FONT["subtitle"],
             color=COLORS["text"])

    return {
        "panel": panel.key,
        "source": [panel.source_t, panel.source_d],
        "distance_wall_candidates": len(families.distance_wall),
        "time_wall_candidates": len(families.time_wall),
        "unique_candidates": len(families.unique),
        "earliest_distance_wall_time": (min(t for t, _d in families.distance_wall)
                                        if families.distance_wall else None),
    }


def _save(fig, stem: Path) -> None:
    fig.savefig(stem.with_suffix(".pdf"), facecolor="white", bbox_inches=None,
                pad_inches=0)
    fig.savefig(stem.with_suffix(".png"), dpi=PNG_DPI, facecolor="white",
                bbox_inches=None, pad_inches=0)
    plt.close(fig)


def generate_assets(output_dir: Path | str | None = None,
                    vmax_kn: float = PROVISIONAL_VMAX_KN,
                    panels: Iterable[str] = ("a", "b"),
                    combined: bool = True,
                    vmin_kn: float = 0.0,
                    delta_nm: float = BLOCK_DEFAULT.delta_nm,
                    tau_h: float = BLOCK_DEFAULT.tau_h) -> dict:
    output = Path(output_dir) if output_dir else Path(__file__).resolve().parent
    output.mkdir(parents=True, exist_ok=True)
    block = BlockSpec(vmax_kn=float(vmax_kn), vmin_kn=float(vmin_kn),
                      delta_nm=float(delta_nm), tau_h=float(tau_h))
    verify_provenance(block)

    chosen = tuple(panels)
    summary: dict[str, object] = {
        "route": block.route,
        "voyage": block.voyage,
        "block": {
            "distance_nm": [block.d_left, block.d_right],
            "time_h": [block.t_top, block.t_bottom],
            "tau_h": block.tau_h,
            "delta_nm": block.delta_nm,
            "vmax_kn": block.vmax_kn,
            "vmin_kn": block.vmin_kn,
        },
        "panels": [],
    }

    filenames = {"a": "state_neighbours", "b": "state_neighbours_hline"}
    for key in chosen:
        fig = plt.figure(figsize=FIGSIZE, facecolor="white")
        panel_summary = _draw_panel(fig, (0.0, 0.0, 1.0, 1.0), block, PANELS[key])
        summary["panels"].append(panel_summary)
        _save(fig, output / filenames[key])

    if combined and set(chosen) == {"a", "b"}:
        fig = plt.figure(figsize=PAIR_FIGSIZE, facecolor="white")
        _draw_panel(fig, (0.0, 0.0, 0.5, 1.0), block, PANELS["a"])
        _draw_panel(fig, (0.5, 0.0, 0.5, 1.0), block, PANELS["b"])
        _save(fig, output / "state_neighbours_pair")

    print(json.dumps(summary, indent=2))
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument("--vmax", type=float, default=FIGURE_VMAX_KN,
                        help="v_max in knots; default is current Indian-Ocean-route L/T+3 convention")
    parser.add_argument("--vmin", type=float, default=FIGURE_VMIN_KN,
                        help="V_min in knots; 0 (default) keeps the illustrative wait leg, "
                             f"{PROVISIONAL_VMIN_KN:.4f} is the paper's L/T-3 floor")
    parser.add_argument("--delta", type=float, default=BLOCK_DEFAULT.delta_nm,
                        help="delta in NM (state spacing on the time lines)")
    parser.add_argument("--tau", type=float, default=BLOCK_DEFAULT.tau_h,
                        help="tau in hours (state spacing on the distance lines)")
    parser.add_argument("--panel", choices=("a", "b", "both"), default="both")
    args = parser.parse_args()
    selected = ("a", "b") if args.panel == "both" else (args.panel,)
    generate_assets(args.output_dir, args.vmax, selected,
                    combined=args.panel == "both", vmin_kn=args.vmin,
                    delta_nm=args.delta, tau_h=args.tau)


if __name__ == "__main__":
    main()

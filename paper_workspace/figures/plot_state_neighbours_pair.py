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
    tau_h: float = 0.1
    delta_nm: float = 1.0
    vmax_kn: float = PROVISIONAL_VMAX_KN
    xlim: tuple[float, float] = (1958.0, 2002.0)
    ylim: tuple[float, float] = (119.2, 126.8)


@dataclass(frozen=True)
class PanelSpec:
    key: str
    source_t: float
    source_d: float
    source_line: str
    subtitle: str


@dataclass(frozen=True)
class CandidateFamilies:
    distance_wall: tuple[tuple[float, float], ...]
    time_wall: tuple[tuple[float, float], ...]
    unique: frozenset[tuple[float, float]]


BLOCK_DEFAULT = BlockSpec()
PANELS = {
    "a": PanelSpec(
        key="a",
        source_t=123.0,
        source_d=FROZEN_D_LEFT_NM,
        source_line="distance",
        subtitle=r"(a) a state on a $\mathit{distance}$ line",
    ),
    "b": PanelSpec(
        key="b",
        source_t=120.0,
        source_d=FROZEN_D_RIGHT_NM - 16.0,
        source_line="time",
        subtitle=r"(b) a state on a $\mathit{time}$ line",
    ),
}


# ---------------------------------------------------------------------------
# Shared style and exact export geometry
# ---------------------------------------------------------------------------

FIGSIZE = (6.0, 4.6)
PAIR_FIGSIZE = (12.0, 4.6)
PLOT_BOX = (0.12, 0.15, 0.72, 0.66)
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
    "count": 8.0,
}

SOURCE_SIZE = 92
CANDIDATE_SIZE = 31
INACTIVE_SIZE = 8
MARKER_EDGE_WIDTH = 0.65
BOUNDARY_WIDTH = 1.35
SOURCE_BOUNDARY_WIDTH = 2.15
NEXT_WALL_WIDTH = 1.9
SPEED_EDGE_WIDTH = 1.8
FAN_WIDTH = 0.72
TIME_DASH = (0, (4, 3))


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


def candidate_families(block: BlockSpec, panel: PanelSpec) -> CandidateFamilies:
    eps = 1e-9
    f1: list[tuple[float, float]] = []
    f2: list[tuple[float, float]] = []

    # Family 1: arrival times anchored backward from the next time line.
    n = 0
    while True:
        dst_t = block.t_bottom - n * block.tau_h
        if dst_t <= panel.source_t + eps:
            break
        speed = (block.d_right - panel.source_d) / (dst_t - panel.source_t)
        if -eps <= speed <= block.vmax_kn + eps:
            f1.append(_node(dst_t, block.d_right))
        n += 1

    # Family 2: arrival distances anchored backward from the next distance line.
    n = 0
    while True:
        dst_d = block.d_right - n * block.delta_nm
        if dst_d < panel.source_d - eps:
            break
        speed = (dst_d - panel.source_d) / (block.t_bottom - panel.source_t)
        if -eps <= speed <= block.vmax_kn + eps:
            f2.append(_node(block.t_bottom, dst_d))
        n += 1

    # The approved geometry includes the wait successor.  It can coincide with
    # the anchored second family (panel b) or be an extra node (panel a).
    wait = _node(block.t_bottom, panel.source_d)
    f2.append(wait)

    f1_unique = tuple(sorted(set(f1)))
    f2_unique = tuple(sorted(set(f2), key=lambda p: (p[1], p[0])))
    unique = frozenset(f1_unique).union(f2_unique)
    return CandidateFamilies(f1_unique, f2_unique, frozenset(unique))


def verify_candidates(block: BlockSpec, panel: PanelSpec,
                      families: CandidateFamilies) -> None:
    eps = 1e-7
    assert block.t_top - eps <= panel.source_t < block.t_bottom - eps
    assert block.d_left - eps <= panel.source_d < block.d_right - eps
    if panel.source_line == "distance":
        assert abs(panel.source_d - block.d_left) <= eps
        assert abs((block.t_bottom - panel.source_t) / block.tau_h
                   - round((block.t_bottom - panel.source_t) / block.tau_h)) <= eps
    else:
        assert abs(panel.source_t - block.t_top) <= eps
        assert abs((block.d_right - panel.source_d) / block.delta_nm
                   - round((block.d_right - panel.source_d) / block.delta_nm)) <= eps

    for dst_t, dst_d in families.unique:
        assert dst_t > panel.source_t + eps
        assert dst_d >= panel.source_d - eps
        assert abs(dst_d - block.d_right) <= eps or abs(dst_t - block.t_bottom) <= eps
        speed = (dst_d - panel.source_d) / (dst_t - panel.source_t)
        assert -eps <= speed <= block.vmax_kn + eps

    if abs(block.vmax_kn - PROVISIONAL_VMAX_KN) <= 1e-9:
        expected = 41 if panel.key == "a" else 66
        assert len(families.unique) == expected, (panel.key, len(families.unique))


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

    # Same four block boundaries in both panels.  Only the line holding the
    # source gets the source-line emphasis.
    left_width = SOURCE_BOUNDARY_WIDTH if panel.source_line == "distance" else BOUNDARY_WIDTH
    top_width = SOURCE_BOUNDARY_WIDTH if panel.source_line == "time" else BOUNDARY_WIDTH
    ax.plot([block.d_left, block.d_left], [block.t_top, block.t_bottom],
            color=COLORS["distance"], lw=left_width, alpha=0.82, zorder=1.3)
    ax.plot([block.d_right, block.d_right], [block.t_top, block.t_bottom],
            color=COLORS["distance"], lw=NEXT_WALL_WIDTH, zorder=1.4)
    ax.plot([block.d_left, block.d_right], [block.t_top, block.t_top],
            color=COLORS["time"], lw=top_width, ls=TIME_DASH, alpha=0.86, zorder=1.3)
    ax.plot([block.d_left, block.d_right], [block.t_bottom, block.t_bottom],
            color=COLORS["time"], lw=NEXT_WALL_WIDTH, ls=TIME_DASH, zorder=1.4)

    # Full anchored grids on the two destination walls; candidate markers are
    # overplotted below, leaving only the inactive points visible in grey.
    all_times: list[float] = []
    n = 0
    while block.t_bottom - n * block.tau_h >= block.t_top - 1e-9:
        all_times.append(round(block.t_bottom - n * block.tau_h, 9))
        n += 1
    all_distances: list[float] = []
    n = 0
    while block.d_right - n * block.delta_nm >= block.d_left - 1e-9:
        all_distances.append(round(block.d_right - n * block.delta_nm, 9))
        n += 1
    ax.scatter([block.d_right] * len(all_times), all_times, s=INACTIVE_SIZE,
               color=COLORS["inactive"], edgecolor="none", zorder=2)
    ax.scatter(all_distances, [block.t_bottom] * len(all_distances),
               s=INACTIVE_SIZE, color=COLORS["inactive"], edgecolor="none", zorder=2)

    # Speed cone under the provisional/final v_max parameter.
    t_fast = panel.source_t + (block.d_right - panel.source_d) / block.vmax_kn
    cone = (
        (panel.source_d, panel.source_t),
        (block.d_right, t_fast),
        (block.d_right, block.t_bottom),
        (panel.source_d, block.t_bottom),
    )
    ax.add_patch(Polygon(cone, closed=True, facecolor=COLORS["cone"],
                         edgecolor="none", alpha=0.85, zorder=1.1))
    ax.plot([panel.source_d, block.d_right], [panel.source_t, t_fast],
            color=COLORS["speed"], lw=SPEED_EDGE_WIDTH, zorder=3.2)
    ax.plot([panel.source_d, panel.source_d], [panel.source_t, block.t_bottom],
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
                    rf"$=({panel.source_t:.1f}\,\mathrm{{h}},\ {panel.source_d:.1f}\,\mathrm{{NM}})$")
    source_offset = (-10, -10) if panel.key == "a" else (-9, -12)
    source_va = "top"
    ax.annotate(source_label, (panel.source_d, panel.source_t), xytext=source_offset,
                textcoords="offset points", fontsize=FONT["source"],
                color=COLORS["source"], ha="right", va=source_va, zorder=6)

    # Four real block boundary labels.
    ax.annotate(rf"$d_i={block.d_left:.1f}\,\mathrm{{NM}}$",
                (block.d_left, block.t_top), xytext=(0, 9), textcoords="offset points",
                fontsize=FONT["boundary"], color=COLORS["distance"],
                ha="left", va="bottom")
    ax.annotate(rf"$d_{{i+1}}={block.d_right:.1f}\,\mathrm{{NM}}$",
                (block.d_right, block.t_top), xytext=(0, 9), textcoords="offset points",
                fontsize=FONT["boundary"], color=COLORS["distance"],
                ha="right", va="bottom")
    ax.annotate(rf"$t_j={block.t_top:.1f}\,\mathrm{{h}}$",
                (block.d_left, block.t_top), xytext=(-7, 0), textcoords="offset points",
                fontsize=FONT["boundary"], color=COLORS["time"],
                ha="right", va="center")
    ax.annotate(rf"$t_{{j+1}}={block.t_bottom:.1f}\,\mathrm{{h}}$",
                (block.d_left, block.t_bottom), xytext=(-7, 0), textcoords="offset points",
                fontsize=FONT["boundary"], color=COLORS["time"],
                ha="right", va="center")

    # Candidate labels: actual absolute values, deterministically thinned.
    for i in _time_label_indices(f1):
        dst_t, dst_d = f1[i]
        ax.annotate(f"{dst_t:.1f}", (dst_d, dst_t), xytext=(6, 0),
                    textcoords="offset points", fontsize=FONT["candidate"],
                    color=COLORS["family1"], ha="left", va="center")
    for i in _sample_indices(len(f2_render), 5):
        dst_t, dst_d = f2_render[i]
        ax.annotate(f"{dst_d:.1f}", (dst_d, dst_t), xytext=(0, -6),
                    textcoords="offset points", fontsize=FONT["candidate"],
                    color=COLORS["family2"], ha="right", va="top", rotation=35)

    # Cone labels and candidate count.
    fraction = 0.70
    fast_x = panel.source_d + fraction * (block.d_right - panel.source_d)
    fast_y = panel.source_t + fraction * (t_fast - panel.source_t)
    ax.annotate(rf"$v_{{\max}}={block.vmax_kn:.3f}\,\mathrm{{kn}}$",
                (fast_x, fast_y), xytext=(0, 8), textcoords="offset points",
                fontsize=FONT["speed"], color=COLORS["speed"],
                ha="center", va="bottom")
    ax.annotate(r"$\bar v=0$", (panel.source_d, (panel.source_t + block.t_bottom) / 2),
                xytext=(-6, 0), textcoords="offset points", fontsize=FONT["speed"],
                color=COLORS["speed"], rotation=90, ha="right", va="center")
    ax.text(0.985, 0.025, rf"$\kappa={len(families.unique)}$",
            transform=ax.transAxes, fontsize=FONT["count"], color=COLORS["text"],
            ha="right", va="bottom")

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
        "earliest_distance_wall_time": min(t for t, _d in families.distance_wall),
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
                    combined: bool = True) -> dict:
    output = Path(output_dir) if output_dir else Path(__file__).resolve().parent
    output.mkdir(parents=True, exist_ok=True)
    block = BlockSpec(vmax_kn=float(vmax_kn))
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
    parser.add_argument("--vmax", type=float, default=PROVISIONAL_VMAX_KN,
                        help="v_max in knots; default is current Indian-Ocean-route L/T+3 convention")
    parser.add_argument("--panel", choices=("a", "b", "both"), default="both")
    args = parser.parse_args()
    selected = ("a", "b") if args.panel == "both" else (args.panel,)
    generate_assets(args.output_dir, args.vmax, selected, combined=args.panel == "both")


if __name__ == "__main__":
    main()

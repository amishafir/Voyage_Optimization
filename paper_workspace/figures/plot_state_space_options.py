"""
Three candidate figures for §4.1 ("ADD A FIGURE"), to compare.

Shared conventions (from the legacy hand sketches: graph.jpeg, sample_voyage.jpeg,
supervisor_board.jpeg):
  - ORIGIN top-left; x = distance d (rightward), y = time t (DOWNWARD).
  - VERTICAL distance lines at subsegment breakpoints d_0..d_M=L
    (heading-change/segment = solid dark; cell crossing = dashed light).
  - HORIZONTAL time lines at {6i : 6i < T} U {T}.

Options:
  A  DP graph        -- fans of speed edges from every node -> reachable states.
  B  candidate paths -- three labelled voyages a,b,c to the same (L,T).
  C  minimal hybrid  -- grid + one origin fan + one optimal path + one shaded cell.

Run:  python3 plot_state_space_options.py
Outputs: state_space_optA/B/C .pdf and .png
"""

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

# --- Illustrative grid ------------------------------------------------------
T = 28.0
L = 300.0
time_lines = [t for t in range(0, int(T) + 1, 6) if t < T] + [T]
dist_lines = [
    (0.0, "segment"), (55.0, "cell"), (110.0, "cell"), (150.0, "segment"),
    (205.0, "cell"), (260.0, "cell"), (300.0, "segment"),
]
d_vals = [d for d, _ in dist_lines]
d_labels = [r"$d_0$", r"$d_1$", r"$d_2$", r"$d_3$", r"$d_4$", r"$d_5$", r"$d_M\!=\!L$"]


def next_dist_line(d):
    return next((dl for dl in d_vals if dl > d + 1e-9), None)


def next_time_line(t):
    return next((tl for tl in time_lines if tl > t + 1e-9), None)


def edge_endpoint(d0, t0, v):
    dl, tl = next_dist_line(d0), next_time_line(t0)
    if dl is None or tl is None:
        return None
    dt_d = (dl - d0) / v
    dt_t = tl - t0
    return (dl, t0 + dt_d) if dt_d <= dt_t else (d0 + v * dt_t, tl)


def setup(ax, title, bands=True):
    # Convention (locked): VERTICAL distance lines (x = distance),
    # HORIZONTAL time lines (y = time, increasing downward).

    # Alternating background bands -- one per MAJOR segment (between heading changes)
    seg_breaks = [d for d, k in dist_lines if k == "segment"]
    band_tints = ["#eef3f9", "#e1ebf3"]
    if bands:
        for i in range(len(seg_breaks) - 1):
            ax.add_patch(plt.Rectangle((seg_breaks[i], 0), seg_breaks[i + 1] - seg_breaks[i], T,
                                       facecolor=band_tints[i % 2], edgecolor="none", zorder=0))
    # Horizontal time lines
    for t in time_lines:
        ax.axhline(t, color="#9aa7b4", lw=0.9, ls=(0, (4, 3)), zorder=1)
    # Vertical distance lines: heading change = bold navy solid + down-triangle;
    #                          cell crossing = faint light dotted
    for d, kind in dist_lines:
        if kind == "segment":
            ax.axvline(d, color="#0d3b66", lw=2.4, ls="-", zorder=1.6)
            ax.scatter([d], [0], marker="v", s=46, color="#0d3b66", zorder=8, clip_on=False)
        else:
            ax.axvline(d, color="#aab7c2", lw=1.0, ls=(0, (1, 3)), zorder=1)
    # Major-segment labels along the bottom
    for i in range(len(seg_breaks) - 1):
        xc = 0.5 * (seg_breaks[i] + seg_breaks[i + 1])
        ax.annotate(f"segment {i + 1}", (xc, T + 1.3), ha="center", va="center",
                    fontsize=8.5, color="#0d3b66", style="italic")
    ax.set_xlim(-6, L + 8)
    ax.set_ylim(T + 2, -2)
    ax.xaxis.set_label_position("top")
    ax.xaxis.tick_top()
    ax.set_xlabel(r"along-track distance $d$  (vertical lines $=$ subsegment breakpoints)", labelpad=8)
    ax.set_ylabel(r"elapsed time $t$  (horizontal lines $=$ 6 h)")
    ax.set_xticks(d_vals)
    ax.set_xticklabels(d_labels)
    ax.set_yticks(time_lines)
    ax.set_yticklabels([("$T$" if abs(t - T) < 1e-9 else f"{int(t)}") for t in time_lines])
    ax.tick_params(length=0)
    for spine in ("bottom", "right"):
        ax.spines[spine].set_visible(False)
    ax.set_title(title, fontsize=10, pad=24, color="#444")


def src_dst(ax):
    ax.scatter([0], [0], s=70, color="#1565c0", zorder=7, edgecolor="white", lw=1.0)
    ax.scatter([L], [T], s=95, marker="*", color="#c62828", zorder=7, edgecolor="white", lw=0.8)
    ax.annotate(r"$(0,0)$", (0, 0), textcoords="offset points", xytext=(8, 10),
                fontsize=9.5, color="#1565c0")
    ax.annotate(r"$(L,T)$", (L, T), textcoords="offset points", xytext=(-44, 12),
                fontsize=9.5, color="#c62828")


def save(fig, name):
    fig.tight_layout()
    fig.savefig(f"{name}.pdf", bbox_inches="tight")
    fig.savefig(f"{name}.png", dpi=200, bbox_inches="tight")
    print(f"wrote {name}.pdf and {name}.png")


# Colours for the four crossing types
_NAVY, _CELL, _TIME, _ARR = "#0d3b66", "#8a6d1a", "#3a6ea5", "#c62828"


def voyage_crossings():
    """The single voyage + a classified, numbered list of its crossings.

    Returns (verts, crossings) where each crossing is
    (number, (d, t), colour, description) and the description names the line
    crossed and the cause. Used by BOTH the figure (badges on points) and the
    key (one row per point) so they never drift.
    """
    verts = [
        (0, 0), (55, 3.67), (71.3, 6), (110, 8.58), (133.9, 12),
        (150, 13.07), (184.5, 18), (205, 19.37), (237.4, 24), (260, 25.51), (300, 28),
    ]
    seg_set = {dd for dd, k in dist_lines if k == "segment"}
    cell_set = {dd for dd, k in dist_lines if k == "cell"}
    dlab = {0.0: "d_0", 55.0: "d_1", 110.0: "d_2", 150.0: "d_3",
            205.0: "d_4", 260.0: "d_5", 300.0: "d_M"}
    cross = []
    for i, (d, t) in enumerate(verts[1:], start=1):
        if abs(d - L) < 1e-6 and abs(t - T) < 1e-6:
            cross.append((i, (d, t), _ARR, "reaches $(L,T)$ — arrival at the ETA"))
        elif any(abs(d - s) < 1e-6 for s in seg_set):
            cross.append((i, (d, t), _NAVY, f"crosses ${dlab[d]}$ — heading change (course $\\psi$)"))
        elif any(abs(d - c) < 1e-6 for c in cell_set):
            cross.append((i, (d, t), _CELL, f"crosses ${dlab[d]}$ — weather cell (space, 0.5$\\degree$)"))
        else:
            tl = min(time_lines, key=lambda x: abs(x - t))
            cross.append((i, (d, t), _TIME, f"crosses $t={int(tl)}$ — 6 h block (time)"))
    return verts, cross


# ============================================================= OPTION A: graph
def option_a():
    fig, ax = plt.subplots(figsize=(7.0, 4.8))
    setup(ax, "Option A — DP graph: speed edges from every node $\\to$ reachable states")
    V = [7.0, 10.0, 13.0, 16.0]
    for d in d_vals[:-1]:
        for t in time_lines[:-1]:
            for v in V:
                ep = edge_endpoint(d, t, v)
                if ep is None:
                    continue
                ax.plot([d, ep[0]], [t, ep[1]], color="#5b8db8", lw=0.7, alpha=0.55, zorder=3)
                ax.scatter([ep[0]], [ep[1]], s=7, color="#3f6f99", zorder=4)
    # grid-intersection nodes
    for d in d_vals:
        for t in time_lines:
            ax.scatter([d], [t], s=10, color="#90a4ae", zorder=2)
    src_dst(ax)
    save(fig, "state_space_optA")
    plt.close(fig)


# ====================================================== OPTION B: candidate paths
def option_b():
    fig, ax = plt.subplots(figsize=(7.0, 4.8))
    setup(ax, "Option B — candidate voyages: each path is a solution; pick least fuel")
    paths = {
        "a": ([(0, 0), (75, 7), (150, 14), (225, 21), (300, 28)], "#1565c0"),
        "b": ([(0, 0), (150, 8), (225, 17), (300, 28)], "#2e7d32"),
        "c": ([(0, 0), (80, 12), (185, 20), (300, 28)], "#8e24aa"),
    }
    for name, (pts, c) in paths.items():
        xs = [p[0] for p in pts]
        ts = [p[1] for p in pts]
        ax.plot(xs, ts, color=c, lw=2.2, zorder=5, solid_capstyle="round")
        ax.scatter(xs, ts, s=22, color=c, zorder=6, edgecolor="white", lw=0.7)
        # label near the second point
        ax.annotate(name, pts[1], textcoords="offset points", xytext=(6, -10),
                    fontsize=11, color=c, fontweight="bold")
    src_dst(ax)
    ax.legend(handles=[
        Line2D([0], [0], color="#1565c0", lw=2.2, label="voyage a"),
        Line2D([0], [0], color="#2e7d32", lw=2.2, label="voyage b"),
        Line2D([0], [0], color="#8e24aa", lw=2.2, label="voyage c"),
    ], loc="lower left", fontsize=8, frameon=True, framealpha=0.95)
    save(fig, "state_space_optB")
    plt.close(fig)


# ====================================================== OPTION C: minimal hybrid
def option_c():
    fig, ax = plt.subplots(figsize=(7.0, 4.8))
    setup(ax, "Option C — minimal: states on the lines, one speed fan, one optimal path")
    # shaded "conditions constant" cell (between d2,d3 and t=6,12)
    ax.add_patch(plt.Rectangle((110, 6), 150 - 110, 12 - 6,
                               facecolor="#ffe0b2", edgecolor="none", alpha=0.9, zorder=0.5))
    ax.annotate("conditions\nconstant", (130, 9), ha="center", va="center",
                fontsize=8, color="#8d5524")
    # one fan from the source
    for v in [4.5, 6.5, 9.2, 12.0, 16.0]:
        ep = edge_endpoint(0.0, 0.0, v)
        if ep is None:
            continue
        ax.plot([0, ep[0]], [0, ep[1]], color="#1565c0", lw=1.4, alpha=0.9, zorder=3)
        ax.scatter([ep[0]], [ep[1]], s=16, color="#1565c0", zorder=4, edgecolor="white", lw=0.5)
    ax.annotate(r"speeds $v\in V$", (30, 6), textcoords="offset points", xytext=(2, 2),
                fontsize=8.5, color="#1565c0")
    # grid-intersection nodes (faint)
    for d in d_vals:
        for t in time_lines:
            ax.scatter([d], [t], s=8, color="#cfd8dc", zorder=2)
    # one optimal path
    path = [(0, 0), (55, 6), (110, 12), (150, 18), (205, 24), (300, 28)]
    xs = [p[0] for p in path]
    ts = [p[1] for p in path]
    ax.plot(xs, ts, color="#e64a19", lw=2.6, zorder=5, solid_capstyle="round")
    ax.scatter(xs, ts, s=24, color="#e64a19", zorder=6, edgecolor="white", lw=0.8)
    ax.annotate("optimal path", (205, 24), textcoords="offset points", xytext=(8, 6),
                fontsize=8.5, color="#e64a19")
    src_dst(ax)
    save(fig, "state_space_optC")
    plt.close(fig)


# ============================== OPTION D: weather + speed constant per cell
def option_d():
    import numpy as np
    fig, ax = plt.subplots(figsize=(7.4, 5.0))
    setup(ax, "Option D — within each cell, weather and optimal speed are constant", bands=False)

    # Synthetic, piecewise-constant "sea-state severity" per cell (illustrative).
    def severity(dmid, tmid):
        return (2.0 + 1.4 * np.sin(dmid / 70.0 + 0.5) + 0.9 * np.cos(tmid / 7.0)
                + 0.5 * np.sin(dmid / 35.0) * np.cos(tmid / 11.0))

    cells = []
    for i in range(len(d_vals) - 1):
        for k in range(len(time_lines) - 1):
            d0, d1 = d_vals[i], d_vals[i + 1]
            t0, t1 = time_lines[k], time_lines[k + 1]
            cells.append((d0, t0, d1 - d0, t1 - t0, severity((d0 + d1) / 2, (t0 + t1) / 2)))
    vals = [c[4] for c in cells]
    norm = plt.Normalize(min(vals), max(vals))
    cmap = plt.cm.YlOrRd
    for d0, t0, w, h, v in cells:
        ax.add_patch(plt.Rectangle((d0, t0), w, h, facecolor=cmap(norm(v)),
                                   alpha=0.78, edgecolor="none", zorder=0.2))

    # Highlight ONE cell and state the invariant
    hd0, ht0, hw, hh = d_vals[1], time_lines[1], d_vals[2] - d_vals[1], time_lines[2] - time_lines[1]
    ax.add_patch(plt.Rectangle((hd0, ht0), hw, hh, facecolor="none",
                               edgecolor="#1a1a1a", lw=2.0, zorder=5))
    ax.annotate("one cell\nweather const\n$\\Rightarrow$ speed const",
                (hd0 + hw / 2, ht0 + hh / 2), ha="center", va="center",
                fontsize=7.8, color="#1a1a1a", zorder=6)

    # The three reasons a new cell begins ------------------------------------
    arrow = dict(arrowstyle="->", color="#1a1a1a", lw=1.3)
    # (1) course change -> a heading-change (segment) distance line
    ax.annotate("new cell: course change\n(heading-change distance line)",
                xy=(150, 21), xytext=(98, 26.7), fontsize=8, color="#0d3b66",
                ha="left", va="center", arrowprops=dict(arrowstyle="->", color="#0d3b66", lw=1.4))
    # (2) weather changes in space -> a cell-crossing distance line
    ax.annotate("new cell: weather changes in space\n(0.5$\\degree$ cell-crossing distance line)",
                xy=(55, 15), xytext=(70, 19), fontsize=8, color="#5a3d00",
                ha="left", va="center", arrowprops=arrow)
    # (3) weather changes in time -> a 6 h horizontal time line
    ax.annotate("new cell: weather changes in time\n(6 h time line)",
                xy=(235, 12), xytext=(150, 6.0), fontsize=8, color="#5a3d00",
                ha="left", va="center", arrowprops=arrow)

    src_dst(ax)
    sm = plt.cm.ScalarMappable(cmap=cmap, norm=norm)
    sm.set_array([])
    cb = fig.colorbar(sm, ax=ax, shrink=0.7, pad=0.02)
    cb.set_label("sea-state severity (illustrative)", fontsize=8)
    cb.ax.tick_params(labelsize=7)
    save(fig, "state_space_optD")
    plt.close(fig)


# ============= OPTION E: like C, but shade the distinct states the voyage visits
def option_e():
    fig, ax = plt.subplots(figsize=(7.0, 4.8))
    setup(ax, "Option E — each cell the voyage enters is a distinct state (weather and speed const)")

    path = [(0, 0), (55, 6), (110, 12), (150, 18), (205, 24), (300, 28)]

    def cell_of(dm, tm):
        i = max(j for j in range(len(d_vals) - 1) if d_vals[j] <= dm + 1e-9)
        k = max(j for j in range(len(time_lines) - 1) if time_lines[j] <= tm + 1e-9)
        return d_vals[i], time_lines[k], d_vals[i + 1] - d_vals[i], time_lines[k + 1] - time_lines[k]

    # Shade ONLY the cells the path traverses, with a restrained single-hue ramp.
    n = len(path) - 1
    seen = set()
    for k in range(n):
        (d0, t0), (d1, t1) = path[k], path[k + 1]
        rect = cell_of((d0 + d1) / 2, (t0 + t1) / 2)
        if rect in seen:
            continue
        seen.add(rect)
        shade = plt.cm.Blues(0.22 + 0.40 * k / max(1, n - 1))
        ax.add_patch(plt.Rectangle(rect[:2], rect[2], rect[3], facecolor=shade,
                                   alpha=0.85, edgecolor="#5a86b0", lw=1.1, zorder=0.4))
        ax.annotate(str(k + 1), (rect[0] + rect[2] / 2, rect[1] + rect[3] / 2),
                    ha="center", va="center", fontsize=8.5, color="#274472",
                    zorder=6, alpha=0.8)

    # Faint origin fan (the discrete speed decisions v in V)
    for v in [4.5, 6.5, 9.2, 12.0, 16.0]:
        ep = edge_endpoint(0.0, 0.0, v)
        if ep is None:
            continue
        ax.plot([0, ep[0]], [0, ep[1]], color="#1565c0", lw=1.2, alpha=0.8, zorder=3)
        ax.scatter([ep[0]], [ep[1]], s=13, color="#1565c0", zorder=4, edgecolor="white", lw=0.5)
    ax.annotate(r"speeds $v\in V$", (30, 6), textcoords="offset points", xytext=(2, 2),
                fontsize=8.5, color="#1565c0")

    # Optimal path on top
    xs = [p[0] for p in path]
    ts = [p[1] for p in path]
    ax.plot(xs, ts, color="#e64a19", lw=2.6, zorder=5, solid_capstyle="round")
    ax.scatter(xs, ts, s=24, color="#e64a19", zorder=6, edgecolor="white", lw=0.8)

    # One explanatory callout in the empty upper-right region
    ax.annotate("each numbered cell is one state:\nconstant weather $\\Rightarrow$ constant speed;\n"
                "a new state begins at a course or\nweather change (a grid line)",
                (212, 1.5), fontsize=7.8, color="#274472", ha="left", va="top")

    src_dst(ax)
    save(fig, "state_space_optE")
    plt.close(fig)


# ===================== OPTION F: the four ways a leg ends (crossing types)
def option_f():
    fig, ax = plt.subplots(figsize=(7.2, 4.9))
    setup(ax, "Option F — every crossing is a speed change; each point is a state transition")

    verts, cross = voyage_crossings()
    xs = [p[0] for p in verts]
    ts_ = [p[1] for p in verts]
    ax.plot(xs, ts_, color="#e64a19", lw=2.4, zorder=4, solid_capstyle="round")

    # A numbered badge sits ON each crossing point, coloured by type.
    for i, (d, t), c, desc in cross:
        ax.text(d, t, str(i), fontsize=7, fontweight="bold", color="white",
                ha="center", va="center", zorder=7,
                bbox=dict(boxstyle="circle,pad=0.16", fc=c, ec="white", lw=0.8))

    # (key/legend is its own figure: option_legend -> state_space_optF_key)
    src_dst(ax)
    save(fig, "state_space_optF")
    plt.close(fig)


# ===================== Standalone KEY for Option F (explains EVERY point)
def option_legend():
    verts, cross = voyage_crossings()
    fig, ax = plt.subplots(figsize=(6.6, 4.6))
    ax.axis("off")
    tx = ax.transAxes

    ax.text(0.0, 1.0, "What happens at each numbered point on the voyage",
            transform=tx, fontsize=11, fontweight="bold", va="top")
    ax.text(0.0, 0.945, "(every crossing is a state transition where the speed may change)",
            transform=tx, fontsize=8.2, style="italic", color="#555", va="top")

    n = len(cross)
    y0, y1 = 0.86, 0.02
    for k, (i, (d, t), c, desc) in enumerate(cross):
        y = y0 - (y0 - y1) * k / (n - 1)
        ax.text(0.035, y, str(i), transform=tx, fontsize=9, fontweight="bold",
                color="white", ha="center", va="center",
                bbox=dict(boxstyle="circle,pad=0.22", fc=c, ec="white", lw=1.0))
        ax.text(0.09, y, desc, transform=tx, fontsize=9, va="center")

    fig.savefig("state_space_optF_key.pdf", bbox_inches="tight")
    fig.savefig("state_space_optF_key.png", dpi=200, bbox_inches="tight")
    print("wrote state_space_optF_key.pdf and state_space_optF_key.png")
    plt.close(fig)


# ===================== SPATIAL MAP companion (geographic cells + route)
def option_map():
    """Spatial (lon/lat) companion to the time-distance state-space figure.

    Shows the 0.5 deg geographic cells, the route, start/end points, and the
    heading change at the interior waypoint. Each cell-boundary crossing along
    the route becomes a subsegment breakpoint (a distance line) in the
    time-distance figure; the heading-change waypoint is the segment boundary.
    """
    from math import ceil, floor
    import numpy as np

    cell = 0.5
    lon0, lon1, lat0, lat1 = 0.0, 3.5, 0.0, 2.5
    A = (0.20, 0.30)      # Port A — start (d_0)
    W = (1.80, 1.55)      # interior waypoint — heading change
    B = (3.30, 0.70)      # Port B — end (d_M)
    route = [A, W, B]

    fig, ax = plt.subplots(figsize=(7.2, 5.2))

    # Shade the geographic cells the route passes through
    samp = []
    for (x0, y0), (x1, y1) in zip(route[:-1], route[1:]):
        for s in np.linspace(0, 1, 600):
            samp.append((x0 + s * (x1 - x0), y0 + s * (y1 - y0)))
    traversed = {(int(x // cell), int(y // cell)) for x, y in samp}
    for cx, cy in traversed:
        ax.add_patch(plt.Rectangle((cx * cell, cy * cell), cell, cell,
                                   facecolor="#e8f0f8", edgecolor="none", zorder=0.3))

    # 0.5 deg grid lines = geographic cell boundaries
    for x in np.arange(lon0, lon1 + 1e-9, cell):
        ax.axvline(x, color="#cfd8dc", lw=0.8, ls=(0, (1, 3)), zorder=1)
    for y in np.arange(lat0, lat1 + 1e-9, cell):
        ax.axhline(y, color="#cfd8dc", lw=0.8, ls=(0, (1, 3)), zorder=1)

    # Route (orange, matching the voyage line in the state-space figure)
    rx = [p[0] for p in route]
    ry = [p[1] for p in route]
    ax.plot(rx, ry, color="#e64a19", lw=2.6, zorder=4, solid_capstyle="round")

    # Cell-boundary crossings along the route = subsegment breakpoints
    def seg_crossings(p0, p1):
        (x0, y0), (x1, y1) = p0, p1
        ts = []
        if abs(x1 - x0) > 1e-12:
            for k in range(ceil(min(x0, x1) / cell), floor(max(x0, x1) / cell) + 1):
                t = (k * cell - x0) / (x1 - x0)
                if 1e-6 < t < 1 - 1e-6:
                    ts.append(t)
        if abs(y1 - y0) > 1e-12:
            for k in range(ceil(min(y0, y1) / cell), floor(max(y0, y1) / cell) + 1):
                t = (k * cell - y0) / (y1 - y0)
                if 1e-6 < t < 1 - 1e-6:
                    ts.append(t)
        return [(x0 + t * (x1 - x0), y0 + t * (y1 - y0)) for t in sorted(set(round(v, 6) for v in ts))]

    crossings = []
    for p0, p1 in zip(route[:-1], route[1:]):
        crossings += seg_crossings(p0, p1)
    ax.scatter([c[0] for c in crossings], [c[1] for c in crossings], s=24,
               color="#1a1a1a", zorder=6, edgecolor="white", lw=0.7)
    # one callout tying a crossing to the subsegment concept
    if len(crossings) >= 3:
        ax.annotate("cell-boundary crossing\n$\\to$ subsegment breakpoint",
                    crossings[2], textcoords="offset points", xytext=(14, -34),
                    fontsize=8, color="#444",
                    arrowprops=dict(arrowstyle="->", color="#444", lw=1.0))

    # Heading-change waypoint (navy, matching the segment lines)
    ax.scatter([W[0]], [W[1]], s=120, marker="v", color="#0d3b66", zorder=7,
               edgecolor="white", lw=1.0)
    ax.annotate("heading change (course $\\psi$)", W, textcoords="offset points",
                xytext=(10, 16), fontsize=8.5, color="#0d3b66", va="center")

    # Start / end
    ax.scatter([A[0]], [A[1]], s=80, color="#1565c0", zorder=7, edgecolor="white", lw=1.0)
    ax.annotate("Port A — start ($d_0$)", A, textcoords="offset points", xytext=(8, -12),
                fontsize=9, color="#1565c0")
    ax.scatter([B[0]], [B[1]], s=120, marker="*", color="#c62828", zorder=7,
               edgecolor="white", lw=0.8)
    ax.annotate("Port B — end ($d_M$)", B, textcoords="offset points", xytext=(-10, 10),
                fontsize=9, color="#c62828", ha="right")

    ax.set_xlim(lon0, lon1)
    ax.set_ylim(lat0, lat1)
    ax.set_aspect("equal")
    ax.set_xlabel(r"longitude (cells $=0.5\degree$)")
    ax.set_ylabel(r"latitude (cells $=0.5\degree$)")
    ax.set_title("Spatial map — route over the geographic cells "
                 "(companion to the time--distance state space)",
                 fontsize=9.5, color="#444", pad=10)
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)

    save(fig, "state_space_map")
    plt.close(fig)


if __name__ == "__main__":
    option_a()
    option_b()
    option_c()
    option_d()
    option_e()
    option_f()
    option_legend()
    option_map()

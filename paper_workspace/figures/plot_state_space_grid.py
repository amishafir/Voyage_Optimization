"""
State-space / DP-graph figure for §4.1 ("ADD A FIGURE").

In the spirit of the legacy hand sketches (old/Dynamic speed optimization/
graph.jpeg, sample_voyage.jpeg, supervisor_board.jpeg) combined with the §4.1
text. Conventions taken from those sketches:

  - ORIGIN at TOP-LEFT.
  - x-axis = along-track distance d, increasing rightward. VERTICAL distance
    lines at the subsegment breakpoints d_0=0, d_1, ..., d_M = L.
  - y-axis = elapsed time t, increasing DOWNWARD. HORIZONTAL time lines every
    6 h plus a final line at T: {6i : 6i < T} U {T}.
  - From a node, a FAN of edges -- one per discrete speed v in V -- each a
    straight segment (slope set by v) running until it first meets the next
    line; the endpoints are the reachable states (nodes). This is the DP graph.
  - One full path from (0,0) to (L,T) is highlighted as a sample voyage.

Values are illustrative, chosen for legibility, not from a real route.

Run:  python3 plot_state_space_grid.py
Outputs: state_space_grid.pdf, state_space_grid.png
"""

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

# --- Illustrative grid ------------------------------------------------------
T = 28.0          # ETA (h) -- not a multiple of 6, to show the final time line
L = 300.0         # total distance (nm)

time_lines = [t for t in range(0, int(T) + 1, 6) if t < T] + [T]   # {6i}U{T}

# Distance lines = subsegment breakpoints; cell crossing vs heading change.
dist_lines = [
    (0.0,   "segment"),   # d_0 (start waypoint)
    (55.0,  "cell"),
    (110.0, "cell"),
    (150.0, "segment"),   # heading change (waypoint)
    (205.0, "cell"),
    (260.0, "cell"),
    (300.0, "segment"),   # d_M = L (destination waypoint)
]
d_vals = [d for d, _ in dist_lines]


def next_dist_line(d):
    for dl in d_vals:
        if dl > d + 1e-9:
            return dl
    return None


def next_time_line(t):
    for tl in time_lines:
        if tl > t + 1e-9:
            return tl
    return None


def edge_endpoint(d0, t0, v):
    """A constant-speed edge from (d0,t0) stops at the first line it meets."""
    dl, tl = next_dist_line(d0), next_time_line(t0)
    if dl is None or tl is None:
        return None
    dt_to_dline = (dl - d0) / v
    dt_to_tline = tl - t0
    if dt_to_dline <= dt_to_tline:          # hits a distance line first
        return (dl, t0 + dt_to_dline)
    return (d0 + v * dt_to_tline, tl)       # hits a time line first


# --- Figure -----------------------------------------------------------------
fig, ax = plt.subplots(figsize=(7.0, 4.8))

# Alternating background bands -- one per MAJOR segment (between heading changes)
seg_breaks = [d for d, k in dist_lines if k == "segment"]      # e.g. [0, 150, 300]
band_tints = ["#eef3f9", "#e1ebf3"]
for i in range(len(seg_breaks) - 1):
    ax.add_patch(plt.Rectangle((seg_breaks[i], 0), seg_breaks[i + 1] - seg_breaks[i], T,
                               facecolor=band_tints[i % 2], edgecolor="none", zorder=0))

# Time lines (horizontal)
for t in time_lines:
    ax.axhline(t, color="#9aa7b4", lw=0.9, ls=(0, (4, 3)), zorder=1)

# Distance lines (vertical), strongly differentiated:
#   heading change (segment / waypoint) -> bold NAVY solid + down-triangle marker
#   cell crossing (0.5 deg)             -> faint light DOTTED
for d, kind in dist_lines:
    if kind == "segment":
        ax.axvline(d, color="#0d3b66", lw=2.4, ls="-", zorder=1.6)
        ax.scatter([d], [0], marker="v", s=46, color="#0d3b66",
                   zorder=8, clip_on=False)
    else:
        ax.axvline(d, color="#aab7c2", lw=1.0, ls=(0, (1, 3)), zorder=1)

# Label each major segment along the bottom (hierarchy: segments contain cells)
for i in range(len(seg_breaks) - 1):
    xc = 0.5 * (seg_breaks[i] + seg_breaks[i + 1])
    ax.annotate(f"segment {i + 1}", (xc, T + 1.3), ha="center", va="center",
                fontsize=8.5, color="#0d3b66", style="italic")

# Grid-intersection nodes (faint)
for d in d_vals:
    for t in time_lines:
        ax.scatter([d], [t], s=9, color="#cfd8dc", zorder=2)

# --- Fans of edges (the discrete speed choices v in V) ----------------------
V_demo = [4.5, 6.5, 9.2, 12.0, 16.0]       # illustrative speeds (nm/h)

def draw_fan(d0, t0, color, lw, alpha, dot=True):
    for v in V_demo:
        ep = edge_endpoint(d0, t0, v)
        if ep is None:
            continue
        ax.plot([d0, ep[0]], [t0, ep[1]], color=color, lw=lw, alpha=alpha, zorder=3)
        if dot:
            ax.scatter([ep[0]], [ep[1]], s=18, color=color, zorder=4,
                       edgecolor="white", lw=0.5)

# Prominent fan from the source (0,0)
draw_fan(0.0, 0.0, "#1565c0", 1.7, 0.95)
# Secondary fans from two downstream nodes -> conveys the full graph texture
draw_fan(55.0, 5.0, "#90a4ae", 1.0, 0.8, dot=True)
draw_fan(110.0, 6.0, "#90a4ae", 1.0, 0.8, dot=True)

# --- One highlighted sample voyage path -------------------------------------
path = [(0, 0), (55, 6), (110, 12), (150, 18), (205, 24), (300, 28)]
px = [p[0] for p in path]
pt = [p[1] for p in path]
ax.plot(px, pt, color="#e64a19", lw=2.6, zorder=5, solid_capstyle="round")
ax.scatter(px, pt, s=26, color="#e64a19", zorder=6, edgecolor="white", lw=0.8)

# Source and destination
ax.scatter([0], [0], s=70, color="#1565c0", zorder=7, edgecolor="white", lw=1.0)
ax.scatter([L], [T], s=95, marker="*", color="#c62828", zorder=7, edgecolor="white", lw=0.8)
ax.annotate(r"$(0,0)$", (0, 0), textcoords="offset points", xytext=(8, 10),
            fontsize=9.5, color="#1565c0")
ax.annotate(r"$(L,T)$", (L, T), textcoords="offset points", xytext=(-42, 14),
            fontsize=9.5, color="#c62828")
ax.annotate("one voyage\n(a path)", (205, 24), textcoords="offset points",
            xytext=(10, 6), fontsize=8.5, color="#e64a19")
ax.annotate(r"edges $=$ speeds $v\in V$", (28, 6), textcoords="offset points",
            xytext=(2, 2), fontsize=8.5, color="#1565c0")

# --- Axes (origin top-left: distance rightward, time downward) --------------
ax.set_xlim(-6, L + 8)
ax.set_ylim(T + 2, -2)                      # inverted -> time increases downward
ax.xaxis.set_label_position("top")
ax.xaxis.tick_top()
ax.set_xlabel(r"along-track distance $d$  (vertical lines $=$ subsegment breakpoints)", labelpad=8)
ax.set_ylabel(r"elapsed time $t$  (horizontal lines $=$ 6 h)")

ax.set_xticks(d_vals)
ax.set_xticklabels([r"$d_0$", r"$d_1$", r"$d_2$", r"$d_3$", r"$d_4$", r"$d_5$", r"$d_M\!=\!L$"])
ax.set_yticks(time_lines)
ax.set_yticklabels([("$T$" if abs(t - T) < 1e-9 else f"{int(t)}") for t in time_lines])
ax.tick_params(length=0)
for spine in ("bottom", "right"):
    ax.spines[spine].set_visible(False)

legend_elems = [
    Line2D([0], [0], color="#0d3b66", lw=2.4, ls="-", marker="v", markersize=6,
           markerfacecolor="#0d3b66", markeredgecolor="#0d3b66",
           label="distance line: heading change (segment)"),
    Line2D([0], [0], color="#aab7c2", lw=1.0, ls=(0, (1, 3)), label="distance line: cell crossing (0.5$\\degree$)"),
    Line2D([0], [0], color="#9aa7b4", lw=0.9, ls=(0, (4, 3)), label="time line: 6 h block (and $T$)"),
    Line2D([0], [0], color="#1565c0", lw=1.7, marker="o", markersize=5,
           markerfacecolor="#1565c0", markeredgecolor="white", label=r"speed edges $\to$ reachable states"),
    Line2D([0], [0], color="#e64a19", lw=2.6, label="a sample voyage (path)"),
]
ax.legend(handles=legend_elems, loc="upper right", fontsize=7.6, frameon=True,
          framealpha=0.95, borderpad=0.6, handlelength=2.2)

fig.tight_layout()
fig.savefig("state_space_grid.pdf", bbox_inches="tight")
fig.savefig("state_space_grid.png", dpi=200, bbox_inches="tight")
print("wrote state_space_grid.pdf and state_space_grid.png")

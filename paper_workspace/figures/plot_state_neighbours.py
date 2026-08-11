"""
Panel (a) of the state-neighbours pair: the popped state sits ON a
DISTANCE line, mid-block. Clean paper version — the teaching notes live
in the joint caption; the panel keeps only the geometry and short labels.

Conventions (legacy sketches): origin top-left; x = distance d (right);
y = elapsed time t (DOWN); vertical distance lines, horizontal time lines.
Band V = [0, v_max] (Aug-5 decision): the slow cone edge is vertical (wait).

Run:  python3 plot_state_neighbours.py
Outputs: state_neighbours.pdf, state_neighbours.png
"""

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon

# --- geometry (illustrative) -----------------------------------------------
d0, t0 = 10.0, 1.0          # the state: ON the distance line d = 10, mid-block
DW, TW = 30.0, 2.4          # next distance wall d_D(d); next time wall t_T(t)
VMAX = 20.0                 # V = [0, v_max]
TAU, DELTA = 0.2, 2.0       # grid steps on the walls

t_fast = t0 + (DW - d0) / VMAX

fam1_t = []                 # arrival times on the distance wall (anchored at TW)
n = 0
while TW - n * TAU >= t_fast - 1e-9:
    fam1_t.append(TW - n * TAU)
    n += 1
fam2_d = []                 # arrival distances on the time wall (anchored at DW)
n = 0
while DW - n * DELTA >= d0 - 1e-9:
    fam2_d.append(DW - n * DELTA)
    n += 1

NAVY, TIMEC = "#0d3b66", "#9aa7b4"
BLUE, GREEN = "#1565c0", "#2e7d32"
ORANGE, FAINT = "#e64a19", "#cfd8dc"

fig, ax = plt.subplots(figsize=(6.0, 4.6))
ax.axhspan(0.0, TW, color="#f4f7fa", zorder=0)

for t in (0.0, TW):
    ax.axhline(t, color=TIMEC, lw=1.0, ls=(0, (4, 3)), zorder=1)
ax.axvline(d0, color=NAVY, lw=1.8, alpha=0.5, zorder=1)      # the state's own line
ax.axvline(DW, color=NAVY, lw=2.4, zorder=1.6)               # the next wall

# faint grid dots outside the reachable windows
tt = TW
while tt > 0.05:
    if not any(abs(tt - x) < 1e-9 for x in fam1_t):
        ax.scatter([DW], [tt], s=13, color=FAINT, zorder=2)
    tt -= TAU
dd = DW
while dd > d0 - 6:
    if not any(abs(dd - x) < 1e-9 for x in fam2_d):
        ax.scatter([dd], [TW], s=13, color=FAINT, zorder=2)
    dd -= DELTA

# the admissible cone: fast edge to the wall, slow edge vertical (wait)
ax.add_patch(Polygon([(d0, t0), (DW, t_fast), (DW, TW), (d0, TW)], closed=True,
                     facecolor="#fff3e0", edgecolor="none", alpha=0.85, zorder=1.2))
ax.plot([d0, DW], [t0, t_fast], color=ORANGE, lw=2.0, zorder=3)
ax.plot([d0, d0], [t0, TW], color=ORANGE, lw=2.0, zorder=3)
ax.plot([DW, DW + 2.6], [t_fast, t_fast + 2.6 / VMAX],
        color=ORANGE, lw=1.1, ls=(0, (2, 3)), alpha=0.55, zorder=2.5)

# candidate arcs + family nodes -- thin the fan lines when there are many
# candidates (readability); every dot/square and its number label stays.
fam2_only = [dp for dp in fam2_d if abs(dp - DW) > 1e-9]
fan1_step = 1 if len(fam1_t) <= 5 else 2
for i, tp in enumerate(fam1_t):
    if i % fan1_step == 0 or i == len(fam1_t) - 1:
        ax.plot([d0, DW], [t0, tp], color="#8ea8c3", lw=0.9, alpha=0.85, zorder=2.8)
fan2_step = 1 if len(fam2_only) <= 5 else 2
for i, dp in enumerate(fam2_only):
    if i % fan2_step == 0 or i == len(fam2_only) - 1:
        ax.plot([d0, dp], [t0, TW], color="#9dbf9e", lw=0.9, alpha=0.9, zorder=2.8)
ax.scatter([DW] * len(fam1_t), fam1_t, s=64, color=BLUE, zorder=4,
           edgecolor="white", lw=0.8)
ax.scatter(fam2_only, [TW] * len(fam2_only), s=64, color=GREEN, zorder=4,
           edgecolor="white", lw=0.8, marker="s")

# grid-value numbers: time on the blue (distance-wall) dots, distance on the
# green (time-wall) squares -- makes the tau/delta spacing concrete. Units
# shown on the first and last of each family only (not every one).
for i, tp in enumerate(fam1_t):
    label = f"{tp:.1f} h" if i in (0, len(fam1_t) - 1) else f"{tp:.1f}"
    ax.annotate(label, (DW, tp), xytext=(9, 0), textcoords="offset points",
                fontsize=8.5, color=BLUE, va="center", ha="left")
for i, dp in enumerate(fam2_only):
    label = f"{dp:.0f} NM" if i in (0, len(fam2_only) - 1) else f"{dp:.0f}"
    ax.annotate(label, (dp, TW), xytext=(0, -9), textcoords="offset points",
                fontsize=8.5, color=GREEN, va="top", ha="center")

# the state
ax.scatter([d0], [t0], s=130, color="#c62828", zorder=5, edgecolor="white", lw=1.1)
ax.annotate(r"$(d,t)$", (d0, t0), xytext=(-12, 11), textcoords="offset points",
            fontsize=14, color="#c62828", ha="right")

# short labels
ax.annotate(r"$d_{\mathcal{D}(d)}$", (DW, 0.10), xytext=(7, 0),
            textcoords="offset points", fontsize=13, color=NAVY, va="top")
ax.annotate(r"$t_{\mathcal{T}(t)}$", (d0 - 5.6, TW), xytext=(0, 9),
            textcoords="offset points", fontsize=13, color="#607080")
ax.annotate(r"$v_{\max}$", (d0 + (DW - d0) * 0.60, t0 + (DW - d0) * 0.60 / VMAX),
            xytext=(0, 12), textcoords="offset points", fontsize=12.5,
            color=ORANGE, ha="center")
ax.annotate(r"$\bar v = 0$", (d0, (t0 + TW) / 2 + 0.12), xytext=(-9, 0),
            textcoords="offset points", fontsize=12.5, color=ORANGE,
            rotation=90, va="center", ha="right")
ktotal = len(fam1_t) + len(fam2_only)

ax.set_xlim(d0 - 6.5, DW + 5.8)
ax.set_ylim(TW + 0.28, -0.16)
ax.set_xticks([]); ax.set_yticks([])
for s in ax.spines.values():
    s.set_visible(False)
fig.tight_layout()

# orientation compass: own inset axes reserved above the plot, so it never
# collides with data-dependent label positions in either panel.
fig.subplots_adjust(top=0.84)
COMPASS = "#33475b"
ax_c = fig.add_axes([0.06, 0.87, 0.34, 0.11])
ax_c.set_xlim(0, 1); ax_c.set_ylim(0, 1); ax_c.axis("off")
ax_c.annotate("", xy=(0.30, 0.80), xytext=(0.02, 0.80),
              arrowprops=dict(arrowstyle="-|>", color=COMPASS, lw=1.4, mutation_scale=14))
ax_c.annotate("", xy=(0.02, 0.10), xytext=(0.02, 0.80),
              arrowprops=dict(arrowstyle="-|>", color=COMPASS, lw=1.4, mutation_scale=14))
ax_c.text(0.36, 0.80, "distance $d$ [NM]", fontsize=10.5, color=COMPASS, va="center", ha="left")
ax_c.text(0.08, 0.10, "time $t$ [h]", fontsize=10.5, color=COMPASS, va="center", ha="left")

fig.savefig("state_neighbours.pdf")
fig.savefig("state_neighbours.png", dpi=300)
print("panel (a): kappa =", ktotal, "| fam1:", len(fam1_t), "| fam2:", len(fam2_only))

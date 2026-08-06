"""
One-state neighbour figure for §4.2's FIG placeholder:

  "a single state (d,t), its two walls d_D(d) and t_T(t), the admissible
   speed cone [v_min, v_max], and the kappa candidate grid nodes it selects
   on the walls --- the two families of Eq. (5)"

Conventions match plot_state_space_grid.py (and the legacy sketches):
  - origin top-left; x = along-track distance d (rightward);
    y = elapsed time t (DOWNWARD);
  - VERTICAL distance lines (cell / heading boundaries),
    HORIZONTAL time lines (forecast blocks).

Values are illustrative, chosen for legibility (kappa = 8 here):
  state (d0,t0) sits ON a distance line (every DP state sits on a line);
  the v_max ray reaches the distance wall inside the block (family 1 opens),
  the v_min ray runs out of the block first (family 1 is clipped at the
  time wall), and the fast part of the cone overshoots the distance wall
  (family 2 is capped at it).

Run:  python3 plot_state_neighbours.py
Outputs: state_neighbours.pdf, state_neighbours.png
"""

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon
from matplotlib.lines import Line2D

# --- geometry (illustrative) -------------------------------------------------
d0, t0 = 10.0, 1.0          # the popped state: ON the distance line d = 10, mid-block (clearly interior)
DW = 30.0                   # next distance wall  d_D(d)
TW = 2.4                    # next time wall      t_T(t)
VMAX, VMIN = 20.0, 0.0      # admissible band V = [0, v_max] (2026-08-05 decision): waiting allowed
TAU, DELTA = 0.2, 2.0       # grid steps on the walls (tau on DW, delta on TW)

t_fast = t0 + (DW - d0) / VMAX          # v_max hits the distance wall (1.4)
d_slow = d0 + VMIN * (TW - t0)          # v = 0: no advance -- the slow edge is vertical (d_slow = d0)
d_fast = d0 + VMAX * (TW - t0)          # v_max "hits" the time wall at 50 -> capped at DW

# family 1: arrival times on the distance wall, anchored at TW stepping back
fam1_t, n = [], 0
while True:
    tp = TW - n * TAU
    n += 1
    if tp < t_fast - 1e-9:
        break
    fam1_t.append(tp)
# family 2: arrival distances on the time wall, anchored at DW stepping back
fam2_d, n = [], 0
while True:
    dp = DW - n * DELTA
    n += 1
    if dp < d_slow - 1e-9:
        break
    fam2_d.append(dp)

NAVY, TIMEC = "#0d3b66", "#9aa7b4"
BLUE, GREEN = "#1565c0", "#2e7d32"
ORANGE, FAINT = "#e64a19", "#cfd8dc"

fig, ax = plt.subplots(figsize=(7.4, 5.0))

# faint block shading between the walls behind everything
ax.axhspan(0.0, TW, color="#f4f7fa", zorder=0)

# time lines (horizontal, dashed) and distance lines (vertical)
for t in (0.0, TW):
    ax.axhline(t, color=TIMEC, lw=0.9, ls=(0, (4, 3)), zorder=1)
ax.axvline(d0, color=NAVY, lw=1.6, alpha=0.5, zorder=1)
ax.text(d0 + 0.5, 0.14, "the state lives on this distance line (just crossed)",
        fontsize=7.6, color=NAVY, alpha=0.85, ha="left")
ax.axvline(DW, color=NAVY, lw=2.2, zorder=1.6)

# faint grid dots on the walls OUTSIDE the reachable windows
tt = TW
while tt > 0.05:
    if not any(abs(tt - x) < 1e-9 for x in fam1_t):
        ax.scatter([DW], [tt], s=10, color=FAINT, zorder=2)
    tt -= TAU
dd = DW
while dd > d0 - 6:
    if not any(abs(dd - x) < 1e-9 for x in fam2_d):
        ax.scatter([dd], [TW], s=10, color=FAINT, zorder=2)
    dd -= DELTA

# the admissible speed cone (slow edge vertical: v = 0, the vessel may wait in place)
cone = Polygon([(d0, t0), (DW, t_fast), (DW, TW), (d_slow, TW)],
               closed=True, facecolor="#fff3e0", edgecolor="none",
               alpha=0.85, zorder=1.2)
ax.add_patch(cone)
ax.plot([d0, DW], [t0, t_fast], color=ORANGE, lw=1.8, zorder=3)          # v_max edge
ax.plot([d0, d_slow], [t0, TW], color=ORANGE, lw=1.8, zorder=3)          # v = 0 edge (vertical)
# dotted continuation showing why the fast window is capped at the wall
ax.plot([DW, DW + 3.0], [t_fast, t_fast + 3.0 / VMAX],
        color=ORANGE, lw=1.0, ls=(0, (2, 3)), alpha=0.55, zorder=2.5)    # v_max past the wall

# candidate arcs + the two families of nodes
for tp in fam1_t:
    ax.plot([d0, DW], [t0, tp], color="#8ea8c3", lw=0.8, alpha=0.85, zorder=2.8)
for dp in fam2_d:
    if abs(dp - DW) > 1e-9:  # corner drawn once, with family 1
        ax.plot([d0, dp], [t0, TW], color="#9dbf9e", lw=0.8, alpha=0.9, zorder=2.8)
ax.scatter([DW] * len(fam1_t), fam1_t, s=46, color=BLUE, zorder=4,
           edgecolor="white", lw=0.7,
           label=r"family 1: arrival times on $d_{\mathcal{D}(d)}$  ($\tau$-spaced)")
fam2_only = [dp for dp in fam2_d if abs(dp - DW) > 1e-9]
ax.scatter(fam2_only, [TW] * len(fam2_only), s=46, color=GREEN, zorder=4,
           edgecolor="white", lw=0.7, marker="s",
           label=r"family 2: arrival distances on $t_{\mathcal{T}(t)}$  ($\delta$-spaced)")

# the state itself
ax.scatter([d0], [t0], s=90, color="#c62828", zorder=5, edgecolor="white", lw=1.0)
ax.annotate(r"$(d,t)$ — on a distance line", (d0 + 0.35, t0 - 0.04), xytext=(16.0, 0.66), textcoords="data",
            fontsize=10.5, color="#c62828", ha="center",
            arrowprops=dict(arrowstyle="-", color="#c62828", lw=0.7,
                            connectionstyle="arc3,rad=-0.2"))

# wall labels
ax.annotate(r"$d_{\mathcal{D}(d)}$ — next distance line" "\n(sea conditions change)",
            (DW, 0.06), xytext=(6, 0), textcoords="offset points",
            fontsize=8.5, color=NAVY, va="top", style="italic")
ax.annotate(r"$t_{\mathcal{T}(t)}$ — next time line (forecast refreshes)",
            (d0 - 5.2, TW), xytext=(0, 8), textcoords="offset points",
            fontsize=8.5, color="#607080", style="italic")

# cone-edge labels (v_max above its ray; the vertical edge is v = 0 — waiting)
ax.annotate(r"$v_{\max}$", (d0 + (DW - d0) * 0.62, t0 + (DW - d0) * 0.62 / VMAX),
            xytext=(0, 10), textcoords="offset points", fontsize=9.5, color=ORANGE,
            ha="center")
ax.annotate(r"$\bar v = 0$ (wait)", (d0, 2.16),
            xytext=(-8, 0), textcoords="offset points", fontsize=9.5, color=ORANGE,
            rotation=90, va="center", ha="right")

# derived-speed line — top band, no arrow (applies to every candidate)
ax.text(19.0, 0.32,
        r"each candidate fixes its own leg speed  "
        r"$\bar v = (\tilde d - d)\,/\,(\tilde t - t) \in \mathcal{V}$ — derived, not chosen",
        fontsize=8.2, color="#33475b", ha="center", style="italic")

# clip/cap notes — in the empty regions outside the cone
ax.annotate("$v_{\\max}$ crosses the wall before the block ends\n"
            "→ family 2 capped at the distance wall",
            (DW + 0.9, t_fast + 0.12), xytext=(21.0, 1.42), textcoords="data",
            fontsize=7.8, color="#8a6d3b", ha="center",
            arrowprops=dict(arrowstyle="-", color="#8a6d3b", lw=0.7,
                            connectionstyle="arc3,rad=-0.18"))
ax.annotate("slow speeds (down to waiting in place) leave the\nblock first → family 1 clipped at the time wall",
            (d0 + 0.4, TW - 0.05), xytext=(13.5, 2.02), textcoords="data",
            fontsize=7.8, color="#8a6d3b", ha="center",
            arrowprops=dict(arrowstyle="-", color="#8a6d3b", lw=0.7,
                            connectionstyle="arc3,rad=0.15"))

# kappa tally — horizontal, to the right of the wall
ktotal = len(fam1_t) + len(fam2_only)
ax.text(DW + 1.0, (t_fast + TW) / 2 + 0.05,
        rf"$\kappa = {ktotal}$" "\ncandidates", fontsize=10.5, color="#33475b",
        va="center", ha="left")

ax.set_xlim(d0 - 6.5, DW + 6.5)
ax.set_ylim(TW + 0.5, -0.18)           # time increases downward
ax.set_xlabel("along-track distance  d  (NM)")
ax.set_ylabel("elapsed time  t  (h)")
ax.set_xticks([])
ax.set_yticks([])
for s in ax.spines.values():
    s.set_visible(False)

ax.legend(loc="lower left", fontsize=8.2, frameon=True, framealpha=0.95,
          borderpad=0.7)
fig.tight_layout()
fig.savefig("state_neighbours.pdf")
fig.savefig("state_neighbours.png", dpi=300)
print("kappa =", ktotal, "| family1:", len(fam1_t), "| family2 (excl. corner):", len(fam2_only))

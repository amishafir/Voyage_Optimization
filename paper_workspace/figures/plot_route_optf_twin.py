"""
Geographic twin of state_space_optF: the SAME voyage on a real map.

A two-leg illustrative voyage (one heading change) is drawn on a real
Gulf-of-Oman basemap over the 0.5 deg weather-cell grid, and EVERY point that
appears in state_space_optF is shown here too, with matching colours/order:
  - cell-boundary crossings        (brown, weather changes in space)
  - 6 h time-block positions       (blue, weather changes in time; placed from
                                    the constant-speed schedule -> ship position
                                    at t = 6, 12, 18, 24 h)
  - the heading change             (navy, course psi, at the waypoint)
  - start (Port A) and arrival     (black dot / red star)

So the two panels correspond point-for-point: optF on the time-distance plane,
this on the map. Legs are straight over open water (no sea-routing artifact).

Run:  python3 plot_route_optf_twin.py
Outputs: route_optf_twin.pdf, route_optf_twin.png
"""

from math import ceil, floor

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
import cartopy.crs as ccrs
import cartopy.feature as cfeature

# --- Illustrative two-leg voyage (lon, lat) over the Gulf of Oman -----------
# Sized so each leg crosses exactly two 0.5 deg cell boundaries -> the same
# 10 points as state_space_optF (4 cell + 4 time + heading + arrival).
A = (57.60, 24.30)     # start (Port A)
J = (58.35, 24.95)     # heading-change waypoint
B = (58.95, 24.45)     # arrival (Port B)
ROUTE = [A, J, B]
T = 28.0
TMARKS = [6, 12, 18, 24]
CELL = 0.5
WINDOW = (57.0, 59.7, 23.5, 25.8)

LAND = "#e8e3d8"
SEA = "#dce9f2"
TRACK = "#b2182b"
NAVY = "#0d3b66"
CELLC = "#8a6d1a"
TIMEC = "#3a6ea5"
ARRC = "#c62828"
TINT = ("#cfe0f1", "#abc9e8")


def seg_len(p, q):
    return ((p[0] - q[0]) ** 2 + (p[1] - q[1]) ** 2) ** 0.5


seglens = [seg_len(ROUTE[i], ROUTE[i + 1]) for i in range(len(ROUTE) - 1)]
total = sum(seglens)


def pos_at_frac(f):
    """Geographic (lon, lat) at fractional distance f in [0,1] along the route."""
    d = f * total
    for i, L in enumerate(seglens):
        if d <= L or i == len(seglens) - 1:
            t = d / L if L > 0 else 0
            p, q = ROUTE[i], ROUTE[i + 1]
            return (p[0] + t * (q[0] - p[0]), p[1] + t * (q[1] - p[1]))
        d -= L
    return ROUTE[-1]


def cum_of(lon, lat):
    """Cumulative distance of a point known to lie on the route polyline."""
    acc = 0.0
    for i, L in enumerate(seglens):
        p, q = ROUTE[i], ROUTE[i + 1]
        # project onto this segment; accept if close
        vx, vy = q[0] - p[0], q[1] - p[1]
        t = ((lon - p[0]) * vx + (lat - p[1]) * vy) / (vx * vx + vy * vy)
        if -1e-6 <= t <= 1 + 1e-6:
            px, py = p[0] + t * vx, p[1] + t * vy
            if abs(px - lon) + abs(py - lat) < 1e-6:
                return acc + t * L
        acc += L
    return acc


def seg_crossings(p, q):
    ts = []
    if abs(q[0] - p[0]) > 1e-12:
        for k in range(ceil(min(p[0], q[0]) / CELL), floor(max(p[0], q[0]) / CELL) + 1):
            t = (k * CELL - p[0]) / (q[0] - p[0])
            if 1e-6 < t < 1 - 1e-6:
                ts.append(t)
    if abs(q[1] - p[1]) > 1e-12:
        for k in range(ceil(min(p[1], q[1]) / CELL), floor(max(p[1], q[1]) / CELL) + 1):
            t = (k * CELL - p[1]) / (q[1] - p[1])
            if 1e-6 < t < 1 - 1e-6:
                ts.append(t)
    return [(p[0] + t * (q[0] - p[0]), p[1] + t * (q[1] - p[1]))
            for t in sorted(set(round(v, 6) for v in ts))]


# --- Build all events -------------------------------------------------------
events = []   # (cum, lon, lat, type, color)
for i in range(len(ROUTE) - 1):
    for (lo, la) in seg_crossings(ROUTE[i], ROUTE[i + 1]):
        events.append((cum_of(lo, la), lo, la, "cell", CELLC))
for tm in TMARKS:
    lo, la = pos_at_frac(tm / T)
    events.append((tm / T * total, lo, la, "time", TIMEC))
events.append((seglens[0], J[0], J[1], "heading", NAVY))   # heading change at J

# drop a cell crossing that coincides with the heading waypoint
events = [e for e in events if e[3] == "heading"
          or not (abs(e[1] - J[0]) < 0.06 and abs(e[2] - J[1]) < 0.06)]
events.sort(key=lambda e: e[0])

# --- Traversed cells --------------------------------------------------------
samp = []
for i in range(len(ROUTE) - 1):
    n = max(1, int(seglens[i] / 0.02))
    for t in range(n + 1):
        f = t / n
        samp.append((ROUTE[i][0] + f * (ROUTE[i + 1][0] - ROUTE[i][0]),
                     ROUTE[i][1] + f * (ROUTE[i + 1][1] - ROUTE[i][1])))
cells = sorted({(floor(lo / CELL), floor(la / CELL)) for lo, la in samp})

# --- Plot -------------------------------------------------------------------
lon0, lon1, lat0, lat1 = WINDOW
fig = plt.figure(figsize=(8.2, 5.2))
ax = plt.axes(projection=ccrs.PlateCarree())
ax.set_extent(WINDOW, crs=ccrs.PlateCarree())
ax.set_facecolor(SEA)
ax.add_feature(cfeature.LAND.with_scale("10m"), facecolor=LAND, zorder=4, rasterized=True)
ax.add_feature(cfeature.COASTLINE.with_scale("10m"), linewidth=0.5,
               edgecolor="#555555", zorder=5, rasterized=True)

for ci, cj in cells:
    ax.add_patch(plt.Rectangle((ci * CELL, cj * CELL), CELL, CELL,
                               transform=ccrs.PlateCarree(), facecolor=TINT[(ci + cj) % 2],
                               edgecolor="#7fa3c4", lw=0.5, alpha=0.75, zorder=2.5))
for x in np.arange(floor(lon0 / CELL) * CELL, lon1 + 1e-9, CELL):
    ax.plot([x, x], [lat0, lat1], color="#9fb3c8", lw=0.5, ls=(0, (1, 2)),
            transform=ccrs.PlateCarree(), zorder=2.6)
for y in np.arange(floor(lat0 / CELL) * CELL, lat1 + 1e-9, CELL):
    ax.plot([lon0, lon1], [y, y], color="#9fb3c8", lw=0.5, ls=(0, (1, 2)),
            transform=ccrs.PlateCarree(), zorder=2.6)

ax.plot([p[0] for p in ROUTE], [p[1] for p in ROUTE], "-", color=TRACK,
        linewidth=2.2, transform=ccrs.PlateCarree(), zorder=6, solid_capstyle="round")

# Numbered points (1..N in route order), then arrival as the last number
for i, (_, lo, la, ty, c) in enumerate(events, start=1):
    ax.text(lo, la, str(i), transform=ccrs.PlateCarree(), fontsize=8,
            fontweight="bold", color="white", ha="center", va="center", zorder=8,
            bbox=dict(boxstyle="circle,pad=0.22", fc=c, ec="white", lw=0.9))
n_arr = len(events) + 1
ax.plot(B[0], B[1], marker="*", color=ARRC, markersize=15, markeredgecolor="white",
        markeredgewidth=0.8, transform=ccrs.PlateCarree(), zorder=9)
ax.text(B[0], B[1], str(n_arr), transform=ccrs.PlateCarree(), fontsize=8,
        fontweight="bold", color="white", ha="center", va="center", zorder=10)

# Start
ax.plot(A[0], A[1], "o", color="black", markersize=6, transform=ccrs.PlateCarree(), zorder=9)
ax.text(A[0] - 0.1, A[1] - 0.18, "Port A — start", fontsize=8.5, transform=ccrs.PlateCarree(),
        ha="left", va="top", zorder=9,
        bbox=dict(boxstyle="round,pad=0.15", fc="white", ec="none", alpha=0.85))
ax.text(B[0] + 0.1, B[1] + 0.12, "Port B", fontsize=8.5, transform=ccrs.PlateCarree(),
        ha="left", va="center", color=ARRC, zorder=9,
        bbox=dict(boxstyle="round,pad=0.15", fc="white", ec="none", alpha=0.85))

gl = ax.gridlines(draw_labels=True, linewidth=0, alpha=0)
gl.top_labels = False
gl.right_labels = False
gl.xlabel_style = {"size": 7}
gl.ylabel_style = {"size": 7}

ax.set_title("Geographic twin of the state space: each numbered point matches "
             "state\\_space\\_optF", fontsize=9, pad=6)

ax.legend(handles=[
    Line2D([0], [0], color=TRACK, lw=2.2, label="route"),
    Line2D([0], [0], marker="o", color=CELLC, lw=0, markersize=8, markeredgecolor="white",
           label="cell-boundary crossing (weather, space)"),
    Line2D([0], [0], marker="o", color=TIMEC, lw=0, markersize=8, markeredgecolor="white",
           label="6 h block (weather, time)"),
    Line2D([0], [0], marker="o", color=NAVY, lw=0, markersize=8, markeredgecolor="white",
           label="heading change (course $\\psi$)"),
    Line2D([0], [0], marker="*", color=ARRC, lw=0, markersize=11, markeredgecolor="white",
           label="arrival (ETA)"),
    Patch(facecolor=TINT[0], edgecolor="#7fa3c4", alpha=0.8, label="0.5$\\degree$ weather cell"),
], loc="lower right", fontsize=7, frameon=True, framealpha=0.95)

fig.savefig("route_optf_twin.pdf", dpi=300, bbox_inches="tight", pad_inches=0.02)
fig.savefig("route_optf_twin.png", dpi=200, bbox_inches="tight", pad_inches=0.02)
print(f"wrote route_optf_twin.* ({len(events)} numbered crossings + arrival = {len(events)+1}, "
      f"{len(cells)} cells)")

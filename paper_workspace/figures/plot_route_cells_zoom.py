"""
Coastal zoom that demonstrates the speed-change points of state_space_optF on a
real map.

Focuses on the START of Route 1 — the Persian Gulf / Strait of Hormuz / Gulf of
Oman — which is enclosed by land (Arabia, Iran, Oman), so it reads clearly as a
map while the 0.5 deg cells stay large. The track is sea-routed around the
Musandam peninsula. Shows:
  - coastlines and land (it looks like a map),
  - individual 0.5 deg GEOGRAPHIC CELLS (checkerboard tint + grid),
  - the ROUTE (sea-respecting),
  - START point (Port A) and the HEADING-CHANGE waypoint (course psi),
  - every CELL-BOUNDARY CROSSING as a numbered speed-change point.

Spatial twin of state_space_optF: every crossing (brown = cell, navy = heading)
is a point where the speed may change.

Run:  python3 plot_route_cells_zoom.py
Outputs: route_cells_zoom.pdf, route_cells_zoom.png
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

from sea_routing import SeaGrid, clip_to_sea

# --- Route 1 start waypoints (lat, lon): Port A, Gulf of Oman, Arabian Sea 1 -
WPS = [(24.75, 52.83), (26.55, 56.45), (24.08, 60.88)]
HEADING_WPS = [(26.55, 56.45)]            # interior waypoint = heading change
START = (24.75, 52.83)
CELL = 0.5
WINDOW = (51.4, 60.9, 22.3, 27.6)         # lon0, lon1, lat0, lat1

LAND = "#e8e3d8"
SEA = "#dce9f2"
TRACK = "#b2182b"
NAVY = "#0d3b66"
CELLC = "#8a6d1a"
TINT = ("#cfe0f1", "#abc9e8")

# --- Sea-routed track through the strait ------------------------------------
grid = SeaGrid((50, 62, 21.5, 28.5), 0.10, 0.05)
track = clip_to_sea(grid.route(WPS))

lon0, lon1, lat0, lat1 = WINDOW


def in_win(la, lo):
    return lon0 <= lo <= lon1 and lat0 <= la <= lat1


def seg_crossings(a, b):
    la0, lo0 = a
    la1, lo1 = b
    ts = []
    if abs(lo1 - lo0) > 1e-12:
        for k in range(ceil(min(lo0, lo1) / CELL), floor(max(lo0, lo1) / CELL) + 1):
            t = (k * CELL - lo0) / (lo1 - lo0)
            if 1e-6 < t < 1 - 1e-6:
                ts.append(t)
    if abs(la1 - la0) > 1e-12:
        for k in range(ceil(min(la0, la1) / CELL), floor(max(la0, la1) / CELL) + 1):
            t = (k * CELL - la0) / (la1 - la0)
            if 1e-6 < t < 1 - 1e-6:
                ts.append(t)
    return [(la0 + t * (la1 - la0), lo0 + t * (lo1 - lo0))
            for t in sorted(set(round(v, 6) for v in ts))]


# Cell-boundary crossings along the (sea-routed) track, in order
raw = []
for a, b in zip(track[:-1], track[1:]):
    raw += seg_crossings(a, b)
# de-duplicate near-identical consecutive crossings (the A* track is dense)
crossings = []
for p in raw:
    if not crossings or abs(p[0] - crossings[-1][0]) + abs(p[1] - crossings[-1][1]) > 0.12:
        crossings.append(p)

# Build ordered events (cell crossings + heading-change waypoints) by inserting
# each heading waypoint at its nearest position along the crossing list.
events = [(la, lo, "cell") for (la, lo) in crossings if in_win(la, lo)]
for hla, hlo in HEADING_WPS:
    if in_win(hla, hlo):
        events.append((hla, hlo, "heading"))
# drop cell crossings within ~9 km of a heading waypoint (they coincide)
hs = [e for e in events if e[2] == "heading"]
events = [e for e in events if e[2] == "heading"
          or not any(abs(e[0] - h[0]) < 0.09 and abs(e[1] - h[1]) < 0.09 for h in hs)]
# order along the track by cumulative arc position
order = {}
acc = 0.0
prev = track[0]
for p in track:
    acc += ((p[0] - prev[0]) ** 2 + (p[1] - prev[1]) ** 2) ** 0.5
    prev = p
def arc_of(la, lo):
    best, bd = 0.0, 1e9
    a = 0.0
    prev = track[0]
    for p in track:
        a += ((p[0] - prev[0]) ** 2 + (p[1] - prev[1]) ** 2) ** 0.5
        d = (p[0] - la) ** 2 + (p[1] - lo) ** 2
        if d < bd:
            bd, best = d, a
        prev = p
    return best
events.sort(key=lambda e: arc_of(e[0], e[1]))

# Focus on a span of consecutive points around the heading change (Strait of
# Hormuz) and zoom the display window tightly around them, keeping their
# original numbers.
FOCUS = {3, 4, 5, 6, 7, 8, 9, 10}
focus = [(i, la, lo, ty) for i, (la, lo, ty) in enumerate(events, start=1) if i in FOCUS]
_flo = [lo for _, _, lo, _ in focus]
_fla = [la for _, la, _, _ in focus]
MLO, MLA = 0.55, 0.45
WINDOW = (min(_flo) - MLO, max(_flo) + MLO, min(_fla) - MLA, max(_fla) + MLA)
lon0, lon1, lat0, lat1 = WINDOW

# Traversed 0.5 deg cells within the window
samp = []
for a, b in zip(track[:-1], track[1:]):
    n = max(1, int(((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5 / 0.02))
    for t in range(n + 1):
        f = t / n
        samp.append((a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f))
cells = sorted({(floor(lo / CELL), floor(la / CELL)) for la, lo in samp
                if lon0 - CELL <= lo <= lon1 + CELL and lat0 - CELL <= la <= lat1 + CELL})

# --- Plot -------------------------------------------------------------------
fig = plt.figure(figsize=(8.0, 5.0))
ax = plt.axes(projection=ccrs.PlateCarree())
ax.set_extent(WINDOW, crs=ccrs.PlateCarree())
ax.set_facecolor(SEA)
ax.add_feature(cfeature.LAND.with_scale("10m"), facecolor=LAND, zorder=4, rasterized=True)
ax.add_feature(cfeature.COASTLINE.with_scale("10m"), linewidth=0.5,
               edgecolor="#555555", zorder=5, rasterized=True)

# Checkerboard 0.5 deg cells the route passes through
for ci, cj in cells:
    ax.add_patch(plt.Rectangle((ci * CELL, cj * CELL), CELL, CELL,
                               transform=ccrs.PlateCarree(),
                               facecolor=TINT[(ci + cj) % 2], edgecolor="#7fa3c4",
                               lw=0.5, alpha=0.75, zorder=2.5))

# 0.5 deg grid lines across the window
for x in np.arange(floor(lon0 / CELL) * CELL, lon1 + 1e-9, CELL):
    ax.plot([x, x], [lat0, lat1], color="#9fb3c8", lw=0.5, ls=(0, (1, 2)),
            transform=ccrs.PlateCarree(), zorder=2.6)
for y in np.arange(floor(lat0 / CELL) * CELL, lat1 + 1e-9, CELL):
    ax.plot([lon0, lon1], [y, y], color="#9fb3c8", lw=0.5, ls=(0, (1, 2)),
            transform=ccrs.PlateCarree(), zorder=2.6)

# Route
ax.plot([p[1] for p in track], [p[0] for p in track], "-", color=TRACK,
        linewidth=2.2, transform=ccrs.PlateCarree(), zorder=6, solid_capstyle="round")

# Numbered speed-change points (only the focus subset, original numbers)
for i, la, lo, ty in focus:
    c = NAVY if ty == "heading" else CELLC
    ax.text(lo, la, str(i), transform=ccrs.PlateCarree(), fontsize=9,
            fontweight="bold", color="white", ha="center", va="center", zorder=8,
            bbox=dict(boxstyle="circle,pad=0.30", fc=c, ec="white", lw=1.0))

# Context arrows (Port A and Port B are off this zoom)
ax.text(lon0 + 0.12, lat1 - 0.18, "$\\leftarrow$ from Port A", fontsize=8.5,
        color=TRACK, transform=ccrs.PlateCarree(), ha="left", va="center", zorder=9,
        bbox=dict(boxstyle="round,pad=0.15", fc="white", ec="none", alpha=0.85))
ax.text(lon1 - 0.12, lat0 + 0.22, "to Port B $\\rightarrow$", fontsize=8.5,
        color=TRACK, transform=ccrs.PlateCarree(), ha="right", va="center", zorder=9,
        bbox=dict(boxstyle="round,pad=0.15", fc="white", ec="none", alpha=0.85))

gl = ax.gridlines(draw_labels=True, linewidth=0, alpha=0)
gl.top_labels = False
gl.right_labels = False
gl.xlabel_style = {"size": 7}
gl.ylabel_style = {"size": 7}

ax.set_title("Persian Gulf $\\to$ Strait of Hormuz $\\to$ Gulf of Oman: each cell "
             "crossing and the heading change is a speed-change point",
             fontsize=8.6, pad=6)

ax.legend(handles=[
    Line2D([0], [0], color=TRACK, lw=2.2, label="route"),
    Line2D([0], [0], marker="o", color=CELLC, lw=0, markersize=8,
           markeredgecolor="white", label="cell-boundary crossing (weather, space)"),
    Line2D([0], [0], marker="o", color=NAVY, lw=0, markersize=8,
           markeredgecolor="white", label="heading change (course $\\psi$)"),
    Patch(facecolor=TINT[0], edgecolor="#7fa3c4", alpha=0.8,
          label="0.5$\\degree$ weather cell (subsegment)"),
], loc="upper center", bbox_to_anchor=(0.5, -0.10), ncol=2, fontsize=7.5,
   frameon=True, framealpha=0.95)

fig.savefig("route_cells_zoom.pdf", dpi=300, bbox_inches="tight", pad_inches=0.02)
fig.savefig("route_cells_zoom.png", dpi=200, bbox_inches="tight", pad_inches=0.02)
print(f"wrote route_cells_zoom.pdf and route_cells_zoom.png "
      f"({len(events)} numbered points, {len(cells)} cells)")

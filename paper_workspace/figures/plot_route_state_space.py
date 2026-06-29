"""
Spatial projection of the state-space figure (state_space_optF) onto the real
route map, in the spirit of routes.png.

For Route 1 (Persian Gulf -> Strait of Malacca) it draws, on the real coastline
map:
  - the 0.5 deg GEOGRAPHIC CELLS the route passes through (shaded band + edges),
  - the ROUTE (sea-respecting track),
  - START / END points (Port A / Port B),
  - the HEADING-CHANGE waypoints (course psi changes), navy markers.

The shaded-cell band is the spatial counterpart of the state-space lattice:
each 0.5 deg cell the route enters is a subsegment, and each cell edge it
crosses is a distance line; the interior waypoints are the heading changes.
The temporal boundaries (6 h blocks, arrival) live only in the time-distance
figure and have no spatial counterpart.

Reuses the land geometry + A* sea router from make_route_maps.py (copied here so
this script is self-contained and has no import side effects).

Run:  python3 plot_route_state_space.py
Outputs: route_state_space.pdf, route_state_space.png
"""

import heapq
import math
from math import floor

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
import cartopy.crs as ccrs
import cartopy.feature as cfeature
import cartopy.io.shapereader as shpreader
import shapely
from shapely.geometry import LineString, Point
from shapely.ops import unary_union
from shapely.prepared import prep

# --- Route 1 waypoints (lat, lon) ------------------------------------------
ROUTE1 = [
    (24.75, 52.83), (26.55, 56.45), (24.08, 60.88), (21.73, 65.73),
    (17.96, 69.19), (14.18, 72.07), (10.45, 75.16), (7.00, 78.46),
    (5.64, 82.12), (4.54, 87.04), (5.20, 92.27), (5.64, 97.16),
    (1.81, 100.10),
]
EXTENT = (48, 103, -2, 30)
CELL = 0.5

LAND = "#e8e3d8"
SEA = "#dce9f2"
TRACK = "#b2182b"
NAVY = "#0d3b66"
CELL_FILL = "#aaccee"
CELL_EDGE = "#5a86b0"

# --- Land geometry (10 m) ---------------------------------------------------
_land_geoms = list(shpreader.Reader(shpreader.natural_earth(
    resolution="10m", category="physical", name="land")).geometries())
LAND_UNION = unary_union(_land_geoms)
PREP_LAND = prep(LAND_UNION)


def clip_to_sea(track, dstep=0.05):
    pts = []
    for a, b in zip(track[:-1], track[1:]):
        n = max(1, int(math.hypot(a[0] - b[0], a[1] - b[1]) / dstep))
        for t in range(n):
            f = t / n
            pts.append((a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f))
    pts.append(track[-1])
    return [p for p in pts if not PREP_LAND.contains(Point(p[1], p[0]))]


class SeaGrid:
    def __init__(self, extent, step, clearance):
        lon0, lon1, lat0, lat1 = extent
        pad = 1.0
        self.lons = np.arange(lon0 - pad, lon1 + pad + 1e-9, step)
        self.lats = np.arange(lat0 - pad, lat1 + pad + 1e-9, step)
        self.step = step
        gx, gy = np.meshgrid(self.lons, self.lats)
        blocked = LAND_UNION.buffer(clearance)
        self.sea = ~shapely.contains_xy(blocked, gx, gy)
        self.nlat, self.nlon = self.sea.shape

    def _nearest_sea(self, lon, lat):
        i = int(round((lon - self.lons[0]) / self.step))
        j = int(round((lat - self.lats[0]) / self.step))
        i = min(max(i, 0), self.nlon - 1)
        j = min(max(j, 0), self.nlat - 1)
        if self.sea[j, i]:
            return j, i
        for r in range(1, max(self.nlat, self.nlon)):
            jj = slice(max(0, j - r), min(self.nlat, j + r + 1))
            ii = slice(max(0, i - r), min(self.nlon, i + r + 1))
            sub = self.sea[jj, ii]
            if sub.any():
                js, is_ = np.where(sub)
                js = js + max(0, j - r)
                is_ = is_ + max(0, i - r)
                d = (js - j) ** 2 + (is_ - i) ** 2
                k = int(np.argmin(d))
                return int(js[k]), int(is_[k])
        raise RuntimeError("no sea cell found")

    def astar(self, a, b):
        ja, ia = self._nearest_sea(a[1], a[0])
        jb, ib = self._nearest_sea(b[1], b[0])
        start, goal = (ja, ia), (jb, ib)
        nbrs = [(-1, 0), (1, 0), (0, -1), (0, 1),
                (-1, -1), (-1, 1), (1, -1), (1, 1)]

        def h(j, i):
            return math.hypot(j - jb, i - ib)

        openq = [(h(*start), 0.0, start)]
        came = {start: None}
        gscore = {start: 0.0}
        while openq:
            _, g, cur = heapq.heappop(openq)
            if cur == goal:
                break
            cj, ci = cur
            for dj, di in nbrs:
                nj, ni = cj + dj, ci + di
                if not (0 <= nj < self.nlat and 0 <= ni < self.nlon):
                    continue
                if not self.sea[nj, ni]:
                    continue
                ng = g + math.hypot(dj, di)
                nn = (nj, ni)
                if ng < gscore.get(nn, float("inf")):
                    gscore[nn] = ng
                    came[nn] = cur
                    heapq.heappush(openq, (ng + h(nj, ni), ng, nn))
        if goal not in came:
            return [a, b]
        path = []
        node = goal
        while node is not None:
            j, i = node
            path.append((self.lats[j], self.lons[i]))
            node = came[node]
        path.reverse()
        return path

    def route(self, wps):
        blocked = LAND_UNION.buffer(0.0)
        out = [wps[0]]
        for a, b in zip(wps[:-1], wps[1:]):
            seg = LineString([(a[1], a[0]), (b[1], b[0])])
            if not blocked.intersects(seg):
                out.append(b)
                continue
            sub = self.astar(a, b)
            simp = LineString([(p[1], p[0]) for p in sub]).simplify(self.step * 1.2)
            if not LAND_UNION.intersects(simp):
                sub = [(y, x) for (x, y) in simp.coords]
            out.extend(sub[1:])
            if out[-1] != b:
                out.append(b)
        return out


# --- Build the sea-respecting track and its cell band -----------------------
grid = SeaGrid(EXTENT, 0.10, 0.05)
track = clip_to_sea(grid.route(ROUTE1))

# 0.5 deg cells the track passes through
samp = []
for a, b in zip(track[:-1], track[1:]):
    n = max(1, int(math.hypot(a[0] - b[0], a[1] - b[1]) / 0.05))
    for t in range(n + 1):
        f = t / n
        samp.append((a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f))
cells = sorted({(floor(lo / CELL), floor(la / CELL)) for la, lo in samp})

# --- Plot -------------------------------------------------------------------
fig = plt.figure(figsize=(8.0, 4.4))
ax = plt.axes(projection=ccrs.PlateCarree())
ax.set_extent(EXTENT, crs=ccrs.PlateCarree())
ax.set_facecolor(SEA)
ax.add_feature(cfeature.LAND.with_scale("10m"), facecolor=LAND, zorder=1, rasterized=True)
ax.add_feature(cfeature.COASTLINE.with_scale("10m"), linewidth=0.4,
               edgecolor="#555555", zorder=2, rasterized=True)

# Shaded 0.5 deg cell band (the geographic cells / subsegments)
for ci, cj in cells:
    ax.add_patch(plt.Rectangle((ci * CELL, cj * CELL), CELL, CELL,
                               transform=ccrs.PlateCarree(), facecolor=CELL_FILL,
                               edgecolor=CELL_EDGE, lw=0.25, alpha=0.5, zorder=3))

# Route track
ax.plot([p[1] for p in track], [p[0] for p in track], "-", color=TRACK,
        linewidth=1.6, transform=ccrs.PlateCarree(), zorder=5)

# Heading-change waypoints (interior), navy down-triangles
ax.plot([w[1] for w in ROUTE1[1:-1]], [w[0] for w in ROUTE1[1:-1]], "v",
        color=NAVY, markersize=6, markeredgecolor="white", markeredgewidth=0.6,
        transform=ccrs.PlateCarree(), zorder=6, linestyle="none")

# Start / end
for (la, lo), lab, dx, dy, ha in [
    (ROUTE1[0], "Port A — start", 0.7, 1.0, "left"),
    (ROUTE1[-1], "Port B — end", 0.7, -1.6, "left"),
]:
    ax.plot(lo, la, "o", color="black", markersize=5,
            transform=ccrs.PlateCarree(), zorder=7)
    ax.text(lo + dx, la + dy, lab, fontsize=8, transform=ccrs.PlateCarree(),
            ha=ha, va="center", zorder=8,
            bbox=dict(boxstyle="round,pad=0.15", fc="white", ec="none", alpha=0.8))

gl = ax.gridlines(draw_labels=True, linewidth=0.3, color="gray", alpha=0.4, linestyle=":")
gl.top_labels = False
gl.right_labels = False
gl.xlabel_style = {"size": 7}
gl.ylabel_style = {"size": 7}
ax.set_title("Route 1 over its 0.5$\\degree$ weather cells "
             "(spatial companion to the time--distance state space)",
             fontsize=9.5, pad=6)

ax.legend(handles=[
    Line2D([0], [0], color=TRACK, lw=1.6, label="route"),
    Line2D([0], [0], marker="o", color="black", lw=0, markersize=6, label="start / end (Port A / B)"),
    Line2D([0], [0], marker="v", color=NAVY, lw=0, markersize=7,
           markeredgecolor="white", label="heading change (course $\\psi$)"),
    Patch(facecolor=CELL_FILL, edgecolor=CELL_EDGE, alpha=0.6,
          label="0.5$\\degree$ weather cell (subsegment)"),
], loc="lower left", fontsize=7.5, frameon=True, framealpha=0.95)

fig.savefig("route_state_space.pdf", dpi=300, bbox_inches="tight", pad_inches=0.02)
fig.savefig("route_state_space.png", dpi=200, bbox_inches="tight", pad_inches=0.02)
print(f"wrote route_state_space.pdf and route_state_space.png ({len(cells)} cells along route)")

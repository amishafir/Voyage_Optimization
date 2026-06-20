"""
Generate the two study-route maps for the paper (Figure: fig:routes).

Produces a single compact, two-panel figure (routes.pdf):
  (a) Route 1 — Persian Gulf -> Strait of Malacca
  (b) Route 2 — St. John's   -> Liverpool (North Atlantic)

Waypoints are taken verbatim from the route definitions in
pipeline/config/routes/{persian_gulf_malacca,st_johns_liverpool}.yaml.

The straight rhumb segments between the (sparse) study waypoints cut across
land in several places (Oman/Musandam, southern India, Sri Lanka, Sumatra).
For a clean map we draw a *sea-respecting* track between the same waypoints:
each segment that would cross land is rerouted around it by an A* shortest path
over a sea grid built from the 10 m Natural Earth land polygons. Waypoints are
unchanged; only the connecting lines bend to stay in water.

Run:  python3 make_route_maps.py
"""

import heapq
import math

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import cartopy.crs as ccrs
import cartopy.feature as cfeature
import cartopy.io.shapereader as shpreader
import shapely
from shapely.geometry import LineString, Point
from shapely.ops import unary_union
from shapely.prepared import prep

# --- Waypoints (lat, lon) ---------------------------------------------------
ROUTE1 = [  # Persian Gulf -> Strait of Malacca
    (24.75, 52.83), (26.55, 56.45), (24.08, 60.88), (21.73, 65.73),
    (17.96, 69.19), (14.18, 72.07), (10.45, 75.16), (7.00, 78.46),
    (5.64, 82.12), (4.54, 87.04), (5.20, 92.27), (5.64, 97.16),
    (1.81, 100.10),
]
ROUTE2 = [  # St. John's -> Liverpool
    (47.57, -52.71), (48.80, -47.50), (50.40, -41.00), (52.00, -34.00),
    (53.30, -26.50), (54.20, -18.50), (55.50, -11.00), (55.80, -7.00),
    (55.20, -5.20), (54.20, -3.80), (53.41, -3.01),
]

#       title, waypoints, extent (lon0,lon1,lat0,lat1), start lbl, end lbl,
#       grid step (deg), coast clearance (deg)
PANELS = [
    ("(a) Route 1: Persian Gulf $\\rightarrow$ Strait of Malacca",
     ROUTE1, (48, 103, -2, 30), "Port A", "Port B", 0.10, 0.05),
    ("(b) Route 2: St. John's $\\rightarrow$ Liverpool",
     ROUTE2, (-57, 2, 44, 59), "St. John's", "Liverpool", 0.08, 0.03),
]

LAND = "#e8e3d8"
SEA = "#dce9f2"
TRACK = "#b2182b"

# --- Land geometry (10 m) ---------------------------------------------------
_land_geoms = list(shpreader.Reader(shpreader.natural_earth(
    resolution="10m", category="physical", name="land")).geometries())
LAND_UNION = unary_union(_land_geoms)
PREP_LAND = prep(LAND_UNION)


def clip_to_sea(track, dstep=0.05):
    """Drop the leading/trailing on-land stabs from an ordered (lat,lon) track.

    The route interior is routed around land already; the only land touches are
    the hops from the last sea point into the port coordinates (some study ports
    sit slightly inland). Densify, keep the in-water points in order, so the
    track terminates at each port's nearest coast. Order is preserved, so the
    first/last kept points are the start/end landings."""
    pts = []
    for a, b in zip(track[:-1], track[1:]):
        n = max(1, int(math.hypot(a[0] - b[0], a[1] - b[1]) / dstep))
        for t in range(n):
            f = t / n
            pts.append((a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f))
    pts.append(track[-1])
    return [p for p in pts if not PREP_LAND.contains(Point(p[1], p[0]))]


# --- Sea-respecting router --------------------------------------------------

class SeaGrid:
    """Boolean sea mask over a panel extent + A* routing between lon/lat points."""

    def __init__(self, extent, step, clearance):
        lon0, lon1, lat0, lat1 = extent
        # Pad the routing box a little beyond the drawn extent so detours can
        # bow outside the visible frame if needed.
        pad = 1.0
        self.lons = np.arange(lon0 - pad, lon1 + pad + 1e-9, step)
        self.lats = np.arange(lat0 - pad, lat1 + pad + 1e-9, step)
        self.step = step
        gx, gy = np.meshgrid(self.lons, self.lats)  # [nlat, nlon]
        blocked = LAND_UNION.buffer(clearance)
        # sea = NOT within buffered land
        self.sea = ~shapely.contains_xy(blocked, gx, gy)
        self.nlat, self.nlon = self.sea.shape

    def _nearest_sea(self, lon, lat):
        i = int(round((lon - self.lons[0]) / self.step))
        j = int(round((lat - self.lats[0]) / self.step))
        i = min(max(i, 0), self.nlon - 1)
        j = min(max(j, 0), self.nlat - 1)
        if self.sea[j, i]:
            return j, i
        # spiral outward to the closest sea cell
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
        """a, b are (lat, lon). Returns list of (lat, lon) along a sea path."""
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
                step_cost = math.hypot(dj, di)
                ng = g + step_cost
                nn = (nj, ni)
                if ng < gscore.get(nn, float("inf")):
                    gscore[nn] = ng
                    came[nn] = cur
                    heapq.heappush(openq, (ng + h(nj, ni), ng, nn))
        if goal not in came:
            return [a, b]  # fallback: straight
        # reconstruct
        path = []
        node = goal
        while node is not None:
            j, i = node
            path.append((self.lats[j], self.lons[i]))
            node = came[node]
        path.reverse()
        return path

    def route(self, wps):
        """Full sea-respecting polyline through wps (list of (lat, lon))."""
        blocked = LAND_UNION.buffer(0.0)  # exact land for the crossing test
        out = [wps[0]]
        for a, b in zip(wps[:-1], wps[1:]):
            seg = LineString([(a[1], a[0]), (b[1], b[0])])
            if not blocked.intersects(seg):
                out.append(b)
                continue
            sub = self.astar(a, b)
            # simplify the blocky grid path, then verify it still avoids land
            simp = LineString([(p[1], p[0]) for p in sub]).simplify(self.step * 1.2)
            if not LAND_UNION.intersects(simp):
                sub = [(y, x) for (x, y) in simp.coords]
            # append, dropping the duplicated first point (== a / last out)
            out.extend(sub[1:])
            if out[-1] != b:
                out.append(b)
        return out


# --- Plot -------------------------------------------------------------------

fig, axes = plt.subplots(
    1, 2, figsize=(7.0, 2.7),
    subplot_kw={"projection": ccrs.PlateCarree()},
)

for ax, (title, wps, extent, start, end, step, clr) in zip(axes, PANELS):
    ax.set_extent(extent, crs=ccrs.PlateCarree())
    ax.set_facecolor(SEA)
    # Rasterise the heavy 10 m land/coastline vectors (keeps PDF small); the
    # track line, markers and text stay vector.
    ax.add_feature(cfeature.LAND.with_scale("10m"), facecolor=LAND, zorder=1,
                   rasterized=True)
    ax.add_feature(cfeature.COASTLINE.with_scale("10m"), linewidth=0.4,
                   edgecolor="#555555", zorder=2, rasterized=True)

    grid = SeaGrid(extent, step, clr)
    track = grid.route(wps)

    # Clip leading/trailing on-land stabs so the track terminates at each port's
    # coast; interior is already routed around land.
    cl = clip_to_sea(track)  # ordered (lat, lon), in water
    start_pt = cl[0]
    end_pt = cl[-1]

    # Tolerance ~0.03 deg (~2 nm) absorbs the harbour-mouth approach at ports
    # whose coordinate sits right on the coast; open-water crossings are >>this.
    on_land = LineString([(p[1], p[0]) for p in cl]).intersection(LAND_UNION).length
    status = "PASS" if on_land < 0.03 else f"FAIL ({on_land:.3f} deg)"
    print(f"  {title[:26]:26s} land-crossing check: {status} (on-land {on_land:.4f} deg)")

    tlons = [p[1] for p in cl]
    tlats = [p[0] for p in cl]
    ax.plot(tlons, tlats, "-", color=TRACK, linewidth=1.3,
            transform=ccrs.PlateCarree(), zorder=4)

    # Intermediate waypoints (all in water) as small dots.
    ax.plot([w[1] for w in wps[1:-1]], [w[0] for w in wps[1:-1]], "o",
            color=TRACK, markersize=2.2, transform=ccrs.PlateCarree(), zorder=5)
    for (la, lo), lab, dx, dy, ha in [
        (start_pt, start, 0.5, 0.8, "left"),
        (end_pt, end, 0.5, -1.4, "left"),
    ]:
        ax.plot(lo, la, "o", color="black", markersize=3.4,
                transform=ccrs.PlateCarree(), zorder=6)
        ax.text(lo + dx, la + dy, lab, fontsize=6.0, transform=ccrs.PlateCarree(),
                ha=ha, va="center", zorder=7,
                bbox=dict(boxstyle="round,pad=0.12", fc="white", ec="none",
                          alpha=0.7))

    gl = ax.gridlines(draw_labels=True, linewidth=0.3, color="gray",
                      alpha=0.4, linestyle=":")
    gl.top_labels = False
    gl.right_labels = False
    gl.xlabel_style = {"size": 5.5}
    gl.ylabel_style = {"size": 5.5}
    ax.set_title(title, fontsize=7.0, pad=3)

fig.subplots_adjust(left=0.04, right=0.99, bottom=0.08, top=0.90, wspace=0.12)
fig.savefig("routes.pdf", dpi=300, bbox_inches="tight", pad_inches=0.02)
fig.savefig("routes.png", dpi=200, bbox_inches="tight", pad_inches=0.02)
print("wrote routes.pdf and routes.png")

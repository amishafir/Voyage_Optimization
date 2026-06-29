"""
Shared sea-respecting router + land geometry for the route-map figures.

Importable with NO side effects (no plotting at module load). Used by
plot_route_state_space.py and plot_route_cells_zoom.py.

Provides:
  LAND_UNION, PREP_LAND  -- Natural Earth 10 m land geometry (union + prepared)
  clip_to_sea(track)     -- drop leading/trailing on-land stabs from a track
  SeaGrid(extent, step, clearance) -- boolean sea mask + A* routing between
                                      (lat, lon) points, .route(waypoints)
"""

import heapq
import math

import numpy as np
import cartopy.io.shapereader as shpreader
import shapely
from shapely.geometry import LineString, Point
from shapely.ops import unary_union
from shapely.prepared import prep

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

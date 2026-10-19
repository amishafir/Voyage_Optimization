"""Check route legs against the Natural Earth 1:10m land (and minor islands).

    python3 -I landcheck.py PYLIB NE_DIR PIPELINE_DIR route.yaml [route.yaml ...]

For every leg of the trimmed route (2 NM cut at both ends, as the collector does):
length, NM inside land, and the minimum clearance to land with where it occurs.
"""
import math
import sys
import warnings

warnings.filterwarnings("ignore")

pylib, ne_dir, pipeline = sys.argv[1:4]
sys.path[:0] = ([] if pylib == "-" else [pylib]) + [pipeline]
import shapefile                     # pyshp
import yaml
from shapely.geometry import LineString, Point, shape
from shapely.ops import transform
from shapely.strtree import STRtree
from shapely.prepared import prep

from shared.rhumb import RhumbLeg
from shared.subsegments import trim_route

polys = []
for name in ("ne_10m_land/ne_10m_land", "ne_10m_minor_islands/ne_10m_minor_islands"):
    for s in shapefile.Reader(f"{ne_dir}/{name}").shapes():
        g = shape(s.__geo_interface__)
        polys.extend(getattr(g, "geoms", [g]))
tree = STRtree(polys)


def leg_points(leg, step_nm):
    n = max(2, int(math.ceil(leg.length_nm / step_nm)) + 1)
    return [leg.point_at(i / (n - 1)) for i in range(n)]


def check(path, step_nm=0.05):
    with open(path) as f:
        cfg = yaml.safe_load(f)
    wps = cfg["waypoints"]
    names = [w.get("name", "") for w in wps]
    pts = trim_route(wps, 2.0, 2.0)
    print(f"== {cfg['name']}  ({path})")
    total = 0.0
    worst = []
    for i, (a, b) in enumerate(zip(pts, pts[1:])):
        leg = RhumbLeg(*a, *b)
        total += leg.length_nm
        p = leg_points(leg, step_nm)
        line = LineString([(lon, lat) for lat, lon in p])
        near = [polys[j] for j in tree.query(line.buffer(0.6))]
        inside = 0
        for lat, lon in p:
            q = Point(lon, lat)
            if any(g.contains(q) for g in near):
                inside += 1
        lat0 = 0.5 * (a[0] + b[0])
        k = math.cos(math.radians(lat0))
        proj = lambda x, y, z=None: (x * 60.0 * k, y * 60.0)
        line_nm = transform(proj, line)
        clear, where = float("inf"), None
        for g in near:
            gn = transform(proj, g)
            d = line_nm.distance(gn)
            if d < clear:
                clear = d
                # the closest leg point
                best = min(p, key=lambda ll: transform(proj, Point(ll[1], ll[0])).distance(gn))
                where = best
        nm_inside = inside * leg.length_nm / max(1, len(p) - 1)
        tag = "CROSSES LAND" if inside else ""
        frm = names[i] if i < len(names) else ""
        to = names[i + 1] if i + 1 < len(names) else ""
        cl = f"{clear:6.2f} NM at ({where[0]:.3f}, {where[1]:.3f})" if where else "  >30 NM"
        print(f"  leg {i:2d} {frm[:24]:24s} -> {to[:24]:24s} {leg.length_nm:7.1f} NM  clearance {cl}  "
              f"{tag + f' ({nm_inside:.2f} NM inside)' if inside else ''}")
        worst.append((inside, clear, i))
    print(f"  total {total:.1f} NM (after the 2 NM trims); legs crossing land: "
          f"{sum(1 for w in worst if w[0])}")


for path in sys.argv[4:]:
    check(path)

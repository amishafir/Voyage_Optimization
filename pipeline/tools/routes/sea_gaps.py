"""Sea intervals along a parallel or meridian: python3 -I sea_gaps.py PYLIB NE_DIR lat|lon VALUE FROM TO"""
import sys, math, warnings
warnings.filterwarnings("ignore")
pylib, ne_dir, kind, val, a, b = sys.argv[1:7]
if pylib != "-":
    sys.path.insert(0, pylib)
import shapefile
from shapely.geometry import LineString, shape
from shapely.strtree import STRtree
val, a, b = float(val), float(a), float(b)
polys = []
for name in ("ne_10m_land/ne_10m_land", "ne_10m_minor_islands/ne_10m_minor_islands"):
    for s in shapefile.Reader(f"{ne_dir}/{name}").shapes():
        g = shape(s.__geo_interface__); polys.extend(getattr(g, "geoms", [g]))
tree = STRtree(polys)
line = LineString([(a, val), (b, val)]) if kind == "lat" else LineString([(val, a), (val, b)])
sea = line
for j in tree.query(line):
    sea = sea.difference(polys[j])
parts = getattr(sea, "geoms", [sea])
k = math.cos(math.radians(val)) if kind == "lat" else 1.0
for p in sorted(parts, key=lambda p: p.bounds[0] if kind == "lat" else p.bounds[1]):
    if p.is_empty: continue
    lo, hi = (p.bounds[0], p.bounds[2]) if kind == "lat" else (p.bounds[1], p.bounds[3])
    print(f"  sea {lo:9.4f} .. {hi:9.4f}  ({(hi - lo) * 60 * k:6.1f} NM)  centre {0.5 * (lo + hi):.4f}")

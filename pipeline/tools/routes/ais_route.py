"""Trace a route along the densest AIS (commercial) traffic that is at most --detour longer
than the shortest sea route, then thin it to rhumb-line waypoints.

    python3 -I ais_route.py PYLIB NE_DIR CUTOUT.npz OUT_PREFIX "LAT,LON" "LAT,LON"
        [--via "LAT,LON;..."] [--detour 0.05] [--tol 2.0]

Lane score of a cell: rel = clip((Lmax - L) / delta, 0, 1), L = log10(AIS positions + 1), Lmax
the largest L within --window NM (local normalization: terrestrial receivers near the coast
log far more messages than satellites offshore). Cost per NM = 1 + beta * rel. For each segment
between consecutive stops, beta is the largest value (bisection) whose cheapest path is at
most (1 + detour) times the shortest sea path. Land (Natural Earth 1:10m land and minor
islands, cell centres) is impassable. Douglas-Peucker in Mercator (rhumb lines straight)
then keeps every leg within --tol NM of the traced path and --clear NM off land.
"""
import argparse
import json
import math
import sys
import warnings

warnings.filterwarnings("ignore")
ap = argparse.ArgumentParser()
for a in ("pylib", "ne_dir", "cutout", "out", "start", "end"):
    ap.add_argument(a)
ap.add_argument("--via", default="")
ap.add_argument("--detour", type=float, default=0.05)
ap.add_argument("--beta-max", type=float, default=20.0)
ap.add_argument("--window", type=float, default=30.0)
ap.add_argument("--delta", type=float, default=2.0)
ap.add_argument("--tol", type=float, default=1.5, help="simplification tolerance near land [NM]")
ap.add_argument("--tol-far", type=float, default=6.0, help="tolerance far from land [NM]; in between, distance to land / 4")
ap.add_argument("--clear", type=float, default=0.3)
ap.add_argument("--offshore", default="", help="segments where cells within --offshore-nm of land count "
                "as off-lane (lane score 1), except within --exempt-nm of the segment's ends")
ap.add_argument("--offshore-nm", type=float, default=20.0)
ap.add_argument("--exempt-nm", type=float, default=25.0)
args = ap.parse_args()
if args.pylib != "-":
    sys.path.insert(0, args.pylib)

import numpy as np
import shapefile
import shapely
from shapely.geometry import LineString, shape
from shapely.strtree import STRtree
from scipy.ndimage import maximum_filter
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import dijkstra

z = np.load(args.cutout)
dens, lat, lon, cd = z["density"].astype(float), z["lat"], z["lon"], float(z["cell_deg"])
H, W = dens.shape
polys = []
for name in ("ne_10m_land/ne_10m_land", "ne_10m_minor_islands/ne_10m_minor_islands"):
    for s in shapefile.Reader(f"{args.ne_dir}/{name}").shapes():
        g = shape(s.__geo_interface__)
        polys.extend(getattr(g, "geoms", [g]))
bbox = shapely.box(lon[0] - 1, lat[-1] - 1, lon[-1] + 1, lat[0] + 1)
polys = [p for p in polys if p.intersects(bbox)]
LON, LAT = np.meshgrid(lon, lat)
land = shapely.contains_xy(shapely.union_all(polys), LON.ravel(), LAT.ravel()).reshape(H, W)
sea = ~land

L = np.log10(dens + 1.0)
L[land] = 0.0
rad = max(1, int(round(args.window / (60.0 * cd))))
yy, xx = np.mgrid[-rad:rad + 1, -rad:rad + 1]
Lmax = maximum_filter(L, footprint=(yy ** 2 + xx ** 2) <= rad ** 2, mode="nearest")
rel = np.clip((Lmax - L) / args.delta, 0.0, 1.0)

idx = -np.ones((H, W), dtype=np.int64)
idx[sea] = np.arange(sea.sum())
n = int(sea.sum())
inv = np.argwhere(sea)
E_src, E_dst, E_len, E_rel = [], [], [], []
for di, dj in ((0, 1), (1, 0), (1, 1), (1, -1)):
    i0, i1 = max(0, -di), H - max(0, di)
    j0, j1 = max(0, -dj), W - max(0, dj)
    src = (slice(i0, i1), slice(j0, j1)); dst = (slice(i0 + di, i1 + di), slice(j0 + dj, j1 + dj))
    ok = sea[src] & sea[dst]
    if di and dj:      # no diagonal step past a land corner
        ok &= sea[(slice(i0 + di, i1 + di), slice(j0, j1))] & sea[(slice(i0, i1), slice(j0 + dj, j1 + dj))]
    la = 0.5 * (LAT[src] + LAT[dst])
    step = 60.0 * cd * np.sqrt(di ** 2 + (dj * np.cos(np.radians(la))) ** 2)
    E_src.append(idx[src][ok]); E_dst.append(idx[dst][ok]); E_len.append(step[ok])
    E_rel.append(0.5 * (rel[src] + rel[dst])[ok])
E_src = np.concatenate(E_src); E_dst = np.concatenate(E_dst)
E_len = np.concatenate(E_len); E_rel = np.concatenate(E_rel)
RS, CS = np.concatenate([E_src, E_dst]), np.concatenate([E_dst, E_src])


from scipy.ndimage import distance_transform_edt
mid_cos = math.cos(math.radians(0.5 * (lat[0] + lat[-1])))
dland = distance_transform_edt(sea, sampling=(60 * cd, 60 * cd * mid_cos))   # NM to land
E_near = None


def graph(beta, erel=None):
    w = E_len * (1.0 + beta * (E_rel if erel is None else erel))
    return coo_matrix((np.concatenate([w, w]), (RS, CS)), shape=(n, n)).tocsr()


def nearest_sea(p):
    la, lo = p
    d2 = ((LAT - la) * 60) ** 2 + ((LON - lo) * 60 * math.cos(math.radians(la))) ** 2
    d2[~sea] = np.inf
    i, j = np.unravel_index(np.argmin(d2), d2.shape)
    return int(idx[i, j]), math.sqrt(d2[i, j])


def path_cells(Gm, a, b):
    dist, pred = dijkstra(Gm, indices=a, return_predecessors=True)
    if not np.isfinite(dist[b]):
        sys.exit("no sea path")
    p = [b]
    while p[-1] != a:
        p.append(pred[p[-1]])
    return p[::-1]


def geo_len(p):
    ij = inv[p]
    la, lo = lat[ij[:, 0]], lon[ij[:, 1]]
    return float(np.sum(np.hypot(np.diff(la) * 60, np.diff(lo) * 60 * np.cos(np.radians(0.5 * (la[1:] + la[:-1]))))))


s_lat, s_lon = map(float, args.start.split(","))
e_lat, e_lon = map(float, args.end.split(","))
stops = [(s_lat, s_lon)] + [tuple(map(float, v.split(","))) for v in args.via.split(";") if v] + [(e_lat, e_lon)]
G0 = graph(0.0)
cells, seg_starts, report = [], [], []
cache = {}
offshore = {int(q) for q in args.offshore.split(",") if q}
for k, (a, b) in enumerate(zip(stops, stops[1:])):
    ai, ad = nearest_sea(a)
    bi, bd = nearest_sea(b)
    erel = None
    if k in offshore:
        ends = np.zeros((H, W), bool)
        for la_, lo_ in (a, b):
            ends |= ((LAT - la_) * 60) ** 2 + ((LON - lo_) * 60 * math.cos(math.radians(la_))) ** 2 <= args.exempt_nm ** 2
        rel_k = np.where((dland < args.offshore_nm) & ~ends, 1.0, rel)
        erel = np.concatenate([0.5 * (rel_k[tuple(inv[E_src].T)] + rel_k[tuple(inv[E_dst].T)])])
    p0 = path_cells(G0, ai, bi)
    L0 = geo_len(p0)
    lo_b, hi_b, best = 0.0, args.beta_max, (0.0, p0, L0)
    pb = path_cells(graph(hi_b, erel), ai, bi)
    if geo_len(pb) <= (1 + args.detour) * L0:
        best = (hi_b, pb, geo_len(pb))
    else:
        for _ in range(10):
            mid = 0.5 * (lo_b + hi_b)
            pm = path_cells(graph(mid, erel), ai, bi)
            Lm = geo_len(pm)
            if Lm <= (1 + args.detour) * L0:
                lo_b, best = mid, (mid, pm, Lm)
            else:
                hi_b = mid
    beta, p, Lp = best
    lane0 = float(np.mean(rel[tuple(inv[p0].T)]))
    lane = float(np.mean(rel[tuple(inv[p].T)]))
    report.append(f"segment {k}: shortest {L0:.1f} NM (mean lane score {lane0:.2f}), traced {Lp:.1f} NM "
                  f"(+{100 * (Lp / L0 - 1):.1f}%, beta {beta:.2f}, mean lane score {lane:.2f}; 0 = on a lane)")
    seg = [tuple(inv[q]) for q in p]
    if cells:
        seg = seg[1:]
    seg_starts.append(len(cells))
    cells.extend(seg)
pts = [(s_lat, s_lon)] + [(float(lat[i]), float(lon[j])) for i, j in cells] + [(e_lat, e_lon)]
via_pts = [1 + q for q in seg_starts[1:]]


def psi(la):
    return math.degrees(math.log(math.tan(math.radians(45 + la / 2))))


tree = STRtree(polys)
P = np.array([(lo, psi(la)) for la, lo in pts])
LATS = np.array([la for la, _ in pts])
DL = np.array([float(dland[i, j]) for i, j in cells])
TOL = np.concatenate([[args.tol], np.clip(DL / 4.0, args.tol, args.tol_far), [args.tol]])


def rhumb_samples(a, b, step_nm=0.05):
    (la1, lo1), (la2, lo2) = a, b
    n_ = max(2, int(math.hypot((la2 - la1) * 60, (lo2 - lo1) * 60 * math.cos(math.radians(0.5 * (la1 + la2)))) / step_nm) + 1)
    y1, y2 = psi(la1), psi(la2)
    out = []
    for k in range(n_):
        f = k / (n_ - 1)
        la = la1 + f * (la2 - la1)
        lo = lo1 + f * (lo2 - lo1) if abs(y2 - y1) < 1e-12 else lo1 + (psi(la) - y1) / (y2 - y1) * (lo2 - lo1)
        out.append((lo, la))
    return out


def leg_ok(a, b):
    line = LineString(rhumb_samples(pts[a], pts[b]))
    kmid = math.cos(math.radians(0.5 * (pts[a][0] + pts[b][0])))
    buf = line.buffer(args.clear / 60.0 / max(kmid, 0.3))
    geom = line if (a == 0 or b == len(pts) - 1) else buf     # harbour approaches only stay off land
    return not any(polys[j].intersects(geom) for j in tree.query(geom))


def dev_nm(a, b):
    if b - a < 2:
        return 0.0, None
    A, B = P[a], P[b]
    AB = B - A
    L2 = float(AB @ AB) or 1e-18
    Q = P[a + 1:b]
    t = np.clip(((Q - A) @ AB) / L2, 0, 1)
    d = np.hypot(*(Q - (A + t[:, None] * AB)).T) * 60 * np.cos(np.radians(LATS[a + 1:b]))
    k = int(np.argmax(d / TOL[a + 1:b]))
    return float(d[k] / TOL[a + 1 + k]), a + 1 + k


def simplify(a, b):
    d, k = dev_nm(a, b)          # deviation in units of the local tolerance
    if k is not None and (d > 1.0 or not leg_ok(a, b)):
        return simplify(a, k)[:-1] + simplify(k, b)
    if k is None and not leg_ok(a, b):
        print(f"WARNING: the step from {pts[a]} to {pts[b]} touches land and cannot be split")
    return [a, b]


bounds = [0] + via_pts + [len(pts) - 1]
keep = [0]
for a, b in zip(bounds, bounds[1:]):
    keep += simplify(a, b)[1:]
wps = [pts[k] for k in keep]
route_len = sum(math.hypot((b[0] - a[0]) * 60, (b[1] - a[1]) * 60 * math.cos(math.radians(0.5 * (a[0] + b[0]))))
                for a, b in zip(wps, wps[1:]))
for line in report:
    print(line)
print(f"{len(wps)} waypoints (tolerance {args.tol} NM near land, up to {args.tol_far} NM offshore), route {route_len:.1f} NM")
json.dump({"waypoints": wps, "traced": pts, "stops": stops, "detour": args.detour, "tol": args.tol,
           "report": report}, open(args.out + ".json", "w"))

from PIL import Image, ImageDraw
img = (255 * (1.0 - rel)).astype(np.uint8)
rgb = np.stack([img, img, img], axis=-1)
rgb[land] = (90, 70, 50)
im = Image.fromarray(rgb, "RGB")
dr = ImageDraw.Draw(im)
xy = lambda la, lo: ((lo - lon[0]) / cd, (lat[0] - la) / cd)
dr.line([xy(la, lo) for la, lo in pts], fill=(0, 160, 255), width=1)
dr.line([xy(la, lo) for la, lo in wps], fill=(255, 40, 40), width=1)
for la, lo in wps:
    x, y = xy(la, lo)
    dr.ellipse([x - 2, y - 2, x + 2, y + 2], outline=(255, 220, 0))
im.save(args.out + ".png")

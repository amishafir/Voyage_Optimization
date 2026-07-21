"""
Fused single-image voyage figure (design "A" — the unrolled ribbon).

ONE image, ONE shared horizontal axis = along-track distance d, that fuses all
four ingredients of the problem:

  * geography  — a slim "ribbon" on TOP: the route unrolled left->right by
                 distance (y = latitude), so every geographic point sits exactly
                 above its distance on the plane below. A true-north cartopy
                 locator inset keeps orientation.
  * route      — the red track, in both the ribbon and the plane.
  * time/dist  — the plane below: elapsed time runs downward; the slope of the
                 red line IS the speed (flatter = slower).
  * weather    — the plane's background is a sea-state field: every
                 (0.5 deg cell  x  6 h block) rectangle is shaded by wave height.
                 The optimal route threads this field, slowing where it is rough.

The 0.5 deg cell boundaries are the shared vertical SPINE: the same lines run
through the ribbon and the plane, stitching geography (where) to time+weather
(when + how rough). Speed is constant within a cell (re-chosen at each crossing),
so the trajectory kinks at every cell/heading boundary.

Same short Strait-of-Hormuz voyage and the same four numbered points as
combined_twin (Port A, 1 = 6 h block, 2 = heading change, 3 = cell crossing,
4 = 6 h block, Port B).

Weather here is ILLUSTRATIVE (a designed field) — swap for real HDF5 later.

Run:  python3 plot_fused_voyage.py
Out:  fused_voyage.pdf, fused_voyage.png
"""

from math import ceil, floor, cos, radians, hypot

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap, Normalize
import cartopy.crs as ccrs
import cartopy.feature as cfeature

from sea_routing import SeaGrid, clip_to_sea

# ---- voyage (same as combined_twin) ---------------------------------------
WPS = [(25.80, 55.90), (26.50, 56.55), (25.95, 57.20)]
HEADING_WP = (26.50, 56.55)
CELL = 0.5
WINDOW = (55.1, 57.9, 25.0, 27.0)
FULL_ROUTE = [(24.75, 52.83), (26.55, 56.45), (24.08, 60.88), (21.73, 65.73),
              (17.96, 69.19), (14.18, 72.07), (10.45, 75.16), (7.00, 78.46),
              (5.64, 82.12), (4.54, 87.04), (5.20, 92.27), (5.64, 97.16),
              (1.81, 100.10)]
FULL_EXTENT = (49.0, 103.0, -1.0, 30.0)

LAND, SEA, TRACK = "#e8e3d8", "#dce9f2", "#b2182b"
NAVY, CELLC, TIMEC, ARRC = "#0d3b66", "#8a6d1a", "#3a6ea5", "#c62828"
TYPE_COLOR = {"cell": CELLC, "time": TIMEC, "heading": NAVY,
              "start": "black", "arrival": ARRC}

# calm -> rough sea-state colormap (pale blue -> deep slate; the crimson route
# and tan land stay clearly distinct from it).
WX_CMAP = LinearSegmentedColormap.from_list(
    "seastate", ["#eef5fb", "#cfe0f1", "#8fb4d9", "#3f6fa5", "#26456b"])

grid = SeaGrid((53, 60, 23.5, 28), 0.10, 0.05)
track = clip_to_sea(grid.route(WPS))


def nm_between(a, b):
    mlat = radians((a[0] + b[0]) / 2)
    return hypot((b[0] - a[0]) * 60.0, (b[1] - a[1]) * 60.0 * cos(mlat))


cum = [0.0]
for a, b in zip(track[:-1], track[1:]):
    cum.append(cum[-1] + nm_between(a, b))
total_nm = cum[-1]


def pos_at_nm(s):
    for k in range(len(cum) - 1):
        if cum[k] <= s <= cum[k + 1]:
            f = (s - cum[k]) / (cum[k + 1] - cum[k]) if cum[k + 1] > cum[k] else 0.0
            return (track[k][0] + f * (track[k + 1][0] - track[k][0]),
                    track[k][1] + f * (track[k + 1][1] - track[k][1]))
    return track[-1]


def nm_of(la, lo):
    best, bd = 0.0, 1e9
    for k, p in enumerate(track):
        d = (p[0] - la) ** 2 + (p[1] - lo) ** 2
        if d < bd:
            bd, best = d, cum[k]
    return best


# ---- 0.5 deg cell-boundary crossings along the track ----------------------
cell_nms = []
prev_cell = None
for s in np.linspace(0.0, total_nm, 2400):
    la, lo = pos_at_nm(s)
    cij = (floor(la / CELL), floor(lo / CELL))
    if prev_cell is not None and cij != prev_cell:
        if not cell_nms or s - cell_nms[-1] > 1.5:
            cell_nms.append(round(s, 3))
    prev_cell = cij
head_nm = nm_of(*HEADING_WP)

# Pedagogical simplification (matches the kept 4-point voyage): show ONE
# representative cell crossing in segment 2 plus the heading change, rather than
# every 0.5 deg crossing of the real track (which would clutter the concept).
# -> three bands: approach (seg 1) | first seg-2 cell | rough seg-2 cell.
_seg2 = [s for s in cell_nms if s > head_nm + 5.0]
chosen_cell = (min(_seg2, key=lambda s: abs(s - 0.85 * total_nm))
               if _seg2 else 0.85 * total_nm)
dist_events = sorted([round(head_nm, 6), round(chosen_cell, 6)])
boundaries = [0.0] + dist_events + [total_nm]          # band edges (nb+1)
nbands = len(boundaries) - 1

# ---- per-band geography + illustrative weather ----------------------------
band_mid = [(boundaries[i] + boundaries[i + 1]) / 2 for i in range(nbands)]
band_lon = [pos_at_nm(m)[1] for m in band_mid]
# Illustrative sea state: the strait (middle band) is the rough bottleneck, the
# sheltered gulf (approach) is calm, and the eastern water is moderate. This
# both tells a clean story (ship crawls through the rough strait) and keeps the
# 6 h line clear of the cell crossing. Falls back to a west->east ramp if the
# band count ever changes.
if nbands == 3:
    base_wave = [1.0, 1.3, 2.4]     # calm gulf | moderate strait | rough open water
else:
    lo_lo, lo_hi = min(band_lon), max(band_lon)
    base_wave = [1.0 + 1.1 * ((lo - lo_lo) / (lo_hi - lo_lo + 1e-9)) for lo in band_lon]
# and worsens over the voyage (later 6 h blocks rougher) — set after T is known.

# speed is constant within a cell and lower where it is rougher (the DP's
# convexity response). Contrast is exaggerated for legibility so the "slow in
# rough water" leg reads as a clearly steeper (more vertical) segment.
if nbands == 3:
    band_speed = [8.6, 8.1, 5.4]    # fast approach + strait, slow rough leg
else:
    band_speed = [min(9.5, max(5.0, 9.6 - 1.6 * w)) for w in base_wave]

# ---- forward walk: constant speed per band; mark 6 h time-line crossings ---
EPS = 1e-6
d = t = 0.0
bi = 0
next_t = 6.0
verts = [(0.0, 0.0, "start")]
while d < total_nm - EPS and len(verts) < 500:
    while bi < nbands and boundaries[bi + 1] <= d + EPS:
        bi += 1
    v = band_speed[min(bi, nbands - 1)]
    nd = boundaries[min(bi + 1, nbands)]
    dt_d = (nd - d) / v
    dt_t = next_t - t
    if dt_d <= dt_t + 1e-9:                      # a distance line binds
        d, t = nd, t + dt_d
        ty = ("arrival" if abs(nd - total_nm) < EPS
              else "heading" if abs(nd - head_nm) < 1e-4 else "cell")
    else:                                        # a 6 h time line binds
        d, t = d + v * dt_t, next_t
        ty = "time"
        next_t += 6.0
    verts.append((d, t, ty))

bounds = [vv[0] for vv in verts]
seg_t = [vv[1] for vv in verts]
T = seg_t[-1]

# 6 h block edges (last block is the T remainder) + temporal worsening factor
block_edges = list(np.arange(0.0, T, 6.0)) + [T]
nblocks = len(block_edges) - 1
tfac = np.linspace(0.9, 1.25, nblocks)          # later blocks rougher
wave = np.array([[base_wave[i] * tfac[j] for i in range(nbands)]
                 for j in range(nblocks)])       # wave[block, band]

interior = [(dd, tt, ty) for (dd, tt, ty) in verts if ty not in ("start", "arrival")]
numbered = [(i + 1, dd, tt, ty) for i, (dd, tt, ty) in enumerate(interior)]


def time_at_nm(s):
    for i in range(len(bounds) - 1):
        if bounds[i] - EPS <= s <= bounds[i + 1] + EPS:
            span = bounds[i + 1] - bounds[i]
            f = (s - bounds[i]) / span if span > EPS else 0.0
            return seg_t[i] + f * (seg_t[i + 1] - seg_t[i])
    return T


# ---- badge placement -------------------------------------------------------
def badge(ax, x, y, num, c, dx=0.0, dy=0.0):
    if abs(dx) < 1e-9 and abs(dy) < 1e-9:
        ax.text(x, y, str(num), fontsize=8, fontweight="bold", color="white",
                ha="center", va="center", zorder=9,
                bbox=dict(boxstyle="circle,pad=0.22", fc=c, ec="white", lw=1.0))
    else:
        ax.plot([x, x + dx], [y, y + dy], color=c, lw=0.8, zorder=8,
                solid_capstyle="round")
        ax.plot([x], [y], "o", color=c, ms=3.4, mec="white", mew=0.5, zorder=8.5)
        ax.text(x + dx, y + dy, str(num), fontsize=8, fontweight="bold",
                color="white", ha="center", va="center", zorder=9,
                bbox=dict(boxstyle="circle,pad=0.22", fc=c, ec="white", lw=1.0))


# nudges (plane): sign flips because time axis is inverted (up = smaller t)
PLANE_OFF = {1: (0, -1.5), 2: (0, 1.4), 3: (0, -1.5), 4: (0, 1.4)}
RIBBON_OFF = {1: (0, 0.11), 2: (0, 0.11), 3: (0, -0.12), 4: (0, -0.12)}


def make_figure(outname):
    fig = plt.figure(figsize=(12.0, 8.6))
    gs = fig.add_gridspec(2, 2, width_ratios=[1.0, 0.34],
                          height_ratios=[0.68, 1.9], hspace=0.28, wspace=0.03)
    axr = fig.add_subplot(gs[0, 0])                 # ribbon (geography)
    axp = fig.add_subplot(gs[1, 0], sharex=axr)     # plane (time x weather)
    axk = fig.add_subplot(gs[:, 1])                 # key / colorbar

    xlim = (-total_nm * 0.02, total_nm * 1.02)

    # =========================== ribbon (geography) ======================
    lat_min = min(p[0] for p in track)
    lat_max = max(p[0] for p in track)
    pad = 0.10 * (lat_max - lat_min)
    axr.set_facecolor(SEA)
    # alternating faint cell bands (neutral — weather lives in the plane)
    for i in range(nbands):
        axr.axvspan(boundaries[i], boundaries[i + 1],
                    facecolor=("#d7e6f2" if i % 2 else "#e6eef6"),
                    edgecolor="none", zorder=0)
    # faint 0.5 deg latitude reference lines
    for yy in np.arange(floor(lat_min / CELL) * CELL, lat_max + CELL, CELL):
        if lat_min - pad < yy < lat_max + pad:
            axr.axhline(yy, color="#a9c0d6", lw=0.5, ls=(0, (1, 3)), zorder=1)
    # unrolled route (y = latitude) + points
    r_lat = [pos_at_nm(s)[0] for s in np.linspace(0, total_nm, 500)]
    r_d = np.linspace(0, total_nm, 500)
    axr.plot(r_d, r_lat, color=TRACK, lw=2.4, solid_capstyle="round", zorder=6)
    axr.plot(0, pos_at_nm(0)[0], "o", color="black", ms=7, zorder=8)
    axr.plot(total_nm, pos_at_nm(total_nm)[0], "*", color=ARRC, ms=16,
             mec="white", zorder=8)
    for num, s, tt, ty in numbered:
        dx, dy = RIBBON_OFF.get(num, (0, 0))
        badge(axr, s, pos_at_nm(s)[0], num, TYPE_COLOR[ty], dx=dx, dy=dy)
    axr.text(0, pos_at_nm(0)[0] + 0.16, "Port A", fontsize=9, ha="left",
             va="bottom", color="black")
    axr.text(total_nm, pos_at_nm(total_nm)[0] - 0.18, "Port B", fontsize=9,
             ha="right", va="top", color=ARRC)
    axr.set_ylim(lat_min - pad, lat_max + 1.6 * pad)
    axr.set_ylabel("latitude", fontsize=9)
    axr.tick_params(labelbottom=False, labelsize=8)
    for sp in ("top", "right"):
        axr.spines[sp].set_visible(False)
    axr.set_title("(a)  geography: the route unrolled left$\\rightarrow$right "
                  "by along-track distance", loc="left", fontsize=11,
                  fontweight="bold", pad=6)

    # locator inset (real map, for orientation) — top-left, over the empty
    # upper-left of the ribbon (the route is low on the left), so it never
    # occludes the route, its points, or Port B.
    pos = axr.get_position()
    iw, ih = 0.135, 0.62 * pos.height
    axl = fig.add_axes([pos.x0 + 0.010, pos.y1 - ih - 0.004, iw, ih],
                       projection=ccrs.PlateCarree())
    axl.set_extent(FULL_EXTENT, crs=ccrs.PlateCarree())
    axl.set_facecolor(SEA)
    axl.add_feature(cfeature.LAND.with_scale("110m"), facecolor=LAND, zorder=1)
    axl.add_feature(cfeature.COASTLINE.with_scale("110m"), linewidth=0.3,
                    edgecolor="#888888", zorder=2)
    axl.plot([p[1] for p in FULL_ROUTE], [p[0] for p in FULL_ROUTE], "-",
             color=TRACK, lw=1.0, transform=ccrs.PlateCarree(), zorder=3)
    lo0, lo1, la0, la1 = WINDOW
    axl.add_patch(plt.Rectangle((lo0, la0), lo1 - lo0, la1 - la0,
                                transform=ccrs.PlateCarree(), facecolor="none",
                                edgecolor=ARRC, lw=1.2, zorder=4))
    axl.set_title("Gulf $\\rightarrow$ Malacca", fontsize=6, pad=1.5)
    for _s in axl.spines.values():
        _s.set_edgecolor("#888888"); _s.set_linewidth(0.6)

    # =========================== plane (time x weather) ==================
    mesh = axp.pcolormesh(np.array(boundaries), np.array(block_edges), wave,
                          cmap=WX_CMAP, shading="flat", zorder=0,
                          norm=Normalize(vmin=float(wave.min()),
                                         vmax=float(wave.max())))
    # 6 h time lines
    for tt in block_edges[1:-1]:
        axp.axhline(tt, color="#5b6b7a", lw=0.8, ls=(0, (5, 3)), zorder=2)
    # the route: slope = speed
    axp.plot(bounds, seg_t, color=TRACK, lw=2.6, solid_capstyle="round", zorder=5)
    axp.plot(0, 0, "o", color="black", ms=7, zorder=6)
    axp.plot(total_nm, T, "*", color=ARRC, ms=16, mec="white", zorder=6)
    for num, s, tt, ty in numbered:
        dx, dy = PLANE_OFF.get(num, (0, 0))
        badge(axp, s, time_at_nm(s), num, TYPE_COLOR[ty], dx=dx, dy=dy)
    axp.set_xlim(*xlim)
    axp.set_ylim(T * 1.04, -T * 0.04)               # t = 0 at top
    axp.set_xlabel("along-track distance $d$ (nm)   —   vertical lines = 0.5$\\degree$ "
                   "cell / heading boundaries", fontsize=9.5)
    axp.set_ylabel("elapsed time $t$ (h)   —   horizontal lines = 6 h blocks",
                   fontsize=9.5)
    for sp in ("top", "right"):
        axp.spines[sp].set_visible(False)
    axp.set_title("(b)  time $\\times$ distance state space, painted with the "
                  "sea-state field",
                  loc="left", fontsize=11, fontweight="bold", pad=6)

    # =========================== shared spine (cell boundaries) ==========
    for s in dist_events:
        c = NAVY if abs(s - head_nm) < 1e-4 else "#7c8b99"
        lw = 2.0 if abs(s - head_nm) < 1e-4 else 1.0
        ls = "-" if abs(s - head_nm) < 1e-4 else (0, (1, 3))
        axr.axvline(s, color=c, lw=lw, ls=ls, zorder=3)
        axp.axvline(s, color=c, lw=lw, ls=ls, zorder=3)

    # =========================== key + colorbar ==========================
    axk.axis("off")
    axk.set_title("what each point is", loc="left", fontsize=10.5, fontweight="bold")
    items = [("start", "o", "Port A", "departure ($t=0$)"),
             ("time", "1", "6 h block", "weather may change (time)"),
             ("heading", "2", "heading change", "course $\\psi$ (segment end)"),
             ("cell", "3", "cell crossing", "weather changes (0.5$\\degree$, space)"),
             ("time", "4", "6 h block", "weather may change (time)"),
             ("arrival", "*", "Port B", "arrival at the ETA")]
    y = 0.955
    for ty, mk, name, desc in items:
        c = TYPE_COLOR[ty]
        if mk == "o":
            axk.plot(0.07, y, "o", color=c, ms=9, mec="white",
                     transform=axk.transAxes, clip_on=False)
        elif mk == "*":
            axk.plot(0.07, y, "*", color=c, ms=15, mec="white",
                     transform=axk.transAxes, clip_on=False)
        else:
            axk.text(0.07, y, mk, transform=axk.transAxes, fontsize=8,
                     fontweight="bold", color="white", ha="center", va="center",
                     bbox=dict(boxstyle="circle,pad=0.22", fc=c, ec="white", lw=1.0))
        axk.text(0.15, y + 0.007, name, transform=axk.transAxes, fontsize=9.2,
                 fontweight="bold", va="center")
        axk.text(0.15, y - 0.021, desc, transform=axk.transAxes, fontsize=8.0,
                 color="#444", va="center")
        y -= 0.072

    # "slope = speed" mini-ruler. Time runs downward, so slope = time/distance
    # = 1/speed: a flat (near-horizontal) leg is FAST, a steep (near-vertical)
    # leg is SLOW.
    y -= 0.02
    axk.text(0.0, y, "reading the plane (slope $=$ speed)", transform=axk.transAxes,
             fontsize=9.2, fontweight="bold", va="center")
    y -= 0.06
    axk.plot([0.06, 0.24], [y + 0.028, y + 0.024], transform=axk.transAxes,
             color=TRACK, lw=2.6, clip_on=False, solid_capstyle="round")  # flat
    axk.text(0.28, y + 0.026, "flat $=$ fast (calm)", transform=axk.transAxes,
             fontsize=8.4, va="center")
    y -= 0.07
    axk.plot([0.12, 0.18], [y + 0.05, y - 0.005], transform=axk.transAxes,
             color=TRACK, lw=2.6, clip_on=False, solid_capstyle="round")   # steep
    axk.text(0.28, y + 0.022, "steep $=$ slow (rough)", transform=axk.transAxes,
             fontsize=8.4, va="center")

    # colorbar for the sea-state field
    cax = fig.add_axes([axk.get_position().x0 + 0.012, 0.10, 0.022, 0.24])
    cb = fig.colorbar(mesh, cax=cax)
    cb.set_label("wave height $H_s$ (m)\n(pale = calm, deep = rough)", fontsize=8.5)
    cb.ax.tick_params(labelsize=7.5)

    fig.savefig(f"{outname}.pdf", dpi=300, bbox_inches="tight", pad_inches=0.06)
    fig.savefig(f"{outname}.png", dpi=200, bbox_inches="tight", pad_inches=0.06)
    plt.close(fig)
    print(f"wrote {outname}.* — {nbands} bands, {nblocks} blocks, "
          f"{len(numbered)} points, T={T:.1f} h, {total_nm:.0f} nm")
    print(f"  bands (nm): {[round(b,1) for b in boundaries]}")
    print(f"  base_wave : {[round(w,2) for w in base_wave]}")
    print(f"  band_speed: {[round(v,2) for v in band_speed]}")
    print(f"  points    : {[(n, round(s,1), ty) for n,s,_,ty in numbered]}")


if __name__ == "__main__":
    make_figure("fused_voyage")

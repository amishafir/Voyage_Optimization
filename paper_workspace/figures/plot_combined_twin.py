"""
Combined two-panel figure built from ONE real Strait-of-Hormuz voyage:

  (a) geographic map   — the strait route over the 0.5 deg weather cells, with
                         the Musandam peninsula coastline (the "map" look).
  (b) time-distance     — the same voyage as a state-space trajectory; slope =
                         speed, so the zig-zag shows speed changing at each
                         crossing.

Both panels are the SAME voyage, so the numbered points (cell crossings = brown,
6 h blocks = blue, heading change = navy, start/arrival) correspond one-to-one.

Speed varies per cell (constant within a cell, re-chosen at each crossing), which
is what makes (b) zig-zag and what the 6 h-block points are placed against.

Run:  python3 plot_combined_twin.py
Outputs: combined_twin.pdf, combined_twin.png
"""

from math import ceil, floor, cos, radians, hypot

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import cartopy.crs as ccrs
import cartopy.feature as cfeature

from sea_routing import SeaGrid, clip_to_sea

# --- A short voyage localised to the Strait of Hormuz (lat, lon) -----------
WPS = [(25.80, 55.90), (26.50, 56.55), (25.95, 57.20)]   # start, heading change, arrival
HEADING_WP = (26.50, 56.55)
CELL = 0.5
WINDOW = (55.1, 57.9, 25.0, 27.0)

# Full Route 1 (Persian Gulf -> Strait of Malacca) waypoints, for the locator
# inset that shows this zoom is a close-up of the start of a 3,393 nm voyage.
FULL_ROUTE = [(24.75, 52.83), (26.55, 56.45), (24.08, 60.88), (21.73, 65.73),
              (17.96, 69.19), (14.18, 72.07), (10.45, 75.16), (7.00, 78.46),
              (5.64, 82.12), (4.54, 87.04), (5.20, 92.27), (5.64, 97.16),
              (1.81, 100.10)]
FULL_EXTENT = (49.0, 103.0, -1.0, 30.0)

LAND, SEA, TRACK = "#e8e3d8", "#dce9f2", "#b2182b"
NAVY, CELLC, TIMEC, ARRC = "#0d3b66", "#8a6d1a", "#3a6ea5", "#c62828"
TINT = ("#cfe0f1", "#abc9e8")
TYPE_COLOR = {"cell": CELLC, "time": TIMEC, "heading": NAVY, "start": "black", "arrival": ARRC}

grid = SeaGrid((53, 60, 23.5, 28), 0.10, 0.05)
track = clip_to_sea(grid.route(WPS))


# --- cumulative nm along the track ------------------------------------------
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


# --- cell-boundary crossings (0.5 deg) along the track ----------------------
def seg_crossings(a, b):
    out = []
    if abs(b[1] - a[1]) > 1e-12:
        for k in range(ceil(min(a[1], b[1]) / CELL), floor(max(a[1], b[1]) / CELL) + 1):
            t = (k * CELL - a[1]) / (b[1] - a[1])
            if 1e-6 < t < 1 - 1e-6:
                out.append(t)
    if abs(b[0] - a[0]) > 1e-12:
        for k in range(ceil(min(a[0], b[0]) / CELL), floor(max(a[0], b[0]) / CELL) + 1):
            t = (k * CELL - a[0]) / (b[0] - a[0])
            if 1e-6 < t < 1 - 1e-6:
                out.append(t)
    return [(a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1]))
            for t in sorted(set(round(v, 6) for v in out))]


# Cell-boundary crossings: walk the track finely and record every nm where the
# 0.5 deg cell index (floor(lat/0.5), floor(lon/0.5)) changes. Robust to track
# vertex density (unlike snapping each crossing to the nearest vertex). A cell
# corner where a lat and a lon line meet is a single index change -> one point.
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

# --- forward walk: speed may change at EVERY line crossing ------------------
# The vessel holds a speed until it meets the nearer of the next distance line
# (cell crossing or heading) or the next 6 h time line; speed is re-chosen at
# each such crossing. Every trajectory vertex is therefore a numbered decision
# point, and every kink in the line carries a number (matches the adaptive legs
# of the DP). Distance boundaries = cell crossings + the heading waypoint (drop
# a cell crossing that nearly coincides with the heading).
dist_events = sorted(set(round(x, 6) for x in
                         ([head_nm] + [s for s in cell_nms if abs(s - head_nm) > 1.5])))
speed_cycle = [9.0, 6.0, 8.4, 6.4, 7.8, 6.6]   # zig-zag so each leg's speed differs -> visible kinks
EPS = 1e-6

d = t = 0.0
k = di = 0
next_t = 6.0
verts = [(0.0, 0.0, "start")]              # (distance nm, time h, type)
while d < total_nm - EPS and len(verts) < 500:
    v = speed_cycle[k % len(speed_cycle)]
    while di < len(dist_events) and dist_events[di] <= d + EPS:
        di += 1
    nd = dist_events[di] if di < len(dist_events) else total_nm
    dt_d = (nd - d) / v          # time to reach the next distance line
    dt_t = next_t - t            # time to reach the next 6 h line
    if dt_d <= dt_t + 1e-9:      # a distance line binds
        d, t = nd, t + dt_d
        ty = ("arrival" if abs(nd - total_nm) < EPS
              else "heading" if abs(nd - head_nm) < 1e-4 else "cell")
    else:                        # a 6 h time line binds
        d, t = d + v * dt_t, next_t
        ty = "time"
        next_t += 6.0
    verts.append((d, t, ty))
    k += 1

bounds = [vv[0] for vv in verts]
seg_t = [vv[1] for vv in verts]
T = seg_t[-1]
interior = [(dd, tt, ty) for (dd, tt, ty) in verts if ty not in ("start", "arrival")]
numbered = [(i + 1, dd, ty) for i, (dd, tt, ty) in enumerate(interior)]
pt_time = {round(dd, 6): tt for (dd, tt, ty) in interior}

# Badge nudging for clustered points (tuned to this fixed 8-point schematic).
# Sign convention: NEGATIVE = above the line, POSITIVE = below (the panel calls
# flip the sign per axis so "above" is up on screen in both map and plane).
# Points 1, 3, 4 sit above the line; their cluster-mates go below. Magnitudes
# stack co-located badges (e.g. 3 higher than 4). Points not listed sit on the line.
BADGE_OFF = {1: -0.9, 2: 0.9, 3: -1.7, 4: -0.85, 5: 0.9, 6: -0.9, 7: 0.9, 8: -0.8}

# Map panel: explicit per-point badge offsets (dlon east+, dlat north+ = right/up),
# for full left/right + above/below control. 1,3,4 above; 2,5 above-right;
# 6,7,8 below-left. Tuned to this fixed 8-point schematic.
MAP_OFF = {
    1: (-0.10,  0.13),   # above-left
    2: (-0.15,  0.24),   # above-left (lifted clear of the NE-climbing route)
    3: (-0.05,  0.24),   # above
    4: ( 0.05,  0.13),   # above
    5: ( 0.12,  0.12),   # above-right
    6: (-0.13, -0.10),   # below-left
    7: (-0.13, -0.22),   # below-left (staggered below 6)
    8: (-0.11, -0.13),   # below-left (clear of the arrival star)
}


def time_at_nm(s):
    for i in range(len(bounds) - 1):
        if bounds[i] - EPS <= s <= bounds[i + 1] + EPS:
            span = bounds[i + 1] - bounds[i]
            f = (s - bounds[i]) / span if span > EPS else 0.0
            return seg_t[i] + f * (seg_t[i + 1] - seg_t[i])
    return T


# --- per-point descriptions for the key ------------------------------------
def describe(ty, s):
    if ty == "cell":
        return "weather-cell crossing (0.5$\\degree$, space)"
    if ty == "time":
        return f"6 h block, $t={round(pt_time.get(round(s, 6), time_at_nm(s)))}$ h (time)"
    return "heading change at the strait (course $\\psi$)"


def place_numbered(ax, coords, off_x=0.0, off_y=0.0, explicit=None, transform=None):
    """Draw numbered badges. For points that cluster along the route, leave a
    small dot on the line and offset the number badge with a thin leader, so
    badges never overlap. `explicit` (num -> (dx, dy)) gives full 2-D control;
    otherwise the offset is BADGE_OFF[num] * (off_x, off_y)."""
    kw = {} if transform is None else dict(transform=transform)
    for num, x, y, c in coords:
        if explicit is not None:
            dx, dy = explicit.get(num, (0.0, 0.0))
        else:
            o = BADGE_OFF.get(num, 0.0)
            dx, dy = o * off_x, o * off_y
        if abs(dx) < 1e-9 and abs(dy) < 1e-9:   # isolated: badge sits on the point
            ax.text(x, y, str(num), fontsize=6.5, fontweight="bold", color="white",
                    ha="center", va="center", zorder=8,
                    bbox=dict(boxstyle="circle,pad=0.20", fc=c, ec="white", lw=0.8), **kw)
        else:                                   # clustered: dot on line + offset badge
            bx, by = x + dx, y + dy
            ax.plot([x, bx], [y, by], color=c, lw=0.7, zorder=7,
                    solid_capstyle="round", **kw)
            ax.plot([x], [y], marker="o", color=c, ms=3.2, markeredgecolor="white",
                    markeredgewidth=0.5, zorder=7.5, **kw)
            ax.text(bx, by, str(num), fontsize=6.5, fontweight="bold", color="white",
                    ha="center", va="center", zorder=8,
                    bbox=dict(boxstyle="circle,pad=0.20", fc=c, ec="white", lw=0.8), **kw)


def _badge(ax, x, y, label, c, fs=7.5, pad=0.18):
    ax.text(x, y, label, transform=ax.transAxes, fontsize=fs, fontweight="bold",
            color="white", ha="center", va="center",
            bbox=dict(boxstyle=f"circle,pad={pad}", fc=c, ec="white", lw=1.0))


def draw_key(axk, style):
    axk.axis("off")
    if style == "A":   # grouped by what binds (space vs time)
        axk.set_title("(c) what happens at each point", loc="left", fontsize=9.5, fontweight="bold")
        space = [(i, s, ty) for i, s, ty in numbered if ty in ("cell", "heading")]
        time_ = [(i, s, ty) for i, s, ty in numbered if ty == "time"]
        y = 0.90
        for header, pts in [("SPACE — distance lines", space),
                            ("TIME — 6 h block lines", time_)]:
            axk.text(0.0, y, header, transform=axk.transAxes, fontsize=8.4,
                     fontweight="bold", color="#333", va="center")
            y -= 0.11
            for i, s, ty in pts:
                _badge(axk, 0.07, y, str(i), TYPE_COLOR[ty])
                axk.text(0.15, y, describe(ty, s), transform=axk.transAxes, fontsize=8.4, va="center")
                y -= 0.105
            y -= 0.05
        axk.plot(0.07, y, "o", color="black", ms=8, markeredgecolor="white",
                 transform=axk.transAxes, clip_on=False)
        axk.text(0.15, y, "Port A (start)", transform=axk.transAxes, fontsize=8.4, va="center")
        y -= 0.10
        axk.plot(0.07, y, "*", color=ARRC, ms=14, markeredgecolor="white",
                 transform=axk.transAxes, clip_on=False)
        axk.text(0.15, y, "Port B (arrival)", transform=axk.transAxes, fontsize=8.4, va="center")

    elif style == "B":   # compact table
        axk.set_title("(c) what happens at each point", loc="left", fontsize=9.5, fontweight="bold")
        xn, xp, xc = 0.05, 0.14, 0.50
        rows = [("S", "black", "Port A", "departure")]
        for i, s, ty in numbered:
            if ty == "cell":
                rows.append((str(i), CELLC, "cell crossing", "weather, space"))
            elif ty == "time":
                rows.append((str(i), TIMEC, "6 h block", f"weather, $t={round(time_at_nm(s))}$ h"))
            else:
                rows.append((str(i), NAVY, "heading change", "course $\\psi$"))
        rows.append(("B", ARRC, "Port B", "arrival (ETA)"))
        y = 0.90
        axk.text(xp, y, "point", transform=axk.transAxes, fontsize=8.2, fontweight="bold", color="#333", va="center")
        axk.text(xc, y, "what changes", transform=axk.transAxes, fontsize=8.2, fontweight="bold", color="#333", va="center")
        y -= 0.04
        axk.plot([0.02, 0.95], [y, y], transform=axk.transAxes, color="#bbb", lw=0.8, clip_on=False)
        y -= 0.07
        for lab, c, pt, ch in rows:
            if lab == "S":
                axk.plot(xn, y, "o", color=c, ms=7, markeredgecolor="white", transform=axk.transAxes, clip_on=False)
            elif lab == "B":
                axk.plot(xn, y, "*", color=c, ms=12, markeredgecolor="white", transform=axk.transAxes, clip_on=False)
            else:
                _badge(axk, xn, y, lab, c, fs=8, pad=0.18)
            axk.text(xp, y, pt, transform=axk.transAxes, fontsize=8.2, va="center")
            axk.text(xc, y, ch, transform=axk.transAxes, fontsize=8.2, va="center")
            y -= 0.095

    elif style == "C":   # type legend only
        axk.set_title("(c) point types", loc="left", fontsize=9.5, fontweight="bold")
        axk.text(0.0, 0.92, "each numbered point is a state transition\nwhere the speed may change",
                 transform=axk.transAxes, fontsize=8.2, style="italic", color="#555", va="top")
        items = [(CELLC, "o", "cell crossing", "weather changes in space (0.5$\\degree$)"),
                 (TIMEC, "o", "6 h block", "weather changes in time"),
                 (NAVY, "o", "heading change", "course $\\psi$ changes"),
                 (ARRC, "*", "start / arrival", "departure / ETA")]
        y = 0.74
        for c, mk, name, desc in items:
            axk.plot(0.06, y, mk, color=c, ms=(13 if mk == "*" else 11),
                     markeredgecolor="white", transform=axk.transAxes, clip_on=False)
            axk.text(0.14, y + 0.018, name, transform=axk.transAxes, fontsize=9.5, fontweight="bold", va="center")
            axk.text(0.14, y - 0.035, desc, transform=axk.transAxes, fontsize=8.3, color="#444", va="center")
            y -= 0.17

    else:   # style "D": structured table
        axk.set_title("(c) point types", loc="left", fontsize=9.5, fontweight="bold")
        axk.text(0.0, 0.93, "each numbered point is a state transition\nwhere the speed may change",
                 transform=axk.transAxes, fontsize=7.8, style="italic", color="#555", va="top")
        xm, xtype, xchg, xbnd = 0.05, 0.13, 0.46, 0.67
        yh = 0.78
        axk.plot([0.02, 0.99], [yh + 0.06, yh + 0.06], transform=axk.transAxes,
                 color="#333", lw=1.1, clip_on=False)   # top rule
        for xx, lab in [(xtype, "point type"), (xchg, "changes"), (xbnd, "boundary")]:
            axk.text(xx, yh, lab, transform=axk.transAxes, fontsize=7.4,
                     fontweight="bold", color="#333", va="center")
        axk.plot([0.02, 0.99], [yh - 0.038, yh - 0.038], transform=axk.transAxes,
                 color="#333", lw=1.1, clip_on=False)
        rows = [
            (CELLC, "o",    "cell crossing",  "weather",        "0.5$\\degree$ cell (space)"),
            (TIMEC, "o",    "6 h block",      "weather",        "6 h line (time)"),
            (NAVY,  "o",    "heading change", "course $\\psi$",  "segment end"),
            (ARRC,  "both", "start / arrival", "—",         "port A / port B"),
        ]
        y = yh - 0.12
        for c, mk, name, chg, bnd in rows:
            if mk == "both":
                axk.plot(xm - 0.015, y, "o", color="black", ms=7, markeredgecolor="white",
                         transform=axk.transAxes, clip_on=False)
                axk.plot(xm + 0.025, y, "*", color=ARRC, ms=12, markeredgecolor="white",
                         transform=axk.transAxes, clip_on=False)
            else:
                axk.plot(xm, y, mk, color=c, ms=10, markeredgecolor="white",
                         transform=axk.transAxes, clip_on=False)
            axk.text(xtype, y, name, transform=axk.transAxes, fontsize=8.0,
                     fontweight="bold", va="center")
            axk.text(xchg, y, chg, transform=axk.transAxes, fontsize=7.6, color="#444", va="center")
            axk.text(xbnd, y, bnd, transform=axk.transAxes, fontsize=7.6, color="#444", va="center")
            y -= 0.135
        axk.plot([0.02, 0.99], [y + 0.06, y + 0.06], transform=axk.transAxes,
                 color="#333", lw=1.1, clip_on=False)


def make_figure(key_style, outname):
    lon0, lon1, lat0, lat1 = WINDOW
    fig = plt.figure(figsize=(11.0, 7.0))
    gs = fig.add_gridspec(2, 2, width_ratios=[1.5, 1.0], height_ratios=[1.0, 1.0],
                          hspace=0.22, wspace=0.05)

    # ---------- panel (a): geographic map ----------
    axm = fig.add_subplot(gs[0, 0], projection=ccrs.PlateCarree())
    axm.set_extent(WINDOW, crs=ccrs.PlateCarree())
    axm.set_facecolor(SEA)
    axm.add_feature(cfeature.LAND.with_scale("10m"), facecolor=LAND, zorder=4, rasterized=True)
    axm.add_feature(cfeature.COASTLINE.with_scale("10m"), linewidth=0.5, edgecolor="#555555",
                    zorder=5, rasterized=True)
    samp = [pos_at_nm(s) for s in np.linspace(0, total_nm, 700)]
    cells = sorted({(floor(lo / CELL), floor(la / CELL)) for la, lo in samp})
    for ci, cj in cells:
        axm.add_patch(plt.Rectangle((ci * CELL, cj * CELL), CELL, CELL, transform=ccrs.PlateCarree(),
                                    facecolor=TINT[(ci + cj) % 2], edgecolor="#7fa3c4", lw=0.5,
                                    alpha=0.7, zorder=2.5))
    for x in np.arange(floor(lon0 / CELL) * CELL, lon1 + 1e-9, CELL):
        axm.plot([x, x], [lat0, lat1], color="#9fb3c8", lw=0.5, ls=(0, (1, 2)),
                 transform=ccrs.PlateCarree(), zorder=2.6)
    for yy in np.arange(floor(lat0 / CELL) * CELL, lat1 + 1e-9, CELL):
        axm.plot([lon0, lon1], [yy, yy], color="#9fb3c8", lw=0.5, ls=(0, (1, 2)),
                 transform=ccrs.PlateCarree(), zorder=2.6)
    axm.plot([p[1] for p in track], [p[0] for p in track], "-", color=TRACK, lw=2.2,
             transform=ccrs.PlateCarree(), zorder=6, solid_capstyle="round")
    axm.plot(track[0][1], track[0][0], "o", color="black", ms=6, transform=ccrs.PlateCarree(), zorder=9)
    axm.plot(track[-1][1], track[-1][0], "*", color=ARRC, ms=15, markeredgecolor="white",
             transform=ccrs.PlateCarree(), zorder=9)
    place_numbered(
        axm,
        [(i, pos_at_nm(s)[1], pos_at_nm(s)[0], TYPE_COLOR[ty]) for i, s, ty in numbered],
        explicit=MAP_OFF, transform=ccrs.PlateCarree())
    axm.text(track[0][1] - 0.08, track[0][0] - 0.16, "Port A", fontsize=8.5, color="black",
             transform=ccrs.PlateCarree(), ha="left", va="top",
             bbox=dict(boxstyle="round,pad=0.12", fc="white", ec="none", alpha=0.85))
    axm.text(track[-1][1] + 0.08, track[-1][0] - 0.05, "Port B", fontsize=8.5, color=ARRC,
             transform=ccrs.PlateCarree(), ha="left", va="center",
             bbox=dict(boxstyle="round,pad=0.12", fc="white", ec="none", alpha=0.85))
    gl = axm.gridlines(draw_labels=True, linewidth=0, alpha=0)
    gl.top_labels = gl.right_labels = False
    gl.xlabel_style = gl.ylabel_style = {"size": 7}
    axm.set_title("(a) geographic map — where each speed-change point is",
                  loc="left", fontsize=9.5, fontweight="bold")

    # ---------- locator inset: this zoom on the full Gulf -> Malacca route ----------
    pos = axm.get_position()
    iw, ih = 0.36 * pos.width, 0.40 * pos.height
    il = pos.x0 + pos.width - iw - 0.006
    ib = pos.y0 + pos.height - ih - 0.006
    axl = fig.add_axes([il, ib, iw, ih], projection=ccrs.PlateCarree())
    axl.set_extent(FULL_EXTENT, crs=ccrs.PlateCarree())
    axl.set_facecolor(SEA)
    axl.add_feature(cfeature.LAND.with_scale("110m"), facecolor=LAND, zorder=1)
    axl.add_feature(cfeature.COASTLINE.with_scale("110m"), linewidth=0.3,
                    edgecolor="#888888", zorder=2)
    axl.plot([p[1] for p in FULL_ROUTE], [p[0] for p in FULL_ROUTE], "-", color=TRACK,
             lw=1.0, transform=ccrs.PlateCarree(), zorder=3, solid_capstyle="round")
    lo0, lo1, la0, la1 = WINDOW
    axl.add_patch(plt.Rectangle((lo0, la0), lo1 - lo0, la1 - la0, transform=ccrs.PlateCarree(),
                                facecolor="none", edgecolor=ARRC, lw=1.3, zorder=4))
    axl.set_title("full route: Gulf $\\rightarrow$ Malacca", fontsize=6.0, pad=1.5)
    for _s in axl.spines.values():
        _s.set_edgecolor("#888888")
        _s.set_linewidth(0.6)

    # ---------- panel (b): time-distance state space ----------
    axt = fig.add_subplot(gs[1, 0])
    axt.add_patch(plt.Rectangle((0, 0), head_nm, T, facecolor="#eef3f9", edgecolor="none", zorder=0))
    axt.add_patch(plt.Rectangle((head_nm, 0), total_nm - head_nm, T, facecolor="#e1ebf3",
                                edgecolor="none", zorder=0))
    for tt in np.arange(6, T, 6):
        axt.axhline(tt, color="#9aa7b4", lw=0.8, ls=(0, (4, 3)), zorder=1)
    for s in cell_nms:
        axt.axvline(s, color="#aab7c2", lw=1.0, ls=(0, (1, 3)), zorder=1)
    axt.axvline(head_nm, color=NAVY, lw=2.0, ls="-", zorder=1.5)
    axt.plot(bounds, seg_t, color=TRACK, lw=2.2, zorder=4, solid_capstyle="round")
    place_numbered(
        axt,
        [(i, s, time_at_nm(s), TYPE_COLOR[ty]) for i, s, ty in numbered],
        off_x=0.0, off_y=2.3)   # inverted time axis: -o = smaller t = up
    axt.plot(0, 0, "o", color="black", ms=6, zorder=6)
    axt.plot(total_nm, T, "*", color=ARRC, ms=15, markeredgecolor="white", zorder=6)
    axt.annotate("segment 1", (head_nm / 2, T * 0.96), ha="center", fontsize=8.5, color=NAVY, style="italic")
    axt.annotate("segment 2", ((head_nm + total_nm) / 2, T * 0.96), ha="center", fontsize=8.5, color=NAVY, style="italic")
    axt.set_xlim(-total_nm * 0.03, total_nm * 1.03)
    axt.set_ylim(T * 1.05, -T * 0.05)
    axt.set_xlabel("along-track distance $d$ (nm)  —  vertical lines = cell/heading boundaries")
    axt.set_ylabel("elapsed time $t$ (h)  —  horizontal lines = 6 h")
    for sp in ("top", "right"):
        axt.spines[sp].set_visible(False)
    axt.set_title("(b) time--distance state space — same points; kink $=$ speed change",
                  loc="left", fontsize=9.5, fontweight="bold")

    # ---------- panel (c): key ----------
    draw_key(fig.add_subplot(gs[:, 1]), key_style)

    fig.savefig(f"{outname}.pdf", dpi=300, bbox_inches="tight", pad_inches=0.05)
    fig.savefig(f"{outname}.png", dpi=200, bbox_inches="tight", pad_inches=0.05)
    plt.close(fig)
    print(f"wrote {outname}.* ({len(numbered)} points, T={T:.1f} h, {total_nm:.0f} nm)")


for _style, _name in [("A", "combined_twin_A"), ("B", "combined_twin_B"),
                      ("C", "combined_twin_C"), ("D", "combined_twin_D")]:
    make_figure(_style, _name)

"""
Fused voyage figure — design "B" (true 2-D map on top + tie-lines).

Same fusion goal as design A, but the top panel is a REAL cartographic map
(cartopy: coastline, 0.5 deg cells, the route in true lat/lon) rather than the
unrolled ribbon. Because the map's x-axis is longitude and the plane's is
along-track distance, the two are stitched by TIE-LINES (matplotlib
ConnectionPatch): each numbered point on the map is joined to the same point's
along-track distance on the plane below, and the cell/heading boundaries drop to
their distance on the plane's x-axis (the shared "spine").

Weather appears in BOTH panels with one shared colormap:
  * map   — each 0.5 deg cell tinted by the wave height the ship MEETS there
            (realised: the cell's value in the 6 h block the ship crosses it).
  * plane — the full space x time field: every (cell x 6 h block) rectangle.

All geometry, the weather field, the trajectory and the four numbered points are
imported from plot_fused_voyage (design A) so the plane is identical.

Run:  python3 plot_fused_voyage_B.py
Out:  fused_voyage_B.pdf, fused_voyage_B.png
"""

from math import floor

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import Normalize
from matplotlib.patches import ConnectionPatch
import cartopy.crs as ccrs
import cartopy.feature as cfeature

import plot_fused_voyage as fv   # geometry + weather + trajectory (design A)

CELL = fv.CELL
NORM = Normalize(vmin=float(fv.wave.min()), vmax=float(fv.wave.max()))


# --- realised wave per band -> per geographic 0.5 deg cell ------------------
def _block_of(t):
    for j in range(fv.nblocks):
        if fv.block_edges[j] - 1e-9 <= t <= fv.block_edges[j + 1] + 1e-9:
            return j
    return fv.nblocks - 1


realized_wave = []
cell_wave = {}
for i in range(fv.nbands):
    mid_d = (fv.boundaries[i] + fv.boundaries[i + 1]) / 2
    j = _block_of(fv.time_at_nm(mid_d))
    w = fv.base_wave[i] * fv.tfac[j]
    realized_wave.append(w)
    la, lo = fv.pos_at_nm(mid_d)
    cell_wave[(floor(lo / CELL), floor(la / CELL))] = w


def make_figure(outname):
    fig = plt.figure(figsize=(12.0, 9.2))
    gs = fig.add_gridspec(2, 2, width_ratios=[1.0, 0.34],
                          height_ratios=[1.15, 1.55], hspace=0.30, wspace=0.03)
    axm = fig.add_subplot(gs[0, 0], projection=ccrs.PlateCarree())
    axp = fig.add_subplot(gs[1, 0])
    axk = fig.add_subplot(gs[:, 1])

    xlim = (-fv.total_nm * 0.02, fv.total_nm * 1.02)

    # =========================== (a) real 2-D map ========================
    lon0, lon1, lat0, lat1 = fv.WINDOW
    axm.set_extent(fv.WINDOW, crs=ccrs.PlateCarree())
    axm.set_facecolor(fv.SEA)
    # 0.5 deg cells the route passes, tinted by the wave height met there
    samp = [fv.pos_at_nm(s) for s in np.linspace(0, fv.total_nm, 700)]
    route_cells = sorted({(floor(lo / CELL), floor(la / CELL)) for la, lo in samp})
    for ci, cj in route_cells:
        w = cell_wave.get((ci, cj))
        fc = fv.WX_CMAP(NORM(w)) if w is not None else "#dfe9f2"
        axm.add_patch(plt.Rectangle((ci * CELL, cj * CELL), CELL, CELL,
                                    transform=ccrs.PlateCarree(), facecolor=fc,
                                    edgecolor="#7fa3c4", lw=0.5, alpha=0.92, zorder=2.5))
    axm.add_feature(cfeature.LAND.with_scale("10m"), facecolor=fv.LAND, zorder=4)
    axm.add_feature(cfeature.COASTLINE.with_scale("10m"), linewidth=0.5,
                    edgecolor="#555555", zorder=5)
    for x in np.arange(floor(lon0 / CELL) * CELL, lon1 + 1e-9, CELL):
        axm.plot([x, x], [lat0, lat1], color="#9fb3c8", lw=0.5, ls=(0, (1, 2)),
                 transform=ccrs.PlateCarree(), zorder=2.6)
    for yy in np.arange(floor(lat0 / CELL) * CELL, lat1 + 1e-9, CELL):
        axm.plot([lon0, lon1], [yy, yy], color="#9fb3c8", lw=0.5, ls=(0, (1, 2)),
                 transform=ccrs.PlateCarree(), zorder=2.6)
    axm.plot([p[1] for p in fv.track], [p[0] for p in fv.track], "-",
             color=fv.TRACK, lw=2.4, transform=ccrs.PlateCarree(), zorder=6,
             solid_capstyle="round")
    axm.plot(fv.track[0][1], fv.track[0][0], "o", color="black", ms=7,
             transform=ccrs.PlateCarree(), zorder=9)
    axm.plot(fv.track[-1][1], fv.track[-1][0], "*", color=fv.ARRC, ms=16,
             mec="white", transform=ccrs.PlateCarree(), zorder=9)
    # numbered badges on the map (small offsets to clear the route), each with
    # the elapsed time when the ship is there -> "when you are where" (tie the
    # plane's time back to the map).
    MAP_OFF = {1: (-0.10, 0.15), 2: (-0.13, 0.22), 3: (-0.17, 0.06), 4: (0.04, -0.17)}
    TLAB_OFF = {1: (-0.02, 0.32), 2: (-0.05, 0.40), 3: (-0.30, 0.06), 4: (0.10, -0.34)}
    map_pt = {}
    for num, s, tt, ty in fv.numbered:
        la, lo = fv.pos_at_nm(s)
        map_pt[num] = (lo, la)
        dx, dy = MAP_OFF.get(num, (0, 0))
        fv.badge(axm, lo, la, num, fv.TYPE_COLOR[ty], dx=dx, dy=dy)
        tdx, tdy = TLAB_OFF.get(num, (0.10, 0.10))
        axm.text(lo + tdx, la + tdy, f"$t={fv.time_at_nm(s):.0f}$ h",
                 transform=ccrs.PlateCarree(), fontsize=7.8, fontweight="bold",
                 color=fv.TYPE_COLOR[ty], ha="center", va="center", zorder=9,
                 bbox=dict(boxstyle="round,pad=0.14", fc="white", ec="none", alpha=0.82))
    axm.text(fv.track[0][1] - 0.06, fv.track[0][0] - 0.14, "Port A  ($t=0$)",
             fontsize=8.6, transform=ccrs.PlateCarree(), ha="left", va="top",
             bbox=dict(boxstyle="round,pad=0.12", fc="white", ec="none", alpha=0.85))
    axm.text(fv.track[-1][1] + 0.07, fv.track[-1][0] - 0.02,
             f"Port B\n(ETA $t={fv.T:.0f}$ h)", fontsize=8.6, color=fv.ARRC,
             transform=ccrs.PlateCarree(), ha="left", va="center",
             bbox=dict(boxstyle="round,pad=0.12", fc="white", ec="none", alpha=0.85))
    # payoff for (c): the rough cell is only reached late in the voyage.
    # (xy is (lon, lat) — pos_at_nm returns (lat, lon), so swap.)
    _rla, _rlo = fv.pos_at_nm(fv.total_nm * 0.90)
    axm.annotate("rough water —\nreached only at $t\\approx$12 h",
                 xy=(_rlo, _rla), xytext=(56.35, 25.28),
                 xycoords=ccrs.PlateCarree()._as_mpl_transform(axm),
                 textcoords=ccrs.PlateCarree()._as_mpl_transform(axm),
                 fontsize=8.2, color=fv.NAVY, ha="center", va="center", zorder=10,
                 bbox=dict(boxstyle="round,pad=0.2", fc="white", ec=fv.NAVY, lw=0.8, alpha=0.9),
                 arrowprops=dict(arrowstyle="->", color=fv.NAVY, lw=1.0))
    gl = axm.gridlines(draw_labels=True, linewidth=0, alpha=0)
    gl.top_labels = gl.right_labels = False
    gl.xlabel_style = gl.ylabel_style = {"size": 7.5}
    axm.set_title("(a)  geographic map — where each point is",
                  loc="left", fontsize=11, fontweight="bold", pad=6)

    # =========================== (b) plane (identical to A) ==============
    mesh = axp.pcolormesh(np.array(fv.boundaries), np.array(fv.block_edges), fv.wave,
                          cmap=fv.WX_CMAP, shading="flat", zorder=0, norm=NORM)
    for tt in fv.block_edges[1:-1]:
        axp.axhline(tt, color="#5b6b7a", lw=0.8, ls=(0, (5, 3)), zorder=2)
    axp.plot(fv.bounds, fv.seg_t, color=fv.TRACK, lw=2.6, solid_capstyle="round", zorder=5)
    axp.plot(0, 0, "o", color="black", ms=7, zorder=6)
    axp.plot(fv.total_nm, fv.T, "*", color=fv.ARRC, ms=16, mec="white", zorder=6)
    PLANE_OFF = {1: (0, -1.5), 2: (0, 1.4), 3: (0, -1.6), 4: (0, 1.5)}
    plane_pt = {}
    for num, s, tt, ty in fv.numbered:
        yy = fv.time_at_nm(s)
        plane_pt[num] = (s, yy)
        dx, dy = PLANE_OFF.get(num, (0, 0))
        fv.badge(axp, s, yy, num, fv.TYPE_COLOR[ty], dx=dx, dy=dy)
    axp.set_xlim(*xlim)
    axp.set_ylim(fv.T * 1.04, -fv.T * 0.04)
    axp.set_xlabel("along-track distance $d$ (nm)   —   vertical lines = 0.5$\\degree$ "
                   "cell / heading boundaries", fontsize=9.5)
    axp.set_ylabel("elapsed time $t$ (h)   —   horizontal lines = 6 h blocks", fontsize=9.5)
    for sp in ("top", "right"):
        axp.spines[sp].set_visible(False)
    axp.set_title("(b)  time $\\times$ distance state space, painted with the "
                  "sea-state field", loc="left", fontsize=11, fontweight="bold", pad=6)

    # spine: cell/heading boundaries as vertical lines in the plane
    for s in fv.dist_events:
        head = abs(s - fv.head_nm) < 1e-4
        axp.axvline(s, color=(fv.NAVY if head else "#7c8b99"),
                    lw=(2.0 if head else 1.0),
                    ls="-" if head else (0, (1, 3)), zorder=3)

    # =========================== tie-lines (map <-> plane) ===============
    # Each map point joins the SAME point on the plane at its true (distance,
    # time): the deeper the line lands, the later the ship is there. So point 1
    # lands on the 6 h line, point 4 on the 12 h line — time is the vertical
    # link between the map (where) and the plane (when).
    for num, s, tt, ty in fv.numbered:
        lo, la = map_pt[num]
        d, yy = plane_pt[num]
        con = ConnectionPatch(xyA=(lo, la), coordsA=axm.transData,
                              xyB=(d, yy), coordsB=axp.transData,
                              color=fv.TYPE_COLOR[ty], lw=1.0, ls=(0, (3, 3)),
                              alpha=0.6, zorder=1)
        fig.add_artist(con)

    # =========================== (c) key + colorbar ======================
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
        c = fv.TYPE_COLOR[ty]
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
        y -= 0.070

    y -= 0.015
    axk.text(0.0, y, "dashed tie-lines", transform=axk.transAxes, fontsize=9.2,
             fontweight="bold", va="center")
    y -= 0.045
    axk.text(0.0, y, "join each place on the map to WHEN\nthe ship is there — the lower it lands,\nthe later in the voyage",
             transform=axk.transAxes, fontsize=8.2, color="#444", va="top")

    y -= 0.10
    axk.text(0.0, y, "reading the plane (slope $=$ speed)", transform=axk.transAxes,
             fontsize=9.2, fontweight="bold", va="center")
    y -= 0.055
    axk.plot([0.06, 0.24], [y + 0.026, y + 0.022], transform=axk.transAxes,
             color=fv.TRACK, lw=2.6, clip_on=False, solid_capstyle="round")
    axk.text(0.28, y + 0.024, "flat $=$ fast (calm)", transform=axk.transAxes,
             fontsize=8.4, va="center")
    y -= 0.065
    axk.plot([0.12, 0.18], [y + 0.048, y - 0.006], transform=axk.transAxes,
             color=fv.TRACK, lw=2.6, clip_on=False, solid_capstyle="round")
    axk.text(0.28, y + 0.020, "steep $=$ slow (rough)", transform=axk.transAxes,
             fontsize=8.4, va="center")

    cax = fig.add_axes([axk.get_position().x0 + 0.006, 0.055, 0.020, 0.17])
    cb = fig.colorbar(mesh, cax=cax)
    cb.set_label("wave height $H_s$ (m)\n(pale calm, deep rough)", fontsize=8.2)
    cb.ax.tick_params(labelsize=7.5)

    fig.savefig(f"{outname}.pdf", dpi=300, bbox_inches="tight", pad_inches=0.06)
    fig.savefig(f"{outname}.png", dpi=200, bbox_inches="tight", pad_inches=0.06)
    plt.close(fig)
    print(f"wrote {outname}.* — realized_wave={[round(w,2) for w in realized_wave]}")


if __name__ == "__main__":
    make_figure("fused_voyage_B")

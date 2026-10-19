"""Cut a window out of the World Bank/IMF ship-density GeoTIFF (tiled, uncompressed int32)
and aggregate it to coarser cells by summing.

    python3 -I ais_cutout.py PYLIB TIF OUT.npz LAT_MIN LAT_MAX LON_MIN LON_MAX [FACTOR]

OUT.npz: density (counts per aggregated cell, int64; NODATA cells count 0), nodata_frac,
lat (cell-centre latitudes, north to south), lon (cell-centre longitudes).
"""
import sys
import numpy as np

pylib, tif, out = sys.argv[1:4]
lat_min, lat_max, lon_min, lon_max = map(float, sys.argv[4:8])
factor = int(sys.argv[8]) if len(sys.argv) > 8 else 4
if pylib != "-":
    sys.path.insert(0, pylib)
import tifffile

NODATA = 2147483647
with tifffile.TiffFile(tif) as t:
    p = t.pages[0]
    H, W = p.shape
    tw, th = p.tilewidth, p.tilelength
    lon0, lat0 = p.tags["ModelTiepointTag"].value[3:5]      # corner of the top-left pixel
    dx = p.tags["ModelPixelScaleTag"].value[0]
    offsets = p.dataoffsets
    ntx = -(-W // tw)
    # pixel window, aligned to the aggregation factor
    c0 = int(np.floor((lon_min - lon0) / dx)) // factor * factor
    c1 = -(-int(np.ceil((lon_max - lon0) / dx)) // factor) * factor
    r0 = int(np.floor((lat0 - lat_max) / dx)) // factor * factor
    r1 = -(-int(np.ceil((lat0 - lat_min) / dx)) // factor) * factor
    win = np.empty((r1 - r0, c1 - c0), dtype=np.int64)
    with open(tif, "rb") as fh:
        for ty in range(r0 // th, (r1 - 1) // th + 1):
            for tx in range(c0 // tw, (c1 - 1) // tw + 1):
                fh.seek(offsets[ty * ntx + tx])
                tile = np.frombuffer(fh.read(tw * th * 4), dtype="<i4").reshape(th, tw)
                ys, xs = ty * th, tx * tw
                a0, a1 = max(r0, ys), min(r1, ys + th)
                b0, b1 = max(c0, xs), min(c1, xs + tw)
                win[a0 - r0:a1 - r0, b0 - c0:b1 - c0] = tile[a0 - ys:a1 - ys, b0 - xs:b1 - xs]
nod = win == NODATA
win[nod] = 0
h, w = win.shape[0] // factor, win.shape[1] // factor
dens = win.reshape(h, factor, w, factor).sum(axis=(1, 3))
nodf = nod.reshape(h, factor, w, factor).mean(axis=(1, 3))
d = dx * factor
lat = lat0 - (r0 + 0.5 * factor) * dx - np.arange(h) * d
lon = lon0 + (c0 + 0.5 * factor) * dx + np.arange(w) * d
np.savez_compressed(out, density=dens, nodata_frac=nodf.astype(np.float32), lat=lat, lon=lon,
                    cell_deg=d, source=tif)
print(f"{out}: {h} x {w} cells of {d:.3f} deg, lat {lat[-1]:.3f}..{lat[0]:.3f}, "
      f"lon {lon[0]:.3f}..{lon[-1]:.3f}; max {dens.max():,}, nodata cells {np.mean(nodf > 0.5):.1%}")

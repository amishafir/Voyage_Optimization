"""Show what the route partition actually is, against what Section 3 says it is.

Section 3 defines a subsegment as a maximal stretch of route inside one segment
and one 0.08-degree cell, ending at a waypoint or a cell boundary. The collected
data instead places sample points at a fixed interval along the route -- 5 NM on
the North Atlantic, 25 NM on the Indian Ocean -- and the solver treats those as
the decision boundaries. The two partitions are different, and this draws all
three on real geometry so the difference can be seen rather than argued about:

    (1) CELL      cell-boundary crossings        -- what Section 3 describes
    (2) SAMPLED   the collected sample points    -- what the experiments use
    (3) UNIFORM   a fixed 5 NM discretisation    -- Tal's simpler alternative

Usage (from pipeline/dp_rebuild/):
    ../../venv/bin/python make_sampling_diagnostic.py
"""
from __future__ import annotations

from pathlib import Path
import h5py
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "paper_workspace" / "data"
OUT = ROOT / "paper_workspace" / "figures" / "sampling_diagnostic"
CELL = 0.08
ROUTES = [("Indian Ocean", DATA / "experiment_b_138wp_v4_sep07.h5", 25.0),
          ("North Atlantic", DATA / "experiment_d_391wp_v4_sep07.h5", 5.0)]


def crossings(lat, lon, d, cell=CELL, n=4000):
    """Along-track distances at which the route crosses a cell boundary."""
    dd = np.linspace(d[0], d[-1], n)
    la = np.interp(dd, d, lat)
    lo = np.interp(dd, d, lon)
    ila = np.floor(la / cell).astype(int)
    ilo = np.floor(lo / cell).astype(int)
    chg = (np.diff(ila) != 0) | (np.diff(ilo) != 0)
    return dd[1:][chg]


def main() -> None:
    fig, axes = plt.subplots(2, 1, figsize=(10.5, 7.4))
    for ax, (name, path, spacing) in zip(axes, ROUTES):
        with h5py.File(path, "r") as h:
            m = h["/metadata"][:]
        order = np.argsort(m["distance_from_start_nm"])
        lat, lon = m["lat"][order], m["lon"][order]
        d = m["distance_from_start_nm"][order]
        orig = m["is_original"][order].astype(bool)

        # a 150 NM window, far enough in to be representative
        lo_d, hi_d = d[0] + 300.0, d[0] + 450.0
        sel = (d >= lo_d) & (d <= hi_d)
        xc = crossings(lat, lon, d)
        xc = xc[(xc >= lo_d) & (xc <= hi_d)]
        xu = np.arange(lo_d, hi_d + 1e-9, 5.0)

        ax.hlines(3, lo_d, hi_d, color="0.75", lw=1)
        ax.vlines(xc, 2.75, 3.25, color="#1f77b4", lw=1.1)
        ax.hlines(2, lo_d, hi_d, color="0.75", lw=1)
        ax.vlines(d[sel], 1.75, 2.25, color="#d62728", lw=1.4)
        ax.plot(d[sel & orig], np.full(int((sel & orig).sum()), 2), "k^", ms=7, zorder=4)
        ax.hlines(1, lo_d, hi_d, color="0.75", lw=1)
        ax.vlines(xu, 0.75, 1.25, color="#2ca02c", lw=1.1)

        ax.set_yticks([3, 2, 1])
        ax.set_yticklabels([f"CELL\n{len(xc)} in 150 NM", f"SAMPLED\nevery {spacing:g} NM",
                           "UNIFORM\nevery 5 NM"], fontsize=8)
        ax.set_ylim(0.4, 3.6)
        ax.set_xlim(lo_d, hi_d)
        ax.set_xlabel("along-track distance (NM)", fontsize=9)
        gaps = np.diff(np.sort(xc))
        extra = f"   shortest cell subsegment {gaps.min():.2f} NM" if len(gaps) else ""
        ax.set_title(f"{name}  —  waypoints ▲{extra}", fontsize=10)
        ax.tick_params(labelsize=8)
    fig.suptitle("Three partitions of the same 150 NM of route", fontsize=11.5)
    fig.tight_layout()
    for ext in ("pdf", "png"):
        fig.savefig(f"{OUT}.{ext}", dpi=200)
    print(f"wrote {OUT}.png")

    print("\n=== counts over the whole route ===")
    for name, path, spacing in ROUTES:
        with h5py.File(path, "r") as h:
            m = h["/metadata"][:]
        o = np.argsort(m["distance_from_start_nm"])
        lat, lon, d = m["lat"][o], m["lon"][o], m["distance_from_start_nm"][o]
        xc = crossings(lat, lon, d)
        g = np.diff(np.sort(xc))
        print(f"  {name:16} length {d[-1]:6.0f} NM")
        print(f"{'':18}CELL    {len(xc):5} crossings   mean {d[-1]/max(len(xc),1):5.2f} NM"
              f"   shortest {g.min():.3f} NM   under 0.5 NM: {(g<0.5).sum()}")
        print(f"{'':18}SAMPLED {len(d):5} points      every {spacing:.0f} NM")
        print(f"{'':18}UNIFORM {int(d[-1]//5):5} points      every 5 NM")


if __name__ == "__main__":
    main()

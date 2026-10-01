"""Forecast error against actuals, per parameter, per lead time, per route (H1).

Answers the claim Section 6.4 makes but never measures: that forecast accuracy
degrades systematically with lead time, and that this is what the forecast cost
of the span table reflects.

Key conventions, both verified against the data rather than assumed:

  * ``sample_hour`` is the ISSUE time of a forecast and ``forecast_hour`` is the
    LEAD from that issue, so a row is valid at ``sample_hour + forecast_hour``.
    Checked by scoring both readings against the actuals: the lead reading gives
    MAE 6.87 km/h on route 1 node 0 against 9.18 for the absolute reading.
  * Wind and current DIRECTION are circular. A plain difference reads 359 deg
    against 1 deg as a 358 deg error; every direction error here is wrapped to
    [-180, 180] before it is summarised.

Only the fields the speed model consumes are reported. Wave height is excluded:
it is not an input to any formula, in our code or in yang2020 (settled
2026-09-08, afb9056), so its error cannot move a result.

Usage (from pipeline/dp_rebuild/):
    ../../venv/bin/python make_forecast_error.py
"""
from __future__ import annotations

from pathlib import Path
import numpy as np
import h5py

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "paper_workspace" / "data"
ROUTES = [("Indian Ocean", DATA / "experiment_b_138wp_v4_sep07.h5"),
          ("North Atlantic", DATA / "experiment_d_391wp_v4_sep07.h5")]

LINEAR = ["wind_speed_10m_kmh", "beaufort_number", "ocean_current_velocity_kmh"]
CIRCULAR = ["wind_direction_10m_deg", "ocean_current_direction_deg"]
FIELDS = LINEAR + CIRCULAR
BANDS = [(0, 6), (6, 12), (12, 24), (24, 48), (48, 72), (72, 120), (120, 161)]
CHUNK = 2_000_000


def wrap180(d: np.ndarray) -> np.ndarray:
    """Signed angular difference folded into [-180, 180]."""
    return (d + 180.0) % 360.0 - 180.0


def actual_grid(aw, field, n_node, n_hour):
    """Dense [node, hour] lookup of the actual value, NaN where unsampled."""
    g = np.full((n_node, n_hour), np.nan, dtype=np.float64)
    g[aw["node_id"].astype(int), aw["sample_hour"].astype(int)] = aw[field]
    return g


def analyse(path: Path):
    with h5py.File(path, "r") as h:
        aw = h["/actual_weather"][:]
        n_node = int(aw["node_id"].max()) + 1
        n_hour = int(aw["sample_hour"].max()) + 1
        grids = {f: actual_grid(aw, f, n_node, n_hour) for f in FIELDS}
        pw = h["/predicted_weather"]
        total = pw.shape[0]
        acc = {f: {b: [0.0, 0.0, 0.0, 0] for b in BANDS} for f in FIELDS}  # |e|, e, e^2, n
        for lo in range(0, total, CHUNK):
            c = pw[lo:lo + CHUNK]
            lead = c["forecast_hour"].astype(int)
            valid = c["sample_hour"].astype(int) + lead
            node = c["node_id"].astype(int)
            ok = (lead > 0) & (valid < n_hour)
            if not ok.any():
                continue
            node, lead, valid = node[ok], lead[ok], valid[ok]
            for f in FIELDS:
                pred = c[f][ok].astype(np.float64)
                act = grids[f][node, valid]
                err = wrap180(pred - act) if f in CIRCULAR else pred - act
                good = ~np.isnan(err)
                if not good.any():
                    continue
                e, L = err[good], lead[good]
                for b in BANDS:
                    m = (L >= b[0]) & (L < b[1])
                    if not m.any():
                        continue
                    s = acc[f][b]
                    s[0] += np.abs(e[m]).sum(); s[1] += e[m].sum()
                    s[2] += (e[m] ** 2).sum(); s[3] += int(m.sum())
    return acc


def main() -> None:
    out = {}
    for name, path in ROUTES:
        print(f"reading {path.name} ...", flush=True)
        out[name] = analyse(path)
    for f in FIELDS:
        unit = "deg" if f in CIRCULAR else ("kn-eq" if "beaufort" in f else "km/h")
        print(f"\n=== {f}   (MAE, {unit}) ===")
        print(f"{'lead (h)':>12}" + "".join(f"{n:>18}" for n, _ in ROUTES) + f"{'ratio NA/IO':>13}")
        for b in BANDS:
            row = f"{str(b[0]) + '-' + str(b[1] - 1):>12}"
            maes = []
            for name, _ in ROUTES:
                s = out[name][f][b]
                mae = s[0] / s[3] if s[3] else float("nan")
                maes.append(mae)
                row += f"{mae:12.3f} (n={s[3] // 1000}k)"[:18].rjust(18)
            row += f"{maes[1] / maes[0]:13.2f}" if maes[0] else " " * 13
            print(row)


if __name__ == "__main__":
    main()

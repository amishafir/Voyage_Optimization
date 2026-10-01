"""Forecast error against actuals, per parameter, per lead, per route (paper Section 6.4).

Measures the claim Section 6.4 previously asserted: that forecast accuracy
degrades with lead time, and that this is what the forecast cost reflects.

Conventions, both verified against the data rather than assumed:

  * ``sample_hour`` is the forecast's ISSUE time and ``forecast_hour`` is the
    LEAD from it, so a row is valid at ``sample_hour + forecast_hour``. Scoring
    both readings against the actuals gives MAE 6.87 km/h for the lead reading
    against 9.18 for the absolute one (route 1, node 0).
  * Wind and current DIRECTION are circular; every direction error is wrapped to
    [-180, 180] before it is summarised.

Only the fields the speed model consumes are reported. Beaufort is shown beside
wind speed but is a deterministic function of it and is never counted as a
separate contributor. Wave height is excluded: not an input to any formula, in
our code or in yang2020 (settled 2026-09-08, afb9056).

STATISTICS. The rows are not independent -- 15.7M rows on route 1 come from ~715
forecast issues over 131 nodes, and adjacent hours, neighbouring nodes and
repeated verification against one actual are all correlated. Intervals therefore
come from a CLUSTER BOOTSTRAP over forecast issues, and the reported n is the
number of issues, never the row count. No hypothesis test is attached: the
section reports measurement with intervals.

Usage (from pipeline/dp_rebuild/):
    ../../venv/bin/python make_forecast_error.py [--boot 400] [--latex]
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import h5py
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "paper_workspace" / "data"
OUT = ROOT / "runs" / "2026_10_01_forecast_error"
ROUTES = [("Indian Ocean", DATA / "experiment_b_138wp_v4_sep07.h5"),
          ("North Atlantic", DATA / "experiment_d_391wp_v4_sep07.h5")]

LINEAR = ["wind_speed_10m_kmh", "beaufort_number", "ocean_current_velocity_kmh"]
CIRCULAR = ["wind_direction_10m_deg", "ocean_current_direction_deg"]
FIELDS = LINEAR + CIRCULAR
LABEL = {"wind_speed_10m_kmh": ("Wind speed", "km/h"),
         "beaufort_number": ("Beaufort number", "BN"),
         "ocean_current_velocity_kmh": ("Current speed", "km/h"),
         "wind_direction_10m_deg": ("Wind direction", "deg"),
         "ocean_current_direction_deg": ("Current direction", "deg")}
BANDS = [(6, 12), (12, 24), (24, 48), (48, 72), (72, 120), (120, 161)]
CHUNK = 2_000_000


def wrap180(d):
    return (d + 180.0) % 360.0 - 180.0


def per_issue_sums(path: Path):
    """Absolute-error sums and counts per (field, band, forecast issue)."""
    with h5py.File(path, "r") as h:
        aw = h["/actual_weather"][:]
        n_node = int(aw["node_id"].max()) + 1
        n_hour = int(aw["sample_hour"].max()) + 1
        grids = {}
        for f in FIELDS:
            g = np.full((n_node, n_hour), np.nan)
            g[aw["node_id"].astype(int), aw["sample_hour"].astype(int)] = aw[f]
            grids[f] = g
        pw = h["/predicted_weather"]
        total = pw.shape[0]
        issues = np.unique(pw["sample_hour"][:])
        pos = {int(v): i for i, v in enumerate(issues)}
        n_iss = len(issues)
        S = {f: {b: np.zeros(n_iss) for b in BANDS} for f in FIELDS}
        N = {f: {b: np.zeros(n_iss, dtype=np.int64) for b in BANDS} for f in FIELDS}
        for lo in range(0, total, CHUNK):
            c = pw[lo:lo + CHUNK]
            lead = c["forecast_hour"].astype(int)
            valid = c["sample_hour"].astype(int) + lead
            node = c["node_id"].astype(int)
            ok = (lead > 0) & (valid < n_hour)
            if not ok.any():
                continue
            idx = np.array([pos[int(v)] for v in c["sample_hour"][ok]])
            node_o, lead_o, valid_o = node[ok], lead[ok], valid[ok]
            for f in FIELDS:
                err = c[f][ok].astype(np.float64) - grids[f][node_o, valid_o]
                if f in CIRCULAR:
                    err = wrap180(err)
                good = ~np.isnan(err)
                if not good.any():
                    continue
                ae, L, I = np.abs(err[good]), lead_o[good], idx[good]
                for b in BANDS:
                    m = (L >= b[0]) & (L < b[1])
                    if not m.any():
                        continue
                    S[f][b] += np.bincount(I[m], weights=ae[m], minlength=n_iss)
                    N[f][b] += np.bincount(I[m], minlength=n_iss)
    return S, N, n_iss


def boot_mae(s, n, n_boot, rng):
    """MAE and a percentile interval from a cluster bootstrap over issues."""
    live = n > 0
    if not live.any():
        return float("nan"), float("nan"), float("nan"), 0
    s, n = s[live], n[live]
    mae = s.sum() / n.sum()
    k = len(s)
    draws = rng.integers(0, k, size=(n_boot, k))
    bs = s[draws].sum(axis=1) / n[draws].sum(axis=1)
    return mae, float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5)), k


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--boot", type=int, default=400)
    ap.add_argument("--latex", action="store_true")
    a = ap.parse_args()
    rng = np.random.default_rng(0)
    res = {}
    for name, path in ROUTES:
        print(f"reading {path.name} ...", flush=True)
        S, N, n_iss = per_issue_sums(path)
        res[name] = {f: {b: boot_mae(S[f][b], N[f][b], a.boot, rng) for b in BANDS} for f in FIELDS}
        res[name]["_issues"] = n_iss
        print(f"   {n_iss} forecast issues (clusters)", flush=True)

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "forecast_error.json").write_text(json.dumps(
        {r: {f: {f"{b[0]}-{b[1]-1}": res[r][f][b] for b in BANDS}
             for f in FIELDS} | {"_issues": res[r]["_issues"]} for r in res}, indent=1))

    for f in FIELDS:
        nm, unit = LABEL[f]
        print(f"\n=== {nm}  (MAE, {unit}; 95% cluster-bootstrap interval) ===")
        print(f"{'lead (h)':>10}" + "".join(f"{n:>30}" for n, _ in ROUTES) + f"{'ratio':>8}")
        for b in BANDS:
            row = f"{f'{b[0]}-{b[1]-1}':>10}"
            ms = []
            for n_, _ in ROUTES:
                m, lo, hi, k = res[n_][f][b]
                ms.append(m)
                row += f"{m:9.3f} [{lo:.3f}, {hi:.3f}]".rjust(30)
            row += f"{ms[1]/ms[0]:8.2f}" if ms[0] else " " * 8
            print(row)
    print(f"\nclusters: " + ", ".join(f"{n} = {res[n]['_issues']} issues" for n, _ in ROUTES))
    print("n is the number of forecast issues, not the number of rows.")


if __name__ == "__main__":
    main()

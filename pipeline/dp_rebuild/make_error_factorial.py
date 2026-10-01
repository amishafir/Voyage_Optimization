"""2x2 factorial: is the Atlantic's higher forecast cost more error, or costlier error?

Separates the two explanations without assuming linearity or additivity, by
crossing the two factors:

                     perturbed by IO's error   perturbed by NA's error
    at IO conditions           A                         B
    at NA conditions           C                         D

    effect of error magnitude = B / A      (same conditions, other route's error)
    effect of conditions      = C / A      (same error, other route's conditions)
    total                     = D / A
    interaction               = (D/A) / ((B/A) * (C/A))

Why not a sensitivity coefficient times an error. The fuel response is NON-LINEAR
in the perturbation: mean |dFCR| per km/h of wind error is 0.00936 mt/h at a
0.5 km/h step and 0.00777 at 4.0. The two routes also have different error
magnitudes, so a single step evaluates them at different points on a curved
response and biases the comparison. Perturbing each cell by a realistic,
measured error avoids both.

The error applied to each field is its RELIANCE-WEIGHTED MAE -- the mean over
lead bands weighted by how often the rolling horizon actually relies on each
band, taken from the re-plan logs -- with a random sign per state. All four
consumed fields are perturbed JOINTLY, so no summing across parameters is
needed. Signs are drawn independently across fields, which is an assumption; it
applies identically to all four cells, so the ratios are far less sensitive to
it than the levels are.

Usage (from pipeline/dp_rebuild/):
    ../../venv/bin/python make_error_factorial.py [--states 700] [--boot 400]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import h5py
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "pipeline"))
from shared.physics import (calculate_sws_from_sog, calculate_fuel_consumption_rate,
                            calculate_ship_heading)
from shared.beaufort import wind_speed_to_beaufort

DATA = ROOT / "paper_workspace" / "data"
RUN = ROOT / "runs" / "2026_10_01_forecast_error"
ROUTES = [("Indian Ocean", DATA / "experiment_b_138wp_v4_sep07.h5", 3393.55 / 280.0),
          ("North Atlantic", DATA / "experiment_d_391wp_v4_sep07.h5", 1955.0 / 168.0)]
PFIELDS = ["wind_speed_10m_kmh", "wind_direction_10m_deg",
           "ocean_current_velocity_kmh", "ocean_current_direction_deg"]
WFIELDS = PFIELDS + ["beaufort_number", "wave_height_m"]


def weighted_mae():
    err = json.loads((RUN / "forecast_error.json").read_text())
    wts = json.loads((RUN / "lead_weights.json").read_text())
    out = {}
    for route in wts:
        out[route] = {f: sum(w * err[route][f][b][0] for b, w in wts[route].items())
                      for f in PFIELDS}
    return out


def states(path, n, rng):
    with h5py.File(path, "r") as h:
        meta = h["/metadata"][:]
        aw = h["/actual_weather"][:]
    lat, lon = meta["lat"], meta["lon"]
    hd = [calculate_ship_heading(lat[i], lon[i], lat[i + 1], lon[i + 1]) for i in range(len(lat) - 1)]
    hd.append(hd[-1])
    ok = ~np.isnan(aw["wind_speed_10m_kmh"]) & ~np.isnan(aw["ocean_current_velocity_kmh"])
    aw = aw[ok]
    idx = rng.choice(len(aw), size=min(n, len(aw)), replace=False)
    out = []
    for i in idx:
        r = aw[i]
        out.append(({f: float(r[f]) for f in WFIELDS},
                    float(hd[min(int(r["node_id"]), len(hd) - 1)])))
    return out


def cell(st, sog, mae, rng):
    """|change in FCR| per state when all four fields are perturbed by `mae`."""
    d = []
    for w, heading in st:
        try:
            f0 = calculate_fuel_consumption_rate(calculate_sws_from_sog(sog, w, heading))
        except Exception:
            continue
        w2 = dict(w)
        for f in PFIELDS:
            w2[f] = w[f] + rng.choice([-1.0, 1.0]) * mae[f]
        w2["wind_speed_10m_kmh"] = max(0.0, w2["wind_speed_10m_kmh"])
        w2["ocean_current_velocity_kmh"] = max(0.0, w2["ocean_current_velocity_kmh"])
        w2["beaufort_number"] = wind_speed_to_beaufort(w2["wind_speed_10m_kmh"])
        try:
            d.append(abs(calculate_fuel_consumption_rate(calculate_sws_from_sog(sog, w2, heading)) - f0))
        except Exception:
            pass
    return np.array(d)


def ci(a, b, n_boot, rng):
    """Ratio of two cell means with a bootstrap interval over states."""
    r = a.mean() / b.mean()
    k = min(len(a), len(b))
    bs = [a[rng.integers(0, len(a), k)].mean() / b[rng.integers(0, len(b), k)].mean()
          for _ in range(n_boot)]
    return r, float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--states", type=int, default=700)
    ap.add_argument("--boot", type=int, default=400)
    a = ap.parse_args()
    rng = np.random.default_rng(7)
    mae = weighted_mae()
    print("reliance-weighted MAE applied as the perturbation:")
    for r in mae:
        print(f"  {r:16} " + "  ".join(f"{f.split('_')[0]}/{f.split('_')[1][:3]}={v:.3f}"
                                       for f, v in mae[r].items()))
    st = {n: states(p, a.states, rng) for n, p, _ in ROUTES}
    sog = {n: s for n, _, s in ROUTES}
    names = [r[0] for r in ROUTES]
    C = {}
    for cond in names:
        for errr in names:
            C[(cond, errr)] = cell(st[cond], sog[cond], mae[errr], rng)
            print(f"  cell: conditions={cond:16} error={errr:16} "
                  f"mean |dFCR| = {C[(cond, errr)].mean():.5f} mt/h  (n={len(C[(cond, errr)])})")
    A = C[(names[0], names[0])]; B = C[(names[0], names[1])]
    Cc = C[(names[1], names[0])]; D = C[(names[1], names[1])]
    print("\n=== decomposition (95% bootstrap interval over states) ===")
    for lbl, num, den in (("effect of error magnitude  B/A", B, A),
                          ("effect of conditions       C/A", Cc, A),
                          ("total                      D/A", D, A)):
        r, lo, hi = ci(num, den, a.boot, rng)
        print(f"  {lbl}: {r:5.2f}  [{lo:.2f}, {hi:.2f}]")
    inter = (D.mean() / A.mean()) / ((B.mean() / A.mean()) * (Cc.mean() / A.mean()))
    print(f"  interaction                   : {inter:5.2f}   (1.00 = the two factors simply multiply)")
    out = {f"{k[0]}|{k[1]}": float(v.mean()) for k, v in C.items()}
    out["_ci"] = {"error_magnitude": list(ci(B, A, a.boot, rng)),
                  "conditions": list(ci(Cc, A, a.boot, rng)),
                  "total": list(ci(D, A, a.boot, rng)),
                  "interaction": float(inter)}
    json.dump(out, open(RUN / "factorial.json", "w"), indent=1)


if __name__ == "__main__":
    main()

"""Fuel sensitivity to a weather error, per route (H2).

H1 measures how wrong the forecast is. This measures what being wrong COSTS,
which is a different quantity: the fuel model is convex in still-water speed
and the required SWS rises as conditions worsen, so the same wind error buys
more fuel error on a harsher route.

Method: at each sampled (node, hour) of the ACTUAL weather, hold the route's
mean SOG target (D/T) and compute the required SWS and its fuel rate. Perturb
one weather parameter by a fixed step, recompute, and take the difference. The
mean |dFCR| per unit of error is the conversion rate that H1's error feeds.

The perturbation is applied to the weather the planner believes, not to the
weather it sails, so this is the sensitivity of the PLAN to a forecast error.

Usage (from pipeline/dp_rebuild/):
    ../../venv/bin/python make_fuel_sensitivity.py
"""
from __future__ import annotations

import sys
from pathlib import Path
import numpy as np
import h5py

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "pipeline"))
from shared.physics import (calculate_sws_from_sog, calculate_fuel_consumption_rate,
                            calculate_ship_heading)

DATA = ROOT / "paper_workspace" / "data"
ROUTES = [("Indian Ocean", DATA / "experiment_b_138wp_v4_sep07.h5", 3393.55 / 280.0),
          ("North Atlantic", DATA / "experiment_d_391wp_v4_sep07.h5", 1955.0 / 168.0)]

# (field, step, unit) -- steps are deliberately round, not matched to the errors
PERTURB = [("wind_speed_10m_kmh", 1.0, "km/h"),
           ("wind_direction_10m_deg", 10.0, "deg"),
           ("ocean_current_velocity_kmh", 0.1, "km/h"),
           ("ocean_current_direction_deg", 10.0, "deg")]
WFIELDS = ["wind_speed_10m_kmh", "wind_direction_10m_deg", "beaufort_number",
           "wave_height_m", "ocean_current_velocity_kmh", "ocean_current_direction_deg"]
N_STATES = 900          # sampled weather states per route


def headings(meta):
    lat, lon = meta["lat"], meta["lon"]
    h = [calculate_ship_heading(lat[i], lon[i], lat[i + 1], lon[i + 1]) for i in range(len(lat) - 1)]
    return np.array(h + [h[-1]])


def fcr_at(w, heading, sog):
    sws = calculate_sws_from_sog(sog, w, heading)
    return calculate_fuel_consumption_rate(sws)


def main() -> None:
    rng = np.random.default_rng(0)
    out = {}
    for name, path, sog in ROUTES:
        with h5py.File(path, "r") as h:
            meta = h["/metadata"][:]
            aw = h["/actual_weather"][:]
        hd = headings(meta)
        ok = ~np.isnan(aw["wind_speed_10m_kmh"]) & ~np.isnan(aw["ocean_current_velocity_kmh"])
        aw = aw[ok]
        idx = rng.choice(len(aw), size=min(N_STATES, len(aw)), replace=False)
        res = {f: [] for f, _, _ in PERTURB}
        base_fcr = []
        for i in idx:
            r = aw[i]
            w = {f: float(r[f]) for f in WFIELDS}
            node = int(r["node_id"])
            heading = float(hd[min(node, len(hd) - 1)])
            try:
                f0 = fcr_at(w, heading, sog)
            except Exception:
                continue
            base_fcr.append(f0)
            for field, step, _ in PERTURB:
                w2 = dict(w)
                w2[field] = w[field] + step
                if field == "wind_speed_10m_kmh":
                    from shared.beaufort import wind_speed_to_beaufort
                    w2["beaufort_number"] = wind_speed_to_beaufort(w2[field])
                try:
                    res[field].append(abs(fcr_at(w2, heading, sog) - f0))
                except Exception:
                    pass
        out[name] = (np.mean(base_fcr), {f: np.mean(v) for f, v in res.items() if v})
        print(f"{name}: sampled {len(base_fcr)} states, mean FCR {np.mean(base_fcr):.4f} mt/h", flush=True)

    print(f"\n=== mean |change in FCR| per unit of weather error (mt/h) ===")
    print(f"{'parameter':30}{'step':>10}" + "".join(f"{n:>18}" for n, _, _ in ROUTES) + f"{'ratio NA/IO':>13}")
    for field, step, unit in PERTURB:
        a = out[ROUTES[0][0]][1].get(field)
        b = out[ROUTES[1][0]][1].get(field)
        if a is None or b is None:
            continue
        print(f"{field:30}{f'+{step:g} {unit}':>10}{a:18.5f}{b:18.5f}{b / a:13.2f}")
    print(f"\n{'baseline mean FCR (mt/h)':30}{'':>10}"
          f"{out[ROUTES[0][0]][0]:18.4f}{out[ROUTES[1][0]][0]:18.4f}"
          f"{out[ROUTES[1][0]][0] / out[ROUTES[0][0]][0]:13.2f}")


if __name__ == "__main__":
    main()

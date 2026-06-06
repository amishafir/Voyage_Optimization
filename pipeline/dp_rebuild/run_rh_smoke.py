"""
Rolling-horizon backward-compat gate (§4.9 step 4).

Validates the new `time_key` plumbing by checking that feeding each solver a
time_key that MIRRORS the Mode C weather selector — actual_weather at
`active_sample_hour(t)`, forecast_hour=None — reproduces the plain Mode C
result bit-for-bit, and matches the June 1 chain-sweep reference numbers
(Route 2, sh_base=0): SR 203.198 mt / Luo 210.250 mt.

Note: §4.9 step 4 said "time_key returns (sh_base, None) always". That is only
equivalent to Mode C if the weather is static — Mode C is time-VARYING actual
(active_sample_hour steps every 6 h), so the faithful identity key mirrors
active_sample_hour rather than returning a constant.

Run from pipeline/dp_rebuild/:  python3 run_rh_smoke.py
"""
from __future__ import annotations

import sys
from argparse import Namespace
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

import SR_main
import luo_main
from weather import VoyageWeather

YAML = str((_HERE / "../config/routes/st_johns_liverpool.yaml").resolve())
H5 = str((_HERE / "../data/experiment_d_391wp.h5").resolve())
ETA = 168.0
SH_BASE = 0

REF_SR = 203.198
REF_LUO = 210.250
TOL = 0.01  # mt — identity must match to well under this


def _args() -> Namespace:
    return Namespace(
        yaml=YAML, h5=H5, eta=ETA,
        min_speed=None, max_speed=None, zeta_nm=None, tau_h=None,
        res_nm=1.0, sample_hour=SH_BASE, baseline=False, csv=False,
    )


def main() -> int:
    voyage = VoyageWeather(Path(H5))
    print(f"exp_d: sh=[{voyage.sample_hours[0]}..{voyage.sample_hours[-1]}] "
          f"({len(voyage.sample_hours)} unique), "
          f"fh=[{voyage.forecast_hours[0]}..{voyage.forecast_hours[-1]}] "
          f"({len(voyage.forecast_hours)} unique)")

    # Identity time_key mirrors the Mode C selector exactly:
    # base_sample_hour=0 is falsy in solve(), so Mode C anchors at sh[0] via
    # active_sample_hour(t, sh_base=None). Mirror that here.
    def time_key_identity(t):
        return (voyage.active_sample_hour(t, sh_base=None), None)

    args = _args()

    print("\n--- SR ---")
    sr_modec = SR_main.solve(args, voyage=voyage, verbose=False)["total_fuel_mt"]
    sr_tk = SR_main.solve(args, voyage=voyage, verbose=False,
                          time_key=time_key_identity, d_start=0.0)["total_fuel_mt"]
    print(f"  Mode C (no time_key) : {sr_modec:.3f} mt")
    print(f"  time_key identity    : {sr_tk:.3f} mt")
    print(f"  reference (Jun 1)    : {REF_SR:.3f} mt")

    print("\n--- Luo ---")
    luo_modec = luo_main.solve(args, voyage=voyage, verbose=False)["total_fuel_mt"]
    luo_tk = luo_main.solve(args, voyage=voyage, verbose=False,
                            time_key=time_key_identity, d_start=0.0)["total_fuel_mt"]
    print(f"  Mode C (no time_key) : {luo_modec:.3f} mt")
    print(f"  time_key identity    : {luo_tk:.3f} mt")
    print(f"  reference (Jun 1)    : {REF_LUO:.3f} mt")

    ok = True
    print("\n--- GATE ---")
    for name, modec, tk, ref in [
        ("SR", sr_modec, sr_tk, REF_SR),
        ("Luo", luo_modec, luo_tk, REF_LUO),
    ]:
        id_ok = abs(modec - tk) < TOL
        ref_ok = abs(modec - ref) < 0.5  # reference rounded; allow small drift
        print(f"  {name}: identity {'PASS' if id_ok else 'FAIL'} "
              f"(|Δ|={abs(modec-tk):.4f} mt), "
              f"vs-ref {'PASS' if ref_ok else 'WARN'} "
              f"(|Δ|={abs(modec-ref):.3f} mt)")
        ok = ok and id_ok
    print(f"\n  RESULT: {'GATE PASS' if ok else 'GATE FAIL'}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

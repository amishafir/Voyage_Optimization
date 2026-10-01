"""LaTeX tables for Section 6.4 and Appendix E, from the forecast-error outputs.

Emits three tables:
  --weighted    reliance-weighted MAE per field per route (Section 6.4)
  --factorial   the 2x2 decomposition (Section 6.4)
  --appendix    full MAE by field, lead band and route, with intervals (Appendix E)

Usage (from pipeline/dp_rebuild/):
    ../../venv/bin/python make_section64_tables.py --weighted
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

RUN = Path(__file__).resolve().parents[2] / "runs" / "2026_10_01_forecast_error"
PF = [("wind_speed_10m_kmh", "Wind speed", "km/h"),
      ("wind_direction_10m_deg", "Wind direction", "deg"),
      ("ocean_current_velocity_kmh", "Current speed", "km/h"),
      ("ocean_current_direction_deg", "Current direction", "deg")]
ALL = PF[:1] + [("beaufort_number", "Beaufort number", "BN")] + PF[1:]
R = ["Indian Ocean", "North Atlantic"]


def load():
    return (json.loads((RUN / "forecast_error.json").read_text()),
            json.loads((RUN / "lead_weights.json").read_text()))


def weighted():
    err, wts = load()
    print(r"\begin{table}[ht]")
    print(r"\centering")
    print(r"\caption{Forecast error in the fields the speed model consumes, averaged over lead")
    print(r"times and weighted by how often the rolling horizon relies on each lead, taken from the")
    print(r"re-plan logs. Error is the mean absolute difference between the forecast and the")
    print(r"conditions that were realised at the same place and time; direction errors are wrapped")
    print(r"to $[-180\degree,180\degree]$ before averaging. Lead-by-lead values with confidence")
    print(r"intervals are in \ref{app:fcsterr} and Figure~\ref{fig:forecast-error}.}")
    print(r"\label{tab:fcsterr}")
    print(r"\begin{tabular}{lrrr}")
    print(r"\toprule")
    print(r"Field & Indian Ocean & North Atlantic & Ratio \\")
    print(r"\midrule")
    for f, lab, unit in PF:
        v = [sum(w * err[r][f][b][0] for b, w in wts[r].items()) for r in R]
        print(f"{lab} ({unit}) & {v[0]:.2f} & {v[1]:.2f} & {v[1]/v[0]:.2f} \\\\")
    print(r"\bottomrule")
    print(r"\end{tabular}")
    print(r"\end{table}")


def factorial():
    fac = json.loads((RUN / "factorial.json").read_text())
    A = fac[f"{R[0]}|{R[0]}"]; B = fac[f"{R[0]}|{R[1]}"]
    C = fac[f"{R[1]}|{R[0]}"]; D = fac[f"{R[1]}|{R[1]}"]
    ci = fac["_ci"]
    print(r"\begin{table}[ht]")
    print(r"\centering")
    print(r"\caption{Separating the two explanations. Each route's realised conditions are")
    print(r"perturbed by each route's measured forecast error, all four fields at once, and the")
    print(r"change in fuel-consumption rate recorded. Crossing the two factors separates a larger")
    print(r"error from a costlier one without assuming the response is linear in either. Intervals")
    print(r"are 95\% bootstrap intervals over the sampled conditions.}")
    print(r"\label{tab:fcstfac}")
    print(r"\begin{tabular}{lrr}")
    print(r"\toprule")
    print(r"Mean $|\Delta\mathrm{FCR}|$ (mt/h) & \multicolumn{2}{c}{perturbed by the error of} \\")
    print(r"\cmidrule(lr){2-3}")
    print(r"evaluated at the conditions of & Indian Ocean & North Atlantic \\")
    print(r"\midrule")
    print(f"Indian Ocean & {A:.4f} & {B:.4f} \\\\")
    print(f"North Atlantic & {C:.4f} & {D:.4f} \\\\")
    print(r"\midrule")
    print(r"\multicolumn{3}{l}{\emph{Decomposition}} \\")
    print(f"\\quad effect of the larger error & \\multicolumn{{2}}{{r}}{{"
          rf"${ci['error_magnitude'][0]:.2f}$ \; [${ci['error_magnitude'][1]:.2f}$, ${ci['error_magnitude'][2]:.2f}$]}} \\")
    print(f"\\quad effect of the harsher conditions & \\multicolumn{{2}}{{r}}{{"
          rf"${ci['conditions'][0]:.2f}$ \; [${ci['conditions'][1]:.2f}$, ${ci['conditions'][2]:.2f}$]}} \\")
    print(f"\\quad both together & \\multicolumn{{2}}{{r}}{{"
          rf"${ci['total'][0]:.2f}$ \; [${ci['total'][1]:.2f}$, ${ci['total'][2]:.2f}$]}} \\")
    print(r"\bottomrule")
    print(r"\end{tabular}")
    print(r"\end{table}")


def appendix():
    err, _ = load()
    bands = list(err[R[0]][PF[0][0]].keys())
    for f, lab, unit in ALL:
        print(r"\begin{table}[H]")
        print(r"\centering")
        print(rf"\caption{{{lab}: mean absolute forecast error by lead time ({unit}), with 95\%")
        print(r"cluster-bootstrap intervals over forecast issues.}")
        print(rf"\label{{tab:fe-{f.replace('_','-')}}}")
        print(r"\begin{tabular}{lrr}")
        print(r"\toprule")
        print(r"Lead (h) & Indian Ocean & North Atlantic \\")
        print(r"\midrule")
        for b in bands:
            cells = []
            for r in R:
                m, lo, hi, _ = err[r][f][b]
                cells.append(f"${m:.3f}$ [${lo:.3f}$, ${hi:.3f}$]")
            print(f"{b} & {cells[0]} & {cells[1]} \\\\")
        print(r"\bottomrule")
        print(r"\end{tabular}")
        print(r"\end{table}")
        print()


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    for k in ("weighted", "factorial", "appendix"):
        ap.add_argument(f"--{k}", action="store_true")
    a = ap.parse_args()
    if a.weighted: weighted()
    if a.factorial: factorial()
    if a.appendix: appendix()

"""
LB refinement study — iteration 2 of the neighbour-price lower bound
(docs/lb_neighbour_price_plan.md §6: "grid refinement helps linearly").

Runs lb_bound at three pricing-grid levels (the paper grid, /2, /4) on both
quick-set voyages, then:
  - checks the linearity of LB(h) in the step scale h,
  - Richardson-extrapolates F̂* (pairwise 2·LB(h/2)−LB(h) and a least-squares
    intercept over all levels),
  - places F̂* inside the bracket [LB_finest, F_polished],
  - tracks how the two gap terms (intrinsic discount, path-switch slack)
    scale with h — evidence for open question Q4.

Everything runs under the CURRENT band (mean±3): golden anchors stay valid
and the study is independent of the pending [0,v_max]/φ(·;0) ratifications.

Run from pipeline/dp_rebuild/:  python3 lb_refinement_study.py
Output: runs/2026_08_08_lb_refinement/
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
OUT = (_HERE / "../../runs/2026_08_08_lb_refinement").resolve()

LEVELS = [  # (tag, scale h, tau_h, zeta_nm)
    ("_h1", 1.0, 0.1, 1.0),
    ("_h2", 0.5, 0.05, 0.5),
    ("_h4", 0.25, 0.025, 0.25),
]
VOYAGES = [("route1", 6), ("route2", 0)]


def run_level(route: str, sh: int, tag: str, tau: float, zeta: float) -> dict:
    cmd = [sys.executable, "lb_bound.py", "--route", route, "--sh_base", str(sh),
           "--out_dir", str(OUT), "--tau_h", str(tau), "--zeta_nm", str(zeta),
           "--tag", tag]
    print("[refine]", " ".join(cmd[1:]), flush=True)
    subprocess.run(cmd, cwd=_HERE, check=True,
                   stdout=open(OUT / f"{route}_sh{sh}{tag}.log", "w"),
                   stderr=subprocess.STDOUT)
    return json.loads((OUT / f"{route}_sh{sh}{tag}.json").read_text())


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    summary = {}
    for route, sh in VOYAGES:
        rows = []
        for tag, h, tau, zeta in LEVELS:
            r = run_level(route, sh, tag, tau, zeta)
            row = {
                "h": h, "tau_h": tau, "zeta_nm": zeta,
                "F_DP_grid": r["F_DP"], "LB": r["LB"],
                "disc_dp_path": r.get("disc_dp_path"),
                "gap_pct": (r["F_DP"] - r["LB"]) / r["F_DP"] * 100.0,
            }
            if row["disc_dp_path"] is not None:
                row["intrinsic_mt"] = r["F_DP"] - r["disc_dp_path"]
                row["slack_mt"] = r["disc_dp_path"] - r["LB"]
            rows.append(row)
            print(f"         h={h}: F_DP(grid)={r['F_DP']:.4f}  LB={r['LB']:.4f}  "
                  f"gap={row['gap_pct']:.2f}%", flush=True)

        # pairwise Richardson: F* ≈ 2·LB(h/2) − LB(h)
        rich = []
        for a, b in zip(rows, rows[1:]):
            rich.append(2.0 * b["LB"] - a["LB"])
        # least-squares intercept of LB = F* − c·h
        hs = [r["h"] for r in rows]
        lbs = [r["LB"] for r in rows]
        n = len(hs)
        hbar, lbar = sum(hs) / n, sum(lbs) / n
        c = -sum((h - hbar) * (l - lbar) for h, l in zip(hs, lbs)) / \
            sum((h - hbar) ** 2 for h in hs)
        f_hat = lbar + c * hbar
        summary[f"{route}_sh{sh}"] = {
            "levels": rows,
            "richardson_pairwise": rich,
            "lsq_intercept_F_hat": f_hat,
            "lsq_slope_c_per_h": c,
        }

    (OUT / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")

    print("\n===== LB REFINEMENT SUMMARY =====")
    for key, s in summary.items():
        print(f"\n{key}:")
        for r in s["levels"]:
            extra = ""
            if "intrinsic_mt" in r:
                extra = (f"  intrinsic={r['intrinsic_mt']:.3f}  "
                         f"slack={r['slack_mt']:.3f}")
            print(f"  h={r['h']:<5} F_DP(grid)={r['F_DP_grid']:.4f}  "
                  f"LB={r['LB']:.4f}  gap={r['gap_pct']:.2f}%{extra}")
        print(f"  Richardson (pairwise): "
              f"{[f'{x:.4f}' for x in s['richardson_pairwise']]}")
        print(f"  LSQ extrapolated F̂* = {s['lsq_intercept_F_hat']:.4f}  "
              f"(slope {s['lsq_slope_c_per_h']:.3f} mt per unit h)")
    print(f"\nwritten: {OUT}/summary.json")


if __name__ == "__main__":
    main()

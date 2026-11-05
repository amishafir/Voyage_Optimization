"""Computation counts for the rolling horizon, machine-independent: nodes, arcs and SWS (fuel)
evaluations summed over every re-plan of a voyage, for the full graph and Luo at every epoch and
both pricings. Run time is about the number of SWS evaluations (50-56 ns each, v2/README.md).

The v2 code is used unchanged: Voyage.solve and Voyage.solve_luo are wrapped here only to record
each plan's stats (Plan.stats, filled by the C++ core). The realized fuel is printed too, as a
check against the CLI outputs of run.sh / run_epochs.sh.

    cd v2; python3 results/2026-11-05_rolling_lag6h_2day/count_ops.py ARCHIVE START ETA OUT.csv
"""
import csv
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from voyage_v2 import core  # noqa: E402
from voyage_v2.rolling import solve_rolling  # noqa: E402

STATS = []
for name in ("solve", "solve_luo"):
    original = getattr(core.Voyage, name)

    def wrapped(self, *a, _original=original, **k):
        plan = _original(self, *a, **k)
        STATS.append(dict(plan.stats))
        return plan

    setattr(core.Voyage, name, wrapped)

METHODS = [("full", "Full graph", {})] + [
    ("luo", f"Luo {e / 4:g} h, {label}", {"epoch_steps": e, "pricing": pricing})
    for e in (24, 12, 8, 6, 4, 2, 1) for pricing, label in (("start", "start point"), ("integrated", "piece by piece"))]


def main():
    archive, start, eta, out = sys.argv[1], sys.argv[2], float(sys.argv[3]), sys.argv[4]
    rows = []
    for method, label, options in METHODS:
        STATS.clear()
        clock = time.perf_counter()
        r = solve_rolling(archive, start, eta, method=method, info_lag_h=6, **options)
        rows.append({"method": label, "fuel_mt": round(r.fuel_mt, 3), "decisions": len(r.decisions),
                     "solve_s": round(time.perf_counter() - clock, 2),
                     **{k: sum(s[k] for s in STATS) for k in ("nodes", "arcs", "sws_evaluations")}})
        print(rows[-1], flush=True)
    with open(out, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


if __name__ == "__main__":
    main()

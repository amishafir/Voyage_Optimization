#!/usr/bin/env python3
"""
The cross-voyage money plot: SR - Luo fuel gap across all 19 voyages (perfect
foresight), both routes. Reads the chain results.csv (no runs). Every bar is
negative => SR beats Luo on every voyage.
"""
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

HERE = Path(__file__).resolve().parent
df = pd.read_csv(HERE.parent / "results" / "2026_06_01_chain_sweep" / "results.csv")

fig, ax = plt.subplots(figsize=(7.2, 4.0))
colors = {"route1": "C0", "route2": "C3"}
labels = {"route1": "Route 1 (Malacca)", "route2": "Route 2 (Atlantic)"}
x = range(len(df))
bars = ax.bar(x, df["gap_pct"], color=[colors[r] for r in df["route"]])
for r in ("route1", "route2"):
    m = df.loc[df.route == r, "gap_pct"].mean()
    ax.axhline(m, color=colors[r], ls=":", lw=1.2)

ax.axhline(0, color="0.4", lw=0.8)
ax.set_xticks(list(x))
ax.set_xticklabels([f"{row.route[-1]}·{row.voyage_idx}" for row in df.itertuples()], fontsize=7)
ax.set_xlabel("Voyage (route · index)")
ax.set_ylabel("SR $-$ Luo fuel gap (%)")
ax.set_title("SR beats Luo on every voyage (perfect foresight, 19 voyages)\n"
             "negative = SR burns less; dotted = per-route mean")
handles = [plt.Rectangle((0, 0), 1, 1, color=colors[r]) for r in ("route1", "route2")]
ax.legend(handles, [labels[r] for r in ("route1", "route2")], frameon=False, loc="lower right")
ax.grid(True, axis="y", alpha=0.3)
fig.tight_layout()
for ext in ("pdf", "png"):
    fig.savefig(HERE / f"plot5_gap_across_voyages.{ext}", dpi=150)

print(f"{len(df)} voyages; all gap_pct < 0: {bool((df.gap_pct < 0).all())}; "
      f"R1 mean {df[df.route=='route1'].gap_pct.mean():.2f}%, "
      f"R2 mean {df[df.route=='route2'].gap_pct.mean():.2f}%")

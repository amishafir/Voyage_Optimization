#!/usr/bin/env python3
"""
Voyage diagnostic plots from existing per-arc chain-sweep CSVs (read-only; no runs).

Plot 1 — time vs distance (voyage trajectory; slope = SOG), SR vs Luo + Naive reference.
Plot 2 — time vs FCR (instantaneous burn profile), SR vs Luo.

Default: Mode-C (perfect-foresight) chain, Route 2, voyage 00 (the canonical
SR 203.2 mt / Luo 210.3 mt voyage). Override with CLI args.

Usage:
    python3 plot_voyage_diagnostics.py [route2|route1] [voyage_00 ...]
"""
import sys
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

HERE = Path(__file__).resolve().parent
RUN = HERE.parent / "results" / "2026_06_01_chain_sweep"   # Mode-C (perfect-foresight) chain

route = sys.argv[1] if len(sys.argv) > 1 else "route2"
voyage = sys.argv[2] if len(sys.argv) > 2 else "voyage_00"
vdir = RUN / route / voyage

sr = pd.read_csv(vdir / "sr.csv")
luo = pd.read_csv(vdir / "luo.csv")
sr_fuel, luo_fuel = sr["fuel_mt"].sum(), luo["fuel_mt"].sum()
T = max(sr["time_h"].max(), luo["time_h"].max())
L = max(sr["distance_nm"].max(), luo["distance_nm"].max())
tag = f"{route.replace('route','Route ')}, {voyage.replace('voyage_','voyage ')} (perfect foresight)"

# ---- Plot 1: time vs distance ------------------------------------------------
fig, ax = plt.subplots(figsize=(6.4, 4.0))
ax.plot([0, T], [0, L], color="0.6", ls=":", lw=1.4, label=f"Naive (constant SOG, {L/T:.2f} kn)")
ax.plot(sr["time_h"], sr["distance_nm"], color="C0", lw=1.8, label=f"SR  ({sr_fuel:.1f} mt)")
ax.plot(luo["time_h"], luo["distance_nm"], color="C3", ls="--", lw=1.8, label=f"Luo ({luo_fuel:.1f} mt)")
ax.set_xlabel("Time (h)"); ax.set_ylabel("Distance (nm)")
ax.set_title(f"Voyage trajectory — {tag}\n(slope = SOG)")
ax.legend(loc="lower right", frameon=False); ax.grid(True, alpha=0.3)
fig.tight_layout()
for ext in ("pdf", "png"):
    fig.savefig(HERE / f"plot1_time_distance_{route}_{voyage}.{ext}", dpi=150)

# ---- Plot 2: time vs FCR -----------------------------------------------------
fig, ax = plt.subplots(figsize=(6.4, 4.0))
ax.plot(sr["time_h"], sr["fcr_mt_per_h"], color="C0", lw=1.6, drawstyle="steps-post", label=f"SR  ({sr_fuel:.1f} mt)")
ax.plot(luo["time_h"], luo["fcr_mt_per_h"], color="C3", ls="--", lw=1.6, drawstyle="steps-post", label=f"Luo ({luo_fuel:.1f} mt)")
ax.set_xlabel("Time (h)"); ax.set_ylabel("FCR (mt/h)")
ax.set_title(f"Fuel consumption rate over the voyage\n{tag}")
ax.legend(loc="upper right", frameon=False); ax.grid(True, alpha=0.3)
fig.tight_layout()
for ext in ("pdf", "png"):
    fig.savefig(HERE / f"plot2_time_fcr_{route}_{voyage}.{ext}", dpi=150)

# ---- Plot 3: cumulative fuel vs time (the money plot — the gap made visible) ----
fig, ax = plt.subplots(figsize=(6.4, 4.0))
ax.plot(sr["time_h"], sr["fuel_mt"].cumsum(), color="C0", lw=2.0, label=f"SR  ({sr_fuel:.1f} mt)")
ax.plot(luo["time_h"], luo["fuel_mt"].cumsum(), color="C3", ls="--", lw=2.0, label=f"Luo ({luo_fuel:.1f} mt)")
ax.set_xlabel("Time (h)"); ax.set_ylabel("Cumulative fuel (mt)")
ax.set_title(f"Cumulative fuel over the voyage\n{tag} — final gap {luo_fuel - sr_fuel:.1f} mt "
             f"({100*(luo_fuel - sr_fuel)/luo_fuel:.1f} %)")
ax.legend(loc="upper left", frameon=False); ax.grid(True, alpha=0.3)
fig.tight_layout()
for ext in ("pdf", "png"):
    fig.savefig(HERE / f"plot3_cumfuel_{route}_{voyage}.{ext}", dpi=150)

# ---- Plot 4: running fuel gap (Luo - SR) vs time — the gap on its own axis ----
import numpy as np
grid = np.linspace(0, T, 600)
sr_cum_i = np.interp(grid, sr["time_h"], sr["fuel_mt"].cumsum())
luo_cum_i = np.interp(grid, luo["time_h"], luo["fuel_mt"].cumsum())
gap = luo_cum_i - sr_cum_i
fig, ax = plt.subplots(figsize=(6.4, 4.0))
ax.axhline(0, color="0.6", lw=0.8)
ax.plot(grid, gap, color="C2", lw=2.0)
ax.fill_between(grid, 0, gap, where=(gap >= 0), color="C2", alpha=0.15)
ax.set_xlabel("Time (h)"); ax.set_ylabel("Fuel gap, Luo $-$ SR (mt)")
ax.set_title(f"Fuel saved by SR over the voyage\n{tag} — ends at {luo_fuel - sr_fuel:.1f} mt "
             f"({100*(luo_fuel - sr_fuel)/luo_fuel:.1f} %)")
ax.grid(True, alpha=0.3)
fig.tight_layout()
for ext in ("pdf", "png"):
    fig.savefig(HERE / f"plot4_fuelgap_{route}_{voyage}.{ext}", dpi=150)

print(f"{tag}: SR {sr_fuel:.3f} mt ({len(sr)} arcs), Luo {luo_fuel:.3f} mt ({len(luo)} arcs); "
      f"L={L:.1f} nm, T={T:.1f} h")
print("wrote:", *(p.name for p in sorted(HERE.glob(f"plot*_{route}_{voyage}.*"))))

"""
Rolling-horizon re-planning on a route archive.

Decisions are made at the start and then every `every_h` hours on the UTC clock
(6 h: 00/06/12/18 UTC, when the ECMWF runs are issued; each run is taken as known
from its start, the zero-delay assumption of the weather products). At each
decision the ship re-plans from where it is to the end of the route, by the same
ETA, with the forecast known then (Voyage.solve or Voyage.solve_luo with
forecast=True), and sails that plan until the next decision. The ship holds the
planned SOG (SOG targeting), so its position at the next decision is the plan's,
whatever the weather. The voyage's fuel is the sailed SOG profile in the actual
(pseudo real-time) weather, every subsegment-by-step piece priced: the sum of the
realized fuel of the arcs it sailed. The SOG window stays fixed over the voyage
(the first plan's mean SOG +/- the band) rather than moving with each re-plan.

    r = solve_rolling(archive, "2026-10-21 00:00", 118, method="full")
    r = solve_rolling(archive, "2026-10-21 00:00", 118, method="luo", epoch_steps=2)
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

import numpy as np

from .core import Plan, Ship, Voyage
from .loader import STEP_SECONDS, VoyageData, load_voyage_data

ARC_FIELDS = ("t0_h", "d0_nm", "t1_h", "d1_nm", "sog_kn", "fuel_mt", "planned_fuel_mt")
EPS_NM = 1e-9


@dataclass
class Decision:
    t_h: float                  # hours after the voyage start
    d_nm: float                 # distance sailed
    remaining_planned_mt: float # the re-plan's objective (forecast) to the end
    remaining_realized_mt: float# the re-plan, if sailed to the end, in the actual weather
    sailed_planned_mt: float    # the part sailed until the next decision: forecast
    sailed_realized_mt: float   # and actual
    solve_s: float


@dataclass
class RollingResult:
    method: str
    feasible: bool
    fuel_mt: float              # realized: the sailed SOG profile in the actual weather
    arrival_h: float
    sog_range_kn: Tuple[float, float]
    decisions: List[Decision] = field(default_factory=list)
    path: Dict[str, np.ndarray] = field(default_factory=dict)   # sailed arcs, voyage hours and distances

    @property
    def planned_fuel_mt(self) -> float:
        """What the sailed arcs were expected to burn when they were planned."""
        return float(self.path["planned_fuel_mt"].sum()) if self.path else float("nan")


def remaining_route(data: VoyageData, d_nm: float) -> np.ndarray:
    """The subsegments from d_nm to the end of the route, the first one cut at d_nm."""
    sub = data.subsegments
    ends = np.cumsum(sub["length_nm"])
    i = int(np.searchsorted(ends, d_nm + EPS_NM, side="right"))
    if i >= len(sub):
        raise ValueError(f"{d_nm} NM is at or past the end of the route ({ends[-1]} NM)")
    out = sub[i:].copy()
    out["length_nm"][0] = ends[i] - d_nm
    out["start_nm"] = np.concatenate([[0.0], np.cumsum(out["length_nm"])[:-1]])
    return out


def _utc(unix: int) -> str:
    return datetime.fromtimestamp(unix, timezone.utc).strftime("%Y-%m-%d %H:%M")


def solve_rolling(archive: str, start: str, eta_hours: float, method: str = "full", every_h: float = 6.0,
                  forecast: bool = True, ship: Optional[Ship] = None, sog_band_kn: float = 3.0,
                  sog_range_kn: Optional[Tuple[float, float]] = None, verbose: bool = False,
                  **solver_options) -> RollingResult:
    """Rolling-horizon voyage with method "full" (Voyage.solve) or "luo" (Voyage.solve_luo;
    solver_options e.g. epoch_steps, dist_step_nm, pricing). forecast=False re-plans with the
    actual weather (an oracle; equals one perfect-information plan up to ties), a check of the
    mechanism. Luo's epochs must divide the decision interval, and with them the start must be
    on the decision clock, so that the decisions fall on epoch boundaries."""
    if method not in ("full", "luo"):
        raise ValueError(f"method must be 'full' or 'luo', got {method!r}")
    ship = ship or Ship.from_yaml()
    every_s = int(round(every_h * 3600))
    if every_s <= 0 or every_s % STEP_SECONDS:
        raise ValueError(f"the decision interval must be a positive multiple of 0.25 h, got {every_h}")
    data = load_voyage_data(archive, start, eta_hours)
    start_unix, end_unix = data.start_unix, data.end_unix
    length = float(data.subsegments["length_nm"].sum())
    if sog_range_kn is None:
        mean = length / (data.eta_steps / 4)
        sog_range_kn = (mean - sog_band_kn, mean + sog_band_kn)

    def solve(voyage: Voyage) -> Plan:
        if method == "full":
            return voyage.solve(forecast=forecast, sog_range_kn=sog_range_kn, **solver_options)
        return voyage.solve_luo(forecast=forecast, sog_range_kn=sog_range_kn, **solver_options)

    result = RollingResult(method, True, 0.0, float("nan"), sog_range_kn)
    sailed = {k: [] for k in ARC_FIELDS}
    t_unix, d = start_unix, 0.0
    while True:
        if t_unix > start_unix:
            data = load_voyage_data(archive, _utc(t_unix), (end_unix - t_unix) / 3600)
        data.subsegments = remaining_route(data, d)
        clock = time.perf_counter()
        plan = solve(Voyage(data, ship))
        solve_s = time.perf_counter() - clock
        offset_h = (t_unix - start_unix) / 3600
        if not plan.feasible:
            result.feasible = False
            raise RuntimeError(f"no feasible plan at {_utc(t_unix)} UTC ({offset_h:g} h, {d:.3f} NM): "
                               f"the remaining {length - d:.1f} NM cannot be sailed by the ETA within "
                               f"SOG {sog_range_kn[0]:.2f}-{sog_range_kn[1]:.2f} kn")
        next_unix = min((t_unix // every_s + 1) * every_s, end_unix)
        horizon_h = (next_unix - t_unix) / 3600
        p = plan.path
        arrives = plan.arrival_h <= horizon_h + 1e-9
        n = len(p["t1_h"]) if arrives else int(np.searchsorted(p["t1_h"], horizon_h + 1e-9, side="right"))
        if not arrives and (n == 0 or abs(p["t1_h"][n - 1] - horizon_h) > 1e-9):
            raise ValueError(f"the plan made at {offset_h:g} h has no arc ending at the next decision "
                             f"({horizon_h:g} h later); with Luo, use epochs that divide the decision "
                             f"interval and a start on the decision clock")
        for k in ARC_FIELDS:
            v = np.asarray(p[k][:n], dtype=float)
            sailed[k].append(v + (offset_h if k in ("t0_h", "t1_h") else d if k in ("d0_nm", "d1_nm") else 0.0))
        result.decisions.append(Decision(offset_h, d, plan.planned_fuel_mt, plan.fuel_mt,
                                         float(p["planned_fuel_mt"][:n].sum()), float(p["fuel_mt"][:n].sum()),
                                         solve_s))
        if verbose:
            print(f"  decision at {offset_h:6.2f} h, {d:8.3f} NM: plan {plan.planned_fuel_mt:9.3f} mt to go "
                  f"(sailed in the actual weather: {plan.fuel_mt:9.3f}); solved in {solve_s:.1f} s")
        if arrives:
            result.arrival_h = offset_h + plan.arrival_h
            break
        d += float(p["d1_nm"][n - 1])
        t_unix = next_unix
    result.path = {k: np.concatenate(v) for k, v in sailed.items()}
    result.fuel_mt = float(result.path["fuel_mt"].sum())
    return result

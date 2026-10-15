"""
Python face of the C++ core (v2/cpp), through ctypes. The library is compiled
on first use, and again whenever a C++ source changes.

    voyage = Voyage(load_voyage_data(path, "2026-10-14 13:20", 280), Ship.from_yaml())
    voyage.arc_cost(sub=10, sog=12.0, t=40)             # pseudo real-time weather
    voyage.arc_cost(sub=10, sog=12.0, t=40, tau=24)     # forecast issued by step 24
"""

from __future__ import annotations

import ctypes
import math
from ctypes import POINTER, c_double, c_float, c_int, c_long
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional

import numpy as np
import yaml

from .build import ensure_library
from .loader import GRIDS, VoyageData

DEFAULT_SHIP = Path(__file__).resolve().parents[1] / "config" / "ship.yaml"
INFEASIBLE_FUEL_MT = 9999.0     # cost of an arc whose SOG needs an SWS outside 2-25 kn


class CoreError(RuntimeError):
    """The C++ core rejected a call."""


class _Ship(ctypes.Structure):
    _fields_ = [("length_m", c_double), ("displacement_t", c_double),
                ("block_coefficient", c_double), ("fcr_coefficient", c_double)]


class _Conditions(ctypes.Structure):
    _fields_ = [("wind_speed_kmh", c_double), ("wind_from_deg", c_double),
                ("current_speed_kmh", c_double), ("current_to_deg", c_double)]


class _ArcInfo(ctypes.Structure):
    _fields_ = [("conditions", _Conditions), ("beaufort", c_int),
                ("sws_kn", c_double), ("hours", c_double), ("fcr_mt_h", c_double), ("fuel_mt", c_double),
                ("feasible", c_int), ("wind_run", c_int), ("current_run", c_int),
                ("wind_held", c_int), ("current_held", c_int)]


class _DPOptions(ctypes.Structure):
    _fields_ = [("sog_band_kn", c_double), ("tick_s", c_int), ("zeta_m", c_double),
                ("merge_nm", c_double), ("forecast", c_int)]


class _LuoOptions(ctypes.Structure):
    _fields_ = [("sog_band_kn", c_double), ("epoch_steps", c_int), ("dist_step_nm", c_double), ("forecast", c_int),
                ("start_point_pricing", c_int)]


class _DPSummary(ctypes.Structure):
    _fields_ = [("feasible", c_int), ("fuel_mt", c_double), ("planned_fuel_mt", c_double), ("arrival_h", c_double),
                ("constant_sog_fuel_mt", c_double), ("v_min_kn", c_double), ("v_max_kn", c_double),
                ("n_segments", c_int), ("path_length", c_int),
                ("nodes", ctypes.c_longlong), ("distance_line_nodes", ctypes.c_longlong),
                ("time_line_nodes", ctypes.c_longlong), ("reached_nodes", ctypes.c_longlong),
                ("arcs", ctypes.c_longlong), ("infeasible_arcs", ctypes.c_longlong),
                ("sws_evaluations", ctypes.c_longlong), ("realized_sws_violations", ctypes.c_longlong),
                ("setup_s", c_double), ("sweep_s", c_double), ("memory_mb", c_double)]


_lib = None


def _library():
    global _lib
    if _lib is None:
        lib = ctypes.CDLL(str(ensure_library()))
        P = ctypes.c_void_p
        sigs = {
            "v2_last_error": (ctypes.c_char_p, []),
            "v2_archive_new": (P, [c_int, c_int]),
            "v2_archive_add_run": (c_int, [P, c_int, c_int, c_int, c_int, POINTER(c_float), POINTER(c_float)]),
            "v2_archive_free": (None, [P]),
            "v2_voyage_new": (P, [POINTER(_Ship), c_int, POINTER(c_double), POINTER(c_double),
                                  POINTER(c_int), POINTER(c_int), c_int, P]),
            "v2_voyage_free": (None, [P]),
            "v2_arc_cost": (c_double, [P, c_int, c_double, c_int, c_int]),
            "v2_arc_costs": (c_int, [P, c_long, POINTER(c_int), POINTER(c_double), POINTER(c_int),
                                     POINTER(c_int), POINTER(c_double)]),
            "v2_arc_detail": (c_int, [P, c_int, c_double, c_int, c_int, POINTER(_ArcInfo)]),
            "v2_dp_solve": (P, [P, POINTER(_DPOptions)]),
            "v2_dp_summary_of": (None, [P, POINTER(_DPSummary)]),
            "v2_dp_path": (None, [P] + [POINTER(c_double)] * 8 + [POINTER(c_int)] * 2),
            "v2_dp_segments": (None, [P] + [POINTER(c_double)] * 3 + [POINTER(c_int)] * 3),
            "v2_dp_free": (None, [P]),
            "v2_luo_solve": (P, [P, POINTER(_LuoOptions)]),
            "v2_beaufort_number": (c_int, [c_double]),
            "v2_sog_from_sws": (c_double, [POINTER(_Ship), c_double, c_double, POINTER(_Conditions)]),
            "v2_sws_from_sog": (c_double, [POINTER(_Ship), c_double, c_double, POINTER(_Conditions)]),
            "v2_fcr_from_sog": (c_double, [POINTER(_Ship), c_double, c_double, POINTER(_Conditions)]),
        }
        for name, (res, args) in sigs.items():
            fn = getattr(lib, name)
            fn.restype, fn.argtypes = res, args
        _lib = lib
    return _lib


def _error() -> str:
    return _library().v2_last_error().decode()


def _raise_if_error(value: float) -> float:
    if math.isnan(value) and _error():
        raise CoreError(_error())
    return value


def _ptr(a: np.ndarray, ctype):
    return a.ctypes.data_as(POINTER(ctype))


# ---------------------------------------------------------------------------
# Ship, conditions and the speed/fuel model
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Ship:
    length_m: float
    displacement_t: float
    block_coefficient: float
    fcr_coefficient: float

    @classmethod
    def from_yaml(cls, path=DEFAULT_SHIP) -> "Ship":
        with open(path) as f:
            cfg = yaml.safe_load(f)
        return cls(**{k: float(cfg[k]) for k in cls.__dataclass_fields__})

    def _c(self) -> _Ship:
        return _Ship(self.length_m, self.displacement_t, self.block_coefficient, self.fcr_coefficient)


@dataclass(frozen=True)
class Conditions:
    wind_speed_kmh: float
    wind_from_deg: float        # direction the wind blows from
    current_speed_kmh: float
    current_to_deg: float       # direction the current flows to

    def _c(self) -> _Conditions:
        return _Conditions(self.wind_speed_kmh, self.wind_from_deg, self.current_speed_kmh, self.current_to_deg)


def beaufort_number(wind_speed_kmh: float) -> int:
    return _library().v2_beaufort_number(wind_speed_kmh)


def sog_from_sws(ship: Ship, sws_kn: float, bearing_deg: float, c: Conditions) -> float:
    return _raise_if_error(_library().v2_sog_from_sws(ship._c(), sws_kn, bearing_deg, c._c()))


def sws_from_sog(ship: Ship, sog_kn: float, bearing_deg: float, c: Conditions) -> float:
    """SWS [kn] needed for sog_kn; inf when no SWS reaches it."""
    return _raise_if_error(_library().v2_sws_from_sog(ship._c(), sog_kn, bearing_deg, c._c()))


def fcr_from_sog(ship: Ship, sog_kn: float, bearing_deg: float, c: Conditions) -> float:
    """FCR [mt/h] needed to make good sog_kn on bearing_deg in conditions c."""
    return _raise_if_error(_library().v2_fcr_from_sog(ship._c(), sog_kn, bearing_deg, c._c()))


# ---------------------------------------------------------------------------
# Plan (result of Voyage.solve)
# ---------------------------------------------------------------------------

@dataclass
class Plan:
    """Minimum-fuel plan: Voyage.solve (full graph, dp.hpp) or Voyage.solve_luo (luo.hpp).
    fuel_mt is realized: the plan's SOG profile in the actual (pseudo real-time) weather, every
    subsegment-by-step piece priced; planned_fuel_mt is what the DP optimized. They differ when
    planning used a forecast or start-point prices."""
    feasible: bool
    fuel_mt: float
    planned_fuel_mt: float
    arrival_h: float
    constant_sog_fuel_mt: float     # every subsegment at the mean SOG, actual weather
    v_min_kn: float
    v_max_kn: float
    stats: Dict                     # nodes, arcs, timings, memory
    path: Dict[str, np.ndarray]     # per arc: t0_h, d0_nm, t1_h, d1_nm, sog_kn, sws_kn, fuel_mt, planned_fuel_mt, segment, step
    segments: Dict[str, np.ndarray] # start_nm, length_nm, bearing_deg, first_sub, n_subs, dominant_sub


def _read_plan(handle) -> Plan:
    """Copy a v2_dp_result into a Plan and free it."""
    lib = _library()
    if not handle:
        raise CoreError(_error())
    try:
        s = _DPSummary()
        lib.v2_dp_summary_of(handle, ctypes.byref(s))
        n = s.path_length
        dbl = {k: np.empty(n) for k in ("t0_h", "d0_nm", "t1_h", "d1_nm", "sog_kn", "sws_kn", "fuel_mt",
                                         "planned_fuel_mt")}
        ints = {k: np.empty(n, dtype=np.int32) for k in ("segment", "step")}
        lib.v2_dp_path(handle, *(_ptr(dbl[k], c_double) for k in dbl), *(_ptr(ints[k], c_int) for k in ints))
        g = s.n_segments
        sd = {k: np.empty(g) for k in ("start_nm", "length_nm", "bearing_deg")}
        si = {k: np.empty(g, dtype=np.int32) for k in ("first_sub", "n_subs", "dominant_sub")}
        lib.v2_dp_segments(handle, *(_ptr(sd[k], c_double) for k in sd), *(_ptr(si[k], c_int) for k in si))
    finally:
        lib.v2_dp_free(handle)
    stats = {k: getattr(s, k) for k, _ in _DPSummary._fields_
             if k not in ("feasible", "fuel_mt", "planned_fuel_mt", "arrival_h", "constant_sog_fuel_mt",
                          "v_min_kn", "v_max_kn")}
    return Plan(bool(s.feasible), s.fuel_mt, s.planned_fuel_mt, s.arrival_h, s.constant_sog_fuel_mt, s.v_min_kn,
                s.v_max_kn, stats, {**dbl, **ints}, {**sd, **si})


# ---------------------------------------------------------------------------
# Voyage
# ---------------------------------------------------------------------------

class Voyage:
    """A route, its ETA and its weather, held by the C++ core."""

    def __init__(self, data: VoyageData, ship: Optional[Ship] = None):
        lib = _library()
        self.data = data
        self.ship = ship or Ship.from_yaml()
        self._handle = None
        archive = lib.v2_archive_new(data.n_cells["wind"], data.n_cells["current"])
        try:
            for grid_index, grid in enumerate(GRIDS):
                for run in data.runs[grid]:
                    if lib.v2_archive_add_run(archive, grid_index, run.init_step, run.first_step, run.n_hours,
                                              _ptr(run.speed, c_float), _ptr(run.direction, c_float)):
                        raise CoreError(f"{grid} run {run.name}: {_error()}")
            sub = data.subsegments
            length = np.ascontiguousarray(sub["length_nm"], dtype=np.float64)
            bearing = np.ascontiguousarray(sub["bearing_deg"], dtype=np.float64)
            wind_cell = np.ascontiguousarray(sub["wind_cell"], dtype=np.int32)
            current_cell = np.ascontiguousarray(sub["current_cell"], dtype=np.int32)
            self._handle = lib.v2_voyage_new(self.ship._c(), len(sub), _ptr(length, c_double),
                                             _ptr(bearing, c_double), _ptr(wind_cell, c_int),
                                             _ptr(current_cell, c_int), data.eta_steps, archive)
            if not self._handle:
                raise CoreError(_error())
        finally:
            lib.v2_archive_free(archive)

    def __del__(self):
        if getattr(self, "_handle", None):
            _library().v2_voyage_free(self._handle)
            self._handle = None

    @property
    def n_subsegments(self) -> int:
        return len(self.data.subsegments)

    def arc_cost(self, sub: int, sog: float, t: int, tau: Optional[int] = None) -> float:
        """Fuel [mt] to sail subsegment `sub` at `sog` knots in the weather at step t,
        as forecast at step tau (omitted: pseudo real-time, tau = t). 9999 when the SOG
        needs an SWS outside 2-25 kn."""
        return _raise_if_error(_library().v2_arc_cost(self._handle, int(sub), float(sog), int(t),
                                                      -1 if tau is None else int(tau)))

    def arc_costs(self, sub, sog, t, tau=None) -> np.ndarray:
        """arc_cost over arrays (broadcast), in one call into C++."""
        tau = -1 if tau is None else tau
        sub, sog, t, tau = np.broadcast_arrays(np.asarray(sub), np.asarray(sog), np.asarray(t), np.asarray(tau))
        sub, t, tau = (np.ascontiguousarray(a, dtype=np.int32).ravel() for a in (sub, t, tau))
        sog = np.ascontiguousarray(sog, dtype=np.float64).ravel()
        out = np.empty(len(sub))
        if _library().v2_arc_costs(self._handle, len(sub), _ptr(sub, c_int), _ptr(sog, c_double),
                                   _ptr(t, c_int), _ptr(tau, c_int), _ptr(out, c_double)):
            raise CoreError(_error())
        return out

    def solve(self, sog_band_kn: float = 3.0, tick_s: int = 4, zeta_m: float = 25.0,
              merge_nm: float = 0.15, forecast: bool = False) -> Plan:
        """Minimum-fuel plan from the start to the end of the route by the ETA: nodes every
        tick_s seconds on every segment boundary and every zeta_m metres on every 0.25 h time
        line, SOG within mean +/- sog_band_kn, subsegments shorter than merge_nm merged. Weather
        is pseudo real-time, or with forecast=True the forecast known at the start."""
        opts = _DPOptions(sog_band_kn, int(tick_s), zeta_m, merge_nm, 1 if forecast else 0)
        return _read_plan(_library().v2_dp_solve(self._handle, ctypes.byref(opts)))

    def solve_luo(self, epoch_steps: int = 24, dist_step_nm: Optional[float] = None, sog_band_kn: float = 3.0,
                  forecast: bool = False, pricing: str = "integrated") -> Plan:
        """Luo et al.'s multistage DP on this voyage (cpp/include/voyage_v2/luo.hpp): constant SOG
        within decision epochs of epoch_steps quarter hours (24 = 6 h), nodes only on the epoch
        boundaries every dist_step_nm (default 0.1 kn x epoch length, 0.6 NM for 6 h epochs).
        pricing="integrated" prices each arc piece by piece along its path; pricing="start" prices
        the whole arc at the conditions where and when it starts, as Luo et al. do (the plan's
        fuel_mt is still its realized fuel). The plan has one arc per epoch."""
        if pricing not in ("integrated", "start"):
            raise ValueError(f"pricing must be 'integrated' or 'start', got {pricing!r}")
        opts = _LuoOptions(sog_band_kn, int(epoch_steps), float(dist_step_nm or 0.0), 1 if forecast else 0,
                           1 if pricing == "start" else 0)
        return _read_plan(_library().v2_luo_solve(self._handle, ctypes.byref(opts)))

    def arc_detail(self, sub: int, sog: float, t: int, tau: Optional[int] = None) -> Dict:
        """Conditions, SWS, FCR and fuel of one arc, and the runs the weather came from."""
        info = _ArcInfo()
        if _library().v2_arc_detail(self._handle, int(sub), float(sog), int(t),
                                    -1 if tau is None else int(tau), ctypes.byref(info)):
            raise CoreError(_error())
        c = info.conditions
        wind_run = self.data.runs["wind"][info.wind_run]
        current_run = self.data.runs["current"][info.current_run]
        return {
            "wind_speed_kmh": c.wind_speed_kmh, "wind_from_deg": c.wind_from_deg,
            "current_speed_kmh": c.current_speed_kmh, "current_to_deg": c.current_to_deg,
            "beaufort": info.beaufort, "bearing_deg": float(self.data.subsegments["bearing_deg"][sub]),
            "length_nm": float(self.data.subsegments["length_nm"][sub]),
            "sws_kn": info.sws_kn, "feasible": bool(info.feasible), "hours": info.hours,
            "fcr_mt_h": info.fcr_mt_h, "fuel_mt": info.fuel_mt,
            "wind_run": wind_run.name, "wind_held": bool(info.wind_held),
            "current_run": current_run.name, "current_held": bool(info.current_held),
        }

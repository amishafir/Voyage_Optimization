"""
Synthetic weather perturbation for stress-testing the rebuilt DP graph.

The rebuild's `sample_hour = block-start` rule means every sub-arc inside a
6 h block reads the SAME cell-canonical weather row — SR DP and Luo DP
end up exploiting only spatial cell variation. That makes the snap-grid
penalty dominate when the optimum trajectory is near-uniform speed, and
hides the regime where SR's mid-block flexibility actually matters.

This module injects controlled WITHIN-BLOCK temporal weather variation on
top of the cell-canonical base. Three modes, all reproducible (seeded):

  * 'none'           — passthrough (sanity check, baseline of the sweep)
  * 'random_walk_ou' — Ornstein-Uhlenbeck (mean-reverting random walk) on
                       wind speed and wave height. One sample path per
                       0.5° cell, hourly resolution. Tunable σ_wind, σ_wave,
                       and correlation time τ_h.
  * 'storm_pulse'    — Gaussian-shaped spike at a chosen (t_storm, d_storm)
                       position. Tests "front passes through mid-voyage".

The perturber recomputes Beaufort number from the perturbed wind speed and
clamps physical fields to non-negative values. Direction fields are kept
at their cell-canonical values (perturbing direction would require careful
circular-mean handling — overkill for the stress test).

Usage:
    from weather_perturb import WeatherPerturber
    perturber = WeatherPerturber(mode='random_walk_ou',
                                 sigma_wind=15.0, sigma_wave=1.0, tau_h=4.0)
    # then in build_atomic_edges:
    nodes, edges = build_atomic_edges(frame, override_sample_hour=0,
                                       perturber=perturber)

Deterministic with seed: same seed → same perturbation realization, so
SR / Luo / baseline all see identical weather and the comparison is fair.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Optional, Tuple

import numpy as np

_HERE = Path(__file__).resolve().parent
_PIPELINE_ROOT = _HERE.parent
if str(_PIPELINE_ROOT) not in sys.path:
    sys.path.insert(0, str(_PIPELINE_ROOT))

from shared.beaufort import wind_speed_to_beaufort  # noqa: E402

from weather import Weather  # noqa: E402
from geo_grid import position_at_d  # noqa: E402


_DEFAULT_MAX_HOURS = 300  # generous upper bound for any voyage we run


@dataclass
class WeatherPerturber:
    """Configurable temporal-variation injection for the cell-canonical lookup."""

    mode: str = "none"            # 'none' | 'random_walk_ou' | 'storm_pulse'
    seed: int = 42

    # OU parameters
    sigma_wind: float = 0.0       # km/h — std of wind perturbation
    sigma_wave: float = 0.0       # m    — std of wave perturbation
    tau_h: float = 4.0            # hours — OU correlation time

    # Storm-pulse parameters
    pulse_t: float = 84.0         # h — center of the pulse along the voyage
    pulse_d: float = 1000.0       # nm — center of the pulse along the route
    pulse_sigma_t: float = 2.0    # h — temporal width
    pulse_sigma_d: float = 100.0  # nm — spatial width
    pulse_dwind: float = 30.0     # km/h — peak wind kick
    pulse_dwave: float = 3.0      # m   — peak wave kick

    grid_deg: float = 0.5         # NWP cell granularity for OU keying
    max_hours: int = _DEFAULT_MAX_HOURS

    # ---- internal state (filled lazily) ----
    _rng: np.random.Generator = field(default=None, repr=False)
    _cell_paths: Dict[Tuple[int, int], Tuple[np.ndarray, np.ndarray]] = field(
        default_factory=dict, repr=False
    )

    def __post_init__(self) -> None:
        if self.mode not in ("none", "random_walk_ou", "storm_pulse"):
            raise ValueError(f"unknown WeatherPerturber.mode {self.mode!r}")
        self._rng = np.random.default_rng(self.seed)

    # ------------------------------------------------------------------ OU

    def _ou_path(self, n: int) -> np.ndarray:
        """Generate one mean-zero, unit-variance OU sample path of length n hours."""
        dt = 1.0
        a = float(np.exp(-dt / max(self.tau_h, 1e-3)))
        sd = float(np.sqrt(max(0.0, 1.0 - a * a)))
        x = np.zeros(n, dtype=np.float64)
        eps = self._rng.standard_normal(n)
        for i in range(1, n):
            x[i] = a * x[i - 1] + sd * eps[i]
        return x

    def _get_cell_paths(self, cell: Tuple[int, int]) -> Tuple[np.ndarray, np.ndarray]:
        """Return cached (wind_path, wave_path) for this cell, generating if first time."""
        cached = self._cell_paths.get(cell)
        if cached is not None:
            return cached
        wind = self._ou_path(self.max_hours)
        wave = self._ou_path(self.max_hours)
        self._cell_paths[cell] = (wind, wave)
        return wind, wave

    # ------------------------------------------------------------------ public

    def perturb(
        self,
        base: Weather,
        t_h: float,
        d_nm: float,
        waypoints,
    ) -> Weather:
        """Return a perturbed Weather for a sub-arc starting at (t_h, d_nm).

        `waypoints` is the route's Waypoint list — used to map d_nm to (lat, lon)
        for cell keying (OU mode) or to compute the spatial spike (storm mode).
        """
        if self.mode == "none":
            return base

        if base.has_nan():
            return base  # don't try to perturb broken weather; pipeline will skip

        d_wind = 0.0
        d_wave = 0.0

        if self.mode == "random_walk_ou":
            lat, lon, _seg = position_at_d(d_nm, waypoints)
            cell = (
                int(np.floor(lat / self.grid_deg)),
                int(np.floor(lon / self.grid_deg)),
            )
            wind_path, wave_path = self._get_cell_paths(cell)
            h = int(round(t_h)) % self.max_hours
            d_wind = self.sigma_wind * float(wind_path[h])
            d_wave = self.sigma_wave * float(wave_path[h])

        elif self.mode == "storm_pulse":
            gauss = float(np.exp(
                -0.5 * (((t_h - self.pulse_t) / max(self.pulse_sigma_t, 1e-3)) ** 2)
                - 0.5 * (((d_nm - self.pulse_d) / max(self.pulse_sigma_d, 1e-3)) ** 2)
            ))
            d_wind = self.pulse_dwind * gauss
            d_wave = self.pulse_dwave * gauss

        new_wind = max(0.0, base.wind_speed_10m_kmh + d_wind)
        new_wave = max(0.0, base.wave_height_m + d_wave)
        new_bn = wind_speed_to_beaufort(new_wind)

        return Weather(
            wind_speed_10m_kmh=new_wind,
            wind_direction_10m_deg=base.wind_direction_10m_deg,
            beaufort_number=new_bn,
            wave_height_m=new_wave,
            ocean_current_velocity_kmh=base.ocean_current_velocity_kmh,
            ocean_current_direction_deg=base.ocean_current_direction_deg,
        )


# ----------------------------------------------------------------------
# Quick self-test
# ----------------------------------------------------------------------

def _quick_demo() -> None:
    """Render a few sample paths to sanity-check the OU process."""
    p = WeatherPerturber(mode="random_walk_ou",
                         sigma_wind=15.0, sigma_wave=1.0, tau_h=4.0, seed=42)
    base = Weather(
        wind_speed_10m_kmh=30.0, wind_direction_10m_deg=270.0,
        beaufort_number=5, wave_height_m=2.0,
        ocean_current_velocity_kmh=0.5, ocean_current_direction_deg=90.0,
    )

    print("OU sample for cell (0, 0), first 24 hours:")
    print(f"  {'h':>3} {'wind':>7} {'BN':>3} {'wave':>5}")
    # Need waypoints to call .perturb — fake it minimally
    from route_waypoints import Waypoint
    wps = [
        Waypoint(idx=1, lat_deg=47.57, lon_deg=-52.71),
        Waypoint(idx=2, lat_deg=53.41, lon_deg=-3.01),
    ]
    for h in range(24):
        w = p.perturb(base, t_h=float(h), d_nm=500.0, waypoints=wps)
        print(f"  {h:>3} {w.wind_speed_10m_kmh:>7.2f} {w.beaufort_number:>3} {w.wave_height_m:>5.2f}")

    print()
    p2 = WeatherPerturber(mode="storm_pulse",
                          pulse_t=84.0, pulse_d=1000.0,
                          pulse_sigma_t=2.0, pulse_sigma_d=100.0,
                          pulse_dwind=30.0, pulse_dwave=3.0)
    print("storm_pulse profile across a cross-section at d=1000:")
    print(f"  {'h':>3} {'wind':>7} {'BN':>3} {'wave':>5}")
    for h in range(78, 91):
        w = p2.perturb(base, t_h=float(h), d_nm=1000.0, waypoints=wps)
        print(f"  {h:>3} {w.wind_speed_10m_kmh:>7.2f} {w.beaufort_number:>3} {w.wave_height_m:>5.2f}")


if __name__ == "__main__":
    _quick_demo()

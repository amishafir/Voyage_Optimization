"""
The spatial grids on which Open-Meteo serves our weather inputs.

Open-Meteo answers a request for (lat, lon) with the value of one grid
point of the model and reports that point's coordinates in the response. The
set of positions answered by the same grid point is that point's *cell*; the
sea conditions are constant inside a cell and can change only where the route
crosses from one cell into the next.

Wind and ocean currents come from different models on different grids:

  current  Marine API, models=meteofrance_currents (Mercator/SMOC ocean model).
           Regular lat-lon grid, 1/12 deg. Grid points sit at odd multiples
           of 1/24 deg, so cell edges fall on the multiples of 1/12 deg.

  wind     Forecast API, models=ecmwf_ifs (ECMWF IFS HRES, about 9 km).
           Octahedral reduced Gaussian grid O1280: 2560 rows of latitude
           0.0703 deg apart, with 20 + 4i points on the i-th row from either
           pole, so the longitude spacing differs from row to row and the
           rows are staggered. A position is answered by the nearest grid
           point in plain (lat, lon) degrees, so a cell is a convex polygon
           (the nearest-point region), not a rectangle.

Each grid class below reproduces the cell-lookup code of the Open-Meteo server
(open-meteo/open-meteo, Sources/App/Domains/RegularGrid.swift and
GaussianGrid.swift), so `cell_of` names the same grid point the API serves.

Requests must pin the model and the cell selection as in `api_params`.
Without `models`, the default `best_match` switches to regional models
with other grids near Europe, North America and in the Persian Gulf. Without
`cell_selection=sea`, the Forecast API prefers land cells near coasts.

The match is exact at sea. Where a cell's grid point is land in the model's
land-sea mask, which happens only within a cell or two of the coast, the API
substitutes a nearby sea point instead. `verify_grid_alignment.py` measures
where this happens on a route.
"""

from __future__ import annotations

import math
from typing import Callable, Hashable, List, Tuple

from shared.rhumb import RhumbLeg, wrap_lon

FORECAST_API_URL = "https://api.open-meteo.com/v1/forecast"
MARINE_API_URL = "https://marine-api.open-meteo.com/v1/marine"


def _round_half_up(x: float) -> int:
    """Nearest integer. Ties never matter here: they are cell edges, and
    cells are only ever evaluated away from their edges."""
    return math.floor(x + 0.5)


class RegularLatLonGrid:
    """A regular lat-lon grid served by nearest grid point in each axis.

    Grid point (i, j) is at (lat_first + i * dlat, lon_first + j * dlon); its
    cell is the dlat x dlon rectangle centred on it.
    """

    def __init__(self, name: str, lat_first: float, lon_first: float,
                 dlat: float, dlon: float, n_lat: int, n_lon: int,
                 api_url: str, api_params: dict):
        self.name = name
        self.lat_first, self.lon_first = lat_first, lon_first
        self.dlat, self.dlon = dlat, dlon
        self.n_lat, self.n_lon = n_lat, n_lon
        self.api_url = api_url
        self.api_params = dict(api_params)

    def cell_of(self, lat: float, lon: float) -> Tuple[int, int]:
        """(row, column) of the grid point that serves (lat, lon)."""
        i = _round_half_up((lat - self.lat_first) / self.dlat)
        if not 0 <= i < self.n_lat:
            raise ValueError(f"latitude {lat} outside the {self.name} grid")
        j = _round_half_up((wrap_lon(lon) - self.lon_first) / self.dlon) % self.n_lon
        return i, j

    def center_of(self, cell: Tuple[int, int]) -> Tuple[float, float]:
        """(lat, lon) of the grid point of `cell`, as the API reports it."""
        i, j = cell
        return self.lat_first + i * self.dlat, wrap_lon(self.lon_first + j * self.dlon)

    def boundary_fractions(self, leg: RhumbLeg) -> List[float]:
        """Fractions in (0, 1) at which `leg` crosses a cell edge.

        Edges are parallels and meridians, and both lat and lon are monotone
        along a rhumb line, so each edge is crossed at most once and its
        crossing point is found in closed form.
        """
        out: List[float] = []
        if not leg.is_east_west:
            lo, hi = sorted((leg.lat1, leg.lat2))
            for k in range(math.ceil((lo - self.lat_first) / self.dlat - 0.5),
                           math.floor((hi - self.lat_first) / self.dlat - 0.5) + 1):
                out.append(leg.fraction_at_lat(self.lat_first + (k + 0.5) * self.dlat))
        lo, hi = sorted((leg.lon1, leg.lon2_unwrapped))
        for k in range(math.ceil((lo - self.lon_first) / self.dlon - 0.5),
                       math.floor((hi - self.lon_first) / self.dlon - 0.5) + 1):
            out.append(leg.fraction_at_lon(self.lon_first + (k + 0.5) * self.dlon))
        # An edge through a waypoint is not a crossing inside the leg; rounding
        # puts it within ~1e-14 of 0 or 1.
        return sorted(f for f in out if 1e-12 < f < 1.0 - 1e-12)


class OctahedralGaussianGrid:
    """ECMWF octahedral reduced Gaussian grid, as Open-Meteo lays it out.

    Row y = 0 .. 2N-1 runs from north to south at latitude
    (N - y - 1) * dy + dy / 2 with dy = 180 / (2N + 0.5). Row y holds
    nx(y) = 20 + 4y points (mirrored in the south) at longitudes 0, 360/nx,
    2*360/nx, ... A position is served by the nearest grid point in squared
    degree distance among the 3 x 3 points around it.
    """

    def __init__(self, name: str, n_lat_lines: int, api_url: str, api_params: dict,
                 search_step_nm: float = 0.25):
        self.name = name
        self.n = n_lat_lines
        self.dy = 180.0 / (2 * n_lat_lines + 0.5)
        self.api_url = api_url
        self.api_params = dict(api_params)
        # Sampling step for locating cell exits; see boundary_fractions.
        self.search_step_nm = search_step_nm

    def nx_of(self, y: int) -> int:
        """Number of grid points on row y."""
        return 20 + 4 * y if y < self.n else (2 * self.n - y - 1) * 4 + 20

    def row_lat(self, y: int) -> float:
        return (self.n - y - 1) * self.dy + self.dy / 2

    def cell_of(self, lat: float, lon: float) -> Tuple[int, int]:
        """(row, column) of the grid point that serves (lat, lon)."""
        lon = wrap_lon(lon)
        center_y = max(1, min(2 * self.n - 2,
                              _round_half_up(self.n - 1 - (lat - self.dy / 2) / self.dy)))
        best, best_d2 = None, math.inf
        for y in (center_y - 1, center_y, center_y + 1):
            nx = self.nx_of(y)
            dx = 360.0 / nx
            point_lat = self.row_lat(y)
            x_center = _round_half_up(lon / dx)
            for x in (x_center - 1, x_center, x_center + 1):
                d2 = (point_lat - lat) ** 2 + (x * dx - lon) ** 2
                if d2 < best_d2:
                    best, best_d2 = (y, x % nx), d2
        return best

    def center_of(self, cell: Tuple[int, int]) -> Tuple[float, float]:
        """(lat, lon) of the grid point of `cell`, as the API reports it."""
        y, x = cell
        return self.row_lat(y), wrap_lon(x * 360.0 / self.nx_of(y))

    def boundary_fractions(self, leg: RhumbLeg) -> List[float]:
        """Fractions in (0, 1) at which `leg` passes from one cell to the next.

        Cells are convex in (lat, lon) and a rhumb line is straight in those
        coordinates to within 1e-9 deg over one search step, so two samples
        in the same cell have no other cell between them. Every cell change
        between consecutive samples is then located by bisection.
        """
        return boundaries_by_search(self.cell_of, leg, self.search_step_nm)


def boundaries_by_search(cell_of: Callable[[float, float], Hashable], leg: RhumbLeg,
                         step_nm: float, tol_nm: float = 1e-9) -> List[float]:
    """Fractions in (0, 1) at which cell_of changes along `leg`.

    Samples the leg every `step_nm` and bisects each change to within
    `tol_nm`. Several changes between two samples are all found, because the
    bisection always locates the exit from the cell the search is currently in.
    """
    length = leg.length_nm
    eps = tol_nm / length

    def cell_at(f: float) -> Hashable:
        return cell_of(*leg.point_at(f))

    n = max(1, math.ceil(length / step_nm))
    out: List[float] = []
    lo_f, lo_cell = eps, cell_at(eps)
    for k in range(1, n + 1):
        f = min(k / n, 1.0 - eps)
        c = cell_at(f)
        while c != lo_cell:
            lo, hi = lo_f, f
            while (hi - lo) * length > tol_nm:
                mid = 0.5 * (lo + hi)
                if cell_at(mid) == lo_cell:
                    lo = mid
                else:
                    hi = mid
            out.append(0.5 * (lo + hi))
            lo_f, lo_cell = hi, cell_at(hi)
        lo_f = f
    return out


# --- The two grids our weather comes on --------------------------------------

CURRENT_GRID = RegularLatLonGrid(
    name="meteofrance_currents",
    lat_first=-80.0 + 1.0 / 24.0, lon_first=-180.0 + 1.0 / 24.0,
    dlat=1.0 / 12.0, dlon=1.0 / 12.0, n_lat=2041, n_lon=4320,
    api_url=MARINE_API_URL,
    api_params={"models": "meteofrance_currents", "cell_selection": "sea"},
)

WIND_GRID = OctahedralGaussianGrid(
    name="ecmwf_ifs",
    n_lat_lines=1280,
    api_url=FORECAST_API_URL,
    api_params={"models": "ecmwf_ifs", "cell_selection": "sea"},
)

DEFAULT_GRIDS = {"wind": WIND_GRID, "current": CURRENT_GRID}

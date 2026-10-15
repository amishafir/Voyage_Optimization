# v2: voyage optimizer (clean start)

Reads a route's weather archive, as written by the live collector on edison
(`pipeline/data/route1_runs.h5`, `route2_runs.h5`; layout in
`pipeline/shared/run_archive.py`), and prices arcs: the fuel to sail one
subsegment at one SOG in the weather of a given time, as forecast at a given
information time. The DP comes later.

Python reads the files and the command line; everything that costs time runs in
the C++ core (`cpp/`), which Python calls through `ctypes`. The core needs only a
C++17 compiler: `voyage_v2` compiles it on first use, and again whenever a C++
source changes (`python3 -m voyage_v2.build` forces a rebuild). Tested on macOS
(clang), edison (g++ 11, Python 3.10) and shlomo1 (g++ 8.3, Python 3.7).

## Command line

```bash
cd v2
python3 -m voyage_v2 ../pipeline/data/route1_runs.h5 --start "2026-10-14 13:20" --eta 280
python3 -m voyage_v2 route1_runs.h5 --start "2026-10-14 13:20" --eta 280 --arc 100 12 40 --arc 100 12 40 20
```

- `--start`: UTC, `YYYY-MM-DD HH:MM` (or decimal hours, `2026-10-14 13.3`), rounded to the nearest 0.25 h.
- `--eta`: hours after the start, a multiple of 0.25.
- `--arc SUB SOG T [TAU]`: subsegment, SOG [kn], step, information step; prints the conditions,
  SWS, fuel and the runs the weather came from.

It prints the route, the runs loaded and how far their data reaches. If the start
is not covered by the archive's wind or current data it prints an error and exits
with status 1.

## Time

Steps are integers counting quarter hours from the (rounded) start: step 0 is the
start, step `ETA*4` the ETA. An arc's actual step `t` and information step `tau`
satisfy `0 <= tau <= t <= ETA*4`; without `tau` the weather is pseudo real-time
(`tau = t`).

## Weather at (t, tau)

For each grid (wind: ECMWF IFS; current: SMOC) and the subsegment's cell:

1. A run is known from its start time on (zero publication delay). Take the newest
   run issued at or before `tau`.
2. If it does not reach `t`, take the next older run that does (so a short 06/18 UTC
   wind run is extended by the previous 00/12 UTC run).
3. Interpolate between the run's hourly values in east/north components (wind
   direction is "from", current direction is "to").
4. If no run issued by `tau` reaches `t`, hold the latest value before `t`.

Only the runs this rule can select are loaded, and only their hours that bracket
the voyage, on their native grid cells.

## Arc cost

`arc_cost(sub, sog, t, tau=None)` [mt] = FCR(SWS) x length / SOG, where SWS is the
still-water speed that makes good `sog` on the subsegment's bearing in those
conditions (exact closed-form inverse of the paper's speed-loss model, Beaufort
number from the wind speed, WMO table in m/s) and FCR = 0.000706 SWS^3 [mt/h]. The
weather is taken at step `t` for the whole subsegment (subsegments are at most a
few NM long).

An arc whose SOG needs an SWS outside 2-25 kn (hardcoded for now in
`cpp/include/voyage_v2/voyage.hpp`), or that no SWS reaches, costs 9999 mt. NaN
means the archive has no value there.

```python
from voyage_v2 import Voyage, load_voyage_data
voyage = Voyage(load_voyage_data("route1_runs.h5", "2026-10-14 13:20", 280))
voyage.arc_cost(100, 12.0, 40)               # pseudo real-time
voyage.arc_cost(100, 12.0, 40, 20)           # forecast known at step 20
voyage.arc_costs(subs, sogs, ts, taus)       # numpy arrays, one call into C++ (about 170 ns per arc)
voyage.arc_detail(100, 12.0, 40, 20)         # conditions, SWS, FCR, source runs
```

The model on its own: `fcr_from_sog(ship, sog, bearing, Conditions(...))`,
`sws_from_sog`, `sog_from_sws`, `beaufort_number`. In C++: `v2::SpeedModel`
(`physics.hpp`), `v2::WeatherArchive` (`weather.hpp`), `v2::Voyage::arc_cost`
(`voyage.hpp`).

Ship particulars: `config/ship.yaml` (`--ship` to use another file).

## Tests

```bash
cd v2
python3 tests/test_physics.py      # C++ model vs pipeline/shared/physics.py
python3 tests/test_voyage.py       # loading and arc_cost vs a plain-Python statement of the rules
V2_ARCHIVE=../pipeline/data/route1_runs.h5 python3 tests/test_voyage.py   # also on a real archive
```

# Reference — where the weather sampling lives, end to end

Written 2026-10-14 as the starting point for a new sampling strategy. Everything below is read from
the code and from the data files themselves, not from memory.

---

## 1. The chain, in order

```
route config (.yaml)          13 or 11 named waypoints, lat/lon
        ↓   collect/waypoints.py : generate_waypoints(route_config, interval_nm)
sample points                 great-circle interpolation every interval_nm
        ↓   collect/collector.py : fetch_wind_bulk / fetch_marine_bulk
Open-Meteo                    two APIs, 100 points per request
        ↓   shared/hdf5_io.py : append_actual / append_predicted
HDF5                          /metadata, /actual_weather, /predicted_weather
        ↓   dp_rebuild/frame.py : cell_weather_at(d, sample_hour, forecast_hour)
solver                        a sample point's reading IS the subsegment's weather
```

**The decision partition is set at step 2, by `interval_nm`, at collection time.** Nothing downstream
can make it finer; the solver only looks up what was collected.

---

## 2. Where each piece is

| What | File |
|---|---|
| Named route waypoints | `pipeline/config/routes/*.yaml` — 5 routes defined |
| Interpolation to sample points | `pipeline/collect/waypoints.py` — `generate_waypoints`, `interpolate_geodesic` |
| API calls, variables, chunking | `pipeline/collect/collector.py` |
| Per-experiment collection scripts | `pipeline/collect/collect_exp_{a,b,c,d}.py` |
| Historical / archive variants | `pipeline/collect/historical_{year,exp_b}.py` |
| Storage schema | `pipeline/shared/hdf5_io.py` |
| Lookup used by the solver | `pipeline/dp_rebuild/frame.py`, `weather.py` |

---

## 3. The APIs

| | Endpoint | Variables requested |
|---|---|---|
| Wind | `https://api.open-meteo.com/v1/forecast` | `wind_speed_10m`, `wind_direction_10m` |
| Marine | `https://marine-api.open-meteo.com/v1/marine` | `ocean_current_velocity`, `ocean_current_direction`, `wave_height` |
| Archive | `https://archive-api.open-meteo.com/v1/archive` | used only by `historical_year.py` |

Both are requested **hourly** and as a **current** snapshot, `timezone=GMT`, in bulk chunks of
**100 locations** per request to avoid a 414.

Per §5 of the paper: wind resolves to roughly **9 km** on an octahedral reduced-Gaussian grid
(ECMWF IFS), currents to **0.08°** (Météo-France SMOC). Both ≈ 5 NM. **Wave height is collected but
is not an input to any formula** and is not used.

Each collection run writes two records: the **actual** conditions now, and the **predicted** series
out to a 168 h horizon at hourly lead resolution.

---

## 4. How sample points are placed — and the detail that matters

`generate_waypoints(route_config, interval_nm)`:

- interpolates along the **great circle** between consecutive named waypoints
  (`interpolate_geodesic`), not the rhumb line
- per segment: `num_intermediate = int(dist_nm / interval_nm) - 1`

**The division leaves a remainder, so the last interval in each segment is longer than the rest.**
Measured in the actual files:

| | nominal | observed gaps |
|---|---|---|
| Indian Ocean | 25 NM | 25.0, 26.6, 28.0, 31.3, 32.5, 33.2, 35.0, 38.1 |
| North Atlantic | 5 NM | 5.0, 5.1, 5.2, 5.5, 5.6, 6.0, 6.2, 6.7 |

So the sampling is **not uniform even where it is nominally uniform** — which is the same effect Tal
anticipated in his option B ("all the subsegments except the last one in each segment").

**Note a second inconsistency:** the route config interpolates on the **great circle**, while §3 of
the paper says the vessel travels *"along a rhumb line (i.e., at a constant bearing)"*. On these leg
lengths the difference is small, but the two are not the same path and the paper asserts one while
the data uses the other.

---

## 5. What the two collections actually are

Read from the HDF5 root attributes — the files record their own provenance:

| | Indian Ocean | North Atlantic |
|---|---|---|
| File | `experiment_b_138wp_v4_sep07.h5` | `experiment_d_391wp_v4_sep07.h5` |
| Route | Persian Gulf → Strait of Malacca | St. John's → Liverpool |
| `interval_nm` | **25** | **5** |
| `sample_interval_hours` | 6 | 6 |
| Collected | 2026-03-08 | 2026-03-08 |
| Nodes / originals | 131 / 13 | 389 / 11 |
| Length | 3396 NM | 1955 NM |

**On Tal's "leftover from the past": confirmed, with a correction.** The 25 NM was a deliberate
setting at collection time in March, recorded in the file. It is not a config mismatch —
`collect_exp_b.py` carries `interval_nm: 12`, but that script targets a *different* route, the
7-waypoint `persian_gulf_io1` subset, not the 13-waypoint Malacca route the paper uses. So the 25 NM
choice was made once in March and never revisited.

---

## 6. What a new strategy has to decide

| # | Decision | Notes |
|---|---|---|
| 1 | **Interval, or cell-crossing?** | `generate_waypoints` only knows how to space by distance. Cell-crossing placement is **new code**: intersect the route with the 0.08° grid |
| 2 | **Great circle or rhumb line?** | The code does great circle; §3 says rhumb line. Pick one and make both agree |
| 3 | **Segment remainders** | Currently absorbed into the last interval. A new strategy should say what it does instead |
| 4 | **Degenerate subsegments** | Cell-crossing gives 53 pieces under 0.5 NM on the Atlantic, shortest 0.49 NM. Needs a merge rule |
| 5 | **Request volume** | Cell-crossing is ~901 and ~723 points against 131 and 389 today. At 100 locations per request and a 6 h cadence over ~180 days, this is the cost driver |
| 6 | **Keep collecting wave height?** | Collected, stored, never used |

---

## 7. The one thing to settle before writing code

**The partition is fixed at collection time.** Whatever is chosen is baked into the HDF5 and cannot
be refined later without collecting again. That argues for collecting at the finest resolution worth
having — cell crossings, or a uniform interval below the data's own ~5 NM resolution — and
**coarsening in the solver** when a coarser partition is wanted, rather than the reverse.

That would also make the partition an **experimental parameter** instead of a collection artefact,
which is what would let the granularity question be asked properly: the same weather record,
re-partitioned, rather than two routes that differ in sampling and in weather at once.

# HDF5 Weather Data: Actuals vs Forecasts Explained

## Overview

The file `pipeline/data/voyage_weather.h5` stores weather data collected along a maritime route (Persian Gulf to Strait of Malacca, 279 waypoints at 12 nm intervals). Data was collected over **12 sample hours** (hours 0–11), once per hour.

The HDF5 has three tables:

| Table | Rows | Purpose |
|-------|------|---------|
| `metadata` | 279 | GPS coordinates and segment info for each waypoint |
| `actual_weather` | 3,348 | Ground-truth observations (279 nodes x 12 hours) |
| `predicted_weather` | 562,464 | 7-day forecasts issued at each sample hour |

---

## Table 1: `actual_weather` — What Really Happened

Each row records the **current (observed) conditions** at a waypoint at the moment we sampled it.

**Columns:** `node_id`, `sample_hour`, `wind_speed_10m_kmh`, `wind_direction_10m_deg`, `beaufort_number`, `wave_height_m`, `ocean_current_velocity_kmh`, `ocean_current_direction_deg`

### Example: Node 0 (Port A, Persian Gulf)

| sample_hour | wind (km/h) | wind dir | beaufort | wave (m) | current (km/h) | current dir |
|:-----------:|:-----------:|:--------:|:--------:|:--------:|:--------------:|:-----------:|
| 0 | 32.8 | 322° | 5 | 0.42 | 1.30 | 124° |
| 4 | 39.9 | 320° | 6 | 0.78 | 1.21 | 153° |
| 8 | 40.5 | 315° | 6 | 1.02 | 1.71 | 198° |
| 11 | 42.1 | 318° | 6 | 1.32 | 1.26 | 180° |

**Reading this:** At hour 0, Port A had 32.8 km/h wind from the northwest (322°) and calm seas (0.42 m waves). Over the next 11 hours, wind intensified to 42.1 km/h and waves grew to 1.32 m.

### Example: Node 278 (Port B, Strait of Malacca) — the NaN problem

| sample_hour | wind (km/h) | wave (m) | current (km/h) |
|:-----------:|:-----------:|:--------:|:--------------:|
| 0 | 2.9 | NaN | NaN |
| 6 | 1.6 | NaN | NaN |
| 11 | 3.0 | NaN | NaN |

Port B is near the coast, outside the Open-Meteo Marine API coverage. Wind data comes from the land-based Weather API, but wave and current data are unavailable (NaN). Only wind is usable at this waypoint.

---

## Table 2: `predicted_weather` — What the Forecast Said

Each row records what the forecast model **predicted** conditions would be at a waypoint for a specific future hour, as seen from a specific sample time.

**Columns:** `node_id`, `forecast_hour`, `sample_hour`, + same 6 weather fields

### Key concepts

- **`sample_hour`** = When we asked for the forecast (0, 1, 2, ... 11). This is the "observation time" — the moment the API was queried.
- **`forecast_hour`** = The time offset (in hours from a reference point) that the forecast is *about*. Ranges from -18 to +173 (about 7 days ahead). Negative values are hindcasts (recent past conditions from the model).

### Example: Node 0, sample_hour = 0 — a single forecast snapshot

At hour 0, we asked the API: *"What will conditions be at Port A for each of the next ~190 hours?"*

| forecast_hour | wind (km/h) | wave (m) | current (km/h) | Interpretation |
|:-------------:|:-----------:|:--------:|:--------------:|:---------------|
| -12 | 9.4 | 0.04 | 0.97 | Hindcast: 12 hours ago |
| -6 | 12.6 | 0.22 | 0.51 | Hindcast: 6 hours ago |
| 0 | 37.7 | 0.78 | 1.15 | **"Now"** (model's estimate of current conditions) |
| 6 | 41.3 | 0.98 | 1.71 | 6 hours from now |
| 12 | 43.1 | 1.16 | 2.02 | 12 hours from now |
| 24 | 32.4 | 1.16 | 1.66 | Tomorrow |
| 48 | 14.7 | 0.40 | 1.05 | 2 days from now |
| 96 | 17.4 | 0.54 | 0.60 | 4 days from now |
| 168 | 13.1 | — | — | 7 days from now |

**Note:** The forecast's "now" (37.7 km/h) differs from the actual observation (32.8 km/h). The forecast is a model estimate, not a direct measurement, so there is always some error even at `forecast_hour=0`.

---

## How Forecasts Change Over Time (Forecast Drift)

The same future point is predicted differently depending on *when* you ask. As we re-query the API each hour, the forecast for a given target time gets updated with newer model data.

### Example: Node 0, forecast_hour = 24 — predicting "24 hours from reference"

| sample_hour (when asked) | predicted wind (km/h) | predicted wave (m) |
|:------------------------:|:---------------------:|:------------------:|
| 0 | 32.4 | 1.16 |
| 2 | 33.9 | 1.16 |
| 4 | 33.9 | 1.16 |
| 8 | 31.9 | 1.16 |
| 10 | 31.9 | 1.10 |

The wind prediction shifted from 32.4 to 33.9 and back to 31.9 km/h across samples. Wave height also adjusted slightly (1.16 -> 1.10). This drift is what makes the stochastic optimization strategy meaningful — newer forecasts have less error.

### Example: Node 0, forecast_hour = 48 — predicting "48 hours from reference"

| sample_hour (when asked) | predicted wind (km/h) | predicted wave (m) |
|:------------------------:|:---------------------:|:------------------:|
| 0 | 14.7 | 0.40 |
| 2 | 14.8 | 0.40 |
| 8 | 14.6 | 0.40 |
| 10 | 14.6 | 0.42 |

Longer-range forecasts (48h) update more slowly — most model runs agree on the broad trend.

---

## Actual vs Forecast Comparison

To see how accurate the forecast is, compare `actual_weather` at `sample_hour=0` with `predicted_weather` at `sample_hour=0, forecast_hour=0`:

| Node | Location | Actual wind | Predicted wind | Error |
|:----:|:---------|:-----------:|:--------------:|:-----:|
| 0 | Port A (Persian Gulf) | 32.8 km/h | 37.7 km/h | +4.9 |
| 50 | Indian Ocean (600 nm) | 15.4 km/h | 16.1 km/h | +0.7 |
| 100 | Indian Ocean (1200 nm) | 22.1 km/h | 19.9 km/h | -2.2 |
| 150 | Indian Ocean (1800 nm) | 2.2 km/h | 3.1 km/h | +0.9 |
| 200 | Bay of Bengal (2400 nm) | 17.0 km/h | 18.5 km/h | +1.5 |
| 250 | Near Malacca (3000 nm) | 13.2 km/h | 10.0 km/h | -3.2 |

The forecast at `forecast_hour=0` is already imperfect — this is because `actual_weather` uses the real-time "current conditions" endpoint, while `predicted_weather` at hour 0 is the model's estimate at the same time. Typical wind error is 1-5 km/h.

---

## How Each Optimization Strategy Uses This Data

### 1. Static Deterministic (LP)
- Uses **only `actual_weather`** at a single sample hour (e.g., `sample_hour=0`)
- Treats weather as fixed for the entire voyage
- Query: `actual_weather WHERE sample_hour = 0`

### 2. Dynamic Deterministic (DP)
- Uses **`predicted_weather`** from a single forecast origin
- Looks up the forecast for each future hour the ship will encounter
- Query: `predicted_weather WHERE sample_hour = 0 AND forecast_hour = t` (where `t` is the hour the ship reaches each waypoint)

### 3. Dynamic Rolling Horizon (DP)
- Uses **`predicted_weather`** but re-queries at each decision point
- As the ship progresses (hour 0 -> 1 -> 2 -> ...), it uses the *latest* forecast available
- Query: `predicted_weather WHERE sample_hour = current_hour AND forecast_hour = future_t`
- This captures forecast drift — newer predictions are more accurate

---

## Walkthrough: 3 Points Traced Through All 3 Files

To make this concrete, here are 3 waypoints — start, middle, end — traced through every table.

### Step 1: `metadata.csv` — Where is each point?

| | Node 0 | Node 140 | Node 278 |
|--|--------|----------|----------|
| **Name** | Port A (Persian Gulf) | WP7-8_3nm (off India) | Port B (Strait of Malacca) |
| **Lat/Lon** | 24.75, 52.83 | 10.02, 75.58 | 1.81, 100.10 |
| **Distance** | 0 nm (start) | 1,714 nm (halfway) | 3,396 nm (end) |
| **Segment** | 0 | 6 | 11 |
| **Original WP?** | Yes | No (interpolated) | Yes |

This file is static — it tells you *where* each of the 279 waypoints sits on the route. Node 140 is an interpolated point (generated between original waypoints 7 and 8), while nodes 0 and 278 are the original departure/arrival ports.

### Step 2: `actual_weather.csv` — What really happened?

This is the **ground truth**. Every hour (0–11), the API was queried for *current conditions* at every waypoint.

**Node 0 (Port A)** — stormy and getting worse:

| hour | wind (km/h) | BN | wave (m) | current (km/h) |
|:----:|:-----------:|:--:|:--------:|:--------------:|
| 0 | 32.8 | 5 | 0.42 | 1.30 |
| 3 | 35.0 | 5 | 0.42 | 1.30 |
| 6 | 40.1 | 6 | 0.78 | 1.48 |
| 9 | 40.5 | 6 | 1.02 | 1.71 |
| 11 | 42.1 | 6 | 1.32 | 1.26 |

Wind increased +28%, waves tripled over 11 hours. A ship departing at hour 0 would face progressively worse conditions.

**Node 140 (mid-ocean, off India)** — calm area:

| hour | wind (km/h) | BN | wave (m) | current (km/h) |
|:----:|:-----------:|:--:|:--------:|:--------------:|
| 0 | 11.5 | 2 | 0.84 | 0.97 |
| 3 | 4.3 | 1 | 0.84 | 0.97 |
| 6 | 2.5 | 1 | 0.88 | 1.09 |
| 9 | 3.7 | 1 | 0.90 | 1.14 |
| 11 | 6.7 | 2 | 0.86 | 1.14 |

Wind dropped to nearly still, waves barely changed. Easy sailing conditions.

**Node 278 (Port B)** — coastal, near-calm, **but wave/current = NaN**:

| hour | wind (km/h) | BN | wave (m) | current (km/h) |
|:----:|:-----------:|:--:|:--------:|:--------------:|
| 0 | 2.9 | 1 | NaN | NaN |
| 6 | 1.6 | 0 | NaN | NaN |
| 11 | 3.0 | 1 | NaN | NaN |

Only wind data is available — the Marine API has no coverage at this coastal location. This is the known Port B problem; optimizers must handle these NaN values.

### Step 3: `predicted_weather.csv` — What did the forecast say?

This file has **two time dimensions**:
- **`sample_hour`** = when we *asked* (0, 1, 2, ... 11)
- **`forecast_hour`** = what future time the prediction is *about* (-18 to +173)

#### Part A: A single forecast snapshot (asked at hour 0, looking ahead)

| forecast_hour | Node 0 wind | Node 140 wind | Node 278 wind |
|:--:|:--:|:--:|:--:|
| +0h (now) | 37.7 km/h | 6.8 km/h | 1.8 km/h |
| +6h | 41.3 | 7.9 | 1.8 |
| +12h | 43.1 | 5.4 | 2.2 |
| +24h | 32.4 | 2.6 | 1.1 |
| +48h | 14.7 | 5.1 | 3.3 |

At hour 0, the forecast predicts Port A wind will peak around +12h then drop to 14.7 km/h in two days. Mid-ocean (Node 140) stays calm throughout. Port B remains near-still.

#### Part B: Forecast drift — same target, different ask times

For **Node 140**, the prediction for `forecast_hour=24` changes as we re-ask each hour:

| asked at hour | predicted wind (km/h) |
|:--:|:--:|
| 0 | 2.6 |
| 4 | 4.5 |
| 8 | 5.5 |
| 11 | 5.5 |

The forecast model updated — later samples revised the wind prediction upward from 2.6 to 5.5 km/h (a 2x change). This is why the **stochastic strategy** re-plans at each decision point: it uses the *newest* forecast rather than committing to one early prediction that may be wrong.

For **Node 0** at `forecast_hour=24`, the drift is smaller:

| asked at hour | predicted wind (km/h) | predicted wave (m) |
|:--:|:--:|:--:|
| 0 | 32.4 | 1.16 |
| 4 | 33.9 | 1.16 |
| 8 | 31.9 | 1.16 |
| 11 | 31.9 | 1.10 |

### Step 4: Connecting the 3 files — how optimization uses them

**Static Deterministic (LP):**
> "At hour 0, Port A has 32.8 km/h wind and 0.42 m waves. Assume this everywhere, for the whole voyage."
>
> Reads: `actual_weather` WHERE `node_id=0, sample_hour=0` (one row per waypoint)

**Dynamic Deterministic (DP):**
> "The forecast from hour 0 says Port A will have 41.3 km/h wind in 6 hours and 32.4 km/h in 24 hours. Plan the whole voyage using this one forecast."
>
> Reads: `predicted_weather` WHERE `sample_hour=0, forecast_hour=t` (one forecast timeline)

**Dynamic Rolling Horizon (DP):**
> "At hour 0, the forecast says Node 140 will have 2.6 km/h wind at +24h. But by hour 4, the updated forecast says 4.5 km/h. Use the newer one."
>
> Reads: `predicted_weather` WHERE `sample_hour=current_hour, forecast_hour=future_t` (re-plans with latest data)

---

## Data Dimensions Summary

```
actual_weather:    279 nodes  x  12 sample_hours  =  3,348 rows
predicted_weather: 279 nodes  x  12 sample_hours  x  ~168 forecast_hours  =  562,464 rows
metadata:          279 nodes  (static, no time dimension)
```

Collection started: 2026-02-15T17:52 UTC, with samples taken every ~60 minutes over 12 hours.

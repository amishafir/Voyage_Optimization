# HDF5 Weather Data: Actuals vs Forecasts Explained

## Overview

This project stores weather data in HDF5 files collected along maritime routes using the Open-Meteo API. Three datasets exist:

| Dataset | HDF5 File | Route | Nodes | Sample Hours | Size |
|---------|-----------|-------|-------|-------------|------|
| **Original** | `pipeline/data/voyage_weather.h5` | Persian Gulf → Malacca (3,394 nm) | 279 (13 original + 266 interpolated) | 12 (hours 0–11) | 6.5 MB |
| **Experiment A** | `pipeline/data/experiment_a_7wp.h5` | Persian Gulf → Indian Ocean 1 (1,678 nm) | 7 (originals only) | 135 (of 144 planned) | 11 MB |
| **Experiment B** | `pipeline/data/experiment_b_138wp.h5` | Persian Gulf → Indian Ocean 1 (1,678 nm) | 138 (7 original + 131 interpolated) | 134 (of 144 planned) | 43 MB |

**Why three datasets?** The original collection (12 hours) was too short to measure forecast accuracy at long lead times. Experiments A and B use a shorter route that fits within the 168-hour forecast window, with 11x more temporal samples. They form a **2x2 factorial design**: exp_a isolates temporal effects (coarse spatial, many hours), exp_b adds spatial resolution (fine spatial, many hours).

All three files share the same HDF5 schema with three tables:

| Table | Purpose |
|-------|---------|
| `/metadata` | GPS coordinates and segment info for each waypoint |
| `/actual_weather` | Ground-truth observations at each (node, sample_hour) |
| `/predicted_weather` | 7-day forecasts issued at each sample hour |

---

## The Three HDF5 Tables

### Table 1: `/metadata` — Where Each Waypoint Is

Static table. One row per waypoint, no time dimension.

**Columns:** `node_id` (int), `lon` (float), `lat` (float), `waypoint_name` (string), `is_original` (bool), `distance_from_start_nm` (float), `segment` (int)

Example from experiment A (7 nodes):

| node_id | lon | lat | waypoint_name | is_original | distance_from_start_nm | segment |
|:-------:|:---:|:---:|:--------------|:-----------:|:----------------------:|:-------:|
| 0 | 52.83 | 24.75 | Port A (Persian Gulf) | True | 0.0 | 0 |
| 1 | 56.45 | 26.55 | Gulf of Oman | True | 223.7 | 1 |
| 2 | 60.88 | 24.08 | Arabian Sea 1 | True | 506.2 | 2 |
| 3 | 65.73 | 21.73 | Arabian Sea 2 | True | 809.2 | 3 |
| 4 | 69.19 | 17.96 | Arabian Sea 3 | True | 1108.2 | 4 |
| 5 | 72.07 | 14.18 | Arabian Sea 4 | True | 1389.5 | 5 |
| 6 | 75.16 | 10.45 | Indian Ocean 1 | True | 1677.6 | 5 |

In experiment B, 131 interpolated waypoints (at 12 nm spacing) fill the gaps between originals — these have `is_original=False`.

In the original dataset, 266 interpolated waypoints (at ~12 nm spacing) span the full 3,394 nm route across 12 segments.

### Table 2: `/actual_weather` — What Really Happened

Each row records the **current (observed) conditions** at a waypoint at the moment we sampled it.

**Columns:** `node_id`, `sample_hour`, `wind_speed_10m_kmh`, `wind_direction_10m_deg`, `beaufort_number`, `wave_height_m`, `ocean_current_velocity_kmh`, `ocean_current_direction_deg`

**Key details:**
- `sample_hour` is always an integer (0, 1, 2, ...)
- `beaufort_number` is **calculated** from wind speed, not fetched from the API
- The last waypoint on each route may have NaN for marine fields (wave, current) — coastal proximity, outside Marine API coverage

#### Example: Node 0 (Port A), original dataset

| sample_hour | wind (km/h) | wind dir | beaufort | wave (m) | current (km/h) | current dir |
|:-----------:|:-----------:|:--------:|:--------:|:--------:|:--------------:|:-----------:|
| 0 | 32.8 | 322° | 5 | 0.42 | 1.30 | 124° |
| 4 | 39.9 | 320° | 6 | 0.78 | 1.21 | 153° |
| 8 | 40.5 | 315° | 6 | 1.02 | 1.71 | 198° |
| 11 | 42.1 | 318° | 6 | 1.32 | 1.26 | 180° |

Wind intensified from 32.8 to 42.1 km/h and waves grew from 0.42 to 1.32 m over 11 hours.

#### The NaN Problem (Last Waypoint)

The final waypoint on each route (Port B on the original route, Indian Ocean 1 on the short route) may return NaN for wave and current data — the Open-Meteo Marine API has no coverage at coastal locations. Only wind data is usable. Optimizers handle this by clamping NaN to 0.0.

### Table 3: `/predicted_weather` — What the Forecast Said

Each row records what the forecast model **predicted** conditions would be at a waypoint for a specific future hour, as seen from a specific sample time.

**Columns:** `node_id`, `forecast_hour`, `sample_hour`, + same 6 weather fields

**Key concepts:**
- **`sample_hour`** = When we asked for the forecast (0, 1, 2, ...). The moment the API was queried.
- **`forecast_hour`** = The time offset (hours from a reference point) that the forecast is *about*. Ranges from approximately -18 to +173 (~7 days ahead). Negative values are hindcasts.

#### Example: Node 0, sample_hour = 0 — a single forecast snapshot

At hour 0, we asked the API: *"What will conditions be at Port A for each of the next ~190 hours?"*

| forecast_hour | wind (km/h) | wave (m) | current (km/h) | Interpretation |
|:-------------:|:-----------:|:--------:|:--------------:|:---------------|
| -12 | 9.4 | 0.04 | 0.97 | Hindcast: 12 hours ago |
| -6 | 12.6 | 0.22 | 0.51 | Hindcast: 6 hours ago |
| 0 | 37.7 | 0.78 | 1.15 | **"Now"** (model's estimate of current conditions) |
| 6 | 41.3 | 0.98 | 1.71 | 6 hours from now |
| 24 | 32.4 | 1.16 | 1.66 | Tomorrow |
| 48 | 14.7 | 0.40 | 1.05 | 2 days from now |
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

The wind prediction shifted from 32.4 to 33.9 and back to 31.9 km/h across samples. This drift is what makes the rolling horizon strategy meaningful — newer forecasts have less error.

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

Typical wind error at `forecast_hour=0` is 1–5 km/h — the "current conditions" estimate is already imperfect.

---

## Ground-Truth Forecast Error Curve (from Experiment B)

With 134 temporal samples and 138 spatial nodes, experiment B provides enough data to compute forecast accuracy as a function of lead time — matching each prediction against the actual observation at that hour.

| Lead Time | Wind RMSE (km/h) | Wind Bias | Wave RMSE (m) | Current RMSE (km/h) |
|:---------:|:----------------:|:---------:|:-------------:|:-------------------:|
| 0h | 4.13 | +0.20 | 0.052 | 0.358 |
| 24h | 4.84 | +0.59 | 0.072 | 0.382 |
| 48h | 5.63 | +1.21 | 0.076 | 0.406 |
| 72h | 6.13 | +1.31 | 0.094 | 0.448 |
| 96h | 7.65 | +2.86 | 0.114 | 0.460 |
| 120h | 8.34 | +3.15 | 0.118 | 0.443 |
| 133h | 8.40 | +2.67 | 0.113 | 0.503 |

**Key findings:**
- **Wind RMSE doubles** over 133 hours (+103%) — wind is the dominant environmental factor for fuel consumption
- **Wind bias grows** from near-zero to +2.7 km/h — forecasts systematically overpredict wind at long lead times
- **Wave and current errors** are much smaller relative to their mean values
- **Error growth accelerates after 72h**, consistent with atmospheric predictability limits

This curve could only be computed with experiment B's 134 samples. The original 12-hour collection was far too short.

---

## How Each Optimization Strategy Uses This Data

### 1. Static Deterministic (LP)
- Uses **only `actual_weather`** at a single sample hour (e.g., `sample_hour=0`)
- Treats weather as fixed for the entire voyage
- Averages weather across all nodes within each segment (12 or 6 segments)
- Query: `actual_weather WHERE sample_hour = 0`

### 2. Dynamic Deterministic (DP)
- Uses **`predicted_weather`** from a single forecast origin
- Looks up the forecast for each future hour the ship will encounter
- Per-node weather (no segment averaging)
- Query: `predicted_weather WHERE sample_hour = 0 AND forecast_hour = t` (where `t` is the hour the ship reaches each waypoint)

### 3. Dynamic Rolling Horizon (RH)
- Uses **`predicted_weather`** but re-queries at each decision point
- As the ship progresses (hour 0 → 6 → 12 → ...), it uses the *latest* forecast available
- Query: `predicted_weather WHERE sample_hour = current_hour AND forecast_hour = future_t`
- This captures forecast drift — newer predictions are more accurate

---

## Walkthrough: 3 Waypoints Traced Through All Tables

To make this concrete, here are 3 waypoints from the original dataset — start, middle, end — traced through every table.

### Step 1: `metadata` — Where is each point?

| | Node 0 | Node 140 | Node 278 |
|--|--------|----------|----------|
| **Name** | Port A (Persian Gulf) | WP7-8_3nm (off India) | Port B (Strait of Malacca) |
| **Lat/Lon** | 24.75, 52.83 | 10.02, 75.58 | 1.81, 100.10 |
| **Distance** | 0 nm (start) | 1,714 nm (halfway) | 3,396 nm (end) |
| **Segment** | 0 | 6 | 11 |
| **Original WP?** | Yes | No (interpolated) | Yes |

Node 140 is an interpolated point between original waypoints 7 and 8, while nodes 0 and 278 are the departure/arrival ports.

### Step 2: `actual_weather` — What really happened?

**Node 0 (Port A)** — stormy and getting worse:

| hour | wind (km/h) | BN | wave (m) | current (km/h) |
|:----:|:-----------:|:--:|:--------:|:--------------:|
| 0 | 32.8 | 5 | 0.42 | 1.30 |
| 3 | 35.0 | 5 | 0.42 | 1.30 |
| 6 | 40.1 | 6 | 0.78 | 1.48 |
| 9 | 40.5 | 6 | 1.02 | 1.71 |
| 11 | 42.1 | 6 | 1.32 | 1.26 |

**Node 140 (mid-ocean, off India)** — calm area:

| hour | wind (km/h) | BN | wave (m) | current (km/h) |
|:----:|:-----------:|:--:|:--------:|:--------------:|
| 0 | 11.5 | 2 | 0.84 | 0.97 |
| 3 | 4.3 | 1 | 0.84 | 0.97 |
| 6 | 2.5 | 1 | 0.88 | 1.09 |
| 9 | 3.7 | 1 | 0.90 | 1.14 |
| 11 | 6.7 | 2 | 0.86 | 1.14 |

**Node 278 (Port B)** — coastal, near-calm, **wave/current = NaN**:

| hour | wind (km/h) | BN | wave (m) | current (km/h) |
|:----:|:-----------:|:--:|:--------:|:--------------:|
| 0 | 2.9 | 1 | NaN | NaN |
| 6 | 1.6 | 0 | NaN | NaN |
| 11 | 3.0 | 1 | NaN | NaN |

### Step 3: `predicted_weather` — What did the forecast say?

#### Part A: A single forecast snapshot (asked at hour 0, looking ahead)

| forecast_hour | Node 0 wind | Node 140 wind | Node 278 wind |
|:--:|:--:|:--:|:--:|
| +0h (now) | 37.7 km/h | 6.8 km/h | 1.8 km/h |
| +6h | 41.3 | 7.9 | 1.8 |
| +12h | 43.1 | 5.4 | 2.2 |
| +24h | 32.4 | 2.6 | 1.1 |
| +48h | 14.7 | 5.1 | 3.3 |

#### Part B: Forecast drift — same target, different ask times

For **Node 140**, the prediction for `forecast_hour=24` changes as we re-ask each hour:

| asked at hour | predicted wind (km/h) |
|:--:|:--:|
| 0 | 2.6 |
| 4 | 4.5 |
| 8 | 5.5 |
| 11 | 5.5 |

The forecast model revised the wind prediction upward from 2.6 to 5.5 km/h (a 2x change). This is why the rolling horizon strategy re-plans at each decision point.

### Step 4: Connecting the tables — how optimization uses them

**Static Deterministic (LP):**
> "At hour 0, Port A has 32.8 km/h wind and 0.42 m waves. Assume this everywhere, for the whole voyage."
>
> Reads: `actual_weather WHERE sample_hour = 0` (one row per waypoint)

**Dynamic Deterministic (DP):**
> "The forecast from hour 0 says Port A will have 41.3 km/h wind in 6 hours and 32.4 km/h in 24 hours. Plan the whole voyage using this one forecast."
>
> Reads: `predicted_weather WHERE sample_hour = 0 AND forecast_hour = t` (one forecast timeline)

**Dynamic Rolling Horizon (RH):**
> "At hour 0, the forecast says Node 140 will have 2.6 km/h wind at +24h. But by hour 4, the updated forecast says 4.5 km/h. Use the newer one."
>
> Reads: `predicted_weather WHERE sample_hour = current_hour AND forecast_hour = future_t` (re-plans with latest data)

---

## Data Dimensions Summary

### Original Dataset (`voyage_weather.h5`)

```
metadata:          279 nodes  (static)
actual_weather:    279 nodes  ×  12 sample_hours          =      3,348 rows
predicted_weather: 279 nodes  ×  12 sample_hours  × ~168h =    562,464 rows
```

Collection started: 2026-02-15T17:52 UTC, samples every ~60 minutes over 12 hours.

### Experiment A (`experiment_a_7wp.h5`)

```
metadata:            7 nodes  (originals only)
actual_weather:      7 nodes  ×  135 sample_hours          =        945 rows
predicted_weather:   7 nodes  ×  135 sample_hours  × ~168h =    158,760 rows
```

### Experiment B (`experiment_b_138wp.h5`)

```
metadata:          138 nodes  (7 original + 131 interpolated at 12 nm)
actual_weather:    138 nodes  ×  134 sample_hours          =     18,492 rows
predicted_weather: 138 nodes  ×  134 sample_hours  × ~168h =  3,106,656 rows
```

### Comparison

| Metric | Original | Exp A | Exp B |
|--------|----------|-------|-------|
| **Route** | Persian Gulf → Malacca | Persian Gulf → IO1 | Persian Gulf → IO1 |
| **Distance** | 3,394 nm | 1,678 nm | 1,678 nm |
| **Voyage duration** | ~280h | ~140h | ~140h |
| **Original waypoints** | 13 | 7 | 7 |
| **Interpolated waypoints** | 266 | 0 | 131 |
| **Total nodes** | 279 | 7 | 138 |
| **Segments (for LP)** | 12 | 6 | 6 |
| **Sample hours** | 12 | 135 | 134 |
| **Predicted weather rows** | 562K | 159K | 3.1M |
| **Weather regime** | Windier (std 10.63 km/h) | Calmer (std 6.07 km/h) | Calmer (std 6.07 km/h) |
| **NaN gaps** | Port B (WP 13) | None | None |

### 2×2 Factorial Design

Experiments A and B were designed to cleanly separate spatial and temporal effects:

| | Few nodes (coarse) | Many nodes (fine) |
|--|---|---|
| **Actual weather** | A-LP (7 nodes, actual) = baseline | B-LP (138 nodes, actual) |
| **Predicted weather** | A-DP (7 nodes, predicted) | B-DP / B-RH (138 nodes, predicted) |

This decomposition revealed: temporal effect (+3.02 kg) > spatial effect (+2.44 kg), with a -1.43 kg interaction (spatial resolution partially mitigates forecast error).

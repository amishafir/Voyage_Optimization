# Pickle Data — Sample Walkthrough

Companion to `sample_weather_data.csv`. Walks through concrete examples to verify collection logic.

## Collection Metadata

| Field | Value |
|-------|-------|
| Voyage start time | 2026-02-14 14:41:45 |
| Total nodes | 182 (every 20th of 3,388 + all 13 original) |
| Actual sample hours | 12 through 25 (14 samples so far) |
| Predicted forecast range | hour 9 to hour 176 (168-hour API horizon) |
| Runs completed | 26 of 36 |

> **Why do actual hours start at 12, not 0?**
> The script was likely re-initialized after 12 runs (the pickle was reset when the waypoint count changed). Runs 1-12 wrote sample_hours 0-11, then a restart created fresh nodes and resumed from run 13 onward (sample_hour = 12).

---

## Sample 1 — Actual Weather at Port A

Two consecutive hourly snapshots of real-time ("current") conditions at Port A.

| Field | Hour 12 | Hour 13 |
|-------|---------|---------|
| wind_speed_10m_kmh | 8.71 | 12.25 |
| wind_direction_10m_deg | 150.3 | 155.7 |
| beaufort_number | 2 | 3 |
| wave_height_m | 0.04 | 0.04 |
| ocean_current_velocity_kmh | 1.15 | 0.51 |
| ocean_current_direction_deg | 231.3 | 225.0 |

**What this means:** At sample hour 12, the script called the Open-Meteo API with `"current"` parameters for Port A's coordinates (52.83E, 24.75N). The API returned the real-time measured conditions. One hour later (hour 13), it called again — wind picked up from 8.7 to 12.2 km/h, current weakened from 1.15 to 0.51 km/h.

**How it's stored:**
```python
node.Actual_weather_conditions[12] = {wind: 8.71, ...}
node.Actual_weather_conditions[13] = {wind: 12.25, ...}
```

**Optimizer access:**
- Static Deterministic uses ONE of these snapshots (e.g., `Actual[12]`) as the weather for the entire voyage.

---

## Sample 2 — Forecast for Hour 36, Viewed from Different Sample Times

The same future target (hour 36) as predicted by 3 different API calls.

| Field | Predicted[36][12] | Predicted[36][18] | Predicted[36][24] |
|-------|-------------------|-------------------|-------------------|
| wind_speed_10m_kmh | 43.89 | 42.63 | 42.87 |
| wind_direction_10m_deg | 319.0 | 322.5 | 319.1 |
| beaufort_number | 6 | 6 | 6 |
| wave_height_m | 1.52 | 1.52 | 1.48 |
| ocean_current_velocity_kmh | 1.15 | 1.15 | 1.30 |
| ocean_current_direction_deg | 128.7 | 128.7 | 123.7 |

**What this means:** Three forecasts for the same future moment (hour 36), each made at a different time:

- `Predicted[36][12]` — Forecast made 24 hours before target. Predicts wind 43.89 km/h.
- `Predicted[36][18]` — Forecast made 18 hours before target. Updates wind to 42.63 km/h.
- `Predicted[36][24]` — Forecast made 12 hours before target. Further revises to 42.87 km/h, wave drops from 1.52 to 1.48 m.

**Key insight:** As the sample time gets closer to the forecast target, the prediction should generally become more accurate. This is the data that makes the stochastic approach possible — it can re-plan using fresher forecasts.

**How it's stored:**
```python
node.Predicted_weather_conditions[36][12] = {wind: 43.89, ...}  # old forecast
node.Predicted_weather_conditions[36][18] = {wind: 42.63, ...}  # newer forecast
node.Predicted_weather_conditions[36][24] = {wind: 42.87, ...}  # newest forecast
```

---

## Sample 3 — Actual vs Predicted at the Same Hour

Comparing ground truth with forecasts for hour 18 at Port A.

| Source | wind_speed | wind_dir | wave_height |
|--------|-----------|----------|-------------|
| Actual[18] | 7.93 | 230.5 | 0.04 |
| Predicted[18][12] (6h ahead) | 10.74 | 219.6 | 0.18 |
| Predicted[18][18] (nowcast) | 10.88 | 214.2 | 0.18 |

**What this means:** At hour 18, the actual wind was 7.93 km/h. But the forecast made at hour 12 (6 hours earlier) predicted 10.74 km/h — an overestimate of ~35%. Even the "nowcast" from hour 18 predicted 10.88 km/h, still off.

**Why this matters:** This forecast error is exactly what the research measures. The LP optimizer would plan using one static snapshot. The DP deterministic would use `Predicted[future_t][12]` for all future hours. The DP stochastic would re-plan at hour 18 using `Predicted[future_t][18]` — getting a slightly different (hopefully better) forecast for the remaining voyage.

---

## Sample 4 — Mid-Route Node

Node 90 (WP7-8_7nm), coordinates (75.24E, 10.37N), 1,684 nm from Port A — deep in the Indian Ocean.

| Field | Actual[12] |
|-------|-----------|
| wind_speed_10m_kmh | 9.00 |
| wave_height_m | 0.72 |
| ocean_current_velocity_kmh | 0.57 |

**What this means:** Same hour 12, different location. Compared to Port A (wave=0.04m), the open ocean has significantly higher waves (0.72m). This demonstrates that weather varies spatially — static approaches miss this variation.

---

## Sample 5 — Port B NaN Issue

Port B (1.81N, 100.10E) — Strait of Malacca, close to coast.

| Field | Actual[12] | Predicted[36][12] |
|-------|-----------|-------------------|
| wind_speed_10m_kmh | 0.72 | 3.89 |
| wind_direction_10m_deg | 270.0 | 33.7 |
| beaufort_number | 0 | 1 |
| wave_height_m | **NaN** | **NaN** |
| ocean_current_velocity_kmh | **NaN** | **NaN** |
| ocean_current_direction_deg | **NaN** | **NaN** |

**What this means:** The Open-Meteo Marine API has no coverage at this coastal location. Wind data comes from the separate Weather API (which works), but wave height and ocean currents come from the Marine API (which returns NaN here). This affects BOTH actual and predicted marine fields.

**Impact on optimizers:** The last segment (WP12 to Port B) will need special handling — either interpolate from the previous waypoint's marine data or use a sensible default.

---

## Sample 6 — Forecast Evolution Over Time

How the prediction for hour 60 at Port A evolves as new API calls are made.

| Sample Hour | wind_speed | wave_height | Note |
|-------------|-----------|-------------|------|
| 12 | 26.28 | 0.78 | 48h ahead |
| 13 | 26.28 | 0.78 | same API window |
| 14 | 26.28 | 0.78 | same API window |
| 15 | 26.28 | 0.78 | same API window |
| **16** | **26.73** | 0.78 | **API updated** |
| 17 | 26.73 | 0.78 | same API window |
| ... | ... | ... | |
| **21** | **27.70** | 0.78 | **API updated again** |
| 22 | 27.70 | 0.78 | |
| 23 | 27.70 | 0.78 | |
| **24** | 27.70 | **0.70** | **wave updated** |
| 25 | 27.70 | 0.70 | |

**What this means:** The Open-Meteo API updates its forecasts roughly every 3-6 hours (at model run boundaries: 00, 06, 12, 18 UTC). Between updates, consecutive sample hours return the same forecast. When the model reruns, the prediction jumps — here, wind increases from 26.28 to 27.70 km/h over 13 hours of samples.

**Why this pattern is correct:** We sample every hour, but the underlying NWP model only runs 4x/day. The "staircase" pattern of identical values between jumps is expected and confirms the data collection logic is working correctly.

---

## Sample 7 — Three Optimization Strategies Side by Side

All three strategies need weather at Port A for hour 36. Here's what each one reads:

| Strategy | Access Pattern | Wind Speed |
|----------|---------------|------------|
| Static Deterministic | `Actual[12]` | **8.71** km/h |
| Dynamic Deterministic | `Predicted[36][12]` | **43.89** km/h |
| Dynamic Rolling Horizon (at hour 18) | `Predicted[36][18]` | **42.63** km/h |

**What this means:**

1. **Static Det** uses the actual weather from a single snapshot (hour 12). It assumes 8.71 km/h wind for the ENTIRE voyage — clearly wrong for hour 36 when winds will be 43+ km/h.

2. **Dynamic Det** uses the forecast made at voyage start (hour 12) for hour 36. It correctly anticipates strong 43.89 km/h winds, but this forecast was made 24 hours early and may not be perfectly accurate.

3. **Dynamic RH** re-plans at hour 18, using a fresher forecast: 42.63 km/h. This is a 6-hours-newer prediction that may be more accurate (or not — that's what the research will quantify).

**The research question:** How much fuel does each strategy save compared to the others? The gap between Static (8.71) and Dynamic (43.89) is dramatic — the static approach would set engine power for calm conditions and then face near-gale winds. The gap between Dynamic Det (43.89) and Dynamic RH (42.63) is smaller — quantifying whether the re-planning effort is worth it.

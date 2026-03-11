# 5. Experimental Setup

## 5.1 Real-Time Forecast Collection and Optimization Pipeline

A central innovation of this study is the construction of an automated pipeline that collects live NWP forecasts and executes speed optimization on every 6-hour model cycle. No prior maritime speed optimization study has demonstrated a system that ingests real forecast updates aligned to NWP initialization times and re-optimizes in real time. Previous studies either use historical reanalysis data, synthetic weather scenarios, or a single forecast snapshot obtained at departure.

The pipeline operates as follows. An automated collection script runs continuously on a remote server, querying the Open-Meteo API at each GFS initialization cycle (00/06/12/18 UTC, offset by 5 hours for processing delay). At each sample hour, it retrieves both current conditions (actual weather) and the full 168-hour forecast profile for every waypoint along the route. The data are stored in an HDF5 file with three tables: `/metadata` (static GPS coordinates and segment assignment per node), `/actual_weather` (observed conditions at each node and sample hour), and `/predicted_weather` (forecast conditions indexed by node, sample hour, and forecast hour).

This infrastructure serves a dual purpose. First, it provides the rolling horizon optimizer with genuinely fresh forecasts at each decision point — the RH does not simulate re-planning on historical data but operates on forecasts that were actually available at the time of each decision. Second, by collecting both actual and predicted weather at every sample hour, the dataset enables direct measurement of forecast error as a function of lead time — the empirical degradation curves that explain the mechanisms behind the results.

The system was deployed across three university servers to ensure redundancy. Collection for Route 1 accumulated 134 hourly samples (later extended to 171 samples at 6-hour intervals), and Route 2 collection is ongoing with 6-hour NWP-aligned sampling.

## 5.2 Weather Data Sources

Weather data were collected using the Open-Meteo API, which provides free access to operational NWP model outputs. Three parameters are sourced from distinct models:

- **Wind speed and direction (10 m):** NOAA Global Forecast System (GFS), 0.25° resolution, initialized every 6 hours (00/06/12/18 UTC), forecast horizon up to 168 hours.
- **Significant wave height:** Meteo-France MFWAM wave model, 0.25° resolution, initialized twice daily, forecast horizon up to 168 hours.
- **Ocean current velocity and direction:** Meteo-France SMOC ocean model, 0.08° resolution, initialized once daily, forecast horizon up to 168 hours.

The Beaufort number is not provided by the API but is calculated from the 10-metre wind speed using the WMO-standard threshold scale (Eq. 9).

## 5.3 Route 1: Persian Gulf–Indian Ocean (Mild Weather)

Route 1 covers waypoints 1–7 of the full Persian Gulf to Strait of Malacca route, spanning 1,678 nm from the Persian Gulf (24.75°N, 52.83°E) to the Indian Ocean (10.45°N, 75.16°E). The 7 original waypoints are interpolated at 1 nm spacing to produce 138 computational nodes. The LP aggregates these into 6 segments (~23 nodes each); the DP and RH operate at full 138-node resolution.

Data were collected hourly over 134 consecutive hours, yielding 134 actual-weather snapshots and 134 complete 168-hour forecast profiles per node. The voyage duration at the reference speed of 12 kn is approximately 140 hours, meaning the actual-weather record covers 96% of a simulated voyage — near-complete temporal realism.

Weather conditions during the collection period were mild: mean wind speed 17.4 km/h (standard deviation 6.07 km/h), mean wave height 0.82 m (std 0.26 m), and mean ocean current velocity 1.38 km/h. The predominant Beaufort numbers were 3–4, with occasional BN 5. This calm regime means algorithm separations are small in absolute terms but are sufficient to establish the ranking and mechanisms.

## 5.4 Route 2: North Atlantic (Harsh Weather)

Route 2 crosses the North Atlantic storm track from St. John's, Newfoundland (47.57°N, 52.71°W) to Liverpool (53.41°N, 3.01°W), a distance of 1,955 nm. The 11 original waypoints are interpolated at 5 nm spacing to produce 389 computational nodes. The LP uses 10 segments; the DP and RH operate at full resolution.

The route traverses latitudes 47°N–56°N during winter, crossing the most active storm track in the Northern Hemisphere. Expected conditions include Beaufort 8–10, significant wave heights of 4–6 m, and frequent storm systems. The voyage duration at 12 kn is approximately 163 hours (~6.8 days), fitting within the GFS 168-hour forecast horizon. This means the DP has forecast coverage for the entire voyage, isolating the forecast freshness effect: any RH advantage over DP comes purely from using fresher forecasts at each decision point, not from extending beyond the forecast horizon.

Data collection commenced on 25 February 2026 using 6-hour NWP-aligned sampling (Section 5.5). Results for Route 2 are reported in Section 6 once the collection period is complete.

[TABLE: route summary]

## 5.5 NWP Model Cycles and Sampling Alignment

An empirical analysis of the predicted weather data from Route 1 (3.1 million rows) was conducted to determine the actual update frequency of each weather parameter in the Open-Meteo API. The analysis tracked consecutive API calls and measured the fraction that returned identical data.

[TABLE: NWP model cycles]

Wind data updates every 6 hours, matching the GFS initialization cycle at 00/06/12/18 UTC. However, a processing delay of approximately 5 hours was observed empirically: 9 out of 10 detected update events occurred at hours where $\text{sample\_hour} \mod 6 = 5$. At each update, 98–100% of all nodes changed simultaneously, confirming that the updates reflect global model refreshes rather than per-location drift.

At 1-hour collection frequency, 86% of consecutive wind API calls returned identical data. For waves (MFWAM, 12-hour cycle), 94% were identical; for currents (SMOC, 24-hour cycle), 97% were identical. Based on these findings, all subsequent data collection (including Route 2 and the extended Route 1 run) was configured with a 6-hour sampling interval offset by 5 hours from UTC midnight, ensuring every sample captures a fresh GFS wind update with zero information loss and 83% fewer API calls.

This empirical finding has a dual role: it informs the data collection infrastructure (reducing API calls from ~45,000 to ~80 per day for Route 2), and it directly motivates the 6-hour re-planning interval used by the RH optimizer (Contribution 6).

## 5.6 Factorial Design

A 2×2 factorial design isolates the effects of spatial resolution and weather source on fuel outcomes. Experiments A and B share the same route and collection period but differ in spatial resolution:

| | Route 1-Coarse | Route 1 |
|---|---|---|
| Nodes | 7 (originals only) | 138 (interpolated at 1 nm) |
| LP segments | 6 | 6 |
| DP/RH nodes | 7 | 138 |

Each experiment is run under two weather sources: actual (observed) and predicted (forecast from hour 0). The four combinations — (7 nodes, actual), (7 nodes, predicted), (138 nodes, actual), (138 nodes, predicted) — form the factorial, with the RH result at 138 nodes as a fifth comparison point. The decomposition separates:

- **Temporal effect** (forecast error): the fuel penalty from using predicted rather than actual weather, holding spatial resolution constant.
- **Spatial effect** (segment averaging): the fuel penalty from using 7 rather than 138 nodes, holding weather source constant.
- **Interaction**: the extent to which finer spatial resolution mitigates or amplifies forecast error.
- **RH benefit**: the additional improvement from re-planning with fresh forecasts.

This design is reported in Section 6.5.

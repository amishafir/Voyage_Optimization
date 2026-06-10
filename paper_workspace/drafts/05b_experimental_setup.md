<!--
DRAFT — Experimental Setup / Data. Unblocked. Numbers from G1 §E (S-1 forecast error, S-2 NWP)
and thesis_brainstorm weather stats. File named 05b to sit after Mechanism (05); final numbering
at assembly (this is the "Data and experimental design" section, before Results).
Voice: TR-C — past tense for what was done, present for the data source's properties.
-->

# 5b. Data and experimental design

## 5b.1 Weather data

Environmental data were obtained from the Open-Meteo API, which serves operational numerical
weather prediction (NWP) products: 10 m wind from the GFS model, significant wave height from
MFWAM, and ocean-current velocity from SMOC [CITE: Open-Meteo]. Beaufort number was computed from
the 10 m wind speed rather than taken from the API (Section 3). For each route, both the realised
("actual") weather and the forecasts ("predicted") issued at each cycle were collected at every
waypoint, at a 6 h sampling cadence, over approximately 80 days. Data were stored in HDF5 with
separate tables for actual weather, predicted weather, and metadata.

The two routes differ markedly in regime [TABLE: route and weather summary]. Route 1 (Persian
Gulf → Malacca) is mild and relatively uniform; Route 2 (North Atlantic) is harsh, with mean wind
and wave conditions several times larger and far more variable [METHODS: insert per-route wind/wave
mean ± s.d. from data]. This contrast is what allows the convexity prediction — that the SR–Luo
gap scales with weather variability (Section 5) — to be tested across regimes.

## 5b.2 Forecast accuracy (supporting measurement S-1)

Forecast error was measured directly by comparing predicted weather against the actual weather
subsequently observed at the same waypoint and time, as a function of lead time. Wind-speed RMSE
grew systematically with lead time: it approximately doubled over the first 133 h on Route 1
(4.13 → 8.40 km/h) and grew more steeply on the harsher Route 2 (+286 % over 144 h)
[TABLE/FIG: forecast error vs lead time]. This degradation is the reason a rolling-horizon plan,
which commits speeds against forecasts that are later revised, consumes more fuel than the
perfect-foresight oracle (Section 6.2); it is reported here as ground truth, independent of any
optimisation.

## 5b.3 NWP model cycle and the re-plan cadence (supporting measurement S-2)

The 6 h rolling-horizon cadence was set to the underlying model refresh, not tuned. The GFS wind
product refreshes every 6 h; the MFWAM wave and SMOC current products refresh every 12 h and 24 h
respectively. Inspection of the predicted-weather record confirmed this empirically: 86 % of
hourly wind queries returned data identical to the previous hour. Re-planning more frequently than
6 h therefore acts on no new information, which is why the cadence is fixed to the model cycle
[TABLE: NWP model cycles].

## 5b.4 Experimental design

Each route was evaluated as a consecutive-voyage chain of departures spaced one ETA apart
(Section 4.5), yielding 7 voyages on Route 1 and 12 on Route 2 — 19 in total, spanning the
collection window. At each departure, both formulations were run under (i) the perfect-foresight
oracle and (ii) the 6 h rolling horizon, and the rolling-horizon result was compared
against the Naive set-and-forget baseline. Identical departure weather was presented to both
formulations at every voyage, so all reported differences are attributable to the speed-decision
granularity and the information regime, not to sampling.

<!--
COVERAGE: data source (GFS/MFWAM/SMOC, Beaufort computed) ✓ | HDF5 actual/predicted ✓ |
two-regime contrast ✓ | S-1 forecast error (G1 E-1/E-2) ✓ | S-2 NWP cycle + 6h (G1 E-4/E-5) ✓ |
design (19-voyage chain, perfect foresight + RH + Naive) ✓.
Resolves 06_results [SETUP] refs (weather stats, forecast error, 6h/GFS).
OPEN: per-route wind/wave mean±s.d. numbers from data/*.h5 (read-only); confirm Open-Meteo cite.
-->

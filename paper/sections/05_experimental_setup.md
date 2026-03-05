# 5. Experimental Setup

<!-- ~800 words -->

## 5.1 Weather Data Source

<!-- Open-Meteo API: GFS (wind), MFWAM (waves), SMOC (currents) -->
<!-- HDF5 structure: actual_weather, predicted_weather, metadata -->

## 5.2 Experiment B: Persian Gulf to Malacca Strait

<!-- 138 nodes, ~140h, 1,678 nm, mild weather -->
<!-- Wind std 6.07 km/h, wave std 0.26 m -->
<!-- 134 actual weather samples — near-complete temporal coverage -->

## 5.3 Experiment D: St. John's to Liverpool

<!-- 389 nodes, ~163h, 1,955 nm, harsh weather -->
<!-- PLACEHOLDER: weather stats pending analysis -->

## 5.4 NWP Model Cycles and Sampling Alignment

<!-- GFS 6h, MFWAM 12h, SMOC 24h -->
<!-- 6h sampling = zero information loss, 83% fewer API calls -->
<!-- ~5h propagation delay from GFS initialization -->
<!-- TABLE: NWP model cycles — see tables/T05_nwp_cycles.md -->

## 5.5 Factorial Design

<!-- 2x2: (7 nodes vs 138 nodes) x (actual vs predicted weather) -->
<!-- exp_a (7 WP) and exp_b (138 WP) -->
<!-- TABLE: experiment summary — see tables/T03_route_summary.md -->


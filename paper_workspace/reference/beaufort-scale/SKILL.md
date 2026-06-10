# Beaufort Number Calculation

## Key Fact

The Beaufort number is **calculated from wind speed**, not obtained from the Open-Meteo API. The API only provides `wind_speed_10m` (km/h) and `wind_direction_10m` (degrees).

## Conversion Formula

Used in `multi_location_wind_forecasting.py` and test files:

```python
# Convert km/h to m/s, then map to Beaufort scale
wind_speed_ms = wind_speed_kmh / 3.6
```

## Beaufort Thresholds (m/s)

| BN | Upper Bound (m/s) | Description |
|----|-------------------|-------------|
| 0 | < 0.5 | Calm |
| 1 | < 1.6 | Light air |
| 2 | < 3.4 | Light breeze |
| 3 | < 5.5 | Gentle breeze |
| 4 | < 8.0 | Moderate breeze |
| 5 | < 10.8 | Fresh breeze |
| 6 | < 13.9 | Strong breeze |
| 7 | < 17.2 | High wind |
| 8 | < 20.8 | Gale |
| 9 | < 24.5 | Strong gale |
| 10 | < 28.5 | Storm |
| 11 | < 32.7 | Violent storm |
| 12 | >= 32.7 | Hurricane |

## Why This Matters

The research paper uses Beaufort number as an index into **Tables 2-4** for wind and wave resistance correction coefficients. These tables provide `C1`-`C6` coefficients for calculating speed reduction due to environmental conditions.

The `utility_functions.py` module uses these coefficients in:
- Wind resistance calculation
- Wave resistance calculation
- Speed Over Ground (SOG) computation

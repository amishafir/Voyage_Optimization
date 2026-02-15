"""
Beaufort scale conversion.

Ported from: test_files/multi_location_forecast_170wp.py:145-174
"""


def wind_speed_to_beaufort(wind_speed_kmh: float) -> int:
    """
    Convert wind speed (km/h) to Beaufort number (0-12).

    Thresholds in m/s: 0.5, 1.6, 3.4, 5.5, 8.0, 10.8,
                       13.9, 17.2, 20.8, 24.5, 28.5, 32.7

    Args:
        wind_speed_kmh: Wind speed in km/h.

    Returns:
        Beaufort number (int, 0-12).
    """
    wind_speed_ms = wind_speed_kmh / 3.6

    if wind_speed_ms < 0.5:
        return 0
    elif wind_speed_ms < 1.6:
        return 1
    elif wind_speed_ms < 3.4:
        return 2
    elif wind_speed_ms < 5.5:
        return 3
    elif wind_speed_ms < 8.0:
        return 4
    elif wind_speed_ms < 10.8:
        return 5
    elif wind_speed_ms < 13.9:
        return 6
    elif wind_speed_ms < 17.2:
        return 7
    elif wind_speed_ms < 20.8:
        return 8
    elif wind_speed_ms < 24.5:
        return 9
    elif wind_speed_ms < 28.5:
        return 10
    elif wind_speed_ms < 32.7:
        return 11
    else:
        return 12

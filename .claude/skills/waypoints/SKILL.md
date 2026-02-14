# GPS Waypoints Reference

## Route: Port A (Persian Gulf) to Port B (Strait of Malacca)

The 13 waypoints (defining 12 voyage segments) are from Table 8 of the research paper.

| WP | Latitude | Longitude | Location |
|----|----------|-----------|----------|
| 1 | 24.75 | 52.83 | Port A (Persian Gulf) |
| 2 | 26.55 | 56.45 | Gulf of Oman |
| 3 | 24.08 | 60.88 | Arabian Sea |
| 4 | 21.73 | 65.73 | Arabian Sea |
| 5 | 17.96 | 69.19 | Arabian Sea |
| 6 | 14.18 | 72.07 | Arabian Sea |
| 7 | 10.45 | 75.16 | Indian Ocean |
| 8 | 7.00 | 78.46 | Indian Ocean |
| 9 | 5.64 | 82.12 | Bay of Bengal |
| 10 | 4.54 | 87.04 | Indian Ocean |
| 11 | 5.20 | 92.27 | Andaman Sea |
| 12 | 5.64 | 97.16 | Andaman Sea |
| 13 | 1.81 | 100.10 | Port B (Strait of Malacca) |

**Note**: Port B (waypoint 13) may return NaN for marine data as it's close to the coast, outside Open-Meteo Marine API coverage.

## Segment Distances

| Segment | From | To | Distance (nm) |
|---------|------|-----|---------------|
| 1 | Port A | WP 2 | 223.8 |
| 2 | WP 2 | WP 3 | 282.5 |
| 3 | WP 3 | WP 4 | 303.2 |
| 4 | WP 4 | WP 5 | 298.4 |
| 5 | WP 5 | WP 6 | 280.5 |
| 6 | WP 6 | WP 7 | 287.3 |
| 7 | WP 7 | WP 8 | 284.4 |
| 8 | WP 8 | WP 9 | 233.3 |
| 9 | WP 9 | WP 10 | 301.8 |
| 10 | WP 10 | WP 11 | 315.7 |
| 11 | WP 11 | WP 12 | 293.8 |
| 12 | WP 12 | Port B | 288.8 |

**Total voyage distance: 3,393.5 nm**

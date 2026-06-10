"""
Authoritative route waypoints for the Persian Gulf → Strait of Malacca voyage.

Source: paper Table 1 (Norstad-style waypoint table) — supplied by user
2026-04-28. Values match the HDF5's first-waypoint-of-each-segment within
rounding.

13 waypoints, 12 segments. Segment k goes from WP_k → WP_{k+1}.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional


@dataclass(frozen=True)
class Waypoint:
    idx: int            # 1..13
    lat_deg: float      # decimal degrees, +north
    lon_deg: float      # decimal degrees, +east
    name: Optional[str] = None
    # Per-segment attributes (associated with the segment STARTING at this WP,
    # i.e. segment index = idx for waypoints 1..12; WP13 has no outgoing segment).
    segment_to_next: Optional[int] = None  # YAML segment id (1..12)
    heading_deg: Optional[float] = None    # β_i: ship heading on this segment
    distance_nm: Optional[float] = None    # d_i: paper-reported segment length
    sws_kn: Optional[float] = None         # V^i_sw: paper's reported speed-through-water
    fuel_paper_mt: Optional[float] = None  # paper's reported fuel for this segment
    wind_dir_deg: Optional[float] = None   # φ_i
    beaufort: Optional[int] = None         # BN_i
    wave_height_m: Optional[float] = None  # h_i
    current_dir_deg: Optional[float] = None  # γ_i
    current_speed_kn: Optional[float] = None  # V^i_c


# Paper Table 1 — 13 waypoints. Segment i goes WP_i → WP_{i+1}.
# β_i, d_i, V^i_sw, BN_i, φ_i, h_i, γ_i, V^i_c attached to the SEGMENT
# starting at WP_i (i.e. on row i+1 of the paper, but conceptually the
# segment's source waypoint).
WAYPOINTS: List[Waypoint] = [
    Waypoint(idx=1,  lat_deg=24.75, lon_deg=52.83,  name="Port A (Persian Gulf)",
             segment_to_next=1,  heading_deg=61.25,  distance_nm=223.86,
             sws_kn=12.7, fuel_paper_mt=25.54,
             wind_dir_deg=139.0, beaufort=3, wave_height_m=1.0,
             current_dir_deg=245.0, current_speed_kn=0.30),
    Waypoint(idx=2,  lat_deg=26.55, lon_deg=56.45,  name="Gulf of Oman",
             segment_to_next=2,  heading_deg=121.53, distance_nm=282.54,
             sws_kn=12.6, fuel_paper_mt=31.93,
             wind_dir_deg=207.0, beaufort=3, wave_height_m=1.0,
             current_dir_deg=248.0, current_speed_kn=0.72),
    Waypoint(idx=3,  lat_deg=24.08, lon_deg=60.88,
             segment_to_next=3,  heading_deg=117.61, distance_nm=303.18,
             sws_kn=12.7, fuel_paper_mt=32.33,
             wind_dir_deg=9.0,  beaufort=4, wave_height_m=1.5,
             current_dir_deg=158.0, current_speed_kn=0.73),
    Waypoint(idx=4,  lat_deg=21.73, lon_deg=65.73,
             segment_to_next=4,  heading_deg=139.03, distance_nm=298.44,
             sws_kn=12.5, fuel_paper_mt=32.18,
             wind_dir_deg=201.0, beaufort=4, wave_height_m=1.5,
             current_dir_deg=178.0, current_speed_kn=0.21),
    Waypoint(idx=5,  lat_deg=17.96, lon_deg=69.19,
             segment_to_next=5,  heading_deg=143.63, distance_nm=280.51,
             sws_kn=12.3, fuel_paper_mt=31.66,
             wind_dir_deg=88.0, beaufort=5, wave_height_m=2.5,
             current_dir_deg=135.0, current_speed_kn=0.49),
    Waypoint(idx=6,  lat_deg=14.18, lon_deg=72.07,
             segment_to_next=6,  heading_deg=140.84, distance_nm=287.34,
             sws_kn=12.2, fuel_paper_mt=32.60,
             wind_dir_deg=86.0, beaufort=4, wave_height_m=1.5,
             current_dir_deg=113.0, current_speed_kn=0.22),
    Waypoint(idx=7,  lat_deg=10.45, lon_deg=75.16,
             segment_to_next=7,  heading_deg=136.42, distance_nm=284.40,
             sws_kn=12.2, fuel_paper_mt=32.00,
             wind_dir_deg=353.0, beaufort=3, wave_height_m=1.0,
             current_dir_deg=338.0, current_speed_kn=0.54),
    Waypoint(idx=8,  lat_deg=7.00,  lon_deg=78.46,
             segment_to_next=8,  heading_deg=110.37, distance_nm=233.25,
             sws_kn=12.2, fuel_paper_mt=30.74,
             wind_dir_deg=35.0, beaufort=5, wave_height_m=2.5,
             current_dir_deg=290.0, current_speed_kn=1.25),
    Waypoint(idx=9,  lat_deg=5.64,  lon_deg=82.12,
             segment_to_next=9,  heading_deg=102.57, distance_nm=301.80,
             sws_kn=12.8, fuel_paper_mt=33.72,
             wind_dir_deg=269.0, beaufort=4, wave_height_m=1.5,
             current_dir_deg=270.0, current_speed_kn=0.28),
    Waypoint(idx=10, lat_deg=4.54,  lon_deg=87.04,
             segment_to_next=10, heading_deg=82.83,  distance_nm=315.70,
             sws_kn=12.6, fuel_paper_mt=32.32,
             wind_dir_deg=174.0, beaufort=3, wave_height_m=1.0,
             current_dir_deg=93.0, current_speed_kn=0.72),
    Waypoint(idx=11, lat_deg=5.20,  lon_deg=92.27,
             segment_to_next=11, heading_deg=84.87,  distance_nm=293.80,
             sws_kn=12.7, fuel_paper_mt=34.41,
             wind_dir_deg=60.0, beaufort=1, wave_height_m=0.1,
             current_dir_deg=185.0, current_speed_kn=0.62),
    Waypoint(idx=12, lat_deg=5.64,  lon_deg=97.16,
             segment_to_next=12, heading_deg=142.39, distance_nm=288.42,
             sws_kn=12.3, fuel_paper_mt=31.57,
             wind_dir_deg=315.0, beaufort=3, wave_height_m=1.0,
             current_dir_deg=90.0, current_speed_kn=0.30),
    Waypoint(idx=13, lat_deg=1.81,  lon_deg=100.10, name="Port B (Strait of Malacca)"),
]


def total_paper_distance_nm() -> float:
    """Sum of paper-reported segment lengths (3393.24 nm for this voyage)."""
    return sum(w.distance_nm for w in WAYPOINTS if w.distance_nm is not None)


def segment_endpoints(seg_id: int) -> tuple[Waypoint, Waypoint]:
    """Return (WP_seg, WP_seg+1) for the given segment id (1..12)."""
    if not 1 <= seg_id <= 12:
        raise ValueError(f"segment id must be 1..12, got {seg_id}")
    return WAYPOINTS[seg_id - 1], WAYPOINTS[seg_id]

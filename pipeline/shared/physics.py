"""
Physics functions for ship speed optimization.

Ported from: Linear programing/utility_functions.py
Based on: "Ship Speed Optimization Considering Ocean Currents
           to Enhance Environmental Sustainability in Maritime Shipping"

All functions use explicit float parameters (not weather-dict style).
The pipeline's transform layers unpack dicts before calling physics.
"""

import math
from typing import Optional, Dict, List

# Constants from the paper and maritime engineering
GRAVITY = 9.81          # m/s²
WATER_DENSITY = 1025.0  # kg/m³ (seawater)
AIR_DENSITY = 1.225     # kg/m³
KINEMATIC_VISCOSITY = 1.19e-6  # m²/s (seawater at 15°C)
CO2_FACTOR = 3.17       # mt CO2 per mt fuel
KNOTS_TO_MS = 0.5144    # knots -> m/s
MS_TO_KNOTS = 1.944     # m/s -> knots


# ---------------------------------------------------------------------------
# Paper Equation (9): Weather direction angle
# ---------------------------------------------------------------------------

def calculate_weather_direction_angle(wind_direction: float, ship_heading: float) -> float:
    """
    Weather direction angle (θ) relative to ship's bow.

    Equation (9): θ = |φ - α|, normalized to [0, π].

    Args:
        wind_direction: Wind direction in radians (from north).
        ship_heading:   Ship heading in radians (from north).

    Returns:
        Weather direction angle in radians [0, π].
    """
    theta_rad = wind_direction - ship_heading
    if theta_rad > math.pi:
        theta_rad -= 2 * math.pi
    elif theta_rad < -math.pi:
        theta_rad += 2 * math.pi
    return abs(theta_rad)


# ---------------------------------------------------------------------------
# Froude number
# ---------------------------------------------------------------------------

def calculate_froude_number(ship_speed_ms: float, ship_length: float) -> float:
    """
    Froude number: Fn = V / sqrt(g * L).

    Args:
        ship_speed_ms: Ship speed in m/s.
        ship_length:   Ship length in meters.

    Returns:
        Froude number (dimensionless).
    """
    return ship_speed_ms / math.sqrt(GRAVITY * ship_length)


# ---------------------------------------------------------------------------
# Paper Table 2: Direction reduction coefficient (Cβ)
# ---------------------------------------------------------------------------

def calculate_direction_reduction_coefficient(theta_deg: float, beaufort_scale: int) -> float:
    """
    Direction reduction coefficient (Cβ) from Table 2.

    Args:
        theta_deg:      Weather direction angle in degrees [0, 180].
        beaufort_scale: Beaufort number [0-12].

    Returns:
        Cβ (≥ 0.1).
    """
    BN = beaufort_scale
    if 0 <= theta_deg <= 30:
        c_beta = 2.0
    elif 30 < theta_deg <= 60:
        c_beta = 1.7 - 0.03 * (BN - 4) ** 2
    elif 60 < theta_deg <= 150:
        c_beta = 0.9 - 0.06 * (BN - 6) ** 2
    else:
        c_beta = 0.4 - 0.03 * (BN - 8) ** 2
    return max(c_beta, 0.1)


# ---------------------------------------------------------------------------
# Paper Table 3: Speed reduction coefficient (CU)
# ---------------------------------------------------------------------------

def calculate_speed_reduction_coefficient(
    froude_number: float,
    block_coefficient: float,
    loading_condition: str = "normal",
) -> float:
    """
    Speed reduction coefficient (CU) from Table 3.

    Args:
        froude_number:     Froude number (dimensionless).
        block_coefficient: Block coefficient Cb.
        loading_condition: 'normal' or 'ballast'.

    Returns:
        CU (≥ 0.1).
    """
    cb = block_coefficient
    Fn = froude_number

    if cb <= 0.55:
        c_u = 1.7 - 1.4 * Fn - 7.4 * Fn ** 2
    elif cb <= 0.60:
        c_u = 2.2 - 2.5 * Fn - 9.7 * Fn ** 2
    elif cb <= 0.65:
        c_u = 2.6 - 3.7 * Fn - 11.6 * Fn ** 2
    elif cb <= 0.70:
        c_u = 3.1 - 5.3 * Fn - 12.4 * Fn ** 2
    elif cb <= 0.75:
        if loading_condition == "normal":
            c_u = 2.4 - 10.6 * Fn - 9.5 * Fn ** 2
        else:
            c_u = 2.6 - 12.5 * Fn - 13.5 * Fn ** 2
    elif cb <= 0.80:
        if loading_condition == "normal":
            c_u = 2.6 - 13.1 * Fn - 15.1 * Fn ** 2
        else:
            c_u = 3.0 - 16.3 * Fn - 21.6 * Fn ** 2
    else:
        if loading_condition == "normal":
            c_u = 3.1 - 18.7 * Fn + 28.0 * Fn ** 2
        else:
            c_u = 3.4 - 20.9 * Fn + 31.8 * Fn ** 2

    return max(c_u, 0.1)


# ---------------------------------------------------------------------------
# Paper Table 4: Ship form coefficient (CForm)
# ---------------------------------------------------------------------------

def calculate_ship_form_coefficient(
    beaufort_scale: int,
    displacement_volume: float,
    loading_condition: str = "normal",
) -> float:
    """
    Ship form coefficient (CForm) from Table 4.

    Args:
        beaufort_scale:      Beaufort number [0-12].
        displacement_volume: Displacement volume in m³.
        loading_condition:   'normal' or 'ballast'.

    Returns:
        CForm.
    """
    BN = beaufort_scale
    displacement_term = displacement_volume ** (2 / 3)

    if loading_condition == "normal":
        return 0.5 * BN + (BN ** 6.5) / (22 * displacement_term)
    else:
        return 0.7 * BN + (BN ** 6.5) / (22 * displacement_term)


# ---------------------------------------------------------------------------
# Paper Equation (7): Speed loss percentage
# ---------------------------------------------------------------------------

def calculate_speed_loss_percentage(c_beta: float, c_u: float, c_form: float) -> float:
    """
    Speed loss percentage: ΔV/Vsw × 100% = Cβ × CU × CForm.

    Clamped to [0, 50]%.

    Returns:
        Speed loss percentage.
    """
    return min(max(c_beta * c_u * c_form, 0), 50)


# ---------------------------------------------------------------------------
# Paper Equation (8): Weather-corrected speed
# ---------------------------------------------------------------------------

def calculate_weather_corrected_speed(ship_speed: float, speed_loss_percent: float) -> float:
    """
    Weather-corrected speed: Vw = Vsw × (1 - ΔV/Vsw/100).

    Minimum 1.0 knots.

    Args:
        ship_speed:         SWS in knots.
        speed_loss_percent: Speed loss [0-50]%.

    Returns:
        Weather-corrected speed in knots (≥ 1.0).
    """
    vw = ship_speed * (1 - speed_loss_percent / 100)
    return max(vw, 1.0)


# ---------------------------------------------------------------------------
# Paper Equations (14-16): SOG vector synthesis
# ---------------------------------------------------------------------------

def calculate_sog_vector_synthesis(
    weather_corrected_speed: float,
    ship_heading: float,
    ocean_current: float,
    current_direction: float,
) -> float:
    """
    SOG via vector synthesis.

    Eq 14: Vx = Vw·sin(α) + Vc·sin(γ)
    Eq 15: Vy = Vw·cos(α) + Vc·cos(γ)
    Eq 16: Vg = sqrt(Vx² + Vy²)

    All angles in radians, speeds in knots.

    Returns:
        Speed over ground (knots).
    """
    vg_x = weather_corrected_speed * math.sin(ship_heading) + ocean_current * math.sin(current_direction)
    vg_y = weather_corrected_speed * math.cos(ship_heading) + ocean_current * math.cos(current_direction)
    return math.sqrt(vg_x ** 2 + vg_y ** 2)


# ---------------------------------------------------------------------------
# Composite: Speed Over Ground (8-step)
# ---------------------------------------------------------------------------

def calculate_speed_over_ground(
    ship_speed: float,
    ocean_current: float,
    current_direction: float = 0.0,
    ship_heading: float = 0.0,
    wind_direction: float = 0.0,
    beaufort_scale: int = 3,
    wave_height: float = 1.0,
    ship_parameters: Optional[Dict] = None,
) -> float:
    """
    Speed Over Ground using the full Speed Correction Model.

    Steps 1-8 from the research paper, plus BN≥5 3.5% reduction.

    Args:
        ship_speed:        SWS in knots.
        ocean_current:     Current speed in knots.
        current_direction: Current direction (radians, from north).
        ship_heading:      Ship heading (radians, from north).
        wind_direction:    Wind direction (radians, from north).
        beaufort_scale:    Beaufort number (0-12).
        wave_height:       Significant wave height (meters).
        ship_parameters:   Ship characteristics dict (optional, has defaults).

    Returns:
        SOG in knots.
    """
    if ship_parameters is None:
        ship_parameters = {
            "length": 200.0,
            "beam": 32.0,
            "draft": 12.0,
            "displacement": 50000.0,
            "block_coefficient": 0.75,
            "wetted_surface": 8000.0,
            "rated_power": 10000.0,
            "max_speed": 14.0,
            "min_speed": 8.0,
        }

    # Step 1: Weather direction angle (Eq 9)
    weather_angle_rad = calculate_weather_direction_angle(wind_direction, ship_heading)
    weather_angle_deg = math.degrees(weather_angle_rad)

    # Step 2: Froude number
    ship_speed_ms = ship_speed * KNOTS_TO_MS
    froude_number = calculate_froude_number(ship_speed_ms, ship_parameters["length"])

    # Step 3: Direction reduction coefficient (Table 2)
    c_beta = calculate_direction_reduction_coefficient(weather_angle_deg, beaufort_scale)

    # Step 4: Speed reduction coefficient (Table 3)
    c_u = calculate_speed_reduction_coefficient(
        froude_number, ship_parameters["block_coefficient"], "normal"
    )

    # Step 5: Ship form coefficient (Table 4)
    displacement_volume = ship_parameters["displacement"] * 1000 / 1025  # tonnes -> m³
    c_form = calculate_ship_form_coefficient(beaufort_scale, displacement_volume, "normal")

    # Step 6: Speed loss percentage (Eq 7)
    speed_loss_percent = calculate_speed_loss_percentage(c_beta, c_u, c_form)

    # Step 7: Weather-corrected speed (Eq 8)
    weather_corrected_speed = calculate_weather_corrected_speed(ship_speed, speed_loss_percent)

    # Step 8: SOG via vector synthesis (Eqs 14-16)
    sog = calculate_sog_vector_synthesis(
        weather_corrected_speed, ship_heading, ocean_current, current_direction
    )

    # Post-processing: BN ≥ 5 additional 3.5% reduction
    if beaufort_scale >= 5:
        sog *= 0.965

    return sog


# ---------------------------------------------------------------------------
# Fuel Consumption Rate: FCR = 0.000706 × SWS³
# ---------------------------------------------------------------------------

def calculate_fuel_consumption_rate(ship_speed: float) -> float:
    """
    Fuel consumption rate (mt/hour).

    FCR = 0.000706 × SWS³.

    Args:
        ship_speed: SWS in knots.

    Returns:
        FCR in mt/hour (≥ 0.1).
    """
    return max(0.000706 * ship_speed ** 3, 0.1)


# ---------------------------------------------------------------------------
# Travel time
# ---------------------------------------------------------------------------

def calculate_travel_time(distance: float, speed_over_ground: float) -> float:
    """
    Travel time = distance / SOG.

    Args:
        distance:           Distance in nautical miles.
        speed_over_ground: SOG in knots.

    Returns:
        Travel time in hours (inf if SOG ≤ 0).
    """
    if speed_over_ground <= 0:
        return float("inf")
    return distance / speed_over_ground


# ---------------------------------------------------------------------------
# Total fuel consumption
# ---------------------------------------------------------------------------

def calculate_total_fuel_consumption(
    distance: float, fuel_consumption_rate: float, speed_over_ground: float
) -> float:
    """
    Total fuel = FCR × travel_time.

    Args:
        distance:              Distance in nautical miles.
        fuel_consumption_rate: FCR in mt/hour.
        speed_over_ground:     SOG in knots.

    Returns:
        Total fuel in mt.
    """
    return fuel_consumption_rate * calculate_travel_time(distance, speed_over_ground)


# ---------------------------------------------------------------------------
# CO2 emissions
# ---------------------------------------------------------------------------

def calculate_co2_emissions(fuel_consumption: float) -> float:
    """
    CO2 emissions = fuel × 3.17.

    Args:
        fuel_consumption: Fuel in mt.

    Returns:
        CO2 in mt.
    """
    return fuel_consumption * CO2_FACTOR


# ---------------------------------------------------------------------------
# Inverse: SWS from SOG (binary search)
# Ported from: Dynamic speed optimization/speed_control_optimizer.py:399-515
# ---------------------------------------------------------------------------

def calculate_sws_from_sog(
    target_sog: float,
    weather: Dict,
    ship_heading_deg: float,
    ship_parameters: Optional[Dict] = None,
    tolerance: float = 0.001,
    max_iterations: int = 50,
) -> float:
    """
    Find the SWS required to achieve a target SOG via binary search.

    This is the inverse of calculate_speed_over_ground.

    Args:
        target_sog:      Desired SOG in knots.
        weather:         Dict with standard field names:
                         wind_speed_10m_kmh, wind_direction_10m_deg,
                         beaufort_number, wave_height_m,
                         ocean_current_velocity_kmh, ocean_current_direction_deg.
        ship_heading_deg: Ship heading in degrees.
        ship_parameters:  Ship characteristics dict (optional, has defaults).
        tolerance:        Convergence tolerance in knots (default 0.001).
        max_iterations:   Max binary search iterations (default 50).

    Returns:
        Required SWS in knots, or target_sog as fallback if search fails.
    """
    # Convert weather dict to physics function inputs
    wind_dir_rad = math.radians(weather.get("wind_direction_10m_deg", 0.0))
    beaufort = int(weather.get("beaufort_number", 3))
    wave_height = weather.get("wave_height_m", 1.0)
    current_speed_knots = weather.get("ocean_current_velocity_kmh", 0.0) / 1.852
    current_dir_rad = math.radians(weather.get("ocean_current_direction_deg", 0.0))
    heading_rad = math.radians(ship_heading_deg)

    def _sog_at(sws):
        return calculate_speed_over_ground(
            ship_speed=sws,
            ocean_current=current_speed_knots,
            current_direction=current_dir_rad,
            ship_heading=heading_rad,
            wind_direction=wind_dir_rad,
            beaufort_scale=beaufort,
            wave_height=wave_height,
            ship_parameters=ship_parameters,
        )

    # Binary search bounds
    min_sws, max_sws = 5.0, 20.0

    # Expand bounds if target is outside range
    min_sog = _sog_at(min_sws)
    max_sog = _sog_at(max_sws)

    if target_sog < min_sog:
        max_sws = min_sws
        min_sws = 1.0
    elif target_sog > max_sog:
        min_sws = max_sws
        max_sws = 30.0

    best_sws = None
    best_error = float("inf")

    for _ in range(max_iterations):
        test_sws = (min_sws + max_sws) / 2.0
        calculated_sog = _sog_at(test_sws)
        error = abs(calculated_sog - target_sog)

        if error < best_error:
            best_error = error
            best_sws = test_sws

        if error < tolerance:
            break

        if calculated_sog < target_sog:
            min_sws = test_sws
        else:
            max_sws = test_sws

        if abs(max_sws - min_sws) < 0.0001:
            break

    if best_sws is not None and best_error < 0.1:
        return best_sws
    return target_sog


# ---------------------------------------------------------------------------
# Ship heading from GPS coordinates
# ---------------------------------------------------------------------------

def calculate_ship_heading(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Initial bearing (heading) from point 1 to point 2.

    Uses the forward azimuth formula:
        θ = atan2(sin(Δλ)·cos(φ2), cos(φ1)·sin(φ2) - sin(φ1)·cos(φ2)·cos(Δλ))

    Args:
        lat1: Latitude of origin in degrees.
        lon1: Longitude of origin in degrees.
        lat2: Latitude of destination in degrees.
        lon2: Longitude of destination in degrees.

    Returns:
        Bearing in degrees [0, 360).
    """
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    d_lambda = math.radians(lon2 - lon1)

    x = math.sin(d_lambda) * math.cos(phi2)
    y = math.cos(phi1) * math.sin(phi2) - math.sin(phi1) * math.cos(phi2) * math.cos(d_lambda)

    bearing = math.degrees(math.atan2(x, y))
    return bearing % 360


# ---------------------------------------------------------------------------
# Load ship parameters from config
# ---------------------------------------------------------------------------

def load_ship_parameters(config: dict) -> Dict:
    """
    Build ship_parameters dict from experiment.yaml config.

    Maps config keys (with units) to the names expected by
    calculate_speed_over_ground().

    Args:
        config: Full experiment config dict.

    Returns:
        Dict with keys: length, beam, draft, displacement,
        block_coefficient, rated_power, max_speed, min_speed.
    """
    ship = config["ship"]
    speed_range = ship["speed_range_knots"]
    return {
        "length": ship["length_m"],
        "beam": ship["beam_m"],
        "draft": ship["draft_m"],
        "displacement": ship["displacement_tonnes"],
        "block_coefficient": ship["block_coefficient"],
        "rated_power": ship["rated_power_kw"],
        "max_speed": speed_range[1],
        "min_speed": speed_range[0],
    }

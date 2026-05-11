#pragma once
#include "common.hpp"

// Physical constants
static constexpr double GRAVITY            = 9.81;
static constexpr double WATER_DENSITY      = 1025.0;
static constexpr double AIR_DENSITY        = 1.225;
static constexpr double KINEMATIC_VISCOSITY = 1.19e-6;
static constexpr double CO2_FACTOR         = 3.17;
static constexpr double KNOTS_TO_MS        = 0.5144;
static constexpr double MS_TO_KNOTS        = 1.944;

// Paper Eq (9): weather direction angle [0, π]
double calculate_weather_direction_angle(double wind_dir_rad, double ship_heading_rad);

// Froude number
double calculate_froude_number(double ship_speed_ms, double ship_length);

// Paper Table 2: Cβ
double calculate_direction_reduction_coefficient(double theta_deg, int bn);

// Paper Table 3: CU
double calculate_speed_reduction_coefficient(double froude, double block_coef,
                                              bool ballast = false);

// Paper Table 4: CForm
double calculate_ship_form_coefficient(int bn, double displacement_vol,
                                        bool ballast = false);

// Paper Eq (7): speed loss %
double calculate_speed_loss_percentage(double c_beta, double c_u, double c_form);

// Paper Eq (8): weather-corrected speed (min 1 kn)
double calculate_weather_corrected_speed(double sws, double speed_loss_pct);

// Paper Eqs (14-16): SOG vector synthesis
double calculate_sog_vector_synthesis(double vw, double heading_rad,
                                       double current_kn, double current_dir_rad);

// Full 8-step SOG from SWS (angles in radians, speeds in knots)
double calculate_speed_over_ground(double sws, double ocean_current_kn,
                                    double current_dir_rad, double heading_rad,
                                    double wind_dir_rad, int bn,
                                    double wave_height_m,
                                    const ShipParameters& params);

// Convenience overload accepting a WeatherDict (angles in degrees)
double calculate_speed_over_ground(double sws, const WeatherDict& weather,
                                    double heading_deg,
                                    const ShipParameters& params);

// FCR = 0.000706 × SWS³  (mt/h, min 0.1)
double calculate_fuel_consumption_rate(double sws);

// Binary-search inverse: SWS → target_sog
double calculate_sws_from_sog(double target_sog, const WeatherDict& weather,
                               double heading_deg, const ShipParameters& params,
                               double tolerance = 0.001, int max_iter = 50);

// Beaufort number from wind speed (km/h)
int wind_speed_to_beaufort(double wind_kmh);

#!/usr/bin/env python3
"""
Interactive SWS Calculator

This script provides an interactive interface for calculating Ship Speed in Still Water (SWS)
from a desired Speed Over Ground (SOG) using the utility functions and voyage data from Table 8.

This is the inverse function of the SOG calculator - given a desired SOG, it finds the required SWS.

User inputs:
- Desired Speed Over Ground (SOG) in knots
- Segment number (1-12)

Output:
- Required SWS using paper-exact methodology
- Detailed breakdown of environmental conditions
- Calculation parameters used

Author: Interactive SWS Calculator
Date: 2025
"""

import sys
import math
from typing import Optional, Tuple

def get_user_input():
    """
    Get user input for SOG and segment number with validation.
    
    Returns:
        tuple: (sog, segment_id) or (None, None) if user wants to exit
    """
    print("🚢 Interactive SWS Calculator")
    print("=" * 50)
    print("Calculate Ship Speed in Still Water (SWS) from desired SOG")
    print("Using paper-exact methodology (inverse function)")
    print("Based on Table 8 data from the research paper")
    print()
    
    while True:
        try:
            # Get SOG input
            sog_input = input("Enter desired Speed Over Ground (SOG) in knots [8-15] (or 'q' to quit): ").strip()
            
            if sog_input.lower() in ['q', 'quit', 'exit']:
                return None, None
            
            sog = float(sog_input)
            
            # Validate SOG range
            if sog < 8.0 or sog > 15.0:
                print("⚠️  Warning: SOG should typically be between 8-15 knots for container ships")
                confirm = input("Continue with this speed? (y/n): ").strip().lower()
                if confirm not in ['y', 'yes']:
                    continue
            
            # Get segment input
            segment_input = input("Enter Segment number [1-12]: ").strip()
            segment_id = int(segment_input)
            
            # Validate segment range
            if segment_id < 1 or segment_id > 12:
                print("❌ Error: Segment number must be between 1 and 12")
                continue
            
            return sog, segment_id
            
        except ValueError:
            print("❌ Error: Please enter valid numbers")
            continue
        except KeyboardInterrupt:
            print("\n\n👋 Goodbye!")
            return None, None

def display_segment_info(segment_id: int):
    """
    Display detailed information about the selected segment.
    
    Args:
        segment_id: Segment number (1-12)
    """
    try:
        from voyage_data import get_segment_info
        
        segment_info = get_segment_info(segment_id)
        
        print(f"\n📊 Segment {segment_id} Environmental Conditions:")
        print("=" * 45)
        print(f"Distance: {segment_info['distance_nm']:.1f} nautical miles")
        print(f"Ship Heading (βᵢ): {segment_info['ship_heading_degrees']:.1f}°")
        print(f"Wind Direction (φᵢ): {segment_info['wind_direction_degrees']:.0f}°")
        print(f"Beaufort Scale: {segment_info['beaufort_scale']}")
        print(f"Wave Height: {segment_info['wave_height_m']:.1f} m")
        print(f"Current Speed: {segment_info['current_speed_knots']:.2f} knots")
        print(f"Current Direction (γᵢ): {segment_info['current_direction_degrees']:.0f}°")
        
        # Calculate weather direction angle
        weather_angle = abs(segment_info['wind_direction_degrees'] - segment_info['ship_heading_degrees'])
        if weather_angle > 180:
            weather_angle = 360 - weather_angle
        
        print(f"Weather Direction Angle: {weather_angle:.1f}°")
        
        # Determine sea conditions
        beaufort = segment_info['beaufort_scale']
        if beaufort <= 2:
            sea_condition = "Calm"
        elif beaufort <= 4:
            sea_condition = "Moderate"
        elif beaufort <= 6:
            sea_condition = "Rough"
        else:
            sea_condition = "Very Rough"
        
        print(f"Sea Condition: {sea_condition}")
        
    except ImportError:
        print("⚠️  Warning: voyage_data module not found")
    except Exception as e:
        print(f"⚠️  Warning: Could not load segment info: {e}")

def calculate_sws_from_sog(target_sog: float, segment_id: int, tolerance: float = 0.001, max_iterations: int = 100) -> Tuple[Optional[float], dict]:
    """
    Calculate the required SWS to achieve a target SOG using iterative root finding.
    
    This function uses binary search to find the SWS that produces the target SOG.
    
    Args:
        target_sog: Desired Speed Over Ground (knots)
        segment_id: Segment number (1-12)
        tolerance: Convergence tolerance for SOG difference (default: 0.001 knots)
        max_iterations: Maximum number of iterations (default: 100)
    
    Returns:
        tuple: (calculated_sws, calculation_info) or (None, {}) if error
    """
    try:
        from utility_functions import calculate_sog_from_voyage_data
        from voyage_data import SHIP_PARAMETERS
        
        # Get segment data for weather conditions
        from voyage_data import get_segment_for_utility_functions
        
        # Use a test SWS to get segment data structure
        test_sws = 10.0
        segment_data = get_segment_for_utility_functions(segment_id, test_sws)
        
        # Binary search bounds - reasonable SWS range
        min_sws = 5.0  # Minimum reasonable SWS
        max_sws = 20.0  # Maximum reasonable SWS
        
        # Check if target SOG is achievable
        min_sog = calculate_sog_from_voyage_data(segment_id, min_sws)
        max_sog = calculate_sog_from_voyage_data(segment_id, max_sws)
        
        # Adjust bounds if target is outside range
        if target_sog < min_sog:
            max_sws = min_sws
            min_sws = 1.0
        elif target_sog > max_sog:
            min_sws = max_sws
            max_sws = 30.0
        
        # Binary search to find SWS
        best_sws = None
        best_error = float('inf')
        iteration_count = 0
        calculation_history = []
        
        for iteration in range(max_iterations):
            iteration_count = iteration + 1
            
            # Test middle point
            test_sws = (min_sws + max_sws) / 2.0
            
            # Calculate SOG for this SWS
            calculated_sog = calculate_sog_from_voyage_data(segment_id, test_sws)
            
            # Calculate error
            error = abs(calculated_sog - target_sog)
            
            # Track best result
            if error < best_error:
                best_error = error
                best_sws = test_sws
            
            # Store calculation step
            calculation_history.append({
                'iteration': iteration_count,
                'sws': test_sws,
                'calculated_sog': calculated_sog,
                'error': error
            })
            
            # Check convergence
            if error < tolerance:
                break
            
            # Adjust search bounds
            if calculated_sog < target_sog:
                min_sws = test_sws
            else:
                max_sws = test_sws
            
            # Check if bounds are too close
            if abs(max_sws - min_sws) < 0.0001:
                break
        
        # Verify final result
        if best_sws is not None:
            final_sog = calculate_sog_from_voyage_data(segment_id, best_sws)
            final_error = abs(final_sog - target_sog)
            
            return best_sws, {
                'target_sog': target_sog,
                'calculated_sws': best_sws,
                'final_sog': final_sog,
                'error': final_error,
                'iterations': iteration_count,
                'converged': final_error < tolerance,
                'calculation_history': calculation_history,
                'segment_data': segment_data
            }
        else:
            return None, {}
            
    except Exception as e:
        print(f"⚠️  Error in SWS calculation: {e}")
        import traceback
        traceback.print_exc()
        return None, {}

def display_detailed_calculation_breakdown(target_sog: float, calculated_sws: float, segment_data: dict):
    """
    Display comprehensive step-by-step calculation breakdown with all formulas and parameters.
    
    Args:
        target_sog: Target Speed Over Ground (knots)
        calculated_sws: Calculated Ship Speed in Still Water (knots)
        segment_data: Segment data dictionary
    """
    try:
        from utility_functions import (
            calculate_speed_over_ground,
            calculate_weather_direction_angle,
            calculate_froude_number,
            calculate_direction_reduction_coefficient,
            calculate_speed_reduction_coefficient,
            calculate_ship_form_coefficient,
            calculate_speed_loss_percentage,
            calculate_weather_corrected_speed,
            calculate_sog_vector_synthesis,
            KNOTS_TO_MS, MS_TO_KNOTS
        )
        from voyage_data import SHIP_PARAMETERS
        
        print(f"\n🔬 COMPREHENSIVE SWS CALCULATION BREAKDOWN (INVERSE FUNCTION)")
        print("=" * 80)
        print("Following the exact methodology from the research paper")
        print("'Ship Speed Optimization Considering Ocean Currents to Enhance")
        print("Environmental Sustainability in Maritime Shipping'")
        print("=" * 80)
        
        # ===============================
        # STEP 1: INPUT PARAMETERS
        # ===============================
        print(f"\n📋 STEP 1: INPUT PARAMETERS")
        print("-" * 40)
        print(f"Target Speed Over Ground (SOG):  {target_sog:.3f} knots")
        print(f"Calculated SWS (Vsw):            {calculated_sws:.3f} knots")
        print(f"Ocean Current Speed (Vc):        {segment_data['ocean_current']:.3f} knots")
        print(f"Current Direction (γ):           {math.degrees(segment_data['current_direction']):.1f}° = {segment_data['current_direction']:.4f} rad")
        print(f"Ship Heading (α/β):              {math.degrees(segment_data['ship_heading']):.1f}° = {segment_data['ship_heading']:.4f} rad")
        print(f"Wind Direction (φ):              {math.degrees(segment_data['wind_direction']):.1f}° = {segment_data['wind_direction']:.4f} rad")
        print(f"Beaufort Scale (BN):             {segment_data['beaufort_scale']}")
        print(f"Wave Height (H):                 {segment_data['wave_height']:.1f} m")
        print(f"Segment Distance:                {segment_data['distance']:.1f} nm")
        
        print(f"\nShip Parameters:")
        for param, value in SHIP_PARAMETERS.items():
            if isinstance(value, float):
                print(f"  {param.replace('_', ' ').title():.<25} {value:.1f}")
            else:
                print(f"  {param.replace('_', ' ').title():.<25} {value}")
        
        # ===============================
        # STEP 2: WEATHER DIRECTION ANGLE
        # ===============================
        print(f"\n🌊 STEP 2: WEATHER DIRECTION ANGLE CALCULATION")
        print("-" * 50)
        print("Formula: θ = |φ - α|  (Paper Equation 9)")
        print("where θ = weather direction angle")
        print("      φ = wind direction")
        print("      α = ship heading")
        
        weather_angle_rad = calculate_weather_direction_angle(
            segment_data['wind_direction'], 
            segment_data['ship_heading']
        )
        weather_angle_deg = math.degrees(weather_angle_rad)
        
        print(f"\nCalculation:")
        print(f"θ = |{math.degrees(segment_data['wind_direction']):.1f}° - {math.degrees(segment_data['ship_heading']):.1f}°|")
        print(f"θ = |{math.degrees(segment_data['wind_direction']) - math.degrees(segment_data['ship_heading']):.1f}°|")
        print(f"θ = {weather_angle_deg:.1f}° = {weather_angle_rad:.4f} rad")
        
        # ===============================
        # STEP 3: FROUDE NUMBER
        # ===============================
        print(f"\n⚓ STEP 3: FROUDE NUMBER CALCULATION")
        print("-" * 40)
        print("Formula: Fn = V / √(g × L)")
        print("where Fn = Froude number (dimensionless)")
        print("      V  = ship speed (m/s)")
        print("      g  = gravitational acceleration (9.81 m/s²)")
        print("      L  = ship length (m)")
        
        ship_speed_ms = calculated_sws * KNOTS_TO_MS
        froude_number = calculate_froude_number(ship_speed_ms, SHIP_PARAMETERS['length'])
        
        print(f"\nCalculation:")
        print(f"V = {calculated_sws:.3f} knots × {KNOTS_TO_MS:.4f} = {ship_speed_ms:.3f} m/s")
        print(f"Fn = {ship_speed_ms:.3f} / √(9.81 × {SHIP_PARAMETERS['length']:.1f})")
        print(f"Fn = {ship_speed_ms:.3f} / √({9.81 * SHIP_PARAMETERS['length']:.1f})")
        print(f"Fn = {ship_speed_ms:.3f} / {math.sqrt(9.81 * SHIP_PARAMETERS['length']):.3f}")
        print(f"Fn = {froude_number:.6f}")
        
        # ===============================
        # STEP 4: DIRECTION REDUCTION COEFFICIENT
        # ===============================
        print(f"\n🧭 STEP 4: DIRECTION REDUCTION COEFFICIENT (Cβ)")
        print("-" * 50)
        print("Based on Paper Table 2 - Weather direction relative to ship's bow")
        
        c_beta = calculate_direction_reduction_coefficient(weather_angle_deg, segment_data['beaufort_scale'])
        
        # Determine which formula applies
        if 0 <= weather_angle_deg <= 30:
            sea_type = "Head sea (0-30°)"
            formula = "Cβ = 2.0"
        elif 30 < weather_angle_deg <= 60:
            sea_type = "Bow sea (30-60°)"
            formula = f"Cβ = 1.7 - 0.03 × (BN - 4)²"
        elif 60 < weather_angle_deg <= 150:
            sea_type = "Beam sea (60-150°)"
            formula = f"Cβ = 0.9 - 0.06 × (BN - 6)²"
        else:
            sea_type = "Following sea (150-180°)"
            formula = f"Cβ = 0.4 - 0.03 × (BN - 8)²"
        
        print(f"\nSea Condition: {sea_type}")
        print(f"Formula: {formula}")
        print(f"where BN = Beaufort Number = {segment_data['beaufort_scale']}")
        print(f"Cβ = {c_beta:.6f}")
        
        # ===============================
        # STEP 5: SPEED REDUCTION COEFFICIENT
        # ===============================
        print(f"\n🚀 STEP 5: SPEED REDUCTION COEFFICIENT (CU)")
        print("-" * 50)
        print("Based on Paper Table 3 - Froude number and block coefficient")
        
        cb = SHIP_PARAMETERS['block_coefficient']
        c_u = calculate_speed_reduction_coefficient(froude_number, cb, 'normal')
        
        print(f"\nBlock Coefficient (Cb): {cb:.3f}")
        print(f"Loading Condition: Normal")
        print(f"Fn = {froude_number:.6f}")
        print(f"CU = {c_u:.6f}")
        
        # ===============================
        # STEP 6: SHIP FORM COEFFICIENT
        # ===============================
        print(f"\n🏗️ STEP 6: SHIP FORM COEFFICIENT (CForm)")
        print("-" * 45)
        print("Based on Paper Table 4 - Beaufort scale and displacement")
        
        displacement_volume = SHIP_PARAMETERS['displacement'] * 1000 / 1025
        c_form = calculate_ship_form_coefficient(segment_data['beaufort_scale'], displacement_volume, 'normal')
        
        print(f"\nDisplacement = {SHIP_PARAMETERS['displacement']:.0f} tonnes")
        print(f"∇ = {displacement_volume:.1f} m³")
        print(f"BN = {segment_data['beaufort_scale']}")
        print(f"CForm = {c_form:.6f}")
        
        # ===============================
        # STEP 7: SPEED LOSS PERCENTAGE
        # ===============================
        print(f"\n📉 STEP 7: SPEED LOSS PERCENTAGE")
        print("-" * 35)
        print("Formula: ΔV/Vsw × 100% = Cβ × CU × CForm  (Paper Equation 7)")
        
        speed_loss_percent = calculate_speed_loss_percentage(c_beta, c_u, c_form)
        
        print(f"\nCalculation:")
        print(f"ΔV/Vsw × 100% = {c_beta:.6f} × {c_u:.6f} × {c_form:.6f}")
        print(f"ΔV/Vsw × 100% = {c_beta * c_u * c_form:.6f}")
        print(f"Speed Loss = {speed_loss_percent:.3f}%")
        
        # ===============================
        # STEP 8: WEATHER-CORRECTED SPEED
        # ===============================
        print(f"\n🌤️ STEP 8: WEATHER-CORRECTED SPEED")
        print("-" * 40)
        print("Formula: Vw = Vsw × (1 - ΔV/Vsw)  (Paper Equation 8)")
        
        weather_corrected_speed = calculate_weather_corrected_speed(calculated_sws, speed_loss_percent)
        
        print(f"\nCalculation:")
        print(f"Vw = {calculated_sws:.3f} × (1 - {speed_loss_percent:.6f}/100)")
        print(f"Vw = {calculated_sws:.3f} × {1 - speed_loss_percent/100:.6f}")
        print(f"Vw = {weather_corrected_speed:.6f} knots")
        
        # ===============================
        # STEP 9: VECTOR SYNTHESIS FOR SOG
        # ===============================
        print(f"\n🧭 STEP 9: SPEED OVER GROUND (SOG) - VECTOR SYNTHESIS")
        print("-" * 55)
        print("Formulas: (Paper Equations 14-16)")
        print("Vx = Vw × sin(α) + Vc × sin(γ)  (Equation 14)")
        print("Vy = Vw × cos(α) + Vc × cos(γ)  (Equation 15)")
        print("Vg = √(Vx² + Vy²)              (Equation 16)")
        
        # Calculate velocity components
        vw_x = weather_corrected_speed * math.sin(segment_data['ship_heading'])
        vw_y = weather_corrected_speed * math.cos(segment_data['ship_heading'])
        vc_x = segment_data['ocean_current'] * math.sin(segment_data['current_direction'])
        vc_y = segment_data['ocean_current'] * math.cos(segment_data['current_direction'])
        vg_x = vw_x + vc_x
        vg_y = vw_y + vc_y
        
        calculated_sog = calculate_sog_vector_synthesis(
            weather_corrected_speed, 
            segment_data['ship_heading'],
            segment_data['ocean_current'], 
            segment_data['current_direction']
        )
        
        # Apply post-processing for severe weather if needed
        if segment_data['beaufort_scale'] >= 5:
            calculated_sog = calculated_sog * 0.965
        
        print(f"\nStep 9a: Ship velocity components")
        print(f"Vw_x = {weather_corrected_speed:.6f} × sin({math.degrees(segment_data['ship_heading']):.1f}°) = {vw_x:.6f}")
        print(f"Vw_y = {weather_corrected_speed:.6f} × cos({math.degrees(segment_data['ship_heading']):.1f}°) = {vw_y:.6f}")
        
        print(f"\nStep 9b: Current velocity components")
        print(f"Vc_x = {segment_data['ocean_current']:.6f} × sin({math.degrees(segment_data['current_direction']):.1f}°) = {vc_x:.6f}")
        print(f"Vc_y = {segment_data['ocean_current']:.6f} × cos({math.degrees(segment_data['current_direction']):.1f}°) = {vc_y:.6f}")
        
        print(f"\nStep 9c: Total velocity components")
        print(f"Vg_x = {vw_x:.6f} + {vc_x:.6f} = {vg_x:.6f}")
        print(f"Vg_y = {vw_y:.6f} + {vc_y:.6f} = {vg_y:.6f}")
        
        print(f"\nStep 9d: Final SOG calculation")
        print(f"Vg = √({vg_x**2:.6f} + {vg_y**2:.6f})")
        print(f"Vg = {calculated_sog:.6f} knots")
        
        # ===============================
        # STEP 10: VERIFICATION
        # ===============================
        print(f"\n✅ STEP 10: VERIFICATION")
        print("-" * 30)
        print(f"Target SOG:        {target_sog:.6f} knots")
        print(f"Calculated SOG:    {calculated_sog:.6f} knots")
        print(f"Difference:        {abs(calculated_sog - target_sog):.6f} knots")
        print(f"Error Percentage:  {abs(calculated_sog - target_sog) / target_sog * 100:.4f}%")
        
        # ===============================
        # STEP 11: SUMMARY
        # ===============================
        print(f"\n🎯 FINAL RESULTS SUMMARY")
        print("=" * 40)
        print(f"Target Speed Over Ground (SOG):  {target_sog:.3f} knots")
        print(f"Required SWS (Vsw):              {calculated_sws:.3f} knots")
        print(f"Calculated SOG:                  {calculated_sog:.3f} knots")
        print(f"Speed Difference (SOG - Vsw):    {calculated_sog - calculated_sws:+.3f} knots")
        print(f"Speed Change Percentage:         {(calculated_sog - calculated_sws)/calculated_sws * 100:+.1f}%")
        
        print(f"\nKey Coefficients:")
        print(f"Direction Reduction (Cβ):        {c_beta:.6f}")
        print(f"Speed Reduction (CU):            {c_u:.6f}")
        print(f"Ship Form (CForm):               {c_form:.6f}")
        print(f"Speed Loss:                      {speed_loss_percent:.3f}%")
        
        print(f"\nTravel Time Analysis:")
        travel_time = segment_data['distance'] / calculated_sog
        travel_time_vsw = segment_data['distance'] / calculated_sws
        
        print(f"Distance:                        {segment_data['distance']:.1f} nm")
        print(f"Travel Time at SOG:              {travel_time:.2f} hours")
        print(f"Travel Time at SWS:              {travel_time_vsw:.2f} hours")
        print(f"Time Difference:                 {travel_time - travel_time_vsw:+.2f} hours")
        
        print(f"\n✅ Complete calculation breakdown finished!")
        print("=" * 80)
        
    except ImportError as e:
        print(f"⚠️  Warning: Could not import required functions: {e}")
    except Exception as e:
        print(f"⚠️  Warning: Error in detailed breakdown: {e}")
        import traceback
        traceback.print_exc()

def calculate_and_display_sws(target_sog: float, segment_id: int):
    """
    Calculate SWS and display detailed results.
    
    Args:
        target_sog: Target Speed Over Ground (knots)
        segment_id: Segment number (1-12)
    """
    try:
        print(f"\n🧮 SWS Calculation for Segment {segment_id}")
        print("=" * 45)
        print(f"Target SOG: {target_sog:.3f} knots")
        print("\n🔍 Finding required SWS using iterative method...")
        
        # Calculate SWS using iterative method
        calculated_sws, calc_info = calculate_sws_from_sog(target_sog, segment_id)
        
        if calculated_sws is None:
            print("❌ Error: Could not calculate SWS")
            return None
        
        print(f"\n✅ Calculation Complete!")
        print(f"Required SWS: {calculated_sws:.3f} knots")
        print(f"Final SOG: {calc_info['final_sog']:.3f} knots")
        print(f"Error: {calc_info['error']:.6f} knots")
        print(f"Iterations: {calc_info['iterations']}")
        print(f"Converged: {'Yes' if calc_info['converged'] else 'No (within reasonable bounds)'}")
        
        # Calculate travel time
        distance = calc_info['segment_data']['distance']
        travel_time = distance / calc_info['final_sog']
        
        print(f"\n⏱️  Travel Time Calculation:")
        print(f"Segment Distance: {distance:.1f} nm")
        print(f"Travel Time at Target SOG: {travel_time:.2f} hours")
        print(f"Travel Time: {travel_time*60:.0f} minutes")
        
        # Display detailed breakdown
        display_detailed_calculation_breakdown(
            target_sog, 
            calculated_sws, 
            calc_info['segment_data']
        )
        
        return calculated_sws
        
    except Exception as e:
        print(f"❌ Error calculating SWS: {e}")
        import traceback
        traceback.print_exc()
        return None

def main():
    """
    Main function to run the interactive SWS calculator.
    """
    print("🚢 Welcome to the Interactive SWS Calculator!")
    print("Calculate required SWS from desired SOG (inverse function)")
    print("Using paper-exact methodology from utility_functions.py")
    print("Environmental data from Table 8 of the research paper")
    print()
    
    while True:
        # Get user input
        target_sog, segment_id = get_user_input()
        
        if target_sog is None or segment_id is None:  # User wants to exit
            print("\n👋 Thank you for using the SWS Calculator!")
            break
        
        # Display segment information
        display_segment_info(segment_id)
        
        # Calculate and display SWS
        calculated_sws = calculate_and_display_sws(target_sog, segment_id)
        
        if calculated_sws is not None:
            print(f"\n✅ Calculation Complete!")
            print(f"📊 Summary: Target SOG {target_sog:.3f} knots → Required SWS {calculated_sws:.3f} knots (Segment {segment_id})")
        
        # Ask if user wants to continue
        print("\n" + "=" * 50)
        continue_calc = input("Calculate another SWS? (y/n): ").strip().lower()
        if continue_calc not in ['y', 'yes']:
            print("\n👋 Thank you for using the SWS Calculator!")
            break
        
        print("\n" + "=" * 50)

def quick_calculation(target_sog: float, segment_id: int):
    """
    Quick calculation function for scripting use.
    
    Args:
        target_sog: Target Speed Over Ground (knots)
        segment_id: Segment number (1-12)
    
    Returns:
        float: Calculated SWS or None if error
    """
    try:
        calculated_sws, calc_info = calculate_sws_from_sog(target_sog, segment_id)
        return calculated_sws
    except:
        return None

if __name__ == "__main__":
    # Check if command line arguments are provided for quick calculation
    if len(sys.argv) == 3:
        try:
            target_sog = float(sys.argv[1])
            segment_id = int(sys.argv[2])
            
            if 1 <= segment_id <= 12:
                sws = quick_calculation(target_sog, segment_id)
                if sws is not None:
                    print(f"SWS Calculation: Target SOG {target_sog:.3f} knots → Required SWS {sws:.3f} knots (Segment {segment_id})")
                else:
                    print("Error: Could not calculate SWS")
            else:
                print("Error: Segment must be between 1 and 12")
        except ValueError:
            print("Error: Invalid input arguments")
            print("Usage: python interactive_sws_calculator.py <target_SOG> <segment_id>")
    else:
        # Run interactive mode
        main()


#!/usr/bin/env python3
"""
Generate Optimization Data for Ship Speed Optimization

This script generates a data file for ship speed optimization with:
- Speeds between 8.0 and 15.7 knots (0.1 knot increments)
- SOG calculations using utility_functions.py and voyage_data.py
- ETA constraint of 280 hours
- Fuel consumption rates using utility_functions.py
- NEW: Segment-specific ship headings for improved accuracy

Author: Data Generation Script
Date: 2025
"""

import numpy as np
import math
from utility_functions import calculate_speed_over_ground, calculate_fuel_consumption_rate
from voyage_data import get_all_segments, SHIP_PARAMETERS, SEGMENT_HEADINGS

def generate_segment_data_8to15_7():
    """
    Generate data using final calibrated utility functions and voyage data
    for speeds 8.0-15.7 knots with segment-specific headings.
    """
    
    # Get voyage data
    segments = get_all_segments()
    
    # Generate speeds from 8.0 to 15.7 with 0.1 increments
    speeds = np.arange(8.0, 15.8, 0.1)  # 8.0, 8.1, ..., 15.6, 15.7
    num_speeds = len(speeds)
    
    # Extract segment lengths from voyage data
    l = [seg['distance_nm'] for seg in segments]
    
    # Calculate SOG matrix for each segment and speed using utility functions
    sog_matrix = []
    for i, segment in enumerate(segments):
        segment_sog = []
        # Convert heading from degrees to radians
        ship_heading_rad = math.radians(SEGMENT_HEADINGS[i])
        
        for k in range(num_speeds):
            # Use final calibrated utility function to calculate SOG with weather effects
            # Using research paper headings from voyage_data.py (Table 8)
            sog = calculate_speed_over_ground(
                ship_speed=speeds[k],
                ocean_current=segment['current_speed_knots'],
                current_direction=segment['current_direction_radians'],
                ship_heading=ship_heading_rad,  # Research paper heading from Table 8
                wind_direction=segment['wind_direction_radians'],
                beaufort_scale=segment['beaufort_scale'],
                wave_height=segment['wave_height_m'],
                ship_parameters=SHIP_PARAMETERS
            )
            segment_sog.append(round(sog, 6))
        sog_matrix.append(segment_sog)
    
    # Calculate speed bounds (L and U) for each segment
    L_bounds = []
    U_bounds = []
    
    for i in range(len(segments)):
        min_sog = np.min(sog_matrix[i])
        max_sog = np.max(sog_matrix[i])
        
        # Set bounds slightly wider than the SOG range to allow optimization
        L_bounds.append(round(min_sog - 0.5, 6))
        U_bounds.append(round(max_sog + 0.5, 6))
    
    # Calculate fuel consumption rates for each speed using utility functions
    fuel_rates = []
    for k in range(num_speeds):
        fcr = calculate_fuel_consumption_rate(speeds[k], SHIP_PARAMETERS)
        fuel_rates.append(round(fcr, 6))
    
    return {
        'ETA': 280,
        'num_segments': 12,
        'num_speeds': num_speeds,
        'l': l,
        'L': L_bounds,
        'U': U_bounds,
        's': [round(speed, 1) for speed in speeds.tolist()],
        'f': sog_matrix,
        'FCR': fuel_rates
    }

def write_data_file(data, filename='data_12segments.dat'):
    """
    Write the optimization data to a file in the required format.
    
    Args:
        data: Dictionary containing optimization data
        filename: Output filename
    """
    
    with open(filename, 'w') as f:
        # Write ETA
        f.write(f"ETA = {data['ETA']};\n\n")
        
        # Write dimensions
        f.write(f"num_segments = {data['num_segments']};\n")
        f.write(f"num_speeds = {data['num_speeds']};   // speed granularity\n\n")
        
        # Write segment lengths
        f.write("l = [" + ", ".join([str(x) for x in data['l']]) + "];  // length of segments in nautical miles\n")
        
        # Write speed bounds
        f.write("L = [" + ", ".join([str(x) for x in data['L']]) + "];      // minimal speed at segment i, SOG terms\n")
        f.write("U = [" + ", ".join([str(x) for x in data['U']]) + "];   // maximal speed at segment i, SOG terms\n\n")
        
        # Write possible speeds
        f.write("s = [" + ", ".join([str(x) for x in data['s']]) + "];  // possible speeds (SWS) in knots\n")
        
        # Write SOG matrix
        f.write("f = [  // SOG at segment i given speed s[k]\n")
        for i, segment in enumerate(data['f']):
            if i == 0:
                f.write("  [" + ", ".join([str(x) for x in segment]) + "]")
            else:
                f.write(", [" + ", ".join([str(x) for x in segment]) + "]")
        f.write(" ];\n")
        
        # Write fuel consumption rates
        f.write("FCR = [" + ", ".join([str(x) for x in data['FCR']]) + "];  // fuel consumption rate when steaming at s[k] (MT/h)\n")

def main():
    """Main function to generate optimization data."""
    
    print("🚢 Ship Speed Optimization Data Generator (8.0-15.7 knots)")
    print("=" * 60)
    print("Using FINAL CALIBRATED SOG calculations from utility_functions.py")
    print("Weather effects: Physically consistent Beaufort scale reductions")
    print("Ocean currents: Vector synthesis with improved accuracy")
    print("Ship headings: Using research paper values from voyage_data.py (Table 8)")
    
    # Display heading values
    print(f"\n📍 Ship Headings by Segment:")
    for i, heading in enumerate(SEGMENT_HEADINGS):
        print(f"   Segment {i+1}: {heading}°")
    
    # Generate data using utility functions
    print(f"\n🔧 Generating optimization data...")
    data = generate_segment_data_8to15_7()
    
    # Write to file
    filename = 'data_12segments.dat'
    write_data_file(data, filename)
    
    print(f"✅ Data generated successfully!")
    print(f"📁 Output file: {filename}")
    print(f"📊 Summary:")
    print(f"   - {data['num_segments']} segments")
    print(f"   - {data['num_speeds']} speed options (8.0-15.7 knots)")
    print(f"   - Total distance: {sum(data['l']):.2f} nautical miles")
    print(f"   - ETA constraint: {data['ETA']:.2f} hours")
    
    # Verify feasibility
    print(f"\n🔍 Feasibility Check:")
    
    # Calculate minimum possible time
    min_times = []
    for i in range(data['num_segments']):
        valid_speeds = []
        for k in range(data['num_speeds']):
            if data['L'][i] <= data['f'][i][k] <= data['U'][i]:
                valid_speeds.append(data['f'][i][k])
        
        if valid_speeds:
            fastest_sog = max(valid_speeds)
            min_time = data['l'][i] / fastest_sog
            min_times.append(min_time)
    
    total_min_time = sum(min_times)
    print(f"   Minimum travel time: {total_min_time:.2f} hours")
    print(f"   ETA constraint: {data['ETA']:.2f} hours")
    
    if total_min_time <= data['ETA']:
        print(f"   ✅ FEASIBLE: Minimum time <= ETA")
        print(f"   Time margin: {data['ETA'] - total_min_time:.2f} hours")
    else:
        print(f"   ❌ INFEASIBLE: Minimum time > ETA")
        print(f"   Time deficit: {total_min_time - data['ETA']:.2f} hours")
    
    # Display SOG comparison for first few segments
    print(f"\n📈 SOG Sample (first 3 segments at 12.0 knots):")
    for i in range(min(3, len(data['f']))):
        # Find SOG for 12.0 knots (dynamically calculate index)
        try:
            speed_12_index = data['s'].index(12.0)  # Find actual index of 12.0 knots
            if speed_12_index < len(data['f'][i]):
                sog_12 = data['f'][i][speed_12_index]
                print(f"   Segment {i+1} (heading {SEGMENT_HEADINGS[i]}°): SOG = {sog_12:.3f} knots")
        except ValueError:
            print(f"   Segment {i+1}: 12.0 knots not in speed range")

if __name__ == "__main__":
    main() 
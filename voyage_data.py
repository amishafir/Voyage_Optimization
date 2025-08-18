"""
Voyage Data for Ship Speed Optimization
Weather and sea condition data for 12 segments from the research article.

This module contains:
- Weather conditions (wind direction φᵢ, Beaufort scale, wave height)
- Sea conditions (current direction, current speed)
- Ship headings for each segment (βᵢ from Table 8)
- Current angles for each segment (γᵢ from Table 8)
- Segment information (distance, coordinates, etc.)
- Functions to process and analyze the data

Based on research paper: "Ship Speed Optimization Considering Ocean Currents to Enhance Environmental Sustainability in Maritime Shipping"

Author: Based on research paper data
Date: 2025
"""

import math
from typing import List, Dict, Tuple

# Data for 12 segments from Table 8 of the research article
SEGMENT_DATA = [
    # segment_id, wind_direction(φᵢ), beaufort, wave_height, current_direction(γᵢ), current_speed
    [1, 139, 3, 1.0, 245, 0.30],
    [2, 207, 3, 1.0, 248, 0.72],
    [3, 9, 4, 1.5, 158, 0.73],
    [4, 201, 4, 1.5, 178, 0.21],
    [5, 88, 5, 2.5, 135, 0.49],
    [6, 86, 4, 1.5, 113, 0.22],
    [7, 353, 3, 1.0, 338, 0.54],
    [8, 35, 5, 2.5, 290, 1.25],
    [9, 269, 4, 1.5, 270, 0.28],
    [10, 174, 3, 1.0, 93, 0.72],
    [11, 60, 1, 0.1, 185, 0.62],
    [12, 315, 3, 1.0, 90, 0.30]
]

# Ship heading for each segment (βᵢ from Table 8)
SEGMENT_HEADINGS = [
    61.25,   # Segment 1
    121.53,  # Segment 2
    117.61,  # Segment 3
    139.03,  # Segment 4
    143.63,  # Segment 5
    140.84,  # Segment 6
    136.42,  # Segment 7
    110.37,  # Segment 8
    102.57,  # Segment 9
    82.83,   # Segment 10
    84.87,   # Segment 11
    142.39   # Segment 12
]



# Additional segment information (estimated based on typical voyage patterns)
SEGMENT_DISTANCES = [
    223.86,  # Segment 1
    282.54,  # Segment 2
    303.18,  # Segment 3
    298.44,  # Segment 4
    280.51,  # Segment 5
    287.34,  # Segment 6
    284.40,  # Segment 7
    233.25,  # Segment 8
    301.80,  # Segment 9
    315.70,  # Segment 10
    293.80,  # Segment 11
    288.42   # Segment 12
]

# Ship parameters for the voyage (typical container ship)
SHIP_PARAMETERS = {
    'length': 200.0,  # meters
    'beam': 32.0,     # meters
    'draft': 12.0,    # meters
    'displacement': 50000.0,  # tonnes
    'block_coefficient': 0.75,
    'wetted_surface': 8000.0,  # m²
    'rated_power': 10000.0,  # kW
    'max_speed': 14.0,  # knots
    'min_speed': 8.0    # knots
}

def convert_degrees_to_radians(degrees: float) -> float:
    """
    Convert degrees to radians.
    
    Args:
        degrees: Angle in degrees (0-360)
    
    Returns:
        Angle in radians
    """
    return math.radians(degrees)

def get_segment_info(segment_id: int) -> Dict:
    """
    Get complete information for a specific segment.
    
    Args:
        segment_id: Segment ID (1-12)
    
    Returns:
        Dictionary with segment information
    """
    if segment_id < 1 or segment_id > 12:
        raise ValueError("Segment ID must be between 1 and 12")
    
    # Get data from the table (segment_id is 1-indexed, but list is 0-indexed)
    data = SEGMENT_DATA[segment_id - 1]
    distance = SEGMENT_DISTANCES[segment_id - 1]
    heading = SEGMENT_HEADINGS[segment_id - 1]
    
    return {
        'segment_id': data[0],
        'wind_direction_degrees': data[1],
        'wind_direction_radians': convert_degrees_to_radians(data[1]),
        'beaufort_scale': data[2],
        'wave_height_m': data[3],
        'current_direction_degrees': data[4],
        'current_direction_radians': convert_degrees_to_radians(data[4]),
        'current_speed_knots': data[5],
        'distance_nm': distance,
        'ship_heading_degrees': heading,
        'ship_heading_radians': convert_degrees_to_radians(heading),
        'current_angle_degrees': data[4],  # Same as current_direction - it's γᵢ
        'current_angle_radians': convert_degrees_to_radians(data[4])
    }

def get_all_segments() -> List[Dict]:
    """
    Get information for all 12 segments.
    
    Returns:
        List of dictionaries with segment information
    """
    segments = []
    for segment_id in range(1, 13):
        segments.append(get_segment_info(segment_id))
    return segments

def get_weather_summary() -> Dict:
    """
    Get summary statistics for weather conditions across all segments.
    
    Returns:
        Dictionary with weather summary
    """
    segments = get_all_segments()
    
    beaufort_values = [seg['beaufort_scale'] for seg in segments]
    wave_heights = [seg['wave_height_m'] for seg in segments]
    current_speeds = [seg['current_speed_knots'] for seg in segments]
    
    return {
        'total_segments': len(segments),
        'average_beaufort': sum(beaufort_values) / len(beaufort_values),
        'max_beaufort': max(beaufort_values),
        'min_beaufort': min(beaufort_values),
        'average_wave_height': sum(wave_heights) / len(wave_heights),
        'max_wave_height': max(wave_heights),
        'min_wave_height': min(wave_heights),
        'average_current_speed': sum(current_speeds) / len(current_speeds),
        'max_current_speed': max(current_speeds),
        'min_current_speed': min(current_speeds),
        'total_distance': sum(seg['distance_nm'] for seg in segments)
    }

def get_segment_for_utility_functions(segment_id: int, ship_speed: float = 12.0) -> Dict:
    """
    Format segment data for use with utility_functions.py.
    
    Args:
        segment_id: Segment ID (1-12)
        ship_speed: Ship speed in still water (knots)
    
    Returns:
        Dictionary formatted for utility_functions.py
    """
    segment_info = get_segment_info(segment_id)
    
    return {
        'segment_id': segment_info['segment_id'],
        'distance': segment_info['distance_nm'],
        'ocean_current': segment_info['current_speed_knots'],
        'current_direction': segment_info['current_direction_radians'],
        'ship_speed': ship_speed,
        'ship_heading': segment_info['ship_heading_radians'],
        'wind_direction': segment_info['wind_direction_radians'],
        'beaufort_scale': segment_info['beaufort_scale'],
        'wave_height': segment_info['wave_height_m'],
        'current_angle': segment_info['current_angle_radians']
    }

def analyze_voyage_conditions() -> Dict:
    """
    Analyze weather and sea conditions for the entire voyage.
    
    Returns:
        Dictionary with voyage analysis
    """
    segments = get_all_segments()
    weather_summary = get_weather_summary()
    
    # Categorize conditions
    calm_segments = [seg for seg in segments if seg['beaufort_scale'] <= 2]
    moderate_segments = [seg for seg in segments if 3 <= seg['beaufort_scale'] <= 4]
    rough_segments = [seg for seg in segments if seg['beaufort_scale'] >= 5]
    
    # Current analysis
    favorable_currents = [seg for seg in segments if seg['current_speed_knots'] > 0.5]
    adverse_currents = [seg for seg in segments if seg['current_speed_knots'] > 0.5]
    
    return {
        'weather_summary': weather_summary,
        'condition_breakdown': {
            'calm_conditions': len(calm_segments),
            'moderate_conditions': len(moderate_segments),
            'rough_conditions': len(rough_segments)
        },
        'current_analysis': {
            'favorable_currents': len(favorable_currents),
            'adverse_currents': len(adverse_currents),
            'strongest_current_segment': max(segments, key=lambda x: x['current_speed_knots'])['segment_id'],
            'weakest_current_segment': min(segments, key=lambda x: x['current_speed_knots'])['segment_id']
        },
        'challenging_segments': [
            seg['segment_id'] for seg in segments 
            if seg['beaufort_scale'] >= 4 or seg['current_speed_knots'] >= 0.7
        ]
    }

def print_voyage_data():
    """
    Print formatted voyage data for all segments.
    """
    print("=" * 80)
    print("VOYAGE DATA - 12 SEGMENTS FROM RESEARCH ARTICLE")
    print("=" * 80)
    
    segments = get_all_segments()
    
    print(f"\n🚢 Ship Parameters:")
    for key, value in SHIP_PARAMETERS.items():
        print(f"   {key}: {value}")
    
    print(f"\n📊 Segment Information:")
    print(f"{'ID':<3} {'Distance':<8} {'Ship Heading':<12} {'Wind Dir':<8} {'Beaufort':<8} {'Wave H':<6} {'Current Dir':<11} {'Current Speed':<12} {'Current Angle':<12}")
    print("-" * 95)
    
    for segment in segments:
        print(f"{segment['segment_id']:<3} {segment['distance_nm']:<8.1f} {segment['ship_heading_degrees']:<12.1f}° {segment['wind_direction_degrees']:<8.0f}° {segment['beaufort_scale']:<8} {segment['wave_height_m']:<6.1f}m {segment['current_direction_degrees']:<11.0f}° {segment['current_speed_knots']:<12.2f}kts {segment['current_angle_degrees']:<12.0f}°")
    
    # Weather summary
    weather_summary = get_weather_summary()
    print(f"\n🌤️  Weather Summary:")
    print(f"   Total Distance: {weather_summary['total_distance']:.1f} nm")
    print(f"   Average Beaufort Scale: {weather_summary['average_beaufort']:.1f}")
    print(f"   Average Wave Height: {weather_summary['average_wave_height']:.1f} m")
    print(f"   Average Current Speed: {weather_summary['average_current_speed']:.2f} knots")
    
    # Voyage analysis
    analysis = analyze_voyage_conditions()
    print(f"\n📈 Voyage Analysis:")
    print(f"   Calm Conditions: {analysis['condition_breakdown']['calm_conditions']} segments")
    print(f"   Moderate Conditions: {analysis['condition_breakdown']['moderate_conditions']} segments")
    print(f"   Rough Conditions: {analysis['condition_breakdown']['rough_conditions']} segments")
    print(f"   Challenging Segments: {analysis['challenging_segments']}")
    
    print(f"\n" + "=" * 80)
    print("✅ Voyage data ready for use with utility_functions.py")
    print("=" * 80)

def main():
    """
    Main function to demonstrate voyage data.
    """
    print_voyage_data()
    
    print(f"\n💡 Usage Examples:")
    print(f"1. Get segment 5 data: get_segment_info(5)")
    print(f"2. Get all segments: get_all_segments()")
    print(f"3. Format for utility functions: get_segment_for_utility_functions(5, 12.0)")
    print(f"4. Analyze voyage: analyze_voyage_conditions()")
    print(f"5. Get segment heading: SEGMENT_HEADINGS[4]  # For segment 5 (0-indexed)")
    print(f"6. Get current angle: SEGMENT_DATA[4][4]  # For segment 5, current_direction field")
    
    print(f"\n🔧 Integration with utility_functions.py:")
    print(f"from utility_functions import calculate_speed_over_ground_paper_exact")
    print(f"from voyage_data import get_segment_for_utility_functions, SHIP_PARAMETERS")
    print(f"")
    print(f"# Example for segment 5 with new heading and current angle data")
    print(f"segment_data = get_segment_for_utility_functions(5, 12.0)")
    print(f"# segment_data now includes 'ship_heading' and 'current_angle' keys")
    print(f"sog = calculate_speed_over_ground_paper_exact(")
    print(f"    ship_speed=12.0,")
    print(f"    ship_heading=segment_data['ship_heading'],")
    print(f"    current_angle=segment_data['current_angle'],")
    print(f"    **segment_data)")
    
    print(f"\n📊 New Data Added:")
    print(f"• Ship headings (βᵢ) for each segment from Table 8")
    print(f"• Current angles (γᵢ) for each segment from Table 8")
    print(f"• Wind angles (φᵢ) already available in SEGMENT_DATA")
    print(f"• All angles available in degrees and radians")

if __name__ == "__main__":
    main() 


import yaml
import numpy as np
import math
from utility_functions import calculate_speed_over_ground as utility_calculate_sog, calculate_travel_time, calculate_fuel_consumption_rate



def calculate_fuel_consumption_rate(speed):
    return 0.000706 * speed**3

def calculate_speed_over_ground(speed, segment_data=None, ship_parameters=None):
    
    # Extract weather parameters from segment data
    ship_heading_deg = segment_data.get('ship_heading', 0.0)
    wind_dir_deg = segment_data.get('wind_dir', 0.0)
    beaufort_scale = segment_data.get('beaufort', 3)
    wave_height = segment_data.get('wave_height', 1.0)
    current_dir_deg = segment_data.get('current_dir', 0.0)
    current_speed = segment_data.get('current_speed', 0.0)
    
    # Convert degrees to radians for utility function
    ship_heading_rad = math.radians(ship_heading_deg)
    wind_dir_rad = math.radians(wind_dir_deg)
    current_dir_rad = math.radians(current_dir_deg)
    
    # Use the comprehensive SOG calculation from utility_functions.py
    sog = utility_calculate_sog(
        ship_speed=speed,
        ocean_current=current_speed,
        current_direction=current_dir_rad,
        ship_heading=ship_heading_rad,
        wind_direction=wind_dir_rad,
        beaufort_scale=beaufort_scale,
        wave_height=wave_height,
        ship_parameters=ship_parameters
    )
    
    return sog


def CreateNode(Node, speed, node_index, ship_parameters=None):
    segment_data = Node['weather_forecasts_list'][0][Node['current_segment']]
    
    # Calculate SOG using weather data and utility functions
    SOG = calculate_speed_over_ground(speed, segment_data, ship_parameters)
    
    # Make copies to avoid modifying the original lists
    cumulative_segment_list = Node['cumulative_segment_list'].copy()
    cumulative_time_list = Node['cumulative_time_list'].copy()
    
    # Check if we have segments and time windows to process
    if not cumulative_segment_list or not cumulative_time_list:
        return None
        
    time_to_segment = (cumulative_segment_list[0] - Node['Elapsed_distance']) / SOG
    # print(f"time_to_segment: {time_to_segment}")
    Time_to_forecast_window = (cumulative_time_list[0] - Node['Elapsed_time'])
    # print(f"Time_to_forecast_window: {Time_to_forecast_window}")
    
    if time_to_segment <= Time_to_forecast_window:

        NewNode = { 
            'comulative_fuel_consumption': Node['comulative_fuel_consumption'] + calculate_fuel_consumption_rate(speed) * time_to_segment,
            'current_segment': Node['current_segment'] + 1,
            'cumulative_segment_list': cumulative_segment_list[1:],  # Remove first element without modifying original
            'cumulative_time_list': cumulative_time_list,
            'weather_forecasts_list': Node['weather_forecasts_list'],
            'Elapsed_time': Node['Elapsed_time'] + time_to_segment,
            'Elapsed_distance': Node['Elapsed_distance'] + SOG * time_to_segment,
            'incoming_arc': {
            'Incoming_node': Node.copy(),  # Make a copy to preserve the state
            'SWS': speed,
            'SOG': SOG,
            'Travel_time': time_to_segment,
            #'Distance': SOG * (forecast_window - Node['Elapsed_time']),
            'Distance': SOG * time_to_segment,
            'FCR': calculate_fuel_consumption_rate(speed),
            'Fuel_consumption': calculate_fuel_consumption_rate(speed) * time_to_segment }  ,
            'node_index': node_index
        }
    else:
        # Cannot complete full distance within forecast window - travel only until window ends
        
        NewNode = { 
            'comulative_fuel_consumption': Node['comulative_fuel_consumption'] + calculate_fuel_consumption_rate(speed) * Time_to_forecast_window,
            'current_segment': Node['current_segment'],
            'cumulative_segment_list': cumulative_segment_list,  # Keep original list
            'cumulative_time_list': cumulative_time_list[1:],  # Remove first element without modifying original
            'weather_forecasts_list': Node['weather_forecasts_list'][1:],  # Remove first element without modifying original
            'Elapsed_time': Node['Elapsed_time'] + Time_to_forecast_window,
            'Elapsed_distance': Node['Elapsed_distance'] + SOG * Time_to_forecast_window,
            'incoming_arc': {
            'Incoming_node': Node.copy(),  # Make a copy to preserve the state
            'SWS': speed,
            'SOG': SOG,
            'Travel_time': Time_to_forecast_window,
            #'Distance': SOG * (forecast_window - Node['Elapsed_time']),
            'Distance': SOG * Time_to_forecast_window,
            'FCR': calculate_fuel_consumption_rate(speed),
            'Fuel_consumption': calculate_fuel_consumption_rate(speed) * Time_to_forecast_window } ,
            'node_index': node_index

        }
    return NewNode


def CreateNodes(Node, speed_values, node_index, ship_parameters=None):

    New_Nodes = []  
    
    for i, speed in enumerate(speed_values):
        new_node = CreateNode(Node, speed, node_index, ship_parameters)
        if new_node is not None:
            New_Nodes.append(new_node)
    print(f"Total new nodes created: {len(New_Nodes)}")
    print("--- End Node Creation ---\n")
    
    return New_Nodes





import yaml
import numpy as np
from utility_functions import calculate_speed_over_ground, calculate_travel_time, calculate_fuel_consumption_rate



def calculate_fuel_consumption_rate(speed):
    return 0.000706 * speed**3

def calculate_speed_over_ground(speed):
    return speed


def CreateNode(Node, speed,node_index):

    SOG = calculate_speed_over_ground(speed)
    
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


def CreateNodes(Node,speed_values,node_index):
    New_Nodes = []  
    
    for i, speed in enumerate(speed_values):
        new_node = CreateNode(Node, speed,node_index)
        if new_node is not None:
            New_Nodes.append(new_node)
    print(f"Total new nodes created: {len(New_Nodes)}")
    print("--- End Node Creation ---\n")
    
    return New_Nodes



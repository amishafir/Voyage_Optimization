

import yaml
import numpy as np
from CreteNodes import CreateNodes
from tqdm import tqdm
import math
import bisect
from utility_functions import calculate_speed_over_ground



class Node:
    def __init__(self):
        self.node_index = None  # Will be set as a tuple (time, distance)
        self.minimal_input_arc = None
        self.minimal_fuel_consumption = math.inf
        self.arcs = []

class Side:
    def __init__(self):
        self.type = None
        self.coordinates = None
        self.side_creator_list = []
        # self.next_vertical_boundary_side = None
        # self.next_horizontal_boundary_side = None
        self.nodes = []


class Arc:
    def __init__(self):
        self.Source_node = None
        self.Destination_node = None
        self.SWS = None
        self.SOG = None # Speed Over Ground
        self.Travel_time = None # Travel time
        self.Distance = None # Distance
        self.FCR = None # Fuel Consumption Rate
        self.fuel_load = None # Fuel load        


class optimizer:
    def __init__(self):
        self.ship_parameters_data = self.load_ship_parameters()
        self.ship_parameters = self.ship_parameters_data.get('ship_parameters', {})
        self.speed_values = self.load_speed_values()
        self.time_granularity = self.load_time_granularity()
        self.distance_granularity = self.load_distance_granularity()
        self.weather_forecasts = self.load_weather_forecasts()
        self.cumulative_segment_list = self.create_cumulative_segment_list()
        self.cumulative_time_list = self.create_cumulative_time_list()
        self.weather_forecasts_list = self.create_weather_forecasts_list()
        self.speed_values_list = self.create_speed_values_list()
        self.graph = self.create_graph()
        self.fit_graph()
        self.solution_path = self.find_solution_path()
        # self.display_solution_path()

    
    def load_ship_parameters(self):
        """Load ship parameters from YAML file"""
        try:
            with open('/Users/ami/Desktop/university/Dynamic speed optimization/ship_parameters.yaml', 'r') as file:
                return yaml.safe_load(file)
        except FileNotFoundError:
            print("Warning: ship_parameters.yaml not found")
            return {}

    def load_weather_forecasts(self):
        """Load weather forecasts from YAML file"""
        try:
            with open('/Users/ami/Desktop/university/Dynamic speed optimization/weather_forecasts.yaml', 'r') as file:
                data = yaml.safe_load(file)
                # The YAML file contains a list of forecasts directly, not wrapped in a 'forecasts' key
                if isinstance(data, list):
                    return data
                else:
                    # Fallback: try to get 'forecasts' key if the structure is different
                    return data.get('forecasts', [])
        except FileNotFoundError:
            print("Warning: weather_forecasts.yaml not found")
            return []

    def create_cumulative_segment_list(self):
        """Create cumulative segment list with cumulative distances"""
        if not self.weather_forecasts:
            return []
        
        # Get segments from the first forecast window (assuming all windows have same segments)
        first_forecast = self.weather_forecasts[0]
        segments = first_forecast.get('segments_table', [])
        
        cumulative_distances = []
        cumulative_distance = 0
        
        for segment in segments:
            # Round each segment distance first, then add to cumulative
            segment_distance = round(segment.get('distance', 0))
            cumulative_distance += segment_distance
            cumulative_distances.append(cumulative_distance)
        print(f"cumulative_distances: {cumulative_distances}")
        return cumulative_distances

    def create_cumulative_time_list(self):
        """Create cumulative time list from forecast windows"""
        if not self.weather_forecasts:
            return []
        
        cumulative_times = []
        for forecast in self.weather_forecasts:
            forecast_window = forecast.get('forecast_window', {})
            end_time = forecast_window.get('end', 0)
            cumulative_times.append(end_time)
        print(f"cumulative_times: {cumulative_times}")
        return cumulative_times

    def create_weather_forecasts_list(self):
        """Create weather forecasts list with segment dictionaries for each forecast window"""
        if not self.weather_forecasts:
            return []
        
        processed_forecasts = []
        
        for forecast in self.weather_forecasts:
            segments_table = forecast.get('segments_table', [])
            segment_dict = {}
            
            for segment in segments_table:
                segment_id = segment.get('id')
                if segment_id is not None:
                    # Create dictionary with all segment parameters except id
                    segment_data = {k: v for k, v in segment.items() if k != 'id'}
                    segment_dict[segment_id] = segment_data
            
            processed_forecasts.append(segment_dict)
            
        print(f"processed_forecasts: {processed_forecasts[0][1]}")
        return processed_forecasts

    def load_speed_values(self):
        """Load speed values from ship parameters YAML file"""
        try:
            # Extract speed constraints from ship parameters data
            speed_constraints = self.ship_parameters_data.get('speed_constraints', {})
            min_speed = speed_constraints.get('min_speed')
            max_speed = speed_constraints.get('max_speed')
            speed_granularity = speed_constraints.get('speed_granularity', 1.0)
            
            # Create speed range array
            speed_range = (min_speed, max_speed)
            return np.arange(speed_range[0], speed_range[1] + speed_granularity, speed_granularity)
        except Exception as e:
            print(f"Warning: Error loading speed values from ship parameters: {e}")
            # Fallback to default values
            return np.arange(10.0, 21.0, 1.0)

    def load_time_granularity(self):
        """Load time granularity from ship parameters YAML file"""
        try:
            speed_constraints = self.ship_parameters_data.get('speed_constraints', {})
            time_granularity = speed_constraints.get('time_granularity', 1.0)
            return float(time_granularity)
        except Exception as e:
            print(f"Warning: Error loading time granularity from ship parameters: {e}")
            # Fallback to default value
            return 1.0

    def load_distance_granularity(self):
        """Load distance granularity from ship parameters YAML file"""
        try:
            speed_constraints = self.ship_parameters_data.get('speed_constraints', {})
            distance_granularity = speed_constraints.get('distance_granularity', 10.0)
            return float(distance_granularity)
        except Exception as e:
            print(f"Warning: Error loading distance granularity from ship parameters: {e}")
            # Fallback to default value
            return 10.0

    def create_speed_values_list(self):
        """Create speed values list for optimization"""
        # This could be customized based on requirements
        return [round(num, 1) for num in self.speed_values.tolist()
]

    

    def display_processed_data(self):
        """Display the processed weather forecast data"""
        print("\n=== PROCESSED WEATHER FORECAST DATA ===")
        print(f"Speed values: {self.speed_values}")
        print(f"Cumulative segment list: {self.cumulative_segment_list}")
        print(f"Cumulative time list: {self.cumulative_time_list}")
        print(f"Weather forecasts list: {len(self.weather_forecasts_list)} forecast windows")
        

    def create_graph(self):
        """Create a 2D graph discretized by distance and time using granularity from ship parameters"""
        
        # Get the maximum cumulative distance and time
        if not self.cumulative_segment_list or not self.cumulative_time_list:
            return np.array([])
        
        max_distance = max(self.cumulative_segment_list)
        max_time = max(self.cumulative_time_list)
        
        # Discretize distance using distance_granularity from ship parameters
        # Columns represent distance: 0, granularity, 2*granularity, ... up to max_distance
        self.distance_segments = np.arange(0, max_distance + self.distance_granularity, self.distance_granularity)
        
        # Discretize time using time_granularity from ship parameters
        # Rows represent time: 0, granularity, 2*granularity, ... up to max_time
        self.time_segments = np.arange(0, max_time + self.time_granularity, self.time_granularity)
        
        # Create 2D array to hold nodes
        # Shape: (num_time_segments, num_distance_segments)
        graph = np.empty((len(self.time_segments), len(self.distance_segments)), dtype=object)
        
        # Fill each cell with an empty node object in the format of create_start_node
        for i, time in enumerate(self.time_segments):
            for j, distance in enumerate(self.distance_segments):
                # Determine current segment based on elapsed distance
                # Segment 1: distance <= cumulative_segment_list[0]
                # Segment 2: cumulative_segment_list[0] < distance <= cumulative_segment_list[1]
                # etc.
                current_segment = 1
                for seg_idx, cum_dist in enumerate(self.cumulative_segment_list):
                    if distance <= cum_dist:
                        current_segment = seg_idx + 1
                        break
                    # If distance exceeds all segments, keep it at the last segment
                    if seg_idx == len(self.cumulative_segment_list) - 1:
                        current_segment = len(self.cumulative_segment_list)
                
                # Check if node is exactly on a time window boundary
                time_tolerance = 1e-6  # Small tolerance for floating point comparison
                is_on_time_boundary = False
                for cum_time in self.cumulative_time_list:
                    if abs(time - cum_time) <= time_tolerance:
                        is_on_time_boundary = True
                        break
                
                # Check if node is exactly on a segment distance boundary
                distance_tolerance = 1e-6  # Small tolerance for floating point comparison
                is_on_distance_boundary = False
                for cum_dist in self.cumulative_segment_list:
                    if abs(distance - cum_dist) <= distance_tolerance:
                        is_on_distance_boundary = True
                        break
                
                # Create a Node instance with node_index as a tuple (time, distance)
                node = Node()
                node.node_index = (float(time), float(distance))
                graph[i, j] = node
        
        return graph 



    def fit_graph(self):
        Sides_queue = []
        Sides_queue.append(self.create_initial_side())
        vertical_boundary_side = Side()
        horizontal_boundary_side = Side()

        
        while Sides_queue:
            current_side = Sides_queue.pop(0)
            print(f"current_side type: {current_side.type}")
            print(f"current_side index: {current_side.nodes[-1].node_index}")


            if current_side.type == 'vertical' and abs(current_side.coordinates[1] - self.distance_segments[-1]) != 0.0 :
                vertical_boundary_side,horizontal_boundary_side  = self.locate_sides(current_side)

            if current_side.type == 'horizontal' and abs(current_side.coordinates[0] - self.cumulative_time_list[-1]) != 0.0 :
                vertical_boundary_side,horizontal_boundary_side = self.locate_sides(current_side)

            if vertical_boundary_side is not None:
                print(f"connecting vertical_boundary_side: {vertical_boundary_side.nodes[-1].node_index}")
                self.connect_sides(current_side, vertical_boundary_side)
                Sides_queue.append(vertical_boundary_side)
            if horizontal_boundary_side is not None:
                print(f"connecting horizontal_boundary_side: {horizontal_boundary_side.nodes[-1].node_index}")
                self.connect_sides(current_side, horizontal_boundary_side)
                Sides_queue.append(horizontal_boundary_side)


            vertical_boundary_side = None
            horizontal_boundary_side = None

        
        return Sides_queue


    def create_initial_side(self):
        print(self.time_segments[-1])
        initial_side = Side()
        initial_side.type = 'vertical'
        initial_side.index = (0,0)
        # Calculate row indices for times from 0 to cumulative_time_list[0]
        # Find which row indices in time_segments correspond to these times
        row_indices = []
        tolerance = 1e-6
        for i, time_val in enumerate(self.time_segments):
            if time_val <= self.cumulative_time_list[0] + tolerance:
                row_indices.append(i)
            else:
                break
        
        column_index = 0  # Distance = 0 (starting point)
        initial_side.coordinates = (row_indices, column_index)
        initial_side.side_creator_list.append(None)
        print(f"initial_side index: {initial_side.index}")
        # Fetch all nodes from the graph using coordinates
        # coordinates = (row_indices_list, column_index)
        initial_side.nodes = [self.graph[row_idx, column_index] for row_idx in row_indices]
        print(f"initial_side.nodes: {len(initial_side.nodes)}")
        print(f"first node: {initial_side.nodes[0].node_index}")
        print(f"last node: {initial_side.nodes[-1].node_index}")
        return initial_side

    def get_next_value_in_list(self, value, value_list):
        """Get the next value in a list given a value.
        
        Args:
            value: The value to find in the list
            value_list: The list to search in
            
        Returns:
            The next value in the list, or None if not found or at the end.
        """
        tolerance = 1e-6
        for idx, val in enumerate(value_list):

            if value == 0:
                return value_list[0]
                break
            elif value == val:
                return value_list[idx + 1]
                break
        

    def locate_sides(self, side):
        tolerance = 1e-6
        if side.type == 'vertical':
            vertical_side = Side()
            vertical_side.type = 'vertical'
            time_coordinates = side.coordinates[0]
            distance_coordinates = self.get_next_value_in_list(side.coordinates[1], self.cumulative_segment_list)
            vertical_side.coordinates = (time_coordinates, distance_coordinates)
            vertical_side.nodes = [self.graph[row_idx, distance_coordinates] for row_idx in time_coordinates]
            vertical_side.side_creator_list.append(side)
 
            # print(f"vertical_side.nodes: {vertical_side.nodes[-1].node_index}")
            

            horizontal_side = Side()
            horizontal_side.type = 'horizontal'
            time_coordinates = side.nodes[-1].node_index[0]
            distance_coordinates = []
            for distance_coordinate in self.distance_segments:
                if distance_coordinate > side.nodes[-1].node_index[1]  + tolerance and distance_coordinate < vertical_side.coordinates[1]  - tolerance:
                    distance_coordinates.append(int(distance_coordinate))
            horizontal_side.coordinates = (time_coordinates, distance_coordinates)
            for col_idx in distance_coordinates:
                horizontal_side.nodes.append(self.graph[int(time_coordinates), int(col_idx)])
            horizontal_side.side_creator_list.append(side)# print(f"horizontal_side.nodes: {horizontal_side.nodes[-1].node_index}")
            return vertical_side, horizontal_side



        elif side.type == 'horizontal':
            tolerance = 1e-6
            horizontal_side = Side()
            horizontal_side.type = 'horizontal'
            time_coordinates = self.get_next_value_in_list(side.coordinates[0], self.cumulative_time_list)
            distance_coordinates = side.coordinates[1]
            horizontal_side.coordinates = (time_coordinates, distance_coordinates)
            horizontal_side.nodes = [self.graph[time_coordinates, col_idx] for col_idx in distance_coordinates]
            horizontal_side.side_creator_list.append(side)# print(f"horizontal_side.nodes: {horizontal_side.nodes[-1].node_index}")


            vertical_side = Side()
            vertical_side.type = 'vertical'
            distance_coordinates = int(side.nodes[-1].node_index[1] + self.distance_granularity)

            time_coordinates = []
            for time_coordinate in self.time_segments:
                if time_coordinate >= side.nodes[-1].node_index[0]  and time_coordinate <= round(horizontal_side.coordinates[0]) :
                    time_coordinates.append(int(time_coordinate))
            vertical_side.coordinates = (time_coordinates, distance_coordinates)
            vertical_side.nodes = [self.graph[row_idx, distance_coordinates] for row_idx in time_coordinates]
            vertical_side.side_creator_list.append(side)
            return vertical_side, horizontal_side

        
        # return vertical_side, horizontal_side

    def calculate_sws_from_sog(self, target_sog, segment_data, tolerance=0.001, max_iterations=50):
        """
        Calculate the required SWS to achieve a target SOG using iterative binary search.
        
        This is the inverse function of SOG calculation - given a desired SOG and weather conditions,
        it finds the required SWS using binary search.
        
        Args:
            target_sog: Desired Speed Over Ground (knots)
            segment_data: Dictionary containing segment weather data
            tolerance: Convergence tolerance for SOG difference (default: 0.001 knots)
            max_iterations: Maximum number of iterations (default: 50)
            
        Returns:
            float: Calculated SWS, or target_sog as fallback if calculation fails
        """
        try:
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
            
            # Binary search bounds - reasonable SWS range
            min_sws = 5.0  # Minimum reasonable SWS
            max_sws = 20.0  # Maximum reasonable SWS
            
            # Check if target SOG is achievable by testing bounds
            min_sog = calculate_speed_over_ground(
                ship_speed=min_sws,
                ocean_current=current_speed,
                current_direction=current_dir_rad,
                ship_heading=ship_heading_rad,
                wind_direction=wind_dir_rad,
                beaufort_scale=beaufort_scale,
                wave_height=wave_height,
                ship_parameters=self.ship_parameters
            )
            
            max_sog = calculate_speed_over_ground(
                ship_speed=max_sws,
                ocean_current=current_speed,
                current_direction=current_dir_rad,
                ship_heading=ship_heading_rad,
                wind_direction=wind_dir_rad,
                beaufort_scale=beaufort_scale,
                wave_height=wave_height,
                ship_parameters=self.ship_parameters
            )
            
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
            
            for iteration in range(max_iterations):
                # Test middle point
                test_sws = (min_sws + max_sws) / 2.0
                
                # Calculate SOG for this SWS using weather data
                calculated_sog = calculate_speed_over_ground(
                    ship_speed=test_sws,
                    ocean_current=current_speed,
                    current_direction=current_dir_rad,
                    ship_heading=ship_heading_rad,
                    wind_direction=wind_dir_rad,
                    beaufort_scale=beaufort_scale,
                    wave_height=wave_height,
                    ship_parameters=self.ship_parameters
                )
                
                # Calculate error from target SOG
                error = abs(calculated_sog - target_sog)
                
                # Track best result
                if error < best_error:
                    best_error = error
                    best_sws = test_sws
                
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
            
            # Return best SWS found, or fallback to target_sog if no good match
            if best_sws is not None and best_error < 0.1:  # Accept if error is less than 0.1 knots
                return best_sws
            else:
                # Fallback: return target_sog as approximation
                return target_sog
                
        except Exception as e:
            # If any error occurs, fallback to target_sog as approximation
            return target_sog

    def connect_sides(self, source_side, destination_side ):
        for s_node in source_side.nodes:
            for d_node in destination_side.nodes:
                arc = self.connect(s_node, d_node)
                if arc is not None:
                    d_node.arcs.append(arc)
                    if d_node.minimal_fuel_consumption > arc.fuel_load + arc.fuel_consumption:
                        d_node.minimal_fuel_consumption = arc.fuel_load + arc.fuel_consumption
                        # print(f"d_node.node_index: {d_node.node_index}")
                        # print(f"graph node minimal_fuel_consumption: {self.graph[int(d_node.node_index[0]), int(d_node.node_index[1])].minimal_fuel_consumption}")
                        # print(f"d_node.minimal_fuel_consumption: {d_node.minimal_fuel_consumption}")
                        d_node.minimal_input_arc = arc
        return

    def connect(self, source_node, destination_node):
        
        # Calculate distance and time differences
        distance_diff = destination_node.node_index[1] - source_node.node_index[1]
        time_diff = destination_node.node_index[0] - source_node.node_index[0]
         # Calculate required Speed Over Ground (SOG) from distance and time
        # Check for valid values
        if time_diff <= 0:
            # print(f"source_node: {source_node.node_index}")
            # print(f"destination_node: {destination_node.node_index}")
            # print(f"time_diff is negative: {time_diff}")
            return None  # Can't have zero or negative time
        # Check if distance is negative
        if distance_diff <= 0:
            # print(f"source_node: {source_node.node_index}")
            # print(f"destination_node: {destination_node.node_index}")
            # print(f"distance_diff is negative: {distance_diff}")
            return None
        sog = round(distance_diff / time_diff, 1)
        # Check if required SOG is in the speed values list
        if sog not in self.speed_values_list:
            # print(f"sog: {sog}")
            # print(f"speed_values: {self.speed_values}")
            # print(f"sog is not in speed values list: {sog}")
            return None
        
        # Calculate Fuel Consumption Rate (FCR) - using the formula from CreteNodes
        # FCR = 0.000706 * speed^3 (in kg/hour)
        # Get the correct forecast window index and segment ID based on the source node
        
        segment_id = int(source_node.node_index[1])
        
        # Find the position where value would be inserted
        #cumulative_distances = [224, 507, 810, 1108, 1389, 1676, 1960, 2193, 2495, 2811, 3105, 3393]


        for i in range(len(self.cumulative_segment_list)):
            if segment_id < self.cumulative_segment_list[i]:
                if i == 0:
                    print(f"Value {segment_id} is before index 0")
                    index_of_segment = 1
                    segment_data = self.weather_forecasts_list[0][index_of_segment]
                    # print(f"segment_data: {segment_data}")
                else:
                    print(f"position === between index {i - 1} and index {i}")
                    index_of_segment = i
                    segment_data = self.weather_forecasts_list[0][index_of_segment]
                    # print(f"segment_data: {segment_data}")
                break
        else:
            print(f"Value {segment_id} is after the last index")
            index_of_segment = len(self.cumulative_segment_list) - 1
            segment_data = self.weather_forecasts_list[0][index_of_segment]
            # print(f"segment_data: {segment_data}")
# Output: position === between index 1 and index 2
    
# Output: position === between index 1 and index 2
        

        
        # print(" --------------------------------")
        
        # Get segment data for the specific forecast window and segment
        segment_data = self.weather_forecasts_list[0][index_of_segment]
        sws = self.calculate_sws_from_sog(sog, segment_data)
        fcr = 0.000706 * (sws ** 3)
        # Calculate total fuel consumption
        arc_fuel_consumption = fcr * time_diff
     # Create the arc object
        arc = Arc()
        arc.Source_node = source_node.node_index
        arc.SWS = sws  # Ship Water Speed
        arc.SOG = sog  # Speed Over Ground
        arc.Travel_time = time_diff # Travel time
        arc.Distance = distance_diff # Distance
        arc.FCR = fcr  # Fuel Consumption Rate
        arc.fuel_consumption = arc_fuel_consumption
        # Calculate fuel load: if source node has no fuel consumption yet, start from 0
        if source_node.node_index[1] == 0:
            arc.fuel_load = 0
        else:
            arc.fuel_load = source_node.minimal_fuel_consumption
        return arc





    def find_solution_path(self):
        """Display the solution path with node indices and fuel consumption."""

        
        print("\n" + "=" * 60)
        print("Optimal Solution Path:")
        
        print("=" * 60)
        destination_nodes = []


        for node in self.graph.flatten():
            if node.node_index[1] == self.graph.shape[1] - 1 and node.minimal_fuel_consumption != math.inf:
                node.index = node.node_index
                destination_nodes.append(node)
                # print(f"node.node_index: {node.index}")
                # print(f"node.minimal_fuel_consumption: {node.minimal_fuel_consumption}")
        
        destination_node = sorted(destination_nodes, key=lambda x: x.minimal_fuel_consumption).pop(0)
        print(f"destination_node: {destination_node.minimal_fuel_consumption}")
        while(1):
            if destination_node.node_index[1] == 0:
                print(f"start_node: {destination_node.node_index}")
                print(f"destination_node minimal_fuel_consumption: {destination_node.minimal_fuel_consumption}")
                break
            print(f"current node: {destination_node.node_index}")
            print(f"current node minimal_fuel_consumption: {destination_node.minimal_fuel_consumption}")
            destination_node = self.graph[int(destination_node.minimal_input_arc.Source_node[0]), int(destination_node.minimal_input_arc.Source_node[1])]

        return 




def main():
    """Main function to run the speed control optimization"""
    print("Starting Speed Control Optimization")
    print("=" * 50)

    # Create optimizer instance (it loads all data internally)
    print("\nInitializing optimizer...")
    opt = optimizer()

    # # Display processed data
    opt.display_processed_data()

#    opt.find_solution_path()
    


   

if __name__ == "__main__":
    main()

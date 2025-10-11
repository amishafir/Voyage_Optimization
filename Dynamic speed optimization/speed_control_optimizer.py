

import yaml
import numpy as np
from CreteNodes import CreateNodes
from tqdm import tqdm

class optimizer:
    def __init__(self):
        self.ship_parameters = self.load_ship_parameters()
        self.speed_values = self.load_speed_values()
        self.weather_forecasts = self.load_weather_forecasts()
        self.cumulative_segment_list = self.create_cumulative_segment_list()
        self.cumulative_time_list = self.create_cumulative_time_list()
        self.weather_forecasts_list = self.create_weather_forecasts_list()
        self.speed_values_list = self.create_speed_values_list()
        self.start_node = self.create_start_node()
        self.destination_nodes = []
        self.graph = self.create_graph()
        self.optimize_speed_policy = self.solve()

    
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
            cumulative_distance += segment.get('distance', 0)
            cumulative_distances.append(cumulative_distance)
        
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
        
        return processed_forecasts

    def load_speed_values(self):
        """Load speed values from ship parameters YAML file"""
        try:
            # Extract speed constraints from ship parameters
            speed_constraints = self.ship_parameters.get('speed_constraints', {})
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

    def create_speed_values_list(self):
        """Create speed values list for optimization"""
        # This could be customized based on requirements
        return self.speed_values.tolist()

    def create_start_node(self):
        """Return the start node configuration"""
        Start_node = {
        'current_segment': 1,
        'cumulative_segment_list': self.create_cumulative_segment_list(),
        'cumulative_time_list': self.create_cumulative_time_list(),
        'weather_forecasts_list': self.create_weather_forecasts_list(),
        'Elapsed_time': 0,
        'Elapsed_distance': 0,
        'comulative_fuel_consumption': 0,
        'incoming_arc': {
        'Incoming_node': {},
        'SWS': 0,  # Ship Water Speed
        'SOG': 0,  # Speed Over Ground
        'Travel_time': 0,
        'Distance': 0,
        'FCR': 0,  # Fuel Consumption Rate
        'Fuel_consumption': 0 
    },
        'node_index': 0
}
        return Start_node.copy()

    

    def display_processed_data(self):
        """Display the processed weather forecast data"""
        print("\n=== PROCESSED WEATHER FORECAST DATA ===")
        print(f"Speed values: {self.speed_values}")
        print(f"Cumulative segment list: {self.cumulative_segment_list}")
        print(f"Cumulative time list: {self.cumulative_time_list}")
        print(f"Weather forecasts list: {len(self.weather_forecasts_list)} forecast windows")
        
        print(f"\nStart node:")
        print(f"  Current segment: {self.start_node['current_segment']}")
        print(f"  Elapsed time: {self.start_node['Elapsed_time']}")
        print(f"  Elapsed distance: {self.start_node['Elapsed_distance']}")
        print(f"  Cumulative fuel consumption: {self.start_node['comulative_fuel_consumption']}")
        print(f"  Incoming arc:")
        print(f"    Still Water Speed (SWS): {self.start_node['incoming_arc']['SWS']}")
        print(f"    Speed Over Ground (SOG): {self.start_node['incoming_arc']['SOG']}")
        print(f"    Travel time: {self.start_node['incoming_arc']['Travel_time']}")
        print(f"    Distance: {self.start_node['incoming_arc']['Distance']}")
        print(f"    Fuel Consumption Rate (FCR): {self.start_node['incoming_arc']['FCR']}")
        print(f"    Fuel consumption: {self.start_node['incoming_arc']['Fuel_consumption']}")
        
        # for i, forecast in enumerate(self.weather_forecasts_list):
        #     print(f"\nForecast window {i+1}:")
        #     for segment_id, segment_data in forecast.items():
        #         print(f"  Segment {segment_id}: {segment_data}")
        # print("=" * 50)
        

    def create_graph(self):
        print("Creating optimization graph...")
        Graph = [self.start_node]
        destination_nodes = []
        
        # Process each node in the graph until no new nodes are created
        i = 0
        while i < len(Graph):
            Node = Graph[i]
            if len(Node['cumulative_segment_list']) > 0:
                new_nodes = CreateNodes(Node, self.speed_values,i)
                Graph.extend(new_nodes)
                print(f"Graph now contains {len(Graph)} nodes")
                i += 1
            else:
                self.destination_nodes.append(Graph[i])
                i += 1

        # Graph creation summary
        print(f"\n=== GRAPH SUMMARY ===")
        print(f"Total nodes created: {len(Graph)}")
        
        # Show final nodes (last few nodes created)
        print(f"\nFinal nodes:")
        for i, node in enumerate(destination_nodes):  # Show last 3 nodes
            print(f"   {i+1}: Elapsed_time={node['Elapsed_time']:.2f}, Elapsed_distance={node['Elapsed_distance']:.2f}, Cumulative_fuel_consumption={node['comulative_fuel_consumption']:.2f}")
        print("=" * 25)

        # Add your graph creation logic here
        return Graph 

    def solve(self):
        """Return optimize_route"""
        print("Solving optimize speed policy ...")
        destination_node =  min(self.destination_nodes, key=lambda node: node['comulative_fuel_consumption'])       # Find the node with minimum cumulative fuel consumption
        print(f"Optimal node found with fuel consumption: {destination_node['comulative_fuel_consumption']:.2f}")

        # Trace back the optimal path
        """Trace back from destination node to start node"""
        print("\n=== OPTIMAL PATH TRACE ===")
        
        current_node = destination_node
        step = 0
        optimize_speed_policy = []
        
        while True:
            # Print current node details
            optimize_speed_policy.append(current_node)  
            # print(f"Step {step}: Node {current_node.get('node_index', 'Unknown')}")
            # print(f"  Elapsed_time: {current_node['Elapsed_time']:.2f}")
            # print(f"  Elapsed_distance: {current_node['Elapsed_distance']:.2f}")
            # print(f"  Cumulative_fuel_consumption: {current_node['comulative_fuel_consumption']:.2f}")
            
            # Check if we've reached the start node (node_index = 0)
            if current_node.get('node_index') == 0:
                print("  -> START NODE REACHED")
                break
            
            # Get the incoming node
            incoming_arc = current_node.get('incoming_arc', {})
            incoming_node = incoming_arc.get('Incoming_node', {})
            #print(f"  Incoming node: {incoming_node}")
            
            if not incoming_node:
                print("  -> No incoming node found, path trace incomplete")
                break
            
            # Move to the previous node
            current_node = incoming_node
            step += 1
            
        optimize_speed_policy.reverse()  # Reverse to get start -> destination order
        self.optimize_speed_policy = optimize_speed_policy  # Store the policy
        print(f"\nOptimal speed policy contains {len(optimize_speed_policy)} nodes")
        return optimize_speed_policy 
       


def main():
    """Main function to run the speed control optimization"""
    print("Starting Speed Control Optimization")
    print("=" * 50)

    # Create optimizer instance (it loads all data internally)
    print("\nInitializing optimizer...")
    opt = optimizer()

    # Display processed data
    opt.display_processed_data()

    # Print the optimal speed policy (already computed in constructor)
    print("\n=== OPTIMAL SPEED POLICY ===")
    for i, node in enumerate(opt.optimize_speed_policy):
        print(f"Step {i}:")
        if 'incoming_arc' in node and node['incoming_arc']:
            arc = node['incoming_arc']
            print(f"  Sailing time: {arc.get('Travel_time', 'N/A')} hours")
            print(f"  Engine speed (SWS): {arc.get('SWS', 'N/A')}")
            print(f"  Speed over Ground (SOG): {arc.get('SOG', 'N/A')}")
        print(f"  Time from departure: {node['Elapsed_time']:.2f}")
        print(f"  Cumulative fuel consumption: {node['comulative_fuel_consumption']:.2f}")
        print(f"  Distance traveled: {node['Elapsed_distance']:.2f}")
        print()
    print("\n" + "=" * 50)
    print("Speed Control Optimization completed!")
    print("=" * 50)
   

if __name__ == "__main__":
    main()

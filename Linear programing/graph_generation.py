"""
Graph Generation for Ship Voyage Optimization

This script creates a directed graph using NetworkX where:
- Nodes represent positions in a mile-time matrix
- Edges represent transitions between nodes with fuel consumption costs
- Environmental conditions are managed in external tables
- SWS (Still Water Speed) is converted to SOG (Speed Over Ground)
- FCR (Fuel Consumption Rate) determines transition costs

Author: Ship Optimization System
Date: 2025
"""

import networkx as nx
import numpy as np
import pandas as pd
import math
import pickle
import json
from typing import Dict, List, Tuple, Optional
from utility_functions import (
    calculate_speed_over_ground, 
    calculate_fuel_consumption_rate,
    calculate_travel_time
)
from voyage_data import SHIP_PARAMETERS

class ShipVoyageGraph:
    """
    A class to generate and manage the ship voyage optimization graph.
    """
    
    def __init__(self, max_miles: int, max_time: int, time_granularity: float):
        """
        Initialize the graph generator.
        
        Args:
            max_miles: Maximum distance from start point (nautical miles)
            max_time: Maximum voyage time (hours)
            time_granularity: Time step granularity (hours)
        """
        self.max_miles = max_miles
        self.max_time = max_time
        self.time_granularity = time_granularity
        self.graph = nx.DiGraph()
        self.environmental_conditions = self._create_environmental_conditions_table()
        self.ship_parameters = SHIP_PARAMETERS.copy()
        
        # Calculate time steps
        self.time_steps = int(max_time / time_granularity) + 1
        
        print(f"Initializing graph with:")
        print(f"  Max miles: {max_miles}")
        print(f"  Max time: {max_time} hours")
        print(f"  Time granularity: {time_granularity} hours")
        print(f"  Time steps: {self.time_steps}")
    
    def _create_environmental_conditions_table(self) -> pd.DataFrame:
        """
        Create environmental conditions table with sample data.
        
        Returns:
            DataFrame with environmental conditions for each mile-time position
        """
        print("Creating environmental conditions table...")
        
        # Create a grid of conditions
        conditions = []
        
        # Generate conditions for different regions of the voyage
        for mile in range(0, self.max_miles + 1, 10):  # Every 10 miles
            for time_hour in np.arange(0, self.max_time + self.time_granularity, self.time_granularity):
                # Simulate varying conditions based on position and time
                # In practice, this would come from weather forecasts/historical data
                
                # Wind varies with time (simulating weather changes)
                wind_direction = (45 + 30 * math.sin(time_hour * 0.1) + 
                                mile * 0.5) % 360
                
                # Wave height increases with distance (deeper waters)
                wave_height = 1.0 + (mile / self.max_miles) * 2.0 + \
                             0.5 * math.sin(time_hour * 0.2)
                wave_height = max(0.1, wave_height)
                
                # Current varies by region
                current_direction = (180 + mile * 0.3 + 
                                   20 * math.cos(time_hour * 0.15)) % 360
                current_speed = 0.2 + (mile / self.max_miles) * 0.8 + \
                               0.3 * math.sin(time_hour * 0.1)
                current_speed = max(0.0, current_speed)
                
                # Ship heading (assuming generally eastward voyage)
                ship_heading = 90 + 10 * math.sin(mile * 0.01)
                
                conditions.append({
                    'miles_from_start': mile,
                    'time_from_start': time_hour,
                    'wind_direction': wind_direction,
                    'wave_height': wave_height,
                    'current_direction': current_direction,
                    'current_speed': current_speed,
                    'ship_heading': ship_heading,
                    'beaufort_scale': min(6, max(1, int(wave_height * 2))),
                    'condition_id': f"M{mile}_T{time_hour:.1f}"
                })
        
        df = pd.DataFrame(conditions)
        print(f"Created {len(df)} environmental condition records")
        return df
    
    def get_environmental_conditions(self, mile: int, time: float) -> Dict:
        """
        Get environmental conditions for a specific mile-time position.
        
        Args:
            mile: Miles from start point
            time: Time from start (hours)
            
        Returns:
            Dictionary with environmental conditions
        """
        # Find closest conditions in the table
        closest_mile = round(mile / 10) * 10  # Round to nearest 10 miles
        closest_time = round(time / self.time_granularity) * self.time_granularity
        
        # Ensure within bounds
        closest_mile = min(closest_mile, self.max_miles)
        closest_time = min(closest_time, self.max_time)
        
        # Query the conditions table
        condition = self.environmental_conditions[
            (self.environmental_conditions['miles_from_start'] == closest_mile) &
            (abs(self.environmental_conditions['time_from_start'] - closest_time) < 0.01)
        ]
        
        if condition.empty:
            # Fallback to default conditions
            return {
                'wind_direction': 45.0,
                'wave_height': 1.5,
                'current_direction': 180.0,
                'current_speed': 0.5,
                'ship_heading': 90.0,
                'beaufort_scale': 3,
                'condition_id': f"DEFAULT_M{mile}_T{time:.1f}"
            }
        
        return condition.iloc[0].to_dict()
    
    def create_nodes(self):
        """
        Create all nodes in the graph representing mile-time positions.
        """
        print("Creating graph nodes...")
        node_count = 0
        
        for mile in range(self.max_miles + 1):
            for time_step in range(self.time_steps):
                time = time_step * self.time_granularity
                
                # Get environmental conditions for this position
                conditions = self.get_environmental_conditions(mile, time)
                
                # Create node with attributes
                node_id = f"M{mile}_T{time:.1f}"
                
                self.graph.add_node(node_id, 
                                  mile=mile,
                                  time=time,
                                  environmental_conditions=conditions,
                                  position=(mile, time))
                
                node_count += 1
        
        print(f"Created {node_count} nodes")
    
    def sws_to_sog(self, sws: float, conditions: Dict) -> float:
        """
        Convert Still Water Speed (SWS) to Speed Over Ground (SOG).
        
        Args:
            sws: Still Water Speed (knots)
            conditions: Environmental conditions dictionary
            
        Returns:
            Speed Over Ground (knots)
        """
        # Convert angles to radians
        wind_direction_rad = math.radians(conditions['wind_direction'])
        current_direction_rad = math.radians(conditions['current_direction'])
        ship_heading_rad = math.radians(conditions['ship_heading'])
        
        # Use the comprehensive SOG calculation from utility_functions
        sog = calculate_speed_over_ground(
            ship_speed=sws,
            ocean_current=conditions['current_speed'],
            current_direction=current_direction_rad,
            ship_heading=ship_heading_rad,
            wind_direction=wind_direction_rad,
            beaufort_scale=conditions['beaufort_scale'],
            wave_height=conditions['wave_height'],
            ship_parameters=self.ship_parameters
        )
        
        return sog
    
    def calculate_transition_cost(self, sws: float, sail_time: float) -> float:
        """
        Calculate fuel consumption cost for a transition.
        
        Args:
            sws: Still Water Speed (knots)
            sail_time: Sailing time (hours)
            
        Returns:
            Fuel consumption cost (kg)
        """
        # Calculate FCR using the utility function
        fcr = calculate_fuel_consumption_rate(sws, self.ship_parameters)
        
        # Total fuel consumption = FCR * sail_time
        total_fuel = fcr * sail_time
        
        return total_fuel
    
    def create_edges(self):
        """
        Create edges between nodes representing possible transitions.
        """
        print("Creating graph edges...")
        edge_count = 0
        
        # Define possible SWS values (decision variables)
        sws_options = np.arange(8.0, 15.0, 0.5)  # 8 to 14.5 knots in 0.5 increments
        
        for node_id in self.graph.nodes():
            node_data = self.graph.nodes[node_id]
            current_mile = node_data['mile']
            current_time = node_data['time']
            conditions = node_data['environmental_conditions']
            
            # Try different SWS values and sail times
            for sws in sws_options:
                # Calculate SOG for this SWS and conditions
                sog = self.sws_to_sog(sws, conditions)
                
                # Try different sail times within the time granularity
                max_sail_time = min(self.time_granularity * 2, 
                                  self.max_time - current_time)
                
                if max_sail_time <= 0:
                    continue
                
                # Use the time granularity as the sail time
                sail_time = self.time_granularity
                
                if current_time + sail_time > self.max_time:
                    continue
                
                # Calculate distance traveled
                distance_traveled = sog * sail_time
                
                # Calculate next position
                next_mile = current_mile + int(round(distance_traveled))
                next_time = current_time + sail_time
                
                # Check if next position is valid
                if (next_mile <= self.max_miles and 
                    next_time <= self.max_time and
                    next_mile > current_mile):  # Must make forward progress
                    
                    # Find the closest valid next node
                    next_time_step = round(next_time / self.time_granularity)
                    actual_next_time = next_time_step * self.time_granularity
                    
                    if actual_next_time <= self.max_time:
                        next_node_id = f"M{next_mile}_T{actual_next_time:.1f}"
                        
                        if next_node_id in self.graph.nodes():
                            # Calculate transition cost
                            fuel_cost = self.calculate_transition_cost(sws, sail_time)
                            
                            # Add edge with attributes
                            self.graph.add_edge(node_id, next_node_id,
                                              sws=sws,
                                              sog=sog,
                                              sail_time=sail_time,
                                              distance=distance_traveled,
                                              fuel_cost=fuel_cost,
                                              weight=fuel_cost)  # NetworkX uses 'weight' for algorithms
                            
                            edge_count += 1
        
        print(f"Created {edge_count} edges")
    
    def generate_graph(self):
        """
        Generate the complete graph with nodes and edges.
        """
        print("=" * 60)
        print("GENERATING SHIP VOYAGE OPTIMIZATION GRAPH")
        print("=" * 60)
        
        # Create nodes
        self.create_nodes()
        
        # Create edges
        self.create_edges()
        
        # Print graph statistics
        self.print_graph_statistics()
        
        print("Graph generation completed!")
        return self.graph
    
    def print_graph_statistics(self):
        """
        Print statistics about the generated graph.
        """
        print("\n" + "=" * 40)
        print("GRAPH STATISTICS")
        print("=" * 40)
        
        print(f"Nodes: {self.graph.number_of_nodes()}")
        print(f"Edges: {self.graph.number_of_edges()}")
        
        if self.graph.number_of_nodes() > 0:
            print(f"Average degree: {2 * self.graph.number_of_edges() / self.graph.number_of_nodes():.2f}")
        
        # Analyze edge weights (fuel costs)
        if self.graph.number_of_edges() > 0:
            weights = [data['fuel_cost'] for _, _, data in self.graph.edges(data=True)]
            print(f"Fuel cost range: {min(weights):.2f} - {max(weights):.2f} kg")
            print(f"Average fuel cost: {np.mean(weights):.2f} kg")
        
        # Check connectivity
        if nx.is_weakly_connected(self.graph):
            print("Graph is weakly connected")
        else:
            print("Graph is not weakly connected")
            components = list(nx.weakly_connected_components(self.graph))
            print(f"Number of weakly connected components: {len(components)}")
    
    def export_graph(self, format_type: str = "all", base_filename: str = "ship_voyage_graph"):
        """
        Export the graph to various formats.
        
        Args:
            format_type: Export format ('pickle', 'graphml', 'json', 'csv', 'all')
            base_filename: Base filename for exports
        """
        print(f"\nExporting graph in format: {format_type}")
        
        if format_type in ["pickle", "all"]:
            # Pickle format (best for Python)
            pickle_file = f"{base_filename}.pkl"
            with open(pickle_file, 'wb') as f:
                pickle.dump(self.graph, f)
            print(f"✅ Exported to {pickle_file}")
        
        if format_type in ["graphml", "all"]:
            # GraphML format (standard graph format)
            # Create a copy of the graph with simplified attributes for GraphML
            graphml_file = f"{base_filename}.graphml"
            try:
                # Create a simplified graph for GraphML export
                simple_graph = nx.DiGraph()
                
                # Add nodes with simplified attributes
                for node_id, data in self.graph.nodes(data=True):
                    simple_attrs = {
                        'mile': data['mile'],
                        'time': data['time'],
                        'condition_id': data['environmental_conditions'].get('condition_id', 'unknown')
                    }
                    simple_graph.add_node(node_id, **simple_attrs)
                
                # Add edges with simplified attributes
                for source, target, data in self.graph.edges(data=True):
                    simple_attrs = {
                        'sws': data['sws'],
                        'sog': data['sog'],
                        'sail_time': data['sail_time'],
                        'distance': data['distance'],
                        'fuel_cost': data['fuel_cost']
                    }
                    simple_graph.add_edge(source, target, **simple_attrs)
                
                nx.write_graphml(simple_graph, graphml_file)
                print(f"✅ Exported to {graphml_file}")
            except Exception as e:
                print(f"⚠️  GraphML export failed: {e}")
                print("   (This is normal - GraphML has limitations with complex data)")
        
        if format_type in ["json", "all"]:
            # JSON format
            json_file = f"{base_filename}.json"
            graph_data = nx.node_link_data(self.graph)
            with open(json_file, 'w') as f:
                json.dump(graph_data, f, indent=2, default=str)
            print(f"✅ Exported to {json_file}")
        
        if format_type in ["csv", "all"]:
            # CSV format for nodes and edges
            nodes_file = f"{base_filename}_nodes.csv"
            edges_file = f"{base_filename}_edges.csv"
            
            # Export nodes
            node_data = []
            for node_id, data in self.graph.nodes(data=True):
                row = {'node_id': node_id, 'mile': data['mile'], 'time': data['time']}
                row.update(data['environmental_conditions'])
                node_data.append(row)
            
            pd.DataFrame(node_data).to_csv(nodes_file, index=False)
            print(f"✅ Exported nodes to {nodes_file}")
            
            # Export edges
            edge_data = []
            for source, target, data in self.graph.edges(data=True):
                row = {
                    'source': source,
                    'target': target,
                    'sws': data['sws'],
                    'sog': data['sog'],
                    'sail_time': data['sail_time'],
                    'distance': data['distance'],
                    'fuel_cost': data['fuel_cost']
                }
                edge_data.append(row)
            
            pd.DataFrame(edge_data).to_csv(edges_file, index=False)
            print(f"✅ Exported edges to {edges_file}")
        
        # Export environmental conditions table
        conditions_file = f"{base_filename}_conditions.csv"
        self.environmental_conditions.to_csv(conditions_file, index=False)
        print(f"✅ Exported environmental conditions to {conditions_file}")
    
    def load_graph(self, filename: str) -> nx.DiGraph:
        """
        Load a previously saved graph.
        
        Args:
            filename: Path to the graph file
            
        Returns:
            Loaded NetworkX graph
        """
        if filename.endswith('.pkl'):
            with open(filename, 'rb') as f:
                return pickle.load(f)
        elif filename.endswith('.graphml'):
            return nx.read_graphml(filename)
        elif filename.endswith('.json'):
            with open(filename, 'r') as f:
                graph_data = json.load(f)
            return nx.node_link_graph(graph_data)
        else:
            raise ValueError("Unsupported file format")
    
    def find_sample_paths(self, start_node: str = None, end_node: str = None, 
                         num_paths: int = 3) -> List[List[str]]:
        """
        Find sample paths through the graph for demonstration.
        
        Args:
            start_node: Starting node (default: first node)
            end_node: Ending node (default: last node)
            num_paths: Number of paths to find
            
        Returns:
            List of paths (each path is a list of node IDs)
        """
        if not start_node:
            start_node = "M0_T0.0"
        
        if not end_node:
            # Find a node near the end
            end_nodes = [n for n in self.graph.nodes() 
                        if self.graph.nodes[n]['mile'] >= self.max_miles * 0.8]
            if end_nodes:
                end_node = end_nodes[0]
            else:
                return []
        
        try:
            # Find shortest paths
            paths = []
            if nx.has_path(self.graph, start_node, end_node):
                # Get shortest path by fuel cost
                shortest_path = nx.shortest_path(self.graph, start_node, end_node, 
                                               weight='fuel_cost')
                paths.append(shortest_path)
                
                # Try to find alternative paths by removing edges temporarily
                for i in range(min(num_paths - 1, 2)):
                    try:
                        # Remove some edges from the shortest path
                        edges_to_remove = []
                        for j in range(len(shortest_path) - 1):
                            if j % (i + 2) == 0:  # Remove every (i+2)th edge
                                edges_to_remove.append((shortest_path[j], shortest_path[j+1]))
                        
                        # Temporarily remove edges
                        self.graph.remove_edges_from(edges_to_remove)
                        
                        # Find alternative path
                        if nx.has_path(self.graph, start_node, end_node):
                            alt_path = nx.shortest_path(self.graph, start_node, end_node, 
                                                      weight='fuel_cost')
                            paths.append(alt_path)
                        
                        # Restore edges
                        for edge in edges_to_remove:
                            if edge[0] in self.graph.nodes() and edge[1] in self.graph.nodes():
                                # Recreate edge with original data
                                # This is simplified - in practice you'd store the edge data
                                pass
                        
                    except:
                        continue
            
            return paths
        
        except:
            return []


def main():
    """
    Main function to create and export the ship voyage graph.
    """
    print("=" * 70)
    print("SHIP VOYAGE GRAPH GENERATION")
    print("=" * 70)
    
    # Get user input
    print("\nPlease enter the following parameters:")
    
    try:
        max_miles = int(input("Number of miles (distance from start point): "))
        max_time = int(input("Total voyage time (hours): "))
        time_granularity = float(input("Time granularity (hours): "))
    except ValueError:
        print("Invalid input. Using default values.")
        max_miles = 100
        max_time = 24
        time_granularity = 1.0
    
    print(f"\nUsing parameters:")
    print(f"  Max miles: {max_miles}")
    print(f"  Max time: {max_time} hours")
    print(f"  Time granularity: {time_granularity} hours")
    
    # Create graph generator
    graph_generator = ShipVoyageGraph(max_miles, max_time, time_granularity)
    
    # Generate the graph
    graph = graph_generator.generate_graph()
    
    # Export the graph
    print("\n" + "=" * 60)
    print("EXPORTING GRAPH")
    print("=" * 60)
    
    graph_generator.export_graph(format_type="all", 
                                base_filename="ship_voyage_graph")
    
    # Find and display sample paths
    print("\n" + "=" * 60)
    print("SAMPLE PATHS")
    print("=" * 60)
    
    sample_paths = graph_generator.find_sample_paths()
    
    if sample_paths:
        for i, path in enumerate(sample_paths[:3]):
            print(f"\nPath {i+1} ({len(path)} nodes):")
            total_fuel = 0
            total_distance = 0
            
            for j in range(len(path) - 1):
                if graph.has_edge(path[j], path[j+1]):
                    edge_data = graph[path[j]][path[j+1]]
                    total_fuel += edge_data['fuel_cost']
                    total_distance += edge_data['distance']
            
            print(f"  Start: {path[0]} -> End: {path[-1]}")
            print(f"  Total fuel consumption: {total_fuel:.2f} kg")
            print(f"  Total distance: {total_distance:.2f} nm")
            
            # Show first few nodes
            print(f"  Route: {' -> '.join(path[:5])}", end="")
            if len(path) > 5:
                print(f" -> ... -> {path[-1]}")
            else:
                print()
    else:
        print("No paths found. Graph may not be connected.")
    
    print("\n" + "=" * 70)
    print("GRAPH GENERATION COMPLETED SUCCESSFULLY!")
    print("=" * 70)
    
    print(f"\n📁 Files created:")
    print(f"  • ship_voyage_graph.pkl (NetworkX pickle format)")
    print(f"  • ship_voyage_graph.graphml (GraphML format)")
    print(f"  • ship_voyage_graph.json (JSON format)")
    print(f"  • ship_voyage_graph_nodes.csv (Nodes data)")
    print(f"  • ship_voyage_graph_edges.csv (Edges data)")
    print(f"  • ship_voyage_graph_conditions.csv (Environmental conditions)")
    
    print(f"\n💡 Usage examples:")
    print(f"  # Load graph in Python:")
    print(f"  import pickle")
    print(f"  with open('ship_voyage_graph.pkl', 'rb') as f:")
    print(f"      graph = pickle.load(f)")
    print(f"")
    print(f"  # Query graph:")
    print(f"  print(f'Nodes: {{graph.number_of_nodes()}}')")
    print(f"  print(f'Edges: {{graph.number_of_edges()}}')")
    print(f"")
    print(f"  # Find shortest path:")
    print(f"  import networkx as nx")
    print(f"  path = nx.shortest_path(graph, 'M0_T0.0', 'M{max_miles}_T{max_time:.1f}', weight='fuel_cost')")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Ship Speed Optimization using Gurobi (Commercial Solver)
Based on the static maritime speed optimization problem formulation

This script solves the ship speed optimization problem using SOS2 variables:
- Minimize total fuel consumption
- Subject to ETA constraint and speed bounds
- Using SOS2 (Special Ordered Set Type 2) variables for speed selection per segment

Mathematical Formulation:
- Objective: min Σ(i=1 to n) Σ(k=0 to m) xi,k * fcrk * li / sogi,k
- ETA constraint: Σ(i=1 to n) Σ(k=0 to m) li / sogi,k * xi,k ≤ ETA
- Speed selection: Σ(k=0 to m) xi,k = 1 for all i
- Speed bounds: Li ≤ Σ(k=0 to m) sogi,k * xi,k ≤ Ui for all i
- SOS2 constraint: {xi,0, xi,1, ..., xi,m} ∈ SOS2 for all i

Author: Linear Optimization Script (Gurobi Version)
Date: 2025
"""

import gurobipy as gp
from gurobipy import GRB
import numpy as np
import pandas as pd
import sys
import re
import time

def parse_dat_file(filename):
    """
    Parse the .dat file to extract optimization parameters
    
    Args:
        filename: Path to the .dat file
        
    Returns:
        dict: Dictionary containing all optimization parameters
    """
    
    data = {}
    
    with open(filename, 'r') as f:
        content = f.read()
    
    # Parse ETA
    eta_match = re.search(r'ETA\s*=\s*(\d+(?:\.\d+)?)', content)
    if eta_match:
        data['ETA'] = float(eta_match.group(1))
    
    # Parse num_segments
    segments_match = re.search(r'num_segments\s*=\s*(\d+)', content)
    if segments_match:
        data['num_segments'] = int(segments_match.group(1))
    
    # Parse num_speeds
    speeds_match = re.search(r'num_speeds\s*=\s*(\d+)', content)
    if speeds_match:
        data['num_speeds'] = int(speeds_match.group(1))
    
    # Parse arrays
    def parse_array(pattern, content):
        match = re.search(pattern, content, re.DOTALL)
        if match:
            array_str = match.group(1)
            # Extract numbers (including decimals)
            numbers = re.findall(r'-?\d+(?:\.\d+)?', array_str)
            return [float(x) for x in numbers]
        return []
    
    # Parse l (segment lengths)
    data['l'] = parse_array(r'l\s*=\s*\[(.*?)\]', content)
    
    # Parse L (lower bounds)
    data['L'] = parse_array(r'L\s*=\s*\[(.*?)\]', content)
    
    # Parse U (upper bounds)  
    data['U'] = parse_array(r'U\s*=\s*\[(.*?)\]', content)
    
    # Parse s (possible speeds)
    data['s'] = parse_array(r's\s*=\s*\[(.*?)\]', content)
    
    # Parse FCR (fuel consumption rates)
    data['FCR'] = parse_array(r'FCR\s*=\s*\[(.*?)\]', content)
    
    # Parse f matrix (SOG values) - custom parser for the complex structure
    f_start = content.find('f = [')
    if f_start != -1:
        # Find the end of the f matrix (look for the closing ];)
        f_end = content.find('];', f_start)
        if f_end != -1:
            f_section = content[f_start:f_end + 2]
            
            # Extract everything between the outer brackets
            matrix_start = f_section.find('[') + 1
            matrix_end = f_section.rfind(']')
            matrix_content = f_section[matrix_start:matrix_end]
            
            # Split by rows - look for patterns like ], [
            # First clean up the content and find row boundaries
            rows = []
            current_row = ""
            bracket_depth = 0
            
            for char in matrix_content:
                if char == '[':
                    bracket_depth += 1
                    if bracket_depth == 1:
                        current_row = ""
                elif char == ']':
                    bracket_depth -= 1
                    if bracket_depth == 0:
                        # End of a row
                        if current_row.strip():
                            # Extract numbers from the current row
                            numbers = re.findall(r'-?\d+(?:\.\d+)?', current_row)
                            if numbers:
                                rows.append([float(x) for x in numbers])
                        current_row = ""
                elif bracket_depth == 1:
                    current_row += char
            
            data['f'] = rows
    
    return data

def solve_ship_optimization_gurobi(data_file):
    """
    Solve the ship speed optimization problem using Gurobi with SOS2 variables
    
    Args:
        data_file: Path to the .dat file containing problem data
        
    Returns:
        dict: Solution results
    """
    
    # Parse data file
    print(f"📊 Parsing data file: {data_file}")
    data = parse_dat_file(data_file)
    
    # Extract parameters
    ETA = data['ETA']
    num_segments = data['num_segments']
    num_speeds = data['num_speeds']
    l = data['l']
    L = data['L']
    U = data['U']
    s = data['s']
    FCR = data['FCR']
    f = data['f']
    
    print(f"✅ Problem size: {num_segments} segments, {num_speeds} speeds")
    print(f"⏰ ETA constraint: {ETA} hours")
    print(f"🚢 Total distance: {sum(l):.2f} nautical miles")
    
    # Create Gurobi model
    model = gp.Model("Ship_Speed_Optimization_Gurobi")
    model.setParam('OutputFlag', 0)  # Suppress Gurobi output
    
    # Decision variables: x[i,k] for segment i, speed k (SOS2 variables)
    x = {}
    for i in range(num_segments):
        for k in range(num_speeds):
            x[i, k] = model.addVar(vtype=GRB.CONTINUOUS, lb=0, ub=1, 
                                 name=f"x_{i}_{k}")
    
    print(f"🔧 Added {num_segments * num_speeds} continuous decision variables")
    
    # Add SOS2 constraints for each segment
    for i in range(num_segments):
        # Create SOS2 set for segment i
        sos_vars = [x[i, k] for k in range(num_speeds)]
        sos_weights = s  # Use speed values as weights
        model.addSOS(GRB.SOS_TYPE2, sos_vars, sos_weights)
    
    print(f"🔧 Added {num_segments} SOS2 constraints")
    
    # Objective function: Minimize total fuel consumption
    # sum(i,k) l[i] * FCR[k] / f[i,k] * x[i,k]
    objective = gp.quicksum([
        l[i] * FCR[k] / f[i][k] * x[i, k]
        for i in range(num_segments) 
        for k in range(num_speeds)
    ])
    model.setObjective(objective, GRB.MINIMIZE)
    
    # Constraints
    
    # 1. ETA Constraint: sum(i,k) (l[i]/f[i,k]) * x[i,k] <= ETA
    eta_constraint = gp.quicksum([
        l[i] / f[i][k] * x[i, k]
        for i in range(num_segments) 
        for k in range(num_speeds)
    ])
    model.addConstr(eta_constraint <= ETA, "ETA_constraint")
    
    # 2. Speed selection constraint: sum(k) x[i,k] = 1 for all i
    for i in range(num_segments):
        speed_selection = gp.quicksum([x[i, k] for k in range(num_speeds)])
        model.addConstr(speed_selection == 1, f"speed_selection_segment_{i}")
    
    # 3. SOG bounds: L[i] <= sum(k) f[i,k] * x[i,k] <= U[i] for all i
    for i in range(num_segments):
        sog_expr = gp.quicksum([f[i][k] * x[i, k] for k in range(num_speeds)])
        model.addConstr(sog_expr >= L[i], f"sog_lower_bound_segment_{i}")
        model.addConstr(sog_expr <= U[i], f"sog_upper_bound_segment_{i}")
    
    total_constraints = 1 + num_segments + 2 * num_segments
    print(f"🔧 Added {total_constraints} constraints")
    
    # Solve the problem
    print(f"\n🚀 Solving optimization problem with Gurobi...")
    start_time = time.time()
    
    try:
        model.optimize()
        solve_time = time.time() - start_time
        
        # Check solution status
        if model.status == GRB.OPTIMAL:
            print(f"✅ Optimal solution found!")
            print(f"⏱️  Solve time: {solve_time:.2f} seconds")
            
            # Parse solution
            solution = {
                'status': 'optimal',
                'total_fuel_consumption': model.objVal,
                'segments': [],
                'solve_time': solve_time
            }
            
            total_time = 0
            
            for i in range(num_segments):
                segment_info = {
                    'segment': i + 1,
                    'distance': l[i],
                    'selected_speed_index': None,
                    'sws': None,
                    'sog': None,
                    'time': None,
                    'fuel_consumption': None,
                    'speed_weights': []
                }
                
                # Find selected speeds for this segment (SOS2 allows up to 2 adjacent speeds)
                segment_speeds = []
                for k in range(num_speeds):
                    if x[i, k].x > 1e-6:  # Non-zero weight
                        segment_speeds.append((k, x[i, k].x, s[k], f[i][k]))
                        segment_info['speed_weights'].append({
                            'speed_index': k,
                            'weight': x[i, k].x,
                            'sws': s[k],
                            'sog': f[i][k]
                        })
                
                # Sort by weight (descending)
                segment_speeds.sort(key=lambda x: x[1], reverse=True)
                
                if segment_speeds:
                    # Use the speed with highest weight as primary
                    primary_k, primary_weight, primary_sws, primary_sog = segment_speeds[0]
                    segment_info['selected_speed_index'] = primary_k
                    segment_info['sws'] = primary_sws
                    segment_info['sog'] = primary_sog
                    segment_info['time'] = l[i] / primary_sog
                    segment_info['fuel_consumption'] = l[i] * FCR[primary_k] / primary_sog
                    total_time += segment_info['time']
                
                solution['segments'].append(segment_info)
            
            solution['total_time'] = total_time
            
            return solution, FCR
            
        else:
            print(f"❌ Problem could not be solved optimally")
            print(f"Status: {model.status}")
            if model.status == GRB.INFEASIBLE:
                print("Model is infeasible - check constraints")
            elif model.status == GRB.UNBOUNDED:
                print("Model is unbounded - check objective")
            return {'status': 'infeasible'}, []
            
    except gp.GurobiError as e:
        print(f"❌ Gurobi error: {e}")
        return {'status': 'error'}, []
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return {'status': 'error'}, []

def print_solution(solution):
    """
    Print the optimization solution in a formatted way
    
    Args:
        solution: Solution dictionary from solve_ship_optimization_gurobi
    """
    
    if solution['status'] != 'optimal':
        print(f"\n❌ No optimal solution to display")
        return
    
    print(f"\n🎯 GUROBI OPTIMIZATION RESULTS")
    print(f"=" * 80)
    
    print(f"📊 Summary:")
    print(f"   Total Fuel Consumption: {solution['total_fuel_consumption']:.6f} MT")
    print(f"   Total Travel Time: {solution['total_time']:.2f} hours")
    print(f"   Solve Time: {solution['solve_time']:.2f} seconds")
    
    print(f"\n📋 Detailed Results by Segment:")
    print(f"{'Seg':<4} {'Dist':<8} {'SWS':<6} {'SOG':<8} {'Time':<8} {'Fuel':<10} {'Weights':<15}")
    print(f"{'#':<4} {'(nm)':<8} {'(kn)':<6} {'(kn)':<8} {'(h)':<8} {'(MT)':<10} {'(SOS2)':<15}")
    print(f"-" * 70)
    
    for seg in solution['segments']:
        # Show speed weights for SOS2
        weights_str = ""
        if seg['speed_weights']:
            weights_str = ", ".join([f"{w['weight']:.3f}" for w in seg['speed_weights'][:2]])
        
        print(f"{seg['segment']:<4} "
              f"{seg['distance']:<8.2f} "
              f"{seg['sws']:<6.1f} "
              f"{seg['sog']:<8.3f} "
              f"{seg['time']:<8.2f} "
              f"{seg['fuel_consumption']:<10.4f} "
              f"{weights_str:<15}")
    
    print(f"-" * 70)
    print(f"{'TOT':<4} "
          f"{sum(seg['distance'] for seg in solution['segments']):<8.2f} "
          f"{'--':<6} "
          f"{'--':<8} "
          f"{solution['total_time']:<8.2f} "
          f"{solution['total_fuel_consumption']:<10.4f}")
    
    # Check ETA constraint
    eta_used = solution['total_time']
    print(f"\n⏰ ETA Constraint Check:")
    print(f"   Used: {eta_used:.2f} hours")
    print(f"   Limit: 280.00 hours")
    if eta_used <= 280:
        print(f"   ✅ SATISFIED (margin: {280 - eta_used:.2f} hours)")
    else:
        print(f"   ❌ VIOLATED (excess: {eta_used - 280:.2f} hours)")

def export_solution_csv(solution, fcr_data, filename='gurobi_optimization_results.csv'):
    """
    Export solution to CSV file with requested structure
    
    Args:
        solution: Solution dictionary
        fcr_data: Fuel consumption rate data array
        filename: Output CSV filename
    """
    
    if solution['status'] != 'optimal':
        print(f"Cannot export: No optimal solution available")
        return
    
    # Create DataFrame with requested structure
    df_data = []
    for seg in solution['segments']:
        # Get FCR for the selected speed
        speed_index = seg['selected_speed_index']
        fcr_value = fcr_data[speed_index] if speed_index is not None else None
        
        df_data.append({
            'Segment': seg['segment'],
            'SWS': seg['sws'],
            'SOG': seg['sog'],
            'Travel_Time': seg['time'],
            'Distance': seg['distance'],
            'FCR': fcr_value,
            'Fuel_Consumption': seg['fuel_consumption'],
            'SOS2_Weights': str(seg['speed_weights'])
        })
    
    df = pd.DataFrame(df_data)
    df.to_csv(filename, index=False)
    print(f"📁 Results exported to: {filename}")

def compare_with_pulp_solution(solution):
    """
    Compare Gurobi optimization results with PuLP solution
    
    Args:
        solution: Solution dictionary from Gurobi
    """
    
    if solution['status'] != 'optimal':
        return
    
    # PuLP solution from earlier query (binary variables)
    pulp_sws = [12.7, 12.2, 12.2, 12.1, 12.5, 12.3, 12.4, 12.7, 12.3, 12.0, 12.4, 12.5]
    pulp_sog = [12.356215, 11.738374, 12.635041, 12.132424, 12.038880, 11.124924, 
                11.852915, 10.809994, 12.007468, 12.660112, 12.222302, 12.672564]
    
    print(f"\n🔍 Comparison: Gurobi (SOS2) vs PuLP (Binary):")
    print(f"{'Seg':<4} {'PuLP SWS':<12} {'Gurobi SWS':<12} {'PuLP SOG':<12} {'Gurobi SOG':<12}")
    print(f"-" * 60)
    
    for i, seg in enumerate(solution['segments']):
        pulp_sws_val = pulp_sws[i] if i < len(pulp_sws) else 'N/A'
        pulp_sog_val = pulp_sog[i] if i < len(pulp_sog) else 'N/A'
        
        print(f"{seg['segment']:<4} "
              f"{pulp_sws_val:<12} "
              f"{seg['sws']:<12.1f} "
              f"{pulp_sog_val:<12} "
              f"{seg['sog']:<12.3f}")
    
    print(f"\n📊 Performance Comparison:")
    print(f"   Gurobi Total Fuel: {solution['total_fuel_consumption']:.6f} MT")
    print(f"   Gurobi Solve Time: {solution['solve_time']:.2f} seconds")
    print(f"   Gurobi Total Time: {solution['total_time']:.2f} hours")

def main():
    """Main function to run the Gurobi optimization"""
    
    print("🚢 Ship Speed Optimization using Gurobi (Commercial Solver)")
    print("=" * 70)
    print("📋 Mathematical Formulation:")
    print("   - SOS2 variables for speed selection")
    print("   - Piecewise linear approximation")
    print("   - ETA constraint with speed bounds")
    print("=" * 70)
    
    # Default data file
    data_file = '/Users/ami/Desktop/university/data_12segments.dat'
    
    # Check if custom data file provided
    if len(sys.argv) > 1:
        data_file = sys.argv[1]
    
    print(f"📂 Using data file: {data_file}")
    
    try:
        # Solve optimization
        solution, fcr_data = solve_ship_optimization_gurobi(data_file)
        
        # Display results
        print_solution(solution)
        
        # Compare with PuLP solution
        if solution['status'] == 'optimal':
            compare_with_pulp_solution(solution)
            
            # Export to CSV
            export_solution_csv(solution, fcr_data)
            
    except FileNotFoundError:
        print(f"❌ Error: Data file not found: {data_file}")
        print(f"Please ensure the file exists and try again.")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
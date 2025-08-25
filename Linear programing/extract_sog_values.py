#!/usr/bin/env python3
"""
Extract SOG values from data_12segments.dat for specific segment/SWS combinations
"""

import re

def parse_data_file(filename):
    """Parse the data file and extract s and f arrays"""
    with open(filename, 'r') as file:
        content = file.read()
    
    # Extract s array (SWS values)
    s_match = re.search(r's = \[(.*?)\];', content, re.DOTALL)
    if s_match:
        s_str = s_match.group(1)
        s = [float(x.strip()) for x in s_str.split(',')]
    else:
        raise ValueError("Could not find s array")
    
    # Extract f array (SOG values)
    f_match = re.search(r'f = \[\s*//.*?\n(.*?)\];', content, re.DOTALL)
    if f_match:
        f_str = f_match.group(1)
        # Split into rows (segments)
        rows = f_str.split('], [')
        f = []
        for i, row in enumerate(rows):
            # Clean up the row string
            row = row.strip().replace('[', '').replace(']', '')
            row_values = [float(x.strip()) for x in row.split(',')]
            f.append(row_values)
    else:
        raise ValueError("Could not find f array")
    
    return s, f

def get_sog_value(s_array, f_array, segment, sws):
    """Get SOG value for a given segment and SWS"""
    # Find index of SWS in s array
    try:
        sws_index = s_array.index(sws)
    except ValueError:
        raise ValueError(f"SWS value {sws} not found in data")
    
    # Get SOG from f array (segment is 1-indexed, convert to 0-indexed)
    segment_index = segment - 1
    if segment_index < 0 or segment_index >= len(f_array):
        raise ValueError(f"Segment {segment} out of range")
    
    sog = f_array[segment_index][sws_index]
    return sog

def main():
    # Requested segment/SWS combinations
    requests = [
        (1, 12.7),
        (2, 12.2),
        (3, 12.2),
        (4, 12.1),
        (5, 12.5),
        (6, 12.3),
        (7, 12.4),
        (8, 12.7),
        (9, 12.3),
        (10, 12.0),
        (11, 12.4),
        (12, 12.5)
    ]
    
    # Parse data file
    data_file = '/Users/ami/Desktop/university/data_12segments.dat'
    s, f = parse_data_file(data_file)
    
    print("Segment\tSWS\tSOG")
    print("-" * 25)
    
    results = []
    for segment, sws in requests:
        try:
            sog = get_sog_value(s, f, segment, sws)
            print(f"{segment}\t{sws}\t{sog:.6f}")
            results.append((segment, sws, sog))
        except ValueError as e:
            print(f"Error for segment {segment}, SWS {sws}: {e}")
    
    return results

if __name__ == "__main__":
    results = main() 
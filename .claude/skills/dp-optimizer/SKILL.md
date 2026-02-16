# DP Optimizer Architecture Reference

## Files

| File | Purpose |
|------|---------|
| `Dynamic speed optimization/speed_control_optimizer.py` | Main DP solver (graph + Dijkstra) |
| `Dynamic speed optimization/utility_functions.py` | Paper formulas (identical to LP version) |
| `Dynamic speed optimization/ship_parameters.yaml` | Ship specs + speed constraints |
| `Dynamic speed optimization/weather_forecasts.yaml` | Time-windowed weather per segment |

## Data Flow

```
ship_parameters.yaml + weather_forecasts.yaml
    |
    v
speed_control_optimizer.py
    |  - Creates 2D node grid (time x distance)
    |  - For each node, creates Sides (speed choices)
    |  - For each Side, computes Arcs (SOG, fuel cost)
    |  - Runs Dijkstra from (t=0, d=0)
    |  - Backtracks optimal path
    v
Output: Speed at each (time, distance) node, total fuel
```

## Graph Classes

```python
class Node:
    time: int               # hours from start
    distance: int           # NM from start
    cost: float = inf       # cumulative fuel (Dijkstra label)
    previous: Node = None   # backpointer

class Side:
    speed: float            # SWS choice (knots)
    start_node: Node
    connections: list[Arc]  # outgoing arcs

class Arc:
    side: Side              # the speed choice
    end_node: Node          # target node
    fuel: float             # fuel for this arc (kg)
    sog: float              # achieved SOG (knots)
```

## Graph Construction

```
Graph dimensions:
- Time:     0 to ETA_hours (step: time_granularity)
- Distance: 0 to total_nm  (step: distance_granularity)
- Speeds:   sws_min to sws_max (step: speed_granularity)

For each node(t, d):
  For each SWS in speed_range:
    weather = lookup(segment_of(d), time_window_of(t))
    SOG = calculate_speed_over_ground(SWS, weather)
    travel_time = distance_granularity / SOG
    fuel = FCR(SWS) * travel_time
    target = node(t + travel_time, d + distance_granularity)
    create Arc(fuel, SOG) from this Side to target Node
```

## Key Algorithm: `fit_graph()` (BFS + Dijkstra hybrid)

1. Start at node(0, 0) with cost=0
2. BFS frontier expansion (sorted by time)
3. For each node, try all speed choices (Sides)
4. Update target node cost if new path is cheaper
5. At destination distance, find minimum-cost node across all times
6. Backtrack via `previous` pointers

## Config Structure (`ship_parameters.yaml`)

```yaml
ship:
  length_m: 200
  beam_m: 32
  draft_m: 12
  displacement: 50000
  block_coefficient: 0.75
  installed_power_kw: 10000
speed_constraints:
  min_knots: 11
  max_knots: 13
granularity:
  speed_knots: 0.1
  time_hours: 1
  distance_nm: 1
```

## Known Bugs

1. **Forecast window bug**: Only uses `weather_forecasts[0]` for all arcs, ignoring time progression. Should use `weather_forecasts[time_window_of(arc.time)]`.

2. **Discrete SOG matching**: `find_solution_path()` expects SOG to exactly match a predefined speed level. Should allow continuous SOG values.

3. **Hardcoded file paths**: Loads YAML from relative paths like `"ship_parameters.yaml"`.

4. **Weather resolution mismatch**: Weather is per-segment (12 segments), but graph has per-NM distance nodes. No interpolation between segment boundaries.

## SWS-from-SOG Inverse (Binary Search)

The DP optimizer includes logic to find the SWS that produces a given SOG:

```python
# Binary search: given target_sog and weather, find SWS
sws_low, sws_high = speed_min, speed_max
while sws_high - sws_low > tolerance:
    sws_mid = (sws_low + sws_high) / 2
    sog_mid = calculate_speed_over_ground(sws_mid, weather)
    if sog_mid < target_sog:
        sws_low = sws_mid
    else:
        sws_high = sws_mid
```

This function is NOT in `utility_functions.py` — it's inline in the optimizer. The new pipeline puts it in `shared/physics.py`.

## Rolling Horizon Extension

The dynamic rolling horizon approach is NOT in the existing code. It will be built as a wrapper:

```
For each decision_point (every N hours):
    1. Get current position (time, distance)
    2. Extract forecast from HDF5 where sample_hour = current_hour
    3. Run dynamic_det.optimize() for remaining voyage
    4. Execute plan until next decision point
    5. Record actual fuel consumed
    6. Repeat from new position
```

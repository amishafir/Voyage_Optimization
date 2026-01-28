# Speed Control Optimizer Analysis

## Voyage Optimization Strategies - Evolution Flow

This section presents the progression from the research paper methodology through implementation strategies to future simulation capabilities.

---

### Strategy Comparison Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    VOYAGE OPTIMIZATION STRATEGIES                            │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐  │
│  │  RESEARCH   │    │   LINEAR    │    │  DYNAMIC    │    │   FUTURE    │  │
│  │   PAPER     │ ─► │ PROGRAMMING │ ─► │ PROGRAMMING │ ─► │ SIMULATION  │  │
│  │  (Theory)   │    │    (LP)     │    │    (DP)     │    │ (Validation)│  │
│  └─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘  │
│                                                                              │
│  • Mathematical    • Static weather   • Time-varying    • Real weather     │
│    formulation     • One speed/segment  weather         • Compare methods  │
│  • SOG equations   • ETA constraint   • Graph-based     • Ensemble data    │
│  • Resistance      • Binary variables • Optimal path    • Fuel savings     │
│    coefficients    • PuLP/Gurobi      • 6-hour windows  • Uncertainty      │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

### 1. Research Paper Approach (Theoretical Foundation)

**Source:** "Ship Speed Optimization Considering Ocean Currents to Enhance Environmental Sustainability in Maritime Shipping"

```
┌─────────────────────────────────────────────────────────────────┐
│                 RESEARCH PAPER METHODOLOGY                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  INPUT:                                                          │
│  ├── Ship parameters (length, beam, Cb, displacement)           │
│  ├── Weather data (wind direction φ, Beaufort BN, wave height)  │
│  ├── Current data (direction γ, speed Vc)                       │
│  └── Ship heading β per segment                                 │
│                                                                  │
│  CALCULATIONS:                                                   │
│  ├── Weather direction angle: θ = |φ - β|         (Eq. 9)       │
│  ├── Direction reduction coeff: Cβ (Table 2)                    │
│  ├── Speed reduction coeff: CU (Table 3)                        │
│  ├── Ship form coeff: Cform (Table 4)                           │
│  ├── Speed loss: ΔV = Cβ × CU × Cform            (Eq. 7)        │
│  ├── Weather-corrected speed: Vw = SWS - ΔV      (Eq. 8)        │
│  └── SOG via vector synthesis: Vg = f(Vw, Vc, γ) (Eq. 14-16)   │
│                                                                  │
│  OUTPUT:                                                         │
│  └── Speed Over Ground (SOG) given SWS and conditions           │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

**Key Equations:**
- FCR = 0.000706 × SWS³ (fuel consumption rate, kg/hour)
- Total Fuel = Σ(FCR × segment_time)
- Segment Time = Distance / SOG

---

### 2. Linear Programming Strategy (Static Optimization)

**Implementation:** `/Linear programing/ship_speed_optimization_pulp.py`

```
┌─────────────────────────────────────────────────────────────────┐
│              LINEAR PROGRAMMING (LP) APPROACH                    │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ASSUMPTIONS:                                                    │
│  ├── Weather is CONSTANT per segment (static)                   │
│  ├── One speed decision per segment                             │
│  ├── Pre-computed SOG lookup table: f[segment][speed]           │
│  └── Fixed ETA constraint                                       │
│                                                                  │
│  DECISION VARIABLES:                                             │
│  └── x[i][j] ∈ {0,1} : select speed j for segment i             │
│                                                                  │
│  OBJECTIVE:                                                      │
│  └── Minimize: Σᵢ Σⱼ (FCR[j] × distance[i] / SOG[i][j]) × x[i][j]│
│                                                                  │
│  CONSTRAINTS:                                                    │
│  ├── Σⱼ x[i][j] = 1  ∀i         (one speed per segment)         │
│  ├── Σᵢ Σⱼ (d[i]/SOG[i][j]) × x[i][j] ≤ ETA  (arrival time)    │
│  └── L[i] ≤ speed[i] ≤ U[i]      (speed bounds)                 │
│                                                                  │
│  SOLVER: PuLP (open-source) or Gurobi (commercial)              │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

**Data Structure (voyage_data.py):**
```python
SEGMENT_DATA = [
    # [segment_id, wind_dir, beaufort, wave_height, current_dir, current_speed]
    [1, 139, 3, 1.0, 245, 0.30],
    [2, 207, 3, 1.0, 248, 0.72],
    # ... 12 segments total
]
SEGMENT_DISTANCES = [223.86, 282.54, 303.18, ...]  # nautical miles
SEGMENT_HEADINGS = [61.25, 121.53, 117.61, ...]    # degrees
```

**Limitations:**
- Cannot adapt to changing weather during segment traversal
- Single forecast snapshot for entire voyage
- No rolling horizon capability

---

### 3. Dynamic Programming Strategy (Time-Varying Optimization)

**Implementation:** `/Dynamic speed optimization/speed_control_optimizer.py`

```
┌─────────────────────────────────────────────────────────────────┐
│           DYNAMIC PROGRAMMING (DP) APPROACH                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ASSUMPTIONS:                                                    │
│  ├── Weather VARIES over time (6-hour windows)                  │
│  ├── Speed can change at any time/distance point                │
│  ├── Graph-based state space (time × distance)                  │
│  └── Optimal substructure property                              │
│                                                                  │
│  STATE SPACE:                                                    │
│  ├── Nodes: (time, distance) pairs                              │
│  ├── Arcs: speed choices connecting nodes                       │
│  └── Arc cost: fuel consumption for that transition             │
│                                                                  │
│  ALGORITHM:                                                      │
│  ├── Build 2D graph (time rows × distance columns)              │
│  ├── For each node, compute arcs to reachable nodes             │
│  ├── Arc fuel = FCR(SWS) × travel_time                          │
│  ├── Propagate minimum fuel cost (Dijkstra-like)                │
│  └── Backtrack from destination for optimal path                │
│                                                                  │
│  TIME WINDOWS:                                                   │
│  ├── 6-hour blocks with distinct weather conditions             │
│  ├── Weather changes at window boundaries                       │
│  └── Speed policy adapts to new conditions                      │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

**Graph Structure:**
```
Distance →
     0      100     200     300    ...    3400 nm
   ┌────────────────────────────────────────────┐
 0 │ ●───────●───────●───────●─────────────────●│
   │ │╲      │╲      │╲      │                  │
 6 │ ●───────●───────●───────●─────────────────●│
   │ │╲      │╲      │╲      │      Time       │
12 │ ●───────●───────●───────●───── Window ────●│
   │ │╲      │╲      │╲      │                  │
18 │ ●───────●───────●───────●─────────────────●│
 ↓ └────────────────────────────────────────────┘
Time (hours)

● = Node (state)
─ = Arc (speed choice)
╲ = Alternative arc (different speed)
```

**Advantages over LP:**
- Adapts to weather changes during voyage
- Can re-optimize at each time window
- Captures temporal dynamics of weather systems

---

### 4. Future Simulation Framework (Validation & Comparison)

**Purpose:** Validate optimization strategies using real weather data from Open-Meteo API

```
┌─────────────────────────────────────────────────────────────────┐
│              SIMULATION FRAMEWORK (PLANNED)                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  DATA SOURCES:                                                   │
│  ├── multi_location_wave_forecast.xlsx (13 waypoints)           │
│  ├── multi_location_wind_forecast.xlsx (13 waypoints)           │
│  ├── 12 API calls × 168 hours = 2,016 rows per waypoint         │
│  └── Ensemble of forecasts for uncertainty quantification       │
│                                                                  │
│  SIMULATION MODES:                                               │
│  ├── Mode A: Dynamic DP with time-varying weather               │
│  ├── Mode B: Static LP with average weather                     │
│  ├── Mode C: Constant speed baseline (12 knots)                 │
│  └── Mode D: Segment-static (one speed per segment)             │
│                                                                  │
│  PROCESS:                                                        │
│  ├── 1. Convert API data → weather_forecasts.yaml format        │
│  ├── 2. Run each optimization mode                              │
│  ├── 3. Simulate voyage with ACTUAL weather                     │
│  ├── 4. Calculate fuel consumption for each mode                │
│  └── 5. Compare results and quantify savings                    │
│                                                                  │
│  METRICS:                                                        │
│  ├── Total fuel consumption (kg)                                │
│  ├── Voyage time (hours)                                        │
│  ├── Fuel efficiency (kg/nm)                                    │
│  ├── CO2 emissions (kg)                                         │
│  └── Fuel savings vs baseline (%)                               │
│                                                                  │
│  ENSEMBLE ANALYSIS:                                              │
│  ├── Multiple forecasts → uncertainty bounds                    │
│  ├── Confidence-weighted speed decisions                        │
│  └── Risk-adjusted routing options                              │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

### End-to-End Data Flow

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                         COMPLETE DATA PIPELINE                                │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                               │
│  ┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐ │
│  │  Open-Meteo │     │   Excel     │     │    YAML     │     │  Optimizer  │ │
│  │     API     │ ──► │   Output    │ ──► │   Config    │ ──► │   Input     │ │
│  └─────────────┘     └─────────────┘     └─────────────┘     └─────────────┘ │
│                                                                               │
│  • Wind speed        • wp_01-wp_13      • 6-hour windows   • Graph nodes     │
│  • Wind direction    • 168 hours each   • 12 segments      • Arc costs       │
│  • Wave height       • sample_time      • Converted units  • Fuel calc       │
│  • Current velocity  • Accumulated      • Ship heading     • Path finding    │
│  • Current direction   forecasts        • Beaufort number                    │
│                                                                               │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                               │
│  ┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐ │
│  │  Optimizer  │     │  Simulate   │     │   Compare   │     │   Report    │ │
│  │   Output    │ ──► │   Voyage    │ ──► │   Methods   │ ──► │   Results   │ │
│  └─────────────┘     └─────────────┘     └─────────────┘     └─────────────┘ │
│                                                                               │
│  • Speed schedule    • Track position   • DP vs LP         • Fuel savings % │
│  • Per time window   • Apply weather    • DP vs Constant   • Time impact    │
│  • Optimal path      • Accumulate fuel  • DP vs Static     • Visualizations │
│                                                                               │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

### Strategy Comparison Matrix

| Feature | Research Paper | LP Strategy | DP Strategy | Simulation |
|---------|---------------|-------------|-------------|------------|
| Weather | Equations only | Static/segment | Time-varying | Real API data |
| Decisions | Manual calc | 1 per segment | Per time+distance | Validate all |
| Time dimension | None | Implicit (ETA) | Explicit (windows) | Actual timeline |
| Adaptability | None | None | High | Retrospective |
| Complexity | O(1) | O(n×m) | O(t×d×s) | O(methods×runs) |
| Implementation | utility_functions.py | ship_speed_optimization_pulp.py | speed_control_optimizer.py | Future work |
| Data source | Table 8 (paper) | voyage_data.py | weather_forecasts.yaml | Open-Meteo API |

**Legend:**
- n = segments, m = speed options
- t = time steps, d = distance steps, s = speeds
- methods = optimization approaches to compare
- runs = simulation iterations

---

## Overview

`/Dynamic speed optimization/speed_control_optimizer.py` is a **dynamic programming graph-based optimizer** for ship voyage speed control. It finds the optimal speed policy to minimize fuel consumption while considering time-varying weather conditions.

---

## Core Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        INPUTS                                   │
├─────────────────────────────────────────────────────────────────┤
│  ship_parameters.yaml     │  weather_forecasts.yaml             │
│  - Ship specs (200m, 32m) │  - Forecast windows (time periods)  │
│  - Speed range (11-13 kt) │  - Per-segment weather data:        │
│  - Granularity settings   │    wind_dir, beaufort, wave_height  │
│                           │    current_dir, current_speed       │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    2D GRAPH (Time × Distance)                   │
├─────────────────────────────────────────────────────────────────┤
│  • Rows = Time steps (1-hour granularity)                       │
│  • Columns = Distance steps (1-mile granularity)                │
│  • Each cell = Node with:                                       │
│    - node_index: (time, distance)                               │
│    - minimal_fuel_consumption                                   │
│    - minimal_input_arc (best incoming edge)                     │
│    - arcs[] (incoming edges)                                    │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    ARCS (Edges between nodes)                   │
├─────────────────────────────────────────────────────────────────┤
│  Each arc represents a speed choice:                            │
│  • SOG = distance_diff / time_diff                              │
│  • SWS = calculated via binary search (inverse SOG function)    │
│  • FCR = 0.000706 × SWS³ (fuel consumption rate)               │
│  • fuel_consumption = FCR × time                                │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    OUTPUT: Optimal Path                         │
├─────────────────────────────────────────────────────────────────┤
│  Backtrack from destination to find minimum fuel path           │
│  Returns sequence of (time, distance) nodes with speeds         │
└─────────────────────────────────────────────────────────────────┘
```

---

## Key Classes

| Class | Purpose |
|-------|---------|
| `Node` | Graph vertex at (time, distance) with fuel tracking |
| `Arc` | Edge connecting nodes with SWS, SOG, FCR, fuel data |
| `Side` | Boundary segment (vertical=same time, horizontal=same distance) |
| `optimizer` | Main class that builds graph and finds optimal path |

---

## Weather Data Format Required

The `weather_forecasts.yaml` expects this structure:

```yaml
- forecast_window:
    start: 0    # hours
    end: 24     # hours
  segments_table:
    - id: 1
      distance: 224      # nautical miles
      ship_heading: 61.25
      wind_dir: 139      # degrees
      beaufort: 3        # Beaufort number (calculated from wind speed)
      wave_height: 1.0   # meters
      current_dir: 245   # degrees
      current_speed: 0.30 # knots
```

---

## Integration Points with Server Data

The multi-location forecasting scripts collect weather data from Open-Meteo API. Here's how server output maps to optimizer input:

| Server Output | Optimizer Input | Conversion Needed |
|---------------|-----------------|-------------------|
| `wind_speed_10m (km/h)` | `beaufort` | Use `wind_speed_to_beaufort()` function |
| `wind_direction_10m (°)` | `wind_dir` | Direct (degrees) |
| `wave_height (m)` | `wave_height` | Direct (meters) |
| `ocean_current_velocity (km/h)` | `current_speed` | Convert to knots (÷ 1.852) |
| `ocean_current_direction (°)` | `current_dir` | Direct (degrees) |

---

## What's Missing for Integration

1. **Ship heading per segment** - Not from weather API, needs route calculation between waypoints
2. **Segment distances** - Need to calculate from waypoint coordinates using Haversine formula
3. **Time window mapping** - Map forecast hours to voyage timeline

---

## Key Functions

| Function | Purpose |
|----------|---------|
| `calculate_sws_from_sog()` | Inverse SOG: given target SOG + weather → required SWS |
| `connect()` | Creates arc between nodes, validates speed is feasible |
| `fit_graph()` | Builds graph by connecting sides (Dijkstra-like expansion) |
| `find_solution_path()` | Backtracks from destination to find optimal route |

---

## Fuel Consumption Formula

```python
FCR = 0.000706 × SWS³  # kg/hour
```

This cubic relationship means small speed reductions yield significant fuel savings.

---

## Ship Parameters (from ship_parameters.yaml)

```yaml
ship_parameters:
  length: 200.0          # meters
  beam: 32.0             # meters
  draft: 12.0            # meters
  displacement: 50000.0  # tonnes
  block_coefficient: 0.75
  wetted_surface: 8000.0 # m²
  rated_power: 10000.0   # kW

speed_constraints:
  max_speed: 13          # knots
  min_speed: 11          # knots
  speed_granularity: 0.1 # knots
  time_granularity: 1    # hours
  distance_granularity: 1 # miles
```

---

## Voyage Waypoints (13 points defining 12 segments)

| WP | Latitude | Longitude | Location |
|----|----------|-----------|----------|
| 1 | 24.75 | 52.83 | Port A (Persian Gulf) |
| 2 | 26.55 | 56.45 | Gulf of Oman |
| 3 | 24.08 | 60.88 | Arabian Sea |
| 4 | 21.73 | 65.73 | Arabian Sea |
| 5 | 17.96 | 69.19 | Arabian Sea |
| 6 | 14.18 | 72.07 | Arabian Sea |
| 7 | 10.45 | 75.16 | Indian Ocean |
| 8 | 7.00 | 78.46 | Indian Ocean |
| 9 | 5.64 | 82.12 | Bay of Bengal |
| 10 | 4.54 | 87.04 | Indian Ocean |
| 11 | 5.20 | 92.27 | Andaman Sea |
| 12 | 5.64 | 97.16 | Andaman Sea |
| 13 | 1.81 | 100.10 | Port B (Strait of Malacca) |

---

## SOG Calculation (from utility_functions.py)

The `calculate_speed_over_ground()` function implements the research paper methodology:

1. **Weather direction angle** (Equation 9): θ = |φ - α|
2. **Froude number**: Fn = V / √(g × L)
3. **Direction reduction coefficient** (Table 2): Cβ based on θ and Beaufort
4. **Speed reduction coefficient** (Table 3): CU based on Fn and block coefficient
5. **Ship form coefficient** (Table 4): Cform based on displacement
6. **Speed loss percentage** (Equation 7): Combined weather effects
7. **Weather-corrected speed** (Equation 8): SWS adjusted for weather
8. **Vector synthesis** (Equations 14-16): Final SOG combining ship speed and current

---

## Beaufort Scale Conversion

```python
def wind_speed_to_beaufort(wind_speed_kmh):
    wind_speed_ms = wind_speed_kmh / 3.6

    if wind_speed_ms < 0.5:   return 0   # Calm
    elif wind_speed_ms < 1.6: return 1   # Light air
    elif wind_speed_ms < 3.4: return 2   # Light breeze
    elif wind_speed_ms < 5.5: return 3   # Gentle breeze
    elif wind_speed_ms < 8.0: return 4   # Moderate breeze
    elif wind_speed_ms < 10.8: return 5  # Fresh breeze
    elif wind_speed_ms < 13.9: return 6  # Strong breeze
    elif wind_speed_ms < 17.2: return 7  # High wind
    elif wind_speed_ms < 20.8: return 8  # Gale
    elif wind_speed_ms < 24.5: return 9  # Strong gale
    elif wind_speed_ms < 28.5: return 10 # Storm
    elif wind_speed_ms < 32.7: return 11 # Violent storm
    else: return 12                       # Hurricane
```

---

## Time Window Integration (6-Hour Windows)

### Design Decision

**Chosen window size: 6 hours**

| Window Size | Pros | Cons |
|-------------|------|------|
| 1 hour | Maximum precision | Overkill, huge graph |
| 3 hours | Good balance | Many windows for 12-day voyage |
| **6 hours** | Weather patterns change meaningfully | Good match for forecast reliability |
| 12 hours | Day/night cycles | May miss storm fronts |
| 24 hours | Simple | Too coarse |

**Reasons for 6 hours:**
1. Wind/wave conditions typically shift every 6-12 hours
2. Open-Meteo hourly data is most reliable in 6-hour blocks
3. 12-day voyage = ~48 windows (manageable) vs 280 windows (1-hour)
4. Maritime forecasts are often issued in 6-hour intervals

---

### Resulting Structure

```
Voyage: ~280 hours (12 days)
├── 47 time windows (0-6, 6-12, 12-18, ... 276-282)
├── Each window contains 12 segments
└── Each segment has weather data averaged from that 6-hour block
```

**From Server Data:**

```
API forecast: 168 hours (7 days)
├── 168 / 6 = 28 time windows available per API call
├── For full voyage, need 2 API calls or rolling updates
└── Each waypoint's hourly data → averaged into 6-hour blocks
```

---

### Data Transformation Pipeline

**Step 1: Extract hourly data from server output (wp_XX sheets)**

```
Hour 0:  wind=15 km/h, wave=1.2m, current=0.8 km/h
Hour 1:  wind=16 km/h, wave=1.1m, current=0.7 km/h
Hour 2:  wind=14 km/h, wave=1.3m, current=0.9 km/h
Hour 3:  wind=15 km/h, wave=1.2m, current=0.8 km/h
Hour 4:  wind=17 km/h, wave=1.4m, current=0.6 km/h
Hour 5:  wind=16 km/h, wave=1.3m, current=0.7 km/h
```

**Step 2: Average into 6-hour window**

```
Window 0-6 averages:
├── wind_speed: 15.5 km/h
├── wave_height: 1.25 m
└── current_velocity: 0.75 km/h
```

**Step 3: Convert units to optimizer format**

```yaml
- forecast_window:
    start: 0
    end: 6
  segments_table:
    - id: 1
      distance: 224        # calculated from waypoints
      ship_heading: 61.25  # calculated from waypoints
      wind_dir: 139        # from API (degrees)
      beaufort: 3          # converted from wind_speed (15.5 km/h → BN 3)
      wave_height: 1.25    # from API (meters)
      current_dir: 245     # from API (degrees)
      current_speed: 0.40  # converted to knots (0.75 km/h ÷ 1.852)
```

---

### Segment Weather Assignment

For each segment (WP[i] → WP[i+1]), weather data options:

| Approach | Description | Recommended Use |
|----------|-------------|-----------------|
| **Start point** | Use WP[i] weather | Simple, good for short segments |
| **End point** | Use WP[i+1] weather | When approaching conditions matter |
| **Average** | Average WP[i] and WP[i+1] | **Recommended** - smooths transitions |
| **Weighted** | Interpolate by position | Most accurate for long segments |

**Recommended approach: Average the two waypoints' weather data for each segment.**

---

### Full Conversion Formula

```python
# For each 6-hour window and each segment:
segment_weather = {
    'wind_dir': avg(wp_start.wind_dir, wp_end.wind_dir),  # circular average
    'beaufort': wind_speed_to_beaufort(avg(wp_start.wind_speed, wp_end.wind_speed)),
    'wave_height': avg(wp_start.wave_height, wp_end.wave_height),
    'current_dir': avg(wp_start.current_dir, wp_end.current_dir),  # circular average
    'current_speed': avg(wp_start.current_speed, wp_end.current_speed) / 1.852,  # km/h to knots
}
```

**Note:** Direction averaging requires circular mean calculation to handle wrap-around (e.g., 350° and 10° should average to 0°, not 180°).

---

## Multi-Forecast Analysis (Ensemble Techniques)

### What Multiple Forecasts Provide

With frequent sampling (e.g., 12 runs over 3 hours), each target hour has multiple forecasts made at different lead times:

```
Run 1 (T=0:00):   Forecast for hours 0, 1, 2, ... 167
Run 2 (T=0:15):   Forecast for hours 0, 1, 2, ... 167
Run 3 (T=0:30):   Forecast for hours 0, 1, 2, ... 167
...
Run 12 (T=2:45):  Forecast for hours 0, 1, 2, ... 167
```

For **Hour 24** at **WP1**, you have 12 different forecasts:
- 24.00 hours ahead (Run 1)
- 23.75 hours ahead (Run 2)
- 23.50 hours ahead (Run 3)
- ...
- 21.25 hours ahead (Run 12)

---

### Use Case 1: Forecast Accuracy by Lead Time

```python
# Compare forecasts to actuals
Compare: Forecast(T=0, hour=2) vs Actual(T=2)
         Forecast(T=0, hour=3) vs Actual(T=3)

# Result: Quantify degradation
"Wave height forecasts degrade 5% per 24 hours of lead time"
```

---

### Use Case 2: Ensemble Averaging (Reduce Variance)

```python
# Multiple forecasts for same target hour → average them
hour_24_forecasts = [run1.hour24, run2.hour24, ..., run12.hour24]
improved_forecast = mean(hour_24_forecasts)  # More stable than single forecast
```

---

### Use Case 3: Bias Correction

```python
# If forecasts consistently over-predict waves:
bias = mean(forecast - actual)  # e.g., +0.15m
corrected_forecast = new_forecast - bias
```

---

### Use Case 4: Confidence Intervals for Optimizer

```python
# Spread between forecasts = uncertainty
wave_forecasts = [1.2, 1.3, 1.1, 1.4, 1.2]  # 5 forecasts for same hour
mean_wave = 1.24
std_wave = 0.11

# Feed uncertainty to optimizer:
# - Optimistic scenario: mean - std = 1.13m
# - Pessimistic scenario: mean + std = 1.35m
```

---

### Use Case 5: Weighted Average (Recent = More Accurate)

```python
# Weight more recent forecasts higher
weights = [0.5, 0.7, 0.8, 0.9, 1.0]  # newer = higher weight
weighted_forecast = sum(w * f for w, f in zip(weights, forecasts)) / sum(weights)
```

---

### Data Structure for Analysis

```
| target_hour      | sample_time | lead_time_hrs | wave_forecast | wave_actual |
|------------------|-------------|---------------|---------------|-------------|
| 2026-01-28 03:00 | 00:00       | 3.0           | 1.25          | 1.30        |
| 2026-01-28 03:00 | 00:15       | 2.75          | 1.28          | 1.30        |
| 2026-01-28 03:00 | 00:30       | 2.5           | 1.29          | 1.30        |
| 2026-01-28 03:00 | 00:45       | 2.25          | 1.30          | 1.30        |
```

---

### Enhanced Optimizer Input (with Uncertainty)

```yaml
- forecast_window:
    start: 0
    end: 6
  segments_table:
    - id: 1
      distance: 224
      ship_heading: 61.25
      wind_dir: 139
      beaufort: 3
      wave_height: 1.25          # ensemble mean
      wave_height_std: 0.11      # uncertainty from forecast spread
      current_speed: 0.40
      current_dir: 245
      confidence: 0.85           # based on lead time and spread
```

**Optimizer can then:**
- Use mean for expected fuel calculation
- Use std for risk-adjusted routing
- Avoid high-uncertainty segments when possible
- Plan buffer fuel for uncertain conditions

---

## Voyage Simulation & Comparison Framework

### Simulation Scenarios

#### Scenario A: Dynamic Optimization (Your Optimizer)

```
Input: Time-varying weather forecasts (6-hour windows)
Method: Graph-based DP finds optimal speed per time/distance
Output: Variable speed schedule that adapts to conditions
```

#### Scenario B: Static/Baseline Voyage (Comparison)

| Baseline | Description | Use Case |
|----------|-------------|----------|
| **Constant Speed** | Fixed speed entire voyage (e.g., 12 knots) | Simplest comparison |
| **Average Weather** | Optimize once using voyage-average conditions | "Plan once" approach |
| **Segment-Static** | One speed per segment, ignore time variation | Current industry practice |
| **Calm Water** | Assume no weather effects (SWS = SOG) | Theoretical minimum |

---

### Simulation Process

```
┌─────────────────────────────────────────────────────────────────┐
│                    SAME WEATHER DATA                            │
│         (from server: 6-hour windows, 12 segments)              │
└─────────────────────────────────────────────────────────────────┘
                    │                           │
                    ▼                           ▼
    ┌───────────────────────────┐   ┌───────────────────────────┐
    │   DYNAMIC OPTIMIZER       │   │   STATIC BASELINE         │
    │   - Variable speed        │   │   - Constant 12 knots     │
    │   - Per 6-hour window     │   │   - Entire voyage         │
    └───────────────────────────┘   └───────────────────────────┘
                    │                           │
                    ▼                           ▼
    ┌───────────────────────────┐   ┌───────────────────────────┐
    │   Simulate voyage:        │   │   Simulate voyage:        │
    │   - Track position/time   │   │   - Track position/time   │
    │   - Apply actual weather  │   │   - Apply actual weather  │
    │   - Calculate fuel used   │   │   - Calculate fuel used   │
    └───────────────────────────┘   └───────────────────────────┘
                    │                           │
                    └───────────┬───────────────┘
                                ▼
                    ┌───────────────────────────┐
                    │   COMPARE RESULTS         │
                    │   - Fuel savings (%)      │
                    │   - Time difference       │
                    │   - Efficiency metrics    │
                    └───────────────────────────┘
```

---

### Comparison Metrics

| Metric | Formula | Unit |
|--------|---------|------|
| Total Fuel | Σ(FCR × time) | kg |
| Voyage Time | Σ(distance / SOG) | hours |
| Fuel Efficiency | Total Fuel / Total Distance | kg/nm |
| CO2 Emissions | Total Fuel × 3.17 | kg CO2 |
| Fuel Savings | (Baseline - Dynamic) / Baseline × 100 | % |
| Time Penalty | (Dynamic - Baseline) / Baseline × 100 | % |

---

### Simulation Algorithm

```python
def simulate_voyage(speed_schedule, weather_data):
    """
    Simulate voyage with given speed schedule and actual weather.

    Args:
        speed_schedule: List of (segment, time_window, SWS) tuples
        weather_data: Actual weather per segment per time window

    Returns:
        total_fuel, total_time, trajectory
    """
    position = 0  # nm from start
    elapsed_time = 0  # hours
    total_fuel = 0  # kg
    trajectory = []

    while position < total_distance:
        # Get current segment and time window
        segment = get_segment(position)
        time_window = get_time_window(elapsed_time)

        # Get speed for this segment/time (from schedule)
        sws = speed_schedule.get_speed(segment, time_window)

        # Get actual weather
        weather = weather_data.get(segment, time_window)

        # Calculate actual SOG with weather effects
        sog = calculate_speed_over_ground(sws, weather)

        # Calculate fuel consumption
        fcr = 0.000706 * sws**3  # kg/hour

        # Advance simulation (1-hour step)
        distance_covered = sog * 1  # 1 hour
        fuel_used = fcr * 1  # 1 hour

        position += distance_covered
        elapsed_time += 1
        total_fuel += fuel_used

        trajectory.append({
            'time': elapsed_time,
            'position': position,
            'sws': sws,
            'sog': sog,
            'fuel': fuel_used
        })

    return total_fuel, elapsed_time, trajectory
```

---

### Baseline Speed Schedule Implementations

#### 1. Constant Speed Baseline

```python
def constant_speed_schedule(target_speed=12.0):
    """Always return the same speed."""
    return lambda segment, time_window: target_speed
```

#### 2. Average Weather Baseline

```python
def average_weather_schedule(weather_data, ship_params):
    """Optimize once using average weather conditions."""
    avg_weather = average_all_windows(weather_data)
    optimal_speed = optimize_for_weather(avg_weather, ship_params)
    return lambda segment, time_window: optimal_speed
```

#### 3. Segment-Static Baseline

```python
def segment_static_schedule(weather_data, ship_params):
    """One optimal speed per segment, averaged over time."""
    segment_speeds = {}
    for segment in segments:
        avg_weather = average_time_windows(weather_data, segment)
        segment_speeds[segment] = optimize_for_weather(avg_weather)
    return lambda segment, time_window: segment_speeds[segment]
```

---

### Expected Results (Based on Research Literature)

| Comparison | Expected Fuel Savings | Time Impact |
|------------|----------------------|-------------|
| Dynamic vs Constant Speed | 5-15% | +2-5% longer |
| Dynamic vs Average Weather | 3-8% | Similar |
| Dynamic vs Segment-Static | 2-5% | Similar |

**Key insight:** Dynamic optimization saves fuel by:
- Slowing down in headwinds/rough seas (fuel cost is cubic with speed)
- Speeding up in favorable conditions (tailwinds, following currents)
- Matching speed to time windows where conditions change significantly

---

### Visualization Outputs

Recommended plots for comparison:

1. **Speed Profile**: SWS vs time for both approaches
2. **Position-Time**: Trajectory comparison
3. **Cumulative Fuel**: Fuel consumption over voyage
4. **Weather Overlay**: Speed decisions vs weather conditions
5. **Efficiency Map**: Fuel per nm across segments

```
Example Speed Profile Plot:

Speed │    ╭──╮        Dynamic
(kts) │ ──╯    ╰──────
  13  │
  12  │ ─────────────── Constant
  11  │
      └─────────────────
        Time (hours)
```

---

## File Dependencies

```
speed_control_optimizer.py
├── imports: CreteNodes.py (CreateNodes class)
├── imports: utility_functions.py (calculate_speed_over_ground)
├── reads: ship_parameters.yaml
└── reads: weather_forecasts.yaml
```

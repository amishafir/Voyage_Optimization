# 4. Methodology

This section presents the three optimization approaches — static deterministic LP, dynamic deterministic DP, and dynamic rolling horizon — followed by the two-phase evaluation framework used to assess their real-world performance, and the theoretical bounds that frame the results.

## 4.1 Static Deterministic Optimization (LP)

The LP formulation selects one SWS from a discrete set $\{v_1, v_2, \ldots, v_K\}$ for each of $S$ voyage segments. Nodes are aggregated into segments by averaging weather conditions (scalar fields by arithmetic mean, direction fields by circular mean). The SOG for segment $i$ at speed $v_k$ is precomputed using the speed correction model (Eqs. 1–8) applied to segment-averaged weather, yielding a matrix $SOG_{ik}$.

The objective minimizes total fuel:

$$\min \sum_{i=1}^{S} \sum_{k=1}^{K} \frac{d_i \cdot FCR(v_k)}{SOG_{ik}} \cdot x_{ik} \tag{14}$$

subject to:

$$\sum_{k=1}^{K} x_{ik} = 1 \quad \forall\, i \in \{1, \ldots, S\} \tag{15}$$

$$\sum_{i=1}^{S} \sum_{k=1}^{K} \frac{d_i}{SOG_{ik}} \cdot x_{ik} \leq T \tag{16}$$

where $x_{ik} \in \{0, 1\}$ are binary decision variables (one speed per segment), $d_i$ is the segment distance, and $T$ is the ETA. The speed set comprises $K = 21$ equally spaced values from 11.0 to 13.0 kn (0.1 kn increments). SOG bounds per segment are enforced as additional constraints.

**SOG bounds.** For each segment $i$, lower and upper SOG bounds are computed by evaluating the speed correction model at the minimum and maximum SWS (11.0 and 13.0 kn) under segment-averaged weather. These bounds ensure the LP does not select a speed that would be infeasible at the segment level — for example, a tailwind segment where even the minimum SWS achieves an SOG above the global minimum. The SOG bounds are enforced as:

$$SOG_{lower,i} \leq \sum_{k=1}^{K} SOG_{ik} \cdot x_{ik} \leq SOG_{upper,i} \quad \forall\, i \tag{EQ: sog_bounds}$$

The formulation was solved using Gurobi (for Route 1) and PuLP/CBC (as a fallback). Solution times were under 0.01 seconds for all instances.

**Segment averaging.** In Route 1, the 138 interpolated nodes are aggregated into $S = 6$ segments (~23 nodes each); in Route 2, 389 nodes are aggregated into $S = 10$ segments (~39 nodes each). Scalar weather fields (wind speed, Beaufort number, wave height, current velocity) are averaged by arithmetic mean; direction fields (wind direction, current direction) are averaged by circular mean to handle the 0°/360° wraparound correctly. This averaging is the source of the LP's systematic fuel estimation bias under SOG-targeting, as analyzed in Section 7.1.

## 4.2 Dynamic Deterministic Optimization (DP)

The DP formulation operates on the full set of $N$ nodes without aggregation. A forward Bellman recursion finds the minimum-fuel path through a time-distance state space, where the state is $(i, t)$ — node index $i$ and discretized time slot $t$.

**Edge cost.** For node $i$ at time $t$, selecting speed $v_k$ produces:

$$c(i, t, k) = FCR(v_k) \cdot \frac{d_i}{SOG(v_k,\, \mathbf{w}_{i,t})} \tag{17}$$

where $\mathbf{w}_{i,t}$ is the weather at node $i$ at forecast hour $t$, obtained from predicted weather with forecast origin at sample hour 0. The SOG is computed via the full speed correction model.

**Bellman recursion.** The minimum cost to reach node $i+1$ at time slot $t'$ is:

$$J^*(i+1, t') = \min_{k} \left[ J^*(i, t) + c(i, t, k) \right] \tag{18}$$

where $t' = \lceil (t \cdot \Delta t + d_i / SOG(v_k, \mathbf{w}_{i,t})) / \Delta t \rceil$ and $\Delta t$ is the time granularity (0.1 h). The recursion is initialized with $J^*(0, 0) = 0$ and proceeds forward through all $N-1$ legs. The optimal arrival state is $\min_{t \leq T/\Delta t} J^*(N, t)$, and the speed schedule is recovered by backtracking parent pointers.

**Weather lookup.** At each state $(i, t)$, the forecast hour is $\min(\lfloor t \cdot \Delta t \rceil, h_{max})$, where $h_{max}$ is the maximum available forecast hour. When the voyage extends beyond the forecast horizon, the last available forecast hour is used as a persistence fallback — the optimizer assumes conditions remain unchanged beyond the forecast boundary.

**State space and complexity.** For Route 1: 138 nodes $\times$ 1,900 time slots $\times$ 21 speeds $\approx$ 5.5M edges. For Route 2: 389 nodes $\times$ 2,130 time slots $\times$ 21 speeds $\approx$ 17.4M edges. The time complexity is $O(N \cdot M \cdot K)$ where $N$ is nodes, $M$ is time slots, and $K$ is speed choices. Sparse storage (dictionary of dictionaries) ensures only reachable states consume memory — in practice, fewer than 15% of $(i, t)$ states are reachable, reducing memory by an order of magnitude. Practical solution times were 2–5 seconds for Route 1 and 8–15 seconds for Route 2 on a single CPU core.

## 4.3 Dynamic Rolling Horizon Optimization (RH)

The RH approach periodically re-solves the DP with updated weather information. At each decision point $\tau = 0, \Delta\tau, 2\Delta\tau, \ldots$ (where $\Delta\tau = 6$ h, aligned to the GFS model refresh cycle), the following steps are executed:

**Step 1: Forecast selection.** The most recent predicted weather with sample hour $\leq \tau$ is loaded, providing the forecast from the closest NWP initialization prior to the current decision time.

**Step 2: Actual weather injection.** For all nodes that fall within the committed window $[\tau, \tau + \Delta\tau]$, the predicted weather is replaced with actual (observed) weather at the closest available sample hour. This ensures that every speed committed in this cycle is planned against ground-truth conditions for the legs the ship will actually traverse before the next re-plan.

**Step 3: Sub-problem solve.** A full DP (Section 4.2) is solved for the remaining voyage — from the current node to the destination — with the remaining ETA as the time constraint and the modified weather grid from Steps 1–2.

**Step 4: Commit and advance.** Only the speeds for legs starting within the $[\tau, \tau + \Delta\tau]$ window are committed to the final schedule. The remaining speeds computed in Step 3 are discarded; they will be re-optimized at the next decision point with fresher information.

Formally, at decision point $\tau$, let $i_\tau$ be the current node and $T_\tau = T - \tau$ the remaining ETA. The RH solves:

$$\min \sum_{j=i_\tau}^{N-1} c(j, t_j, k_j) \quad \text{s.t. } \sum_{j=i_\tau}^{N-1} \frac{d_j}{SOG(v_{k_j}, \tilde{\mathbf{w}}_{j,t_j})} \leq T_\tau \tag{19}$$

where the modified weather $\tilde{\mathbf{w}}$ is:

$$\tilde{\mathbf{w}}_{j,t} = \begin{cases}
\mathbf{w}^{actual}_{j,t} & \text{if } \tau \leq t \leq \tau + \Delta\tau \\
\mathbf{w}^{predicted}_{j,t} & \text{otherwise}
\end{cases} \tag{20}$$

Only the committed portion ($j$ such that $t_j \in [\tau, \tau + \Delta\tau]$) enters the final schedule.

**Infeasibility fallback.** In rare cases, injecting actual weather for the committed window can make the sub-problem infeasible (e.g., when headwinds are stronger than forecast and the remaining ETA is tight). When this occurs, the optimizer retries with forecast-only weather, accepting slightly higher plan-simulation mismatch in exchange for feasibility.

**Decision point count.** For Route 1 ($T = 140$ h, $\Delta\tau = 6$ h): up to 24 decision points (fewer if the ship reaches the destination early). For Route 2 ($T = 163$ h, $\Delta\tau = 6$ h): up to 28 decision points. Each decision point requires a full DP solve over the remaining voyage, so total computation scales as $O(D \cdot N \cdot M \cdot K)$ where $D$ is the number of decision points, $N$ the average remaining nodes, $M$ the time slots, and $K$ the speed choices.

## 4.4 Two-Phase Evaluation Framework

Every optimization approach is evaluated in two phases: **planning** (the optimizer selects speeds under its available weather information) and **simulation** (the planned speeds are tested against actual weather to determine true fuel consumption). This separation reveals how well each optimizer's assumptions hold in practice.

### 4.4.1 Planning Phase

Each optimizer sees different weather during planning:

[TABLE: approach comparison]

All three optimizers produce valid schedules with SWS within [11, 13] kn — zero violations occur during planning. Violations arise only during simulation, when actual weather differs from what was assumed.

### 4.4.2 Simulation Phase

The simulation engine takes the planned SOG schedule and determines the SWS the engine must set at each leg to maintain that SOG under actual weather. This is the SOG-targeting mechanism:

1. For each leg $i$, the simulator receives the target $V_{g,i}$ from the optimizer's plan.
2. The inverse speed correction model finds the SWS $V_{s,i}$ required to achieve $V_{g,i}$ under the actual weather at node $i$. Because the forward SOG function (Section 3.3) is monotonically increasing in $V_s$ but has no closed-form inverse, the inversion is performed by binary search over the SWS range [5, 25] kn with a convergence tolerance of 0.001 kn (typically 15–20 iterations).
3. If $V_{s,i} \notin [11, 13]$ kn, it is clamped to the engine limits and the achieved SOG is recomputed using the forward model. This constitutes an SWS violation — the ship cannot maintain the planned ground speed under the actual weather conditions at that node.
4. Fuel is computed as $FCR(V_{s,i}^{clamped}) \times d_i / V_{g,i}^{actual}$, where $V_{g,i}^{actual}$ equals the target SOG if no clamping occurred, or the recomputed SOG otherwise.

**Static vs time-varying simulation.** LP and DP are simulated against a frozen actual-weather snapshot at hour 0. This is consistent with their planning assumption: both plan against a single temporal reference. RH is simulated with time-varying actual weather, where the simulator selects the closest available sample hour to each leg's cumulative transit time. This matches RH's planning assumption that each committed window uses weather observed at that decision time.

The rationale for this asymmetry is methodological fairness. Simulating LP and DP against time-varying weather would penalize them for temporal drift they never planned for — conflating forecast error with temporal misalignment. Simulating RH against static hour-0 weather would unfairly penalize it for correctly matching the temporal conditions. Each approach is tested against the weather it was designed to use. A consequence is that LP's plan-simulation gap reflects only spatial averaging (it plans and simulates with actual weather), while DP's gap includes forecast error (it plans with predicted weather but is simulated against actual). This is an inherent difference in what each approach is designed to do, not a confound — and results in Section 6 confirm that LP produces equivalent fuel to constant-speed sailing regardless of whether actual or predicted weather is used for planning.

### 4.4.3 How Violations Arise

During planning, all optimizers choose SWS values within [11, 13] kn by construction. During simulation, violations occur because actual weather at a specific node differs from the weather used in planning:

- **LP violations** arise from segment averaging: individual nodes within a segment experience worse conditions than the segment mean, requiring SWS above 13 kn to maintain the planned SOG.
- **DP violations** arise from forecast error: predicted weather at planning time differs from actual weather at simulation time, and the divergence grows with lead time.
- **RH violations** are minimal because the committed window uses actual weather. The residual violations occur at the boundary of the last decision point, where the optimizer falls back to forecast weather for the remaining legs.

## 4.5 Theoretical Bounds

Three bounds frame the optimization opportunity:

**Upper bound (maximum fuel).** Constant SWS = 13 kn (maximum engine speed) at every node, with SOG varying according to actual weather. This represents the worst-case fuel consumption within the feasible speed range. For Route 1: 203.91 mt.

**Optimal bound (minimum achievable fuel).** DP with time-varying actual weather — equivalent to perfect foresight. The optimizer knows the exact weather at every node at the time the ship passes through it. This produces the minimum fuel achievable under real weather with per-node resolution. For Route 1: 176.23 mt, with zero SWS violations.

**Average bound (calm-water floor).** Constant SOG equal to total distance divided by ETA (i.e., $V_g = D_{total} / T$), computed in calm water where SWS = SOG. For Route 1: SOG = 11.98 kn, yielding 170.06 mt. By Jensen's inequality on the convex cubic FCR, any speed variation above or below this constant increases total fuel. This bound is a theoretical floor; it is not achievable under non-uniform weather.

The **optimization span** is the difference between upper and optimal bounds (203.91 $-$ 176.23 = 27.68 mt for Route 1). The **weather tax** is the difference between the optimal bound and the average bound (176.23 $-$ 170.06 = 6.17 mt) — the unavoidable cost of operating in non-uniform conditions even with a perfect optimizer. Each approach's fuel above the optimal bound is its **information penalty**: the cost of imperfect weather knowledge or spatial averaging. These three metrics — span, tax, and penalty — provide a normalized framework for comparing approaches: the **span captured** by an approach, defined as $(F_{upper} - F_{approach}) / (F_{upper} - F_{optimal}) \times 100\%$, measures how much of the theoretical optimization opportunity is realized.

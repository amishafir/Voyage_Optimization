# 4. Methodology

<!-- ~2,000 words -->
<!-- Contributions carried: C1 (SOG-targeting rationale) -->

## 4.1 Linear Programming Formulation

<!-- Objective, SOS2 variables for piecewise linear approximation, constraints -->
<!-- Segment averaging: 6 segments from ~138 nodes -->
<!-- Eqs 11–13 -->

## 4.2 Dynamic Programming Formulation

<!-- Graph construction, edge cost, forward Bellman recursion, backtracking -->
<!-- Per-node resolution, time-varying weather -->
<!-- Eqs 14–16 -->

## 4.3 Rolling Horizon Formulation

<!-- Decision points every 6h, committed window, re-solve remainder -->
<!-- Actual weather injection for committed window -->
<!-- Eq 17: RH decision rule -->
<!-- Eq 18: actual weather injection -->

## 4.4 Two-Phase Evaluation Framework

<!-- Phase 1: Planning — what weather each approach sees -->
<!-- TABLE: approach comparison — see tables/T04_approach_comparison.md -->

### 4.4.1 Planning Phase

<!-- LP: actual weather, segment-averaged -->
<!-- DP: predicted weather from forecast origin 0 -->
<!-- RH: predicted + actual at each 6h decision point -->

### 4.4.2 Simulation Phase

<!-- LP/DP: static (sample_hour=0) -->
<!-- RH: time-varying (closest actual sample per leg) -->
<!-- How violations arise: planned SOG -> required SWS under actual weather -> clamp -->

## 4.5 Theoretical Bounds

<!-- Upper: constant SWS=13 kn -->
<!-- Optimal: DP with time-varying actual weather (perfect foresight) -->
<!-- Average: constant SOG = total_distance / ETA -->


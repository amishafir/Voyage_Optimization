# Paper Outline — Transportation Research Part C

## Title

**Speed Over Ground Targeting Reveals the True Value of Dynamic Voyage Optimization: Comparing LP, DP, and Rolling Horizon Under Real Weather Forecasts**

## Target

- Journal: Transportation Research Part C: Emerging Technologies
- Length: ~8,000–10,000 words (excluding references)
- Scope: exp_b (Persian Gulf, mild weather) + exp_d (North Atlantic, harsh weather)

## Six Contributions

| # | Contribution | Primary Section |
|---|-------------|-----------------|
| C1 | SOG-targeting simulation reverses LP/DP ranking (Jensen's inequality on cubic FCR) | 04_methodology, 07_discussion |
| C2 | RH with actual weather injection within 0.1% of theoretical optimal | 06_results |
| C3 | Forecast horizon effect is route-length dependent | 06_results, 07_discussion |
| C4 | Information value hierarchy: temporal > spatial > re-planning | 07_discussion |
| C5 | Empirical forecast error curve (wind RMSE doubles over 133h) | 06_results |
| C6 | 6h replan frequency = GFS model cycle alignment (86% hourly calls redundant) | 06_results, 07_discussion |

---

## Section Structure

### 00 — Abstract (~250 words)

**Purpose:** Summarize problem, method, key results, and implications.
**Contributions carried:** All 6 (one sentence each).
**Write last** — after all sections are complete.

### 01 — Introduction (~1,200 words)

**Purpose:** Motivate the problem, establish the research gap, state contributions.
**Structure:**
1. Maritime fuel optimization matters now (IMO 2023 GHG strategy, EEXI, CII) → [CITE: regulatory]
2. Speed optimization approaches exist (LP, DP, metaheuristics) but are never compared on the same route → [CITE: Pillar 1]
3. Simulation assumption gap: fixed-SWS vs SOG-targeting → [CITE: Pillar 4]
4. Weather forecast quality degrades but nobody measures propagation through optimizer → [CITE: Pillar 3]
5. Rolling horizon exists in OR but rarely in maritime speed optimization → [CITE: Pillar 5]
6. **Gap statement** (1 paragraph)
7. **Contributions list** (numbered, C1–C6)
8. Paper organization paragraph

**Source files:** `docs/literature_review_strategy.md` (gap statements), `context/literature/pillar_{1,4,5,6}_*.md`
**Tables/Figures:** None

### 02 — Literature Review (~1,500 words)

**Purpose:** Establish the gap systematically, organized by pillar.
**Structure:**
1. Ship speed optimization methods (LP, DP, metaheuristics) — Pillar 1
2. Fuel consumption modeling and the cubic relationship — Pillar 2
3. Weather forecasting in maritime optimization — Pillar 3
4. Simulation methodology: SOG-targeting vs fixed-SWS — Pillar 4
5. Rolling horizon and information value — Pillar 5
6. Summary of gaps table

**Source files:** `context/literature/pillar_{1-6}_*.md`, `context/literature/_index.md`
**Tables/Figures:** Table — gap summary (pillar × what exists × what's missing)

### 03 — Problem Formulation (~1,000 words)

**Purpose:** Define the ship, route, physics model, and decision framework.
**Structure:**
1. Ship parameters (200m, 32m beam, 10,000 kW, 11–13 kn range)
2. Route description (exp_b: Persian Gulf → Malacca, 138 nodes; exp_d: St. John's → Liverpool, 389 nodes)
3. Physics model: SOG calculation chain (Eqs 1–8)
4. FCR formula: `0.000706 × V_s³`
5. Decision variable: SOG (not SWS) — explain SOG-targeting
6. Total fuel calculation

**Source files:** `/research-paper` skill, `/waypoints` skill, `docs/thesis_brainstorm.md`
**Tables/Figures:** Table — ship parameters; Table — route summary; Figure — route map
**Equations:** Eqs 1–10 (SOG chain + FCR + segment fuel)

### 04 — Methodology (~2,000 words)

**Purpose:** Define the three optimization approaches + simulation framework.
**Structure:**
1. **LP formulation** — objective, SOS2 variables, constraints, segment averaging
2. **DP formulation** — graph construction, edge cost, forward Bellman, backtracking
3. **RH formulation** — decision points, committed window, actual weather injection, re-solve
4. **Two-phase evaluation framework** — planning (optimizer sees weather) → simulation (test against actual)
   - Phase 1: what weather each approach sees (table)
   - Phase 2: how simulation works (static vs time-varying)
   - How violations arise
5. **Theoretical bounds** — upper (SWS=13), optimal (DP with perfect foresight), average (constant speed)

**Source files:** `/lp-optimizer`, `/dp-optimizer` skills, `docs/thesis_brainstorm.md` §3, `docs/meeting_prep_2026_02_23.md`
**Tables/Figures:** Table — approach comparison (weather source, resolution, re-planning)
**Equations:** Eqs 11–18 (LP objective, LP constraints, DP recursion, RH decision rule)
**Contributions carried:** C1 (SOG-targeting rationale)

### 05 — Experimental Setup (~800 words)

**Purpose:** Describe data collection, datasets, and experimental design.
**Structure:**
1. Open-Meteo API — what it provides (GFS wind, MFWAM waves, SMOC currents)
2. HDF5 data structure (actual_weather, predicted_weather, metadata)
3. Experiment B — route, nodes, duration, weather conditions
4. Experiment D — route, nodes, duration, weather conditions
5. NWP model cycles and 6h sampling alignment
6. 2×2 factorial design (exp_a/b) for decomposition

**Source files:** `docs/meeting_prep_2026_02_23.md` §1, `docs/meeting_prep_2026_03_02.md` §2, `docs/thesis_brainstorm.md` §8
**Tables/Figures:** Table — experiment summary (route, nodes, hours, weather stats)

### 06 — Results (~2,000 words)

**Purpose:** Present all quantitative findings.
**Structure:**
1. **Main comparison** — LP/DP/RH plan vs sim fuel, gaps, violations (exp_b table, exp_d table)
2. **Theoretical bounds** — framing the optimization span
3. **Ranking reversal** — fixed-SWS vs SOG-target comparison table
4. **Forecast error curves** — RMSE vs lead time for both routes
5. **2×2 factorial decomposition** — temporal vs spatial vs interaction
6. **Replan frequency sweep** — 1h to 24h, new-info rates
7. **Horizon sweep** — short route (flat) vs long route (plateau at 72h)
8. **SWS violation analysis** — per-approach, severity, geographic clustering
9. **Generalizability** — findings that hold across both routes

**Source files:** `docs/thesis_brainstorm.md` §3–8, `docs/meeting_prep_2026_03_09.md`
**Tables/Figures:** ~6 tables (main results ×2, forecast error, decomposition, sensitivity, violations); ~3 figures (RMSE curves, fuel comparison bar chart, horizon sweep plot)
**Contributions carried:** C2, C3, C5, C6

### 07 — Discussion (~1,500 words)

**Purpose:** Interpret results, explain mechanisms, connect to literature.
**Structure:**
1. **Jensen's inequality mechanism** — why SOG-targeting penalizes LP (C1)
2. **Information value hierarchy** — temporal freshness > spatial resolution > re-planning (C4)
3. **Weather tax and information penalty** — decomposing fuel above optimal
4. **Route-length dependence** — when dynamic optimization matters (C3)
5. **Practical implications** — 6h replan = GFS cycle, 86% API redundancy (C6)
6. **Comparison with literature** — how our findings relate to prior work
7. **Limitations** — simulation credibility, calm weather on exp_b, two routes only

**Source files:** `docs/thesis_brainstorm.md` §3–4, §9–12
**Contributions carried:** C1, C3, C4, C6

### 08 — Conclusion (~500 words)

**Purpose:** Summarize contributions, state practical implications, suggest future work.
**Structure:**
1. Summary of six contributions (1 sentence each)
2. Practical recommendation: use RH with 6h replan aligned to NWP cycles
3. Future work: more routes, harsher weather (exp_c), FCR exponent sensitivity, forecast quality threshold

**Source files:** `docs/thesis_brainstorm.md` §12

---

## Tables Plan

| # | Table | Section | Source |
|---|-------|---------|--------|
| 1 | Ship parameters | 03 | `/research-paper` skill |
| 2 | Route and experiment summary | 05 | thesis_brainstorm §8 |
| 3 | Approach comparison (weather, resolution, re-planning) | 04 | thesis_brainstorm §3 |
| 4 | Main results — exp_b | 06 | thesis_brainstorm §3 |
| 5 | Main results — exp_d | 06 | pending (~Mar 8) |
| 6 | Ranking reversal (fixed-SWS vs SOG-target) | 06 | thesis_brainstorm §3 |
| 7 | Forecast error vs lead time | 06 | thesis_brainstorm §6 |
| 8 | 2×2 factorial decomposition | 06 | thesis_brainstorm §4 |
| 9 | Replan frequency sweep | 06 | thesis_brainstorm §5 |
| 10 | NWP model cycles | 05 or 06 | thesis_brainstorm §6b |
| 11 | Generalizability across routes | 06 | thesis_brainstorm §8 |

## Figures Plan

| # | Figure | Section | Type |
|---|--------|---------|------|
| 1 | Route maps (exp_b, exp_d) | 05 | Map plot |
| 2 | Wind RMSE vs lead time (both routes) | 06 | Line plot |
| 3 | Fuel comparison bar chart (LP/DP/RH, both routes) | 06 | Grouped bar |
| 4 | Horizon sweep (DP and RH fuel vs horizon length) | 06 | Line plot |
| 5 | Plan-sim gap visualization | 06 or 07 | Bar or waterfall |

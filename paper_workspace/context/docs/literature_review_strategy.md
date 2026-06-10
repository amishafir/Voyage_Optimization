# Literature Review Strategy

## Access & Accounts

**Default login for academic databases:** `amishafir@mail.tau.ac.il`

| Platform | URL | Access |
|----------|-----|--------|
| ResearchGate | researchgate.net | Login with `amishafir@mail.tau.ac.il` |
| Google Scholar | scholar.google.com | Login with `amishafir@mail.tau.ac.il` |
| Scopus | scopus.com | TAU institutional login (`amishafir@mail.tau.ac.il`) |
| Web of Science | webofscience.com | TAU institutional login (`amishafir@mail.tau.ac.il`) |
| IEEE Xplore | ieeexplore.ieee.org | TAU institutional login (`amishafir@mail.tau.ac.il`) |
| ScienceDirect | sciencedirect.com | TAU institutional login (`amishafir@mail.tau.ac.il`) |
| MDPI | mdpi.com | Login with `amishafir@mail.tau.ac.il` (open access) |
| SpringerLink | link.springer.com | TAU institutional login (`amishafir@mail.tau.ac.il`) |
| Taylor & Francis | tandfonline.com | TAU institutional login (`amishafir@mail.tau.ac.il`) |

**Tip:** For paywalled papers, use TAU library proxy or access from campus network / VPN (`vpn.tau.ac.il`).

---

## Structure: 6 Pillars Mapped to Thesis Contributions

Each pillar serves a specific thesis function: establishing the gap the thesis fills.

| Pillar | Thesis Contribution It Supports |
|--------|--------------------------------|
| 1. Ship Speed Optimization | Field positioning — nobody compares LP vs DP vs RH on same route |
| 2. Fuel Consumption & Resistance | Justifies physics model, frames Jensen's inequality insight |
| 3. Weather Forecasting & NWP | Grounds forecast error analysis and NWP cycle findings |
| 4. Simulation Methodology | Defends SOG-targeting as correct simulation model (most novel) |
| 5. Rolling Horizon & Information Value | Positions RH as superior, explains why through information theory |
| 6. Regulatory & Industry Context | Motivates the entire thesis — why fuel optimization matters now |

---

## Pillar 1: Ship Speed Optimization (core field positioning)

**Purpose:** Show what exists, identify the gap (no one compares LP vs DP vs RH under realistic simulation).

| Sub-topic | What to find | Why |
|-----------|-------------|-----|
| LP-based voyage optimization | Papers using LP/MILP for speed selection per segment | Our primary paper falls here — position it |
| DP / graph-based approaches | Time-distance graph construction, Dijkstra on fuel cost | Our DP module extends this |
| Rolling horizon / MPC in maritime | RH applied to ship routing or speed | Likely sparse — this is the gap |
| Metaheuristics (GA, PSO) | Our paper's GA baseline; others doing the same | Show LP/DP are underexplored vs GA dominance |
| Weather routing vs speed optimization | Routing = path choice; speed opt = fixed path, vary speed | Clarify scope — we do speed optimization, not routing |

**Gap to establish:** Most papers compare one method against a baseline. Nobody does LP vs DP vs RH on the same route with the same physics model, and nobody examines how the simulation model (SOG-target vs fixed-SWS) affects the ranking.

### Search queries

```
"ship speed optimization" "linear programming"
"voyage optimization" "dynamic programming" fuel
"rolling horizon" "ship speed" OR "vessel speed"
"ship speed optimization" "weather" comparison
"maritime" "speed optimization" "metaheuristic" OR "genetic algorithm"
"weather routing" vs "speed optimization" maritime
```

### Key papers to find

- [ ] The seminal LP ship speed optimization papers (likely Norstad et al., Fagerholt et al.)
- [ ] DP/graph-based voyage optimization papers
- [ ] Any RH/MPC applied to ship speed (may be very few — document the absence)
- [ ] GA/PSO papers for ship speed (to show the metaheuristic dominance in the field)
- [ ] Review/survey papers on maritime speed optimization (for a broad field map)

---

## Pillar 2: Fuel Consumption & Resistance Modeling

**Purpose:** Justify the physics model (Tables 2-4, Equations 7-16) and the cubic FCR.

| Sub-topic | What to find | Why |
|-----------|-------------|-----|
| Power-speed relationship | The 2.7–3.3 exponent range across ship types | Validates our cubic (3.0) and frames sensitivity analysis |
| Resistance decomposition | Holtrop-Mennen, Hollenbach, ITTC-1957 | Our paper uses a simpler empirical model — acknowledge trade-off |
| Added resistance in waves | Beaufort-based vs spectral methods | Our Cbeta/CU/CForm tables are one approach among several |
| Current effects on SOG | Vector projection methods | Our Eq 14-16; show this is standard |
| FCR convexity / Jensen's inequality | Any paper noting that speed averaging underestimates fuel | This is contribution #1 — if nobody's said it, that's the gap |

**Gap to establish:** The cubic FCR convexity is well known in naval architecture, but its implication for segment-averaged LP optimization under SOG-targeting has not been analyzed. Jensen's inequality on cubic FCR is the mechanism, but nobody has connected it to the LP vs DP ranking reversal.

### Search queries

```
"fuel consumption rate" "cubic" ship speed
"ship resistance" "added resistance" waves Beaufort
"Holtrop-Mennen" OR "Hollenbach" ship resistance calculation
"power-speed" exponent ship "2.7" OR "3.0" OR "3.3"
"Jensen's inequality" "fuel consumption" OR "convex" ship
"ITTC 1957" friction resistance ship
"speed reduction coefficient" waves ship
```

### Key papers to find

- [ ] Holtrop-Mennen (1982, 1984) — the standard resistance prediction method
- [ ] Hollenbach (1998) — alternative resistance method
- [ ] ITTC-1957 friction line — foundational reference
- [ ] Papers documenting the cubic (or 2.7-3.3) power-speed exponent
- [ ] Any paper connecting Jensen's inequality to fuel estimation under variable speed

---

## Pillar 3: Weather Forecasting & NWP Models

**Purpose:** Ground the forecast error analysis and NWP cycle findings in meteorological literature.

| Sub-topic | What to find | Why |
|-----------|-------------|-----|
| GFS / ECMWF forecast accuracy | Operational verification reports, RMSE vs lead time | Compare our empirical curve (4.1 to 8.4 km/h) against published baselines |
| NWP update cycles | GFS 6h, ECMWF 6h/12h, wave model cycles | Corroborate our empirical finding with official documentation |
| Forecast accuracy in maritime context | Papers on wind/wave forecast quality for ship routing | Likely thin — most routing papers assume "known weather" |
| Open-Meteo / reanalysis data | API-based weather sources for maritime research | Methodological justification for our data source |
| Atmospheric predictability limit | ~72-96h for synoptic wind, Lorenz (1969) | Explains our horizon plateau at 72h |

**Gap to establish:** Speed optimization papers typically assume either perfect weather or a single forecast. Nobody has measured how forecast degradation with lead time propagates through the optimizer to affect fuel outcomes. Our forecast error curve + horizon sweep fills this.

### Search queries

```
"GFS" "forecast accuracy" wind RMSE "lead time"
"ECMWF" verification "10m wind" accuracy
"NWP" "maritime" OR "ship routing" forecast
"weather forecast" "ship speed optimization" uncertainty
"atmospheric predictability" limit Lorenz
"wave forecast" accuracy "lead time" MFWAM OR "ECMWF WAM"
"Open-Meteo" weather API
"ocean current" forecast accuracy SMOC OR Copernicus
```

### Key papers to find

- [ ] NCEP/GFS verification reports (official RMSE statistics by lead time)
- [ ] ECMWF forecast skill documentation
- [ ] Lorenz (1969) — atmospheric predictability limits
- [ ] Papers using weather forecast data in maritime optimization (document how they handle uncertainty)
- [ ] Wave forecast accuracy papers (MFWAM, ECMWF WAM)

---

## Pillar 4: Simulation Methodology & SOG-Targeting (PRIORITY)

**Purpose:** Defend SOG-targeting as the correct simulation model. This is the most novel methodological contribution.

**Priority: START HERE** — this is the most urgent gap (thesis brainstorm action item #10) and relatively small effort.

| Sub-topic | What to find | Why |
|-----------|-------------|-----|
| SOG-targeting in practice | IMO EEXI, CII operational guidelines; charter party clauses | Proves SOG-targeting is how ships actually operate |
| Just-in-time arrival / virtual arrival | BIMCO, IMO guidelines on arrival scheduling | Ships target arrival time -> they target SOG, not SWS |
| Plan-vs-actual simulation frameworks | How other papers simulate planned speed under different weather | Most assume fixed-SWS — document this to show our innovation |
| Slow steaming literature | Papers on reduced-speed operations | Often assume constant speed -> closest to our "LP = constant speed" finding |
| Jensen's inequality in applied optimization | Applications where convexity of objective changes optimal strategy | Mathematical foundation for contribution #1 |

**Gap to establish:** The maritime optimization literature overwhelmingly simulates plans by holding SWS constant (what the engine does). But ships target SOG (to meet arrival schedules). This difference, through Jensen's inequality on cubic FCR, reverses the LP vs DP ranking. Nobody has identified this.

### Search queries

```
"speed over ground" targeting ship operational
"just in time arrival" IMO shipping
"virtual arrival" BIMCO maritime
"EEXI" "speed" operational compliance
"slow steaming" "constant speed" ship fuel
"plan" "actual" simulation "ship speed" OR "voyage"
"Jensen's inequality" optimization "convex" application
"charter party" "speed" "performance" clause
"CII" "operational" speed reduction ship
```

### Key papers to find

- [ ] IMO MEPC resolutions on EEXI and CII (official documents)
- [ ] BIMCO virtual arrival / just-in-time clauses
- [ ] Papers on slow steaming that assume constant SOG (validates our framing)
- [ ] Any paper that distinguishes SOG-targeting from SWS-targeting in simulation
- [ ] Jensen's inequality applications in engineering optimization

---

## Pillar 5: Rolling Horizon & Information Value

**Purpose:** Position RH as superior and explain why through information theory.

| Sub-topic | What to find | Why |
|-----------|-------------|-----|
| Rolling horizon in stochastic optimization | RH/MPC in supply chain, energy, logistics | Show RH is established elsewhere but rare in maritime speed opt |
| Value of information (VOI) | Decision-theoretic framework for when better info helps | Our "information value hierarchy" (temporal > spatial > re-planning) fits here |
| Stochastic weather routing | Papers using ensemble forecasts or scenario trees | Alternative to RH — position ours as simpler, more operational |
| Re-planning frequency in operations | How often to re-optimize in practice | Our 6h = GFS cycle finding is novel |
| Forecast horizon vs decision horizon | When does longer forecast help? | Our route-length dependence finding |

**Gap to establish:** Rolling horizon exists in OR theory but is rarely applied to ship speed optimization with real forecast data. Nobody has analyzed the interaction between NWP model refresh cycles and optimal replan frequency.

### Search queries

```
"rolling horizon" maritime OR shipping OR vessel
"model predictive control" "ship" speed OR routing
"value of information" "voyage planning" OR "ship routing"
"stochastic" "weather routing" ship ensemble
"re-planning" OR "replanning" frequency optimization maritime
"forecast horizon" "decision" optimization shipping
"rolling horizon" "stochastic" "operations research" survey
```

### Key papers to find

- [ ] Survey/textbook on rolling horizon optimization (Sethi & Sorger, or similar)
- [ ] Any RH applied to maritime speed optimization (document absence if none)
- [ ] Value of information theory — foundational references (Howard 1966, Raiffa 1968)
- [ ] Stochastic weather routing papers (ensemble-based approaches)
- [ ] MPC in maritime context (likely vessel path control, not speed optimization)

---

## Pillar 6: Regulatory & Industry Context

**Purpose:** Motivate the entire thesis — why does fuel optimization matter now?

| Sub-topic | What to find | Why |
|-----------|-------------|-----|
| IMO GHG strategy (2023 revision) | Net-zero by ~2050, interim targets | Motivation for the work |
| EEXI (Energy Efficiency Existing Ship Index) | Mandatory since Jan 2023, requires speed reduction | Directly relevant — speed optimization is an EEXI compliance tool |
| CII (Carbon Intensity Indicator) | Annual rating A-E, operational measure | Our 2.3% fuel saving -> quantify CII impact |
| EU ETS for shipping (2024) | Carbon pricing now applies to maritime | Economic motivation — fuel savings = carbon cost savings |
| SEEMP Part III | Company-specific implementation plan | Operational context for optimization adoption |

**Gap to establish:** Regulations now mandate fuel efficiency, but the tools available (LP-based, constant-weather assumptions) are inadequate. Dynamic approaches with real forecast data are needed but underdeveloped.

### Search queries

```
"IMO" "GHG strategy" 2023 shipping
"EEXI" "Energy Efficiency Existing Ship Index" compliance
"CII" "Carbon Intensity Indicator" operational rating
"EU ETS" shipping 2024 maritime
"SEEMP" "Ship Energy Efficiency Management Plan" Part III
IMO MEPC "speed reduction" "fuel efficiency"
```

### Key papers/documents to find

- [ ] IMO MEPC.377(80) — 2023 revised GHG strategy
- [ ] IMO MEPC.328(76) — EEXI and CII amendments
- [ ] EU Regulation 2023/957 — EU ETS extension to maritime
- [ ] BIMCO slow steaming / virtual arrival clauses
- [ ] DNV, Lloyd's, or ClassNK reports on CII compliance strategies

---

## Priority Order

| Priority | Pillar | Effort | Reason |
|:--------:|--------|:------:|--------|
| 1 | 4 — SOG-targeting validation | Small | Most urgent gap, validates your most novel claim |
| 2 | 1 — Speed optimization survey | Medium | Frames the entire thesis, needed first for introduction |
| 3 | 6 — Regulatory context | Small | Easy to collect, motivates the "so what" |
| 4 | 2 — Fuel & resistance modeling | Medium | Justifies your physics model |
| 5 | 3 — Weather forecasting & NWP | Medium | Grounds your empirical findings in met literature |
| 6 | 5 — Rolling horizon & VOI | Medium | Positions your most impactful contribution |

---

## Reference Management

**Suggested tool:** Zotero (free, integrates with TAU library, exports to BibTeX/LaTeX).

**Naming convention for downloaded papers:**
```
AuthorYear_ShortTitle.pdf
e.g., Norstad2011_ShipSpeedOptLP.pdf
     HoltropMennen1982_ResistancePrediction.pdf
```

**Storage:** `context/literature/` (create subdirectories per pillar if needed).

---

## Log

| Date | Action |
|------|--------|
| 2026-02-25 | Strategy document created |

# Style Guide — Transportation Research Part C

## Journal Requirements

- **Word limit:** ~8,000–10,000 words (excluding references, tables, figure captions)
- **Abstract:** max 250 words, structured (no subheadings)
- **Keywords:** 5–6 keywords below abstract
- **Reference style:** Author-year (Elsevier/Harvard), e.g., (Psaraftis and Kontovas, 2013)
- **Figures:** Grayscale-compatible; captions below; referenced as "Fig. 1"
- **Tables:** Captions above; referenced as "Table 1"
- **Equations:** Numbered sequentially, referenced as "Eq. (1)"

## Writing Voice

- Third person, passive preferred: "The optimization was performed..." not "We optimized..."
- Past tense for methods and results: "The LP optimizer selected...", "Wind RMSE increased..."
- Present tense for general truths and established facts: "Fuel consumption rate is cubic in SWS"
- Avoid hedging when data supports the claim; use hedging for extrapolation
- No contractions, no colloquialisms
- "This study" or "the present study" — not "we" or "our"

## Notation

| Symbol | Meaning | Unit |
|--------|---------|------|
| $V_s$ (or SWS) | Still Water Speed | knots (kn) |
| $V_g$ (or SOG) | Speed Over Ground | knots (kn) |
| $FCR$ | Fuel Consumption Rate | mt/h |
| $BN$ | Beaufort Number | dimensionless |
| $H_w$ | Significant wave height | m |
| $V_w$ | Wind speed at 10m | km/h |
| $V_c$ | Ocean current velocity | km/h |
| $\theta_w$ | Wind direction relative to heading | degrees |
| $\theta_c$ | Current direction relative to heading | degrees |
| $d_i$ | Distance of segment/leg $i$ | nm |
| $T$ | Required voyage time (ETA) | hours |
| $F_n$ | Froude number | dimensionless |
| $C_\beta$ | Direction reduction coefficient | dimensionless |
| $C_U$ | Speed reduction coefficient | dimensionless |
| $C_{Form}$ | Ship form coefficient | dimensionless |

### Subscript Conventions

- $i$ — segment (LP) or node/leg (DP/RH)
- $k$ — speed choice index
- $t$ — time slot or sample hour

## Terminology

| Use | Don't Use | Why |
|-----|-----------|-----|
| segment | — | LP spatial unit (~280 nm, averaged) |
| leg or node | — | DP/RH spatial unit (~12 nm or ~5 nm) |
| actual weather | observed weather, ground truth | Consistent with HDF5 table name |
| predicted weather | forecast weather | Consistent with HDF5 table name |
| plan-simulation gap | plan-actual gap | "Actual" is ambiguous (actual fuel vs actual weather) |
| SOG-targeting | SOG targeting, speed targeting | Hyphenated compound modifier |
| rolling horizon (RH) | receding horizon, MPC | Use RH throughout; mention MPC only when citing others |
| static deterministic (LP) | — | Full name on first use, then "LP" |
| dynamic deterministic (DP) | — | Full name on first use, then "DP" |
| dynamic rolling horizon (RH) | — | Full name on first use, then "RH" |
| SWS violation | speed violation, engine violation | Specific: the SWS exceeds [11, 13] kn |
| information penalty | — | Fuel cost above optimal due to imperfect information |
| weather tax | — | Fuel cost above average bound due to non-uniform weather |
| NWP | numerical weather prediction | Spell out on first use |

## Units

- Speed: knots (kn)
- Fuel: metric tonnes (mt)
- Distance: nautical miles (nm)
- Time: hours (h)
- Wind speed: km/h (as provided by Open-Meteo API)
- Wave height: metres (m)
- Current velocity: km/h
- Temperature: not used

## Citation Markers (in draft)

Use these placeholders during drafting — resolved by `paper-assembler`:

- `[CITE: Author Year]` — e.g., `[CITE: Psaraftis 2013]`
- `[TABLE: description]` — e.g., `[TABLE: main results exp_b]`
- `[FIG: description]` — e.g., `[FIG: wind RMSE vs lead time]`
- `[EQ: number]` — e.g., `[EQ: 7]` for equation cross-references

## Number Formatting

- Fuel: 2 decimal places in mt (e.g., 176.40 mt)
- Percentages: 1 decimal place (e.g., +2.5%)
- RMSE: 2 decimal places (e.g., 4.13 km/h)
- Violations: fraction and percentage (e.g., 4/137 (2.9%))
- Distances: 0 decimal places for route length (e.g., 1,955 nm), 1 for segment distance
- Time: 0 or 1 decimal place (e.g., 140h, 131.5h)

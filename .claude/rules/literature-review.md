# Literature Review Conventions

## Citation Format

Use this format for all citations in pillar files:
```
Author(s), Year. *Title*. Journal, Volume(Issue), Pages. DOI
```

Examples:
- `Norstad, I., Fagerholt, K., Laporte, G., 2011. *Tramp ship routing and scheduling with speed optimization*. Transportation Research Part C, 19(5), 853-865. https://doi.org/10.1016/j.trc.2010.05.001`
- `IMO, 2023. *2023 IMO Strategy on Reduction of GHG Emissions from Ships*. MEPC.377(80).`

## PDF Naming

Pattern: `AuthorYear_ShortTitle.pdf`
- Use first author's last name only
- CamelCase for the short title, max ~30 characters
- Examples: `Norstad2011_ShipSpeedOptLP.pdf`, `HoltropMennen1982_Resistance.pdf`
- Store in: `context/literature/pdfs/`

## Validation Requirements

Every paper entering a pillar file MUST have:
1. **Confirmed existence** — DOI resolved OR found in Semantic Scholar with matching metadata
2. **Accurate citation** — title, authors, year, journal all verified
3. **User approval** — entry reviewed in conversation before filing

Papers with UNCONFIRMED or SUSPECT status must NOT be filed until validated.

## Pillar Assignment

- Each paper has exactly ONE primary pillar
- Papers can have secondary pillar assignments noted in the cross-pillar table in `_index.md`
- Assign based on the paper's main contribution, not where it's most useful to us

## Entry Completeness

All template fields are required. If information is unavailable, use:
- `"Not available from abstract"` — when working from metadata only (no PDF)
- `"Not applicable"` — when a field genuinely doesn't apply (e.g., IMO resolution has no "Methodology")

Never leave a field blank or with "TBD" — fill it or mark why it's empty.

## Tags

Use sub-topic tags from `docs/literature_review_strategy.md`. Consistent tags per pillar:

| Pillar | Valid Tags |
|--------|-----------|
| 1 | `LP-based`, `DP-based`, `rolling-horizon`, `MPC`, `metaheuristic`, `GA`, `PSO`, `weather-routing`, `speed-optimization`, `survey` |
| 2 | `power-speed-exponent`, `resistance-decomposition`, `Holtrop-Mennen`, `Hollenbach`, `ITTC`, `added-resistance-waves`, `current-effects`, `FCR-convexity`, `Jensen-inequality` |
| 3 | `GFS`, `ECMWF`, `NWP-accuracy`, `forecast-verification`, `maritime-weather`, `Open-Meteo`, `atmospheric-predictability`, `wave-forecast` |
| 4 | `SOG-targeting`, `just-in-time`, `virtual-arrival`, `plan-vs-actual`, `slow-steaming`, `Jensen-inequality`, `EEXI-operational`, `CII-operational` |
| 5 | `rolling-horizon`, `MPC`, `value-of-information`, `stochastic-routing`, `replan-frequency`, `forecast-horizon`, `ensemble-forecast` |
| 6 | `IMO-GHG`, `EEXI`, `CII`, `EU-ETS`, `SEEMP`, `slow-steaming`, `decarbonization` |

## Gap Framing

When writing "Limitations / Gaps", always frame relative to what our thesis does differently. Common gap patterns:

- "Assumes constant weather / perfect forecast" → we use real NWP with degradation
- "Uses only one optimization method" → we compare LP, DP, and RH
- "Fixed-SWS simulation" → we use SOG-targeting
- "No rolling horizon" → we implement RH with NWP cycle alignment
- "Synthetic weather data" → we use real Open-Meteo API data
- "No forecast error analysis" → we measure propagation through optimizer

## Index Maintenance

The `_index.md` article counts must always match the actual entries in each pillar file. When filing an entry:
1. Increment the count in the Progress table
2. Add a row to the All Articles table
3. Add to Cross-Pillar References if applicable
4. Update the "Total: N articles" line

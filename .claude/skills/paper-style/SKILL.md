# Paper Style Guide

> Reference skill for writing conventions. Read `paper/style_guide.md` for the full guide.

## Usage

```
/paper-style
```

## Quick Reference

**Journal:** Transportation Research Part C (Elsevier)

### Voice
- Third person, passive: "The optimization was performed..."
- Past tense for methods/results, present for general truths
- "This study" — never "we" or "our"

### Key Notation
| Symbol | Meaning | Unit |
|--------|---------|------|
| $V_s$ / SWS | Still Water Speed | kn |
| $V_g$ / SOG | Speed Over Ground | kn |
| $FCR$ | Fuel Consumption Rate | mt/h |
| $BN$ | Beaufort Number | — |

### Terminology Rules
- "segment" (LP, averaged) vs "leg/node" (DP/RH, per-waypoint)
- "actual weather" / "predicted weather" (matches HDF5)
- "SOG-targeting" (hyphenated)
- "plan-simulation gap" (not "plan-actual")
- "SWS violation" when SWS ∉ [11, 13] kn

### Number Formatting
- Fuel: 2 dp in mt (176.40 mt)
- Percentages: 1 dp (+2.5%)
- RMSE: 2 dp (4.13 km/h)
- Violations: fraction + % (4/137, 2.9%)

### Citation Markers
- `[CITE: Author Year]` — resolved by assembler
- `[TABLE: description]` — table reference
- `[FIG: description]` — figure reference
- `[EQ: number]` — equation cross-reference

## Process

When invoked, read and present the full style guide from `paper/style_guide.md`.

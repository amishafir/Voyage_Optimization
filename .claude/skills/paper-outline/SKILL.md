# Paper Outline

> Reference skill for the paper structure. Read `paper/paper_outline.md` for the full outline.

## Usage

```
/paper-outline
```

## Quick Reference

**Target:** Transportation Research Part C, ~8,000–10,000 words, exp_b + exp_d.

### Sections

| # | Section | Words | Contributions | Status |
|---|---------|:-----:|:-------------:|:------:|
| 00 | Abstract | 250 | All | Pending |
| 01 | Introduction | 1,200 | — | Pending |
| 02 | Literature Review | 1,500 | — | Pending |
| 03 | Problem Formulation | 1,000 | — | Pending |
| 04 | Methodology | 2,000 | C1 | Pending |
| 05 | Experimental Setup | 800 | — | Pending |
| 06 | Results | 2,000 | C2,C3,C5,C6 | Pending |
| 07 | Discussion | 1,500 | C1,C3,C4,C6 | Pending |
| 08 | Conclusion | 500 | All | Pending |

### Six Contributions

1. **C1:** SOG-targeting simulation reverses LP/DP ranking (Jensen's inequality on cubic FCR)
2. **C2:** RH with actual weather injection within 0.1% of theoretical optimal (176.40 vs 176.23 mt)
3. **C3:** Forecast horizon effect is route-length dependent (flat on short, plateau at 72h on long)
4. **C4:** Information value hierarchy: temporal > spatial > re-planning
5. **C5:** Empirical forecast error curve: wind RMSE doubles (4.13→8.40 km/h) over 133h
6. **C6:** 6h replan frequency = GFS cycle alignment; 86% of hourly API calls return identical data

### Narrative Arc

1. Lead with SOG-targeting insight (methodological novelty)
2. Present 2×2 decomposition (credible quantitative evidence)
3. Present forecast error curve (ground truth, no simulation assumptions)
4. Layer in forecast horizon + route-length dependence
5. Organize as information value hierarchy (actionable framework)

## Process

When invoked, read the full outline at `paper/paper_outline.md` and present the current status of each section. Check which `paper/sections/*.md` files exist and report word counts.

## Important Files

- `paper/paper_outline.md` — full outline with per-section details
- `paper/style_guide.md` — formatting conventions
- `paper/sections/*.md` — section drafts

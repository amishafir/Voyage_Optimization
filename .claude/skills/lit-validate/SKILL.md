# Literature Validation

Validate that a paper citation is real, accurate, and correctly attributed. Catches hallucinated or inaccurate references before they enter the literature review.

## Usage

```
/lit-validate <citation or DOI>
```

Examples:
- `/lit-validate Norstad et al. 2011 ship speed optimization` — validate by author/title
- `/lit-validate 10.1016/j.trb.2010.03.005` — validate by DOI
- `/lit-validate` — validate all entries in a specified pillar file

## Validation Pipeline

### Check 1: DOI Resolution

If a DOI is provided or found:

1. Use `WebFetch` on `https://doi.org/<DOI>` — it should redirect to the publisher page
2. Extract the actual title, authors, journal, and year from the resolved page
3. Compare against the claimed citation — flag any mismatches

If no DOI:
- Search Semantic Scholar API by title:
  ```
  https://api.semanticscholar.org/graph/v1/paper/search?query=ENCODED_TITLE&limit=5&fields=title,authors,year,journal,externalIds,citationCount
  ```
- Match by fuzzy title comparison (allow minor word differences)
- If a match is found, report the DOI for future reference

### Check 2: Metadata Cross-Check

Compare the claimed citation against the resolved metadata:

| Field | Check |
|-------|-------|
| **Title** | Must match (allow minor differences in capitalization, punctuation) |
| **Authors** | First author must match; order should be consistent |
| **Year** | Must match exactly |
| **Journal** | Must match (allow abbreviation differences, e.g., "J. Mar. Sci." vs "Journal of Marine Science") |

Flag mismatches with severity:
- **CRITICAL**: Title or first author doesn't match — likely wrong paper or hallucinated
- **WARNING**: Year off by 1, or journal name slightly different — may be preprint vs published version
- **INFO**: Minor formatting differences — acceptable

### Check 3: Existence Confirmation

Rate the paper's existence confidence:

| Confidence | Criteria |
|------------|----------|
| **CONFIRMED** | DOI resolves to matching paper, or found in Semantic Scholar with matching metadata |
| **LIKELY** | Found in web search with consistent details, but no DOI confirmation |
| **UNCONFIRMED** | Only found in secondary references or AI-generated text; could not independently verify |
| **SUSPECT** | Metadata inconsistencies, DOI doesn't resolve, or no trace found anywhere |

### Check 4: Accessibility Check

Report how the user can access the full paper:
- **Open Access**: Direct PDF link available
- **TAU Access**: Available through TAU institutional login (Scopus, IEEE, ScienceDirect, etc.)
- **Paywalled**: Requires purchase or alternative access
- **Not Available Online**: May need interlibrary loan

## Output Format

```
## Validation Report: [Author (Year)]

### Claimed Citation
> [The citation as provided]

### Resolution
- **DOI:** [DOI if found] → [resolves to: URL]
- **Semantic Scholar:** [found/not found] — [citation count] citations
- **Status:** CONFIRMED / LIKELY / UNCONFIRMED / SUSPECT

### Metadata Comparison
| Field | Claimed | Verified | Match |
|-------|---------|----------|-------|
| Title | ... | ... | YES/NO |
| Authors | ... | ... | YES/NO |
| Year | ... | ... | YES/NO |
| Journal | ... | ... | YES/NO |

### Issues Found
- [List any mismatches or concerns, or "None — citation is accurate"]

### Access
- [How to access the full paper]

### Verdict: PASS / FAIL / NEEDS REVIEW
```

## Batch Validation

When asked to validate an entire pillar file:

1. Read the pillar file (e.g., `context/literature/pillar_1_speed_optimization.md`)
2. Extract all citation entries (look for `**Citation:**` lines)
3. Validate each one sequentially
4. Produce a summary table:

```
## Batch Validation: Pillar X

| # | Author (Year) | DOI | Status | Issues |
|---|--------------|-----|--------|--------|
| 1 | ... | ... | CONFIRMED | None |
| 2 | ... | ... | SUSPECT | Title mismatch |
| ... | | | | |

**Summary:** X/Y confirmed, Z issues found
```

## Important Rules

- **Be skeptical.** Papers suggested by AI (including yourself) may not exist. Always verify.
- **DOI is the gold standard.** A resolving DOI with matching metadata = confirmed.
- **Semantic Scholar is the backup.** If no DOI, this is the best structured source.
- **Report honestly.** If you can't confirm a paper exists, say so clearly — better to flag it now than cite a phantom paper in the thesis.
- **Check for retracted papers.** If the Semantic Scholar result or publisher page mentions retraction, flag immediately.

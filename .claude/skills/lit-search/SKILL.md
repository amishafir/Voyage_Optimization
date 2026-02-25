# Literature Search

Search for real, citable research papers relevant to a specific literature review pillar or topic.

## Usage

```
/lit-search <topic or pillar number>
```

Examples:
- `/lit-search pillar 4` — search for SOG-targeting / simulation methodology papers
- `/lit-search Jensen's inequality fuel consumption` — search for a specific topic
- `/lit-search "rolling horizon" maritime speed optimization` — search with a query

## Search Strategy

### Step 1: Understand the Target

1. If a pillar number is given, read the corresponding file:
   - `context/literature/pillar_1_speed_optimization.md` through `pillar_6_regulatory.md`
2. Read the strategy doc for search queries and key papers to find:
   - `docs/literature_review_strategy.md`
3. Identify the **gap statement** — every paper found should help establish or contrast with this gap.

### Step 2: Search Multiple Sources

Use all three source types, in order:

#### Source A: Web Search (Google Scholar / general)

Use the `WebSearch` tool with academic queries. Strategies:
- Use the pre-defined search queries from the strategy doc
- Add `site:scholar.google.com` or `site:researchgate.net` for academic results
- Search for `"exact title"` when chasing a specific known paper
- Try variations: `"ship speed optimization"` vs `"vessel speed optimization"` vs `"voyage optimization"`

#### Source B: Semantic Scholar API

Use `WebFetch` to query the Semantic Scholar API (free, no key needed):

```
https://api.semanticscholar.org/graph/v1/paper/search?query=QUERY&limit=10&fields=title,authors,year,journal,externalIds,citationCount,abstract
```

- URL-encode the query
- This returns structured metadata including DOI, citation count, and abstract
- Great for confirming paper existence and getting citation counts

For a specific paper by DOI:
```
https://api.semanticscholar.org/graph/v1/paper/DOI:10.xxxx/xxxxx?fields=title,authors,year,journal,externalIds,citationCount,abstract,references
```

#### Source C: Local PDFs

Scan existing PDFs in the project for references to chase:
- `context/literature/pdfs/` — already downloaded papers
- `context/` — the main research paper and description
- Use `Grep` to search for author names, keywords, or titles across PDF text (if readable)

### Step 3: Compile Results

For each paper found, report:

| Field | Value |
|-------|-------|
| **Title** | Full title |
| **Authors** | Author list |
| **Year** | Publication year |
| **Journal** | Journal or conference name |
| **DOI** | DOI if available |
| **Citations** | Citation count (from Semantic Scholar) |
| **Abstract** | First 2-3 sentences or full if short |
| **Relevance** | One sentence on how it relates to the pillar's gap statement |
| **Confidence** | HIGH (confirmed via DOI/Semantic Scholar), MEDIUM (found in search, not yet verified), LOW (mentioned in other papers, not independently confirmed) |

### Step 4: Recommend Priority

Rank the found papers by:
1. **Direct relevance** to the pillar's gap statement
2. **Citation count** (higher = more foundational)
3. **Recency** (newer = more current state of the art)
4. **Availability** (open access > paywalled)

Present the top 5-10 papers as a prioritized list.

## Important Rules

- **NEVER fabricate papers.** If you're not confident a paper exists, mark confidence as LOW and suggest the user verify it.
- **Always try to confirm via Semantic Scholar API** before reporting a paper as HIGH confidence.
- **Include DOI when available** — this is the primary validation anchor.
- **Report "not found" honestly** — if a topic has few papers, that itself supports the gap argument.
- **Cross-reference pillar files** — check if a paper is already entered in another pillar file before recommending it.

## Output Format

```
## Search Results: [Topic/Pillar]

**Query used:** [the search terms]
**Sources checked:** Web Search, Semantic Scholar API, Local PDFs
**Papers found:** X total, Y high-confidence

### Priority List

1. **Author et al. (Year)** — *Title*
   - Journal: ...
   - DOI: ...
   - Citations: ...
   - Relevance: ...
   - Confidence: HIGH

2. ...

### Already in pillar files
- [List any papers already entered]

### Gap evidence
- [Note if the search confirms a gap — e.g., "No papers found combining RH with real forecast data for ship speed"]
```

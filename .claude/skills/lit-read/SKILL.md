# Literature Read & Summarize

Read a downloaded PDF and extract a structured literature entry matching the project template.

## Usage

```
/lit-read <pdf-path> [pillar-number]
```

Examples:
- `/lit-read context/literature/pdfs/Norstad2011_ShipSpeedOptLP.pdf 1`
- `/lit-read context/literature/pdfs/HoltropMennen1982_Resistance.pdf 2`

## Process

### Step 1: Read the PDF

Use the `Read` tool on the PDF file path. The tool can read PDFs directly.

For large PDFs (>10 pages), read in stages:
1. First read pages 1-5 (title, abstract, introduction, methodology overview)
2. Then read the results/conclusions section (usually last 3-5 pages)
3. Read middle sections only if needed for specific details

### Step 2: Load Context

Read the relevant pillar file to understand the gap statement and sub-topics:
- `context/literature/pillar_<N>_*.md` (if pillar number provided)
- `docs/literature_review_strategy.md` (for the full pillar context)

Also read our research paper for comparison:
- `context/Ship Speed Optimization Considering Ocean Currents to Enhance Environmental Sustainability in Maritime Shipping.pdf` (pages 1-5 for abstract/intro)

### Step 3: Extract Structured Entry

Fill in every field from the template (`context/literature/_template.md`):

#### Citation
- Extract: author(s), year, title, journal, volume, issue, pages, DOI
- Format: `Author(s), Year. *Title*. Journal, Volume(Issue), Pages. DOI`
- If DOI is not visible in the PDF, search for it via Semantic Scholar API

#### PDF Path
- Use the path provided by the user
- Confirm it follows the naming convention: `AuthorYear_ShortTitle.pdf`
- If it doesn't, suggest renaming

#### Tags
- Assign sub-topics from the pillar's sub-topic list in the strategy doc
- Example for Pillar 1: `LP-based`, `DP-based`, `rolling-horizon`, `metaheuristic`, `weather-routing`

#### Summary (2-3 sentences)
- What the paper does, what method it uses, and what it finds
- Keep it factual and specific — no filler phrases

#### Key Findings (bullet points)
- 3-5 specific, quantitative findings where possible
- Include numbers: fuel savings percentages, cost reductions, speed ranges
- Focus on findings relevant to our thesis

#### Methodology
- What optimization method (LP, DP, GA, etc.)
- What data (real weather, synthetic, historical)
- What ship type and route
- What simulation approach (if any)

#### Relevance to Thesis
- How does this paper relate to our specific contributions?
- Does it support our gap argument? Contradict it? Provide a baseline?
- Reference our three contributions:
  1. LP vs DP ranking reversal under SOG-targeting (Jensen's inequality)
  2. Forecast error propagation through the optimizer
  3. RH superiority through NWP refresh cycle alignment

#### Quotable Claims
- Extract 2-3 specific statements with page numbers
- Prioritize: quantitative claims, gap admissions ("future work should..."), methodological assumptions
- Use exact quotes where possible

#### Limitations / Gaps
- What does this paper NOT do that we do?
- Common gaps to look for:
  - Assumes constant weather / perfect forecast
  - Uses only one optimization method (no comparison)
  - Simulates with fixed-SWS (not SOG-targeting)
  - No rolling horizon / re-planning
  - Synthetic weather data (not real NWP)

### Step 4: Present for Review

Output the complete entry in copy-paste-ready format (matching the template structure). Do NOT write it to the pillar file — present it for the user to review first.

Include a brief assessment at the end:

```
## Assessment

- **Quality:** HIGH / MEDIUM / LOW (methodological rigor, journal quality)
- **Relevance:** HIGH / MEDIUM / LOW (how central to our gap argument)
- **Recommended pillar(s):** Primary: X, Secondary: Y (if cross-pillar)
- **Priority for thesis:** MUST-CITE / SHOULD-CITE / NICE-TO-HAVE
```

## Important Rules

- **Read the actual PDF.** Do not summarize from memory or training data alone. The Read tool can handle PDFs.
- **Be precise with quotes.** Include page numbers. Don't paraphrase and call it a quote.
- **Flag uncertainties.** If a section of the PDF is unreadable or unclear, say so.
- **Cross-reference.** Check if this paper is already in any pillar file before producing the entry.
- **Stay focused on our thesis.** The summary should emphasize aspects relevant to our research, not give a generic overview.

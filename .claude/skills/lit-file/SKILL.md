# Literature File

Append a reviewed literature entry to the correct pillar file and update the master index.

## Usage

```
/lit-file <pillar-number>
```

The entry to file should be in the current conversation (output of `/lit-read` or the `lit-reviewer` agent, already reviewed and approved by the user).

## Process

### Step 1: Identify the Entry

Look for the most recent literature entry in the conversation. It should have the template fields:
- Citation, PDF, Tags, Summary, Key Findings, Methodology, Relevance to Thesis, Quotable Claims, Limitations / Gaps

If no entry is found in the conversation, ask the user to provide one or run `/lit-read` first.

### Step 2: Read Current State

1. Read the target pillar file: `context/literature/pillar_<N>_*.md`
2. Read the index: `context/literature/_index.md`
3. Check if the paper is already in the pillar file (search by first author + year)

If already present:
- Alert the user: "This paper is already in pillar X. Update the existing entry instead?"
- If user confirms update, use Edit to replace the existing entry

### Step 3: Append to Pillar File

1. If the placeholder entry still exists (`[Placeholder — remove when first real entry is added]`), remove it
2. Append the new entry at the end of the file, before any trailing whitespace
3. Ensure the entry starts with `---` separator and follows the template format

### Step 4: Update the Index

Update `context/literature/_index.md`:

1. **Article count:** Increment the count for the target pillar in the Progress table
2. **All Articles table:** Add a new row with: Author(s), Year, Pillar number, One-line relevance
3. **Cross-Pillar References:** If the entry spans multiple pillars (noted in assessment), add it to the cross-pillar table

### Step 5: Confirm

Report what was done:
```
Filed: [Author (Year)] — *[Title]*
  → Pillar X: [pillar_file.md] (entry #N)
  → Index updated: [new count] articles in pillar X, [total] total
  → Cross-pillar: [Yes/No — if yes, which secondary pillars]
```

## Important Rules

- **Never file without user approval.** The entry must have been reviewed in the conversation first.
- **Check for duplicates.** Always search the pillar file by author + year before appending.
- **Preserve formatting.** The entry must match the template structure exactly.
- **Keep the index accurate.** The counts must match the actual number of entries in each pillar file.
- **Remove placeholders.** Delete the placeholder entry on first real filing.

#!/usr/bin/env python3
"""
Scan paper sections and tables for gaps: placeholders, TODOs, PENDINGs,
missing references, empty sections, and unresolved cross-references.

Usage:
    python3 paper/check_gaps.py
"""

import os
import re
import sys
from pathlib import Path
from collections import defaultdict

PAPER_DIR = Path(__file__).parent
SECTIONS_DIR = PAPER_DIR / "sections"
TABLES_DIR = PAPER_DIR / "tables"
FIGURES_DIR = PAPER_DIR / "figures"
BIB_DIR = PAPER_DIR / "bibliography"

# Patterns that indicate something is missing or incomplete
GAP_PATTERNS = [
    (r"PENDING", "PENDING placeholder — data or results not yet available"),
    (r"TODO", "TODO item — action needed"),
    (r"TBD", "TBD — to be determined"),
    (r"PLACEHOLDER", "PLACEHOLDER — content not yet written"),
    (r"\[CITE:\s*[^\]]+\]", "Unresolved citation"),
    (r"\[TABLE:\s*[^\]]+\]", "Unresolved table reference"),
    (r"\[FIG:\s*[^\]]+\]", "Unresolved figure reference"),
    (r"\[EQ:\s*[^\]]+\]", "Unresolved equation reference"),
    (r"<!--.*?-->", "HTML comment (draft note or instruction)"),
]

# Patterns for skeleton-only sections (only comments/headers, no prose)
SKELETON_RE = re.compile(r"^(?:\s*$|#.*|<!--.*-->.*|\s*\|.*\|.*)*$", re.DOTALL)


def scan_file(path: Path) -> list:
    """Scan a single file for gaps. Returns list of (line_no, pattern_desc, matched_text)."""
    findings = []
    try:
        content = path.read_text(encoding="utf-8")
    except Exception as e:
        findings.append((0, "READ ERROR", str(e)))
        return findings

    lines = content.splitlines()

    for line_no, line in enumerate(lines, 1):
        for pattern, desc in GAP_PATTERNS:
            matches = re.finditer(pattern, line, re.IGNORECASE)
            for m in matches:
                text = m.group(0).strip()
                # Skip if it's just defining the pattern format in the style guide
                if "paper/style_guide" in str(path):
                    continue
                findings.append((line_no, desc, text[:80]))

    # Check if file is skeleton-only (no real prose, just headers and comments)
    prose_lines = [
        l for l in lines
        if l.strip()
        and not l.strip().startswith("#")
        and not l.strip().startswith("<!--")
        and not l.strip().startswith("|")
        and not l.strip().startswith("---")
        and not l.strip().startswith("$$")
        and not l.strip().startswith("```")
        and not l.strip().startswith(">")
        and not l.strip().startswith("- **")
        and not l.strip().startswith("%")
    ]
    # A section file with <3 lines of real prose is likely a skeleton
    if len(prose_lines) < 3 and path.suffix == ".md" and "sections" in str(path):
        findings.append((0, "SKELETON", f"Only {len(prose_lines)} prose lines — section not yet written"))

    return findings


def check_cross_references(sections_dir: Path, tables_dir: Path) -> list:
    """Check that referenced tables and figures exist."""
    findings = []

    # Collect all table files
    table_files = {f.stem for f in tables_dir.glob("T*.md")} if tables_dir.exists() else set()

    # Collect all [TABLE:] and [FIG:] references from sections
    for section_file in sorted(sections_dir.glob("*.md")):
        content = section_file.read_text(encoding="utf-8")

        # Check for references to table numbers not in tables/
        for m in re.finditer(r"Table (\d+)", content):
            table_num = int(m.group(1))
            expected = f"T{table_num:02d}"
            matching = [t for t in table_files if t.startswith(expected)]
            if not matching:
                findings.append((
                    section_file.name,
                    f"References Table {table_num} but no {expected}_*.md found in tables/"
                ))

    return findings


def check_equation_continuity(sections_dir: Path) -> list:
    """Check that equation numbers are sequential across sections."""
    findings = []
    eq_numbers = []

    for section_file in sorted(sections_dir.glob("*.md")):
        content = section_file.read_text(encoding="utf-8")
        for m in re.finditer(r"\\tag\{(\d+\w?)\}", content):
            eq_numbers.append((m.group(1), section_file.name))

    # Check for gaps in integer equation numbers
    int_eqs = []
    for eq, fname in eq_numbers:
        try:
            int_eqs.append((int(eq), fname))
        except ValueError:
            pass  # skip 8a, 8b, etc.

    int_eqs.sort()
    for i in range(1, len(int_eqs)):
        prev_num, prev_file = int_eqs[i - 1]
        curr_num, curr_file = int_eqs[i]
        if curr_num - prev_num > 1:
            missing = list(range(prev_num + 1, curr_num))
            findings.append((
                curr_file,
                f"Equation gap: {prev_num} ({prev_file}) -> {curr_num} ({curr_file}), "
                f"missing: {missing}"
            ))

    return findings


def count_words(path: Path) -> int:
    """Rough word count excluding markdown syntax, comments, and LaTeX."""
    content = path.read_text(encoding="utf-8")
    # Remove HTML comments
    content = re.sub(r"<!--.*?-->", "", content, flags=re.DOTALL)
    # Remove LaTeX display math
    content = re.sub(r"\$\$.*?\$\$", "", content, flags=re.DOTALL)
    # Remove inline LaTeX
    content = re.sub(r"\$[^$]+\$", "", content)
    # Remove markdown headers
    content = re.sub(r"^#+\s+.*$", "", content, flags=re.MULTILINE)
    # Remove table rows
    content = re.sub(r"^\|.*\|$", "", content, flags=re.MULTILINE)
    # Remove horizontal rules
    content = re.sub(r"^---+$", "", content, flags=re.MULTILINE)
    # Remove citation/reference placeholders
    content = re.sub(r"\[(?:CITE|TABLE|FIG|EQ):[^\]]+\]", "", content)
    words = content.split()
    return len(words)


def main():
    print("=" * 70)
    print("  PAPER GAP CHECKER")
    print("=" * 70)

    total_gaps = 0
    total_words = 0

    # --- Sections ---
    print("\n## SECTIONS\n")
    section_files = sorted(SECTIONS_DIR.glob("*.md"))
    for sf in section_files:
        gaps = scan_file(sf)
        wc = count_words(sf)
        total_words += wc

        status = "OK" if not gaps else f"{len(gaps)} gap(s)"
        skeleton = any(g[1] == "SKELETON" for g in gaps)
        if skeleton:
            status = "SKELETON (not written)"
            wc_str = f"  [{wc} words]"
        else:
            wc_str = f"  [{wc} words]"

        non_comment = [g for g in gaps if g[1] != "HTML comment (draft note or instruction)"]
        has_issues = len(non_comment) > 0

        icon = "  " if not has_issues else "!!"
        print(f"  {icon} {sf.name:<35s} {status:<30s}{wc_str}")

        for line_no, desc, text in gaps:
            if desc == "HTML comment (draft note or instruction)":
                continue  # skip verbose comment listing
            if desc == "SKELETON":
                continue  # already shown in status
            total_gaps += 1
            loc = f"L{line_no}" if line_no else "   "
            print(f"       {loc:>5s}  {desc}: {text}")

    # --- Tables ---
    print("\n## TABLES\n")
    table_files = sorted(TABLES_DIR.glob("*.md"))
    for tf in table_files:
        gaps = scan_file(tf)
        non_trivial = [g for g in gaps if g[1] not in (
            "HTML comment (draft note or instruction)", "SKELETON"
        )]
        status = "OK" if not non_trivial else f"{len(non_trivial)} gap(s)"
        icon = "  " if not non_trivial else "!!"
        print(f"  {icon} {tf.name:<35s} {status}")
        for line_no, desc, text in non_trivial:
            total_gaps += 1
            loc = f"L{line_no}" if line_no else "   "
            print(f"       {loc:>5s}  {desc}: {text}")

    # --- Figures ---
    print("\n## FIGURES\n")
    fig_readme = FIGURES_DIR / "README.md"
    if fig_readme.exists():
        gaps = scan_file(fig_readme)
        todo_count = sum(1 for g in gaps if "TODO" in g[2].upper())
        print(f"     {fig_readme.name:<35s} {todo_count} figure(s) marked TODO")
        total_gaps += todo_count
    else:
        print("     No figures/README.md found")

    # --- Bibliography ---
    print("\n## BIBLIOGRAPHY\n")
    bib_file = BIB_DIR / "references.bib"
    if bib_file.exists():
        content = bib_file.read_text()
        entry_count = content.count("@")
        if entry_count == 0:
            print(f"  !! {bib_file.name:<35s} EMPTY — no entries yet")
            total_gaps += 1
        else:
            print(f"     {bib_file.name:<35s} {entry_count} entries")
    else:
        print("  !! references.bib not found")
        total_gaps += 1

    # --- Cross-references ---
    print("\n## CROSS-REFERENCE CHECKS\n")
    xref_issues = check_cross_references(SECTIONS_DIR, TABLES_DIR)
    if xref_issues:
        for fname, issue in xref_issues:
            print(f"  !! {fname}: {issue}")
            total_gaps += 1
    else:
        print("     All table/figure cross-references OK")

    # --- Equation continuity ---
    print("\n## EQUATION CONTINUITY\n")
    eq_issues = check_equation_continuity(SECTIONS_DIR)
    if eq_issues:
        for fname, issue in eq_issues:
            print(f"  !! {fname}: {issue}")
            total_gaps += 1
    else:
        print("     Equation numbering is sequential")

    # --- Unresolved citations across all sections ---
    print("\n## UNRESOLVED CITATIONS\n")
    all_cites = defaultdict(list)
    for sf in section_files:
        content = sf.read_text(encoding="utf-8")
        for m in re.finditer(r"\[CITE:\s*([^\]]+)\]", content):
            cite_text = m.group(1).strip()
            # Split on semicolons for multi-cites
            for c in cite_text.split(";"):
                c = c.strip()
                all_cites[c].append(sf.name)

    if all_cites:
        print(f"     {len(all_cites)} unique citations to resolve:\n")
        for cite, files in sorted(all_cites.items()):
            flist = ", ".join(sorted(set(files)))
            print(f"       [{cite}]  <- {flist}")
    else:
        print("     No unresolved citations (or no sections written yet)")

    # --- Summary ---
    print("\n" + "=" * 70)
    written = [sf for sf in section_files if count_words(sf) > 50]
    skeleton = [sf for sf in section_files if sf not in written]
    print(f"  Sections written:  {len(written)}/{len(section_files)}  "
          f"({', '.join(s.stem for s in written)})")
    print(f"  Sections pending:  {len(skeleton)}  "
          f"({', '.join(s.stem for s in skeleton)})")
    print(f"  Total word count:  {total_words}")
    print(f"  Total gaps found:  {total_gaps}")
    print("=" * 70)

    return 1 if total_gaps > 0 else 0


if __name__ == "__main__":
    sys.exit(main())

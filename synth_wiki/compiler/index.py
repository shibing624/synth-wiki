# -*- coding: utf-8 -*-
"""
@author:XuMing(xuming624@qq.com)
@description: Generate SCHEMA.md and index.md for the wiki output directory.
"""
from __future__ import annotations
import os
import yaml
from datetime import datetime, timezone


SCHEMA_TEMPLATE = """# Wiki Schema

## Domain
{description}

## Conventions
- File names: lowercase, hyphens, no spaces (e.g., `transformer-architecture.md`)
- Every wiki page starts with YAML frontmatter
- Use `[[wikilinks]]` to link between pages (minimum 2 outbound links per page)
- When updating a page, always bump the `updated` date
- Every new page must be added to `index.md`

## Frontmatter
```yaml
---
title: Page Title
created: YYYY-MM-DD
updated: YYYY-MM-DD
type: entity | concept | comparison | technique | claim
tags: [from taxonomy below]
sources: [raw/source-file.md]
confidence: high | medium | low
---
```

## Tag Taxonomy
{tag_taxonomy}

Rule: every tag on a page must appear in this taxonomy. Add new tags here first.

## Page Thresholds
- **Create a page** when an entity/concept appears in {page_threshold}+ sources OR is central to one source
- **Add to existing page** when a source mentions something already covered
- **DON'T create a page** for passing mentions or minor details
- **Split a page** when it exceeds ~200 lines

## Update Policy
When new information conflicts with existing content:
1. Check the dates -- newer sources generally supersede older ones
2. If genuinely contradictory, note both positions with dates and sources
3. Mark the contradiction in frontmatter: `contradictions: [page-name]`
4. Flag for user review in the lint report
"""

DEFAULT_TAG_TAXONOMY = """- General: concept, technique, claim, comparison
- Domain: model, architecture, benchmark, training
- Meta: person, company, tool, dataset"""


def generate_schema(output_dir: str, description: str = "",
                    page_threshold: int = 1,
                    tag_taxonomy: str = "") -> str:
    """Generate SCHEMA.md in the output directory if it does not exist.

    Returns the path to the schema file.
    """
    schema_path = os.path.join(output_dir, "SCHEMA.md")
    if os.path.exists(schema_path):
        return schema_path

    if not description:
        description = "Knowledge base compiled by synth-wiki."
    if not tag_taxonomy:
        tag_taxonomy = DEFAULT_TAG_TAXONOMY

    content = SCHEMA_TEMPLATE.format(
        description=description,
        tag_taxonomy=tag_taxonomy,
        page_threshold=page_threshold,
    )
    os.makedirs(output_dir, exist_ok=True)
    with open(schema_path, "w") as f:
        f.write(content)
    return schema_path


def generate_index(output_dir: str, project_name: str = "") -> str:
    """Generate index.md listing all wiki pages grouped by type.

    Scans entities/, concepts/, comparisons/ directories and builds
    a human-friendly index with one-line descriptions from frontmatter.

    Returns the path to the index file.
    """
    index_path = os.path.join(output_dir, "index.md")

    sections = {
        "Entities": "entities",
        "Concepts": "concepts",
        "Comparisons": "comparisons",
        "Syntheses": "syntheses",
    }

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    total = 0
    section_entries: dict[str, list[str]] = {}

    for section_name, subdir in sections.items():
        dir_path = os.path.join(output_dir, subdir)
        entries = []
        if os.path.isdir(dir_path):
            for fname in sorted(os.listdir(dir_path)):
                if not fname.endswith(".md"):
                    continue
                slug = fname[:-3]
                title = _format_title(slug)
                summary = _extract_frontmatter_field(os.path.join(dir_path, fname), "title")
                if not summary:
                    summary = _extract_frontmatter_field(os.path.join(dir_path, fname), "concept")
                if not summary:
                    summary = title
                entries.append(f"- [[{slug}]] -- {summary}")
                total += 1
        section_entries[section_name] = entries

    lines = [
        "# Wiki Index",
        "",
        f"> Content catalog for **{project_name or 'synth-wiki'}**.",
        f"> Last updated: {now} | Total pages: {total}",
        "",
    ]

    for section_name in sections:
        lines.append(f"## {section_name}")
        entries = section_entries[section_name]
        if entries:
            lines.extend(entries)
        else:
            lines.append("*(none yet)*")
        lines.append("")

    with open(index_path, "w") as f:
        f.write("\n".join(lines))
    return index_path


def _format_title(slug: str) -> str:
    return " ".join(w.capitalize() for w in slug.split("-"))


def _extract_frontmatter_field(path: str, field: str) -> str:
    """Extract a field value from YAML frontmatter."""
    try:
        with open(path) as f:
            content = f.read(2000)
        if not content.startswith("---"):
            return ""
        end = content.find("---", 3)
        if end < 0:
            return ""
        fm_text = content[3:end]
        fm = yaml.safe_load(fm_text)
        if isinstance(fm, dict):
            return str(fm.get(field, ""))
    except (OSError, yaml.YAMLError):
        pass
    return ""

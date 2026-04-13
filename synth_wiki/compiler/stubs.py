# -*- coding: utf-8 -*-
"""
@author:XuMing(xuming624@qq.com)
@description: Pass 4: Generate stub pages for dangling wikilinks.

Scans all wiki articles for [[wikilinks]], resolves them against existing pages
(by slug and by alias), and creates minimal stub pages for unresolved links so
that Obsidian graph view and link navigation work out-of-the-box.
"""
from __future__ import annotations
import os
import re
import unicodedata
from datetime import datetime, timezone

import yaml


_WIKILINK_RE = re.compile(r'\[\[([^\]|]+)(?:\|[^\]]+)?\]\]')

_WIKI_SUBDIRS = ("concepts", "entities", "comparisons")


def generate_stubs(output_dir: str) -> list[str]:
    """Scan wiki articles for dangling [[wikilinks]] and create stub pages.

    Returns list of created stub file paths.
    """
    slug_to_path, alias_to_slug = _build_page_index(output_dir)
    referenced = _collect_wikilinks(output_dir)

    created: list[str] = []
    for target in sorted(referenced):
        if _resolve_link(target, slug_to_path, alias_to_slug):
            continue
        # Dangling link: create a stub
        stub_slug = _to_slug(target)
        if not stub_slug:
            continue
        # Avoid creating duplicate if slug already exists
        if stub_slug in slug_to_path:
            continue
        stub_path = os.path.join(output_dir, "concepts", stub_slug + ".md")
        if os.path.exists(stub_path):
            continue
        _write_stub(stub_path, stub_slug, target)
        slug_to_path[stub_slug] = stub_path
        created.append(stub_path)
    return created


def _build_page_index(output_dir: str) -> tuple[dict[str, str], dict[str, str]]:
    """Build slug->path mapping and alias->slug mapping from all wiki pages."""
    slug_to_path: dict[str, str] = {}
    alias_to_slug: dict[str, str] = {}

    for subdir in _WIKI_SUBDIRS:
        dir_path = os.path.join(output_dir, subdir)
        if not os.path.isdir(dir_path):
            continue
        for fname in os.listdir(dir_path):
            if not fname.endswith(".md"):
                continue
            slug = fname[:-3]
            fpath = os.path.join(dir_path, fname)
            slug_to_path[slug] = fpath

            # Also index the formatted name
            alias_to_slug[slug.lower()] = slug

            # Extract aliases from frontmatter
            aliases = _extract_aliases(fpath)
            for alias in aliases:
                alias_to_slug[alias.lower()] = slug

            # Extract concept name from frontmatter
            concept_name = _extract_field(fpath, "concept")
            if concept_name:
                alias_to_slug[concept_name.lower()] = slug

    return slug_to_path, alias_to_slug


def _collect_wikilinks(output_dir: str) -> set[str]:
    """Collect all unique wikilink targets from wiki articles."""
    targets: set[str] = set()
    for subdir in _WIKI_SUBDIRS:
        dir_path = os.path.join(output_dir, subdir)
        if not os.path.isdir(dir_path):
            continue
        for fname in os.listdir(dir_path):
            if not fname.endswith(".md"):
                continue
            fpath = os.path.join(dir_path, fname)
            with open(fpath) as f:
                content = f.read()
            for m in _WIKILINK_RE.finditer(content):
                target = m.group(1).strip()
                if target:
                    targets.add(target)
    return targets


def _resolve_link(target: str, slug_to_path: dict, alias_to_slug: dict) -> bool:
    """Check if a wikilink target resolves to an existing page."""
    # Direct slug match
    if target in slug_to_path:
        return True
    # Case-insensitive alias match
    if target.lower() in alias_to_slug:
        return True
    # Try converting target to slug and check
    slug = _to_slug(target)
    if slug in slug_to_path:
        return True
    return False


def _to_slug(name: str) -> str:
    """Convert a display name to a slug (lowercase, hyphens, no spaces)."""
    # Remove parenthetical annotations like "搜索引擎营销|SEM（搜索引擎营销）"
    name = re.sub(r'[（(][^）)]*[）)]', '', name).strip()
    # Normalize unicode
    name = unicodedata.normalize("NFKC", name)
    # Replace spaces, underscores, dots with hyphens
    slug = re.sub(r'[\s_./\\]+', '-', name.lower())
    # Remove non-word chars except hyphens and CJK
    slug = re.sub(r'[^\w\u4e00-\u9fff-]', '', slug)
    # Collapse multiple hyphens
    slug = re.sub(r'-{2,}', '-', slug)
    return slug.strip('-')


def _write_stub(path: str, slug: str, display_name: str) -> None:
    """Write a minimal stub page."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    title = display_name
    now = datetime.now(timezone.utc).isoformat()
    content = f"""---
concept: {slug}
aliases: [{_yaml_quote(display_name)}]
confidence: low
stub: true
created_at: {now}
---

# {title}

> [!stub] This page is a stub
> This page was auto-generated because other articles link to it.
> It will be expanded when relevant source material is added.
"""
    with open(path, "w") as f:
        f.write(content)


def _yaml_quote(s: str) -> str:
    """Quote a string for inline YAML list."""
    if '"' in s:
        return "'" + s + "'"
    return '"' + s + '"'


def _extract_aliases(path: str) -> list[str]:
    """Extract aliases list from YAML frontmatter."""
    fm = _parse_frontmatter(path)
    if not fm:
        return []
    aliases = fm.get("aliases", [])
    if isinstance(aliases, list):
        return [str(a) for a in aliases]
    return []


def _extract_field(path: str, field: str) -> str:
    """Extract a single field from YAML frontmatter."""
    fm = _parse_frontmatter(path)
    if not fm:
        return ""
    return str(fm.get(field, ""))


def _parse_frontmatter(path: str) -> dict | None:
    """Parse YAML frontmatter from a markdown file."""
    with open(path) as f:
        content = f.read(3000)
    if not content.startswith("---"):
        return None
    end = content.find("---", 3)
    if end < 0:
        return None
    fm = yaml.safe_load(content[3:end])
    if isinstance(fm, dict):
        return fm
    return None

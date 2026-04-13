# -*- coding: utf-8 -*-
"""
@author:XuMing(xuming624@qq.com)
@description: Generate overview.md - a bird's-eye view of the entire wiki.

Uses LLM to produce a high-level summary of the knowledge base,
listing main themes, key concepts, and navigation guidance.
"""
from __future__ import annotations
import json
import os
from datetime import datetime, timezone
from typing import Optional

import httpx

from synth_wiki.llm.client import Client, Message, CallOpts


def generate_overview(
    output_dir: str,
    client: Client,
    model: str,
    project_name: str = "",
    language: str = "zh-CN",
    max_tokens: int = 3000,
) -> str:
    """Generate or update overview.md for the wiki.

    Reads all concept/entity/comparison/synthesis frontmatter and
    asks LLM to write a high-level overview. Returns the path.
    """
    overview_path = os.path.join(output_dir, "overview.md")

    # Collect page inventory
    inventory = _collect_inventory(output_dir)
    if not inventory["total"]:
        return ""

    prompt = _build_overview_prompt(inventory, project_name, language)
    resp = client.chat_completion([
        Message(role="system", content=(
            f"You are a knowledge base curator. Generate a concise overview "
            f"page that helps readers understand what this wiki covers and "
            f"how to navigate it. Use [[wikilinks]] in slug format. "
            f"Write ALL content in {language}."
        )),
        Message(role="user", content=prompt),
    ], CallOpts(model=model, max_tokens=max_tokens))

    content = resp.content
    if not content.startswith("---"):
        now = datetime.now(timezone.utc).isoformat()
        fm = (
            f"---\n"
            f"title: Overview\n"
            f"type: overview\n"
            f"updated_at: {now}\n"
            f"---\n\n"
        )
        content = fm + content

    with open(overview_path, "w") as f:
        f.write(content)
    return overview_path


def _collect_inventory(output_dir: str) -> dict:
    """Scan wiki directories and collect page titles and counts."""
    sections = {
        "concepts": "concepts",
        "entities": "entities",
        "comparisons": "comparisons",
        "syntheses": "syntheses",
        "summaries": "summaries",
    }
    inventory = {"total": 0, "sections": {}}
    for label, subdir in sections.items():
        dir_path = os.path.join(output_dir, subdir)
        pages = []
        if os.path.isdir(dir_path):
            for fname in sorted(os.listdir(dir_path)):
                if not fname.endswith(".md"):
                    continue
                slug = fname[:-3]
                title = " ".join(w.capitalize() for w in slug.split("-"))
                pages.append({"slug": slug, "title": title})
        inventory["sections"][label] = pages
        inventory["total"] += len(pages)
    return inventory


def _build_overview_prompt(inventory: dict, project_name: str, language: str) -> str:
    parts = [
        f"Generate a wiki overview page for the knowledge base: {project_name or 'synth-wiki'}",
        f"Total pages: {inventory['total']}",
    ]
    for section, pages in inventory["sections"].items():
        if not pages:
            continue
        titles = [p["title"] for p in pages[:15]]
        extra = f" (and {len(pages) - 15} more)" if len(pages) > 15 else ""
        parts.append(f"\n{section.capitalize()} ({len(pages)} pages): {', '.join(titles)}{extra}")

    parts.append(f"\nIMPORTANT: Write in {language}.")
    parts.append("Use YAML frontmatter with: title, type: overview, updated_at.")
    parts.append("All [[wikilinks]] MUST use lowercase-hyphenated slug format.")
    parts.append(
        "Structure:\n"
        "1. Introduction - What this knowledge base covers (2-3 sentences)\n"
        "2. Main Themes - The major topic areas, each with key [[wikilinks]]\n"
        "3. Key Concepts - The most important concepts to start with\n"
        "4. How to Navigate - Brief guidance on using this wiki\n"
        "5. Statistics - Page counts by type"
    )
    return "\n".join(parts)

# -*- coding: utf-8 -*-
"""
@author:XuMing(xuming624@qq.com)
@description: Query-to-archive: archive valuable Q&A answers as wiki pages.

When a user asks a question and gets a substantive answer from the wiki,
this module can archive that answer as a new wiki concept page, closing
the explore→archive loop from Karpathy's LLM Wiki design.
"""
from __future__ import annotations
import json
import os
import re
from datetime import datetime, timezone
from typing import Optional

import httpx

from synth_wiki.llm.client import Client, Message, CallOpts
from synth_wiki.memory import Store as MemoryStore, Entry
from synth_wiki.vectors import Store as VectorStore


def archive_query(
    output_dir: str,
    question: str,
    answer: str,
    sources_used: list[str],
    client: Client,
    model: str,
    mem_store: MemoryStore,
    vec_store: VectorStore,
    embedder=None,
    language: str = "zh-CN",
    max_tokens: int = 3000,
) -> str:
    """Archive a Q&A exchange as a wiki page.

    Returns the path to the created page, or empty string on failure.
    """
    # Ask LLM to determine if the answer is worth archiving and extract a concept name
    eval_resp = client.chat_completion([
        Message(role="system", content=(
            "You evaluate Q&A exchanges for a personal knowledge wiki. "
            "Decide if the answer contains substantial knowledge worth archiving. "
            "Output ONLY valid JSON."
        )),
        Message(role="user", content=(
            f"Question: {question}\n\n"
            f"Answer (first 500 chars): {answer[:500]}\n\n"
            "Should this be archived as a wiki page? Respond with JSON:\n"
            '{"archive": true/false, "slug": "lowercase-hyphenated-name", '
            '"title": "Human Readable Title", "reason": "why"}'
        )),
    ], CallOpts(model=model, max_tokens=200))

    eval_data = _parse_json(eval_resp.content)
    if not eval_data.get("archive", False):
        return ""

    slug = eval_data.get("slug", "")
    title = eval_data.get("title", "")
    if not slug:
        return ""

    # Clean slug
    slug = re.sub(r'[^a-z0-9-]', '-', slug.lower()).strip('-')
    while '--' in slug:
        slug = slug.replace('--', '-')

    # Generate the wiki page from the Q&A
    page_resp = client.chat_completion([
        Message(role="system", content=(
            f"You are a wiki author. Convert a Q&A exchange into a proper wiki article. "
            f"Use YAML frontmatter and [[wikilinks]] in slug format. "
            f"Write ALL content in {language}."
        )),
        Message(role="user", content=(
            f"Convert this Q&A into a wiki article:\n\n"
            f"Question: {question}\n\n"
            f"Answer:\n{answer}\n\n"
            f"Article slug: {slug}\n"
            f"Article title: {title}\n"
            f"Sources used: {', '.join(sources_used)}\n\n"
            "Use YAML frontmatter with: concept, type: query-derived, sources, "
            "confidence: medium, origin_question, created_at.\n"
            "Include sections: Overview, Details, See Also with [[wikilinks]].\n"
            "All [[wikilinks]] MUST use lowercase-hyphenated slug format."
        )),
    ], CallOpts(model=model, max_tokens=max_tokens))

    content = page_resp.content
    if not content.startswith("---"):
        now = datetime.now(timezone.utc).isoformat()
        sources_json = json.dumps(sources_used, ensure_ascii=False)
        fm = (
            f"---\n"
            f"concept: {slug}\n"
            f"type: query-derived\n"
            f"sources: {sources_json}\n"
            f"confidence: medium\n"
            f"origin_question: {json.dumps(question, ensure_ascii=False)}\n"
            f"created_at: {now}\n"
            f"---\n\n"
        )
        content = fm + content

    concepts_dir = os.path.join(output_dir, "concepts")
    os.makedirs(concepts_dir, exist_ok=True)
    abs_path = os.path.join(concepts_dir, slug + ".md")

    with open(abs_path, "w") as f:
        f.write(content)

    # Index for search
    mem_store.add(Entry(
        id=f"concept:{slug}",
        content=content,
        tags=["query-derived"],
        article_path=abs_path,
    ))
    if embedder:
        vec = embedder.embed(content)
        vec_store.upsert(f"concept:{slug}", vec)

    return abs_path


def _parse_json(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        json_lines = []
        in_block = False
        for line in lines:
            if line.startswith("```"):
                in_block = not in_block
                continue
            if in_block:
                json_lines.append(line)
        text = "\n".join(json_lines)
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        text = text[start:end + 1]
    try:
        return json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return {}

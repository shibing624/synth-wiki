# -*- coding: utf-8 -*-
"""
@author:XuMing(xuming624@qq.com)
@description: Pass 3: Write encyclopedia articles for extracted concepts.
"""
from __future__ import annotations
import json
import os
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

import httpx

from synth_wiki.compiler.concepts import ExtractedConcept
from synth_wiki.compiler.progress import phase_bar
from synth_wiki.llm.client import Client, Message, CallOpts
from synth_wiki.memory import Store as MemoryStore, Entry
from synth_wiki.ontology import Store as OntologyStore, Entity, Relation
from synth_wiki.ontology import TYPE_CONCEPT, TYPE_TECHNIQUE, TYPE_CLAIM, TYPE_ENTITY, TYPE_COMPARISON, TYPE_SOURCE, REL_CITES
from synth_wiki.ontology import REL_IMPLEMENTS, REL_EXTENDS, REL_OPTIMIZES, REL_CONTRADICTS, REL_PREREQUISITE_OF, REL_TRADES_OFF


# Map concept type -> output subdirectory
_TYPE_TO_SUBDIR = {
    "entity": "entities",
    "comparison": "comparisons",
}
_DEFAULT_SUBDIR = "concepts"
from synth_wiki.vectors import Store as VectorStore


@dataclass
class ArticleResult:
    concept_name: str
    article_path: str = ""
    error: Optional[Exception] = None


def write_articles(output_dir: str, concepts: list[ExtractedConcept],
                   client: Client, model: str, max_tokens: int, max_parallel: int,
                   mem_store: MemoryStore, vec_store: VectorStore,
                   ont_store: OntologyStore, embedder=None,
                   language: str = "zh-CN") -> list[ArticleResult]:
    results = [None] * len(concepts)
    bar = phase_bar("Pass 3: Write articles", len(concepts), unit="article")
    with ThreadPoolExecutor(max_workers=max_parallel) as pool:
        futures = {}
        for i, c in enumerate(concepts):
            f = pool.submit(write_one_article, output_dir, c, client, model,
                            max_tokens, mem_store, vec_store, ont_store, embedder, language)
            futures[f] = i
        for f in as_completed(futures):
            results[futures[f]] = f.result()
            bar.update(1)
    bar.close()
    return results


def write_one_article(output_dir: str, concept: ExtractedConcept,
                      client: Client, model: str, max_tokens: int,
                      mem_store: MemoryStore, vec_store: VectorStore,
                      ont_store: OntologyStore, embedder=None,
                      language: str = "zh-CN") -> ArticleResult:
    result = ArticleResult(concept_name=concept.name)
    try:
        subdir = _TYPE_TO_SUBDIR.get(concept.type, _DEFAULT_SUBDIR)
        abs_path = os.path.join(output_dir, subdir, concept.name + ".md")
        existing = ""
        if os.path.exists(abs_path):
            with open(abs_path) as f:
                existing = f.read()

        prompt = _build_article_prompt(concept, existing, language)
        resp = client.chat_completion([
            Message(role="system", content=f"You are a wiki author. Use YAML frontmatter and [[wikilinks]]. Write ALL content in {language}."),
            Message(role="user", content=prompt),
        ], CallOpts(model=model, max_tokens=max_tokens))

        content = resp.content
        if not content.startswith("---"):
            content = _build_frontmatter(concept) + "\n\n" + content
        content = _normalize_confidence(content)

        os.makedirs(os.path.join(output_dir, subdir), exist_ok=True)
        with open(abs_path, "w") as f:
            f.write(content)
        result.article_path = abs_path

        entity_type = TYPE_CONCEPT
        if concept.type == "technique":
            entity_type = TYPE_TECHNIQUE
        elif concept.type == "claim":
            entity_type = TYPE_CLAIM
        elif concept.type == "entity":
            entity_type = TYPE_ENTITY
        elif concept.type == "comparison":
            entity_type = TYPE_COMPARISON
        ont_store.add_entity(Entity(id=concept.name, type=entity_type, name=_format_name(concept.name), article_path=abs_path))

        for src in concept.sources:
            ont_store.add_entity(Entity(id=src, type=TYPE_SOURCE, name=os.path.basename(src)))
            ont_store.add_relation(Relation(id=f"{concept.name}-cites-{_sanitize(src)}", source_id=concept.name, target_id=src, relation=REL_CITES))

        _extract_relations(concept.name, content, ont_store)

        mem_store.add(Entry(id=f"concept:{concept.name}", content=content, tags=[entity_type] + concept.aliases, article_path=abs_path))

        if embedder:
            vec = embedder.embed(content)
            vec_store.upsert(f"concept:{concept.name}", vec)

    except (httpx.HTTPError, RuntimeError, IOError, json.JSONDecodeError) as e:
        result.error = e
    return result


def _build_article_prompt(concept: ExtractedConcept, existing: str, language: str = "zh-CN") -> str:
    parts = [f"Write a comprehensive wiki article about: {_format_name(concept.name)}"]
    parts.append(f"Concept ID: {concept.name}")
    parts.append(f"Article type: {concept.type}")
    if concept.aliases:
        parts.append(f"Aliases: {', '.join(concept.aliases)}")
    parts.append(f"Sources: {', '.join(concept.sources)}")
    if existing:
        parts.append(f"\nExisting article (update/expand):\n{existing}")
    parts.append(f"\nIMPORTANT: Write the entire article in {language}.")
    parts.append("Use YAML frontmatter with concept, aliases, sources, confidence (high/medium/low).")
    parts.append("IMPORTANT: All [[wikilinks]] MUST use lowercase-hyphenated slug format, e.g. [[machine-learning]], [[natural-language-processing]], [[deep-learning]]. NEVER use display names like [[机器学习]] or [[Machine Learning]].")
    if concept.type == "entity":
        parts.append("Include sections: Overview, Key Facts, Relationships, Timeline, See also with [[wikilinks]].")
    elif concept.type == "comparison":
        parts.append("Include sections: Overview, Comparison Table (markdown table), Analysis, Verdict, See also with [[wikilinks]].")
    else:
        parts.append("Include sections: Definition, How it works, Variants, Trade-offs, See also with [[wikilinks]].")
    return "\n".join(parts)


def _build_frontmatter(concept: ExtractedConcept) -> str:
    aliases = json.dumps(concept.aliases, ensure_ascii=False) if concept.aliases else "[]"
    sources = json.dumps(concept.sources, ensure_ascii=False) if concept.sources else "[]"
    return f"---\nconcept: {concept.name}\naliases: {aliases}\nsources: {sources}\nconfidence: medium\ncreated_at: {datetime.now(timezone.utc).isoformat()}\n---"


def _format_name(name: str) -> str:
    return " ".join(w.capitalize() for w in name.split("-"))


def _sanitize(s: str) -> str:
    return s.replace("/", "-").replace("\\", "-").replace(".", "-").replace(" ", "-")


def _normalize_confidence(content: str) -> str:
    lines = content.split("\n")
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("confidence:"):
            value = stripped.split(":", 1)[1].strip().lower()
            mapped = _map_confidence(value)
            lines[i] = f"confidence: {mapped}"
            break
    return "\n".join(lines)


def _map_confidence(value: str) -> str:
    if value in ("high", "5", "5/5", "100%", "certain", "very high"):
        return "high"
    if value in ("low", "1", "2", "1/5", "2/5", "uncertain", "speculative"):
        return "low"
    return "medium"


def _extract_relations(concept_id: str, content: str, ont_store: OntologyStore) -> None:
    # TODO: Replace keyword matching with LLM-based relation extraction in the article
    # writing prompt for higher accuracy. Current approach produces false positives.
    link_re = re.compile(r'\[\[([^\]]+)\]\]')
    links = {m.group(1) for m in link_re.finditer(content) if m.group(1) != concept_id}
    content_lower = content.lower()
    patterns = [
        (["implements", "implementation of"], REL_IMPLEMENTS),
        (["extends", "extension of", "builds on"], REL_EXTENDS),
        (["optimizes", "optimization of", "improves upon"], REL_OPTIMIZES),
        (["contradicts", "conflicts with"], REL_CONTRADICTS),
        (["prerequisite", "requires knowledge of"], REL_PREREQUISITE_OF),
        (["trade-off", "tradeoff", "trades off"], REL_TRADES_OFF),
    ]
    for target in links:
        # Skip if target entity does not exist yet (parallel writes or dangling wikilinks)
        if ont_store.get_entity(target) is None:
            continue
        target_lower = target.lower()
        for keywords, rel_type in patterns:
            for kw in keywords:
                if kw in content_lower and target_lower in content_lower:
                    ont_store.add_relation(Relation(id=f"{concept_id}-{rel_type}-{target}", source_id=concept_id, target_id=target, relation=rel_type))
                    break

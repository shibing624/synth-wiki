# -*- coding: utf-8 -*-
"""
@author:XuMing(xuming624@qq.com)
@description: Pass 4: Synthesize cross-source insights.

Groups summaries by topic clusters and generates synthesis pages that
cross-reference multiple sources, identifying patterns, contradictions,
and emergent insights that individual concept pages miss.
"""
from __future__ import annotations
import json
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

import httpx

from synth_wiki.compiler.concepts import ExtractedConcept
from synth_wiki.compiler.progress import phase_bar
from synth_wiki.compiler.summarize import SummaryResult
from synth_wiki.llm.client import Client, Message, CallOpts
from synth_wiki.memory import Store as MemoryStore, Entry
from synth_wiki.vectors import Store as VectorStore


@dataclass
class SynthesisResult:
    title: str
    slug: str
    path: str = ""
    source_count: int = 0
    error: Optional[Exception] = None


def generate_syntheses(
    output_dir: str,
    summaries: list[SummaryResult],
    concepts: list[ExtractedConcept],
    client: Client,
    model: str,
    max_tokens: int,
    max_parallel: int,
    mem_store: MemoryStore,
    vec_store: VectorStore,
    embedder=None,
    language: str = "zh-CN",
    min_cluster_size: int = 3,
) -> list[SynthesisResult]:
    """Generate synthesis pages from cross-source topic clusters.

    1. Cluster summaries by shared concepts
    2. For each cluster with >= min_cluster_size sources, generate a synthesis
    3. Write to wiki/syntheses/ directory
    """
    valid = [s for s in summaries if s.error is None and s.summary]
    if len(valid) < min_cluster_size:
        return []

    clusters = _cluster_by_concepts(valid, concepts, min_cluster_size)
    if not clusters:
        return []

    synth_dir = os.path.join(output_dir, "syntheses")
    os.makedirs(synth_dir, exist_ok=True)

    results = [None] * len(clusters)
    bar = phase_bar("Pass 4: Synthesize", len(clusters), unit="synthesis")
    with ThreadPoolExecutor(max_workers=max_parallel) as pool:
        futures = {}
        for i, cluster in enumerate(clusters):
            f = pool.submit(
                _write_one_synthesis, output_dir, cluster, client, model,
                max_tokens, mem_store, vec_store, embedder, language,
            )
            futures[f] = i
        for f in as_completed(futures):
            results[futures[f]] = f.result()
            bar.update(1)
    bar.close()
    return results


@dataclass
class _Cluster:
    theme: str
    slug: str
    summaries: list[SummaryResult]
    shared_concepts: list[str]


def _cluster_by_concepts(
    summaries: list[SummaryResult],
    concepts: list[ExtractedConcept],
    min_size: int,
) -> list[_Cluster]:
    """Group summaries that share concepts into thematic clusters."""
    # Build source -> concepts mapping
    source_concepts: dict[str, set[str]] = {}
    for c in concepts:
        for src in c.sources:
            source_concepts.setdefault(src, set()).add(c.name)

    # Build concept -> sources mapping
    concept_sources: dict[str, set[str]] = {}
    for c in concepts:
        concept_sources[c.name] = set(c.sources)

    # Find concept groups that co-occur across multiple sources
    # Use concepts that appear in >= min_size sources as cluster seeds
    seed_concepts = [
        c for c in concepts
        if len(c.sources) >= min_size
    ]

    if not seed_concepts:
        # Fallback: try to find overlapping source groups
        return _cluster_by_overlap(summaries, source_concepts, min_size)

    # Group by most-connected concept
    summary_map = {s.source_path: s for s in summaries}
    used_sources = set()
    clusters = []

    for seed in sorted(seed_concepts, key=lambda c: len(c.sources), reverse=True):
        cluster_sources = [
            s for s in seed.sources
            if s in summary_map and s not in used_sources
        ]
        if len(cluster_sources) < min_size:
            continue

        # Collect all shared concepts for this cluster
        shared = set()
        for src in cluster_sources:
            shared.update(source_concepts.get(src, set()))

        cluster_summaries = [summary_map[s] for s in cluster_sources]
        theme = _format_theme(seed.name)
        slug = seed.name + "-synthesis"

        clusters.append(_Cluster(
            theme=theme,
            slug=slug,
            summaries=cluster_summaries,
            shared_concepts=sorted(shared),
        ))
        used_sources.update(cluster_sources)

    return clusters


def _cluster_by_overlap(
    summaries: list[SummaryResult],
    source_concepts: dict[str, set[str]],
    min_size: int,
) -> list[_Cluster]:
    """Fallback clustering: group sources with overlapping concept sets."""
    if len(summaries) < min_size:
        return []

    # Single cluster: all sources together as a general synthesis
    shared = set()
    for src_path in source_concepts:
        shared.update(source_concepts[src_path])

    if not shared:
        return []

    # Pick the most common concept as the theme
    concept_freq: dict[str, int] = {}
    for concepts_set in source_concepts.values():
        for c in concepts_set:
            concept_freq[c] = concept_freq.get(c, 0) + 1

    top_concept = max(concept_freq, key=concept_freq.get)
    theme = _format_theme(top_concept)

    return [_Cluster(
        theme=theme,
        slug="general-synthesis",
        summaries=summaries,
        shared_concepts=sorted(shared),
    )]


def _write_one_synthesis(
    output_dir: str,
    cluster: _Cluster,
    client: Client,
    model: str,
    max_tokens: int,
    mem_store: MemoryStore,
    vec_store: VectorStore,
    embedder=None,
    language: str = "zh-CN",
) -> SynthesisResult:
    result = SynthesisResult(
        title=cluster.theme,
        slug=cluster.slug,
        source_count=len(cluster.summaries),
    )
    try:
        synth_dir = os.path.join(output_dir, "syntheses")
        abs_path = os.path.join(synth_dir, cluster.slug + ".md")

        existing = ""
        if os.path.exists(abs_path):
            with open(abs_path) as f:
                existing = f.read()

        prompt = _build_synthesis_prompt(cluster, existing, language)
        resp = client.chat_completion([
            Message(role="system", content=(
                f"You are a knowledge synthesis expert. Your job is to analyze "
                f"multiple sources about related topics and produce a cross-cutting "
                f"synthesis that reveals patterns, contradictions, and insights "
                f"that individual articles miss. Use [[wikilinks]] in slug format. "
                f"Write ALL content in {language}."
            )),
            Message(role="user", content=prompt),
        ], CallOpts(model=model, max_tokens=max_tokens))

        content = resp.content
        if not content.startswith("---"):
            content = _build_frontmatter(cluster) + "\n\n" + content

        os.makedirs(synth_dir, exist_ok=True)
        with open(abs_path, "w") as f:
            f.write(content)
        result.path = abs_path

        # Index for search
        mem_store.add(Entry(
            id=f"synthesis:{cluster.slug}",
            content=content,
            tags=["synthesis"] + cluster.shared_concepts[:5],
            article_path=abs_path,
        ))
        if embedder:
            vec = embedder.embed(content)
            vec_store.upsert(f"synthesis:{cluster.slug}", vec)

    except (httpx.HTTPError, RuntimeError, IOError, json.JSONDecodeError) as e:
        result.error = e
    return result


def _build_synthesis_prompt(cluster: _Cluster, existing: str, language: str) -> str:
    parts = [
        f"Generate a cross-source synthesis about: {cluster.theme}",
        f"This synthesis covers {len(cluster.summaries)} sources.",
        f"\nShared concepts across these sources: {', '.join(cluster.shared_concepts[:20])}",
        "\n--- Source Summaries ---",
    ]
    for s in cluster.summaries:
        # Truncate each summary to fit context
        text = s.summary[:800] if len(s.summary) > 800 else s.summary
        parts.append(f"\n### Source: {os.path.basename(s.source_path)}\n{text}")

    if existing:
        parts.append(f"\n--- Existing synthesis (update/expand) ---\n{existing[:1000]}")

    parts.append(f"\nIMPORTANT: Write the entire synthesis in {language}.")
    parts.append("Use YAML frontmatter with: title, type: synthesis, sources (list), concepts (list), created_at.")
    parts.append("IMPORTANT: All [[wikilinks]] MUST use lowercase-hyphenated slug format.")
    parts.append(
        "Structure the synthesis with these sections:\n"
        "1. Overview - What these sources collectively tell us\n"
        "2. Key Patterns - Common themes and agreements\n"
        "3. Contradictions & Tensions - Where sources disagree\n"
        "4. Emergent Insights - What becomes clear only when reading all sources together\n"
        "5. Open Questions - What remains unresolved\n"
        "6. See Also - [[wikilinks]] to related concept pages"
    )
    return "\n".join(parts)


def _build_frontmatter(cluster: _Cluster) -> str:
    sources = json.dumps(
        [os.path.basename(s.source_path) for s in cluster.summaries],
        ensure_ascii=False,
    )
    concepts = json.dumps(cluster.shared_concepts[:10], ensure_ascii=False)
    now = datetime.now(timezone.utc).isoformat()
    return (
        f"---\n"
        f"title: {cluster.theme}\n"
        f"type: synthesis\n"
        f"sources: {sources}\n"
        f"concepts: {concepts}\n"
        f"created_at: {now}\n"
        f"---"
    )


def _format_theme(name: str) -> str:
    return " ".join(w.capitalize() for w in name.split("-"))

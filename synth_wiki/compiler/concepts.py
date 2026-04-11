# -*- coding: utf-8 -*-
"""
@author:XuMing(xuming624@qq.com)
@description: Pass 2: Extract concepts from summaries via LLM. | Extracts knowledge concepts from source summaries.
"""
from __future__ import annotations
import json
from dataclasses import dataclass, field

from synth_wiki.compiler.progress import phase_bar
from synth_wiki.compiler.summarize import SummaryResult
from synth_wiki.llm.client import Client, Message, CallOpts

CONCEPT_BATCH_SIZE = 20


@dataclass
class ExtractedConcept:
    name: str
    aliases: list[str] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)
    type: str = "concept"


def extract_concepts(summaries: list[SummaryResult], existing_concepts: dict,
                     client: Client, model: str,
                     language: str = "zh-CN") -> list[ExtractedConcept]:
    valid = [s for s in summaries if s.error is None and s.summary]
    if not valid:
        return []

    existing_list = list(existing_concepts.keys())
    all_concepts: list[ExtractedConcept] = []
    num_batches = (len(valid) + CONCEPT_BATCH_SIZE - 1) // CONCEPT_BATCH_SIZE
    bar = phase_bar("Pass 2: Extract concepts", num_batches, unit="batch")

    for i in range(0, len(valid), CONCEPT_BATCH_SIZE):
        batch = valid[i:i + CONCEPT_BATCH_SIZE]
        summary_texts = []
        for s in batch:
            text = s.summary[:1000] + "\n..." if len(s.summary) > 1000 else s.summary
            summary_texts.append(f"### Source: {s.source_path}\n{text}")

        dedup = list(existing_list) + [c.name for c in all_concepts]
        prompt = f"""Extract concepts from these summaries.
Existing concepts (avoid duplicates): {', '.join(dedup)}

Summaries:
{chr(10).join(summary_texts)}

For each concept: name (lowercase-hyphenated), aliases (in {language}), sources (file paths), type (concept/technique/claim).
Output ONLY a JSON array."""

        try:
            resp = client.chat_completion([
                Message(role="system", content=f"You are a concept extraction system. Output valid JSON only. Concept names and aliases MUST be in {language}."),
                Message(role="user", content=prompt),
            ], CallOpts(model=model, max_tokens=8192))
            concepts = parse_concepts_json(resp.content)
            all_concepts.extend(concepts)
        except Exception:
            continue
        finally:
            bar.update(1)

    bar.close()
    all_concepts = filter_noisy_concepts(all_concepts)
    all_concepts = deduplicate_concepts(all_concepts)
    return all_concepts


def parse_concepts_json(text: str) -> list[ExtractedConcept]:
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
    start = text.find("[")
    end = text.rfind("]")
    if start >= 0 and end > start:
        text = text[start:end + 1]
    data = json.loads(text)
    return [ExtractedConcept(name=c.get("name", ""), aliases=c.get("aliases", []),
                             sources=c.get("sources", []), type=c.get("type", "concept"))
            for c in data]


def filter_noisy_concepts(concepts: list[ExtractedConcept]) -> list[ExtractedConcept]:
    result = []
    for c in concepts:
        if len(c.name) < 2:
            continue
        if "$" in c.name or "\\" in c.name:
            continue
        if "/" in c.name or ".md" in c.name:
            continue
        if c.name.isdigit():
            continue
        result.append(c)
    return result


def deduplicate_concepts(concepts: list[ExtractedConcept]) -> list[ExtractedConcept]:
    seen: dict[str, ExtractedConcept] = {}
    for c in concepts:
        if c.name in seen:
            existing = seen[c.name]
            for s in c.sources:
                if s not in existing.sources:
                    existing.sources.append(s)
            for a in c.aliases:
                if a not in existing.aliases:
                    existing.aliases.append(a)
        else:
            seen[c.name] = ExtractedConcept(name=c.name, aliases=list(c.aliases), sources=list(c.sources), type=c.type)
    return list(seen.values())

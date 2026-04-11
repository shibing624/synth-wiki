# -*- coding: utf-8 -*-
"""
@author:XuMing(xuming624@qq.com)
@description: Hybrid search: TreeSearch auto mode + optional vector reranking.
"""
from __future__ import annotations
import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from synth_wiki.memory import Store as MemoryStore
from synth_wiki.vectors import Store as VectorStore

RRF_K = 60  # Standard RRF constant (Cormack et al. 2009)


@dataclass
class SearchOpts:
    query: str = ""
    tags: list[str] = field(default_factory=list)
    boost_tags: list[str] = field(default_factory=list)
    limit: int = 10
    timestamps: dict[str, datetime] = field(default_factory=dict)


@dataclass
class SearchResult:
    id: str
    content: str
    tags: list[str]
    article_path: str
    fts_rank: int = 0
    vector_rank: int = 0
    score: float = 0.0


class Searcher:
    def __init__(self, memory: MemoryStore, vectors: VectorStore):
        self._memory = memory
        self._vectors = vectors

    def search(self, opts: SearchOpts, query_vec: list[float] | None = None) -> list[SearchResult]:
        limit = opts.limit if opts.limit > 0 else 10
        candidate_limit = limit * 3

        # TreeSearch auto mode (tree walk + FTS5 scoring)
        fts_results = self._memory.search(opts.query, opts.tags or None, candidate_limit)

        # Vector search
        vec_results = []
        if query_vec is not None:
            vec_results = self._vectors.search(query_vec, candidate_limit)

        # Build fusion entries
        scores: dict[str, dict] = {}
        for r in fts_results:
            scores[r.id] = {
                "content": r.content,
                "tags": r.tags,
                "article_path": r.article_path,
                "fts_rank": r.rank,
                "vector_rank": 0,
            }

        for r in vec_results:
            if r.id not in scores:
                entry = self._memory.get(r.id)
                if not entry:
                    continue
                scores[r.id] = {
                    "content": entry.content,
                    "tags": entry.tags,
                    "article_path": entry.article_path,
                    "fts_rank": 0,
                    "vector_rank": 0,
                }
            scores[r.id]["vector_rank"] = r.rank

        # Calculate RRF scores
        results = []
        for id, entry in scores.items():
            score = 0.0
            if entry["fts_rank"] > 0:
                score += 1.0 / (RRF_K + entry["fts_rank"])
            if entry["vector_rank"] > 0:
                score += 1.0 / (RRF_K + entry["vector_rank"])

            # Tag boost: +3% per matching boost tag, cap 15%
            score += _tag_boost(entry["tags"], opts.boost_tags)

            # Recency boost: 14-day half-life, max +5%
            if id in opts.timestamps:
                score += _recency_boost(opts.timestamps[id])

            results.append(SearchResult(
                id=id, content=entry["content"], tags=entry["tags"],
                article_path=entry["article_path"],
                fts_rank=entry["fts_rank"], vector_rank=entry["vector_rank"],
                score=score,
            ))

        results.sort(key=lambda r: r.score, reverse=True)
        return results[:limit]


def _tag_boost(entry_tags: list[str], boost_tags: list[str]) -> float:
    if not boost_tags:
        return 0.0
    matches = sum(1 for bt in boost_tags if any(bt.lower() == et.lower() for et in entry_tags))
    return min(matches * 0.03, 0.15)


def _recency_boost(updated_at: datetime) -> float:
    age_days = (datetime.now(timezone.utc) - updated_at).total_seconds() / 86400
    if age_days < 0:
        age_days = 0
    return 0.05 * (2 ** (-age_days / 14.0))

# -*- coding: utf-8 -*-
"""
@author:XuMing(xuming624@qq.com)
@description: Entry store powered by TreeSearch auto mode.

Uses TreeSearcher (tree walk + FTS5) for search instead of raw FTS5Index,
which gives structure-aware Best-First Search with auto flat/tree routing.
"""
from __future__ import annotations
import hashlib
import json
import sqlite3
import threading
from dataclasses import dataclass, field
from typing import Optional

from treesearch.fts import FTS5Index
from treesearch.tree import Document
from treesearch.tree_searcher import TreeSearcher


@dataclass
class Entry:
    id: str
    content: str
    tags: list[str] = field(default_factory=list)
    article_path: str = ""


@dataclass
class SearchResult:
    id: str
    content: str
    tags: list[str]
    article_path: str
    score: float = 0.0
    rank: int = 0


class Store:
    def __init__(self, db_path: str):
        self._db_path = db_path
        self._lock = threading.Lock()
        self._fts = FTS5Index(db_path=db_path)
        # Enable cross-thread usage for ThreadPoolExecutor in write_articles
        if self._fts._conn is not None:
            self._fts._conn.close()
            self._fts._conn = sqlite3.connect(db_path, check_same_thread=False)
            self._fts._conn.execute("PRAGMA journal_mode=WAL")
            self._fts._conn.execute("PRAGMA synchronous=NORMAL")
        self._searcher = TreeSearcher(fts_index=self._fts)

    def add(self, entry: Entry) -> None:
        doc = _entry_to_document(entry)
        with self._lock:
            self._fts.index_document(doc)

    def update(self, entry: Entry) -> None:
        with self._lock:
            self._fts.delete_document(entry.id)
            doc = _entry_to_document(entry)
            self._fts.index_document(doc)

    def delete(self, id: str) -> None:
        with self._lock:
            self._fts.delete_document(id)

    def get(self, id: str) -> Optional[Entry]:
        with self._lock:
            doc = self._fts.load_document(id)
        if doc is None:
            return None
        return _document_to_entry(doc)

    def search(self, query: str, tags: list[str] | None = None, limit: int = 10) -> list[SearchResult]:
        if not query or not query.strip():
            return []
        with self._lock:
            # Load all indexed documents for TreeSearcher
            docs = self._fts.load_all_documents()
            if not docs:
                return []
            # TreeSearcher auto mode: tree walk with FTS5 scoring
            paths, flat_nodes = self._searcher.search(query, docs)
            results = []
            seen = set()
            for node in flat_nodes:
                doc_id = node.get("doc_id", "")
                if not doc_id or doc_id in seen:
                    continue
                seen.add(doc_id)
                doc = self._fts.load_document(doc_id)
                if doc is None:
                    continue
                entry = _document_to_entry(doc)
                if tags and not any(t in entry.tags for t in tags):
                    continue
                results.append(SearchResult(
                    id=entry.id,
                    content=entry.content,
                    tags=entry.tags,
                    article_path=entry.article_path,
                    score=node.get("score", node.get("fts_score", 0.0)),
                    rank=len(results) + 1,
                ))
                if len(results) >= limit:
                    break
        return results

    def count(self) -> int:
        with self._lock:
            stats = self._fts.get_stats()
        return stats.get("document_count", 0)

    def close(self) -> None:
        with self._lock:
            self._fts.close()


def content_hash(content: str) -> str:
    return hashlib.sha256(content.encode()).hexdigest()


def _entry_to_document(entry: Entry) -> Document:
    """Convert an Entry to a TreeSearch Document for indexing."""
    desc = json.dumps({"tags": entry.tags, "article_path": entry.article_path}, ensure_ascii=False)
    return Document(
        doc_id=entry.id,
        doc_name=entry.id,
        structure=[{
            "node_id": "0",
            "title": entry.article_path,
            "text": entry.content,
            "summary": "",
            "prefix_summary": "",
            "line_start": 0,
            "line_end": 0,
            "nodes": [],
        }],
        doc_description=desc,
        metadata={},
        source_type="entry",
    )


def _document_to_entry(doc: Document) -> Entry:
    """Convert a TreeSearch Document back to an Entry."""
    content = ""
    article_path = ""
    if doc.structure:
        node = doc.structure[0]
        content = node.get("text", "")
        article_path = node.get("title", "")
    tags = []
    if doc.doc_description:
        try:
            meta = json.loads(doc.doc_description)
            tags = meta.get("tags", [])
            article_path = meta.get("article_path", article_path)
        except (json.JSONDecodeError, TypeError):
            pass
    return Entry(id=doc.doc_id, content=content, tags=tags, article_path=article_path)

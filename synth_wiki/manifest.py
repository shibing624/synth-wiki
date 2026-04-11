# -*- coding: utf-8 -*-
"""
@author:XuMing(xuming624@qq.com)
@description: 
"""
from __future__ import annotations
import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class Source:
    hash: str = ""
    type: str = ""
    size_bytes: int = 0
    added_at: str = ""
    compiled_at: str = ""
    summary_path: str = ""
    concepts_produced: list[str] = field(default_factory=list)
    chunk_count: int = 0
    status: str = "pending"  # pending, compiled, error


@dataclass
class Concept:
    article_path: str = ""
    sources: list[str] = field(default_factory=list)
    last_compiled: str = ""


@dataclass
class Manifest:
    version: int = 2
    sources: dict[str, Source] = field(default_factory=dict)
    concepts: dict[str, Concept] = field(default_factory=dict)
    embed_model: str = ""
    embed_dim: int = 0

    @classmethod
    def new(cls) -> Manifest:
        return cls()

    def add_source(self, path: str, hash: str, typ: str, size: int) -> None:
        self.sources[path] = Source(
            hash=hash, type=typ, size_bytes=size,
            added_at=_now(), status="pending",
        )

    def mark_compiled(self, path: str, summary_path: str, concepts: list[str] | None = None) -> None:
        if path in self.sources:
            src = self.sources[path]
            src.compiled_at = _now()
            src.summary_path = summary_path
            src.concepts_produced = concepts or []
            src.status = "compiled"

    def remove_source(self, path: str) -> None:
        self.sources.pop(path, None)

    def add_concept(self, name: str, article_path: str, sources: list[str]) -> None:
        self.concepts[name] = Concept(
            article_path=article_path, sources=sources, last_compiled=_now(),
        )

    def pending_sources(self) -> dict[str, Source]:
        return {p: s for p, s in self.sources.items() if s.status == "pending"}

    @property
    def source_count(self) -> int:
        return len(self.sources)

    @property
    def concept_count(self) -> int:
        return len(self.concepts)

    def save(self, path: str) -> None:
        data = {
            "version": self.version,
            "sources": {k: _source_to_dict(v) for k, v in self.sources.items()},
            "concepts": {k: _concept_to_dict(v) for k, v in self.concepts.items()},
        }
        if self.embed_model:
            data["embed_model"] = self.embed_model
        if self.embed_dim:
            data["embed_dim"] = self.embed_dim
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
            f.write("\n")


def load(path: str) -> Manifest:
    if not os.path.exists(path):
        return Manifest.new()
    with open(path) as f:
        data = json.load(f)
    m = Manifest(version=data.get("version", 2))
    m.embed_model = data.get("embed_model", "")
    m.embed_dim = data.get("embed_dim", 0)
    for k, v in data.get("sources", {}).items():
        m.sources[k] = Source(
            hash=v.get("hash", ""), type=v.get("type", ""),
            size_bytes=v.get("size_bytes", 0), added_at=v.get("added_at", ""),
            compiled_at=v.get("compiled_at", ""), summary_path=v.get("summary_path", ""),
            concepts_produced=v.get("concepts_produced", []),
            chunk_count=v.get("chunk_count", 0), status=v.get("status", "pending"),
        )
    for k, v in data.get("concepts", {}).items():
        m.concepts[k] = Concept(
            article_path=v.get("article_path", ""),
            sources=v.get("sources", []),
            last_compiled=v.get("last_compiled", ""),
        )
    return m


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()

def _source_to_dict(s: Source) -> dict:
    return {"hash": s.hash, "type": s.type, "size_bytes": s.size_bytes,
            "added_at": s.added_at, "compiled_at": s.compiled_at,
            "summary_path": s.summary_path, "concepts_produced": s.concepts_produced,
            "chunk_count": s.chunk_count, "status": s.status}

def _concept_to_dict(c: Concept) -> dict:
    return {"article_path": c.article_path, "sources": c.sources, "last_compiled": c.last_compiled}

# -*- coding: utf-8 -*-
"""
@author:XuMing(xuming624@qq.com)
@description: Vector embedding store with cosine similarity search. | Vector embeddings storage and cosine similarity search.
"""
from __future__ import annotations
import math
import struct
from dataclasses import dataclass

from synth_wiki.storage import DB


@dataclass
class VectorResult:
    id: str
    score: float
    rank: int = 0


class Store:
    def __init__(self, db: DB):
        self._db = db

    def upsert(self, id: str, embedding: list[float]) -> None:
        blob = encode_float32s(embedding)
        def _upsert(cursor):
            cursor.execute(
                """INSERT INTO vec_entries (id, embedding, dimensions) VALUES (?, ?, ?)
                   ON CONFLICT(id) DO UPDATE SET embedding=excluded.embedding, dimensions=excluded.dimensions""",
                (id, blob, len(embedding)),
            )
        self._db.write_tx(_upsert)

    def delete(self, id: str) -> None:
        def _delete(cursor):
            cursor.execute("DELETE FROM vec_entries WHERE id=?", (id,))
        self._db.write_tx(_delete)

    def search(self, query: list[float], limit: int = 10) -> list[VectorResult]:
        # TODO: This is brute-force linear scan O(n). Replace with FAISS or sqlite-vec
        # for datasets larger than ~10k vectors.
        cursor = self._db.read_db.cursor()
        cursor.execute("SELECT id, embedding, dimensions FROM vec_entries")

        results: list[VectorResult] = []
        for row in cursor.fetchall():
            vec = decode_float32s(row[1])
            if len(vec) != len(query):
                continue
            score = cosine_similarity(query, vec)
            results = _insert_sorted(results, VectorResult(id=row[0], score=score), limit)

        for i in range(len(results)):
            results[i].rank = i + 1
        return results

    def count(self) -> int:
        cursor = self._db.read_db.cursor()
        cursor.execute("SELECT COUNT(*) FROM vec_entries")
        return cursor.fetchone()[0]

    def dimensions(self) -> int:
        cursor = self._db.read_db.cursor()
        cursor.execute("SELECT COALESCE(MAX(dimensions), 0) FROM vec_entries")
        return cursor.fetchone()[0]


def cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(ai * bi for ai, bi in zip(a, b))
    norm_a = math.sqrt(sum(ai * ai for ai in a))
    norm_b = math.sqrt(sum(bi * bi for bi in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def encode_float32s(v: list[float]) -> bytes:
    return struct.pack(f"<{len(v)}f", *v)


def decode_float32s(buf: bytes) -> list[float]:
    count = len(buf) // 4
    return list(struct.unpack(f"<{count}f", buf))


def _insert_sorted(results: list[VectorResult], item: VectorResult, limit: int) -> list[VectorResult]:
    pos = len(results)
    while pos > 0 and results[pos - 1].score < item.score:
        pos -= 1
    if pos >= limit:
        return results
    results.insert(pos, item)
    if len(results) > limit:
        results.pop()
    return results

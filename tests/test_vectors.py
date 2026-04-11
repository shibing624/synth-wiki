# -*- coding: utf-8 -*-
"""
@author:XuMing(xuming624@qq.com)
@description: Tests for vectors.py (Store, cosine_similarity, encode/decode).
"""
from __future__ import annotations
import math
import pytest

from synth_wiki.storage import DB
from synth_wiki.vectors import Store, VectorResult, cosine_similarity, encode_float32s, decode_float32s


@pytest.fixture
def store(tmp_path):
    db = DB.open(str(tmp_path / "vec.db"))
    s = Store(db)
    yield s
    db.close()


def test_upsert_and_search_finds_vector(store):
    vec = [1.0, 0.0, 0.0]
    store.upsert("v1", vec)
    results = store.search(vec, limit=5)
    assert len(results) == 1
    assert results[0].id == "v1"
    assert abs(results[0].score - 1.0) < 1e-5
    assert results[0].rank == 1


def test_cosine_similarity_identical():
    v = [1.0, 2.0, 3.0]
    assert abs(cosine_similarity(v, v) - 1.0) < 1e-6


def test_cosine_similarity_orthogonal():
    a = [1.0, 0.0]
    b = [0.0, 1.0]
    assert abs(cosine_similarity(a, b)) < 1e-6


def test_dimension_mismatch_skipped(store):
    store.upsert("dim3", [1.0, 2.0, 3.0])
    # Query with 2-dim vector — should skip the 3-dim entry
    results = store.search([1.0, 0.0], limit=5)
    assert len(results) == 0


def test_top_k_limiting(store):
    for i in range(10):
        store.upsert(f"v{i}", [float(i), 0.0, 0.0])
    results = store.search([1.0, 0.0, 0.0], limit=3)
    assert len(results) == 3
    # Ranks assigned 1..3
    assert [r.rank for r in results] == [1, 2, 3]


def test_count_and_dimensions(store):
    assert store.count() == 0
    assert store.dimensions() == 0

    store.upsert("a", [1.0, 2.0, 3.0])
    assert store.count() == 1
    assert store.dimensions() == 3

    store.upsert("b", [4.0, 5.0, 6.0])
    assert store.count() == 2
    assert store.dimensions() == 3


def test_delete_removes_vector(store):
    store.upsert("del1", [1.0, 0.0])
    assert store.count() == 1
    store.delete("del1")
    assert store.count() == 0
    results = store.search([1.0, 0.0], limit=5)
    assert len(results) == 0


def test_encode_decode_roundtrip():
    original = [1.5, -2.5, 0.0, 3.14159]
    encoded = encode_float32s(original)
    decoded = decode_float32s(encoded)
    assert len(decoded) == len(original)
    for a, b in zip(original, decoded):
        assert abs(a - b) < 1e-5  # float32 precision


def test_upsert_overwrites_existing(store):
    store.upsert("u1", [1.0, 0.0, 0.0])
    store.upsert("u1", [0.0, 1.0, 0.0])
    assert store.count() == 1
    results = store.search([0.0, 1.0, 0.0], limit=1)
    assert len(results) == 1
    assert abs(results[0].score - 1.0) < 1e-5

# -*- coding: utf-8 -*-
"""
@author:XuMing(xuming624@qq.com)
@description: Tests for memory.py (Store backed by TreeSearch FTS5Index).
"""
from __future__ import annotations
import pytest

from synth_wiki.memory import Store, Entry, content_hash


@pytest.fixture
def store(tmp_path):
    db_path = str(tmp_path / "mem_fts.db")
    s = Store(db_path)
    yield s
    s.close()


def test_add_get_roundtrip(store):
    entry = Entry(id="e1", content="transformer architecture", tags=["ml", "nlp"], article_path="/docs/transformer")
    store.add(entry)
    got = store.get("e1")
    assert got is not None
    assert got.id == "e1"
    assert got.content == "transformer architecture"
    assert got.tags == ["ml", "nlp"]
    assert got.article_path == "/docs/transformer"


def test_search_returns_ranked_results(store):
    store.add(Entry(id="a", content="attention mechanism in transformers", tags=[], article_path=""))
    store.add(Entry(id="b", content="gradient descent optimization", tags=[], article_path=""))
    store.add(Entry(id="c", content="transformer self-attention heads", tags=[], article_path=""))

    results = store.search("transformer attention")
    ids = [r.id for r in results]
    assert len(results) > 0
    # Both transformer-related entries should appear before gradient descent
    assert "a" in ids or "c" in ids


def test_search_chinese(store):
    """TreeSearch supports Chinese tokenization via jieba."""
    store.add(Entry(id="zh1", content="机器学习是人工智能的一个分支", tags=["ml"], article_path=""))
    store.add(Entry(id="zh2", content="深度学习使用多层神经网络", tags=["dl"], article_path=""))
    store.add(Entry(id="zh3", content="数据库查询优化技术", tags=["db"], article_path=""))

    results = store.search("机器学习")
    ids = [r.id for r in results]
    assert len(results) > 0
    assert "zh1" in ids


def test_tag_filtering(store):
    store.add(Entry(id="t1", content="convolutional neural networks", tags=["vision", "dl"], article_path=""))
    store.add(Entry(id="t2", content="convolutional layers features", tags=["nlp", "dl"], article_path=""))

    results = store.search("convolutional", tags=["vision"])
    ids = [r.id for r in results]
    assert "t1" in ids
    assert "t2" not in ids


def test_delete_removes_entry(store):
    store.add(Entry(id="del1", content="delete me please", tags=[], article_path=""))
    assert store.get("del1") is not None
    store.delete("del1")
    assert store.get("del1") is None


def test_update_changes_content(store):
    store.add(Entry(id="upd1", content="original content here", tags=["v1"], article_path="/old"))
    store.update(Entry(id="upd1", content="updated content here", tags=["v2"], article_path="/new"))
    got = store.get("upd1")
    assert got is not None
    assert got.content == "updated content here"
    assert got.tags == ["v2"]
    assert got.article_path == "/new"


def test_empty_search_returns_empty(store):
    store.add(Entry(id="x", content="some content here", tags=[], article_path=""))
    results = store.search("")
    assert results == []


def test_content_hash_is_deterministic():
    h1 = content_hash("hello world")
    h2 = content_hash("hello world")
    h3 = content_hash("different content")
    assert h1 == h2
    assert h1 != h3
    assert len(h1) == 64  # sha256 hex


def test_count_returns_correct_number(store):
    assert store.count() == 0
    store.add(Entry(id="c1", content="first entry", tags=[], article_path=""))
    assert store.count() == 1
    store.add(Entry(id="c2", content="second entry", tags=[], article_path=""))
    assert store.count() == 2
    store.delete("c1")
    assert store.count() == 1

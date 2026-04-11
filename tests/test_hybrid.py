# -*- coding: utf-8 -*-
"""
@author:XuMing(xuming624@qq.com)
@description: Tests for hybrid search (TreeSearch FTS5 + vector).
"""
import pytest
from datetime import datetime, timezone, timedelta
from synth_wiki.storage import DB
from synth_wiki.memory import Store as MemoryStore, Entry
from synth_wiki.vectors import Store as VectorStore
from synth_wiki.hybrid import Searcher, SearchOpts, SearchResult, _tag_boost, _recency_boost, RRF_K


@pytest.fixture
def stores(tmp_path):
    db_path = str(tmp_path / "test.db")
    db = DB.open(db_path)
    mem = MemoryStore(db_path)
    vec = VectorStore(db)
    # Add test data
    mem.add(Entry(id="doc1", content="machine learning algorithms neural networks", tags=["ml", "ai"], article_path="wiki/doc1.md"))
    mem.add(Entry(id="doc2", content="database optimization query performance", tags=["db"], article_path="wiki/doc2.md"))
    mem.add(Entry(id="doc3", content="neural network deep learning transformers", tags=["ml", "dl"], article_path="wiki/doc3.md"))
    # Add vectors (simple 3-dim)
    vec.upsert("doc1", [1.0, 0.0, 0.0])
    vec.upsert("doc2", [0.0, 1.0, 0.0])
    vec.upsert("doc3", [0.9, 0.1, 0.0])
    yield db, mem, vec
    mem.close()
    db.close()


class TestHybridSearch:
    def test_fts_only_search(self, stores):
        db, mem, vec = stores
        searcher = Searcher(mem, vec)
        results = searcher.search(SearchOpts(query="machine learning"))
        assert len(results) > 0
        assert results[0].fts_rank > 0

    def test_hybrid_search_combines_signals(self, stores):
        db, mem, vec = stores
        searcher = Searcher(mem, vec)
        results = searcher.search(SearchOpts(query="neural networks"), query_vec=[1.0, 0.0, 0.0])
        assert len(results) > 0

    def test_rrf_scoring_correct(self):
        fts_rank = 1
        vec_rank = 2
        expected = 1.0 / (RRF_K + fts_rank) + 1.0 / (RRF_K + vec_rank)
        assert abs(expected - (1 / 61 + 1 / 62)) < 1e-10

    def test_tag_boost_increases_score(self):
        assert _tag_boost(["ml", "ai"], ["ml"]) == pytest.approx(0.03)
        assert _tag_boost(["ml", "ai"], ["ml", "ai"]) == pytest.approx(0.06)
        assert _tag_boost(["ml"], []) == 0.0

    def test_tag_boost_caps_at_15_percent(self):
        tags = ["a", "b", "c", "d", "e", "f"]
        boost = _tag_boost(tags, tags)
        assert boost == pytest.approx(0.15)

    def test_recency_boost_recent(self):
        now = datetime.now(timezone.utc)
        boost = _recency_boost(now)
        assert 0.04 < boost <= 0.05

    def test_recency_boost_old(self):
        old = datetime.now(timezone.utc) - timedelta(days=28)
        boost = _recency_boost(old)
        assert boost < 0.015

    def test_limit_truncation(self, stores):
        db, mem, vec = stores
        searcher = Searcher(mem, vec)
        results = searcher.search(SearchOpts(query="neural learning machine", limit=1))
        assert len(results) <= 1

    def test_empty_query_returns_empty(self, stores):
        db, mem, vec = stores
        searcher = Searcher(mem, vec)
        results = searcher.search(SearchOpts(query=""))
        assert results == []

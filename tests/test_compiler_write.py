# -*- coding: utf-8 -*-
"""
@author:XuMing(xuming624@qq.com)
@description: Tests for synth_wiki.compiler.write module.
"""
import os
import pytest
from unittest.mock import MagicMock
from synth_wiki.compiler.concepts import ExtractedConcept
from synth_wiki.compiler.write import write_articles, write_one_article, ArticleResult, _normalize_confidence, _format_name
from synth_wiki.llm.client import Response, Usage
from synth_wiki.storage import DB
from synth_wiki.memory import Store as MemoryStore
from synth_wiki.vectors import Store as VectorStore
from synth_wiki.ontology import Store as OntologyStore


@pytest.fixture
def stores(tmp_path):
    db_path = str(tmp_path / "test.db")
    db = DB.open(db_path)
    mem = MemoryStore(db_path)
    vec = VectorStore(db)
    ont = OntologyStore(db)
    yield db, mem, vec, ont
    mem.close()
    db.close()


@pytest.fixture
def mock_client():
    client = MagicMock()
    client.chat_completion.return_value = Response(
        content="---\nconcept: test-concept\nconfidence: high\n---\n\n## Definition\nA test concept.",
        model="test", usage=Usage()
    )
    return client


class TestWriteArticles:
    def test_creates_article_file(self, tmp_path, stores, mock_client):
        db, mem, vec, ont = stores
        output_dir = str(tmp_path / "wiki")
        os.makedirs(os.path.join(output_dir, "concepts"), exist_ok=True)
        concept = ExtractedConcept(name="test-concept", sources=["raw/doc.md"], type="concept")
        results = write_articles(output_dir, [concept], mock_client, "test", 4000, 1, mem, vec, ont)
        assert len(results) == 1
        assert results[0].error is None
        assert os.path.exists(results[0].article_path)

    def test_creates_ontology_entity(self, tmp_path, stores, mock_client):
        db, mem, vec, ont = stores
        output_dir = str(tmp_path / "wiki")
        os.makedirs(os.path.join(output_dir, "concepts"), exist_ok=True)
        concept = ExtractedConcept(name="ont-test", sources=["raw/doc.md"], type="technique")
        write_one_article(output_dir, concept, mock_client, "test", 4000, mem, vec, ont)
        entity = ont.get_entity("ont-test")
        assert entity is not None
        assert entity.type == "technique"

    def test_indexes_in_fts5(self, tmp_path, stores, mock_client):
        db, mem, vec, ont = stores
        output_dir = str(tmp_path / "wiki")
        os.makedirs(os.path.join(output_dir, "concepts"), exist_ok=True)
        concept = ExtractedConcept(name="fts-test", sources=["raw/doc.md"])
        write_one_article(output_dir, concept, mock_client, "test", 4000, mem, vec, ont)
        entry = mem.get("concept:fts-test")
        assert entry is not None


class TestNormalizeConfidence:
    def test_high(self):
        assert "confidence: high" in _normalize_confidence("confidence: 5/5")

    def test_low(self):
        assert "confidence: low" in _normalize_confidence("confidence: speculative")

    def test_medium_default(self):
        assert "confidence: medium" in _normalize_confidence("confidence: unknown-value")


class TestFormatName:
    def test_kebab_to_title(self):
        assert _format_name("self-attention") == "Self Attention"

    def test_single_word(self):
        assert _format_name("transformer") == "Transformer"

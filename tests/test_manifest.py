# -*- coding: utf-8 -*-
"""
@author:XuMing(xuming624@qq.com)
@description: 
"""
from __future__ import annotations
import json
import os
import tempfile

import pytest

from synth_wiki.manifest import Concept, Manifest, Source, load


# 1. Manifest.new() is empty with version=2
def test_new_manifest_is_empty():
    m = Manifest.new()
    assert m.version == 2
    assert m.sources == {}
    assert m.concepts == {}
    assert m.embed_model == ""
    assert m.embed_dim == 0


# 2. load non-existent file returns empty manifest
def test_load_nonexistent_returns_empty(tmp_path):
    m = load(str(tmp_path / "does_not_exist.json"))
    assert m.version == 2
    assert m.sources == {}
    assert m.concepts == {}


# 3. save + load roundtrip preserves all fields
def test_roundtrip(tmp_path):
    m = Manifest.new()
    m.embed_model = "text-embedding-3-small"
    m.embed_dim = 1536
    m.add_source("doc.pdf", "abc123", "pdf", 4096)
    m.mark_compiled("doc.pdf", "summaries/doc.md", ["python", "testing"])
    m.add_concept("python", "articles/python.md", ["doc.pdf"])

    path = str(tmp_path / "manifest.json")
    m.save(path)

    m2 = load(path)
    assert m2.version == 2
    assert m2.embed_model == "text-embedding-3-small"
    assert m2.embed_dim == 1536
    assert "doc.pdf" in m2.sources
    src = m2.sources["doc.pdf"]
    assert src.hash == "abc123"
    assert src.type == "pdf"
    assert src.size_bytes == 4096
    assert src.summary_path == "summaries/doc.md"
    assert src.concepts_produced == ["python", "testing"]
    assert src.status == "compiled"
    assert "python" in m2.concepts
    c = m2.concepts["python"]
    assert c.article_path == "articles/python.md"
    assert c.sources == ["doc.pdf"]


# 4. add_source sets status="pending" and adds correctly
def test_add_source_pending():
    m = Manifest.new()
    m.add_source("file.txt", "deadbeef", "text", 512)
    assert "file.txt" in m.sources
    src = m.sources["file.txt"]
    assert src.hash == "deadbeef"
    assert src.type == "text"
    assert src.size_bytes == 512
    assert src.status == "pending"
    assert src.added_at != ""


# 5. mark_compiled updates status, summary_path, compiled_at, concepts_produced
def test_mark_compiled():
    m = Manifest.new()
    m.add_source("doc.md", "hash1", "markdown", 1024)
    m.mark_compiled("doc.md", "summaries/doc.md", ["concept_a", "concept_b"])
    src = m.sources["doc.md"]
    assert src.status == "compiled"
    assert src.summary_path == "summaries/doc.md"
    assert src.concepts_produced == ["concept_a", "concept_b"]
    assert src.compiled_at != ""


# 6. remove_source deletes the source
def test_remove_source():
    m = Manifest.new()
    m.add_source("to_remove.pdf", "h1", "pdf", 100)
    assert "to_remove.pdf" in m.sources
    m.remove_source("to_remove.pdf")
    assert "to_remove.pdf" not in m.sources


def test_remove_nonexistent_source_is_noop():
    m = Manifest.new()
    m.remove_source("ghost.pdf")  # should not raise


# 7. add_concept stores correctly
def test_add_concept():
    m = Manifest.new()
    m.add_concept("machine_learning", "articles/ml.md", ["paper1.pdf", "paper2.pdf"])
    assert "machine_learning" in m.concepts
    c = m.concepts["machine_learning"]
    assert c.article_path == "articles/ml.md"
    assert c.sources == ["paper1.pdf", "paper2.pdf"]
    assert c.last_compiled != ""


# 8. pending_sources filters only status=="pending"
def test_pending_sources():
    m = Manifest.new()
    m.add_source("pending.pdf", "h1", "pdf", 100)
    m.add_source("compiled.pdf", "h2", "pdf", 200)
    m.mark_compiled("compiled.pdf", "summaries/compiled.md")
    pending = m.pending_sources()
    assert "pending.pdf" in pending
    assert "compiled.pdf" not in pending


# 9. source_count and concept_count return correct values
def test_counts():
    m = Manifest.new()
    assert m.source_count == 0
    assert m.concept_count == 0
    m.add_source("a.pdf", "h1", "pdf", 10)
    m.add_source("b.pdf", "h2", "pdf", 20)
    assert m.source_count == 2
    m.add_concept("topic_a", "articles/a.md", ["a.pdf"])
    assert m.concept_count == 1
    m.remove_source("a.pdf")
    assert m.source_count == 1


# 10. Multiple sources and concepts work together
def test_multiple_sources_and_concepts(tmp_path):
    m = Manifest.new()
    sources = [
        ("file1.pdf", "h1", "pdf", 100),
        ("file2.md", "h2", "markdown", 200),
        ("file3.txt", "h3", "text", 300),
    ]
    for path, hash_, typ, size in sources:
        m.add_source(path, hash_, typ, size)

    m.mark_compiled("file1.pdf", "summaries/file1.md", ["concept_x"])
    m.mark_compiled("file2.md", "summaries/file2.md", ["concept_y", "concept_z"])

    m.add_concept("concept_x", "articles/x.md", ["file1.pdf"])
    m.add_concept("concept_y", "articles/y.md", ["file2.md"])
    m.add_concept("concept_z", "articles/z.md", ["file2.md"])

    assert m.source_count == 3
    assert m.concept_count == 3

    pending = m.pending_sources()
    assert list(pending.keys()) == ["file3.txt"]

    # roundtrip
    manifest_path = str(tmp_path / "manifest.json")
    m.save(manifest_path)
    m2 = load(manifest_path)
    assert m2.source_count == 3
    assert m2.concept_count == 3
    assert m2.sources["file1.pdf"].status == "compiled"
    assert m2.sources["file3.txt"].status == "pending"
    assert m2.concepts["concept_z"].sources == ["file2.md"]


# verify JSON file ends with newline
def test_save_ends_with_newline(tmp_path):
    m = Manifest.new()
    path = str(tmp_path / "manifest.json")
    m.save(path)
    with open(path, "rb") as f:
        content = f.read()
    assert content.endswith(b"\n")


# mark_compiled on unknown path is a noop
def test_mark_compiled_unknown_path():
    m = Manifest.new()
    m.mark_compiled("nonexistent.pdf", "summaries/x.md")  # should not raise
    assert m.source_count == 0

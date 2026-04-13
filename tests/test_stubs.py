# -*- coding: utf-8 -*-
"""Tests for synth_wiki.compiler.stubs module."""
import os
import pytest
from synth_wiki.compiler.stubs import generate_stubs, _to_slug, _resolve_link, _build_page_index


@pytest.fixture
def wiki_dir(tmp_path):
    """Create a minimal wiki output directory with some articles."""
    concepts = tmp_path / "concepts"
    concepts.mkdir()

    # Article with wikilinks pointing to non-existent pages
    (concepts / "vector-search.md").write_text(
        '---\nconcept: vector-search\naliases: ["向量搜索"]\nconfidence: high\n---\n\n'
        '# Vector Search\n\nRelated to [[machine-learning]] and [[deep-learning]].\n'
        'See also [[information-retrieval]].\n'
    )

    # Article that has an alias
    (concepts / "information-retrieval.md").write_text(
        '---\nconcept: information-retrieval\naliases: ["信息检索", "IR"]\nconfidence: high\n---\n\n'
        '# Information Retrieval\n\nUses [[vector-search]] and [[bm25]].\n'
    )
    return tmp_path


def test_generate_stubs_creates_missing_pages(wiki_dir):
    created = generate_stubs(str(wiki_dir))
    # machine-learning, deep-learning, bm25 should be created as stubs
    slugs = {os.path.basename(p).replace(".md", "") for p in created}
    assert "machine-learning" in slugs
    assert "deep-learning" in slugs
    assert "bm25" in slugs
    # information-retrieval already exists, should NOT be created
    assert "information-retrieval" not in slugs
    # vector-search already exists, should NOT be created
    assert "vector-search" not in slugs


def test_stubs_have_correct_frontmatter(wiki_dir):
    generate_stubs(str(wiki_dir))
    stub_path = os.path.join(str(wiki_dir), "concepts", "machine-learning.md")
    assert os.path.exists(stub_path)
    with open(stub_path) as f:
        content = f.read()
    assert "stub: true" in content
    assert "confidence: low" in content
    assert "concept: machine-learning" in content


def test_alias_resolution_prevents_duplicate_stubs(wiki_dir):
    """If a wikilink matches an alias, no stub should be created."""
    concepts = wiki_dir / "concepts"
    (concepts / "test-article.md").write_text(
        '---\nconcept: test-article\nconfidence: high\n---\n\n'
        '# Test\n\nSee [[向量搜索]] and [[IR]].\n'
    )
    created = generate_stubs(str(wiki_dir))
    slugs = {os.path.basename(p).replace(".md", "") for p in created}
    # "向量搜索" is an alias of vector-search -> should NOT create stub
    assert "向量搜索" not in slugs
    # "IR" is an alias of information-retrieval -> should NOT create stub
    assert "ir" not in slugs


def test_to_slug():
    assert _to_slug("Machine Learning") == "machine-learning"
    assert _to_slug("机器学习") == "机器学习"
    assert _to_slug("BM25") == "bm25"
    assert _to_slug("A* Search") == "a-search"
    assert _to_slug("deep-learning") == "deep-learning"


def test_idempotent(wiki_dir):
    """Running generate_stubs twice should not create duplicates."""
    first = generate_stubs(str(wiki_dir))
    second = generate_stubs(str(wiki_dir))
    assert len(second) == 0
    assert len(first) > 0


def test_build_page_index(wiki_dir):
    slug_to_path, alias_to_slug = _build_page_index(str(wiki_dir))
    assert "vector-search" in slug_to_path
    assert "information-retrieval" in slug_to_path
    assert "向量搜索" in alias_to_slug
    assert "信息检索" in alias_to_slug
    assert "ir" in alias_to_slug


def test_wikilink_with_display_text(wiki_dir):
    """[[target|display text]] should resolve to target."""
    concepts = wiki_dir / "concepts"
    (concepts / "alias-test.md").write_text(
        '---\nconcept: alias-test\nconfidence: high\n---\n\n'
        '# Test\n\nSee [[vector-search|向量搜索技术]].\n'
    )
    created = generate_stubs(str(wiki_dir))
    slugs = {os.path.basename(p).replace(".md", "") for p in created}
    # vector-search already exists, should not be stubbed
    assert "vector-search" not in slugs

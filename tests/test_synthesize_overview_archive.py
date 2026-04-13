# -*- coding: utf-8 -*-
"""
Tests for synthesize, overview, and archive modules.
"""
import json
import os
from unittest.mock import MagicMock, patch

import pytest

from synth_wiki.compiler.synthesize import (
    generate_syntheses, _cluster_by_concepts, _Cluster, _build_synthesis_prompt,
    _build_frontmatter, SynthesisResult,
)
from synth_wiki.compiler.overview import generate_overview, _collect_inventory
from synth_wiki.compiler.archive import archive_query, _parse_json
from synth_wiki.compiler.concepts import ExtractedConcept
from synth_wiki.compiler.summarize import SummaryResult
from synth_wiki.llm.client import Response


# ---- synthesize tests ----

class TestClusterByConcepts:
    def test_clusters_by_shared_concepts(self):
        summaries = [
            SummaryResult(source_path="a.md", summary="summary a"),
            SummaryResult(source_path="b.md", summary="summary b"),
            SummaryResult(source_path="c.md", summary="summary c"),
        ]
        concepts = [
            ExtractedConcept(name="transformer", sources=["a.md", "b.md", "c.md"]),
            ExtractedConcept(name="attention", sources=["a.md", "b.md"]),
        ]
        clusters = _cluster_by_concepts(summaries, concepts, min_size=3)
        assert len(clusters) >= 1
        assert clusters[0].slug == "transformer-synthesis"
        assert len(clusters[0].summaries) == 3

    def test_no_cluster_below_min_size(self):
        summaries = [
            SummaryResult(source_path="a.md", summary="summary a"),
            SummaryResult(source_path="b.md", summary="summary b"),
        ]
        concepts = [
            ExtractedConcept(name="x", sources=["a.md"]),
        ]
        clusters = _cluster_by_concepts(summaries, concepts, min_size=3)
        assert len(clusters) == 0

    def test_empty_inputs(self):
        clusters = _cluster_by_concepts([], [], min_size=3)
        assert clusters == []


class TestBuildSynthesisPrompt:
    def test_prompt_contains_theme(self):
        cluster = _Cluster(
            theme="Transformer Architecture",
            slug="transformer-synthesis",
            summaries=[SummaryResult(source_path="a.md", summary="text a")],
            shared_concepts=["transformer", "attention"],
        )
        prompt = _build_synthesis_prompt(cluster, "", "zh-CN")
        assert "Transformer Architecture" in prompt
        assert "transformer" in prompt
        assert "zh-CN" in prompt

    def test_prompt_includes_existing(self):
        cluster = _Cluster(
            theme="Test",
            slug="test-synthesis",
            summaries=[SummaryResult(source_path="a.md", summary="text")],
            shared_concepts=["x"],
        )
        prompt = _build_synthesis_prompt(cluster, "old content here", "en")
        assert "old content here" in prompt


class TestBuildFrontmatter:
    def test_frontmatter_format(self):
        cluster = _Cluster(
            theme="Test Theme",
            slug="test-synthesis",
            summaries=[SummaryResult(source_path="a.md", summary="text")],
            shared_concepts=["x", "y"],
        )
        fm = _build_frontmatter(cluster)
        assert fm.startswith("---")
        assert "title: Test Theme" in fm
        assert "type: synthesis" in fm


class TestGenerateSyntheses:
    def test_returns_empty_for_few_summaries(self):
        results = generate_syntheses(
            "/tmp/fake", [], [], MagicMock(), "model", 1000, 1,
            MagicMock(), MagicMock(), None, "zh-CN", min_cluster_size=3,
        )
        assert results == []

    @patch("synth_wiki.compiler.synthesize._write_one_synthesis")
    def test_calls_write_for_each_cluster(self, mock_write, tmp_path):
        mock_write.return_value = SynthesisResult(title="Test", slug="test", path=str(tmp_path / "test.md"))
        summaries = [
            SummaryResult(source_path=f"{i}.md", summary=f"s{i}") for i in range(5)
        ]
        concepts = [
            ExtractedConcept(name="big-concept", sources=[f"{i}.md" for i in range(5)]),
        ]
        mem = MagicMock()
        vec = MagicMock()
        results = generate_syntheses(
            str(tmp_path), summaries, concepts, MagicMock(), "model", 1000, 1,
            mem, vec, None, "zh-CN", min_cluster_size=3,
        )
        assert len(results) >= 1
        assert mock_write.called


# ---- overview tests ----

class TestCollectInventory:
    def test_counts_pages(self, tmp_path):
        concepts_dir = tmp_path / "concepts"
        concepts_dir.mkdir()
        (concepts_dir / "foo.md").write_text("test")
        (concepts_dir / "bar.md").write_text("test")

        inv = _collect_inventory(str(tmp_path))
        assert inv["total"] == 2
        assert len(inv["sections"]["concepts"]) == 2

    def test_empty_wiki(self, tmp_path):
        inv = _collect_inventory(str(tmp_path))
        assert inv["total"] == 0


class TestGenerateOverview:
    def test_returns_empty_for_empty_wiki(self, tmp_path):
        client = MagicMock()
        result = generate_overview(str(tmp_path), client, "model")
        assert result == ""
        client.chat_completion.assert_not_called()

    def test_generates_overview(self, tmp_path):
        concepts_dir = tmp_path / "concepts"
        concepts_dir.mkdir()
        (concepts_dir / "foo.md").write_text("---\nconcept: foo\n---\ntest")

        client = MagicMock()
        client.chat_completion.return_value = Response(content="# Overview\nThis wiki covers foo.")

        result = generate_overview(str(tmp_path), client, "model", "test-wiki", "zh-CN")
        assert result == str(tmp_path / "overview.md")
        assert os.path.exists(result)
        content = open(result).read()
        assert "Overview" in content


# ---- archive tests ----

class TestParseJson:
    def test_parses_clean_json(self):
        result = _parse_json('{"archive": true, "slug": "test"}')
        assert result["archive"] is True
        assert result["slug"] == "test"

    def test_parses_json_in_code_block(self):
        result = _parse_json('```json\n{"archive": false}\n```')
        assert result["archive"] is False

    def test_returns_empty_for_invalid(self):
        result = _parse_json("not json at all")
        assert result == {}

    def test_extracts_json_from_text(self):
        result = _parse_json('Some text {"archive": true, "slug": "x"} more text')
        assert result["archive"] is True


class TestArchiveQuery:
    def test_does_not_archive_if_llm_says_no(self, tmp_path):
        client = MagicMock()
        client.chat_completion.return_value = Response(
            content='{"archive": false, "slug": "", "reason": "trivial"}'
        )
        mem = MagicMock()
        vec = MagicMock()
        result = archive_query(
            str(tmp_path), "what is 1+1?", "it's 2", [],
            client, "model", mem, vec, None, "zh-CN",
        )
        assert result == ""

    def test_archives_when_llm_approves(self, tmp_path):
        concepts_dir = tmp_path / "concepts"
        concepts_dir.mkdir()

        responses = [
            Response(content='{"archive": true, "slug": "addition-basics", "title": "Addition Basics", "reason": "good"}'),
            Response(content="---\nconcept: addition-basics\ntype: query-derived\n---\n\n# Addition Basics\nContent here."),
        ]
        client = MagicMock()
        client.chat_completion.side_effect = responses

        mem = MagicMock()
        vec = MagicMock()
        result = archive_query(
            str(tmp_path), "How does addition work?", "Addition is...",
            ["math.md"], client, "model", mem, vec, None, "zh-CN",
        )
        assert result.endswith("addition-basics.md")
        assert os.path.exists(result)
        mem.add.assert_called_once()


# ---- integration: pipeline CompileResult now has syntheses_written ----

class TestCompileResultFields:
    def test_syntheses_written_field(self):
        from synth_wiki.compiler.pipeline import CompileResult
        r = CompileResult()
        assert r.syntheses_written == 0
        r.syntheses_written = 3
        assert r.syntheses_written == 3

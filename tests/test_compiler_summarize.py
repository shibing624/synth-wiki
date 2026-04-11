# -*- coding: utf-8 -*-
"""
@author:XuMing(xuming624@qq.com)
@description: Tests for synth_wiki.compiler.summarize module.
"""
import os
import pytest
from unittest.mock import MagicMock
from synth_wiki.compiler.diff import SourceInfo
from synth_wiki.compiler.summarize import summarize, summarize_one, SummaryResult
from synth_wiki.llm.client import Response, Usage


@pytest.fixture
def mock_client():
    client = MagicMock()
    client.chat_completion.return_value = Response(content="Test summary content", model="test", usage=Usage())
    return client


@pytest.fixture
def project(tmp_path):
    (tmp_path / "raw").mkdir()
    (tmp_path / "wiki" / "summaries").mkdir(parents=True)
    return tmp_path


class TestSummarize:
    def test_single_source_produces_summary(self, project, mock_client):
        (project / "raw" / "test.md").write_text("# Hello World\nSome content here.")
        abs_path = str(project / "raw" / "test.md")
        output_dir = str(project / "wiki")
        info = SourceInfo(path=abs_path, hash="h1", type="article", size=100)
        results = summarize(output_dir, [info], mock_client, "test-model", 2000, 1)
        assert len(results) == 1
        assert results[0].error is None
        assert results[0].summary == "Test summary content"
        assert os.path.exists(results[0].summary_path)

    def test_summary_file_has_frontmatter(self, project, mock_client):
        (project / "raw" / "doc.md").write_text("content")
        abs_path = str(project / "raw" / "doc.md")
        output_dir = str(project / "wiki")
        info = SourceInfo(path=abs_path, hash="h2", type="article", size=10)
        result = summarize_one(output_dir, info, mock_client, "test", 2000)
        with open(result.summary_path) as f:
            content = f.read()
        assert content.startswith("---")
        assert abs_path in content  # source path in frontmatter

    def test_error_in_extraction(self, project, mock_client):
        abs_path = str(project / "raw" / "nonexistent.md")
        output_dir = str(project / "wiki")
        info = SourceInfo(path=abs_path, hash="h3", type="article", size=0)
        result = summarize_one(output_dir, info, mock_client, "test", 2000)
        assert result.error is not None

    def test_parallel_execution(self, project, mock_client):
        output_dir = str(project / "wiki")
        for i in range(3):
            (project / "raw" / f"file{i}.md").write_text(f"Content {i}")
        sources = [
            SourceInfo(path=str(project / "raw" / f"file{i}.md"), hash=f"h{i}", type="article", size=10)
            for i in range(3)
        ]
        results = summarize(output_dir, sources, mock_client, "test", 2000, 2)
        assert len(results) == 3
        assert all(r.error is None for r in results)

    def test_image_source(self, project, mock_client):
        (project / "raw" / "img.png").write_bytes(b"\x89PNG")
        abs_path = str(project / "raw" / "img.png")
        output_dir = str(project / "wiki")
        info = SourceInfo(path=abs_path, hash="h4", type="image", size=4)
        result = summarize_one(output_dir, info, mock_client, "test", 2000)
        assert result.error is None
        assert "Image source" in result.summary

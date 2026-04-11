# -*- coding: utf-8 -*-
"""
@author:XuMing(xuming624@qq.com)
@description: Tests for synth_wiki.compiler.pipeline module.
"""
import os
import pytest
from unittest.mock import MagicMock, patch

from synth_wiki import paths
from synth_wiki.compiler.pipeline import (
    compile, CompileOpts, CompileResult,
    _write_changelog, _load_state, _save_state, CompileState,
)
from synth_wiki.config import Config, Source, APIConfig, ModelsConfig, CompilerConfig
from synth_wiki.llm.client import Response, Usage
from synth_wiki.wiki import init_greenfield


@pytest.fixture
def project(tmp_path):
    """Create a full project with a source file."""
    source_dir = str(tmp_path / "raw")
    output_dir = str(tmp_path / "wiki")
    init_greenfield("test-compile", source_dir, output_dir)
    # Override config to use fake API key and disable auto-commit
    from synth_wiki.config import load
    cfg = load(paths.config_path(), "test-compile")
    cfg.api.api_key = "fake_key"
    cfg.compiler.auto_commit = False
    cfg.save(paths.config_path())
    # Add a source
    os.makedirs(source_dir, exist_ok=True)
    (tmp_path / "raw" / "test.md").write_text("# Test Document\n\nSome content about machine learning.")
    return tmp_path


@pytest.fixture
def mock_llm():
    """Mock LLM client creation."""
    with patch("synth_wiki.compiler.pipeline.Client") as mock_cls:
        mock_client = MagicMock()
        mock_client.chat_completion.return_value = Response(
            content="Test summary output", model="test", usage=Usage(input_tokens=100, output_tokens=50)
        )
        mock_client.set_tracker = MagicMock()
        mock_client.set_pass = MagicMock()
        mock_cls.return_value = mock_client
        yield mock_client


@pytest.fixture
def mock_concepts():
    """Mock concept extraction to return a simple concept."""
    with patch("synth_wiki.compiler.pipeline.extract_concepts") as mock:
        from synth_wiki.compiler.concepts import ExtractedConcept
        mock.return_value = [ExtractedConcept(name="test-concept", sources=["test.md"], type="concept")]
        yield mock


@pytest.fixture
def mock_articles():
    """Mock article writing."""
    with patch("synth_wiki.compiler.pipeline.write_articles") as mock:
        from synth_wiki.compiler.write import ArticleResult
        mock.return_value = [ArticleResult(concept_name="test-concept", article_path="/tmp/concepts/test-concept.md")]
        yield mock


@pytest.fixture
def mock_embedder():
    """Mock embedder to return None (no embedding)."""
    with patch("synth_wiki.compiler.pipeline.new_from_config", return_value=None):
        yield


class TestCompilePipeline:
    def test_full_pipeline_one_source(self, project, mock_llm, mock_concepts, mock_articles, mock_embedder):
        result = compile("test-compile", CompileOpts(config_path=paths.config_path()))
        assert result.added == 1
        assert result.summarized == 1
        assert result.concepts_extracted == 1
        assert result.articles_written == 1
        assert result.errors == 0

    def test_dry_run_no_writes(self, project, mock_embedder):
        result = compile("test-compile", CompileOpts(dry_run=True, config_path=paths.config_path()))
        assert result.added == 1
        assert result.summarized == 0  # dry run doesn't actually summarize

    def test_empty_diff_returns_early(self, tmp_path, mock_embedder):
        source_dir = str(tmp_path / "raw2")
        output_dir = str(tmp_path / "wiki2")
        init_greenfield("empty-test", source_dir, output_dir)
        from synth_wiki.config import load
        cfg = load(paths.config_path(), "empty-test")
        cfg.api.api_key = "fake_key"
        cfg.save(paths.config_path())
        result = compile("empty-test", CompileOpts(config_path=paths.config_path()))
        assert result.added == 0
        assert result.summarized == 0

    def test_removed_sources_cleaned(self, project, mock_llm, mock_concepts, mock_articles, mock_embedder):
        # First compile
        compile("test-compile", CompileOpts(config_path=paths.config_path()))
        # Remove source file
        os.remove(str(project / "raw" / "test.md"))
        # Second compile
        result2 = compile("test-compile", CompileOpts(config_path=paths.config_path()))
        assert result2.removed == 1

    def test_changelog_written(self, project, mock_llm, mock_concepts, mock_articles, mock_embedder):
        compile("test-compile", CompileOpts(config_path=paths.config_path()))
        changelog = project / "wiki" / "CHANGELOG.md"
        assert changelog.exists()
        content = changelog.read_text()
        assert "CHANGELOG" in content


class TestCompileState:
    def test_save_and_load(self, tmp_path):
        state = CompileState(compile_id="test-123", started_at="2024-01-01", pass_num=2, completed=["a.md"])
        path = str(tmp_path / "state.json")
        _save_state(path, state)
        loaded = _load_state(path)
        assert loaded is not None
        assert loaded.compile_id == "test-123"
        assert loaded.completed == ["a.md"]

    def test_load_nonexistent(self, tmp_path):
        assert _load_state(str(tmp_path / "nope.json")) is None


class TestWriteChangelog:
    def test_creates_new_changelog(self, tmp_path):
        output_dir = str(tmp_path / "wiki")
        os.makedirs(output_dir, exist_ok=True)
        result = CompileResult(added=1, summarized=1, concepts_extracted=2, articles_written=2)
        _write_changelog(output_dir, result)
        changelog_path = os.path.join(output_dir, "CHANGELOG.md")
        assert os.path.exists(changelog_path)
        with open(changelog_path) as f:
            content = f.read()
        assert "Added: 1" in content

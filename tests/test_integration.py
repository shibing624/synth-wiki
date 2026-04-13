# -*- coding: utf-8 -*-
"""
@author:XuMing(xuming624@qq.com)
@description: End-to-end integration test.
"""
import os
import pytest
from unittest.mock import patch, MagicMock

from synth_wiki import paths
from synth_wiki.wiki import init_greenfield, get_status, run_doctor
from synth_wiki.compiler.pipeline import compile, CompileOpts
from synth_wiki.storage import DB
from synth_wiki.memory import Store as MemoryStore, Entry
from synth_wiki.vectors import Store as VectorStore
from synth_wiki.hybrid import Searcher, SearchOpts
from synth_wiki.linter import Runner, LintContext
from synth_wiki.manifest import load as load_manifest
from synth_wiki.llm.client import Response, Usage


@pytest.fixture
def project(tmp_path):
    source_dir = str(tmp_path / "raw")
    output_dir = str(tmp_path / "wiki")
    init_greenfield("integration-test", source_dir, output_dir)
    # Fix config for testing
    from synth_wiki.config import load
    cfg = load(paths.config_path(), "integration-test")
    cfg.api.api_key = "fake_openai_key"
    cfg.compiler.auto_commit = False
    cfg.save(paths.config_path())
    # Add source documents
    os.makedirs(source_dir, exist_ok=True)
    (tmp_path / "raw" / "ml-intro.md").write_text(
        "# Machine Learning Introduction\n\nML is a field of AI.\n"
        "It uses algorithms to learn from data without explicit programming."
    )
    (tmp_path / "raw" / "deep-learning.md").write_text(
        "# Deep Learning\n\nDeep learning uses neural networks with many layers.\n"
        "It is a subset of machine learning."
    )
    return tmp_path


class TestIntegration:
    def test_init_creates_valid_project(self, project):
        """Init creates all necessary files and passes doctor."""
        result = run_doctor("integration-test")
        config_ok = any(c.name == "config" and c.status == "ok" for c in result.checks)
        assert config_ok

    def test_full_pipeline(self, project):
        """Init -> compile -> verify artifacts."""
        mock_resp = Response(
            content="Summary of the document about machine learning concepts.",
            model="test", usage=Usage(input_tokens=100, output_tokens=50)
        )
        mock_concept_resp = Response(
            content='[{"name":"machine-learning","aliases":["ML"],"sources":["ml-intro.md"],"type":"concept"}]',
            model="test", usage=Usage()
        )
        mock_article_resp = Response(
            content="---\nconcept: machine-learning\nconfidence: high\n---\n\n## Definition\nML is a field of AI.",
            model="test", usage=Usage()
        )

        call_count = [0]
        def side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] <= 2:
                return mock_resp
            elif call_count[0] == 3:
                return mock_concept_resp
            else:
                return mock_article_resp

        with patch("synth_wiki.compiler.pipeline.Client") as mock_cls, \
             patch("synth_wiki.compiler.pipeline.new_from_config", return_value=None):
            mock_client = MagicMock()
            mock_client.chat_completion.side_effect = side_effect
            mock_client.set_tracker = MagicMock()
            mock_client.set_pass = MagicMock()
            mock_cls.return_value = mock_client

            result = compile("integration-test", CompileOpts(config_path=paths.config_path()))

        assert result.added == 2
        assert result.summarized == 2
        assert result.errors == 0

        mf = load_manifest(paths.manifest_path("integration-test"))
        assert mf.source_count == 2

        summaries_dir = project / "wiki" / "summaries"
        assert summaries_dir.exists()

    def test_search_after_compile(self, project):
        """After indexing, search returns results."""
        db_path = paths.db_path("integration-test")
        db = DB.open(db_path)
        mem = MemoryStore(db_path)
        vec = VectorStore(db)

        mem.add(Entry(id="raw/ml-intro.md", content="Machine learning is a field of AI",
                      tags=["article"], article_path="wiki/summaries/ml-intro.md"))

        searcher = Searcher(mem, vec)
        results = searcher.search(SearchOpts(query="machine learning"))
        mem.close()
        db.close()

        assert len(results) > 0
        assert "ml-intro" in results[0].id

    def test_lint_on_compiled(self, project):
        """Lint runs without errors on fresh project."""
        from synth_wiki.config import load
        cfg = load(paths.config_path(), "integration-test")
        ctx = LintContext(output_dir=cfg.resolve_output(),
                         db_path=paths.db_path("integration-test"))
        runner = Runner()
        results = runner.run(ctx)
        assert isinstance(results, list)

    def test_status_counts(self, project):
        """Status reflects project state."""
        info = get_status("integration-test")
        assert info.project == "integration-test"
        assert info.mode == "greenfield"
        assert info.source_count == 0

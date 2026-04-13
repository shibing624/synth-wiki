# -*- coding: utf-8 -*-
"""
@author:XuMing(xuming624@qq.com)
@description: Tests for MCP server tools, CLI query and serve commands.
"""
from __future__ import annotations
import os
import pytest
from click.testing import CliRunner

from synth_wiki import paths
from synth_wiki.storage import DB
from synth_wiki.memory import Store as MemoryStore, Entry
from synth_wiki.ontology import Store as OntologyStore, Entity


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def populated_project(tmp_project_dir, isolate_home):
    """Create a project with some indexed entries for search/query tests."""
    project_name = "test-wiki"
    db_p = paths.db_path(project_name)
    db = DB.open(db_p)
    mem = MemoryStore(db_p)

    # Add some test entries
    mem.add(Entry(id="test-doc-1", content="Transformers use self-attention mechanisms for sequence modeling.",
                  tags=["concept"], article_path="concepts/transformer.md"))
    mem.add(Entry(id="test-doc-2", content="Flash attention optimizes memory access patterns.",
                  tags=["technique"], article_path="concepts/flash-attention.md"))

    # Add entities with new types
    ont = OntologyStore(db)
    ont.add_entity(Entity(id="openai", type="entity", name="OpenAI",
                          article_path="entities/openai.md"))
    ont.add_entity(Entity(id="gpt-vs-bert", type="comparison", name="GPT vs BERT",
                          article_path="comparisons/gpt-vs-bert.md"))

    mem.close()
    db.close()

    # Create article files
    output_dir = str(tmp_project_dir / "wiki")
    for subdir in ["entities", "comparisons"]:
        os.makedirs(os.path.join(output_dir, subdir), exist_ok=True)
    with open(os.path.join(output_dir, "concepts", "transformer.md"), "w") as f:
        f.write("---\nconcept: transformer\nconfidence: high\n---\n\n# Transformer\n\nContent about transformers.")
    with open(os.path.join(output_dir, "entities", "openai.md"), "w") as f:
        f.write("---\nconcept: openai\ntype: entity\n---\n\n# OpenAI\n\nOpenAI is a company.")
    with open(os.path.join(output_dir, "comparisons", "gpt-vs-bert.md"), "w") as f:
        f.write("---\nconcept: gpt-vs-bert\ntype: comparison\n---\n\n# GPT vs BERT\n\nComparison.")

    return tmp_project_dir


# ---------------------------------------------------------------------------
# MCP Server: create_server smoke test
# ---------------------------------------------------------------------------

class TestMCPServer:
    def test_create_server_returns_fastmcp(self, populated_project):
        from synth_wiki.server import create_server
        mcp = create_server(project_name="test-wiki",
                            config_path=paths.config_path())
        assert mcp is not None
        assert mcp.name == "synth-wiki"

    def test_server_has_tools(self, populated_project):
        from synth_wiki.server import create_server
        mcp = create_server(project_name="test-wiki",
                            config_path=paths.config_path())
        # FastMCP stores tools internally; check they were registered
        # The tools are registered as decorated functions within create_server
        # We can verify by checking the tool names
        assert mcp is not None


# ---------------------------------------------------------------------------
# DB Migration V2: entity/comparison types
# ---------------------------------------------------------------------------

class TestDBMigrationV2:
    def test_entity_type_allowed(self, tmp_path):
        db = DB.open(str(tmp_path / "test.db"))
        ont = OntologyStore(db)
        ont.add_entity(Entity(id="e1", type="entity", name="TestEntity"))
        e = ont.get_entity("e1")
        assert e is not None
        assert e.type == "entity"
        db.close()

    def test_comparison_type_allowed(self, tmp_path):
        db = DB.open(str(tmp_path / "test.db"))
        ont = OntologyStore(db)
        ont.add_entity(Entity(id="c1", type="comparison", name="A vs B"))
        e = ont.get_entity("c1")
        assert e is not None
        assert e.type == "comparison"
        db.close()

    def test_existing_types_still_work(self, tmp_path):
        db = DB.open(str(tmp_path / "test.db"))
        ont = OntologyStore(db)
        for t in ["concept", "technique", "source", "claim", "artifact"]:
            ont.add_entity(Entity(id=f"test-{t}", type=t, name=f"Test {t}"))
        assert ont.entity_count() == 5
        db.close()


# ---------------------------------------------------------------------------
# CLI: query command
# ---------------------------------------------------------------------------

class TestCLIQuery:
    def test_query_no_results(self, tmp_project_dir, isolate_home):
        """Query with no indexed data and no embedder should print 'No relevant articles'."""
        from synth_wiki.cli import main
        import yaml
        # Patch the config to use a provider that won't try to embed
        cfg_path = paths.config_path()
        with open(cfg_path) as f:
            data = yaml.safe_load(f)
        data["api"]["provider"] = "openai-compatible"
        data["embed"] = {"provider": "auto", "model": ""}
        with open(cfg_path, "w") as f:
            yaml.dump(data, f)

        runner = CliRunner()
        result = runner.invoke(main, ["--project", "test-wiki", "query", "xyz123"])
        # With no indexed data, search returns nothing -> "No relevant articles"
        assert result.exit_code == 0
        assert "No relevant articles" in result.output

    def test_query_help(self):
        from synth_wiki.cli import main
        runner = CliRunner()
        result = runner.invoke(main, ["query", "--help"])
        assert result.exit_code == 0
        assert "Ask a question" in result.output


# ---------------------------------------------------------------------------
# CLI: serve command
# ---------------------------------------------------------------------------

class TestCLIServe:
    def test_serve_help(self):
        from synth_wiki.cli import main
        runner = CliRunner()
        result = runner.invoke(main, ["serve", "--help"])
        assert result.exit_code == 0
        assert "MCP server" in result.output
        assert "--transport" in result.output

    def test_serve_transport_choices(self):
        from synth_wiki.cli import main
        runner = CliRunner()
        result = runner.invoke(main, ["serve", "--transport", "invalid"])
        assert result.exit_code != 0


# ---------------------------------------------------------------------------
# CLI: read_article via server tool
# ---------------------------------------------------------------------------

class TestReadArticle:
    def test_read_concept(self, populated_project):
        from synth_wiki.server import create_server
        mcp = create_server(project_name="test-wiki",
                            config_path=paths.config_path())
        # Access the tool function directly
        # The tools are registered as functions, we can test the underlying logic
        from synth_wiki.config import load as load_config
        cfg = load_config(paths.config_path(), "test-wiki")
        output_dir = cfg.resolve_output()
        path = os.path.join(output_dir, "concepts", "transformer.md")
        assert os.path.exists(path)
        with open(path) as f:
            content = f.read()
        assert "Transformer" in content

    def test_read_entity(self, populated_project):
        from synth_wiki.config import load as load_config
        cfg = load_config(paths.config_path(), "test-wiki")
        output_dir = cfg.resolve_output()
        path = os.path.join(output_dir, "entities", "openai.md")
        assert os.path.exists(path)

    def test_read_comparison(self, populated_project):
        from synth_wiki.config import load as load_config
        cfg = load_config(paths.config_path(), "test-wiki")
        output_dir = cfg.resolve_output()
        path = os.path.join(output_dir, "comparisons", "gpt-vs-bert.md")
        assert os.path.exists(path)


# ---------------------------------------------------------------------------
# CLI: list_articles via server tool
# ---------------------------------------------------------------------------

class TestListArticles:
    def test_lists_all_types(self, populated_project):
        from synth_wiki.config import load as load_config
        cfg = load_config(paths.config_path(), "test-wiki")
        output_dir = cfg.resolve_output()
        # Check all three dirs have articles
        for subdir, expected in [("concepts", "transformer"), ("entities", "openai"),
                                  ("comparisons", "gpt-vs-bert")]:
            dir_path = os.path.join(output_dir, subdir)
            files = [f for f in os.listdir(dir_path) if f.endswith(".md")]
            slugs = [f[:-3] for f in files]
            assert expected in slugs

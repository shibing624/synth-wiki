# -*- coding: utf-8 -*-
"""
@author:XuMing(xuming624@qq.com)
@description: Tests for synth_wiki.cli module.
"""
import os
import pytest
from click.testing import CliRunner

from synth_wiki import paths
from synth_wiki.cli import main


@pytest.fixture
def runner():
    return CliRunner()


class TestCLI:
    def test_help(self, runner):
        result = runner.invoke(main, ["--help"])
        assert result.exit_code == 0
        assert "synth-wiki" in result.output

    def test_init_creates_project(self, runner, tmp_path):
        source_dir = str(tmp_path / "raw")
        output_dir = str(tmp_path / "wiki")
        result = runner.invoke(main, [
            "init", "--name", "cli-test", "--source", source_dir, "--output", output_dir
        ])
        assert result.exit_code == 0, result.output
        assert "initialized" in result.output.lower() or "cli-test" in result.output
        assert os.path.exists(paths.config_path())

    def test_status_on_project(self, runner, tmp_path):
        source_dir = str(tmp_path / "raw")
        output_dir = str(tmp_path / "wiki")
        runner.invoke(main, ["init", "--name", "status-cli", "--source", source_dir, "--output", output_dir])
        result = runner.invoke(main, ["--project", "status-cli", "status"])
        assert result.exit_code == 0
        assert "Sources:" in result.output or "Project:" in result.output

    def test_doctor_on_project(self, runner, tmp_path):
        source_dir = str(tmp_path / "raw")
        output_dir = str(tmp_path / "wiki")
        runner.invoke(main, ["init", "--name", "doctor-cli", "--source", source_dir, "--output", output_dir])
        result = runner.invoke(main, ["--project", "doctor-cli", "doctor"])
        assert result.exit_code == 0
        assert "[OK]" in result.output

    def test_lint_on_empty_project(self, runner, tmp_path):
        source_dir = str(tmp_path / "raw")
        output_dir = str(tmp_path / "wiki")
        runner.invoke(main, ["init", "--name", "lint-cli", "--source", source_dir, "--output", output_dir])
        result = runner.invoke(main, ["--project", "lint-cli", "lint"])
        assert result.exit_code == 0

    def test_compile_dry_run(self, runner, tmp_path):
        source_dir = str(tmp_path / "raw")
        output_dir = str(tmp_path / "wiki")
        runner.invoke(main, ["init", "--name", "compile-cli", "--source", source_dir, "--output", output_dir])
        os.makedirs(source_dir, exist_ok=True)
        (tmp_path / "raw" / "test.md").write_text("# Test\nContent")
        result = runner.invoke(main, ["--project", "compile-cli", "compile", "--dry-run"])
        assert result.exit_code == 0
        assert "added" in result.output.lower() or "Compile" in result.output

    def test_ingest_file(self, runner, tmp_path):
        source_dir = str(tmp_path / "raw")
        output_dir = str(tmp_path / "wiki")
        runner.invoke(main, ["init", "--name", "ingest-cli", "--source", source_dir, "--output", output_dir])
        src = tmp_path / "external.md"
        src.write_text("# External doc")
        result = runner.invoke(main, ["--project", "ingest-cli", "ingest", str(src)])
        assert result.exit_code == 0
        assert "Ingested" in result.output

    def test_projects_list(self, runner, tmp_path):
        source_dir = str(tmp_path / "raw")
        output_dir = str(tmp_path / "wiki")
        runner.invoke(main, ["init", "--name", "list-test", "--source", source_dir, "--output", output_dir])
        result = runner.invoke(main, ["projects"])
        assert result.exit_code == 0
        assert "list-test" in result.output

    def test_search_on_empty(self, runner, tmp_path):
        source_dir = str(tmp_path / "raw")
        output_dir = str(tmp_path / "wiki")
        runner.invoke(main, ["init", "--name", "search-cli", "--source", source_dir, "--output", output_dir])
        result = runner.invoke(main, ["--project", "search-cli", "search", "test"])
        assert result.exit_code == 0

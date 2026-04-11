# -*- coding: utf-8 -*-
"""
@author:XuMing(xuming624@qq.com)
@description: Tests for synth_wiki.wiki module.
"""
import os
import pytest
import yaml

from synth_wiki import paths
from synth_wiki.wiki import (
    init_greenfield, init_vault_overlay, scan_folders,
    ingest_path, get_status, format_status, run_doctor, format_doctor, _slugify_url,
)


class TestInitGreenfield:
    def test_creates_all_dirs(self, tmp_path):
        source_dir = str(tmp_path / "raw")
        output_dir = str(tmp_path / "wiki")
        init_greenfield("test-project", source_dir, output_dir)
        assert os.path.isdir(source_dir)
        assert os.path.isdir(os.path.join(output_dir, "summaries"))
        assert os.path.isdir(os.path.join(output_dir, "concepts"))
        # Config is in global home
        assert os.path.exists(paths.config_path())
        # Manifest is in global home
        assert os.path.exists(paths.manifest_path("test-project"))
        # DB is in global home
        assert os.path.exists(paths.db_path("test-project"))

    def test_config_has_project_name(self, tmp_path):
        source_dir = str(tmp_path / "raw")
        output_dir = str(tmp_path / "wiki")
        init_greenfield("my-wiki", source_dir, output_dir)
        from synth_wiki.config import load
        cfg = load(paths.config_path(), "my-wiki")
        assert cfg.project == "my-wiki"

    def test_registers_in_global_config(self, tmp_path):
        source_dir = str(tmp_path / "raw")
        output_dir = str(tmp_path / "wiki")
        init_greenfield("proj-a", source_dir, output_dir)
        with open(paths.config_path()) as f:
            data = yaml.safe_load(f)
        assert "proj-a" in data["projects"]
        assert data["projects"]["proj-a"]["output"] == output_dir


class TestInitVaultOverlay:
    def test_creates_output_structure(self, tmp_path):
        vault_dir = str(tmp_path / "vault")
        os.makedirs(vault_dir)
        init_vault_overlay("vault-proj", vault_dir, ["notes"], ["templates"])
        output_dir = os.path.join(vault_dir, "_wiki")
        assert os.path.isdir(os.path.join(output_dir, "summaries"))
        assert os.path.isdir(os.path.join(output_dir, "concepts"))
        assert os.path.exists(paths.config_path())


class TestScanFolders:
    def test_counts_files(self, tmp_path):
        (tmp_path / "notes").mkdir()
        (tmp_path / "notes" / "file1.md").write_text("hello")
        (tmp_path / "notes" / "file2.md").write_text("world")
        (tmp_path / "data").mkdir()
        (tmp_path / "data" / "sheet.csv").write_text("a,b")
        result = scan_folders(str(tmp_path))
        names = {f.name for f in result}
        assert "notes" in names
        notes = next(f for f in result if f.name == "notes")
        assert notes.file_count == 2
        assert notes.has_md is True


class TestIngestPath:
    def test_copies_file_and_updates_manifest(self, tmp_path):
        source_dir = str(tmp_path / "raw")
        output_dir = str(tmp_path / "wiki")
        init_greenfield("ingest-test", source_dir, output_dir)
        src = tmp_path / "external.md"
        src.write_text("# External document")
        result = ingest_path("ingest-test", str(src))
        assert result.type == "article"
        assert os.path.exists(result.source_path)
        from synth_wiki.manifest import load as load_mf
        mf = load_mf(paths.manifest_path("ingest-test"))
        assert result.source_path in mf.sources


class TestGetStatus:
    def test_returns_correct_counts(self, tmp_path):
        source_dir = str(tmp_path / "raw")
        output_dir = str(tmp_path / "wiki")
        init_greenfield("status-test", source_dir, output_dir)
        info = get_status("status-test")
        assert info.project == "status-test"
        assert info.mode == "greenfield"
        assert info.source_count == 0

    def test_format_status_readable(self, tmp_path):
        source_dir = str(tmp_path / "raw")
        output_dir = str(tmp_path / "wiki")
        init_greenfield("fmt-test", source_dir, output_dir)
        info = get_status("fmt-test")
        text = format_status(info)
        assert "fmt-test" in text
        assert "greenfield" in text


class TestDoctor:
    def test_passes_on_valid_project(self, tmp_path):
        source_dir = str(tmp_path / "raw")
        output_dir = str(tmp_path / "wiki")
        init_greenfield("doctor-test", source_dir, output_dir)
        result = run_doctor("doctor-test")
        assert not result.has_errors()

    def test_fails_on_missing_config(self, tmp_path):
        result = run_doctor("nonexistent-project")
        assert result.has_errors()

    def test_format_doctor_readable(self, tmp_path):
        source_dir = str(tmp_path / "raw")
        output_dir = str(tmp_path / "wiki")
        init_greenfield("doc-test", source_dir, output_dir)
        result = run_doctor("doc-test")
        text = format_doctor(result)
        assert "[OK]" in text


class TestSlugifyUrl:
    def test_basic(self):
        assert _slugify_url("https://example.com/page") == "example-com-page"

    def test_truncates_long_urls(self):
        result = _slugify_url("https://example.com/" + "a" * 100)
        assert len(result) <= 80

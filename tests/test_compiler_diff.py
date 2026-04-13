# -*- coding: utf-8 -*-
"""
@author:XuMing(xuming624@qq.com)
@description: Tests for synth_wiki.compiler.diff module.
"""
import os
import pytest
from synth_wiki.config import Config, Source
from synth_wiki.manifest import Manifest
from synth_wiki.compiler.diff import diff, file_hash, SourceInfo
from synth_wiki.paths import is_ignored


@pytest.fixture
def project(tmp_path):
    """Create a minimal project structure with absolute paths."""
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    source_abs = str(raw_dir)
    config = Config(project="test", sources=[Source(path=source_abs, type="auto", watch=True)])
    manifest = Manifest.new()
    return tmp_path, config, manifest


class TestDiff:
    def test_new_file_detected_as_added(self, project):
        tmp_path, cfg, mf = project
        (tmp_path / "raw" / "test.md").write_text("# Hello")
        result = diff(cfg, mf)
        assert len(result.added) == 1
        assert result.added[0].path == str(tmp_path / "raw" / "test.md")
        assert result.added[0].type == "article"

    def test_modified_file_detected(self, project):
        tmp_path, cfg, mf = project
        f = tmp_path / "raw" / "test.md"
        f.write_text("original")
        abs_path = str(f)
        h = file_hash(abs_path)
        mf.add_source(abs_path, h, "article", len("original"))
        # Modify file
        f.write_text("modified content")
        result = diff(cfg, mf)
        assert len(result.modified) == 1

    def test_deleted_file_detected_as_removed(self, project):
        tmp_path, cfg, mf = project
        abs_path = str(tmp_path / "raw" / "gone.md")
        mf.add_source(abs_path, "sha256:abc", "article", 10)
        result = diff(cfg, mf)
        assert len(result.removed) == 1
        assert result.removed[0] == abs_path

    def test_ignored_paths_skipped(self, project):
        tmp_path, cfg, mf = project
        cfg.ignore = ["secret_stuff"]
        secret_dir = tmp_path / "raw" / "secret_stuff"
        secret_dir.mkdir()
        (secret_dir / "hidden.md").write_text("secret")
        (tmp_path / "raw" / "public.md").write_text("public")
        result = diff(cfg, mf)
        assert len(result.added) == 1
        assert "public.md" in result.added[0].path

    def test_empty_directory_returns_empty_diff(self, project):
        tmp_path, cfg, mf = project
        result = diff(cfg, mf)
        assert len(result.added) == 0
        assert len(result.modified) == 0
        assert len(result.removed) == 0

    def test_hash_is_deterministic(self, project):
        tmp_path, _, _ = project
        f = tmp_path / "raw" / "test.md"
        f.write_text("deterministic content")
        h1 = file_hash(str(f))
        h2 = file_hash(str(f))
        assert h1 == h2
        assert h1.startswith("sha256:")


class TestIsIgnored:
    def test_folder_match(self):
        assert is_ignored("/abs/raw/secret_stuff/file.md", ["secret_stuff"]) is True

    def test_exact_match(self):
        assert is_ignored("/abs/raw/secret_stuff", ["secret_stuff"]) is True

    def test_no_match(self):
        assert is_ignored("/abs/raw/public/file.md", ["secret_stuff"]) is False

    def test_path_component_match(self):
        assert is_ignored("/abs/raw/secret_stuff/sub/file.md", ["secret_stuff"]) is True

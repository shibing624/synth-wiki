# -*- coding: utf-8 -*-
"""
@author:XuMing(xuming624@qq.com)
@description: Tests for prompts module.
"""
from __future__ import annotations
import os
import pytest
import tempfile

import synth_wiki.prompts as prompts
from synth_wiki.prompts import (
    render,
    load_from_dir,
    scaffold_defaults,
    available,
    reset,
    _filename_to_template_name,
    _template_name_to_filename,
)


def setup_function():
    reset()


def test_render_default_template_with_data():
    result = render("write_article", {
        "concept_name": "Python",
        "concept_id": "python-lang",
        "sources": "docs.python.org",
        "max_tokens": "4000",
    })
    assert "Python" in result
    assert "python-lang" in result


def test_load_from_dir_overrides_default(tmp_path):
    custom = tmp_path / "custom_write_article.md"
    custom.write_text("Custom template: $concept_name")
    load_from_dir(str(tmp_path))
    result = render("custom_write_article", {"concept_name": "Django"})
    assert "Custom template: Django" == result


def test_scaffold_defaults_creates_files(tmp_path):
    scaffold_defaults(str(tmp_path))
    files = list(tmp_path.iterdir())
    assert len(files) > 0
    names = [f.name for f in files]
    assert any(n.endswith(".md") for n in names)


def test_scaffold_defaults_skips_existing(tmp_path):
    existing = tmp_path / "write-article.md"
    existing.write_text("my custom content")
    scaffold_defaults(str(tmp_path))
    assert existing.read_text() == "my custom content"


def test_available_lists_all_templates():
    names = available()
    assert len(names) >= 4
    assert "write_article.txt" in names
    assert "extract_concepts.txt" in names
    assert "capture_knowledge.txt" in names
    assert "caption_image.txt" in names


def test_reset_restores_defaults(tmp_path):
    custom = tmp_path / "my_custom.md"
    custom.write_text("My custom template")
    load_from_dir(str(tmp_path))
    assert "my_custom.txt" in available()
    reset()
    assert "my_custom.txt" not in available()


def test_unknown_template_raises_key_error():
    with pytest.raises(KeyError, match="unknown template"):
        render("nonexistent_template")


def test_filename_to_template_name_md():
    assert _filename_to_template_name("write-article.md") == "write_article.txt"


def test_filename_to_template_name_txt():
    assert _filename_to_template_name("extract_concepts.txt") == "extract_concepts.txt"


def test_filename_to_template_name_hyphens():
    assert _filename_to_template_name("capture-knowledge.md") == "capture_knowledge.txt"


def test_template_name_to_filename():
    assert _template_name_to_filename("write_article.txt") == "write-article.md"


def test_template_name_to_filename_no_suffix():
    assert _template_name_to_filename("capture_knowledge") == "capture-knowledge.md"

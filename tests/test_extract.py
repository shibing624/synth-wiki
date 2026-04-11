# -*- coding: utf-8 -*-
"""
@author:XuMing(xuming624@qq.com)
@description: Tests for extract module.
"""
from __future__ import annotations
import os
import pytest
import tempfile

from synth_wiki.extract import (
    Chunk,
    SourceContent,
    detect_source_type,
    extract,
    is_image_source,
    chunk_if_needed,
)


def test_detect_source_type_md():
    assert detect_source_type("notes.md") == "article"


def test_detect_source_type_pdf():
    assert detect_source_type("paper.pdf") == "paper"


def test_detect_source_type_py():
    assert detect_source_type("script.py") == "code"


def test_detect_source_type_txt():
    assert detect_source_type("readme.txt") == "article"


def test_detect_source_type_csv():
    assert detect_source_type("data.csv") == "data"


def test_detect_source_type_jpg():
    assert detect_source_type("photo.jpg") == "image"


def test_detect_source_type_unknown():
    assert detect_source_type("file.xyz") == "article"


def test_extract_reads_markdown(tmp_path):
    md_file = tmp_path / "test.md"
    md_file.write_text("# Hello\nThis is markdown.")
    result = extract(str(md_file))
    assert result.text == "# Hello\nThis is markdown."
    assert result.type == "article"


def test_extract_reads_python_code(tmp_path):
    py_file = tmp_path / "script.py"
    py_file.write_text("def hello():\n    return 'world'\n")
    result = extract(str(py_file))
    assert "def hello" in result.text
    assert result.type == "code"


def test_extract_raises_for_pdf(tmp_path):
    pdf_file = tmp_path / "paper.pdf"
    pdf_file.write_bytes(b"%PDF-1.4 fake content")
    with pytest.raises(NotImplementedError):
        extract(str(pdf_file))


def test_extract_returns_image_type(tmp_path):
    png_file = tmp_path / "photo.png"
    png_file.write_bytes(b"\x89PNG\r\n\x1a\n")
    result = extract(str(png_file))
    assert result.type == "image"
    assert result.text == ""


def test_chunk_if_needed_short_content():
    content = SourceContent(text="Short text", type="article")
    chunk_if_needed(content, max_tokens=1000)
    assert content.chunk_count == 1
    assert len(content.chunks) == 1
    assert content.chunks[0].text == "Short text"
    assert content.chunks[0].index == 0


def test_chunk_if_needed_splits_long_content():
    # 4 chars/token, 10 tokens = 40 chars max
    long_text = "\n".join([f"Line {i:03d} content here" for i in range(20)])
    content = SourceContent(text=long_text, type="article")
    chunk_if_needed(content, max_tokens=10)
    assert content.chunk_count > 1
    assert len(content.chunks) == content.chunk_count
    for i, chunk in enumerate(content.chunks):
        assert chunk.index == i
        assert len(chunk.text) <= 10 * 4 + 50  # allow some slack for line boundaries


def test_is_image_source_true():
    content = SourceContent(text="", type="image")
    assert is_image_source(content) is True


def test_is_image_source_false():
    content = SourceContent(text="hello", type="article")
    assert is_image_source(content) is False

# -*- coding: utf-8 -*-
"""
@author:XuMing(xuming624@qq.com)
@description: Raw text extraction from various document formats (PDF, docx, etc.).
"""
from __future__ import annotations
from dataclasses import dataclass, field
import os

CHARS_PER_TOKEN = 4  # Approximate: ~4 characters per token for GPT tokenizers


@dataclass
class Chunk:
    index: int
    text: str


@dataclass
class SourceContent:
    text: str
    type: str
    chunk_count: int = 1
    chunks: list[Chunk] = field(default_factory=list)


TYPE_MAP = {
    ".md": "article", ".markdown": "article", ".txt": "article",
    ".pdf": "paper", ".epub": "paper",
    ".py": "code", ".js": "code", ".ts": "code", ".go": "code",
    ".java": "code", ".rs": "code", ".c": "code", ".cpp": "code", ".h": "code",
    ".csv": "data", ".json": "data", ".yaml": "data", ".yml": "data",
    ".png": "image", ".jpg": "image", ".jpeg": "image", ".gif": "image",
    ".webp": "image", ".svg": "image",
    ".html": "article", ".xml": "article",
    ".docx": "paper", ".pptx": "paper", ".xlsx": "data",
    ".eml": "article",
}


def detect_source_type(path: str) -> str:
    ext = os.path.splitext(path)[1].lower()
    return TYPE_MAP.get(ext, "article")


def extract(path: str, type_hint: str = "") -> SourceContent:
    ext = os.path.splitext(path)[1].lower()
    src_type = type_hint or detect_source_type(path)

    text_exts = {
        ".md", ".markdown", ".txt", ".py", ".js", ".ts", ".go", ".java",
        ".rs", ".c", ".cpp", ".h", ".csv", ".json", ".yaml", ".yml",
        ".html", ".xml", ".eml",
    }
    if ext in text_exts:
        with open(path, "r", errors="replace") as f:
            text = f.read()
        return SourceContent(text=text, type=src_type)

    if ext in {".pdf", ".docx", ".pptx", ".xlsx", ".epub"}:
        raise NotImplementedError(
            f"Binary format {ext} extraction not yet implemented. "
            "Use text formats (.md, .txt) for now."
        )

    if ext in {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg"}:
        return SourceContent(text="", type="image")

    try:
        with open(path, "r", errors="replace") as f:
            text = f.read()
        return SourceContent(text=text, type=src_type)
    except Exception:
        raise ValueError(f"Cannot extract content from {path}")


def is_image_source(content: SourceContent) -> bool:
    return content.type == "image"


def chunk_if_needed(content: SourceContent, max_tokens: int) -> None:
    """Split content into chunks if it exceeds max_tokens (estimated at 4 chars/token)."""
    max_chars = max_tokens * CHARS_PER_TOKEN
    if len(content.text) <= max_chars:
        content.chunk_count = 1
        content.chunks = [Chunk(index=0, text=content.text)]
        return

    lines = content.text.split("\n")
    chunks = []
    current_chunk: list[str] = []
    current_size = 0

    for line in lines:
        line_size = len(line) + 1
        if current_size + line_size > max_chars and current_chunk:
            chunks.append("\n".join(current_chunk))
            current_chunk = []
            current_size = 0
        current_chunk.append(line)
        current_size += line_size

    if current_chunk:
        chunks.append("\n".join(current_chunk))

    content.chunk_count = len(chunks)
    content.chunks = [Chunk(index=i, text=t) for i, t in enumerate(chunks)]

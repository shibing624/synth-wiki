# -*- coding: utf-8 -*-
"""
@author:XuMing(xuming624@qq.com)
@description: 
"""
from __future__ import annotations
import os
from dataclasses import dataclass, field
from pathlib import Path
from string import Template


_TEMPLATES_DIR = Path(__file__).parent / "templates"
_active_templates: dict[str, str] = {}
_default_templates: dict[str, str] = {}


def _load_defaults() -> dict[str, str]:
    templates = {}
    if _TEMPLATES_DIR.exists():
        for f in _TEMPLATES_DIR.iterdir():
            if f.suffix == ".txt":
                templates[f.name] = f.read_text()
    return templates


_default_templates = _load_defaults()
_active_templates = dict(_default_templates)


def load_from_dir(dir_path: str) -> None:
    """Load user prompt templates from directory, overriding defaults."""
    global _active_templates
    if not dir_path or not os.path.isdir(dir_path):
        return
    _active_templates = dict(_default_templates)
    for entry in os.listdir(dir_path):
        if entry.endswith((".md", ".txt")):
            template_name = _filename_to_template_name(entry)
            with open(os.path.join(dir_path, entry)) as f:
                _active_templates[template_name] = f.read()


def render(name: str, data: dict | None = None) -> str:
    """Render a named template with data using $-style substitution."""
    template_name = name + ".txt" if not name.endswith(".txt") else name
    if template_name not in _active_templates:
        raise KeyError(f"prompts: unknown template {name!r}")
    tmpl = Template(_active_templates[template_name])
    return tmpl.safe_substitute(data or {})


def scaffold_defaults(dir_path: str) -> None:
    """Copy bundled templates to directory for customization."""
    os.makedirs(dir_path, exist_ok=True)
    for name, content in _default_templates.items():
        out_name = _template_name_to_filename(name)
        out_path = os.path.join(dir_path, out_name)
        if os.path.exists(out_path):
            continue
        header = (
            f"# {out_name}\n"
            "# Edit to customize synth-wiki prompt.\n"
            "# Delete to revert to default.\n\n"
        )
        with open(out_path, "w") as f:
            f.write(header + content)


def available() -> list[str]:
    return list(_active_templates.keys())


def reset() -> None:
    global _active_templates
    _active_templates = dict(_default_templates)


def _filename_to_template_name(filename: str) -> str:
    name = os.path.splitext(filename)[0]
    name = name.replace("-", "_")
    return name + ".txt"


def _template_name_to_filename(template_name: str) -> str:
    name = template_name.removesuffix(".txt")
    name = name.replace("_", "-")
    return name + ".md"


@dataclass
class SummarizeData:
    source_path: str = ""
    source_type: str = ""
    max_tokens: int = 2000


@dataclass
class ExtractData:
    existing_concepts: str = ""
    summaries: str = ""


@dataclass
class WriteArticleData:
    concept_name: str = ""
    concept_id: str = ""
    sources: str = ""
    related_concepts: list[str] = None
    existing_article: str = ""
    max_tokens: int = 4000


@dataclass
class CaptionData:
    source_path: str = ""


@dataclass
class CaptureData:
    context: str = ""
    tags: str = ""

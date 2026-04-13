# -*- coding: utf-8 -*-
"""
@author:XuMing(xuming624@qq.com)
@description: Wiki operations: init, ingest, status, doctor.

All persistent state lives under ~/.synth_wiki/ (config, DB, manifests).
Project directories only contain source files and compiled output.
"""
from __future__ import annotations
import hashlib
import os
import shutil
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

import yaml

import httpx

from synth_wiki import git
from synth_wiki import paths
from synth_wiki.config import Config, Source, VaultConfig, load, load_global
from synth_wiki.extract import detect_source_type
from synth_wiki.manifest import Manifest, load as load_manifest
from synth_wiki.storage import DB
from synth_wiki.memory import Store as MemoryStore
from synth_wiki.vectors import Store as VectorStore
from synth_wiki.ontology import Store as OntologyStore


def init_greenfield(project_name: str, source_dir: str, output_dir: str,
                    model: str = "gpt-4o-mini", home_dir: str = "") -> None:
    """Create a new synth-wiki project.

    Args:
        project_name: Unique project identifier.
        source_dir: Absolute path to the source documents directory.
        output_dir: Absolute path for compiled wiki output.
        model: Default LLM model name.
        home_dir: Override home directory for config/db/manifest.
                  If empty, uses the global ~/.synth_wiki/.
    """
    source_dir = os.path.abspath(source_dir)
    output_dir = os.path.abspath(output_dir)

    # Resolve paths: use custom home_dir or global defaults
    if home_dir:
        home_dir = os.path.abspath(home_dir)
        os.makedirs(home_dir, exist_ok=True)
        cfg_path = os.path.join(home_dir, "config.yaml")
        db_p = os.path.join(home_dir, "db", f"{project_name}.db")
        mf_p = os.path.join(home_dir, "manifests", f"{project_name}.json")
        os.makedirs(os.path.dirname(db_p), exist_ok=True)
        os.makedirs(os.path.dirname(mf_p), exist_ok=True)
    else:
        cfg_path = paths.config_path()
        db_p = paths.db_path(project_name)
        mf_p = paths.manifest_path(project_name)

    # Create source and output directories
    os.makedirs(source_dir, exist_ok=True)
    for sub in ["summaries", "concepts", "connections", "outputs", "images", "archive"]:
        os.makedirs(os.path.join(output_dir, sub), exist_ok=True)

    # Register project in config
    _register_project(project_name, {
        "description": f"synth-wiki project: {project_name}",
        "sources": [{"path": source_dir, "type": "auto", "watch": True}],
        "output": output_dir,
    }, model, cfg_path)

    # Create DB
    db = DB.open(db_p)
    db.close()

    # Create empty manifest
    Manifest.new().save(mf_p)

    # Git init in source dir if desired
    if git.is_available() and os.path.isdir(source_dir):
        parent = os.path.dirname(source_dir)
        if not git.is_repo(parent):
            git.init(parent)


def init_vault_overlay(project_name: str, vault_dir: str, source_folders: list[str],
                       ignore_folders: list[str], output: str = "_wiki",
                       model: str = "gpt-4o-mini", home_dir: str = "") -> None:
    """Initialize synth-wiki on an existing Obsidian vault."""
    vault_dir = os.path.abspath(vault_dir)
    output_dir = os.path.join(vault_dir, output)

    for sub in ["summaries", "concepts", "connections", "outputs", "images", "archive"]:
        os.makedirs(os.path.join(output_dir, sub), exist_ok=True)

    sources = [{"path": os.path.join(vault_dir, sf), "type": "article", "watch": True} for sf in source_folders]
    ignore = ignore_folders + [output]

    # Resolve paths: use custom home_dir or global defaults
    if home_dir:
        home_dir = os.path.abspath(home_dir)
        os.makedirs(home_dir, exist_ok=True)
        cfg_path = os.path.join(home_dir, "config.yaml")
        db_p = os.path.join(home_dir, "db", f"{project_name}.db")
        mf_p = os.path.join(home_dir, "manifests", f"{project_name}.json")
        os.makedirs(os.path.dirname(db_p), exist_ok=True)
        os.makedirs(os.path.dirname(mf_p), exist_ok=True)
    else:
        cfg_path = paths.config_path()
        db_p = paths.db_path(project_name)
        mf_p = paths.manifest_path(project_name)

    _register_project(project_name, {
        "description": f"Obsidian vault with synth-wiki: {project_name}",
        "vault": {"root": vault_dir},
        "sources": sources,
        "output": output_dir,
        "ignore": ignore,
    }, model, cfg_path)

    db = DB.open(db_p)
    db.close()
    Manifest.new().save(mf_p)


def _register_project(project_name: str, project_data: dict, model: str,
                      config_path: str = "") -> None:
    """Add or update a project in a config file."""
    cfg_path = config_path or paths.config_path()
    os.makedirs(os.path.dirname(cfg_path), exist_ok=True)

    data = {}
    if os.path.exists(cfg_path):
        with open(cfg_path) as f:
            data = yaml.safe_load(f) or {}

    if "projects" not in data:
        data["projects"] = {}

    # Set default global API config if not present
    if "api" not in data:
        data["api"] = {
            "provider": "openai-compatible",
            "api_key": "${OPENAI_API_KEY}",
            "base_url": "${OPENAI_BASE_URL}",
        }
    if "models" not in data:
        data["models"] = {
            "summarize": model,
            "extract": model,
            "write": model,
            "lint": model,
            "query": model,
        }

    data["projects"][project_name] = project_data

    with open(cfg_path, "w") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False)


@dataclass
class FolderInfo:
    name: str
    file_count: int = 0
    has_md: bool = False
    has_pdf: bool = False


def scan_folders(dir: str) -> list[FolderInfo]:
    """List top-level folders with file statistics."""
    folders = []
    for entry in sorted(os.listdir(dir)):
        full = os.path.join(dir, entry)
        if not os.path.isdir(full) or entry.startswith(".") or entry == "_wiki":
            continue
        info = FolderInfo(name=entry)
        for root, _, files in os.walk(full):
            for f in files:
                info.file_count += 1
                ext = os.path.splitext(f)[1].lower()
                if ext == ".md":
                    info.has_md = True
                elif ext == ".pdf":
                    info.has_pdf = True
        folders.append(info)
    return folders


@dataclass
class IngestResult:
    source_path: str
    type: str
    size: int


def ingest_path(project_name: str, src_path: str, config_path: str = "") -> IngestResult:
    """Copy a local file to the appropriate source folder."""
    cfg_path = config_path or paths.config_path()
    cfg = load(cfg_path, project_name)
    abs_path = os.path.abspath(src_path)
    if not os.path.exists(abs_path):
        raise FileNotFoundError(f"ingest: file not found: {abs_path}")

    src_type = detect_source_type(abs_path)
    dest_dir = cfg.resolve_sources()[0] if cfg.sources else os.path.expanduser("~/raw")
    os.makedirs(dest_dir, exist_ok=True)

    dest_path = os.path.join(dest_dir, os.path.basename(abs_path))
    shutil.copy2(abs_path, dest_path)

    with open(abs_path, "rb") as f:
        h = f"sha256:{hashlib.sha256(f.read()).hexdigest()}"
    mf = load_manifest(paths.manifest_path(project_name))
    mf.add_source(dest_path, h, src_type, os.path.getsize(abs_path))
    mf.save(paths.manifest_path(project_name))

    return IngestResult(source_path=dest_path, type=src_type, size=os.path.getsize(abs_path))


def ingest_url(project_name: str, url: str, config_path: str = "") -> IngestResult:
    """Download URL and save to source folder."""
    cfg_path = config_path or paths.config_path()
    cfg = load(cfg_path, project_name)

    resp = httpx.get(url, timeout=30.0, follow_redirects=True)
    resp.raise_for_status()
    body = resp.content

    content = f"---\nsource_url: {url}\ningested_at: {datetime.now(timezone.utc).isoformat()}\n---\n\n{body.decode('utf-8', errors='replace')}"

    dest_dir = cfg.resolve_sources()[0] if cfg.sources else os.path.expanduser("~/raw")
    os.makedirs(dest_dir, exist_ok=True)
    filename = _slugify_url(url) + ".md"
    dest_path = os.path.join(dest_dir, filename)

    with open(dest_path, "w") as f:
        f.write(content)

    h = f"sha256:{hashlib.sha256(content.encode()).hexdigest()}"
    mf = load_manifest(paths.manifest_path(project_name))
    mf.add_source(dest_path, h, "article", len(content))
    mf.save(paths.manifest_path(project_name))

    return IngestResult(source_path=dest_path, type="article", size=len(content))


@dataclass
class StatusInfo:
    project: str = ""
    mode: str = ""
    source_count: int = 0
    pending_count: int = 0
    concept_count: int = 0
    entry_count: int = 0
    vector_count: int = 0
    vector_dims: int = 0
    entity_count: int = 0
    relation_count: int = 0
    git_clean: bool = True
    last_commit: str = ""
    last_message: str = ""


@dataclass
class Stores:
    mem: MemoryStore
    vec: VectorStore
    ont: OntologyStore


def get_status(project_name: str, stores: Optional[Stores] = None,
               config_path: str = "", home_dir: str = "") -> StatusInfo:
    cfg_path = config_path or paths.config_path()
    cfg = load(cfg_path, project_name)
    info = StatusInfo(project=cfg.project, mode="vault-overlay" if cfg.is_vault_overlay else "greenfield")

    if home_dir:
        home_dir = os.path.abspath(home_dir)
        mf_p = os.path.join(home_dir, "manifests", f"{project_name}.json")
        db_p = os.path.join(home_dir, "db", f"{project_name}.db")
    else:
        mf_p = paths.manifest_path(project_name)
        db_p = paths.db_path(project_name)

    mf = load_manifest(mf_p)
    info.source_count = mf.source_count
    info.concept_count = mf.concept_count
    info.pending_count = len(mf.pending_sources())

    if stores:
        mem, vec, ont = stores.mem, stores.vec, stores.ont
    else:
        db = DB.open(db_p)
        mem = MemoryStore(db_p)
        vec = VectorStore(db)
        ont = OntologyStore(db)

    info.entry_count = mem.count()
    info.vector_count = vec.count()
    info.vector_dims = vec.dimensions()
    info.entity_count = ont.entity_count()
    info.relation_count = ont.relation_count()

    if not stores:
        mem.close()
        db.close()

    # Check git in source dirs
    source_dirs = cfg.resolve_sources()
    for src_dir in source_dirs:
        if git.is_repo(src_dir):
            s = git.status(src_dir)
            info.git_clean = s == ""
            info.last_commit, info.last_message = git.last_commit(src_dir)
            break

    return info


def format_status(s: StatusInfo) -> str:
    out = f"Project: {s.project} ({s.mode})\n"
    out += f"Sources: {s.source_count} ({s.pending_count} pending)\n"
    out += f"Concepts: {s.concept_count}\n"
    out += f"Entries: {s.entry_count} indexed\n"
    out += f"Vectors: {s.vector_count}"
    if s.vector_dims > 0:
        out += f" ({s.vector_dims}-dim)"
    out += f"\nEntities: {s.entity_count}, Relations: {s.relation_count}\n"
    if s.last_commit:
        git_status = "clean" if s.git_clean else "dirty"
        out += f"Git: {s.last_commit} {s.last_message} ({git_status})\n"
    return out


@dataclass
class DoctorCheck:
    name: str
    status: str  # ok, warn, error, info
    message: str


@dataclass
class DoctorResult:
    checks: list[DoctorCheck] = field(default_factory=list)

    def has_errors(self) -> bool:
        return any(c.status == "error" for c in self.checks)


def run_doctor(project_name: str, config_path: str = "") -> DoctorResult:
    result = DoctorResult()

    try:
        cfg_path = config_path or paths.config_path()
        cfg = load(cfg_path, project_name)
        result.checks.append(DoctorCheck("config", "ok", f"Project {cfg.project!r} loaded"))
    except Exception as e:
        result.checks.append(DoctorCheck("config", "error", f"Failed to load config: {e}"))
        return result

    db_p = paths.db_path(project_name)
    if os.path.exists(db_p):
        result.checks.append(DoctorCheck("database", "ok", f"DB exists at {db_p}"))
    else:
        result.checks.append(DoctorCheck("database", "error", "DB not found"))

    for sp in cfg.resolve_sources():
        if not os.path.isdir(sp):
            result.checks.append(DoctorCheck("sources", "warn", f"Source dir not found: {sp}"))

    if cfg.api.provider and (not cfg.api.api_key or cfg.api.api_key.startswith("${")):
        result.checks.append(DoctorCheck("api", "warn", f"API key not set for {cfg.api.provider}"))
    elif cfg.api.provider:
        result.checks.append(DoctorCheck("api", "ok", f"Provider: {cfg.api.provider}"))

    output_dir = cfg.resolve_output()
    if os.path.isdir(output_dir):
        result.checks.append(DoctorCheck("output", "ok", f"Output: {output_dir}"))
    else:
        result.checks.append(DoctorCheck("output", "warn", f"Output dir not found: {output_dir}"))

    return result


def format_doctor(r: DoctorResult) -> str:
    icons = {"ok": "[OK]", "warn": "[WARN]", "error": "[ERROR]", "info": "[INFO]"}
    out = ""
    for c in r.checks:
        out += f"  {icons.get(c.status, '[?]')} {c.name}: {c.message}\n"
    if r.has_errors():
        out += "\nSome checks failed. Fix errors above before compiling.\n"
    else:
        out += "\nAll checks passed.\n"
    return out


def _slugify_url(url: str) -> str:
    s = url.replace("https://", "").replace("http://", "")
    result = []
    for c in s.lower():
        if c.isalnum():
            result.append(c)
        else:
            result.append("-")
    slug = "".join(result)
    while "--" in slug:
        slug = slug.replace("--", "-")
    slug = slug.strip("-")
    return slug[:80]

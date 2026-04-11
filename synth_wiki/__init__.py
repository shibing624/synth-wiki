# -*- coding: utf-8 -*-
"""
@author:XuMing(xuming624@qq.com)
@description: synth-wiki: AI-powered wiki compiler.

Usage:
    from synth_wiki import Config, load_config, compile, Searcher
    cfg = load_config("~/.synth_wiki/config.yaml", "my-project")
    result = compile("my-project")
"""
__version__ = "0.1.2"

# --- Submodules (keep for internal cross-imports) ---
from synth_wiki import git
from synth_wiki import log
from synth_wiki import paths

# --- Config ---
from synth_wiki.config import (
    Config,
    APIConfig,
    ModelsConfig,
    EmbedConfig,
    CompilerConfig,
    SearchConfig,
    LintingConfig,
    ServeConfig,
    Source,
    VaultConfig,
    load as load_config,
    load_global as load_global_config,
    list_projects,
)

# --- Wiki operations ---
from synth_wiki.wiki import (
    init_greenfield,
    init_vault_overlay,
    scan_folders,
    FolderInfo,
    ingest_path,
    ingest_url,
    IngestResult,
    get_status,
    format_status,
    StatusInfo,
    Stores,
    run_doctor,
    format_doctor,
    DoctorCheck,
    DoctorResult,
)

# --- Compiler pipeline ---
from synth_wiki.compiler import (
    compile,
    CompileOpts,
    CompileResult,
    diff,
    DiffResult,
    SourceInfo,
    summarize,
    SummaryResult,
    extract_concepts,
    ExtractedConcept,
    write_articles,
    ArticleResult,
)

# --- Search ---
from synth_wiki.hybrid import Searcher, SearchOpts, SearchResult

# --- LLM client ---
from synth_wiki.llm import (
    Client,
    Message,
    CallOpts,
    Usage,
    Response,
    CostTracker,
    CostReport,
)

# --- Storage ---
from synth_wiki.storage import DB
from synth_wiki.manifest import Manifest
from synth_wiki.memory import Store as MemoryStore, Entry
from synth_wiki.vectors import Store as VectorStore, VectorResult
from synth_wiki.ontology import (
    Store as OntologyStore,
    Entity,
    Relation,
    Direction,
    TraverseOpts,
)

# --- Embedding ---
from synth_wiki.embed import Embedder, APIEmbedder, OllamaEmbedder, new_from_config

__all__ = [
    # version
    "__version__",
    # submodules
    "git", "log", "paths",
    # config
    "Config", "APIConfig", "ModelsConfig", "EmbedConfig", "CompilerConfig",
    "SearchConfig", "LintingConfig", "ServeConfig", "Source", "VaultConfig",
    "load_config", "load_global_config", "list_projects",
    # wiki
    "init_greenfield", "init_vault_overlay", "scan_folders", "FolderInfo",
    "ingest_path", "ingest_url", "IngestResult",
    "get_status", "format_status", "StatusInfo", "Stores",
    "run_doctor", "format_doctor", "DoctorCheck", "DoctorResult",
    # compiler
    "compile", "CompileOpts", "CompileResult",
    "diff", "DiffResult", "SourceInfo",
    "summarize", "SummaryResult",
    "extract_concepts", "ExtractedConcept",
    "write_articles", "ArticleResult",
    # search
    "Searcher", "SearchOpts", "SearchResult",
    # llm
    "Client", "Message", "CallOpts", "Usage", "Response",
    "CostTracker", "CostReport",
    # storage
    "DB", "Manifest",
    "MemoryStore", "Entry",
    "VectorStore", "VectorResult",
    "OntologyStore", "Entity", "Relation", "Direction", "TraverseOpts",
    # embedding
    "Embedder", "APIEmbedder", "OllamaEmbedder", "new_from_config",
]

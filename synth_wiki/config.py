# -*- coding: utf-8 -*-
"""
@author:XuMing(xuming624@qq.com)
@description: Configuration loading, parsing, and validation.

Config lives at ~/.synth_wiki/config.yaml and supports multiple projects.
Global settings (api, models, embed, compiler, search, linting, serve)
serve as defaults; each project under "projects:" can override ANY field
including api, models, compiler, etc. for full per-project customization.
Nested dicts (api, models, compiler, search, linting, serve, embed) are
deep-merged: project-level keys override global keys, unset keys inherit.
"""
from __future__ import annotations
import os
import re
from dataclasses import dataclass, field
from typing import Optional
import yaml


@dataclass
class VaultConfig:
    root: str = "."


@dataclass
class Source:
    path: str = "raw"
    type: str = "auto"
    watch: bool = True


@dataclass
class APIConfig:
    provider: str = ""
    api_key: str = ""
    base_url: str = ""
    rate_limit: int = 0
    extra_body: dict = field(default_factory=dict)


@dataclass
class ModelsConfig:
    summarize: str = ""
    extract: str = ""
    write: str = ""
    lint: str = ""
    query: str = ""


@dataclass
class EmbedConfig:
    provider: str = "auto"
    model: str = ""
    dimensions: int = 0
    api_key: str = ""
    base_url: str = ""


@dataclass
class CompilerConfig:
    max_parallel: int = 4
    debounce_seconds: int = 2
    summary_max_tokens: int = 2000
    article_max_tokens: int = 4000
    auto_commit: bool = True
    auto_lint: bool = True
    mode: str = ""
    estimate_before: bool = False
    prompt_cache: Optional[bool] = None
    batch_threshold: int = 0
    token_price_per_million: float = 0.0
    page_threshold: int = 1  # min source count to create a page (1=no filter, 2+=Karpathy rule)

    @property
    def prompt_cache_enabled(self) -> bool:
        if self.prompt_cache is None:
            return True
        return self.prompt_cache


@dataclass
class SearchConfig:
    default_limit: int = 10


@dataclass
class LintingConfig:
    auto_fix_passes: list[str] = field(default_factory=lambda: ["consistency", "completeness", "style"])
    staleness_threshold_days: int = 90


@dataclass
class ServeConfig:
    transport: str = "stdio"
    port: int = 3333


@dataclass
class Config:
    version: int = 1
    project: str = ""
    description: str = ""
    language: str = "zh-CN"
    vault: Optional[VaultConfig] = None
    sources: list[Source] = field(default_factory=lambda: [Source()])
    output: str = "wiki"
    ignore: list[str] = field(default_factory=list)
    api: APIConfig = field(default_factory=APIConfig)
    models: ModelsConfig = field(default_factory=ModelsConfig)
    embed: Optional[EmbedConfig] = None
    compiler: CompilerConfig = field(default_factory=CompilerConfig)
    search: SearchConfig = field(default_factory=SearchConfig)
    linting: LintingConfig = field(default_factory=LintingConfig)
    serve: ServeConfig = field(default_factory=ServeConfig)
    _raw_yaml: str = ""  # original YAML text before env var expansion

    @property
    def is_vault_overlay(self) -> bool:
        return self.vault is not None

    def resolve_output(self) -> str:
        """Return absolute output directory path."""
        return os.path.abspath(self.output)

    def resolve_sources(self) -> list[str]:
        """Return absolute source directory paths."""
        paths = []
        for s in self.sources:
            paths.append(os.path.abspath(s.path))
        return paths

    @property
    def language_label(self) -> str:
        """Human-readable language name for prompt injection."""
        labels = {
            "zh-CN": "Simplified Chinese (简体中文)",
            "zh-TW": "Traditional Chinese (繁體中文)",
            "en": "English",
            "ja": "Japanese (日本語)",
            "ko": "Korean (한국어)",
        }
        return labels.get(self.language, self.language)

    def validate(self) -> None:
        if not self.project:
            raise ValueError("config: 'project' is required")
        if not self.output:
            raise ValueError("config: 'output' is required")
        if not self.sources:
            raise ValueError("config: at least one source is required")
        valid_providers = {"anthropic", "openai", "gemini", "ollama", "openai-compatible", ""}
        if self.api.provider not in valid_providers:
            raise ValueError(f"config: invalid provider {self.api.provider!r}")
        if self.serve.transport and self.serve.transport not in {"stdio", "sse"}:
            raise ValueError(f"config: invalid transport {self.serve.transport!r}")
        valid_modes = {"standard", "batch", "auto", ""}
        if self.compiler.mode not in valid_modes:
            raise ValueError(f"config: invalid compiler.mode {self.compiler.mode!r}")

    def save(self, path: str) -> None:
        data = _config_to_dict(self)
        # Never write expanded API keys to disk — omit api_key fields entirely
        if "api" in data:
            data["api"].pop("api_key", None)
        if "embed" in data:
            data["embed"].pop("api_key", None)
        with open(path, "w") as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=False)

    @classmethod
    def defaults(cls) -> Config:
        return cls()


def _str(val: object, default: str = "") -> str:
    """Return val as string, coercing None to default."""
    if val is None:
        return default
    return str(val)


def _expand_env_vars(s: str) -> str:
    """Replace ${VAR} references with environment variable values."""
    def replacer(m: re.Match) -> str:
        return os.environ.get(m.group(1), "")
    return re.sub(r'\$\{([^}]+)\}', replacer, s)


def load(path: str, project_name: str = "") -> Config:
    """Load config from YAML file with env var expansion.

    If the YAML has a 'projects' dict, merges global settings with the
    project-specific overrides. If project_name is empty and there's only
    one project, it is auto-selected.
    """
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"Config not found: {path}\n"
            f"Run 'synth-wiki init --name <project> --source <dir> --output <dir>' to create one."
        )
    with open(path) as f:
        raw = f.read()
    expanded = _expand_env_vars(raw)
    data = yaml.safe_load(expanded) or {}

    if "projects" in data and data["projects"]:
        projects = data["projects"]
        if not project_name:
            if len(projects) == 1:
                project_name = next(iter(projects))
            elif "project" in data:
                project_name = data["project"]
            else:
                raise ValueError(f"config: multiple projects defined, specify one of: {list(projects.keys())}")
        if project_name not in projects:
            raise ValueError(f"config: project {project_name!r} not found, available: {list(projects.keys())}")
        project_data = projects[project_name]
        merged = _merge_project(data, project_data, project_name)
        cfg = _dict_to_config(merged)
    else:
        cfg = _dict_to_config(data)

    cfg.validate()
    return cfg


def load_global(path: str) -> dict[str, Config]:
    """Load all project configs from a global config file.

    Returns a dict of project_name -> Config. Returns empty dict if file missing.
    """
    if not os.path.exists(path):
        return {}
    with open(path) as f:
        raw = f.read()
    expanded = _expand_env_vars(raw)
    data = yaml.safe_load(expanded) or {}

    result = {}
    if "projects" in data and data["projects"]:
        for name, project_data in data["projects"].items():
            merged = _merge_project(data, project_data, name)
            cfg = _dict_to_config(merged)
            cfg.validate()
            result[name] = cfg
    else:
        cfg = _dict_to_config(data)
        cfg.validate()
        result[cfg.project] = cfg
    return result


def list_projects(path: str) -> list[str]:
    """List project names from a config file. Returns [] if file missing."""
    if not os.path.exists(path):
        return []
    with open(path) as f:
        raw = f.read()
    expanded = _expand_env_vars(raw)
    data = yaml.safe_load(expanded) or {}
    if "projects" in data and data["projects"]:
        return list(data["projects"].keys())
    return [data.get("project", "")]


def _merge_project(global_data: dict, project_data: dict, project_name: str) -> dict:
    """Merge global config with project-specific overrides."""
    merged = {}
    for key in global_data:
        if key == "projects":
            continue
        merged[key] = global_data[key]
    merged["project"] = project_name
    for key, value in project_data.items():
        if key in ("api", "models", "compiler", "search", "linting", "serve", "embed"):
            if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
                merged_section = dict(merged[key])
                merged_section.update(value)
                merged[key] = merged_section
            else:
                merged[key] = value
        else:
            merged[key] = value
    return merged


def _dict_to_config(data: dict) -> Config:
    """Convert a parsed YAML dict to a Config dataclass."""
    cfg = Config.defaults()
    cfg.version = data.get("version", 1)
    cfg.project = data.get("project", "")
    cfg.description = data.get("description", "")
    cfg.language = data.get("language", "zh-CN")
    cfg.output = data.get("output", "wiki")
    cfg.ignore = data.get("ignore", [])

    if "vault" in data and data["vault"]:
        cfg.vault = VaultConfig(root=data["vault"].get("root", "."))

    if "sources" in data:
        raw_sources = data["sources"]
        if isinstance(raw_sources, list):
            cfg.sources = [
                Source(
                    path=s.get("path", "raw") if isinstance(s, dict) else str(s),
                    type=s.get("type", "auto") if isinstance(s, dict) else "auto",
                    watch=s.get("watch", True) if isinstance(s, dict) else True,
                )
                for s in raw_sources
            ]
        elif isinstance(raw_sources, str):
            cfg.sources = [Source(path=raw_sources)]

    if "api" in data:
        a = data["api"]
        cfg.api = APIConfig(
            provider=_str(a.get("provider")),
            api_key=_str(a.get("api_key")),
            base_url=_str(a.get("base_url")),
            rate_limit=a.get("rate_limit") or 0,
            extra_body=a.get("extra_body") or {},
        )

    if "models" in data:
        m = data["models"]
        cfg.models = ModelsConfig(
            summarize=_str(m.get("summarize")),
            extract=_str(m.get("extract")),
            write=_str(m.get("write")),
            lint=_str(m.get("lint")),
            query=_str(m.get("query")),
        )

    if "embed" in data and data["embed"]:
        e = data["embed"]
        cfg.embed = EmbedConfig(
            provider=e.get("provider", "auto"),
            model=e.get("model", ""),
            dimensions=e.get("dimensions", 0),
            api_key=e.get("api_key", ""),
            base_url=e.get("base_url", ""),
        )

    if "compiler" in data:
        c = data["compiler"]
        cfg.compiler = CompilerConfig(
            max_parallel=c.get("max_parallel", 4),
            debounce_seconds=c.get("debounce_seconds", 2),
            summary_max_tokens=c.get("summary_max_tokens", 2000),
            article_max_tokens=c.get("article_max_tokens", 4000),
            auto_commit=c.get("auto_commit", True),
            auto_lint=c.get("auto_lint", True),
            mode=c.get("mode", ""),
            estimate_before=c.get("estimate_before", False),
            prompt_cache=c.get("prompt_cache"),
            batch_threshold=c.get("batch_threshold", 0),
            token_price_per_million=c.get("token_price_per_million", 0.0),
            page_threshold=c.get("page_threshold", 1),
        )

    if "search" in data:
        s = data["search"]
        cfg.search = SearchConfig(
            default_limit=s.get("default_limit", 10),
        )

    if "linting" in data:
        l = data["linting"]
        cfg.linting = LintingConfig(
            auto_fix_passes=l.get("auto_fix_passes", ["consistency", "completeness", "style"]),
            staleness_threshold_days=l.get("staleness_threshold_days", 90),
        )

    if "serve" in data:
        s = data["serve"]
        cfg.serve = ServeConfig(
            transport=s.get("transport", "stdio"),
            port=s.get("port", 3333),
        )

    return cfg


def _config_to_dict(cfg: Config) -> dict:
    """Convert Config to a dict for YAML serialization."""
    d: dict = {
        "version": cfg.version,
        "project": cfg.project,
        "description": cfg.description,
        "language": cfg.language,
        "sources": [{"path": s.path, "type": s.type, "watch": s.watch} for s in cfg.sources],
        "output": cfg.output,
    }
    if cfg.ignore:
        d["ignore"] = cfg.ignore
    if cfg.vault:
        d["vault"] = {"root": cfg.vault.root}
    d["api"] = {
        "provider": cfg.api.provider,
        "api_key": cfg.api.api_key,
    }
    if cfg.api.base_url:
        d["api"]["base_url"] = cfg.api.base_url
    if cfg.api.rate_limit:
        d["api"]["rate_limit"] = cfg.api.rate_limit
    if cfg.api.extra_body:
        d["api"]["extra_body"] = cfg.api.extra_body
    d["models"] = {
        "summarize": cfg.models.summarize,
        "extract": cfg.models.extract,
        "write": cfg.models.write,
        "lint": cfg.models.lint,
        "query": cfg.models.query,
    }
    if cfg.embed:
        d["embed"] = {
            "provider": cfg.embed.provider,
            "model": cfg.embed.model,
            "dimensions": cfg.embed.dimensions,
            "api_key": cfg.embed.api_key,
            "base_url": cfg.embed.base_url,
        }
    d["compiler"] = {
        "max_parallel": cfg.compiler.max_parallel,
        "debounce_seconds": cfg.compiler.debounce_seconds,
        "summary_max_tokens": cfg.compiler.summary_max_tokens,
        "article_max_tokens": cfg.compiler.article_max_tokens,
        "auto_commit": cfg.compiler.auto_commit,
        "auto_lint": cfg.compiler.auto_lint,
        "mode": cfg.compiler.mode,
        "estimate_before": cfg.compiler.estimate_before,
        "batch_threshold": cfg.compiler.batch_threshold,
        "token_price_per_million": cfg.compiler.token_price_per_million,
        "page_threshold": cfg.compiler.page_threshold,
    }
    if cfg.compiler.prompt_cache is not None:
        d["compiler"]["prompt_cache"] = cfg.compiler.prompt_cache
    d["search"] = {
        "default_limit": cfg.search.default_limit,
    }
    d["linting"] = {
        "auto_fix_passes": cfg.linting.auto_fix_passes,
        "staleness_threshold_days": cfg.linting.staleness_threshold_days,
    }
    d["serve"] = {"transport": cfg.serve.transport, "port": cfg.serve.port}
    return d

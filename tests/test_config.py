# -*- coding: utf-8 -*-
"""
@author:XuMing(xuming624@qq.com)
@description: Tests for synth_wiki.config module.
"""
import os
import pytest
import yaml

from synth_wiki.config import (
    Config,
    VaultConfig,
    Source,
    APIConfig,
    CompilerConfig,
    load,
    load_global,
    list_projects,
    _expand_env_vars,
    _merge_project,
)
from synth_wiki import paths


# ---------------------------------------------------------------------------
# 1. Load valid config from global config (multi-project)
# ---------------------------------------------------------------------------

def test_load_valid_config(tmp_project_dir):
    cfg_path = paths.config_path()
    cfg = load(cfg_path, "test-wiki")
    assert cfg.project == "test-wiki"
    assert cfg.api.provider == "gemini"
    assert cfg.api.api_key == "fake_openai_key"
    assert len(cfg.sources) == 1
    assert cfg.compiler.auto_commit is False
    assert cfg.compiler.auto_lint is False
    assert cfg.serve.transport == "stdio"
    assert cfg.serve.port == 3333


def test_load_auto_selects_single_project(tmp_project_dir):
    cfg_path = paths.config_path()
    cfg = load(cfg_path)  # no project_name, auto-select
    assert cfg.project == "test-wiki"


def test_load_multiple_projects_requires_name(tmp_path, isolate_home):
    config = {
        "api": {"provider": "gemini", "api_key": "key"},
        "models": {"summarize": "m", "extract": "m", "write": "m", "lint": "m", "query": "m"},
        "projects": {
            "proj-a": {"sources": [{"path": "/a/raw"}], "output": "/a/wiki"},
            "proj-b": {"sources": [{"path": "/b/raw"}], "output": "/b/wiki"},
        }
    }
    cfg_path = paths.config_path()
    os.makedirs(os.path.dirname(cfg_path), exist_ok=True)
    with open(cfg_path, "w") as f:
        yaml.dump(config, f)

    with pytest.raises(ValueError, match="multiple projects"):
        load(cfg_path)

    cfg = load(cfg_path, "proj-a")
    assert cfg.project == "proj-a"
    assert cfg.output == "/a/wiki"


def test_load_project_not_found(tmp_path, isolate_home):
    config = {
        "api": {"provider": "", "api_key": ""},
        "projects": {
            "only": {"sources": [{"path": "/raw"}], "output": "/wiki"},
        }
    }
    cfg_path = paths.config_path()
    os.makedirs(os.path.dirname(cfg_path), exist_ok=True)
    with open(cfg_path, "w") as f:
        yaml.dump(config, f)

    with pytest.raises(ValueError, match="not found"):
        load(cfg_path, "missing")


# ---------------------------------------------------------------------------
# 2. Env var expansion
# ---------------------------------------------------------------------------

def test_env_var_expansion(tmp_path, monkeypatch):
    monkeypatch.setenv("MY_API_KEY", "secret-abc")
    config_yaml = """
version: 1
project: env-test
output: wiki
sources:
  - path: raw
api:
  provider: anthropic
  api_key: ${MY_API_KEY}
"""
    config_path = tmp_path / "config.yaml"
    config_path.write_text(config_yaml)
    cfg = load(str(config_path))
    assert cfg.api.api_key == "secret-abc"


def test_env_var_expansion_home(tmp_path):
    home = os.environ.get("HOME", "/tmp")
    config_yaml = f"""
version: 1
project: home-test
output: wiki
sources:
  - path: raw
api:
  provider: ""
  api_key: ""
description: home is ${{HOME}}
"""
    config_path = tmp_path / "config.yaml"
    config_path.write_text(config_yaml)
    cfg = load(str(config_path))
    assert cfg.description == f"home is {home}"


def test_env_var_missing_becomes_empty(tmp_path, monkeypatch):
    monkeypatch.delenv("NONEXISTENT_VAR_XYZ", raising=False)
    config_yaml = """
version: 1
project: test
output: wiki
sources:
  - path: raw
api:
  provider: ""
  api_key: ${NONEXISTENT_VAR_XYZ}
"""
    config_path = tmp_path / "config.yaml"
    config_path.write_text(config_yaml)
    cfg = load(str(config_path))
    assert cfg.api.api_key == ""


# ---------------------------------------------------------------------------
# 3. Validation errors
# ---------------------------------------------------------------------------

def test_validation_missing_project():
    cfg = Config.defaults()
    cfg.project = ""
    with pytest.raises(ValueError, match="'project' is required"):
        cfg.validate()


def test_validation_invalid_provider():
    cfg = Config.defaults()
    cfg.project = "test"
    cfg.api.provider = "unknown-provider"
    with pytest.raises(ValueError, match="invalid provider"):
        cfg.validate()


def test_validation_invalid_transport():
    cfg = Config.defaults()
    cfg.project = "test"
    cfg.serve.transport = "grpc"
    with pytest.raises(ValueError, match="invalid transport"):
        cfg.validate()


def test_validation_invalid_mode():
    cfg = Config.defaults()
    cfg.project = "test"
    cfg.compiler.mode = "turbo"
    with pytest.raises(ValueError, match="invalid compiler.mode"):
        cfg.validate()


def test_validation_empty_sources():
    cfg = Config.defaults()
    cfg.project = "test"
    cfg.sources = []
    with pytest.raises(ValueError, match="at least one source"):
        cfg.validate()


# ---------------------------------------------------------------------------
# 4. Defaults are applied for missing fields
# ---------------------------------------------------------------------------

def test_defaults(tmp_path):
    config_yaml = """
version: 1
project: minimal
sources:
  - path: docs
"""
    config_path = tmp_path / "config.yaml"
    config_path.write_text(config_yaml)
    cfg = load(str(config_path))
    assert cfg.output == "wiki"
    assert cfg.api.provider == ""
    assert cfg.compiler.max_parallel == 4
    assert cfg.compiler.debounce_seconds == 2
    assert cfg.compiler.summary_max_tokens == 2000
    assert cfg.compiler.article_max_tokens == 4000
    assert cfg.compiler.auto_commit is True
    assert cfg.compiler.auto_lint is True
    assert cfg.search.default_limit == 10
    assert cfg.serve.transport == "stdio"
    assert cfg.serve.port == 3333
    assert cfg.embed is None
    assert cfg.vault is None
    assert cfg.linting.staleness_threshold_days == 90
    assert cfg.linting.auto_fix_passes == ["consistency", "completeness", "style"]
    assert cfg.language == "zh-CN"


# ---------------------------------------------------------------------------
# 5. Save + reload roundtrip
# ---------------------------------------------------------------------------

def test_save_reload_roundtrip(tmp_project_dir):
    cfg_path = paths.config_path()
    cfg = load(cfg_path, "test-wiki")
    save_path = str(tmp_project_dir / "config_saved.yaml")
    cfg.save(save_path)
    cfg2 = load(save_path)
    assert cfg2.project == cfg.project
    assert cfg2.output == cfg.output
    assert cfg2.api.provider == cfg.api.provider
    assert cfg2.compiler.max_parallel == cfg.compiler.max_parallel
    assert cfg2.search.default_limit == cfg.search.default_limit
    assert cfg2.serve.port == cfg.serve.port
    assert len(cfg2.sources) == len(cfg.sources)
    assert cfg2.sources[0].path == cfg.sources[0].path


# ---------------------------------------------------------------------------
# 6. resolve_output and resolve_sources (no project_dir param)
# ---------------------------------------------------------------------------

def test_resolve_output_absolute(tmp_path):
    cfg = Config.defaults()
    cfg.project = "test"
    cfg.output = "/absolute/wiki"
    assert cfg.resolve_output() == "/absolute/wiki"


def test_resolve_sources_absolute():
    cfg = Config.defaults()
    cfg.project = "test"
    cfg.sources = [Source(path="/abs/path/raw")]
    sources = cfg.resolve_sources()
    assert sources == ["/abs/path/raw"]


def test_resolve_sources_multiple():
    cfg = Config.defaults()
    cfg.project = "test"
    cfg.sources = [Source(path="/src/a"), Source(path="/src/b")]
    sources = cfg.resolve_sources()
    assert sources == ["/src/a", "/src/b"]


# ---------------------------------------------------------------------------
# 7. is_vault_overlay
# ---------------------------------------------------------------------------

def test_is_vault_overlay_false():
    cfg = Config.defaults()
    assert cfg.is_vault_overlay is False


def test_is_vault_overlay_true():
    cfg = Config.defaults()
    cfg.vault = VaultConfig(root="/vault/root")
    assert cfg.is_vault_overlay is True


def test_vault_config_loaded(tmp_path):
    config_yaml = """
version: 1
project: vault-test
output: wiki
sources:
  - path: raw
vault:
  root: /my/vault
"""
    config_path = tmp_path / "config.yaml"
    config_path.write_text(config_yaml)
    cfg = load(str(config_path))
    assert cfg.is_vault_overlay is True
    assert cfg.vault.root == "/my/vault"


# ---------------------------------------------------------------------------
# 7.5 language config
# ---------------------------------------------------------------------------

def test_language_default():
    cfg = Config.defaults()
    assert cfg.language == "zh-CN"


def test_language_label():
    cfg = Config.defaults()
    assert "简体中文" in cfg.language_label


def test_language_loaded_from_yaml(tmp_path):
    config_yaml = """
version: 1
project: lang-test
output: wiki
language: en
sources:
  - path: raw
"""
    config_path = tmp_path / "config.yaml"
    config_path.write_text(config_yaml)
    cfg = load(str(config_path))
    assert cfg.language == "en"
    assert cfg.language_label == "English"


def test_language_missing_defaults_zh_cn(tmp_path):
    config_yaml = """
version: 1
project: no-lang
output: wiki
sources:
  - path: raw
"""
    config_path = tmp_path / "config.yaml"
    config_path.write_text(config_yaml)
    cfg = load(str(config_path))
    assert cfg.language == "zh-CN"


def test_language_save_roundtrip(tmp_path):
    cfg = Config.defaults()
    cfg.project = "rt-test"
    cfg.language = "ja"
    save_path = str(tmp_path / "config.yaml")
    cfg.save(save_path)
    cfg2 = load(save_path)
    assert cfg2.language == "ja"


# ---------------------------------------------------------------------------
# 8. prompt_cache_enabled
# ---------------------------------------------------------------------------

def test_prompt_cache_enabled_default():
    cfg = CompilerConfig()
    assert cfg.prompt_cache is None
    assert cfg.prompt_cache_enabled is True


def test_prompt_cache_enabled_explicit_true():
    cfg = CompilerConfig(prompt_cache=True)
    assert cfg.prompt_cache_enabled is True


def test_prompt_cache_enabled_explicit_false():
    cfg = CompilerConfig(prompt_cache=False)
    assert cfg.prompt_cache_enabled is False


def test_prompt_cache_loaded_from_yaml(tmp_path):
    config_yaml = """
version: 1
project: cache-test
output: wiki
sources:
  - path: raw
compiler:
  prompt_cache: false
"""
    config_path = tmp_path / "config.yaml"
    config_path.write_text(config_yaml)
    cfg = load(str(config_path))
    assert cfg.compiler.prompt_cache is False
    assert cfg.compiler.prompt_cache_enabled is False


# ---------------------------------------------------------------------------
# 9. Multi-project functions: load_global, list_projects, _merge_project
# ---------------------------------------------------------------------------

def test_load_global(tmp_path, isolate_home):
    config = {
        "api": {"provider": "gemini", "api_key": "key"},
        "models": {"summarize": "m", "extract": "m", "write": "m", "lint": "m", "query": "m"},
        "projects": {
            "proj-a": {"sources": [{"path": "/a/raw"}], "output": "/a/wiki"},
            "proj-b": {"sources": [{"path": "/b/raw"}], "output": "/b/wiki"},
        }
    }
    cfg_path = paths.config_path()
    os.makedirs(os.path.dirname(cfg_path), exist_ok=True)
    with open(cfg_path, "w") as f:
        yaml.dump(config, f)

    result = load_global(cfg_path)
    assert "proj-a" in result
    assert "proj-b" in result
    assert result["proj-a"].output == "/a/wiki"
    assert result["proj-b"].api.provider == "gemini"


def test_list_projects_multi(tmp_path, isolate_home):
    config = {
        "api": {"provider": "", "api_key": ""},
        "projects": {
            "a": {"sources": [{"path": "/a"}], "output": "/ao"},
            "b": {"sources": [{"path": "/b"}], "output": "/bo"},
        }
    }
    cfg_path = paths.config_path()
    os.makedirs(os.path.dirname(cfg_path), exist_ok=True)
    with open(cfg_path, "w") as f:
        yaml.dump(config, f)

    names = list_projects(cfg_path)
    assert set(names) == {"a", "b"}


def test_merge_project_deep_merges_api():
    global_data = {
        "api": {"provider": "gemini", "api_key": "global_key", "rate_limit": 10},
        "models": {"summarize": "m1"},
    }
    project_data = {
        "api": {"api_key": "project_key"},
        "sources": [{"path": "/src"}],
        "output": "/out",
    }
    merged = _merge_project(global_data, project_data, "test")
    assert merged["api"]["provider"] == "gemini"  # from global
    assert merged["api"]["api_key"] == "project_key"  # overridden
    assert merged["api"]["rate_limit"] == 10  # from global
    assert merged["output"] == "/out"


def test_merge_project_overrides_all_sections():
    """Project-level config can override every section: api, models, compiler, search, embed, linting, serve."""
    global_data = {
        "api": {"provider": "gemini", "api_key": "global_key", "base_url": ""},
        "models": {"summarize": "g-sum", "extract": "g-ext", "write": "g-wr", "lint": "g-li", "query": "g-q"},
        "compiler": {"max_parallel": 4, "auto_commit": True, "summary_max_tokens": 2000},
        "search": {"default_limit": 10},
        "embed": {"provider": "auto", "model": "global-embed"},
        "linting": {"staleness_threshold_days": 90},
        "serve": {"transport": "stdio", "port": 3333},
        "language": "zh-CN",
    }
    project_data = {
        "sources": [{"path": "/proj/raw"}],
        "output": "/proj/wiki",
        "api": {"provider": "openai-compatible", "base_url": "https://proj.api.com/v1"},
        "models": {"summarize": "proj-sum", "write": "proj-wr"},
        "compiler": {"max_parallel": 8, "auto_commit": False},
        "search": {"default_limit": 20},
        "embed": {"model": "proj-embed"},
        "linting": {"staleness_threshold_days": 30},
        "serve": {"port": 9999},
        "language": "en",
    }
    merged = _merge_project(global_data, project_data, "custom-proj")

    # api: provider overridden, api_key inherited, base_url overridden
    assert merged["api"]["provider"] == "openai-compatible"
    assert merged["api"]["api_key"] == "global_key"
    assert merged["api"]["base_url"] == "https://proj.api.com/v1"

    # models: summarize/write overridden, extract/lint/query inherited
    assert merged["models"]["summarize"] == "proj-sum"
    assert merged["models"]["write"] == "proj-wr"
    assert merged["models"]["extract"] == "g-ext"
    assert merged["models"]["lint"] == "g-li"
    assert merged["models"]["query"] == "g-q"

    # compiler: max_parallel/auto_commit overridden, summary_max_tokens inherited
    assert merged["compiler"]["max_parallel"] == 8
    assert merged["compiler"]["auto_commit"] is False
    assert merged["compiler"]["summary_max_tokens"] == 2000

    # search: overridden
    assert merged["search"]["default_limit"] == 20

    # embed: model overridden, provider inherited
    assert merged["embed"]["model"] == "proj-embed"
    assert merged["embed"]["provider"] == "auto"

    # linting: overridden
    assert merged["linting"]["staleness_threshold_days"] == 30

    # serve: port overridden, transport inherited
    assert merged["serve"]["port"] == 9999
    assert merged["serve"]["transport"] == "stdio"

    # language: scalar field, directly replaced
    assert merged["language"] == "en"

    # project name set
    assert merged["project"] == "custom-proj"


def test_project_override_full_load(tmp_path, isolate_home):
    """End-to-end: load a multi-project config where a project overrides api, models, compiler."""
    config_yaml = """
api:
  provider: gemini
  api_key: global_key
models:
  summarize: global-model
  extract: global-model
  write: global-model
  lint: global-model
  query: global-model
compiler:
  max_parallel: 4
  auto_commit: true
  summary_max_tokens: 2000
search:
  default_limit: 10
projects:
  proj-a:
    sources:
      - path: /a/raw
    output: /a/wiki
    api:
      provider: openai-compatible
      base_url: https://a.api.com/v1
    models:
      summarize: a-model
    compiler:
      max_parallel: 16
      auto_commit: false
  proj-b:
    sources:
      - path: /b/raw
    output: /b/wiki
    language: en
"""
    cfg_path = paths.config_path()
    os.makedirs(os.path.dirname(cfg_path), exist_ok=True)
    with open(cfg_path, "w") as f:
        f.write(config_yaml)

    cfg_a = load(cfg_path, "proj-a")
    assert cfg_a.api.provider == "openai-compatible"
    assert cfg_a.api.api_key == "global_key"  # inherited
    assert cfg_a.api.base_url == "https://a.api.com/v1"
    assert cfg_a.models.summarize == "a-model"
    assert cfg_a.models.extract == "global-model"  # inherited
    assert cfg_a.compiler.max_parallel == 16
    assert cfg_a.compiler.auto_commit is False
    assert cfg_a.compiler.summary_max_tokens == 2000  # inherited
    assert cfg_a.search.default_limit == 10  # inherited

    cfg_b = load(cfg_path, "proj-b")
    assert cfg_b.api.provider == "gemini"  # inherited
    assert cfg_b.api.api_key == "global_key"  # inherited
    assert cfg_b.models.summarize == "global-model"  # inherited
    assert cfg_b.compiler.max_parallel == 4  # inherited
    assert cfg_b.language == "en"  # overridden


# ---------------------------------------------------------------------------
# 10. extra_body config (openai-compatible)
# ---------------------------------------------------------------------------

def test_extra_body_loaded(tmp_path):
    config_yaml = """
version: 1
project: extra-test
output: wiki
sources:
  - path: raw
api:
  provider: openai-compatible
  api_key: test_key
  base_url: https://example.com/v3
  extra_body:
    thinking:
      type: disabled
"""
    config_path = tmp_path / "config.yaml"
    config_path.write_text(config_yaml)
    cfg = load(str(config_path))
    assert cfg.api.extra_body == {"thinking": {"type": "disabled"}}
    assert cfg.api.provider == "openai-compatible"

# -*- coding: utf-8 -*-
"""
@author:XuMing(xuming624@qq.com)
@description: Shared fixtures for tests.
"""
import os
import pytest
import yaml
from synth_wiki import paths


@pytest.fixture(autouse=True)
def isolate_home(tmp_path, monkeypatch):
    """Redirect ~/.synth_wiki/ to a temp dir for every test."""
    fake_home = str(tmp_path / "synth_wiki_home")
    monkeypatch.setattr(paths, "HOME_DIR", fake_home)
    os.makedirs(fake_home, exist_ok=True)
    return fake_home


@pytest.fixture
def tmp_project_dir(tmp_path, isolate_home):
    """Create a temporary project with config in the global home dir."""
    project_name = "test-wiki"
    source_dir = str(tmp_path / "raw")
    output_dir = str(tmp_path / "wiki")

    os.makedirs(source_dir, exist_ok=True)
    os.makedirs(os.path.join(output_dir, "summaries"), exist_ok=True)
    os.makedirs(os.path.join(output_dir, "concepts"), exist_ok=True)

    config = {
        "version": 1,
        "api": {"provider": "gemini", "api_key": "fake_key"},
        "models": {
            "summarize": "gemini-2.5-flash",
            "extract": "gemini-2.5-flash",
            "write": "gemini-2.5-flash",
            "lint": "gemini-2.5-flash",
            "query": "gemini-2.5-flash",
        },
        "compiler": {"max_parallel": 4, "auto_commit": False, "auto_lint": False},
        "search": {"hybrid_weight_bm25": 0.7, "hybrid_weight_vector": 0.3, "default_limit": 10},
        "serve": {"transport": "stdio", "port": 3333},
        "projects": {
            project_name: {
                "description": "test project",
                "sources": [{"path": source_dir, "type": "auto", "watch": True}],
                "output": output_dir,
            }
        }
    }

    cfg_path = paths.config_path()
    os.makedirs(os.path.dirname(cfg_path), exist_ok=True)
    with open(cfg_path, "w") as f:
        yaml.dump(config, f)

    # Create DB dir
    os.makedirs(os.path.join(isolate_home, "db"), exist_ok=True)
    os.makedirs(os.path.join(isolate_home, "manifests"), exist_ok=True)

    return tmp_path

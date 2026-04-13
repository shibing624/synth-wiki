# -*- coding: utf-8 -*-
"""
@author:XuMing(xuming624@qq.com)
@description: Centralized path management for ~/.synth_wiki/ home directory.

All persistent state (config, DB, manifests, compile state, lint logs) lives
under ~/.synth_wiki/ so target project directories stay clean.
"""
from __future__ import annotations
import os
from datetime import datetime, timezone

# The global home directory for synth-wiki state
HOME_DIR = os.path.join(os.path.expanduser("~"), ".synth_wiki")


def home_dir() -> str:
    """Return the global ~/.synth_wiki/ directory, creating it if needed."""
    os.makedirs(HOME_DIR, exist_ok=True)
    return HOME_DIR


def config_path() -> str:
    """Return path to the global config file: ~/.synth_wiki/config.yaml"""
    return os.path.join(home_dir(), "config.yaml")


def db_path(project: str) -> str:
    """Return path to the project's SQLite DB: ~/.synth_wiki/db/{project}.db"""
    db_dir = os.path.join(home_dir(), "db")
    os.makedirs(db_dir, exist_ok=True)
    return os.path.join(db_dir, f"{project}.db")


def manifest_path(project: str) -> str:
    """Return path to the project's manifest: ~/.synth_wiki/manifests/{project}.json"""
    mf_dir = os.path.join(home_dir(), "manifests")
    os.makedirs(mf_dir, exist_ok=True)
    return os.path.join(mf_dir, f"{project}.json")


def compile_state_path(project: str) -> str:
    """Return path to compile checkpoint: ~/.synth_wiki/state/{project}.json"""
    state_dir = os.path.join(home_dir(), "state")
    os.makedirs(state_dir, exist_ok=True)
    return os.path.join(state_dir, f"{project}.json")


def lintlog_dir(project: str) -> str:
    """Return path to lint log directory: ~/.synth_wiki/lintlog/{project}/"""
    log_dir = os.path.join(home_dir(), "lintlog", project)
    os.makedirs(log_dir, exist_ok=True)
    return log_dir


def ensure_home() -> None:
    """Create the home directory structure."""
    for sub in ["db", "manifests", "state", "lintlog"]:
        os.makedirs(os.path.join(HOME_DIR, sub), exist_ok=True)


def is_ignored(path: str, ignore: list[str]) -> bool:
    """Check if path matches any ignore pattern."""
    basename = os.path.basename(path)
    for pattern in ignore:
        if basename == pattern or pattern in path:
            return True
    return False


def utc_now_iso() -> str:
    """Return current UTC time as ISO 8601 string."""
    return datetime.now(timezone.utc).isoformat()

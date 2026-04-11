# -*- coding: utf-8 -*-
"""
@author:XuMing(xuming624@qq.com)
@description: Git operations via subprocess. | Git version control operations and wrapper utilities.
"""
from __future__ import annotations
import shutil
import subprocess


def is_available() -> bool:
    """Check if git is installed."""
    return shutil.which("git") is not None


def is_repo(dir: str) -> bool:
    """Check if directory is inside a git repository."""
    if not is_available():
        return False
    result = subprocess.run(
        ["git", "-C", dir, "rev-parse", "--git-dir"],
        capture_output=True, text=True,
    )
    return result.returncode == 0


def init(dir: str) -> None:
    """Initialize a new git repository."""
    if not is_available():
        return
    subprocess.run(["git", "-C", dir, "init"], capture_output=True, check=True)


def add(dir: str, *paths: str) -> None:
    """Stage files for commit. Silently ignores failures."""
    if not is_available():
        return
    cmd = ["git", "-C", dir, "add"] + list(paths)
    subprocess.run(cmd, capture_output=True)


def commit(dir: str, message: str) -> None:
    """Create a commit. Silently ignores failures."""
    if not is_available():
        return
    subprocess.run(
        ["git", "-C", dir, "commit", "-m", message],
        capture_output=True,
    )


def auto_commit(dir: str, message: str) -> None:
    """Stage all changes and commit. Silently ignores failures."""
    if not is_available() or not is_repo(dir):
        return
    add(dir, ".")
    commit(dir, message)


def status(dir: str) -> str:
    """Return short status output."""
    if not is_available():
        return ""
    result = subprocess.run(
        ["git", "-C", dir, "status", "--short"],
        capture_output=True, text=True,
    )
    return result.stdout.strip()


def last_commit(dir: str) -> tuple[str, str]:
    """Return (hash, message) of last commit. Returns ("", "") if no commits."""
    if not is_available() or not is_repo(dir):
        return "", ""
    result = subprocess.run(
        ["git", "-C", dir, "log", "-1", "--format=%h %s"],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        return "", ""
    line = result.stdout.strip()
    parts = line.split(" ", 1)
    if len(parts) == 2:
        return parts[0], parts[1]
    return line, ""

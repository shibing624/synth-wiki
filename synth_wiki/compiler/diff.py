# -*- coding: utf-8 -*-
"""
@author:XuMing(xuming624@qq.com)
@description: Source directory scanning and diffing against manifest.
"""
from __future__ import annotations
import hashlib
import os
from dataclasses import dataclass

from synth_wiki.config import Config
from synth_wiki.extract import detect_source_type
from synth_wiki.manifest import Manifest


@dataclass
class SourceInfo:
    path: str  # absolute path
    hash: str
    type: str
    size: int


@dataclass
class DiffResult:
    added: list[SourceInfo]
    modified: list[SourceInfo]
    removed: list[str]


def diff(cfg: Config, mf: Manifest) -> DiffResult:
    """Scan source directories and compare against manifest."""
    result = DiffResult(added=[], modified=[], removed=[])

    current: dict[str, SourceInfo] = {}
    source_paths = cfg.resolve_sources()

    for src_dir in source_paths:
        if not os.path.isdir(src_dir):
            continue
        for root, dirs, files in os.walk(src_dir):
            for fname in files:
                abs_path = os.path.join(root, fname)

                if _is_ignored(abs_path, cfg.ignore):
                    continue

                file_size = os.path.getsize(abs_path)
                file_h = file_hash(abs_path)

                current[abs_path] = SourceInfo(
                    path=abs_path,
                    hash=file_h,
                    type=detect_source_type(abs_path),
                    size=file_size,
                )

    # Compare against manifest
    for path, info in current.items():
        if path not in mf.sources:
            result.added.append(info)
        elif mf.sources[path].hash != info.hash:
            result.modified.append(info)

    # Find removed
    for path in mf.sources:
        if path not in current:
            result.removed.append(path)

    return result


def file_hash(path: str) -> str:
    """Compute SHA-256 hash of a file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return f"sha256:{h.hexdigest()}"


def _is_ignored(path: str, ignore: list[str]) -> bool:
    """Check if path matches any ignore pattern."""
    basename = os.path.basename(path)
    for pattern in ignore:
        if basename == pattern:
            return True
        if pattern in path:
            return True
    return False

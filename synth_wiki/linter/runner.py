# -*- coding: utf-8 -*-
"""
@author:XuMing(xuming624@qq.com)
@description: Lint runner and reporting.
"""
from __future__ import annotations
import json
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Protocol, Optional

from synth_wiki.storage import DB

_logger = logging.getLogger(__name__)


class LintPass(Protocol):
    def name(self) -> str: ...
    def run(self, ctx: LintContext) -> list[Finding]: ...
    def can_auto_fix(self) -> bool: ...
    def fix(self, ctx: LintContext, findings: list[Finding]) -> None: ...


@dataclass
class Finding:
    pass_name: str
    severity: str  # "error", "warning", "info"
    path: str = ""
    message: str = ""
    fix: str = ""


@dataclass
class LintContext:
    output_dir: str  # absolute path to output directory
    db_path: str = ""
    db: Optional[DB] = None

    def ensure_db(self):
        if self.db is not None: return
        if not self.db_path: return
        self.db = DB.open(self.db_path)


@dataclass
class LintResult:
    findings: list[Finding]
    pass_name: str
    duration: float = 0.0


class Runner:
    def __init__(self):
        from synth_wiki.linter.passes import (CompletenessPass, StylePass, OrphansPass,
            ConsistencyPass, ImputePass, StalenessPass, ContradictionDetectionPass)
        self._passes: list = [
            CompletenessPass(), StylePass(), OrphansPass(),
            ConsistencyPass(), ImputePass(), StalenessPass(),
            ContradictionDetectionPass(),
        ]

    def run(self, ctx: LintContext, pass_name: str = "", fix: bool = False) -> list[LintResult]:
        ctx.ensure_db()
        results = []
        for p in self._passes:
            if pass_name and p.name() != pass_name: continue
            start = time.time()
            try:
                findings = p.run(ctx)
            except Exception as e:
                _logger.warning("lint pass %s failed: %s", p.name(), e)
                continue
            duration = time.time() - start
            if fix and p.can_auto_fix() and findings:
                try: p.fix(ctx, findings)
                except Exception as e:
                    _logger.warning("lint auto-fix %s failed: %s", p.name(), e)
            results.append(LintResult(findings=findings, pass_name=p.name(), duration=duration))
        return results


def save_report(project_name: str, results: list[LintResult]) -> None:
    from synth_wiki import paths
    log_dir = paths.lintlog_dir(project_name)
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    json_path = os.path.join(log_dir, f"lint-{timestamp}.json")
    data = [{"pass": r.pass_name, "findings": [{"severity": f.severity, "message": f.message, "path": f.path} for f in r.findings]} for r in results]
    with open(json_path, "w") as f: json.dump(data, f, indent=2)


def format_findings(results: list[LintResult]) -> str:
    out = ""
    total = 0
    for r in results:
        if r.findings:
            out += f"{r.pass_name}: {len(r.findings)} findings\n"
            for f in r.findings:
                out += f"  [{f.severity}] {f.message}"
                if f.path: out += f" ({f.path})"
                out += "\n"
            total += len(r.findings)
    if total == 0: return "No issues found.\n"
    out += f"\nTotal: {total} findings\n"
    return out

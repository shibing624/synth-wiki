# -*- coding: utf-8 -*-
"""
@author:XuMing(xuming624@qq.com)
@description: Lint passes: completeness, style, orphans, consistency, impute, staleness.
"""
from __future__ import annotations
import os
import re
import time
from synth_wiki.linter.runner import Finding, LintContext
from synth_wiki.ontology import Store as OntologyStore


class CompletenessPass:
    def name(self) -> str: return "completeness"
    def can_auto_fix(self) -> bool: return False
    def fix(self, ctx, findings): pass

    def run(self, ctx: LintContext) -> list[Finding]:
        findings = []
        concepts_dir = os.path.join(ctx.output_dir, "concepts")
        if not os.path.isdir(concepts_dir): return findings
        link_re = re.compile(r'\[\[([^\]]+)\]\]')
        existing = {os.path.splitext(e)[0] for e in os.listdir(concepts_dir) if e.endswith(".md")}
        for entry in os.listdir(concepts_dir):
            if not entry.endswith(".md"): continue
            with open(os.path.join(concepts_dir, entry)) as f:
                content = f.read()
            for m in link_re.finditer(content):
                target = m.group(1)
                if target not in existing:
                    findings.append(Finding(pass_name="completeness", severity="warning",
                        path=os.path.join(concepts_dir, entry),
                        message=f"broken [[{target}]] -- no article exists"))
        return findings


class StylePass:
    def name(self) -> str: return "style"
    def can_auto_fix(self) -> bool: return True

    def run(self, ctx: LintContext) -> list[Finding]:
        findings = []
        concepts_dir = os.path.join(ctx.output_dir, "concepts")
        if not os.path.isdir(concepts_dir): return findings
        for entry in os.listdir(concepts_dir):
            if not entry.endswith(".md"): continue
            with open(os.path.join(concepts_dir, entry)) as f:
                content = f.read()
            if not content.startswith("---"):
                findings.append(Finding(pass_name="style", severity="warning",
                    path=os.path.join(concepts_dir, entry),
                    message="missing YAML frontmatter", fix="add frontmatter"))
        return findings

    def fix(self, ctx: LintContext, findings: list[Finding]) -> None:
        for f in findings:
            if f.fix != "add frontmatter": continue
            if not os.path.exists(f.path): continue
            with open(f.path) as fh:
                content = fh.read()
            name = os.path.splitext(os.path.basename(f.path))[0]
            fm = f"---\nconcept: {name}\nconfidence: low\n---\n\n"
            with open(f.path, "w") as fp: fp.write(fm + content)


class OrphansPass:
    def name(self) -> str: return "orphans"
    def can_auto_fix(self) -> bool: return False
    def fix(self, ctx, findings): pass

    def run(self, ctx: LintContext) -> list[Finding]:
        findings = []
        if not ctx.db: return findings
        from synth_wiki.ontology import Store as OntologyStore, Direction
        ont = OntologyStore(ctx.db)
        for e in ont.list_entities(""):
            if e.type == "source": continue
            rels = ont.get_relations(e.id, Direction.BOTH, "")
            if not rels:
                findings.append(Finding(pass_name="orphans", severity="info",
                    path=e.article_path, message=f"orphan entity {e.name!r} -- no relations"))
        return findings


class ConsistencyPass:
    def name(self) -> str: return "consistency"
    def can_auto_fix(self) -> bool: return False
    def fix(self, ctx, findings): pass

    def run(self, ctx: LintContext) -> list[Finding]:
        findings = []
        if not ctx.db: return findings
        cursor = ctx.db.read_db.cursor()
        cursor.execute("SELECT source_id, target_id FROM relations WHERE relation='contradicts'")
        for src, tgt in cursor.fetchall():
            findings.append(Finding(pass_name="consistency", severity="warning",
                message=f"contradiction: {src} contradicts {tgt}"))
        return findings


class ImputePass:
    def name(self) -> str: return "impute"
    def can_auto_fix(self) -> bool: return False
    def fix(self, ctx, findings): pass

    def run(self, ctx: LintContext) -> list[Finding]:
        findings = []
        concepts_dir = os.path.join(ctx.output_dir, "concepts")
        if not os.path.isdir(concepts_dir): return findings
        todo_re = re.compile(r'(?i)\[TODO\]|\[UNKNOWN\]|\[TBD\]')
        for entry in os.listdir(concepts_dir):
            if not entry.endswith(".md"): continue
            with open(os.path.join(concepts_dir, entry)) as f:
                content = f.read()
            matches = todo_re.findall(content)
            if matches:
                findings.append(Finding(pass_name="impute", severity="warning",
                    path=os.path.join(concepts_dir, entry),
                    message=f"contains {len(matches)} placeholder(s): {', '.join(matches)}"))
        return findings


class StalenessPass:
    def name(self) -> str: return "staleness"
    def can_auto_fix(self) -> bool: return False
    def fix(self, ctx, findings): pass

    def run(self, ctx: LintContext) -> list[Finding]:
        findings = []
        concepts_dir = os.path.join(ctx.output_dir, "concepts")
        if not os.path.isdir(concepts_dir): return findings
        threshold = 90 * 86400  # 90 days in seconds
        now = time.time()
        for entry in os.listdir(concepts_dir):
            if not entry.endswith(".md"): continue
            mtime = os.path.getmtime(os.path.join(concepts_dir, entry))
            age = now - mtime
            if age > threshold:
                findings.append(Finding(pass_name="staleness", severity="info",
                    path=os.path.join(concepts_dir, entry),
                    message=f"article is {int(age/86400)} days old"))
        return findings

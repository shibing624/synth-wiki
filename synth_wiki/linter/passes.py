# -*- coding: utf-8 -*-
"""
@author:XuMing(xuming624@qq.com)
@description: Lint passes: completeness, style, orphans, consistency, impute, staleness.
"""
from __future__ import annotations
import os
import re
import time

import yaml

from synth_wiki.linter.runner import Finding, LintContext


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


class ContradictionDetectionPass:
    """Detect cross-source contradictions by scanning articles that share sources.

    Unlike ConsistencyPass which only checks already-tagged 'contradicts' relations,
    this pass proactively finds articles covering the same sources with conflicting
    confidence levels or contradictory keywords.
    """
    def name(self) -> str: return "contradiction_detection"
    def can_auto_fix(self) -> bool: return False
    def fix(self, ctx, findings): pass

    def run(self, ctx: LintContext) -> list[Finding]:
        findings = []
        # Scan all article directories
        article_dirs = ["concepts", "entities", "comparisons"]
        articles: dict[str, dict] = {}  # slug -> {path, sources, confidence}
        for subdir in article_dirs:
            dir_path = os.path.join(ctx.output_dir, subdir)
            if not os.path.isdir(dir_path):
                continue
            for entry in os.listdir(dir_path):
                if not entry.endswith(".md"):
                    continue
                path = os.path.join(dir_path, entry)
                fm = _parse_frontmatter(path)
                slug = os.path.splitext(entry)[0]
                articles[slug] = {
                    "path": path,
                    "sources": fm.get("sources", []),
                    "confidence": fm.get("confidence", ""),
                    "contradictions": fm.get("contradictions", []),
                }

        # Build source -> articles index
        source_to_articles: dict[str, list[str]] = {}
        for slug, info in articles.items():
            for src in info["sources"]:
                source_to_articles.setdefault(src, []).append(slug)

        # Check for articles sharing sources with conflicting confidence
        checked = set()
        for src, slugs in source_to_articles.items():
            if len(slugs) < 2:
                continue
            for i, a in enumerate(slugs):
                for b in slugs[i + 1:]:
                    pair = tuple(sorted([a, b]))
                    if pair in checked:
                        continue
                    checked.add(pair)
                    conf_a = articles[a]["confidence"]
                    conf_b = articles[b]["confidence"]
                    if conf_a and conf_b and conf_a != conf_b:
                        if _is_conflicting_confidence(conf_a, conf_b):
                            findings.append(Finding(
                                pass_name="contradiction_detection",
                                severity="warning",
                                path=articles[a]["path"],
                                message=f"potential contradiction: '{a}' (confidence: {conf_a}) vs '{b}' (confidence: {conf_b}) share source '{src}'",
                            ))

        # Report already-marked contradictions that may need review
        for slug, info in articles.items():
            for contra in info["contradictions"]:
                if contra not in articles:
                    findings.append(Finding(
                        pass_name="contradiction_detection",
                        severity="info",
                        path=info["path"],
                        message=f"marked contradiction target '{contra}' not found in wiki",
                    ))
        return findings


def _is_conflicting_confidence(a: str, b: str) -> bool:
    """Check if two confidence levels are significantly conflicting."""
    levels = {"high": 3, "medium": 2, "low": 1}
    va = levels.get(a, 0)
    vb = levels.get(b, 0)
    return abs(va - vb) >= 2  # high vs low is a conflict


def _parse_frontmatter(path: str) -> dict:
    """Parse YAML frontmatter from a markdown file."""
    try:
        with open(path) as f:
            content = f.read(2000)
        if not content.startswith("---"):
            return {}
        end = content.find("---", 3)
        if end < 0:
            return {}
        fm = yaml.safe_load(content[3:end])
        if isinstance(fm, dict):
            return fm
    except (OSError, yaml.YAMLError):
        pass
    return {}

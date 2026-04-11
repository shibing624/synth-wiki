# -*- coding: utf-8 -*-
"""
@author:XuMing(xuming624@qq.com)
@description: Tests for synth_wiki.linter module.
"""
from __future__ import annotations
import json
import os
import time
import pytest

from synth_wiki import paths
from synth_wiki.storage import DB
from synth_wiki.ontology import Store as OntologyStore, Entity, Relation
from synth_wiki.linter.runner import (
    Finding, LintContext, LintResult, Runner, save_report, format_findings
)
from synth_wiki.linter.passes import (
    CompletenessPass, StylePass, OrphansPass, ConsistencyPass, ImputePass, StalenessPass
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def ctx(tmp_path):
    """Temp project with concepts dir. output_dir is absolute."""
    output_dir = str(tmp_path / "wiki")
    concepts_dir = os.path.join(output_dir, "concepts")
    os.makedirs(concepts_dir, exist_ok=True)
    return LintContext(output_dir=output_dir)


@pytest.fixture
def ctx_with_db(tmp_path):
    """Temp project with concepts dir and an open DB."""
    output_dir = str(tmp_path / "wiki")
    concepts_dir = os.path.join(output_dir, "concepts")
    os.makedirs(concepts_dir, exist_ok=True)
    db = DB.open(str(tmp_path / "test.db"))
    return LintContext(output_dir=output_dir, db=db), db


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def write_concept(ctx: LintContext, name: str, content: str) -> str:
    path = os.path.join(ctx.output_dir, "concepts", f"{name}.md")
    with open(path, "w") as f:
        f.write(content)
    return path


# ---------------------------------------------------------------------------
# 1. CompletenessPass: broken [[wikilink]] found
# ---------------------------------------------------------------------------

def test_completeness_broken_link(ctx):
    write_concept(ctx, "alpha", "See also [[beta]] for more details.")
    # beta.md does NOT exist
    findings = CompletenessPass().run(ctx)
    assert len(findings) == 1
    assert "beta" in findings[0].message
    assert findings[0].severity == "warning"
    assert findings[0].pass_name == "completeness"


def test_completeness_no_broken_links(ctx):
    write_concept(ctx, "alpha", "See also [[beta]] for more details.")
    write_concept(ctx, "beta", "Beta article.")
    findings = CompletenessPass().run(ctx)
    assert findings == []


# ---------------------------------------------------------------------------
# 2. StylePass: missing frontmatter detected
# ---------------------------------------------------------------------------

def test_style_missing_frontmatter(ctx):
    write_concept(ctx, "gamma", "No frontmatter here.\n")
    findings = StylePass().run(ctx)
    assert len(findings) == 1
    assert findings[0].severity == "warning"
    assert "frontmatter" in findings[0].message


def test_style_has_frontmatter(ctx):
    write_concept(ctx, "delta", "---\nconcept: delta\n---\n\nBody text.\n")
    findings = StylePass().run(ctx)
    assert findings == []


# ---------------------------------------------------------------------------
# 3. StylePass: auto-fix adds frontmatter
# ---------------------------------------------------------------------------

def test_style_autofix_adds_frontmatter(ctx):
    path = write_concept(ctx, "epsilon", "Body text without frontmatter.\n")
    findings = StylePass().run(ctx)
    assert len(findings) == 1
    StylePass().fix(ctx, findings)
    with open(path) as f:
        content = f.read()
    assert content.startswith("---")
    assert "concept: epsilon" in content
    assert "Body text without frontmatter." in content


# ---------------------------------------------------------------------------
# 4. OrphansPass: orphan entity found (entity with no relations)
# ---------------------------------------------------------------------------

def test_orphans_entity_no_relations(ctx_with_db):
    ctx, db = ctx_with_db
    ont = OntologyStore(db)
    ont.add_entity(Entity(id="e1", type="concept", name="LonelyNode"))
    findings = OrphansPass().run(ctx)
    assert len(findings) == 1
    assert "LonelyNode" in findings[0].message
    assert findings[0].severity == "info"


def test_orphans_entity_with_relation(ctx_with_db):
    ctx, db = ctx_with_db
    ont = OntologyStore(db)
    ont.add_entity(Entity(id="e1", type="concept", name="A"))
    ont.add_entity(Entity(id="e2", type="concept", name="B"))
    ont.add_relation(Relation(id="r1", source_id="e1", target_id="e2", relation="extends"))
    findings = OrphansPass().run(ctx)
    # Both e1 and e2 have relations now
    assert findings == []


def test_orphans_skips_source_type(ctx_with_db):
    ctx, db = ctx_with_db
    ont = OntologyStore(db)
    ont.add_entity(Entity(id="s1", type="source", name="SomePaper"))
    findings = OrphansPass().run(ctx)
    assert findings == []


# ---------------------------------------------------------------------------
# 5. ConsistencyPass: contradiction found
# ---------------------------------------------------------------------------

def test_consistency_contradiction(ctx_with_db):
    ctx, db = ctx_with_db
    ont = OntologyStore(db)
    ont.add_entity(Entity(id="c1", type="claim", name="ClaimA"))
    ont.add_entity(Entity(id="c2", type="claim", name="ClaimB"))
    ont.add_relation(Relation(id="r1", source_id="c1", target_id="c2", relation="contradicts"))
    findings = ConsistencyPass().run(ctx)
    assert len(findings) == 1
    assert "c1" in findings[0].message
    assert "c2" in findings[0].message
    assert findings[0].severity == "warning"


def test_consistency_no_contradictions(ctx_with_db):
    ctx, db = ctx_with_db
    ont = OntologyStore(db)
    ont.add_entity(Entity(id="c1", type="concept", name="A"))
    ont.add_entity(Entity(id="c2", type="concept", name="B"))
    ont.add_relation(Relation(id="r1", source_id="c1", target_id="c2", relation="extends"))
    findings = ConsistencyPass().run(ctx)
    assert findings == []


# ---------------------------------------------------------------------------
# 6. ImputePass: [TODO] placeholder found
# ---------------------------------------------------------------------------

def test_impute_todo_found(ctx):
    write_concept(ctx, "zeta", "This section is [TODO] and [UNKNOWN].\n")
    findings = ImputePass().run(ctx)
    assert len(findings) == 1
    assert "2 placeholder" in findings[0].message
    assert findings[0].severity == "warning"


def test_impute_tbd_found(ctx):
    write_concept(ctx, "eta", "Status: [TBD]\n")
    findings = ImputePass().run(ctx)
    assert len(findings) == 1


def test_impute_no_placeholders(ctx):
    write_concept(ctx, "theta", "Everything is known.\n")
    findings = ImputePass().run(ctx)
    assert findings == []


# ---------------------------------------------------------------------------
# 7. StalenessPass: old article found (mtime 100 days ago)
# ---------------------------------------------------------------------------

def test_staleness_old_article(ctx):
    path = write_concept(ctx, "iota", "Old content.\n")
    # Set mtime to 100 days ago
    old_time = time.time() - 100 * 86400
    os.utime(path, (old_time, old_time))
    findings = StalenessPass().run(ctx)
    assert len(findings) == 1
    assert "100" in findings[0].message
    assert findings[0].severity == "info"


def test_staleness_fresh_article(ctx):
    write_concept(ctx, "kappa", "Fresh content.\n")
    # mtime is now (just created), well within 90 days
    findings = StalenessPass().run(ctx)
    assert findings == []


# ---------------------------------------------------------------------------
# 8. Runner runs all passes
# ---------------------------------------------------------------------------

def test_runner_runs_all_passes(ctx):
    write_concept(ctx, "lambda", "Has [[broken]] link and no frontmatter. [TODO]\n")
    runner = Runner()
    results = runner.run(ctx)
    pass_names = {r.pass_name for r in results}
    assert "completeness" in pass_names
    assert "style" in pass_names
    assert "impute" in pass_names
    assert "orphans" in pass_names
    assert "consistency" in pass_names
    assert "staleness" in pass_names


# ---------------------------------------------------------------------------
# 9. Runner runs single pass by name
# ---------------------------------------------------------------------------

def test_runner_single_pass(ctx):
    write_concept(ctx, "mu", "No frontmatter.\n")
    runner = Runner()
    results = runner.run(ctx, pass_name="style")
    assert len(results) == 1
    assert results[0].pass_name == "style"
    assert len(results[0].findings) == 1


def test_runner_single_pass_no_match(ctx):
    runner = Runner()
    results = runner.run(ctx, pass_name="nonexistent")
    assert results == []


# ---------------------------------------------------------------------------
# 10. save_report writes file to lint log dir
# ---------------------------------------------------------------------------

def test_save_report():
    results = [
        LintResult(findings=[Finding(pass_name="style", severity="warning", message="missing frontmatter")],
                   pass_name="style", duration=0.01),
    ]
    save_report("test-lint-project", results)
    log_dir = paths.lintlog_dir("test-lint-project")
    files = [f for f in os.listdir(log_dir) if f.startswith("lint-") and f.endswith(".json")]
    assert len(files) == 1
    with open(os.path.join(log_dir, files[0])) as f:
        data = json.load(f)
    assert data[0]["pass"] == "style"
    assert data[0]["findings"][0]["severity"] == "warning"


# ---------------------------------------------------------------------------
# 11. format_findings produces readable output
# ---------------------------------------------------------------------------

def test_format_findings_with_issues():
    results = [
        LintResult(
            findings=[
                Finding(pass_name="style", severity="warning", message="missing frontmatter", path="wiki/concepts/foo.md"),
                Finding(pass_name="style", severity="warning", message="missing frontmatter", path="wiki/concepts/bar.md"),
            ],
            pass_name="style",
        ),
        LintResult(findings=[], pass_name="completeness"),
    ]
    output = format_findings(results)
    assert "style: 2 findings" in output
    assert "[warning]" in output
    assert "foo.md" in output
    assert "Total: 2 findings" in output


def test_format_findings_no_issues():
    results = [LintResult(findings=[], pass_name="style")]
    output = format_findings(results)
    assert output == "No issues found.\n"

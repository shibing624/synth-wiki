# -*- coding: utf-8 -*-
"""
@author:XuMing(xuming624@qq.com)
@description: Tests for new features: entity/comparison types, SCHEMA.md, index.md,
    page threshold filtering, contradiction detection.
"""
from __future__ import annotations
import os
import pytest
import yaml

from synth_wiki.compiler.concepts import (
    ExtractedConcept, filter_by_source_count, deduplicate_concepts,
)
from synth_wiki.compiler.index import generate_schema, generate_index
from synth_wiki.compiler.write import _TYPE_TO_SUBDIR, _DEFAULT_SUBDIR
from synth_wiki.linter.runner import LintContext, Runner
from synth_wiki.linter.passes import ContradictionDetectionPass


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def write_article(output_dir: str, subdir: str, name: str, content: str) -> str:
    dir_path = os.path.join(output_dir, subdir)
    os.makedirs(dir_path, exist_ok=True)
    path = os.path.join(dir_path, f"{name}.md")
    with open(path, "w") as f:
        f.write(content)
    return path


# ---------------------------------------------------------------------------
# 1. Entity/Comparison type routing
# ---------------------------------------------------------------------------

class TestTypeRouting:
    def test_entity_routes_to_entities_dir(self):
        assert _TYPE_TO_SUBDIR.get("entity") == "entities"

    def test_comparison_routes_to_comparisons_dir(self):
        assert _TYPE_TO_SUBDIR.get("comparison") == "comparisons"

    def test_concept_uses_default_dir(self):
        assert _TYPE_TO_SUBDIR.get("concept") is None
        assert _DEFAULT_SUBDIR == "concepts"

    def test_technique_uses_default_dir(self):
        assert _TYPE_TO_SUBDIR.get("technique") is None


# ---------------------------------------------------------------------------
# 2. SCHEMA.md generation
# ---------------------------------------------------------------------------

class TestSchemaGeneration:
    def test_generates_schema(self, tmp_path):
        output_dir = str(tmp_path / "wiki")
        os.makedirs(output_dir, exist_ok=True)
        path = generate_schema(output_dir, description="Test wiki", page_threshold=2)
        assert os.path.exists(path)
        with open(path) as f:
            content = f.read()
        assert "# Wiki Schema" in content
        assert "Test wiki" in content
        assert "2+ sources" in content

    def test_does_not_overwrite_existing(self, tmp_path):
        output_dir = str(tmp_path / "wiki")
        os.makedirs(output_dir, exist_ok=True)
        schema_path = os.path.join(output_dir, "SCHEMA.md")
        with open(schema_path, "w") as f:
            f.write("# Custom Schema\n")
        generate_schema(output_dir)
        with open(schema_path) as f:
            content = f.read()
        assert content == "# Custom Schema\n"

    def test_default_description(self, tmp_path):
        output_dir = str(tmp_path / "wiki")
        os.makedirs(output_dir, exist_ok=True)
        generate_schema(output_dir)
        with open(os.path.join(output_dir, "SCHEMA.md")) as f:
            content = f.read()
        assert "synth-wiki" in content


# ---------------------------------------------------------------------------
# 3. index.md generation
# ---------------------------------------------------------------------------

class TestIndexGeneration:
    def test_generates_index_with_articles(self, tmp_path):
        output_dir = str(tmp_path / "wiki")
        write_article(output_dir, "concepts", "attention",
                       "---\nconcept: attention\n---\nContent about attention.")
        write_article(output_dir, "entities", "openai",
                       "---\nconcept: openai\n---\nOpenAI is a company.")
        write_article(output_dir, "comparisons", "gpt-vs-bert",
                       "---\nconcept: gpt-vs-bert\n---\nComparison of GPT and BERT.")
        path = generate_index(output_dir, project_name="test-project")
        assert os.path.exists(path)
        with open(path) as f:
            content = f.read()
        assert "# Wiki Index" in content
        assert "Total pages: 3" in content
        assert "[[attention]]" in content
        assert "[[openai]]" in content
        assert "[[gpt-vs-bert]]" in content
        assert "## Entities" in content
        assert "## Concepts" in content
        assert "## Comparisons" in content

    def test_empty_wiki(self, tmp_path):
        output_dir = str(tmp_path / "wiki")
        os.makedirs(output_dir, exist_ok=True)
        path = generate_index(output_dir)
        with open(path) as f:
            content = f.read()
        assert "Total pages: 0" in content
        assert "*(none yet)*" in content


# ---------------------------------------------------------------------------
# 4. Page threshold (source count) filtering
# ---------------------------------------------------------------------------

class TestPageThreshold:
    def test_no_filter_when_threshold_1(self):
        concepts = [
            ExtractedConcept(name="a", sources=["s1.md"]),
            ExtractedConcept(name="b", sources=["s1.md", "s2.md"]),
        ]
        result = filter_by_source_count(concepts, 1)
        assert len(result) == 2

    def test_filter_single_source_when_threshold_2(self):
        concepts = [
            ExtractedConcept(name="single", sources=["s1.md"]),
            ExtractedConcept(name="multi", sources=["s1.md", "s2.md"]),
            ExtractedConcept(name="triple", sources=["s1.md", "s2.md", "s3.md"]),
        ]
        result = filter_by_source_count(concepts, 2)
        assert len(result) == 2
        assert {c.name for c in result} == {"multi", "triple"}

    def test_filter_all_below_threshold(self):
        concepts = [
            ExtractedConcept(name="a", sources=["s1.md"]),
            ExtractedConcept(name="b", sources=["s2.md"]),
        ]
        result = filter_by_source_count(concepts, 3)
        assert result == []

    def test_dedup_then_filter(self):
        """After dedup merges sources, concepts may pass threshold."""
        concepts = [
            ExtractedConcept(name="test", sources=["a.md"]),
            ExtractedConcept(name="test", sources=["b.md"]),
        ]
        deduped = deduplicate_concepts(concepts)
        assert len(deduped) == 1
        assert len(deduped[0].sources) == 2
        result = filter_by_source_count(deduped, 2)
        assert len(result) == 1


# ---------------------------------------------------------------------------
# 5. ContradictionDetectionPass
# ---------------------------------------------------------------------------

class TestContradictionDetection:
    def test_detects_conflicting_confidence(self, tmp_path):
        output_dir = str(tmp_path / "wiki")
        write_article(output_dir, "concepts", "alpha",
                       "---\nconcept: alpha\nconfidence: high\nsources:\n  - paper.md\n---\nAlpha content.")
        write_article(output_dir, "concepts", "beta",
                       "---\nconcept: beta\nconfidence: low\nsources:\n  - paper.md\n---\nBeta content.")
        ctx = LintContext(output_dir=output_dir)
        findings = ContradictionDetectionPass().run(ctx)
        assert len(findings) == 1
        assert "potential contradiction" in findings[0].message
        assert findings[0].severity == "warning"

    def test_no_contradiction_same_confidence(self, tmp_path):
        output_dir = str(tmp_path / "wiki")
        write_article(output_dir, "concepts", "alpha",
                       "---\nconcept: alpha\nconfidence: high\nsources:\n  - paper.md\n---\n")
        write_article(output_dir, "concepts", "beta",
                       "---\nconcept: beta\nconfidence: high\nsources:\n  - paper.md\n---\n")
        ctx = LintContext(output_dir=output_dir)
        findings = ContradictionDetectionPass().run(ctx)
        assert findings == []

    def test_no_contradiction_medium_vs_high(self, tmp_path):
        """medium vs high is only 1 level apart, not flagged."""
        output_dir = str(tmp_path / "wiki")
        write_article(output_dir, "concepts", "alpha",
                       "---\nconcept: alpha\nconfidence: medium\nsources:\n  - paper.md\n---\n")
        write_article(output_dir, "concepts", "beta",
                       "---\nconcept: beta\nconfidence: high\nsources:\n  - paper.md\n---\n")
        ctx = LintContext(output_dir=output_dir)
        findings = ContradictionDetectionPass().run(ctx)
        assert findings == []

    def test_missing_contradiction_target(self, tmp_path):
        output_dir = str(tmp_path / "wiki")
        write_article(output_dir, "concepts", "alpha",
                       "---\nconcept: alpha\ncontradictions:\n  - nonexistent\n---\n")
        ctx = LintContext(output_dir=output_dir)
        findings = ContradictionDetectionPass().run(ctx)
        assert len(findings) == 1
        assert "not found" in findings[0].message

    def test_scans_entities_and_comparisons(self, tmp_path):
        output_dir = str(tmp_path / "wiki")
        write_article(output_dir, "entities", "company-a",
                       "---\nconcept: company-a\nconfidence: high\nsources:\n  - report.md\n---\n")
        write_article(output_dir, "comparisons", "a-vs-b",
                       "---\nconcept: a-vs-b\nconfidence: low\nsources:\n  - report.md\n---\n")
        ctx = LintContext(output_dir=output_dir)
        findings = ContradictionDetectionPass().run(ctx)
        assert len(findings) == 1
        assert "potential contradiction" in findings[0].message

    def test_runner_includes_contradiction_detection(self, tmp_path):
        output_dir = str(tmp_path / "wiki")
        os.makedirs(os.path.join(output_dir, "concepts"), exist_ok=True)
        ctx = LintContext(output_dir=output_dir)
        runner = Runner()
        results = runner.run(ctx)
        pass_names = {r.pass_name for r in results}
        assert "contradiction_detection" in pass_names

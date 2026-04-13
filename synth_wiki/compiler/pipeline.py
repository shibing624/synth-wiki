# -*- coding: utf-8 -*-
"""
@author:XuMing(xuming624@qq.com)
@description: Full compile orchestrator: diff -> summarize -> concepts -> write -> synthesize -> overview.
"""
from __future__ import annotations
import json
import os
import sys
from dataclasses import dataclass, field, asdict
from typing import Optional

from tqdm import tqdm

from synth_wiki import log
from synth_wiki import paths
from synth_wiki.config import load as load_config
from synth_wiki.compiler.diff import diff, SourceInfo, DiffResult
from synth_wiki.compiler.summarize import summarize, SummaryResult
from synth_wiki.compiler.concepts import extract_concepts, ExtractedConcept
from synth_wiki.compiler.write import write_articles, ArticleResult
from synth_wiki.compiler.images import extract_images
from synth_wiki.compiler.index import generate_schema, generate_index
from synth_wiki.compiler.synthesize import generate_syntheses
from synth_wiki.compiler.overview import generate_overview
from synth_wiki.embed import new_from_config
from synth_wiki import git
from synth_wiki.llm.client import Client
from synth_wiki.llm.cost import CostTracker, CostReport, format_report
from synth_wiki.manifest import load as load_manifest
from synth_wiki.memory import Store as MemoryStore, Entry
from synth_wiki.ontology import Store as OntologyStore
from synth_wiki.paths import utc_now_iso
from synth_wiki.prompts import load_from_dir
from synth_wiki.storage import DB
from synth_wiki.vectors import Store as VectorStore


@dataclass
class CompileOpts:
    dry_run: bool = False
    fresh: bool = False
    batch: bool = False
    no_cache: bool = False
    tracker: Optional[CostTracker] = None
    config_path: str = ""


@dataclass
class CompileResult:
    added: int = 0
    modified: int = 0
    removed: int = 0
    summarized: int = 0
    concepts_extracted: int = 0
    articles_written: int = 0
    syntheses_written: int = 0
    errors: int = 0
    cost_report: Optional[CostReport] = None


@dataclass
class CompileState:
    compile_id: str = ""
    started_at: str = ""
    pass_num: int = 1
    completed: list[str] = field(default_factory=list)
    pending: list[str] = field(default_factory=list)
    failed: list[dict] = field(default_factory=list)


def compile(project_name: str, opts: CompileOpts = None) -> CompileResult:
    """Run the full compile pipeline.

    Args:
        project_name: The project name as defined in ~/.synth_wiki/config.yaml.
        opts: Compile options.
    """
    if opts is None:
        opts = CompileOpts()
    result = CompileResult()

    cfg_path = opts.config_path or paths.config_path()
    cfg = load_config(cfg_path, project_name)

    output_dir = cfg.resolve_output()
    source_dirs = cfg.resolve_sources()

    # Ensure output directories exist
    for sub in ["summaries", "concepts", "entities", "comparisons", "connections", "syntheses", "outputs", "images", "archive"]:
        os.makedirs(os.path.join(output_dir, sub), exist_ok=True)

    prompts_dir = os.path.join(output_dir, "prompts")
    if os.path.isdir(prompts_dir):
        load_from_dir(prompts_dir)

    mf_path = paths.manifest_path(project_name)
    mf = load_manifest(mf_path)

    state_path = paths.compile_state_path(project_name)
    state = None
    if not opts.fresh:
        state = _load_state(state_path)

    diff_result = diff(cfg, mf)
    result.added = len(diff_result.added)
    result.modified = len(diff_result.modified)
    result.removed = len(diff_result.removed)

    total_changes = result.added + result.modified + result.removed
    if total_changes == 0:
        print("No changes detected.", file=sys.stderr)
        return result

    print(f"Diff: +{result.added} added, ~{result.modified} modified, -{result.removed} removed", file=sys.stderr)

    if opts.dry_run:
        return result

    client = Client(cfg.api.provider, cfg.api.api_key, cfg.api.base_url, cfg.api.rate_limit, cfg.api.extra_body)

    tracker = opts.tracker or CostTracker(cfg.api.provider, cfg.compiler.token_price_per_million)
    client.set_tracker(tracker)

    db_p = paths.db_path(project_name)
    db = DB.open(db_p)
    mem_store = MemoryStore(db_p)
    vec_store = VectorStore(db)
    ont_store = OntologyStore(db)
    embedder = new_from_config(cfg)

    if state is None:
        state = CompileState(
            compile_id=utc_now_iso().replace(":", "").replace("-", "")[:15],
            started_at=_now(),
            pass_num=1,
        )

    try:
        to_process = diff_result.added + diff_result.modified

        model = cfg.models.summarize or "gpt-4o-mini"
        max_tokens = cfg.compiler.summary_max_tokens or 2000
        client.set_pass("summarize")

        summaries = summarize(output_dir, to_process, client, model, max_tokens, cfg.compiler.max_parallel, cfg.language)

        embed_bar = tqdm(summaries, desc="Indexing summaries", unit="file", dynamic_ncols=True,
                         bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}]")
        for sr in embed_bar:
            if sr.error is not None:
                result.errors += 1
                state.failed.append({"path": sr.source_path, "error": str(sr.error)})
                continue
            result.summarized += 1

            for s in to_process:
                if s.path == sr.source_path:
                    if sr.source_path not in mf.sources:
                        mf.add_source(s.path, s.hash, s.type, s.size)
                    else:
                        mf.sources[sr.source_path].hash = s.hash
                    break
            mf.mark_compiled(sr.source_path, sr.summary_path, sr.concepts)

            try:
                mem_store.add(Entry(id=sr.source_path, content=sr.summary,
                                   tags=[sr.source_path.split(".")[-1]], article_path=sr.summary_path))
            except Exception as e:
                log.warn("embedding failed", source=sr.source_path, error=str(e))

            if embedder:
                try:
                    vec = embedder.embed(sr.summary)
                    vec_store.upsert(sr.source_path, vec)
                except Exception as e:
                    log.warn("embedding failed", source=sr.source_path, error=str(e))

            state.completed.append(sr.source_path)

        successful = [s for s in summaries if s.error is None and s.summary]
        if successful:
            extract_model = cfg.models.extract or model
            client.set_pass("extract")
            concepts = extract_concepts(successful, mf.concepts, client, extract_model, cfg.language, cfg.compiler.max_parallel, cfg.compiler.page_threshold)
            result.concepts_extracted = len(concepts)

            for c in concepts:
                mf.add_concept(c.name, os.path.join(output_dir, "concepts", c.name + ".md"), c.sources)

            if concepts:
                write_model = cfg.models.write or model
                article_max = cfg.compiler.article_max_tokens or 4000
                client.set_pass("write")
                articles = write_articles(output_dir, concepts, client, write_model,
                                         article_max, cfg.compiler.max_parallel,
                                         mem_store, vec_store, ont_store, embedder, cfg.language)
                for ar in articles:
                    if ar.error is not None:
                        result.errors += 1
                    else:
                        result.articles_written += 1

        # Pass 4: Synthesize cross-source insights
        if successful and concepts:
            synth_model = cfg.models.write or model
            synth_max = cfg.compiler.article_max_tokens or 4000
            client.set_pass("synthesize")
            syntheses = generate_syntheses(
                output_dir, successful, concepts, client, synth_model,
                synth_max, cfg.compiler.max_parallel,
                mem_store, vec_store, embedder, cfg.language,
            )
            for sr in syntheses:
                if sr.error is not None:
                    result.errors += 1
                else:
                    result.syntheses_written += 1
            if result.syntheses_written > 0:
                print(f"Syntheses: {result.syntheses_written} cross-source pages", file=sys.stderr)

        # Generate overview
        overview_model = cfg.models.write or model
        client.set_pass("overview")
        generate_overview(output_dir, client, overview_model, cfg.project, cfg.language)

        extract_images(output_dir, to_process)

        for removed in diff_result.removed:
            mf.remove_source(removed)
            mem_store.delete(removed)
            vec_store.delete(removed)

        mf.save(mf_path)

        _write_changelog(output_dir, result)

        generate_schema(output_dir, description=cfg.description,
                        page_threshold=cfg.compiler.page_threshold)
        generate_index(output_dir, project_name=cfg.project)

        if result.errors == 0:
            try:
                os.remove(state_path)
            except FileNotFoundError:
                pass
        else:
            _save_state(state_path, state)

        if cfg.compiler.auto_commit and source_dirs:
            # Auto-commit in the first source directory's parent (if it's a git repo)
            for src_dir in source_dirs:
                parent = os.path.dirname(src_dir) if not os.path.isdir(os.path.join(src_dir, ".git")) else src_dir
                if git.is_repo(parent):
                    git.auto_commit(parent, f"compile: +{result.added} sources, {result.concepts_extracted} concepts, {result.articles_written} articles")
                    break

        cost_report = tracker.report()
        if cost_report.total_tokens > 0:
            result.cost_report = cost_report
            print(f"Cost: {cost_report.total_tokens:,} tokens, ${cost_report.estimated_cost:.4f}", file=sys.stderr)

    finally:
        mem_store.close()
        db.close()

    return result


def _load_state(path: str) -> Optional[CompileState]:
    try:
        with open(path) as f:
            data = json.load(f)
        return CompileState(**{k: data[k] for k in CompileState.__dataclass_fields__ if k in data})
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def _save_state(path: str, state: CompileState) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(asdict(state), f, indent=2)


def _write_changelog(output_dir: str, result: CompileResult) -> None:
    changelog_path = os.path.join(output_dir, "CHANGELOG.md")
    entry = (
        f"## {_now()}\n\n"
        f"- Added: {result.added} sources\n"
        f"- Summarized: {result.summarized}\n"
        f"- Concepts: {result.concepts_extracted}\n"
        f"- Articles: {result.articles_written}\n"
        f"- Syntheses: {result.syntheses_written}\n"
        f"- Errors: {result.errors}\n\n"
    )
    header = "# CHANGELOG\n\nCompilation history for synth-wiki.\n\n"
    if os.path.exists(changelog_path):
        with open(changelog_path) as f:
            existing = f.read()
        if "## " in existing:
            idx = existing.index("## ")
            content = existing[idx:]
            with open(changelog_path, "w") as f:
                f.write(header + entry + content)
        else:
            with open(changelog_path, "w") as f:
                f.write(header + entry)
    else:
        os.makedirs(os.path.dirname(changelog_path), exist_ok=True)
        with open(changelog_path, "w") as f:
            f.write(header + entry)


def _now() -> str:
    return utc_now_iso()

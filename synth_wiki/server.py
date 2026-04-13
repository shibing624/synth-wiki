# -*- coding: utf-8 -*-
"""
@author:XuMing(xuming624@qq.com)
@description: MCP (Model Context Protocol) server for synth-wiki.

Exposes wiki search, query, ingest, compile, lint, and status as MCP tools.
Runs via stdio or SSE transport.

Usage:
    synth-wiki serve                     # stdio (default, for Claude Code / Cursor)
    synth-wiki serve --transport sse     # SSE (for web clients)
"""
from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Literal

from mcp.server.fastmcp import FastMCP

from synth_wiki import paths
from synth_wiki.config import Config, load as load_config


@contextmanager
def _search_context(project: str, cfg_path: str):
    """Open DB/MemoryStore/VectorStore/Searcher with guaranteed cleanup."""
    from synth_wiki.storage import DB
    from synth_wiki.memory import Store as MemoryStore
    from synth_wiki.vectors import Store as VectorStore
    from synth_wiki.hybrid import Searcher

    db_p = paths.db_path(project)
    db = DB.open(db_p)
    mem = MemoryStore(db_p)
    vec = VectorStore(db)
    try:
        yield mem, vec, Searcher(mem, vec)
    finally:
        mem.close()
        db.close()


def _do_search(project: str, cfg: Config, cfg_path: str,
               query: str, tags: list[str], limit: int):
    """Shared search logic for search tool and query tool."""
    from synth_wiki.hybrid import SearchOpts
    from synth_wiki.embed import new_from_config

    query_vec = None
    embedder = new_from_config(cfg)
    if embedder:
        query_vec = embedder.embed(query)

    with _search_context(project, cfg_path) as (mem, vec, searcher):
        return searcher.search(SearchOpts(query=query, tags=tags, limit=limit), query_vec)


def _do_query(project: str, cfg: Config, cfg_path: str, question: str,
              archive: bool = False) -> str:
    """Shared Q&A logic for query tool and CLI query command."""
    from synth_wiki.llm.client import Client, Message, CallOpts

    results = _do_search(project, cfg, cfg_path, question, [], 5)
    if not results:
        return "No relevant articles found in the wiki."

    context_parts = []
    for r in results:
        snippet = r.content[:500]
        context_parts.append(f"### {r.article_path}\n{snippet}")
    context = "\n\n".join(context_parts)

    client = Client(cfg.api.provider, cfg.api.api_key, cfg.api.base_url,
                    cfg.api.rate_limit, cfg.api.extra_body)
    model = cfg.models.query or cfg.models.write or "gpt-4o-mini"

    resp = client.chat_completion([
        Message(role="system", content=(
            "You are a wiki assistant. Answer the user's question based on the wiki articles provided. "
            "Cite the articles you use with [[article-name]] wikilinks. "
            f"Answer in {cfg.language_label}."
        )),
        Message(role="user", content=f"Wiki context:\n{context}\n\nQuestion: {question}"),
    ], CallOpts(model=model, max_tokens=2000))

    sources = ", ".join(r.article_path for r in results[:3])
    answer = f"{resp.content}\n\n---\nSources: {sources}"

    # Archive the Q&A if requested
    if archive:
        from synth_wiki.compiler.archive import archive_query
        from synth_wiki.storage import DB
        from synth_wiki.memory import Store as MemoryStore
        from synth_wiki.vectors import Store as VectorStore
        from synth_wiki.embed import new_from_config

        output_dir = cfg.resolve_output()
        db_p = paths.db_path(project)
        db = DB.open(db_p)
        mem = MemoryStore(db_p)
        vec = VectorStore(db)
        embedder = new_from_config(cfg)
        try:
            sources_used = [r.article_path for r in results[:3]]
            archived_path = archive_query(
                output_dir, question, resp.content, sources_used,
                client, model, mem, vec, embedder, cfg.language,
            )
            if archived_path:
                answer += f"\n[Archived to {os.path.basename(archived_path)}]"
        finally:
            mem.close()
            db.close()

    return answer


def create_server(project_name: str = "", config_path: str = "") -> FastMCP:
    """Create and configure the MCP server with all synth-wiki tools."""

    mcp = FastMCP(
        name="synth-wiki",
        instructions=(
            "synth-wiki is an LLM-compiled personal knowledge base. "
            "Use the tools below to search, query, ingest sources, compile, lint, "
            "and inspect the wiki."
        ),
    )

    def _resolve_project(proj: str) -> str:
        """Resolve project name from argument or auto-detect."""
        if proj:
            return proj
        if project_name:
            return project_name
        from synth_wiki.config import list_projects
        cfg_p = config_path or paths.config_path()
        projects = list_projects(cfg_p)
        if len(projects) == 1:
            return projects[0]
        raise ValueError(f"Multiple projects found, specify one: {projects}")

    def _cfg_path() -> str:
        return config_path or paths.config_path()

    # ------------------------------------------------------------------
    # Tool: search
    # ------------------------------------------------------------------
    @mcp.tool()
    def search(query: str, tags: str = "", limit: int = 10, project: str = "") -> str:
        """Search the wiki using TreeSearch + optional vector reranking.

        Args:
            query: Natural language search query.
            tags: Comma-separated tag filter (optional).
            limit: Maximum number of results (default 10).
            project: Project name (optional if only one project configured).

        Returns:
            Formatted search results with scores and article paths.
        """
        proj = _resolve_project(project)
        cfg = load_config(_cfg_path(), proj)
        tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else []

        results = _do_search(proj, cfg, _cfg_path(), query, tag_list, limit)

        if not results:
            return "No results found."

        lines = []
        for i, r in enumerate(results):
            content = r.content[:200] + "..." if len(r.content) > 200 else r.content
            lines.append(f"{i+1}. [{r.score:.4f}] {r.article_path}")
            lines.append(f"   {content}")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Tool: query
    # ------------------------------------------------------------------
    @mcp.tool()
    def query(question: str, archive: bool = False, project: str = "") -> str:
        """Answer a question using wiki knowledge. Searches relevant articles and synthesizes an answer via LLM.

        Args:
            question: Natural language question about the wiki's domain.
            archive: If true, archive the Q&A as a new wiki page (default false).
            project: Project name (optional).

        Returns:
            LLM-generated answer with cited wiki articles.
        """
        proj = _resolve_project(project)
        cfg = load_config(_cfg_path(), proj)
        return _do_query(proj, cfg, _cfg_path(), question, archive=archive)

    # ------------------------------------------------------------------
    # Tool: ingest
    # ------------------------------------------------------------------
    @mcp.tool()
    def ingest(target: str, project: str = "") -> str:
        """Add a source file or URL to the wiki for compilation.

        Args:
            target: Local file path or URL to ingest.
            project: Project name (optional).

        Returns:
            Ingestion result with file path, type, and size.
        """
        from synth_wiki.wiki import ingest_path, ingest_url

        proj = _resolve_project(project)
        if target.startswith("http://") or target.startswith("https://"):
            result = ingest_url(proj, target, _cfg_path())
        else:
            result = ingest_path(proj, target, _cfg_path())
        return f"Ingested: {result.source_path} (type: {result.type}, {result.size} bytes)"

    # ------------------------------------------------------------------
    # Tool: compile
    # ------------------------------------------------------------------
    @mcp.tool()
    def compile(dry_run: bool = False, fresh: bool = False, project: str = "") -> str:
        """Compile sources into wiki articles.

        Args:
            dry_run: If true, only show changes without writing (default false).
            fresh: If true, ignore checkpoint and recompile all (default false).
            project: Project name (optional).

        Returns:
            Compilation summary with counts.
        """
        from synth_wiki.compiler.pipeline import compile as do_compile, CompileOpts

        proj = _resolve_project(project)
        result = do_compile(proj, CompileOpts(
            dry_run=dry_run, fresh=fresh, config_path=_cfg_path()))

        parts = [
            f"Added: {result.added}",
            f"Modified: {result.modified}",
            f"Removed: {result.removed}",
            f"Summarized: {result.summarized}",
            f"Concepts: {result.concepts_extracted}",
            f"Articles: {result.articles_written}",
            f"Syntheses: {result.syntheses_written}",
            f"Errors: {result.errors}",
        ]
        if result.cost_report:
            parts.append(f"Cost: {result.cost_report.total_tokens:,} tokens, ${result.cost_report.estimated_cost:.4f}")
        return "\n".join(parts)

    # ------------------------------------------------------------------
    # Tool: lint
    # ------------------------------------------------------------------
    @mcp.tool()
    def lint(fix: bool = False, pass_name: str = "", project: str = "") -> str:
        """Run quality checks on wiki articles.

        Args:
            fix: Auto-fix issues where possible (default false).
            pass_name: Run only a specific lint pass (optional).
            project: Project name (optional).

        Returns:
            Lint findings report.
        """
        from synth_wiki.linter import Runner, LintContext, format_findings

        proj = _resolve_project(project)
        cfg = load_config(_cfg_path(), proj)
        ctx = LintContext(output_dir=cfg.resolve_output(), db_path=paths.db_path(proj))
        runner = Runner()
        results = runner.run(ctx, pass_name, fix)
        return format_findings(results)

    # ------------------------------------------------------------------
    # Tool: status
    # ------------------------------------------------------------------
    @mcp.tool()
    def status(project: str = "") -> str:
        """Show wiki statistics and health.

        Args:
            project: Project name (optional).

        Returns:
            Formatted status with source/concept/vector counts.
        """
        from synth_wiki.wiki import get_status, format_status

        proj = _resolve_project(project)
        info = get_status(proj, config_path=_cfg_path())
        return format_status(info)

    # ------------------------------------------------------------------
    # Tool: read_article
    # ------------------------------------------------------------------
    @mcp.tool()
    def read_article(name: str, project: str = "") -> str:
        """Read a wiki article by its concept name (slug).

        Args:
            name: Article slug (e.g., 'self-attention', 'transformer').
            project: Project name (optional).

        Returns:
            Full article content, or error if not found.
        """
        proj = _resolve_project(project)
        cfg = load_config(_cfg_path(), proj)
        output_dir = cfg.resolve_output()

        for subdir in ["concepts", "entities", "comparisons", "syntheses"]:
            path = os.path.join(output_dir, subdir, f"{name}.md")
            if os.path.exists(path):
                with open(path) as f:
                    return f.read()

        return f"Article '{name}' not found in concepts/, entities/, comparisons/, or syntheses/."

    # ------------------------------------------------------------------
    # Tool: list_articles
    # ------------------------------------------------------------------
    @mcp.tool()
    def list_articles(article_type: str = "", project: str = "") -> str:
        """List all wiki articles, optionally filtered by type.

        Args:
            article_type: Filter by type: 'concept', 'entity', 'comparison', or '' for all.
            project: Project name (optional).

        Returns:
            List of article names grouped by type.
        """
        proj = _resolve_project(project)
        cfg = load_config(_cfg_path(), proj)
        output_dir = cfg.resolve_output()

        type_dirs = {"concept": "concepts", "entity": "entities", "comparison": "comparisons", "synthesis": "syntheses"}
        if article_type and article_type in type_dirs:
            scan = {article_type: type_dirs[article_type]}
        else:
            scan = type_dirs

        lines = []
        total = 0
        for type_name, subdir in scan.items():
            dir_path = os.path.join(output_dir, subdir)
            if not os.path.isdir(dir_path):
                continue
            articles = sorted(f[:-3] for f in os.listdir(dir_path) if f.endswith(".md"))
            if articles:
                lines.append(f"## {type_name.capitalize()}s ({len(articles)})")
                for a in articles:
                    lines.append(f"  - {a}")
                total += len(articles)

        if not lines:
            return "No articles found."
        lines.insert(0, f"Total: {total} articles\n")
        return "\n".join(lines)

    return mcp


def run_server(project_name: str = "", config_path: str = "",
               transport: Literal["stdio", "sse", "streamable-http"] = "stdio",
               port: int = 0) -> None:
    """Create and run the MCP server."""
    mcp = create_server(project_name, config_path)
    if port:
        mcp.settings.port = port
    mcp.run(transport=transport)

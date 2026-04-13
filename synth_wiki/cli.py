# -*- coding: utf-8 -*-
"""
@author:XuMing(xuming624@qq.com)
@description: Click CLI for synth-wiki.

Config lives at ~/.synth_wiki/config.yaml; specify --project to select which project.
"""
import os
import click
from synth_wiki import log
from synth_wiki import paths


@click.group()
@click.option("--project", default="", help="Project name (from config.yaml)")
@click.option("--config", "config_path", default="", help="Config file path (default: ~/.synth_wiki/config.yaml)")
@click.option("-v", "--verbose", count=True, help="Increase verbosity")
@click.pass_context
def main(ctx, project, config_path, verbose):
    """synth-wiki: LLM-compiled personal knowledge base."""
    log.set_verbosity(verbose)
    ctx.ensure_object(dict)
    ctx.obj["project"] = project
    ctx.obj["config_path"] = config_path or paths.config_path()


@main.command()
@click.option("--name", default="", help="Project name (default: current directory name)")
@click.option("--source", default="", help="Source directory (default: ./raw)")
@click.option("--output", default="", help="Output directory (default: ./wiki)")
@click.option("--vault", is_flag=True, help="Initialize as vault overlay")
@click.option("--model", default="gpt-4o-mini", help="Default LLM model")
@click.pass_context
def init(ctx, name, source, output, vault, model):
    """Initialize a new synth-wiki project.

    Creates config at ~/.synth_wiki/config.yaml with sensible defaults.
    All options are optional — just run 'synth-wiki init' in your project directory.
    """
    from synth_wiki.wiki import init_greenfield, init_vault_overlay
    cwd = os.getcwd()
    name = name or os.path.basename(cwd)
    source = os.path.abspath(source or os.path.join(cwd, "raw"))
    output = os.path.abspath(output or os.path.join(cwd, "wiki"))
    os.makedirs(source, exist_ok=True)
    if vault:
        from synth_wiki.wiki import scan_folders
        folders = scan_folders(source)
        source_folders = [f.name for f in folders if f.file_count > 0]
        ignore_folders = [f.name for f in folders if f.file_count == 0]
        init_vault_overlay(name, source, source_folders, ignore_folders, output, model)
    else:
        init_greenfield(name, source, output, model)
    click.echo(f"Project {name!r} initialized.")
    click.echo(f"  Config : {paths.config_path()}")
    click.echo(f"  Sources: {source}")
    click.echo(f"  Output : {output}")
    click.echo(f"\nNext steps:")
    click.echo(f"  1. Edit {paths.config_path()} to set your API key and model")
    click.echo(f"  2. Copy source files into {source}")
    click.echo(f"  3. Run: synth-wiki compile")


@main.command()
@click.option("--project", default="", help="Project name (from config.yaml)")
@click.option("--watch", is_flag=True, help="Watch for changes and recompile")
@click.option("--dry-run", is_flag=True, help="Show changes without writing")
@click.option("--fresh", is_flag=True, help="Ignore checkpoint")
@click.option("--batch", is_flag=True, help="Use batch API")
@click.option("--no-cache", is_flag=True, help="Disable prompt caching")
@click.pass_context
def compile(ctx, project, watch, dry_run, fresh, batch, no_cache):
    """Compile sources into wiki articles."""
    project_name = _resolve_project(ctx, project)
    if not project_name:
        return
    if watch:
        from synth_wiki.compiler.watch import watch as do_watch
        click.echo("Watching for changes... (Ctrl+C to stop)")
        do_watch(project_name, debounce_seconds=2, config_path=ctx.obj["config_path"])
        return
    from synth_wiki.compiler.pipeline import compile as do_compile, CompileOpts
    result = do_compile(project_name, CompileOpts(
        dry_run=dry_run, fresh=fresh, batch=batch, no_cache=no_cache,
        config_path=ctx.obj["config_path"]))
    click.echo(f"Compile: +{result.added} added, ~{result.modified} modified, -{result.removed} removed, "
               f"{result.summarized} summarized, {result.concepts_extracted} concepts, {result.articles_written} articles")


@main.command()
@click.option("--project", default="", help="Project name (from config.yaml)")
@click.pass_context
def status(ctx, project):
    """Show wiki stats and health."""
    from synth_wiki.wiki import get_status, format_status
    project_name = _resolve_project(ctx, project)
    if not project_name:
        return
    info = get_status(project_name, config_path=ctx.obj["config_path"])
    click.echo(format_status(info))


@main.command()
@click.option("--project", default="", help="Project name (from config.yaml)")
@click.argument("query_text", nargs=-1, required=True)
@click.option("--tags", default="", help="Comma-separated tag filter")
@click.option("--limit", default=10, help="Maximum results")
@click.pass_context
def search(ctx, project, query_text, tags, limit):
    """Search the wiki."""
    from synth_wiki.config import load
    from synth_wiki.storage import DB
    from synth_wiki.memory import Store as MemoryStore
    from synth_wiki.vectors import Store as VectorStore
    from synth_wiki.hybrid import Searcher, SearchOpts
    from synth_wiki.embed import new_from_config

    project_name = _resolve_project(ctx, project)
    if not project_name:
        return
    cfg = load(ctx.obj["config_path"], project_name)
    db_p = paths.db_path(project_name)
    db = DB.open(db_p)
    mem = MemoryStore(db_p)
    vec = VectorStore(db)
    searcher = Searcher(mem, vec)

    query = " ".join(query_text)
    tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else []

    query_vec = None
    embedder = new_from_config(cfg)
    if embedder:
        query_vec = embedder.embed(query)

    results = searcher.search(SearchOpts(query=query, tags=tag_list, limit=limit), query_vec)
    mem.close()
    db.close()

    if not results:
        click.echo("No results found.")
        return
    for i, r in enumerate(results):
        content = r.content[:120] + "..." if len(r.content) > 120 else r.content
        click.echo(f"{i+1}. [{r.score:.4f}] {r.article_path}")
        click.echo(f"   {content}")


@main.command()
@click.option("--project", default="", help="Project name (from config.yaml)")
@click.option("--fix", is_flag=True, help="Auto-fix issues")
@click.option("--pass-name", "pass_name", default="", help="Run specific pass")
@click.pass_context
def lint(ctx, project, fix, pass_name):
    """Run linting passes on the wiki."""
    from synth_wiki.config import load
    from synth_wiki.linter import Runner, LintContext, format_findings, save_report

    project_name = _resolve_project(ctx, project)
    if not project_name:
        return
    cfg = load(ctx.obj["config_path"], project_name)
    ctx_lint = LintContext(output_dir=cfg.resolve_output(),
                           db_path=paths.db_path(project_name))
    runner = Runner()
    results = runner.run(ctx_lint, pass_name, fix)
    click.echo(format_findings(results))
    save_report(project_name, results)


@main.command()
@click.option("--project", default="", help="Project name (from config.yaml)")
@click.argument("target")
@click.pass_context
def ingest(ctx, project, target):
    """Add a source to the wiki."""
    from synth_wiki.wiki import ingest_path, ingest_url
    project_name = _resolve_project(ctx, project)
    if not project_name:
        return
    if target.startswith("http://") or target.startswith("https://"):
        result = ingest_url(project_name, target, ctx.obj["config_path"])
    else:
        result = ingest_path(project_name, target, ctx.obj["config_path"])
    click.echo(f"Ingested: {result.source_path} (type: {result.type}, {result.size} bytes)")


@main.command()
@click.option("--project", default="", help="Project name (from config.yaml)")
@click.pass_context
def doctor(ctx, project):
    """Validate configuration and connectivity."""
    from synth_wiki.wiki import run_doctor, format_doctor
    project_name = _resolve_project(ctx, project)
    if not project_name:
        return
    result = run_doctor(project_name, ctx.obj["config_path"])
    click.echo(format_doctor(result))


@main.command(name="projects")
@click.pass_context
def list_projects_cmd(ctx):
    """List all configured projects."""
    from synth_wiki.config import list_projects
    projects = list_projects(ctx.obj["config_path"])
    if not projects:
        click.echo("No projects configured.")
        return
    for p in projects:
        click.echo(f"  - {p}")


@main.command()
@click.option("--project", default="", help="Project name (from config.yaml)")
@click.argument("question", nargs=-1, required=True)
@click.pass_context
def query(ctx, project, question):
    """Ask a question and get an answer from the wiki."""
    from synth_wiki.config import load
    from synth_wiki.server import _do_query

    project_name = _resolve_project(ctx, project)
    if not project_name:
        return

    question_text = " ".join(question)
    cfg = load(ctx.obj["config_path"], project_name)
    answer = _do_query(project_name, cfg, ctx.obj["config_path"], question_text)
    click.echo(answer)


@main.command()
@click.option("--project", default="", help="Project name (from config.yaml)")
@click.option("--transport", default="stdio", type=click.Choice(["stdio", "sse"]),
              help="MCP transport (default: stdio)")
@click.option("--port", default=0, type=int, help="Port for SSE transport (default: from config)")
@click.pass_context
def serve(ctx, project, transport, port):
    """Start the MCP server for IDE/agent integration.

    Exposes wiki search, query, ingest, compile, lint, and status as MCP tools.
    Use stdio transport for Claude Code / Cursor, SSE for web clients.
    """
    from synth_wiki.server import run_server

    project_name = _resolve_project(ctx, project)
    if not project_name:
        return

    cfg_path = ctx.obj["config_path"]
    if not port:
        from synth_wiki.config import load
        cfg = load(cfg_path, project_name)
        port = cfg.serve.port

    click.echo(f"Starting MCP server (transport={transport}, project={project_name})")
    run_server(project_name=project_name, config_path=cfg_path,
               transport=transport, port=port)


def _resolve_project(ctx, local_project: str = "") -> str:
    """Resolve project name: local --project > global --project > auto-detect."""
    project_name = local_project or ctx.obj["project"]
    if project_name:
        return project_name
    from synth_wiki.config import list_projects
    projects = list_projects(ctx.obj["config_path"])
    if len(projects) == 1:
        return projects[0]
    click.echo(f"Multiple projects found. Specify --project: {projects}")
    return ""


if __name__ == "__main__":
    main()

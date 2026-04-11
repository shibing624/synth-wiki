[**🇨🇳中文**](README_ZH.md) | **🌐English**

<div align="center">
  <a href="https://github.com/shibing624/synth-wiki">
    <img src="https://raw.githubusercontent.com/shibing624/synth-wiki/main/docs/logo.svg" height="150" alt="Logo">
  </a>
</div>

-----------------

# synth-wiki
[![PyPI version](https://badge.fury.io/py/synth-wiki.svg)](https://badge.fury.io/py/synth-wiki)
[![Downloads](https://static.pepy.tech/badge/synth-wiki)](https://pepy.tech/project/synth-wiki)
[![License Apache 2.0](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)
[![python_version](https://img.shields.io/badge/Python-3.12%2B-green.svg)](pyproject.toml)
[![GitHub issues](https://img.shields.io/github/issues/shibing624/synth-wiki.svg)](https://github.com/shibing624/synth-wiki/issues)
[![Wechat Group](https://img.shields.io/badge/wechat-group-green.svg?logo=wechat)](#community--support)

An implementation of [Andrej Karpathy's idea](https://x.com/karpathy/status/2039805659525644595) for an LLM-compiled personal knowledge base. Written in Python.

Drop in your papers, articles, and notes. `synth-wiki` compiles them into a structured, interlinked wiki — with concepts extracted, cross-references discovered, and everything searchable via a powerful tree-aware search engine.

- **Your sources in, a wiki out.** Add documents to a folder. The LLM reads, summarizes, extracts concepts, and writes interconnected articles.
- **Compounding knowledge.** Every new source enriches existing articles. The wiki gets smarter as it grows.
- **Ask your wiki questions.** Enhanced structure-aware search powered by [TreeSearch](https://github.com/shibing624/TreeSearch). Ask natural language questions and get cited, highly-relevant answers.
- **Native Chinese Support.** Built-in Jieba tokenization ensures excellent retrieval for Chinese documents.

## Install

### From PyPI

```bash
pip install -U synth-wiki
```

### From source

```bash
git clone https://github.com/shibing624/synth-wiki.git
cd synth-wiki
pip install -e .
```

### Dependencies

- Python >= 3.12
- click >= 8.1
- pyyaml >= 6.0
- httpx >= 0.27
- pytreesearch >= 0.1 (auto mode tree search)
- loguru >= 0.7

## Quickstart

### 1. Initialize a project

```bash
mkdir my-wiki && cd my-wiki
synth-wiki init
```

This creates:
- `./raw/` — drop your source files here
- `./wiki/` — compiled wiki output
- `~/.synth_wiki/config.yaml` — global config (auto-generated with sensible defaults)

### 2. Set your API key

The generated config uses OpenAI-compatible API by default. Set your environment variables:

```bash
export OPENAI_API_KEY="sk-xxx"
export OPENAI_BASE_URL="https://api.openai.com/v1"  # or any compatible endpoint
```

Or edit `~/.synth_wiki/config.yaml` directly:

```yaml
api:
  provider: openai-compatible
  api_key: ${OPENAI_API_KEY}
  base_url: ${OPENAI_BASE_URL}

models:
  summarize: gpt-4o-mini
  extract: gpt-4o-mini
  write: gpt-4o-mini
  lint: gpt-4o-mini
  query: gpt-4o-mini
```

Other supported providers: `openai`, `anthropic`, `gemini`, `ollama`.

### 3. Add sources and compile

```bash
# Add source files
cp ~/papers/*.pdf raw/
cp ~/articles/*.md raw/

# Compile
synth-wiki compile

# Watch mode (auto-recompile on file changes)
synth-wiki compile --watch

# Search
synth-wiki search "attention mechanism"
```

## Supported Source Formats

Just drop files into your source folder — `synth-wiki` detects the format automatically.

| Format | Extensions | What gets extracted |
|--------|-----------|-------------------|
| Markdown | `.md` | Body text with frontmatter parsed separately |
| PDF | `.pdf` | Full text via PyMuPDF |
| Word | `.docx` | Document text |
| JSON / JSONL | `.json`, `.jsonl` | Parsed and searched structurally |
| Code | `.py`, `.java`, `.go`, `.ts` | Source code parsed via AST and regex |
| Plain text | `.txt`, `.csv` | Raw content |
| Images | `.png`, `.jpg`, `.svg` | Image files |

## Commands

| Command | Description |
|---------|------------|
| `synth-wiki init [--name] [--source] [--output] [--vault]` | Initialize project (all options optional) |
| `synth-wiki compile [--watch] [--dry-run] [--fresh] [--batch] [--no-cache]` | Compile sources into wiki articles |
| `synth-wiki search "query" [--tags] [--limit]` | Search via TreeSearch |
| `synth-wiki query "question"` | Q&A against the wiki |
| `synth-wiki ingest <url\|path>` | Add a source |
| `synth-wiki lint [--fix] [--pass-name]` | Check and fix article quality |
| `synth-wiki status` | Wiki stats and health |
| `synth-wiki doctor` | Check config and connection status |
| `synth-wiki projects` | List all configured projects |

## Directory Structure

```
~/.synth_wiki/                    # Global state directory
├── config.yaml                   # Global config (shared by all projects)
├── db/
│   └── my-wiki.db                # Project SQLite database (WAL mode)
├── manifests/
│   └── my-wiki.json              # Source manifest and compile status
├── state/
│   └── my-wiki.json              # Compile checkpoint (auto-deleted on success)
└── lintlog/
    └── my-wiki/                  # Lint report history

./raw/                            # Source files directory (user-managed)
├── paper-1.md
├── notes.txt
└── captures/                     # URL-ingested files

./wiki/                           # Compiled output directory (auto-generated)
├── summaries/                    # Pass 1: Source summaries
├── concepts/                     # Pass 3: Wiki articles
│   ├── transformer.md
│   └── self-attention.md
├── connections/
├── outputs/
├── images/                       # Extracted images
├── archive/
├── prompts/                      # Custom prompts (optional)
└── CHANGELOG.md                  # Compile history
```

## Knowledge Capture: Ingest and Learning

### Ingest local files

```bash
synth-wiki ingest /path/to/document.md
synth-wiki ingest /path/to/notes.txt
```

The `ingest` command will:
1. Detect file type by extension
2. Copy the file to the project source directory
3. Compute SHA-256 hash
4. Register the source in the manifest as pending compilation
5. Print the result (path, type, size)

### Ingest URLs

```bash
synth-wiki ingest https://example.com/article
```

URL ingestion will:
1. Download the page content via httpx (30s timeout, follows redirects)
2. Wrap the content as a Markdown file with YAML frontmatter recording source URL and ingest time
3. Save to source directory with a slugified filename
4. Register in manifest

### Compile Pipeline

Imported sources go through a 4-step compilation:

```
Source Files (MD/PDF/DOCX/JSON/Code/TXT/Image)
        │
        ▼
  ┌───────────────┐
  │  1. Diff      │  Compare manifest, detect added/modified/deleted
  └──────┬────────┘
         │  change list
         ▼
  ┌───────────────┐
  │  2. Summarize │  LLM generates summaries concurrently
  └──────┬────────┘
         │  summaries
         ▼
  ┌───────────────┐
  │  3. Extract   │  LLM batch-extracts concepts, aliases, types
  │   Concepts    │
  └──────┬────────┘
         │  concepts
         ▼
  ┌───────────────┐
  │  4. Write     │  LLM writes wiki articles per concept
  │   Articles    │  auto-creates [[wikilinks]] and ontology relations
  └──────┬────────┘
         │
         ▼
  Structured Wiki (summaries + concept articles + knowledge graph)
```

Compilation supports checkpoint resume: if interrupted, the next compile picks up from the last checkpoint. Use `--fresh` to ignore checkpoints and restart.

> **Details:** [Knowledge Capture: Ingest and Learning](docs/mcp-knowledge-capture.md)

## Watch Mode

`synth-wiki compile --watch` enables real-time file watching. When source files are added, modified, or deleted, compilation is automatically triggered.

- **Primary mode**: Uses [watchdog](https://github.com/gorakhargosh/watchdog) (fsevents on macOS, inotify on Linux) for native file system events
- **Fallback mode**: If watchdog is not installed, automatically degrades to polling (2-second interval)
- **Debounce**: 2-second debounce to batch rapid file changes into a single compile
- **Concurrency protection**: Lock-based guard prevents overlapping compiles
- **Initial compile**: Runs one compile on startup to catch any missed changes

Install watchdog for best performance:

```bash
pip install synth-wiki[watch]
```

> **Details:** [Installation and Configuration](docs/self-hosted-server.md)

## Ontology: Entity-Relation Knowledge Graph

synth-wiki automatically builds an ontology (knowledge graph) during compilation, connecting concepts, techniques, and sources through typed edges. The knowledge graph is stored in SQLite with CHECK constraints for data integrity.

### How it works

After Pass 3 (write_articles), `_extract_relations()` scans article content for `[[wikilinks]]` and checks for keywords near the links. If matched, a typed relation edge is created.

For example, an article about Flash Attention containing:

> Flash Attention **optimizes** the memory access pattern of [[Self-Attention]]

Creates the edge: `Flash-Attention --optimizes--> Self-Attention`

### Entity Types

| Type | Description | Created when |
|------|-------------|-------------|
| `concept` | General concept | Default type, created during Pass 3 |
| `technique` | Specific technique/method | Concept type is "technique" |
| `source` | Source file | Auto-created for each source reference |
| `claim` | Assertion/conclusion | Concept type is "claim" |
| `artifact` | Output/product | Reserved type |

### Relation Types

| Type | Extraction Keywords | Description |
|------|-------------------|-------------|
| `implements` | implements, implementation of | A implements B |
| `extends` | extends, extension of, builds on | A extends B |
| `optimizes` | optimizes, optimization of, improves upon | A optimizes B |
| `contradicts` | contradicts, conflicts with | A contradicts B |
| `cites` | *(auto-created)* | A cites source B |
| `prerequisite_of` | prerequisite, requires knowledge of | A is prerequisite of B |
| `trades_off` | trade-off, tradeoff, trades off | A trades off with B |
| `derived_from` | *(auto-created)* | A is derived from B |

### Graph Traversal

```python
from synth_wiki.ontology import Store, TraverseOpts, Direction

store = Store(db)

# BFS traversal from an entity, following outbound edges, depth 2
neighbors = store.traverse("flash-attention", TraverseOpts(
    direction=Direction.OUTBOUND,
    max_depth=2,
))

# Inbound edges (who points to this entity)
inbound = store.traverse("self-attention", TraverseOpts(
    direction=Direction.INBOUND,
    max_depth=1,
))

# Bidirectional with relation type filter
both = store.traverse("transformer", TraverseOpts(
    direction=Direction.BOTH,
    max_depth=1,
    relation_type="extends",
))
```

### Cycle Detection

```python
cycles = store.detect_cycles("flash-attention")
# Returns: [["flash-attention", "B", "C", "flash-attention"], ...]
```

> **Details:** [Configurable Relations](docs/configurable-relations.md)

## Search Quality Powered by TreeSearch

synth-wiki uses a hybrid search pipeline combining **TreeSearch auto mode** (Best-First tree walk + FTS5) with optional vector semantic search, fused via Reciprocal Rank Fusion (RRF).

### How it works

```
User Query
  -> TreeSearch auto mode (tree walk with FTS5 scoring, auto flat/tree routing)
  -> Optional vector cosine similarity search (if embedder configured)
  -> RRF fusion (K=60, combining TreeSearch rank + vector rank)
  -> Tag boost (+3% per matching tag, capped at 15%)
  -> Recency boost (14-day half-life, max +5%)
  -> Return top-N results sorted by combined score
```

### TreeSearch Auto Mode

Unlike traditional vector RAG that chops documents into chunks and loses context, synth-wiki uses **[TreeSearch](https://github.com/shibing624/TreeSearch)** in auto mode — the most effective search strategy.

- **Best-First Tree Walk**: Anchor retrieval → expansion → path scoring over document tree structures, not just flat BM25 ranking
- **Auto Mode Routing**: Automatically switches between Tree search (articles, papers, markdown) and Flat search (code files) based on document `source_type`
- **Document Routing**: Multi-document queries first route to top-K relevant documents via FTS5, then perform deep tree search within each
- **No Embeddings Required**: Millisecond-level structure-aware matching with intelligent cross-document scoring
- **Excellent CJK Support**: Integrated jieba tokenizer for high-quality Chinese text retrieval

### Vector Search (Optional)

When an embedding provider is configured, synth-wiki generates vector embeddings for summaries and concept articles. At query time, the query is also embedded and compared via brute-force cosine similarity.

Supported embedding providers (auto-detected in cascade order):
1. **Explicit config** — `embed.model` in config.yaml
2. **Provider default** — OpenAI: `text-embedding-3-small`, Gemini: `gemini-embedding-2-preview`, Voyage: `voyage-3-lite`, Mistral: `mistral-embed`
3. **Ollama local** — `nomic-embed-text` (auto-detected if Ollama is running)
4. **None** — TreeSearch-only search (still fully functional)

### RRF Fusion

TreeSearch and vector results are fused using Reciprocal Rank Fusion:

```
score(doc) = 1/(K + treesearch_rank) + 1/(K + vector_rank)
```

Where `K = 60`. Documents ranked highly by either method receive a strong combined score.

### Fallback Behavior

The search pipeline degrades gracefully:
- **No embedder configured** — TreeSearch-only. Auto mode tree walk still delivers high quality.
- **Empty index** — Returns empty results.
- **Vector dimensions mismatch** — Mismatched vectors are silently skipped.
- **Ollama not running** — Falls back to API embedding or TreeSearch-only.

> **Details:** [Search Quality (EN)](docs/search-quality.md) | [搜索质量 (中文)](docs/search-quality-zh.md)

## Configuration

### Full config example

```yaml
# Global API config
api:
  provider: openai-compatible      # openai, anthropic, gemini, ollama, openai-compatible
  api_key: ${OPENAI_API_KEY}       # Supports ${ENV_VAR} expansion
  base_url: ${OPENAI_BASE_URL}
  rate_limit: 0                    # Requests per minute, 0 = unlimited
  extra_body: {}

# Models (per compilation stage)
models:
  summarize: gpt-4o-mini           # Pass 1: Summarize
  extract: gpt-4o-mini             # Pass 2: Concept extraction
  write: gpt-4o-mini               # Pass 3: Article writing
  lint: gpt-4o-mini                # Linter
  query: gpt-4o-mini               # Query (reserved)

# Embedding config (optional, auto-cascades if not set)
embed:
  provider: auto                   # auto, openai, gemini, voyage, mistral, ollama
  model: ""                        # Empty = use provider default
  dimensions: 0                    # 0 = auto-detect
  api_key: ""                      # Empty = reuse api.api_key
  base_url: ""

# Compiler config
compiler:
  max_parallel: 4                  # Max concurrent LLM calls per phase
  debounce_seconds: 2
  summary_max_tokens: 2000
  article_max_tokens: 4000
  auto_commit: true                # Auto git commit after compile
  auto_lint: true                  # Auto lint after compile
  mode: ""                         # standard, batch, auto
  prompt_cache: null               # null=true (cache enabled by default)

# Search config
search:
  default_limit: 10

# Linter config
linting:
  auto_fix_passes:
    - consistency
    - completeness
    - style
  staleness_threshold_days: 90

# Language (affects article generation language)
language: zh-CN                    # zh-CN, zh-TW, en, ja, ko

# Project definitions
projects:
  my-wiki:
    description: "Personal knowledge base"
    sources:
      - path: /Users/me/raw
        type: auto
        watch: true
    output: /Users/me/wiki
```

### Multi-project config

```yaml
projects:
  research:
    description: "AI research notes"
    sources:
      - path: ~/research/raw
    output: ~/research/wiki
    models:
      write: gpt-4o              # Better model for research articles

  work:
    description: "Work notes"
    sources:
      - path: ~/work/raw
    output: ~/work/wiki
```

Use `--project` to specify which project:

```bash
synth-wiki compile --project research
synth-wiki status --project work
synth-wiki search --project research "attention"
```

If there is only one project, `--project` can be omitted.

### LLM Provider Examples

**OpenAI:**
```yaml
api:
  provider: openai
  api_key: ${OPENAI_API_KEY}
models:
  summarize: gpt-4o-mini
  write: gpt-4o
```

**Anthropic:**
```yaml
api:
  provider: anthropic
  api_key: ${ANTHROPIC_API_KEY}
models:
  summarize: claude-sonnet-4
  write: claude-sonnet-4
```

**Gemini:**
```yaml
api:
  provider: gemini
  api_key: ${GEMINI_API_KEY}
models:
  summarize: gemini-2.5-flash
  write: gemini-2.5-flash
```

**OpenAI-Compatible (OpenRouter, Together, Groq, etc.):**
```yaml
api:
  provider: openai-compatible
  base_url: https://openrouter.ai/api/v1
  api_key: ${OPENROUTER_API_KEY}
models:
  summarize: google/gemini-2.5-flash-preview
  write: anthropic/claude-sonnet-4
```

**Ollama (local, no API key needed):**
```yaml
api:
  provider: ollama
  base_url: http://localhost:11434
models:
  summarize: llama3
  write: llama3
```

### Embedding Cascade

synth-wiki uses a 3-level cascade strategy to auto-select embedding provider:

| Provider | Default Model | Dimensions |
|----------|--------------|-----------|
| openai | text-embedding-3-small | 1536 |
| gemini | gemini-embedding-2-preview | 768 |
| voyage | voyage-3-lite | 1024 |
| mistral | mistral-embed | 1024 |
| ollama | nomic-embed-text | 768 |

### Vault Overlay Mode (Obsidian)

If you already use Obsidian, synth-wiki can overlay on your existing vault:

```bash
synth-wiki init --name my-vault --vault --source ~/my-vault --output _wiki
```

- Source files come from existing vault folders
- Output writes to `_wiki/` subdirectory inside the vault
- Obsidian can directly browse compiled output
- `[[wikilinks]]` are compatible with Obsidian's link format

## Python API

### Search

```python
from synth_wiki import DB, MemoryStore, VectorStore, Searcher, SearchOpts
from synth_wiki import paths, load_config
from synth_wiki.embed import new_from_config

cfg = load_config(paths.config_path(), "my-project")
db = DB.open(paths.db_path("my-project"))
mem = MemoryStore(paths.db_path("my-project"))
vec = VectorStore(db)
searcher = Searcher(mem, vec)

# FTS5-only search
results = searcher.search(SearchOpts(query="attention mechanism", limit=10))

# Hybrid search with vector
embedder = new_from_config(cfg)
query_vec = embedder.embed("attention mechanism") if embedder else None
results = searcher.search(SearchOpts(query="attention mechanism", limit=10), query_vec)

for r in results:
    print(f"[{r.score:.4f}] {r.article_path}")
    print(f"  {r.content[:120]}...")

mem.close()
db.close()
```

### Ingest

```python
from synth_wiki.wiki import ingest_path, ingest_url

# Ingest local file
result = ingest_path("my-project", "/path/to/document.md")
print(f"Ingested: {result.source_path} ({result.type}, {result.size} bytes)")

# Ingest URL
result = ingest_url("my-project", "https://example.com/article")
print(f"Ingested: {result.source_path} ({result.type}, {result.size} bytes)")
```

### Ontology

```python
from synth_wiki.ontology import Store, TraverseOpts, Direction

store = Store(db)

# Add/update entity (upsert)
store.add_entity(entity)

# Get entity
entity = store.get_entity("flash-attention")

# List entities (optionally filter by type)
all_concepts = store.list_entities("concept")

# Add relation (upsert, unique on source+target+relation)
store.add_relation(relation)

# Query relations
rels = store.get_relations("flash-attention", Direction.OUTBOUND)
rels = store.get_relations("flash-attention", Direction.BOTH, "optimizes")

# Stats
store.entity_count()           # Total entities
store.entity_count("concept")  # Entities of specific type
store.relation_count()         # Total relations
```

## Acknowledgements

- [xoai/sage-wiki](https://github.com/xoai/sage-wiki) — Go implementation of llm-wiki
- [Andrej Karpathy's llm-wiki idea](https://x.com/karpathy/status/2039805659525644595) — the original inspiration

## Community & Support

- **GitHub Issues** — [Open an issue](https://github.com/shibing624/synth-wiki/issues)
- **WeChat Group** — Add WeChat `xuming624` with note "nlp" to join the tech discussion group

<img src="https://github.com/shibing624/TreeSearch/blob/main/docs/wechat.jpeg" width="200" />

## Citation

If you use synth-wiki in your research, please cite:

```bibtex
@software{xu2026synthwiki,
  author = {Xu, Ming},
  title = {synth-wiki: LLM-Compiled Personal Knowledge Base},
  year = {2026},
  publisher = {GitHub},
  url = {https://github.com/shibing624/synth-wiki}
}
```

## Contributing

Contributions are welcome! Please submit a [Pull Request](https://github.com/shibing624/synth-wiki/pulls).

## License

[Apache License 2.0](LICENSE)

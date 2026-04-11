# Search Quality

synth-wiki uses a hybrid search pipeline combining TreeSearch FTS5 full-text search with optional vector semantic search, fused via Reciprocal Rank Fusion (RRF).

## How it works

```
User Query
  -> TreeSearch FTS5 full-text search (structure-aware keyword matching)
  -> Optional vector cosine similarity search (if embedder configured)
  -> RRF fusion (K=60, combining FTS5 rank + vector rank)
  -> Tag boost (+3% per matching tag, capped at 15%)
  -> Recency boost (14-day half-life, max +5%)
  -> Return top-N results sorted by combined score
```

## Key features

### TreeSearch FTS5 full-text search

synth-wiki replaces naive FTS5 with **[TreeSearch](https://github.com/shibing624/TreeSearch)**, a structure-aware full-text search engine. Documents are parsed into tree structures (e.g., Markdown heading hierarchy), preserving semantic context during retrieval.

Key advantages over standard FTS5:
- **Structure-aware**: Respects Markdown headings, JSON keys, and other hierarchical structures
- **No embeddings required**: Millisecond-level keyword matching with intelligent cross-document scoring
- **Auto mode**: Automatically switches between Tree search (articles, papers) and Flat search (code files) based on document type
- **Excellent CJK support**: Integrated jieba tokenizer for high-quality Chinese text retrieval

Each indexed document is stored as a `treesearch.tree.Document` with structured nodes, enabling the search engine to understand document hierarchy rather than treating content as flat text.

### Vector search (optional)

When an embedding provider is configured, synth-wiki generates vector embeddings for summaries and concept articles. At query time, the query is also embedded and compared against all stored vectors via brute-force cosine similarity.

Supported embedding providers (auto-detected in cascade order):
1. **Explicit config** — `embed.model` in config.yaml
2. **Provider default** — OpenAI: `text-embedding-3-small`, Gemini: `gemini-embedding-2-preview`, Voyage: `voyage-3-lite`, Mistral: `mistral-embed`
3. **Ollama local** — `nomic-embed-text` (auto-detected if Ollama is running)
4. **None** — FTS5-only search (still fully functional)

### RRF fusion

FTS5 and vector results are fused using Reciprocal Rank Fusion (Cormack et al. 2009):

```
score(doc) = 1/(K + fts_rank) + 1/(K + vector_rank)
```

Where `K = 60`. This ensures that documents ranked highly by either method receive a strong combined score, without requiring score normalization between the two systems.

### Tag boost

Each search result matching a `boost_tag` receives a +3% score boost, capped at 15% total. This allows callers to prioritize results from specific source types or categories.

### Recency boost

Results with known timestamps receive a recency boost using a 14-day half-life exponential decay:

```
boost = 0.05 * 2^(-age_days / 14)
```

Maximum boost is +5% (for just-updated documents). Documents older than ~2 months receive negligible boost.

## Configuration

```yaml
search:
  default_limit: 10     # maximum results per query (default: 10)
```

Search configuration is minimal by design. The `default_limit` controls how many results are returned. All other behavior (RRF constant, boost weights) is hardcoded to well-tested defaults.

### Embedding configuration

To enable vector search, configure an embedding provider:

```yaml
# Use provider's default embedding model
embed:
  provider: auto   # auto-detect from api.provider

# Or specify explicitly
embed:
  provider: openai
  model: text-embedding-3-small
  api_key: ${OPENAI_API_KEY}
```

If no embedding is configured, synth-wiki falls back to FTS5-only search, which is still high quality thanks to TreeSearch.

### Local embeddings (Ollama)

If Ollama is running locally with an embedding model, synth-wiki auto-detects it:

```bash
# Pull an embedding model
ollama pull nomic-embed-text

# synth-wiki will auto-detect and use it — no config needed
```

## CLI usage

```bash
# Basic search
synth-wiki search "attention mechanism"

# Search with tag filter
synth-wiki search "transformer" --tags "paper,article"

# Limit results
synth-wiki search "gradient descent" --limit 5
```

## Python API usage

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

## How indexing works

Documents are indexed at two points during compilation:

1. **Pass 1 (Summarize)** — Each source summary is added to both the FTS5 index (via `MemoryStore`) and the vector store (if an embedder is available)
2. **Pass 3 (Write articles)** — Each concept article is added to both stores, tagged with entity type and aliases

The FTS5 index stores entries as TreeSearch `Document` objects with structured nodes, enabling structure-aware retrieval. The vector store persists embeddings as float32 BLOBs in SQLite.

## Fallback behavior

The search pipeline degrades gracefully:

- **No embedder configured** — FTS5-only search. Still high quality with TreeSearch.
- **Empty FTS5 index** — Returns empty results.
- **Vector dimensions mismatch** — Mismatched vectors are silently skipped during cosine similarity.
- **Ollama not running** — Falls back to API embedding or FTS5-only.

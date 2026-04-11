# 搜索质量

synth-wiki 采用混合搜索流水线，将 TreeSearch FTS5 全文检索与可选的向量语义搜索相结合，通过 Reciprocal Rank Fusion (RRF) 进行融合。

## 工作原理

```
用户查询
  -> TreeSearch FTS5 全文检索（结构感知的关键词匹配）
  -> 可选的向量余弦相似度搜索（需配置 embedder）
  -> RRF 融合（K=60，合并 FTS5 排名 + 向量排名）
  -> 标签加权（每个匹配标签 +3%，上限 15%）
  -> 时效加权（14 天半衰期，最高 +5%）
  -> 按综合得分排序，返回 top-N 结果
```

## 核心特性

### TreeSearch FTS5 全文检索

synth-wiki 使用 **[TreeSearch](https://github.com/shibing624/TreeSearch)** 替代朴素 FTS5，这是一个结构感知的全文搜索引擎。文档被解析为树状结构（如 Markdown 标题层级），在检索时保留语义上下文。

相较于标准 FTS5 的优势：
- **结构感知**：理解 Markdown 标题、JSON 键等层级结构
- **无需 Embedding**：毫秒级关键词匹配，智能跨文档评分
- **Auto 模式**：根据文档类型自动切换 Tree 搜索（文章、论文）和 Flat 搜索（代码文件）
- **中文支持**：集成 jieba 分词器，中文检索质量优异

每个索引文档以 `treesearch.tree.Document` 存储，包含结构化节点，使搜索引擎能理解文档层级而非将内容视为扁平文本。

### 向量搜索（可选）

配置 Embedding 后，synth-wiki 会为摘要和概念文章生成向量嵌入。查询时，查询文本同样被嵌入，通过暴力余弦相似度与所有已存储向量进行比较。

支持的 Embedding 提供商（按级联顺序自动检测）：
1. **显式配置** — config.yaml 中的 `embed.model`
2. **Provider 默认值** — OpenAI: `text-embedding-3-small`、Gemini: `gemini-embedding-2-preview`、Voyage: `voyage-3-lite`、Mistral: `mistral-embed`
3. **Ollama 本地** — `nomic-embed-text`（Ollama 运行时自动检测）
4. **无** — 仅 FTS5 搜索（依然完全可用）

### RRF 融合

FTS5 与向量搜索结果通过 Reciprocal Rank Fusion (Cormack et al. 2009) 进行融合：

```
score(doc) = 1/(K + fts_rank) + 1/(K + vector_rank)
```

其中 `K = 60`。这确保了任一方法中排名靠前的文档都能获得较高的综合得分，无需在两个系统之间进行分数归一化。

### 标签加权

每个匹配 `boost_tag` 的搜索结果获得 +3% 分数加成，总计上限 15%。调用方可以借此优先展示特定来源类型或分类的结果。

### 时效加权

具有时间戳的结果会获得基于 14 天半衰期指数衰减的时效加权：

```
boost = 0.05 * 2^(-age_days / 14)
```

最大加权为 +5%（刚更新的文档）。超过约 2 个月的文档加权可忽略不计。

## 配置

```yaml
search:
  default_limit: 10     # 每次查询的最大返回数量（默认 10）
```

搜索配置有意保持精简。`default_limit` 控制返回结果数量，其他行为（RRF 常数、加权权重）均硬编码为经过充分测试的默认值。

### Embedding 配置

启用向量搜索需配置 Embedding 提供商：

```yaml
# 使用提供商的默认 Embedding 模型
embed:
  provider: auto   # 从 api.provider 自动检测

# 或显式指定
embed:
  provider: openai
  model: text-embedding-3-small
  api_key: ${OPENAI_API_KEY}
```

未配置 Embedding 时，synth-wiki 回退到仅 FTS5 搜索，借助 TreeSearch 依然能保证较高的检索质量。

### 本地 Embedding（Ollama）

如果本地运行了 Ollama 并安装了 Embedding 模型，synth-wiki 会自动检测：

```bash
# 拉取 Embedding 模型
ollama pull nomic-embed-text

# synth-wiki 会自动检测并使用，无需额外配置
```

## CLI 用法

```bash
# 基础搜索
synth-wiki search "注意力机制"

# 带标签过滤的搜索
synth-wiki search "transformer" --tags "paper,article"

# 限制结果数量
synth-wiki search "梯度下降" --limit 5
```

## Python API 用法

```python
from synth_wiki import DB, MemoryStore, VectorStore, Searcher, SearchOpts
from synth_wiki import paths, load_config
from synth_wiki.embed import new_from_config

cfg = load_config(paths.config_path(), "my-project")
db = DB.open(paths.db_path("my-project"))
mem = MemoryStore(paths.db_path("my-project"))
vec = VectorStore(db)
searcher = Searcher(mem, vec)

# 仅 FTS5 搜索
results = searcher.search(SearchOpts(query="注意力机制", limit=10))

# 混合搜索（含向量）
embedder = new_from_config(cfg)
query_vec = embedder.embed("注意力机制") if embedder else None
results = searcher.search(SearchOpts(query="注意力机制", limit=10), query_vec)

for r in results:
    print(f"[{r.score:.4f}] {r.article_path}")
    print(f"  {r.content[:120]}...")

mem.close()
db.close()
```

## 索引机制

文档在编译过程中的两个阶段被索引：

1. **Pass 1（摘要）** — 每个来源的摘要同时写入 FTS5 索引（通过 `MemoryStore`）和向量存储（如有 embedder）
2. **Pass 3（撰写文章）** — 每篇概念文章同时写入两个存储，附带实体类型和别名标签

FTS5 索引将条目存储为 TreeSearch `Document` 对象（含结构化节点），支持结构感知的检索。向量存储将嵌入以 float32 BLOB 形式持久化在 SQLite 中。

## 降级行为

搜索流水线能优雅降级：

- **未配置 Embedder** — 仅 FTS5 搜索，借助 TreeSearch 依然保持较高质量。
- **FTS5 索引为空** — 返回空结果。
- **向量维度不匹配** — 余弦相似度计算时静默跳过不匹配的向量。
- **Ollama 未运行** — 回退到 API Embedding 或仅 FTS5 搜索。

[**🌐English**](README.md) | **🇨🇳中文**

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
[![Wechat Group](https://img.shields.io/badge/wechat-group-green.svg?logo=wechat)](#社区与支持)

基于 [Andrej Karpathy 的想法](https://x.com/karpathy/status/2039805659525644595) 实现的 LLM 编译型个人知识库。使用 Python 编写。

将你的论文、文章和笔记放入文件夹，`synth-wiki` 会将它们编译为结构化、互相链接的 wiki —— 自动提取概念、发现交叉引用，并基于结构感知的搜索引擎支持全文检索问答。

- **输入源文件，输出 wiki。** 将文档放入文件夹。LLM 会阅读、摘要、提取概念，并生成互相关联的文章。
- **知识持续积累。** 每一个新源文件都会丰富已有文章。wiki 会随着内容增长变得越来越智能。
- **向你的 wiki 提问。** 基于 [TreeSearch](https://github.com/shibing624/TreeSearch) 的结构感知文档检索库。告别丢失上下文的 RAG 分块，获取带引用的高精准回答。
- **原生中文支持。** 内置 jieba 分词，支持毫秒级的纯中文高质量检索。

## 安装

### 从 PyPI 安装

```bash
pip install -U synth-wiki
```

### 从源码安装

```bash
git clone https://github.com/shibing624/synth-wiki.git
cd synth-wiki
pip install -e .
```

### 依赖

- Python >= 3.12
- click >= 8.1
- pyyaml >= 6.0
- httpx >= 0.27
- pytreesearch >= 0.1（FTS5 全文搜索）
- loguru >= 0.7

## 快速开始

### 1. 初始化项目

```bash
mkdir my-wiki && cd my-wiki
synth-wiki init
```

自动创建：
- `./raw/` — 源文件目录，将你的文档放入此处
- `./wiki/` — 编译输出目录
- `~/.synth_wiki/config.yaml` — 全局配置文件（自动生成，含合理默认值）

### 2. 配置 API Key

生成的配置默认使用 OpenAI 兼容 API。设置环境变量即可：

```bash
export OPENAI_API_KEY="sk-xxx"
export OPENAI_BASE_URL="https://api.openai.com/v1"  # 或任何兼容端点
```

也可以直接编辑 `~/.synth_wiki/config.yaml`：

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

支持的 provider: `openai`, `openai-compatible`, `anthropic`, `gemini`, `ollama`。

### 3. 添加源文件并编译

```bash
# 放入源文件
cp ~/papers/*.pdf raw/
cp ~/articles/*.md raw/

# 编译
synth-wiki compile

# Watch 模式（文件变更时自动重新编译）
synth-wiki compile --watch

# 搜索
synth-wiki search "attention mechanism"
```

## 支持的源文件格式

只需将文件放入源文件夹 —— `synth-wiki` 会自动检测格式并提取内容。

| 格式 | 扩展名 | 提取内容 |
|------|--------|---------|
| Markdown | `.md` | 正文与树状层级，frontmatter 单独解析 |
| PDF | `.pdf` | 提取全文文本 |
| Word | `.docx` | 文档文本 |
| JSON / JSONL | `.json`, `.jsonl` | 嵌套结构解析 |
| 代码 | `.py`, `.java`, `.go` 等 | 基于 AST 和正则的结构化提取 |
| 纯文本 | `.txt`, `.csv` | 原始内容 |
| 图片 | `.png`, `.jpg`, `.svg` | 图片文件 |

## 命令

| 命令 | 说明 |
|------|------|
| `synth-wiki init [--name] [--source] [--output] [--vault]` | 初始化项目（所有参数可选） |
| `synth-wiki compile [--watch] [--dry-run] [--fresh] [--batch] [--no-cache]` | 将源文件编译为 wiki 文章 |
| `synth-wiki search "query" [--tags] [--limit]` | 通过 TreeSearch 引擎进行文档搜索 |
| `synth-wiki query "question"` | 对 wiki 进行自然语言问答 |
| `synth-wiki ingest <url\|path>` | 添加单个源文件 |
| `synth-wiki lint [--fix] [--pass-name]` | 检查并修复文章质量 |
| `synth-wiki status` | 查看 wiki 统计和健康状态 |
| `synth-wiki doctor` | 检查配置和连接状态 |
| `synth-wiki projects` | 列出所有配置的项目 |
| `synth-wiki serve [--transport] [--port]` | 启动 MCP 服务器（IDE/Agent 集成） |

## 目录结构

```
~/.synth_wiki/                    # 全局状态目录
├── config.yaml                   # 全局配置（所有项目共享）
├── db/
│   └── my-wiki.db                # 项目 SQLite 数据库（WAL 模式）
├── manifests/
│   └── my-wiki.json              # 来源清单和编译状态
├── state/
│   └── my-wiki.json              # 编译断点（成功后自动删除）
└── lintlog/
    └── my-wiki/                  # Lint 报告历史

./raw/                            # 源文件目录（用户管理）
├── paper-1.md
├── notes.txt
└── captures/                     # URL 导入的文件

./wiki/                           # 编译输出目录（自动生成）
├── SCHEMA.md                     # 领域约定、标签体系、建页阈值
├── index.md                      # 自动生成的内容目录（按类型分节）
├── summaries/                    # Pass 1: 来源摘要
├── concepts/                     # Pass 3: 百科文章（概念/技术/主张）
│   ├── transformer.md
│   └── self-attention.md
├── entities/                     # 实体页面（人物、组织、产品、模型）
├── comparisons/                  # 对比分析页面
├── connections/
├── outputs/
├── images/                       # 提取的图片
├── archive/
├── prompts/                      # 自定义 prompt（可选）
└── CHANGELOG.md                  # 编译历史
```

## 知识导入

### 导入本地文件

```bash
synth-wiki ingest /path/to/document.md
synth-wiki ingest /path/to/notes.txt
```

`ingest` 命令会：
1. 检测文件类型（根据扩展名自动判断）
2. 将文件复制到项目配置的 source 目录
3. 计算 SHA-256 哈希
4. 在 manifest 中注册该来源，标记为待编译
5. 输出导入结果（路径、类型、大小）

### 导入 URL

```bash
synth-wiki ingest https://example.com/article
```

URL 导入会：
1. 使用 httpx 下载页面内容（30 秒超时，自动跟随重定向）
2. 将内容包装为 Markdown 文件，添加 YAML frontmatter 记录来源 URL 和导入时间
3. 保存到 source 目录，文件名从 URL 自动 slugify
4. 在 manifest 中注册

### 编译流水线

导入的来源经过 4 步编译处理：

```
源文件 (MD/PDF/DOCX/JSON/Code/TXT/Image)
        │
        ▼
  ┌───────────────┐
  │  1. Diff      │  对比 manifest，检测 新增/修改/删除
  └──────┬────────┘
         │  变更列表
         ▼
  ┌───────────────┐
  │  2. Summarize │  LLM 并发生成每个来源的摘要
  └──────┬────────┘
         │  摘要列表
         ▼
  ┌───────────────┐
  │  3. Extract   │  LLM 从摘要中批量提取概念、别名、类型
  │   Concepts    │
  └──────┬────────┘
         │  概念列表
         ▼
  ┌───────────────┐
  │  4. Write     │  LLM 为每个概念撰写百科文章
  │   Articles    │  自动创建 [[wikilinks]] 和 ontology 关系
  └──────┬────────┘
         │
         ▼
  结构化 Wiki（摘要 + 概念文章 + 知识图谱）
```

编译支持断点续传：如果中途失败，下次编译会从上次的检查点继续。使用 `--fresh` 忽略检查点重新开始。

> **详见：** [Knowledge Capture: Ingest and Learning](docs/mcp-knowledge-capture.md)

## Watch 模式

`synth-wiki compile --watch` 启用实时文件监听。源文件新增、修改或删除时，自动触发编译。

- **主模式**：使用 [watchdog](https://github.com/gorakhargosh/watchdog)（macOS 上使用 fsevents，Linux 上使用 inotify）监听原生文件系统事件
- **降级模式**：未安装 watchdog 时，自动降级为 polling（2 秒间隔）
- **防抖**：2 秒防抖，将连续的文件变更合并为一次编译
- **并发保护**：基于锁机制防止重复编译
- **初始编译**：启动时先跑一次编译补漏

安装 watchdog 获得最佳性能：

```bash
pip install synth-wiki[watch]
```

## 质量检查（Linter）

`synth-wiki lint` 对所有 wiki 文章运行质量检查。使用 `--fix` 自动修复可修复的问题。

| 检查项 | 说明 | 自动修复 |
|--------|------|----------|
| `completeness` | 指向不存在文章的 `[[wikilinks]]` | 否 |
| `style` | 缺少 YAML frontmatter | 是 |
| `orphans` | 知识图谱中无关系的孤立实体 | 否 |
| `consistency` | 已标记的 `contradicts` 矛盾关系 | 否 |
| `impute` | 占位标记 `[TODO]`、`[UNKNOWN]`、`[TBD]` | 否 |
| `staleness` | 超过 90 天未更新的文章 | 否 |
| `contradiction_detection` | 跨源矛盾检测（共享同一来源的文章间 confidence 冲突） | 否 |

```bash
synth-wiki lint                    # 运行所有检查
synth-wiki lint --fix              # 自动修复可修复项
synth-wiki lint --pass-name style  # 只运行单个检查
```

## 知识图谱（Ontology）

synth-wiki 在编译过程中自动构建知识图谱，将概念、技术、来源等实体通过有类型的边连接起来。知识图谱存储在 SQLite 中，通过 CHECK 约束保证数据完整性。

### 工作原理

编译 Pass 3 写出百科文章后，`_extract_relations()` 会扫描文章内容中的 `[[wikilinks]]`，并检查链接附近是否出现关键词。如果匹配，就创建一条有类型的关系边。

例如，一篇关于 Flash Attention 的文章包含：

> Flash Attention **optimizes** the memory access pattern of [[Self-Attention]]

编译器会创建边：`Flash-Attention --optimizes--> Self-Attention`

### 实体类型

| 类型 | 说明 | 创建时机 |
|------|------|----------|
| `concept` | 通用概念 | 默认类型，Pass 3 写文章时创建 |
| `technique` | 具体技术/方法 | 概念 type 为 "technique" 时 |
| `entity` | 人物、组织、产品、模型 | 概念 type 为 "entity" 时 |
| `comparison` | 对比分析 | 概念 type 为 "comparison" 时 |
| `source` | 来源文件 | 概念引用的每个源文件自动创建 |
| `claim` | 断言/结论 | 概念 type 为 "claim" 时 |
| `artifact` | 产出物 | 保留类型 |

### 关系类型

| 类型 | 提取关键词 | 说明 |
|------|-----------|------|
| `implements` | implements, implementation of | A 是 B 的实现 |
| `extends` | extends, extension of, builds on | A 扩展了 B |
| `optimizes` | optimizes, optimization of, improves upon | A 优化了 B |
| `contradicts` | contradicts, conflicts with | A 与 B 矛盾 |
| `cites` | *（程序自动创建）* | A 引用了来源 B |
| `prerequisite_of` | prerequisite, requires knowledge of | A 是 B 的前置知识 |
| `trades_off` | trade-off, tradeoff, trades off | A 与 B 存在权衡 |
| `derived_from` | *（程序自动创建）* | A 派生自 B |

### 图遍历

```python
from synth_wiki.ontology import Store, TraverseOpts, Direction

store = Store(db)

# 从某实体出发，沿出边 BFS 遍历 2 层
neighbors = store.traverse("flash-attention", TraverseOpts(
    direction=Direction.OUTBOUND,
    max_depth=2,
))

# 沿入边遍历（谁指向了这个实体）
inbound = store.traverse("self-attention", TraverseOpts(
    direction=Direction.INBOUND,
    max_depth=1,
))

# 双向遍历，按关系类型过滤
both = store.traverse("transformer", TraverseOpts(
    direction=Direction.BOTH,
    max_depth=1,
    relation_type="extends",
))
```

### 环检测

```python
cycles = store.detect_cycles("flash-attention")
# 返回值: [["flash-attention", "B", "C", "flash-attention"], ...]
```

## 由 TreeSearch 驱动的卓越搜索质量

synth-wiki 采用混合搜索流水线，将 **TreeSearch auto mode**（Best-First tree walk + FTS5）与可选的向量语义搜索相结合，通过 Reciprocal Rank Fusion (RRF) 进行融合。

### 工作原理

```
用户查询
  -> TreeSearch auto mode（树遍历 + FTS5 评分，自动 flat/tree 路由）
  -> 可选的向量余弦相似度搜索（需配置 embedder）
  -> RRF 融合（K=60，合并 TreeSearch 排名 + 向量排名）
  -> 标签加权（每个匹配标签 +3%，上限 15%）
  -> 时效加权（14 天半衰期，最高 +5%）
  -> 按综合得分排序，返回 top-N 结果
```

### TreeSearch Auto Mode

有别于将文档切碎导致上下文断裂的传统向量 RAG 方案，synth-wiki 使用 **[TreeSearch](https://github.com/shibing624/TreeSearch)** 的 auto mode — 效果最好的搜索策略。

- **Best-First 树遍历**：锚点检索 → 扩展 → 路径评分，基于文档树结构搜索，不是简单的 BM25 平铺排序
- **Auto 模式路由**：根据文档 `source_type` 自动切换 Tree 搜索（文章、论文、Markdown）和 Flat 搜索（代码文件）
- **文档路由**：多文档查询时先通过 FTS5 粗选 top-K 相关文档，再对每个文档进行深度树搜索
- **无需 Embedding**：毫秒级结构感知匹配，智能跨文档评分
- **中文支持**：集成 jieba 分词器，中文检索质量优异

### 向量搜索（可选）

配置 Embedding 后，synth-wiki 会为摘要和概念文章生成向量嵌入。查询时，查询文本同样被嵌入，通过余弦相似度与所有已存储向量进行比较。

支持的 Embedding 提供商（按级联顺序自动检测）：
1. **显式配置** — config.yaml 中的 `embed.model`
2. **Provider 默认值** — OpenAI: `text-embedding-3-small`、Gemini: `gemini-embedding-2-preview`、Voyage: `voyage-3-lite`、Mistral: `mistral-embed`
3. **Ollama 本地** — `nomic-embed-text`（Ollama 运行时自动检测）
4. **无** — 仅 TreeSearch 搜索（auto mode tree walk 依然完全可用）

### RRF 融合

TreeSearch 与向量搜索结果通过 Reciprocal Rank Fusion 进行融合：

```
score(doc) = 1/(K + treesearch_rank) + 1/(K + vector_rank)
```

其中 `K = 60`。任一方法中排名靠前的文档都能获得较高的综合得分。

### 降级行为

搜索流水线能优雅降级：
- **未配置 Embedder** — 仅 TreeSearch，auto mode tree walk 依然保持高质量。
- **索引为空** — 返回空结果。
- **向量维度不匹配** — 余弦相似度计算时静默跳过不匹配的向量。
- **Ollama 未运行** — 回退到 API Embedding 或仅 TreeSearch 搜索。

## 配置详解

### 完整配置示例

```yaml
# 全局 API 配置
api:
  provider: openai-compatible      # openai, anthropic, gemini, ollama, openai-compatible
  api_key: ${OPENAI_API_KEY}       # 支持 ${ENV_VAR} 环境变量展开
  base_url: ${OPENAI_BASE_URL}
  rate_limit: 0                    # 每分钟请求数限制，0 为不限
  extra_body: {}

# 模型配置（按编译阶段分别指定）
models:
  summarize: gpt-4o-mini           # Pass 1: 摘要
  extract: gpt-4o-mini             # Pass 2: 概念提取
  write: gpt-4o-mini               # Pass 3: 文章撰写
  lint: gpt-4o-mini                # Linter
  query: gpt-4o-mini               # 查询（预留）

# Embedding 配置（可选，不配置则走自动级联）
embed:
  provider: auto                   # auto, openai, gemini, voyage, mistral, ollama
  model: ""                        # 空则使用 provider 默认模型
  dimensions: 0                    # 0 则自动检测
  api_key: ""                      # 空则复用 api.api_key
  base_url: ""

# 编译器配置
compiler:
  max_parallel: 4                  # 每阶段最大 LLM 并发数
  debounce_seconds: 2
  summary_max_tokens: 2000         # 摘要最大 token
  article_max_tokens: 4000         # 文章最大 token
  auto_commit: true                # 编译后自动 git commit
  auto_lint: true                  # 编译后自动 lint
  mode: ""                         # standard, batch, auto
  prompt_cache: null               # null=true（默认启用缓存）
  page_threshold: 1                # 建页最低源数量（2 = Karpathy 规则：2+ 源才建页）

# 搜索配置
search:
  default_limit: 10

# Linter 配置
linting:
  auto_fix_passes:
    - consistency
    - completeness
    - style
  staleness_threshold_days: 90

# MCP 服务器配置
serve:
  transport: stdio                 # stdio（Claude Code / Cursor）, sse（Web 客户端）
  port: 3333                       # SSE 模式端口

# 语言（影响文章生成语言）
language: zh-CN                    # zh-CN, zh-TW, en, ja, ko

# 项目定义
projects:
  my-wiki:
    description: "个人知识库"
    sources:
      - path: /Users/me/raw
        type: auto
        watch: true
    output: /Users/me/wiki
```

### 多项目配置

```yaml
projects:
  research:
    description: "AI 研究笔记"
    sources:
      - path: ~/research/raw
    output: ~/research/wiki
    models:
      write: gpt-4o              # 研究项目用更好的模型写文章

  work:
    description: "工作笔记"
    sources:
      - path: ~/work/raw
    output: ~/work/wiki
```

使用 `--project` 指定操作哪个项目：

```bash
synth-wiki compile --project research
synth-wiki status --project work
synth-wiki search --project research "attention"
```

如果只有一个项目，`--project` 可以省略。

### LLM Provider 配置示例

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

**OpenAI-Compatible (OpenRouter, Together, Groq 等):**
```yaml
api:
  provider: openai-compatible
  base_url: https://openrouter.ai/api/v1
  api_key: ${OPENROUTER_API_KEY}
models:
  summarize: google/gemini-2.5-flash-preview
  write: anthropic/claude-sonnet-4
```

**Ollama（本地运行，无需 API key）:**
```yaml
api:
  provider: ollama
  base_url: http://localhost:11434
models:
  summarize: llama3
  write: llama3
```

### Embedding 级联检测

synth-wiki 使用三级级联策略自动选择 Embedding 提供商：

| Provider | 默认模型 | 维度 |
|----------|---------|------|
| openai | text-embedding-3-small | 1536 |
| gemini | gemini-embedding-2-preview | 768 |
| voyage | voyage-3-lite | 1024 |
| mistral | mistral-embed | 1024 |
| ollama | nomic-embed-text | 768 |

### Vault Overlay 模式（Obsidian）

如果你已经在使用 Obsidian，synth-wiki 可以作为 overlay 叠加在现有 vault 上：

```bash
synth-wiki init --name my-vault --vault --source ~/my-vault --output _wiki
```

- 源文件来自 vault 中已有的文件夹
- 输出写入 vault 内的 `_wiki/` 子目录
- Obsidian 可以直接浏览编译输出
- `[[wikilinks]]` 与 Obsidian 的链接格式兼容

**将 wiki 输出目录作为 Obsidian vault 使用：**

编译输出目录（`wiki/`）可以直接作为独立的 Obsidian vault：

1. 打开 Obsidian，选择 "Open folder as vault"，选择你的 `wiki/` 目录
2. 概念文章中的 `[[wikilinks]]` 会渲染为可点击的链接
3. Graph View 可视化所有概念之间的知识网络
4. YAML frontmatter 支持 Dataview 查询（如 `TABLE tags FROM "concepts" WHERE confidence = "high"`）
5. `SCHEMA.md` 和 `index.md` 自动生成 -- `index.md` 是可导航的内容目录
6. 编译过程中提取的图片存储在 `images/` -- 将其设为 Obsidian 的附件文件夹

推荐安装的 Obsidian 插件：
- **Dataview** -- 跨 wiki 页面进行结构化查询
- **Graph Analysis** -- 更深入的知识图谱探索

## MCP 服务器（IDE / Agent 集成）

synth-wiki 内置 [MCP](https://modelcontextprotocol.io/) 服务器，将所有 wiki 操作暴露为 MCP 工具。支持与 Claude Code、Cursor、Windsurf 及任何 MCP 兼容客户端集成。

### 快速开始

```bash
# 安装 MCP 支持
pip install synth-wiki[mcp]

# 启动服务器（stdio 模式，适用于 Claude Code / Cursor）
synth-wiki serve

# SSE 模式（适用于 Web 客户端）
synth-wiki serve --transport sse --port 3333
```

### Claude Code 集成

在 Claude Code MCP 配置中添加（`~/.claude.json` 或项目 `.mcp.json`）：

```json
{
  "mcpServers": {
    "synth-wiki": {
      "command": "synth-wiki",
      "args": ["serve", "--project", "my-wiki"]
    }
  }
}
```

### 可用 MCP 工具

| 工具 | 说明 |
|------|------|
| `search` | 通过 TreeSearch + 可选向量重排序搜索 wiki |
| `query` | 提问并获得 LLM 合成的带引用回答 |
| `ingest` | 添加源文件或 URL 用于编译 |
| `compile` | 将源文件编译为 wiki 文章 |
| `lint` | 对 wiki 文章运行质量检查 |
| `status` | 查看 wiki 统计和健康状态 |
| `read_article` | 按 slug 名称读取特定 wiki 文章 |
| `list_articles` | 列出所有 wiki 文章，可按类型过滤 |

### 使用示例

配置完成后，可以在 Claude Code 中直接对话：

```
> 在我的 wiki 中搜索 "注意力机制"
> 我的 wiki 里关于 transformer 有什么内容？
> 将这个 URL 导入我的 wiki: https://example.com/paper
> 编译我的 wiki
> 对我的 wiki 做一次质量检查
```

## Python API

### 搜索

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

### 知识导入

```python
from synth_wiki.wiki import ingest_path, ingest_url

# 导入本地文件
result = ingest_path("my-project", "/path/to/document.md")
print(f"Ingested: {result.source_path} ({result.type}, {result.size} bytes)")

# 导入 URL
result = ingest_url("my-project", "https://example.com/article")
print(f"Ingested: {result.source_path} ({result.type}, {result.size} bytes)")
```

### 知识图谱

```python
from synth_wiki.ontology import Store, TraverseOpts, Direction

store = Store(db)

# 添加/更新实体（upsert）
store.add_entity(entity)

# 获取单个实体
entity = store.get_entity("flash-attention")

# 列出所有实体（可按类型过滤）
all_concepts = store.list_entities("concept")

# 添加关系（upsert，source+target+relation 唯一约束）
store.add_relation(relation)

# 查询关系
rels = store.get_relations("flash-attention", Direction.OUTBOUND)
rels = store.get_relations("flash-attention", Direction.BOTH, "optimizes")

# 统计
store.entity_count()           # 总实体数
store.entity_count("concept")  # 特定类型实体数
store.relation_count()         # 总关系数
```

## 致谢

- [xoai/sage-wiki](https://github.com/xoai/sage-wiki) — Go 语言版本的 llm-wiki
- [Andrej Karpathy 的 llm-wiki 想法](https://x.com/karpathy/status/2039805659525644595) — 项目灵感来源

## 社区与支持

- **GitHub Issues** — [提交 issue](https://github.com/shibing624/synth-wiki/issues)
- **微信群** — 添加微信号 `xuming624`，备注 "nlp"，加入技术交流群

<img src="https://github.com/shibing624/TreeSearch/blob/main/docs/wechat.jpeg" width="200" />

## 引用

如果您在研究中使用了 synth-wiki，请引用：

```bibtex
@software{xu2026synthwiki,
  author = {Xu, Ming},
  title = {synth-wiki: LLM-Compiled Personal Knowledge Base},
  year = {2026},
  publisher = {GitHub},
  url = {https://github.com/shibing624/synth-wiki}
}
```

## 贡献

欢迎贡献！请提交 [Pull Request](https://github.com/shibing624/synth-wiki/pulls)。

## 许可证

[Apache License 2.0](LICENSE)

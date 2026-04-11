# Installation and Configuration

synth-wiki 是一个 Python CLI 工具，通过 pip 安装后即可使用。所有持久化状态存储在 `~/.synth_wiki/` 目录下，项目目录只包含源文件和编译输出。

## 安装

### 从 PyPI 安装

```bash
pip install synth-wiki
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

```bash
# 初始化项目
synth-wiki init --name my-wiki --source ./raw --output ./wiki

# 编辑配置文件，设置 API key
vim ~/.synth_wiki/config.yaml

# 复制源文件到 raw/ 目录
cp ~/notes/*.md ./raw/

# 编译
synth-wiki compile

# 搜索
synth-wiki search "transformer architecture"

# 查看状态
synth-wiki status
```

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
        └── lint-20250115-083000.json

./raw/                            # 源文件目录（用户管理）
├── paper-1.md
├── notes.txt
└── captures/                     # URL 导入的文件

./wiki/                           # 编译输出目录（自动生成）
├── summaries/                    # Pass 1: 来源摘要
├── concepts/                     # Pass 3: 百科文章
│   ├── transformer.md
│   └── self-attention.md
├── connections/
├── outputs/
├── images/                       # 提取的图片
├── archive/
├── prompts/                      # 自定义 prompt（可选）
└── CHANGELOG.md                  # 编译历史
```

## 配置文件详解

配置文件位于 `~/.synth_wiki/config.yaml`，支持多项目。全局设置作为默认值，每个项目可以覆盖任意字段。

### 完整配置示例

```yaml
# 全局 API 配置
api:
  provider: openai-compatible      # openai, anthropic, gemini, ollama, openai-compatible
  api_key: ${OPENAI_API_KEY}       # 支持 ${ENV_VAR} 环境变量展开
  base_url: ${OPENAI_BASE_URL}
  rate_limit: 0                    # 每分钟请求数限制，0 为不限
  extra_body: {}                   # 附加请求体参数

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
    # 项目级覆盖（可选）
    # models:
    #   write: claude-sonnet-4
```

### 多项目配置

```yaml
api:
  provider: openai
  api_key: ${OPENAI_API_KEY}

models:
  summarize: gpt-4o-mini
  extract: gpt-4o-mini
  write: gpt-4o-mini

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

## LLM Provider 配置

### OpenAI

```yaml
api:
  provider: openai
  api_key: ${OPENAI_API_KEY}
models:
  summarize: gpt-4o-mini
  write: gpt-4o
```

### Anthropic

```yaml
api:
  provider: anthropic
  api_key: ${ANTHROPIC_API_KEY}
models:
  summarize: claude-sonnet-4
  write: claude-sonnet-4
```

### Gemini

```yaml
api:
  provider: gemini
  api_key: ${GEMINI_API_KEY}
models:
  summarize: gemini-2.5-flash
  write: gemini-2.5-flash
```

### OpenAI-Compatible (OpenRouter, Together, Groq 等)

任何兼容 OpenAI API 的服务都可以使用：

```yaml
# OpenRouter
api:
  provider: openai-compatible
  base_url: https://openrouter.ai/api/v1
  api_key: ${OPENROUTER_API_KEY}
models:
  summarize: google/gemini-2.5-flash-preview
  write: anthropic/claude-sonnet-4
```

```yaml
# Together AI
api:
  provider: openai-compatible
  base_url: https://api.together.xyz/v1
  api_key: ${TOGETHER_API_KEY}
```

```yaml
# Groq
api:
  provider: openai-compatible
  base_url: https://api.groq.com/openai/v1
  api_key: ${GROQ_API_KEY}
```

### Ollama (本地运行)

不需要 API key，数据不离开本地网络：

```yaml
api:
  provider: ollama
  base_url: http://localhost:11434
models:
  summarize: llama3
  write: llama3
```

## Embedding 级联检测

synth-wiki 使用三级级联策略自动选择 embedding provider：

1. **显式配置** — 如果 `embed.model` 非空且有 API key，使用指定的 embedding 模型
2. **Provider 默认** — 如果主 LLM provider 有对应的默认 embedding 模型，使用之
3. **Ollama 本地** — 如果本地 Ollama 可用，使用 `nomic-embed-text` (768 维)
4. **None** — 以上都不可用时，禁用向量搜索，仅使用 FTS5 全文搜索

各 provider 的默认 embedding 模型：

| Provider | 默认模型 | 维度 |
|----------|---------|------|
| openai | text-embedding-3-small | 1536 |
| gemini | gemini-embedding-2-preview | 768 |
| voyage | voyage-3-lite | 1024 |
| mistral | mistral-embed | 1024 |
| ollama | nomic-embed-text | 768 |

## CLI 命令参考

```bash
synth-wiki [OPTIONS] COMMAND [ARGS]
```

全局选项：

| 选项 | 说明 |
|------|------|
| `--project NAME` | 指定项目名（多项目时必填） |
| `--config PATH` | 指定配置文件路径（默认 `~/.synth_wiki/config.yaml`） |
| `-v, --verbose` | 增加日志详细度（可叠加 -vv） |

### init

```bash
synth-wiki init [OPTIONS]
```

| 选项 | 默认值 | 说明 |
|------|--------|------|
| `--name` | 当前目录名 | 项目名称 |
| `--source` | `./raw` | 源文件目录 |
| `--output` | `./wiki` | 输出目录 |
| `--vault` | false | Obsidian vault overlay 模式 |
| `--model` | gpt-4o-mini | 默认 LLM 模型 |

### compile

```bash
synth-wiki compile [OPTIONS]
```

| 选项 | 说明 |
|------|------|
| `--dry-run` | 只显示变更，不实际编译 |
| `--fresh` | 忽略编译断点，全部重新编译 |
| `--batch` | 使用 batch API |
| `--no-cache` | 禁用 prompt 缓存 |

### search

```bash
synth-wiki search [OPTIONS] QUERY...
```

| 选项 | 默认值 | 说明 |
|------|--------|------|
| `--tags` | "" | 逗号分隔的标签过滤 |
| `--limit` | 10 | 最大结果数 |

### lint

```bash
synth-wiki lint [OPTIONS]
```

| 选项 | 说明 |
|------|------|
| `--fix` | 自动修复可修复的问题 |
| `--pass-name` | 只运行指定的 lint pass |

### 其他命令

| 命令 | 说明 |
|------|------|
| `status` | 显示项目统计和健康状态 |
| `ingest TARGET` | 导入文件或 URL |
| `doctor` | 检查配置和连接状态 |
| `projects` | 列出所有配置的项目 |

## Vault Overlay 模式

如果你已经在使用 Obsidian，synth-wiki 可以作为 overlay 叠加在现有 vault 上：

```bash
synth-wiki init --name my-vault --vault --source ~/my-vault --output _wiki
```

Vault overlay 模式下：
- 源文件来自 vault 中已有的文件夹
- 输出写入 vault 内的 `_wiki/` 子目录
- Obsidian 可以直接浏览编译输出
- `[[wikilinks]]` 与 Obsidian 的链接格式兼容

## 健康检查

```bash
synth-wiki doctor
```

Doctor 检查以下项目：

- **config** — 配置文件是否加载成功
- **database** — SQLite 数据库是否存在
- **sources** — 源文件目录是否存在
- **api** — API key 是否配置
- **output** — 输出目录是否存在

输出示例：

```
  [OK] config: Project 'my-wiki' loaded
  [OK] database: DB exists at ~/.synth_wiki/db/my-wiki.db
  [WARN] api: API key not set for openai-compatible
  [OK] output: Output: /Users/me/wiki

All checks passed.
```

# Knowledge Capture: Ingest and Learning

synth-wiki 提供多种方式将知识输入到你的个人 wiki 中：本地文件导入、URL 抓取、以及编译过程中自动产生的 learnings 记录。

## Ingest: 导入知识来源

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

支持的文本格式：`.md`、`.txt`、`.py`、`.js`、`.ts`、`.go`、`.java`、`.rs`、`.c`、`.cpp`、`.csv`、`.json`、`.yaml`、`.html`、`.xml`、`.eml` 等。

二进制格式（`.pdf`、`.docx`、`.pptx`、`.xlsx`、`.epub`）目前尚未实现提取，会抛出 `NotImplementedError`。使用文本格式（.md, .txt）作为替代。

### 导入 URL

```bash
synth-wiki ingest https://example.com/article
```

URL 导入会：

1. 使用 httpx 下载页面内容（30 秒超时，自动跟随重定向）
2. 将内容包装为 Markdown 文件，添加 YAML frontmatter 记录来源 URL 和导入时间
3. 保存到 source 目录，文件名从 URL 自动 slugify
4. 在 manifest 中注册

生成的文件格式：

```markdown
---
source_url: https://example.com/article
ingested_at: 2025-01-15T08:30:00+00:00
---

(页面内容)
```

### Python API

```python
from synth_wiki.wiki import ingest_path, ingest_url

# 导入本地文件
result = ingest_path("my-project", "/path/to/document.md")
print(f"Ingested: {result.source_path} ({result.type}, {result.size} bytes)")

# 导入 URL
result = ingest_url("my-project", "https://example.com/article")
print(f"Ingested: {result.source_path} ({result.type}, {result.size} bytes)")
```

## 文件类型检测

synth-wiki 根据文件扩展名自动检测来源类型：

| 扩展名 | 类型 | 说明 |
|--------|------|------|
| `.md`, `.txt`, `.html` | article | 文章/笔记 |
| `.pdf`, `.docx`, `.epub` | paper | 论文/文档 |
| `.py`, `.js`, `.go` 等 | code | 代码文件 |
| `.csv`, `.json`, `.yaml` | data | 数据文件 |
| `.png`, `.jpg`, `.svg` | image | 图片文件 |

未识别的扩展名默认为 `article` 类型。

## Learnings: 自学习记录

synth-wiki 的 linter 在扫描文章时会产生 learnings，存储在 SQLite 的 `learnings` 表中：

```sql
CREATE TABLE learnings (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL,        -- 学习类型
    content TEXT NOT NULL,     -- 学习内容
    tags TEXT,                 -- 标签（JSON）
    created_at TEXT,           -- 创建时间
    source_lint_pass TEXT      -- 来源 lint pass
);
```

Linter 的 6 个 pass 在运行过程中可以记录发现的模式和问题：

| Lint Pass | 说明 |
|-----------|------|
| completeness | 检查文章完整性（frontmatter、必要章节） |
| style | 检查写作风格（标题层级、链接格式） |
| orphans | 检查孤立文章（无入链/出链） |
| consistency | 检查交叉引用一致性 |
| impute | 推断缺失信息 |
| staleness | 检查过期文章 |

## 完整工作流

典型的知识捕获到编译的完整流程：

```bash
# 1. 初始化项目
synth-wiki init --name my-knowledge --source ./raw --output ./wiki

# 2. 配置 API（编辑 ~/.synth_wiki/config.yaml）
#    设置 api.provider, api.api_key, models 等

# 3. 导入知识来源
synth-wiki ingest ~/notes/deep-learning.md
synth-wiki ingest https://arxiv.org/abs/2301.00001
cp ~/papers/*.md ./raw/           # 或直接复制到 source 目录

# 4. 编译
synth-wiki compile
# 输出: +3 added, ~0 modified, -0 removed, 3 summarized, 12 concepts, 12 articles

# 5. 查看状态
synth-wiki status
# Project: my-knowledge (greenfield)
# Sources: 3 (0 pending)
# Concepts: 12
# Entries: 15 indexed
# Vectors: 15 (768-dim)
# Entities: 18, Relations: 24

# 6. 搜索
synth-wiki search "attention mechanism"

# 7. 检查质量
synth-wiki lint
```

## 编译 Pipeline

导入的来源经过 4 步编译处理：

1. **Diff** — 对比 manifest 和实际文件，找出新增/修改/删除的来源
2. **Summarize** — LLM 生成每个来源的摘要
3. **Extract Concepts** — LLM 从摘要中提取概念、别名、类型
4. **Write Articles** — LLM 为每个概念撰写百科文章，自动创建 wikilinks 和 ontology 关系

编译支持断点续传：如果中途失败，下次编译会从上次的检查点继续。使用 `--fresh` 忽略检查点重新开始。

## Manifest 追踪

每个来源在 manifest 中记录：

- 文件路径和 SHA-256 哈希（用于增量编译的变更检测）
- 文件类型和大小
- 编译状态（是否已编译、摘要路径、提取的概念列表）

Manifest 存储在 `~/.synth_wiki/manifests/{project}.json`。

# Ontology: Entity-Relation Knowledge Graph

synth-wiki 在编译过程中自动构建知识图谱（ontology），将概念、技术、来源等实体通过有类型的边连接起来。知识图谱的数据存储在 SQLite 数据库中，通过 SQL CHECK 约束保证数据完整性。

## 工作原理

编译 Pass 3（write_articles）写出百科文章后，`_extract_relations()` 会扫描文章内容中的 `[[wikilinks]]`，并检查链接附近是否出现关键词。如果匹配，就创建一条有类型的关系边。

例如，一篇关于 Flash Attention 的文章包含：

> Flash Attention **optimizes** the memory access pattern of [[Self-Attention]]

编译器检测到关键词 "optimizes" 和 wikilink `[[Self-Attention]]` 共同出现，创建边：

```
Flash-Attention --optimizes--> Self-Attention
```

此外，`cites` 关系在编译时自动创建——每个概念的来源文件（sources）都会生成一条 `cites` 边。

## 实体类型

SQLite 通过 CHECK 约束限定 5 种实体类型：

| 类型 | 说明 | 创建时机 |
|------|------|----------|
| `concept` | 通用概念 | 默认类型，Pass 3 写文章时创建 |
| `technique` | 具体技术/方法 | 概念 type 为 "technique" 时 |
| `source` | 来源文件 | 概念引用的每个源文件自动创建 |
| `claim` | 断言/结论 | 概念 type 为 "claim" 时 |
| `artifact` | 产出物 | 保留类型 |

实体结构：

```python
@dataclass
class Entity:
    id: str           # 唯一标识（通常是概念名）
    type: str         # 上述 5 种之一
    name: str         # 人类可读名称
    definition: str   # 定义文本
    article_path: str # 对应文章路径
    created_at: str
    updated_at: str
```

## 关系类型

SQLite 通过 CHECK 约束限定 8 种关系类型：

| 类型 | 提取关键词 | 说明 |
|------|-----------|------|
| `implements` | implements, implementation of | A 是 B 的实现 |
| `extends` | extends, extension of, builds on | A 扩展了 B |
| `optimizes` | optimizes, optimization of, improves upon | A 优化了 B |
| `contradicts` | contradicts, conflicts with | A 与 B 矛盾 |
| `cites` | *(程序自动创建)* | A 引用了来源 B |
| `prerequisite_of` | prerequisite, requires knowledge of | A 是 B 的前置知识 |
| `trades_off` | trade-off, tradeoff, trades off | A 与 B 存在权衡 |
| `derived_from` | *(程序自动创建)* | A 派生自 B |

其中 `cites` 和 `derived_from` 没有关键词匹配，由代码逻辑直接创建。

## 关系提取逻辑

`_extract_relations()` 的工作流程：

1. 用正则 `\[\[([^\]]+)\]\]` 提取文章中所有 wikilink 目标
2. 排除自引用（目标 == 当前概念）
3. 将文章内容转为小写
4. 对每个 wikilink 目标，遍历关键词模式表
5. 如果关键词和目标名都出现在文章内容中，创建关系边
6. 关系 ID 格式：`{concept_id}-{relation_type}-{target_id}`
7. 使用 `ON CONFLICT DO NOTHING` 避免重复边

关系边还有自环保护：`source_id == target_id` 时抛出 `ValueError`。

## 图遍历

`ontology.Store` 提供 BFS 遍历和环检测：

### BFS 遍历

```python
from synth_wiki.ontology import Store, TraverseOpts, Direction

store = Store(db)

# 从某实体出发，沿出边遍历 2 层
neighbors = store.traverse("flash-attention", TraverseOpts(
    direction=Direction.OUTBOUND,
    max_depth=2,
))

# 沿入边遍历（谁指向了这个实体）
inbound = store.traverse("self-attention", TraverseOpts(
    direction=Direction.INBOUND,
    max_depth=1,
))

# 双向遍历
both = store.traverse("transformer", TraverseOpts(
    direction=Direction.BOTH,
    max_depth=1,
    relation_type="extends",  # 可选：只沿特定关系类型
))
```

遍历参数：
- `direction`: `OUTBOUND`（出边）、`INBOUND`（入边）、`BOTH`（双向）
- `relation_type`: 过滤特定关系类型，空字符串表示所有类型
- `max_depth`: 最大遍历深度，范围 1–5

### 环检测

```python
cycles = store.detect_cycles("flash-attention")
# 返回值: [["flash-attention", "B", "C", "flash-attention"], ...]
```

使用 DFS 沿出边查找从给定实体出发能到达的所有环路。返回每条环路的完整路径（首尾相同）。

## 查询 API

```python
from synth_wiki.ontology import Store

store = Store(db)

# 添加/更新实体（upsert）
store.add_entity(entity)

# 获取单个实体
entity = store.get_entity("flash-attention")

# 列出所有实体（可按类型过滤）
all_concepts = store.list_entities("concept")
all_entities = store.list_entities()

# 删除实体
store.delete_entity("flash-attention")

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

## 数据库 Schema

实体表：

```sql
CREATE TABLE entities (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL CHECK(type IN ('concept','technique','source','claim','artifact')),
    name TEXT NOT NULL,
    definition TEXT,
    article_path TEXT,
    metadata JSON,
    created_at TEXT,
    updated_at TEXT
);
```

关系表：

```sql
CREATE TABLE relations (
    id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
    target_id TEXT NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
    relation TEXT NOT NULL CHECK(relation IN (
        'implements','extends','optimizes','contradicts',
        'cites','prerequisite_of','trades_off','derived_from'
    )),
    metadata JSON,
    created_at TEXT,
    UNIQUE(source_id, target_id, relation)
);
```

索引覆盖 `source_id`、`target_id` 和 `relation` 三个字段，支持高效的方向性查询和类型过滤。

## 与搜索的配合

知识图谱独立于搜索索引（FTS5 + 向量）运行。当前版本中，ontology 数据通过 `status` 命令展示统计信息（实体数、关系数），通过 `doctor` 命令检查健康状态。搜索结果的上下文扩展（利用图邻居补充结果）属于规划中的功能。

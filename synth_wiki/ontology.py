# -*- coding: utf-8 -*-
"""
@author:XuMing(xuming624@qq.com)
@description: Entity-relation graph store with BFS traversal and cycle detection. | Knowledge graph ontology definitions, entity types, and relationship edges.
"""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from synth_wiki.storage import DB

# Entity types
TYPE_CONCEPT = "concept"
TYPE_TECHNIQUE = "technique"
TYPE_SOURCE = "source"
TYPE_CLAIM = "claim"
TYPE_ARTIFACT = "artifact"

# Relation types
REL_IMPLEMENTS = "implements"
REL_EXTENDS = "extends"
REL_OPTIMIZES = "optimizes"
REL_CONTRADICTS = "contradicts"
REL_CITES = "cites"
REL_PREREQUISITE_OF = "prerequisite_of"
REL_TRADES_OFF = "trades_off"
REL_DERIVED_FROM = "derived_from"


class Direction(Enum):
    OUTBOUND = "outbound"
    INBOUND = "inbound"
    BOTH = "both"


@dataclass
class Entity:
    id: str
    type: str
    name: str
    definition: str = ""
    article_path: str = ""
    created_at: str = ""
    updated_at: str = ""


@dataclass
class Relation:
    id: str
    source_id: str
    target_id: str
    relation: str
    created_at: str = ""


@dataclass
class TraverseOpts:
    direction: Direction = Direction.OUTBOUND
    relation_type: str = ""
    max_depth: int = 1


class Store:
    def __init__(self, db: DB):
        self._db = db

    def add_entity(self, e: Entity) -> None:
        """Upsert entity."""
        now = _now()
        if not e.created_at:
            e.created_at = now
        if not e.updated_at:
            e.updated_at = now

        def _upsert(cursor):
            cursor.execute(
                """INSERT INTO entities (id, type, name, definition, article_path, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(id) DO UPDATE SET
                     name=excluded.name, definition=excluded.definition,
                     article_path=excluded.article_path, updated_at=excluded.updated_at""",
                (e.id, e.type, e.name, e.definition, e.article_path, e.created_at, e.updated_at),
            )

        self._db.write_tx(_upsert)

    def get_entity(self, id: str) -> Optional[Entity]:
        cursor = self._db.read_db.cursor()
        cursor.execute(
            "SELECT id, type, name, COALESCE(definition,''), COALESCE(article_path,''), created_at, updated_at FROM entities WHERE id=?",
            (id,),
        )
        row = cursor.fetchone()
        if not row:
            return None
        return Entity(id=row[0], type=row[1], name=row[2], definition=row[3], article_path=row[4], created_at=row[5], updated_at=row[6])

    def list_entities(self, entity_type: str = "") -> list[Entity]:
        cursor = self._db.read_db.cursor()
        if entity_type:
            cursor.execute(
                "SELECT id, type, name, COALESCE(definition,''), COALESCE(article_path,''), created_at, updated_at FROM entities WHERE type=? ORDER BY name",
                (entity_type,),
            )
        else:
            cursor.execute(
                "SELECT id, type, name, COALESCE(definition,''), COALESCE(article_path,''), created_at, updated_at FROM entities ORDER BY name"
            )
        return [
            Entity(id=r[0], type=r[1], name=r[2], definition=r[3], article_path=r[4], created_at=r[5], updated_at=r[6])
            for r in cursor.fetchall()
        ]

    def delete_entity(self, id: str) -> None:
        def _delete(cursor):
            cursor.execute("DELETE FROM entities WHERE id=?", (id,))

        self._db.write_tx(_delete)

    def add_relation(self, r: Relation) -> None:
        """Add typed edge. Self-loops not allowed. Upsert semantics."""
        if r.source_id == r.target_id:
            raise ValueError(f"ontology: self-loops not allowed (entity {r.source_id!r})")
        if not r.created_at:
            r.created_at = _now()

        def _insert(cursor):
            cursor.execute(
                """INSERT INTO relations (id, source_id, target_id, relation, created_at)
                   VALUES (?, ?, ?, ?, ?)
                   ON CONFLICT(source_id, target_id, relation) DO NOTHING""",
                (r.id, r.source_id, r.target_id, r.relation, r.created_at),
            )

        self._db.write_tx(_insert)

    def get_relations(self, entity_id: str, direction: Direction = Direction.OUTBOUND, relation_type: str = "") -> list[Relation]:
        cursor = self._db.read_db.cursor()
        if direction == Direction.OUTBOUND:
            sql = "SELECT id, source_id, target_id, relation, created_at FROM relations WHERE source_id=?"
            args = [entity_id]
        elif direction == Direction.INBOUND:
            sql = "SELECT id, source_id, target_id, relation, created_at FROM relations WHERE target_id=?"
            args = [entity_id]
        else:
            sql = "SELECT id, source_id, target_id, relation, created_at FROM relations WHERE source_id=? OR target_id=?"
            args = [entity_id, entity_id]
        if relation_type:
            sql += " AND relation=?"
            args.append(relation_type)
        cursor.execute(sql, args)
        return [Relation(id=r[0], source_id=r[1], target_id=r[2], relation=r[3], created_at=r[4]) for r in cursor.fetchall()]

    def traverse(self, entity_id: str, opts: TraverseOpts) -> list[Entity]:
        """BFS traversal from entity, returning connected entities."""
        max_depth = max(1, min(opts.max_depth, 5))
        visited = {entity_id}
        queue = [entity_id]
        result = []
        for _ in range(max_depth):
            if not queue:
                break
            next_queue = []
            for eid in queue:
                rels = self.get_relations(eid, opts.direction, opts.relation_type)
                for r in rels:
                    neighbor = r.target_id if r.target_id != eid else r.source_id
                    if neighbor in visited:
                        continue
                    visited.add(neighbor)
                    next_queue.append(neighbor)
                    entity = self.get_entity(neighbor)
                    if entity:
                        result.append(entity)
            queue = next_queue
        return result

    def detect_cycles(self, entity_id: str) -> list[list[str]]:
        """DFS to find cycles reachable from entity following outbound edges."""
        cycles = []
        stack = [(entity_id, [entity_id])]
        while stack:
            current, path = stack.pop()
            rels = self.get_relations(current, Direction.OUTBOUND, "")
            for r in rels:
                if r.target_id == entity_id:
                    cycles.append(path + [r.target_id])
                    continue
                if r.target_id in path:
                    continue
                stack.append((r.target_id, path + [r.target_id]))
        return cycles

    def entity_count(self, entity_type: str = "") -> int:
        cursor = self._db.read_db.cursor()
        if entity_type:
            cursor.execute("SELECT COUNT(*) FROM entities WHERE type=?", (entity_type,))
        else:
            cursor.execute("SELECT COUNT(*) FROM entities")
        return cursor.fetchone()[0]

    def relation_count(self) -> int:
        cursor = self._db.read_db.cursor()
        cursor.execute("SELECT COUNT(*) FROM relations")
        return cursor.fetchone()[0]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()

# -*- coding: utf-8 -*-
"""
@author:XuMing(xuming624@qq.com)
@description: Tests for ontology entity-relation graph store.
"""
from __future__ import annotations
import pytest

from synth_wiki.ontology import (
    Direction,
    Entity,
    Relation,
    Store,
    TraverseOpts,
    TYPE_CONCEPT,
    TYPE_TECHNIQUE,
    REL_IMPLEMENTS,
    REL_EXTENDS,
    REL_CITES,
)


@pytest.fixture
def db(tmp_path):
    from synth_wiki.storage import DB
    return DB.open(str(tmp_path / "test.db"))


@pytest.fixture
def store(db):
    return Store(db)


def make_entity(id: str, type: str = TYPE_CONCEPT, name: str = "") -> Entity:
    return Entity(id=id, type=type, name=name or f"Entity {id}")


def make_relation(id: str, source_id: str, target_id: str, relation: str = REL_IMPLEMENTS) -> Relation:
    return Relation(id=id, source_id=source_id, target_id=target_id, relation=relation)


# 1. Add + get entity roundtrip
def test_add_get_entity(store):
    e = Entity(id="e1", type=TYPE_CONCEPT, name="Transformer", definition="Attention model", article_path="/articles/transformer.md")
    store.add_entity(e)
    got = store.get_entity("e1")
    assert got is not None
    assert got.id == "e1"
    assert got.type == TYPE_CONCEPT
    assert got.name == "Transformer"
    assert got.definition == "Attention model"
    assert got.article_path == "/articles/transformer.md"
    assert got.created_at != ""
    assert got.updated_at != ""


# 2. List entities by type
def test_list_entities_by_type(store):
    store.add_entity(make_entity("c1", TYPE_CONCEPT, "Alpha"))
    store.add_entity(make_entity("c2", TYPE_CONCEPT, "Beta"))
    store.add_entity(make_entity("t1", TYPE_TECHNIQUE, "Technique A"))

    concepts = store.list_entities(TYPE_CONCEPT)
    assert len(concepts) == 2
    assert all(e.type == TYPE_CONCEPT for e in concepts)

    techniques = store.list_entities(TYPE_TECHNIQUE)
    assert len(techniques) == 1
    assert techniques[0].id == "t1"

    all_entities = store.list_entities()
    assert len(all_entities) == 3


# 3. Delete entity (verify gone)
def test_delete_entity(store):
    store.add_entity(make_entity("e1"))
    assert store.get_entity("e1") is not None
    store.delete_entity("e1")
    assert store.get_entity("e1") is None


# 4. Add relation, get outbound
def test_get_relations_outbound(store):
    store.add_entity(make_entity("a"))
    store.add_entity(make_entity("b"))
    store.add_relation(make_relation("r1", "a", "b", REL_IMPLEMENTS))

    rels = store.get_relations("a", Direction.OUTBOUND)
    assert len(rels) == 1
    assert rels[0].source_id == "a"
    assert rels[0].target_id == "b"
    assert rels[0].relation == REL_IMPLEMENTS


# 5. Add relation, get inbound
def test_get_relations_inbound(store):
    store.add_entity(make_entity("a"))
    store.add_entity(make_entity("b"))
    store.add_relation(make_relation("r1", "a", "b", REL_IMPLEMENTS))

    rels = store.get_relations("b", Direction.INBOUND)
    assert len(rels) == 1
    assert rels[0].source_id == "a"
    assert rels[0].target_id == "b"


# 6. Add relation, get both directions
def test_get_relations_both(store):
    store.add_entity(make_entity("a"))
    store.add_entity(make_entity("b"))
    store.add_entity(make_entity("c"))
    store.add_relation(make_relation("r1", "a", "b", REL_IMPLEMENTS))
    store.add_relation(make_relation("r2", "c", "b", REL_EXTENDS))

    # b has one inbound from a and one inbound from c
    rels = store.get_relations("b", Direction.BOTH)
    assert len(rels) == 2

    # a has one outbound to b
    rels_a = store.get_relations("a", Direction.BOTH)
    assert len(rels_a) == 1


# 7. Self-loop raises ValueError
def test_self_loop_raises(store):
    store.add_entity(make_entity("a"))
    with pytest.raises(ValueError, match="self-loops not allowed"):
        store.add_relation(make_relation("r1", "a", "a", REL_IMPLEMENTS))


# 8. Traverse depth=1 returns direct neighbors
def test_traverse_depth_1(store):
    store.add_entity(make_entity("a"))
    store.add_entity(make_entity("b"))
    store.add_entity(make_entity("c"))
    store.add_relation(make_relation("r1", "a", "b", REL_IMPLEMENTS))
    store.add_relation(make_relation("r2", "b", "c", REL_IMPLEMENTS))

    result = store.traverse("a", TraverseOpts(direction=Direction.OUTBOUND, max_depth=1))
    ids = {e.id for e in result}
    assert ids == {"b"}


# 9. Traverse depth=2 returns 2-hop neighbors
def test_traverse_depth_2(store):
    store.add_entity(make_entity("a"))
    store.add_entity(make_entity("b"))
    store.add_entity(make_entity("c"))
    store.add_relation(make_relation("r1", "a", "b", REL_IMPLEMENTS))
    store.add_relation(make_relation("r2", "b", "c", REL_IMPLEMENTS))

    result = store.traverse("a", TraverseOpts(direction=Direction.OUTBOUND, max_depth=2))
    ids = {e.id for e in result}
    assert ids == {"b", "c"}


# 10. Detect cycles finds cycle (A->B->C->A)
def test_detect_cycles_found(store):
    store.add_entity(make_entity("a"))
    store.add_entity(make_entity("b"))
    store.add_entity(make_entity("c"))
    store.add_relation(make_relation("r1", "a", "b", REL_IMPLEMENTS))
    store.add_relation(make_relation("r2", "b", "c", REL_IMPLEMENTS))
    store.add_relation(make_relation("r3", "c", "a", REL_IMPLEMENTS))

    cycles = store.detect_cycles("a")
    assert len(cycles) >= 1
    # Each cycle path should start at "a" and end at "a"
    for cycle in cycles:
        assert cycle[0] == "a"
        assert cycle[-1] == "a"


# 11. Detect cycles returns empty for acyclic graph
def test_detect_cycles_empty(store):
    store.add_entity(make_entity("a"))
    store.add_entity(make_entity("b"))
    store.add_entity(make_entity("c"))
    store.add_relation(make_relation("r1", "a", "b", REL_IMPLEMENTS))
    store.add_relation(make_relation("r2", "b", "c", REL_IMPLEMENTS))

    cycles = store.detect_cycles("a")
    assert cycles == []


# 12. entity_count with and without type filter
def test_entity_count(store):
    assert store.entity_count() == 0
    store.add_entity(make_entity("c1", TYPE_CONCEPT))
    store.add_entity(make_entity("c2", TYPE_CONCEPT))
    store.add_entity(make_entity("t1", TYPE_TECHNIQUE))

    assert store.entity_count() == 3
    assert store.entity_count(TYPE_CONCEPT) == 2
    assert store.entity_count(TYPE_TECHNIQUE) == 1


# 13. relation_count
def test_relation_count(store):
    assert store.relation_count() == 0
    store.add_entity(make_entity("a"))
    store.add_entity(make_entity("b"))
    store.add_entity(make_entity("c"))
    store.add_relation(make_relation("r1", "a", "b", REL_IMPLEMENTS))
    store.add_relation(make_relation("r2", "b", "c", REL_CITES))

    assert store.relation_count() == 2


# 14. Delete entity cascades relations
def test_delete_entity_cascades_relations(store):
    store.add_entity(make_entity("a"))
    store.add_entity(make_entity("b"))
    store.add_entity(make_entity("c"))
    store.add_relation(make_relation("r1", "a", "b", REL_IMPLEMENTS))
    store.add_relation(make_relation("r2", "b", "c", REL_IMPLEMENTS))

    assert store.relation_count() == 2
    store.delete_entity("b")
    # Both relations referencing b should be cascaded
    assert store.relation_count() == 0

# -*- coding: utf-8 -*-
"""
@author:XuMing(xuming624@qq.com)
@description: Tests for storage.py (DB class).
"""
from __future__ import annotations
import os
import tempfile
import pytest

from synth_wiki.storage import DB


@pytest.fixture
def db(tmp_path):
    path = str(tmp_path / "test.db")
    d = DB.open(path)
    yield d
    d.close()


def test_open_creates_file(tmp_path):
    path = str(tmp_path / "new.db")
    assert not os.path.exists(path)
    d = DB.open(path)
    d.close()
    assert os.path.exists(path)


def test_migrations_run(db):
    # schema_version should have version=1
    cursor = db.read_db.cursor()
    cursor.execute("SELECT MAX(version) FROM schema_version")
    assert cursor.fetchone()[0] == 1


def test_learnings_table_exists(db):
    def _insert(cursor):
        cursor.execute(
            "INSERT INTO learnings (id, type, content, tags, created_at) VALUES (?, ?, ?, ?, ?)",
            ("l1", "rule", "some learning content", "tag1", "2024-01-01"),
        )
    db.write_tx(_insert)

    cursor = db.read_db.cursor()
    cursor.execute("SELECT id, content FROM learnings WHERE id=?", ("l1",))
    row = cursor.fetchone()
    assert row is not None
    assert row[0] == "l1"
    assert row[1] == "some learning content"


def test_vec_entries_table_exists(db):
    import struct
    blob = struct.pack("<3f", 1.0, 2.0, 3.0)
    def _insert(cursor):
        cursor.execute(
            "INSERT INTO vec_entries (id, embedding, dimensions) VALUES (?, ?, ?)",
            ("v1", blob, 3),
        )
    db.write_tx(_insert)

    cursor = db.read_db.cursor()
    cursor.execute("SELECT id, dimensions FROM vec_entries WHERE id=?", ("v1",))
    row = cursor.fetchone()
    assert row is not None
    assert row[0] == "v1"
    assert row[1] == 3


def test_entities_relations_tables_exist(db):
    def _insert(cursor):
        cursor.execute(
            "INSERT INTO entities (id, type, name, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
            ("ent1", "concept", "Attention", "2024-01-01", "2024-01-01"),
        )
        cursor.execute(
            "INSERT INTO entities (id, type, name, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
            ("ent2", "technique", "Transformer", "2024-01-01", "2024-01-01"),
        )
        cursor.execute(
            "INSERT INTO relations (id, source_id, target_id, relation, created_at) VALUES (?, ?, ?, ?, ?)",
            ("rel1", "ent1", "ent2", "implements", "2024-01-01"),
        )
    db.write_tx(_insert)

    cursor = db.read_db.cursor()
    cursor.execute("SELECT COUNT(*) FROM entities")
    assert cursor.fetchone()[0] == 2

    cursor.execute("SELECT relation FROM relations WHERE id=?", ("rel1",))
    assert cursor.fetchone()[0] == "implements"


def test_write_tx_commits_on_success(db):
    def _insert(cursor):
        cursor.execute(
            "INSERT INTO vec_entries (id, embedding, dimensions) VALUES (?, ?, ?)",
            ("commit_test", b"\x00" * 4, 1),
        )
    db.write_tx(_insert)

    cursor = db.read_db.cursor()
    cursor.execute("SELECT id FROM vec_entries WHERE id=?", ("commit_test",))
    assert cursor.fetchone() is not None


def test_write_tx_rollback_on_exception(db):
    with pytest.raises(Exception):
        def _bad(cursor):
            cursor.execute(
                "INSERT INTO vec_entries (id, embedding, dimensions) VALUES (?, ?, ?)",
                ("rollback_test", b"\x00" * 4, 1),
            )
            raise RuntimeError("forced error")
        db.write_tx(_bad)

    cursor = db.read_db.cursor()
    cursor.execute("SELECT id FROM vec_entries WHERE id=?", ("rollback_test",))
    assert cursor.fetchone() is None


def test_close_is_idempotent(db):
    db.close()
    db.close()  # should not raise


def test_wal_mode_enabled(db):
    cursor = db.write_db.cursor()
    cursor.execute("PRAGMA journal_mode")
    mode = cursor.fetchone()[0]
    assert mode == "wal"

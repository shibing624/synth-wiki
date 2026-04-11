# -*- coding: utf-8 -*-
"""
@author:XuMing(xuming624@qq.com)
@description: SQLite database with WAL mode, FTS5, single-writer pattern. | SQLite database initialization and connection management.
"""
from __future__ import annotations
import sqlite3
import threading

MIGRATION_V1 = """
-- Vector embeddings
CREATE TABLE IF NOT EXISTS vec_entries (
    id TEXT PRIMARY KEY,
    embedding BLOB NOT NULL,
    dimensions INTEGER NOT NULL
);

-- Ontology: entities
CREATE TABLE IF NOT EXISTS entities (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL CHECK(type IN ('concept','technique','source','claim','artifact')),
    name TEXT NOT NULL,
    definition TEXT,
    article_path TEXT,
    metadata JSON,
    created_at TEXT,
    updated_at TEXT
);

-- Ontology: relations
CREATE TABLE IF NOT EXISTS relations (
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

CREATE INDEX IF NOT EXISTS idx_relations_source ON relations(source_id);
CREATE INDEX IF NOT EXISTS idx_relations_target ON relations(target_id);
CREATE INDEX IF NOT EXISTS idx_relations_type ON relations(relation);

-- Self-learning
CREATE TABLE IF NOT EXISTS learnings (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL,
    content TEXT NOT NULL,
    tags TEXT,
    created_at TEXT,
    source_lint_pass TEXT
);
"""


class DB:
    def __init__(self, path: str):
        self._path = path
        self._write_lock = threading.Lock()
        self._closed = False

        # Write connection
        self._write_conn = sqlite3.connect(path, check_same_thread=False)
        self._write_conn.execute("PRAGMA journal_mode=WAL")
        self._write_conn.execute("PRAGMA busy_timeout=5000")
        self._write_conn.execute("PRAGMA foreign_keys=ON")
        self._write_conn.execute("PRAGMA synchronous=NORMAL")

        # Read connection
        self._read_conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True, check_same_thread=False)
        self._read_conn.execute("PRAGMA busy_timeout=5000")
        self._read_conn.execute("PRAGMA foreign_keys=ON")

        self._migrate()

    @classmethod
    def open(cls, path: str) -> DB:
        return cls(path)

    @property
    def write_db(self) -> sqlite3.Connection:
        return self._write_conn

    @property
    def read_db(self) -> sqlite3.Connection:
        return self._read_conn

    def write_tx(self, fn) -> None:
        """Execute fn(cursor) within a serialized write transaction."""
        with self._write_lock:
            cursor = self._write_conn.cursor()
            try:
                fn(cursor)
                self._write_conn.commit()
            except Exception:
                self._write_conn.rollback()
                raise

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._read_conn.close()
        self._write_conn.close()

    def _migrate(self) -> None:
        cursor = self._write_conn.cursor()
        cursor.execute("CREATE TABLE IF NOT EXISTS schema_version (version INTEGER NOT NULL)")
        row = cursor.fetchone()
        cursor.execute("SELECT COALESCE(MAX(version), 0) FROM schema_version")
        version = cursor.fetchone()[0]

        migrations = [MIGRATION_V1]
        for i in range(version, len(migrations)):
            cursor.executescript(migrations[i])
            cursor.execute("INSERT INTO schema_version (version) VALUES (?)", (i + 1,))
        self._write_conn.commit()

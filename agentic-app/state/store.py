"""
Agentic - SQLite Persistence Store
===================================
Provides durable storage for:
  - Sessions (id, created_at, title)
  - Crystal memory records (compressed episodic)
  - Bedrock facts (semantic long-term knowledge)

Uses only the Python standard library (sqlite3).
All operations are synchronous and guarded by a threading.Lock.
"""
from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from threading import Lock
from typing import Any

from utils.logger import build_logger

log = build_logger("agentic.store")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    id          TEXT PRIMARY KEY,
    title       TEXT NOT NULL DEFAULT 'Session',
    created_at  REAL NOT NULL,
    updated_at  REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS crystal (
    record_id   TEXT PRIMARY KEY,
    session_id  TEXT NOT NULL,
    summary     TEXT NOT NULL,
    tags        TEXT NOT NULL DEFAULT '[]',
    ts          REAL NOT NULL,
    importance  REAL NOT NULL DEFAULT 0.3,
    FOREIGN KEY (session_id) REFERENCES sessions(id)
);

CREATE TABLE IF NOT EXISTS bedrock (
    fact_id     TEXT PRIMARY KEY,
    category    TEXT NOT NULL,
    text        TEXT NOT NULL,
    confidence  REAL NOT NULL DEFAULT 0.8,
    ts          REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS fluid (
    entry_id    TEXT PRIMARY KEY,
    session_id  TEXT NOT NULL,
    role        TEXT NOT NULL,
    text        TEXT NOT NULL,
    tags        TEXT NOT NULL DEFAULT '[]',
    ts          REAL NOT NULL,
    FOREIGN KEY (session_id) REFERENCES sessions(id)
);

CREATE INDEX IF NOT EXISTS idx_crystal_session ON crystal(session_id, ts DESC);
CREATE INDEX IF NOT EXISTS idx_bedrock_cat    ON bedrock(category, ts DESC);
CREATE INDEX IF NOT EXISTS idx_fluid_session  ON fluid(session_id, ts ASC);
"""


class Store:
    """Thread-safe SQLite persistence layer."""

    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        self._lock = Lock()
        self._conn = sqlite3.connect(
            str(db_path),
            check_same_thread=False,
            isolation_level=None,   # autocommit; we manage transactions manually
        )
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._init_schema()
        log.info("Store opened: %s", db_path)

    # ------------------------------------------------------------------
    # Schema
    # ------------------------------------------------------------------

    def _init_schema(self) -> None:
        with self._lock:
            self._conn.executescript(_SCHEMA)

    # ------------------------------------------------------------------
    # Session
    # ------------------------------------------------------------------

    def session_create(self, session_id: str, title: str = "New Session") -> None:
        now = time.time()
        with self._lock:
            self._conn.execute(
                "INSERT OR IGNORE INTO sessions(id, title, created_at, updated_at) "
                "VALUES (?, ?, ?, ?)",
                (session_id, title, now, now),
            )

    def session_update_title(self, session_id: str, title: str) -> None:
        with self._lock:
            self._conn.execute(
                "UPDATE sessions SET title=?, updated_at=? WHERE id=?",
                (title, time.time(), session_id),
            )

    def session_touch(self, session_id: str) -> None:
        with self._lock:
            self._conn.execute(
                "UPDATE sessions SET updated_at=? WHERE id=?",
                (time.time(), session_id),
            )

    def session_list(self, limit: int = 50) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT id, title, created_at, updated_at "
                "FROM sessions ORDER BY updated_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]

    def session_delete(self, session_id: str) -> None:
        with self._lock:
            self._conn.execute(
                "DELETE FROM crystal WHERE session_id=?", (session_id,)
            )
            self._conn.execute(
                "DELETE FROM fluid WHERE session_id=?", (session_id,)
            )
            self._conn.execute(
                "DELETE FROM sessions WHERE id=?", (session_id,)
            )

    # ------------------------------------------------------------------
    # Crystal memory
    # ------------------------------------------------------------------

    def crystal_insert(self, record: Any) -> None:
        """Accept a CrystalRecord dataclass instance."""
        with self._lock:
            self._conn.execute(
                "INSERT OR REPLACE INTO crystal"
                "(record_id, session_id, summary, tags, ts, importance) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    record.record_id,
                    record.session_id,
                    record.summary,
                    json.dumps(record.tags),
                    record.ts,
                    record.importance,
                ),
            )

    def crystal_query(
        self,
        session_id: str,
        limit: int = 10,
        tags: list[str] | None = None,
    ) -> list[Any]:
        from core.memory_lattice import CrystalRecord  # local import to avoid cycle

        with self._lock:
            if tags:
                rows = self._conn.execute(
                    "SELECT * FROM crystal WHERE session_id=? "
                    "ORDER BY ts DESC LIMIT ?",
                    (session_id, limit * 3),
                ).fetchall()
                filtered = []
                for r in rows:
                    row_tags = json.loads(r["tags"])
                    if any(t in row_tags for t in tags):
                        filtered.append(r)
                rows = filtered[:limit]
            else:
                rows = self._conn.execute(
                    "SELECT * FROM crystal WHERE session_id=? "
                    "ORDER BY ts DESC LIMIT ?",
                    (session_id, limit),
                ).fetchall()

        return [
            CrystalRecord(
                record_id=r["record_id"],
                session_id=r["session_id"],
                summary=r["summary"],
                tags=json.loads(r["tags"]),
                ts=r["ts"],
                importance=r["importance"],
            )
            for r in rows
        ]

    # ------------------------------------------------------------------
    # Bedrock facts
    # ------------------------------------------------------------------

    def bedrock_insert(self, fact: Any) -> None:
        """Accept a BedrockFact dataclass instance."""
        with self._lock:
            self._conn.execute(
                "INSERT OR REPLACE INTO bedrock"
                "(fact_id, category, text, confidence, ts) "
                "VALUES (?, ?, ?, ?, ?)",
                (fact.fact_id, fact.category, fact.text, fact.confidence, fact.ts),
            )

    def bedrock_query(
        self, category: str | None = None, limit: int = 20
    ) -> list[Any]:
        from core.memory_lattice import BedrockFact  # local import to avoid cycle

        with self._lock:
            if category:
                rows = self._conn.execute(
                    "SELECT * FROM bedrock WHERE category=? "
                    "ORDER BY ts DESC LIMIT ?",
                    (category, limit),
                ).fetchall()
            else:
                rows = self._conn.execute(
                    "SELECT * FROM bedrock ORDER BY ts DESC LIMIT ?",
                    (limit,),
                ).fetchall()

        return [
            BedrockFact(
                fact_id=r["fact_id"],
                category=r["category"],
                text=r["text"],
                confidence=r["confidence"],
                ts=r["ts"],
            )
            for r in rows
        ]

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    # ------------------------------------------------------------------
    # Fluid memory persistence (crash-safe working context)
    # ------------------------------------------------------------------

    def fluid_insert(
        self,
        entry_id: str,
        session_id: str,
        role: str,
        text: str,
        tags: list[str],
        ts: float,
    ) -> None:
        """Persist a single FluidEntry row."""
        with self._lock:
            self._conn.execute(
                "INSERT OR REPLACE INTO fluid"
                "(entry_id, session_id, role, text, tags, ts) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (entry_id, session_id, role, text, json.dumps(tags), ts),
            )

    def fluid_restore(self, session_id: str) -> list[dict[str, Any]]:
        """Return all persisted fluid entries for *session_id* in ts order."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT entry_id, role, text, tags, ts "
                "FROM fluid WHERE session_id=? ORDER BY ts ASC",
                (session_id,),
            ).fetchall()
        return [
            {
                "entry_id": r["entry_id"],
                "role":     r["role"],
                "text":     r["text"],
                "tags":     json.loads(r["tags"]),
                "ts":       r["ts"],
            }
            for r in rows
        ]

    def fluid_delete_entries(self, entry_ids: list[str]) -> None:
        """Delete specific fluid rows by their entry_ids."""
        if not entry_ids:
            return
        placeholders = ",".join("?" * len(entry_ids))
        with self._lock:
            self._conn.execute(
                f"DELETE FROM fluid WHERE entry_id IN ({placeholders})",
                entry_ids,
            )

    def fluid_clear(self, session_id: str) -> None:
        """Delete all fluid rows for *session_id*."""
        with self._lock:
            self._conn.execute(
                "DELETE FROM fluid WHERE session_id=?", (session_id,)
            )

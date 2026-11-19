"""SQLite persistence layer — stdlib only, zero infrastructure (D5 resolution).

Storage model:
- projects: one row per saved design document
- versions: immutable snapshots per project (version history)
- runs:     simulation/verification results keyed by their input hash

Concurrency: WAL journaling; a single connection guarded by a lock (FastAPI
runs sync endpoints in a thread pool). The database file location comes from
LOGICFORGE_DB (default: ./logicforge.db). Backups: copy the file, or use the
sqlite3 backup API — see docs/DEPLOYMENT.md.
"""

from __future__ import annotations

import json
import os
import sqlite3
import threading
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

_DB_PATH = os.environ.get("LOGICFORGE_DB", "./logicforge.db")
_write_lock = threading.Lock()


def write_lock() -> threading.Lock:
    """The guard shared by writes and online backups."""
    return _write_lock


_connection: sqlite3.Connection | None = None


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def connect(db_path: str | None = None) -> sqlite3.Connection:
    """Open (or reopen) the database and ensure the schema exists."""
    global _connection, _DB_PATH
    if db_path is not None:
        _DB_PATH = db_path
        _connection = None
    if _connection is None:
        path = Path(_DB_PATH)
        path.parent.mkdir(parents=True, exist_ok=True)
        _connection = sqlite3.connect(str(path), check_same_thread=False)
        _connection.row_factory = sqlite3.Row
        _connection.execute("PRAGMA journal_mode=WAL")
        _connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS projects (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                kind TEXT NOT NULL DEFAULT 'circuit',
                document TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS versions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                label TEXT NOT NULL,
                document TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                input_hash TEXT NOT NULL,
                kind TEXT NOT NULL,
                result TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_versions_project ON versions(project_id);
            CREATE INDEX IF NOT EXISTS idx_runs_hash ON runs(input_hash);
            """
        )
    return _connection


def close() -> None:
    global _connection
    if _connection is not None:
        _connection.close()
        _connection = None


@dataclass(frozen=True)
class ProjectRecord:
    id: str
    name: str
    kind: str
    document: dict[str, object]
    created_at: str
    updated_at: str


def _row_to_project(row: sqlite3.Row) -> ProjectRecord:
    return ProjectRecord(
        id=row["id"],
        name=row["name"],
        kind=row["kind"],
        document=json.loads(row["document"]),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def save_project(project_id: str, name: str, document: dict[str, object], kind: str = "circuit") -> ProjectRecord:
    """Insert or update a project (upsert by id)."""
    now = _now()
    with _write_lock, connect() as db:
        db.execute(
            """
            INSERT INTO projects (id, name, kind, document, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                name = excluded.name,
                kind = excluded.kind,
                document = excluded.document,
                updated_at = excluded.updated_at
            """,
            (project_id, name, kind, json.dumps(document), now, now),
        )
    row = connect().execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
    return _row_to_project(row)


def get_project(project_id: str) -> ProjectRecord | None:
    row = connect().execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
    return _row_to_project(row) if row is not None else None


def list_projects() -> list[ProjectRecord]:
    rows = connect().execute("SELECT * FROM projects ORDER BY updated_at DESC").fetchall()
    return [_row_to_project(row) for row in rows]


def delete_project(project_id: str) -> bool:
    with _write_lock, connect() as db:
        cursor = db.execute("DELETE FROM projects WHERE id = ?", (project_id,))
        return cursor.rowcount > 0


def add_version(project_id: str, label: str, document: dict[str, object]) -> int:
    """Append an immutable version snapshot; the project row is kept current."""
    now = _now()
    with _write_lock, connect() as db:
        cursor = db.execute(
            "INSERT INTO versions (project_id, label, document, created_at) VALUES (?, ?, ?, ?)",
            (project_id, label, json.dumps(document), now),
        )
        db.execute(
            "UPDATE projects SET document = ?, updated_at = ? WHERE id = ?",
            (json.dumps(document), now, project_id),
        )
        return int(cursor.lastrowid or 0)


def list_versions(project_id: str) -> list[dict[str, object]]:
    rows = (
        connect()
        .execute(
            "SELECT id, label, created_at FROM versions WHERE project_id = ? ORDER BY id DESC",
            (project_id,),
        )
        .fetchall()
    )
    return [{"id": row["id"], "label": row["label"], "created_at": row["created_at"]} for row in rows]


def get_version(project_id: str, version_id: int) -> dict[str, object] | None:
    row = (
        connect()
        .execute(
            "SELECT document FROM versions WHERE project_id = ? AND id = ?",
            (project_id, version_id),
        )
        .fetchone()
    )
    return json.loads(row["document"]) if row is not None else None


def save_run(input_hash: str, kind: str, result: dict[str, object]) -> None:
    """Record a simulation/verification result keyed by its input hash."""
    with _write_lock, connect() as db:
        db.execute(
            "INSERT INTO runs (input_hash, kind, result, created_at) VALUES (?, ?, ?, ?)",
            (input_hash, kind, json.dumps(result), _now()),
        )


def list_runs_by_hash(input_hash: str, limit: int = 20) -> list[dict[str, object]]:
    rows = (
        connect()
        .execute(
            "SELECT id, kind, result, created_at FROM runs WHERE input_hash = ? ORDER BY id DESC LIMIT ?",
            (input_hash, limit),
        )
        .fetchall()
    )
    return [
        {"id": row["id"], "kind": row["kind"], "result": json.loads(row["result"]), "created_at": row["created_at"]}
        for row in rows
    ]


def backup(target_path: str) -> int:
    """Consistent online backup via the sqlite3 backup API; returns pages copied."""
    source = connect()
    target = sqlite3.connect(target_path)
    with _write_lock:
        source.backup(target)
    target.close()
    return 1


def reset_for_tests(db_path: str = ":memory:") -> None:
    """Point the layer at a fresh in-memory database (test isolation)."""
    global _connection, _DB_PATH
    _DB_PATH = db_path
    _connection = None
    connect()

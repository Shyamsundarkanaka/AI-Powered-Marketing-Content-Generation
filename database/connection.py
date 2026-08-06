"""SQLite connection handling and schema initialization."""
from __future__ import annotations

import logging
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from config.settings import DATABASE_PATH

logger = logging.getLogger(__name__)

SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"


def get_connection() -> sqlite3.Connection:
    """Open a new SQLite connection with row access by column name.

    WAL mode plus a busy timeout let the worker thread and the Streamlit
    polling thread share the same file without one's write blocking the
    other's read long enough to raise "database is locked".
    """
    conn = sqlite3.connect(DATABASE_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA busy_timeout = 30000")
    return conn


@contextmanager
def connection_scope() -> Iterator[sqlite3.Connection]:
    """Context manager that commits on success and rolls back on error."""
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _migrate(conn: sqlite3.Connection) -> None:
    """Add columns introduced after the initial schema, without a table rebuild.

    `CREATE TABLE IF NOT EXISTS` in schema.sql never touches an existing table,
    so new nullable/defaulted columns are added here, guarded by a column-exists
    check so re-running is always a no-op.
    """
    existing = {row["name"] for row in conn.execute("PRAGMA table_info(jobs)")}
    if "current_stage" not in existing:
        conn.execute("ALTER TABLE jobs ADD COLUMN current_stage TEXT")
    if "cancel_requested" not in existing:
        conn.execute("ALTER TABLE jobs ADD COLUMN cancel_requested INTEGER NOT NULL DEFAULT 0")


def init_db() -> None:
    """Create all tables defined in schema.sql if they do not already exist."""
    schema_sql = SCHEMA_PATH.read_text(encoding="utf-8")
    with connection_scope() as conn:
        conn.executescript(schema_sql)
        _migrate(conn)
    logger.info("Database initialized at %s", DATABASE_PATH)

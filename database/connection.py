"""Database connection and schema initialization utilities."""

from __future__ import annotations

import sqlite3
from pathlib import Path


PRODUCTS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS products (
    product_id INTEGER PRIMARY KEY AUTOINCREMENT,
    url TEXT NOT NULL UNIQUE,
    product_name TEXT,
    category TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_processed_at TEXT,
    drive_link TEXT,
    approval_status TEXT NOT NULL DEFAULT 'not_reviewed'
)
"""


def get_connection(database_path: str | Path) -> sqlite3.Connection:
    """Return a configured SQLite connection for ``database_path``.

    The parent directory is created when it does not yet exist. Foreign-key
    checks are enabled on every connection because SQLite disables them by
    default. Callers are responsible for closing the returned connection.
    """
    path = Path(database_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def initialize_database(database_path: str | Path) -> None:
    """Create the application's database schema when it is missing or outdated."""
    connection = get_connection(database_path)
    try:
        with connection:
            connection.execute(PRODUCTS_TABLE_SQL)
            columns = {row["name"] for row in connection.execute("PRAGMA table_info(products)")}
            if "category" not in columns:
                connection.execute("ALTER TABLE products ADD COLUMN category TEXT")
    finally:
        connection.close()
"""Repository functions for products awaiting marketing-content generation."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path

from database.connection import get_connection, initialize_database


@dataclass(frozen=True)
class Product:
    """A product tracked by the marketing-content generation workflow."""

    product_id: int
    url: str
    product_name: str | None
    category: str | None
    status: str
    created_at: str
    updated_at: str
    last_processed_at: str | None
    drive_link: str | None
    approval_status: str


def add_product(
    database_path: str | Path,
    url: str,
    product_name: str | None = None,
    category: str | None = None,
) -> Product:
    """Store a product and return its persisted record.

    Raises:
        ValueError: If ``url`` is blank or already exists in the database.
    """
    normalized_url = url.strip()
    if not normalized_url:
        raise ValueError("Product URL cannot be blank.")

    initialize_database(database_path)
    connection = get_connection(database_path)
    try:
        with connection:
            cursor = connection.execute(
                "INSERT INTO products (url, product_name, category) VALUES (?, ?, ?)",
                (normalized_url, product_name, category),
            )
            row = connection.execute(
                "SELECT * FROM products WHERE product_id = ?", (cursor.lastrowid,)
            ).fetchone()
    except sqlite3.IntegrityError as error:
        raise ValueError(f"Product URL already exists: {normalized_url}") from error
    finally:
        connection.close()

    return _row_to_product(row)


def get_next_unprocessed_product(database_path: str | Path) -> Product | None:
    """Return the oldest pending product, or ``None`` when no work remains."""
    initialize_database(database_path)
    connection = get_connection(database_path)
    try:
        row = connection.execute(
            "SELECT * FROM products WHERE status = 'pending' ORDER BY product_id LIMIT 1"
        ).fetchone()
    finally:
        connection.close()
    return _row_to_product(row) if row is not None else None


def _row_to_product(row: sqlite3.Row) -> Product:
    """Convert a SQLite row to the public product record type."""
    return Product(
        product_id=row["product_id"],
        url=row["url"],
        product_name=row["product_name"],
        category=row["category"],
        status=row["status"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        last_processed_at=row["last_processed_at"],
        drive_link=row["drive_link"],
        approval_status=row["approval_status"],
    )
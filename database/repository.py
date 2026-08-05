"""CRUD operations for products, jobs, versions, outputs and logs."""
from __future__ import annotations

import json
import logging
from typing import Optional

from config.settings import OUTPUT_DIR
from database.connection import connection_scope
from database.models import Job, LogEntry, Output, Product, ScrapedData, Version

logger = logging.getLogger(__name__)


def _slugify(name: str) -> str:
    return "".join(c.lower() if c.isalnum() else "-" for c in name).strip("-")


# --- Products ----------------------------------------------------------------

def create_product(name: str, url: str) -> Product:
    """Add a new product from just a name and a source URL."""
    output_dir = str(OUTPUT_DIR / _slugify(name))
    with connection_scope() as conn:
        cursor = conn.execute(
            "INSERT INTO products (name, url, output_dir) VALUES (?, ?, ?)",
            (name, url, output_dir),
        )
        product_id = cursor.lastrowid
        row = conn.execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()
    logger.info("Created product %s (%s)", name, url)
    return Product.from_row(row)


def get_product(product_id: int) -> Optional[Product]:
    with connection_scope() as conn:
        row = conn.execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()
    return Product.from_row(row) if row else None


def list_products() -> list[Product]:
    with connection_scope() as conn:
        rows = conn.execute("SELECT * FROM products ORDER BY created_at DESC").fetchall()
    return [Product.from_row(row) for row in rows]


def count_rejections_by_product() -> dict[int, int]:
    """Number of Rejected versions per product, keyed by product_id."""
    with connection_scope() as conn:
        rows = conn.execute(
            "SELECT product_id, COUNT(*) AS n FROM versions WHERE status = 'Rejected' GROUP BY product_id"
        ).fetchall()
    return {row["product_id"]: row["n"] for row in rows}


def count_rejections_for_product(product_id: int) -> int:
    with connection_scope() as conn:
        row = conn.execute(
            "SELECT COUNT(*) FROM versions WHERE product_id = ? AND status = 'Rejected'",
            (product_id,),
        ).fetchone()
    return row[0]


def update_product_status(product_id: int, status: str) -> None:
    with connection_scope() as conn:
        conn.execute(
            "UPDATE products SET status = ?, updated_at = datetime('now') WHERE id = ?",
            (status, product_id),
        )
    logger.info("Product %s status -> %s", product_id, status)


def update_product_name(product_id: int, name: str) -> None:
    with connection_scope() as conn:
        conn.execute(
            "UPDATE products SET name = ?, updated_at = datetime('now') WHERE id = ?",
            (name, product_id),
        )
    logger.info("Product %s name -> %s", product_id, name)


def delete_product(product_id: int) -> None:
    with connection_scope() as conn:
        conn.execute("DELETE FROM products WHERE id = ?", (product_id,))
    logger.info("Deleted product %s", product_id)


# --- Jobs ----------------------------------------------------------------

def create_job(product_id: int) -> Job:
    """Queue a background job for a product and flip it to Pending/Running intake."""
    with connection_scope() as conn:
        cursor = conn.execute(
            "INSERT INTO jobs (product_id) VALUES (?)",
            (product_id,),
        )
        job_id = cursor.lastrowid
        row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
    logger.info("Created job %s for product %s", job_id, product_id)
    return Job.from_row(row)


def get_next_pending_job() -> Optional[Job]:
    """Fetch the oldest pending job (single-worker, one-product-at-a-time model)."""
    with connection_scope() as conn:
        row = conn.execute(
            "SELECT * FROM jobs WHERE status = 'Pending' ORDER BY created_at ASC LIMIT 1"
        ).fetchone()
    return Job.from_row(row) if row else None


def update_job_status(job_id: int, status: str, error_message: Optional[str] = None) -> None:
    with connection_scope() as conn:
        if status == "Running":
            conn.execute(
                "UPDATE jobs SET status = ?, started_at = datetime('now') WHERE id = ?",
                (status, job_id),
            )
        elif status in ("Completed", "Failed", "Cancelled"):
            conn.execute(
                "UPDATE jobs SET status = ?, error_message = ?, completed_at = datetime('now') WHERE id = ?",
                (status, error_message, job_id),
            )
        else:
            conn.execute("UPDATE jobs SET status = ? WHERE id = ?", (status, job_id))
    logger.info("Job %s status -> %s", job_id, status)


def list_jobs_for_product(product_id: int) -> list[Job]:
    with connection_scope() as conn:
        rows = conn.execute(
            "SELECT * FROM jobs WHERE product_id = ? ORDER BY created_at DESC", (product_id,)
        ).fetchall()
    return [Job.from_row(row) for row in rows]


# --- Versions ----------------------------------------------------------------

def create_version(product_id: int, job_id: Optional[int], reviewer_feedback: Optional[str] = None) -> Version:
    """Create a new immutable version. Versions are never overwritten."""
    with connection_scope() as conn:
        next_number = conn.execute(
            "SELECT COALESCE(MAX(version_number), 0) + 1 FROM versions WHERE product_id = ?",
            (product_id,),
        ).fetchone()[0]
        product_row = conn.execute(
            "SELECT output_dir FROM products WHERE id = ?", (product_id,)
        ).fetchone()
        output_dir = f"{product_row['output_dir']}/v{next_number}"
        cursor = conn.execute(
            """INSERT INTO versions (product_id, job_id, version_number, reviewer_feedback, output_dir)
               VALUES (?, ?, ?, ?, ?)""",
            (product_id, job_id, next_number, reviewer_feedback, output_dir),
        )
        version_id = cursor.lastrowid
        row = conn.execute("SELECT * FROM versions WHERE id = ?", (version_id,)).fetchone()
    logger.info("Created version %s (v%s) for product %s", version_id, next_number, product_id)
    return Version.from_row(row)


def get_latest_version(product_id: int) -> Optional[Version]:
    with connection_scope() as conn:
        row = conn.execute(
            "SELECT * FROM versions WHERE product_id = ? ORDER BY version_number DESC LIMIT 1",
            (product_id,),
        ).fetchone()
    return Version.from_row(row) if row else None


def list_versions_for_product(product_id: int) -> list[Version]:
    with connection_scope() as conn:
        rows = conn.execute(
            "SELECT * FROM versions WHERE product_id = ? ORDER BY version_number DESC",
            (product_id,),
        ).fetchall()
    return [Version.from_row(row) for row in rows]


def update_version_status(version_id: int, status: str, reviewer_feedback: Optional[str] = None) -> None:
    with connection_scope() as conn:
        conn.execute(
            "UPDATE versions SET status = ?, reviewer_feedback = ? WHERE id = ?",
            (status, reviewer_feedback, version_id),
        )
    logger.info("Version %s status -> %s", version_id, status)


# --- Outputs ----------------------------------------------------------------

def add_output(version_id: int, output_type: str, file_path: str) -> Output:
    with connection_scope() as conn:
        cursor = conn.execute(
            "INSERT INTO outputs (version_id, output_type, file_path) VALUES (?, ?, ?)",
            (version_id, output_type, file_path),
        )
        output_id = cursor.lastrowid
        row = conn.execute("SELECT * FROM outputs WHERE id = ?", (output_id,)).fetchone()
    return Output.from_row(row)


def list_outputs_for_version(version_id: int) -> list[Output]:
    with connection_scope() as conn:
        rows = conn.execute(
            "SELECT * FROM outputs WHERE version_id = ? ORDER BY created_at ASC", (version_id,)
        ).fetchall()
    return [Output.from_row(row) for row in rows]


# --- Scraped data ----------------------------------------------------------------

def upsert_scraped_data(
    product_id: int,
    title: str,
    description_html: str,
    description_text: str,
    price: Optional[float],
    compare_at_price: Optional[float],
    image_urls: list[str],
    specs: dict[str, str],
) -> ScrapedData:
    """Insert or overwrite the single scraped_data row for a product."""
    with connection_scope() as conn:
        conn.execute(
            """INSERT INTO scraped_data
                   (product_id, title, description_html, description_text,
                    price, compare_at_price, image_urls, specs, scraped_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
               ON CONFLICT(product_id) DO UPDATE SET
                   title = excluded.title,
                   description_html = excluded.description_html,
                   description_text = excluded.description_text,
                   price = excluded.price,
                   compare_at_price = excluded.compare_at_price,
                   image_urls = excluded.image_urls,
                   specs = excluded.specs,
                   scraped_at = excluded.scraped_at""",
            (
                product_id, title, description_html, description_text,
                price, compare_at_price, json.dumps(image_urls), json.dumps(specs),
            ),
        )
        row = conn.execute(
            "SELECT * FROM scraped_data WHERE product_id = ?", (product_id,)
        ).fetchone()
    logger.info("Upserted scraped_data for product %s", product_id)
    return ScrapedData.from_row(row)


def get_scraped_data(product_id: int) -> Optional[ScrapedData]:
    with connection_scope() as conn:
        row = conn.execute(
            "SELECT * FROM scraped_data WHERE product_id = ?", (product_id,)
        ).fetchone()
    return ScrapedData.from_row(row) if row else None


# --- Logs ----------------------------------------------------------------

def add_log(message: str, product_id: Optional[int] = None, job_id: Optional[int] = None,
            level: str = "INFO") -> LogEntry:
    with connection_scope() as conn:
        cursor = conn.execute(
            "INSERT INTO logs (product_id, job_id, level, message) VALUES (?, ?, ?, ?)",
            (product_id, job_id, level, message),
        )
        log_id = cursor.lastrowid
        row = conn.execute("SELECT * FROM logs WHERE id = ?", (log_id,)).fetchone()
    return LogEntry.from_row(row)


def list_logs_for_product(product_id: int, limit: int = 200) -> list[LogEntry]:
    with connection_scope() as conn:
        rows = conn.execute(
            "SELECT * FROM logs WHERE product_id = ? ORDER BY created_at DESC LIMIT ?",
            (product_id, limit),
        ).fetchall()
    return [LogEntry.from_row(row) for row in rows]

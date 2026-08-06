"""Seed the database with the starting product catalog.

Run with: python -m database.seed_products

Idempotent — the `url` column is UNIQUE, so re-running skips what already
exists rather than creating duplicates. Add further products through the
Dashboard's "Add Product" form, or by extending SEED_PRODUCTS here.
"""
from __future__ import annotations

import logging
import sqlite3

from config.logging_setup import configure_logging
from database.connection import init_db
from database.repository import InvalidProductError, create_product

logger = logging.getLogger(__name__)

# One product from each of three different collections, so the pipeline is
# exercised against genuinely different spec tables, price points and photo
# counts rather than three near-identical hoverboards.
SEED_PRODUCTS: tuple[tuple[str, str], ...] = (
    (
        "8.5 Off-Road Pro",
        "https://radboards.in/collections/buy-hoverboards-online-for-kids-for-adults"
        "/products/8-5-off-road-pro",
    ),
    (
        "Classic 6.5 Limited Edition",
        "https://radboards.in/collections/buy-hoverboards-online-for-kids-for-adults"
        "/products/buy-hoverboard-online-classic-6-5-limited-edition",
    ),
    (
        "Rover Off-Roader XL",
        "https://radboards.in/collections/professional/products/rover-off-roader-xl",
    ),
)


def seed() -> int:
    """Insert any seed product that isn't already present. Returns how many were added."""
    init_db()
    added = 0
    for name, url in SEED_PRODUCTS:
        try:
            product = create_product(name, url)
        except sqlite3.IntegrityError:
            print(f"  = already present: {name}")
        except InvalidProductError as exc:
            print(f"  ! skipped {name}: {exc}")
        else:
            added += 1
            print(f"  + #{product.id} {product.name}")
    return added


def main() -> None:
    configure_logging()
    print(f"Seeding {len(SEED_PRODUCTS)} products…")
    added = seed()
    print(f"\nDone — {added} added.")
    print("Next: streamlit run streamlit_app/app.py, then press Run on a product.")


if __name__ == "__main__":
    main()

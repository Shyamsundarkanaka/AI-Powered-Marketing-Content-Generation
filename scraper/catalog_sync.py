"""Synchronize the focused Radboards catalogue with the local SQLite tracker."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from database.repository import add_product
from scraper.radboards import RadboardsScraper


@dataclass(frozen=True)
class CatalogSyncResult:
    """Counts returned after a catalogue-to-database synchronization."""

    inserted: int
    skipped_existing: int


def sync_catalog_to_database(
    database_path: str | Path,
    scraper: RadboardsScraper | None = None,
) -> CatalogSyncResult:
    """Add focused Radboards products to SQLite without duplicating URLs.

    The catalogue remains the source of scraped product details. SQLite stores
    the product identity, title, and category so future workflow runs can
    choose the next pending product.
    """
    active_scraper = scraper or RadboardsScraper()
    inserted = 0
    skipped_existing = 0

    for category, products in active_scraper.fetch_all_categories().items():
        for product in products:
            try:
                add_product(database_path, product.url, product.title, category)
                inserted += 1
            except ValueError as error:
                if "already exists" not in str(error):
                    raise
                skipped_existing += 1

    return CatalogSyncResult(inserted=inserted, skipped_existing=skipped_existing)
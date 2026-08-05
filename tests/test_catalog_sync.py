"""Tests for synchronizing the focused catalogue into SQLite."""

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from database.repository import get_next_unprocessed_product
from scraper.catalog_sync import sync_catalog_to_database
from scraper.radboards import ScrapedProduct


class _FakeScraper:
    """Return a small deterministic catalogue for synchronization tests."""

    def fetch_all_categories(self) -> dict[str, list[ScrapedProduct]]:
        """Return two products from the approved catalogue scope."""
        return {
            "Hoverboards": [
                ScrapedProduct(
                    category="Hoverboards", title="Classic 6.5", url="https://radboards.in/products/classic-6-5",
                    description="", price_inr=16999, available=True, image_urls=(),
                )
            ],
            "E-Scooters": [
                ScrapedProduct(
                    category="E-Scooters", title="Shockwave V1", url="https://radboards.in/products/shockwave-v1",
                    description="", price_inr=36000, available=True, image_urls=(),
                )
            ],
        }


class CatalogSyncTests(unittest.TestCase):
    """Verify that products are added once and retain their category."""

    def setUp(self) -> None:
        """Create an isolated database path for each test."""
        self.temporary_directory = TemporaryDirectory()
        self.database_path = Path(self.temporary_directory.name) / "marketing_content.db"
        self.scraper = _FakeScraper()

    def tearDown(self) -> None:
        """Remove the temporary database after each test."""
        self.temporary_directory.cleanup()

    def test_sync_inserts_focused_products(self) -> None:
        """New catalogue products are saved as pending database records."""
        result = sync_catalog_to_database(self.database_path, self.scraper)
        next_product = get_next_unprocessed_product(self.database_path)

        self.assertEqual(result.inserted, 2)
        self.assertEqual(result.skipped_existing, 0)
        self.assertEqual(next_product.category, "Hoverboards")
        self.assertEqual(next_product.product_name, "Classic 6.5")

    def test_sync_skips_products_already_in_database(self) -> None:
        """Repeating a synchronization does not add duplicate product URLs."""
        sync_catalog_to_database(self.database_path, self.scraper)
        result = sync_catalog_to_database(self.database_path, self.scraper)

        self.assertEqual(result.inserted, 0)
        self.assertEqual(result.skipped_existing, 2)


if __name__ == "__main__":
    unittest.main()
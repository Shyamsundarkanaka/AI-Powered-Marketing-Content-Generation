"""Tests for the product repository."""

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from database.connection import initialize_database
from database.repository import add_product, get_next_unprocessed_product


class ProductRepositoryTests(unittest.TestCase):
    """Verify product persistence against an isolated SQLite database."""

    def setUp(self) -> None:
        """Create a temporary database path for each test."""
        self.temporary_directory = TemporaryDirectory()
        self.database_path = Path(self.temporary_directory.name) / "marketing_content.db"

    def tearDown(self) -> None:
        """Remove the temporary database after each test."""
        self.temporary_directory.cleanup()

    def test_initialize_database_creates_products_table(self) -> None:
        """Database initialization creates the SQLite file and schema."""
        initialize_database(self.database_path)

        self.assertTrue(self.database_path.exists())

    def test_add_product_and_get_next_unprocessed_product(self) -> None:
        """A new product is available as the next pending product."""
        added_product = add_product(
            self.database_path,
            "https://radboards.in/products/example",
            "Example Board",
        )

        next_product = get_next_unprocessed_product(self.database_path)

        self.assertEqual(next_product, added_product)
        self.assertEqual(next_product.status, "pending")
        self.assertEqual(next_product.approval_status, "not_reviewed")

    def test_add_product_rejects_duplicate_urls(self) -> None:
        """The same product URL cannot be tracked twice."""
        add_product(self.database_path, "https://radboards.in/products/example")

        with self.assertRaisesRegex(ValueError, "already exists"):
            add_product(self.database_path, "https://radboards.in/products/example")


if __name__ == "__main__":
    unittest.main()
"""Tests for the narrowly scoped Radboards product scraper."""

import json
import unittest

from scraper.radboards import MAX_PRODUCTS_PER_CATEGORY, TARGET_CATEGORIES, RadboardsScraper


class RadboardsScraperTests(unittest.TestCase):
    """Verify catalogue parsing without making live website requests."""

    def test_scope_contains_exactly_five_categories(self) -> None:
        """Only the selected five product categories are eligible for scraping."""
        self.assertEqual(len(TARGET_CATEGORIES), 5)
        self.assertEqual(
            [category.name for category in TARGET_CATEGORIES],
            [
                "Hoverboards",
                "Self Balancing Scooters",
                "Handle Hoverboards",
                "Electric Unicycles",
                "E-Scooters",
            ],
        )

    def test_fetch_category_maps_public_shopify_product_data(self) -> None:
        """A public catalogue record becomes the project's stable product model."""
        payload = {
            "products": [
                {
                    "title": "Electric Unicycle KingSong 14M",
                    "handle": "electric-unicycle-kingsong-14m",
                    "body_html": "<p>Compact <strong>electric</strong> ride.</p>",
                    "variants": [{"price": "50000.00", "available": True}],
                    "images": [{"src": "https://cdn.shopify.com/example.jpg"}],
                }
            ]
        }
        requested_urls: list[str] = []

        def fetcher(url: str) -> bytes:
            requested_urls.append(url)
            return json.dumps(payload).encode("utf-8")

        product = RadboardsScraper(fetcher).fetch_category(TARGET_CATEGORIES[3])[0]

        self.assertEqual(product.category, "Electric Unicycles")
        self.assertEqual(product.title, "Electric Unicycle KingSong 14M")
        self.assertEqual(product.price_inr, 50000)
        self.assertTrue(product.available)
        self.assertEqual(product.description, "Compact electric ride.")
        self.assertEqual(product.image_urls, ("https://cdn.shopify.com/example.jpg",))
        self.assertIn("electric-unicycle-euc/products.json?limit=7", requested_urls[0])

    def test_fetch_category_limits_results_to_seven_products(self) -> None:
        """A larger feed cannot expand the approved product scope."""
        payload = {
            "products": [
                {
                    "title": f"Product {number}",
                    "handle": f"product-{number}",
                    "body_html": "",
                    "variants": [{"price": "1.00", "available": True}],
                    "images": [],
                }
                for number in range(MAX_PRODUCTS_PER_CATEGORY + 1)
            ]
        }

        products = RadboardsScraper(lambda _: json.dumps(payload).encode("utf-8")).fetch_category(
            TARGET_CATEGORIES[0]
        )

        self.assertEqual(len(products), MAX_PRODUCTS_PER_CATEGORY)


if __name__ == "__main__":
    unittest.main()
"""Tests for controlled local product-image downloads."""

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from scraper.image_downloader import MAX_IMAGES_PER_PRODUCT, download_product_images
from scraper.radboards import ScrapedProduct


class ImageDownloaderTests(unittest.TestCase):
    """Verify image downloads without requesting live website images."""

    def setUp(self) -> None:
        """Create an isolated output folder for each test."""
        self.temporary_directory = TemporaryDirectory()
        self.output_directory = Path(self.temporary_directory.name)
        self.product = ScrapedProduct(
            category="Electric Unicycles",
            title="KingSong 14M",
            url="https://radboards.in/products/electric-unicycle-kingsong-14m",
            description="A compact electric unicycle.",
            price_inr=50000,
            available=True,
            image_urls=(
                "https://cdn.shopify.com/images/one.jpg?version=1",
                "https://cdn.shopify.com/images/two.png",
            ),
        )

    def tearDown(self) -> None:
        """Remove test files after each test."""
        self.temporary_directory.cleanup()

    def test_downloads_images_to_product_specific_folder(self) -> None:
        """Images are stored with stable names under their product handle."""
        paths = download_product_images(self.product, self.output_directory, lambda _: b"image-data")

        self.assertEqual(len(paths), 2)
        self.assertEqual(paths[0].name, "01.jpg")
        self.assertEqual(paths[1].name, "02.png")
        self.assertEqual(paths[0].read_bytes(), b"image-data")
        self.assertIn("electric-unicycle-kingsong-14m", str(paths[0]))

    def test_reuses_existing_images_without_downloading_again(self) -> None:
        """A second run does not overwrite or re-request local image files."""
        download_product_images(self.product, self.output_directory, lambda _: b"first-download")

        def unexpected_download(_: str) -> bytes:
            raise AssertionError("Existing images should not be downloaded again.")

        paths = download_product_images(self.product, self.output_directory, unexpected_download)

        self.assertEqual(paths[0].read_bytes(), b"first-download")

    def test_limits_downloads_to_five_images(self) -> None:
        """The downloader preserves the bounded product-image scope."""
        product = self.product.__class__(
            **{**self.product.__dict__, "image_urls": tuple(f"https://cdn.shopify.com/{number}.jpg" for number in range(6))}
        )

        paths = download_product_images(product, self.output_directory, lambda _: b"image-data")

        self.assertEqual(len(paths), MAX_IMAGES_PER_PRODUCT)


if __name__ == "__main__":
    unittest.main()
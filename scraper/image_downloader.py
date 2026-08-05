"""Download a bounded set of public product images for local processing."""

from __future__ import annotations

from pathlib import Path
from typing import Callable
from urllib.error import URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from scraper.radboards import ScrapedProduct

MAX_IMAGES_PER_PRODUCT = 5
_ALLOWED_IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}


class ImageDownloadError(RuntimeError):
    """Raised when a public product image cannot be downloaded."""


def _download_bytes(url: str) -> bytes:
    """Download a public image without authentication."""
    request = Request(url, headers={"User-Agent": "RadboardsMarketingContentBot/1.0"})
    try:
        with urlopen(request, timeout=30) as response:
            return response.read()
    except URLError as error:
        raise ImageDownloadError(f"Unable to download product image: {url}") from error


def _safe_folder_name(product: ScrapedProduct) -> str:
    """Create a stable local folder name from the public product URL."""
    handle = urlsplit(product.url).path.rstrip("/").split("/")[-1]
    if not handle:
        raise ValueError("Product URL must contain a product handle.")
    return handle


def _image_suffix(url: str) -> str:
    """Return a safe local file suffix for an image URL."""
    suffix = Path(urlsplit(url).path).suffix.lower()
    return suffix if suffix in _ALLOWED_IMAGE_SUFFIXES else ".jpg"


def download_product_images(
    product: ScrapedProduct,
    output_directory: str | Path = "output/images",
    downloader: Callable[[str], bytes] = _download_bytes,
) -> tuple[Path, ...]:
    """Download up to five images for ``product`` and return their local paths.

    Existing files are reused, making repeated runs safe and avoiding duplicate
    website requests. Images are kept outside version control under
    ``output/images``.
    """
    product_directory = Path(output_directory) / _safe_folder_name(product)
    product_directory.mkdir(parents=True, exist_ok=True)

    local_paths: list[Path] = []
    for position, image_url in enumerate(product.image_urls[:MAX_IMAGES_PER_PRODUCT], start=1):
        image_path = product_directory / f"{position:02d}{_image_suffix(image_url)}"
        if not image_path.exists():
            try:
                image_path.write_bytes(downloader(image_url))
            except OSError as error:
                raise ImageDownloadError(f"Unable to save product image: {image_path}") from error
        local_paths.append(image_path)

    return tuple(local_paths)
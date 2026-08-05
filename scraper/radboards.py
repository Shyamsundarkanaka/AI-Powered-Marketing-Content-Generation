"""Read the selected Radboards product catalogue from its public Shopify feed."""

from __future__ import annotations

import json
from dataclasses import dataclass
from html.parser import HTMLParser
from typing import Callable
from urllib.error import URLError
from urllib.request import Request, urlopen

BASE_URL = "https://radboards.in"
MAX_PRODUCTS_PER_CATEGORY = 7


@dataclass(frozen=True)
class ProductCategory:
    """A Radboards collection included in the marketing-content scope."""

    name: str
    collection_handle: str


TARGET_CATEGORIES = (
    ProductCategory("Hoverboards", "buy-hoverboards-online-for-kids-for-adults"),
    ProductCategory("Self Balancing Scooters", "professional"),
    ProductCategory("Handle Hoverboards", "handle-hoverboard"),
    ProductCategory("Electric Unicycles", "electric-unicycle-euc"),
    ProductCategory("E-Scooters", "electric-kickscooter-for-adults-kickscooter-electric-adults-kids"),
)


@dataclass(frozen=True)
class ScrapedProduct:
    """Product information required by the downstream marketing workflow."""

    category: str
    title: str
    url: str
    description: str
    price_inr: int
    available: bool
    image_urls: tuple[str, ...]


class _TextExtractor(HTMLParser):
    """Convert product-description HTML to clean, readable text."""

    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        """Collect non-empty text fragments from the HTML body."""
        cleaned_data = " ".join(data.split())
        if cleaned_data:
            self.parts.append(cleaned_data)


def _html_to_text(html: str) -> str:
    """Return collapsed text from a Shopify product description."""
    extractor = _TextExtractor()
    extractor.feed(html)
    return " ".join(extractor.parts)


def _download_json(url: str) -> bytes:
    """Download a public Radboards JSON endpoint without authentication."""
    request = Request(url, headers={"User-Agent": "RadboardsMarketingContentBot/1.0"})
    try:
        with urlopen(request, timeout=20) as response:
            return response.read()
    except URLError as error:
        raise RuntimeError(f"Unable to fetch Radboards catalogue: {url}") from error


class RadboardsScraper:
    """Fetch products from the five approved Radboards collections only."""

    def __init__(self, fetcher: Callable[[str], bytes] = _download_json) -> None:
        """Create a scraper using ``fetcher`` for public HTTP requests."""
        self._fetcher = fetcher

    def fetch_category(self, category: ProductCategory) -> list[ScrapedProduct]:
        """Fetch up to seven products from one approved collection."""
        endpoint = (
            f"{BASE_URL}/collections/{category.collection_handle}/products.json"
            f"?limit={MAX_PRODUCTS_PER_CATEGORY}"
        )
        try:
            payload = json.loads(self._fetcher(endpoint).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise RuntimeError(f"Radboards returned invalid catalogue data for {category.name}.") from error

        products = payload.get("products")
        if not isinstance(products, list):
            raise RuntimeError(f"Radboards catalogue data is missing products for {category.name}.")

        return [self._to_scraped_product(category, product) for product in products[:MAX_PRODUCTS_PER_CATEGORY]]

    def fetch_all_categories(self) -> dict[str, list[ScrapedProduct]]:
        """Fetch only the five pre-approved product categories."""
        return {category.name: self.fetch_category(category) for category in TARGET_CATEGORIES}

    @staticmethod
    def _to_scraped_product(category: ProductCategory, product: dict[str, object]) -> ScrapedProduct:
        """Map a Shopify product record to the stable project data model."""
        variants = product.get("variants", [])
        images = product.get("images", [])
        first_variant = variants[0] if isinstance(variants, list) and variants else {}
        price_inr = int(float(first_variant.get("price", 0))) if isinstance(first_variant, dict) else 0
        image_urls = tuple(
            image["src"]
            for image in images
            if isinstance(image, dict) and isinstance(image.get("src"), str)
        )
        available = any(
            isinstance(variant, dict) and variant.get("available") is True for variant in variants
        ) if isinstance(variants, list) else False
        handle = product.get("handle")
        title = product.get("title")
        body_html = product.get("body_html")
        if not isinstance(handle, str) or not isinstance(title, str):
            raise RuntimeError("Radboards catalogue returned a product without a title or handle.")

        return ScrapedProduct(
            category=category.name,
            title=title,
            url=f"{BASE_URL}/products/{handle}",
            description=_html_to_text(body_html) if isinstance(body_html, str) else "",
            price_inr=price_inr,
            available=available,
            image_urls=image_urls,
        )
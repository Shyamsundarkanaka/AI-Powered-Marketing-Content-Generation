"""Scrapes a single Shopify product page via its public `.json` endpoint.

Any Shopify storefront exposes structured product data at `<product-url>.json`
— title, description HTML, variants with prices, and images — with no auth and
no JS rendering required. Radboards is one such store, but nothing here is
specific to it, which is what lets `brand/generate.py` repoint the whole system
at a different store.

The description's spec table (charging time, motor, range, …) arrives as a
plain HTML `<table>` inside `body_html`, and is parsed out separately from the
descriptive prose so agents can quote specs verbatim.
"""
from __future__ import annotations

import logging
from typing import Any, Optional
from urllib.parse import urlsplit, urlunsplit

from bs4 import BeautifulSoup

from config.http import http_session
from config.settings import HTTP_TIMEOUT_SECONDS

logger = logging.getLogger(__name__)

# Spec tables are the useful part of a product page, but a store can put an
# arbitrarily long one there. This bounds what reaches a prompt.
MAX_SPECS = 40
MAX_SPEC_VALUE_CHARS = 200


class ScrapeError(RuntimeError):
    """Raised when a product page can't be fetched or has no usable data."""


def json_url(product_url: str) -> str:
    """Turn a product page URL into its Shopify `.json` endpoint URL."""
    scheme, netloc, path, _query, _fragment = urlsplit(product_url)
    if not scheme or not netloc:
        raise ScrapeError(f"{product_url!r} is not a valid absolute URL")
    path = path.rstrip("/")
    if not path.endswith(".json"):
        path += ".json"
    return urlunsplit((scheme, netloc, path, "", ""))


def _parse_specs_and_description(body_html: str) -> tuple[dict[str, str], str]:
    """Split body_html into a specs dict (from its <table>) and plain description text."""
    soup = BeautifulSoup(body_html or "", "html.parser")

    specs: dict[str, str] = {}
    for table in soup.find_all("table"):
        for row in table.find_all("tr"):
            cells = row.find_all(["td", "th"])
            if len(cells) >= 2:
                key = " ".join(cells[0].get_text(strip=True).split())
                value = " ".join(cells[1].get_text(strip=True).split())
                if key and value and len(specs) < MAX_SPECS:
                    specs[key] = value[:MAX_SPEC_VALUE_CHARS]
        # Remove the table so its cells don't also show up in the prose.
        table.decompose()

    description_text = " ".join(soup.get_text(separator=" ").split())
    return specs, description_text


def _to_float(value: Any) -> Optional[float]:
    """Shopify sends prices as decimal strings; a bad one must not fail a scrape."""
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        logger.warning("Ignoring unparseable price value %r", value)
        return None


def _cheapest_available_variant(variants: list[dict[str, Any]]) -> dict[str, Any]:
    """The variant a shopper would actually be quoted.

    Taking `variants[0]` blindly is wrong on any store whose first variant is
    sold out or is an accessory add-on: the brief would then be built around a
    price the customer can't buy at. Prefer available variants, cheapest first.
    """
    if not variants:
        return {}
    priced = [v for v in variants if _to_float(v.get("price")) is not None]
    if not priced:
        return variants[0]
    available = [v for v in priced if v.get("available", True)]
    return min(available or priced, key=lambda v: _to_float(v.get("price")) or 0.0)


def scrape_product(product_url: str) -> dict[str, Any]:
    """Fetch and parse one Shopify product page.

    Returns a dict with: title, description_html, description_text, price,
    compare_at_price, image_urls, specs.
    """
    endpoint = json_url(product_url)
    try:
        response = http_session().get(endpoint, timeout=HTTP_TIMEOUT_SECONDS)
    except Exception as exc:  # noqa: BLE001 — requests raises a family of these
        raise ScrapeError(f"GET {endpoint} failed: {type(exc).__name__}: {exc}") from exc

    if response.status_code != 200:
        raise ScrapeError(
            f"GET {endpoint} returned {response.status_code}. "
            f"Check the product URL is correct and the store is a public Shopify storefront."
        )

    try:
        payload = response.json()
    except ValueError as exc:
        raise ScrapeError(
            f"{endpoint} did not return JSON — this may not be a Shopify product page."
        ) from exc

    product = payload.get("product")
    if not isinstance(product, dict) or not product.get("title"):
        raise ScrapeError(f"No usable 'product' object in the response from {endpoint}")

    body_html = product.get("body_html") or ""
    specs, description_text = _parse_specs_and_description(body_html)
    variant = _cheapest_available_variant(product.get("variants") or [])
    image_urls = [img["src"] for img in (product.get("images") or []) if img.get("src")]

    if not image_urls:
        logger.warning("Product %r has no images; the video will use brand backgrounds only.", product["title"])

    return {
        "title": product["title"].strip(),
        "description_html": body_html,
        "description_text": description_text,
        "price": _to_float(variant.get("price")),
        "compare_at_price": _to_float(variant.get("compare_at_price")),
        "image_urls": image_urls,
        "specs": specs,
    }

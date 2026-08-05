"""Scrapes a single Radboards (Shopify) product page via its .json endpoint.

Radboards is a standard Shopify store: every product page at
``<url>`` has a matching ``<url>.json`` endpoint returning structured
product data (title, description, price, images) with no JS rendering
required. The description's spec table (charging time, motor, range, ...)
arrives as a plain HTML `<table>` inside `body_html` and is parsed out
separately from the descriptive text.
"""
from __future__ import annotations

import logging
from typing import Optional
from urllib.parse import urlsplit, urlunsplit

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

REQUEST_TIMEOUT = 15
USER_AGENT = "Mozilla/5.0 (compatible; RadboardsContentBot/1.0)"


class ScrapeError(RuntimeError):
    """Raised when a product page can't be fetched or has no usable data."""


def _json_url(product_url: str) -> str:
    """Turn a product page URL into its Shopify `.json` endpoint URL."""
    scheme, netloc, path, _query, _fragment = urlsplit(product_url)
    path = path.rstrip("/") + ".json"
    return urlunsplit((scheme, netloc, path, "", ""))


def _parse_specs_and_description(body_html: str) -> tuple[dict[str, str], str]:
    """Split body_html into a specs dict (from its <table>) and plain description text."""
    soup = BeautifulSoup(body_html or "", "html.parser")

    specs: dict[str, str] = {}
    for table in soup.find_all("table"):
        for row in table.find_all("tr"):
            cells = row.find_all("td")
            if len(cells) >= 2:
                key = cells[0].get_text(strip=True)
                value = cells[1].get_text(strip=True)
                if key:
                    specs[key] = value
        table.decompose()

    description_text = " ".join(soup.get_text(separator=" ").split())
    return specs, description_text


def _to_float(value: Optional[str]) -> Optional[float]:
    if value in (None, ""):
        return None
    return float(value)


def scrape_product(product_url: str) -> dict:
    """Fetch and parse one Radboards product page.

    Returns a dict with: title, description_html, description_text, price,
    compare_at_price, image_urls, specs.
    """
    json_url = _json_url(product_url)
    response = requests.get(json_url, headers={"User-Agent": USER_AGENT}, timeout=REQUEST_TIMEOUT)
    if response.status_code != 200:
        raise ScrapeError(f"GET {json_url} returned {response.status_code}")

    payload = response.json()
    product = payload.get("product")
    if not product:
        raise ScrapeError(f"No 'product' object in response from {json_url}")

    body_html = product.get("body_html") or ""
    specs, description_text = _parse_specs_and_description(body_html)

    variants = product.get("variants") or []
    first_variant = variants[0] if variants else {}

    image_urls = [img["src"] for img in product.get("images", []) if img.get("src")]

    return {
        "title": product["title"],
        "description_html": body_html,
        "description_text": description_text,
        "price": _to_float(first_variant.get("price")),
        "compare_at_price": _to_float(first_variant.get("compare_at_price")),
        "image_urls": image_urls,
        "specs": specs,
    }

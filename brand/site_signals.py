"""Pulls raw brand signals from any live Shopify storefront — no auth required.

Same trick as `scraper/shopify.py` (Shopify's public `.json` endpoints), plus a
plain homepage fetch for meta tags and an "About" page if the nav links to one.
This is deliberately shallow: it gathers just enough raw material for the
brand-generation prompts in `brand/generate.py` to reason about, not a full
site crawl.
"""
from __future__ import annotations

import logging
import re
from typing import Any
from urllib.parse import urljoin, urlsplit, urlunsplit

import requests
from bs4 import BeautifulSoup

from config.http import http_session
from config.settings import HTTP_TIMEOUT_SECONDS

logger = logging.getLogger(__name__)

MAX_PRODUCTS = 20
MAX_SNIPPET_CHARS = 500


class SiteSignalError(RuntimeError):
    """Raised when the store can't be reached or has no public product catalog."""


def _root(url: str) -> str:
    scheme, netloc, _path, _query, _fragment = urlsplit(url)
    if not scheme:
        scheme = "https"
    return urlunsplit((scheme, netloc, "", "", ""))


def _get(url: str) -> requests.Response | None:
    try:
        resp = http_session().get(url, timeout=HTTP_TIMEOUT_SECONDS)
        if resp.status_code == 200:
            return resp
        logger.warning("GET %s returned %s", url, resp.status_code)
    except requests.RequestException as exc:
        logger.warning("GET %s failed: %s", url, exc)
    return None


def _fetch_homepage_meta(root: str) -> dict[str, Any]:
    resp = _get(root)
    if not resp:
        return {}
    soup = BeautifulSoup(resp.text, "html.parser")

    title = (soup.title.string or "").strip() if soup.title else ""

    description = ""
    meta_desc = soup.find("meta", attrs={"name": "description"})
    if meta_desc and meta_desc.get("content"):
        description = meta_desc["content"].strip()

    theme_color = ""
    meta_theme = soup.find("meta", attrs={"name": "theme-color"})
    if meta_theme and meta_theme.get("content"):
        theme_color = meta_theme["content"].strip()

    currency_match = re.search(r'Shopify\.currency\s*=\s*\{[^}]*?"active"\s*:\s*"([A-Z]{3})"', resp.text)
    currency_code = currency_match.group(1) if currency_match else ""

    about_snippet = ""
    about_link = soup.find("a", string=re.compile(r"about|our story", re.I))
    if about_link and about_link.get("href"):
        about_resp = _get(urljoin(root, about_link["href"]))
        if about_resp:
            about_soup = BeautifulSoup(about_resp.text, "html.parser")
            about_snippet = " ".join(about_soup.get_text(separator=" ").split())[:MAX_SNIPPET_CHARS]

    return {
        "site_title": title,
        "meta_description": description,
        "theme_color": theme_color,
        "currency_code": currency_code,
        "about_snippet": about_snippet,
    }


def _fetch_sample_products(root: str) -> list[dict[str, Any]]:
    resp = _get(urljoin(root, f"/products.json?limit={MAX_PRODUCTS}"))
    if not resp:
        return []
    try:
        payload = resp.json()
    except ValueError:
        return []

    products = []
    for product in (payload.get("products") or [])[:MAX_PRODUCTS]:
        variants = product.get("variants") or []
        prices = [float(v["price"]) for v in variants if v.get("price") not in (None, "")]
        soup = BeautifulSoup(product.get("body_html") or "", "html.parser")
        description = " ".join(soup.get_text(separator=" ").split())[:MAX_SNIPPET_CHARS]
        products.append(
            {
                "title": product.get("title"),
                "product_type": product.get("product_type") or "",
                "tags": product.get("tags") or "",
                "price_min": min(prices) if prices else None,
                "price_max": max(prices) if prices else None,
                "description": description,
            }
        )
    return products


def collect_signals(store_url: str) -> dict[str, Any]:
    """Gather everything the brand-generation prompts need from a live Shopify store.

    Raises `SiteSignalError` if the store has no reachable public product catalog —
    that catalog is the one thing every downstream prompt depends on.
    """
    root = _root(store_url)
    products = _fetch_sample_products(root)
    if not products:
        raise SiteSignalError(
            f"Could not read {root}/products.json — is this a live, public Shopify store?"
        )
    meta = _fetch_homepage_meta(root)
    return {"root_url": root, **meta, "sample_products": products}

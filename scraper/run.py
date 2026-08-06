"""Scrape one or all products and store the results in `scraped_data`.

The worker calls `scrape_and_store()` as the first stage of every job. The CLI
is for re-scraping without running a full generation:

    python -m scraper.run --product-id 5
    python -m scraper.run --all
"""
from __future__ import annotations

import argparse
import logging

from database.connection import init_db
from database.repository import (
    add_log,
    get_product,
    list_products,
    update_product_name,
    upsert_scraped_data,
)
from scraper.shopify import ScrapeError, scrape_product

logger = logging.getLogger(__name__)


def scrape_and_store(product_id: int, job_id: int | None = None) -> None:
    product = get_product(product_id)
    if not product:
        raise ValueError(f"No product with id {product_id}")

    logger.info("Scraping product %s (%s)", product.id, product.url)
    try:
        data = scrape_product(product.url)
    except ScrapeError as exc:
        add_log(f"Scrape failed: {exc}", product_id=product.id, job_id=job_id, level="ERROR")
        raise

    if data["title"] and data["title"] != product.name:
        logger.info("Product %s name changed: %r -> %r", product.id, product.name, data["title"])
        update_product_name(product.id, data["title"])

    upsert_scraped_data(
        product_id=product.id,
        title=data["title"],
        description_html=data["description_html"],
        description_text=data["description_text"],
        price=data["price"],
        compare_at_price=data["compare_at_price"],
        image_urls=data["image_urls"],
        specs=data["specs"],
    )
    add_log(
        f"Scraped OK: {len(data['image_urls'])} images, {len(data['specs'])} specs",
        product_id=product.id,
        job_id=job_id,
        level="INFO",
    )
    logger.info("Stored scraped_data for product %s", product.id)


def main() -> None:
    from config.logging_setup import configure_logging

    parser = argparse.ArgumentParser(description="Scrape Shopify product pages.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--product-id", type=int, help="Scrape a single product by id.")
    group.add_argument("--all", action="store_true", help="Scrape every product in the database.")
    args = parser.parse_args()

    configure_logging()
    init_db()

    if args.product_id is not None:
        try:
            scrape_and_store(args.product_id)
        except (ScrapeError, ValueError) as exc:
            raise SystemExit(f"Scrape failed: {exc}") from None
        return

    products = list_products()
    logger.info("Scraping %d products", len(products))
    failures = 0
    for product in products:
        try:
            scrape_and_store(product.id)
        except ScrapeError as exc:
            failures += 1
            logger.error("Product %s failed: %s", product.id, exc)
    logger.info("Done: %d/%d succeeded", len(products) - failures, len(products))
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

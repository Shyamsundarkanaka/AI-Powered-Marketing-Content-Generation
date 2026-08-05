"""Seed the database with the initial batch of Radboards products.

Run with: python -m database.seed_products
"""
from __future__ import annotations

import logging
import sqlite3

from database.connection import init_db
from database.repository import create_product

logging.basicConfig(level=logging.INFO)

SEED_PRODUCTS = [
    ("8.5 Off-Road Pro", "https://radboards.in/collections/buy-hoverboards-online-for-kids-for-adults/products/8-5-off-road-pro"),
    ("Classic 6.5 Limited Edition", "https://radboards.in/collections/buy-hoverboards-online-for-kids-for-adults/products/buy-hoverboard-online-classic-6-5-limited-edition"),
    ("Classic 6.5 Lightning Edition", "https://radboards.in/collections/buy-hoverboards-online-for-kids-for-adults/products/buy-hoverboard-online-classic-6-5-lightning-edition"),
    ("Rover Off-Roader XL", "https://radboards.in/collections/professional/products/rover-off-roader-xl"),
    ("Maverick", "https://radboards.in/collections/handle-hoverboard/products/maverick"),
]


def seed() -> None:
    init_db()
    for name, url in SEED_PRODUCTS:
        try:
            product = create_product(name, url)
            print(f"Added product #{product.id}: {product.name}")
        except sqlite3.IntegrityError:
            print(f"Skipped (already exists): {name}")


if __name__ == "__main__":
    seed()

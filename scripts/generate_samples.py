#!/usr/bin/env python3
"""
Generate queries for a few sample Shopify-like products and print a concise preview.
No file is saved—this is for quick manual testing.
"""
from __future__ import annotations

import os
import sys
import asyncio
from typing import List, Dict, Any

# Ensure repo root is on sys.path when running as a script
REPO_ROOT = os.path.dirname(os.path.dirname(__file__))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from app.services.product_adapter import map_shopify_products  # noqa: E402
from app.services.query_generator import generate_queries_for_batch  # noqa: E402
from app.schemas import ProductIn  # noqa: E402
from app.config import settings  # noqa: E402


SAMPLES: List[Dict[str, Any]] = [
    {
        "id": 1,
        "title": "Red Silk Midi Dress",
        "handle": "red-silk-midi-dress",
        "body_html": "<p>Elegant red midi dress made from 100% silk with a flattering A-line silhouette. Ideal for weddings and evening events.</p>",
        "vendor": "AURORA",
        "product_type": "Clothing > Dresses > Midi",
        "tags": ["Silk", "Wedding", "Evening", "Red"],
        "variants": [
            {"price": "129.00"},
            {"price": "139.00"},
        ],
        "options": [
            {"name": "Size", "values": ["XS", "S", "M", "L", "XL"]}
        ],
    },
    {
        "id": 2,
        "title": "Men's Black Leather Biker Jacket",
        "handle": "mens-black-leather-biker-jacket",
        "body_html": "<p>Classic biker jacket crafted from genuine leather. Slim fit with zip fastening and quilted shoulders.</p>",
        "vendor": "URBANRIDE",
        "product_type": "Men > Outerwear > Jackets",
        "tags": ["Leather", "Biker", "Black", "Slim Fit"],
        "variants": [
            {"price": "299.00"}
        ],
        "options": [
            {"name": "Size", "values": ["S", "M", "L"]}
        ],
    },
    {
        "id": 3,
        "title": "Cashmere Crewneck Sweater",
        "handle": "cashmere-crewneck-sweater",
        "body_html": "<p>Soft and warm crewneck sweater spun from certified cashmere. Ribbed trims and relaxed fit.</p>",
        "vendor": "NORDWIND",
        "product_type": "Clothing > Knitwear > Crewneck",
        "tags": ["Cashmere", "Knitwear", "Sweater", "Winter"],
        "variants": [
            {"price": "220.00"},
            {"price": "210.00"}
        ],
        "options": [
            {"name": "Size", "values": ["XS", "S", "M", "L", "XL"]}
        ],
    },
]


def print_preview(products: List[ProductIn], results):
    for p, r in zip(products, results):
        print("\n=== Product ===")
        print("id:", p.id)
        print("title:", p.title)
        if p.price is not None:
            print("price:", p.price)
        if p.size:
            print("size:", p.size)
        if p.vendor:
            print("vendor:", p.vendor)
        if p.product_type:
            print("product_type:", p.product_type)
        if p.tags:
            print("tags:", ", ".join(p.tags))
        print("queries:", len(r.queries))

        for q in r.queries[:10]:
            print(f"- {q.style} -- {q.bucket} -- {q.text}")


async def main():
    settings.concurrency_limit = 1
    products = map_shopify_products(SAMPLES)
    results = await generate_queries_for_batch(products)
    print_preview(products, results)


if __name__ == "__main__":
    asyncio.run(main())

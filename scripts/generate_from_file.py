#!/usr/bin/env python3
"""
Load products from app/data/merged_products_clean.json, adapt them to ProductIn,
run the generator (optionally limited), and print a concise preview of results.

Usage:
  python3 scripts/generate_from_file.py [--limit N]

Notes:
- Requires OPENAI_API_KEY and dependencies installed.
- Uses existing app.config settings; set settings.openai_model, etc., as needed.
"""
from __future__ import annotations

import os
import sys
import argparse
import json
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


def load_products(path: str) -> List[dict]:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("products", [])


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


def build_export_records(products: List[ProductIn], results) -> List[Dict[str, Any]]:
    records: List[Dict[str, Any]] = []
    for p, r in zip(products, results):
        rec: Dict[str, Any] = {
            "id": p.id,
            "title": p.title,
            "description": p.description,
            "price": p.price,
            "material": p.material,
            "size": p.size,
            "rating": p.rating,
            "product_type": p.product_type,
            "vendor": p.vendor,
            "tags": p.tags,
            "queries": [
                {"text": q.text, "style": q.style, "bucket": q.bucket}
                for q in r.queries
            ],
        }
        records.append(rec)
    return records


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--path", default="app/data/merged_products_clean.json", help="Input JSON path")
    parser.add_argument("--limit", type=int, default=2, help="Number of products to process")
    parser.add_argument("--concurrency", type=int, default=1, help="Concurrency limit for generation")
    parser.add_argument(
        "--out",
        default="app/data/generated_queries.json",
        help="Output JSON path for generated queries",
    )
    args = parser.parse_args()

    settings.concurrency_limit = args.concurrency

    raw = load_products(args.path)
    products = map_shopify_products(raw[: args.limit])

    if not products:
        print("No valid products found in input.")
        return

    results = await generate_queries_for_batch(products)

    # Build and save export before printing preview
    export_records = build_export_records(products, results)
    out_dir = os.path.dirname(args.out)
    if out_dir and not os.path.exists(out_dir):
        os.makedirs(out_dir, exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(export_records, f, ensure_ascii=False, indent=2)
    print(f"Saved {len(export_records)} records to {args.out}")

    print_preview(products, results)


if __name__ == "__main__":
    asyncio.run(main())

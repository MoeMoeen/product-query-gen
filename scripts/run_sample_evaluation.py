"""Run a few sample evaluation requests against the live evaluator pipeline.

Requirements:
  - OPENAI_API_KEY set (for unstructured LLM extraction case)
Run:
  uv run python scripts/run_sample_evaluation.py
"""
from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import Dict, Any, List

from httpx import AsyncClient, ASGITransport
from app.main import app

DATA_PATH = Path(__file__).resolve().parents[1] / "app" / "data" / "generated_queries.json"


def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    # Make evaluator modules verbose
    logging.getLogger("evaluator.extract").setLevel(logging.DEBUG)
    logging.getLogger("evaluator.resolve").setLevel(logging.DEBUG)
    logging.getLogger("evaluator.score").setLevel(logging.DEBUG)
    logging.getLogger("evaluator.pipeline").setLevel(logging.DEBUG)


def load_sample_products() -> List[Dict[str, Any]]:
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def pick_query(product: Dict[str, Any], style: str = "natural") -> str:
    for q in product.get("queries", []):
        if q.get("style") == style:
            return q.get("text")
    # fallback to any query text
    return product.get("queries", [{}])[0].get("text", product.get("title", ""))


def build_requests_for_product(prod: Dict[str, Any]) -> List[Dict[str, Any]]:
    pid = str(prod["id"])
    title = prod["title"]
    user_query = pick_query(prod, style="natural")  # richer query

    gt = [{"product_id": pid, "title": title}]  # ground-truth list

    # 1) Correct structured: contains product_id
    req_structured_correct = dict(
        name=f"{pid} | structured_correct",
        payload={
            "query": {"query_id": f"{pid}-sc", "query_text": user_query},
            "ground_truth_products": gt,
            "chatbot_answer": {
                "products": [{"product_id": pid, "title": title}]
            },
        },
        expect=True,
    )

    # 2) Wrong structured: structured, but missing product_id
    req_structured_wrong = dict(
        name=f"{pid} | structured_wrong",
        payload={
            "query": {"query_id": f"{pid}-sw", "query_text": user_query},
            "ground_truth_products": gt,
            "chatbot_answer": {
                "products": [{"title": "Some cozy knit cardigan"}]
            },
        },
        expect=False,
    )

    # 3) Correct unstructured: mentions product id explicitly (LLM should extract it)
    req_unstructured_correct = dict(
        name=f"{pid} | unstructured_correct",
        payload={
            "query": {"query_id": f"{pid}-uc", "query_text": user_query},
            "ground_truth_products": gt,
            "chatbot_answer": {
                "raw_text": (
                    f"Great choice! Recommending the exact match: '{title}'. "
                    f"For precise tracking, note the product id {pid}. "
                    "It’s in stock and ships this week."
                )
            },
        },
        expect=True,
    )

    # 4) Wrong unstructured: talks about something else, with a different id
    req_unstructured_wrong = dict(
        name=f"{pid} | unstructured_wrong",
        payload={
            "query": {"query_id": f"{pid}-uw", "query_text": user_query},
            "ground_truth_products": gt,
            "chatbot_answer": {
                "raw_text": (
                    "Based on your request, here’s a different recommendation: "
                    "Cozy Alpaca Scarf, product id p_fake_001. Customers love it."
                )
            },
        },
        expect=False,
    )

    return [
        req_structured_correct,
        req_structured_wrong,
        req_unstructured_correct,
        req_unstructured_wrong,
    ]


async def main():
    setup_logging()
    products = load_sample_products()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        all_reqs = []
        for prod in products:
            all_reqs.extend(build_requests_for_product(prod))

        print(f"Running {len(all_reqs)} scenarios across {len(products)} products...\n")

        ok = 0
        for r in all_reqs:
            name = r["name"]
            payload = r["payload"]
            expect = r["expect"]

            resp = await client.post("/evaluate/answer", json=payload)
            resp.raise_for_status()
            data = resp.json()
            matched = data.get("matched", False)
            labels = data.get("labels", [])
            details = {k: len(v) for k, v in data.get("details", {}).items()}

            verdict = "PASS" if matched == expect else "FAIL"
            if verdict == "PASS":
                ok += 1

            print(
                f"[{verdict}] {name} -> matched={matched} expect={expect} labels={labels} details={details}"
            )

        print(f"\nSummary: {ok}/{len(all_reqs)} scenarios passed")


if __name__ == "__main__":
    asyncio.run(main())

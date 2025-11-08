"""Run a few sample evaluation requests against the live evaluator pipeline.

Requirements:
  - OPENAI_API_KEY set (for unstructured LLM extraction case)
Run:
  uv run python scripts/run_sample_evaluation.py
"""
from __future__ import annotations

import asyncio
from httpx import AsyncClient
from app.main import app
from app.schemas_eval import (
    EvaluationRequest,
    QueryContext,
    ProductRef,
    ChatbotAnswer,
)


async def main():
    client = AsyncClient(app=app, base_url="http://test")

    # Ground truth products
    gt_red_dress = ProductRef(product_id="p_red", title="Red Silk Dress")
    gt_blue_jeans = ProductRef(product_id="p_jeans", title="Blue Jeans", sku="SKU-BJ-32")

    # 1) Structured success (exact)
    req_structured = EvaluationRequest(
        query=QueryContext(query_id="q1", query_text="red silk dress"),
        ground_truth_products=[gt_red_dress],
        chatbot_answer=ChatbotAnswer(products=[ProductRef(product_id="p_red", title="Red Silk Dress")]),
    )

    # 2) Structured wrong
    req_structured_wrong = EvaluationRequest(
        query=QueryContext(query_id="q2", query_text="red silk dress"),
        ground_truth_products=[gt_red_dress],
        chatbot_answer=ChatbotAnswer(products=[ProductRef(product_id="p_other", title="Blue Cotton Shirt")]),
    )

    # 3) Structured SKU resolution
    req_structured_sku = EvaluationRequest(
        query=QueryContext(query_id="q3", query_text="blue jeans size 32"),
        ground_truth_products=[gt_blue_jeans],
        chatbot_answer=ChatbotAnswer(products=[ProductRef(sku="SKU-BJ-32", title="Blue Jeans 32")]),
    )

    # 4) Unstructured (expects LLM extraction). Provide richer, non-short natural queries inspired by dataset.
    #    We'll include multiple examples to exercise extraction of brand/material/price/occasion/fit.
    natural_queries = [
        # Inspired by cardigan product (material/price/occasion/fit)
        "I'm looking for a warm ribbed cardigan made from a wool and cashmere blend, ideally around $520,"
        " that I can throw on when the weather starts to cool.",
        # Brand-focused narrative
        "Do you carry an Allude cardigan for women in a cozy camel shade with a chunky ribbed finish and a zip front?",
        # Fit-focused request
        "Can you show me cardigans with a chunky ribbed texture available in size small that feel soft and premium?",
        # Jeans product (sku/fit/price)
        "I'm after blue jeans in size 32 with a clean look—nothing distressed—ideally under $250.",
        # Occasion-oriented sweater
        "Do you have a one-shoulder wool-and-cashmere sweater that's soft and stylish for an evening out?",
    ]

    # We'll embed one of these natural strings in the chatbot raw_text for extraction; also include an explicit id mention
    # to ensure we hit the exact-match path for demonstration.
    raw_text_combo = (
        " ".join(natural_queries)
        + " Also, our catalog includes the Red Silk Dress (id: p_red) among other items."
    )

    req_unstructured = EvaluationRequest(
        query=QueryContext(query_id="q4", query_text="help me find options for cool weather outfits"),
        ground_truth_products=[gt_red_dress],
        chatbot_answer=ChatbotAnswer(raw_text=raw_text_combo),
    )

    requests = [
        ("structured_exact", req_structured),
        ("structured_wrong", req_structured_wrong),
        ("structured_sku", req_structured_sku),
        ("unstructured_llm", req_unstructured),
    ]

    for label, req in requests:
        resp = await client.post("/evaluate/answer", json=req.model_dump())
        print(f"=== {label} ===")
        print(resp.json())
        print()

    await client.aclose()


if __name__ == "__main__":
    asyncio.run(main())

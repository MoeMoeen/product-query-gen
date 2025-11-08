"""Prompt templates for evaluation LLM extraction.

M0: Provide stubs. Filled out in M2 with JSON-mode specifics.
"""
from __future__ import annotations

from typing import Optional, List


def extraction_system_prompt() -> str:
    return (
        "You are a product mention extraction engine. Return ONLY valid JSON matching the schema: "
        '{"products":[{"extracted_title":"string","product_id":null,"sku":null,"url":null,'
        '"attrs":{},"confidence":0.0}]}'
    )


def extraction_user_prompt(raw_text: str, query_text: str, hints: Optional[List[str]] = None) -> str:
    hint_block = "" if not hints else "\nHINT_TITLES:\n" + "\n".join(hints)
    return (
        f"QUERY: {query_text}\n"\
        f"ANSWER_TEXT: {raw_text}\n"\
        f"Extract product mentions. Only JSON. {hint_block}"\
    )

"""Candidate extraction logic.

Structured path: pass through ProductRef objects provided in chatbot_answer.products.
Unstructured path: call LLM extractor (JSON-mode) to obtain product mentions.

NOTE: Actual LLM call will be implemented in M2. For M0 scaffolding we provide
an async stub so downstream pipeline wiring compiles.
"""
from __future__ import annotations

import json
import logging
from typing import List, Optional, Dict, Any
from app.schemas_eval import ChatbotAnswer, CandidateRef, QueryContext, Attrs
from app.config import get_openai_async_client, settings
from app.prompts_eval import extraction_system_prompt, extraction_user_prompt


logger = logging.getLogger("evaluator.extract")


async def _call_llm_extractor(raw_text: str, query_text: str, hints: Optional[List[str]] = None) -> str:
    """Call OpenAI in JSON-only mode to extract product mentions.

    Returns raw JSON string. Tests will monkeypatch this function.
    """
    client = get_openai_async_client()
    if client is None:
        raise RuntimeError("OpenAI client not available. Set OPENAI_API_KEY and install openai.")

    sys_prompt = extraction_system_prompt()
    user_prompt = extraction_user_prompt(raw_text, query_text, hints)

    resp = await client.chat.completions.create(
        model=settings.openai_model,
        messages=[
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=settings.eval_temperature,
        response_format={"type": "json_object"},
        max_tokens=settings.openai_max_tokens,
    )
    content = resp.choices[0].message.content or "{}"
    if logger.isEnabledFor(logging.DEBUG):
        logger.debug("LLM raw extraction output: %s", content)
    return content


def _extract_json_block(text: str) -> Optional[str]:
    """Try to find a top-level JSON object in text by brace matching.

    Returns the JSON substring or None.
    """
    start = text.find("{")
    if start == -1:
        return None
    depth = 0
    for i, ch in enumerate(text[start:], start=start):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    return None


def _coerce_float(val: Any, default: float = 0.0) -> float:
    try:
        f = float(val)
        if f < 0.0:
            return 0.0
        if f > 1.0:
            return 1.0
        return f
    except Exception:
        return default


def _parse_candidates_from_json(payload: Dict[str, Any]) -> List[CandidateRef]:
    items = payload.get("products") or []
    out: List[CandidateRef] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        title = item.get("extracted_title") or item.get("title")
        product_id = item.get("product_id")
        sku = item.get("sku")
        url = item.get("url")
        parent_id = item.get("parent_id")
        attrs_obj = item.get("attrs") or {}
        # Minimal validation: must have at least one identifying signal
        if not (title or product_id or sku or url):
            continue
        confidence = _coerce_float(item.get("confidence"), 0.0)
        # Map attrs dict into Attrs model safely
        attrs = Attrs(**{k: v for k, v in attrs_obj.items() if k in Attrs.model_fields})  # type: ignore[attr-defined]
        candidate = CandidateRef(
            product_id=product_id,
            parent_id=parent_id,
            title=title.strip() if isinstance(title, str) else title,
            url=url,
            sku=sku,
            attrs=attrs,
            source="llm_extractor",
            llm_extraction_confidence=confidence,
        )
        # If we extracted a product_id, we treat it as resolved immediately.
        if candidate.product_id and not candidate.resolved_product_id:
            candidate.resolved_product_id = candidate.product_id
        out.append(candidate)
        if len(out) >= settings.max_candidates:
            break
    return out


async def extract_candidates(chatbot_answer: ChatbotAnswer, query: QueryContext) -> List[CandidateRef]:
    """Return candidate products extracted from the chatbot answer.

    For M0: If structured products exist, wrap them; else return empty list (LLM later).
    """
    # Structured path
    if chatbot_answer.products:
        logger.info("extract: structured path with %d products", len(chatbot_answer.products))
        out: List[CandidateRef] = []
        for i, p in enumerate(chatbot_answer.products):
            logger.debug("extract: structured item %d -> id=%s sku=%s url=%s title=%r",
                         i, getattr(p, "product_id", None), getattr(p, "sku", None),
                         getattr(p, "url", None), getattr(p, "title", None))
            out.append(CandidateRef(**p.model_dump(), source="structured"))
        logger.info("extract: structured produced %d candidates", len(out))
        return out

    # Unstructured path
    raw = (chatbot_answer.raw_text or "").strip()
    logger.info("extract: unstructured path, raw_text_len=%d, query_id=%s", len(raw), getattr(query, "query_id", None))
    if not raw:
        logger.warning("extract: empty raw_text; returning no candidates")
        return []

    try:
        llm_raw = await _call_llm_extractor(raw, query.query_text, hints=None)
        logger.debug("extract: llm raw json (truncated 500): %s", str(llm_raw)[:500])

        # llm_raw is expected to be a JSON string; try to extract a top-level JSON block
        payload_str = None
        if isinstance(llm_raw, str):
            payload_str = _extract_json_block(llm_raw) or llm_raw
        else:
            # If the llm client returns a dict-like object already, convert to string/json
            try:
                payload_str = json.dumps(llm_raw)
            except Exception:
                payload_str = None

        if not payload_str:
            logger.warning("extract: LLM extractor returned no payload; returning no candidates")
            return []

        try:
            payload = json.loads(payload_str)
        except Exception as exc:
            logger.exception("extract: failed to parse LLM JSON payload: %s", exc)
            return []

        candidates = _parse_candidates_from_json(payload)
        logger.info("extract: unstructured produced %d candidates", len(candidates))
        for i, c in enumerate(candidates):
            logger.debug("extract: unstructured item %d -> id=%s sku=%s url=%s title=%r conf=%s",
                         i, c.product_id, c.sku, c.url, c.title, getattr(c, "llm_extraction_confidence", None))
        return candidates
    except Exception as e:
        logger.exception("extract: LLM extraction failed: %s", e)
        return []

#app/services/generator.py
"""Service to generate search queries for products using OpenAI."""

from typing import List, Dict, Any
import json
from app.schemas import ProductIn, QueryOut, GeneratedQueriesOut
from app.config import settings, get_openai_async_client, setup_logging
from app import prompts

logger = setup_logging()


def _product_to_prompt_dict(product: ProductIn) -> Dict[str, Any]:
    return {
        "id": product.id,
        "title": product.title,
        "description": product.description,
        "price": product.price,
        "material": product.material,
        "size": product.size,
        "rating": product.rating,
    }


async def generate_queries_for_product(product: ProductIn) -> List[QueryOut]:
    client = get_openai_async_client()
    if client is None:
        raise RuntimeError("OpenAI SDK not available. Ensure 'openai' is installed.")
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is not set in environment.")

    sys_prompt = prompts.system_prompt()
    user_prompt = prompts.user_prompt_for_product(_product_to_prompt_dict(product))

    try:
        resp = await client.chat.completions.create(
            model=settings.openai_model,
            messages=[
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=settings.openai_temperature,
            max_tokens=settings.openai_max_tokens,
        )
    except Exception:
        logger.exception("LLM call failed for product_id=%s", product.id)
        raise

    # Guard against malformed SDK responses
    if not getattr(resp, "choices", None):
        logger.warning("Empty response (no choices) for product_id=%s", product.id)
        return []
    first = resp.choices[0]
    message = getattr(first, "message", None)
    if not message or not getattr(message, "content", None):
        logger.warning("Empty message content for product_id=%s", product.id)
        return []

    content = (message.content or "").strip()
    logger.debug("LLM raw output for product_id=%s: %s", product.id, content)

    # Try to extract JSON
    data: Dict[str, Any]
    try:
        # Content is expected to be minified JSON as instructed
        data = json.loads(content)
    except json.JSONDecodeError:
        # Heuristic: try to find the first and last braces
        start = content.find("{")
        end = content.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                data = json.loads(content[start : end + 1])
            except Exception:
                logger.warning("Failed to parse JSON after brace extraction for product_id=%s", product.id)
                data = {"queries": []}
        else:
            logger.warning("No JSON object found in model output for product_id=%s", product.id)
            data = {"queries": []}

    raw_queries = data.get("queries", [])
    out: List[QueryOut] = []
    for q in raw_queries:
        text = (q.get("text") or "").strip()
        style = (q.get("style") or "").strip() or "short"
        bucket = (q.get("bucket") or "").strip() or "misc"
        if not text:
            continue
        # Constrain style and bucket lightly
        style_norm = "natural" if style.lower().startswith("nat") else "short"
        bucket_norm = prompts.valid_bucket_or_misc(bucket)
        out.append(QueryOut(text=text, style=style_norm, bucket=bucket_norm))

    # Basic dedupe while preserving order
    seen = set()
    deduped: List[QueryOut] = []
    for q in out:
        key = (q.text.lower(), q.style, q.bucket)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(q)

    return deduped


async def generate_queries_for_batch(products: List[ProductIn]) -> List[GeneratedQueriesOut]:
    results: List[GeneratedQueriesOut] = []
    # Sequential for now; could be parallelized with asyncio.gather if needed
    for product in products:
        queries = await generate_queries_for_product(product)
        results.append(GeneratedQueriesOut(product_id=product.id, queries=queries))
    return results

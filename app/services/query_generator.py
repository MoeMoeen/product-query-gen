#app/services/generator.py
"""Service to generate search queries for products using OpenAI."""

from typing import List, Dict, Any
import json
import asyncio
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


async def generate_queries_for_single_product(product: ProductIn) -> List[QueryOut]:
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
            top_p=0.9,
            frequency_penalty=0.3,
            presence_penalty=0.2,
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
        # Constrain style and bucket with whitelist/defaults
        style_l = style.lower()
        style_norm = "natural" if style_l in {"natural", "long"} else "short"
        bucket_norm = prompts.valid_bucket_or_misc(bucket)
        try:
            out.append(QueryOut(text=text, style=style_norm, bucket=bucket_norm))
        except Exception:
            logger.exception("Invalid query item skipped for product_id=%s", product.id)

    # Basic dedupe while preserving order
    seen = set()
    deduped: List[QueryOut] = []
    for q in out:
        key = (q.text.lower(), q.style, q.bucket)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(q)

    # If self-check is enabled, run a second-pass selection/repair
    if settings.llm_self_check:
        try:
            first_json = json.dumps({"queries": [q.model_dump() for q in deduped]}, separators=(",", ":"))
            refine_prompt = prompts.self_check_prompt(_product_to_prompt_dict(product), first_json)
            resp2 = await client.chat.completions.create(
                model=settings.openai_model,
                messages=[
                    {"role": "system", "content": sys_prompt},
                    {"role": "user", "content": refine_prompt},
                ],
                temperature=min(settings.openai_temperature, 0.7),
                max_tokens=settings.openai_max_tokens,
                top_p=0.9,
                frequency_penalty=0.2,
                presence_penalty=0.1,
            )
            if getattr(resp2, "choices", None) and getattr(resp2.choices[0], "message", None):
                content2 = (resp2.choices[0].message.content or "").strip()
                logger.debug("LLM self-check output for product_id=%s: %s", product.id, content2)
                try:
                    data2 = json.loads(content2)
                except json.JSONDecodeError:
                    s = content2.find("{")
                    e = content2.rfind("}")
                    data2 = json.loads(content2[s:e+1]) if s != -1 and e != -1 and e > s else {"queries": []}
                refined: List[QueryOut] = []
                for q in data2.get("queries", []):
                    text = (q.get("text") or "").strip()
                    style = (q.get("style") or "").strip() or "short"
                    bucket = (q.get("bucket") or "").strip() or "misc"
                    if not text:
                        continue
                    style_norm = "natural" if style.lower() in {"natural", "long"} else "short"
                    bucket_norm = prompts.valid_bucket_or_misc(bucket)
                    try:
                        refined.append(QueryOut(text=text, style=style_norm, bucket=bucket_norm))
                    except Exception:
                        logger.exception("Invalid refined query skipped for product_id=%s", product.id)
                # Apply dedupe again and bucket cap (≤2) in case model slips
                seen2 = set()
                capped: Dict[str, int] = {}
                final: List[QueryOut] = []
                for q in refined:
                    key = (q.text.lower(), q.style, q.bucket)
                    if key in seen2:
                        continue
                    if capped.get(q.bucket, 0) >= 2:
                        continue
                    seen2.add(key)
                    capped[q.bucket] = capped.get(q.bucket, 0) + 1
                    final.append(q)
                if final:
                    return final
        except Exception:
            logger.exception("Self-check/selection pass failed for product_id=%s; using first-pass output", product.id)

    return deduped


async def generate_queries_for_batch(products: List[ProductIn]) -> List[GeneratedQueriesOut]:
    """Generate queries for a batch of products with error isolation.

    - If settings.concurrency_limit <= 1, run sequentially.
    - Otherwise, run with asyncio.gather and a semaphore to limit concurrency.
    """
    if not products:
        return []

    async def run_one(p: ProductIn) -> GeneratedQueriesOut:
        try:
            queries = await generate_queries_for_single_product(p)
        except Exception:
            logger.exception("Failed to generate queries for product_id=%s", p.id)
            queries = []
        return GeneratedQueriesOut(product_id=p.id, queries=queries)

    concur_limit = max(1, int(settings.concurrency_limit))
    if concur_limit <= 1:
        # Sequential path
        results: List[GeneratedQueriesOut] = []
        for p in products:
            results.append(await run_one(p))
        return results

    # Concurrent path with semaphore
    sem = asyncio.Semaphore(concur_limit)

    async def limited_run(p: ProductIn) -> GeneratedQueriesOut:
        async with sem:
            return await run_one(p)

    tasks = [limited_run(p) for p in products]
    return await asyncio.gather(*tasks)

"""Adapter to map Shopify-like product dicts into ProductIn schema.

- Strip HTML to compact description text
- Parse price from variants (min available)
- Extract size as comma-joined list from options where name == 'Size'
- Pass through vendor, product_type, tags
- Do NOT set material here; let LLM infer from description/tags/product_type
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional
import re
import html

from app.schemas import ProductIn

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


def _html_to_text(s: Optional[str], max_len: int = 512) -> Optional[str]:
    if not s:
        return None
    # Unescape HTML entities then drop tags
    s = html.unescape(s)
    s = _TAG_RE.sub(" ", s)
    # Normalize whitespace
    s = _WS_RE.sub(" ", s).strip()
    if not s:
        return None
    if len(s) > max_len:
        # Truncate at word boundary if possible
        cut = s.rfind(" ", 0, max_len)
        s = s[: cut if cut > 0 else max_len].rstrip()
    return s


def _parse_price(product: Dict[str, Any]) -> Optional[float]:
    variants = product.get("variants") or []
    prices: List[float] = []
    for v in variants:
        p = v.get("price")
        if p is None:
            continue
        try:
            prices.append(float(p))
        except (TypeError, ValueError):
            continue
    return min(prices) if prices else None


def _extract_size(product: Dict[str, Any]) -> Optional[str]:
    options = product.get("options") or []
    for opt in options:
        name = (opt.get("name") or "").strip().lower()
        if name == "size":
            vals = opt.get("values") or []
            # ensure strings and strip
            cleaned = [str(v).strip() for v in vals if str(v).strip()]
            if cleaned:
                # dedupe preserving order
                seen = set()
                ordered: List[str] = []
                for v in cleaned:
                    if v not in seen:
                        seen.add(v)
                        ordered.append(v)
                return ",".join(ordered)
    return None


def map_shopify_product(p: Dict[str, Any]) -> Optional[ProductIn]:
    # Basic guards
    if not isinstance(p, dict) or not p.get("title") or p.get("id") is None:
        return None

    pid = str(p.get("id"))
    title = str(p.get("title"))
    description = _html_to_text(p.get("body_html"))
    price = _parse_price(p)
    size = _extract_size(p)

    vendor = p.get("vendor") or None
    product_type = p.get("product_type") or None
    tags = p.get("tags") or None
    if isinstance(tags, list):
        tags = [str(t).strip() for t in tags if str(t).strip()]
        if not tags:
            tags = None
    else:
        tags = None

    return ProductIn(
        id=pid,
        title=title,
        description=description,
        price=price,
        size=size,
        material=None,  # let LLM infer
        rating=None,
        vendor=vendor,
        product_type=product_type,
        tags=tags,
    )


def map_shopify_products(products: List[Dict[str, Any]]) -> List[ProductIn]:
    out: List[ProductIn] = []
    for p in products:
        mp = map_shopify_product(p)
        if mp is not None:
            out.append(mp)
    return out

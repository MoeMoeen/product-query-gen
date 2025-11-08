"""Candidate resolution logic (simplified: exact identifiers only).

Resolve candidates by direct identifiers only: product_id, sku, or url.
No semantic or title-based matching.
"""
from __future__ import annotations

from typing import List
import logging
from app.schemas_eval import CandidateRef, ProductRef


logger = logging.getLogger("evaluator.resolve")


async def resolve_candidates(candidates: List[CandidateRef], ground_truth: List[ProductRef]):
    """Resolve candidates to catalog product identifiers.

    M0: If product_id present, keep; else leave unresolved.
    Returns updated list (in-place modifications allowed but we copy for clarity).
    """
    gt_by_sku = {p.sku: p for p in ground_truth if getattr(p, "sku", None)}
    gt_by_url = {p.url: p for p in ground_truth if getattr(p, "url", None)}
    # Title normalization removed in simplified mode (no title matching)

    resolved: List[CandidateRef] = []
    c_id = c_sku = c_url = 0

    for c in candidates:
        # Direct by product_id
        if c.product_id:
            c.resolved_product_id = c.product_id
            c_id += 1
        # Fallback direct by SKU
        elif c.sku and c.sku in gt_by_sku:
            c.resolved_product_id = gt_by_sku[c.sku].product_id
            c_sku += 1
        # Fallback direct by URL
        elif c.url and c.url in gt_by_url:
            c.resolved_product_id = gt_by_url[c.url].product_id
            c_url += 1
        resolved.append(c)
    logger.info("resolve: %d by id, %d by sku, %d by url; total candidates=%d", c_id, c_sku, c_url, len(candidates))
    return resolved

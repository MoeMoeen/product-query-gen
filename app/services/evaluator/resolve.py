"""Candidate resolution logic (simplified: exact identifiers only).

Resolve candidates by direct identifiers only: product_id, sku, or url.
No semantic or title-based matching.
"""
from __future__ import annotations

from typing import List
from app.schemas_eval import CandidateRef, ProductRef


async def resolve_candidates(candidates: List[CandidateRef], ground_truth: List[ProductRef]):
    """Resolve candidates to catalog product identifiers.

    M0: If product_id present, keep; else leave unresolved.
    Returns updated list (in-place modifications allowed but we copy for clarity).
    """
    gt_by_sku = {p.sku: p for p in ground_truth if getattr(p, "sku", None)}
    gt_by_url = {p.url: p for p in ground_truth if getattr(p, "url", None)}
    # Title normalization removed in simplified mode (no title matching)

    resolved: List[CandidateRef] = []

    for c in candidates:
        # Direct by product_id
        if c.product_id:
            c.resolved_product_id = c.product_id
        # Fallback direct by SKU
        elif c.sku and c.sku in gt_by_sku:
            c.resolved_product_id = gt_by_sku[c.sku].product_id
        # Fallback direct by URL
        elif c.url and c.url in gt_by_url:
            c.resolved_product_id = gt_by_url[c.url].product_id
        resolved.append(c)
    return resolved

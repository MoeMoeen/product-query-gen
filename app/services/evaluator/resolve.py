"""Candidate resolution logic (simplified: exact identifiers only).

Resolve candidates by direct identifiers only: product_id, sku, or url.
No semantic or title-based matching.
"""
from __future__ import annotations

from typing import List
import logging
from app.schemas_eval import CandidateRef, ProductRef


logger = logging.getLogger("evaluator.resolve")


async def resolve_candidates(candidates: List[CandidateRef], ground_truth: List[ProductRef]) -> List[CandidateRef]:
    gt_ids = {p.product_id for p in ground_truth if p.product_id}
    gt_sku_to_id = {p.sku: p.product_id for p in ground_truth if p.sku and p.product_id}
    gt_url_to_id = {p.url: p.product_id for p in ground_truth if p.url and p.product_id}

    logger.info("resolve: %d candidates, gt_ids=%s", len(candidates), list(gt_ids))

    for i, c in enumerate(candidates):
        if c.product_id:
            c.resolved_product_id = c.product_id
            logger.debug("resolve: [%d] via product_id -> %s", i, c.resolved_product_id)
            continue
        if c.sku and c.sku in gt_sku_to_id:
            c.resolved_product_id = gt_sku_to_id[c.sku]
            logger.debug("resolve: [%d] via sku %s -> %s", i, c.sku, c.resolved_product_id)
            continue
        if c.url and c.url in gt_url_to_id:
            c.resolved_product_id = gt_url_to_id[c.url]
            logger.debug("resolve: [%d] via url %s -> %s", i, c.url, c.resolved_product_id)
            continue
        logger.debug("resolve: [%d] unresolved (no id/sku/url match)", i)

    return candidates

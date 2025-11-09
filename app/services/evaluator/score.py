"""Simplified scoring logic.

Only distinguishes exact matches (resolved_product_id in ground_truth) vs wrong.
Variant, semantic, and composite scoring removed per rollback to M2 scope.
"""
from __future__ import annotations

from typing import List
import logging
from app.schemas_eval import CandidateRef, ProductRef, MatchDetail



logger = logging.getLogger("evaluator.score")


async def score_candidates(candidates: List[CandidateRef], ground_truth: List[ProductRef]) -> List[MatchDetail]:
    gt_ids = {p.product_id for p in ground_truth if p.product_id}
    out: List[MatchDetail] = []
    logger.info("score: evaluating %d candidates against %d gt ids", len(candidates), len(gt_ids))

    for i, c in enumerate(candidates):
        label = "exact_match" if (c.resolved_product_id and c.resolved_product_id in gt_ids) else "wrong"
        logger.debug("score: [%d] resolved_id=%s -> label=%s", i, c.resolved_product_id, label)
        out.append(MatchDetail(candidate=c, label=label, score=0.0, reasons=[]))

    return out

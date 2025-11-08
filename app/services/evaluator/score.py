"""Simplified scoring logic.

Only distinguishes exact matches (resolved_product_id in ground_truth) vs wrong.
Variant, semantic, and composite scoring removed per rollback to M2 scope.
"""
from __future__ import annotations

from typing import List
from app.schemas_eval import CandidateRef, ProductRef, MatchDetail



async def score_candidates(candidates: List[CandidateRef], ground_truth: List[ProductRef]) -> List[MatchDetail]:
    """Assign labels and scores to candidates based on ground-truth.

    M0 logic:
    - exact_match if candidate.resolved_product_id matches any ground_truth.product_id
    - else wrong (score 0.0)
    """
    gt_ids = {p.product_id for p in ground_truth if p.product_id}
    details: List[MatchDetail] = []
    for c in candidates:
        label = "wrong"
        score = 0.0
        reasons: List[str] = []
        if c.resolved_product_id and c.resolved_product_id in gt_ids:
            label = "exact_match"
            score = 1.0
            reasons.append("exact id match")
        details.append(MatchDetail(candidate=c, label=label, score=score, reasons=reasons))
    return details

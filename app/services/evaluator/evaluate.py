"""
Orchestration for evaluation pipeline. Takes an EvaluationRequest and returns an EvaluationResult.
"""
from __future__ import annotations

from typing import List, Dict
import logging

from app.schemas_eval import (
    EvaluationRequest,
    EvaluationResult,
    MatchDetail,
)
from .extract import extract_candidates
from .resolve import resolve_candidates
from .score import score_candidates


logger = logging.getLogger("evaluator.pipeline")


async def evaluate_one(req: EvaluationRequest) -> EvaluationResult:
    """Evaluate a single chatbot answer against ground-truth products."""

    logger.info("pipeline: starting evaluation")
    candidates = await extract_candidates(req.chatbot_answer, req.query)
    logger.info("pipeline: extracted %d candidates", len(candidates))
    candidates = await resolve_candidates(candidates, req.ground_truth_products)
    details = await score_candidates(candidates, req.ground_truth_products)

    # Group details by label
    by_label: Dict[str, List[MatchDetail]] = {}
    for match_detail in details:
        by_label.setdefault(match_detail.label, []).append(match_detail)

    labels = list(by_label.keys())
    # Simplified: matched is true if any exact_match exists
    matched = any(d.label == "exact_match" for d in details)
    logger.info("pipeline: matched=%s labels=%s", matched, labels)
    return EvaluationResult(
        query=req.query,
        labels=labels,
        matched=matched,
        details=by_label,
        explanations=[],
    )


# Batch evaluation removed per simplified scope

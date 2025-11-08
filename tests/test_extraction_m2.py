import json
import pytest
from app.schemas_eval import (
    ProductRef,
    ChatbotAnswer,
    QueryContext,
    EvaluationRequest,
)
from app.services.evaluator import evaluate_one

# Monkeypatch target imported in extract module
import app.services.evaluator.extract as extract_mod


@pytest.mark.asyncio
async def test_llm_malformed_json_recovery(monkeypatch):
    # Simulate malformed JSON with trailing text
    raw_response = '{"products":[{"extracted_title":"Red Silk Dress","confidence":0.93}]} EXTRA STUFF'

    async def fake_call_llm(raw_text: str, query_text: str, hints=None):  # type: ignore
        return raw_response

    monkeypatch.setattr(extract_mod, "_call_llm_extractor", fake_call_llm)

    req = EvaluationRequest(
        query=QueryContext(query_id="q_malformed", query_text="red silk dress"),
        ground_truth_products=[ProductRef(product_id="p1", title="Red Silk Dress")],
        chatbot_answer=ChatbotAnswer(raw_text="We have a Red Silk Dress for you."),
    )
    result = await evaluate_one(req)
    # With simplified exact-only logic, title-only extraction won't resolve → matched False
    assert result.matched is False
    # Ensure candidate was parsed from LLM output (appears under 'wrong')
    llm_wrong = [d for d in result.details.get("wrong", []) if d.candidate.source == "llm_extractor"]
    assert llm_wrong, "Expected at least one LLM extracted candidate in wrong group"


@pytest.mark.asyncio
async def test_llm_confidence_capture(monkeypatch):
    raw_response = json.dumps({
        "products": [
            {"extracted_title": "Blue Jeans", "confidence": 0.77, "sku": "SKU-XYZ"},
            {"extracted_title": "Green Hat", "confidence": 1.2},  # coerced to 1.0
        ]
    })

    async def fake_call_llm(raw_text: str, query_text: str, hints=None):  # type: ignore
        return raw_response

    monkeypatch.setattr(extract_mod, "_call_llm_extractor", fake_call_llm)

    req = EvaluationRequest(
        query=QueryContext(query_id="q_conf", query_text="blue jeans"),
        ground_truth_products=[ProductRef(product_id="p2", title="Blue Jeans", sku="SKU-XYZ")],
        chatbot_answer=ChatbotAnswer(raw_text="Our Blue Jeans and Green Hat are popular."),
    )
    result = await evaluate_one(req)
    # Confidence values captured
    all_candidates = [d.candidate for group in result.details.values() for d in group]
    jeans = next(c for c in all_candidates if c.title == "Blue Jeans")
    assert jeans.llm_extraction_confidence is not None and abs(jeans.llm_extraction_confidence - 0.77) < 1e-6
    hat = next(c for c in all_candidates if c.title == "Green Hat")
    assert hat.llm_extraction_confidence == 1.0  # clipped


@pytest.mark.asyncio
async def test_llm_no_valid_json(monkeypatch):
    async def fake_call_llm(raw_text: str, query_text: str, hints=None):  # type: ignore
        return "TOTALLY INVALID"

    monkeypatch.setattr(extract_mod, "_call_llm_extractor", fake_call_llm)

    req = EvaluationRequest(
        query=QueryContext(query_id="q_invalid", query_text="black tshirt"),
        ground_truth_products=[ProductRef(product_id="p3", title="Black T-Shirt")],
        chatbot_answer=ChatbotAnswer(raw_text="Mention of product but broken output"),
    )
    result = await evaluate_one(req)
    # Should not crash; likely wrong label only; matched False
    assert result.matched is False
    # No llm_extractor candidates
    assert not any(d.candidate.source == "llm_extractor" for group in result.details.values() for d in group)

import pytest
from app.schemas_eval import (
    Attrs,
    ProductRef,
    ChatbotAnswer,
    QueryContext,
    EvaluationRequest,
)
from app.services.evaluator import evaluate_one


@pytest.mark.asyncio
async def test_extraction_structured_passthrough_and_exact():
    gt = [
        ProductRef(product_id="p1", title="Red Silk Dress", attrs=Attrs(material="silk", size="M", price=199.99), parent_id="parent-1"),
    ]
    answer = ChatbotAnswer(products=[
        ProductRef(product_id="p1", title=" Red Silk Dress "),
    ])
    req = EvaluationRequest(
        query=QueryContext(query_id="q1", query_text="Do you have a red silk dress?"),
        ground_truth_products=gt,
        chatbot_answer=answer,
        top_k=3,
    )
    result = await evaluate_one(req)
    assert result.matched is True
    assert "exact_match" in result.labels
    # Metrics removed in simplified mode


@pytest.mark.asyncio
async def test_resolution_by_sku_to_exact():
    gt = [
        ProductRef(product_id="p2", parent_id="parent-2", title="Blue Jeans", attrs=Attrs(size="32")),
    ]
    # No product_id in candidate; use SKU to resolve; parent_id implies variant
    answer = ChatbotAnswer(products=[
        ProductRef(sku="SKU-123", parent_id="parent-2", title="Blue Jeans 32"),
    ])
    # Ground truth includes SKU mapping via same item
    gt[0].sku = "SKU-123"

    req = EvaluationRequest(
        query=QueryContext(query_id="q2", query_text="blue jeans 32"),
        ground_truth_products=gt,
        chatbot_answer=answer,
    )
    result = await evaluate_one(req)
    assert result.matched is True
    assert "exact_match" in result.labels


@pytest.mark.asyncio
async def test_wrong_label_and_metrics():
    gt = [ProductRef(product_id="p3", title="Black T-Shirt", parent_id="parent-3")]
    answer = ChatbotAnswer(products=[ProductRef(product_id="p999", title="Green Hat")])
    req = EvaluationRequest(
        query=QueryContext(query_id="q3", query_text="black tshirt"),
        ground_truth_products=gt,
        chatbot_answer=answer,
    )
    result = await evaluate_one(req)
    assert result.matched is False
    assert "wrong" in result.labels



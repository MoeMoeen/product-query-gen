from __future__ import annotations

from pydantic import BaseModel, Field
from typing import List, Optional, Dict


class Attrs(BaseModel):
    brand: Optional[str] = None
    material: Optional[str] = None
    size: Optional[str] = None
    price: Optional[float] = None
    rating: Optional[float] = None
    color: Optional[str] = None


class ProductRef(BaseModel):
    product_id: Optional[str] = None
    parent_id: Optional[str] = None
    title: Optional[str] = None
    url: Optional[str] = None
    sku: Optional[str] = None
    attrs: Attrs = Attrs()


class ChatbotAnswer(BaseModel):
    products: Optional[List[ProductRef]] = None  # structured
    raw_text: Optional[str] = None  # unstructured


class QueryContext(BaseModel):
    query_id: str
    query_text: str


class CatalogContext(BaseModel):
    variants: Optional[List[ProductRef]] = None


class EvaluationRequest(BaseModel):
    query: QueryContext
    ground_truth_products: List[ProductRef]
    chatbot_answer: ChatbotAnswer
    catalog_context: Optional[CatalogContext] = None


class CandidateRef(ProductRef):
    source: str = Field(..., description="structured|llm_extractor")
    llm_extraction_confidence: Optional[float] = None
    resolved_product_id: Optional[str] = None


class MatchDetail(BaseModel):
    candidate: CandidateRef
    label: str  # exact_match|variant_match|close_match|wrong|empty
    score: float
    reasons: List[str]


class EvaluationResult(BaseModel):
    query: QueryContext
    labels: List[str]
    matched: bool
    details: Dict[str, List[MatchDetail]]
    explanations: List[str]

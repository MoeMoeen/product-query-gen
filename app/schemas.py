from pydantic import BaseModel
from typing import List, Optional, Dict, Any

class ProductIn(BaseModel):
    id: str
    title: str
    description: Optional[str] = None
    price: Optional[float] = None
    material: Optional[str] = None
    size: Optional[str] = None
    rating: Optional[float] = None
    # Optional context fields to enrich prompting
    product_type: Optional[str] = None
    vendor: Optional[str] = None
    tags: Optional[List[str]] = None

class ProductsIn(BaseModel):
    products: List[ProductIn]


class QueryOut(BaseModel):
    text: str
    style: str   # "short" | "natural"
    bucket: str  # e.g. "price", "occasion"

class GeneratedQueriesOut(BaseModel):
    product_id: str
    queries: List[QueryOut]

class GeneratedQueriesBatchOut(BaseModel):
    results: List[GeneratedQueriesOut]


class ShopifyProductsIn(BaseModel):
    """Accepts raw Shopify-like product objects (dicts)."""
    products: List[Dict[str, Any]]

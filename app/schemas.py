from pydantic import BaseModel
from typing import List, Optional

class ProductIn(BaseModel):
    id: str
    title: str
    description: Optional[str] = None
    price: Optional[float] = None
    material: Optional[str] = None
    size: Optional[str] = None
    rating: Optional[float] = None

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

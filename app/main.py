from fastapi import FastAPI
from app.config import settings
from app.schemas import ProductsIn, GeneratedQueriesBatchOut
from app.services.query_generator import generate_queries_for_batch

app = FastAPI(
    title=settings.project_name,
    version=settings.version,
)

@app.post("/generate", response_model=GeneratedQueriesBatchOut)
async def generate_batch(payload: ProductsIn):
    """
    Accepts a list of products and returns generated queries for each product.
    """
    results = await generate_queries_for_batch(payload.products)
    return GeneratedQueriesBatchOut(results=results)

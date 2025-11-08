from fastapi import FastAPI
from app.config import settings
from app.schemas import ProductsIn, GeneratedQueriesBatchOut, ShopifyProductsIn
from app.services.query_generator import generate_queries_for_batch
from app.services.product_adapter import map_shopify_products
from fastapi import APIRouter
from app.schemas_eval import (
    EvaluationRequest,
    EvaluationResult,
)
from app.services.evaluator import evaluate_one

app = FastAPI(
    title=settings.project_name,
    version=settings.version,
)


# Existing query generation endpoints

@app.post("/generate", response_model=GeneratedQueriesBatchOut)
async def generate_batch(payload: ProductsIn):
    """
    Accepts a list of products and returns generated queries for each product.
    """
    results = await generate_queries_for_batch(payload.products)
    return GeneratedQueriesBatchOut(results=results)


@app.post("/generate/shopify", response_model=GeneratedQueriesBatchOut)
async def generate_batch_shopify(payload: ShopifyProductsIn):
    """
    Accepts Shopify-like product objects, adapts them into ProductIn, and returns generated queries.
    """
    products = map_shopify_products(payload.products)
    results = await generate_queries_for_batch(products)
    return GeneratedQueriesBatchOut(results=results)


# Evaluation router (mounted inline for simplicity; could be separate module)
eval_router = APIRouter(prefix="/evaluate", tags=["evaluation"])


@eval_router.post("/answer", response_model=EvaluationResult)
async def evaluate_answer(payload: EvaluationRequest):
    return await evaluate_one(payload)


app.include_router(eval_router)

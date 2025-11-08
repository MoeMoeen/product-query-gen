### Evaluation Micro-Service:

**What this microservice does (in plain terms)**

Given:

The original query our generator produced, a ground-truth product set (the product(s) a query was truly about), and a chatbot’s answer (which may include product recommendations/results), the service parses the chatbot output, resolves product(s) mentioned there, and decides whether the chatbot included the correct product(s). It then reports matches, near-matches, misses, and basic metrics (precision/recall, etc.).

* ✅ **Inputs:**

  1. the **original query** (the one our generator produced),
  2. the **ground-truth product set** the query was generated for,
  3. the **chatbot’s response** (structured or unstructured).

* ✅ **Extraction policy:**

  * **Structured chatbot output →** deterministic resolution (rules).
  * **Unstructured chatbot output →** **LLM-based extraction only** (no regex/cheap heuristics).
  * In **both** paths we add **semantic scoring** (embeddings) in the matcher.

---

# Microservice: Answer Evaluator

## 1) High-level pipeline

1. **Input ingest**

   * `query_context`: `query_id`, `query_text`.
   * `ground_truth_products`: one or more `ProductRef` (the intended product(s)).
   * `chatbot_answer`: either `products=[...]` (structured) **or** `raw_text="..."` (unstructured).

2. **Candidate extraction**

   * **Structured:** trust schema → normalize → `CandidateRef[]`.
   * **Unstructured:** call **LLM extractor** → returns `CandidateRef[]` with `llm_extraction_confidence` (0–1).

     * We’ll use JSON-schema (function-calling) to force structure.

3. **Resolution to catalog**

   * For each `CandidateRef`, resolve to a **catalog product** (by `product_id/sku/url/slug`; fallback title+brand+material via semantic nearest-neighbor if needed).

4. **Matching & scoring (hybrid = rules + semantic)**

   * **Exact:** same `product_id` ∈ ground truth.
   * **Variant:** same `parent_id` (same canonical product, different size/color).
   * **Semantic close:** cosine(emb(cand.title), emb(gt.title)) plus attribute agreements (brand/material/size, price closeness).
   * Compute a **composite score** and assign a label: `exact_match | variant_match | close_match | wrong`.

5. **Evaluation metrics**

   * Per query: TP/FP/FN, precision/recall/F1, success@k, coverage, and an **explanations[]** list (human-readable).

---

## 2) Data contracts (Pydantic)

```python
# app/schemas_eval.py
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

class Attrs(BaseModel):
    brand: Optional[str] = None
    material: Optional[str] = None
    size: Optional[str] = None
    price: Optional[float] = None
    rating: Optional[float] = None
    color: Optional[str] = None
    # extend as needed

class ProductRef(BaseModel):
    product_id: Optional[str] = None       # may be absent in unstructured
    parent_id: Optional[str] = None        # canonical parent (variant grouping)
    title: Optional[str] = None
    url: Optional[str] = None
    sku: Optional[str] = None
    attrs: Attrs = Attrs()

class ChatbotAnswer(BaseModel):
    products: Optional[List[ProductRef]] = None  # structured
    raw_text: Optional[str] = None               # unstructured

class QueryContext(BaseModel):
    query_id: str
    query_text: str

class CatalogContext(BaseModel):
    # Optional helpers (e.g., variant map) to improve matching
    variants: Optional[List[ProductRef]] = None

class EvaluationRequest(BaseModel):
    query: QueryContext
    ground_truth_products: List[ProductRef]
    chatbot_answer: ChatbotAnswer
    catalog_context: Optional[CatalogContext] = None
    top_k: int = 3

class CandidateRef(ProductRef):
    source: str = Field(..., description="structured|llm_extractor")
    llm_extraction_confidence: Optional[float] = None
    resolved_product_id: Optional[str] = None  # after catalog resolution

class MatchDetail(BaseModel):
    candidate: CandidateRef
    label: str  # exact_match|variant_match|close_match|wrong|empty
    score: float
    reasons: List[str]

class EvaluationResult(BaseModel):
    query: QueryContext
    labels: List[str]                       # aggregated labels present
    matched: bool                           # did we include any correct product?
    details: Dict[str, List[MatchDetail]]   # by label
    metrics: Dict[str, Any]                 # precision, recall, f1, success@k
    explanations: List[str]

class EvaluationBatchRequest(BaseModel):
    items: List[EvaluationRequest]

class EvaluationBatchResult(BaseModel):
    results: List[EvaluationResult]
    aggregate: Dict[str, Any]  # macro/micro metrics
```

---

## 3) Endpoints (FastAPI)

```python
# app/main_eval.py (or fold into main.py under /evaluate)
from fastapi import APIRouter
from app.schemas_eval import (
    EvaluationRequest, EvaluationResult,
    EvaluationBatchRequest, EvaluationBatchResult
)
from app.services.evaluator import evaluate_one, evaluate_batch

router = APIRouter(prefix="/evaluate", tags=["evaluation"])

@router.post("/answer", response_model=EvaluationResult)
async def evaluate_answer(payload: EvaluationRequest):
    return await evaluate_one(payload)

@router.post("/batch", response_model=EvaluationBatchResult)
async def evaluate_batch_answers(payload: EvaluationBatchRequest):
    return await evaluate_batch(payload)
```

---

## 4) Service layout

```
app/
  services/
    evaluator/
      __init__.py
      extract.py      # structured passthrough + LLM extractor (unstructured)
      resolve.py      # resolve CandidateRef -> catalog product_id/parent_id
      score.py        # composite score (rules + semantic)
      evaluate.py     # orchestrates: extract -> resolve -> match -> metrics
```

### 4.1 Extraction

* **Structured:**

  * If `chatbot_answer.products` exists → normalize (lowercase titles, trim), wrap into `CandidateRef(source="structured")`.

* **Unstructured (LLM-only):**

  * Call **LLM extractor** with a strict JSON schema (function calling / json_mode).
  * Output: `[{title?, product_id?, url?, sku?, attrs?, confidence}]`
  * Convert to `CandidateRef(source="llm_extractor", llm_extraction_confidence=…)`.

**LLM extractor prompt (sketch):**

* System: “Extract product mentions from the text and return **only JSON** matching this schema.”
* User: include `raw_text` and, if helpful, a set of **catalog titles/brands** as hints (optional).
* Response format: `{"products":[{...}]}` (we’ll enforce with JSON mode).

### 4.2 Resolution

* If `product_id/sku/url` present → resolve directly.
* Else: (title, brand, material)

  * Compute **embedding** for candidate title.
  * Search **catalog embeddings** (precomputed) → nearest neighbor top-k.
  * Pick top candidate above threshold → set `resolved_product_id`.
  * Keep the NN score for later.

### 4.3 Scoring (rules + semantic)

For each candidate (resolved to a catalog product):

* **Rules:**

  * if `resolved_product_id ∈ ground_truth_ids` → `exact_match`, score = 1.00
  * elif `resolved_parent_id ∈ ground_truth_parent_ids` → `variant_match`, score = 0.90
* **Semantic agreement:**

  * `title_sim = cosine(emb(cand_title), emb(gt_title_max))`
  * `brand_match = 1 if same else 0`
  * `material_match = 1 if same else 0`
  * `size_match = 1 if same else 0`
  * `price_ok = 1 if |cand.price - gt.price| / gt.price <= 0.1 else 0`
  * composite:

    ```
    sem_score = 0.55*title_sim + 0.10*brand_match + 0.10*material_match \
                + 0.10*size_match + 0.15*price_ok
    ```
* **Labeling thresholds (when not exact/variant):**

  * if `sem_score >= 0.80` → `close_match`
  * else → `wrong`
* Attach `reasons`: short bullet points explaining which signals fired.

### 4.4 Metrics

* Let `GT` = ground-truth set, `P` = predicted included set (exact+variant+close).
* **TP** = `P ∩ GT`, **FP** = `P − GT`, **FN** = `GT − P`.
* Precision/Recall/F1; **success@k** if we treat top-k candidates from chatbot.
* `matched = (len(TP) > 0)` (or stricter if required).

---

## 5) Embeddings (semantic)

* Use OpenAI `text-embedding-3-small` (cheap & decent) for:

  * **Candidate titles**
  * **Ground-truth titles**
  * **Catalog titles** (precompute + store vector index for fast NN, e.g., FAISS later)

* Compute cosine similarity for `title_sim`.

* Keep everything pluggable; if you swap models, scoring stays.

---

## 6) Minimal implementation order

1. **Schemas & endpoints** (`/evaluate/answer`, `/evaluate/batch`)
2. **Structured path** (no LLM): normalize → resolve (by id/sku/url) → score → metrics.
3. **LLM extractor** (unstructured path) with JSON-schema output.
4. **Embeddings** for semantic score (inline first; FAISS later).
5. **Catalog resolver**: add embedding NN fallback when `product_id` is absent.
6. **Batch aggregation metrics**.

---

## 7) Example request/response (unstructured)

**Request**

```json
{
  "query": {"query_id":"q42","query_text":"Do you have a red silk dress in size M under $200?"},
  "ground_truth_products": [
    {"product_id":"p1","parent_id":"red-silk-123","title":"Red Silk Dress","attrs":{"material":"silk","size":"M","price":199.99}}
  ],
  "chatbot_answer": {
    "raw_text": "We recommend our Red Silk Dress in size M for $199.99, or the Burgundy Satin Dress."
  }
}
```

**Response (abridged)**

```json
{
  "query":{"query_id":"q42","query_text":"Do you have a red silk dress in size M under $200?"},
  "matched": true,
  "labels":["exact_match","wrong"],
  "details":{
    "exact_match":[{"candidate":{"title":"Red Silk Dress","source":"llm_extractor","resolved_product_id":"p1"},"label":"exact_match","score":1.0,"reasons":["exact id match"]}],
    "wrong":[{"candidate":{"title":"Burgundy Satin Dress","source":"llm_extractor"},"label":"wrong","score":0.31,"reasons":["material mismatch","low title similarity"]}]
  },
  "metrics":{"precision":0.5,"recall":1.0,"f1":0.6667,"success_at_k":{"k":3,"success":true}},
  "explanations":["p1 exactly matches ground-truth; satin candidate differs in material/color."]
}
```

---

## 8) Where things live (keeping your project tidy)

```
app/
  main.py                # add router.include_router(evaluate.router)
  schemas_eval.py
  services/
    evaluator/
      evaluate.py        # evaluate_one / evaluate_batch
      extract.py         # structured passthrough + LLM extractor (JSON schema)
      resolve.py         # id/url/sku → product; semantic NN fallback
      score.py           # rules + semantic composite, labels, metrics
  prompts_eval.py        # LLM extractor prompt(s)
```

---


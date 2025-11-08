# Evaluation Microservice — Implementation Plan & Checklist

Purpose
- Evaluate chatbot answers against ground-truth products for a generated query.
- (Rolled-back scope) Output only presence/absence of exact ground-truth products; advanced labels and metrics deferred.

Status
- [x] Design doc (docs/Eval_service.md)
- [x] Implementation scaffold (schemas, router, services)
- [x] Structured-path evaluation (no LLM)
- [x] Unstructured extraction (LLM)
- [ ] Embedding-based resolution/scoring (rolled back)
- [ ] Batch endpoints + aggregation (deferred)
- [x] Tests (current exact-match scope)
- [ ] README update

Milestones
1) M0 — Scaffolding (Day 0)
  - [x] Schemas file: app/schemas_eval.py
  - [x] Router: /evaluate endpoints
  - [x] Service package: app/services/evaluator/{extract,resolve,score,evaluate}.py
  - [x] Prompts: app/prompts_eval.py
  - [x] Settings: add embedding model + eval params in app/config.py

2) M1 — Structured Answer Path (Deterministic) (Day 0–1)
  - [x] Passthrough candidates from structured products
  - [x] Direct resolution by product_id/sku/url
  - [x] Rule-based labels (exact/variant) + minimal metrics
  - [x] Basic unit tests

3) M2 — LLM Extraction for Unstructured (Day 1–2)
  - [x] JSON-only extractor (chat.completions/json mode)
  - [x] Robust JSON parsing (brace fallback, logging raw output at DEBUG)
  - [x] Per-item validation & confidence capture
  - [x] Unit tests with mocked LLM

4) M3 — Semantic Resolution & Scoring (Deferred / Rolled Back)
  - [ ] (All semantic features paused; will reintroduce later with revised requirements.)

5) M4 — Batch + Aggregation (Day 2)
   - [ ] POST /evaluate/batch
   - [ ] Macro/micro metrics (precision/recall/F1)
   - [ ] success@k (k list configurable)
   - [ ] Integration tests

6) M5 — Docs & Operationalization (Day 2)
   - [ ] README: usage examples, envs, limits
   - [ ] Log fields: hit rates, extraction errors, parse failures
   - [ ] Env flags documented

APIs (planned)
- POST /evaluate/answer → EvaluationResult
- POST /evaluate/batch → EvaluationBatchResult

Schemas (new: app/schemas_eval.py)
- Attrs {brand, material, size, price, rating, color?}
- ProductRef {product_id?, parent_id?, title?, url?, sku?, attrs}
- ChatbotAnswer {products?[], raw_text?}
- QueryContext {query_id, query_text}
- CatalogContext {variants?[]}
- EvaluationRequest {query, ground_truth_products[], chatbot_answer, catalog_context?, top_k}
- CandidateRef (extends ProductRef) {source: structured|llm_extractor, llm_extraction_confidence?, resolved_product_id?, resolved_parent_id?}
- MatchDetail {candidate, label: exact_match|variant_match|close_match|wrong|empty, score, reasons[]}
- EvaluationResult {query, labels[], matched, details{label->[]}, metrics{}, explanations[]}
- EvaluationBatchRequest {items[]}
- EvaluationBatchResult {results[], aggregate{}}

Services (app/services/evaluator/)
- extract.py
  - extract_candidates(answer, query) -> List[CandidateRef]
  - Structured passthrough; Unstructured → LLM extractor
- resolve.py
  - resolve_candidates(candidates, ground_truth, catalog_ctx?) -> List[CandidateRef]
  - ID/URL/SKU direct; else embeddings NN to nearest ground-truth/catalog
- score.py
  - score_candidate(candidate, ground_truth_set) -> MatchDetail
  - Composite: 0.55*title_sim + 0.10*brand + 0.10*material + 0.10*size + 0.15*price_ok
  - Thresholds: close ≥ 0.80; price tolerance ≤ 12%
- evaluate.py
  - evaluate_one(req) → EvaluationResult
  - Pipeline: extract → resolve → score → order (label priority, score desc) → metrics
- metrics.py
  - aggregate(details, gt_count, top_k_list) → precision/recall/f1, success@k

Prompts (app/prompts_eval.py)
- extraction_system_prompt()
- extraction_user_prompt(raw_text, query_text, hints?) → JSON-only:
  {"products":[{"extracted_title":"...", "product_id":null, "sku":null, "url":null, "attrs":{...}, "confidence":0.0-1.0}]}

Config (app/config.py)
- EMBEDDING_MODEL=text-embedding-3-small
- EVAL_TEMPERATURE=0.2
- TITLE_SIM_THRESHOLD=0.82
- CLOSE_THRESHOLD=0.80
- PRICE_TOLERANCE_PCT=0.12
- MAX_CANDIDATES=10
- LOG_LEVEL honored (DEBUG logs raw LLM extraction)

Quality Gates
- JSON parse resilience; no crashes on malformed extraction.
- Deterministic behavior when structured input present.
- Unit tests for each module; integration test per endpoint.
- No secrets logged; redact raw text on WARN/ERROR.

Test Plan (pytest)
- test_extraction_structured_passthrough
- test_extraction_llm_malformed_json
- test_resolution_direct_id
- test_resolution_embedding_match
- test_scoring_labels_variants
- test_metrics_success_at_k
- test_evaluate_one_structured_and_unstructured
- test_batch_macro_micro

Operational Notes
- Rate limits: batch embeddings where possible.
- Timeouts: per LLM call and per request guard.
- Concurrency: reuse existing app-level semaphore if needed.

Change Log (update as we progress)
 - [x] M0 scaffolding committed
 - [x] M1 structured path done
 - [x] M2 extraction done
 - [ ] M3 semantic scoring rolled back (simplified to exact-only)
- [ ] M4 batch + aggregation done
- [ ] M5 docs + ops done
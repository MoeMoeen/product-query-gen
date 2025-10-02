---

```markdown
# Product Query Generator

## 📌 Overview
**Product Query Generator** is a FastAPI-based service that generates **synthetic human-like search queries** for e-commerce products.  
The queries simulate real customer search behavior (short keywords + natural language phrases) and can be used to **evaluate and improve search engine relevance**.  

Queries can be **precomputed and cached** in a database, with **on-demand generation as fallback** for unseen products.

---

## 🏗️ Architecture
- **Input:** List of product objects (JSON).  
- **Process:** Query generation using LLM, organized into **query buckets** (price, occasion, material, fit, etc.).  
- **Output:** List of `{ product_id, queries[] }` mappings.  
- **Mode:** **Precompute + cache with on-demand fallback**.  

---

## 📂 Project Structure
```

app/
main.py          # FastAPI app + routes
config.py        # env settings
schemas.py       # Pydantic models for request/response
prompts.py       # Prompt templates for LLM
services/
generator.py   # Core generation logic
pyproject.toml     # uv project definition
.env               # environment variables
README.md

````

---

## ⚙️ Setup

### Install uv (if not installed)
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
````

### Clone repo

```bash
git clone git@github.com:YOUR_USERNAME/product-query-gen.git
cd product-query-gen
```

### Create environment

```bash
uv venv
source .venv/bin/activate
```

### Install dependencies

```bash
uv add fastapi uvicorn openai python-dotenv
```

### Configure `.env`

```
OPENAI_API_KEY=sk-your-api-key
OPENAI_MODEL=gpt-4o-mini
```

---

## ▶️ Run Service

```bash
uv run uvicorn app.main:app --reload
```

Docs available at:
👉 [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

---

## 📘 API Specification

### Endpoint

`POST /generate`

### Input Schema (`ProductsIn`)

```json
{
  "products": [
    {
      "id": "string",
      "title": "string",
      "description": "string (optional)",
      "price": 0.0,
      "material": "string",
      "size": "string",
      "rating": 0.0
    }
  ]
}
```

### Output Schema (`GeneratedQueriesBatchOut`)

```json
{
  "results": [
    {
      "product_id": "string",
      "queries": [
        {
          "text": "string",
          "style": "short | natural",
          "bucket": "price | occasion | material | fit | brand | rating"
        }
      ]
    }
  ]
}
```

---

## 🛠️ Roadmap

* **Phase 1**: FastAPI service + JSON I/O + LLM generation.
* **Phase 2**: Postgres persistence (SQLAlchemy + Alembic).
* **Phase 3**: Add caching logic:

  * Check DB for precomputed queries.
  * Generate new ones on-demand if missing.
* **Phase 4**: Evaluation pipeline (relevance metrics).
* **Phase 5**: Multi-language queries + other verticals.

---

## 🔑 Key Metadata

* Language: Python 3.11+
* Framework: FastAPI
* Package manager: uv
* Deployment target: container-ready (future)
* Mode: Precompute + cache (with on-demand fallback)

---

## 🤖 Agent Instructions

If you are an AI agent interacting with this project, follow these rules:

### **Project Context**

* This is a **real-world production-grade project**, not a toy.
* It generates **synthetic human-like queries** for fashion & apparel products.
* Used for **evaluating search engine relevance**.

### **Responsibilities**

* Respect the **modular design**:

  * `main.py` → API entrypoint.
  * `schemas.py` → data contracts.
  * `generator.py` → query generation logic.
  * `prompts.py` → LLM prompt templates.
  * `config.py` → environment + client setup.
* Always add new code in the **appropriate layer**, don’t mix concerns.

### **When Extending**

* **New fields in input/output?** → Update `schemas.py`.
* **Change generation logic?** → Update `generator.py` and, if prompts change, update `prompts.py`.
* **Add external service (DB, cache, etc.)?** → Add config in `config.py`.
* **Add new endpoints?** → Define in `main.py`, keep consistent response models.
* **Write migrations?** → Use Alembic when persistence is added (Phase 2).

### **Code Quality**

* Always use **async/await** in API + services.
* Follow **PEP8 + typing** (`List[str]`, not just `list`).
* Keep functions **small and single-purpose**.
* Do not hardcode secrets → always load from `.env` via `config.py`.

### **Testing**

* Write new tests under `/tests` when functionality grows.
* Use pytest + httpx for API tests.
* Mock external LLM calls when unit testing.

### **Deployment**

* Future-ready for containerization.
* Don’t add deployment files (`Dockerfile`, `compose`) unless requested.

---


"""Run a few sample evaluation requests against the live evaluator pipeline.

Requirements:
    - OPENAI_API_KEY set (for unstructured LLM extraction case)
Run:
    uv run python scripts/run_sample_evaluation.py
Produces:
    - app/data/sample_evaluation_report.json (overwritten each run)
"""
from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import Dict, Any, List

from httpx import AsyncClient, ASGITransport

# Try importing the FastAPI app; if running as a raw script without PYTHONPATH,
# add the project root to sys.path and retry. This avoids permanent path hacks.
try:
    from app.main import app  # type: ignore
except ModuleNotFoundError:
    import sys as _sys
    from pathlib import Path as _Path
    _root = _Path(__file__).resolve().parents[1]
    if str(_root) not in _sys.path:
        _sys.path.insert(0, str(_root))
    from app.main import app  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "app" / "data" / "sample_chatbot_responses.json"
REPORT_PATH = ROOT / "app" / "data" / "sample_evaluation_report.json"


def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    # Make evaluator modules verbose
    logging.getLogger("evaluator.extract").setLevel(logging.DEBUG)
    logging.getLogger("evaluator.resolve").setLevel(logging.DEBUG)
    logging.getLogger("evaluator.score").setLevel(logging.DEBUG)
    logging.getLogger("evaluator.pipeline").setLevel(logging.DEBUG)


def load_sample_products() -> List[Dict[str, Any]]:
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def pick_query(product: Dict[str, Any], style: str = "natural") -> str:
    for q in product.get("queries", []):
        if q.get("style") == style:
            return q.get("text")
    # fallback to any query text
    return product.get("queries", [{}])[0].get("text", product.get("title", ""))


def build_requests_for_product(prod: Dict[str, Any]) -> List[Dict[str, Any]]:
    pid = str(prod["id"]) if "id" in prod else ""
    title = prod.get("title", "")
    user_query = pick_query(prod, style="natural")  # richer query

    gt = [{"product_id": pid, "title": title}]  # ground-truth list

    requests: List[Dict[str, Any]] = []
    responses = prod.get("chatbot_responses", {})
    groups = [
        ("structured_correct", True),
        ("structured_incorrect", False),
        ("unstructured_correct", True),
        ("unstructured_incorrect", False),
    ]

    for group_name, expect in groups:
        for idx, answer in enumerate(responses.get(group_name, [])):
            requests.append(
                dict(
                    name=f"{pid} | {group_name}[{idx}]",
                    product_id=pid,
                    product_title=title,
                    group=group_name,
                    index=idx,
                    payload={
                        "query": {"query_id": f"{pid}-{group_name}-{idx}", "query_text": user_query},
                        "ground_truth_products": gt,
                        "chatbot_answer": answer,
                    },
                    expect=expect,
                )
            )
    return requests


def build_report_skeleton(products_count: int) -> Dict[str, Any]:
    return {
        "meta": {
            "timestamp": logging.Formatter.formatTime(logging.Formatter(), record=logging.LogRecord(
                name="", level=0, pathname="", lineno=0, msg="", args=(), exc_info=None
            )),
            "products_count": products_count,
        },
        "summary": {
            "total": 0,
            "passed": 0,
            "failed": 0,
            "by_group": {
                "structured_correct": {"total": 0, "passed": 0, "failed": 0},
                "structured_incorrect": {"total": 0, "passed": 0, "failed": 0},
                "unstructured_correct": {"total": 0, "passed": 0, "failed": 0},
                "unstructured_incorrect": {"total": 0, "passed": 0, "failed": 0},
            },
        },
        "scenarios": [],
    }


def write_report(report: Dict[str, Any]) -> None:
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)


async def main():
    setup_logging()
    products = load_sample_products()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        all_reqs = []
        for prod in products:
            all_reqs.extend(build_requests_for_product(prod))

        print(f"Running {len(all_reqs)} scenarios across {len(products)} products...\n")

        report = build_report_skeleton(products_count=len(products))
        ok = 0
        for r in all_reqs:
            name = r["name"]
            payload = r["payload"]
            expect = r["expect"]
            group = r["group"]
            product_id = r["product_id"]
            product_title = r["product_title"]
            idx = r["index"]

            resp = await client.post("/evaluate/answer", json=payload)
            resp.raise_for_status()
            data = resp.json()
            matched = data.get("matched", False)
            labels = data.get("labels", [])
            details = {k: len(v) for k, v in data.get("details", {}).items()}

            verdict = "PASS" if matched == expect else "FAIL"
            if verdict == "PASS":
                ok += 1

            print(
                f"[{verdict}] {name} -> matched={matched} expect={expect} labels={labels} details={details}"
            )

            # Update report
            report["summary"]["total"] += 1
            report["summary"]["by_group"][group]["total"] += 1
            if verdict == "PASS":
                report["summary"]["passed"] += 1
                report["summary"]["by_group"][group]["passed"] += 1
            else:
                report["summary"]["failed"] += 1
                report["summary"]["by_group"][group]["failed"] += 1

            scenario_entry = {
                "name": name,
                "product_id": product_id,
                "product_title": product_title,
                "group": group,
                "index": idx,
                "expect": expect,
                "result": {
                    "matched": matched,
                    "labels": labels,
                    "details": details,
                },
                "request": {
                    "query": payload.get("query"),
                    "ground_truth_products": payload.get("ground_truth_products"),
                    "chatbot_answer": payload.get("chatbot_answer"),
                },
            }
            report["scenarios"].append(scenario_entry)

        # Persist report (overwrite each run)
        write_report(report)
        print(f"\nSummary: {ok}/{len(all_reqs)} scenarios passed")
        print(f"Report written to: {REPORT_PATH}")


if __name__ == "__main__":
    asyncio.run(main())

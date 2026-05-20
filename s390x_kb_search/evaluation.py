"""Search quality evaluation framework."""
from __future__ import annotations

import json
import logging
from typing import Any

from s390x_kb_search.resources import SearchResources
from s390x_kb_search.search import hybrid_search

logger = logging.getLogger(__name__)


def evaluate_search(
    eval_questions: list[dict[str, Any]],
    resources: SearchResources,
    k: int = 5,
) -> dict[str, Any]:
    hit_at_1 = 0
    hit_at_3 = 0
    hit_at_5 = 0
    mrr_sum = 0.0
    evaluated = 0

    results_detail = []

    for q in eval_questions:
        expected_urls = q.get("expected_urls", [])
        if not expected_urls:
            continue

        question = q["question"]
        search_results = hybrid_search(question, resources, k=k)
        result_urls = [r.get("url", "") for r in search_results]

        first_hit_rank = None
        for rank, url in enumerate(result_urls, 1):
            if url in expected_urls:
                first_hit_rank = rank
                break

        if first_hit_rank is not None:
            if first_hit_rank <= 1:
                hit_at_1 += 1
            if first_hit_rank <= 3:
                hit_at_3 += 1
            if first_hit_rank <= 5:
                hit_at_5 += 1
            mrr_sum += 1.0 / first_hit_rank

        evaluated += 1
        results_detail.append({
            "id": q["id"],
            "question": question,
            "expected_urls": expected_urls,
            "result_urls": result_urls[:5],
            "first_hit_rank": first_hit_rank,
        })

    if evaluated == 0:
        return {"error": "No questions with expected URLs to evaluate"}

    return {
        "total_questions": len(eval_questions),
        "evaluated": evaluated,
        "hit_at_1": round(hit_at_1 / evaluated, 4),
        "hit_at_3": round(hit_at_3 / evaluated, 4),
        "hit_at_5": round(hit_at_5 / evaluated, 4),
        "mrr": round(mrr_sum / evaluated, 4),
        "details": results_detail,
    }


def run_evaluation(
    eval_questions_path: str,
    resources: SearchResources,
    k: int = 5,
) -> dict[str, Any]:
    with open(eval_questions_path) as f:
        questions = json.load(f)

    results = evaluate_search(questions, resources, k=k)

    logger.info("Evaluation results:")
    logger.info("  Hit@1: %.4f", results["hit_at_1"])
    logger.info("  Hit@3: %.4f", results["hit_at_3"])
    logger.info("  Hit@5: %.4f", results["hit_at_5"])
    logger.info("  MRR:   %.4f", results["mrr"])

    return results
